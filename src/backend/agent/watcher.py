"""
Theo dõi job huấn luyện - phần CHẠY BẰNG CODE của Operation Agent.

Train mất từ vài phút tới hàng giờ, nên không thể bắt LLM ngồi hỏi "xong chưa".
Sau khi start_training trả job_id, một thread nền hỏi get_job_info định kỳ tới
khi status ≠ 0 (mũi tên "theo dõi job" trong sơ đồ), rồi:

  1. Kiểm định kết quả so với ràng buộc trong R (vd "accuracy ≥ 0.9") - bằng
     code, không tốn token.
  2. Phát sự kiện ra frontend (SSE) và ghi vào phiên chat, để lượt chat kế tiếp
     Agent Manager biết job đã xong mà không phải hỏi lại backend.

Mỗi lần hỏi chỉ đọc danh sách job (GET /inference/jobs) và không gọi LLM.
"""

# Standard libraries
import logging
import os
import threading
import time

# Local modules
from agent import tools, tracing


_log = logging.getLogger("agent.watcher")

DEFAULT_POLL_SECONDS = 20
# Config không có timeout thì backend chạy tới khi mọi model xong, không giới
# hạn. Watcher vẫn phải có hạn để thread không sống mãi.
_BACKEND_DEFAULT_MAX_TIME = 4 * 60 * 60
# Ngoài max_time, job còn phải xếp hàng Kafka và gộp kết quả các worker.
_GRACE_SECONDS = 15 * 60

# Metric "càng nhỏ càng tốt". Nguồn: LOWER_IS_BETTER_METRICS trong
# src/core/constants.py của backend.
LOWER_IS_BETTER = {"mse", "mae", "mape", "rmse"}

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


def _round(scores: dict) -> dict:
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in (scores or {}).items()}


