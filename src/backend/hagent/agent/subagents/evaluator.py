"""
DeerFlow-AutoML — Evaluator Sub-agent.

Chuyên đánh giá, so sánh kết quả training, và đề xuất model tốt nhất.

SRP: Chỉ xử lý domain evaluation/comparison.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from hagent.agent.state import AutoMLState, EvaluationResult
from hagent.agent.subagents import SubAgent
from hagent.agent.tools.automl_tools import get_job_info, list_jobs

logger = logging.getLogger(__name__)


class EvaluatorAgent(SubAgent):

    @property
    def name(self) -> str:
        return "evaluator"

    @property
    def prompt_file(self) -> str:
        return "evaluator.md"

    @property
    def tools(self) -> list:
        return [get_job_info, list_jobs]

    def _extract_context(self, response: AIMessage, state: AutoMLState) -> dict:
        updates: dict[str, Any] = {}

        job_results: list[dict] = []
        for msg in state.get("messages", []):
            if hasattr(msg, "name") and msg.name == "get_job_info":
                try:
                    data = (
                        json.loads(msg.content)
                        if isinstance(msg.content, str)
                        else msg.content
                    )
                    if isinstance(data, dict) and "error" not in data:
                        job_results.append(data)
                except (json.JSONDecodeError, TypeError):
                    pass

        if job_results:
            best_job = max(
                job_results,
                key=lambda j: j.get("best_score", 0) or 0,
                default=None,
            )

            updates["evaluation"] = EvaluationResult(
                job_ids=[j.get("id", j.get("job_id", "")) for j in job_results],
                comparison_table=job_results,
                best_job_id=best_job.get("id", "") if best_job else None,
                recommendation=best_job.get("best_model") if best_job else None,
            )
            updates["current_phase"] = "evaluated"

        return updates


def _create_agent(**kwargs) -> EvaluatorAgent:
    return EvaluatorAgent(**kwargs)


_agent = _create_agent()


async def evaluator_node(state: AutoMLState) -> dict:
    """LangGraph node: Evaluator sub-agent."""
    return await _agent.run(state)
