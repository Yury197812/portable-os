"""Investigation B: Map all 50 corpus files through 6 pipelines, derive real rules.

Now that we know 9/10 cases favor plain LZMA, let's check on larger sample.
For each file, compute ratios for all 6 pipelines and find the EXACT conditions
where atomize+compress helps.

Sample: 50 files from BHA corpus.
"""
import sys
import json
import io
import csv
import lzma
from pathlib import Path

CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")


def is_text(data):
    sample = data[:8192]
    text_chars = sum(1 for c in sample if 0x20 <= c <= 0x7e or c in (0x09, 0x0a, 0x0d))
    return text_chars / len(sample) >= 0.95 if sample else True


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


def lzma_compress(data, level=9):
    return lzma.compress(data, format=lzma.FORMAT_XZ,
                          filters=[{"id": lzma.FILTER_LZMA2, "preset": level}],
                          check=-1)


def main():
    files = sorted([p for p in CORPUS.glob("*") if p.is_file() and p.name != "manifest.json"])
    print(f"=== 6-pipeline matrix for {len(files)} corpus files ===")
    results = []
    for path in files:
        try:
            data = path.read_bytes()
        except Exception:
            continue
        if len(data) > 5_000_000:
            continue
        original = len(data)
        sample = data[:8192]
        if is_text(sample) and b"," in sample and b"\n" in sample:
            first_line = sample.split(b"\n", 1)[0]
            if first_line.count(b",") >= 2:
                atm = atomize_csv(data)
            else:
                atm = b"<seq>" + data + b"</seq>"
        else:
            atm = b"<seq>" + data + b"</seq>"
        plain = lzma_compress(data, 9)
        atm_lzma = lzma_compress(atm, 9)
        lzma_atm = atomize_csv(plain)
        lzma_atm_lzma = lzma_compress(lzma_atm, 9)
        lzma_lzma = lzma_compress(plain, 9)
        sizes = {
            "A": len(atm),
            "plain": len(plain),
            "A+L": len(atm_lzma),
            "L+A": len(lzma_atm),
            "L+A+L": len(lzma_atm_lzma),
            "L+L": len(lzma_lzma),
        }
        best = min(sizes, key=sizes.get)
        results.append({"file": path.name, "size": original, **sizes, "best": best})
    print(f"{'file':45s}  {'size':>9s} | {'plain':>7s} {'A':>7s} {'A+L':>7s} {'L+A':>7s} {'L+A+L':>7s} {'L+L':>7s} {'best':>7s}")
    for r in results:
        print(f"  {r['file']:43s}  {r['size']:>9d} | {r['plain']:>7d} {r['A']:>7d} {r['A+L']:>7d} {r['L+A']:>7d} {r['L+A+L']:>7d} {r['L+L']:>7d} {r['best']:>7s}")
    best_count = {}
    for r in results:
        best_count.setdefault(r["best"], 0)
        best_count[r["best"]] += 1
    print("\nBest pipeline distribution:")
    for k, v in sorted(best_count.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} files ({v/len(results)*100:.1f}%)")
    out_path = Path(r"D:\4\bha-codecs\benchmark\all-files-6-pipeline.json")
    out_path.write_text(json.dumps({
        "n_files": len(results),
        "best_distribution": best_count,
        "results": results,
    }, indent=2))
    print(f"\nresults: {out_path}")


if __name__ == "__main__":
    main()
