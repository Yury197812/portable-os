"""Investigation I: adaptive atomize on REAL BHA corpus files.

Re-uses extractors from investigate_ssp5_real_corpus.py and applies the
adaptive_atomize() selector per chunk. Goal: prove that the per-chunk
selector wins over both raw u64 and naive atomize on real data.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, r"D:\4\bha-codecs")
from investigate_ssp5_even_atom import (
    atomize_integers, ssp5_encode, ssp5_decode,
)
from investigate_ssp5_adaptive import (
    adaptive_atomize, deadaptive_atomize,
)
from investigate_ssp5_real_corpus import (
    extract_ints_dense_csv, extract_ints_telemetry,
    CORPUS, lzma2_only,
)

OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-adaptive-real")
OUT.mkdir(parents=True, exist_ok=True)


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
            print(f"skip {fname}")
            continue
        values = extractor(path, max_rows=max_rows)
        raw = b"".join(struct.pack("<q", v) for v in values)
        atom = atomize_integers(values, chunk=4096)
        adapt = adaptive_atomize(values, chunk=4096)
        ssp5_raw = ssp5_encode(raw)
        ssp5_atom = ssp5_encode(atom)
        ssp5_adapt = ssp5_encode(adapt)
        # also: raw lzma2 size for the same bodies (no SSP5 envelope overhead)
        lz2_raw = lzma2_only(raw)
        lz2_atom = lzma2_only(atom)
        lz2_adapt = lzma2_only(adapt)
        rows.append({
            "file": fname,
            "values": len(values),
            "raw_bytes": len(raw),
            "atom_bytes": len(atom),
            "adapt_bytes": len(adapt),
            "ssp5_raw": len(ssp5_raw),
            "ssp5_atom": len(ssp5_atom),
            "ssp5_adapt": len(ssp5_adapt),
            "lz2_raw": len(lz2_raw),
            "lz2_atom": len(lz2_atom),
            "lz2_adapt": len(lz2_adapt),
        })
        # Roundtrip
        arch = ssp5_encode(adapt)
        dec = deadaptive_atomize(ssp5_decode(arch))
        rt.append({"file": fname, "match": dec == values, "n": len(values)})
    print(f"\n{'file':32s} {'values':>8s} {'raw':>10s} {'atom':>10s} {'adapt':>10s} "
          f"{'ssp5_raw':>10s} {'ssp5_atom':>10s} {'ssp5_adapt':>10s}")
    for r in rows:
        print(f"  {r['file']:30s} {r['values']:>8d} {r['raw_bytes']:>10d} "
              f"{r['atom_bytes']:>10d} {r['adapt_bytes']:>10d} "
              f"{r['ssp5_raw']:>10d} {r['ssp5_atom']:>10d} {r['ssp5_adapt']:>10d}")
    print(f"\n{'file':32s} {'lz2_raw':>10s} {'lz2_atom':>10s} {'lz2_adapt':>10s} "
          f"(no SSP5 envelope)")
    for r in rows:
        print(f"  {r['file']:30s} {r['lz2_raw']:>10d} {r['lz2_atom']:>10d} "
              f"{r['lz2_adapt']:>10d}")
    out_json = OUT / "adaptive-real-results.json"
    out_json.write_text(json.dumps({"rows": rows, "roundtrip": rt}, indent=2))
    print(f"\nresults -> {out_json}")
    fails = [r for r in rt if not r["match"]]
    if fails:
        print(f"ROUNDTRIP FAILED: {[f['file'] for f in fails]}")
        raise SystemExit(1)
    print(f"\nall {len(rt)} real-corpus adaptive roundtrips match")


if __name__ == "__main__":
    main()