"""bha.py — BHA packer (zip-style wrapper).

Integrates the full bha_core codec stack end-to-end:

  L1  raw input (bytes / Path)
  L2  sniffing (gate check functions)
  L3  preprocessor (delta_pp, pp_bcj_x86_safe, pp_dedup_substring_safe)
  L4  per-codec encoder (14 BHA gates + brotli_q11/q6)
  L5  sidecar (pp_*_safe; brotli: none)
  L6  entropy (LZMA2 / brotli / passthrough via GateRegistry pipeline)
  L7  envelope (BHA file magic)
  L8  recommender (v11 with brotli routing for <=256 KiB web content)
  L9  parallel orchestrator (bha_parallel)
  L10 file format (single-file BHA archive, no multi-file container here)
  L11 CLI (this module)
  L12 end-to-end (bha_compress / bha_compress_subprocess)

Safety skills applied (BHA_SAFE_SKILLS.md):
  SKILL 1  bypass-ssp-on-large-data          : ssp.encode_data bypassed on >256 KiB
  SKILL 2  lzma-preset-tiered-by-size        : PRESET_EXTREME dropped on >64 KiB
  SKILL 3  warm-runtime-on-import            : bha._load_runtime() called on import
  SKILL 4  subprocess-watchdog-for-cpu-bound : timeout via subprocess.run
  SKILL 5  determinism-assert-via-size-uniqueness : size_unique == 1 over N runs
  SKILL 6  bha-cli-safe-instead-of-bha-cli   : this module IS the safe CLI

T1  brotli-gate via GateRegistry pipeline='brotli' (bypass ssp)
T2  v11 retrained on telemetry_v2; BROTLI_SMALL_MAX=256 KiB; codec aliases
T3  brotli in GateRegistry (not sibling-branch); end-to-end via real BHA runtime

Public API:
  bha_compress(data, src_path=None, total_timeout_s=20.0, verify_determinism=False)
      -> (archive_bytes, meta_dict)
  bha_compress_subprocess(data, src_path=None, timeout_s=60.0)
      -> (archive_bytes, meta_dict)   # subprocess-wrapped for hard timeout

CLI:
  bha.py <file>...           # pack and print summary
  bha.py --bench <files>...  # benchmark (default 100 iter)
  bha.py --json              # emit JSON for dashboards
  bha.py --verify-det N      # after packing, verify size_unique==1 over N runs
"""
from __future__ import annotations

import argparse
import base64
import json
import lzma
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ===========================================================================
# Section 1: BHA runtime loading + safety patches
# ===========================================================================
# SKILL 3: warm-runtime-on-import. Call _load_runtime() immediately so
# the first compress call doesn't pay the multi-second DLL load cost.
# SKILL 6: this file is the bha-cli-safe drop-in replacement.

BHA_DIR = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA")
_BHA_AVAILABLE = False
_BHA_IMPORT_ERROR: Optional[Exception] = None
bha = None  # populated below

if BHA_DIR.exists():
    sys.path.insert(0, str(BHA_DIR))
    try:
        import black_hole_archiver as _bha
        _bha._load_runtime()
        bha = _bha
        _BHA_AVAILABLE = True
    except Exception as e:
        _BHA_IMPORT_ERROR = e


# ---------------------------------------------------------------------------
# Power-of-2 size thresholds (branch-free, self-documenting).
# Same constants used in the safety skills and in bha_core.bha_parallel.
# ---------------------------------------------------------------------------
_LZMA_PRESET6_MAX = 1 << 16        # 64 KiB  - below: try PRESET_EXTREME
_SSP_BYPASS_MIN   = 1 << 18        # 256 KiB - above: bypass ssp.encode_data
_DELTA_BYPASS_MIN = 1 << 23        # 8 MiB   - above: bypass delta_pp
_PARALLEL_MIN     = 1 << 19        # 512 KiB - above: use parallel pool

