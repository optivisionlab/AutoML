"""
Kiểm tra luồng đa agent mà KHÔNG cần LLM thật hay backend thật.

    cd src/backend
    python -m agent.tests.agents_test

LLM giả trả lời theo kịch bản của từng agent (nhận ra agent qua system prompt),
backend giả giữ dataset glass + job trong bộ nhớ. Nhờ vậy đi được trọn luồng:

    Manager → Prompt Agent → Data Agent → Model Agent → validate_config
            → Operation Agent → start_training → watcher → kiểm định → sự kiện

và kiểm được các chốt chặn bằng code (config bịa cột, chạy config chưa kiểm,
chạy trùng, job của người khác) - những thứ không được phép phụ thuộc vào việc
LLM có ngoan hay không. Không tốn quota, chạy trong vài giây.
"""

# Standard libraries
import json
import os
import time
import traceback
from types import SimpleNamespace

# Chạy watcher nhanh trong test. Đặt TRƯỚC khi import agent.
os.environ["AGENT_JOB_POLL_SECONDS"] = "2"
# Không đẩy trace của LLM giả lên Langfuse thật. Đặt rỗng thì load_dotenv()
# không ghi đè bằng key trong .env.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""

# Local modules
from agent import tools  # noqa: E402
from agent.api_client import ApiError  # noqa: E402
from agent.chat import ChatSession  # noqa: E402
from agent.team import normalize_requirements, parse_json  # noqa: E402
from agent.watcher import JobWatcher, verify_result  # noqa: E402


DATASET_ID = "66f0aa000000000000000001"
USER_ID = "u-1"
COLUMNS = ["Id", "RI", "Na", "Mg", "Al", "Si", "K", "Ca", "Ba", "Fe", "Type"]


# --------------------------------------------------------------- backend giả

class FakeApi:
    """Thay HAutoMLClient: cùng tên method, dữ liệu trong bộ nhớ."""

    def __init__(self) -> None:
        self.base_url = "fake://hautoml"
        self.access_token = "token-that"
        self.refresh_token = None
        self.user_id = USER_ID
        self.jobs: dict[str, dict] = {}
        self.started: list[dict] = []
        self.activated: list[tuple] = []
        # Số lần hỏi job trước khi job "xong".
        self.polls_until_done = 2

    def close(self) -> None:
        pass

    def get_me(self) -> dict:
        return {"_id": USER_ID}

    def list_datasets(self, owner_id: str) -> list:
        return [{"_id": DATASET_ID, "dataName": "glass", "dataType": "classification"}]

    def get_dataset_info(self, dataset_id: str) -> dict:
        if dataset_id != DATASET_ID:
            raise ApiError(404, "Không tìm thấy dataset")
        return {"_id": DATASET_ID, "dataName": "glass", "dataType": "classification"}

    def get_dataset_features(self, dataset_id: str, problem_type: str) -> dict:
        return {"features": {c: c == "Type" for c in COLUMNS}}

    def get_dataset_preview(self, dataset_id: str) -> dict:
        rows = [
            {c: (i if c == "Id" else (i % 6 + 1 if c == "Type" else round(1.5 + i / 100, 3))) for c in COLUMNS}
            for i in range(50)
        ]
        return {"rows": 214, "data": rows}

    def get_metrics(self, problem_type: str) -> dict:
        if problem_type == "regression":
            return {"metrics": ["mse", "mae", "mape", "r2"]}
        return {"metrics": ["accuracy", "balanced_accuracy", "f1_macro", "f1_weighted"]}

    def start_training(self, dataset_id: str, user_id: str, config: dict) -> dict:
        job_id = f"job-{len(self.jobs) + 1}"
        self.started.append(config)
        self.jobs[job_id] = {
            "job_id": job_id, "status": 0, "activate": 0, "config": config,
            "data": {"id": dataset_id, "name": "glass"}, "_polls": 0,
        }
        return {"status": "success", "job_id": job_id}

    def list_jobs(self, user_id: str) -> list:
        listed = []
        for job in self.jobs.values():
            job["_polls"] += 1
            if job["status"] == 0 and job["_polls"] > self.polls_until_done:
                job.update(
                    status=1,
                    best_model="RandomForestClassifier",
                    best_score=0.93,
                    best_params={"n_estimators": 200},
                    orther_model_scores=[{
                        "model_name": "RandomForestClassifier",
                        "scores": {"accuracy": 0.93, "f1_macro": 0.88},
                    }],
                )
            listed.append({k: v for k, v in job.items() if not k.startswith("_")})
        return listed

    def get_job_info(self, job_id: str) -> dict:
        return {k: v for k, v in self.jobs[job_id].items() if not k.startswith("_")}

    def activate_model(self, job_id: str, activate: bool) -> dict:
        self.activated.append((job_id, activate))
        self.jobs[job_id]["activate"] = 1 if activate else 0
        return {"job_id": job_id, "activate": int(activate)}


