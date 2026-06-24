"""
DeerFlow-AutoML — Model Selector Sub-agent.

Chuyên đề xuất thuật toán ML phù hợp dựa trên dataset context,
problem type, và requirements của người dùng.

SRP: Chỉ xử lý domain model selection/recommendation.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage

from hagent.agent.state import AutoMLState
from hagent.agent.subagents import SubAgent
from hagent.agent.tools.automl_tools import MODEL_TOOLS, get_dataset_info

logger = logging.getLogger(__name__)


class ModelSelectorAgent(SubAgent):

    @property
    def name(self) -> str:
        return "model_selector"

    @property
    def prompt_file(self) -> str:
        return "model_selector.md"

    @property
    def tools(self) -> list:
        return list(MODEL_TOOLS) + [get_dataset_info]

    def _extract_context(self, response: AIMessage, state: AutoMLState) -> dict:
        updates: dict[str, Any] = {}
        if response.content and any(
            kw in response.content.lower()
            for kw in ["đề xuất", "recommend", "suggest", "phù hợp"]
        ):
            updates["current_phase"] = "model_selected"
        return updates


def _create_agent(**kwargs) -> ModelSelectorAgent:
    return ModelSelectorAgent(**kwargs)


_agent = _create_agent()


async def model_selector_node(state: AutoMLState) -> dict:
    """LangGraph node: Model Selector sub-agent."""
    return await _agent.run(state)
