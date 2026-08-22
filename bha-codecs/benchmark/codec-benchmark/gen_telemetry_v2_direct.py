"""generate_telemetry_v2: produce telemetry_v2.json for v11 recommender
training, including BHA_VS_BROTLI crossover fixtures.

Unlike generate_telemetry_v2.py, this version doesn't go through bench_codecs.py
subprocess (which has a hard-coded manifest path). Instead it directly calls
bench_codecs.run_codec on each fixture and writes results.json in the
same schema as bench_codecs.py produces.
"""
from __future__ import annotations
import argparse
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).parent
_PROJECT = _HERE.parent.parent  # .../benchmark/codec-benchmark -> .../bha-codecs
sys.path.insert(0, str(_PROJECT))

from bha_core import bench_codecs

# Default corpus = manifest (50 BHA files) + BHA_VS_BROTLI crossover
# fixtures (10) + bro_* small fixtures (5). Plus a couple of synthetic
# edge cases.
CORPUS_GLOBS_DEFAULT = [
    # From manifest path (real BHA fixtures)
    r'D:\PROJECT UNIVERSE\01Compression\BHA\TEST\*',
    # Crossover window
    'crossover_html_100kb.html',
    'crossover_html_200kb.html',
    'crossover_html_400kb.html',
    'crossover_html_800kb.html',
    'crossover_html_1024kb.html',
    'crossover_json_100kb.json',
    'crossover_json_200kb.json',
    'crossover_json_400kb.json',
    'crossover_json_800kb.json',
    'crossover_json_1024kb.json',
    # Brotli-vs-BHA small fixtures
    'bro_html+json-50k.html',
    'bro_json-50k.json',
    'bro_json-80k.json',
    'bro_markdown-50k.md',
    'bro_markdown-80k.md',
]
_FIXTURES_DIR = _PROJECT / 'benchmark'

# Skip slow codecs on large files to keep the benchmark under a few minutes.
# lzma9_extreme and zopfli_deflate_15 take 30+ seconds on 1 MB+ inputs.
SKIP_ON_LARGE = {'lzma9_extreme', 'zopfli_deflate_15'}
LARGE_THRESHOLD = 1 << 18  # 256 KiB - above this, skip slow codecs


def resolve_corpus(extra_globs: list[str], max_size: int) -> list[Path]:
    """Resolve fixture paths from a mix of literal paths and globs.

    Globs are matched against _FIXTURES_DIR (= _PROJECT/benchmark). Literal
    Windows paths are used as-is. Numbered iteration artefacts (foo (1).html)
    are skipped in favour of originals.
    """
    pattern = re.compile(r'\(\d+\)')
    out: list[Path] = []
    seen: set[Path] = set()
    for entry in extra_globs:
        if '*' in entry or '?' in entry:
            base = Path(entry)
            if not base.is_absolute():
                base = _FIXTURES_DIR / entry
            for cand in sorted(base.parent.glob(base.name)):
                if cand.is_file() and not pattern.search(cand.name) \
                        and cand.stat().st_size <= max_size \
                        and cand not in seen:
                    seen.add(cand)
                    out.append(cand)
        else:
            p = Path(entry)
            if not p.is_absolute():
                p = _FIXTURES_DIR / entry
            if p.exists() and p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def run(args) -> None:
    fixtures = resolve_corpus(CORPUS_GLOBS_DEFAULT, args.max_file_size)
    print(f'fixtures resolved: {len(fixtures)}', flush=True)
    for f in fixtures:
        print(f'  {f.name:50s}  {f.stat().st_size:>10d} B', flush=True)

    rows = []
    iter_target = args.iter
    bench_codecs.iter_target = iter_target

    for i, fp in enumerate(fixtures, 1):
        data = fp.read_bytes()
        row = {
            'file': fp.name,
            'path': str(fp),
            'input_size': len(data),
            'codecs': [],
        }
        for codec in bench_codecs.CODECS:
            if codec['name'] in SKIP_ON_LARGE and len(data) >= LARGE_THRESHOLD:
                row['codecs'].append({
                    'codec': codec['name'],
                    'error': 'skipped (large file, slow codec)',
                })
                continue
            t0 = time.perf_counter()
            try:
                res = bench_codecs.run_codec(codec, data)
            except Exception as e:
                res = {'codec': codec['name'], 'error': str(e)}
            row['codecs'].append(res)
        rows.append(row)
        # Per-file summary
        valid = [c for c in row['codecs'] if 'error' not in c]
        if valid:
            best = min(valid, key=lambda c: c['bits_per_byte'])
            print(f'  [{i}/{len(fixtures)}] {fp.name:40s} '
                  f'best={best["codec"]:15s}  {best["bits_per_byte"]:.2f} b/B',
                  flush=True)

    out = {
        'iterations': iter_target,
        'n_files': len(fixtures),
        'n_codecs': len(bench_codecs.CODECS),
        'codecs_registered': [c['name'] for c in bench_codecs.CODECS],
        'rows': rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f'\nresults: {args.out}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iter', type=int, default=3)
    ap.add_argument('--max-file-size', type=int, default=2_000_000,
                    help='Cap fixture size (default 2MB, covers crossover window)')
    ap.add_argument('--out', type=Path,
                    default=_PROJECT / 'benchmark' / 'codec-benchmark' / 'telemetry_v2.json')
    args = ap.parse_args()
    run(args)


if __name__ == '__main__':
    main()