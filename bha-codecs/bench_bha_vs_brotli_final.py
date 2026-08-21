"""BHA vs Brotli — final benchmark, 100-200KB files (where BHA finishes in seconds).

Generates a Brotli-favorable HTML bundle ~200KB. Runs brotli q6/q9 and BHA.
Also tests a real 200KB-file from 03_literature_data.
"""
import time, json, subprocess, sys, os
from pathlib import Path
import brotli

BHA_CLI = r"D:\PROJECT UNIVERSE\01Compression\BHA\bha_cli.py"
OUT = Path(r"D:\4\bha-codecs\benchmark\bha_vs_brotli.json")

# Brotli-friendly content: HTML+inline JSON, ~200KB
TEMPLATE = open(r"D:\4\bha-codecs\benchmark\ssp5-recommender-v4\_tmp_sources\html.html", "rb").read()

def gen_html() -> bytes:
    """Real-shaped HTML, ~200KB, repeating cards + JSON."""
    import random
    rnd = random.Random(7)
    parts = ['<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">']
    parts.append('<title>Brotli specific</title>')
    parts.append('<style>.c{display:block;padding:4px;margin:2px;color:#333;font-family:sans-serif}')
    parts.append('.h{font-weight:bold;color:#06c}.item{border:1px solid #ccc;padding:8px;margin:4px}</style>')
    parts.append('</head><body><div class="container">')
    cards = []
    for i in range(5000):
        cards.append(
            f'<div class="item" data-id="{i:06d}">'
            f'<span class="h">#{i:06d}</span> '
            f'<span class="c">Пользователь user_{i:05d} активен, роль '
            f'{"admin" if i%3==0 else "editor" if i%3==1 else "viewer"}</span>'
            f'<span class="c">email: user{i}@example.com</span>'
            f'<span class="c">время: 2026-08-2{i%9}T12:00:0{i%10}Z</span>'
            f'</div>'
        )
    parts.append("".join(cards))
    obj = {"users": [], "metadata": {"version": "1.0.0", "ts": 1700000000}}
    for i in range(2000):
        obj["users"].append({
            "id": i, "name": f"user_{i:05d}",
            "email": f"user{i}@example.com",
            "role": ["admin", "editor", "viewer"][i % 3],
            "active": i % 2 == 0,
        })
    parts.append('<script>const DATA=' + json.dumps(obj, ensure_ascii=False) + ';')
    parts.append('function render(){return DATA.users.map(u=>u.id).join(",")}render();</script>')
    parts.append('</div></body></html>')
    txt = "".join(parts)
    return txt.encode("utf-8")


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


def bha_bench_one(path: str) -> dict:
    cmd = [sys.executable, BHA_CLI, "benchmark", path, "--json"]
    t = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return {"error": proc.stderr[-500:], "elapsed_ms": round(1000*(time.perf_counter()-t), 1)}
    j = json.loads(proc.stdout)
    return j["rows"][0]


def main():
    # 1) generated HTML ~150-200KB
    html_data = gen_html()
    html_path = r"D:\4\bha-codecs\benchmark\bro_specific_html_200k.html"
    Path(html_path).write_bytes(html_data)
    print(f"Generated HTML: {len(html_data)} bytes -> {html_path}")

    inputs = [{"path": html_path, "kind": "html-inline-json"}]

    # 2) take a medium-size real JSON (200-500KB) from literature
    for p in Path(r"D:\4\03_literature_data").glob("*.json"):
        sz = p.stat().st_size
        if 50_000 <= sz <= 300_000:
            inputs.append({"path": str(p), "kind": "zenodo-meta-json"})
            if len(inputs) >= 5:
                break

    rows = []
    print(f"\n{'file':50s} {'in':>9s}  {'BHA':>8s} {'q6':>8s} {'q9':>8s} {'q11':>8s}  BHA% q6% q9% q11%  BHAms q6ms verdict")
    for it in inputs:
        data = Path(it["path"]).read_bytes()
        b6 = brotli_bench(data, 6)
        b9 = brotli_bench(data, 9)
        b11 = brotli_bench(data, 11)
        bha = bha_bench_one(it["path"])
        if "error" in bha:
            bha_size = -1
            bha_ratio = -1.0
            bha_ms = -1
            verdict = "BHA timeout/error"
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
            "brotli_q6_size": b6["size"], "brotli_q6_ratio_pct": b6["ratio_pct"],
            "brotli_q6_pack_ms": b6["pack_ms"],
            "brotli_q9_size": b9["size"], "brotli_q9_ratio_pct": b9["ratio_pct"],
            "brotli_q9_pack_ms": b9["pack_ms"],
            "brotli_q11_size": b11["size"], "brotli_q11_ratio_pct": b11["ratio_pct"],
            "brotli_q11_pack_ms": b11["pack_ms"],
            "brotli_q11_decode_ms": b11["decode_ms"],
            "verdict": verdict,
        })
        print(
            f"{Path(it['path']).name:50s} {len(data):>9d}  "
            f"{bha_size:>8d} {b6['size']:>8d} {b9['size']:>8d} {b11['size']:>8d}  "
            f"{bha_ratio:>4.2f} {b6['ratio_pct']:>4.2f} {b9['ratio_pct']:>4.2f} {b11['ratio_pct']:>4.2f}  "
            f"{bha_ms:>5.0f} {b6['pack_ms']:>4.0f}  {verdict}"
        )

    valid = [r for r in rows if r["bha_size"] > 0]
    n_bha_wins = sum(1 for r in valid if r["bha_size"] < r["brotli_q11_size"])
    bha_total = sum(r["bha_size"] for r in valid)
    q6_total = sum(r["brotli_q6_size"] for r in valid)
    q9_total = sum(r["brotli_q9_size"] for r in valid)
    q11_total = sum(r["brotli_q11_size"] for r in valid)
    in_total = sum(r["size_in"] for r in valid)
    bha_total_ms = sum(r["bha_pack_ms"] for r in valid)
    q6_total_ms = sum(r["brotli_q6_pack_ms"] for r in valid)

    summary = {
        "files_compared": len(valid),
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
        "bha_wins_vs_q11": n_bha_wins,
        "bha_size_minus_q11_pct": round(100 * (bha_total - q11_total) / q11_total, 2),
    }
    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out = {"summary": summary, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
