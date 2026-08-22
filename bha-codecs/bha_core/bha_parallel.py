"""
bha_parallel: process-pool parallelization of BHA's 17-gate orchestrator.

Key insight from notes.md / memory (the previous ThreadPoolExecutor attempt
FAILED because ssp._RUNTIME is shared state with lock contention in
the BHA C++ DLL). Using multiprocessing.ProcessPoolExecutor instead
sidesteps this entirely: each worker is a fresh Python process with its
own ssp._RUNTIME. No GIL, no shared DLL state, no lock contention.

Design:
- One worker_init() call per process: loads ssp._RUNTIME once.
- One worker_gate() call: runs a single gate + delta_pp.
- Coordinator: submits ~10-15 independent gates in parallel, picks
  min(encoded size) result. Plus fallback: lzma_fallback_archive.
- Threshold >= 500KB: smaller files have multiprocessing spawn
  overhead (~200ms/worker) that exceeds the LZMA2 encoding cost
  (memory-historical-factory-cleanup line 10: per-worker
  re-import overhead 30ms × N eats the win at N<=11).

SAFETY: original BHA source (black_hole_archiver.py) is NOT modified.
This module is opt-in only via bha_parallel_compress().

Caveat from memory-spillover-completed-tracks.md line 33:
multiprocessing.Manager() requires freeze_support() guard. We don't
use Manager, but we do use Pool/ProcessPoolExecutor which uses spawn
on Windows. Need __main__ guard + freeze_support() for safety.
"""
from __future__ import annotations
import sys
import time
import os
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple

# When run as a script (not imported as part of the bha_core package),
# add the package directory and the BHA runtime to sys.path so the
# cross-imports (bha_delta, bha_v10_pp_safe, bha_recommender_v11) resolve.
# When imported as `bha_core.bha_parallel`, the package mechanism handles
# this and these paths are no-ops.
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

# Threshold: file size below which multiprocessing overhead exceeds gain
# Based on memory-historical-factory-cleanup line 10:
# "per-worker re-import overhead (30ms × N) eats the win at N<=11"
# For BHA LZMA2 encoding at ~500MB/s, 500KB = ~1ms per worker,
# 8 workers = 8ms total work + 200ms spawn = no win.
# 1MB+ = 2ms+ work, win.
# Use a power-of-2 quantized threshold for branch-free size class checks.
# 2**19 = 524288 ~= 512KB (close to 500KB), 2**21 = 2097152 ~= 2MB.
PARALLEL_MIN_SIZE = 1 << 19   # 512KB; below this, sequential path is faster
PARALLEL_MEDIUM_MAX = 1 << 21  # 2MB; medium files get 1-2 workers
PARALLEL_LARGE_MAX = 1 << 23   # 8MB; large files get 2-4 workers
PARALLEL_XLARGE_MIN = 1 << 23  # 8MB+; xlarge files use full pool
DEFAULT_WORKERS = 8

# Adaptive threshold tuning. The simple 500KB cut-off was a v1 guess
# that gave 1.15x avg and 3/6 wins on the 6-fixture benchmark
# (see bha-codecs/README.md section 11.4). The cost model:
#   startup_per_worker = 0.2s      (Python + bha modules + ssp_DLL)
#   work_per_byte     = 2 ns/byte  (lzma ~500 MB/s)
# We parallelize only if total work across N workers dominates
# total startup (rule of thumb: 2x ratio = break-even).
#
# File classification:
#   is_csv_like  = first 1KB is plain ASCII with ',' or '\t' in
#                 line 0 and '\n' in <=1KB.  Cheap sniff.
# Then:
#   small <500KB       -> never profitable on 8 workers
#   csv_like <100KB     -> 2 workers (delta_pp wins despite overhead)
#   medium 500KB-1MB    -> baseline sequential, or 2-worker (low overhead)
#   large >1MB          -> 4-8 workers (real work amortizes)
#
# If is_csv_like is True and data has numeric columns, the threshold
# drops because delta_pp encodes delta_pp output, not raw data.
# We keep the existing public API: bha_parallel_compress always
# uses the determined n_workers; user can override via max_workers.

import os as _os  # noqa: E402 (top-level for early use)


