"""
LLM chép sai ID 24 ký tự hex khi viết lại vào văn bản (rơi / thừa / sai một ký tự).

Gặp trong benchmark (2/430 lượt, đều do Agent Manager, đều rơi chữ "e" trong "...085e1..."):
- B03_r03: Manager giao việc với "6b085148e6a07f17f740902" thay cho "6b085e148e6a07f17f740902"; Data Agent
  nhận lỗi 400 rồi tự tìm ra ID đúng, và Manager báo người dùng rằng ID CỦA HỌ thiếu một chữ.
- D05_r01: câu trả lời cuối ghi job "6b085158e6a07f17f740908" thay cho "6b085e158e6a07f17f740908".

Code chuẩn hoá ID (không gọi LLM): chuỗi giống ID không khớp ID thật nào của người dùng nhưng gần duy nhất
một ID thật (khoảng cách sửa nhỏ nhất, không hoà) thì thay bằng ID thật; mơ hồ hay quá xa thì để nguyên.
"""
from types import SimpleNamespace

import pytest

from agent import agent_openai, chat as chat_module, ids, providers
from agent.chat import ChatSession
from agent.tests.test_agent import Backend

DS = ["6b085e148e6a07f17f740902", "6b085e148e6a07f17f740903", "6b085e148e6a07f17f740904"]
JOBS = ["6b085e158e6a07f17f740908", "6b085e1f8e6a07f17f740909"]
TYPO_DS = "6b085148e6a07f17f740902"     # B03_r03: rơi chữ e
TYPO_JOB = "6b085158e6a07f17f740908"    # D05_r01: rơi chữ e


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(providers, "tracing_enabled", lambda: False)
    monkeypatch.setattr(agent_openai, "_BACKOFF_BASE", 0.0)


class HexBackend(Backend):
    """Tài khoản có 3 dataset và 2 job với ID kiểu ObjectId (liên tiếp, chỉ khác vài ký tự cuối)."""

    def list_datasets(self):
        return [{"_id": d, "dataName": f"ds{i}"} for i, d in enumerate(DS)]

    def list_jobs(self):
        return [{"_id": j, "user": {"id": "user-1"}, "status": 1} for j in JOBS]


@pytest.fixture
def make_session():
    sessions = []

    def make(api, *user_messages):
        session = ChatSession(api=api, auto_login=False, verbose=False)
        session._config = SimpleNamespace(model="test-model", name="test")
        for text in user_messages:
            session.messages.append({"role": "user", "content": text})
        sessions.append(session)
        return session

    yield make
    for session in sessions:
        session.close()


# ------------------------------------------------------------------ hàm thuần


def test_dropped_character_is_restored_to_the_unique_closest_id():
    text, fixes = ids.canonicalize_ids(f"Phân tích dataset {TYPO_DS} giúp tôi", set(DS))
    assert text == f"Phân tích dataset {DS[0]} giúp tôi"
    assert fixes == [(TYPO_DS, DS[0])]


def test_known_ids_and_unrelated_hex_are_left_alone():
    known = set(DS)
    for text in (f"dataset {DS[1]}", "ID ffffffffffffffffffffffff không tồn tại", "hash 0123456789abcdef0123456789abcdef",
                 "không có ID nào", "giá trị 1.4608 và 11.9474"):
        assert ids.canonicalize_ids(text, known) == (text, [])


def test_ambiguous_near_miss_is_left_alone():
    # Sai đúng một ký tự cuối: cách ...902 và ...903 bằng nhau -> không đoán.
    typo = "6b085e148e6a07f17f74090a"
    assert ids.canonicalize_ids(f"dataset {typo}", set(DS[:2]) | {"6b085e148e6a07f17f74090b"})[1] == []


def test_far_away_token_is_left_alone():
    assert ids.canonicalize_ids("dataset 6b0aaaaaaaaaaaaaaaaaaaaa", set(DS)) == ("dataset 6b0aaaaaaaaaaaaaaaaaaaaa", [])


# ------------------------------------------------------------------ trong phiên chat


def test_delegation_task_carries_the_real_id_when_the_manager_mistyped_it(make_session, monkeypatch):
    api = HexBackend()
    session = make_session(api, f"Tạo cấu hình classification cho {DS[0]} với target NotAColumn, feature RI,Na.")
    seen = {}
    monkeypatch.setattr(session.team, "_run_subagent",
                        lambda agent, task, context="": seen.setdefault(agent, task) and {"ok": True, "report": "ok"})
    _, dispatch = session.team.tools_for("agent-manager")
    dispatch["ask_data_agent"](api, task=f"Phân tích dataset có id {TYPO_DS}", dataset_id=TYPO_DS)
    assert TYPO_DS not in seen["data-agent"]
    assert DS[0] in seen["data-agent"]


def test_user_typed_id_is_never_rewritten(make_session, monkeypatch):
    # Người dùng tự gõ ID (kể cả sai) thì giữ nguyên: không âm thầm sửa lời người dùng.
    api = HexBackend()
    session = make_session(api, f"Xem dataset {TYPO_DS}")
    seen = {}
    monkeypatch.setattr(session.team, "_run_subagent",
                        lambda agent, task, context="": seen.setdefault(agent, task) and {"ok": True, "report": "ok"})
    _, dispatch = session.team.tools_for("agent-manager")
    dispatch["ask_data_agent"](api, task=f"Phân tích dataset {TYPO_DS}")
    assert TYPO_DS in seen["data-agent"]


def test_final_answer_shows_the_real_job_id(make_session, monkeypatch):
    api = HexBackend()
    session = make_session(api, f"Cho tôi kết quả job {JOBS[0]}.")
    answer = f"Từ kết quả job **{TYPO_JOB}**: f1_macro = 0.7338."

    def fake_loop(llm, model, messages, *args, **kwargs):
        messages.append({"role": "assistant", "content": answer})
        return answer

    monkeypatch.setattr(chat_module, "run_tool_loop", fake_loop)
    session._llm = object()  # không dựng client LLM thật: vòng tool đã được giả lập
    tool_schemas, dispatch = session.team.tools_for("agent-manager")
    final = session._run_manager(tool_schemas, dispatch, "Job vừa hỏi có f1_macro bao nhiêu?")
    assert TYPO_JOB not in final and JOBS[0] in final
    assert session.messages[-1]["content"] == final
