"""Test pp_bcj_x86 and pp_dedup_substring gates on all 50 BHA files."""
import sys, time
from pathlib import Path
# Resolve bha_core.* imports. Project root is the parent of bha_core/.
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, r'D:\PROJECT UNIVERSE\01Compression\BHA')

import bha_core.bha_parallel as bha_parallel
from bha_core.bha_parallel import worker_gate

CORPUS = Path(r'D:\PROJECT UNIVERSE\01Compression\BHA\TEST')

# Smaller files only to keep wall clock reasonable
files = sorted([p for p in CORPUS.iterdir() if p.is_file() and p.suffix != ".json" and p.stat().st_size < 2_000_000])
n = len(files)

print(f"file                                in       lzma_fallback  pp_dedup  pp_bcj    pp_zero    best_pp")
print("-" * 110)
wins_pp_dedup = wins_pp_bcj = 0
for p in files:
    data = p.read_bytes()
    sizes = {}
    for gate in ['pp_dedup_substring', 'pp_bcj_x86', 'pp_zero_extend', 'lzma_fallback']:
        result = worker_gate((gate, data, str(p)))
        if result is None:
            sizes[gate] = None
        else:
            _, sz, _ = result
            sizes[gate] = sz
    pp_sizes = {k: v for k, v in sizes.items() if v is not None and k.startswith('pp_')}
    best_pp = min(pp_sizes, key=pp_sizes.get) if pp_sizes else None
    if best_pp == 'pp_dedup_substring': wins_pp_dedup += 1
    if best_pp == 'pp_bcj_x86': wins_pp_bcj += 1
    print(f"{p.name[:35]:35s} {len(data):>8d}  "
          f"{sizes.get('lzma_fallback', 'N/A'):>13}  "
          f"{sizes.get('pp_dedup_substring', 'N/A') or '-':>8}  "
          f"{sizes.get('pp_bcj_x86', 'N/A') or '-':>7}  "
          f"{sizes.get('pp_zero_extend', 'N/A') or '-':>8}  "
          f"{(best_pp or '-'):>20s}")

print(f"\n{n} files tested")
print(f"pp_dedup_substring wins as best pp: {wins_pp_dedup}")
print(f"pp_bcj_x86 wins as best pp:         {wins_pp_bcj}")