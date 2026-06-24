"""
Tests cho Phase 2 — Multi-Agent Sub-agents + Registry (SOLID).

Test categories:
1. SubAgent base class
2. Sub-agent instantiation & prompt loading
3. AgentRegistry + ToolRegistry
4. Coordinator routing (keyword + LLM parse) — dynamic
5. Graph build — dynamic from registry
6. Context extraction
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import httpx

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ══════════════════════════════════════════════════════════
# 1. SubAgent Base Class
# ══════════════════════════════════════════════════════════


class TestSubAgentBase:

    def test_import(self):
        from hagent.agent.subagents import SubAgent
        assert SubAgent is not None

    def test_fallback_prompt(self):
        from hagent.agent.subagents import SubAgent
        # SubAgent is abstract, create a concrete subclass
        class DummyAgent(SubAgent):
            @property
            def name(self): return "dummy"
            @property
            def prompt_file(self): return "nonexistent.md"
            @property
            def tools(self): return []

        agent = DummyAgent()
        prompt = agent._fallback_prompt()
        assert "dummy" in prompt

    def test_format_context_empty(self):
        from hagent.agent.subagents import SubAgent
        class DummyAgent(SubAgent):
            @property
            def name(self): return "d"
            @property
            def prompt_file(self): return "x.md"
            @property
            def tools(self): return []

        agent = DummyAgent()
        result = agent._format_context(None)
        assert "Chưa có" in result

    def test_format_context_with_data(self):
        from hagent.agent.subagents import SubAgent
        class DummyAgent(SubAgent):
            @property
            def name(self): return "d"
            @property
            def prompt_file(self): return "x.md"
            @property
            def tools(self): return []

        agent = DummyAgent()
        wm = {
            "datasets": {"ds1": {"name": "iris.csv"}},
            "jobs": {"j1": {"status": "completed", "best_model": "RF"}},
        }
        result = agent._format_context(wm)
        assert "iris.csv" in result
        assert "completed" in result

    def test_dependency_injection_llm_factory(self):
        """LLM factory inject qua constructor — SOLID DIP."""
        from hagent.agent.subagents import SubAgent
        class DummyAgent(SubAgent):
            @property
            def name(self): return "d"
            @property
            def prompt_file(self): return "x.md"
            @property
            def tools(self): return []

        mock_factory = lambda: "mock_llm"
        agent = DummyAgent(llm_factory=mock_factory)
        assert agent._create_llm() == "mock_llm"


# ══════════════════════════════════════════════════════════
# 2. Sub-agent Instantiation
# ══════════════════════════════════════════════════════════


class TestSubAgentInstances:

    def test_data_analyst(self):
        from hagent.agent.subagents.data_analyst import DataAnalystAgent
        agent = DataAnalystAgent()
        assert agent.name == "data_analyst"
        assert len(agent.tools) >= 2

    def test_model_selector(self):
        from hagent.agent.subagents.model_selector import ModelSelectorAgent
        agent = ModelSelectorAgent()
        assert agent.name == "model_selector"
        assert len(agent.tools) >= 2

    def test_training_monitor(self):
        from hagent.agent.subagents.training_monitor import TrainingMonitorAgent
        agent = TrainingMonitorAgent()
        assert agent.name == "training_monitor"
        assert len(agent.tools) >= 3

    def test_evaluator(self):
        from hagent.agent.subagents.evaluator import EvaluatorAgent
        agent = EvaluatorAgent()
        assert agent.name == "evaluator"
        assert len(agent.tools) >= 2

    def test_node_functions_callable(self):
        from hagent.agent.subagents.data_analyst import data_analyst_node
        from hagent.agent.subagents.model_selector import model_selector_node
        from hagent.agent.subagents.training_monitor import training_monitor_node
        from hagent.agent.subagents.evaluator import evaluator_node
        for fn in [data_analyst_node, model_selector_node, training_monitor_node, evaluator_node]:
            assert callable(fn)

    def test_prompts_load(self):
        from hagent.agent.subagents.data_analyst import DataAnalystAgent
        from hagent.agent.subagents.evaluator import EvaluatorAgent
        for AgentCls in [DataAnalystAgent, EvaluatorAgent]:
            agent = AgentCls()
            prompt = agent.load_prompt(None)
            assert len(prompt) > 20


# ══════════════════════════════════════════════════════════
# 3. Agent Registry + Tool Registry
# ══════════════════════════════════════════════════════════


class TestAgentRegistry:

    def test_tool_map_builds(self):
        from hagent.agent.registry import get_tool_map
        tmap = get_tool_map()
        assert len(tmap) >= 7  # ALL_TOOLS has 7 tools
        assert "list_datasets" in tmap
        assert "start_training" in tmap

    def test_resolve_tools(self):
        from hagent.agent.registry import resolve_tools
        tools = resolve_tools(["list_datasets", "get_dataset_info"])
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "list_datasets" in names

    def test_resolve_tools_invalid(self):
        from hagent.agent.registry import resolve_tools
        # Invalid tool name should be skipped with warning
        tools = resolve_tools(["nonexistent_tool"])
        assert len(tools) == 0

    def test_registry_loads(self):
        from hagent.agent.registry import get_agent_registry, reset_registry
        reset_registry()
        registry = get_agent_registry()
        names = registry.agent_names()
        assert len(names) >= 4
        assert "data_analyst" in names
        assert "evaluator" in names

    def test_registry_get_entry(self):
        from hagent.agent.registry import get_agent_registry
        registry = get_agent_registry()
        entry = registry.get_entry("data_analyst")
        assert entry is not None
        assert entry.module_path != ""
        assert entry.node_function_name != ""

    def test_registry_dynamic_import(self):
        from hagent.agent.registry import get_agent_registry
        registry = get_agent_registry()
        node_fn = registry.get_node_function("data_analyst")
        assert callable(node_fn)

    def test_registry_all_node_functions(self):
        from hagent.agent.registry import get_agent_registry
        registry = get_agent_registry()
        fns = registry.get_node_functions()
        assert len(fns) >= 4
        for name, fn in fns.items():
            assert callable(fn), f"{name} is not callable"

    def test_registry_is_valid_agent(self):
        from hagent.agent.registry import get_agent_registry
        registry = get_agent_registry()
        assert registry.is_valid_agent("data_analyst")
        assert not registry.is_valid_agent("nonexistent_agent")

    def test_registry_get_all_tools(self):
        from hagent.agent.registry import get_agent_registry
        registry = get_agent_registry()
        tools = registry.get_all_tools()
        assert len(tools) >= 5  # Deduplicated across agents
        names = [t.name for t in tools]
        assert "list_datasets" in names

    def test_reset_registry(self):
        from hagent.agent.registry import get_agent_registry, reset_registry
        r1 = get_agent_registry()
        reset_registry()
        r2 = get_agent_registry()
        assert r1 is not r2


# ══════════════════════════════════════════════════════════
# 4. Coordinator Routing — Dynamic
# ══════════════════════════════════════════════════════════


class TestCoordinatorRouting:

    def test_keyword_route_data(self):
        from hagent.agent.coordinator import keyword_route
        result = keyword_route("Hiển thị danh sách dataset")
        assert result == "data_analyst"

    def test_keyword_route_training(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("Bắt đầu huấn luyện model") == "training_monitor"

    def test_keyword_route_eval(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("So sánh kết quả các model") == "evaluator"

    def test_keyword_route_model(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("Có những thuật toán nào khả dụng?") == "model_selector"

    def test_parse_route_tag(self):
        from hagent.agent.coordinator import parse_coordinator_response
        target, text = parse_coordinator_response("[ROUTE:data_analyst] Phân tích dataset")
        assert target == "data_analyst"
        assert "Phân tích" in text

    def test_parse_route_invalid(self):
        from hagent.agent.coordinator import parse_coordinator_response
        target, _ = parse_coordinator_response("[ROUTE:nonexistent_xyz] Test")
        assert target is None

    def test_parse_no_route(self):
        from hagent.agent.coordinator import parse_coordinator_response
        target, text = parse_coordinator_response("Xin chào, tôi là HAgent")
        assert target is None

    def test_routing_instruction_dynamic(self):
        from hagent.agent.coordinator import _build_routing_instruction
        instruction = _build_routing_instruction()
        assert "ROUTE" in instruction
        # Agent names come from registry, not hardcoded
        from hagent.agent.registry import get_agent_registry
        for name in get_agent_registry().agent_names():
            assert name in instruction

    def test_valid_agents_from_registry(self):
        from hagent.agent.coordinator import _get_valid_agents
        agents = _get_valid_agents()
        assert len(agents) >= 4
        # These come from YAML, not hardcoded
        assert isinstance(agents, set)


# ══════════════════════════════════════════════════════════
# 5. Dynamic Graph Build
# ══════════════════════════════════════════════════════════


class TestDynamicGraph:

    def test_build_graph(self):
        from hagent.agent.graph import build_automl_graph, reset_graph
        reset_graph()
        graph = build_automl_graph()
        assert graph is not None

    def test_graph_has_dynamic_nodes(self):
        from hagent.agent.graph import build_automl_graph, reset_graph
        from hagent.agent.registry import get_agent_registry
        reset_graph()
        graph = build_automl_graph()
        node_names = set(graph.nodes.keys())

        # Fixed nodes
        for fixed in ["coordinator", "coordinator_tools", "sub_tools", "synthesize"]:
            assert fixed in node_names, f"Missing fixed node: {fixed}"

        # Dynamic nodes from registry
        registry = get_agent_registry()
        for agent_name in registry.agent_names():
            assert agent_name in node_names, f"Missing dynamic node: {agent_name}"

    def test_graph_compiles(self):
        from hagent.agent.graph import build_automl_graph, reset_graph
        reset_graph()
        compiled = build_automl_graph().compile()
        assert compiled is not None

    def test_coordinator_route_end(self):
        from hagent.agent.graph import coordinator_route
        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(content="Hello")], "next_agent": None}
        assert coordinator_route(state) == "end"

    def test_coordinator_route_subagent(self):
        from hagent.agent.graph import coordinator_route
        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(content="")], "next_agent": "data_analyst"}
        assert coordinator_route(state) == "data_analyst"

    def test_coordinator_route_tools(self):
        from hagent.agent.graph import coordinator_route
        from langchain_core.messages import AIMessage
        msg = AIMessage(content="", tool_calls=[{"id": "1", "name": "x", "args": {}}])
        state = {"messages": [msg], "next_agent": None}
        assert coordinator_route(state) == "coordinator_tools"

    def test_subagent_route_tools(self):
        from hagent.agent.graph import subagent_route
        from langchain_core.messages import AIMessage
        msg = AIMessage(content="", tool_calls=[{"id": "1", "name": "x", "args": {}}])
        state = {"messages": [msg]}
        assert subagent_route(state) == "sub_tools"

    def test_subagent_route_synthesize(self):
        from hagent.agent.graph import subagent_route
        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(content="Done")]}
        assert subagent_route(state) == "synthesize"

    def test_after_sub_tools_routes_back(self):
        from hagent.agent.graph import after_sub_tools
        state = {"messages": [], "next_agent": "training_monitor"}
        assert after_sub_tools(state) == "training_monitor"

    def test_after_sub_tools_no_agent(self):
        from hagent.agent.graph import after_sub_tools
        state = {"messages": [], "next_agent": None}
        assert after_sub_tools(state) == "synthesize"

    def test_no_hardcoded_agent_names_in_graph(self):
        """Verify graph.py doesn't contain hardcoded agent name sets."""
        import inspect
        from hagent.agent import graph
        source = inspect.getsource(graph)
        # Should NOT contain hardcoded set of agent names
        assert '{"data_analyst", "model_selector"' not in source
        assert "VALID_AGENTS = {" not in source


