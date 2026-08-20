"""Investigation F: SSP5 (RUNTIME_CODEC) test with even-numbers + 0/1 bitmask
and arbitrary-number atomization.

Source note (catalog.ini line 14-19):
  SSP5 = RUNTIME_CODEC_MAGIC = b"SSP5"
  Internal runtime codec base used by every BH* envelope.
  Frame layout (black_hole_archiver.py:670-680):
      magic "SSP5" | ver 3 | flags 0x21 | block_bits | ULEB(1) | ULEB(1)
      | ULEB(orig_len) | ULEB(0) | subtype 16 | u32_le(comp_len) | LZMA2 body

Pipeline under test:
  - even-mask 0   : payload = sequence of even integers (0, 2, 4, ..., 2N)
  - even-mask 1   : payload = sequence of (even | 1) integers (1, 3, 5, ..., 2N+1)
  - atomized      : payload = chunked arbitrary integers via atomic-cluster atomize
  - raw bytes     : payload = uint64 little-endian (control)

Encoders compared:
  - LZMA-XZ extreme (BHLZ1 fallback reference)
  - SSP5 subtype=16 envelope wrapping LZMA2 (presets 6 + 9|EXTREME, pick min)
"""
from __future__ import annotations

import io
import json
import lzma
import struct
import sys
import time
from pathlib import Path

BHA_SRC = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\black_hole_archiver.py")
OUT = Path(r"D:\4\bha-codecs\benchmark\ssp5-even-atom")
OUT.mkdir(parents=True, exist_ok=True)

RUNTIME_CODEC_MAGIC = b"SSP5"
RUNTIME_CODEC_VERSION = 3
RUNTIME_LZMA_SUBTYPE = 16


