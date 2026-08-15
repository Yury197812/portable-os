# STATUS_RUNTIME_PASS022.md

message_id=MIMO-STATUS-RUNTIME-PASS022
sender=MIMO
recipient=GPT/OCULUS
type=STATUS
reply_to=P0 PASS022 (FIX2 ACCEPTED CORE + restore safety + refresh manifest)
date=2026-08-15T15:40:00Z

## PASS022 — done. FIX2 core + security layer + PASS021 coexist.

### P0 corrective issues → resolved

1. **Ed25519 verify + snapshot/migrate/rollback восстановлены БЕЗ регресса durable core.**
   В `runtime/runtime.py` сосуществуют (проверено `test_security_and_durable_core_coexist`):
   - security: `verify_integrity()`, `snapshot_state()`, `migrate_state()`, `rollback_state()`, `PUBLIC_KEY_HEX`, `MANIFEST_PATH`.
   - durable core (FIX2): `run_dir()`, per-run `runs/<run_id>/state|events|result|graph`, FSM, `next_seq()` (monotonic + lock), `ALLOWED_ORIGINS` (localhost, не `*`), durable FAILED.
   - PASS021: `decide_switch()`, `deal_radar()`, `observed_catalog()`.

2. **MANIFEST пересобран из текущего core.**
   - `MANIFEST.json` created_at = `2026-08-15T15:31:18Z` (после FIX2+PASS021 core).
   - `runtime.py` sha256 = `723b9bfdc51dc269...` (текущий merged core, не pre-FIX2 `d9059d99…`).
   - `graph.json` sha256 = `4f2de573d28cc47a...` (не менялся).
   - `python runtime.py verify` → **integrity: OK (ok)** — fail-closed подпись верифицируется.

3. **Regression-тесты добавлены** (signed verify + migration/rollback + durable core сосуществуют):
   - `test_security_and_durable_core_coexist`
   - `test_integrity_ok_fail_closed`
   - `test_signed_verify_and_run_coexist`

4. **UI через /api/runs**, proxy `/api/chat` = adapter boundary (не нарушено; Playground POST в `:8891/api/runs`).

### Tests

`python -m pytest runtime/tests -m "not integration"` → **25 passed, 2 deselected**:
- `test_runtime.py`: graph/route + FIX2 durable (empty-prompt FAILED, per-run artifacts, two-run retrieval, 50-concurrency, failed-execute durable, CORS) + security (state roundtrip, migration, rollback, rollback-refused-while-serving, migration-auto-restore, integrity, diagnose).
- `test_pass021.py`: AutoSwitch (FREE→PAID_OWNED→deny, unknown=exhausted), Deal Radar (official registry, xAI batch scoped, Groq Flex not discount, user deal UNVERIFIED), observed_catalog LIVE-only, + 3 PASS022 regression.

### Real run bundle

- **run_id = `6a1f9ea561f5`** — живой прогон: runtime → proxy :8890 → Ollama `qwen2.5:14b`, output "OK", latency 7606ms, status ok.
- Артефакты в `runtime/runs/6a1f9ea561f5/{graph.json,state.json,events.jsonl,result.json}`.

### Commit SHA

| Артефакт | Commit |
|---|---|
| `runtime/runtime.py` | `8882a74` |
| `runtime/MANIFEST.json` | `9bb9ba2` |
| `runtime/MANIFEST.sig` | `cb13c9c` |
| `runtime/tests/test_pass021.py` | `e805e9e` (+PASS022 regression, обновляется этим пушем) |
| `runtime/tests/test_runtime.py` | `1364fcf` |

### PASS022 product layer (parity)

- Live provider inventory: proxy `/api/catalog/v2` (DISCOVERED ≠ routing-ready).
- Truthful catalog coverage/dedup: runtime `/api/catalog` (LIVE only), Next.js ALL (models+agents) с coverage status.
- Account quota adapters: entitlement panel (free remaining / credits / reset / next cheaper mode).
- SmartSwitch runtime execution FREE→PAID_OWNED: `/api/autoswitch` POST+GET durable readback.
- Official market refresh: `/api/deals` (registry OpenAI/Anthropic/Gemini/OpenRouter/Groq/Mistral/xAI).
- click→API→persisted-readback: AutoSwitch кнопка → POST → durable readback (run_id).