def summarize_job(job: dict, requirements: dict | None = None) -> dict:
    """
    Tóm tắt kết quả job cho Manager và frontend.

    PHẢI kèm điểm đầy đủ: best_score chỉ là điểm theo metric_sort, các metric
    khác (precision, recall, f1...) nằm trong orther_model_scores. Thiếu phần này
    thì agent kết luận sai là "hệ thống không có các chỉ số khác".
    """
    config = job.get("config") or {}
    metric = (config.get("metric_sort") or "").strip().lower()
    summary = {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "dataset": (job.get("data") or {}).get("name"),
        "metric_sort": config.get("metric_sort"),
    }
    if job.get("status") == 1:
        entries = job.get("orther_model_scores") or []
        best = next((e for e in entries if e.get("model_name") == job.get("best_model")), {})
        # Xếp hạng theo metric_sort; metric sai số thì nhỏ hơn là tốt hơn.
        ranked = sorted(
            (e for e in entries if isinstance((e.get("scores") or {}).get(metric), (int, float))),
            key=lambda e: e["scores"][metric],
            reverse=metric not in LOWER_IS_BETTER,
        )
        summary.update({
            "best_model": job.get("best_model"),
            "best_score": job.get("best_score"),
            "best_model_scores": _round(best.get("scores")),
            "leaderboard": [
                {"model": e.get("model_name"), metric: round(e["scores"][metric], 4)} for e in ranked
            ],
            "best_params": job.get("best_params"),
            # Hết max_time thì model chưa xong bị huỷ: số model ít hơn danh mục
            # nghĩa là bảng xếp hạng chưa đủ.
            "models_scored": len(entries),
            "not_available": "Backend không lưu ma trận nhầm lẫn hay đường ROC - chỉ có các metric trong best_model_scores.",
        })
        # Chỉ kèm kiểm định khi người dùng có đặt ràng buộc - không thì agent
        # dễ diễn giải "checks rỗng" thành "chưa kiểm định được".
        verification = verify_result(job, requirements)
        if verification["checks"]:
            summary["verification"] = verification
    elif job.get("status") == tools.JOB_CANCELLED:
        summary["error"] = job.get("infor") or "Job đã bị huỷ."
        summary["cancelled"] = True
    elif job.get("status") == tools.JOB_FAILED:
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

        state = {"started": time.time(), "last_status": None, "warned": None}

        while not self._stopped.is_set():
            # Bọc cả lần hỏi: một lỗi ngoài dự kiến (bản ghi job dị dạng, client
            # đã đóng...) không được giết thread trong im lặng - thread chết thì
            # job biến khỏi active() và người dùng không bao giờ được báo.
            try:
                if self._poll_once(job_id, requirements, emit, state):
                    return
            except Exception:  # noqa: BLE001
                _log.exception("theo dõi job %s lỗi", job_id)
                self._warn(emit, state, job_id, "error", "Lỗi tạm thời khi theo dõi job, sẽ thử lại.")

            if time.time() >= deadline:
                summary = {
                    "job_id": job_id,
                    "status": state["last_status"],
                    "error": "Quá thời gian chờ mà job chưa kết thúc. Hỏi lại sau để xem trạng thái.",
                }
                emit("job_watch_timeout", level="WARNING", **summary)
                self._finish(summary)
                return

            self._stopped.wait(self._poll)

    @staticmethod
    def _warn(emit, state: dict, job_id: str, kind: str, error: str) -> None:
        """Báo một lần cho mỗi đợt lỗi; lần hỏi thành công sau đó phát job_watch_resumed."""
        if state["warned"] == kind:
            return
        emit("job_watch_warning", level="WARNING", job_id=job_id, error=error)
        state["warned"] = kind

    def _finish(self, summary: dict) -> None:
        try:
            self._on_finish(summary)
        except Exception:  # noqa: BLE001 - lỗi ghi sự kiện không được làm treo thread
            _log.exception("on_finish lỗi cho job %s", summary.get("job_id"))

    def _poll_once(self, job_id: str, requirements: dict | None, emit, state: dict) -> bool:
        """Hỏi trạng thái job một lần. True khi việc theo dõi đã kết thúc."""
        job, problem = tools.find_own_job(self._api, job_id)

        if problem is None:
            if state["warned"]:
                emit("job_watch_resumed", job_id=job_id)
                state["warned"] = None
            status = job.get("status")
            if status != state["last_status"]:
                emit(
                    "job_status",
                    job_id=job_id,
                    status=status,
                    elapsed=round(time.time() - state["started"]),
                )
                state["last_status"] = status

            if status in tools.JOB_FINISHED:
                try:
                    summary = summarize_job(job, requirements)
                except Exception:  # noqa: BLE001 - bản ghi dị dạng: vẫn phải báo job đã xong
                    _log.exception("tóm tắt job %s lỗi", job_id)
                    summary = {"job_id": job_id, "status": status, "error": job.get("infor")}
                if status == tools.JOB_SUCCESS and wants_deploy(requirements):
                    summary["activation"] = self._activate(job_id, summary)
                failed = status != tools.JOB_SUCCESS or (summary.get("verification") or {}).get("passed") is False
                emit("job_done" if status == tools.JOB_SUCCESS else "job_failed", level="WARNING" if failed else None, **summary)
                self._finish(summary)
                return True
            return False

        if problem.get("status_code") == 404:
            # Job không còn trong danh sách của người dùng: bị xoá hoặc ID sai.
            summary = {"job_id": job_id, "status": None, "error": problem.get("error")}
            emit("job_failed", level="ERROR", **summary)
            self._finish(summary)
            return True

        if problem.get("status_code") in (401, 403):
            self._warn(emit, state, job_id, "auth", "Phiên đăng nhập hết hạn, sẽ thử lại khi có token mới.")
        # Lỗi khác (mất mạng, backend khởi động lại) coi là tạm thời: hỏi lại sau.
        return False

    def _activate(self, job_id: str, summary: dict) -> dict:
        """
        Người dùng đã dặn "train xong kích hoạt luôn" (R.service.deploy): kích hoạt
        ngay khi job xong, không chờ lượt chat sau. Job không đạt ràng buộc người
        dùng đặt ra thì KHÔNG kích hoạt - để người dùng quyết.
        """
        if (summary.get("verification") or {}).get("passed") is False:
            return {
                "ok": False,
                "skipped": True,
                "error": "Không tự kích hoạt vì kết quả không đạt ràng buộc người dùng đặt ra.",
            }
        try:
            result = tools.activate_model(self._api, job_id)
        except Exception as error:  # noqa: BLE001
            _log.exception("tự kích hoạt job %s lỗi", job_id)
            return {"ok": False, "error": f"Lỗi nội bộ khi kích hoạt ({type(error).__name__})."}
        if not result.get("ok"):
            return {"ok": False, "error": str(result.get("error") or "Không kích hoạt được.")}
        return {"ok": True, "endpoint_url": result.get("endpoint_url")}


def wants_deploy(requirements: dict | None) -> bool:
    """R.service.deploy: người dùng muốn dùng model ngay sau khi train."""
    value = ((requirements or {}).get("service") or {}).get("deploy")
    return value is True or str(value).strip().lower() == "true"