def _is_csv_like(data: bytes) -> bool:
    """Quick sniff: first line is plain ASCII, has a comma or tab,
    and at least one newline within the first 1KB. False negatives
    are fine - we just won't apply the CSV boost."""
    sample = data[:1024]
    if not sample:
        return False
    head = sample.split(b'\n', 1)[0]
    if not head or len(head) > 256:
        return False
    # require plain ASCII (no high-bit) and a delimiter
    if any(b > 127 for b in head):
        return False
    if b',' not in head and b'\t' not in head and b';' not in head:
        return False
    # require at least one more line within first 1KB
    return b'\n' in sample[1:]


def _select_parallel_strategy(
    size: int,
    is_csv_like: bool,
    n_workers_max: int = DEFAULT_WORKERS,
) -> int:
    """Return optimal worker count, or 0 to skip parallel path.

    Empirical model:
    - per-worker startup = 0.2s (Python + bha imports + ssp_DLL load)
    - per-worker work  = 2 ns/byte (lzma 500 MB/s)
    - delta_pp on CSV may deliver large compression even for small
      inputs, so CSV path uses lower threshold.
    """
    # 1. Below the minimum: never profitable, even with delta_pp
    if size < (1 << 18):  # < 256KB
        return 0
    # 2. CSV path: delta_pp can win even on small files
    if is_csv_like:
        if size < PARALLEL_MIN_SIZE:  # 256-512KB CSV: 1 worker (low overhead)
            return 1
        if size < PARALLEL_MEDIUM_MAX:  # 512KB-2MB: 2 workers
            return 2
        return min(4, n_workers_max)
    # 3. Non-CSV path: must amortize worker startup
    if size < PARALLEL_MEDIUM_MAX:  # < 2MB: 0 or 1 worker
        return 0
    if size < (1 << 24):  # 2-16MB: 2 workers
        return 2
    if size < (1 << 26):  # 16-64MB: 4 workers
        return 4
    return min(n_workers_max, 8)  # 64MB+: 8 workers


def _select_workers_for(data: bytes) -> int:
    """Public entry: classify data and return optimal worker count."""
    n_max = max(1, DEFAULT_WORKERS)
    return _select_parallel_strategy(
        len(data), _is_csv_like(data), n_max
    )

# Global worker state (set once per worker process by worker_init)
_WORKER_SSP = None
_WORKER_BHA_DELTA = None


def worker_init() -> None:
    """Called once per worker process to load BHA's ssp runtime and
    bha_delta. Avoids re-import cost per task."""
    global _WORKER_SSP, _WORKER_BHA_DELTA
    if _WORKER_SSP is not None:
        return
    from black_hole_archiver import _load_runtime
    _WORKER_SSP = _load_runtime()
    # Pre-load bha_delta for column detection.
    # In subprocess spawn, the bha_core package is importable because
    # the parent's directory is on PYTHONPATH (set by ProcessPoolExecutor
    # initializer). Use absolute import to avoid sys.path mutation.
    import bha_core.bha_delta as bha_delta  # type: ignore
    _WORKER_BHA_DELTA = bha_delta


