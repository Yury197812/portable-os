"""Drop-in replacement for bha_cli.py with the safety patches baked in.

Patches applied (from bha.py):
  - LZMA presets: skip PRESET_EXTREME on files >64KB
  - ssp.encode_data: bypass entirely on files >256KB (use LZMA archive)

Reads the same argv shape as the original bha_cli.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Apply the safety patches FIRST, before any BHA code path runs.
sys.path.insert(0, str(Path(__file__).parent))
import bha  # noqa: F401  (apply patches on import)

from black_hole_archiver import (
    KIND_FILE, KIND_DIR, ARCHIVE_SUFFIX,
    _best_directory_payload, _build_bha, _default_archive_path,
    _normalize_archive_output, _unique_path,
    pack_file as _orig_pack_file,
    pack_directory as _orig_pack_directory,
    unpack_archive as _orig_unpack_archive,
)


def pack_file(src: Path, dst=None):
    return _orig_pack_file(src, dst)


def pack_directory(src: Path, dst=None):
    return _orig_pack_directory(src, dst)


def unpack_archive(src: Path, target=None):
    return _orig_unpack_archive(src, target)


def benchmark(paths, as_json=False):
    """Same behaviour as bha_cli benchmark."""
    from black_hole_archiver import pack_file as pf
    rows = []
    total_in = 0
    total_out = 0
    for p in paths:
        p = Path(p)
        data = p.read_bytes()
        t0 = time.perf_counter()
        out, src_size, dst_size = pf(p, None)  # writes <p>.bha
        pack_ms = 1000 * (time.perf_counter() - t0)
        # extract and verify
        from black_hole_archiver import unpack_archive, _sha256_file
        with open(out, "rb") as f:
            arc_bytes = f.read()
        t1 = time.perf_counter()
        decoded = unpack_archive(out)
        verify_ms = 1000 * (time.perf_counter() - t1)
        rt_ok = _sha256_file(p) == _sha256_file(decoded)
        rows.append({
            "path": str(p),
            "input_bytes": src_size,
            "archive_bytes": dst_size,
            "ratio_pct": round(100.0 * dst_size / max(1, src_size), 4),
            "pack_ms": round(pack_ms, 3),
            "verify_ms": round(verify_ms, 3),
            "rt_ok": rt_ok,
        })
        total_in += src_size
        total_out += dst_size
        # clean up .bha file
        try:
            out.unlink()
        except OSError:
            pass
    summary = {
        "files": len(rows),
        "input_bytes": total_in,
        "archive_bytes": total_out,
        "ratio_pct": round(100.0 * total_out / max(1, total_in), 4),
    }
    if as_json:
        print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False))
    else:
        print(f"files={summary['files']}  in={summary['input_bytes']}  out={summary['archive_bytes']}  ratio={summary['ratio_pct']}%")
        for r in rows:
            print(f"  {Path(r['path']).name:50s}  in={r['input_bytes']:>10d}  out={r['archive_bytes']:>9d}  {r['ratio_pct']:>6.2f}%  pack={r['pack_ms']:>6.0f}ms  verify={r['verify_ms']:>5.0f}ms  rt={r['rt_ok']}")


def main():
    ap = argparse.ArgumentParser(prog="bha_cli_safe")
    sp = ap.add_subparsers(dest="action", required=True)
    sp.add_parser("archive")
    sp.add_parser("extract")
    sp.add_parser("verify")
    p_bench = sp.add_parser("benchmark")
    p_bench.add_argument("paths", nargs="+")
    p_bench.add_argument("--json", action="store_true")
    sp.add_parser("test")
    args, rest = ap.parse_known_args()

    if args.action == "benchmark":
        benchmark(args.paths, as_json=args.json)
        return 0
    # For archive/extract/verify, defer to original bha_cli by re-invoking
    # it with the same args. Simpler: just call the original entry point.
    import subprocess
    BHA_CLI = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py")
    cmd = [sys.executable, str(BHA_CLI), args.action, *rest]
    r = subprocess.run(cmd)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main() or 0)
