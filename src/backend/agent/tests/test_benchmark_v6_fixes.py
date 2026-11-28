"""
Lỗi tìm thấy ở pilot benchmark hautoml-v6-pilot3 (2026-11-28), khoá hành vi đã sửa.

- G12: người dùng ép dùng mọi cột kể cả GPA (quyết định GradeClass) và StudentID. Agent giữ đúng config người
  dùng chốt nhưng không cảnh báo rò rỉ target / cột định danh, và báo điểm như kết quả bình thường. Một nguyên
  nhân: `looks_like_id` không nhận tên kiểu CamelCase (`StudentID`, `PlayerID`), nên config không có cảnh báo.
- C03/C08 (góp ý phụ): agent hứa "lưu lại mẫu" - việc hệ thống không làm được.
"""
import pytest

from agent import tools
from agent.skills import load_skills


def _validate_module():
    return tools._load_skill_script("model-agent", "validate_config")


@pytest.mark.parametrize("column", ["StudentID", "PlayerID", "CustomerId", "userID", "user_id", "ID", "id_khach",
                                    "Order2ID", "uuid"])
def test_id_columns_are_recognised(column):
    assert _validate_module().looks_like_id(column)


@pytest.mark.parametrize("column", ["paid", "valid", "Fluid", "Humidity", "GPA", "AVID", "Age", "Android"])
def test_ordinary_columns_are_not_ids(column):
    assert not _validate_module().looks_like_id(column)


def test_config_with_camelcase_id_feature_carries_warning():
    module = _validate_module()
    schema = {"columns": [{"name": n, "dtype": "float64"} for n in ("StudentID", "GPA", "Age", "GradeClass")],
              "target_candidates": ["GradeClass"], "problem_type": "classification"}
    config = {"choose": "new_model", "problem_type": "classification", "target": "GradeClass",
              "list_feature": ["StudentID", "GPA", "Age"], "metric_sort": "f1_macro",
              "search_algorithm": "random_search", "max_time": 900}
    result = module.validate_config(config, schema, ["f1_macro", "accuracy"])
    assert any("StudentID" in w for w in result["warnings"])


def _skill_text(name):
    return next(s for s in load_skills() if s.name == name).instructions


def test_model_agent_reports_risky_user_forced_features():
    text = _skill_text("model-agent")
    assert "rò rỉ" in text and "người dùng chỉ định" in text.lower()


def test_manager_relays_leakage_warnings_and_does_not_overpromise():
    text = _skill_text("agent-manager")
    assert "rò rỉ" in text and "thổi phồng" in text
    assert "lưu" in text and "không hứa" in text.lower()