def worker_gate(args: Tuple[str, bytes, Optional[str]]) -> Optional[Tuple[str, int, bytes]]:
    """Run a single gate or transformation.

    args: (gate_name, data, src_path_str_or_None)
    Returns: (gate_name, encoded_size, encoded_bytes) or None

    Refactored (T17 Oculus atomization): the 242-line if/elif chain was
    replaced with a registry-driven dispatcher. Special gates that
    don't fit the standard (check + encode + build_archive) contract
    (delta_pp, v10 pp, structured) are handled below.
    """
    global _WORKER_SSP
    gate_name, data, src_path_str = args
    src_path = Path(src_path_str) if src_path_str else None
    ssp = _WORKER_SSP
    if ssp is None:
        worker_init()
        ssp = _WORKER_SSP

    # Special gates (custom logic, not in standard registry)
    if gate_name == 'delta_pp':
        # Run bha_delta preprocessor + LZMA2 encode of result
        from .bha_delta import try_column_delta
        from black_hole_archiver import _build_file_lzma_fallback_archive
        delta_bytes = try_column_delta(data)
        if delta_bytes is not None:
            arc = _build_file_lzma_fallback_archive(delta_bytes)
            return (gate_name, len(arc), arc)
        return None

    if gate_name == 'lzma_fallback':
        from black_hole_archiver import _build_file_lzma_fallback_archive
        arc = _build_file_lzma_fallback_archive(data)
        return (gate_name, len(arc), arc)

    if gate_name == 'ssp_fallback':
        arc, _stats = ssp.encode_data(data, None, 1, r=1, block_bits=32, allow_ssp=False)
        if ssp.decode_data(arc, None) == data:
            return (gate_name, len(arc), arc)
        return None

    # Brotli gates: bypass ssp pipeline entirely. Round-trip is
    # brotli.compress -> brotli.decompress (no BHA envelope). Best on
    # small (<=64 KB) web/structured-text files where the BHA envelope
    # overhead (~370-700 B) eats the brotli ratio win. See
    # BHA_VS_BROTLI.md for the baseline that motivated this gate.
    if gate_name in ('brotli_q11', 'brotli_q6'):
        try:
            from .bha_codec_backends import (
                is_available as _brotli_available,
                quality_for, brotli_compress, brotli_decompress,
            )
        except Exception:
            return None
        if not _brotli_available():
            return None
        q = quality_for(gate_name)
        if q is None:
            return None
        try:
            arc = brotli_compress(data, quality=q)
            decoded = brotli_decompress(arc)
        except Exception:
            return None
        if decoded != data:
            return None
        return (gate_name, len(arc), arc)

    if gate_name == 'structured':
        from black_hole_archiver import (
            _structured_transform_file, _decode_line_delta,
            _build_runtime_lzma_archive, _build_file_structured_archive,
        )
        mode, transformed = _structured_transform_file(
            src_path, data, single_file=True, base_rt_guard=False)
        if mode == 2:  # DIR_STRUCT_MODE_LINE_DELTA
            arc = _build_runtime_lzma_archive(transformed)
            if _decode_line_delta(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_structured_archive(arc)),
                        _build_file_structured_archive(arc))
        return None

    # v10 pp gates: round-trip safe preprocessors with custom sidecar logic
    if gate_name in ('pp_dedup_substring', 'pp_bcj_x86', 'pp_zero_extend'):
        from black_hole_archiver import (
            _build_runtime_lzma_archive,
        )
        from .bha_v10_pp_safe import (
            pp_dedup_substring_safe, decode_dedup_substring,
            pp_bcj_x86_safe, decode_bcj_x86,
            pp_zero_extend_safe,
        )
        if gate_name == 'pp_dedup_substring':
            preprocessed, sidecar = pp_dedup_substring_safe(data)
        elif gate_name == 'pp_bcj_x86':
            preprocessed, sidecar = pp_bcj_x86_safe(data)
        else:  # pp_zero_extend
            preprocessed, sidecar = pp_zero_extend_safe(data)
        # Zero-extend has no decoder yet — gate disabled
        if gate_name == 'pp_zero_extend':
            return None
        if not sidecar or sidecar == b'\x00\x00\x00\x00':
            return None  # No pattern found
        arc = _build_runtime_lzma_archive(preprocessed)
        # Layout: [arc][u32 LE sidecar_len][sidecar]
        sidecar_blob = len(sidecar).to_bytes(4, 'little') + sidecar
        full_arc = arc + sidecar_blob
        # Round-trip verification
        sidecar_len_actual = int.from_bytes(
            full_arc[len(arc):len(arc) + 4], 'little'
        )
        body_actual = arc
        sidecar_actual = full_arc[len(arc) + 4:len(arc) + 4 + sidecar_len_actual]
        decoded_body = ssp.decode_data(body_actual, None)
        if gate_name == 'pp_dedup_substring':
            reconstructed = decode_dedup_substring(decoded_body, sidecar_actual)
        else:  # pp_bcj_x86
            reconstructed = decode_bcj_x86(decoded_body, sidecar_actual)
        if reconstructed == data:
            return (gate_name, len(full_arc), full_arc)
        return None

    # Standard 14 BHA codec gates — dispatch via registry
    from .bha_gates import DEFAULT_REGISTRY, ensure_registered
    ensure_registered()
    if not DEFAULT_REGISTRY.has(gate_name):
        return None
    result = DEFAULT_REGISTRY.run(gate_name, data, src_path, ssp)
    if result is None:
        return None
    size, archive = result
    return (gate_name, size, archive)


