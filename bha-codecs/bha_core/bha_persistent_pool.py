"""bha_persistent_pool: long-lived ProcessPoolExecutor for BHA orchestrator.

Problem (from bha_parallel.py README section 11.4):
- Per-call ProcessPoolExecutor pays ~200ms spawn cost per worker
- HTML 1.5MB: spawn 8 workers × 200ms = 1.6s overhead on top of 100ms encode
- Speedup losses on HTML: 0.40x (parallel slower than sequential)

Solution: keep a singleton pool alive across compress() calls.
- Lazy init on first bha_parallel_compress()
- Workers preload ssp._RUNTIME + bha_delta once and keep them
- Idle timeout: if no calls for IDLE_TIMEOUT_S, shut down the pool
- Thread-safe init via threading.Lock

Trade-offs:
- Persistent pool holds ~300MB RSS (8 workers × ~30MB each)
- On Windows: spawn-only, so first call still pays startup
- Subsequent calls amortize startup to ~0ms

API:
- bha_parallel_compress(data, src_path, baseline, max_workers=None) -> (bytes, meta)
  Same signature as bha_parallel.bha_parallel_compress
- shutdown_pool() for explicit cleanup (tests, atexit)
"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple

# When run standalone, ensure cross-imports from bha_core resolve.
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

# Reuse adaptive threshold tuning from bha_parallel.
# If bha_parallel is not importable (e.g. older checkout), fall back
# to the same logic inline.
try:
    from .bha_parallel import _is_csv_like, _select_parallel_strategy
    _HAS_BHA_PARALLEL = True
except ImportError:
    _HAS_BHA_PARALLEL = False

PARALLEL_MIN_SIZE = 1 << 19  # 512KB — matches bha_parallel (1 << 19)
DEFAULT_WORKERS = 8
IDLE_TIMEOUT_S = 60.0  # shutdown pool after 60s of inactivity


# ---------------------------------------------------------------------------
# Worker init: imported by the worker subprocess on startup
# ---------------------------------------------------------------------------
def worker_init() -> None:
    """Called once per worker process when the pool starts.

    Loads ssp._RUNTIME and bha_delta so each gate call reuses them.
    Mirrors bha_parallel.worker_init but exposed at module level so
    ProcessPoolExecutor(initializer=...) can find it without importing
    the parent module (avoids circular import).
    """
    global _WORKER_SSP, _WORKER_BHA_DELTA
    if _WORKER_SSP is not None:
        return
    from black_hole_archiver import _load_runtime
    _WORKER_SSP = _load_runtime()
    # Use absolute import so subprocess spawn can find bha_core.bha_delta
    import bha_core.bha_delta as bha_delta  # type: ignore
    _WORKER_BHA_DELTA = bha_delta


_WORKER_SSP = None
_WORKER_BHA_DELTA = None


# ---------------------------------------------------------------------------
# Adaptive threshold (inline copy of bha_parallel if unavailable)
# ---------------------------------------------------------------------------
def _is_csv_like(data: bytes) -> bool:
    sample = data[:1024]
    if not sample:
        return False
    head = sample.split(b'\n', 1)[0]
    if not head or len(head) > 256:
        return False
    if any(b > 127 for b in head):
        return False
    if b',' not in head and b'\t' not in head and b';' not in head:
        return False
    return b'\n' in sample[1:]


def _select_parallel_strategy(size: int, is_csv_like: bool, n_workers_max: int = DEFAULT_WORKERS) -> int:
    if size < 200_000:
        return 0
    if is_csv_like:
        if size < 500_000:
            return 1
        if size < 2_000_000:
            return 2
        return min(4, n_workers_max)
    if size < 2_000_000:
        return 0
    if size < 10_000_000:
        return 2
    if size < 50_000_000:
        return 4
    return min(n_workers_max, 8)


def _select_workers_for(data: bytes) -> int:
    return _select_parallel_strategy(len(data), _is_csv_like(data), DEFAULT_WORKERS)


# ---------------------------------------------------------------------------
# Singleton pool: lazy-init, idle-shutdown, thread-safe
# ---------------------------------------------------------------------------
class _PoolHolder:
    """Process-singleton holder for a long-lived BHA worker pool."""

    def __init__(self):
        self._lock = threading.Lock()
        self._executor: Optional[ProcessPoolExecutor] = None
        self._workers: int = 0
        self._last_used: float = 0.0

    def get(self, n_workers: int) -> ProcessPoolExecutor:
        """Return the singleton pool, creating it if needed.

        If a stale pool with fewer workers exists, shut it down and
        create a fresh one. Otherwise reuse.
        """
        with self._lock:
            now = time.perf_counter()
            if self._executor is not None:
                # Shutdown if idle for too long
                if now - self._last_used > IDLE_TIMEOUT_S:
                    self._shutdown_unlocked()
            if self._executor is None:
                self._executor = ProcessPoolExecutor(
                    max_workers=n_workers,
                    initializer=worker_init,
                )
                self._workers = n_workers
            elif self._workers < n_workers:
                # Need more workers — shutdown and recreate
                # (ProcessPoolExecutor cannot resize dynamically)
                self._shutdown_unlocked()
                self._executor = ProcessPoolExecutor(
                    max_workers=n_workers,
                    initializer=worker_init,
                )
                self._workers = n_workers
            self._last_used = now
            return self._executor

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_unlocked()

    def _shutdown_unlocked(self) -> None:
        if self._executor is not None:
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._executor = None
            self._workers = 0
            self._last_used = 0.0

    @property
    def is_active(self) -> bool:
        return self._executor is not None


_HOLDER = _PoolHolder()


def shutdown_pool() -> None:
    """Shutdown the persistent pool (call from atexit or tests)."""
    _HOLDER.shutdown()


# ---------------------------------------------------------------------------
# Worker gate (reused from bha_parallel via process-spawn)
# ---------------------------------------------------------------------------
# Imported AFTER _HOLDER is defined so the worker can find worker_init
# in this module's namespace via __main__ on Windows spawn.
from .bha_parallel import worker_gate, _is_csv_like as _bp_is_csv  # noqa: E402

# Sanity check: make sure worker_gate imports worker_init from this module.
# On Windows spawn, the worker process re-imports __main__ which imports
# this module, which makes worker_init available.


# ---------------------------------------------------------------------------
# Public API: drop-in replacement for bha_parallel.bha_parallel_compress
# ---------------------------------------------------------------------------
def bha_parallel_compress(
    data: bytes,
    src_path: Optional[Path] = None,
    max_workers: Optional[int] = None,
    baseline: Optional[bytes] = None,
) -> Tuple[bytes, dict]:
    """Persistent-pool BHA orchestrator.

    Returns: (best_arc, meta_dict) — same shape as bha_parallel.bha_parallel_compress.
    """
    if max_workers is None:
        max_workers = _select_workers_for(data)
    t0 = time.perf_counter()
    is_csv = _is_csv_like(data)
    meta = {
        'method': 'parallel_persistent',
        'max_workers': max_workers,
        'selected_n_workers': max_workers,
        'is_csv_like': is_csv,
        'elapsed_s': 0.0,
        'best_gate': None,
        'best_size': 0,
        'n_gates_succeeded': 0,
        'gates_tried': [],
        'pool_reused': _HOLDER.is_active,
    }

    # Below threshold — skip parallel path
    if max_workers == 0 or len(data) < PARALLEL_MIN_SIZE:
        meta['method'] = 'below_threshold_sequential_fallback'
        if baseline is not None:
            meta['best_size'] = len(baseline)
            meta['best_gate'] = 'baseline'
            meta['elapsed_s'] = time.perf_counter() - t0
            return baseline, meta
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
        'pp_dedup_substring', 'pp_bcj_x86', 'pp_zero_extend',
    ]
    args_list = [(g, data, src_path_str) for g in gates]
    candidates = []
    if baseline is not None:
        candidates.append(('baseline', len(baseline), baseline))

    pool_init_ms = 0.0
    try:
        pool_t0 = time.perf_counter()
        executor = _HOLDER.get(max_workers)
        pool_init_ms = (time.perf_counter() - pool_t0) * 1000.0
        futures = {executor.submit(worker_gate, a): a[0] for a in args_list}
        for fut in as_completed(futures):
            name = futures[fut]
            meta['gates_tried'].append(name)
            try:
                res = fut.result()
                if res is not None:
                    candidates.append(res)
                    meta['n_gates_succeeded'] += 1
            except Exception:
                pass
    except Exception as e:
        # Pool may be BrokenProcessPool (workers died). Recreate once and retry.
        err_name = type(e).__name__
        if 'Broken' in err_name or 'broken' in str(e).lower():
            _HOLDER.shutdown()
            try:
                pool_t0 = time.perf_counter()
                executor = _HOLDER.get(max_workers)
                pool_init_ms = (time.perf_counter() - pool_t0) * 1000.0
                futures = {executor.submit(worker_gate, a): a[0] for a in args_list}
                for fut in as_completed(futures):
                    name = futures[fut]
                    meta['gates_tried'].append(name)
                    try:
                        res = fut.result()
                        if res is not None:
                            candidates.append(res)
                            meta['n_gates_succeeded'] += 1
                    except Exception:
                        pass
            except Exception:
                meta['method'] = 'pool_failed_sequential'
                if baseline is not None:
                    meta['best_size'] = len(baseline)
                    meta['best_gate'] = 'baseline'
                    meta['elapsed_s'] = time.perf_counter() - t0
                    return baseline, meta
                raise
        else:
            meta['method'] = 'pool_failed_sequential'
            if baseline is not None:
                meta['best_size'] = len(baseline)
                meta['best_gate'] = 'baseline'
                meta['elapsed_s'] = time.perf_counter() - t0
                return baseline, meta
            raise

    # Sequential fallbacks (cheap, not worth parallelizing)
    try:
        from black_hole_archiver import _build_file_lzma_fallback_archive
        ssp_arc = _build_file_lzma_fallback_archive(data)
        candidates.append(('lzma_fallback', len(ssp_arc), ssp_arc))
    except Exception:
        pass

    if not candidates:
        from black_hole_archiver import _build_file_lzma_fallback_archive
        arc = _build_file_lzma_fallback_archive(data)
        candidates.append(('lzma_fallback_emergency', len(arc), arc))

    candidates.sort(key=lambda c: c[1])
    name, size, arc = candidates[0]
    meta['best_gate'] = name
    meta['best_size'] = size
    meta['pool_init_ms'] = round(pool_init_ms, 2)
    meta['elapsed_s'] = time.perf_counter() - t0
    return arc, meta


# ---------------------------------------------------------------------------
# Entry point + minimal unit tests
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    mp.freeze_support()

    print('=== bha_persistent_pool unit tests ===')

    # Threshold tests
    cases = [
        (50_000, False, 0),
        (1_000_000, False, 0),
        (2_000_000, False, 2),
        (10_000_000, False, 4),
        (50_000_000, False, 8),
        (300_000, True, 1),
        (1_000_000, True, 2),
        (3_000_000, True, 4),
    ]
    for size, is_csv, want in cases:
        got = _select_parallel_strategy(size, is_csv, n_workers_max=8)
        assert got == want, f'{size}/{is_csv}: got {got}, want {want}'
        print(f'  strategy({size}, {is_csv}) = {got} OK')

    # _is_csv_like basic
    assert _is_csv_like(b'a,b,c\n1,2,3\n')
    assert not _is_csv_like(b'<!DOCTYPE html>')
    assert not _is_csv_like(b'')
    print('  _is_csv_like OK')

    # Holder init/shutdown
    h = _PoolHolder()
    assert not h.is_active
    ex = h.get(2)
    assert h.is_active
    assert h._workers == 2
    # Reuse — should be same executor
    ex2 = h.get(2)
    assert ex is ex2, 'should reuse the same pool'
    print('  holder reuse OK')
    h.shutdown()
    assert not h.is_active

    # Resize
    h = _PoolHolder()
    h.get(2)
    ex_big = h.get(4)
    assert h._workers == 4
    print('  holder resize OK')
    h.shutdown()

    print('\nAll unit tests passed.')

    # If a path is given, run a real benchmark
    import sys
    if len(sys.argv) >= 2:
        path = Path(sys.argv[1])
        if path.exists():
            data = path.read_bytes()
            print(f'\n=== benchmark on {path.name} ({len(data)} bytes) ===')
            # First call: pays spawn cost
            t = time.perf_counter()
            arc1, meta1 = bha_parallel_compress(data, src_path=path)
            first_ms = (time.perf_counter() - t) * 1000
            print(f'  1st call: out={len(arc1)} best={meta1["best_gate"]} '
                  f'pool_init_ms={meta1.get("pool_init_ms", "?")} '
                  f'total={first_ms:.0f}ms '
                  f'pool_reused={meta1["pool_reused"]}')
            # Second call: pool is warm
            t = time.perf_counter()
            arc2, meta2 = bha_parallel_compress(data, src_path=path)
            second_ms = (time.perf_counter() - t) * 1000
            print(f'  2nd call: out={len(arc2)} best={meta2["best_gate"]} '
                  f'pool_init_ms={meta2.get("pool_init_ms", "?")} '
                  f'total={second_ms:.0f}ms '
                  f'pool_reused={meta2["pool_reused"]} '
                  f'speedup={first_ms/second_ms:.2f}x')
            shutdown_pool()
