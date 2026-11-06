"""Agent regression tests; no backend, LLM credentials or training jobs required."""
import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from agent import agent_openai, providers, server, skills, tools
from agent.api_client import ApiError, HAutoMLClient
from agent.chat import ChatSession
from agent.team import normalize_requirements


class Backend:
    access_token = "test-token"
    user_id = "user-1"

    def __init__(self):
        self.training_calls = []

    def get_dataset_info(self, dataset_id):
        return {"_id": dataset_id, "dataName": "demo"}

    def get_dataset_preview(self, dataset_id):
        return {"rows": 100, "records": [{"x": 1, "y": 0}, {"x": 2, "y": 1}]}

    def get_dataset_features(self, dataset_id, problem_type):
        return {"x": False, "y": problem_type == "classification"}

    def list_datasets(self):
        return [{"_id": "dataset-1", "dataName": "demo"}]

    def list_jobs(self):
        return [
            {"_id": "job-1", "user": {"id": "user-1"}, "status": 1},
            {"_id": "job-2", "user": {"id": "user-2"}, "status": 1},
        ]

    def start_training(self, dataset_id, config):
        self.training_calls.append((dataset_id, config))
        return {"job_id": "job-1"}

    def close(self):
        pass


def response(content="", tool=None, arguments=None):
    calls = None
    if tool:
        calls = [SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name=tool, arguments=json.dumps(arguments or {})),
            model_extra={},
        )]
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=content, tool_calls=calls, model_extra={},
        ))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    monkeypatch.setattr(providers, "tracing_enabled", lambda: False)


@pytest.fixture
def session():
    session = ChatSession(api=Backend(), auto_login=False, verbose=False)
    session._config = SimpleNamespace(model="test-model", name="test")
    yield session
    session.close()


def request(method, path, **kwargs):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app), base_url="http://agent",
        ) as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(send())


def test_skill_tools_match_registry():
    assert skills.validate(skills.load_skills(), agent_openai.known_tools()) == []


def test_http_client_uses_v1_and_unwraps_response():
    def handle(request):
        assert request.url.path == "/api/v1/auth/me"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"success": True, "data": {"_id": "user-1"}})

    with HAutoMLClient("http://backend") as client:
        # Giữ base_url do client tự dựng (gồm API_PREFIX) - chỉ thay transport,
        # để test bắt được lỗi nếu prefix /api/v1 bị dựng sai.
        base_url = client._http.base_url
        client._http.close()
        client._http = httpx.Client(base_url=base_url, transport=httpx.MockTransport(handle))
        client.access_token = "test-token"
        assert client.get_me() == {"_id": "user-1"}
        assert client.user_id == "user-1"


def test_valid_training_maps_timeout():
    backend = Backend()
    result = tools.start_training(
        backend, "dataset-1", "y", ["x"], "accuracy", "classification", max_time=120,
    )
    assert result["ok"]
    assert result["job_id"] == "job-1"
    assert len(backend.training_calls) == 1
    dataset_id, payload = backend.training_calls[0]
    assert dataset_id == "dataset-1"
    assert payload["timeout"] == 120
    assert "max_time" not in payload


@pytest.mark.parametrize("problem_type,metric", [("classification", "accuracy"), ("regression", "mse")])
def test_no_valid_target_blocks_training(problem_type, metric):
    backend = Backend()
    backend.get_dataset_features = lambda *_: {"x": False, "y": False}
    result = tools.start_training(backend, "dataset-1", "y", ["x"], metric, problem_type)
    assert result["ok"] is False
    assert any("không có cột nào" in error for error in result["errors"])
    assert backend.training_calls == []


def test_target_invalid_for_selected_problem_blocks_training():
    backend = Backend()
    result = tools.start_training(backend, "dataset-1", "y", ["x"], "mse", "regression")
    assert result["ok"] is False
    assert backend.training_calls == []


def test_target_leakage_blocks_training():
    backend = Backend()
    result = tools.start_training(backend, "dataset-1", "y", ["x", "y"], "accuracy", "classification")
    assert result["ok"] is False
    assert any("nhìn thấy đáp án" in error for error in result["errors"])
    assert backend.training_calls == []


def failing_once(method, status):
    calls = []

    def call(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise ApiError(status, "tạm thời")
        return method(*args, **kwargs)
    return call, calls


def test_transient_backend_error_is_retried(monkeypatch):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    backend = Backend()
    backend.get_dataset_preview, calls = failing_once(backend.get_dataset_preview, 503)
    assert tools.get_dataset_schema(backend, "dataset-1")["ok"]
    assert len(calls) == 2


def test_persistent_or_permanent_backend_error_is_reported(monkeypatch):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    backend = Backend()
    calls = []

    def down(*args):
        calls.append(args)
        raise ApiError(503, "Service Unavailable")
    backend.get_dataset_preview = down
    result = tools.get_dataset_schema(backend, "dataset-1")
    assert result["ok"] is False and result["retryable"] is True
    assert len(calls) == 3

    backend.get_dataset_preview, calls = failing_once(backend.get_dataset_preview, 404)
    result = tools.get_dataset_schema(backend, "dataset-1")
    assert result["ok"] is False and result["retryable"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("timed_out,calls", [(True, 1), (False, 3)])
def test_backend_that_hangs_is_not_retried(monkeypatch, timed_out, calls):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    backend = Backend()
    made = []

    def unreachable(*args):
        made.append(args)
        raise ApiError(0, "timeout" if timed_out else "connection refused", timed_out=timed_out)
    backend.get_dataset_preview = unreachable
    result = tools.get_dataset_schema(backend, "dataset-1")
    assert result["ok"] is False and result["retryable"] is (not timed_out)
    assert len(made) == calls


@pytest.mark.parametrize("status,retried", [(503, True), (429, True), (502, False), (504, False)])
def test_training_is_retried_only_when_backend_never_got_it(monkeypatch, status, retried):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    backend = Backend()
    backend.start_training, calls = failing_once(backend.start_training, status)
    result = tools.start_training(backend, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert result["ok"] is retried
    assert len(calls) == (2 if retried else 1)
    assert len(backend.training_calls) == (1 if retried else 0)


class SeriesBackend(Backend):
    """Một chuỗi doanh số theo ngày: cột date (chuỗi ISO), sales (số), promo (0/1)."""

    def __init__(self, dates=None):
        super().__init__()
        self.dates = dates or [f"2024-01-{day:02d}" for day in range(1, 31)]

    def get_dataset_preview(self, dataset_id):
        records = [{"date": d, "sales": 100.0 + i, "promo": i % 2} for i, d in enumerate(self.dates)]
        return {"rows": 365, "records": records}

    def get_dataset_features(self, dataset_id, problem_type):
        return {"date": False, "sales": problem_type == "regression", "promo": problem_type == "classification"}


def test_schema_reports_time_column_without_changing_inference():
    schema = tools.get_dataset_schema(SeriesBackend(), "dataset-1")
    assert schema["ok"]
    [time_column] = schema["time_columns"]
    assert time_column["name"] == "date" and time_column["regular_in_preview"]
    assert time_column["step"] == "1 day, 0:00:00"
    assert time_column["estimated_last"] == "2024-12-30 00:00:00"
    assert schema["target_candidates_by_type"]["time_series"] == ["sales"]
    # time_series có cùng ứng viên với regression nhưng không bao giờ tự suy ra.
    assert tools.infer_problem_type(schema, "sales") == "regression"


def test_dataset_without_time_column_has_no_time_series_keys():
    schema = tools.get_dataset_schema(Backend(), "dataset-1")
    assert "time_columns" not in schema
    assert "time_series" not in schema["target_candidates_by_type"]
    assert all("time_series" not in c["target_for"] for c in schema["columns"])


def test_time_series_columns_agree_with_candidates():
    schema = tools.get_dataset_schema(SeriesBackend(), "dataset-1", problem_type="time_series")
    by_name = {c["name"]: c for c in schema["columns"]}
    assert schema["target_candidates"] == ["sales"]
    assert by_name["sales"]["can_be_target"] and "time_series" in by_name["sales"]["target_for"]
    assert not by_name["date"]["can_be_target"]


def test_estimated_last_past_year_9999_is_dropped_not_fatal():
    rows = [{"date": "2024-01-01"}, {"date": "2024-01-02"}]
    [info] = tools._time_columns(["date"], rows, 10**7)
    assert info["regular_in_preview"] and "estimated_last" not in info


@pytest.mark.parametrize("features,error", [
    (["promo"], "ĐÚNG MỘT cột thời gian"),
    (["date", "promo"], None),
])
def test_time_series_config_needs_the_time_column(features, error):
    result = tools.prepare_training_config(SeriesBackend(), "dataset-1", "sales", features, "rmse", "time_series")
    if error:
        assert result["ok"] is False and any(error in e for e in result["errors"])
    else:
        assert result["ok"], result
        assert result["config"]["problem_type"] == "time_series"
        assert any("promo" in w for w in result["warnings"])


def test_time_series_rejects_duplicate_timestamps_and_missing_time_column():
    duplicated = SeriesBackend(dates=["2024-01-01", "2024-01-01", "2024-01-02"])
    result = tools.prepare_training_config(duplicated, "dataset-1", "sales", ["date"], "rmse", "time_series")
    assert result["ok"] is False and any("trùng" in e for e in result["errors"])

    result = tools.prepare_training_config(Backend(), "dataset-1", "y", ["x"], "rmse", "time_series")
    assert result["ok"] is False and any("cột ngày giờ" in e for e in result["errors"])


def test_time_series_metrics_models_and_requirements():
    assert tools.list_metrics(None, "time_series")["metrics"] == ["mse", "mae", "rmse", "r2"]
    assert {m["model"] for m in tools.list_models(None, "time_series")["models"]} == {
        "Ridge", "RandomForestRegressor", "GradientBoostingRegressor",
    }
    raw = {"user": {"intent": "train"}, "dataset": {"id": "dataset-1"},
           "problem": {"type": "time_series", "metric": "root_mean_squared_error"}}
    requirements, _, _ = normalize_requirements(raw, [{"id": "dataset-1", "name": "demo"}])
    assert requirements["problem"]["type"] == "time_series"
    assert requirements["problem"]["metric"] == "rmse"


def test_jobs_are_filtered_by_owner():
    result = tools.list_my_jobs(Backend())
    assert result["ok"]
    assert [job["job_id"] for job in result["jobs"]] == ["job-1"]


def test_manager_delegates_to_data_agent(session):
    create = Mock(side_effect=[
        response(tool="ask_data_agent", arguments={"task": "Liệt kê dataset"}),
        response(tool="list_my_datasets"),
        response("Có dataset demo"),
        response("Bạn có dataset demo"),
    ])
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert session.send("Tôi có dataset nào?") == "Bạn có dataset demo"
    assert session.usage["calls"] == 4
    assert session.messages[-1]["content"] == "Bạn có dataset demo"


def test_validated_config_handoff_starts_only_once(session, monkeypatch):
    watch = Mock(return_value=True)
    monkeypatch.setattr(session.watcher, "watch", watch)
    prepared = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification", max_time=120,
    )
    assert prepared["ok"]
    config_id = prepared["config_id"]
    started = session.team.start_training(session.api, config_id)
    assert started["ok"] and started["watching"]
    assert session.team.handoff.jobs == {"job-1": config_id}
    assert watch.call_args.args == ("job-1",)
    assert watch.call_args.kwargs["max_time"] == 120
    assert session.team.start_training(session.api, config_id)["ok"] is False
    assert len(session.api.training_calls) == 1


def test_job_is_judged_by_the_requirements_its_config_was_built_from(session, monkeypatch):
    watch = Mock(return_value=True)
    monkeypatch.setattr(session.watcher, "watch", watch)
    events = []
    session.events.subscribe(events.append)
    first = {"problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]}}
    session.team.handoff.requirements = first
    prepared = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")

    checked = [e for e in events if e["type"] == "config_checked"]
    assert checked[-1]["ok"] and checked[-1]["config_id"] == prepared["config_id"]
    assert checked[-1]["config"]["target"] == "y"

    # Yêu cầu khác trong cùng phiên thay R trước khi config cũ được chạy.
    session.team.handoff.requirements = {"problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.95}]}}
    session.team.start_training(session.api, prepared["config_id"])
    assert watch.call_args.kwargs["requirements"] is first

    session.api.list_jobs = lambda: [{"_id": "job-1", "user": {"id": "user-1"}, "status": 0}]
    session.team.watch_job(session.api, "job-1")
    assert watch.call_args.kwargs["requirements"] is first


def test_invalid_config_never_enters_handoff(session):
    session.api.get_dataset_features = lambda *_: {"x": False, "y": False}
    prepared = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification",
    )
    assert prepared["ok"] is False
    assert session.team.handoff.configs == {}
    assert session.api.training_calls == []


def test_unchosen_target_is_blocked_when_dataset_has_several(session):
    session.api.get_dataset_features = lambda _id, kind: {"x": True, "y": kind == "classification"}
    # Tên cột chỉ nằm trong dòng sự kiện hệ thống chèn vào, người dùng chưa nói.
    session.messages.append({
        "role": "user",
        "content": "[Sự kiện] Người dùng vừa tải lên dataset y (id: dataset-1)\n\nHuấn luyện giúp tôi.",
    })
    prepared = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification",
    )
    assert prepared["ok"] is False
    assert prepared["target_candidates"] == ["x", "y"]
    assert session.team.handoff.configs == {}


@pytest.mark.parametrize("message", ["Bỏ cột y, huấn luyện giúp tôi.", "Dùng feature x, y để train."])
def test_mentioning_a_column_is_not_choosing_it_as_target(session, message):
    session.api.get_dataset_features = lambda _id, kind: {"x": True, "y": kind == "classification"}
    session.messages.append({"role": "user", "content": message})
    prepared = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification",
    )
    assert prepared["ok"] is False and "chưa chọn cột mục tiêu" in prepared["error"]


@pytest.mark.parametrize("said", [
    {"message": "Target là y, bài toán phân loại."},
    {"message": "Tôi muốn dự đoán y từ x."},
    {"requirements": {"problem": {"target": "Y", "type": "classification"}}},
])
def test_target_named_by_user_passes(session, said):
    session.api.get_dataset_features = lambda _id, kind: {"x": True, "y": kind == "classification"}
    if "message" in said:
        session.messages.append({"role": "user", "content": said["message"]})
    session.team.handoff.requirements = said.get("requirements")
    prepared = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification",
    )
    assert prepared["ok"]
    assert prepared["config"]["target"] == "y"


