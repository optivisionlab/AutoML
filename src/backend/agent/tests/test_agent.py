"""Agent regression tests; no backend, LLM credentials or training jobs required."""
import asyncio
import json
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


@pytest.mark.parametrize("status,retried", [(503, True), (504, False)])
def test_training_is_retried_only_when_backend_never_got_it(monkeypatch, status, retried):
    monkeypatch.setattr(tools, "_RETRY_DELAYS", (0, 0))
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
    names = [name for name, _ in _sse_events(result.text)]
    assert names == ["job_done", "reconnect"]


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
