"""Investigation G: SSP5 + atomize on REAL corpus files.

Extracts integers from numeric files in D:\\PROJECT UNIVERSE\\01Compression\\BHA\\TEST
and compares:
  - LZMA-XZ extreme on raw u64 stream (control)
  - SSP5 envelope on raw u64 stream
  - LZMA-XZ extreme on atomized stream
  - SSP5 envelope on atomized stream

Numbers come from real dense_numeric CSV (uints 0-65535, very dense)
and telemetry log (timestamps + values, moderate density).
"""
from __future__ import annotations

import csv
import io
import json
import lzma
import re
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_even_atom import (
    atomize_integers,
    deatomize_integers,
    ssp5_decode,
    ssp5_encode,
)

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-real-corpus")
OUT.mkdir(parents=True, exist_ok=True)


def lzma_xz_extreme(data: bytes) -> bytes:
    return lzma.compress(data, format=lzma.FORMAT_XZ,
                          preset=7 | lzma.PRESET_EXTREME)


def lzma2_only(data: bytes) -> bytes:
    """Plain LZMA2 (matches SSP5 inner codec, no SSP5 envelope)."""
    best = None
    for preset in (6, 9 | lzma.PRESET_EXTREME):
        comp = lzma.compress(data, format=lzma.FORMAT_RAW,
                              filters=[{"id": lzma.FILTER_LZMA2, "preset": preset}])
        if best is None or len(comp) < len(best):
            best = comp
    return best


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------
NUM_RE = re.compile(rb"-?\d+")


def extract_ints_dense_csv(path: Path, max_rows: int = 500_000) -> list[int]:
    """All integer cells from a dense numeric CSV."""
    out = []
    with path.open("rb") as f:
        rd = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        for r_idx, row in enumerate(rd):
            if r_idx >= max_rows:
                break
            for cell in row:
                cell = cell.strip()
                if not cell:
                    continue
                try:
                    out.append(int(cell))
                except ValueError:
                    pass
    return out


def extract_ints_telemetry(path: Path, max_rows: int = 500_000) -> list[int]:
    """Two ints per line: timestamp, value (skip header)."""
    out = []
    with path.open("rb") as f:
        line_iter = f
        for r_idx, raw in enumerate(line_iter):
            if r_idx >= max_rows:
                break
            if r_idx == 0:
                continue  # header
            nums = NUM_RE.findall(raw)
            for n in nums:
                try:
                    out.append(int(n))
                except ValueError:
                    pass
    return out


def pack_u64(values: list[int]) -> bytes:
    return b"".join(struct.pack("<q", v) for v in values)


def measure(name: str, data: bytes) -> dict:
    t0 = time.perf_counter()
    ssp5 = ssp5_encode(data)
    t1 = time.perf_counter()
    lzma_xz = lzma_xz_extreme(data)
    t2 = time.perf_counter()
    lzma2 = lzma2_only(data)
    t3 = time.perf_counter()
    return {
        "name": name,
        "orig_bytes": len(data),
        "ssp5_bytes": len(ssp5),
        "lzma_xz_bytes": len(lzma_xz),
        "lzma2_bytes": len(lzma2),
        "ssp5_ms": round((t1 - t0) * 1000, 2),
        "lzma_xz_ms": round((t2 - t1) * 1000, 2),
        "lzma2_ms": round((t3 - t2) * 1000, 2),
        "ssp5_pct": round(100 * len(ssp5) / max(1, len(data)), 3),
        "lzma_xz_pct": round(100 * len(lzma_xz) / max(1, len(data)), 3),
        "lzma2_pct": round(100 * len(lzma2) / max(1, len(data)), 3),
    }


def main():
    files = [
        ("dense_numeric_csv_300k.csv", extract_ints_dense_csv, 500_000),
        ("telemetry_logs_1m.log", extract_ints_telemetry, 500_000),
    ]
    rows = []
    rt = []
    for fname, extractor, max_rows in files:
        path = CORPUS / fname
        if not path.exists():
            print(f"skip {fname}: not found")
            continue
        t0 = time.perf_counter()
        values = extractor(path, max_rows=max_rows)
        t_extract = (time.perf_counter() - t0) * 1000
        print(f"\n{fname}: extracted {len(values):,} ints in {t_extract:.1f} ms")
        raw = pack_u64(values)
        atom = atomize_integers(values, chunk=4096)
        rows.append(measure(f"{fname}__raw_u64", raw))
        rows.append(measure(f"{fname}__atomized", atom))

        # Roundtrip
        arch = ssp5_encode(atom)
        dec_atom = ssp5_decode(arch)
        dec = deatomize_integers(dec_atom)
        ok = dec == values
        rt.append({
            "file": fname,
            "values": len(values),
            "atom_bytes": len(atom),
            "ssp5_bytes": len(arch),
            "match": ok,
        })
    print(f"\n{'case':42s} {'orig':>10s} {'ssp5':>9s} {'lzma':>9s} {'lzma2':>9s} "
          f"{'ssp5%':>7s} {'lzma%':>7s} {'lz2%':>7s}")
    for r in rows:
        print(f"  {r['name']:40s} {r['orig_bytes']:>10d} "
              f"{r['ssp5_bytes']:>9d} {r['lzma_xz_bytes']:>9d} {r['lzma2_bytes']:>9d} "
              f"{r['ssp5_pct']:>7.3f} {r['lzma_xz_pct']:>7.3f} {r['lzma2_pct']:>7.3f}")
    out_json = OUT / "real-corpus-results.json"
    out_json.write_text(json.dumps({"rows": rows, "roundtrip": rt}, indent=2))
    print(f"\nresults -> {out_json}")
    fails = [r for r in rt if not r["match"]]
    if fails:
        print(f"ROUNDTRIP FAILED: {[f['file'] for f in fails]}")
        raise SystemExit(1)
    print(f"\nall {len(rt)} real-corpus roundtrips match")


if __name__ == "__main__":
    main()