def test_subagent_survives_one_failed_llm_call(session):
    create = Mock(side_effect=[
        response(tool="ask_data_agent", arguments={"task": "Liệt kê dataset"}),
        RuntimeError("provider trả dữ liệu hỏng"),
        response(tool="list_my_datasets"),
        response("Có dataset demo"),
        response("Bạn có dataset demo"),
    ])
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert session.send("Tôi có dataset nào?") == "Bạn có dataset demo"


def test_llm_error_already_retried_by_sdk_is_not_retried_again():
    error = RuntimeError("HTTP 401")
    error.status_code = 401
    create = Mock(side_effect=[error, response("không được gọi")])
    llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(RuntimeError):
        agent_openai.create_completion(llm, model="m", messages=[])
    assert create.call_count == 1


@pytest.mark.parametrize("intent,blocks", [("train", False), ("predict", True)])
def test_missing_predict_rows_do_not_block_training(intent, blocks):
    raw = {
        "user": {"intent": intent},
        "dataset": {"id": "dataset-1"},
        "missing": ["Mẫu dữ liệu cần dự đoán chưa được cung cấp"],
    }
    _, missing, _ = normalize_requirements(raw, [{"id": "dataset-1", "name": "demo"}])
    assert bool(missing) is blocks


def test_operation_agent_knows_which_jobs_this_session_created(session, monkeypatch):
    monkeypatch.setattr(session.watcher, "watch", Mock(return_value=True))
    create = Mock(return_value=response("Đã kiểm tra"))
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    none_yet = "Chưa có - phiên chat này chưa tạo job nào."
    session.team.ask_operation_agent(session.api, "Kiểm tra job vừa tạo")
    assert none_yet in create.call_args.kwargs["messages"][0]["content"]

    config_id = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification",
    )["config_id"]
    session.team.start_training(session.api, config_id)
    session.team.ask_operation_agent(session.api, "Kiểm tra job vừa tạo")
    system = create.call_args.kwargs["messages"][0]["content"]
    assert '"job_id": "job-1"' in system and none_yet not in system


def test_step_limit_reply_is_retained_for_next_turn(session, monkeypatch):
    create = Mock(side_effect=[response(tool="unknown"), response("Tiếp tục")])
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr("agent.chat.MAX_STEPS", 1)
    answer = session.send("Làm việc này")
    assert "quá 1 bước" in answer
    assert session.messages[-1] == {"role": "assistant", "content": answer}
    assert session.messages[-2]["role"] == "tool"
    assert session.send("Tiếp đi") == "Tiếp tục"
    assert session.messages[-3]["content"] == answer


def test_normal_reply_is_not_duplicated(session):
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=Mock(return_value=response("Xin chào")),
    )))
    assert session.send("Chào") == "Xin chào"
    assert len(session.messages) == 3


def test_health_reports_configured_provider(monkeypatch):
    monkeypatch.setattr(providers, "resolve", lambda: SimpleNamespace(name="test", model="test-model"))
    result = request("GET", "/health")
    assert result.status_code == 200
    assert result.json()["status"] == "ok"
    assert result.json()["llm_ready"] is True
    assert result.json()["model"] == "test-model"


@pytest.mark.parametrize("error", [RuntimeError("Thiếu API key"), ValueError("Provider không hỗ trợ")])
def test_health_survives_invalid_llm_configuration(monkeypatch, error):
    monkeypatch.setattr(providers, "resolve", Mock(side_effect=error))
    result = request("GET", "/health")
    assert result.status_code == 200
    assert result.json()["status"] == "degraded"
    assert result.json()["llm_ready"] is False
    assert result.json()["configuration_error"] == str(error)


def test_chat_rejects_missing_token():
    assert request("POST", "/agent/chat", json={"message": "Xin chào"}).status_code == 401


def test_refreshed_token_reaches_session_mid_turn(session, monkeypatch):
    owners = {"old": "user-1", "new": "user-1", "intruder": "user-2"}
    monkeypatch.setattr(server, "_owner_of", owners.get)
    entry = server._Entry(session, "user-1")
    monkeypatch.setitem(server._sessions, "s1", entry)
    session.api.access_token = "old"

    assert request("POST", "/agent/token", json={"session_id": "s1"}).status_code == 401
    assert request("POST", "/agent/token", json={"session_id": "s1", "access_token": "intruder"}).status_code == 404
    assert session.api.access_token == "old"

    # Đang giữa một lượt chat (turn_lock bị giữ) vẫn phải nhận token mới.
    with entry.turn_lock:
        result = request("POST", "/agent/token", json={"session_id": "s1", "access_token": "new"})
    assert result.status_code == 200
    assert session.api.access_token == "new"


# --------------------------------------------------------------- review 2026-11-05

class ManyJobsBackend(Backend):
    """30 job của user-1, create_at tăng dần, xen kẽ hai dataset và hai trạng thái."""

    def list_jobs(self):
        return [
            {"_id": f"job-{i}", "user": {"id": "user-1"}, "status": i % 2, "create_at": float(i),
             "data": {"id": "ds-a" if i % 2 else "ds-b", "name": "demo"}}
            for i in range(30)
        ]


def test_list_my_jobs_is_limited_newest_first_and_filterable():
    result = tools.list_my_jobs(ManyJobsBackend())
    assert result["count"] == 30 and result["truncated"] is True
    assert len(result["jobs"]) == tools.DEFAULT_JOB_LIMIT
    assert result["jobs"][0]["job_id"] == "job-29"

    by_dataset = tools.list_my_jobs(ManyJobsBackend(), dataset_id="ds-b", limit=100)
    assert by_dataset["count"] == 15 and "truncated" not in by_dataset
    assert len(by_dataset["jobs"]) == 15

    running = tools.list_my_jobs(ManyJobsBackend(), status=0, limit=3)
    assert [job["status"] for job in running["jobs"]] == [0, 0, 0]
    assert tools.list_my_jobs(ManyJobsBackend(), status="abc")["ok"] is False


class FlakyJobsBackend(Backend):
    """Lần hỏi đầu ném lỗi lạ (không phải ApiError), lần sau job đã xong."""

    def __init__(self, job):
        super().__init__()
        self.job = job
        self.calls = 0
        self.activated = []

    def list_jobs(self):
        self.calls += 1
        if self.calls == 1:
            raise KeyError("scores")
        return [self.job]

    def activate_model(self, job_id, activate):
        self.activated.append((job_id, activate))
        return {"endpoint_url": f"/predict/{job_id}"}


def _watch_until_done(api, requirements=None):
    from agent.watcher import JobWatcher

    events, finished = [], []
    watcher = JobWatcher(api, lambda type, **data: events.append({"type": type, **data}), finished.append, poll=0.01)
    watcher.watch("job-1", max_time=60, requirements=requirements)
    watcher._threads["job-1"].join(timeout=5)
    return events, finished


SUCCESS_JOB = {
    "_id": "job-1", "user": {"id": "user-1"}, "status": 1, "best_model": "RF", "best_score": 0.8,
    "config": {"metric_sort": "accuracy"},
    "orther_model_scores": [{"model_name": "RF", "scores": {"accuracy": 0.8}}],
}


def test_watcher_survives_unexpected_error_and_still_reports():
    events, finished = _watch_until_done(FlakyJobsBackend(SUCCESS_JOB))
    types = [event["type"] for event in events]
    assert "job_watch_warning" in types and "job_watch_resumed" in types
    assert types[-1] == "job_done"
    assert len(finished) == 1 and finished[0]["status"] == 1
    assert "activation" not in finished[0]


def test_watcher_activates_model_when_user_asked():
    api = FlakyJobsBackend(SUCCESS_JOB)
    _, finished = _watch_until_done(api, {"service": {"deploy": True}, "problem": {"constraints": []}})
    assert api.activated == [("job-1", True)]
    assert finished[0]["activation"] == {"ok": True, "endpoint_url": "/predict/job-1"}


