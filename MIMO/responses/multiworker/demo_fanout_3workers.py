#!/usr/bin/env python3
"""demo_fanout_3workers.py — FAN_OUT на троих воркеров (A + B + C).

WORKER_A = DeepSeek V4-Pro (api.deepseek.com)
WORKER_B = MiniMax-M3 (api.minimax.io)
WORKER_C = OpenRouter gpt-oss-20b:free (TEST/NON-CANON, user's own key)

Все три — реальные вызовы, ничего не выдумано. WORKER_C = user override
(NON-CANON, без namespace-прав), зафиксирован отдельным документом.
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\4\OUT\MIMO")))
import multiworker as mw  # noqa: E402

PROMPT = "What is 12 * 13? Reply with only the number."


def exec_a(worker_id, task):
    body = json.dumps({"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": task.get("prompt", PROMPT)}]}).encode()
    req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    return {"output": resp["choices"][0]["message"]["content"].strip(), "latency_ms": int((time.time() - t0) * 1000),
            "failure_rate": 0.0, "output_refs": [task["task_id"] + "-a"], "provenance": ["deepseek-v4-pro"], "fencing_token": 1}


def exec_b(worker_id, task):
    body = json.dumps({"model": "MiniMax-M3", "messages": [{"role": "user", "content": task.get("prompt", PROMPT)}]}).encode()
    req = urllib.request.Request("https://api.minimax.io/v1/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["MINIMAX_API_KEY"]})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    content = resp["choices"][0]["message"]["content"]
    if "</think>" in content:
        content = content.split("</think>", 1)[1].strip()
    return {"output": content, "latency_ms": int((time.time() - t0) * 1000),
            "failure_rate": 0.0, "output_refs": [task["task_id"] + "-b"], "provenance": ["MiniMax-M3"], "fencing_token": 2}


def exec_c(worker_id, task):
    body = json.dumps({"model": "openai/gpt-oss-20b:free", "messages": [{"role": "user", "content": task.get("prompt", PROMPT)}]}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    return {"output": resp["choices"][0]["message"]["content"].strip(), "latency_ms": int((time.time() - t0) * 1000),
            "failure_rate": 0.0, "output_refs": [task["task_id"] + "-c"], "provenance": ["openrouter-gpt-oss-20b-free"], "fencing_token": 3}


def main() -> int:
    task = {"task_id": "fanout-3workers-1", "mode": "FAN_OUT", "prompt": PROMPT}

    # register B and C heartbeats so fan_out treats them as live
    mw.register_worker("MIMO_MINIMAX", "inst-b")
    mw.register_worker("MIMO_OPENROUTER_C", "inst-c")

    executors = {
        "MIMO_DEEPSEEK": exec_a,
        "MIMO_MINIMAX": exec_b,
        "MIMO_OPENROUTER_C": exec_c,
    }
    report = mw.fan_out(task, ["MIMO_DEEPSEEK", "MIMO_MINIMAX", "MIMO_OPENROUTER_C"], lambda wid, t: executors[wid](wid, t))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
