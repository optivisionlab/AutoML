"""
Tests cho DeerFlow-AutoML Agent — Chạy với Mock LLM Server.

Test categories:
1. Config loading — hagent.yaml, LLM models, routing
2. LLM factory — create_chat_model cho các providers
3. Agent graph — StateGraph build, routing logic
4. Coordinator — prompt loading, keyword routing
5. Tools — automl_tools schema validation
6. SSE streaming — format validation
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import httpx

# Đảm bảo import path
BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ══════════════════════════════════════════════════════════
# 1. Config Loading Tests
# ══════════════════════════════════════════════════════════


class TestConfigLoading:
    """Test hagent.yaml config loading — không hardcode."""

    def test_load_config_returns_dict(self):
        from hagent.bridge.config import load_config
        load_config.cache_clear()
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert "llm" in cfg
        assert "agent" in cfg

    def test_llm_section_has_models(self):
        from hagent.bridge.config import get_llm_models
        models = get_llm_models()
        assert isinstance(models, list)
        assert len(models) >= 1

    def test_llm_models_have_required_fields(self):
        from hagent.bridge.config import get_llm_models
        for model in get_llm_models():
            assert "name" in model, f"Model thiếu 'name': {model}"
            assert "provider" in model, f"Model thiếu 'provider': {model}"
            assert "model" in model, f"Model thiếu 'model': {model}"

    def test_agent_config_has_routing(self):
        from hagent.bridge.config import get_routing_config
        routing = get_routing_config()
        assert isinstance(routing, dict)
        assert len(routing) >= 1

    def test_agent_config_has_suggestions(self):
        from hagent.bridge.config import get_suggestions
        suggestions = get_suggestions()
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1

    def test_cache_config(self):
        from hagent.bridge.config import get_cache_config
        cache = get_cache_config()
        assert "enabled" in cache
        assert "ttl_seconds" in cache
        assert "max_entries" in cache
        assert isinstance(cache["ttl_seconds"], int)

    def test_error_messages(self):
        from hagent.bridge.config import get_error_messages
        errors = get_error_messages()
        assert isinstance(errors, dict)
        assert "generic" in errors
        assert "timeout" in errors

    def test_prompt_file_exists(self):
        from hagent.bridge.config import load_prompt_file
        content = load_prompt_file()
        assert isinstance(content, str)
        assert len(content) > 50
        assert "{world_model_summary}" in content

    def test_env_var_override(self):
        """Config hỗ trợ env var override."""
        from hagent.bridge.config import get_agent_config
        original = get_agent_config()["max_iterations"]

        with patch.dict(os.environ, {"AGENT_MAX_ITERATIONS": "99"}):
            overridden = get_agent_config()["max_iterations"]
            assert overridden == 99


# ══════════════════════════════════════════════════════════
# 2. LLM Config Tests
# ══════════════════════════════════════════════════════════


class TestLLMConfig:
    """Test multi-provider LLM configuration."""

    def test_load_llm_configs(self):
        from hagent.agent.llm_config import load_llm_configs
        configs = load_llm_configs()
        assert len(configs) >= 1

    def test_model_config_dataclass(self):
        from hagent.agent.llm_config import ModelConfig
        cfg = ModelConfig(
            name="test",
            provider="openai",
            model="gpt-4o-mini",
            api_key="$OPENAI_API_KEY",
        )
        assert cfg.name == "test"
        assert cfg.provider == "openai"

    def test_resolve_api_key_env_var(self):
        from hagent.agent.llm_config import ModelConfig
        with patch.dict(os.environ, {"MY_KEY": "secret123"}):
            cfg = ModelConfig(name="t", provider="openai", model="m", api_key="$MY_KEY")
            assert cfg.resolve_api_key() == "secret123"

    def test_resolve_api_key_braces(self):
        from hagent.agent.llm_config import ModelConfig
        with patch.dict(os.environ, {"MY_KEY": "secret456"}):
            cfg = ModelConfig(name="t", provider="openai", model="m", api_key="${MY_KEY}")
            assert cfg.resolve_api_key() == "secret456"

    def test_resolve_api_key_literal(self):
        from hagent.agent.llm_config import ModelConfig
        cfg = ModelConfig(name="t", provider="openai", model="m", api_key="literal-key")
        assert cfg.resolve_api_key() == "literal-key"

    def test_get_default_model_config(self):
        from hagent.agent.llm_config import get_default_model_config
        cfg = get_default_model_config()
        assert cfg.name is not None
        assert cfg.provider in {"openai", "anthropic", "ollama", "openai_compatible"}

    def test_list_available_models(self):
        from hagent.agent.llm_config import list_available_models
        models = list_available_models()
        assert isinstance(models, list)
        for m in models:
            assert "name" in m
            assert "provider" in m

    def test_unsupported_provider_raises(self):
        from hagent.agent.llm_config import ModelConfig, _build_model
        cfg = ModelConfig(name="t", provider="unknown_provider", model="m")
        with pytest.raises(ValueError, match="không được hỗ trợ"):
            from hagent.agent.llm_config import create_chat_model
            # Patch configs to return our bad config
            with patch("hagent.agent.llm_config.get_default_model_config", return_value=cfg):
                create_chat_model()

    def test_create_chat_model_openai_compatible(self, mock_llm_server, mock_llm_base_url):
        """Tạo model OpenAI-compatible kết nối mock server."""
        from hagent.agent.llm_config import ModelConfig, _build_model

        cfg = ModelConfig(
            name="ci-mock",
            provider="openai_compatible",
            model="mock-model",
            api_key="test-key",
            base_url=mock_llm_base_url,
        )
        model = _build_model("openai_compatible", cfg, "test-key", 0.0, 1024)
        assert model is not None


# ══════════════════════════════════════════════════════════
# 3. Agent State Tests
# ══════════════════════════════════════════════════════════


class TestAgentState:
    """Test AutoMLState schema."""

    def test_state_has_messages(self):
        from hagent.agent.state import AutoMLState
        state: AutoMLState = {"messages": []}
        assert "messages" in state

    def test_dataset_context_typing(self):
        from hagent.agent.state import DatasetContext
        ctx: DatasetContext = {
            "id": "ds_001",
            "name": "iris.csv",
            "n_rows": 150,
            "n_cols": 5,
            "features": ["f1", "f2"],
            "target": "species",
            "problem_type": "classification",
        }
        assert ctx["problem_type"] == "classification"

    def test_job_context_typing(self):
        from hagent.agent.state import JobContext
        ctx: JobContext = {
            "id": "job_001",
            "dataset_id": "ds_001",
            "status": "completed",
            "models": ["RandomForest"],
            "best_model": "RandomForest",
            "best_score": 0.95,
            "metrics": {"accuracy": 0.95},
        }
        assert ctx["status"] == "completed"


# ══════════════════════════════════════════════════════════
# 4. Coordinator Tests
# ══════════════════════════════════════════════════════════


class TestCoordinator:
    """Test coordinator routing và prompt loading."""

    def test_keyword_route_data_analyst(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("Hiển thị danh sách dataset") == "data_analyst"

    def test_keyword_route_training(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("Bắt đầu huấn luyện model") == "training_monitor"

    def test_keyword_route_evaluator(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("So sánh kết quả các model") == "evaluator"

    def test_keyword_route_model_selector(self):
        from hagent.agent.coordinator import keyword_route
        assert keyword_route("Có những thuật toán nào khả dụng?") == "model_selector"

    def test_keyword_route_no_match(self):
        from hagent.agent.coordinator import keyword_route
        result = keyword_route("Xin chào!")
        # Có thể None hoặc match nhẹ — miễn không crash
        assert result is None or isinstance(result, str)

    def test_parse_response_route(self):
        from hagent.agent.coordinator import parse_coordinator_response
        target, text = parse_coordinator_response("[ROUTE:data_analyst] Phân tích dataset")
        assert target == "data_analyst"
        assert "Phân tích" in text

    def test_parse_response_direct(self):
        from hagent.agent.coordinator import parse_coordinator_response
        target, text = parse_coordinator_response("Xin chào, tôi là HAgent")
        assert target is None
        assert "HAgent" in text

    def test_world_model_formatting(self):
        from hagent.agent.coordinator import _format_world_model_summary

        # Empty
        assert "Chưa có" in _format_world_model_summary(None)

        # With data
        wm = {
            "datasets": {"ds_001": {"name": "iris.csv"}},
            "jobs": {"job_001": {"status": "completed"}},
        }
        summary = _format_world_model_summary(wm)
        assert "iris.csv" in summary
        assert "completed" in summary

    def test_load_system_prompt(self):
        from hagent.agent.coordinator import _load_system_prompt
        prompt = _load_system_prompt(None)
        assert isinstance(prompt, str)
        assert "Chưa có" in prompt  # world model empty placeholder


# ══════════════════════════════════════════════════════════
# 5. Tools Tests
# ══════════════════════════════════════════════════════════


class TestAutoMLTools:
    """Test tool definitions — schema, registry."""

    def test_all_tools_registered(self):
        from hagent.agent.tools.automl_tools import ALL_TOOLS
        assert len(ALL_TOOLS) >= 5

    def test_tool_names_unique(self):
        from hagent.agent.tools.automl_tools import ALL_TOOLS
        names = [t.name for t in ALL_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_tools_have_descriptions(self):
        from hagent.agent.tools.automl_tools import ALL_TOOLS
        for tool in ALL_TOOLS:
            assert tool.description, f"Tool '{tool.name}' thiếu description"
            assert len(tool.description) > 10

    def test_tool_registries(self):
        from hagent.agent.tools.automl_tools import (
            DATASET_TOOLS,
            TRAINING_TOOLS,
            MODEL_TOOLS,
            SYSTEM_TOOLS,
        )
        assert len(DATASET_TOOLS) >= 2
        assert len(TRAINING_TOOLS) >= 2
        assert len(MODEL_TOOLS) >= 1
        assert len(SYSTEM_TOOLS) >= 1

    def test_cache_functions(self):
        from hagent.agent.tools.automl_tools import (
            _cache_key,
            _get_cached,
            _set_cache,
            _cache,
        )
        _cache.clear()

        key = _cache_key("/test", {"a": 1})
        assert _get_cached(key) is None

        _set_cache(key, {"result": "ok"})
        cached = _get_cached(key)
        assert cached == {"result": "ok"}


# ══════════════════════════════════════════════════════════
# 6. Graph Tests
# ══════════════════════════════════════════════════════════


class TestAgentGraph:
    """Test LangGraph StateGraph build."""

    def test_build_graph(self):
        from hagent.agent.graph import build_automl_graph
        graph = build_automl_graph()
        assert graph is not None

    def test_graph_compiles(self):
        from hagent.agent.graph import build_automl_graph
        graph = build_automl_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_should_continue_no_tool_calls(self):
        from hagent.agent.graph import should_continue
        from langchain_core.messages import AIMessage

        state = {"messages": [AIMessage(content="Hello")]}
        assert should_continue(state) == "end"

    def test_should_continue_with_tool_calls(self):
        from hagent.agent.graph import should_continue
        from langchain_core.messages import AIMessage

        msg = AIMessage(
            content="",
            tool_calls=[{"id": "1", "name": "test", "args": {}}],
        )
        state = {"messages": [msg]}
        assert should_continue(state) == "tools"


# ══════════════════════════════════════════════════════════
# 7. Integration Test (with Mock LLM)
# ══════════════════════════════════════════════════════════


class TestIntegrationMockLLM:
    """Integration test — agent + mock LLM server."""

    @pytest.mark.asyncio
    async def test_mock_llm_health(self, mock_llm_server):
        """Mock LLM server phản hồi health check."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:11435/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_mock_llm_models(self, mock_llm_server):
        """Mock LLM server liệt kê models."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:11435/v1/models")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["data"]) >= 1

    @pytest.mark.asyncio
    async def test_mock_llm_chat_completion(self, mock_llm_server):
        """Mock LLM server trả về chat completion."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://127.0.0.1:11435/v1/chat/completions",
                json={
                    "model": "mock-model",
                    "messages": [{"role": "user", "content": "Xin chào"}],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"]
            assert "HAgent" in data["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_mock_llm_tool_call(self, mock_llm_server):
        """Mock LLM server trả về tool call khi có tools."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "list_datasets",
                    "description": "List datasets",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://127.0.0.1:11435/v1/chat/completions",
                json={
                    "model": "mock-model",
                    "messages": [{"role": "user", "content": "Hiển thị danh sách dataset"}],
                    "tools": tools,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            choice = data["choices"][0]
            assert choice["finish_reason"] == "tool_calls"
            assert choice["message"]["tool_calls"][0]["function"]["name"] == "list_datasets"