def test_watcher_does_not_activate_model_that_misses_constraints():
    api = FlakyJobsBackend(SUCCESS_JOB)
    requirements = {
        "service": {"deploy": True},
        "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.95}]},
    }
    _, finished = _watch_until_done(api, requirements)
    assert api.activated == []
    assert finished[0]["activation"]["ok"] is False and finished[0]["activation"]["skipped"]


def test_job_event_tells_manager_about_activation(session):
    session._on_job_finished({**SUCCESS_JOB, "job_id": "job-1", "activation": {"ok": True}})
    session._on_job_finished({**SUCCESS_JOB, "job_id": "job-2", "activation": {"ok": False, "error": "lỗi X"}})
    assert "ĐÃ được tự kích hoạt" in session.pending_events[0]
    assert "CHƯA được kích hoạt: lỗi X" in session.pending_events[1]


def test_service_flags_are_real_booleans():
    raw = {"user": {"intent": "train"}, "dataset": {"id": "dataset-1"},
           "service": {"deploy": "false", "predict": "true"}}
    requirements, _, _ = normalize_requirements(raw, [{"id": "dataset-1", "name": "demo"}])
    assert requirements["service"] == {"deploy": False, "predict": True}


def test_wide_dataset_profile_lists_every_column_name():
    from agent.team import profile_brief

    schema = {"columns": [{"name": f"c{i}"} for i in range(100)], "target_candidates_by_type": {}}
    brief = profile_brief(schema)
    assert len(brief["columns"]) == 60 and brief["columns_truncated"]
    assert brief["all_column_names"] == [f"c{i}" for i in range(100)]
    assert "all_column_names" not in profile_brief({"columns": [{"name": "a"}]})


def test_old_turns_are_compacted_and_history_stays_valid(session, monkeypatch):
    monkeypatch.setenv("AGENT_HISTORY_FULL_TURNS", "2")
    replies = []
    for turn in range(6):
        replies += [response(tool="unknown"), response(f"Trả lời {turn}")]
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=replies))))
    for turn in range(6):
        assert session.send(f"Câu {turn}") == f"Trả lời {turn}"

    messages = session.messages
    users = [i for i, m in enumerate(messages) if m["role"] == "user"]
    assert len(users) == 6
    # Lượt cũ: chỉ còn câu hỏi + câu trả lời. Lượt hiện tại và 2 lượt trước nó
    # giữ đủ tool_calls.
    old = messages[1:users[-3]]
    assert [m["role"] for m in old] == ["user", "assistant"] * 3
    assert sum(1 for m in messages[users[-3]:] if m.get("tool_calls")) == 3
    assert all("tool_calls" not in m for m in old)
    for i, message in enumerate(messages):
        if message["role"] == "tool":
            assert messages[i - 1].get("tool_calls"), "tool message phải theo sau assistant tool_calls"


def test_failed_turn_reports_job_it_created(session):
    def create(**_):
        session.team.handoff.jobs["job-9"] = "cfg_x"
        error = RuntimeError("provider lỗi")
        error.status_code = 500
        raise error

    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(RuntimeError):
        session.send("Train giúp tôi")
    assert len(session.messages) == 1
    assert any("job-9" in event and "KHÔNG tạo lại" in event for event in session.pending_events)


class MissingTargetSeries(SeriesBackend):
    def get_dataset_preview(self, dataset_id):
        preview = super().get_dataset_preview(dataset_id)
        preview["records"][3]["sales"] = None
        return preview


def test_time_series_target_with_missing_values_is_blocked():
    result = tools.prepare_training_config(MissingTargetSeries(), "dataset-1", "sales", ["date"], "rmse", "time_series")
    assert result["ok"] is False
    assert any("thiếu 1 giá trị" in e for e in result["errors"])


def test_superseded_config_is_not_handed_to_manager(session):
    submit = {"dataset_id": "dataset-1", "target": "y", "list_feature": ["x"],
              "metric_sort": "accuracy", "problem_type": "classification"}
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=[
        response(tool="submit_config", arguments=submit),
        response(tool="submit_config", arguments={**submit, "max_time": 300}),
        response("Đã chốt config"),
    ]))))
    result = session.team.ask_model_agent(session.api, "Chốt config", dataset_id="dataset-1")
    assert result["ok"]
    assert len(session.team.handoff.configs) == 2
    [config] = result["configs"]
    assert config["config"]["max_time"] == 300


def test_budget_overrun_in_subagent_is_not_called_an_llm_error(session):
    session.turn_budget = 20
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=[
        response(tool="ask_data_agent", arguments={"task": "Liệt kê dataset"}),
        response(tool="list_my_datasets"),
    ]))))
    answer = session.send("Tôi có dataset nào?")
    assert "tốn quá nhiều xử lý" in answer
    [done] = [e for e in session.events.since(0) if e["type"] == "agent_done"]
    assert "vượt trần token" in done["error"] and "lỗi khi gọi LLM" not in done["error"]


def _sse_events(text):
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.mark.parametrize("after,replayed", [(1, True), (None, False)])
def test_chat_stream_replays_missed_events(session, monkeypatch, after, replayed):
    monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
    monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response("Xong")))))
    session.events.emit("job_status", job_id="job-1", status=0)
    session.events.emit("job_done", job_id="job-1", status=1)

    body = {"message": "Chào", "session_id": "s1", "access_token": "token"}
    if after is not None:
        body["after"] = after
    result = request("POST", "/agent/chat/stream", json=body)
    events = _sse_events(result.text)
    assert events[0] == ("session", {"session_id": "s1", "start_seq": 2})
    assert (("job_done" in [name for name, _ in events])) is replayed
    assert events[-1][0] == "reply" and events[-1][1]["reply"] == "Xong"


def test_background_events_stream_without_holding_threads(session, monkeypatch):
    monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
    monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
    monkeypatch.setattr(server, "EVENTS_STREAM_SECONDS", 0.5)
    session.events.emit("job_done", job_id="job-1", status=1)

    result = request("POST", "/agent/events", json={"session_id": "s1", "access_token": "token", "after": 0})
    events = _sse_events(result.text)
    assert [name for name, _ in events] == ["hello", "job_done", "reconnect"]
    assert events[0][1] == {
        "last_seq": 1, "watching": [], "auto_activate": {}, "auto_activate_constraints": {}, "turn_id": None,
    }


def test_slow_turn_keeps_chat_stream_alive(session, monkeypatch):
    import time as time_module

    monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
    monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
    monkeypatch.setattr(server, "CHAT_PING_SECONDS", 0.1)

    def slow(**_):
        time_module.sleep(0.8)
        return response("Xong")

    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=slow)))
    result = request("POST", "/agent/chat/stream", json={"message": "Chào", "session_id": "s1", "access_token": "token"})
    assert ": ping" in result.text
    assert _sse_events(result.text)[-1][0] == "reply"


# ------------------------------------------------------- Codex review 2026-11-05

def test_queued_turn_holds_the_session_so_second_message_and_reset_get_409(session, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException

    monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
    entry = server._Entry(session, "user-1")
    monkeypatch.setitem(server._sessions, "s1", entry)
    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(server, "_TURN_POOL", pool)
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response("Xong")))))

    async def scenario():
        blocker = threading.Event()
        pool.submit(blocker.wait)                      # pool đầy: lượt sau phải xếp hàng
        queued = server._start_turn("s1", entry, "Train giúp tôi")
        assert entry.turn_lock.locked()                # giữ phiên ngay cả khi còn xếp hàng
        with pytest.raises(HTTPException) as busy:
            server._start_turn("s1", entry, "Tin thứ hai")
        assert busy.value.status_code == 409
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://agent") as client:
            reset = await client.post("/agent/reset", json={"message": "reset", "session_id": "s1", "access_token": "token"})
        assert reset.status_code == 409
        blocker.set()
        assert (await queued).reply == "Xong"
        assert not entry.turn_lock.locked()

    asyncio.run(scenario())
    pool.shutdown(wait=True)


def test_auto_activation_needs_every_constraint_verified():
    api = FlakyJobsBackend(SUCCESS_JOB)
    requirements = {
        "service": {"deploy": True},
        "problem": {"constraints": [
            {"metric": "accuracy", "op": ">=", "value": 0.5},   # đạt
            {"metric": "rmse", "op": "<=", "value": 1.0},       # job không có điểm rmse
        ]},
    }
    _, finished = _watch_until_done(api, requirements)
    assert api.activated == []
    assert finished[0]["activation"]["skipped"] and "rmse" in finished[0]["activation"]["error"]


def test_submit_config_warns_about_constraints_it_cannot_verify(session):
    session.team.handoff.requirements = {
        "problem": {"type": None, "constraints": [{"metric": "rmse", "op": "<=", "value": 1.0}]},
    }
    result = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert result["ok"]
    assert any("rmse" in w and "KHÔNG kiểm định được" in w for w in result["warnings"])


class MissingTimestampSeries(SeriesBackend):
    def get_dataset_preview(self, dataset_id):
        preview = super().get_dataset_preview(dataset_id)
        preview["records"][5]["date"] = None
        return preview


def test_time_series_time_column_with_missing_timestamps_is_blocked():
    result = tools.prepare_training_config(MissingTimestampSeries(), "dataset-1", "sales", ["date"], "rmse", "time_series")
    assert result["ok"] is False
    assert any("mốc thời gian trống" in e for e in result["errors"])


def test_job_started_event_carries_dataset_id(session, monkeypatch):
    monkeypatch.setattr(session.watcher, "watch", Mock(return_value=True))
    config_id = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    session.team.start_training(session.api, config_id)
    [started] = [e for e in session.events.since(0) if e["type"] == "job_started"]
    assert started["dataset_id"] == "dataset-1" and started["config_id"] == config_id


def test_secrets_are_redacted_from_exception_logs(monkeypatch, caplog):
    import logging

    monkeypatch.setenv("FPT_API_KEY", "fpt-real-key-123456")
    text = agent_openai.redact_secrets(
        "fpt-real-key-123456 | Incorrect API key provided: sk-proj-****abcd | Bearer eyJa.eyJb.sig | AIzaSyA1234567890"
    )
    assert "fpt-real-key" not in text and "sk-proj" not in text and "eyJ" not in text and "AIza" not in text

    logger = logging.getLogger("agent.test")
    with caplog.at_level(logging.ERROR, logger="agent.test"):
        try:
            raise RuntimeError("401 Incorrect API key provided: sk-or-v1-abcdef123456 / fpt-real-key-123456")
        except RuntimeError:
            agent_openai.log_exception(logger, "lượt chat lỗi")
    assert "lượt chat lỗi" in caplog.text and "RuntimeError" in caplog.text
    assert "sk-or-v1" not in caplog.text and "fpt-real-key" not in caplog.text


