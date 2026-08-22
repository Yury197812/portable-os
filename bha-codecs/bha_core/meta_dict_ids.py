"""bha_core meta_dict_ids: shared key vocabulary for telemetry dicts.

Across the bha_core stack (bha_compress, bha_parallel, bha_persistent_pool,
bench harness) we use the same set of keys in `meta` dicts. To save
bandwidth (e.g. for cross-process telemetry, persistent pool metadata,
benchmark JSON output) and to make keys consistent across modules, all
modules should reference this single source of truth.

Each key is a short ID (1-4 chars) that encodes the semantic meaning.
A short reverse map (full → id, id → full) is provided for
documentation and human-readable fallbacks.

This is the "встроенный фильтр-словарь" (embedded filter-dictionary)
the user asked us to apply: it decomposes the verbose JSON keys into
compact ID-encoded form, with the original full names kept for
backwards compatibility / debug output.

Note: this is the documentation / vocabulary layer. Actual call sites
use the short IDs as dict keys directly (e.g. `meta[ID.ELAPSED_S]`
not `meta["elapsed_s"]`). The full name is computed by
`id_to_full(id)` when serializing to JSON.
"""
from __future__ import annotations
from typing import Dict


class _MetaId:
    """Namespace for meta-dict key constants.

    Each class attribute is a short ID (1-4 chars). The full name (in
    comment) is the human-readable equivalent used in docs.
    """

    # === bha_compress (L12 pipeline) ===
    ELAPSED_S = "etd"          # elapsed_s (float, seconds)
    TIMED_OUT = "tmo"          # timed_out (bool)
    REACHED_FINISH = "rf"     # reached_finish (bool)
    METHOD = "mth"            # method (str: lzma_archive, delta_pp, ...)
    SKIPPED_DELTA = "skd"     # skipped_delta (bool, >8 MiB)
    SKIPPED_SSP = "sks"       # skipped_ssp (bool, >256 KiB)
    SIZE_CLASS = "szc"        # size_class (str: tiny/small/medium/large)
    INPUT_BYTES = "ib"        # input_bytes (int)

    # === bha_parallel (L9 orchestrator) ===
    BEST_GATE = "bgt"         # best_gate (str)
    BEST_SIZE = "bsz"         # best_size (int)
    N_GATES_SUCCEEDED = "ngs" # n_gates_succeeded (int)
    GATES_TRIED = "gtr"       # gates_tried (list[str])
    ELAPSED = "el"           # elapsed (float, parallel seconds)
    METHOD_PARALLEL = "mpa"   # 'parallel' | 'fallback_sequential' | ...
    WORKERS_USED = "wku"     # selected_n_workers (int)
    POOL_INIT_MS = "pim"     # pool_init_ms (float)
    POOL_REUSED = "pru"      # pool_reused (bool)

    # === benchmark harness (L11 CLI) ===
    FILE = "fn"             # file (str)
    PATH = "pth"            # path (str)
    ITERATIONS = "itr"      # iterations (int)
    FINISHED = "fnh"        # finished (int, count of successful runs)
    ERRORS = "err"          # errors (int)
    SIZE_BYTES = "sbz"      # size_bytes (dict)
    RATIO_PCT_MEDIAN = "rpm" # ratio_pct_median (float)
    PACK_MS = "pms"         # pack_ms (dict)
    THROUGHPUT_FILES_PER_S = "tps"  # throughput_files_per_s (float)

    # === T8 recommender integration ===
    V11_PRIORITY = "vpr"   # v11_priority (list[str])
    V11_LZMA_PRESET = "vlp"  # v11_lzma_preset (int)
    V11_ONLY_MODE = "vom"   # v11_only_mode (bool)


_FULL_NAMES: Dict[str, str] = {
    # bha_compress
    "etd": "elapsed_s",
    "tmo": "timed_out",
    "rf":  "reached_finish",
    "mth": "method",
    "skd": "skipped_delta",
    "sks": "skipped_ssp",
    "szc": "size_class",
    "ib":  "input_bytes",
    # bha_parallel
    "bgt": "best_gate",
    "bsz": "best_size",
    "ngs": "n_gates_succeeded",
    "gtr": "gates_tried",
    "el":  "elapsed",
    "mpa": "method",
    "wku": "selected_n_workers",
    "pim": "pool_init_ms",
    "pru": "pool_reused",
    # benchmark
    "fn":  "file",
    "pth": "path",
    "itr": "iterations",
    "fnh": "finished",
    "err": "errors",
    "sbz": "size_bytes",
    "rpm": "ratio_pct_median",
    "pms": "pack_ms",
    "tps": "throughput_files_per_s",
    # v11
    "vpr": "v11_priority",
    "vlp": "v11_lzma_preset",
    "vom": "v11_only_mode",
}

_ID_NAMES: Dict[str, str] = {v: k for k, v in _FULL_NAMES.items()}


def id_to_full(key_id: str) -> str:
    """Map a 1-4 char ID to its full name. Falls back to key_id if unknown."""
    return _FULL_NAMES.get(key_id, key_id)


def full_to_id(full_name: str) -> str:
    """Map a full name to its 1-4 char ID. Falls back to full_name if unknown."""
    return _ID_NAMES.get(full_name, full_name)


# Public re-export
__all__ = ["_MetaId", "id_to_full", "full_to_id"]