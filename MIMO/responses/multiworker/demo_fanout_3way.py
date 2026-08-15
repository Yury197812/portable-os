#!/usr/bin/env python3
"""demo_fanout_3way.py — тестовый FAN_OUT на троих (Control Tower + A + B).

Одна задача broadcast на WORKER_A и WORKER_B. Оба выполняют РЕАЛЬНО через
свои backend'ы:
  - WORKER_A (MIMO_DEEPSEEK): qwen2.5:14b через runtime :8891/api/runs
  - WORKER_B (MIMO_MINIMAX):  MiniMax-M3 через api.minimax.io/v1/chat/completions

Затем merge + battlecheck на реальных ответах. Ничего не выдумано."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\4\OUT\MIMO")))
import multiworker as mw  # noqa: E402

TASK_PROMPT = "What is 12 * 13? Reply with only the number."


def exec_a(worker_id, task):
    """WORKER_A: qwen2.5:14b via runtime :8891 (Ollama)."""
    body = json.dumps({"model": "qwen2.5:14b", "prompt": task.get("prompt", TASK_PROMPT)}).encode()
    req = urllib.request.Request("http://127.0.0.1:8891/api/runs", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return {
        "output": r.get("output"),
        "latency_ms": r.get("latency_ms"),
        "failure_rate": 0.0,
        "output_refs": [task["task_id"] + "-a"],
        "provenance": ["runtime-live", "qwen2.5:14b-ollama"],
        "fencing_token": 1,
    }


def exec_b(worker_id, task):
    """WORKER_B: MiniMax-M3 via api.minimax.io."""
    key = os.environ.get("MINIMAX_API_KEY")
    if not key:
        return None
    body = json.dumps({"model": "MiniMax-M3", "messages": [{"role": "user", "content": task.get("prompt", TASK_PROMPT)}]}).encode()
    req = urllib.request.Request("https://api.minimax.io/v1/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        r = json.loads(resp.read().decode())
    latency = int((time.time() - t0) * 1000)
    content = r["choices"][0]["message"]["content"]
    # strip <think> wrapper if present
    if "</think>" in content:
        content = content.split("</think>", 1)[1].strip()
    return {
        "output": content,
        "latency_ms": latency,
        "failure_rate": 0.0,
        "output_refs": [task["task_id"] + "-b"],
        "provenance": ["minimax-live", "MiniMax-M3"],
        "fencing_token": 2,
    }


def main() -> int:
    task = {"task_id": "fanout-3way-1", "mode": "FAN_OUT", "prompt": TASK_PROMPT}

    # register WORKER_B heartbeat (it registered on GitHub; mark live here)
    mw.register_worker("MIMO_MINIMAX", "inst-minimax-b")

    report = mw.fan_out(task, ["MIMO_DEEPSEEK", "MIMO_MINIMAX"], lambda wid, t: exec_a(wid, t) if wid == "MIMO_DEEPSEEK" else exec_b(wid, t))

    print(json.dumps({
        "task": task,
        "per_worker": report["per_worker"],
        "merged": report["merged"],
    }, ensure_ascii=False, indent=2))

    # battlecheck on the real outputs
    bc_inputs = {}
    for wid, pw in report["per_worker"].items():
        if pw.get("status") == "SUCCEEDED":
            res = pw["result"]
            bc_inputs[wid] = {"output": res.get("output"), "latency_ms": res.get("latency_ms"), "failure_rate": res.get("failure_rate")}
    bc = mw.battlecheck(bc_inputs)
    print("BATTLECHECK:", json.dumps(bc, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
