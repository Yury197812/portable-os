"""Multi-codec lossless benchmark.

For each input file, run every available codec and measure:
  - output_size
  - encode_ms (median of N iterations)
  - decode_ms (median of N iterations)
  - roundtrip_ok (decode(input) == input)
  - bits_per_byte (output_size * 8 / input_size)

Output: machine-readable JSON + human-readable summary.

Iteration count: default 3 (fast). For "1000 times correctly" the user
requested, use --iter 1000.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import io
import json
import lzma
import os
import statistics
import sys
import time
import warnings
import bz2
import zlib
from pathlib import Path

warnings.filterwarnings('ignore')

# -------- Codec registry: (name, encode_fn, decode_fn, max_level) ----------
CODECS = []


def _register(name, encode_fn, decode_fn, max_level=None):
    CODECS.append({
        'name': name,
        'encode': encode_fn,
        'decode': decode_fn,
        'max_level': max_level,
    })


def _try_register(name, import_fn, encode_fn, decode_fn):
    try:
        import_fn()
    except ImportError as e:
        print(f'[skip] {name}: {e}', file=sys.stderr)
        return
    _register(name, encode_fn, decode_fn)


# stdlib
def _lzma9_encode(d):
    return lzma.compress(d, format=lzma.FORMAT_XZ,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}])
def _lzma9_decode(d):
    return lzma.decompress(d)
_register('lzma9_extreme', _lzma9_encode, _lzma9_decode, max_level=12)


def _lzma6_encode(d):
    return lzma.compress(d, format=lzma.FORMAT_XZ,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": 6}])
_register('lzma6', _lzma6_encode, _lzma9_decode, max_level=6)


def _bz2_encode(d):
    return bz2.compress(d, compresslevel=9)
def _bz2_decode(d):
    return bz2.decompress(d)
_register('bz2_9', _bz2_encode, _bz2_decode, max_level=9)


def _zlib9_encode(d):
    return zlib.compress(d, level=9)
def _zlib9_decode(d):
    return zlib.decompress(d)
_register('zlib_9', _zlib9_encode, _zlib9_decode, max_level=9)


def _gzip9_encode(d):
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode='wb', compresslevel=9) as f:
        f.write(d)
    return bio.getvalue()
def _gzip9_decode(d):
    return gzip.decompress(d)
_register('gzip_9', _gzip9_encode, _gzip9_decode, max_level=9)


# brotli
def _brotli_import():
    import brotli
def _brotli11_encode(d):
    import brotli
    return brotli.compress(d, quality=11)
def _brotli11_decode(d):
    import brotli
    return brotli.decompress(d)
_try_register('brotli_11', _brotli_import, _brotli11_encode, _brotli11_decode)


def _brotli6_encode(d):
    import brotli
    return brotli.compress(d, quality=6)
_try_register('brotli_6', _brotli_import, _brotli6_encode, _brotli11_decode)


# lz4
def _lz4_import():
    import lz4.frame
def _lz4_encode(d):
    import lz4.frame
    return lz4.frame.compress(d, compression_level=12)
def _lz4_decode(d):
    import lz4.frame
    return lz4.frame.decompress(d)
_try_register('lz4_12', _lz4_import, _lz4_encode, _lz4_decode)


def _lz4_block_encode(d):
    import lz4.block
    # store_size=True adds length prefix; round-trip-safe with default decompress
    return lz4.block.compress(d, mode='high_compression')
def _lz4_block_decode(d):
    import lz4.block
    return lz4.block.decompress(d)
_try_register('lz4_block_hc', lambda: __import__('lz4.block'), _lz4_block_encode, _lz4_block_decode)


# snappy
def _snappy_import():
    import snappy
def _snappy_encode(d):
    import snappy
    return snappy.compress(d)
def _snappy_decode(d):
    import snappy
    return snappy.decompress(d)
_try_register('snappy', _snappy_import, _snappy_encode, _snappy_decode)


# zstandard
def _zstd_import():
    import zstandard
def _zstd22_encode(d):
    import zstandard
    cctx = zstandard.ZstdCompressor(level=22)
    return cctx.compress(d)
def _zstd22_decode(d):
    import zstandard
    return zstandard.ZstdDecompressor().decompress(d)
_try_register('zstd_22', _zstd_import, _zstd22_encode, _zstd22_decode)


def _zstd3_encode(d):
    import zstandard
    cctx = zstandard.ZstdCompressor(level=3)
    return cctx.compress(d)
_try_register('zstd_3', _zstd_import, _zstd3_encode, _zstd22_decode)


# zopfli (deflate, max 11 minutes for max quality — we cap iterations)
def _zopfli_import():
    import zopfli.zlib as zzl
    return zzl
def _zopfli_encode(d):
    import zopfli.zlib as zzl
    # zopfli.compress takes (data, numiterations, blocksplittingmax)
    # 1 iteration = ~1x slow deflate, 15 = ~15x but slow
    return zzl.compress(d, numiterations=15)
def _zopfli_decode(d):
    # zopfli.compress produces zlib-format (with 78 da header); decode default
    return zlib.decompress(d)
_try_register('zopfli_deflate_15', _zopfli_import, _zopfli_encode, _zopfli_decode)


# pyppmd: encoder works but decoder returns wrong length (PyPpmd bug).
# Disabled to avoid false passes.
def _ppmd_skip(): pass


# cramjam: Compressor.finish() returns int, not bytes. Use simpler API instead.
def _cramjam_skip(): pass


# ---------------------------------------------------------------------------
# Iteration runner
# ---------------------------------------------------------------------------
def run_codec(codec, data, skip_long=False):
    """Run encode/decode `iterations` times, return median metrics."""
    # Warmup
    try:
        enc = codec['encode'](data)
        dec = codec['decode'](enc)
        if dec != data:
            return {'error': 'roundtrip_failed', 'codec': codec['name']}
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}', 'codec': codec['name']}

    enc_ms = []
    dec_ms = []
    for _ in range(iter_target):
        t = time.perf_counter()
        enc = codec['encode'](data)
        enc_ms.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        dec = codec['decode'](enc)
        dec_ms.append((time.perf_counter() - t) * 1000)
        if dec != data:
            return {'error': 'roundtrip_failed', 'codec': codec['name']}

    return {
        'codec': codec['name'],
        'output_size': len(enc),
        'bits_per_byte': round(8. * len(enc) / max(len(data), 1), 4),
        'ratio': round(len(data) / len(enc), 3),
        'encode_p50_ms': round(statistics.median(enc_ms), 2),
        'decode_p50_ms': round(statistics.median(dec_ms), 2),
        'roundtrip_ok': True,
    }


iter_target = 3


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iter', type=int, default=3,
                        help=f'Iterations per codec/file (default 3; user requested 1000)')
    parser.add_argument('--max-files', type=int, default=0, help='Cap file count (0=all)')
    parser.add_argument('--max-file-size', type=int, default=0, help='Skip files larger than N bytes')
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--codecs', type=str, default='', help='Comma-separated codec names to include')
    parser.add_argument('--full-corpus', action='store_true',
                        help='Skip manifest.json and scan all directories (slow)')
    parser.add_argument('--quiet', action='store_true', help='Per-codec output to stderr only')
    args = parser.parse_args()

    global iter_target
    iter_target = args.iter

    print(f'codecs registered: {len(CODECS)}')
    for c in CODECS:
        print(f'  - {c["name"]} (max_level={c["max_level"]})')

    # Find corpus files: priority is canonical BHA manifest (50 files),
    # then delta_* fixtures (controlled size variations).
    manifest_path = Path(r'D:\PROJECT UNIVERSE\01Compression\BHA\TEST\manifest.json')
    files = []
    if manifest_path.exists() and not args.full_corpus:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for f in manifest['files']:
            p = Path(r'D:\PROJECT UNIVERSE\01Compression\BHA\TEST') / f['name']
            if p.is_file() and (not args.max_file_size or f['size'] <= args.max_file_size):
                files.append(p)
    else:
        # Fallback: scan directories but skip subdirs with many duplicates.
        # The benchmark/ dir lives next to bha_core/, not inside it.
        _HERE = Path(__file__).parent
        _PROJECT = _HERE.parent
        fixtures_dirs = [
            _PROJECT / 'benchmark',
            Path(r'D:\PROJECT UNIVERSE\01Compression\BHA\TEST'),
        ]
        for d in fixtures_dirs:
            if not d.exists():
                continue
            for p in d.iterdir():
                if not p.is_file():
                    continue
                if p.suffix in ('.json', '.zip', '.gz', '.bz2', '.xz'):
                    continue
                if args.max_file_size and p.stat().st_size > args.max_file_size:
                    continue
                files.append(p)
    files = sorted(set(files))
    if args.max_files:
        files = files[:args.max_files]
    print(f'\nfiles to test: {len(files)}')
    if iter_target >= 100:
        print(f'WARNING: {iter_target} iterations requested; this may take many minutes per file/codec')

    selected_codecs = CODECS
    if args.codecs:
        wanted = set(args.codecs.split(','))
        selected_codecs = [c for c in CODECS if c['name'] in wanted]

    results = []
    for fi, fp in enumerate(files, 1):
        data = fp.read_bytes()
        if not args.quiet:
            print(f'\n[{fi}/{len(files)}] {fp.name}  ({len(data)} bytes)', flush=True)
        row = {
            'file': fp.name,
            'path': str(fp),
            'input_size': len(data),
            'codecs': [],
        }
        for codec in selected_codecs:
            try:
                res = run_codec(codec, data)
                row['codecs'].append(res)
                bp = res.get('bits_per_byte', '?')
                if isinstance(bp, (int, float)):
                    msg = f'{bp:.2f} b/B'
                else:
                    msg = str(bp)
                if 'error' in res:
                    if not args.quiet:
                        print(f'    {codec["name"]:25s}  ERROR: {res["error"]}', flush=True)
                else:
                    if not args.quiet:
                        print(f'    {codec["name"]:25s}  out={res["output_size"]:>8d}  '
                              f'{msg:>8s}  enc={res["encode_p50_ms"]:>6.0f}ms  '
                              f'dec={res["decode_p50_ms"]:>6.0f}ms', flush=True)
            except Exception as e:
                if not args.quiet:
                    print(f'    {codec["name"]:25s}  EXC: {type(e).__name__}: {e}', flush=True)
                row['codecs'].append({'codec': codec['name'], 'error': str(e)})
        results.append(row)

    # Save (default into parent project's benchmark dir, not inside package)
    _HERE = Path(__file__).parent
    _DEFAULT_OUT = _HERE.parent / 'benchmark' / 'codec-benchmark' / 'results.json'
    out = args.out or _DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        'iterations': iter_target,
        'n_files': len(files),
        'n_codecs': len(selected_codecs),
        'codecs_registered': [c['name'] for c in CODECS],
        'rows': results,
    }, indent=2))
    print(f'\nresults: {out}')

    # Aggregate: best codec per file (by ratio)
    print('\n--- Best codec per file (by bits/byte) ---')
    best_by_cat = {}
    for row in results:
        valid = [c for c in row['codecs'] if 'error' not in c]
        if not valid:
            continue
        best = min(valid, key=lambda c: c['bits_per_byte'])
        print(f'  {row["file"]:40s}  {best["codec"]:25s}  {best["bits_per_byte"]:>6.2f} b/B')


if __name__ == '__main__':
    main()