"""Tests for multiworker.py (P0 PREP: multi-worker coordination)."""
import sys
from pathlib import Path

import pytest

MW = Path(r"D:\4\OUT\MIMO")
sys.path.insert(0, str(MW))

import multiworker as mw  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state(monkeypatch, tmp_path):
    mw._HEARTBEATS.clear()
    mw._CAPABILITIES.clear()
    mw._FENCE["value"] = 0
    monkeypatch.setattr(mw, "MW_DIR", tmp_path / "workers")
    yield


def test_worker_b_not_live_until_heartbeat():
    st = mw.worker_status("MIMO_MINIMAX")
    assert st["status"] == "PREPARED/WAITING_HEARTBEAT"
    assert st["instance_id"] is None


def test_worker_a_is_live():
    st = mw.worker_status("MIMO_DEEPSEEK")
    assert st["status"] == "LIVE"
    assert st["role"] == "WORKER_A"


def test_register_worker_b_moves_to_heartbeat_seen():
    mw.register_worker("MIMO_MINIMAX", "instance-42")
    st = mw.worker_status("MIMO_MINIMAX")
    assert st["status"] == "HEARTBEAT_SEEN_BUT_UNVERIFIED"
    assert st["instance_id"] == "instance-42"


def test_task_envelope_all_fields():
    env = mw.make_task_envelope(worker_id="MIMO_DEEPSEEK", required_capabilities=["tool_use"])
    for f in ("task_id", "parent_task_id", "worker_id", "recipient", "required_capabilities",
              "priority", "deadline", "budget", "max_attempts", "input_refs", "output_refs",
              "provenance", "status", "fencing_token"):
        assert f in env


def test_task_envelope_rejects_unknown_mode():
    with pytest.raises(ValueError):
        mw.make_task_envelope(mode="NOPE")


def test_assign_and_complete_with_fence():
    r = mw.assign_task({"task_id": "t1", "mode": "SOLO"}, "MIMO_DEEPSEEK")
    assert r["ok"] is True
    token = r["task"]["fencing_token"]
    done = mw.complete_task("MIMO_DEEPSEEK", "t1", token, {"out": "ok"})
    assert done["ok"] is True
    assert done["fenced"] is False


def test_stale_token_blocks_complete():
    mw.assign_task({"task_id": "t2", "mode": "SOLO"}, "MIMO_DEEPSEEK")
    # wrong token -> fenced
    r = mw.complete_task("MIMO_DEEPSEEK", "t2", 99999, {"out": "late"})
    assert r["ok"] is False
    assert r["fenced"] is True


def test_per_worker_dirs_isolated(tmp_path):
    a = mw.ensure_worker_dirs("MIMO_DEEPSEEK")
    b = mw.ensure_worker_dirs("MIMO_MINIMAX")
    for name in ("inbox", "outbox", "state", "work"):
        assert a[name] != b[name]
        assert a[name].exists() and b[name].exists()


def test_capability_not_assumed_from_brand():
    st = mw.capability_status("MIMO_DEEPSEEK")
    dims = st["calibrated"]
    # all dimensions start UNMEASURED (None), never brand-assumed
    assert dims["samples"] == 0
    assert dims["quality"] is None
    assert dims["tool_use"] is None


def test_observation_records_empirically():
    mw.record_observation("MIMO_DEEPSEEK", "latency_ms", 850)
    st = mw.capability_status("MIMO_DEEPSEEK")
    assert st["calibrated"]["latency_ms"] == 850
    assert st["calibrated"]["samples"] == 1
    # other dims still unmeasured
    assert st["calibrated"]["quality"] is None


def test_observation_unknown_dimension_rejected():
    r = mw.record_observation("MIMO_DEEPSEEK", "brand_strength", 1.0)
    assert r["ok"] is False


def test_merge_results_dedup_conflict():
    results = [
        {"task_id": "x", "worker_id": "A", "output_refs": ["o1"], "provenance": ["run-a"], "fencing_token": 1},
        {"task_id": "x", "worker_id": "B", "output_refs": ["o1"], "provenance": ["run-b"], "fencing_token": 2},
    ]
    m = mw.merge_results(results)
    assert m["verdict"] == "CONFLICT"
    assert len(m["accepted"]) == 1
    assert len(m["conflicts"]) == 1


def test_merge_results_clean():
    results = [
        {"task_id": "x", "worker_id": "A", "output_refs": ["o1"], "provenance": ["a"], "fencing_token": 1},
        {"task_id": "y", "worker_id": "B", "output_refs": ["o2"], "provenance": ["b"], "fencing_token": 2},
    ]
    m = mw.merge_results(results)
    assert m["verdict"] == "CLEAN"
    assert len(m["accepted"]) == 2


def test_broker_fanout_vs_solo():
    f = mw.broker_route({"mode": "FAN_OUT"}, ["A", "B"])
    assert f["route"] == "broadcast"
    assert f["workers"] == ["A", "B"]
    s = mw.broker_route({"mode": "SOLO"}, ["A", "B"])
    assert s["route"] == "exclusive"
    assert s["worker"] == "A"