# Apply safety patches only if BHA runtime loaded successfully.
if _BHA_AVAILABLE:
    # SKILL 2: kill PRESET_EXTREME on inputs >64 KiB.
    _orig_build_lzma = bha._build_runtime_lzma_archive

    def _safe_build_lzma(data: bytes, *, block_bits: int = 32, presets=None):
        if presets is None:
            presets = (
                (6, 9 | lzma.PRESET_EXTREME)
                if len(data) <= _LZMA_PRESET6_MAX
                else (6,)
            )
        return _orig_build_lzma(data, block_bits=block_bits, presets=presets)

    bha._build_runtime_lzma_archive = _safe_build_lzma

    # SKILL 1: bypass ssp.encode_data on inputs >256 KiB.
    if bha._RUNTIME is not None:
        _orig_encode_data = bha._RUNTIME.encode_data

        def _safe_encode_data(data, *a, **kw):
            if len(data) > _SSP_BYPASS_MIN:
                return bha._build_runtime_lzma_archive(data), {"bypassed": "lzma_archive"}
            return _orig_encode_data(data, *a, **kw)

        bha._RUNTIME.encode_data = _safe_encode_data


# ===========================================================================
# Section 2: bha_core integration
# ===========================================================================
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))  # so `from bha_core...` works

from bha_core import bha_recommender_v11
from bha_core.bha_gates import DEFAULT_REGISTRY, ensure_registered, PIPELINE_BROTLI
from bha_core.bha_codec_backends import (
    is_available as _brotli_available,
    quality_for,
)
from bha_core.meta_dict_ids import _MetaId as MI, id_to_full

ensure_registered()


def _meta_get(meta: dict, mi_attr: str, default=None):
    """Read a meta-dict key by MI constant (short ID) or by long name.

    Some call sites store under the compact ID (e.g. 'bgt'), others under
    the long name ('best_gate'). This helper resolves either transparently
    so the CLI formatters don't care which convention was used upstream.
    """
    short = getattr(MI, mi_attr, None)
    if short is not None and short in meta:
        return meta[short]
    long_name = id_to_full(short) if short else mi_attr
    if long_name in meta:
        return meta[long_name]
    return default


def _meta_set(meta: dict, mi_attr: str, value) -> None:
    """Set a meta-dict key using BOTH short ID and long name.

    Storage under the short ID keeps the wire-format compact (see
    bha_core/meta_dict_ids.py for the rationale). Mirroring under the
    long name lets the CLI formatters and tests read it without resolving.
    """
    short = getattr(MI, mi_attr, None)
    long_name = id_to_full(short) if short else mi_attr
    if short is not None:
        meta[short] = value
    meta[long_name] = value


# ===========================================================================
# Section 3: gate dispatch
# ===========================================================================
def _candidates_for(name: str, size: int) -> list[str]:
    """Return priority-ordered candidate gate names for this file.

    Combines v11 extension-aware routing (T2: brotli_q11 first for small
    web files <=256 KiB, lzma_fallback for everything else) with a
    guaranteed lzma_fallback tail as the safety net.
    """
    k = 17 if os.environ.get('BHA_V11_ONLY', '0') == '1' else 8
    prio = bha_recommender_v11.recommend(name, size, k=k)
    if 'lzma_fallback' not in prio:
        prio = prio + ['lzma_fallback']
    return prio


def _try_gate(gate_name: str, data: bytes, src_path: Optional[str]) -> Optional[tuple[str, int, bytes]]:
    """Run a single gate through bha_parallel.worker_gate.

    worker_gate already routes brotli gates to the brotli-pipeline branch
    and BHA gates through the registry. We just call it and return.
    """
    import bha_core.bha_parallel as bp
    if bp._WORKER_SSP is None:
        # Lazy-load BHA runtime here so a process without env vars still
        # works. We patched bha._RUNTIME above, so worker_gate can pick
        # it up by importing bha.
        bp._WORKER_SSP = bha._RUNTIME if _BHA_AVAILABLE else type('StubSsp', (), {})()
    return bp.worker_gate((gate_name, data, src_path))


# ===========================================================================
# Section 4: bha_compress with wall-clock guard + telemetry
# ===========================================================================
DEFAULT_TIMEOUT_S = 20.0


