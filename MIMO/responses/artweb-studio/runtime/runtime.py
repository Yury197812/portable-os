#!/usr/bin/env python3
"""
runtime.py — ArtWeb Studio executable runtime.

A "run" executes a workflow graph (validate -> route -> execute -> record)
over the model catalog. Every run is a first-class entity with a run_id and
durable artifacts:

  graph.json   — the workflow DAG (read-only definition)
  state.json   — aggregate runtime state (runs_total, last_run_id, ...)
  events.jsonl — append-only event log (one JSON object per line)
  result.json  — the most recent run result

Chat inference is delegated over HTTP to the playground proxy
(http://127.0.0.1:8890/api/chat), which owns the provider keys.

Usage:
  python runtime.py run --model <id> --prompt "<text>" [--provider ollama] [--json]
  python runtime.py serve [--port 8891]      # HTTP /api/runs
  python runtime.py graph                    # print the DAG
  python runtime.py state                    # print current state

Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

RUNTIME_DIR = Path(__file__).parent
GRAPH_PATH = RUNTIME_DIR / "graph.json"
STATE_PATH = RUNTIME_DIR / "state.json"
EVENTS_PATH = RUNTIME_DIR / "events.jsonl"
RESULT_PATH = RUNTIME_DIR / "result.json"

CHAT_URL = "http://127.0.0.1:8890/api/chat"
DEFAULT_PORT = 8891


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_graph() -> dict:
    if GRAPH_PATH.exists():
        return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    return {"id": "artweb-chat-run", "nodes": ["validate", "route", "execute", "record"], "edges": []}


def log_event(run_id: str, node: str, status: str, **fields) -> dict:
    rec = {"run_id": run_id, "node": node, "status": status, "ts": now_iso(), **fields}
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"runs_total": 0}


def save_state(state: dict) -> None:
    state["updated_at"] = now_iso()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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


def run(payload: dict) -> dict:
    """Execute one run over the graph. Returns the result dict."""
    run_id = uuid.uuid4().hex[:12]
    model = payload.get("model", "qwen2.5:14b")
    messages = payload.get("messages") or [{"role": "user", "content": payload.get("prompt", "")}]
    temperature = float(payload.get("temperature", 0.7))
    t0 = time.time()

    # node: validate
    if not messages or not any((m.get("content") or "").strip() for m in messages):
        log_event(run_id, "validate", "error", error="empty prompt")
        return {"run_id": run_id, "status": "error", "error": "empty prompt"}
    log_event(run_id, "validate", "ok", model=model, message_count=len(messages))

    # node: route
    backend = route_backend(payload)
    log_event(run_id, "route", "ok", backend=backend)

    # node: execute
    try:
        resp = chat(backend, model, messages, temperature)
        content = resp.get("content", "")
        latency = resp.get("latency_ms")
        log_event(run_id, "execute", "ok", backend=backend, latency_ms=latency)
    except Exception as e:
        log_event(run_id, "execute", "error", error=str(e)[:200])
        return {"run_id": run_id, "status": "error", "error": str(e)[:200]}

    # node: record
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
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    state = load_state()
    state["runs_total"] = state.get("runs_total", 0) + 1
    state["last_run_id"] = run_id
    state["last_status"] = "ok"
    save_state(state)

    log_event(run_id, "record", "ok", total_elapsed_ms=int((time.time() - t0) * 1000))
    return result


# ---------------------------------------------------------------------------
# HTTP /api/runs
# ---------------------------------------------------------------------------

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
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
        elif self.path.startswith("/api/runs/"):
            run_id = self.path.split("/")[-1]
            if RESULT_PATH.exists():
                res = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
                if res.get("run_id") == run_id:
                    self._json(res)
                    return
            self._json({"error": "run not found"}, 404)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/runs":
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n).decode())
        except Exception:
            return self._json({"error": "bad json"}, 400)
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

    args = p.parse_args()

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
        print(f"runtime /api/runs on http://127.0.0.1:{args.port}", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()

    if args.cmd == "graph":
        print(json.dumps(load_graph(), ensure_ascii=False, indent=2))

    if args.cmd == "state":
        print(json.dumps(load_state(), ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
