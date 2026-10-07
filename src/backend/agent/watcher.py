"""
Theo dõi job huấn luyện - phần CHẠY BẰNG CODE của Operation Agent.

Train mất từ vài phút tới hàng giờ, nên không thể bắt LLM ngồi hỏi "xong chưa".
Sau khi start_training trả job_id, một thread nền hỏi get_job_info định kỳ tới
khi status ≠ 0 (mũi tên "theo dõi job" trong sơ đồ), rồi:

  1. Kiểm định kết quả so với ràng buộc trong R (vd "accuracy ≥ 0.9") - bằng
     code, không tốn token.
  2. Phát sự kiện ra frontend (SSE) và ghi vào phiên chat, để lượt chat kế tiếp
     Agent Manager biết job đã xong mà không phải hỏi lại backend.

Mỗi lần hỏi chỉ một request (/get-list-job-by-userId) và không gọi LLM.
"""

# Standard libraries
import os
import threading
import time

# Local modules
from agent import tools, tracing


DEFAULT_POLL_SECONDS = 20
# Backend dùng 3600 giây khi config không có max_time (automl/v2/master.py).
_BACKEND_DEFAULT_MAX_TIME = 3600
# Ngoài max_time, job còn phải xếp hàng Kafka và gộp kết quả các worker.
_GRACE_SECONDS = 15 * 60

# Metric "càng nhỏ càng tốt". Nguồn: ERROR_METRICS trong automl/v2/master.py.
LOWER_IS_BETTER = {"mse", "mae", "mape", "rmse", "log_loss"}

_OPS = {
    ">=": lambda score, value: score >= value,
    ">": lambda score, value: score > value,
    "<=": lambda score, value: score <= value,
    "<": lambda score, value: score < value,
}


def poll_seconds() -> float:
    raw = os.getenv("AGENT_JOB_POLL_SECONDS", "").strip()
    try:
        return max(2.0, float(raw)) if raw else DEFAULT_POLL_SECONDS
    except ValueError:
        return DEFAULT_POLL_SECONDS


def job_score(job: dict, metric: str) -> float | None:
    """
    Điểm của model tốt nhất theo một metric.

    best_score chỉ là điểm theo metric_sort. Metric khác phải tìm trong
    orther_model_scores (tên trường backend viết sai chính tả, giữ nguyên).
    """
    metric = (metric or "").strip().lower()
    config = job.get("config") or {}
    if metric == (config.get("metric_sort") or "").strip().lower():
        score = job.get("best_score")
        return float(score) if isinstance(score, (int, float)) else None

    for entry in job.get("orther_model_scores") or []:
        if entry.get("model_name") == job.get("best_model"):
            score = (entry.get("scores") or {}).get(metric)
            return float(score) if isinstance(score, (int, float)) else None
    return None


def verify_result(job: dict, requirements: dict | None) -> dict:
    """
    Kiểm định kết quả job theo ràng buộc người dùng đặt ra trong R.problem.constraints.

    Returns:
        {"passed": True | False | None, "checks": [...]}. None nghĩa là không có
        ràng buộc nào kiểm được - KHÔNG phải trượt.
    """
    constraints = ((requirements or {}).get("problem") or {}).get("constraints") or []
    checks = []

    for constraint in constraints:
        metric = constraint.get("metric")
        op = constraint.get("op")
        value = constraint.get("value")
        score = job_score(job, metric)

        check = {"metric": metric, "op": op, "value": value, "score": score}
        if score is None or op not in _OPS or not isinstance(value, (int, float)):
            check["passed"] = None
            check["note"] = "Job không có điểm cho metric này."
        else:
            check["passed"] = _OPS[op](score, value)
        checks.append(check)

    judged = [c["passed"] for c in checks if c["passed"] is not None]
    return {"passed": all(judged) if judged else None, "checks": checks}


def summarize_job(job: dict, requirements: dict | None = None) -> dict:
    config = job.get("config") or {}
    summary = {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "dataset": (job.get("data") or {}).get("name"),
        "metric_sort": config.get("metric_sort"),
    }
    if job.get("status") == 1:
        summary.update({
            "best_model": job.get("best_model"),
            "best_score": job.get("best_score"),
            "best_params": job.get("best_params"),
            "time_limit_reached": job.get("time_limit_reached"),
            "verification": verify_result(job, requirements),
        })
    elif job.get("status") == -1:
        summary["error"] = job.get("infor")
    return summary


