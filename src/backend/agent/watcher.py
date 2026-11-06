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
from agent.agent_openai import log_exception


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

    # False nếu có ràng buộc trượt; True chỉ khi MỌI ràng buộc đạt; còn lại (có ràng buộc không
    # kiểm được) là None - "chưa kiểm đủ", không phải "đạt hết".
    results = [c["passed"] for c in checks]
    if any(result is False for result in results):
        passed = False
    elif results and all(result is True for result in results):
        passed = True
    else:
        passed = None
    return {"passed": passed, "checks": checks}


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
        # Frontend cần hai trường này để dựng form dự đoán đúng loại (time_series) và
        # lấy kiểu cột của dataset, kể cả khi không thấy sự kiện job_started.
        "dataset_id": (job.get("data") or {}).get("id"),
        "problem_type": config.get("problem_type"),
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
        # job_id -> trạng thái tự kích hoạt model khi job xong:
        #   "pending"    sẽ kích hoạt khi job xong (nếu đạt ràng buộc)
        #   "cancelled"  người dùng đã huỷ
        #   "activating" đang kích hoạt (đã nhận việc - huỷ lúc này bị từ chối)
        #   "done"       đã xử lý xong lời hứa (kích hoạt, hoặc bỏ vì không đạt / job hỏng / bị xoá)
        #   "expired"    hết giờ theo dõi trước khi job xong - lời hứa HẾT HIỆU LỰC
        #   "off"        không ai yêu cầu
        # Đặt MỘT lần khi bắt đầu theo dõi job lần đầu; theo dõi lại không tính lại từ R - lựa
        # chọn huỷ của người dùng không được bị ghi đè. Lời hứa chỉ sống khi watcher còn theo
        # dõi job: không có đường nào kích hoạt "về sau" mà người dùng không thấy / không huỷ được.
        self._auto: dict[str, str] = {}
        # R lúc hứa: ràng buộc để kiểm khi kích hoạt (reset phiên không làm mất nó).
        self._promise_requirements: dict[str, dict | None] = {}
        # Điều kiện người dùng nêu khi BẬT tự kích hoạt lúc job đang chạy ("đạt accuracy >= 0.9
        # thì kích hoạt"): cộng vào ràng buộc của R (thay ràng buộc cùng metric), dùng cả khi
        # kiểm định kết quả lẫn khi quyết định kích hoạt - không thì kích hoạt bất kể điểm.
        self._added_constraints: dict[str, list[dict]] = {}
        # Trạng thái trước khi hết giờ theo dõi (off / cancelled): theo dõi lại thì khôi phục -
        # chỉ lời hứa đang chờ (pending) mới thật sự hết hiệu lực.
        self._before_expiry: dict[str, str] = {}
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def watch(
        self,
        job_id: str,
        max_time: int | None = None,
        requirements: dict | None = None,
        trace_context: dict | None = None,
        dataset_id: str | None = None,
        problem_type: str | None = None,
        auto_activate: bool | None = None,
    ) -> bool:
        """
        Bắt đầu theo dõi. Trả False nếu job này đang được theo dõi rồi.

        dataset_id / problem_type chỉ để gắn vào sự kiện job_watch cho frontend.
        auto_activate: tự kích hoạt model khi xong; None = theo R.service.deploy.

        trace_context: vị trí trong trace Langfuse của tool đã tạo job (xem
            tracing.current_context) - sự kiện job được ghi làm con của nó,
            nên mở trace là thấy cả lúc tạo lẫn lúc xong.
        """
        with self._lock:
            thread = self._threads.get(job_id)
            if thread is not None and thread.is_alive():
                return False
            # Theo dõi lại mà không có R (vd sau khi reset phiên): kiểm định theo R lúc hứa.
            if requirements is None:
                requirements = self._promise_requirements.get(job_id)

            deadline = time.time() + (max_time or _BACKEND_DEFAULT_MAX_TIME) + _GRACE_SECONDS
            thread = threading.Thread(
                target=self._run,
                args=(job_id, deadline, requirements, trace_context),
                name=f"job-watch-{job_id[:8]}",
                daemon=True,
            )
            self._threads[job_id] = thread
            if job_id not in self._auto:
                wanted = wants_deploy(requirements) if auto_activate is None else bool(auto_activate)
                self._auto[job_id] = "pending" if wanted else "off"
                self._promise_requirements[job_id] = requirements
            elif self._auto[job_id] == "expired" and self._before_expiry.get(job_id) in ("off", "cancelled"):
                self._auto[job_id] = self._before_expiry.pop(job_id)
            elif self._auto[job_id] == "expired":
                # Lời hứa đang chờ đã hết hiệu lực khi hết giờ: theo dõi lại KHÔNG tự sống lại ("off"),
                # nhưng người dùng yêu cầu lại thì bật được (team.watch_job đặt mốc cho lời mới).
                self._auto[job_id] = "off"
            # Phát job_watch TRƯỚC khi thread chạy: thread có thể phát ngay job_watch_warning /
            # job_status, và frontend phải thấy "bắt đầu theo dõi" trước mọi sự kiện của job.
            self._emit(
                "job_watch", agent="operation-agent", job_id=job_id, deadline=deadline,
                dataset_id=dataset_id, problem_type=problem_type, auto_activate=self._auto[job_id] == "pending",
                auto_activate_constraints=self._constraints_locked(job_id),
            )
            thread.start()
        return True

    def auto_activate(self, job_id: str) -> bool:
        """Job này còn lời hứa tự kích hoạt chưa thực hiện."""
        with self._lock:
            return self._auto.get(job_id) == "pending"

    def auto_state(self, job_id: str) -> str:
        """pending | cancelled | activating | done | expired | off (job chưa từng theo dõi: off)."""
        with self._lock:
            return self._auto.get(job_id, "off")

    def auto_activate_constraints_map(self) -> dict[str, list[dict]]:
        """job_id đang theo dõi còn lời hứa -> điều kiện sẽ kiểm (rỗng = kích hoạt bất kể điểm)."""
        with self._lock:
            return {
                job_id: self._constraints_locked(job_id)
                for job_id, thread in self._threads.items()
                if thread.is_alive() and self._auto.get(job_id) == "pending"
            }

    def auto_activate_map(self) -> dict[str, bool]:
        """job_id đang theo dõi -> còn lời hứa tự kích hoạt không (cho hello / reconnect)."""
        with self._lock:
            return {
                job_id: self._auto.get(job_id) == "pending"
                for job_id, thread in self._threads.items()
                if thread.is_alive()
            }

    def set_auto_activate(self, job_id: str, enabled: bool, constraints: list[dict] | None = None) -> str:
        """
        Bật/tắt tự kích hoạt cho một job ĐANG được theo dõi (người dùng đổi ý sau khi job đã
        chạy: nút trên thẻ job, hoặc tool set_auto_activate của Operation Agent).

        constraints (chỉ khi bật): điều kiện người dùng vừa nêu, đã chuẩn hoá - cộng vào ràng
        buộc được kiểm lúc job xong (thay ràng buộc cùng metric).

        Returns:
            "ok" | "not_watched" (job không còn được theo dõi) | "in_progress" (đang kích
            hoạt) | "finished" (lời hứa đã xử lý xong hoặc đã hết hiệu lực).
        """
        with self._lock:
            thread = self._threads.get(job_id)
            if thread is None or not thread.is_alive():
                return "not_watched"
            state = self._auto.get(job_id)
            if state == "activating":
                return "in_progress"
            if state in ("done", "expired"):
                return "finished"
            self._auto[job_id] = "pending" if enabled else "cancelled"
            if enabled and constraints:
                self._added_constraints[job_id] = _merge_constraints(self._added_constraints.get(job_id) or [], constraints)
            # Phát trong khoá: thứ tự sự kiện khớp thứ tự đổi trạng thái.
            self._emit(
                "auto_activate_changed", agent="operation-agent", job_id=job_id, enabled=bool(enabled),
                auto_activate_constraints=self._constraints_locked(job_id),
            )
        return "ok"

    def activate_promised(self, job_id: str, summary: dict, job: dict | None = None) -> dict | None:
        """
        Thực hiện lời hứa tự kích hoạt của job (đúng MỘT lần): None nếu không có lời hứa nào
        đang chờ (không yêu cầu, đã huỷ, đã làm, hết hiệu lực). Nhận việc trong khoá
        (pending -> activating), nên huỷ đúng lúc job xong bị từ chối rõ ràng thay vì "ok" mà
        vẫn kích hoạt. Không có lời hứa thì chốt luôn trạng thái cuối trong CÙNG khoá - một lần
        bật lọt vào ngay sau đó sẽ bị từ chối ("finished") thay vì "ok" rồi bị bỏ im lặng.

        job: bản ghi job - kiểm định lại theo đúng R vừa nhận việc và ghi vào summary, để điều
        hiện cho người dùng và điều quyết định kích hoạt là một.
        """
        with self._lock:
            state = self._auto.get(job_id)
            if state != "pending":
                if state in ("cancelled", "off", None):
                    self._auto[job_id] = "done"
                return None
            self._auto[job_id] = "activating"
            requirements = self._with_added(job_id, self._promise_requirements.get(job_id))
        if job is not None and "summary_error" not in summary:
            # Như summarize_job: chỉ kèm "verification" khi CÓ ràng buộc (không có = "không đặt ràng
            # buộc nào", không phải "chưa kiểm đủ").
            summary.pop("verification", None)
            try:
                verification = verify_result(job, requirements)
                if verification["checks"]:
                    summary["verification"] = verification
            except Exception:  # noqa: BLE001 - không kiểm được: activate_if_allowed từ chối (có ràng buộc mà không có kết quả kiểm)
                log_exception(_log, "kiểm định lại job %s lỗi", job_id)
                if ((requirements or {}).get("problem") or {}).get("constraints"):
                    summary["summary_error"] = "Không kiểm định được kết quả job theo ràng buộc người dùng đặt."
        try:
            return self.activate_if_allowed(job_id, summary, requirements)
        finally:
            with self._lock:
                self._auto[job_id] = "done"

    def checked_constraints(self, job_id: str) -> list[dict]:
        """Các ràng buộc sẽ được kiểm khi job xong (R lúc hứa + điều kiện thêm sau)."""
        with self._lock:
            return self._constraints_locked(job_id)

    def _constraints_locked(self, job_id: str) -> list[dict]:
        """checked_constraints khi đang giữ self._lock (khoá không vào lại được)."""
        requirements = self._with_added(job_id, self._promise_requirements.get(job_id))
        return [dict(c) for c in ((requirements or {}).get("problem") or {}).get("constraints") or []]

    def _with_added(self, job_id: str, requirements: dict | None) -> dict | None:
        """R kèm điều kiện thêm sau của job (gọi khi đang giữ self._lock)."""
        added = self._added_constraints.get(job_id)
        if not added:
            return requirements
        requirements = dict(requirements or {})
        problem = dict(requirements.get("problem") or {})
        problem["constraints"] = _merge_constraints(problem.get("constraints") or [], added)
        requirements["problem"] = problem
        return requirements

    def requirements_now(self, job_id: str, requirements: dict | None) -> dict | None:
        """R để kiểm định kết quả lúc job xong: R của lần theo dõi + điều kiện thêm sau."""
        with self._lock:
            return self._with_added(job_id, requirements)

    def drop_promise(self, job_id: str, state: str = "done") -> bool:
        """
        Kết thúc việc theo dõi: mọi trạng thái chưa cuối (pending / cancelled / off) thành
        trạng thái cuối (job xong / hỏng / bị xoá: done; hết giờ theo dõi: expired) - không
        bật lại được trong lúc thread đang dừng. True nếu một lời hứa ĐANG chờ bị bỏ.
        """
        with self._lock:
            previous = self._auto.get(job_id)
            if previous in ("pending", "cancelled", "off", None):
                self._auto[job_id] = state
                if state == "expired" and previous in ("cancelled", "off"):
                    self._before_expiry[job_id] = previous
            return previous == "pending"

    def active(self) -> list[str]:
        with self._lock:
            return [job_id for job_id, thread in self._threads.items() if thread.is_alive()]

    def stop(self) -> None:
        self._stopped.set()

    def _run(self, job_id: str, deadline: float, requirements: dict | None, trace_context: dict | None = None) -> None:
        def emit(type: str, level: str | None = None, with_auto: bool = False, **data) -> None:
            if with_auto:
                # Chụp trạng thái tự kích hoạt và phát TRONG khoá (như set_auto_activate): một lần huỷ
                # chen giữa không bị sự kiện mang trạng thái cũ (seq lớn hơn) che lại trên thẻ job.
                with self._lock:
                    data["auto_activate"] = self._auto.get(job_id) == "pending"
                    data["auto_activate_constraints"] = self._constraints_locked(job_id)
                    self._emit(type, agent="operation-agent", **data)
            else:
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
                log_exception(_log, "theo dõi job %s lỗi", job_id)
                self._warn(emit, state, job_id, "error", "Lỗi tạm thời khi theo dõi job, sẽ thử lại.")

            if time.time() >= deadline:
                summary = {
                    "job_id": job_id,
                    "status": state["last_status"],
                    "error": "Quá thời gian chờ mà job chưa kết thúc. Hỏi lại sau để xem trạng thái.",
                }
                if self.drop_promise(job_id, "expired"):
                    # Đã hứa tự kích hoạt mà thôi theo dõi: lời hứa hết hiệu lực - nói rõ là CHƯA
                    # kích hoạt và sẽ không tự kích hoạt về sau (người dùng kích hoạt thủ công).
                    summary["auto_activate_skipped"] = True
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
            log_exception(_log, "on_finish lỗi cho job %s", summary.get("job_id"))

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
                    # Kèm trạng thái tự kích hoạt hiện tại (auto_activate + điều kiện): thẻ job dựng lại
                    # được kể cả khi job_started / job_watch đã trôi khỏi bộ đệm sự kiện.
                    with_auto=True,
                )
                state["last_status"] = status

            if status in tools.JOB_FINISHED:
                try:
                    summary = summarize_job(job, self.requirements_now(job_id, requirements))
                except Exception:  # noqa: BLE001 - bản ghi dị dạng: vẫn phải báo job đã xong
                    log_exception(_log, "tóm tắt job %s lỗi", job_id)
                    summary = {
                        "job_id": job_id,
                        "status": status,
                        "error": job.get("infor"),
                        # Không đọc được kết quả - KHÔNG phải "không có ràng buộc" hay "thiếu điểm".
                        "summary_error": "Không đọc được kết quả chi tiết của job (bản ghi dị dạng).",
                    }
                if status == tools.JOB_SUCCESS:
                    activation = self.activate_promised(job_id, summary, job)
                    if activation is not None:
                        summary["activation"] = activation
                self.drop_promise(job_id)
                failed = status != tools.JOB_SUCCESS or (summary.get("verification") or {}).get("passed") is False
                emit("job_done" if status == tools.JOB_SUCCESS else "job_failed", level="WARNING" if failed else None, **summary)
                self._finish(summary)
                return True
            return False

        if problem.get("status_code") == 404:
            # Job không còn trong danh sách của người dùng: bị xoá hoặc ID sai.
            self.drop_promise(job_id)
            summary = {"job_id": job_id, "status": None, "error": problem.get("error")}
            emit("job_failed", level="ERROR", **summary)
            self._finish(summary)
            return True

        if problem.get("status_code") in (401, 403):
            self._warn(emit, state, job_id, "auth", "Phiên đăng nhập hết hạn, sẽ thử lại khi có token mới.")
        # Lỗi khác (mất mạng, backend khởi động lại) coi là tạm thời: hỏi lại sau.
        return False

    def activate_if_allowed(self, job_id: str, summary: dict, requirements: dict | None) -> dict:
        """
        Người dùng đã dặn "train xong kích hoạt luôn" (R.service.deploy): kích hoạt
        ngay khi job xong, không chờ lượt chat sau. Job không đạt ràng buộc người
        dùng đặt ra thì KHÔNG kích hoạt - để người dùng quyết.
        """
        # Mọi ràng buộc phải ĐẠT thật. passed của verify_result bỏ qua ràng buộc không
        # kiểm được (job không có điểm cho metric đó), nên không dùng nó ở đây.
        checks = (summary.get("verification") or {}).get("checks") or []
        if any(check.get("passed") is False for check in checks):
            return {
                "ok": False,
                "skipped": True,
                "error": "Không tự kích hoạt vì kết quả không đạt ràng buộc người dùng đặt ra.",
            }
        unchecked = [str(check.get("metric")) for check in checks if check.get("passed") is not True]
        # Có ràng buộc mà không có kết quả kiểm định nào (tóm tắt job lỗi vì bản ghi dị
        # dạng): chưa ràng buộc nào được kiểm - không được coi như đạt.
        constraints = ((requirements or {}).get("problem") or {}).get("constraints") or []
        # Ràng buộc của lời hứa mà bản kiểm định không có (kiểm theo R khác): cũng là chưa kiểm.
        checked_metrics = {str(check.get("metric")) for check in checks}
        unchecked += sorted({str(c.get("metric")) for c in constraints} - checked_metrics)
        if constraints and not checks:
            return {
                "ok": False,
                "skipped": True,
                "error": "Không tự kích hoạt vì không đọc được kết quả job để kiểm định ràng buộc người dùng đặt ra.",
            }
        if unchecked:
            return {
                "ok": False,
                "skipped": True,
                "error": (
                    f"Không tự kích hoạt vì không kiểm được ràng buộc theo {', '.join(unchecked)} "
                    "(job không có điểm cho metric đó)."
                ),
            }
        try:
            result = tools.activate_model(self._api, job_id)
        except Exception as error:  # noqa: BLE001
            log_exception(_log, "tự kích hoạt job %s lỗi", job_id)
            return {"ok": False, "error": f"Lỗi nội bộ khi kích hoạt ({type(error).__name__})."}
        if not result.get("ok"):
            return {"ok": False, "error": str(result.get("error") or "Không kích hoạt được.")}
        return {"ok": True, "endpoint_url": result.get("endpoint_url")}


def _merge_constraints(existing: list[dict], added: list[dict]) -> list[dict]:
    """Ràng buộc mới thay ràng buộc cùng metric (lời mới nhất của người dùng), giữ phần còn lại."""
    metrics = {c.get("metric") for c in added}
    return [c for c in existing if c.get("metric") not in metrics] + [dict(c) for c in added]


def wants_deploy(requirements: dict | None) -> bool:
    """R.service.deploy: người dùng muốn dùng model ngay sau khi train."""
    value = ((requirements or {}).get("service") or {}).get("deploy")
    return value is True or str(value).strip().lower() == "true"