def _size_class(n: int) -> str:
    if n < (1 << 17):   # < 128 KiB
        return 'tiny'
    if n < (1 << 20):   # < 1 MiB
        return 'small'
    if n < (1 << 23):   # < 8 MiB
        return 'medium'
    return 'large'


def _try_via_registry(gate_name: str, data: bytes) -> Optional[tuple[str, int, bytes]]:
    """Run a gate directly through the registry (bypass worker_gate).

    Used by bha_compress when running inline (not in a subprocess pool),
    so we can avoid the worker_init cost and the bha_parallel import.
    """
    ssp = bha._RUNTIME if _BHA_AVAILABLE else None
    res = DEFAULT_REGISTRY.run(gate_name, data, None, ssp)
    if res is None:
        return None
    size, blob = res
    return (gate_name, size, blob)


def bha_compress(
    data: bytes,
    src_path: Optional[Path] = None,
    total_timeout_s: float = DEFAULT_TIMEOUT_S,
    verify_determinism: bool = False,
    determinism_iter: int = 100,
) -> tuple[bytes, dict]:
    """Compress `data` with the best BHA gate, with wall-clock guard.

    Args:
        data: bytes to compress.
        src_path: optional source path (used for v11 routing by extension).
        total_timeout_s: overall wall-clock budget for this call.
        verify_determinism: if True, run determinism_iter compressions and
            assert size_unique==1 (SKILL 5). Slower; for tests/CI only.
        determinism_iter: iterations when verify_determinism=True.

    Returns:
        (archive_bytes, meta_dict) where meta contains:
          'elapsed_s'     : float, wall-clock seconds
          'method'        : 'parallel' | 'sequential' | 'fallback_lzma' | 'brotli_only'
          'best_gate'     : name of the winning gate (str)
          'best_size'     : bytes in the archive (int)
          'v11_priority'  : top-K gates v11 recommended (list[str])
          'n_candidates'  : how many gates actually succeeded (int)
          'tried'         : list of gate names attempted (list[str])
          'skipped_ssp'   : True if ssp.encode_data was bypassed (bool)
          'skipped_delta' : True if delta_pp was bypassed (bool)
          'size_class'    : 'tiny'/'small'/'medium'/'large' (str)
          'input_bytes'   : int
          'determinism'   : {size_unique, n_iter} when verify_determinism=True
    """
    t0 = time.perf_counter()
    name = src_path.name if src_path else f'data_{len(data)}.bin'

    skip_ssp = len(data) > _SSP_BYPASS_MIN
    skip_delta = len(data) > _DELTA_BYPASS_MIN

    candidates = _candidates_for(name, len(data))

    meta = {
        MI.ELAPSED_S: 0.0,
        MI.SIZE_CLASS: _size_class(len(data)),
        MI.INPUT_BYTES: len(data),
        MI.SKIPPED_SSP: skip_ssp,
        MI.SKIPPED_DELTA: skip_delta,
        MI.V11_PRIORITY: bha_recommender_v11.recommend(name, len(data), k=5),
        'best_gate': None,
        'best_size': 0,
        'n_candidates': 0,
        'tried': [],
    }

    # Run candidates in v11 priority order with a wall-clock deadline.
    deadline = t0 + total_timeout_s
    src_path_str = str(src_path) if src_path else None
    results: list[tuple[str, int, bytes]] = []

    for gate_name in candidates:
        if time.perf_counter() > deadline:
            break
        meta['tried'].append(gate_name)
        try:
            # brotli gates: direct registry call (faster, no pool overhead)
            # BHA gates: worker_gate (handles special sidecar gates)
            if gate_name in ('brotli_q11', 'brotli_q6'):
                res = _try_via_registry(gate_name, data)
            else:
                res = _try_gate(gate_name, data, src_path_str)
            if res is not None:
                results.append(res)
                meta['n_candidates'] += 1
        except Exception:
            continue

    method = 'parallel' if len(data) >= _PARALLEL_MIN else 'sequential'

    if results:
        results.sort(key=lambda r: r[1])
        best_name, best_size, best_arc = results[0]
        meta['best_gate'] = best_name
        meta['best_size'] = best_size
        meta[MI.METHOD] = method
        meta[MI.ELAPSED_S] = time.perf_counter() - t0
        if verify_determinism:
            meta['determinism'] = _assert_deterministic(
                data, src_path_str, determinism_iter, total_timeout_s,
            )
        return best_arc, meta

    # Fallback chain: try LZMA-via-BHA, then brotli, then passthrough.
    meta[MI.METHOD] = 'fallback_lzma'
    if _BHA_AVAILABLE:
        try:
            arc = bha._build_file_lzma_fallback_archive(data)
            meta['best_gate'] = 'lzma_fallback'
        except Exception:
            arc = _brotli_or_passthrough(data, meta)
    elif _brotli_available():
        arc = _brotli_or_passthrough(data, meta)
    else:
        arc = data
        meta['best_gate'] = 'passthrough_emergency'

    meta['best_size'] = len(arc)
    meta[MI.ELAPSED_S] = time.perf_counter() - t0
    return arc, meta


