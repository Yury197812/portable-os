"""Tests for the ArtWeb Studio runtime engine (runtime.py)."""
import sys
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """Redirect runtime artifact paths to a temp dir (no pollution)."""
    monkeypatch.setattr(runtime, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(runtime, "EVENTS_PATH", tmp_path / "events.jsonl")
    monkeypatch.setattr(runtime, "RESULT_PATH", tmp_path / "result.json")
    return tmp_path


def test_graph_is_valid_dag():
    g = runtime.load_graph()
    node_ids = {n["id"] for n in g["nodes"]}
    assert {"validate", "route", "execute", "record"} <= node_ids
    for e in g["edges"]:
        assert e["from"] in node_ids
        assert e["to"] in node_ids


def test_route_backend():
    assert runtime.route_backend({"model": "qwen2.5:14b"}) == "ollama"
    assert runtime.route_backend({"model": "openai/gpt-oss-20b:free"}) == "openrouter_free"
    assert runtime.route_backend({"provider": "groq", "model": "x"}) == "groq"


def test_run_empty_prompt_fails(isolated):
    result = runtime.run({"model": "qwen2.5:14b", "prompt": "   "})
    assert result["status"] == "error"
    assert "empty prompt" in result["error"]
    assert result["run_id"]


def test_state_roundtrip(isolated):
    runtime.save_state({"runs_total": 3, "last_run_id": "abc"})
    st = runtime.load_state()
    assert st["runs_total"] == 3
    assert st["last_run_id"] == "abc"
    assert "updated_at" in st


@pytest.mark.integration
def test_run_live():
    """Live run via the proxy + local Ollama; skipped if backend is down."""
    import urllib.request
    try:
        urllib.request.urlopen(runtime.CHAT_URL.replace("/api/chat", "/api/health"), timeout=5)
    except Exception:
        pytest.skip("backend proxy not available")
    result = runtime.run({"model": "qwen2.5:14b", "prompt": "Say OK in one word"})
    assert result["status"] == "ok"
    assert result["run_id"]
    assert result["output"]
    assert result["latency_ms"] > 0
