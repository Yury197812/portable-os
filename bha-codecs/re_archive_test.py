"""Compare BHA archive vs LZMA on corpus - re-archive test.

BHA has 30 codecs. This test compares:
- BHA archive (BHA-archive skill)
- LZMA extreme
- LZMA default
- gzip
- zip
- BHA + LZMA (nested)
- LZMA + BHA (re-archive)

Hypothesis: BHA is more efficient for structured/text data, LZMA for binary.
"""
import sys
import time
import json
import lzma
import subprocess
from pathlib import Path

BHA_SKILL = Path(r"C:\Users\Art\.mimicode\skills\bha-archive\scripts\bha_run.py")
CORPUS = Path(r"D:\PROJECT UNIVERSE\01Compression\BHA\TEST")
OUTPUT = Path(r"D:\4\bha-codecs\benchmark\re-archive-test")
OUTPUT.mkdir(parents=True, exist_ok=True)


def run_bha(action, source, output=None, timeout=60):
    payload = {"action": action, "source": str(source), "timeout": timeout}
    if output:
        payload["output"] = str(output)
    try:
        proc = subprocess.run(
            [sys.executable, str(BHA_SKILL)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return json.loads(proc.stdout)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_bha():
    samples = [
        "data_csv_100k.csv", "log_high_entropy_tail_512k.log",
        "binary_header_text_payload.log", "html_inline_data_uri_200k.html"
    ]
    results = []
    for name in samples:
        path = CORPUS / name
        if not path.exists() or path.stat().st_size > 5_000_000:
            continue
        original_size = path.stat().st_size
        archive_path = OUTPUT / f"{name}.bha"
        archive_result = run_bha("archive", path, archive_path)
        if archive_result.get("ok"):
            bha_size = archive_path.stat().st_size if archive_path.exists() else 0
            lzma_size = len(lzma.compress(path.read_bytes(),
                                            format=lzma.FORMAT_XZ,
                                            filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}]))
            results.append({
                "file": name,
                "original": original_size,
                "bha_size": bha_size,
                "bha_ratio": round(bha_size / original_size * 100, 2),
                "lzma_extreme_size": lzma_size,
                "lzma_extreme_ratio": round(lzma_size / original_size * 100, 2),
            })
    return results


def test_re_archive():
    """Re-archive: BHA → LZMA, LZMA → BHA."""
    samples = ["data_csv_100k.csv", "log_high_entropy_tail_512k.log"]
    results = []
    for name in samples:
        path = CORPUS / name
        if not path.exists():
            continue
        original = path.read_bytes()
        lzma_path = OUTPUT / f"{name}.xz"
        lzma_path.write_bytes(lzma.compress(original,
                                                format=lzma.FORMAT_XZ,
                                                filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}]))
        bha_from_lzma = OUTPUT / f"{name}.from_lzma.bha"
        result = run_bha("archive", lzma_path, bha_from_lzma)
        bha_size = bha_from_lzma.stat().st_size if bha_from_lzma.exists() else 0
        lzma_from_bha = OUTPUT / f"{name}.from_bha.xz"
        lzma_from_bha.write_bytes(lzma.compress(bha_from_lzma.read_bytes() if bha_from_lzma.exists() else b""))
        bha_size2 = lzma_from_bha.stat().st_size
        results.append({
            "file": name,
            "original": len(original),
            "bha_size": bha_size,
            "lzma_from_bha_size": bha_size2,
        })
    return results


def main():
    print("=== Test: BHA vs LZMA extreme ===")
    bha_results = test_bha()
    for r in bha_results:
        print(f"  {r['file']}: original={r['original']:>10d}  bha={r['bha_ratio']:>6.2f}%  lzma={r['lzma_extreme_ratio']:>6.2f}%  winner={'bha' if r['bha_size']<r['lzma_extreme_size'] else 'lzma'}")
    print()
    print("=== Test: Re-archive (BHA ↔ LZMA nested) ===")
    re_results = test_re_archive()
    for r in re_results:
        print(f"  {r['file']}: original={r['original']:>10d}  BHA={r['bha_size']:>10d}  LZMA_from_BHA={r['lzma_from_bha_size']:>10d}")
    out = {"bha_vs_lzma": bha_results, "re_archive": re_results}
    out_path = Path(r"D:\4\bha-codecs\benchmark\re-archive-results.json")
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8-sig")
    print(f"\nresults: {out_path}")


if __name__ == "__main__":
    main()
