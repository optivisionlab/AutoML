"""Agent regression tests; no backend, LLM credentials or training jobs required."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from agent import agent_openai, providers, server, skills, tools
from agent.api_client import HAutoMLClient
from agent.chat import ChatSession


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


def test_invalid_config_never_enters_handoff(session):
    session.api.get_dataset_features = lambda *_: {"x": False, "y": False}
    prepared = session.team.submit_config(
        session.api, "dataset-1", "y", ["x"], "accuracy", "classification",
    )
    assert prepared["ok"] is False
    assert session.team.handoff.configs == {}
    assert session.api.training_calls == []


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