def bha_parallel_compress(
    data: bytes,
    src_path: Optional[Path] = None,
    max_workers: Optional[int] = None,
    baseline: Optional[bytes] = None,
) -> Tuple[bytes, dict]:
    """ProcessPoolExecutor-based parallel orchestrator with adaptive
    threshold tuning.

    Returns: (best_arc, meta_dict) where meta contains
        'method': 'parallel' or 'fallback_sequential' or
                 'fallback_sequential_csv' or 'csv_1w'
        'elapsed_s': float,
        'best_gate': str,
        'best_size': int,
        'n_gates_succeeded': int,
        'gates_tried': list of str,
        'selected_n_workers': int (workers actually used, may be 0),
        'is_csv_like': bool (whether file was detected as CSV-like).

    Adaptive strategy (see _select_parallel_strategy):
    - < 200KB: skip parallel path entirely
    - CSV-like + <500KB: 1 worker (low overhead, delta_pp wins)
    - CSV-like + 500KB-2MB: 2 workers
    - CSV-like + >2MB: up to 4 workers
    - Non-CSV + <2MB: skip parallel
    - Non-CSV + 2-10MB: 2 workers
    - Non-CSV + 10-50MB: 4 workers
    - Non-CSV + >50MB: 4-8 workers
    """
    # Auto-select worker count if caller did not pass an override
    if max_workers is None:
        max_workers = _select_workers_for(data)
    t0 = time.perf_counter()
    is_csv = _is_csv_like(data)
    meta = {
        'method': 'parallel',
        'max_workers': max_workers,
        'selected_n_workers': max_workers,
        'is_csv_like': is_csv,
        'elapsed_s': 0.0,
        'best_gate': None,
        'best_size': 0,
        'n_gates_succeeded': 0,
        'gates_tried': [],
    }

    # Adaptive threshold: selected_n_workers was set by _select_workers_for.
    # If 0 -> skip the pool entirely and use sequential fallback.
    if max_workers == 0 or len(data) < PARALLEL_MIN_SIZE:
        meta['method'] = 'below_threshold_sequential_fallback'
        if baseline is not None:
            meta['best_size'] = len(baseline)
            meta['best_gate'] = 'baseline'
            meta['elapsed_s'] = time.perf_counter() - t0
            return baseline, meta
        # Fall through: at least produce a fallback archive
        from black_hole_archiver import _build_file_lzma_fallback_archive
        arc = _build_file_lzma_fallback_archive(data)
        meta['best_gate'] = 'lzma_fallback'
        meta['best_size'] = len(arc)
        meta['elapsed_s'] = time.perf_counter() - t0
        return arc, meta

    src_path_str = str(src_path) if src_path is not None else None
    # Use v11 recommender to prioritize gates (highest-priority first).
    # Falls back to all gates if v11 rules not loaded.
    use_v11 = os.environ.get('BHA_USE_V11', '1') != '0'
    v11_only = os.environ.get('BHA_V11_ONLY', '0') == '1'
    if use_v11:
        try:
            from .bha_recommender_v11 import recommend as v11_recommend, lzma_preset_for as v11_preset
            file_name = src_path.name if src_path else 'unknown.dat'
            # Use larger k if v11_only mode
            k = 17 if v11_only else 5
            priority = v11_recommend(file_name, len(data), k=k)
            meta['v11_priority'] = priority
            meta['v11_lzma_preset'] = v11_preset(file_name, len(data))
            meta['v11_only_mode'] = v11_only
        except Exception:
            priority = None
            meta['v11_priority'] = None
            meta['v11_lzma_preset'] = None
            meta['v11_only_mode'] = False
    else:
        priority = None
        meta['v11_priority'] = None
        meta['v11_lzma_preset'] = None
        meta['v11_only_mode'] = False

    all_gates = [
        'delta_pp',
        'quoted_csv', 'telemetry_csv', 'sparse_pattern', 'dense_sparse',
        'mixed_formula', 'sparse_col', 'tabular_col', 'record_transpose',
        'vartrans', 'line_norm', 'json_array', 'markdown_table', 'css_struct',
        'pp_dedup_substring', 'pp_bcj_x86', 'pp_zero_extend',
        'brotli_q11', 'brotli_q6',
    ]
    if priority:
        if v11_only:
            # v11 decides which gates to run (subset of all)
            gates = list(priority)
        else:
            # Run v11-prioritized gates first, then fill with remaining
            seen = set(priority)
            gates = list(priority) + [g for g in all_gates if g not in seen]
    else:
        gates = all_gates
    args_list = [(g, data, src_path_str) for g in gates]
    candidates = []
    if baseline is not None:
        candidates.append(('baseline', len(baseline), baseline))
    else:
        # No baseline means caller wants pure parallel result
        # We add lzma_fallback as the guaranteed-correct finalizer
        pass

    try:
        with ProcessPoolExecutor(max_workers=max_workers, initializer=worker_init) as ex:
            futures = {ex.submit(worker_gate, a): a[0] for a in args_list}
            for fut in as_completed(futures):
                name = futures[fut]
                meta['gates_tried'].append(name)
                try:
                    res = fut.result()
                    if res is not None:
                        candidates.append(res)
                        meta['n_gates_succeeded'] += 1
                except Exception as e:
                    # Worker exception - skip this gate
                    pass
    except Exception as e:
        # Pool failed - fall back to sequential
        meta['method'] = 'pool_failed_sequential'
        if baseline is not None:
            meta['best_size'] = len(baseline)
            meta['best_gate'] = 'baseline'
            meta['elapsed_s'] = time.perf_counter() - t0
            return baseline, meta
        raise

    # Add ssp_fallback and lzma_fallback to candidates (these need
    # sequential, can't be parallelized usefully)
    try:
        from black_hole_archiver import _build_file_lzma_fallback_archive
        # v11: if recommender says preset 9, use EXTREME
        if use_v11 and meta.get('v11_lzma_preset') == 9:
            import lzma as _lz
            from black_hole_archiver import _build_runtime_lzma_archive
            # preset 9 EXTREME requires building directly
            best_preset = _lz.compress(
                data, format=_lz.FORMAT_RAW,
                filters=[{"id": _lz.FILTER_LZMA2, "preset": 9 | _lz.PRESET_EXTREME}]
            )
            from black_hole_archiver import uleb_encode
            out_arr = bytearray(b'BHST1')
            out_arr.extend(uleb_encode(len(data)))
            out_arr.extend(uleb_encode(0))
            out_arr.extend(len(best_preset).to_bytes(4, 'little'))
            out_arr.extend(best_preset)
            candidates.append(('lzma_fallback_v11preset9', len(out_arr), bytes(out_arr)))
        ssp_arc = _build_file_lzma_fallback_archive(data)
        candidates.append(('lzma_fallback', len(ssp_arc), ssp_arc))
    except Exception:
        pass

    # Pick smallest
    if not candidates:
        # Should not happen
        from black_hole_archiver import _build_file_lzma_fallback_archive
        arc = _build_file_lzma_fallback_archive(data)
        candidates.append(('lzma_fallback_emergency', len(arc), arc))

    candidates.sort(key=lambda c: c[1])
    name, size, arc = candidates[0]
    meta['best_gate'] = name
    meta['best_size'] = size
    meta['elapsed_s'] = time.perf_counter() - t0
    return arc, meta


