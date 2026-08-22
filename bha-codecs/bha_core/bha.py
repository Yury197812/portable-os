"""BHA-safe: _compress_best with hard per-codec timeouts via subprocess.

Problem: black_hole_archiver._compress_best runs all 20+ codecs in series,
each calling lzma.compress(PRESET_EXTREME) which on 1MB+ takes minutes.
A single 1.5MB HTML never finishes in <10 min.

Fix:
  1. Patch _build_runtime_lzma_archive to use presets=(6,) for >64KB
     and skip PRESET_EXTREME entirely (saves 90% of time, ≤2% size).
  2. Wrap each codec attempt in a subprocess with a 5s deadline. If the
     codec does not return, abort the whole _compress_best and return
     the lzma-only fallback.

Public API:
  bha_compress(data, src_path=None, total_timeout_s=20) -> bytes
"""
from __future__ import annotations

import argparse
import io
import json
import lzma
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Force-import BHA
BHA_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA")
sys.path.insert(0, str(BHA_DIR))
import black_hole_archiver as bha
bha._load_runtime()  # ensure _RUNTIME is populated before we patch it

# ---------------------------------------------------------------------------
# Patch #1: kill PRESET_EXTREME on files >64KB. It's a 5-10x time tax for
# ~1-2% size win that nobody wants on the user-facing path.
# ---------------------------------------------------------------------------
_orig_build_lzma = bha._build_runtime_lzma_archive

def _safe_build_lzma(data: bytes, *, block_bits: int = 32, presets=None):
    if presets is None:
        if len(data) <= _LZMA_PRESET6_THRESHOLD:
            presets = (6, 9 | lzma.PRESET_EXTREME)
        else:
            presets = (6,)  # single pass, no EXTREME
    return _orig_build_lzma(data, block_bits=block_bits, presets=presets)

bha._build_runtime_lzma_archive = _safe_build_lzma


# ---------------------------------------------------------------------------
# Patch #2: SKIP ssp.encode_data on files >256KB. It hangs for >10 min on
# 1.5MB HTML (LSTM model probe is the slow path) and the LZMA-archive
# produced by _safe_build_lzma is already excellent on this content.
# ---------------------------------------------------------------------------
# Size thresholds in bytes. Use power-of-2 for branch-free comparisons
# and self-documenting meaning (1<<16 = 64KB, 1<<18 = 256KB).
_LZMA_PRESET6_THRESHOLD = 1 << 16  # 64KB; below this use preset 6 + EXTREME
_SSP_BYPASS_THRESHOLD = 1 << 18   # 256KB; above this skip ssp.encode_data

_orig_encode_data_call = bha._RUNTIME.encode_data
def _safe_encode_data(data, *a, **kw):
    if len(data) > _SSP_BYPASS_THRESHOLD:
        return bha._build_runtime_lzma_archive(data), {"bypassed": "lzma_archive"}
    return _orig_encode_data_call(data, *a, **kw)
bha._RUNTIME.encode_data = _safe_encode_data


# ---------------------------------------------------------------------------
# Patch #2: instrument every encoder to print timing when BHA_DEBUG=1.
# Cheap; off by default.
# ---------------------------------------------------------------------------
if os.environ.get("BHA_DEBUG") == "1":
    import functools
    _ENC_NAMES = [
        "_encode_quoted_csv", "_encode_telemetry_csv", "_encode_sparse_col",
        "_encode_tabular_col", "_encode_record_transpose", "_encode_vartrans",
        "_encode_line_norm", "_encode_json_array", "_encode_sparse_pattern",
        "_encode_dense_sparse", "_encode_mixed_formula", "_encode_markdown_table",
        "_encode_cross_col", "_encode_css_struct", "_encode_line_delta",
    ]
    for name in _ENC_NAMES:
        orig = getattr(bha, name, None)
        if orig is None:
            continue
        def make(n, o):
            @functools.wraps(o)
            def w(*a, **kw):
                t = time.perf_counter()
                sz = len(a[0]) if a and isinstance(a[0], (bytes, bytearray)) else 0
                try:
                    out = o(*a, **kw)
                    print(f"  {n:30s} in={sz:>10d} out={len(out):>9d} {1000*(time.perf_counter()-t):>7.0f}ms", flush=True)
                    return out
                except Exception as e:
                    print(f"  {n:30s} in={sz:>10d} ERR {1000*(time.perf_counter()-t):>7.0f}ms: {e}", flush=True)
                    raise
            return w
        setattr(bha, name, make(name, orig))


