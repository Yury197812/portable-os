"""BHA vs Brotli — small-to-medium files (≤80KB), where BHA finishes fast.

BHA on files >1MB hangs in `_compress_best` (path 2817+ `_compress_best` calls).
Stay under 80KB to get measurable BHA results in seconds.
"""
import time, json, subprocess, sys
from pathlib import Path
import brotli

BHA_CLI = r"D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py"
OUT = Path(r"D:\4\bha-codecs\benchmark\bha_vs_brotli_small.json")


def gen_html(target_kb: int) -> bytes:
    """Real-shaped HTML+inline JSON, target size in KB."""
    import random
    rnd = random.Random(11)
    parts = ['<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Sample</title>']
    parts.append('<style>.c{padding:4px;margin:2px}.h{font-weight:bold;color:#06c}</style></head><body>')
    n = target_kb // 4
    cards = []
    for i in range(n):
        cards.append(
            f'<div class="item" data-id="{i:05d}">'
            f'<span class="h">#{i:05d}</span>'
            f'<span class="c">user_{i:05d} активен, role={"admin" if i%3==0 else "editor" if i%3==1 else "viewer"}</span>'
            f'<span class="c">user{i}@example.com</span>'
            f'<span class="c">2026-08-2{i%9}T12:00:0{i%10}Z</span>'
            f'</div>'
        )
    parts.append("".join(cards))
    obj = {"users": [], "v": "1.0.0"}
    for i in range(min(n, 600)):
        obj["users"].append({"id": i, "name": f"user_{i:05d}",
                             "role": ["admin", "editor", "viewer"][i % 3]})
    parts.append('<script>const D=' + json.dumps(obj, ensure_ascii=False) + ';D.users.length;render=()=>D.users.length;</script>')
    parts.append('</body></html>')
    return "".join(parts).encode("utf-8")


def gen_json_blob(target_kb: int) -> bytes:
    """Big repetitive JSON object (zenodo-like)."""
    import random
    rnd = random.Random(13)
    n = target_kb // 2
    obj = {"hits": {"hits": []}, "meta": {"total": n, "page": 1, "version": "1.0.0"}}
    for i in range(n):
        obj["hits"]["hits"].append({
            "id": f"zenodo-{i:08d}",
            "type": ["publication", "dataset", "poster"][i % 3],
            "title": f"Исследование номер {i} в области науки",
            "authors": [
                {"name": f"Author {i:05d}", "affiliation": f"University {i % 50}"},
                {"name": f"Coauthor {i:05d}", "affiliation": f"Institute {i % 30}"},
            ],
            "tags": [f"tag_{i%100}", f"field_{i%40}", f"year_{2020 + (i % 6)}"],
            "doi": f"10.5281/zenodo.{1000000 + i}",
            "files": [{"name": f"file_{i}.pdf", "size": 100000 + i}],
        })
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def gen_markdown(target_kb: int) -> bytes:
    """Markdown docs (Brotli-friendly)."""
    parts = ["# Глава 1. Введение\n\n"]
    para = (
        "Машинное обучение — это раздел искусственного интеллекта, "
        "изучающий методы построения алгоритмов, способных обучаться на данных. "
        "Нейронные сети, деревья решений, метод ближайших соседей и другие подходы "
        "позволяют решать задачи классификации, регрессии и кластеризации. "
    )
    while sum(len(p) for p in parts) < target_kb * 1024:
        parts.append(f"## Раздел {len(parts) // 2}\n\n{para * 5}\n")
    return "\n".join(parts).encode("utf-8")


def brotli_bench(data: bytes, q: int) -> dict:
    t = time.perf_counter()
    c = brotli.compress(data, quality=q)
    pack_ms = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    r = brotli.decompress(c)
    dec_ms = (time.perf_counter() - t) * 1000.0
    assert r == data
    return {"size": len(c), "ratio_pct": round(100 * len(c) / len(data), 4),
            "pack_ms": round(pack_ms, 2), "decode_ms": round(dec_ms, 2)}


def bha_bench_one(path: str, timeout_s: int = 90) -> dict:
    cmd = [sys.executable, BHA_CLI, "benchmark", path, "--json"]
    t = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout {timeout_s}s", "elapsed_ms": round(1000*(time.perf_counter()-t), 1)}
    if proc.returncode != 0:
        return {"error": proc.stderr[-300:]}
    j = json.loads(proc.stdout)
    return j["rows"][0]


