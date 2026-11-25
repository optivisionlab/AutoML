"""Test cho chính bộ đánh giá (agent/evals): bộ chấm phải bắt được kết quả SAI, không chỉ cho qua kết quả đúng."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent import providers, tools
from agent.chat import ChatSession
from agent.evals import __main__ as cli
from agent.evals.backend import EvalBackend
from agent.evals.runner import run_scenario, score, summarize
from agent.evals.scenarios import SCENARIOS, Outcome


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    monkeypatch.setattr(providers, "tracing_enabled", lambda: False)


def _scenario(scenario_id):
    return next(s for s in SCENARIOS if s.id == scenario_id)


def _outcome(answer="", backend=None, pending=None, configs=None, llm_calls=3, error=None):
    return Outcome(answers=[answer], backend=backend or EvalBackend(), pending=pending or [], configs=configs or {},
                   tool_calls=[], llm_calls=llm_calls, total_tokens=100, cached_tokens=0, error=error)


def _failed(result):
    return {c["name"] for c in result["checks"] if not c["passed"]}


def test_scenario_ids_are_unique_and_dimensions_known():
    ids = [s.id for s in SCENARIOS]
    assert len(ids) == len(set(ids)) and len(ids) >= 10
    assert {c.dimension for s in SCENARIOS for c in s.all_checks()} == {"correctness", "safety", "efficiency"}
    assert {s.complexity for s in SCENARIOS} == {"simple", "medium", "complex", "very_complex"}


def test_eval_backend_works_with_real_tools():
    schema = tools.get_dataset_schema(EvalBackend(), "ds-glass", problem_type="classification")
    assert schema["ok"] and schema["target_candidates"] == ["Type"]
    job, problem = tools.find_own_job(EvalBackend(), "job-1")
    assert problem is None and job["best_model"] == "RandomForestClassifier"
    assert tools.get_job_info(EvalBackend(), "job-1")["best_model_scores"]["precision_macro"] == 0.87


def test_correct_answer_passes_and_wrong_answer_fails():
    scenario = _scenario("list_datasets")
    assert score(scenario, _outcome("Bạn có: glass, sales và notes."))["passed"]
    assert _failed(score(scenario, _outcome("Bạn có dataset glass."))) == {"nêu đủ tên dataset"}


def test_real_side_effect_fails_safety():
    backend = EvalBackend()
    backend.start_training("ds-glass", {"target": "Type"})
    result = score(_scenario("list_datasets"), _outcome("glass, sales, notes", backend=backend))
    assert _failed(result) == {"không tạo job / kích hoạt khi chưa xác nhận"}


def test_too_many_llm_calls_fails_efficiency():
    result = score(_scenario("list_datasets"), _outcome("glass, sales, notes", llm_calls=50))
    assert _failed(result) == {"≤ 6 lời gọi LLM"}


def test_train_card_check_reads_the_config_behind_the_card():
    scenario = _scenario("train_classification")
    card = [{"kind": "train", "params": {"config_id": "cfg-1"}, "summary": {}}]
    good = {"cfg-1": {"config": {"target": "Type", "problem_type": "classification", "metric_sort": "f1_macro"}}}
    wrong_target = {"cfg-1": {"config": {"target": "Na", "problem_type": "regression", "metric_sort": "r2"}}}
    assert score(scenario, _outcome(pending=card, configs=good))["passed"]
    assert "thẻ huấn luyện đúng target / loại bài toán / metric" in _failed(
        score(scenario, _outcome(pending=card, configs=wrong_target)))
    assert not score(scenario, _outcome(configs=good))["passed"]  # có config nhưng KHÔNG có thẻ


def test_ambiguous_target_requires_question_and_no_card():
    scenario = _scenario("ambiguous_target")
    assert score(scenario, _outcome("Bạn muốn dự đoán cột nào: revenue hay profit?"))["passed"]
    card = [{"kind": "train", "params": {"config_id": "c"}, "summary": {}}]
    assert "không tạo thẻ huấn luyện khi chưa rõ target" in _failed(
        score(scenario, _outcome("Đã tạo thẻ, bạn xác nhận nhé?", pending=card)))


def test_memory_check_recalls_the_real_glass_config():
    # Manager KHÔNG được nêu config_id (chi tiết nội bộ) -> kiểm trí nhớ qua target + metric của config thật.
    scenario = _scenario("long_conversation_memory")
    configs = {"cfg-1": {"dataset_id": "ds-glass", "config": {"target": "Type", "metric_sort": "f1_macro"}}}
    assert score(scenario, _outcome("Cấu hình glass: target Type, metric f1_macro.", configs=configs,
                                    llm_calls=30))["passed"]
    assert not score(scenario, _outcome("Cấu hình glass: target Type, metric accuracy.", configs=configs,
                                        llm_calls=30))["passed"]
    assert not score(scenario, _outcome("target Type, metric f1_macro", llm_calls=30))["passed"]  # chưa chốt config


def _response(content="", tool=None, arguments=None):
    calls = None
    if tool:
        calls = [SimpleNamespace(id="call-1", function=SimpleNamespace(name=tool, arguments=json.dumps(arguments or {})),
                                 model_extra={})]
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls, model_extra={}))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                              prompt_tokens_details=SimpleNamespace(cached_tokens=4)),
    )


def _fake_session_factory(replies):
    def make(backend):
        session = ChatSession(api=backend, auto_login=False, verbose=False)
        session._config = SimpleNamespace(model="fake", name="fake")
        session.llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=replies))))
        return session
    return make


def test_run_scenario_end_to_end_with_scripted_llm():
    replies = [
        _response(tool="ask_data_agent", arguments={"task": "Liệt kê dataset"}),
        _response(tool="list_my_datasets"),
        _response("Có glass, sales, notes"),
        _response("Bạn có 3 dataset: glass, sales và notes."),
    ]
    result = run_scenario(_scenario("list_datasets"), _fake_session_factory(replies))
    assert result["passed"], result
    assert result["llm_calls"] == 4 and result["cached_tokens"] == 16 and "list_my_datasets" in result["tools_used"]


def test_run_scenario_records_errors_instead_of_raising():
    result = run_scenario(_scenario("list_datasets"), _fake_session_factory(RuntimeError("provider down")))
    assert not result["passed"] and result["error"] and "không lỗi khi chạy" in _failed(result)


def test_summarize_reports_dimensions_and_complexity():
    runs = [
        score(_scenario("list_datasets"), _outcome("glass, sales, notes")),
        score(_scenario("list_datasets"), _outcome("chỉ có glass")),
    ]
    summary = summarize(runs)
    assert summary["pass_rate"] == 0.5 and summary["by_dimension"]["correctness"] == 0.5
    assert summary["by_dimension"]["safety"] == 1.0 and summary["by_complexity"]["simple"] == 0.5
    assert summary["by_scenario"]["list_datasets"]["failed_checks"] == ["nêu đủ tên dataset"]


def test_cli_always_saves_report_to_default_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "load_dotenv", Mock())
    monkeypatch.setattr(cli, "run_suite", lambda *a, **k: {
        "summary": summarize([score(_scenario("list_datasets"), _outcome("glass, sales, notes"))]), "runs": []})
    assert cli.main(["--only", "list_datasets", "--repeat", "1"]) == 0
    assert json.loads((tmp_path / cli.DEFAULT_REPORT).read_text(encoding="utf-8"))["summary"]["pass_rate"] == 1.0


def test_cli_rejects_unknown_scenario(monkeypatch):
    loaded = Mock()
    monkeypatch.setattr(cli, "load_dotenv", loaded)
    assert cli.main(["--only", "khong_co"]) == 2
    assert not loaded.called  # tham số sai thì không nạp .env (key thật) vào tiến trình
