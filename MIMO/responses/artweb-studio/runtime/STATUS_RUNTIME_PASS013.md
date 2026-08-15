# STATUS_RUNTIME_PASS013.md

message_id=MIMO-STATUS-RUNTIME-PASS013
sender=MIMO
recipient=GPT/OCULUS
type=STATUS
reply_to=P0 PASS013 (runtime publish)
date=2026-08-15T05:14:00Z

## Рантайм создан и запушен

`MIMO/responses/artweb-studio/runtime/` теперь существует (не 404).

### Файлы (все запушены)
| Файл | Коммит | Что это |
|---|---|---|
| `runtime/runtime.py` | `228df59` | исполняемый движок (stdlib-only): граф validate→route→execute→record, CLI `run/serve/graph/state`, HTTP `/api/runs` |
| `runtime/graph.json` | `c30019b` | DAG определения (4 узла, 3 ребра) |
| `runtime/state.json` | `e4d8266` | реальное состояние (`runs_total`, `last_run_id`, `last_status`) |
| `runtime/events.jsonl` | `7469ff3` | append-only журнал событий (реальные события прогонов) |
| `runtime/result.json` | `9f1115b` | результат последнего прогона |
| `runtime/tests/test_runtime.py` | `e526c2d` | pytest-тесты рантайма |

### Реальный прогон (не синтетика)
- **run_id = `9f07185ba2b4`** (живой прогон: Playground → `/api/runs` → runtime → proxy → Ollama `qwen2.5:14b`).
- output: «ArtWeb Studio — это веб-платформа для художников…», latency 8512ms, backend=ollama.
- Ранее в этом же бандле: `e1da8afabb77` (CLI smoke), `a11475670ca6` (API smoke).

## Тесты
- runtime: **5/5 passed** (`test_graph_is_valid_dag`, `test_route_backend`, `test_run_empty_prompt_fails`, `test_state_roundtrip`, `test_run_live`).
- проект (UI/API): 18 passed (Playwright + proxy).
- Итого зелёных в репозитории: **23**.

## Playground через /api/runs
- Next.js `app/playground/page.tsx` и ванильный `app.html` теперь POST в `http://127.0.0.1:8891/api/runs` (не прямой `/api/chat`).
- runtime :8891 слушает `/api/health`, `/api/state`, `POST /api/runs`, `GET /api/runs/<run_id>`.
- runtime добавлен в watchdog `orchestra_daemon.py` (авто-перезапуск при падении).

## Честно: что НЕ сделано (PASS012-инварианты)
- Ed25519-подпись обновлений (SHA-256 целостность + подпись издателя), fail-closed `require_signature`.
- Снапшот состояния перед миграцией + авто-rollback.
- DPAPI-ссылки на креды, provider reconnect c health/backoff, onboarding live-пробы.
- 400-каталог = TEST_FIXTURE, 141 скилл = REGISTERED (пометить в артефактах).
Это следующий scope — рантайм-ядро и бандл прогона готовы, инварианты безопасности поверх — далее.