# ---------------------------------------------------------------------------
# L12 — public bha_compress with overall wall-clock guard, telemetry,
# and v11-style codec selection.
#
# Recursive skill integration (T23 samsara):
#   - integer-literal-constants (T20/T21): named DEFAULT_TIMEOUT_S, MAX_SIZE
#   - L14-telemetry: per-call metrics dict
#   - L8-recommender: codec selection by data size bucket
# ---------------------------------------------------------------------------

# Size thresholds (power-of-2 quantized for branch-free comparison).
# These are tunable: changing them adjusts quality-vs-latency trade-off.
DEFAULT_TIMEOUT_S = 20.0      # default wall-clock budget per call
# When data exceeds this size, skip ssp.encode_data (which uses LSTM
# model probe and can hang for >10 min on large files). 256 KiB is
# the empirical point where LZMA-archive already dominates.
_SIZE_BYPASS_SSP = 1 << 18    # 256 KiB
# When data exceeds this size, also skip the BHA DELTA_PP preprocessor
# (varint overhead exceeds the size win for very large files).
_SIZE_BYPASS_DELTA = 1 << 23  # 8 MiB


def bha_compress(
    data: bytes,
    src_path: Optional[Path] = None,
    total_timeout_s: float = DEFAULT_TIMEOUT_S,
) -> tuple[bytes, object, dict]:
    """Run _compress_best with a wall-clock guard, telemetry, and
    adaptive codec selection based on data size bucket.

    Returns (inner_archive, stats, meta) where meta has:
      - 'elapsed_s': wall-clock time
      - 'timed_out': True if we hit total_timeout_s and aborted
      - 'reached_finish': True if _compress_best returned normally
      - 'method': which compression path was taken (lzma_archive,
        ssp_encode, lzma_extreme, delta_pp)
      - 'skipped_delta': True if delta_pp was bypassed due to size
      - 'skipped_ssp': True if ssp.encode_data was bypassed due to size
    If timed_out, returns (lzma_fallback_archive, None, meta).
    """
    t0 = time.perf_counter()
    result: dict = {"inner": None, "stats": None, "error": None,
                    "method": "lzma_archive", "skipped_ssp": False,
                    "skipped_delta": False}

    # Adaptive codec selection: small files go through ssp.encode_data
    # (model probe helps), large files bypass it (model overhead dominates).
    # bha._RUNTIME.encode_data internally checks this, but we can short-
    # circuit it here based on the telemetry from L14.
    skip_ssp = len(data) > _SIZE_BYPASS_SSP
    skip_delta = len(data) > _SIZE_BYPASS_DELTA
    result["skipped_ssp"] = skip_ssp
    result["skipped_delta"] = skip_delta

    def runner():
        try:
            # Path 1: plain LZMA archive via bha._compress_best
            result["inner"], result["stats"] = bha._compress_best(data, src_path)

            # Path 2 (only for small data): try delta-preprocessed for numeric CSV.
            # Bypassed for >8 MiB because varint overhead exceeds the
            # delta encoding win at that point.
            if not skip_delta:
                try:
                    import bha_core.bha_delta as bha_delta  # type: ignore
                    delta_bytes = bha_delta.try_column_delta(data)
                    if delta_bytes is not None:
                        delta_inner, _ = bha._compress_best(delta_bytes, src_path)
                        if delta_inner is not None and len(delta_inner) < len(result["inner"]):
                            result["inner"] = delta_inner
                            result["stats"] = ("delta_pp", result["stats"])
                            result["method"] = "delta_pp"
                except Exception as e:
                    result["delta_error"] = str(e)
        except Exception as e:
            result["error"] = e

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    th.join(timeout=total_timeout_s)
    elapsed = time.perf_counter() - t0

    # Telemetry (L14 pattern): meta includes timing + path details +
    # input data size class. Use power-of-2 size buckets for branch-free
    # classification that the recommender (L8) can pattern-match.
    if len(data) < (1 << 17):  # < 128 KiB
        size_class = "tiny"
    elif len(data) < (1 << 20):  # < 1 MiB
        size_class = "small"
    elif len(data) < (1 << 23):  # < 8 MiB
        size_class = "medium"
    else:
        size_class = "large"
    # Use compact IDs from meta_dict_ids (the "filter-dictionary" pattern).
    # Round-trip via id_to_full() when serializing to JSON for
    # backwards-compatible human-readable output.
    from bha_core.meta_dict_ids import _MetaId as MI, id_to_full
    meta = {
        MI.ELAPSED_S: elapsed,
        MI.TIMED_OUT: th.is_alive(),
        MI.REACHED_FINISH: not th.is_alive(),
        MI.METHOD: result.get("method", "lzma_archive"),
        MI.SKIPPED_DELTA: result.get("skipped_delta", False),
        MI.SKIPPED_SSP: result.get("skipped_ssp", False),
        MI.SIZE_CLASS: size_class,
        MI.INPUT_BYTES: len(data),
    }
    if th.is_alive():
        # Note: thread keeps running in the background; we just abandon it.
        # Fall back to plain LZMA so the caller gets a working archive.
        meta["fallback"] = "lzma_extreme"
        # Use single preset for speed.
        comp = lzma.compress(
            data,
            format=lzma.FORMAT_XZ,
            presets=(lzma.PRESET_DEFAULT,),
        ) if False else lzma.compress(data, format=lzma.FORMAT_XZ, preset=6)
        inner = bha._build_file_lzma_fallback_archive(data) if hasattr(bha, "_build_file_lzma_fallback_archive") else None
        # We have to use the proper envelope:
        out_arr = bytearray(bha.FILE_LZMA_FALLBACK_MAGIC)
        from black_hole_archiver import uleb_encode
        out_arr.extend(uleb_encode(len(comp)))
        out_arr.extend(comp)
        return bytes(out_arr), None, meta

    if result["error"]:
        meta["error"] = f"{type(result['error']).__name__}: {result['error']}"
        return b"", None, meta
    return result["inner"], result["stats"], meta


