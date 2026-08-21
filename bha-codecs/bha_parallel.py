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

sys.path.insert(0, r'D:\\4\\bha-codecs')
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

# Threshold: file size below which multiprocessing overhead exceeds gain
# Based on memory-historical-factory-cleanup line 10:
# "per-worker re-import overhead (30ms × N) eats the win at N<=11"
# For BHA LZMA2 encoding at ~500MB/s, 500KB = ~1ms per worker,
# 8 workers = 8ms total work + 200ms spawn = no win.
# 1MB+ = 2ms+ work, win.
PARALLEL_MIN_SIZE = 500 * 1024  # 500KB
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
    if size < 200_000:  # < 200KB
        return 0
    # 2. CSV path: delta_pp can win even on small files
    if is_csv_like:
        if size < 500_000:  # 200-500KB CSV: 1 worker (low overhead)
            return 1
        if size < 2_000_000:  # 500KB-2MB: 2 workers
            return 2
        return min(4, n_workers_max)
    # 3. Non-CSV path: must amortize worker startup
    if size < 2_000_000:    # < 2MB: 0 or 1 worker
        return 0
    if size < 10_000_000:   # 2-10MB: 2 workers
        return 2
    if size < 50_000_000:   # 10-50MB: 4 workers
        return 4
    return min(n_workers_max, 8)  # 50MB+: 8 workers


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
    # Pre-load bha_delta for column detection
    sys.path.insert(0, r'D:\\4\\bha-codecs')
    import bha_delta
    _WORKER_BHA_DELTA = bha_delta


