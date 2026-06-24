"""
DeerFlow-AutoML — Data Analyst Sub-agent.

Chuyên phân tích datasets: liệt kê, xem thông tin chi tiết,
đề xuất preprocessing, feature engineering.

SRP: Chỉ xử lý domain datasets/features.
DIP: LLM factory inject từ base class.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from hagent.agent.state import AutoMLState, DatasetContext
from hagent.agent.subagents import SubAgent
from hagent.agent.tools.automl_tools import DATASET_TOOLS

logger = logging.getLogger(__name__)


class DataAnalystAgent(SubAgent):

    @property
    def name(self) -> str:
        return "data_analyst"

    @property
    def prompt_file(self) -> str:
        return "data_analyst.md"

    @property
    def tools(self) -> list:
        return list(DATASET_TOOLS)

    def _extract_context(self, response: AIMessage, state: AutoMLState) -> dict:
        """Extract dataset context từ tool results trong message history."""
        updates: dict[str, Any] = {}

        for msg in state.get("messages", []):
            if hasattr(msg, "name") and msg.name == "get_dataset_info":
                try:
                    data = (
                        json.loads(msg.content)
                        if isinstance(msg.content, str)
                        else msg.content
                    )
                    if isinstance(data, dict) and "error" not in data:
                        updates["dataset_context"] = DatasetContext(
                            id=data.get("id", data.get("_id", "")),
                            name=data.get("name", data.get("filename", "")),
                            n_rows=data.get("n_rows", data.get("row_count", 0)),
                            n_cols=data.get("n_cols", data.get("col_count", 0)),
                            features=data.get("features", data.get("columns", [])),
                            target=data.get("target", None),
                            problem_type=data.get("problem_type", None),
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

        return updates


def _create_agent(**kwargs) -> DataAnalystAgent:
    """Factory function — cho phép inject dependencies khi test."""
    return DataAnalystAgent(**kwargs)


# LangGraph node function
_agent = _create_agent()


async def data_analyst_node(state: AutoMLState) -> dict:
    """LangGraph node: Data Analyst sub-agent."""
    return await _agent.run(state)
