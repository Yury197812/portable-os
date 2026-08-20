"""Investigation D: Atomize compressed data, then re-atomize.

Tests whether recursive atomization of LZMA streams reveals additional
patterns. The hypothesis: if LZMA output still has structural patterns
in the metadata blocks (e.g., filenames, sizes, metadata), then re-atomizing
could capture them and yield better compression.

Pipeline: data -> LZMA(plain) -> atomize -> LZMA -> atomize -> LZMA
         -> atomize -> LZMA -> ... (iterate)
"""
import sys
import lzma
import io
import csv
import re
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def atomize_csv(data):
    try:
        text = data.decode("utf-8", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or len(rows) < 2:
            return data
        out = io.BytesIO()
        out.write(f"FORMAT=CSV\nROWS={len(rows)-1}\nCOLS={len(rows[0])}\n".encode())
        for h in rows[0]:
            out.write(f"H={h}\n".encode())
        cols = list(zip(*rows[1:]))
        for col in cols:
            unique = list(dict.fromkeys(col))
            cn = f"COL{cols.index(col)}"
            out.write(f"{cn}_UNIQUE={len(unique)}\n".encode())
            for idx, v in enumerate(unique):
                out.write(f"{cn}_{idx}={v}\n".encode())
        out.write(b"DICT_END\n")
        n = len(cols[0]) if cols else 0
        for r in range(n):
            row = []
            for col in cols:
                unique = list(dict.fromkeys(col))
                row.append(str(unique.index(col[r])))
            out.write(",".join(row).encode() + b"\n")
        return out.getvalue()
    except Exception:
        return data


def atomize_lzma(data):
    """Atomize LZMA stream - extract property/header structure."""
    try:
        # LZMA files start with header
        text = data.decode("latin-1", errors="replace")[:2000]
    except Exception:
        return data
    out = io.BytesIO()
    out.write(f"FORMAT=LZMA\nSIZE={len(data)}\nHEADER=\"{text[:500]}\"\n".encode())
    # count bytes
    hist = [0] * 256
    for b in data[:65536]:
        hist[b] += 1
    out.write(b"BHIST=" + b",".join(str(x).encode() for x in hist) + b"\n")
    out.write(b"DATA_BEGIN\n")
    out.write(data[:65536])
    out.write(b"\n")
    return out.getvalue()


def lzma_compress(data, level=9):
    return lzma.compress(data, format=lzma.FORMAT_XZ,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": level}],
                          check=-1)


def is_text(data):
    sample = data[:8192]
    text_chars = sum(1 for c in sample if 0x20 <= c <= 0x7e or c in (0x09, 0x0a, 0x0d))
    return text_chars / len(sample) >= 0.95 if sample else True


def is_csv(data):
    sample = data[:8192]
    return is_text(sample) and b"," in sample and b"\n" in sample and sample.split(b"\n", 1)[0].count(b",") >= 2


def main():
    files = [
        "data_csv_100k.csv", "log_high_entropy_tail_512k.log",
        "binary_header_text_payload.log", "ini_config_128k.ini",
    ]
    print("=== Investigation D: Recursive atomization of LZMA streams ===\n")
    for fname in files:
        path = CORPUS / fname
        if not path.exists():
            continue
        data = path.read_bytes()
        if len(data) > 5_000_000:
            continue
        if is_csv(data):
            A1 = atomize_csv(data)
        else:
            A1 = b"<seq>" + data + b"</seq>"
        L1 = lzma_compress(data, 9)
        AL1 = atomize_csv(L1) if not is_text(L1[:1000]) else b"<seq>" + L1 + b"</seq>"
        L2 = lzma_compress(A1, 9)
        AL2 = atomize_lzma(L1)
        L3 = lzma_compress(AL1, 9)
        A3 = atomize_lzma(L2)
        L4 = lzma_compress(A3, 9)
        A4 = atomize_lzma(L3)
        L5 = lzma_compress(A4, 9)
        print(f"=== {fname} ===")
        print(f"  Original: {len(data):>10d}")
        print(f"  LZMA(plain)        L1: {len(L1):>10d}  ratio: {len(L1)/len(data)*100:.2f}%")
        print(f"  LZMA(atm)          L2: {len(L2):>10d}  ratio: {len(L2)/len(data)*100:.2f}%")
        print(f"  LZMA(atm2)         L3: {len(L3):>10d}  ratio: {len(L3)/len(data)*100:.2f}%")
        print(f"  LZMA(atm3)         L4: {len(L4):>10d}  ratio: {len(L4)/len(data)*100:.2f}%")
        print(f"  LZMA(atm4)         L5: {len(L5):>10d}  ratio: {len(L5)/len(data)*100:.2f}%")
        print(f"  LZMA2(atm(plain)) AL1->L2 best? {len(L2)<len(L1)} (LZMA2 of atom better than LZMA alone)")
        print(f"  Diminishing returns? L3 vs L2: {len(L3)-len(L2):+5d} bytes, L4 vs L3: {len(L4)-len(L3):+5d}, L5 vs L4: {len(L5)-len(L4):+5d}")
        print()


if __name__ == "__main__":
    main()