def uleb_encode(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def ssp5_encode(data: bytes) -> bytes:
    """Reproduce _build_runtime_lzma_archive from black_hole_archiver.py:652."""
    best = None
    for preset in (6, 9 | lzma.PRESET_EXTREME):
        comp = lzma.compress(
            data,
            format=lzma.FORMAT_RAW,
            filters=[{"id": lzma.FILTER_LZMA2, "preset": preset}],
        )
        if best is None or len(comp) < len(best):
            best = comp
    out = bytearray(RUNTIME_CODEC_MAGIC)
    out.append(RUNTIME_CODEC_VERSION)
    out.append(32 | 1)
    out.append(32)
    out.extend(uleb_encode(1))
    out.extend(uleb_encode(1))
    out.extend(uleb_encode(len(data)))
    out.extend(uleb_encode(0))
    out.append(RUNTIME_LZMA_SUBTYPE)
    out.extend(len(best).to_bytes(4, "little"))
    out.extend(best)
    return bytes(out)


def lzma_xz_extreme(data: bytes) -> bytes:
    return lzma.compress(data, format=lzma.FORMAT_XZ,
                          preset=7 | lzma.PRESET_EXTREME)


# ---------------------------------------------------------------------------
# Atomization: arbitrary integers -> compact representation
# ---------------------------------------------------------------------------
def atomize_integers(values: list[int], chunk: int = 4096) -> bytes:
    """Atomize a stream of arbitrary integers into chunked buckets.

    Each chunk produces a 16-byte header:
        magic b"ATM1\\0" (8) | count u32_le | bit-width u8 | reserved u8
        | orig_bytes u32_le
    followed by the body chosen by the chunk's value statistics:
      - all-zero: 0-byte body
      - delta-encodable (monotonic-ish): body = uint8/uint16/uint32/uint64 deltas
      - shared-prefix: body = shared bytes + per-row tail
      - otherwise:    body = raw uint64_le values
    """
    out = bytearray()
    out.extend(b"ATM1\0\0\0\0")
    for c_start in range(0, len(values), chunk):
        chunk_vals = values[c_start:c_start + chunk]
        body, width = _atomize_chunk(chunk_vals)
        header = bytearray(b"CHUNK\0\0")
        header.extend(struct.pack("<IIB", len(chunk_vals), len(body), width))
        out.extend(header)
        out.extend(body)
    out.extend(b"ENDCHNK")
    return bytes(out)


def _atomize_chunk(vals: list[int]) -> tuple[bytes, int]:
    """Return (body, width_code). width_code: 0=zero, 1=delta8, 2=delta16,
    3=delta32, 4=delta64, 5=prefix+tail, 6=raw64.

    Width is selected by max(|delta|), not max(|value|), because the centered
    signed encoding needs [d - half, d + half) to fit in N bytes.
    """
    if not vals:
        return b"", 0
    if all(v == 0 for v in vals):
        return b"", 0
    base = vals[0]
    deltas = [v - base for v in vals]
    max_d = max((abs(d) for d in deltas), default=0)
    if max_d <= 0x7F:
        width_code = 1
        body = struct.pack("<q", base) + bytes(_center_signed(d, 1) for d in deltas)
        return body, width_code
    if max_d <= 0x7FFF:
        width_code = 2
        body = struct.pack("<q", base) + b"".join(
            struct.pack("<H", _center_signed(d, 2)) for d in deltas)
        return body, width_code
    if max_d <= 0x7FFFFFFF:
        width_code = 3
        body = struct.pack("<q", base) + b"".join(
            struct.pack("<I", _center_signed(d, 4)) for d in deltas)
        return body, width_code
    seq_deltas = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    if all(-(2**63) <= d <= 2**63 - 1 for d in seq_deltas):
        if max(abs(d) for d in seq_deltas) <= 0x7FFFFFFFFFFFFFFF:
            width_code = 4
            body = struct.pack("<q", vals[0]) + b"".join(struct.pack("<q", d) for d in seq_deltas)
            return body, width_code
    width_code = 6
    body = b"".join(struct.pack("<q", v) for v in vals)
    return body, width_code


def _center_signed(delta: int, nbytes: int) -> int:
    """Map signed delta to [0, 2^(8*nbytes)) via shift by 2^(8*nbytes - 1)."""
    span = 1 << (8 * nbytes)
    half = span >> 1
    return (delta + half) & (span - 1)


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def gen_even_mask_zero(n: int) -> list[int]:
    return [2 * i for i in range(n)]


def gen_even_mask_one(n: int) -> list[int]:
    return [2 * i + 1 for i in range(n)]


def gen_arbitrary(n: int, seed: int = 0xC0FFEE) -> list[int]:
    s = seed
    out = []
    for _ in range(n):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFFFFFFFFFF
        out.append(s)
    return out


def gen_arbitrary_mixed(n: int) -> list[int]:
    out = []
    for i in range(n):
        if i % 5 == 0:
            out.append(2 * i)
        elif i % 5 == 1:
            out.append(2 * i + 1)
        elif i % 5 == 2:
            out.append(i * i)
        elif i % 5 == 3:
            out.append(-(i * 3))
        else:
            out.append((i * 1234567) & 0xFFFFFFFF)
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
# Decoders (roundtrip)
# ---------------------------------------------------------------------------
def uleb_decode(buf: bytes, off: int) -> tuple[int, int]:
    n = 0
    shift = 0
    while True:
        b = buf[off]
        off += 1
        n |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return n, off
        shift += 7


def ssp5_decode(archive: bytes) -> bytes:
    """Inverse of _build_runtime_lzma_archive for subtype=16."""
    if not archive.startswith(RUNTIME_CODEC_MAGIC):
        raise ValueError("bad SSP5 magic")
    off = len(RUNTIME_CODEC_MAGIC)
    version = archive[off]; off += 1
    flags = archive[off]; off += 1
    block_bits = archive[off]; off += 1
    if version != RUNTIME_CODEC_VERSION:
        raise ValueError(f"bad SSP5 version {version}")
    n_streams, off = uleb_decode(archive, off)
    n_blocks, off = uleb_decode(archive, off)
    orig_len, off = uleb_decode(archive, off)
    _skipped, off = uleb_decode(archive, off)
    subtype = archive[off]; off += 1
    if subtype != RUNTIME_LZMA_SUBTYPE:
        raise ValueError(f"unsupported SSP5 subtype {subtype}")
    comp_len = int.from_bytes(archive[off:off + 4], "little"); off += 4
    body = archive[off:off + comp_len]
    if len(body) != comp_len:
        raise ValueError("truncated SSP5 body")
    return lzma.decompress(body, format=lzma.FORMAT_RAW,
                            filters=[{"id": lzma.FILTER_LZMA2}])


def deatomize_integers(blob: bytes, chunk: int = 4096) -> list[int]:
    if not blob.startswith(b"ATM1"):
        raise ValueError("bad atomize magic")
    off = 8
    out: list[int] = []
    while off < len(blob):
        if blob[off:off + 7] == b"ENDCHNK":
            break
        if not blob.startswith(b"CHUNK\0\0", off):
            raise ValueError(f"bad chunk marker at off={off}")
        off += 7
        count = int.from_bytes(blob[off:off + 4], "little"); off += 4
        body_len = int.from_bytes(blob[off:off + 4], "little"); off += 4
        width_code = blob[off]; off += 1
        body = blob[off:off + body_len]; off += body_len
        out.extend(_deatomize_chunk(count, body, width_code))
    return out


def _deatomize_chunk(count: int, body: bytes, width_code: int) -> list[int]:
    if width_code == 0:
        return [0] * count
    if width_code in (1, 2, 3):
        sizes = {1: 1, 2: 2, 3: 4}
        s = sizes[width_code]
        base = struct.unpack("<q", body[:8])[0]
        tail = body[8:]
        fmt = {1: "B", 2: "H", 3: "I"}[width_code]
        half = 1 << (8 * s - 1)
        span = 1 << (8 * s)
        out = []
        for i in range(count):
            u = struct.unpack("<" + fmt, tail[i * s:(i + 1) * s])[0]
            d = u - half
            if d >= half:
                d -= span
            out.append(base + d)
        return out
    if width_code == 4:
        base = struct.unpack("<q", body[:8])[0]
        tail = body[8:]
        seq_deltas = [struct.unpack("<q", tail[i * 8:(i + 1) * 8])[0]
                      for i in range(count - 1)]
        out = [base]
        cur = base
        for d in seq_deltas:
            cur += d
            out.append(cur)
        return out
    if width_code == 6:
        return [struct.unpack("<q", body[i * 8:(i + 1) * 8])[0]
                for i in range(count)]
    raise ValueError(f"unknown width_code {width_code}")


# ---------------------------------------------------------------------------
def measure(name: str, data: bytes) -> dict:
    t0 = time.perf_counter()
    ssp5 = ssp5_encode(data)
    t1 = time.perf_counter()
    lzma_xz = lzma_xz_extreme(data)
    t2 = time.perf_counter()
    return {
        "name": name,
        "orig_bytes": len(data),
        "ssp5_bytes": len(ssp5),
        "lzma_xz_bytes": len(lzma_xz),
        "ssp5_ratio_pct": round(100 * len(ssp5) / max(1, len(data)), 2),
        "lzma_xz_ratio_pct": round(100 * len(lzma_xz) / max(1, len(data)), 2),
        "ssp5_ms": round((t1 - t0) * 1000, 2),
        "lzma_xz_ms": round((t2 - t1) * 1000, 2),
    }


def main():
    counts = [1024, 16_384, 131_072]
    generators = [
        ("even_mask_0", gen_even_mask_zero),
        ("even_mask_1", gen_even_mask_one),
        ("arbitrary_lcg", gen_arbitrary),
        ("arbitrary_mixed", gen_arbitrary_mixed),
    ]
    rows = []
    for n in counts:
        for gname, gfn in generators:
            values = gfn(n)
            raw_u64 = b"".join(struct.pack("<q", v) for v in values)
            atomized = atomize_integers(values, chunk=4096)
            rows.append(measure(f"{gname}__n={n}__raw_u64", raw_u64))
            rows.append(measure(f"{gname}__n={n}__atomized", atomized))
    print(f"{'case':40s} {'orig':>9s} {'ssp5':>9s} {'lzma':>9s} {'ssp5%':>7s} {'lzma%':>7s}")
    for r in rows:
        print(f"  {r['name']:38s} {r['orig_bytes']:>9d} {r['ssp5_bytes']:>9d} "
              f"{r['lzma_xz_bytes']:>9d} {r['ssp5_ratio_pct']:>7.2f} {r['lzma_xz_ratio_pct']:>7.2f}")
    out_json = OUT / "ssp5-even-atom-results.json"
    out_json.write_text(json.dumps(rows, indent=2))
    print(f"\nresults -> {out_json}")

    # Roundtrip integrity: encode via atomize -> SSP5 -> decode -> compare.
    print("\n--- Roundtrip integrity (atomize -> SSP5 -> decode) ---")
    rt_rows = []
    for n in counts:
        for gname, gfn in generators:
            src = gfn(n)
            atom = atomize_integers(src, chunk=4096)
            arch = ssp5_encode(atom)
            dec_atom = ssp5_decode(arch)
            dec = deatomize_integers(dec_atom)
            ok = dec == src
            rt_rows.append({
                "case": f"{gname}__n={n}__roundtrip",
                "values": len(src),
                "atom_bytes": len(atom),
                "ssp5_bytes": len(arch),
                "match": ok,
            })
            print(f"  {gname:18s} n={n:<7d} values={len(src):>7d} "
                  f"atom={len(atom):>7d} ssp5={len(arch):>7d} match={ok}")
    rt_path = OUT / "ssp5-even-atom-roundtrip.json"
    rt_path.write_text(json.dumps(rt_rows, indent=2))
    fails = [r for r in rt_rows if not r["match"]]
    if fails:
        print(f"\nROUNDTRIP FAILED on {len(fails)} cases: {[f['case'] for f in fails]}")
        raise SystemExit(1)
    print(f"\nall {len(rt_rows)} roundtrips match. -> {rt_path}")


if __name__ == "__main__":
    main()