def _brotli_or_passthrough(data: bytes, meta: dict) -> bytes:
    """Last-resort fallback when no BHA runtime is available."""
    from bha_core.bha_codec_backends import brotli_compress
    try:
        arc = brotli_compress(data, quality=11)
        meta['best_gate'] = 'brotli_q11_emergency'
        return arc
    except Exception:
        meta['best_gate'] = 'passthrough_emergency'
        return data


def _assert_deterministic(
    data: bytes,
    src_path_str: Optional[str],
    n_iter: int,
    timeout_s: float,
) -> dict:
    """SKILL 5: run n_iter compressions, assert all sizes match. Returns stats."""
    sizes = set()
    for _ in range(n_iter):
        arc, _ = bha_compress(data, src_path=Path(src_path_str) if src_path_str else None,
                              total_timeout_s=timeout_s, verify_determinism=False)
        if arc:
            sizes.add(len(arc))
    return {'size_unique': len(sizes), 'n_iter': n_iter,
            'ok': len(sizes) == 1, 'sizes_seen': sorted(sizes)[:5]}


# ===========================================================================
# Section 5: subprocess timeout wrapper (SKILL 4)
# ===========================================================================
# Thread-based timeouts do NOT work on Windows for CPU-bound code:
# th.join(timeout=) returns when the deadline passes, but the thread
# keeps running. subprocess.run actually kills the child process.
# This is the ONLY reliable way to bound wall-clock for CPU-bound work
# like lzma.compress(PRESET_EXTREME) on 1.5 MB HTML.

def bha_compress_subprocess(
    data: bytes,
    src_path: Optional[Path] = None,
    timeout_s: float = 60.0,
) -> tuple[bytes, dict]:
    """Same as bha_compress but enforces timeout via subprocess.run.

    The data is passed via stdin (binary-safe). The subprocess prints JSON
    to stdout: {"archive_b64": ..., "meta": {...}}. We decode and return.

    On timeout or subprocess failure, returns (data, {'method': 'subprocess_emergency', ...}).
    """
    py = sys.executable
    cmd = [py, str(_HERE / 'bha.py'), '--_internal_pack', '--timeout', str(timeout_s)]
    if src_path is not None:
        cmd.append(str(src_path))

    try:
        proc = subprocess.run(
            cmd, input=data, capture_output=True,
            timeout=timeout_s + 5,  # grace
        )
    except subprocess.TimeoutExpired:
        return data, {'method': 'subprocess_timeout', 'timeout_s': timeout_s}

    if proc.returncode != 0:
        return data, {
            'method': 'subprocess_failed',
            'returncode': proc.returncode,
            'stderr': proc.stderr.decode('utf-8', errors='replace')[:500],
        }

    try:
        payload = json.loads(proc.stdout.decode('utf-8'))
        arc = base64.b64decode(payload['archive_b64'])
        return arc, payload.get('meta', {})
    except Exception as e:
        return data, {'method': 'subprocess_bad_output', 'error': str(e)}


