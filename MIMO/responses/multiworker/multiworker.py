#!/usr/bin/env python3
"""
multiworker.py — ArtWeb Orchestra multi-worker coordination layer.

Prepares the Orchestra for a second independent MIMO worker (WORKER_B) on the
same host without breaking the existing WORKER_A transport.

Honesty rules (P0 PREP):
- WORKER_B is NOT live until its namespace/heartbeat actually appears. Until
  then every reference reports PREPARED/WAITING_HEARTBEAT — never LIVE.
- No shared writable result.json/state.json between workers; each worker has
  its own inbox/outbox/state/work dirs.
- Lease/fencing prevents two workers completing the same task.
- Worker capabilities are calibrated empirically, never assumed from brand.

Stdlib-only.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

try:
    import msvcrt  # Windows file locking (IPC)
except ImportError:  # pragma: no cover
    msvcrt = None

ROOT = Path(r"D:\4\OUT\MIMO")
MW_DIR = ROOT / "workers"

# ---------------------------------------------------------------------------
# Worker registry
# ---------------------------------------------------------------------------

# Static worker definitions. WORKER_A = us (live); WORKER_B = future MiniMax
# (NOT live until it registers). model_backend is a string, never an assumption.
WORKERS = {
    "MIMO_DEEPSEEK": {
        "worker_id": "MIMO_DEEPSEEK",
        "role": "WORKER_A",
        "engine": "MIMO",
        "model_backend": "DeepSeek V4-Pro 0813",
        "local_root": str(Path(r"C:\Users\Art\ArtWebStudio\artweb-studio\runtime")),
        "github_namespace": "MIMO/responses/",
        "ntfy_topic": "artweb-mimo-bus-20260814-8d3f2a761c4e",
        "live": True,
    },
    "MIMO_MINIMAX": {
        "worker_id": "MIMO_MINIMAX",
        "role": "WORKER_B",
        "engine": "MIMO",
        "model_backend": "MiniMax",
        "local_root": str(Path(r"D:\4\OUT\MIMO_MINIMAX")),
        "github_namespace": "MIMO/workers/MIMO_MINIMAX/",
        "ntfy_topic": "artweb-mimo-minimax-bus-20260815-e50aec37c62f",
        "live": False,
    },
}

# live heartbeat map: worker_id -> {instance_id, last_heartbeat_ts}
_HEARTBEATS: dict[str, dict] = {}
_HB_LOCK = threading.Lock()


def worker_dir(worker_id: str) -> Path:
    return MW_DIR / worker_id


def _subdirs(worker_id: str) -> dict[str, Path]:
    d = worker_dir(worker_id)
    sub = {name: d / name for name in ("inbox", "outbox", "state", "work")}
    return sub


def ensure_worker_dirs(worker_id: str) -> dict[str, Path]:
    subs = _subdirs(worker_id)
    for p in subs.values():
        p.mkdir(parents=True, exist_ok=True)
    return subs


def register_worker(worker_id: str, instance_id: str, model_backend: str | None = None) -> dict:
    """Register a worker instance with a heartbeat. Idempotent."""
    if worker_id not in WORKERS:
        return {"ok": False, "error": f"unknown worker {worker_id}", "known": sorted(WORKERS)}
    with _HB_LOCK:
        _HEARTBEATS[worker_id] = {
            "instance_id": instance_id,
            "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model_backend": model_backend or WORKERS[worker_id]["model_backend"],
        }
    ensure_worker_dirs(worker_id)
    return {"ok": True, "worker_id": worker_id, "instance_id": instance_id}


def heartbeat(worker_id: str, instance_id: str) -> dict:
    """Update a worker's heartbeat timestamp."""
    return register_worker(worker_id, instance_id)


def worker_status(worker_id: str | None = None) -> dict:
    """Status for one worker or all. WORKER_B reports PREPARED/WAITING_HEARTBEAT
    until a heartbeat actually appears — never LIVE."""
    def one(wid: str) -> dict:
        meta = WORKERS[wid]
        hb = _HEARTBEATS.get(wid)
        if hb:
            status = "LIVE" if meta["live"] else "HEARTBEAT_SEEN_BUT_UNVERIFIED"
        else:
            status = "LIVE" if meta["live"] else "PREPARED/WAITING_HEARTBEAT"
        return {
            "worker_id": wid,
            "role": meta["role"],
            "engine": meta["engine"],
            "model_backend": meta["model_backend"],
            "status": status,
            "instance_id": hb["instance_id"] if hb else None,
            "last_heartbeat": hb["last_heartbeat"] if hb else None,
            "local_root": meta["local_root"],
            "github_namespace": meta["github_namespace"],
            "ntfy_topic": meta["ntfy_topic"],
        }
    if worker_id:
        return one(worker_id) if worker_id in WORKERS else {"error": "unknown worker"}
    return {"workers": [one(w) for w in WORKERS]}


# ---------------------------------------------------------------------------
# Task envelope
# ---------------------------------------------------------------------------

