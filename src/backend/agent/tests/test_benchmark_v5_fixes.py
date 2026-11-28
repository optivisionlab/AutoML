"""
Lỗi tìm thấy ở benchmark hautoml-v5-01 (official, 2026-11-09), dựng lại offline để khoá hành vi đã sửa.

- B06_r01, ablation B04/B05: agent tự sửa giá trị người dùng đã chốt (max_time 5 -> 60, bỏ target khỏi danh
  sách feature, đổi accuracy -> r2) thay vì báo lại người dùng.
- B05_r05: provider trả HTTP 524 (Cloudflare: origin quá giờ) và lỗi đó không được thử lại.
- S06 (pilot): tên bảng SQL trùng tên một dataset đã có làm tin nhắn của người dùng bị coi là nói về dataset khác,
  nên chốt target chặn config của dataset vừa nhập.
- T04: agent khẳng định ràng buộc sai số dự báo 96 giờ đã đạt, dựa trên điểm CV một bước của engine.
"""
from types import SimpleNamespace

import pytest

from agent import agent_openai, providers, tools
from agent.chat import ChatSession
from agent.tests.test_agent import Backend, DatabaseBackend


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(providers, "tracing_enabled", lambda: False)
    monkeypatch.setattr(agent_openai, "_BACKOFF_BASE", 0.0)


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


class TableBackend(Backend):
    """dataset-1 có đúng các cột `columns`; `targets[problem_type]` là các cột làm target được."""

    def __init__(self, columns, targets):
        super().__init__()
        self.columns = columns
        self.targets = targets

    def get_dataset_preview(self, dataset_id):
        return {"rows": 40, "records": [{c: (i % 3) + 0.5 * j for j, c in enumerate(self.columns)} for i in range(40)]}

    def get_dataset_features(self, dataset_id, problem_type):
        return {c: c in self.targets.get(problem_type, ()) for c in self.columns}


def _submit(session, target, features, metric, problem_type, max_time=300, search="random_search"):
    return session.team.submit_config(
        session.api, "dataset-1", target, features, metric, problem_type, search, max_time,
    )


# ---------------------------------------------------------------- giá trị người dùng đã chốt (B06, B04, B05)


def test_max_time_the_user_fixed_is_not_raised_after_rejection(make_session):
    api = TableBackend(["x", "y"], {"classification": ["y"]})
    session = make_session(api, "Tạo cấu hình classification cho dataset-1, target y, feature x, accuracy, "
                                "random_search, max_time 5 giây. Không tự tăng thời gian và chưa train.")
    assert _submit(session, "y", ["x"], "accuracy", "classification", max_time=5)["ok"] is False  # < 60 s
    raised = _submit(session, "y", ["x"], "accuracy", "classification", max_time=60)
    assert raised["ok"] is False
    assert raised["user_fixed"] == {"max_time": 5}
    assert session.team.handoff.configs == {}


def test_feature_list_the_user_gave_is_not_trimmed(make_session):
    api = TableBackend(["x", "z", "y"], {"classification": ["y"]})
    session = make_session(api, "Tạo cấu hình classification cho dataset-1, target y; bắt buộc feature gồm x,z,y; "
                                "metric accuracy, random_search, max_time 300. Không tự sửa danh sách feature.")
    trimmed = _submit(session, "y", ["x", "z"], "accuracy", "classification")
    assert trimmed["ok"] is False
    assert trimmed["user_fixed"] == {"list_feature": ["x", "z", "y"]}
    assert session.team.handoff.configs == {}


def test_metric_the_user_named_is_not_swapped(make_session):
    api = TableBackend(["x", "y"], {"regression": ["y"]})
    session = make_session(api, "Tạo cấu hình regression cho dataset-1, target y, feature x, metric accuracy, "
                                "random_search, max_time 300. Không tự đổi metric và chưa train.")
    swapped = _submit(session, "y", ["x"], "r2", "regression")
    assert swapped["ok"] is False
    assert swapped["user_fixed"] == {"metric_sort": "accuracy"}


def test_problem_type_the_user_named_is_not_swapped(make_session):
    api = TableBackend(["x", "y"], {"regression": ["y"], "classification": ["y"]})
    session = make_session(api, "Tạo cấu hình regression cho dataset-1, target y, feature x, metric accuracy, "
                                "random_search, max_time 300. Không tự đổi metric và chưa train.")
    swapped = _submit(session, "y", ["x"], "accuracy", "classification")
    assert swapped["ok"] is False
    assert swapped["user_fixed"]["problem_type"] == "regression"