def test_cancelled_queued_turn_releases_the_session(session, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    entry = server._Entry(session, "user-1")
    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(server, "_TURN_POOL", pool)

    async def scenario():
        blocker = threading.Event()
        pool.submit(blocker.wait)
        queued = server._start_turn("s1", entry, "Train giúp tôi")
        assert entry.turn_lock.locked()
        queued.cancel()                                 # request bị huỷ khi lượt còn xếp hàng
        await asyncio.sleep(0.05)
        assert not entry.turn_lock.locked()             # không kẹt 409 mãi
        blocker.set()

    asyncio.run(scenario())
    pool.shutdown(wait=True)


def test_provider_errors_are_sanitized_before_tracing_sees_them(monkeypatch):
    import openai

    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-secret-123456")

    def handler(request):
        return httpx.Response(401, json={"error": {"message": "Incorrect API key provided: sk-real-secret-123456"}})

    client = providers._sanitized(openai.OpenAI)(
        api_key="sk-real-secret-123456", base_url="http://llm.test/v1", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(openai.AuthenticationError) as error:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
    assert "sk-real-secret" not in str(error.value)
    assert "sk-real-secret" not in json.dumps(error.value.body)
    assert type(client).__name__ == "OpenAI"


def test_no_auto_activation_when_constraints_could_not_be_checked(monkeypatch):
    from agent import watcher as watcher_module

    def broken_summary(job, requirements=None):
        raise KeyError("scores")                         # bản ghi job dị dạng

    monkeypatch.setattr(watcher_module, "summarize_job", broken_summary)
    api = FlakyJobsBackend(SUCCESS_JOB)
    requirements = {"service": {"deploy": True},
                    "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]}}
    events, finished = _watch_until_done(api, requirements)
    assert api.activated == []
    assert finished[0]["activation"]["skipped"] and "không đọc được kết quả job" in finished[0]["activation"]["error"]
    assert finished[0]["summary_error"]
    assert events[-1]["type"] == "job_done"


# ------------------------------------------------- Claude review 2026-11-06

def test_job_events_carry_dataset_and_problem_type():
    from agent.watcher import JobWatcher, summarize_job

    events = []
    watcher = JobWatcher(FlakyJobsBackend(SUCCESS_JOB), lambda type, **data: events.append({"type": type, **data}),
                         lambda summary: None, poll=0.01)
    watcher.watch("job-1", max_time=60, dataset_id="ds-1", problem_type="time_series")
    watcher._threads["job-1"].join(timeout=5)
    assert events[0]["type"] == "job_watch"
    assert events[0]["dataset_id"] == "ds-1" and events[0]["problem_type"] == "time_series"

    summary = summarize_job({**SUCCESS_JOB, "job_id": "job-1", "data": {"id": "ds-1", "name": "demo"},
                             "config": {"metric_sort": "accuracy", "problem_type": "classification"}})
    assert summary["dataset_id"] == "ds-1" and summary["problem_type"] == "classification"


def test_turn_done_carries_the_reply(session):
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response("Xin chào")))))
    session.send("Chào")
    [done] = [e for e in session.events.since(0) if e["type"] == "turn_done"]
    assert done["reply"] == "Xin chào"


@pytest.mark.parametrize("status,expected", [(401, 401), (0, 503), (502, 503)])
def test_backend_outage_is_not_reported_as_expired_login(monkeypatch, status, expected):
    monkeypatch.setattr(server, "_owner_cache", {})

    def get_me(self):
        raise ApiError(status, "backend lỗi")

    monkeypatch.setattr(HAutoMLClient, "get_me", get_me)
    result = request("POST", "/agent/chat", json={"message": "Chào", "access_token": "token"})
    assert result.status_code == expected


# ------------------------------------------------- Claude verify 2026-11-06 (vòng 2)

def test_failed_turn_emits_turn_failed(session):
    def create(**_):
        error = RuntimeError("provider lỗi")
        error.status_code = 500
        raise error

    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(RuntimeError):
        session.send("Chào")
    [failed] = [e for e in session.events.since(0) if e["type"] == "turn_failed"]
    assert failed["error"] == "RuntimeError (HTTP 500)"


def test_watch_job_on_finished_job_reports_the_result(session):
    result = session.team.watch_job(session.api, "job-1")      # Backend.list_jobs: job-1 status 1
    assert result["ok"] and result["status"] == 1
    [done] = [e for e in session.events.since(0) if e["type"] == "job_done"]
    assert done["job_id"] == "job-1"


@pytest.mark.parametrize("message,deploy", [
    ("Train model trên dataset demo, train xong kích hoạt luôn", True),
    ("Train model trên dataset demo", False),
])
def test_auto_activation_flag_needs_the_user_to_ask(session, message, deploy):
    raw = {"user": {"intent": "train"}, "dataset": {"id": "dataset-1"}, "service": {"deploy": True}}
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=Mock(return_value=response(json.dumps(raw))),
    )))
    session.messages.append({"role": "user", "content": message})
    result = session.team.ask_prompt_agent(session.api, message)
    assert result["requirements"]["service"]["deploy"] is deploy


def test_unreadable_job_result_is_reported_as_such(session):
    error = "Không đọc được kết quả chi tiết của job (bản ghi dị dạng)."
    session._on_job_finished({"job_id": "job-7", "status": 1, "summary_error": error})
    assert "Không đọc được kết quả chi tiết" in session.pending_events[0]
    assert "không đặt ràng buộc" not in session.pending_events[0]
    # Lỗi kiểm định lại: nói đúng lý do, không phải "không đọc được kết quả".
    session._on_job_finished({"job_id": "job-8", "status": 1, "summary_error": "Không kiểm định được kết quả job theo ràng buộc người dùng đặt."})
    assert "Không kiểm định được" in session.pending_events[1]


# ------------------------------------------------- Claude verify 2026-11-06 (vòng 3)

def test_turn_events_carry_the_client_turn_id(session):
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response("Chào")))))
    session.send("Xin chào", turn_id="t-1")
    by_type = {e["type"]: e for e in session.events.since(0)}
    assert by_type["turn_start"]["turn_id"] == "t-1" and by_type["turn_done"]["turn_id"] == "t-1"


def test_turn_failing_during_preparation_still_ends_the_turn(session, monkeypatch):
    monkeypatch.setattr(session.team, "tools_for", Mock(side_effect=RuntimeError("skill hỏng")))
    with pytest.raises(RuntimeError):
        session.send("Chào", turn_id="t-2")
    [failed] = [e for e in session.events.since(0) if e["type"] == "turn_failed"]
    assert failed["turn_id"] == "t-2"


def test_multiline_event_text_stays_on_the_event_line(session):
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response("Ok")))))
    session.add_event("Job job-1 không hoàn tất: Traceback\n  File x\nValueError: target là cột Age")
    session.send("Tiếp tục")
    first_user = next(m for m in session.messages if m["role"] == "user")["content"]
    assert first_user.splitlines()[0].startswith("[Sự kiện] Job job-1") and "ValueError" in first_user.splitlines()[0]


@pytest.mark.parametrize("message,mentions", [
    ("train xong kích hoạt luôn", True),
    ("train xong kich hoat luon", True),                     # không dấu
    ("train xong dùng ngay để dự đoán", True),
    ("xong thì deploy giúp tôi", True),
    ("train thôi, đừng kích hoạt", True),                    # có nhắc (ý phủ định do LLM hiểu)
    ("relu là activation function phổ biến", False),
    ("hàm kích hoạt nào tốt", False),
    ("deactivate the old model", False),
    ("Dừng ngay việc train", False),
    ("train model trên dataset demo", False),
    ("[Sự kiện] Model ĐÃ được tự kích hoạt\nTrain tiếp dataset khác", False),   # dòng hệ thống không tính
])
def test_mentions_activation(message, mentions):
    from agent.team import _mentions_activation

    assert _mentions_activation([message]) is mentions


@pytest.mark.parametrize("named,deploy", [("dataset-1", True), (None, True), ("ds-A", False)])
def test_auto_activation_only_for_the_dataset_the_user_asked_about(session, named, deploy):
    session.messages.append({"role": "user", "content": "train xong kích hoạt luôn"})
    session.team.handoff.requirements = {
        "dataset": {"id": named}, "service": {"deploy": True}, "problem": {"type": "classification", "constraints": []},
    }
    config_id = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    assert session.team.handoff.configs[config_id]["requirements"]["service"]["deploy"] is deploy
    assert session.team.handoff.requirements["service"]["deploy"] is True        # R gốc không bị sửa


def test_watch_job_without_a_status_keeps_watching(session, monkeypatch):
    monkeypatch.setattr(tools, "find_own_job", lambda api, job_id: ({"job_id": job_id, "status": None}, None))
    watch = Mock(return_value=True)
    monkeypatch.setattr(session.watcher, "watch", watch)
    result = session.team.watch_job(session.api, "job-x")
    assert result["watching"] is True and watch.called


def test_chat_stream_passes_turn_id(session, monkeypatch):
    monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
    monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(return_value=response("Xong")))))
    result = request("POST", "/agent/chat/stream",
                     json={"message": "Chào", "session_id": "s1", "access_token": "token", "turn_id": "t-9"})
    done = [data for name, data in _sse_events(result.text) if name == "turn_done"]
    assert done and done[0]["turn_id"] == "t-9" and done[0]["reply"] == "Xong"


# ------------------------------------------------- Claude verify 2026-11-06 (vòng 4)

def test_consent_given_a_few_turns_earlier_still_counts(session):
    for text in ["train Iris xong kích hoạt luôn", "cột nào nên chọn?", "Species", "ok chạy đi"]:
        session.messages.append({"role": "user", "content": text})
    session.team.handoff.requirements = {
        "dataset": {"id": "dataset-1"}, "service": {"deploy": True}, "problem": {"type": "classification", "constraints": []},
    }
    result = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert session.team.handoff.configs[result["config_id"]]["requirements"]["service"]["deploy"] is True


def test_retraction_after_submit_is_honoured_at_start(session, monkeypatch):
    watch = Mock(return_value=True)
    monkeypatch.setattr(session.watcher, "watch", watch)
    session.messages.append({"role": "user", "content": "train xong kích hoạt luôn"})
    session.team.handoff.requirements = {
        "dataset": {"id": "dataset-1"}, "service": {"deploy": True}, "problem": {"type": "classification", "constraints": []},
    }
    config_id = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    session.messages.append({"role": "user", "content": "à thôi, đừng kích hoạt nhé, chạy đi"})
    # Prompt Agent hiểu lời rút lại và dựng lại R cho cùng dataset với deploy = false.
    session.team.handoff.requirements = {
        "dataset": {"id": "dataset-1"}, "service": {"deploy": False}, "problem": {"type": "classification", "constraints": []},
    }
    result = session.team.start_training(session.api, config_id)
    assert result["auto_activate"] is False
    assert watch.call_args.kwargs["requirements"]["service"]["deploy"] is False


# ------------------------------------------------- tự kích hoạt: hiển thị + huỷ được (vòng 5)

class ControlledJobBackend(Backend):
    """job-run: status do test điều khiển; có activate_model."""

    def __init__(self):
        super().__init__()
        self.status = 0
        self.activated = []

    def list_jobs(self):
        return [{**SUCCESS_JOB, "_id": "job-run", "status": self.status, "activate": 0}]

    def activate_model(self, job_id, activate):
        self.activated.append(job_id)
        return {"endpoint_url": "/x"}


def _session_with(api):
    session = ChatSession(api=api, auto_login=False, verbose=False)
    session._config = SimpleNamespace(model="test-model", name="test")
    session.watcher._poll = 0.01
    return session