class JobWatcher:
    """
    Mỗi job một thread daemon. Dừng khi job xong, hết hạn chờ, hoặc phiên đóng.

    Token người dùng chỉ sống 15 phút (ACCESS_EXPIRE) trong khi job có thể chạy
    hàng giờ. Gặp 401 thì KHÔNG bỏ cuộc: frontend gửi token mới mỗi lần gọi
    agent, server gán lại vào cùng client, lần hỏi sau sẽ qua.
    """

    def __init__(self, api, emit, on_finish, poll: float | None = None) -> None:
        self._api = api
        self._emit = emit
        self._on_finish = on_finish
        self._poll = poll or poll_seconds()
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def watch(
        self,
        job_id: str,
        max_time: int | None = None,
        requirements: dict | None = None,
        trace_context: dict | None = None,
    ) -> bool:
        """
        Bắt đầu theo dõi. Trả False nếu job này đang được theo dõi rồi.

        trace_context: vị trí trong trace Langfuse của tool đã tạo job (xem
            tracing.current_context) - sự kiện job được ghi làm con của nó,
            nên mở trace là thấy cả lúc tạo lẫn lúc xong.
        """
        with self._lock:
            thread = self._threads.get(job_id)
            if thread is not None and thread.is_alive():
                return False

            deadline = time.time() + (max_time or _BACKEND_DEFAULT_MAX_TIME) + _GRACE_SECONDS
            thread = threading.Thread(
                target=self._run,
                args=(job_id, deadline, requirements, trace_context),
                name=f"job-watch-{job_id[:8]}",
                daemon=True,
            )
            self._threads[job_id] = thread
            thread.start()

        self._emit("job_watch", agent="operation-agent", job_id=job_id, deadline=deadline)
        return True

    def active(self) -> list[str]:
        with self._lock:
            return [job_id for job_id, thread in self._threads.items() if thread.is_alive()]

    def stop(self) -> None:
        self._stopped.set()

    def _run(self, job_id: str, deadline: float, requirements: dict | None, trace_context: dict | None = None) -> None:
        def emit(type: str, level: str | None = None, **data) -> None:
            self._emit(type, agent="operation-agent", **data)
            tracing.log_event(type, trace_context, data, level=level)

        started = time.time()
        last_status = None
        auth_warned = False

        while not self._stopped.is_set():
            job, problem = tools.find_own_job(self._api, job_id)

            if problem is None:
                auth_warned = False
                status = job.get("status")
                if status != last_status:
                    emit(
                        "job_status",
                        job_id=job_id,
                        status=status,
                        elapsed=round(time.time() - started),
                    )
                    last_status = status

                if status in (1, -1):
                    summary = summarize_job(job, requirements)
                    failed = status != 1 or (summary.get("verification") or {}).get("passed") is False
                    emit("job_done" if status == 1 else "job_failed", level="WARNING" if failed else None, **summary)
                    self._on_finish(summary)
                    return

            elif problem.get("status_code") == 404:
                # Job không còn trong danh sách của người dùng: bị xoá hoặc ID sai.
                summary = {"job_id": job_id, "status": None, "error": problem.get("error")}
                emit("job_failed", level="ERROR", **summary)
                self._on_finish(summary)
                return

            elif problem.get("status_code") in (401, 403) and not auth_warned:
                emit(
                    "job_watch_warning",
                    level="WARNING",
                    job_id=job_id,
                    error="Phiên đăng nhập hết hạn, sẽ thử lại khi có token mới.",
                )
                auth_warned = True
            # Lỗi khác (mất mạng, backend khởi động lại) coi là tạm thời: hỏi lại sau.

            if time.time() >= deadline:
                summary = {
                    "job_id": job_id,
                    "status": last_status,
                    "error": "Quá thời gian chờ mà job chưa kết thúc. Hỏi lại sau để xem trạng thái.",
                }
                emit("job_watch_timeout", level="WARNING", **summary)
                self._on_finish(summary)
                return

            self._stopped.wait(self._poll)