def _cli_orchestrator(argv=None) -> int:
    """CLI entry point for bha-orchestrate console script.

    Runs the parallel orchestrator on one or more files, prints per-file
    results. Honors BHA_USE_V11 / BHA_V11_ONLY env vars (see module docs).
    """
    import argparse
    if argv is None:
        argv = sys.argv[1:]
    ap = argparse.ArgumentParser(
        prog="bha-orchestrate",
        description="Parallel BHA orchestrator with v11 recommender.",
    )
    ap.add_argument("files", nargs="+", type=Path,
                    help="Files to compress in parallel.")
    ap.add_argument("--max-workers", type=int, default=None,
                    help="Override worker count (default: auto from data size).")
    args = ap.parse_args(argv)

    # Required for Windows multiprocessing spawn
    mp.freeze_support()

    total_in = 0
    total_par = 0
    n = 0
    for path_str in args.files:
        path = Path(path_str)
        if not path.exists():
            print(f"skip {path}: missing", file=sys.stderr)
            continue
        data = path.read_bytes()
        import bha_core.bha as bha
        t0 = time.perf_counter()
        seq_arc, _, seq_meta = bha.bha_compress(data, src_path=path, total_timeout_s=120.0)
        seq_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        par_arc, par_meta = bha_parallel_compress(data, src_path=path, baseline=seq_arc,
                                                 max_workers=args.max_workers)
        par_ms = (time.perf_counter() - t0) * 1000

        total_in += len(data)
        total_par += len(par_arc)
        n += 1
        print(f"{path.name:50s}  in={len(data):>9d}  "
              f"seq={len(seq_arc):>6d} ({seq_ms:>7.0f}ms)  "
              f"par={len(par_arc):>6d} ({par_ms:>7.0f}ms)  "
              f"best={par_meta['best_gate']:>22s}")
    print(f"\n{n} files  in={total_in}  par={total_par}  "
          f"par_best_ratio={100*total_par/total_in:.2f}%")
    return 0


