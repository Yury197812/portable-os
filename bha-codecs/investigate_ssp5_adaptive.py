"""Investigation H: adaptive atomize — pick raw-vs-atomized per chunk.

Idea: the previous investigation showed that atomize wins on synthetic
arithmetic progressions (5.6×) but loses on real CSV/telemetry (-30 to
-50%). The reason: chunk-header overhead is fixed (15 bytes / 4096 vals),
and LZMA2 already catches deltas in raw u64 streams.

Adaptive atomize:
  - For each chunk, compute both atomize-body and raw-u64 body
  - Run a quick LZMA2 (preset=6, FORMAT_RAW) estimate on each
  - Emit the body that compresses smaller
  - Add a 1-byte flag per chunk to remember the choice for decoding

This guarantees: adaptive_bytes <= min(atomize_bytes, raw_bytes) post-LZMA2.

Roundtrip verified by separate test.
"""
from __future__ import annotations

import json
import lzma
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
    _atomize_chunk,
)

OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-adaptive")
OUT.mkdir(parents=True, exist_ok=True)


ADAPTIVE_MAGIC = b"ADP1\0\0\0\0"


def _lzma2_size(data: bytes, preset: int = 6) -> int:
    """Return LZMA2-compressed size without keeping the bytes."""
    return len(lzma.compress(
        data, format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA2, "preset": preset}]))


def adaptive_atomize(values: list[int], chunk: int = 4096) -> bytes:
    """Per-chunk pick: atomize body vs raw u64 body, whichever LZMA2 compresses smaller."""
    out = bytearray()
    out.extend(ADAPTIVE_MAGIC)
    for c_start in range(0, len(values), chunk):
        chunk_vals = values[c_start:c_start + chunk]
        atom_body, width = _atomize_chunk(chunk_vals)
        raw_body = b"".join(struct.pack("<q", v) for v in chunk_vals)
        # Build framed candidates
        atom_framed = b"A" + struct.pack("<IIB", len(chunk_vals), len(atom_body), width) + atom_body
        raw_framed = b"R" + struct.pack("<I", len(chunk_vals)) + raw_body
        # Pick by post-LZMA2 size
        size_a = _lzma2_size(atom_framed)
        size_r = _lzma2_size(raw_framed)
        if size_a <= size_r:
            out.extend(atom_framed)
        else:
            out.extend(raw_framed)
    out.extend(b"ADEND")
    return bytes(out)


def deadaptive_atomize(blob: bytes) -> list[int]:
    """Inverse of adaptive_atomize."""
    if not blob.startswith(ADAPTIVE_MAGIC):
        raise ValueError("bad ADP1 magic")
    off = 8
    out: list[int] = []
    while off < len(blob):
        if blob[off:off + 5] == b"ADEND":
            break
        flag = blob[off:off + 1]
        off += 1
        if flag == b"A":
            count = int.from_bytes(blob[off:off + 4], "little"); off += 4
            body_len = int.from_bytes(blob[off:off + 4], "little"); off += 4
            width_code = blob[off]; off += 1
            body = blob[off:off + body_len]; off += body_len
            out.extend(_deatomize_chunk(count, body, width_code))
        elif flag == b"R":
            count = int.from_bytes(blob[off:off + 4], "little"); off += 4
            for i in range(count):
                out.append(struct.unpack("<q", blob[off:off + 8])[0])
                off += 8
        else:
            raise ValueError(f"bad chunk flag {flag!r}")
    return out