# ----------------------------------------------------------------- LLM giả

def _usage() -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)


def _message(content: str = "", calls: list | None = None) -> SimpleNamespace:
    tool_calls = None
    if calls:
        tool_calls = [
            SimpleNamespace(
                id=f"call-{i}-{name}",
                function=SimpleNamespace(name=name, arguments=json.dumps(args, ensure_ascii=False)),
                model_extra={},
            )
            for i, (name, args) in enumerate(calls)
        ]
    return SimpleNamespace(content=content, tool_calls=tool_calls, model_extra={})


def _tool_results(messages: list) -> list[dict]:
    return [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]


def _agent_of(messages: list) -> str:
    system = messages[0]["content"]
    for title in ("Prompt Agent", "Data Agent", "Model Agent", "Operation Agent"):
        if f"Bạn là {title}" in system:
            return title
    return "Manager"


class ScriptedLLM:
    """Mỗi agent một kịch bản, quyết định bước tiếp theo theo các kết quả tool đã có."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model: str, messages: list, **_kwargs):
        agent = _agent_of(messages)
        self.calls.append(agent)
        message = getattr(self, "_" + agent.split()[0].lower())(messages, _tool_results(messages))
        return SimpleNamespace(usage=_usage(), choices=[SimpleNamespace(message=message)])

    # Agent Manager: train trọn luồng.
    def _manager(self, messages, results):
        turn = [m for m in messages if m.get("role") == "tool"]
        last_user = max(i for i, m in enumerate(messages) if m.get("role") == "user")
        results = [json.loads(m["content"]) for m in messages[last_user:] if m.get("role") == "tool"]
        step = len(results)
        if step == 0:
            return _message(calls=[("ask_prompt_agent", {"request": "Huấn luyện mô hình trên glass, accuracy trên 0.9"})])
        if step == 1:
            dataset_id = results[0]["requirements"]["dataset"]["id"]
            return _message(calls=[("ask_data_agent", {"task": "Phân tích để huấn luyện", "dataset_id": dataset_id})])
        if step == 2:
            return _message(calls=[("ask_model_agent", {"task": "Chốt config", "dataset_id": DATASET_ID})])
        if step == 3:
            config_id = results[2]["configs"][0]["config_id"]
            return _message(calls=[("ask_operation_agent", {"task": f"Chạy config {config_id}"})])
        assert turn  # đã đi qua đủ 4 sub-agent
        return _message(f"Đã bắt đầu huấn luyện, job {results[3]['jobs_started'][0]}.")

    def _prompt(self, messages, results):
        # Cố ý trả dataset id SAI nhưng tên đúng: code phải sửa lại theo tên.
        return _message(json.dumps({
            "user": {"intent": "train", "expertise": "unknown"},
            "problem": {
                "type": "classification", "target": None, "metric": None,
                "constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}, {"metric": "tốt", "op": "~"}],
                "max_time": None,
            },
            "dataset": {"id": "id-bia", "name": "glass"},
            "model": {"preferred": [], "search_algorithm": None},
            "knowledge": {"notes": []},
            "service": {"deploy": False, "predict": False},
            "missing": [],
        }))

    def _data(self, messages, results):
        if not results:
            return _message(calls=[("get_dataset_schema", {"dataset_id": DATASET_ID})])
        return _message("glass: 214 dòng, 11 cột, target_candidates = [Type]. Loại cột Id (khoá).")

    def _model(self, messages, results):
        if not results:
            return _message(calls=[("list_metrics", {"problem_type": "classification"})])
        if len(results) == 1:
            # Cố ý cho target lọt vào list_feature: validate_config phải chặn.
            return _message(calls=[("submit_config", {
                "dataset_id": DATASET_ID, "target": "Type",
                "list_feature": ["RI", "Na", "Type"], "metric_sort": "accuracy",
            })])
        if len(results) == 2:
            assert results[1]["ok"] is False, results[1]
            return _message(calls=[("submit_config", {
                "dataset_id": DATASET_ID, "target": "Type",
                "list_feature": [c for c in COLUMNS if c not in ("Id", "Type")],
                "metric_sort": "accuracy", "rationale": "Type là ứng viên duy nhất",
            })])
        return _message(f"Đã chốt {results[-1]['config_id']}.")

    def _operation(self, messages, results):
        if not results:
            context = messages[0]["content"]
            config_id = context.split('"config_id": "')[1].split('"')[0]
            return _message(calls=[("start_training", {"config_id": config_id})])
        if len(results) == 1:
            # Thử chạy lại cùng config và chạy config bịa: cả hai phải bị chặn.
            config_id = results[0]["config"] and messages[0]["content"].split('"config_id": "')[1].split('"')[0]
            return _message(calls=[("start_training", {"config_id": config_id}), ("start_training", {"config_id": "cfg_bia"})])
        return _message(f"Job {results[0]['job_id']} đã vào hàng đợi.")


# ------------------------------------------------------------------- test

def test_parse_json() -> None:
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Đây là kết quả: {"a": {"b": 2}} nhé') == {"a": {"b": 2}}
    for bad in ("không có json", "[1, 2]"):
        try:
            parse_json(bad)
        except ValueError:
            continue
        raise AssertionError(f"parse_json phải từ chối: {bad!r}")


def test_normalize_requirements() -> None:
    datasets = [{"id": "a", "name": "glass", "type": "classification"}, {"id": "b", "name": "house", "type": "regression"}]

    r, missing, _ = normalize_requirements({"user": {"intent": "train"}, "dataset": {"id": "bịa"}}, datasets)
    assert r["dataset"]["id"] is None and missing, "id bịa + nhiều dataset → phải hỏi lại"
    assert set(r) == {"user", "problem", "dataset", "model", "knowledge", "service"}

    r, missing, _ = normalize_requirements({"user": {"intent": "train"}, "dataset": {"id": "b"}}, datasets)
    assert r["problem"]["type"] == "regression" and not missing, "loại bài toán suy từ dataset"

    r, _, _ = normalize_requirements({"problem": {"max_time": 5, "constraints": "xx"}}, datasets[:1])
    assert r["problem"]["max_time"] is None and r["problem"]["constraints"] == []


def test_verify_result() -> None:
    job = {
        "status": 1, "best_model": "RF", "best_score": 0.93, "config": {"metric_sort": "accuracy"},
        "orther_model_scores": [{"model_name": "RF", "scores": {"accuracy": 0.93, "f1_macro": 0.80}}],
    }
    ok = verify_result(job, {"problem": {"constraints": [{"metric": "accuracy", "op": ">=", "value": 0.9}]}})
    assert ok["passed"] is True
    bad = verify_result(job, {"problem": {"constraints": [{"metric": "f1_macro", "op": ">=", "value": 0.85}]}})
    assert bad["passed"] is False, "metric khác metric_sort phải đọc từ orther_model_scores"
    assert verify_result(job, None)["passed"] is None, "không có ràng buộc ≠ trượt"


def test_ownership_checks() -> None:
    api = FakeApi()
    assert tools.activate_model(api, "job-cua-nguoi-khac")["status_code"] == 404
    assert tools.get_job_info(api, "job-cua-nguoi-khac")["ok"] is False
    api.start_training(DATASET_ID, USER_ID, {"list_feature": ["RI"]})
    assert tools.activate_model(api, "job-1")["ok"] is False, "job chưa xong không được kích hoạt"
    assert api.activated == []


def test_full_flow() -> None:
    api = FakeApi()
    session = ChatSession(verbose=False, access_token="token-that", api=api)
    session.llm = ScriptedLLM()
    session._config = SimpleNamespace(name="fake", model="fake-model")

    events: list[dict] = []
    session.events.subscribe(events.append)

    reply = session.send("Huấn luyện mô hình trên glass, accuracy trên 0.9")
    assert "job-1" in reply, reply

    # Prompt Agent bịa id → code sửa theo tên; ràng buộc rác bị bỏ.
    r = session.team.handoff.requirements
    assert r["dataset"]["id"] == DATASET_ID
    assert r["problem"]["constraints"] == [{"metric": "accuracy", "op": ">=", "value": 0.9}]

    # validate_config chặn lần submit đầu, chỉ lần hai mới thành config.
    checks = [e["ok"] for e in events if e["type"] == "config_checked"]
    assert checks == [False, True], checks

    # Chỉ đúng MỘT job được tạo: chạy trùng và config bịa đều bị chặn.
    assert len(api.started) == 1 and "Type" not in api.started[0]["list_feature"]
    blocked = [e for e in events if e["type"] == "tool_call" and e["name"] == "start_training" and not e["ok"]]
    assert len(blocked) == 2, blocked

    # Thứ tự uỷ thác đúng sơ đồ.
    order = [e["agent"] for e in events if e["type"] == "agent_start"]
    assert order == ["prompt-agent", "data-agent", "model-agent", "operation-agent"], order

    # Watcher: chờ job xong, kiểm định đạt, sự kiện vào phiên cho lượt sau.
    deadline = time.time() + 15
    while time.time() < deadline and not any(e["type"] == "job_done" for e in events):
        time.sleep(0.2)
    done = next(e for e in events if e["type"] == "job_done")
    assert done["verification"]["passed"] is True, done
    assert any("đã huấn luyện xong" in text for text in session.pending_events)
    assert session.watcher.active() == []

    session.close()


def test_watcher_survives_expired_token() -> None:
    api = FakeApi()
    api.start_training(DATASET_ID, USER_ID, {"metric_sort": "accuracy"})
    real_list = api.list_jobs
    failures = {"left": 2}

    def flaky(user_id):
        if failures["left"]:
            failures["left"] -= 1
            raise ApiError(401, "Token hết hạn")
        return real_list(user_id)

    api.list_jobs = flaky
    events, finished = [], []
    watcher = JobWatcher(api, lambda type, **data: events.append(type), finished.append, poll=0.05)
    watcher.watch("job-1", max_time=60)

    deadline = time.time() + 5
    while time.time() < deadline and not finished:
        time.sleep(0.05)
    assert finished and finished[0]["status"] == 1, (events, finished)
    assert events.count("job_watch_warning") == 1, events


def _read_sse(response) -> list[tuple[str, dict]]:
    events, name = [], None
    for line in response.iter_lines():
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: "):
            events.append((name, json.loads(line[6:])))
    return events


def test_server_streams() -> None:
    from fastapi.testclient import TestClient

    from agent import server

    api = FakeApi()
    session = ChatSession(verbose=False, access_token="token-that", api=api)
    session.llm = ScriptedLLM()
    session._config = SimpleNamespace(name="fake", model="fake-model")
    server._sessions["test-session"] = server._Entry(session)
    server.EVENTS_STREAM_SECONDS = 1

    try:
        client = TestClient(server.app)
        body = {"message": "Huấn luyện mô hình trên glass", "session_id": "test-session", "access_token": "token-moi"}
        with client.stream("POST", "/agent/chat/stream", json=body) as response:
            assert response.status_code == 200
            streamed = _read_sse(response)

        names = [name for name, _ in streamed]
        assert names[0] == "session" and names[-1] == "reply", names
        assert "agent_start" in names and "config_checked" in names
        reply = streamed[-1][1]
        assert reply["agents"] == ["prompt-agent", "data-agent", "model-agent", "operation-agent"], reply
        assert reply["watching"] == ["job-1"] and "submit_config" in reply["tools"]
        # Token gửi kèm request phải tới được client mà watcher đang dùng.
        assert api.access_token == "token-moi"

        last_seq = streamed[-1][1].get("seq") or max(d.get("seq", 0) for _, d in streamed)
        with client.stream("POST", "/agent/events", json={"session_id": "test-session", "after": last_seq}) as response:
            background = _read_sse(response)
        assert background[-1][0] == "reconnect", background

        missing = client.post("/agent/events", json={"session_id": "khong-co"})
        assert missing.status_code == 404
    finally:
        server._sessions.pop("test-session").session.close()


def test_upload_reaches_manager() -> None:
    """File tải lên vào kho của user, và lượt chat sau Manager + Prompt Agent thấy id."""
    from fastapi.testclient import TestClient

    from agent import server

    api = FakeApi()
    uploaded = {}

    def upload_dataset_content(user_id, data_name, data_type, filename, content, mime_type="text/csv"):
        uploaded.update(user_id=user_id, name=data_name, filename=filename)
        return {"_id": "ds-moi", "dataName": data_name, "dataType": data_type}

    api.upload_dataset_content = upload_dataset_content
    session = ChatSession(verbose=False, access_token="token-that", api=api)
    server._sessions["upload-session"] = server._Entry(session)

    try:
        client = TestClient(server.app)
        response = client.post(
            "/agent/upload",
            data={"session_id": "upload-session", "access_token": "token-that", "data_type": "classification"},
            files={"file": ("iris.csv", b"a,b,label\n1,2,x\n3,4,y\n", "text/csv")},
        )
        assert response.status_code == 200, response.text
        assert uploaded["user_id"] == USER_ID, "user_id phải lấy từ token, không từ client"
        assert response.json()["dataset"]["id"] == "ds-moi"

        # Lượt chat kế tiếp: sự kiện được ghép vào đầu tin, Prompt Agent cũng thấy.
        seen = {}

        def capture(model, messages, **_):
            seen.setdefault("manager_user", messages[-1]["content"])
            return SimpleNamespace(usage=_usage(), choices=[SimpleNamespace(message=_message("ok"))])

        session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=capture)))
        session._config = SimpleNamespace(name="fake", model="fake")
        session.send("phân tích dataset vừa tải")
        assert "ds-moi" in seen["manager_user"] and seen["manager_user"].startswith("[Sự kiện]")
        assert any("ds-moi" in m for m in session.recent_user_messages(6))
        assert session.pending_events == []
    finally:
        server._sessions.pop("upload-session").session.close()


def main() -> None:
    cases = [
        test_upload_reaches_manager,
        test_parse_json,
        test_normalize_requirements,
        test_verify_result,
        test_ownership_checks,
        test_full_flow,
        test_watcher_survives_expired_token,
        test_server_streams,
    ]
    failed = 0
    for case in cases:
        try:
            case()
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {case.__name__}")
            traceback.print_exc()
        else:
            print(f"ok    {case.__name__}")

    print(f"\n{len(cases) - failed}/{len(cases)} đạt")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