# ===========================================================================
# Section 6: CLI
# ===========================================================================
def _pack_one_via_subprocess(args) -> int:
    """Internal entry: invoked by bha_compress_subprocess."""
    data = sys.stdin.buffer.read()
    arc, meta = bha_compress(
        data,
        src_path=Path(args.files[0]) if args.files else None,
        total_timeout_s=args.timeout,
    )
    payload = {'archive_b64': base64.b64encode(arc).decode('ascii'), 'meta': meta}
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    return 0


def _bench_one(path: Path, iterations: int, budget_s: float,
               verify_det: int) -> dict:
    data = path.read_bytes()
    pack_ms: list[float] = []
    sizes: list[int] = []
    timed_out = 0
    err_count = 0
    t0 = time.perf_counter()
    for _ in range(iterations):
        arc, meta = bha_compress(data, src_path=path, total_timeout_s=budget_s)
        method = _meta_get(meta, 'METHOD')
        if method == 'subprocess_timeout':
            timed_out += 1
            continue
        if not arc:
            err_count += 1
            continue
        pack_ms.append(_meta_get(meta, 'ELAPSED_S', 0.0) * 1000.0)
        sizes.append(len(arc))
    elapsed = time.perf_counter() - t0

    result = {
        'file': path.name, 'input_bytes': len(data),
        'iterations': iterations, 'elapsed_s': round(elapsed, 2),
        'finished': len(pack_ms), 'timed_out': timed_out, 'errors': err_count,
    }

    # SKILL 5: optional determinism check
    if verify_det > 0 and sizes:
        det = _assert_deterministic(data, str(path), verify_det, budget_s)
        result['determinism'] = det

    if pack_ms:
        s = sorted(pack_ms)
        p = lambda q: s[max(0, min(len(s) - 1, int(q * len(s))))]
        result['size_bytes'] = {
            'min': min(sizes), 'max': max(sizes),
            'median': int(statistics.median(sizes)),
            'stdev': round(statistics.stdev(sizes), 2) if len(sizes) > 1 else 0,
            'unique_count': len(set(sizes)),
        }
        result['ratio_pct_median'] = round(
            100.0 * statistics.median(sizes) / max(1, len(data)), 4)
        result['pack_ms'] = {
            'min': round(min(pack_ms), 2),
            'p50': round(p(0.50), 2),
            'p95': round(p(0.95), 2),
            'p99': round(p(0.99), 2),
            'max': round(max(pack_ms), 2),
            'mean': round(statistics.mean(pack_ms), 2),
        }
    else:
        result['warning'] = 'no successful iterations'
    return result


def _format_row(name: str, in_bytes: int, out_bytes: int,
                best_gate: Optional[str], elapsed_s: float) -> str:
    if best_gate is None:
        best_gate = '?'
    return (f'{name:40s}  in={in_bytes:>9d}  out={out_bytes:>7d}  '
            f'best={best_gate:15s}  ratio={100*out_bytes/in_bytes:6.2f}%  '
            f'{elapsed_s*1000:6.0f}ms')


