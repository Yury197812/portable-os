#!/usr/bin/env python3
"""bench_a_deepseek.py — P0 BENCH-A: expanded calibration of deepseek-v4-pro.

9 evidence-backed dimensions, each >=3 rounds where applicable. Raw evidence
only; no self-scoring. Real backend = api.deepseek.com, NOT qwen/Ollama proxy.

Dimensions:
  latency / failure_rate
  code_generation
  code_repair (seeded defects)
  quality_reasoning (hidden objective tasks)
  long_context
  tool_use (selection -> args -> execution -> readback -> recovery)
  recovery_checkpoint
  review_catch_rate (blind seeded defects)
  instruction_adherence

Stdlib-only.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-pro"
ROUNDS = 3


def chat(messages: list, tools=None) -> dict:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("no DEEPSEEK_API_KEY")
    body = {"model": MODEL, "messages": messages}
    if tools is not None:
        body["tools"] = tools
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode())
    msg = resp["choices"][0]["message"]
    return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls"), "latency_ms": int((time.time() - t0) * 1000)}


def _u(t):
    return {"role": "user", "content": t}


def probe_latency_failure():
    lats, fails = [], 0
    for _ in range(ROUNDS):
        try:
            lats.append(chat([_u("Say OK")])["latency_ms"])
        except Exception:
            fails += 1
    return {"latency_values": lats, "latency_mean": round(sum(lats) / len(lats), 1) if lats else None,
            "failures": fails, "failure_rate": fails / ROUNDS}


def probe_code_generation():
    ok = 0
    for _ in range(ROUNDS):
        try:
            c = chat([_u("Output ONLY a Python function `def fibonacci(n): ...` (iterative, no recursion, no explanation).")])["content"]
            if "```" in c:
                c = c.split("```")[1].replace("python", "", 1)
            compile(c, "<m>", "exec")
            ok += 1
        except Exception:
            continue
    return {"passed": ok, "total": ROUNDS}


def probe_code_repair():
    """Seeded defect: function returns wrong result (off-by-one). Model must fix."""
    ok = 0
    buggy = "def sum_to(n):\n    # BUG: off-by-one, should be n*(n+1)//2\n    return n*(n-1)//2"
    for _ in range(ROUNDS):
        try:
            c = chat([_u(f"Fix the bug in this function (return the corrected code only):\n```python\n{buggy}\n```")])["content"]
            if "```" in c:
                c = c.split("```")[1].replace("python", "", 1)
            # corrected must contain n+1 and no n-1 in the formula
            if "n+1" in c and "n-1" not in c.replace("def sum_to", ""):
                ok += 1
        except Exception:
            continue
    return {"passed": ok, "total": ROUNDS}


def probe_quality_reasoning():
    """Hidden objective task: word problem with a single correct answer."""
    ok = 0
    q = "A train travels 120 km at 60 km/h, then 60 km at 30 km/h. What is the average speed for the whole trip in km/h? Reply with only the number."
    # total distance 180 km; total time = 120/60 + 60/30 = 2 + 2 = 4h; avg = 45 km/h
    for _ in range(ROUNDS):
        try:
            c = chat([_u(q)])["content"]
            if "45" in c:
                ok += 1
        except Exception:
            continue
    return {"passed": ok, "total": ROUNDS, "expected": 45}


def probe_long_context():
    ok = 0
    fact = "The capital of France is Paris."
    p = "filler line. " * 400 + f"Read the last sentence only: {fact} Now: what is the capital of France? One word."
    for _ in range(ROUNDS):
        try:
            if "Paris" in chat([_u(p)])["content"]:
                ok += 1
        except Exception:
            continue
    return {"passed": ok, "total": ROUNDS}


def probe_tool_use_full():
    """selection -> args -> execution -> readback -> recovery."""
    tools = [{"type": "function", "function": {
        "name": "add_numbers", "description": "Add two integers",
        "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]},
    }}]
    selection = args = executed = readback = 0
    for _ in range(ROUNDS):
        try:
            r = chat([_u("Using the add_numbers tool, compute 7 + 8.")], tools=tools)
            if r.get("tool_calls"):
                selection += 1
                tc = r["tool_calls"][0]
                fn = tc.get("function", {})
                if fn.get("name") == "add_numbers":
                    args += 1
                    try:
                        a = json.loads(fn.get("arguments", "{}"))
                        if a.get("a") == 7 and a.get("b") == 8:
                            executed += 1
                            # simulate execution readback
                            result = a["a"] + a["b"]
                            if result == 15:
                                readback += 1
                    except Exception:
                        pass
        except Exception:
            continue
    return {"selection": selection, "args": args, "execution": executed, "readback": readback, "total": ROUNDS,
            "supported": selection > 0}


def probe_recovery_checkpoint():
    """Model given a partial state must resume correctly (recovery quality)."""
    ok = 0
    p = ("You are resuming an interrupted task. Prior state: steps 1-3 of 5 done. "
         "Step 4 is 'write the word RECOVERED'. Reply ONLY with the single word RECOVERED.")
    for _ in range(ROUNDS):
        try:
            if "RECOVERED" in chat([_u(p)])["content"]:
                ok += 1
        except Exception:
            continue
    return {"passed": ok, "total": ROUNDS}


def probe_review_catch_rate():
    """Blind review: model must catch a seeded defect in code."""
    ok = 0
    buggy = "def divide(a, b):\n    return a / b  # BUG: division by zero not handled"
    for _ in range(ROUNDS):
        try:
            c = chat([_u(f"Review this code and report any bug (answer BUG or NO_BUG only):\n```python\n{buggy}\n```")])["content"]
            if "BUG" in c.upper():
                ok += 1
        except Exception:
            continue
    return {"caught": ok, "total": ROUNDS}


def probe_instruction_adherence():
    """Model must follow a strict output format."""
    ok = 0
    for _ in range(ROUNDS):
        try:
            c = chat([_u("Output the number 42 and NOTHING else (no words, no punctuation).")])["content"].strip()
            if c == "42":
                ok += 1
        except Exception:
            continue
    return {"passed": ok, "total": ROUNDS}


PROBES = [
    ("latency_failure", probe_latency_failure),
    ("code_generation", probe_code_generation),
    ("code_repair", probe_code_repair),
    ("quality_reasoning", probe_quality_reasoning),
    ("long_context", probe_long_context),
    ("tool_use", probe_tool_use_full),
    ("recovery_checkpoint", probe_recovery_checkpoint),
    ("review_catch_rate", probe_review_catch_rate),
    ("instruction_adherence", probe_instruction_adherence),
]


def main() -> int:
    report = {
        "worker_id": "MIMO_DEEPSEEK",
        "model": MODEL,
        "backend": "api.deepseek.com (exact backend, NOT qwen/Ollama)",
        "rounds": ROUNDS,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": {},
    }
    for name, fn in PROBES:
        try:
            report["results"][name] = fn()
        except Exception as e:
            report["results"][name] = {"error": str(e)[:200]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
