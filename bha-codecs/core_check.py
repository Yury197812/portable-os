"""Minimal core correctness check for bha-codecs project.

Runs every script in bha_core/ that must always pass and reports
pass/fail. Designed to be the 'one script to verify everything works'.

Usage: python core_check.py
"""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r'D:\4\bha-codecs')
CORE = ROOT / 'bha_core'


def run(label: str, args: list[str], cwd: Path, timeout: float = 300.0,
        extra_pythonpath: list[Path] | None = None) -> tuple[bool, str]:
    """Run subprocess, return (passed, output).

    Args:
        label: display name for the test
        args: command-line args for python interpreter
        cwd: working directory for the subprocess
        timeout: max wall-clock seconds
        extra_pythonpath: additional paths prepended to PYTHONPATH so
            bha_core.* imports resolve regardless of cwd
    """
    print(f'  [{label}] ...', flush=True)
    env = None
    if extra_pythonpath:
        import os
        env = os.environ.copy()
        existing = env.get('PYTHONPATH', '')
        pp = os.pathsep.join(str(p) for p in extra_pythonpath)
        env['PYTHONPATH'] = pp + (os.pathsep + existing if existing else '')
    t = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable] + args,
            cwd=str(cwd),
            capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        elapsed = time.perf_counter() - t
        if proc.returncode != 0:
            return False, f'FAIL ({elapsed:.1f}s) rc={proc.returncode}\n{proc.stderr[-500:]}'
        return True, f'OK ({elapsed:.1f}s)'
    except subprocess.TimeoutExpired:
        return False, f'TIMEOUT after {timeout}s'
    except Exception as e:
        return False, f'EXC: {type(e).__name__}: {e}'


def main():
    print('=== BHA-codecs core correctness check ===')
    print(f'  package: {CORE}\n')
    results = []

    # All these scripts import from bha_core.* so they need the parent
    # project dir on PYTHONPATH. We pass it via env.
    py_pp = [ROOT]

    # 1. Adaptive int encoder round-trip + 72 fixture compression
    ok, msg = run('bha_delta.py', ['-m', 'bha_core.bha_delta'], cwd=ROOT,
                  timeout=120, extra_pythonpath=py_pp)
    results.append(('adaptive int (bha_delta)', ok, msg))

    # 2. v10 round-trip safe preprocessors
    ok, msg = run('bha_v10_pp_safe.py', ['-m', 'bha_core.bha_v10_pp_safe'], cwd=ROOT,
                  timeout=60, extra_pythonpath=py_pp)
    results.append(('v10 pp round-trip (bha_v10_pp_safe)', ok, msg))

    # 3. Persistent worker pool unit tests
    ok, msg = run('bha_persistent_pool.py', ['-m', 'bha_core.bha_persistent_pool'], cwd=ROOT,
                  timeout=60, extra_pythonpath=py_pp)
    results.append(('persistent pool (bha_persistent_pool)', ok, msg))

    # 4. Parallel orchestrator unit tests + 1 file CLI
    # CLI mode requires sys.argv to contain the file path, so we run
    # via Python directly (not -m) with explicit script path.
    ok, msg = run('bha_parallel.py',
                  [str(CORE / 'bha_parallel.py'),
                   str(ROOT / 'benchmark' / 'delta_arith_500kb.csv')],
                  cwd=ROOT, timeout=180, extra_pythonpath=py_pp)
    results.append(('parallel orchestrator (bha_parallel)', ok, msg))

    # 5. v11 recommender API (recommend + lzma_preset_for)
    ok, msg = run('bha_recommender_v11.py', ['-m', 'bha_core.bha_recommender_v11'],
                  cwd=ROOT, timeout=30, extra_pythonpath=py_pp)
    results.append(('v11 recommender API (bha_recommender_v11)', ok, msg))

    # 6. L15 training + LOO eval
    ok, msg = run('recommender_v11.py', ['-m', 'bha_core.recommender_v11'],
                  cwd=ROOT, timeout=120, extra_pythonpath=py_pp)
    results.append(('L15 training (recommender_v11)', ok, msg))

    # 7. Multi-codec benchmark (smoke: 3 files)
    ok, msg = run('bench_codecs.py',
                  [str(CORE / 'bench_codecs.py'), '--iter', '1',
                   '--max-files', '3', '--max-file-size', '100000',
                   '--quiet', '--out', str(ROOT / 'benchmark' / 'codec-benchmark' / '_core.json')],
                  cwd=ROOT, timeout=120, extra_pythonpath=py_pp)
    results.append(('multi-codec bench (bench_codecs)', ok, msg))

    # 8. v10 gates test (longer timeout — runs 45 files × 3 gates)
    ok, msg = run('test_v10_pp_gates.py',
                  [str(ROOT / 'test_v10_pp_gates.py')],
                  cwd=ROOT, timeout=900, extra_pythonpath=py_pp)
    results.append(('v10 gates (test_v10_pp_gates)', ok, msg))

    # ---- Summary ----
    print('\n=== SUMMARY ===')
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_total = len(results)
    for label, ok, msg in results:
        flag = 'PASS' if ok else 'FAIL'
        print(f'  {flag:4s}  {label:50s}  {msg}')

    print(f'\n{n_pass}/{n_total} passed')
    sys.exit(0 if n_pass == n_total else 1)


if __name__ == '__main__':
    main()