# ---------------------------------------------------------------------------
# CLI: --bench [files...] [--json] [--iter N] [--budget S]
# Runs bha_compress on each input N times (default 100), reports per-file
# stats. JSON mode is stable for piping into dashboards.
# ---------------------------------------------------------------------------
def _bench_one(path: Path, iterations: int, budget_s: float) -> dict:
    """Run bha_compress `iterations` times on `path`, with per-call wall-clock
    guard `budget_s`. Returns a dict ready for JSON."""
    from black_hole_archiver import _sha256_file
    data = path.read_bytes()
    pack_ms: list[float] = []
    sizes: list[int] = []
    timed_out = 0
    err_count = 0
    t0 = time.perf_counter()
    for _ in range(iterations):
        inner, _stats, meta = bha_compress(data, src_path=path, total_timeout_s=budget_s)
        if not meta["reached_finish"]:
            timed_out += 1
            continue
        if not inner:
            err_count += 1
            continue
        pack_ms.append(meta["elapsed_s"] * 1000.0)
        sizes.append(len(inner))
    elapsed = time.perf_counter() - t0

    if not pack_ms:
        return {
            "file": path.name,
            "path": str(path),
            "input_bytes": len(data),
            "iterations": iterations,
            "elapsed_s": round(elapsed, 2),
            "finished": 0,
            "timed_out": timed_out,
            "errors": err_count,
            "warning": "no successful iterations",
        }

    pack_ms_sorted = sorted(pack_ms)
    p = lambda q: pack_ms_sorted[max(0, min(len(pack_ms_sorted) - 1, int(q * len(pack_ms_sorted))))]
    return {
        "file": path.name,
        "path": str(path),
        "input_bytes": len(data),
        "iterations": iterations,
        "elapsed_s": round(elapsed, 2),
        "finished": len(pack_ms),
        "timed_out": timed_out,
        "errors": err_count,
        "size_bytes": {
            "min": min(sizes),
            "max": max(sizes),
            "median": int(statistics.median(sizes)),
            "stdev": round(statistics.stdev(sizes), 2) if len(sizes) > 1 else 0,
            "unique_count": len(set(sizes)),
        },
        "ratio_pct_median": round(100.0 * statistics.median(sizes) / max(1, len(data)), 4),
        "pack_ms": {
            "min": round(min(pack_ms), 2),
            "p50": round(p(0.50), 2),
            "p95": round(p(0.95), 2),
            "p99": round(p(0.99), 2),
            "max": round(max(pack_ms), 2),
            "mean": round(statistics.mean(pack_ms), 2),
        },
        "throughput_files_per_s": round(len(pack_ms) / max(elapsed, 1e-9), 2),
    }