def worker_gate(args: Tuple[str, bytes, Optional[str]]) -> Optional[Tuple[str, int, bytes]]:
    """Run a single gate or transformation.

    args: (gate_name, data, src_path_str_or_None)
    Returns: (gate_name, encoded_size, encoded_bytes) or None
    """
    global _WORKER_SSP
    gate_name, data, src_path_str = args
    src_path = Path(src_path_str) if src_path_str else None
    ssp = _WORKER_SSP
    if ssp is None:
        worker_init()
        ssp = _WORKER_SSP

    from black_hole_archiver import (
        _quoted_csv_safety_risk, _quoted_csv_delimiter, _quoted_csv_gate,
        _encode_quoted_csv, _decode_quoted_csv, _build_file_quoted_csv_archive,
        _telemetry_csv_gate, _encode_telemetry_csv, _decode_telemetry_csv,
        _build_file_telemetry_csv_archive,
        _sparse_pattern_delimiter, _encode_sparse_pattern, _decode_sparse_pattern,
        _build_file_sparse_pattern_archive,
        _dense_sparse_delimiter, _encode_dense_sparse, _decode_dense_sparse,
        _build_file_dense_sparse_archive,
        _mixed_formula_gate, _encode_mixed_formula, _decode_mixed_formula,
        _build_file_mixed_formula_archive,
        _build_runtime_lzma_archive, _build_file_lzma_fallback_archive,
        _sparse_col_gate, _encode_sparse_col, _decode_sparse_col,
        _build_file_sparse_col_archive,
        _tabular_col_gate, _encode_tabular_col, _decode_tabular_col,
        _build_file_tabular_col_archive,
        _record_transpose_gate, _encode_record_transpose, _decode_record_transpose,
        _build_file_record_transpose_archive,
        _vartrans_gate, _encode_vartrans, _decode_vartrans, _build_file_vartrans_archive,
        _line_norm_gate, _encode_line_norm, _decode_line_norm,
        _build_file_line_norm_archive,
        _json_array_gate, _encode_json_array, _decode_json_array,
        _build_file_json_array_archive,
        _markdown_table_gate, _encode_markdown_table, _decode_markdown_table,
        _build_file_markdown_table_archive,
        _css_struct_gate, _encode_css_struct, _decode_css_struct,
        _build_file_css_struct_archive,
        _structured_transform_file, _decode_line_delta, _build_file_structured_archive,
    )

    try:
        if gate_name == 'delta_pp':
            # Run bha_delta preprocessor + LZMA2 encode of result
            from bha_delta import try_column_delta
            delta_bytes = try_column_delta(data)
            if delta_bytes is not None:
                # Use _build_file_lzma_fallback_archive (format=XZ
                # handles large dict_size correctly). _build_runtime_lzma_archive
                # uses preset=6 which has dict_size clamped to 131072,
                # too small for data >128KB.
                arc = _build_file_lzma_fallback_archive(delta_bytes)
                return (gate_name, len(arc), arc)
            return None
        elif gate_name == 'lzma_fallback':
            arc = _build_file_lzma_fallback_archive(data)
            return (gate_name, len(arc), arc)
        elif gate_name == 'ssp_fallback':
            arc, _stats = ssp.encode_data(data, None, 1, r=1, block_bits=32, allow_ssp=False)
            if ssp.decode_data(arc, None) == data:
                return (gate_name, len(arc), arc)
        elif gate_name == 'quoted_csv':
            if not _quoted_csv_safety_risk(src_path, data):
                return None
            delim = _quoted_csv_delimiter(src_path)
            if delim is None or not _quoted_csv_gate(src_path, data):
                return None
            blob = _encode_quoted_csv(data, delim)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_quoted_csv(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_quoted_csv_archive(arc)), _build_file_quoted_csv_archive(arc))
        elif gate_name == 'telemetry_csv':
            if not _telemetry_csv_gate(data):
                return None
            blob = _encode_telemetry_csv(data)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_telemetry_csv(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_telemetry_csv_archive(arc)), _build_file_telemetry_csv_archive(arc))
        elif gate_name == 'sparse_pattern':
            delim = _sparse_pattern_delimiter(src_path, data)
            if delim is None:
                return None
            blob = _encode_sparse_pattern(data, delim)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_sparse_pattern(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_sparse_pattern_archive(arc)), _build_file_sparse_pattern_archive(arc))
        elif gate_name == 'dense_sparse':
            delim = _dense_sparse_delimiter(src_path, data)
            if delim is None:
                return None
            blob = _encode_dense_sparse(data, delim)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_dense_sparse(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_dense_sparse_archive(arc)), _build_file_dense_sparse_archive(arc))
        elif gate_name == 'mixed_formula':
            if not _mixed_formula_gate(src_path, data):
                return None
            blob = _encode_mixed_formula(data)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_mixed_formula(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_mixed_formula_archive(arc)), _build_file_mixed_formula_archive(arc))
        elif gate_name == 'sparse_col':
            delim = _sparse_col_gate(data)
            if delim is None:
                return None
            blob = _encode_sparse_col(data, delim)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_sparse_col(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_sparse_col_archive(arc)), _build_file_sparse_col_archive(arc))
        elif gate_name == 'tabular_col':
            delim = _tabular_col_gate(data)
            if delim is None:
                return None
            blob = _encode_tabular_col(data, delim)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_tabular_col(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_tabular_col_archive(arc)), _build_file_tabular_col_archive(arc))
        elif gate_name == 'record_transpose':
            shape = _record_transpose_gate(data)
            if shape is None:
                return None
            stride, rows, delim = shape
            blob = _encode_record_transpose(data, stride, rows, delim)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_record_transpose(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_record_transpose_archive(arc)), _build_file_record_transpose_archive(arc))
        elif gate_name == 'vartrans':
            shape = _record_transpose_gate(data)
            delim = _vartrans_gate(data, record_transpose_active=shape is not None)
            if delim is None:
                return None
            blob = _encode_vartrans(data, delim)
            arc, _stats = ssp.encode_data(blob, None, 1, r=1, block_bits=32, allow_ssp=False)
            if _decode_vartrans(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_vartrans_archive(arc)), _build_file_vartrans_archive(arc))
        elif gate_name == 'line_norm':
            if src_path is None or not _line_norm_gate(src_path, data):
                return None
            blob = _encode_line_norm(data)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_line_norm(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_line_norm_archive(arc)), _build_file_line_norm_archive(arc))
        elif gate_name == 'json_array':
            if src_path is None or not _json_array_gate(src_path, data):
                return None
            blob = _encode_json_array(data)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_json_array(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_json_array_archive(arc)), _build_file_json_array_archive(arc))
        elif gate_name == 'markdown_table':
            if src_path is None or not _markdown_table_gate(src_path, data):
                return None
            blob = _encode_markdown_table(data)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_markdown_table(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_markdown_table_archive(arc)), _build_file_markdown_table_archive(arc))
        elif gate_name == 'css_struct':
            if src_path is None or not _css_struct_gate(src_path, data):
                return None
            blob = _encode_css_struct(data)
            arc = _build_runtime_lzma_archive(blob)
            if _decode_css_struct(ssp.decode_data(arc, None)) == data:
                return (gate_name, len(_build_file_css_struct_archive(arc)), _build_file_css_struct_archive(arc))
        elif gate_name == 'structured':
            mode, transformed = _structured_transform_file(
                src_path, data, single_file=True, base_rt_guard=False)
            if mode == 2:  # DIR_STRUCT_MODE_LINE_DELTA = 2
                arc = _build_runtime_lzma_archive(transformed)
                if _decode_line_delta(ssp.decode_data(arc, None)) == data:
                    return (gate_name, len(_build_file_structured_archive(arc)), _build_file_structured_archive(arc))
        return None
    except Exception as e:
        # Log silently in worker; coordinator can still pick other results
        import sys
        import traceback
        print(f'worker_gate({gate_name}) failed: {e}', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None


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
    gates = [
        'delta_pp',
        'quoted_csv', 'telemetry_csv', 'sparse_pattern', 'dense_sparse',
        'mixed_formula', 'sparse_col', 'tabular_col', 'record_transpose',
        'vartrans', 'line_norm', 'json_array', 'markdown_table', 'css_struct',
    ]
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

    # _select_parallel_strategy: matrix
    cases = [
        # (size, is_csv, expected_workers, desc)
        (50_000,   False, 0, '<200KB non-CSV -> 0'),
        (200_000,  False, 0, '200KB non-CSV -> 0'),
        (1_000_000,False, 0, '1MB non-CSV -> 0'),
        (2_000_000,False, 2, '2MB non-CSV -> 2'),
        (10_000_000,False,4, '10MB non-CSV -> 4'),
        (50_000_000,False,8, '50MB non-CSV -> 8 (boundary)'),
        (60_000_000,False,8, '60MB non-CSV -> 8'),
        (100_000_000,False,8, '100MB non-CSV -> 8'),
        (50_000,   True,  0, '<200KB CSV -> 0'),
        (300_000,  True,  1, '300KB CSV -> 1'),
        (1_000_000,True,  2, '1MB CSV -> 2'),
        (3_000_000,True,  4, '3MB CSV -> 4'),
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
        # Get baseline (sequential bha_compress via bha.py)
        sys.path.insert(0, r'D:\\4\\bha-codecs')
        import bha
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
