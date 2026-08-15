#!/usr/bin/env python3
"""
capability_measure.py — empirical capability measurement for ArtWeb workers.

Benchmarks a worker's model against the 7 capability dimensions by actually
running probes through the proxy (:8890 /api/chat). VERIFIED only when ALL
rounds verify (min 3 rounds); a single success is UNVERIFIED; zero runs =
NOT_RUN. Capabilities are measured, never assumed from brand.

Probes:
  latency_ms    — real round-trip latency (min/mean/max over rounds)
  failure_rate  — failures / total calls (0 = all succeeded)
  code          — model must emit syntactically-valid Python (py_compile)
  tool_use      — model must emit a well-formed tool_call JSON object
  long_context  — model must retrieve a fact from the tail of a long prompt

Stdlib-only.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parent))
import multiworker as mw  # noqa: E402

PROXY_CHAT = "http://127.0.0.1:8890/api/chat"


def chat_once(model: str, messages: list, temperature: float = 0.0) -> dict:
    """One chat call to the proxy. Returns {content, latency_ms} or raises."""
    body = json.dumps({"provider": "ollama", "model": model, "messages": messages, "temperature": temperature}).encode()
    req = Request(PROXY_CHAT, data=body, method="POST", headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    latency = int((time.time() - t0) * 1000)
    content = resp.get("content", "")
    return {"content": content, "latency_ms": latency}


def _probe_latency(model: str, rounds: int) -> dict:
    values = []
    for _ in range(rounds):
        r = chat_once(model, [{"role": "user", "content": "Say OK"}])
        values.append(r["latency_ms"])
    return {"ok": True, "values": values, "mean": sum(values) / len(values),
            "min": min(values), "max": max(values)}


def _probe_failure_rate(model: str, rounds: int) -> dict:
    failures = 0
    for _ in range(rounds):
        try:
            chat_once(model, [{"role": "user", "content": "ping"}])
        except Exception:
            failures += 1
    return {"ok": failures == 0, "failures": failures, "total": rounds,
            "failure_rate": failures / rounds}


def _probe_code(model: str, rounds: int) -> dict:
    """Model must emit syntactically-valid Python (py_compile) each round."""
    ok = 0
    for _ in range(rounds):
        try:
            r = chat_once(model, [{"role": "user", "content": "Output ONLY a Python function `def add(a,b): return a+b` with no explanation."}])
            code = _extract_code(r["content"])
            compile(code, "<model-output>", "exec")  # syntax check on the string
            ok += 1
        except Exception:
            continue
    return {"ok": ok == rounds, "passed": ok, "total": rounds}


def _extract_code(text: str) -> str:
    """Best-effort extract a code block from a model answer."""
    if "```" in text:
        parts = text.split("```")
        # parts[0] is prose before the first fence; subsequent chunks may carry
        # a language tag line then the code. Pick a chunk that looks like code.
        for p in parts[1:]:
            if not p.strip():
                continue
            if "def " in p or "return" in p or "import" in p:
                lines = p.splitlines()
                if lines and lines[0].strip().lower() in ("python", "py", "python3"):
                    lines = lines[1:]
                return "\n".join(lines)
    return text


def _probe_tool_use(model: str, rounds: int) -> dict:
    """Model must emit a well-formed tool_call JSON object."""
    ok = 0
    for _ in range(rounds):
        try:
            r = chat_once(model, [{"role": "user", "content": "Call the tool `read_file` with args {\"path\": \"/tmp/x\"}. Output ONLY JSON."}])
            content = r["content"].strip()
            obj = json.loads(content)
            if obj.get("tool") or obj.get("name") or obj.get("tool_call"):
                ok += 1
        except Exception:
            continue
    return {"ok": ok == rounds, "passed": ok, "total": rounds}


def _probe_long_context(model: str, rounds: int) -> dict:
    """Model must retrieve a fact buried at the tail of a long prompt."""
    ok = 0
    filler = "filler line. " * 400  # ~5K tokens of padding
    secret = "ZEBRA-4271"
    prompt = filler + f"The secret code is {secret}. Reply with only that code."
    for _ in range(rounds):
        try:
            r = chat_once(model, [{"role": "user", "content": prompt}])
            if secret in r["content"]:
                ok += 1
        except Exception:
            continue
    return {"ok": ok == rounds, "passed": ok, "total": rounds}


PROBES = {
    "latency_ms": _probe_latency,
    "failure_rate": _probe_failure_rate,
    "code": _probe_code,
    "tool_use": _probe_tool_use,
    "long_context": _probe_long_context,
}


def measure(worker_id: str, model: str, rounds: int = 3, dimensions: list[str] | None = None) -> dict:
    """Run battle probes for the requested dimensions and record observations.

    VERIFIED only when ALL rounds verify; partial = UNVERIFIED."""
    if worker_id not in mw.WORKERS:
        return {"ok": False, "error": f"unknown worker {worker_id}"}
    rounds = max(1, rounds)
    dims = dimensions or list(PROBES.keys())
    report = {"worker_id": worker_id, "model": model, "rounds": rounds, "results": {}}

    for dim in dims:
        if dim not in PROBES:
            report["results"][dim] = {"ok": False, "error": f"unknown dimension {dim}"}
            continue
        try:
            probe = PROBES[dim](model, rounds)
            report["results"][dim] = probe
            if probe.get("ok"):
                if dim == "latency_ms":
                    # each round is its own observation -> running stats
                    for v in probe.get("values", []):
                        mw.record_observation(worker_id, dim, v)
                elif dim == "failure_rate":
                    # record a 0.0 (no failures) per round that passed
                    for _ in range(rounds):
                        mw.record_observation(worker_id, dim, probe["failure_rate"])
                else:
                    # pass/fail probes: one observation per verified round
                    for _ in range(rounds):
                        mw.record_observation(worker_id, dim, 1.0)
        except Exception as e:
            report["results"][dim] = {"ok": False, "error": str(e)[:200]}

    report["capability_status"] = mw.capability_status(worker_id)
    return report


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Measure worker capabilities empirically")
    p.add_argument("worker_id")
    p.add_argument("--model", default="qwen2.5:14b")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--dims", default=None, help="comma-separated dimensions")
    args = p.parse_args()
    dims = args.dims.split(",") if args.dims else None
    report = measure(args.worker_id, args.model, args.rounds, dims)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
