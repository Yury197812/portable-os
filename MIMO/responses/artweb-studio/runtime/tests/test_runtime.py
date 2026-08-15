"""Tests for the ArtWeb Studio runtime engine (runtime.py)."""
import json
import sys
import threading
from pathlib import Path

import pytest

RUNTIME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME_DIR))

import runtime  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """Redirect runtime artifact paths to a temp dir (no pollution)."""
    monkeypatch.setattr(runtime, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runtime, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(runtime, "GRAPH_PATH", tmp_path / "graph.json")
    monkeypatch.setattr(runtime, "SNAPSHOT_DIR", tmp_path / "snapshots")
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
    runtime._SEQ["value"] = 0
    return tmp_path


def _fake_chat(monkeypatch, content="OK", latency_ms=5):
    def fake(provider, model, messages, temperature=0.7):
        return {"content": content, "latency_ms": latency_ms}

    monkeypatch.setattr(runtime, "chat", fake)


# --- graph / routing ---

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


# --- FIX2: durable per-run store ---

def test_run_empty_prompt_fails_durable(isolated):
    result = runtime.run({"model": "qwen2.5:14b", "prompt": "   "})
    assert result["status"] == "error"
    assert "empty prompt" in result["error"]
    assert result["run_id"]
    assert runtime.read_run_result(result["run_id"])["status"] == "error"
    st = runtime.read_run_state(result["run_id"])
    assert st["status"] == "FAILED"
    assert st["nodes"]["validate"] == "FAILED"


def test_run_success_writes_per_run_artifacts(isolated, monkeypatch):
    _fake_chat(monkeypatch)
    result = runtime.run({"model": "qwen2.5:14b", "prompt": "hello"})
    rid = result["run_id"]
    assert result["status"] == "ok"
    d = runtime.run_dir(rid)
    assert (d / "state.json").exists()
    assert (d / "events.jsonl").exists()
    assert (d / "result.json").exists()
    assert (d / "graph.json").exists()
    assert runtime.read_run_state(rid)["status"] == "SUCCEEDED"
    events = runtime.read_run_events(rid)
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert len(seqs) >= 6


def test_two_runs_both_retrievable(isolated, monkeypatch):
    """GET of an old run_id must still work after a later run completes."""
    _fake_chat(monkeypatch)
    r1 = runtime.run({"model": "qwen2.5:14b", "prompt": "first"})
    r2 = runtime.run({"model": "qwen2.5:14b", "prompt": "second"})
    assert r1["run_id"] != r2["run_id"]
    assert runtime.read_run_result(r1["run_id"])["output"] == "OK"
    assert runtime.read_run_result(r2["run_id"])["output"] == "OK"
    assert runtime.read_run_result(r1["run_id"])["run_id"] == r1["run_id"]


def test_fifty_concurrent_runs_no_loss(isolated, monkeypatch):
    """50 concurrent runs -> 50 terminal results, no lost state/events."""
    _fake_chat(monkeypatch)
    results = []
    errors = []
    lock = threading.Lock()

    def worker(i):
        try:
            r = runtime.run({"model": "qwen2.5:14b", "prompt": f"p{i}"})
            with lock:
                results.append(r)
        except Exception as e:  # pragma: no cover - failure means the test fails
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert len(results) == 50
    assert all(r["status"] == "ok" for r in results)
    for r in results:
        assert runtime.read_run_result(r["run_id"]) is not None
        assert runtime.read_run_state(r["run_id"])["status"] == "SUCCEEDED"
    assert runtime.load_state()["runs_total"] == 50
    all_seqs = []
    for r in results:
        seqs = [e["seq"] for e in runtime.read_run_events(r["run_id"])]
        assert seqs == sorted(seqs), "seq must be monotonic within a run"
        all_seqs.extend(seqs)
    assert len(all_seqs) == len(set(all_seqs)), "event seqs must be globally unique"


def test_failed_execute_is_durable(isolated, monkeypatch):
    """A backend error must persist FAILED run/node state and result."""
    def boom(provider, model, messages, temperature=0.7):
        raise RuntimeError("backend down")

    monkeypatch.setattr(runtime, "chat", boom)
    result = runtime.run({"model": "qwen2.5:14b", "prompt": "x"})
    assert result["status"] == "error"
    assert "backend down" in result["error"]
    rid = result["run_id"]
    assert runtime.read_run_state(rid)["status"] == "FAILED"
    assert runtime.read_run_state(rid)["nodes"]["execute"] == "FAILED"
    assert runtime.read_run_result(rid)["status"] == "error"
    assert runtime.load_state()["last_status"] == "FAILED"


def test_cors_localhost_allowlist(isolated):
    """CORS must never send wildcard; only localhost origins are allowed."""

    class Probe(runtime.H):
        def __init__(self, origin):
            self._sent = []
            self.headers = {"Origin": origin} if origin else {}

        def send_header(self, k, v):
            self._sent.append((k, v))

    assert "http://localhost:3000" in runtime.ALLOWED_ORIGINS
    assert "https://evil.example.com" not in runtime.ALLOWED_ORIGINS
    assert "*" not in runtime.ALLOWED_ORIGINS

    h = Probe("https://evil.example.com")
    h._cors()
    assert all(k != "Access-Control-Allow-Origin" for k, _ in h._sent)

    h = Probe("http://localhost:3000")
    h._cors()
    assert ("Access-Control-Allow-Origin", "http://localhost:3000") in h._sent
    assert ("Vary", "Origin") in h._sent


# --- security layer: state schema / snapshot / rollback ---

def test_state_roundtrip(isolated):
    runtime.save_state({"runs_total": 3, "last_run_id": "abc"})
    st = runtime.load_state()
    assert st["runs_total"] == 3
    assert st["last_run_id"] == "abc"
    assert "updated_at" in st


def test_migration_adds_schema_version(isolated):
    state_path = Path(str(runtime.STATE_PATH))
    state_path.write_text(json.dumps({"runs_total": 3}))
    state = runtime.migrate_state()
    assert state["schema_version"] == 1
    assert state["runs_total"] == 3
    assert runtime.latest_snapshot() is not None


def test_rollback_restores_snapshot(isolated):
    state_path = Path(str(runtime.STATE_PATH))
    state_path.write_text(json.dumps({"runs_total": 3, "schema_version": 1}))
    runtime.snapshot_state()
    state_path.write_text(json.dumps({"runs_total": 99, "schema_version": 1}))
    assert runtime.rollback_state()["runs_total"] == 3


def test_rollback_refused_while_serving(isolated):
    runtime._serving = True
    try:
        with pytest.raises(RuntimeError):
            runtime.rollback_state()
    finally:
        runtime._serving = False


def test_migration_auto_restore_on_failure(isolated, monkeypatch):
    state_path = Path(str(runtime.STATE_PATH))
    state_path.write_text(json.dumps({"runs_total": 3}))
    runtime.snapshot_state()

    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(OSError):
        runtime.migrate_state()
    monkeypatch.undo()
    assert json.loads(state_path.read_text())["runs_total"] == 3


def test_integrity_ok():
    ok, err = runtime.verify_integrity()
    assert ok, err


def test_diagnose_returns_expected_checks():
    checks = {d["check"] for d in runtime.diagnose()}
    assert {"integrity", "graph", "backend", "local_model"} <= checks


# --- live integration (backend-dependent) ---

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


@pytest.mark.integration
def test_onboard_live():
    """Onboarding with LIVE chat probe; skipped if backend is down."""
    import urllib.request
    try:
        urllib.request.urlopen(runtime.CHAT_URL.replace("/api/chat", "/api/health"), timeout=5)
    except Exception:
        pytest.skip("backend proxy not available")
    result = runtime.onboard()
    assert result["ready"] is True
    assert result["live_probe"]["ok"] is True
    assert result["live_probe"]["content"]
