"""Tests for PASS026: durable work queue + lease fencing."""
import sys
import time
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture()
def isolated_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(runtime, "QUEUE_LOCK_PATH", tmp_path / "queue" / "queue.lock")
    runtime._FENCE["value"] = 0
    return tmp_path


def test_enqueue_creates_queued_job(isolated_queue):
    job = runtime.enqueue_job({"prompt": "hi"})
    assert job["status"] == "QUEUED"
    assert job["fence"] >= 1
    assert job["job_id"]
    st = runtime.queue_status()
    assert st["jobs"].get("QUEUED", 0) == 1


def test_lease_assigns_new_fence(isolated_queue):
    job = runtime.enqueue_job({"x": 1})
    leased = runtime.lease_job("worker-1")
    assert leased["status"] == "LEASED"
    assert leased["worker"] == "worker-1"
    # lease bumps the fencing token
    assert leased["fence"] > job["fence"]


def test_complete_with_correct_fence(isolated_queue):
    runtime.enqueue_job({"x": 1})
    leased = runtime.lease_job("w")
    r = runtime.complete_job(leased["job_id"], leased["fence"], {"out": "ok"})
    assert r["ok"] is True
    assert r["status"] == "SUCCEEDED"
    assert runtime._read_job(leased["job_id"])["status"] == "SUCCEEDED"


def test_stale_fence_blocks_side_effect(isolated_queue):
    """A stale worker with an old token cannot complete a reclaimed job."""
    runtime.enqueue_job({"x": 1})
    leased = runtime.lease_job("w")
    old_fence = leased["fence"]
    # reclaim the job (e.g. worker stalled)
    runtime.reclaim_stale(max_age_seconds=0)
    # stale worker tries to complete with the OLD token -> fenced
    r = runtime.complete_job(leased["job_id"], old_fence, {"out": "late"})
    assert r["ok"] is False
    assert r["fenced"] is True
    assert "stale fence" in r["error"]
    # job was NOT marked SUCCEEDED by the stale worker
    assert runtime._read_job(leased["job_id"])["status"] != "SUCCEEDED"


def test_reclaim_bumps_fence(isolated_queue):
    runtime.enqueue_job({"x": 1})
    leased = runtime.lease_job("w")
    before = leased["fence"]
    rr = runtime.reclaim_stale(max_age_seconds=0)
    assert rr["count"] == 1
    after = runtime._read_job(leased["job_id"])["fence"]
    assert after > before


def test_fail_with_correct_fence(isolated_queue):
    runtime.enqueue_job({"x": 1})
    leased = runtime.lease_job("w")
    r = runtime.fail_job(leased["job_id"], leased["fence"], "boom")
    assert r["ok"] is True
    assert runtime._read_job(leased["job_id"])["status"] == "FAILED"


def test_fence_monotonic_across_jobs(isolated_queue):
    f1 = runtime.next_fence()
    f2 = runtime.next_fence()
    f3 = runtime.next_fence()
    assert f1 < f2 < f3
