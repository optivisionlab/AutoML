"""
conftest.py — Pytest fixtures cho DeerFlow-AutoML tests.

Cung cấp:
- Mock LLM server (OpenAI-compatible) chạy background
- hagent.yaml override cho test environment
- Reusable fixtures cho agent, tools, config
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

# ── Đường dẫn ────────────────────────────────────────────

BACKEND_DIR = Path(__file__).parent.parent
HAGENT_DIR = BACKEND_DIR / "hagent"
MOCK_SERVER_SCRIPT = Path(__file__).parent / "mock_llm_server.py"

MOCK_LLM_PORT = 11435
MOCK_LLM_URL = f"http://127.0.0.1:{MOCK_LLM_PORT}/v1"


# ── Environment setup ────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """
    Cấu hình environment cho toàn bộ test session.
    Chỉ set env vars, KHÔNG hardcode trong code sản phẩm.
    """
    os.environ["HAGENT_CONFIG"] = str(HAGENT_DIR / "hagent.yaml")
    os.environ["HAUTOML_BASE_URL"] = "http://127.0.0.1:8585"

    # Override LLM config để dùng mock server
    os.environ["LLM_DEFAULT_MODEL"] = "ci-mock"
    os.environ["OPENAI_API_KEY"] = "test-key-not-real"

    # Đảm bảo module path
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    yield

    # Cleanup
    for key in ["LLM_DEFAULT_MODEL", "OPENAI_API_KEY"]:
        os.environ.pop(key, None)


# ── Mock LLM Server ──────────────────────────────────────


@pytest.fixture(scope="session")
def mock_llm_server(setup_test_env):
    """
    Chạy mock LLM server trong background process.
    Server tự tắt khi test session kết thúc.
    """
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_SERVER_SCRIPT), "--port", str(MOCK_LLM_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(BACKEND_DIR),
    )

    # Chờ server sẵn sàng
    max_wait = 15
    for i in range(max_wait * 2):
        try:
            resp = httpx.get(f"http://127.0.0.1:{MOCK_LLM_PORT}/health", timeout=2)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        stdout, stderr = proc.communicate()
        pytest.fail(
            f"Mock LLM server không khởi động được sau {max_wait}s.\n"
            f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        )

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── Config fixtures ──────────────────────────────────────


@pytest.fixture
def mock_llm_base_url():
    """URL của mock LLM server."""
    return MOCK_LLM_URL


@pytest.fixture
def agent_config():
    """Load agent config từ hagent.yaml."""
    from hagent.bridge.config import get_agent_config
    return get_agent_config()


@pytest.fixture
def llm_config():
    """Load LLM config từ hagent.yaml."""
    from hagent.bridge.config import get_llm_config
    return get_llm_config()
