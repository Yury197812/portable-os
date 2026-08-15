"""Tests for capability_measure.py + running stats + verdict (PASS010 §5)."""
import sys
from pathlib import Path

import pytest

MW = Path(r"D:\4\OUT\MIMO")
sys.path.insert(0, str(MW))

import multiworker as mw  # noqa: E402
import capability_measure as cm  # noqa: E402


@pytest.fixture(autouse=True)
def reset(monkeypatch, tmp_path):
    mw._CAPABILITIES.clear()
    mw._FENCE["value"] = 0
    mw._HEARTBEATS.clear()
    monkeypatch.setattr(mw, "MW_DIR", tmp_path / "workers")
    yield


# --- running stats in multiworker ---

def test_running_stats_mean_min_max():
    for v in (10.0, 20.0, 30.0):
        mw.record_observation("MIMO_DEEPSEEK", "latency_ms", v)
    stats = mw._dim_stats("MIMO_DEEPSEEK", "latency_ms")
    assert stats["count"] == 3
    assert stats["mean"] == 20.0
    assert stats["min"] == 10.0
    assert stats["max"] == 30.0


def test_verdict_requires_min_rounds():
    # 0 observations -> NOT_RUN
    assert mw.dimension_verdict("MIMO_DEEPSEEK", "code") == "NOT_RUN"
    # 1 -> UNVERIFIED
    mw.record_observation("MIMO_DEEPSEEK", "code", 1.0)
    assert mw.dimension_verdict("MIMO_DEEPSEEK", "code") == "UNVERIFIED"
    # 3 -> VERIFIED
    mw.record_observation("MIMO_DEEPSEEK", "code", 1.0)
    mw.record_observation("MIMO_DEEPSEEK", "code", 1.0)
    assert mw.dimension_verdict("MIMO_DEEPSEEK", "code") == "VERIFIED"


# --- battle probes (with chat mocked) ---

def test_probe_code_valid(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": "```python\ndef add(a,b):\n    return a+b\n```", "latency_ms": 50}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_code("m", 3)
    assert r["ok"] is True
    assert r["passed"] == 3


def test_probe_code_invalid(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": "def add(a,b) return a+b  # syntax error", "latency_ms": 50}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_code("m", 3)
    assert r["ok"] is False
    assert r["passed"] == 0


def test_probe_tool_use_valid(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": '{"tool": "read_file", "args": {"path": "/tmp/x"}}', "latency_ms": 40}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_tool_use("m", 3)
    assert r["ok"] is True


def test_probe_failure_rate_all_ok(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": "OK", "latency_ms": 10}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_failure_rate("m", 3)
    assert r["ok"] is True
    assert r["failure_rate"] == 0.0


def test_probe_failure_rate_counts_failures(monkeypatch):
    calls = {"n": 0}
    def fake_chat(model, messages, temperature=0.0):
        calls["n"] += 1
        if calls["n"] % 2 == 1:
            raise RuntimeError("down")
        return {"content": "OK", "latency_ms": 10}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_failure_rate("m", 4)
    assert r["ok"] is False
    assert r["failures"] == 2
    assert r["failure_rate"] == 0.5


def test_measure_records_observations(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": '{"tool": "read_file", "args": {}}', "latency_ms": 55}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    # measure only latency (deterministic value)
    report = cm.measure("MIMO_DEEPSEEK", "m", rounds=3, dimensions=["latency_ms"])
    assert report["results"]["latency_ms"]["ok"] is True
    st = mw.capability_status("MIMO_DEEPSEEK")
    assert st["calibrated"]["latency_ms"]["verdict"] == "VERIFIED"
    assert st["calibrated"]["latency_ms"]["mean"] == 55.0


def test_measure_unknown_worker():
    r = cm.measure("NOPE", "m")
    assert r["ok"] is False


def test_probe_quality_correct(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": "156", "latency_ms": 30}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_quality("m", 3)
    assert r["ok"] is True
    assert r["passed"] == 3


def test_probe_quality_wrong(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": "155", "latency_ms": 30}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    r = cm._probe_quality("m", 3)
    assert r["ok"] is False


def test_capability_persistence_roundtrip(monkeypatch):
    def fake_chat(model, messages, temperature=0.0):
        return {"content": "156", "latency_ms": 30}
    monkeypatch.setattr(cm, "chat_once", fake_chat)
    cm.measure("MIMO_DEEPSEEK", "m", rounds=3, dimensions=["quality"], persist=True)
    # simulate process restart: clear in-memory, then reload from disk
    mw._CAPABILITIES.clear()
    r = mw.load_capabilities("MIMO_DEEPSEEK")
    assert r["ok"] is True
    st = mw.capability_status("MIMO_DEEPSEEK")
    assert st["calibrated"]["quality"]["verdict"] == "VERIFIED"
    assert st["calibrated"]["quality"]["count"] == 3


def test_load_capabilities_missing():
    r = mw.load_capabilities("MIMO_MINIMAX")
    assert r["ok"] is False
    assert "no persisted" in r["reason"]
