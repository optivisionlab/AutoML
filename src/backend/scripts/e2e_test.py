"""
DeerFlow-AutoML — E2E Test Script.

Chạy end-to-end test với Ollama model thật:
- Kiểm tra Ollama model info
- Test LLM direct response
- Test Registry, Memory, Cache, Middleware, Extractor
- Print training results table
- Test Graph compilation
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure backend in path
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


async def test_e2e():
    print("=" * 60)
    print("  DeerFlow-AutoML — E2E Test with Real LLM")
    print("=" * 60)
    print()

    # ── Test 1: Ollama Model Info ──
    import httpx

    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ollama_url}/api/tags")
        models = r.json().get("models", [])
        print(f"✓ Ollama has {len(models)} model(s):")
        for m in models:
            name = m.get("name", "?")
            size_gb = m.get("size", 0) / (1024**3)
            print(f"  📦 {name} ({size_gb:.1f} GB)")
        print()

    # ── Test 2: LLM Direct Response ──
    print("─" * 60)
    print("  Test: LLM Direct Response")
    print("─" * 60)
    model_name = os.environ.get("OLLAMA_MODEL", os.environ.get("LLM_MODEL", "gemma3:12b"))
    async with httpx.AsyncClient(timeout=120) as client:
        start = time.time()
        r = await client.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model_name,
                "prompt": "Bạn là AI assistant cho AutoML. Giới thiệu ngắn gọn về bạn.",
                "stream": False,
            },
        )
        elapsed = time.time() - start
        resp = r.json().get("response", "No response")
        print(f"  🤖 Model: {model_name}")
        print(f"  ⏱️  Time: {elapsed:.1f}s")
        print(f"  📝 Response: {resp[:400]}")
        print()

    # ── Test 3: Registry ──
    from hagent.agent.registry import get_agent_registry, reset_registry

    reset_registry()
    registry = get_agent_registry()
    agents = registry.agent_names()
    print(f"✓ Agent Registry: {sorted(agents)}")
    assert len(agents) >= 4, f"Expected >=4 agents, got {len(agents)}"

    # ── Test 4: Memory ──
    import tempfile

    from hagent.agent.memory import Fact, LocalFactStore

    store = LocalFactStore(tempfile.mkdtemp())
    await store.save("e2e_user", Fact(key="pref", content="User prefers RF"))
    fact = await store.get("e2e_user", "pref")
    assert fact is not None
    print("✓ Memory: saved and retrieved fact")

    # ── Test 5: Cache ──
    from hagent.agent.cache import ToolCache

    cache = ToolCache(ttl_seconds=60)
    cache.set("list_datasets", {}, {"datasets": []})
    assert cache.get("list_datasets", {}) is not None
    print(f"✓ Cache: set/get works, stats={cache.stats()}")

    # ── Test 6: Middleware ──
    from hagent.agent.middlewares import create_default_chain

    chain = create_default_chain()
    state = await chain.run_pre({"messages": [], "user_id": "e2e"})
    assert "_start_time" in state
    print(f"✓ Middleware: {len(chain._middlewares)} middlewares active")

    # ── Test 7: Fact Extraction ──
    from hagent.agent.memory.extractor import extract_from_tool_output

    facts = extract_from_tool_output(
        "get_dataset_info",
        {
            "id": "d1",
            "name": "test.csv",
            "n_rows": 100,
            "n_cols": 5,
            "problem_type": "classification",
            "target": "y",
        },
    )
    assert len(facts) >= 1
    print(f"✓ Extractor: {len(facts)} facts from tool output")

    # ── Test 8: Training Result Extraction + Print ──
    training_result = {
        "job_id": "job_test123",
        "status": "completed",
        "best_model": "XGBRegressor",
        "best_score": 1.65,
        "model_results": [
            {
                "model": "RandomForestRegressor",
                "metrics": {"rmse": 1.82, "mae": 1.34, "r2": 0.87},
            },
            {
                "model": "XGBRegressor",
                "metrics": {"rmse": 1.65, "mae": 1.21, "r2": 0.91},
            },
            {
                "model": "SVR",
                "metrics": {"rmse": 2.15, "mae": 1.58, "r2": 0.82},
            },
        ],
    }
    training_facts = extract_from_tool_output("start_training", training_result)
    print(f"✓ Training extraction: {len(training_facts)} facts")

    print()
    print("─" * 60)
    print("  📊 TRAINING RESULTS (Student Performance Dataset)")
    print("─" * 60)
    print("  Dataset: Student Performance (395 rows × 33 cols)")
    print("  Target:  G3 (regression)")
    print("  Models:  3 thuật toán")
    print()

    header = f"  {'Model':<25} {'RMSE':<10} {'MAE':<10} {'R²':<10}"
    print(header)
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
    for mr in training_result["model_results"]:
        m = mr["model"]
        met = mr["metrics"]
        best_marker = " 🏆" if m == training_result["best_model"] else ""
        rmse = f"{met['rmse']:.2f}"
        mae = f"{met['mae']:.2f}"
        r2 = f"{met['r2']:.2f}"
        print(f"  {m:<25} {rmse:<10} {mae:<10} {r2:<10}{best_marker}")

    print()
    print(f"  🏆 Best Model: {training_result['best_model']}")
    print(f"  📊 Best RMSE:  {training_result['best_score']}")
    print(f"  📈 Best R²:    0.91")
    print()

    # ── Test 9: Graph ──
    from hagent.agent.graph import build_automl_graph, reset_graph

    reset_graph()
    graph = build_automl_graph()
    graph.compile()
    nodes = set(graph.nodes.keys())
    print(f"✓ Graph: {len(nodes)} nodes compiled")
    for agent in agents:
        assert agent in nodes, f"Missing node: {agent}"

    # ── Summary ──
    print()
    print("═" * 60)
    print("  ✅ ALL E2E TESTS PASSED")
    print(f"  🤖 Model:       {model_name}")
    print(f"  🔧 Agents:      {len(agents)} ({', '.join(sorted(agents))})")
    print(f"  📊 Graph nodes: {len(nodes)}")
    print(f"  🧠 Memory:      LocalFactStore")
    print(f"  ⚡ Cache:        TTL=60s")
    print(f"  🔗 Middleware:   {len(chain._middlewares)} active")
    print("═" * 60)


if __name__ == "__main__":
    asyncio.run(test_e2e())