# Task status FSM: QUEUED -> LEASED -> RUNNING -> SUCCEEDED|FAILED|RECLAIMED.
# Task modes (Control Tower selects): SOLO / REVIEW / FAN_OUT / PIPELINE /
# BATTLECHECK / FAILOVER. Only Control Tower promotes outputs to canon.
TASK_MODES = ("SOLO", "REVIEW", "FAN_OUT", "PIPELINE", "BATTLECHECK", "FAILOVER")


def make_task_envelope(**fields) -> dict:
    """Build a canonical task envelope with all required fields defaulted.

    Required (P0 PREP §4): task_id, parent_task_id, worker_id/recipient,
    required_capabilities, priority, deadline, budget, max_attempts,
    input_refs, output_refs, provenance, status, fencing_token."""
    env = {
        "task_id": fields.get("task_id") or uuid.uuid4().hex[:12],
        "parent_task_id": fields.get("parent_task_id"),
        "worker_id": fields.get("worker_id"),
        "recipient": fields.get("recipient") or fields.get("worker_id"),
        "required_capabilities": fields.get("required_capabilities") or [],
        "priority": fields.get("priority", 5),
        "deadline": fields.get("deadline"),
        "budget": fields.get("budget"),
        "max_attempts": fields.get("max_attempts", 1),
        "input_refs": fields.get("input_refs") or [],
        "output_refs": fields.get("output_refs") or [],
        "provenance": fields.get("provenance") or [],
        "status": fields.get("status", "QUEUED"),
        "fencing_token": fields.get("fencing_token", 0),
        "mode": fields.get("mode") or "SOLO",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if env["mode"] not in TASK_MODES:
        raise ValueError(f"unknown mode {env['mode']}")
    return env


# ---------------------------------------------------------------------------
# Lease / fencing (cross-worker)
# ---------------------------------------------------------------------------

_FENCE = {"value": 0}
_FENCE_LOCK = threading.Lock()


def next_fencing_token() -> int:
    with _FENCE_LOCK:
        _FENCE["value"] += 1
        return _FENCE["value"]


def _file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
    try:
        if msvcrt is not None:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        return f
    except Exception:
        f.close()
        raise


def _file_unlock(f) -> None:
    try:
        if msvcrt is not None:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    finally:
        f.close()


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Task store (per-worker work dir)
# ---------------------------------------------------------------------------

def task_path(worker_id: str, task_id: str) -> Path:
    return _subdirs(worker_id)["work"] / f"{task_id}.json"


def assign_task(task: dict, worker_id: str) -> dict:
    """Assign a task to a worker. Sets worker_id/recipient and a fresh fencing
    token. The worker must present this token to complete — prevents two
    workers from both completing the same task."""
    if worker_id not in WORKERS:
        return {"ok": False, "error": f"unknown worker {worker_id}"}
    ensure_worker_dirs(worker_id)
    env = make_task_envelope(**task)
    env["worker_id"] = worker_id
    env["recipient"] = worker_id
    env["fencing_token"] = next_fencing_token()
    env["status"] = "QUEUED"
    f = _file_lock(_subdirs(worker_id)["work"] / ".lock")
    try:
        _atomic_write(task_path(worker_id, env["task_id"]), json.dumps(env, ensure_ascii=False, indent=2))
    finally:
        _file_unlock(f)
    return {"ok": True, "task": env}


def complete_task(worker_id: str, task_id: str, fencing_token: int, result: dict, status: str = "SUCCEEDED") -> dict:
    """Complete a task. Fenced: stale token -> refuse (two workers can't both
    complete the same task)."""
    p = task_path(worker_id, task_id)
    if not p.exists():
        return {"ok": False, "error": "task not found", "fenced": False}
    f = _file_lock(p.parent / ".lock")
    try:
        env = json.loads(p.read_text(encoding="utf-8"))
        if env.get("fencing_token") != fencing_token:
            return {"ok": False, "error": f"stale fencing token {fencing_token} != {env.get('fencing_token')}", "fenced": True}
        env["status"] = status
        env["result"] = result
        env["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _atomic_write(p, json.dumps(env, ensure_ascii=False, indent=2))
        return {"ok": True, "task_id": task_id, "status": status, "fenced": False}
    finally:
        _file_unlock(f)


# ---------------------------------------------------------------------------
# Worker capability registry + empirical calibration
# ---------------------------------------------------------------------------

# Capability registry: capabilities are CALIBRATED from observed runs, never
# assumed from brand. quality/tool_use/code/long_context/latency_ms/cost/
# failure_rate are all empirical — empty until measured.
_CAPABILITIES: dict[str, dict] = {}


def capability_dimensions() -> list[str]:
    return ["quality", "tool_use", "code", "long_context", "latency_ms", "cost", "failure_rate"]


def init_capability(worker_id: str) -> dict:
    if worker_id not in _CAPABILITIES:
        _CAPABILITIES[worker_id] = {dim: None for dim in capability_dimensions()}
        _CAPABILITIES[worker_id]["samples"] = 0
    return _CAPABILITIES[worker_id]


def _dim_stats(worker_id: str, dim: str) -> dict:
    """Running stats for one dimension: count, mean, min, max, last."""
    caps = init_capability(worker_id)
    s = caps.get(f"_stats_{dim}")
    if not s:
        return {"dim": dim, "count": 0, "mean": None, "min": None, "max": None, "last": caps.get(dim)}
    n = s["count"]
    return {
        "dim": dim,
        "count": n,
        "mean": s["sum"] / n,
        "min": s["min"],
        "max": s["max"],
        "last": caps.get(dim),
    }


def record_observation(worker_id: str, dim: str, value: float) -> dict:
    """Record one empirical observation with running stats. DISCOVERED ≠
    VERIFIED — a single observation does not establish a capability; only
    repeated calibration (min 3 rounds) does."""
    init_capability(worker_id)
    caps = _CAPABILITIES[worker_id]
    if dim not in capability_dimensions():
        return {"ok": False, "error": f"unknown dimension {dim}"}
    key = f"_stats_{dim}"
    s = caps.get(key) or {"count": 0, "sum": 0.0, "min": None, "max": None}
    s["count"] += 1
    s["sum"] += value
    s["min"] = value if s["min"] is None else min(s["min"], value)
    s["max"] = value if s["max"] is None else max(s["max"], value)
    caps[key] = s
    caps[dim] = value  # last observation
    caps["samples"] = caps.get("samples", 0) + 1
    return {"ok": True, "worker_id": worker_id, "dim": dim, "value": value, "stats": _dim_stats(worker_id, dim)}


def dimension_verdict(worker_id: str, dim: str, min_rounds: int = 3) -> str:
    """VERIFIED only when >= min_rounds observations exist. Otherwise
    UNVERIFIED (partial) or NOT_RUN (zero)."""
    stats = _dim_stats(worker_id, dim)
    n = stats["count"]
    if n == 0:
        return "NOT_RUN"
    if n >= min_rounds:
        return "VERIFIED"
    return "UNVERIFIED"


def capability_status(worker_id: str | None = None) -> dict:
    """Capability registry snapshot with per-dimension running stats + verdict.
    Dimensions with count=0 = NOT measured. Never infer strengths from brand."""
    def one(wid: str) -> dict:
        dims = {}
        for dim in capability_dimensions():
            dims[dim] = {**_dim_stats(wid, dim), "verdict": dimension_verdict(wid, dim)}
        return {"worker_id": wid, "calibrated": dims, "samples": init_capability(wid).get("samples", 0)}
    if worker_id:
        return one(worker_id) if worker_id in WORKERS else {"error": "unknown worker"}
    return {"capabilities": {w: one(w) for w in WORKERS}}


# ---------------------------------------------------------------------------
# Result merge protocol
# ---------------------------------------------------------------------------

def merge_results(results: list[dict]) -> dict:
    """Merge N worker results: dedup by output_refs hash, build conflict graph,
    attach evidence/provenance, battlecheck verdict, accept/reject.

    Returns {accepted, rejected, conflicts, evidence, verdict}."""
    seen = {}
    conflicts = []
    evidence = []
    accepted = []
    rejected = []

    for r in results:
        key = r.get("output_refs") and tuple(sorted(r.get("output_refs", []))) or r.get("task_id")
        if key in seen:
            conflicts.append({"a": seen[key], "b": r.get("worker_id") or r.get("task_id"), "reason": "duplicate output_refs"})
            rejected.append(r)
            continue
        seen[key] = r.get("worker_id") or r.get("task_id")
        accepted.append(r)
        evidence.append({"worker": r.get("worker_id"), "provenance": r.get("provenance", []), "fencing_token": r.get("fencing_token")})

    verdict = "CLEAN" if not conflicts else "CONFLICT"
    return {
        "accepted": accepted,
        "rejected": rejected,
        "conflicts": conflicts,
        "evidence": evidence,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Task broker
# ---------------------------------------------------------------------------

def broker_route(task: dict, available_workers: list[str]) -> dict:
    """Route a task per mode:
    - SOLO / REVIEW / PIPELINE: exclusive route to ONE worker (by capability or
      round-robin) — never fan out.
    - FAN_OUT / BATTLECHECK: broadcast to ALL available workers for comparison.
    Control Tower owns final acceptance."""
    mode = task.get("mode", "SOLO")
    if mode in ("FAN_OUT", "BATTLECHECK"):
        return {"mode": mode, "route": "broadcast", "workers": list(available_workers)}
    if mode in ("SOLO", "REVIEW", "PIPELINE", "FAILOVER"):
        # pick first available (routing policy refinement owned by Control Tower)
        return {"mode": mode, "route": "exclusive", "worker": available_workers[0] if available_workers else None}
    return {"mode": mode, "route": "unknown_mode"}