# ══════════════════════════════════════════════════════════
# 6. Context Extraction
# ══════════════════════════════════════════════════════════


class TestContextExtraction:

    def test_data_analyst_extract(self):
        from hagent.agent.subagents.data_analyst import DataAnalystAgent
        from langchain_core.messages import AIMessage, ToolMessage

        agent = DataAnalystAgent()
        tool_msg = ToolMessage(
            content=json.dumps({"id": "ds1", "name": "iris.csv", "n_rows": 150, "n_cols": 5}),
            name="get_dataset_info", tool_call_id="c1",
        )
        result = agent._extract_context(AIMessage(content=""), {"messages": [tool_msg]})
        assert "dataset_context" in result
        assert result["dataset_context"]["name"] == "iris.csv"

    def test_training_monitor_extract(self):
        from hagent.agent.subagents.training_monitor import TrainingMonitorAgent
        from langchain_core.messages import AIMessage, ToolMessage

        agent = TrainingMonitorAgent()
        tool_msg = ToolMessage(
            content=json.dumps({"job_id": "j1", "dataset_id": "d1", "status": "completed",
                                "best_model": "RF", "best_score": 0.95, "metrics": {"acc": 0.95}}),
            name="get_job_info", tool_call_id="c2",
        )
        result = agent._extract_context(AIMessage(content=""), {"messages": [tool_msg]})
        assert result["job_context"]["status"] == "completed"
        assert result["current_phase"] == "completed"

    def test_evaluator_extract(self):
        from hagent.agent.subagents.evaluator import EvaluatorAgent
        from langchain_core.messages import AIMessage, ToolMessage

        agent = EvaluatorAgent()
        msgs = [
            ToolMessage(content=json.dumps({"id": "j1", "best_model": "RF", "best_score": 0.92}),
                        name="get_job_info", tool_call_id="c1"),
            ToolMessage(content=json.dumps({"id": "j2", "best_model": "XGB", "best_score": 0.95}),
                        name="get_job_info", tool_call_id="c2"),
        ]
        result = agent._extract_context(AIMessage(content=""), {"messages": msgs})
        assert result["evaluation"]["best_job_id"] == "j2"
        assert result["evaluation"]["recommendation"] == "XGB"