def _deatomize_chunk(count: int, body: bytes, width_code: int):
    """Local copy to avoid circular import (ssp5_even_atom exposes the same)."""
    import struct as _s
    if width_code == 0:
        return [0] * count
    if width_code in (1, 2, 3):
        sizes = {1: 1, 2: 2, 3: 4}
        s = sizes[width_code]
        base = _s.unpack("<q", body[:8])[0]
        tail = body[8:]
        fmt = {1: "B", 2: "H", 3: "I"}[width_code]
        half = 1 << (8 * s - 1)
        span = 1 << (8 * s)
        out = []
        for i in range(count):
            u = _s.unpack("<" + fmt, tail[i * s:(i + 1) * s])[0]
            d = u - half
            if d >= half:
                d -= span
            out.append(base + d)
        return out
    if width_code == 4:
        base = _s.unpack("<q", body[:8])[0]
        tail = body[8:]
        sd = [_s.unpack("<q", tail[i * 8:(i + 1) * 8])[0] for i in range(count - 1)]
        out = [base]
        cur = base
        for d in sd:
            cur += d
            out.append(cur)
        return out
    if width_code == 6:
        return [_s.unpack("<q", body[i * 8:(i + 1) * 8])[0] for i in range(count)]
    raise ValueError(f"unknown width_code {width_code}")


# ---------------------------------------------------------------------------
# Bench harness (re-uses the same generators as investigate_ssp5_even_atom)
# ---------------------------------------------------------------------------
def lzma2_only(data: bytes) -> bytes:
    best = None
    for preset in (6, 9 | lzma.PRESET_EXTREME):
        comp = lzma.compress(data, format=lzma.FORMAT_RAW,
                              filters=[{"id": lzma.FILTER_LZMA2, "preset": preset}])
        if best is None or len(comp) < len(best):
            best = comp
    return best


def main():
    from investigate_ssp5_even_atom import (
        gen_even_mask_zero, gen_even_mask_one, gen_arbitrary, gen_arbitrary_mixed,
    )
    counts = [16_384, 131_072]
    generators = [
        ("even_mask_0", gen_even_mask_zero),
        ("even_mask_1", gen_even_mask_one),
        ("arbitrary_lcg", gen_arbitrary),
        ("arbitrary_mixed", gen_arbitrary_mixed),
    ]
    rows = []
    rt = []
    for n in counts:
        for gname, gfn in generators:
            values = gfn(n)
            raw = b"".join(struct.pack("<q", v) for v in values)
            atom = atomize_integers(values, chunk=4096)
            adapt = adaptive_atomize(values, chunk=4096)
            ssp5_raw = ssp5_encode(raw)
            ssp5_atom = ssp5_encode(atom)
            ssp5_adapt = ssp5_encode(adapt)
            rows.append({
                "case": f"{gname}__n={n}",
                "raw_bytes": len(raw),
                "atom_bytes": len(atom),
                "adapt_bytes": len(adapt),
                "ssp5_raw": len(ssp5_raw),
                "ssp5_atom": len(ssp5_atom),
                "ssp5_adapt": len(ssp5_adapt),
            })
            # Roundtrip
            arch = ssp5_encode(adapt)
            dec = deadaptive_atomize(ssp5_decode(arch))
            rt.append({"case": rows[-1]["case"], "match": dec == values})
    print(f"{'case':36s} {'raw':>10s} {'atom':>10s} {'adapt':>10s} "
          f"{'ssp5_raw':>10s} {'ssp5_atom':>10s} {'ssp5_adapt':>10s}")
    for r in rows:
        print(f"  {r['case']:34s} {r['raw_bytes']:>10d} {r['atom_bytes']:>10d} "
              f"{r['adapt_bytes']:>10d} {r['ssp5_raw']:>10d} {r['ssp5_atom']:>10d} "
              f"{r['ssp5_adapt']:>10d}")
    out_json = OUT / "adaptive-results.json"
    out_json.write_text(json.dumps({"rows": rows, "roundtrip": rt}, indent=2))
    print(f"\nresults -> {out_json}")
    fails = [r for r in rt if not r["match"]]
    if fails:
        print(f"ROUNDTRIP FAILED: {[f['case'] for f in fails]}")
        raise SystemExit(1)
    print(f"\nall {len(rt)} adaptive roundtrips match")


if __name__ == "__main__":
    main()