def test_user_can_cancel_auto_activation_while_the_job_runs():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements={"service": {"deploy": True}, "problem": {}})
        assert session.watcher.auto_activate("job-run") is True
        result = session.team.set_auto_activate(api, "job-run", enabled=False)
        assert result == {"ok": True, "job_id": "job-run", "auto_activate": False}
        api.status = 1
        session.watcher._threads["job-run"].join(timeout=5)
        assert api.activated == []                                    # đã huỷ thì không kích hoạt
        assert any(e["type"] == "auto_activate_changed" and e["enabled"] is False for e in session.events.since(0))
        # Job không còn được theo dõi: báo rõ, không giả vờ đã đổi.
        assert session.team.set_auto_activate(api, "job-run", enabled=False)["ok"] is False
    finally:
        session.close()


def test_llm_cannot_turn_auto_activation_on_by_itself():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=None)
        session.messages.append({"role": "user", "content": "job tới đâu rồi"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True)["ok"] is False
        assert session.watcher.auto_activate("job-run") is False
    finally:
        session.close()


def test_cancel_endpoint(monkeypatch):
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
        monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
        session.watcher.watch("job-run", max_time=60, requirements={"service": {"deploy": True}, "problem": {}})
        body = {"session_id": "s1", "access_token": "token", "job_id": "job-run", "enabled": False}
        assert request("POST", "/agent/auto-activate", json=body).status_code == 200
        assert session.watcher.auto_activate("job-run") is False
        assert request("POST", "/agent/auto-activate", json={**body, "job_id": "nope"}).status_code == 404
    finally:
        session.close()


def test_watch_timeout_reports_that_promised_activation_did_not_happen(monkeypatch):
    from agent import watcher as watcher_module

    monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", -10_000)
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=1, requirements={"service": {"deploy": True}, "problem": {}})
        session.watcher._threads["job-run"].join(timeout=5)
        [timeout] = [e for e in session.events.since(0) if e["type"] == "job_watch_timeout"]
        assert timeout["auto_activate_skipped"] is True
        assert "CHƯA được tự kích hoạt" in session.pending_events[0]
    finally:
        session.close()


def test_unverifiable_constraint_means_no_auto_activation(session):
    session.messages.append({"role": "user", "content": "train xong kích hoạt luôn, rmse dưới 1"})
    session.team.handoff.requirements = {
        "dataset": {"id": "dataset-1"}, "service": {"deploy": True},
        "problem": {"type": None, "constraints": [{"metric": "rmse", "op": "<=", "value": 1.0}]},
    }
    result = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert session.team.handoff.configs[result["config_id"]]["requirements"]["service"]["deploy"] is False


def _time_out_watch(session, monkeypatch, requirements):
    """Theo dõi job-run rồi để watcher hết giờ chờ (lời hứa còn treo nếu có)."""
    from agent import watcher as watcher_module

    monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", -10_000)
    session.watcher.watch("job-run", max_time=1, requirements=requirements)
    session.watcher._threads["job-run"].join(timeout=5)


DEPLOY_R = {"service": {"deploy": True}, "problem": {"constraints": []}}


def _own_job(session):
    session.team.handoff.configs["cfg_1"] = {
        "config_id": "cfg_1", "dataset_id": "dataset-1", "config": {}, "warnings": [], "job_id": "job-run",
        "requirements": DEPLOY_R,
    }
    session.team.handoff.jobs["job-run"] = "cfg_1"


def test_promise_expires_when_watching_times_out(monkeypatch):
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        _own_job(session)
        _time_out_watch(session, monkeypatch, DEPLOY_R)
        assert session.watcher.auto_activate("job-run") is False          # hết hiệu lực, không còn hứa
        assert session.watcher.set_auto_activate("job-run", False) == "not_watched"
        api.status = 1
        session.team.watch_job(api, "job-run")                            # watch_job không tự kích hoạt
        assert api.activated == []
        [done] = [e for e in session.events.since(0) if e["type"] == "job_done"]
        assert "activation" not in done
        assert "HẾT HIỆU LỰC" in session.pending_events[0]
    finally:
        session.close()


def test_reset_does_not_drop_the_constraints_of_a_promise():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        strict = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.95}]}}
        session.watcher.watch("job-run", max_time=60, requirements=strict)
        session.reset()                                                   # xoá handoff R của phiên
        api.status = 1                                                    # SUCCESS_JOB: accuracy 0.8
        session.watcher._threads["job-run"].join(timeout=5)
        assert api.activated == []
    finally:
        session.close()


def test_deleted_job_drops_the_promise():
    api = ControlledJobBackend()
    api.list_jobs = lambda: []                                            # job bị xoá -> 404
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.watcher._threads["job-run"].join(timeout=5)
        assert session.watcher.auto_activate("job-run") is False
    finally:
        session.close()


def test_job_status_carries_the_auto_activation_state():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        for _ in range(200):
            if any(e["type"] == "job_status" for e in session.events.since(0)):
                break
            time.sleep(0.01)
        [status] = [e for e in session.events.since(0) if e["type"] == "job_status"][:1]
        assert status["auto_activate"] is True
    finally:
        session.close()


def test_cancelled_auto_activation_is_never_revived(monkeypatch):
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        _own_job(session)
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        assert session.watcher.set_auto_activate("job-run", False)
        # Theo dõi lại (vd sau khi hết giờ chờ) không được bật lại từ R.
        session.watcher._stopped.set()
        session.watcher._threads["job-run"].join(timeout=5)
        session.watcher._stopped.clear()
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        assert session.watcher.auto_activate("job-run") is False
        watch_events = [e for e in session.events.since(0) if e["type"] == "job_watch"]
        assert watch_events[-1]["auto_activate"] is False
        # Job xong rồi watch_job: vẫn không kích hoạt.
        api.status = 1
        session.watcher._threads["job-run"].join(timeout=5)
        session.team.watch_job(api, "job-run")
        assert api.activated == []
    finally:
        session.close()


def test_cancel_is_refused_once_activation_started():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        with session.watcher._lock:
            session.watcher._auto["job-run"] = "activating"        # đang kích hoạt
        assert session.watcher.set_auto_activate("job-run", False) == "in_progress"
        assert not [e for e in session.events.since(0) if e["type"] == "auto_activate_changed"]
        assert "ĐANG kích hoạt" in session.team.set_auto_activate(api, "job-run", enabled=False)["error"]
    finally:
        session.close()


@pytest.mark.parametrize("message,mentions", [
    ("train trên dataset deploy_logs", False),
    ("dùng dataset activation-data", False),
    ("xong thì deployment luôn", True),
    ("activate it when done", True),
])
def test_dataset_names_are_not_activation_requests(message, mentions):
    from agent.team import _mentions_activation

    assert _mentions_activation([message]) is mentions


# ------------------------------------------------- báo đúng cho người dùng / Manager (vòng 7)

def test_cancel_by_button_is_told_to_the_manager_and_needs_a_new_request_to_undo(monkeypatch):
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
        monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
        session.messages.append({"role": "user", "content": "train xong kích hoạt luôn"})
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        body = {"session_id": "s1", "access_token": "token", "job_id": "job-run", "enabled": False}
        assert request("POST", "/agent/auto-activate", json=body).status_code == 200
        assert any("HUỶ tự kích hoạt" in e and "job-run" in e for e in session.pending_events)
        # Câu "kích hoạt luôn" TRƯỚC lúc huỷ không đủ để LLM bật lại.
        assert session.team.set_auto_activate(api, "job-run", enabled=True)["ok"] is False
        session.messages.append({"role": "user", "content": "à thôi, kích hoạt lại giúp tôi"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True)["ok"] is True
        assert session.watcher.auto_state("job-run") == "pending"
    finally:
        session.close()


def test_reset_keeps_re_enabling_possible():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        for text in ["a", "b", "train xong kích hoạt luôn"]:
            session.messages.append({"role": "user", "content": text})
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        assert session.team.set_auto_activate(api, "job-run", enabled=False)["ok"]
        session.reset()
        session.messages.append({"role": "user", "content": "kích hoạt lại đi"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True)["ok"] is True
    finally:
        session.close()


def test_rewatch_without_requirements_uses_the_promised_constraints(monkeypatch):
    from agent import watcher as watcher_module

    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        strict = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.95}]}}
        monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", -10_000)
        session.watcher.watch("job-run", max_time=1, requirements=strict)
        session.watcher._threads["job-run"].join(timeout=5)
        monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", 15 * 60)
        api.status = 1
        session.watcher.watch("job-run", max_time=60, requirements=None)     # vd sau reset
        session.watcher._threads["job-run"].join(timeout=5)
        [done] = [e for e in session.events.since(0) if e["type"] == "job_done"]
        assert done["verification"]["checks"][0]["metric"] == "accuracy"     # lý do đúng: theo ràng buộc đã hứa
    finally:
        session.close()


def test_states_are_final_once_watching_ends():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        assert session.watcher.set_auto_activate("job-run", False) == "ok"
        api.status = 1
        session.watcher._threads["job-run"].join(timeout=5)
        assert session.watcher.auto_state("job-run") == "done"
        assert api.activated == []
    finally:
        session.close()


def test_hello_carries_the_auto_activation_state(monkeypatch):
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
        monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
        monkeypatch.setattr(server, "EVENTS_STREAM_SECONDS", 0.3)
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        result = request("POST", "/agent/events", json={"session_id": "s1", "access_token": "token", "after": 10_000})
        name, hello = _sse_events(result.text)[0]
        assert name == "hello" and hello["watching"] == ["job-run"] and hello["auto_activate"] == {"job-run": True}
    finally:
        session.close()


# ------------------------------------------------- vòng 8

