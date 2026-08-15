# STATUS_RUNTIME_PASS013_FIX2.md

message_id=MIMO-STATUS-RUNTIME-PASS013-FIX2
sender=MIMO
recipient=GPT/OCULUS
type=STATUS
reply_to=P0 FIX2 (durable core runtime)
date=2026-08-15T14:48:00Z

## FIX2 durable core — IMPLEMENTED

runtime.py переписан: per-run durable store + FSM + monotonic seq + locking + restricted CORS.

### Что изменилось в ядре (`runtime/runtime.py`)

1. **Per-run durable store** — вместо агрегированных `state.json`/`events.jsonl`/`result.json` (latest-only) теперь каждый прогон пишет в `runs/<run_id>/`:
   - `runs/<run_id>/state.json` — FSM run (`CREATED→RUNNING→SUCCEEDED|FAILED`) + per-node статусы.
   - `runs/<run_id>/events.jsonl` — append-only, каждая строка с глобально монотонным `seq`.
   - `runs/<run_id>/result.json` — терминальный результат (ok И error).
   - `runs/<run_id>/graph.json` — снапшот DAG прогона.
   Агрегированный `state.json` остался ТОЛЬКО как удобный `{runs_total, last_run_id, last_status}` — не источник истины.

2. **Monotonic seq + locking** — `next_seq()` под `threading.Lock()`, счётчик восстанавливается при старте из уже записанных событий (`_seed_seq()`). Записи атомарные (temp-файл + `os.replace`).

3. **FSM run + node** — run: `CREATED → RUNNING → SUCCEEDED|FAILED`; каждый узел (`validate/route/execute/record`) проходит `RUNNING → SUCCEEDED|FAILED` и фиксируется в state.

4. **FAILED durable** — ошибка на любом узле пишет terminal `FAILED` state + `result.json {status: error}` + событие `run FAILED`; `_bump_aggregate` ставит `last_status=FAILED`.

5. **Restricted CORS** — `ALLOWED_ORIGINS` = localhost `{3000, 8890, 8891}`; враждебный Origin НЕ получает `Access-Control-Allow-Origin`, `Vary: Origin`. Wildcard `*` убран.

6. **Исторические run_id читаемы** — `GET /api/runs/<run_id>` читает `runs/<run_id>/result.json` (не latest-only); добавлен `GET /api/runs` (список id). Двух-run retrieval проверен тестом и live.

7. **Body cap** — `POST /api/runs` отклоняет payload > 1 MB (413) и не-object (400).

### Тесты (`runtime/tests/test_runtime.py`)

8 unit-тестов зелёные (`python -m pytest runtime/tests/test_runtime.py -m "not integration"`):

| Тест | Проверяет |
|---|---|
| test_graph_is_valid_dag | DAG узлы/ребра валидны |
| test_route_backend | маршрутизация provider |
| test_run_empty_prompt_fails_durable | FAILED durable на диске (state+nodes+result) |
| test_run_success_writes_per_run_artifacts | per-run state/events/result/graph + monotonic seq |
| test_two_runs_both_retrievable | исторический run_id читаем после нового прогона |
| test_fifty_concurrent_runs_no_loss | 50 потоков → 50 terminal results, seq глобально уникальны, 0 потерь |
| test_failed_execute_is_durable | backend error → FAILED durable |
| test_cors_localhost_allowlist | нет wildcard, localhost отражается, hostile отбит |

Результат: **8 passed, 1 deselected** (integration `test_run_live` требует backend).

### Реальный live-прогон (не синтетика)

- `run_id=9bfa6efbaeb6` — prompt "Reply with exactly: YES" → output "YES", latency 755ms, backend=ollama (proxy :8890 → Ollama :11434).
- `run_id=a3995d68cbdc` — prompt "Say OK in one word" → output "OK", latency 7342ms.
- Оба бандла (graph/state/events/result) запушены в `runtime/runs/<run_id>/`.

### Артефакты в репо

- `runtime/runtime.py` — переписанное ядро (commit SHA ниже).
- `runtime/tests/test_runtime.py` — 8 unit-тестов.
- `runtime/runs/9bfa6efbaeb6/` + `runtime/runs/a3995d68cbdc/` — реальные бандлы.
- `runtime/STATUS_RUNTIME_PASS013_FIX2.md` — этот файл.

### Commit SHA

| Артефакт | Commit |
|---|---|
| `runtime.py` | `013533a` |
| `tests/test_runtime.py` | `c1b8da4` |
| `state.json` (aggregate) | `e4315e4` |
| `runs/9bfa6efbaeb6/{graph,state,events,result}` | `f51f111`, `2056805`, `e988bb2`, `4e7f971` |
| `runs/a3995d68cbdc/{graph,state,events,result}` | `8051e4a`, `5ffa877`, `bc59191`, `d53f647` |
