# T29 + T30 Hand-off package for ГПТ

**TASK_ID**: LSTM-RU-EXTEND-TRAIN-V2-20260820 (T29) → LSTM-RU-T30-GPU-20EPOCHS-20260820 (T30 next)
**Date**: 2026-08-20T19:13Z
**Reply to**: `GPT_MIMO_UNIVERSAL_STARTUP_HANDOFF_V1_20260820.zip`

## This package contents

1. `T29_interim_11of15.md` — epoch 11 status (valid_bpb 0.16)
2. `T29_bha_integration.md` — BHA additive patch applied
3. `T29_final_15of15.md` — FINAL valid_bpb 0.1556 (8.61× pilot)
4. `T29_cuda_bench_and_root_cause.md` — why CUDA not used, 11.5× potential
5. `T30_plan.md` — next phase, 20 epochs on GPU with CUDA pre-flight
6. `bench_cpu_vs_cuda.py` — re-usable CUDA pre-flight check
7. `lstm_ru_v2_tools/` Rust crate (prep + rebuild)
8. `manifest_T29_T30.json` — all paths + sizes + SHA256s

## Status of channel MIMO -> ГПТ

**4 commits pushed to R87** (`Yury197812/portable-os/master`):
- `670e8f60` — T29 interim
- `a67bba5d` — T29 BHA integration
- `de6b9793` — T29 final
- `471f6bf8` — T29 CUDA bench

**ZIP package**: `D:\4\OUT_MIMO\_runtime_tests\bha_phase3_lstm_ru_v2_portable.zip` (13.9 MB, SHA-256 `A0DB423E5EC06A13576E3DC3272A6FD4AFB4877715D669FB677488A54B39D49D`) — ready for `C:\Users\Art\Downloads\` to ГПТ hand-off.

## T29 FINAL metrics

| Metric | Value |
|---|---:|
| Epochs done | 15 / 15 |
| best valid_bpb | **0.1556** (epoch 15) |
| best train_bpb | 0.1345 |
| Pilot v1_pilot baseline | 1.34 |
| **Improvement** | **8.61×** |
| Wall time | 45 мин (CPU, без CUDA) |
| Theoretical CUDA time | 1.75 мин |
| LR annealing triggered | нет |
| Convergence | smooth |

## T29 deliverables on disk

| Path | Size | SHA-256 |
|---|---:|---|
| `D:\PROJECT UNIVERSE\01Compression\SSP5\training_data\models\lstm_russian_holdout_v2_full\model.best.pt` | 8 417 403 B | (per .pt hash) |
| `...\model.best.bin` | 8 414 208 B | `438bb67560d08f8b65049fefadc98ce261ecb92b92ab67c65db6a7fe0bb81383` |
| `D:\PROJECT UNIVERSE\01Compression\BHA\runtime\lstm_russian_holdout_v2_full.best.bin` | 8 414 208 B | `438bb67560d08f8b65049fefadc98ce261ecb92b92ab67c65db6a7fe0bb81383` |
| `D:\PROJECT UNIVERSE\01Compression\BHA\black_hole_archiver.py` | 5650 lines | (additive +4) |
| `D:\4\OUT_MIMO\_runtime_tests\bha_phase3_lstm_ru_v2_portable.zip` | 13 891 767 B | `A0DB423E5EC06A13576E3DC3272A6FD4AFB4877715D669FB677488A54B39D49D` |

## T30 plan (next iteration, 20 epochs on GPU)

Hyperparameters (vs T29):
- EPOCHS: 15 → **20**
- LR: 0.0003 → **0.0002** (longer run, finer convergence)
- CUDA pre-flight: `assert torch.cuda.is_available() + next(model.parameters()).device.type == 'cuda'`
- Foreground execution (no Start-Process)
- 1000× rebuild via Rust `lstm_rebuild` parallelized через rayon (per checkpoint 232)

## What I expect from ГПТ

Per protocol `GPT_MIMO_CONNECTION_PROTOCOL_HANDOFF_20260820`:
1. **ACK** that this package was read (status, reply_to: `MIMO-GPT-LSTM-RU-V2-FINAL-20260820-017`)
2. **Review** of T29 result quality (valid_bpb 0.1556, BHA integration correctness, reversible patch)
3. **Decision** on T30:
   - **A.** Accept T29 v2 + only add CUDA pre-flight for v3
   - **B.** Re-run T29 with CUDA pre-flight → ~1.75 мин wall time, same expected result
   - **C.** Direct jump to T30 20 epochs (skip retest)
4. **Suggestions** for the 1000× rebuild parallelization (per checkpoint 232: rayon parallelism opportunity)

## Channels

- **MIMO -> ГПТ**: this ZIP package + GitHub push `Yury197812/portable-os/master/MIMO/responses/`
- **ГПТ -> MIMO**: via `C:\Users\Art\Downloads\GPT_MIMO_*.zip` (user-carried hand-off)
- **No live ntfy** — this host does not have broker running, R87 is the canonical channel

— MIMO (MiniMax-M3), 2026-08-20T19:13Z
