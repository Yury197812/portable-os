"""Investigation E: BHA archive (SSP5) + atomize + LZMA combination.

Tests whether BHA's internal codec captures additional structure beyond
plain LZMA, and whether the combination with atomize gives additional gain.

Pipelines tested:
- plain LZMA
- BHA archive (SSP5 + structural encoding)
- atomize + LZMA (already tested)
- BHA + LZMA (BHA then LZMA on BHA output)
- BHA + atomize (BHA then atomize)
- LZMA + BHA (LZMA then BHA - BHA on compressed)
- BHA + LZMA + atomize (BHA + LZMA then atomize)
"""
import sys
import lzma
import io
import csv
import json
import subprocess
from pathlib import Path

BHA_SKILL = Path(r"C:\Users\Art\.mimicode\skills\bha-archive\scripts\bha_run.py")
CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
OUTPUT = Path(r"D:\4\bha-codecs\benchmark\bha-combination")
OUTPUT.mkdir(parents=True, exist_ok=True)


def invoke_bha(action, source, output):
    payload = {"action": action, "source": str(source), "timeout": 60}
    if output:
        payload["output"] = str(output)
    proc = subprocess.run(
        [sys.executable, str(BHA_SKILL)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": "bha_failed", "stderr": proc.stderr}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "non_json", "stdout": proc.stdout[:200]}


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


def is_csv(data):
    sample = data[:8192]
    return b"," in sample and b"\n" in sample and sample.split(b"\n", 1)[0].count(b",") >= 2


def main():
    test_files = [
        "data_csv_100k.csv", "log_high_entropy_tail_512k.log",
        "binary_header_text_payload.log", "ini_config_128k.ini",
        "data_json_100k.json", "log_long_repeated_512k.log",
    ]
    print("=== Investigation E: BHA + LZMA + atomize combinations ===\n")
    print(f"{'file':40s}  {'orig':>9s} | {'plain':>7s} | {'BHA':>7s} | {'A+L':>7s} | {'BHA+L':>7s} | {'L+BHA':>7s} | {'BHA+atm':>7s} | {'best':>15s}")
    results = []
    for fname in test_files:
        path = CORPUS / fname
        if not path.exists():
            continue
        data = path.read_bytes()
        original_size = len(data)
        plain = lzma_compress(data, 9)
        bha_path = OUTPUT / f"{fname}.bha"
        bha_result = invoke_bha("archive", path, bha_path)
        bha_size = bha_path.stat().st_size if bha_path.exists() else 0
        bha_compressed_size = bha_result.get("stdout", "").split("\n")[0].split()[-1] if bha_result.get("ok") else "?"
        if is_csv(data):
            atomized = atomize_csv(data)
        else:
            atomized = b"<seq>" + data + b"</seq>"
        atm_lzma = lzma_compress(atomized, 9)
        bha_lzma = lzma_compress(open(bha_path, "rb").read(), 9) if bha_path.exists() else b""
        lzma_bha_path = OUTPUT / f"{fname}.lzma_then.bha"
        lzma_bha_result = invoke_bha("archive", OUTPUT / fname, lzma_bha_path)
        lzma_bha_size = lzma_bha_path.stat().st_size if lzma_bha_path.exists() else 0
        if bha_path.exists():
            bha_data = open(bha_path, "rb").read()
            bha_atm = bha_data
            if is_csv(bha_data[:8192]):
                bha_atm = atomize_csv(bha_data)
            else:
                bha_atm = b"<seq>" + bha_data + b"</seq>"
            bha_atm_lzma = lzma_compress(bha_atm, 9)
        else:
            bha_atm_lzma = b""
        sizes = {
            "plain": len(plain),
            "BHA": bha_size,
            "A+L": len(atm_lzma),
            "BHA+L": len(bha_lzma),
            "L+BHA": lzma_bha_size,
            "BHA+atm": len(bha_atm_lzma),
        }
        best = min((k, v) for k, v in sizes.items() if v > 0)
        best_name, best_size = best
        results.append({"file": fname, "size": original_size, **sizes, "best": best_name})
        print(f"  {fname:38s}  {original_size:>9d} | "
              f"{sizes['plain']:>7d} | "
              f"{sizes['BHA']:>7d} | "
              f"{sizes['A+L']:>7d} | "
              f"{sizes['BHA+L']:>7d} | "
              f"{sizes['L+BHA']:>7d} | "
              f"{sizes['BHA+atm']:>7d} | {best_name:>15s}")
    best_count = {}
    for r in results:
        best_count.setdefault(r["best"], 0)
        best_count[r["best"]] += 1
    print(f"\nBest pipeline distribution (n={len(results)}):")
    for k, v in sorted(best_count.items(), key=lambda x: -x[1]):
        print(f"  {k:10s}: {v} files")
    out_path = OUTPUT / "combination-results.json"
    out_path.write_text(json.dumps({
        "n_files": len(results),
        "best_distribution": best_count,
        "results": results,
    }, indent=2))
    print(f"\nresults: {out_path}")


if __name__ == "__main__":
    main()