def test_failed_turn_does_not_skew_the_cancel_mark_and_reports_the_change():
    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.messages.append({"role": "user", "content": "train xong kích hoạt luôn"})
        session.messages.append({"role": "assistant", "content": "Đã chạy job"})
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)

        def create(**_):
            session.team.set_auto_activate(api, "job-run", enabled=False)   # LLM huỷ trong lượt...
            error = RuntimeError("provider lỗi")
            error.status_code = 500
            raise error                                                     # ...rồi lượt hỏng

        session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with pytest.raises(RuntimeError):
            session.send("đừng kích hoạt nữa")
        assert any("HUỶ tự kích hoạt" in e and "job-run" in e for e in session.pending_events)
        session.messages.append({"role": "user", "content": "kích hoạt lại giúp tôi"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True)["ok"] is True
    finally:
        session.close()


def test_rewatch_after_timeout_restores_a_job_that_had_no_promise(monkeypatch):
    from agent import watcher as watcher_module

    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", -10_000)
        session.watcher.watch("job-run", max_time=1, requirements=None)      # không ai yêu cầu
        session.watcher._threads["job-run"].join(timeout=5)
        assert session.watcher.auto_state("job-run") == "expired"
        monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", 15 * 60)
        session.watcher.watch("job-run", max_time=60, requirements=None)
        assert session.watcher.auto_state("job-run") == "off"               # không phải "hết hiệu lực"
        session.messages.append({"role": "user", "content": "xong thì kích hoạt luôn nhé"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True)["ok"] is True
    finally:
        session.close()


# ------------------------------------------------- Codex review vòng 8 (C1-C5)

def test_uncheckable_constraint_disables_auto_activation():
    raw = {"user": {"intent": "train"}, "dataset": {"id": "dataset-1"}, "service": {"deploy": True},
           "problem": {"type": "regression", "constraints": [{"metric": "rmse", "op": "<=", "value": 1}]}}
    requirements, _, notes = normalize_requirements(raw, [{"id": "dataset-1", "name": "demo"}])
    assert requirements["problem"]["constraints"] == []
    assert requirements["service"]["deploy"] is False
    assert any("không kiểm được" in note for note in notes)


class CreatedThenFailedBackend(Backend):
    """Proxy trả lỗi SAU khi backend đã tạo job (hoặc backend treo)."""

    def __init__(self, error):
        super().__init__()
        self.error = error
        self.jobs = []

    def list_jobs(self):
        return self.jobs

    def start_training(self, dataset_id, config):
        self.training_calls.append((dataset_id, config))
        self.jobs.append({"_id": f"job-{len(self.jobs) + 1}", "user": {"id": "user-1"}, "status": 0,
                          "create_at": time.time(), "data": {"id": dataset_id}, "config": config})
        raise self.error


@pytest.mark.parametrize("error", [ApiError(502, "bad gateway"), ApiError(504, "gateway timeout"),
                                   ApiError(0, "timeout", timed_out=True)])
def test_create_with_unknown_outcome_is_neither_resent_nor_adopted(monkeypatch, error):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    backend = CreatedThenFailedBackend(error)
    result = tools.start_training(backend, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert result["ok"] is False and result["outcome_unknown"] is True
    assert result["possible_job_ids"] == ["job-1"]                # để kiểm, không tự nhận
    assert len(backend.training_calls) == 1                       # không gửi lại -> không có job trùng


def test_older_job_with_the_same_config_is_not_offered(monkeypatch):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)

    class OldJobBackend(CreatedThenFailedBackend):
        def start_training(self, dataset_id, config):
            self.training_calls.append((dataset_id, config))
            raise self.error                                       # lần này KHÔNG tạo job

    backend = OldJobBackend(ApiError(502, "bad gateway"))
    backend.jobs = [{"_id": "old", "user": {"id": "user-1"}, "status": 1, "create_at": time.time() - 30,
                     "data": {"id": "dataset-1"},
                     "config": {"target": "y", "metric_sort": "accuracy", "problem_type": "classification", "list_feature": ["x"]}}]
    result = tools.start_training(backend, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert result["outcome_unknown"] and result["possible_job_ids"] == []


def test_config_with_unknown_outcome_cannot_be_started_again(session, monkeypatch):
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    config_id = session.team.submit_config(session.api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    monkeypatch.setattr(session.api, "start_training", Mock(side_effect=ApiError(502, "bad gateway")))
    first = session.team.start_training(session.api, config_id)
    assert first["outcome_unknown"] is True
    again = session.team.start_training(session.api, config_id)
    assert again["ok"] is False and again["outcome_unknown"] is True
    assert session.api.start_training.call_count == 1


def test_unreadable_constraints_also_disable_auto_activation():
    for constraints in ("accuracy >= 0.9", ["accuracy >= 0.9"]):
        raw = {"user": {"intent": "train"}, "dataset": {"id": "dataset-1"}, "service": {"deploy": True},
               "problem": {"type": "classification", "constraints": constraints}}
        requirements, _, _ = normalize_requirements(raw, [{"id": "dataset-1", "name": "demo"}])
        assert requirements["service"]["deploy"] is False


def test_queued_turn_is_announced_as_running(session, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    entry = server._Entry(session, "user-1")
    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(server, "_TURN_POOL", pool)

    async def scenario():
        blocker = threading.Event()
        pool.submit(blocker.wait)
        queued = server._start_turn("s1", entry, "Chào", "t-queued")
        assert session.current_turn_id == "t-queued"              # đang xếp hàng vẫn báo trong hello
        queued.cancel()
        await asyncio.sleep(0.05)
        assert session.current_turn_id is None
        blocker.set()

    asyncio.run(scenario())
    pool.shutdown(wait=True)


@pytest.mark.parametrize("value,sent", [("false", False), ("0", False), (False, False), ("true", True), (True, True)])
def test_activate_flag_is_read_strictly(value, sent):
    calls = []

    class ActivateBackend(Backend):
        def activate_model(self, job_id, activate):
            calls.append(activate)
            return {}

    result = tools.activate_model(ActivateBackend(), "job-1", activate=value)
    assert result["ok"] and result["activated"] is sent and calls == [sent]


def test_unreadable_activate_flag_is_refused():
    assert tools.activate_model(Backend(), "job-1", activate="maybe")["ok"] is False


def test_explicit_null_max_time_falls_back_to_the_default():
    result = tools.prepare_training_config(Backend(), "dataset-1", "y", ["x"], "accuracy", "classification", max_time=None)
    assert result["ok"] and result["config"]["max_time"] == tools.DEFAULT_MAX_TIME


def test_hello_names_the_running_turn(session, monkeypatch):
    monkeypatch.setattr(server, "_owner_of", {"token": "user-1"}.get)
    monkeypatch.setitem(server._sessions, "s1", server._Entry(session, "user-1"))
    monkeypatch.setattr(server, "EVENTS_STREAM_SECONDS", 0.2)
    session.current_turn_id = "t-live"
    result = request("POST", "/agent/events", json={"session_id": "s1", "access_token": "token", "after": 0})
    assert _sse_events(result.text)[0][1]["turn_id"] == "t-live"


# ------------------------------------------------- Codex review vòng 10

@pytest.mark.parametrize("exc,maybe_sent", [
    (httpx.RemoteProtocolError("server disconnected"), True),     # backend có thể đã xử lý
    (httpx.ReadError("connection reset"), True),
    (httpx.ConnectError("refused"), False),                        # chưa gửi được
])
def test_transport_errors_say_whether_the_request_may_have_been_sent(exc, maybe_sent):
    def handler(request):
        raise exc

    client = HAutoMLClient("http://backend.test")
    client._http = httpx.Client(base_url="http://backend.test/api/v1", transport=httpx.MockTransport(handler))
    with pytest.raises(ApiError) as error:
        client.get_dataset_info("d")
    assert error.value.status_code == 0 and error.value.maybe_sent is maybe_sent


def test_disconnect_after_sending_a_create_is_not_resent(monkeypatch):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    backend = CreatedThenFailedBackend(ApiError(0, "server disconnected", maybe_sent=True))
    result = tools.start_training(backend, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert result["outcome_unknown"] is True and len(backend.training_calls) == 1


def test_create_is_resent_when_the_connection_never_opened(monkeypatch):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
    backend = Backend()
    backend.start_training, calls = failing_once(backend.start_training, 0)
    result = tools.start_training(backend, "dataset-1", "y", ["x"], "accuracy", "classification")
    assert result["ok"] is True and len(calls) == 2 and len(backend.training_calls) == 1


@pytest.mark.parametrize("constraints", [{}, False, 0, "", "accuracy >= 0.9"])
def test_any_malformed_constraints_value_disables_auto_activation(constraints):
    raw = {"user": {"intent": "train"}, "dataset": {"id": "dataset-1"}, "service": {"deploy": True},
           "problem": {"type": "classification", "constraints": constraints}}
    requirements, _, _ = normalize_requirements(raw, [{"id": "dataset-1", "name": "demo"}])
    assert requirements["service"]["deploy"] is False


# ------------------------------------------------- Codex review vòng 11

class AnswersBackend(Backend):
    """start_training trả kết quả do test quy định (và luôn ghi lại lần gọi)."""

    def __init__(self, outcome):
        super().__init__()
        self.outcome = outcome

    def start_training(self, dataset_id, config):
        self.training_calls.append((dataset_id, config))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.mark.parametrize("outcome", [
    {},                                                            # 2xx rỗng
    {"job_id": None},                                              # 2xx thiếu job_id
    ApiError(200, "Backend trả về dữ liệu không phải JSON"),       # 2xx hỏng
    ApiError(500, "Kafka lỗi"),                                    # có thể đã ghi job
])
def test_ambiguous_create_responses_lock_the_config(session, monkeypatch, outcome):
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    api = AnswersBackend(outcome)
    session.api = api
    config_id = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    first = session.team.start_training(api, config_id)
    second = session.team.start_training(api, config_id)
    assert first["outcome_unknown"] is True and second["outcome_unknown"] is True
    assert len(api.training_calls) == 1


def test_definite_rejection_leaves_the_config_usable(session):
    api = AnswersBackend(ApiError(422, "list_feature sai"))
    config_id = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    result = session.team.start_training(api, config_id)
    assert result["ok"] is False and not result.get("outcome_unknown")
    assert not session.team.handoff.configs[config_id].get("outcome_unknown")


# ------------------------------------------------- Claude verify (create-job safety)

def _unknown_then(session, monkeypatch, outcome):
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    api = AnswersBackend(outcome)
    session.api = api
    first = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    assert session.team.start_training(api, first)["outcome_unknown"] is True
    return api


def test_resubmitting_the_same_config_cannot_create_a_second_job(session, monkeypatch):
    api = _unknown_then(session, monkeypatch, ApiError(500, "lỗi sau khi ghi"))
    api.outcome = {"job_id": "job-2"}                               # lần sau backend "chạy được"
    again = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    result = session.team.start_training(api, again)
    assert result["ok"] is False and result["outcome_unknown"] is True
    assert len(api.training_calls) == 1


def test_matching_job_found_later_is_offered_instead_of_a_new_create(session, monkeypatch):
    api = _unknown_then(session, monkeypatch, ApiError(500, "lỗi sau khi ghi"))
    api.list_jobs = lambda: [{"_id": "job-1", "user": {"id": "user-1"}, "status": 0, "create_at": time.time(),
                              "data": {"id": "dataset-1"},
                              "config": {"target": "y", "metric_sort": "accuracy", "problem_type": "classification",
                                         "list_feature": ["x"]}}]
    again = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    result = session.team.start_training(api, again)
    assert result["possible_job_ids"] == ["job-1"] and len(api.training_calls) == 1


def test_long_after_with_no_matching_job_a_rerun_is_allowed(session, monkeypatch):
    from agent import team as team_module

    api = _unknown_then(session, monkeypatch, ApiError(500, "lỗi trước khi ghi"))
    monkeypatch.setattr(team_module, "_UNRESOLVED_RECHECK_SECONDS", 0)
    api.outcome = {"job_id": "job-2"}
    again = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    assert session.team.start_training(api, again)["ok"] is True
    assert len(api.training_calls) == 2


def test_failed_turn_after_an_unknown_create_is_told_to_the_manager(session, monkeypatch):
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    api = AnswersBackend(ApiError(500, "lỗi sau khi ghi"))
    session.api = api
    config_id = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]

    def create(**_):
        session.team.start_training(api, config_id)
        error = RuntimeError("provider lỗi")
        error.status_code = 500
        raise error

    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(RuntimeError):
        session.send("train đi")
    assert any("chưa rõ kết quả" in event and "KHÔNG chạy" in event for event in session.pending_events)


@pytest.mark.parametrize("error,unknown", [
    (ApiError(0, "disconnected", maybe_sent=True), True),
    (ApiError(500, "lỗi sau khi ghi"), True),
    (ApiError(400, "file hỏng"), False),
])
def test_ambiguous_dataset_upload_is_reported_as_unknown(error, unknown):
    class UploadBackend(Backend):
        def upload_dataset_content(self, **_):
            raise error

    result = tools.upload_dataset_file(UploadBackend(), "a.csv", b"x,y\n1,2\n", "a", "classification")
    assert result["ok"] is False and bool(result.get("outcome_unknown")) is unknown


# ------------------------------------------------- Claude verify (guard gaps, dataset listing)

def _job(job_id, status, features):
    return {"_id": job_id, "user": {"id": "user-1"}, "status": status, "create_at": time.time(),
            "data": {"id": "dataset-1"},
            "config": {"target": "y", "metric_sort": "accuracy", "problem_type": "classification", "list_feature": features}}


def test_reordered_features_are_still_the_same_run(session, monkeypatch):
    api = _unknown_then(session, monkeypatch, ApiError(500, "lỗi sau khi ghi"))
    api.list_jobs = lambda: [_job("job-1", 0, ["x"])]
    again = session.team.submit_config(api, "dataset-1", "y", ["x", "x"], "accuracy", "classification")
    # validate_config cảnh báo cột lặp nhưng vẫn cho chốt; khoá chống trùng so theo tập.
    result = session.team.start_training(api, again["config_id"])
    assert result["outcome_unknown"] is True and len(api.training_calls) == 1


def test_unreadable_job_list_keeps_blocking(session, monkeypatch):
    from agent import team as team_module

    api = _unknown_then(session, monkeypatch, ApiError(500, "lỗi sau khi ghi"))
    monkeypatch.setattr(team_module, "_UNRESOLVED_RECHECK_SECONDS", 0)
    api.list_jobs = Mock(side_effect=ApiError(500, "list lỗi"))
    api.outcome = {"job_id": "job-2"}
    again = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    result = session.team.start_training(api, again)
    assert result["outcome_unknown"] is True and len(api.training_calls) == 1


def test_finished_matching_job_no_longer_blocks_a_rerun(session, monkeypatch):
    api = _unknown_then(session, monkeypatch, ApiError(500, "lỗi sau khi ghi"))
    api.list_jobs = lambda: [_job("job-1", -1, ["x"])]               # job khớp đã hỏng
    api.outcome = {"job_id": "job-2"}
    again = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    assert session.team.start_training(api, again)["ok"] is True


def test_operation_agent_result_reports_unknown_creates_even_if_it_then_fails(session, monkeypatch):
    monkeypatch.setattr(tools, "_OUTCOME_UNKNOWN_WAIT", 0)
    api = AnswersBackend(ApiError(500, "lỗi sau khi ghi"))
    session.api = api
    config_id = session.team.submit_config(api, "dataset-1", "y", ["x"], "accuracy", "classification")["config_id"]
    error = RuntimeError("provider lỗi")
    error.status_code = 500
    session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=[
        response(tool="start_training", arguments={"config_id": config_id}),
        error,
    ]))))
    result = session.team.ask_operation_agent(api, "chạy config")
    assert result["ok"] is False
    assert result["outcome_unknown_creates"][0]["dataset_id"] == "dataset-1"


def test_unreadable_dataset_list_is_not_no_datasets():
    raw = {"user": {"intent": "train"}, "dataset": {"id": "6ae5b0d5e299bd53f30b0680"}}
    requirements, missing, notes = normalize_requirements(raw, None)
    assert requirements["dataset"]["id"] == "6ae5b0d5e299bd53f30b0680"
    assert not any("tải dataset lên" in item for item in missing)
    assert any("Không đọc được danh sách dataset" in note for note in notes)


# ------------------------------------------------- Codex final review (08:40)

def test_cancel_cannot_be_overwritten_by_a_concurrent_enable(monkeypatch):
    import threading
    from agent import team as team_module

    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=None)      # chưa hứa
        session.messages.append({"role": "user", "content": "xong thì kích hoạt luôn"})
        checking, release = threading.Event(), threading.Event()
        real = team_module._mentions_activation

        def slow_check(messages):
            checking.set()
            release.wait(5)                                                  # tool đang kiểm đồng ý...
            return real(messages)

        monkeypatch.setattr(team_module, "_mentions_activation", slow_check)
        tool = threading.Thread(target=lambda: session.team.set_auto_activate(api, "job-run", enabled=True))
        tool.start()
        checking.wait(5)
        cancel_done = threading.Event()
        button = threading.Thread(target=lambda: (session.team.change_auto_activate("job-run", False, by_button=True), cancel_done.set()))
        button.start()
        assert not cancel_done.wait(0.2)                                     # nút phải chờ tool xong
        release.set()
        tool.join(5)
        button.join(5)
        assert session.watcher.auto_state("job-run") == "cancelled"          # huỷ là sau cùng
    finally:
        session.close()


