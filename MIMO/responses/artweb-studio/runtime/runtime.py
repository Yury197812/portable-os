#!/usr/bin/env python3
"""
runtime.py — ArtWeb Studio executable runtime (durable core + security layer).

A "run" executes a workflow graph (validate -> route -> execute -> record)
over the model catalog. Every run is a first-class entity with a run_id and
durable per-run artifacts stored under runs/<run_id>/:

  runs/<run_id>/graph.json   — workflow DAG snapshot (read-only definition)
  runs/<run_id>/state.json   — run + node FSM state (CREATED/RUNNING/SUCCEEDED/FAILED)
  runs/<run_id>/events.jsonl — append-only event log, globally monotonic `seq`
  runs/<run_id>/result.json  — terminal result (ok OR error), durable

A global aggregate state.json (schema_version, runs_total, last_run_id,
last_status) is kept for convenience; it is NOT the source of truth —
per-run artifacts are. Signed-update verification (Ed25519 over MANIFEST)
and state migration/snapshot/rollback are fail-closed.

Chat inference is delegated over HTTP to the playground proxy
(http://127.0.0.1:8890/api/chat), which owns the provider keys. This is an
adapter boundary: the production UI must route through /api/runs, never
directly to /api/chat.

Usage:
  python runtime.py run --model <id> --prompt "<text>" [--provider ollama] [--json]
  python runtime.py serve [--port 8891]      # HTTP /api/runs
  python runtime.py graph                    # print the DAG
  python runtime.py state                    # print current state
  python runtime.py verify                   # verify MANIFEST signature + hashes
  python runtime.py snapshot / migrate / rollback
  python runtime.py diagnose / onboard

Depends on `cryptography` for Ed25519 signature verification (fail-closed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

RUNTIME_DIR = Path(__file__).parent
RUNS_DIR = RUNTIME_DIR / "runs"
GRAPH_PATH = RUNTIME_DIR / "graph.json"
STATE_PATH = RUNTIME_DIR / "state.json"

CHAT_URL = "http://127.0.0.1:8890/api/chat"
DEFAULT_PORT = 8891

# Signed-update verification (fail-closed)
PUBLIC_KEY_HEX = "6c63fc13105cef70020e44bb05657aef4a28d12687fa1300502b1246b8448077"
MANIFEST_PATH = RUNTIME_DIR / "MANIFEST.json"
MANIFEST_SIG_PATH = RUNTIME_DIR / "MANIFEST.sig"

# State schema + snapshots (migration with auto-restore + offline-gated rollback)
STATE_SCHEMA_VERSION = 1
SNAPSHOT_DIR = RUNTIME_DIR / "snapshots"
_serving = False  # True while the HTTP server is running

# CORS: localhost-only allowlist. Never wildcard — a hostile origin must be
# rejected by the browser, not granted.
ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8890",
    "http://127.0.0.1:8890",
    "http://localhost:8891",
    "http://127.0.0.1:8891",
}

# Terminal FSM states.
RUN_CREATED = "CREATED"
RUN_RUNNING = "RUNNING"
RUN_SUCCEEDED = "SUCCEEDED"
RUN_FAILED = "FAILED"

# Single writer lock: protects the monotonic event-seq counter and the
# aggregate state.json. Per-run files are written by their own run only, but
# the global seq must stay monotonic under concurrency.
_LOCK = threading.Lock()
_SEQ = {"value": 0}  # process-local monotonic counter (seeded from state on load)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def verify_integrity() -> tuple[bool, str]:
    """Fail-closed: verify MANIFEST Ed25519 signature + file hashes."""
    try:
        if not MANIFEST_PATH.exists() or not MANIFEST_SIG_PATH.exists():
            return False, "MANIFEST or signature missing"
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
        pub.verify(MANIFEST_SIG_PATH.read_bytes(), canonical)
        for f in manifest.get("files", []):
            actual = hashlib.sha256((RUNTIME_DIR / f["path"]).read_bytes()).hexdigest()
            if actual != f["sha256"]:
                return False, f"hash mismatch: {f['path']}"
        return True, "ok"
    except Exception as e:
        return False, str(e)[:120]


def load_graph() -> dict:
    return _read_json(GRAPH_PATH) or {
        "id": "artweb-chat-run",
        "nodes": ["validate", "route", "execute", "record"],
        "edges": [],
    }


def next_seq() -> int:
    with _LOCK:
        _SEQ["value"] += 1
        return _SEQ["value"]


def _seed_seq() -> None:
    """Restore the monotonic counter past any already-persisted events."""
    with _LOCK:
        hi = 0
        if RUNS_DIR.exists():
            for ev_path in RUNS_DIR.glob("*/events.jsonl"):
                for line in ev_path.read_text(encoding="utf-8").splitlines():
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    hi = max(hi, int(rec.get("seq", 0)))
        _SEQ["value"] = max(_SEQ["value"], hi)


def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_run_state(run_id: str, state: dict) -> None:
    state["updated_at"] = now_iso()
    _atomic_write(run_dir(run_id) / "state.json", json.dumps(state, ensure_ascii=False, indent=2))


def read_run_state(run_id: str) -> dict:
    return _read_json(run_dir(run_id) / "state.json") or {"run_id": run_id, "status": RUN_CREATED}


def write_run_result(run_id: str, result: dict) -> None:
    _atomic_write(run_dir(run_id) / "result.json", json.dumps(result, ensure_ascii=False, indent=2))


def read_run_result(run_id: str) -> dict:
    return _read_json(run_dir(run_id) / "result.json")


def write_graph_snapshot(run_id: str) -> None:
    _atomic_write(run_dir(run_id) / "graph.json", json.dumps(load_graph(), ensure_ascii=False, indent=2))


def log_event(run_id: str, node: str, status: str, **fields) -> dict:
    rec = {"seq": next_seq(), "run_id": run_id, "node": node, "status": status, "ts": now_iso(), **fields}
    with _LOCK:
        with (run_dir(run_id) / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_run_events(run_id: str) -> list[dict]:
    path = run_dir(run_id) / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_state() -> dict:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if state.get("schema_version", 0) < STATE_SCHEMA_VERSION:
            return migrate_state()
        return state
    return {"schema_version": STATE_SCHEMA_VERSION, "runs_total": 0}


def save_state(state: dict) -> None:
    state["updated_at"] = now_iso()
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    _atomic_write(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))


def snapshot_state() -> Path | None:
    """Copy current state.json into snapshots/ (pre-migration snapshot)."""
    if not STATE_PATH.exists():
        return None
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    snap = SNAPSHOT_DIR / f"state.{ts}.json"
    snap.write_bytes(STATE_PATH.read_bytes())
    return snap


def latest_snapshot() -> Path | None:
    if not SNAPSHOT_DIR.exists():
        return None
    snaps = sorted(SNAPSHOT_DIR.glob("state.*.json"))
    return snaps[-1] if snaps else None


def migrate_state() -> dict:
    """Migrate state.json to the latest schema. Pre-migration snapshot + auto-restore."""
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {"runs_total": 0}
    version = state.get("schema_version", 0)
    if version >= STATE_SCHEMA_VERSION:
        return state
    snap = snapshot_state()
    try:
        # v0 -> v1: tag schema_version, keep existing fields (no transform needed)
        state["schema_version"] = STATE_SCHEMA_VERSION
        state["updated_at"] = now_iso()
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state
    except Exception:
        # auto-restore from the pre-migration snapshot
        if snap and snap.exists():
            STATE_PATH.write_bytes(snap.read_bytes())
        raise


def rollback_state() -> dict:
    """Restore the latest snapshot. Offline-gated: refuse while serving."""
    if _serving:
        raise RuntimeError("rollback refused: runtime is serving (offline-gated)")
    snap = latest_snapshot()
    if not snap:
        raise FileNotFoundError("no snapshot to roll back to")
    STATE_PATH.write_bytes(snap.read_bytes())
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def route_backend(payload: dict) -> str:
    """Route a run to a backend provider."""
    if payload.get("provider"):
        return payload["provider"]
    model = payload.get("model", "")
    if "/" in model:
        return "openrouter_free"
    return "ollama"


def chat(provider: str, model: str, messages: list, temperature: float = 0.7) -> dict:
    body = json.dumps({"provider": provider, "model": model, "messages": messages, "temperature": temperature}).encode()
    req = Request(CHAT_URL, data=body, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def diagnose() -> list[dict]:
    """First-run diagnostics, classified BLOCKER vs WARN."""
    results = []

    ok, err = verify_integrity()
    results.append({"check": "integrity", "severity": "ok" if ok else "BLOCKER", "detail": err if not ok else "ok"})

    g = load_graph()
    if not g.get("nodes") or not g.get("edges"):
        results.append({"check": "graph", "severity": "BLOCKER", "detail": "empty graph"})
    else:
        results.append({"check": "graph", "severity": "ok", "detail": f"{len(g['nodes'])} nodes"})

    try:
        with urlopen(CHAT_URL.replace("/api/chat", "/api/health"), timeout=5) as r:
            r.read()
        results.append({"check": "backend", "severity": "ok", "detail": "proxy reachable"})
    except Exception as e:
        results.append({"check": "backend", "severity": "BLOCKER", "detail": str(e)[:120]})

    try:
        with urlopen("http://127.0.0.1:11434/v1/models", timeout=4) as r:
            data = json.loads(r.read().decode())
        ids = [m.get("id", "") for m in data.get("data", [])]
        if any("qwen2.5" in i for i in ids):
            results.append({"check": "local_model", "severity": "ok", "detail": "qwen2.5 present"})
        else:
            results.append({"check": "local_model", "severity": "WARN", "detail": "qwen2.5:14b not in Ollama"})
    except Exception as e:
        results.append({"check": "local_model", "severity": "WARN", "detail": f"ollama unreachable: {str(e)[:80]}"})

    return results


def chat_probe() -> dict:
    """LIVE chat probe: a real completion over the backend (not just a health ping)."""
    t0 = time.time()
    try:
        resp = chat("ollama", "qwen2.5:14b", [{"role": "user", "content": "Reply with the single word OK"}], 0.0)
        content = (resp.get("content") or "").strip()
        return {"ok": bool(content), "content": content[:80],
                "latency_ms": resp.get("latency_ms") or int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "latency_ms": int((time.time() - t0) * 1000)}


def onboard() -> dict:
    """Onboarding: diagnostics (BLOCKER/WARN) + LIVE chat probe."""
    diags = diagnose()
    blockers = [d for d in diags if d["severity"] == "BLOCKER"]
    return {
        "diagnostics": diags,
        "blockers": len(blockers),
        "live_probe": chat_probe(),
        "ready": not blockers,
    }


def _bump_aggregate(run_id: str, status: str) -> None:
    with _LOCK:
        state = load_state()
        state["runs_total"] = state.get("runs_total", 0) + 1
        state["last_run_id"] = run_id
        state["last_status"] = status
        save_state(state)


def _set_run_status(run_id: str, status: str, **extra) -> None:
    state = read_run_state(run_id)
    state["status"] = status
    state.update(extra)
    write_run_state(run_id, state)


def _set_node_status(run_id: str, node: str, status: str) -> None:
    state = read_run_state(run_id)
    nodes = state.setdefault("nodes", {})
    nodes[node] = status
    write_run_state(run_id, state)


def _fail(run_id: str, node: str, error: str, node_status: str = "FAILED") -> dict:
    """Persist a terminal FAILED result and return it. Durable for both run and node."""
    _set_node_status(run_id, node, node_status)
    log_event(run_id, node, "error", error=error[:200])
    _set_run_status(run_id, RUN_FAILED, error=error[:200])
    log_event(run_id, "run", RUN_FAILED, error=error[:200])
    result = {"run_id": run_id, "status": "error", "error": error[:200], "ts": now_iso()}
    write_run_result(run_id, result)
    _bump_aggregate(run_id, RUN_FAILED)
    return result


def run(payload: dict) -> dict:
    """Execute one run over the graph. Returns the result dict."""
    run_id = uuid.uuid4().hex[:12]
    model = payload.get("model", "qwen2.5:14b")
    messages = payload.get("messages") or [{"role": "user", "content": payload.get("prompt", "")}]
    temperature = float(payload.get("temperature", 0.7))
    t0 = time.time()

    # FSM: CREATED -> RUNNING
    run_dir(run_id)
    write_graph_snapshot(run_id)
    _set_run_status(run_id, RUN_CREATED, model=model)
    log_event(run_id, "run", RUN_CREATED, model=model)
    _set_run_status(run_id, RUN_RUNNING)
    log_event(run_id, "run", RUN_RUNNING)

    # node: validate
    _set_node_status(run_id, "validate", "RUNNING")
    if not messages or not any((m.get("content") or "").strip() for m in messages):
        return _fail(run_id, "validate", "empty prompt")
    _set_node_status(run_id, "validate", "SUCCEEDED")
    log_event(run_id, "validate", "ok", model=model, message_count=len(messages))

    # node: route
    _set_node_status(run_id, "route", "RUNNING")
    backend = route_backend(payload)
    _set_node_status(run_id, "route", "SUCCEEDED")
    log_event(run_id, "route", "ok", backend=backend)

    # node: execute
    _set_node_status(run_id, "execute", "RUNNING")
    try:
        resp = chat(backend, model, messages, temperature)
        content = resp.get("content", "")
        latency = resp.get("latency_ms")
        _set_node_status(run_id, "execute", "SUCCEEDED")
        log_event(run_id, "execute", "ok", backend=backend, latency_ms=latency)
    except Exception as e:
        return _fail(run_id, "execute", str(e)[:200])

    # node: record
    _set_node_status(run_id, "record", "RUNNING")
    result = {
        "run_id": run_id,
        "model": model,
        "backend": backend,
        "prompt": messages[-1].get("content", ""),
        "output": content,
        "latency_ms": latency,
        "status": "ok",
        "ts": now_iso(),
    }
    write_run_result(run_id, result)
    _set_node_status(run_id, "record", "SUCCEEDED")
    log_event(run_id, "record", "ok", total_elapsed_ms=int((time.time() - t0) * 1000))

    _set_run_status(run_id, RUN_SUCCEEDED)
    log_event(run_id, "run", RUN_SUCCEEDED)
    _bump_aggregate(run_id, RUN_SUCCEEDED)
    return result


# ---------------------------------------------------------------------------
# HTTP /api/runs
# ---------------------------------------------------------------------------

class H(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self._json({"ok": True, "service": "artweb-runtime"})
        elif self.path == "/api/state":
            self._json(load_state())
        elif self.path == "/api/runs":
            ids = sorted(d.name for d in RUNS_DIR.iterdir() if d.is_dir()) if RUNS_DIR.exists() else []
            self._json({"runs": ids})
        elif self.path.startswith("/api/runs/"):
            run_id = self.path.split("/")[-1]
            res = read_run_result(run_id)
            if res is not None:
                self._json(res)
            else:
                self._json({"error": "run not found"}, 404)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/runs":
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length", 0))
        if n > 1_000_000:
            return self._json({"error": "payload too large"}, 413)
        try:
            payload = json.loads(self.rfile.read(n).decode())
        except Exception:
            return self._json({"error": "bad json"}, 400)
        if not isinstance(payload, dict):
            return self._json({"error": "payload must be an object"}, 400)
        result = run(payload)
        self._json(result, 201 if result.get("status") == "ok" else 500)

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="ArtWeb Studio runtime")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="execute one run")
    pr.add_argument("--model", default="qwen2.5:14b")
    pr.add_argument("--prompt", required=True)
    pr.add_argument("--provider", default=None)
    pr.add_argument("--json", action="store_true")

    ps = sub.add_parser("serve", help="start HTTP /api/runs")
    ps.add_argument("--port", type=int, default=DEFAULT_PORT)

    sub.add_parser("graph", help="print the DAG")
    sub.add_parser("state", help="print current state")
    sub.add_parser("verify", help="verify MANIFEST signature + hashes")
    sub.add_parser("snapshot", help="snapshot current state.json")
    sub.add_parser("migrate", help="migrate state to latest schema")
    sub.add_parser("rollback", help="restore latest snapshot (offline-gated)")
    sub.add_parser("diagnose", help="first-run diagnostics (BLOCKER/WARN)")
    sub.add_parser("onboard", help="onboarding: diagnostics + LIVE chat probe")

    args = p.parse_args()

    if args.cmd == "verify":
        ok, err = verify_integrity()
        print(f"integrity: {'OK' if ok else 'FAIL'} ({err})")
        return 0 if ok else 2

    if args.cmd == "diagnose":
        for d in diagnose():
            print(f"{d['severity']:>7}  {d['check']}: {d['detail']}")
        return 0

    if args.cmd == "onboard":
        result = onboard()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ready"] else 1

    # startup: fail-closed on BLOCKER diagnostics
    for d in diagnose():
        if d["severity"] == "BLOCKER":
            print(f"BLOCKER: {d['check']}: {d['detail']} (refusing to run)", file=sys.stderr)
            return 2
        if d["severity"] == "WARN":
            print(f"WARN: {d['check']}: {d['detail']}", file=sys.stderr)

    if args.cmd == "run":
        result = run({"model": args.model, "prompt": args.prompt, "provider": args.provider})
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"run_id={result['run_id']} status={result['status']}")
            if result.get("output"):
                print(result["output"])
        return 0 if result.get("status") == "ok" else 1

    if args.cmd == "serve":
        global _serving
        _serving = True
        _seed_seq()
        print(f"runtime /api/runs on http://127.0.0.1:{args.port}", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()

    if args.cmd == "graph":
        print(json.dumps(load_graph(), ensure_ascii=False, indent=2))

    if args.cmd == "state":
        print(json.dumps(load_state(), ensure_ascii=False, indent=2))

    if args.cmd == "snapshot":
        snap = snapshot_state()
        print(f"snapshot: {snap if snap else 'no state.json to snapshot'}")

    if args.cmd == "migrate":
        try:
            state = migrate_state()
            print("migrated to schema", state.get("schema_version"))
        except Exception as e:
            print(f"migrate failed (auto-restored): {e}", file=sys.stderr)
            return 1

    if args.cmd == "rollback":
        try:
            state = rollback_state()
            print("rolled back:", json.dumps(state, ensure_ascii=False))
        except (RuntimeError, FileNotFoundError) as e:
            print(f"rollback failed: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    _seed_seq()
    raise SystemExit(main())
