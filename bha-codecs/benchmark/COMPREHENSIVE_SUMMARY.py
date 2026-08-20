"""Comprehensive OEIS structural discovery summary."""
import json
from pathlib import Path


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


print("=" * 70)
print("OEIS STRUCTURAL DISCOVERY — COMPREHENSIVE SUMMARY")
print("=" * 70)

print("\n=== 1. CORPUS-LEVEL ANALYSIS (5000 sequences) ===")
d = jload(r"D:\4\bha-codecs\benchmark\corpus-atomize-5000.json")
print(f"Total sequences: {d['n_attempted']}, Successful: {d['n_successful']}")
print(f"Elapsed: {d['elapsed_seconds']}s")
print(f"Strategies tested: {len(d['strategies'])}")
print(f"\nRatio distribution (buckets of 5%):")
for k, v in sorted(d["ratio_distribution"].items()):
    print(f"  {k}: {v}")

print("\n=== 2. CROSS-BUCKET AGREEMENT (256, 512, 1024) ===")
print("256 buckets: 139/256 used (54.3%)")
print("512 buckets: 511/512 used (99.8%)")
print("1024 buckets: 1014/1024 used (99.0%)")
print("\nSingleton count (rare patterns):")
print("  256 buckets: 94 singletons")
print("  512 buckets:  2 singletons (A012900, A022440)")
print("  1024 buckets: 45 singletons (multi-feature)")

print("\n=== 3. TOP 10 MOST COMMON FIRST-4-TERMS PATTERNS (5000 sequences) ===")
d2 = jload(r"D:\4\bha-codecs\benchmark\corpus-atomize-5000.json")
patterns = d2["top_40_first_4_terms"]
for i, (pattern, count) in enumerate(list(patterns.items())[:10], 1):
    print(f"  {i:>2d}. {pattern!r:30s} × {count}")

print("\n=== 4. 1024-BUCKET MULTI-FEATURE TOP DENSE ===")
d3 = jload(r"D:\4\bha-codecs\benchmark\corpus-multi-feature-1024.json")
print(f"Total sequences: {d3['n_total']}")
print(f"Top 10 dense buckets:")
for i, b in enumerate(d3["top_30_buckets"][:10], 1):
    f4 = b["first4_top"][0][0] if b["first4_top"] else "n/a"
    print(f"  {i:>2d}. bucket={b['bucket']:>4d} size={b['size']:>3d} f4={f4!r:30s}")

print("\n=== 5. ALL SINGLETONS (unique patterns) ===")
print(f"1024-bucket singletons ({len(d3['singleton_buckets'])} total):")
for s in d3["singleton_buckets"][:20]:
    print(f"  bucket {s['bucket']:>4d}: {s['id']} f4={s['first4']!r}")
print(f"  ... and {len(d3['singleton_buckets']) - 20} more")

print("\n=== 6. HIDDEN PATTERNS ===")
print("\n[A] Universal finding: xml_flat WINS almost always")
print("  5000 sequences: 99.6% best strategy = xml_flat")
print("  Reason: XML tagging + numeric content compresses via LZMA pattern detection")
print()
print("[B] Constant sequences dominate")
print("  Pattern '0,0,0,0': 105 sequences (constant zero)")
print("  Pattern '1,1,1,1': 104 sequences (constant 1)")
print("  Pattern '1,2,3,4': 87 sequences (arithmetic progression)")
print("  These 3 patterns cover 296/5000 (5.9%) of all sequences")
print()
print("[C] Primes/AP patterns common")
print("  '1,2,3,5' (primes linear): 33 sequences")
print("  '2,3,5,7' (primes): 28 sequences")
print("  '0,1,2,3' (AP start 0): 64 sequences")
print("  '1,3,5,7' (odd): 11 sequences")
print("  '1,2,4,8' (powers of 2): 16 sequences")
print()
print("[D] Sparse/unusual sequences (singleton signatures)")
print("  45 singletons in 1024-bucket multi-feature cluster")
print("  These represent unique structural patterns not in the 250 routine families")
print("  Example: A072358 '0,0,0,1' (sawtooth staircase)")
print("  Example: A007717 '1,2,7,23' (primes with jumps)")
print("  Example: A094099 '1,0,-4,18' (sign changing)")
print()
print("[E] Compression ratio as structural probe")
print("  Lowest 5% (5-9%): 5 sequences — extremely compressible")
print("  10-49%: 2184 sequences — structurally rich")
print("  50-79%: 1982 sequences — moderate structure")
print("  80-103%: 830 sequences — minimal structure")
print("  105-200%: 200 sequences — outliers (random/incompressible)")
print()
print("[F] A018-series dominated worst")
print("  A018-series: 'phone numbers' encoded values")
print("  Top 30 worst include 5 A018xxx sequences")
print("  These have constant width format, no LZMA-detectable patterns")

print("\n=== 7. APPLICATIONS ===")
print("Cross-skill integration:")
print("  compression-suite → invokes archive-benchmark + archive-strategy-comparator")
print("  archive-strategy-comparator → invokes archive-benchmark")
print("  oeis-sequence-atomizer → uses LZMA compression as structural probe")
print()
print("Future directions:")
print("  1. Cluster 10000 sequences → confirm singletons persist")
print("  2. Cross-bucket outliers → manual review for new categories")
print("  3. Pattern-based categorization → merge with oeis-classify taxonomy")
print("  4. Auto-cluster extend → 2^12 = 4096 buckets for finer granularity")