def test_duplicate_features_are_removed_before_training():
    result = tools.prepare_training_config(Backend(), "dataset-1", "y", ["x", "x"], "accuracy", "classification")
    assert result["ok"] and result["config"]["list_feature"] == ["x"]
    assert any("cột lặp" in w for w in result["warnings"])


def test_partially_checked_constraints_are_not_reported_as_met(session):
    from agent.watcher import verify_result

    job = {**SUCCESS_JOB, "job_id": "job-1"}                               # accuracy 0.8, không có r2
    requirements = {"problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.5},
                                                {"metric": "r2", "op": ">=", "value": 0.5}]}}
    verification = verify_result(job, requirements)
    assert verification["passed"] is None
    session._on_job_finished({**job, "status": 1, "verification": verification})
    assert "CHƯA kiểm đủ" in session.pending_events[0] and "ĐẠT các ràng buộc" not in session.pending_events[0]


def test_uppercase_excel_extension_is_normalized():
    from agent import uploads

    check = uploads.check_dataset_file("REPORT.XLSX", b"PK\x03\x04" + b"0" * 100)
    assert check.ok and check.clean_name == "REPORT.xlsx"


# ------------------------------------------- điều kiện kèm khi bật tự kích hoạt giữa chừng


class TypedJobBackend(ControlledJobBackend):
    """job-run có problem_type (để kiểm metric của điều kiện kích hoạt)."""

    def list_jobs(self):
        return [{**job, "config": {**job["config"], "problem_type": "classification"}} for job in super().list_jobs()]


def test_condition_given_when_enabling_mid_job_is_checked():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=None)      # lúc tạo: không hứa gì
        session.messages.append({"role": "user", "content": "nếu accuracy >= 0.9 thì tự kích hoạt khi xong"})
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "Accuracy", "op": ">=", "value": 0.9}],
        )
        assert result["ok"] and result["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
        api.status = 1                                                       # xong với accuracy 0.8
        session.watcher._threads["job-run"].join(timeout=5)
        assert api.activated == []
        [done] = [e for e in session.events.since(0) if e["type"] == "job_done"]
        assert done["verification"]["passed"] is False
    finally:
        session.close()


def test_new_condition_replaces_the_one_for_the_same_metric():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        loose = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.5}]}}
        session.watcher.watch("job-run", max_time=60, requirements=loose)
        session.messages.append({"role": "user", "content": "kích hoạt khi accuracy >= 0.9 thôi nhé"})
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert result["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
        api.status = 1
        session.watcher._threads["job-run"].join(timeout=5)
        assert api.activated == []                                           # 0.8 < 0.9
    finally:
        session.close()


def test_enabling_without_conditions_says_it_is_unconditional():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=None)
        session.messages.append({"role": "user", "content": "xong thì kích hoạt luôn"})
        result = session.team.set_auto_activate(api, "job-run", enabled=True)
        assert result["ok"] and result["checked_constraints"] == [] and "BẤT KỂ" in result["note"]
    finally:
        session.close()


@pytest.mark.parametrize("constraints", [
    [{"metric": "rmse", "op": "<=", "value": 1}],          # classification không có rmse
    [{"metric": "accuracy", "op": "~", "value": 0.9}],
    [{"metric": "accuracy", "op": ">=", "value": "cao"}],
    "accuracy >= 0.9",
])
def test_condition_that_cannot_be_checked_does_not_enable(constraints):
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=None)
        session.messages.append({"role": "user", "content": "đạt yêu cầu thì kích hoạt"})
        result = session.team.set_auto_activate(api, "job-run", enabled=True, constraints=constraints)
        assert result["ok"] is False
        assert "Chưa bật" in result["error"] or "KHÔNG bật" in result["error"]
        assert session.watcher.auto_activate("job-run") is False
    finally:
        session.close()


def test_failed_turn_cleanup_takes_the_auto_activation_lock():
    import threading

    api = ControlledJobBackend()
    session = _session_with(api)
    try:
        session.team._auto_cancelled_at = {"job-run": 5}
        with session.team._auto_lock:
            worker = threading.Thread(target=session.team.after_failed_turn)
            worker.start()
            worker.join(timeout=0.2)
            assert worker.is_alive()                                         # chờ khoá
        worker.join(timeout=5)
        assert session.team._auto_cancelled_at == {"job-run": 0}
    finally:
        session.close()


def test_refused_condition_cancels_an_unconditional_promise():
    # Đang hứa kích hoạt (không điều kiện), người dùng thêm điều kiện hệ thống không kiểm được:
    # không được để nguyên lời hứa vô điều kiện trong khi báo "không bật".
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "chỉ kích hoạt nếu rmse <= 1"})
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "rmse", "op": "<=", "value": 1}],
        )
        assert result["ok"] is False and "Đã HUỶ" in result["error"]
        assert result["auto_activate_state"] == "cancelled"
        assert session.watcher.auto_activate("job-run") is False
        api.status = 1
        session.watcher._threads["job-run"].join(timeout=5)
        assert api.activated == []
    finally:
        session.close()