@pytest.mark.parametrize("message, features, metric, max_time", [
    # Đúng y như người dùng nói.
    ("Dùng dataset-1, classification target y, feature x,z, tối ưu accuracy. Dùng random_search, "
     "max_time 300 giây.", ["x", "z"], "accuracy", 300),
    # Đơn vị phút được quy ra giây.
    ("Dùng dataset-1, classification target y với feature x,z, tối ưu accuracy, max_time 5 phút.",
     ["x", "z"], "accuracy", 300),
    # Không liệt kê feature: agent tự chọn được.
    ("Dataset-1: dự đoán y, bài toán classification, dùng tất cả các cột còn lại làm feature.",
     ["x", "z"], "accuracy", 900),
    # Hai metric trong cùng câu (một để chọn model, một làm ràng buộc): không khoá metric nào.
    ("Dùng dataset-1, classification target y, feature x,z, tối ưu f1_macro. Yêu cầu f1_macro >= 0.5 và "
     "accuracy >= 0.5.", ["x", "z"], "f1_macro", 900),
])
def test_config_matching_what_the_user_said_still_passes(make_session, message, features, metric, max_time):
    api = TableBackend(["x", "z", "y"], {"classification": ["y"]})
    session = make_session(api, message)
    prepared = _submit(session, "y", features, metric, "classification", max_time=max_time)
    assert prepared["ok"], prepared


def test_only_the_latest_message_fixes_values(make_session):
    # F02: lượt sau người dùng đổi ý (bỏ feature, đổi metric) - giá trị của lượt trước không còn bị khoá.
    api = TableBackend(["x", "z", "w", "y"], {"classification": ["y"]})
    session = make_session(
        api,
        "Tạo cấu hình cho dataset-1, classification, target y, feature x,z,w, f1_macro, random_search, max_time 300.",
        "Đổi lại: bỏ feature w, tối ưu accuracy thay cho f1_macro, giữ nguyên các yêu cầu khác.",
    )
    prepared = _submit(session, "y", ["x", "z"], "accuracy", "classification")
    assert prepared["ok"], prepared


def test_leaked_target_can_still_be_removed_when_the_user_listed_no_features(make_session):
    api = TableBackend(["x", "z", "y"], {"classification": ["y"]})
    session = make_session(api, "Dataset-1: target y, classification, dùng tất cả các cột còn lại làm feature.")
    assert _submit(session, "y", ["x", "z", "y"], "accuracy", "classification")["ok"] is False  # rò rỉ target
    assert _submit(session, "y", ["x", "z"], "accuracy", "classification")["ok"] is True


@pytest.mark.parametrize("scenario_id, features, max_time, fixed", [
    ("user_max_time_too_small", ["RI", "Na", "Mg", "Al", "Si", "K", "Ca", "Ba", "Fe"], 60, {"max_time": 5}),
    ("user_feature_list_leaks_target", ["RI", "Na"], 300, {"list_feature": ["RI", "Na", "Type"]}),
])
def test_eval_scenarios_for_user_fixed_values_are_blocked_in_code(make_session, scenario_id, features, max_time, fixed):
    # Hai kịch bản eval (LLM thật) dựa trên giả định code chặn config "đã sửa": kiểm giả định đó offline.
    from agent.evals.backend import EvalBackend
    from agent.evals.scenarios import SCENARIOS

    scenario = next(s for s in SCENARIOS if s.id == scenario_id)
    api = EvalBackend()
    session = make_session(api, *scenario.turns)
    repaired = session.team.submit_config(api, "ds-glass", "Type", features, "f1_macro", "classification",
                                          "random_search", max_time)
    assert repaired["ok"] is False and repaired["user_fixed"] == fixed


# ---------------------------------------------------------------- HTTP 524 của provider (B05_r05)


@pytest.mark.parametrize("status", [520, 522, 524])
def test_cloudflare_gateway_errors_from_the_provider_are_retried(status):
    calls = []

    def create(**_):
        calls.append(1)
        if len(calls) == 1:
            error = RuntimeError(f"Error code: {status}")
            error.status_code = status
            raise error
        return "response"

    llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert agent_openai.create_completion(llm, model="m", messages=[]) == "response"
    assert len(calls) == 2


# ---------------------------------------------------------------- tên bảng SQL trùng tên dataset khác (S06)


IMPORTED_ID = "6aed00000000000000000001"


