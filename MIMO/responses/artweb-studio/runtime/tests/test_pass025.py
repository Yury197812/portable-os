"""Tests for PASS025: capability quarantine with dependency-graph propagation."""
import sys
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture(autouse=True)
def reset_quarantine():
    runtime._QUARANTINE.clear()
    yield
    runtime._QUARANTINE.clear()


def test_quarantine_propagates_to_agents_and_workflows():
    r = runtime.quarantine("tool_use", "capability probe failed")
    assert r["ok"] is True
    # tool_use -> agents + workflows from dependency graph
    assert "web-designer" in r["quarantined_agents"]
    assert "chat-run" in r["quarantined_workflows"]


def test_quarantine_unknown_capability_rejected():
    r = runtime.quarantine("nonexistent", "x")
    assert r["ok"] is False
    assert "known" in r


def test_quarantine_status_blocks_transitively():
    runtime.quarantine("tool_use", "probe failed")
    st = runtime.quarantine_status()
    assert "tool_use" in st["quarantined_capabilities"]
    assert "web-designer" in st["blocked_agents"]
    assert "chat-run" in st["blocked_workflows"]


def test_is_quarantined_routing_gate():
    runtime.quarantine("vision", "down")
    assert runtime.is_quarantined("capability", "vision") is True
    assert runtime.is_quarantined("agent", "ui-tester") is True
    assert runtime.is_quarantined("workflow", "ui-e2e") is True
    # unrelated nodes stay routable
    assert runtime.is_quarantined("agent", "code-reviewer") is False


def test_unquarantine_clears_only_capability():
    runtime.quarantine("tool_use", "x")
    runtime.quarantine("code", "y")
    runtime.unquarantine("tool_use")
    assert runtime.is_quarantined("capability", "tool_use") is False
    # code quarantine remains independent
    assert runtime.is_quarantined("capability", "code") is True
    assert runtime.is_quarantined("agent", "code-reviewer") is True


def test_unquarantine_unknown_rejected():
    r = runtime.unquarantine("not-there")
    assert r["ok"] is False


def test_independent_quarantine_not_cleared_by_other():
    # code depends on code-reviewer; tool_use depends on web-designer etc.
    runtime.quarantine("code", "c")
    runtime.quarantine("tool_use", "t")
    runtime.unquarantine("tool_use")
    # code-reviewer still blocked via code
    assert runtime.is_quarantined("agent", "code-reviewer") is True
    # web-designer no longer blocked (tool_use cleared)
    assert runtime.is_quarantined("agent", "web-designer") is False