if __name__ == '__main__':
    # Required for Windows multiprocessing spawn (per
    # memory-spillover-completed-tracks.md line 33)
    mp.freeze_support()

    # ----- Unit tests for adaptive threshold tuning -----
    print('=== bha_parallel unit tests ===')

    # _is_csv_like: positive case
    csv_data = b'idx,val,score\n' + b'1,2,3\n' * 100
    assert _is_csv_like(csv_data), 'plain CSV should be detected'
    print('  _is_csv_like(csv)  OK')

    # _is_csv_like: negative cases
    assert not _is_csv_like(b'<!DOCTYPE html><html>'), 'HTML should not be CSV'
    print('  _is_csv_like(html) OK')

    assert not _is_csv_like(b''), 'empty should not be CSV'
    print('  _is_csv_like(empty) OK')

    assert not _is_csv_like(b'\xff\xfe\xfd'), 'non-ASCII should not be CSV'
    print('  _is_csv_like(non-ASCII) OK')

    # _select_parallel_strategy: matrix (uses power-of-2 quantized thresholds)
    cases = [
        # (size, is_csv, expected_workers, desc)
        (1 << 16,    False, 0, '<64KB non-CSV -> 0'),
        (1 << 18,    False, 0, '<256KB non-CSV -> 0'),
        (1 << 20,    False, 0, '1MB non-CSV -> 0'),
        (1 << 21,    False, 2, '2MB non-CSV -> 2'),
        (1 << 23,    False, 2, '8MB non-CSV -> 2'),
        (1 << 25,    False, 4, '32MB non-CSV -> 4 (boundary)'),
        (1 << 26,    False, 4, '64MB non-CSV -> 4'),
        (1 << 27,    False, 4, '128MB non-CSV -> 4'),
        (1 << 16,    True,  0, '<64KB CSV -> 0'),
        (1 << 19,    True,  1, '512KB CSV -> 1'),
        (1 << 20,    True,  2, '1MB CSV -> 2'),
        (1 << 22,    True,  4, '4MB CSV -> 4'),
    ]
    for size, is_csv, want, desc in cases:
        got = _select_parallel_strategy(size, is_csv, n_workers_max=8)
        assert got == want, f'{desc}: got {got}, want {want}'
        print(f'  {desc:30s} OK ({got})')

    print('All unit tests passed.\n')

    # ----- CLI benchmark mode -----
    import sys
    if len(sys.argv) < 2:
        print('Usage: bha_parallel.py <file> [file...]', file=sys.stderr)
        sys.exit(1)

    total_in = 0
    total_par = 0
    total_seq = 0
    n = 0
    for path_str in sys.argv[1:]:
        path = Path(path_str)
        data = path.read_bytes()
        # Get baseline (sequential bha_compress via bha.py).
        # Use absolute import to avoid sys.path mutation.
        import bha_core.bha as bha  # type: ignore
        t0 = time.perf_counter()
        seq_arc, _stats, seq_meta = bha.bha_compress(data, src_path=path, total_timeout_s=120.0)
        seq_ms = (time.perf_counter() - t0) * 1000
        # Run parallel
        t0 = time.perf_counter()
        par_arc, par_meta = bha_parallel_compress(data, src_path=path, baseline=seq_arc)
        par_ms = (time.perf_counter() - t0) * 1000

        total_in += len(data)
        total_par += len(par_arc)
        total_seq += len(seq_arc)
        n += 1
        print(f'{path.name:50s}  in={len(data):>9d}  '
              f'seq={len(seq_arc):>6d} ({seq_ms:>7.0f}ms)  '
              f'par={len(par_arc):>6d} ({par_ms:>7.0f}ms)  '
              f'best={par_meta["best_gate"]}')
    print(f'\n{n} files  in={total_in}  seq={total_seq}  par={total_par}  '
          f'speedup={total_seq/max(total_par,1):.2f}x size  '
          f'par_best_ratio={100*total_par/total_in:.2f}%')