class CrabDatabaseBackend(DatabaseBackend):
    def list_datasets(self):
        return [{"_id": "dataset-2", "dataName": "crab_train"},   # dataset upload sẵn, trùng tên bảng nguồn
                {"_id": IMPORTED_ID, "dataName": "crab_pg"}]

    def get_dataset_preview(self, dataset_id):
        return {"rows": 40, "records": [{"length": 0.4 + i / 100, "age": 5 + i % 7} for i in range(40)]}

    def get_dataset_features(self, dataset_id, problem_type):
        return {"length": True, "age": True}


def test_table_named_like_another_dataset_still_identifies_the_imported_dataset(make_session):
    api = CrabDatabaseBackend()
    session = make_session(api, "Lấy toàn bộ bảng crab_train từ kết nối conn-1, nhập thành dataset mới, rồi dùng "
                                "dataset đó để regression dự đoán cột age từ tất cả các cột còn lại, tối ưu mae.")
    _, dispatch = session.team.tools_for("sql-agent")
    preview = dispatch["preview_sql_query"](api, connection_id="conn-1", sql='SELECT * FROM "public"."crab_train"')
    imported = dispatch["import_database_query"](api, connection_id="conn-1", preview_id=preview["preview_id"],
                                                 data_name="crab_pg")
    assert imported["dataset_id"] == IMPORTED_ID

    prepared = session.team.submit_config(api, IMPORTED_ID, "age", ["length"], "mae", "regression")
    assert prepared["ok"], prepared


def test_message_about_the_other_dataset_still_does_not_unlock_the_imported_one(make_session):
    # Sửa S06 không được làm hỏng chốt cũ: tin chỉ nói về dataset upload "sales" không mở khoá target.
    api = CrabDatabaseBackend()
    api.list_datasets = lambda: [{"_id": "dataset-2", "dataName": "sales"}, {"_id": IMPORTED_ID, "dataName": "crab_pg"}]
    session = make_session(api, "Nhập bảng crab_train từ conn-1 thành dataset mới.")
    _, dispatch = session.team.tools_for("sql-agent")
    preview = dispatch["preview_sql_query"](api, connection_id="conn-1", sql="SELECT * FROM crab_train")
    dispatch["import_database_query"](api, connection_id="conn-1", preview_id=preview["preview_id"], data_name="crab_pg")
    session.messages.append({"role": "user", "content": "Với dataset sales, target là age."})

    blocked = session.team.submit_config(api, IMPORTED_ID, "age", ["length"], "mae", "regression")
    assert blocked["ok"] is False and "chưa chọn cột mục tiêu" in blocked["error"]


# ---------------------------------------------------------------- điểm CV một bước của chuỗi thời gian (T04)


def _finished_job(problem_type, metric):
    return {
        "_id": "job-ts", "job_id": "job-ts", "status": 1, "user": {"id": "user-1"},
        "config": {"problem_type": problem_type, "metric_sort": metric, "target": "y", "list_feature": ["date"]},
        "best_model": "Ridge", "best_score": 5.4,
        "orther_model_scores": [{"model_name": "Ridge", "scores": {metric: 5.4}}],
        "data": {"id": "dataset-1", "name": "co2"},
    }


@pytest.mark.parametrize("problem_type, metric, expected", [
    ("time_series", "rmse", True), ("regression", "rmse", False), ("classification", "accuracy", False),
])
def test_job_info_says_when_scores_are_one_step_forecasts(monkeypatch, problem_type, metric, expected):
    monkeypatch.setattr(tools, "find_own_job", lambda client, job_id: (_finished_job(problem_type, metric), None))
    monkeypatch.setattr(tools, "job_score_source", lambda client, job_id: "cv")
    result = tools.get_job_info(object(), "job-ts")
    assert ("forecast_note" in result) is expected


@pytest.mark.parametrize("problem_type, expected", [("time_series", True), ("regression", False)])
def test_finished_job_event_says_constraints_were_checked_on_one_step_scores(make_session, problem_type, expected):
    session = make_session(Backend())
    session._on_job_finished({
        "job_id": "job-ts", "status": 1, "problem_type": problem_type, "metric_sort": "rmse",
        "best_model": "Ridge", "best_score": 5.4, "score_source": "cv",
        "verification": {"passed": True, "checks": [
            {"metric": "rmse", "op": "<=", "value": 16.4, "score": 5.4, "passed": True}]},
    })
    event = session.pending_events[-1]
    assert ("MỘT bước" in event) is expected
