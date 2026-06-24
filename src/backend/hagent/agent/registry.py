"""
DeerFlow-AutoML — Agent & Tool Registries.

Đọc YAML config để discover agents và tools tại runtime.
KHÔNG hardcode bất kỳ tên agent, module path, hay tool name nào.

SOLID:
  S — Registry chỉ làm 1 việc: đọc config → resolve → cung cấp
  O — Thêm agent mới chỉ cần thêm YAML, không sửa Python
  D — Graph/Coordinator inject registry, không import trực tiếp
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── Tool Registry ────────────────────────────────────────


def _build_tool_map() -> dict[str, Any]:
    """
    Build map: tool_name → tool_object.
    Đọc từ automl_tools.ALL_TOOLS — mỗi tool đã có .name attribute.
    """
    from hagent.agent.tools.automl_tools import ALL_TOOLS
    return {tool.name: tool for tool in ALL_TOOLS}


_tool_map: dict[str, Any] | None = None


def get_tool_map() -> dict[str, Any]:
    """Singleton tool map."""
    global _tool_map
    if _tool_map is None:
        _tool_map = _build_tool_map()
    return _tool_map


def resolve_tools(tool_names: list[str]) -> list[Any]:
    """
    Resolve danh sách tool names (từ YAML) → tool objects.

    Args:
        tool_names: Danh sách tên tools từ YAML config.

    Returns:
        Danh sách LangChain tool objects.
    """
    tmap = get_tool_map()
    tools = []
    for name in tool_names:
        if name in tmap:
            tools.append(tmap[name])
        else:
            logger.warning(
                "Tool '%s' trong config không tìm thấy trong registry. "
                "Có thể bạn đã đổi tên tool hoặc chưa đăng ký.",
                name,
            )
    return tools


# ── Agent Entry ──────────────────────────────────────────


@dataclass
class AgentEntry:
    """Một entry agent đã resolve từ YAML config."""
    name: str
    module_path: str
    node_function_name: str
    prompt_file: str
    tool_names: list[str] = field(default_factory=list)
    _node_fn: Callable | None = field(default=None, repr=False)

    def get_node_function(self) -> Callable:
        """Dynamic import + resolve node function."""
        if self._node_fn is None:
            try:
                module = importlib.import_module(self.module_path)
                self._node_fn = getattr(module, self.node_function_name)
            except (ImportError, AttributeError) as e:
                raise ImportError(
                    f"Không thể import '{self.module_path}.{self.node_function_name}' "
                    f"cho agent '{self.name}'. Kiểm tra YAML config. Error: {e}"
                ) from e
        return self._node_fn

    def get_tools(self) -> list[Any]:
        """Resolve tool names → tool objects."""
        return resolve_tools(self.tool_names)


# ── Agent Registry ───────────────────────────────────────


class AgentRegistry:
    """
    Registry đọc YAML config, resolve agents tại runtime.

    Cách dùng:
        registry = get_agent_registry()
        for name in registry.agent_names():
            node_fn = registry.get_node_function(name)
            graph.add_node(name, node_fn)
    """

    def __init__(self):
        self._agents: dict[str, AgentEntry] = {}
        self._loaded = False

    def load_from_config(self) -> None:
        """Đọc agent.subagents từ YAML config."""
        from hagent.bridge.config import get_subagents_config

        subagents_cfg = get_subagents_config()
        if not subagents_cfg:
            logger.warning("Không tìm thấy agent.subagents trong config.")
            return

        for agent_name, agent_cfg in subagents_cfg.items():
            entry = AgentEntry(
                name=agent_name,
                module_path=agent_cfg.get("module", ""),
                node_function_name=agent_cfg.get("node_function", ""),
                prompt_file=agent_cfg.get("prompt_file", ""),
                tool_names=agent_cfg.get("tools", []),
            )
            self._agents[agent_name] = entry
            logger.debug("Registered agent: %s → %s", agent_name, entry.module_path)

        self._loaded = True
        logger.info(
            "Agent registry loaded: %d agents [%s]",
            len(self._agents),
            ", ".join(self._agents.keys()),
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_from_config()

    def agent_names(self) -> set[str]:
        """Tên tất cả agents đã đăng ký."""
        self._ensure_loaded()
        return set(self._agents.keys())

    def get_entry(self, name: str) -> AgentEntry | None:
        """Lấy AgentEntry theo tên."""
        self._ensure_loaded()
        return self._agents.get(name)

    def get_node_function(self, name: str) -> Callable:
        """Lấy node function cho một agent (dynamic import)."""
        entry = self.get_entry(name)
        if entry is None:
            raise KeyError(f"Agent '{name}' chưa đăng ký trong YAML config.")
        return entry.get_node_function()

    def get_node_functions(self) -> dict[str, Callable]:
        """Lấy tất cả node functions: {name: callable}."""
        self._ensure_loaded()
        return {name: entry.get_node_function() for name, entry in self._agents.items()}

    def get_all_tools(self) -> list[Any]:
        """Lấy tất cả tools từ tất cả agents (deduplicated)."""
        self._ensure_loaded()
        seen = set()
        tools = []
        for entry in self._agents.values():
            for tool in entry.get_tools():
                if tool.name not in seen:
                    seen.add(tool.name)
                    tools.append(tool)
        return tools

    def is_valid_agent(self, name: str) -> bool:
        """Kiểm tra tên agent có hợp lệ không."""
        self._ensure_loaded()
        return name in self._agents


# ── Singleton ────────────────────────────────────────────

_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Singleton AgentRegistry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def reset_registry() -> None:
    """Reset registry — dùng khi test hoặc config thay đổi."""
    global _registry, _tool_map
    _registry = None
    _tool_map = None
