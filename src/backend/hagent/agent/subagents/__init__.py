"""
DeerFlow-AutoML — Sub-agent Base Class.

Cung cấp pattern chung cho tất cả sub-agents:
- Load system prompt từ file (config-driven, không hardcode path)
- Bind tools subset (mỗi sub-agent khai báo riêng)
- Thực thi LLM call + trả kết quả về state
- Dependency injection cho LLM factory (testable)

SOLID Principles:
  S — Mỗi sub-agent chỉ làm 1 việc (SRP)
  O — Mở rộng qua kế thừa, không sửa base (OCP)
  L — Sub-agents thay thế được cho nhau trong graph (LSP)
  I — Interface gọn: run() + _extract_context() (ISP)
  D — LLM factory inject qua constructor, không import trực tiếp (DIP)

Reference: DeerFlow's agent pattern (mỗi agent = prompt + tools + LLM)
"""

from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import AIMessage, SystemMessage

from hagent.agent.state import AutoMLState

logger = logging.getLogger(__name__)


def _default_prompts_dir() -> Path:
    """Lấy prompts directory từ config, fallback sang relative path."""
    try:
        from hagent.bridge.config import load_config
        cfg = load_config()
        agent_cfg = cfg.get("agent", {})
        prompt_path = agent_cfg.get("system_prompt_path", "./prompts/coordinator.md")
        # Derive prompts dir từ prompt file path
        base = Path(__file__).parent.parent.parent
        prompt_dir = (base / Path(prompt_path).parent)
        if prompt_dir.exists():
            return prompt_dir
    except Exception:
        pass
    return Path(__file__).parent.parent.parent / "prompts"


class SubAgent(abc.ABC):
    """
    Abstract base class cho DeerFlow-AutoML sub-agents.

    Mỗi sub-agent khai báo:
    - name (property): Tên agent (dùng cho routing)
    - prompt_file (property): Tên file markdown chứa system prompt
    - tools (property): Danh sách LangChain tools

    LLM factory được inject qua constructor — không import trực tiếp.
    """

    def __init__(
        self,
        *,
        llm_factory: Callable[[], Any] | None = None,
        prompts_dir: Path | None = None,
    ):
        """
        Args:
            llm_factory: Callable tạo ChatModel. None → dùng default.
            prompts_dir: Thư mục chứa prompt files. None → đọc từ config.
        """
        self._llm_factory = llm_factory
        self._prompts_dir = prompts_dir
        self._prompt_cache: str | None = None

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Tên sub-agent (dùng cho routing và logging)."""
        ...

    @property
    @abc.abstractmethod
    def prompt_file(self) -> str:
        """Tên file .md chứa system prompt."""
        ...

    @property
    @abc.abstractmethod
    def tools(self) -> list:
        """Danh sách LangChain tools mà agent được phép dùng."""
        ...

    # ── Prompt loading (config-driven) ───────────────────

    def _get_prompts_dir(self) -> Path:
        """Lấy prompts directory — ưu tiên injected, rồi config, rồi fallback."""
        if self._prompts_dir is not None:
            return self._prompts_dir
        return _default_prompts_dir()

    def load_prompt(self, world_model: dict | None = None) -> str:
        """Load và format system prompt từ file."""
        if self._prompt_cache is None:
            prompt_path = self._get_prompts_dir() / self.prompt_file
            if prompt_path.exists():
                self._prompt_cache = prompt_path.read_text(encoding="utf-8")
            else:
                logger.warning(
                    "Prompt file '%s' không tồn tại, dùng fallback.",
                    prompt_path,
                )
                self._prompt_cache = self._fallback_prompt()

        wm_summary = self._format_context(world_model)
        try:
            return self._prompt_cache.format(
                world_model_summary=wm_summary,
                agent_name=self.name,
            )
        except KeyError:
            return self._prompt_cache

    def _fallback_prompt(self) -> str:
        """Prompt mặc định khi không tìm thấy file."""
        return (
            f"Bạn là {self.name}, một sub-agent chuyên biệt trong hệ thống HAutoML. "
            f"Hãy hoàn thành nhiệm vụ được giao và trả lời rõ ràng.\n\n"
            f"## Context\n{{world_model_summary}}"
        )

    def _format_context(self, world_model: dict | None) -> str:
        """Format world model thành context string."""
        if not world_model:
            return "Chưa có dữ liệu context."

        lines = []
        datasets = world_model.get("datasets", {})
        jobs = world_model.get("jobs", {})

        if datasets:
            ds_list = [
                f"  - {did}: {d.get('name', '?')}"
                for did, d in list(datasets.items())[:5]
            ]
            lines.append(f"**Datasets ({len(datasets)}):**\n" + "\n".join(ds_list))
        if jobs:
            job_list = [
                f"  - {jid}: {j.get('status', '?')} ({j.get('best_model', 'N/A')})"
                for jid, j in list(jobs.items())[:5]
            ]
            lines.append(f"**Jobs ({len(jobs)}):**\n" + "\n".join(job_list))

        return "\n".join(lines) if lines else "Chưa có dữ liệu context."

    # ── LLM factory (dependency injection) ───────────────

    def _create_llm(self):
        """Tạo LLM instance — ưu tiên injected factory, rồi default."""
        if self._llm_factory is not None:
            return self._llm_factory()

        from hagent.agent.llm_config import create_chat_model
        return create_chat_model()

    # ── Main execution ───────────────────────────────────

    async def run(self, state: AutoMLState) -> dict:
        """
        Thực thi sub-agent: load prompt → bind tools → gọi LLM.

        Returns:
            Dict update cho AutoMLState (messages + context updates).
        """
        messages = state["messages"]
        world_model = state.get("world_model")

        system_prompt = self.load_prompt(world_model)

        llm = self._create_llm()
        if self.tools:
            llm = llm.bind_tools(self.tools)

        full_messages = [SystemMessage(content=system_prompt)] + list(messages)

        logger.info("Sub-agent '%s' đang xử lý...", self.name)
        response = await llm.ainvoke(full_messages)

        state_update: dict[str, Any] = {"messages": [response]}

        context_update = self._extract_context(response, state)
        state_update.update(context_update)

        logger.info(
            "Sub-agent '%s' hoàn thành. Tool calls: %d",
            self.name,
            len(response.tool_calls)
            if hasattr(response, "tool_calls") and response.tool_calls
            else 0,
        )
        return state_update

    def _extract_context(self, response: AIMessage, state: AutoMLState) -> dict:
        """
        Override trong sub-class để extract domain-specific context.
        Default: không extract gì.
        """
        return {}