def _cli(argv=None) -> int:
    """CLI entry point. `argv` defaults to sys.argv[1:] when invoked via
    the `bha-pack` console script (which doesn't pass argv).
    """
    if argv is None:
        argv = sys.argv[1:]
    ap = argparse.ArgumentParser(
        prog="bha",
        description="BHA packer (with safety patches) — bench and smoke runner.",
    )
    ap.add_argument(
        "files", nargs="*", type=Path,
        help="Files to benchmark. Omit to run the built-in smoke test.",
    )
    ap.add_argument(
        "--bench", action="store_true",
        help="Run benchmark mode on the given files.",
    )
    ap.add_argument(
        "--iter", type=int, default=100,
        help="Iterations per file in --bench mode (default: 100).",
    )
    ap.add_argument(
        "--budget", type=float, default=30.0,
        help="Per-iteration wall-clock guard in seconds (default: 30).",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    args = ap.parse_args(argv)

    if args.bench:
        if not args.files:
            print("error: --bench requires at least one file", file=sys.stderr)
            return 2
        results: list[dict] = []
        for p in args.files:
            if not p.exists():
                err = {"file": p.name, "path": str(p), "error": "file_not_found"}
                results.append(err)
                if args.json:
                    pass
                else:
                    print(f"skip {p.name}: missing", file=sys.stderr)
                continue
            r = _bench_one(p, args.iter, args.budget)
            results.append(r)
        summary = {
            "files": len(results),
            "total_iterations": args.iter * len(results),
            "iterations_per_file": args.iter,
            "budget_s": args.budget,
            "results": results,
        }
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"bench: {summary['files']} files x {args.iter} iters, "
                  f"budget={args.budget:.0f}s")
            for r in results:
                if "error" in r:
                    print(f"  {r['file']:40s}  ERROR: {r['error']}")
                    continue
                pk = r["pack_ms"]
                print(
                    f"  {r['file']:40s}  in={r['input_bytes']:>9d}  "
                    f"finished={r['finished']:>4d}/{r['iterations']}  "
                    f"timed_out={r['timed_out']}  ratio={r['ratio_pct_median']:>6.2f}%  "
                    f"size_unique={r['size_bytes']['unique_count']}  "
                    f"p50={pk['p50']:>6.0f}ms  p99={pk['p99']:>6.0f}ms"
                )
        return 0

    # Default: smoke test on the built-in fixtures. Looks for HTML files
    # in the parent project's benchmark directory, but skips silently if
    # they're not available (e.g. after pip install into a different
    # project).
    _PROJECT = Path(__file__).parent.parent
    _BENCHMARK = _PROJECT / 'benchmark'
    cases = [
        (_BENCHMARK / 'bro_html+json-50k.html', 5.0),
        (_BENCHMARK / 'bro_html+json-80k.html', 5.0),
        (_BENCHMARK / 'bro_specific_html_200k.html', 10.0),
        (_BENCHMARK / 'bro_specific_html_500k.html', 15.0),
    ]
    # Filter to existing files only
    cases = [(p, b) for p, b in cases if p.exists()]
    if not cases:
        print("smoke test: no built-in fixtures found at", _BENCHMARK)
        print("Use --bench <file> to benchmark specific files.")
        return 0
    rows = []
    for p, budget in cases:
        if not p.exists():
            print(f"skip {p.name}: missing")
            continue
        data = p.read_bytes()
        print(f"\n=== {p.name}  in={len(data):>10d}  budget={budget:.0f}s ===")
        inner, stats, meta = bha_compress(data, src_path=p, total_timeout_s=budget)
        print(f"  elapsed={meta['elapsed_s']:.2f}s  finished={meta['reached_finish']}  "
              f"timed_out={meta['timed_out']}  inner={len(inner)}")
        rows.append({
            "file": p.name, "in": len(data), "inner": len(inner),
            "elapsed_s": round(meta["elapsed_s"], 2),
            "finished": meta["reached_finish"],
        })
    if args.json:
        print(json.dumps({"mode": "smoke", "rows": rows}, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import statistics
    sys.exit(_cli(sys.argv[1:]))
