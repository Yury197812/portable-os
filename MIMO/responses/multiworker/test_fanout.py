"""Tests for FAN_OUT + battlecheck + inbox/outbox protocol (3-way interaction)."""
import sys
from pathlib import Path

import pytest

MW = Path(r"D:\4\OUT\MIMO")
sys.path.insert(0, str(MW))

import multiworker as mw  # noqa: E402


@pytest.fixture(autouse=True)
def reset(monkeypatch, tmp_path):
    mw._HEARTBEATS.clear()
    mw._CAPABILITIES.clear()
    mw._FENCE["value"] = 0
    monkeypatch.setattr(mw, "MW_DIR", tmp_path / "workers")
    yield


def _executor_a(worker_id, task):
    return {"output": "hello from A", "latency_ms": 500, "failure_rate": 0.0,
            "output_refs": [f"{task.get('task_id')}-a"], "provenance": ["run-a"], "fencing_token": 1}


# --- inbox / outbox ---

def test_post_and_read_inbox():
    mw.post_task_to_inbox("MIMO_DEEPSEEK", {"task_id": "t-inbox", "mode": "SOLO"})
    inbox = mw.read_inbox("MIMO_DEEPSEEK")
    assert any(t["task_id"] == "t-inbox" for t in inbox)


def test_write_and_read_outbox():
    mw.write_result("MIMO_DEEPSEEK", "t-out", {"output": "ok"})
    rec = mw.read_outbox("MIMO_DEEPSEEK", "t-out")
    assert rec["status"] == "SUCCEEDED"
    assert rec["result"]["output"] == "ok"


# --- FAN_OUT ---

def test_fan_out_skips_unlive_worker_b():
    task = {"task_id": "t-fan", "mode": "FAN_OUT"}
    report = mw.fan_out(task, ["MIMO_DEEPSEEK", "MIMO_MINIMAX"], _executor_a)
    assert report["per_worker"]["MIMO_DEEPSEEK"]["status"] == "SUCCEEDED"
    assert report["per_worker"]["MIMO_MINIMAX"]["status"] == "SKIPPED"
    assert "waiting heartbeat" in report["per_worker"]["MIMO_MINIMAX"]["reason"]
    # only A contributed a result
    assert len(report["merged"]["accepted"]) == 1


def test_fan_out_rejects_wrong_mode():
    r = mw.fan_out({"mode": "SOLO"}, ["MIMO_DEEPSEEK"], _executor_a)
    assert r["ok"] is False


def test_fan_out_broadcast_when_b_live():
    # register WORKER_B heartbeat -> it becomes HEARTBEAT_SEEN (executor runs)
    mw.register_worker("MIMO_MINIMAX", "inst-b")
    def exec_both(wid, task):
        return {"output": f"from {wid}", "latency_ms": 100, "failure_rate": 0.0,
                "output_refs": [f"{task.get('task_id')}-{wid}"], "provenance": [wid], "fencing_token": 2}
    report = mw.fan_out({"task_id": "t2", "mode": "BATTLECHECK"}, ["MIMO_DEEPSEEK", "MIMO_MINIMAX"], exec_both)
    assert report["per_worker"]["MIMO_DEEPSEEK"]["status"] == "SUCCEEDED"
    assert report["per_worker"]["MIMO_MINIMAX"]["status"] == "SUCCEEDED"
    assert len(report["merged"]["accepted"]) == 2


# --- battlecheck ---

def test_battlecheck_incomplete_when_b_missing():
    r = mw.battlecheck({"MIMO_DEEPSEEK": {"output": "x", "latency_ms": 100}})
    assert r["verdict"] == "INCOMPLETE"
    assert "WORKER_B" in r["reason"]


def test_battlecheck_compares_latency():
    r = mw.battlecheck({
        "MIMO_DEEPSEEK": {"output": "x", "latency_ms": 100, "failure_rate": 0.0},
        "MIMO_MINIMAX": {"output": "y", "latency_ms": 300, "failure_rate": 0.0},
    })
    assert r["verdict"] == "A_WINS"
    assert r["metrics"]["latency_ms"] == {"A": 100, "B": 300}


def test_battlecheck_tie():
    r = mw.battlecheck({
        "MIMO_DEEPSEEK": {"output": "x", "latency_ms": 100, "failure_rate": 0.0},
        "MIMO_MINIMAX": {"output": "y", "latency_ms": 100, "failure_rate": 0.0},
    })
    assert r["verdict"] == "TIE"


def test_battlecheck_b_wins_on_lower_failure():
    r = mw.battlecheck({
        "MIMO_DEEPSEEK": {"output": "x", "failure_rate": 0.5},
        "MIMO_MINIMAX": {"output": "y", "failure_rate": 0.0},
    })
    assert r["verdict"] == "B_WINS"
