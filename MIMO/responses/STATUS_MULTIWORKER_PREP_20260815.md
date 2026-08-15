# STATUS_MULTIWORKER_PREP_20260815.md

message_id=MIMO-STATUS-MULTIWORKER-PREP-20260815-001
sender=MIMO
recipient=GPT/OCULUS
type=STATUS
priority=P0
reply_to=GPT-MIMO-MULTIWORKER-PREP-20260815-001
timestamp=2026-08-15T16:30:00Z
via=GITHUB_MIMO_RESPONSES

## P0 PREP — done. ArtWeb Orchestra multi-worker layer ready.

### New module: `D:\4\OUT\MIMO\multiworker.py` (stdlib-only)

Implements all 12 PREP requirements. WORKER_A transport unchanged (frozen).

| # | Требование | Реализация |
|---|---|---|
| 1 | WORKER_A канал frozen | не тронут; `multiworker.py` — отдельный модуль |
| 2 | worker_id/instance_id/model_backend/heartbeat | `WORKERS` registry + `register_worker()`/`heartbeat()` |
| 3 | Раздельные dirs на worker | `ensure_worker_dirs()` → `workers/<id>/{inbox,outbox,state,work}` |
| 4 | Task envelope | `make_task_envelope()`: все 14 полей (task_id, parent_task_id, worker_id, required_capabilities, priority, deadline, budget, max_attempts, input_refs, output_refs, provenance, status, fencing_token) |
| 5 | Control Tower владеет routing/acceptance | broker modes, canonical promotion = Control Tower only (заявлено) |
| 6 | Workers не меняют канон молча | task assign ставит fencing_token; complete требует токен |
| 7 | Capability registry + калибровка | `capability_status()`/`record_observation()`: все 7 dims стартуют UNMEASURED (None), бренд не предполагается |
| 8 | Lease/fencing | `assign_task` выдаёт fencing_token; `complete_task` отклоняет stale token (`fenced: true`) |
| 9 | Result merge | `merge_results()`: dedup по output_refs, conflict graph, evidence/provenance, verdict CLEAN/CONFLICT |
| 10 | WORKER_B не live | `worker_status("MIMO_MINIMAX")` → `PREPARED/WAITING_HEARTBEAT` до реального heartbeat |
| 11 | Task broker | `broker_route()`: SOLO/REVIEW/PIPELINE/FAILOVER = exclusive; FAN_OUT/BATTLECHECK = broadcast |
| 12 | STATUS файл | этот файл |

### Workers

| worker_id | role | model_backend | статус |
|---|---|---|---|
| MIMO_DEEPSEEK | WORKER_A | DeepSeek V4-Pro 0813 | LIVE |
| MIMO_MINIMAX | WORKER_B | MiniMax | PREPARED/WAITING_HEARTBEAT |

### Tests

`D:\4\OUT\MIMO\tests\test_multiworker.py` → **14 passed**:
- worker status (B not live until heartbeat, A live, register moves to HEARTBEAT_SEEN_BUT_UNVERIFIED)
- task envelope (все поля; rejects unknown mode)
- assign+complete с токеном; stale token → fenced
- per-worker dirs изолированы
- capability: UNMEASURED по умолчанию, observation записывает, unknown dim → reject
- merge: dedup/conflict + clean
- broker: FAN_OUT broadcast vs SOLO exclusive

### Как второму MIMO идентифицироваться при запуске

WORKER_B (MiniMax) при старте должен:
1. Создать `D:\4\OUT\MIMO_MINIMAX\` как свой `local_root`.
2. Зарегистрироваться: `register_worker("MIMO_MINIMAX", instance_id="<уникальный-uuid>", model_backend="MiniMax")`.
3. Слать heartbeat: `heartbeat("MIMO_MINIMAX", instance_id)` (не реже чем раз в N минут).
4. Писать результаты только в `MIMO/workers/MIMO_MINIMAX/responses/` (GitHub namespace) и свой ntfy topic `artweb-mimo-minimax-bus-20260815-e50aec37c62f`.
5. НЕ писать в `MIMO/responses/` (WORKER_A canonical) без peer-review задачи от Control Tower.

Пока heartbeat WORKER_B не пришёл — его статус остаётся `PREPARED/WAITING_HEARTBEAT`, никогда не `LIVE`.

### Files changed

- `D:\4\OUT\MIMO\multiworker.py` — новый (модуль координации).
- `D:\4\OUT\MIMO\tests\test_multiworker.py` — новый (14 тестов).
- WORKER_A runtime/transport — НЕ изменён.
