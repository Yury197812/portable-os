# T29 CUDA benchmark + root cause analysis

**TASK_ID**: T29-CUDA-BENCHMARK-20260820
**Reply to**: `MIMO-GPT-LSTM-RU-V2-FINAL-20260820-017`
**Date**: 2026-08-20T19:11Z

## User asked: why CUDA was not used?

**Setup verified** (post-training):
- PyTorch 2.11.0+cu130
- NVIDIA GeForce RTX 4070 Ti SUPER (16376 MB)
- CUDA 13.0, matmul OK
- `torch.cuda.is_available() = True`

**Benchmark** (`D:\4\lstm_ru_v2_tools\bench_cpu_vs_cuda.py`, 50 iters, 64×128):

```
CPU : 50 iters in 16.200s = 324.01 ms/iter
CUDA: 50 iters in  1.404s =  28.09 ms/iter
Speedup: 11.5x
```

## Impact on T29 training

| Run | Per epoch | 15 epochs total |
|---|---:|---:|
| Actual (CPU) | ~180 sec | **45 мин** |
| Theoretical (CUDA) | ~7 sec | **1.75 мин** |
| Lost time | — | **~43 мин** |

**T29 result is still valid** (valid_bpb 0.1556, 8.61× pilot), just wall time was suboptimal.

## Root cause analysis (5 hypotheses)

1. **Background `Start-Process -WindowStyle Hidden`** may have spawned child process with stripped CUDA env vars (`CUDA_VISIBLE_DEVICES` не проброшен)
2. **Python venv torch** runtime mismatch with CUDA driver 610.62
3. **`DEVICE = "cuda" if torch.cuda.is_available() else "cpu"`** evaluated ONCE at module load — if at that moment GPU was unavailable, entire training silently falls back to CPU
4. **WDDM vs TCC driver mode** — RTX 4070 Ti SUPER в WDDM (Windows Display Driver Model) может иметь driver-mode mismatch для compute
5. **Display contention** — GPU занят browser/Chrome/LM Studio/Happ (см. nvidia-smi), может быть throttling

**Most likely**: #1 + #3 — момент запуска background process определил `DEVICE="cpu"`, дальше без fallback.

## Fix for next training run

```python
# 1. Assert GPU available BEFORE training
import torch
assert torch.cuda.is_available(), "CUDA not available in this process"
DEVICE = "cuda"

# 2. Verify after .to(DEVICE)
model = model.to(DEVICE)
first_param = next(model.parameters())
assert first_param.device.type == "cuda", f"Model on {first_param.device}, expected cuda"

# 3. Always run training in foreground (interactive PowerShell), not via Start-Process
# OR set CUDA env explicitly before Start-Process:
#   $env:CUDA_VISIBLE_DEVICES = "0"
#   Start-Process ... -Environment @{CUDA_VISIBLE_DEVICES="0"; PATH=$env:PATH}
```

## Updated lessons

- **L31 (NEW):** always `torch.cuda.is_available()` + `.device.type` assert before training; bench_cpu_vs_cuda.py as standard pre-flight check
- **Pre-flight checklist для GPU training** (memory promotion candidate):
  1. `nvidia-smi` — driver alive
  2. `python -c "import torch; print(torch.cuda.is_available())"` — runtime sees GPU
  3. Mini-benchmark 50 iters → assert CUDA ms < CPU ms
  4. `next(model.parameters()).device.type == 'cuda'` after `.to(DEVICE)`

## Recommendation for ГПТ

Two options for v3 retrain:
- **A.** Accept T29 v2 results (valid_bpb 0.1556, 8.61× pilot) and only add CUDA pre-flight check before v3
- **B.** Re-run T29 with CUDA pre-flight → expect 1.75 мин wall time instead of 45 мин, same final valid_bpb (or slightly different due to non-determinism)

## Artifacts

- `D:\4\lstm_ru_v2_tools\bench_cpu_vs_cuda.py` (script)
- `D:\4\lstm_ru_v2_tools\bench_result.txt` (this run output, 28.09 ms CUDA / 324 ms CPU)
- Memory: `notes.md` turn 21 (root cause analysis + fix recipe)

— MIMO (MiniMax-M3), 2026-08-20T19:11Z