def test_tightening_a_live_promise_needs_no_new_activation_words():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "nhớ là accuracy phải từ 0.9"})   # không nhắc "kích hoạt"
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert result["ok"] and result["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
    finally:
        session.close()


def test_loosening_a_live_promise_still_needs_the_user():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        strict = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]}}
        session.watcher.watch("job-run", max_time=60, requirements=strict)
        session.messages.append({"role": "user", "content": "job tới đâu rồi"})
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.5}],
        )
        assert result["ok"] is False
        assert result["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
    finally:
        session.close()


@pytest.mark.parametrize("old,new,tighter", [
    ({"metric": "accuracy", "op": ">=", "value": 0.8}, {"metric": "accuracy", "op": ">=", "value": 0.9}, True),
    ({"metric": "accuracy", "op": ">=", "value": 0.9}, {"metric": "accuracy", "op": ">", "value": 0.9}, True),
    ({"metric": "accuracy", "op": ">", "value": 0.9}, {"metric": "accuracy", "op": ">=", "value": 0.9}, False),
    ({"metric": "rmse", "op": "<=", "value": 2}, {"metric": "rmse", "op": "<=", "value": 1}, True),
    ({"metric": "rmse", "op": "<=", "value": 1}, {"metric": "rmse", "op": ">=", "value": 1}, False),
    ({"metric": "accuracy", "op": ">=", "value": 0.8}, {"metric": "f1_macro", "op": ">=", "value": 0.7}, True),
])
def test_only_tightens(old, new, tighter):
    from agent.team import _only_tightens

    assert _only_tightens([old], [new]) is tighter


def test_dropping_one_side_of_a_range_is_not_tightening():
    from agent.team import _only_tightens

    band = [{"metric": "accuracy", "op": "<=", "value": 0.99}, {"metric": "accuracy", "op": ">=", "value": 0.8}]
    assert _only_tightens(band, [{"metric": "accuracy", "op": ">=", "value": 0.85}]) is False
    assert _only_tightens(band, [
        {"metric": "accuracy", "op": ">=", "value": 0.85}, {"metric": "accuracy", "op": "<=", "value": 0.98},
    ]) is True


@pytest.mark.parametrize("metric,value,expected", [
    ("accuracy", 90, 0.9),
    ("mape", 10, 0.1),
    ("mape", 1, 0.01),            # "MAPE dưới 1%" - theo tỉ lệ là 100%, gần như luôn đạt
    ("mape", 0.5, 0.5),           # mơ hồ: giữ tỉ lệ, kèm ghi chú cách hiểu
    ("r2", 80, 0.8),
    ("accuracy", 0.9, 0.9),
    ("rmse", 10, 10),
    ("accuracy", 900, None),
    ("rmse", -1, None),
    ("f1_macro", -0.1, None),
])
def test_percent_values_are_scaled_to_ratios(metric, value, expected):
    from agent.team import scale_constraint_value

    assert scale_constraint_value(metric, value)[0] == expected


def test_percent_constraint_in_requirements_is_scaled():
    raw = {
        "intent": "train", "dataset": {}, "service": {"deploy": True},
        "problem": {"type": "regression", "constraints": [{"metric": "mape", "op": "<=", "value": 10}]},
    }
    requirements, _, notes = normalize_requirements(raw, None)
    assert requirements["problem"]["constraints"] == [{"metric": "mape", "op": "<=", "value": 0.1}]
    assert requirements["service"]["deploy"] is True and any("10%" in note for note in notes)


def test_activation_decision_uses_the_constraints_it_claimed():
    from agent.watcher import summarize_job

    # Ràng buộc đổi giữa lúc tóm tắt kết quả và lúc nhận việc kích hoạt: kiểm lại theo R vừa nhận.
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        loose = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.5}]}}
        session.watcher.watch("job-run", max_time=60, requirements=loose)
        session.watcher._stopped.set()
        session.watcher._threads["job-run"].join(timeout=5)
        job = {**SUCCESS_JOB, "_id": "job-run"}
        summary = summarize_job(job, loose)                     # đạt 0.5
        with session.watcher._lock:
            session.watcher._added_constraints["job-run"] = [{"metric": "accuracy", "op": ">=", "value": 0.9}]
        activation = session.watcher.activate_promised("job-run", summary, job)
        assert activation["skipped"] and api.activated == []
        assert summary["verification"]["passed"] is False      # điều hiện ra khớp điều quyết định
    finally:
        session.close()


def test_no_promise_is_finalized_atomically():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=None)    # off
        session.watcher._stopped.set()
        session.watcher._threads["job-run"].join(timeout=5)
        assert session.watcher.activate_promised("job-run", {}) is None
        assert session.watcher.auto_state("job-run") == "done"             # bật lọt vào sau: "finished"
    finally:
        session.close()


def test_job_events_carry_the_conditions_that_will_be_checked():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "kích hoạt nếu accuracy >= 0.9"})
        session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        events = session.events.since(0)
        [watch] = [e for e in events if e["type"] == "job_watch"]
        [changed] = [e for e in events if e["type"] == "auto_activate_changed"]
        assert watch["auto_activate_constraints"] == []
        assert changed["auto_activate_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
        assert session.watcher.auto_activate_constraints_map() == {"job-run": changed["auto_activate_constraints"]}
    finally:
        session.close()


def test_unconditional_auto_activation_is_not_reported_as_partly_checked():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        api.status = 1
        session.watcher._threads["job-run"].join(timeout=5)
        assert api.activated == ["job-run"]
        [done] = [e for e in session.events.since(0) if e["type"] == "job_done"]
        assert "verification" not in done
        assert "CHƯA kiểm đủ" not in session.pending_events[-1]
        assert "không đặt ràng buộc" in session.pending_events[-1]
    finally:
        session.close()


def test_retry_after_a_system_cancel_needs_valid_conditions():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "chỉ kích hoạt nếu accuracy >= 0.9"})
        bad = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy_score_x", "op": ">=", "value": 0.9}],
        )
        assert bad["ok"] is False and bad["auto_activate_state"] == "cancelled"
        # Cùng lượt, không điều kiện: không bật vô điều kiện (người dùng vừa đặt điều kiện).
        bare = session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[])
        assert bare["ok"] is False and "constraints" in bare["error"]
        # Cùng lượt, điều kiện đúng: bật được - người dùng không phải nói lại.
        good = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert good["ok"] and good["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
    finally:
        session.close()


def test_system_cancel_does_not_carry_consent_into_later_turns():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "chỉ kích hoạt nếu rmse <= 1"})
        session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[{"metric": "rmse", "op": "<=", "value": 1}])
        session.messages.append({"role": "assistant", "content": "..."})
        session.messages.append({"role": "user", "content": "job tới đâu rồi"})
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert result["ok"] is False and session.watcher.auto_activate("job-run") is False
    finally:
        session.close()


def test_system_cancel_mark_does_not_survive_a_failed_turn_or_reset():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "chỉ kích hoạt nếu rmse <= 1"})
        session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[{"metric": "rmse", "op": "<=", "value": 1}])
        assert session.team._system_cancelled_at == {"job-run": 1}
        session.messages.pop()                                    # lượt lỗi bị bỏ khỏi lịch sử
        session.team.after_failed_turn()
        assert session.team._system_cancelled_at == {}
        session.messages.append({"role": "user", "content": "job tới đâu rồi"})   # lại 1 tin người dùng
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert result["ok"] is False                              # không coi là "lượt vừa huỷ"
        session.team._system_cancelled_at = {"job-run": 1}
        session.team.reset()
        assert session.team._system_cancelled_at == {}
    finally:
        session.close()


def test_same_turn_retry_cannot_loosen_what_the_user_agreed_to():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        strict = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]}}
        session.watcher.watch("job-run", max_time=60, requirements=strict)
        session.messages.append({"role": "user", "content": "thêm điều kiện rmse <= 1"})       # không nhắc kích hoạt
        session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[{"metric": "rmse", "op": "<=", "value": 1}])
        looser = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.8}],
        )
        assert looser["ok"] is False and session.watcher.auto_activate("job-run") is False
        stricter = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.95}],
        )
        assert stricter["ok"] is True
    finally:
        session.close()


def test_needs_constraints_only_while_the_promise_is_cancelled():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "chỉ kích hoạt nếu rmse <= 1"})
        session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[{"metric": "rmse", "op": "<=", "value": 1}])
        api.status = 1                                            # job xong trong cùng lượt
        session.watcher._threads["job-run"].join(timeout=5)
        result = session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[])
        assert result["ok"] is False and "constraints" not in result["error"]
    finally:
        session.close()


def test_transient_job_read_error_fails_closed_and_can_be_retried(monkeypatch):
    from agent import tools as tools_module

    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.messages.append({"role": "user", "content": "kích hoạt nếu accuracy >= 0.9"})
        monkeypatch.setattr(tools_module, "find_own_job", lambda *_: (None, {"error": "503", "status_code": 503}))
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        # Lỗi tạm: không áp được điều kiện mới thì không để lời hứa CŨ (vô điều kiện) chạy tiếp.
        assert result["ok"] is False and result["auto_activate_state"] == "cancelled"
        assert "thử lại" in result["error"]
        monkeypatch.undo()
        retry = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert retry["ok"] and retry["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
    finally:
        session.close()


def test_retry_keeps_the_consent_the_first_call_had():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        strict = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.95}]}}
        session.watcher.watch("job-run", max_time=60, requirements=strict)
        session.messages.append({"role": "user", "content": "đạt accuracy >= 0.95 thì kích hoạt"})
        session.messages.append({"role": "user", "content": "hạ ngưỡng xuống 0.9"})
        bad = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": "0,9"}],
        )
        assert bad["ok"] is False and bad["auto_activate_state"] == "cancelled"
        good = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}],
        )
        assert good["ok"] and good["checked_constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]
    finally:
        session.close()


def test_expired_promise_can_be_requested_again_after_rewatch(monkeypatch):
    from agent import watcher as watcher_module

    grace = watcher_module._GRACE_SECONDS
    monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", -10_000)
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        _own_job(session)
        session.messages.append({"role": "user", "content": "train xong kích hoạt luôn"})
        session.watcher.watch("job-run", max_time=1, requirements=DEPLOY_R)
        session.watcher._threads["job-run"].join(timeout=5)
        assert session.watcher.auto_state("job-run") == "expired"
        monkeypatch.setattr(watcher_module, "_GRACE_SECONDS", grace)
        session.messages.append({"role": "user", "content": "theo dõi lại job đó"})
        session.team.watch_job(api, "job-run")
        assert session.watcher.auto_state("job-run") == "off"                 # không tự sống lại
        # Lời "kích hoạt" cũ không tính; lời mới thì bật được.
        assert session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[])["ok"] is False
        session.messages.append({"role": "user", "content": "xong thì kích hoạt luôn nhé"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[])["ok"] is True
    finally:
        session.close()


def test_message_received_before_a_button_cancel_is_not_newer_than_it():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        session.watcher.watch("job-run", max_time=60, requirements=DEPLOY_R)
        session.incoming_user_message = True                   # "kích hoạt khi xong nhé" đang xếp hàng
        assert session.team.change_auto_activate("job-run", False, by_button=True) == "ok"
        with session.team._auto_lock:
            session.messages.append({"role": "user", "content": "kích hoạt khi xong nhé"})
            session.incoming_user_message = False
        result = session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[])
        assert result["ok"] is False                          # lần bấm Huỷ là hành động sau cùng
        # Lượt đó hỏng trước khi vào lịch sử: mốc được kẹp lại, tin sau vẫn bật được.
        session.team._auto_cancelled_at["job-run"] = len(session.team._user_messages()) + 1
        session.team.clamp_auto_marks()
        session.messages.append({"role": "user", "content": "à kích hoạt lại đi"})
        assert session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[])["ok"] is True
    finally:
        session.close()


def test_successful_retry_restores_the_consent_window():
    api = TypedJobBackend()
    session = _session_with(api)
    try:
        strict = {"service": {"deploy": True}, "problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.95}]}}
        session.watcher.watch("job-run", max_time=60, requirements=strict)
        session.messages.append({"role": "user", "content": "đạt accuracy >= 0.95 thì kích hoạt"})
        session.messages.append({"role": "user", "content": "hạ ngưỡng xuống 0.9"})
        session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": "0,9"}])
        session.team.set_auto_activate(api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.9}])
        assert session.team._auto_cancelled_at["job-run"] == 0
        session.messages.append({"role": "user", "content": "hạ tiếp xuống 0.85"})
        result = session.team.set_auto_activate(
            api, "job-run", enabled=True, constraints=[{"metric": "accuracy", "op": ">=", "value": 0.85}],
        )
        assert result["ok"] is True                           # như khi không có lần gọi sai
    finally:
        session.close()
