"""
DeerFlow-AutoML — Training Monitor Sub-agent.

Chuyên quản lý training jobs: khởi tạo, theo dõi trạng thái,
báo cáo kết quả training.

SRP: Chỉ xử lý domain training lifecycle.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from hagent.agent.state import AutoMLState, JobContext
from hagent.agent.subagents import SubAgent
from hagent.agent.tools.automl_tools import TRAINING_TOOLS

logger = logging.getLogger(__name__)


class TrainingMonitorAgent(SubAgent):

    @property
    def name(self) -> str:
        return "training_monitor"

    @property
    def prompt_file(self) -> str:
        return "training_monitor.md"

    @property
    def tools(self) -> list:
        return list(TRAINING_TOOLS)

    def _extract_context(self, response: AIMessage, state: AutoMLState) -> dict:
        updates: dict[str, Any] = {}

        for msg in state.get("messages", []):
            if not hasattr(msg, "name"):
                continue

            try:
                data = (
                    json.loads(msg.content)
                    if isinstance(msg.content, str)
                    else msg.content
                )
                if not isinstance(data, dict) or "error" in data:
                    continue
            except (json.JSONDecodeError, TypeError):
                continue

            if msg.name == "start_training":
                updates["job_context"] = JobContext(
                    id=data.get("job_id", data.get("id", "")),
                    dataset_id=data.get("dataset_id", ""),
                    status="pending",
                    models=data.get("models", []),
                )
                updates["current_phase"] = "training"

            elif msg.name == "get_job_info":
                updates["job_context"] = JobContext(
                    id=data.get("job_id", data.get("id", "")),
                    dataset_id=data.get("dataset_id", ""),
                    status=data.get("status", "unknown"),
                    models=data.get("models", []),
                    best_model=data.get("best_model"),
                    best_score=data.get("best_score"),
                    metrics=data.get("metrics", {}),
                )
                if data.get("status") == "completed":
                    updates["current_phase"] = "completed"

        return updates


def _create_agent(**kwargs) -> TrainingMonitorAgent:
    return TrainingMonitorAgent(**kwargs)


_agent = _create_agent()


async def training_monitor_node(state: AutoMLState) -> dict:
    """LangGraph node: Training Monitor sub-agent."""
    return await _agent.run(state)