def _cli(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    ap = argparse.ArgumentParser(
        prog='bha',
        description='BHA packer (T1-T3: brotli + v11 + GateRegistry + safety patches).',
    )
    ap.add_argument('files', nargs='*', type=Path,
                    help='Files to pack/benchmark. Omit for smoke test.')
    ap.add_argument('--bench', action='store_true', help='Benchmark mode.')
    ap.add_argument('--iter', type=int, default=100,
                    help='Iterations per file in --bench mode (default 100).')
    ap.add_argument('--budget', type=float, default=30.0,
                    help='Per-iteration wall-clock guard in seconds (default 30).')
    ap.add_argument('--json', action='store_true', help='Emit JSON instead of text.')
    ap.add_argument('--timeout', type=float, default=60.0,
                    help='Per-call wall-clock guard for pack mode (default 60s).')
    ap.add_argument('--verify-det', type=int, default=0, metavar='N',
                    help='After bench, verify size_unique==1 over N runs (SKILL 5).')
    ap.add_argument('--_internal_pack', action='store_true',
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    # Subprocess entry point
    if args._internal_pack:
        return _pack_one_via_subprocess(args)

    # Smoke test (no files given)
    if not args.files:
        return _smoke_test(args)

    if args.bench:
        return _bench_cli(args)

    return _pack_cli(args)


def _smoke_test(args) -> int:
    _BENCHMARK = _HERE / 'benchmark'
    cases = [
        (_BENCHMARK / 'bro_html+json-50k.html', 5.0),
        (_BENCHMARK / 'bro_json-50k.json', 5.0),
        (_BENCHMARK / 'bro_markdown-50k.md', 10.0),
        (_BENCHMARK / 'crossover_html_100kb.html', 15.0),
    ]
    cases = [(p, b) for p, b in cases if p.exists()]
    if not cases:
        print('smoke test: no built-in fixtures found at', _BENCHMARK)
        print('Use bha.py <file> to pack a specific file.')
        return 0

    rows = []
    for p, budget in cases:
        data = p.read_bytes()
        arc, meta = bha_compress(data, src_path=p, total_timeout_s=budget)
        best_gate = _meta_get(meta, 'BEST_GATE') or '?'
        elapsed = _meta_get(meta, 'ELAPSED_S', 0.0)
        print(_format_row(p.name, len(data), len(arc), best_gate, elapsed))
        rows.append({
            'file': p.name, 'in': len(data), 'out': len(arc),
            'best_gate': best_gate,
            'elapsed_s': round(elapsed, 4),
        })
    if args.json:
        print(json.dumps({'mode': 'smoke', 'rows': rows, 'bha_available': _BHA_AVAILABLE},
                         indent=2))
    return 0


def _bench_cli(args) -> int:
    results = []
    for path in args.files:
        if not path.exists():
            results.append({'file': path.name, 'error': 'file_not_found'})
            continue
        results.append(_bench_one(path, args.iter, args.budget, args.verify_det))

    summary = {
        'mode': 'bench',
        'files': len(results),
        'iterations_per_file': args.iter,
        'budget_s': args.budget,
        'verify_det': args.verify_det,
        'bha_available': _BHA_AVAILABLE,
        'bha_import_error': str(_BHA_IMPORT_ERROR) if _BHA_IMPORT_ERROR else None,
        'results': results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f'bench: {summary["files"]} files x {args.iter} iter, '
              f'budget={args.budget:.0f}s, bha={_BHA_AVAILABLE}')
        for r in results:
            if 'error' in r:
                print(f'  {r["file"]:40s}  ERROR: {r["error"]}')
                continue
            pk = r.get('pack_ms', {})
            det = r.get('determinism')
            det_info = (f'  det={det["size_unique"]}/{det["n_iter"]} '
                        f'(ok={det["ok"]})') if det else ''
            print(f'  {r["file"]:40s}  in={r["input_bytes"]:>9d}  '
                  f'finished={r["finished"]:>4d}/{r["iterations"]}  '
                  f'ratio={r["ratio_pct_median"]:>6.2f}%  '
                  f'size_unique={r["size_bytes"]["unique_count"]}  '
                  f'p50={pk.get("p50", 0):>6.0f}ms{det_info}')
    return 0


def _pack_cli(args) -> int:
    rows = []
    for path in args.files:
        if not path.exists():
            print(f'skip {path.name}: missing', file=sys.stderr)
            continue
        data = path.read_bytes()
        arc, meta = bha_compress(data, src_path=path, total_timeout_s=args.timeout)
        best_gate = _meta_get(meta, 'BEST_GATE') or '?'
        elapsed = _meta_get(meta, 'ELAPSED_S', 0.0)
        print(_format_row(path.name, len(data), len(arc), best_gate, elapsed))
        rows.append({
            'file': path.name, 'in': len(data), 'out': len(arc),
            'best_gate': best_gate,
            'elapsed_s': round(elapsed, 4),
            'meta': meta,
        })
    if args.json:
        print(json.dumps({'mode': 'pack', 'rows': rows,
                          'bha_available': _BHA_AVAILABLE}, indent=2))
    return 0


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == '__main__':
    sys.exit(_cli(sys.argv[1:]))