def main():
    inputs = []

    # Generated small files (Brotli-friendly domain)
    cases = [
        ("html+json-50k",  gen_html(50),  ".html"),
        ("html+json-80k",  gen_html(80),  ".html"),
        ("json-50k",       gen_json_blob(50),  ".json"),
        ("json-80k",       gen_json_blob(80),  ".json"),
        ("markdown-50k",   gen_markdown(50),  ".md"),
        ("markdown-80k",   gen_markdown(80),  ".md"),
    ]
    for name, data, ext in cases:
        p = Path(r"D:\4\bha-codecs\benchmark") / f"bro_{name}{ext}"
        p.write_bytes(data)
        inputs.append({"path": str(p), "kind": name})

    # Also real small JSON files
    for p in Path(r"D:\4\03_literature_data").glob("*.json"):
        sz = p.stat().st_size
        if 20_000 <= sz <= 80_000:
            inputs.append({"path": str(p), "kind": "real-zenodo"})
            if sum(1 for x in inputs if x["kind"] == "real-zenodo") >= 3:
                break

    rows = []
    print(f"\n{'file':50s} {'in':>9s}  {'BHA':>7s} {'q6':>7s} {'q9':>7s} {'q11':>7s}  BHA% q6% q9% q11%  BHAms q6ms q11ms  verdict")
    for it in inputs:
        data = Path(it["path"]).read_bytes()
        b6 = brotli_bench(data, 6)
        b9 = brotli_bench(data, 9)
        b11 = brotli_bench(data, 11)
        bha = bha_bench_one(it["path"], timeout_s=60)
        if "error" in bha:
            bha_size = -1
            bha_ratio = -1.0
            bha_ms = -1
            verdict = "BHA-FAIL"
        else:
            bha_size = bha["archive_bytes"]
            bha_ratio = bha["ratio_pct"]
            bha_ms = bha["pack_ms"]
            if bha_size < b11["size"]:
                verdict = "BHA<q11"
            elif bha_size < b6["size"]:
                verdict = "BHA<q6"
            else:
                verdict = "brotli"
        rows.append({
            "file": Path(it["path"]).name, "kind": it["kind"],
            "size_in": len(data),
            "bha_size": bha_size, "bha_ratio_pct": bha_ratio, "bha_pack_ms": bha_ms,
            "brotli_q6_size": b6["size"], "brotli_q6_ratio_pct": b6["ratio_pct"], "brotli_q6_pack_ms": b6["pack_ms"],
            "brotli_q9_size": b9["size"], "brotli_q9_ratio_pct": b9["ratio_pct"], "brotli_q9_pack_ms": b9["pack_ms"],
            "brotli_q11_size": b11["size"], "brotli_q11_ratio_pct": b11["ratio_pct"],
            "brotli_q11_pack_ms": b11["pack_ms"], "brotli_q11_decode_ms": b11["decode_ms"],
            "verdict": verdict,
        })
        print(
            f"{Path(it['path']).name:50s} {len(data):>9d}  "
            f"{bha_size:>7d} {b6['size']:>7d} {b9['size']:>7d} {b11['size']:>7d}  "
            f"{bha_ratio:>4.2f} {b6['ratio_pct']:>4.2f} {b9['ratio_pct']:>4.2f} {b11['ratio_pct']:>4.2f}  "
            f"{bha_ms:>5.0f} {b6['pack_ms']:>4.0f} {b11['pack_ms']:>5.0f}  {verdict}"
        )

    valid = [r for r in rows if r["bha_size"] > 0]
    n_bha_wins = sum(1 for r in valid if r["bha_size"] < r["brotli_q11_size"])
    n_bha_lt_q6 = sum(1 for r in valid if r["bha_size"] < r["brotli_q6_size"])
    bha_total = sum(r["bha_size"] for r in valid)
    q6_total = sum(r["brotli_q6_size"] for r in valid)
    q9_total = sum(r["brotli_q9_size"] for r in valid)
    q11_total = sum(r["brotli_q11_size"] for r in valid)
    in_total = sum(r["size_in"] for r in valid)
    bha_total_ms = sum(r["bha_pack_ms"] for r in valid)
    q6_total_ms = sum(r["brotli_q6_pack_ms"] for r in valid)
    q11_total_ms = sum(r["brotli_q11_pack_ms"] for r in valid)

    summary = {
        "files_compared": len(valid),
        "files_total": len(rows),
        "bha_wins_vs_q11": n_bha_wins,
        "bha_wins_vs_q6": n_bha_lt_q6,
        "bha_total_bytes": bha_total,
        "brotli_q6_total_bytes": q6_total,
        "brotli_q9_total_bytes": q9_total,
        "brotli_q11_total_bytes": q11_total,
        "input_total_bytes": in_total,
        "bha_overall_ratio_pct": round(100 * bha_total / in_total, 4),
        "brotli_q6_overall_ratio_pct": round(100 * q6_total / in_total, 4),
        "brotli_q9_overall_ratio_pct": round(100 * q9_total / in_total, 4),
        "brotli_q11_overall_ratio_pct": round(100 * q11_total / in_total, 4),
        "bha_total_pack_ms": round(bha_total_ms, 1),
        "brotli_q6_total_pack_ms": round(q6_total_ms, 1),
        "brotli_q11_total_pack_ms": round(q11_total_ms, 1),
        "bha_size_minus_q11_pct": round(100 * (bha_total - q11_total) / q11_total, 2),
        "bha_size_minus_q6_pct": round(100 * (bha_total - q6_total) / q6_total, 2),
    }
    print("\n=== SUMMARY (Brotli-friendly content, small files) ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out = {"summary": summary, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
