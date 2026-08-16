# STATUS_DISK_C_NEURO_20260816.md

message_id=MIMO-STATUS-DISK-C-NEURO-20260816-001
sender=MIMO (WORKER_A, DeepSeek V4-Pro 0813)
recipient=USER (via LM Studio mini-chat) + GPT/OCULUS
type=STATUS
priority=P1
timestamp=2026-08-16T16:29:00Z

## Disk C: neural-model inventory

User directive (16:29): «СИСТЕМНЫЙ!!! Диск !!! С него не запускаем нейронки | Объясни всем».

### Inventory (read-only, не модифицировал)

- **C: total/free**: 465.8 / 77.9 GB (84% used)
- **C:\Users\Art\.ollama\models\blobs**: **8.37 GB** (Ollama model blobs)
- **C:\Users\Art\.ollama\models\manifests**: present
- **C:\Users\Art\.lmstudio\models**: directory exists (LM Studio models)
- **C:\Users\Art\.lmstudio\hub, extensions, bin**: present (LM Studio runtime dirs)
- **`D:\4\.cache\lm-studio\models`** — empty (no LM Studio models on D:)

### Active services that depend on C: neural models

| Service | Port | Provider status | Impact of stopping |
|---|---|---|---|
| `:8890` proxy | 8890 | 4 providers registered (ollama, lmstudio, groq, openrouter_free); ollama healthy (consec_failures=0, last_success=1786815061) | ollama + lmstudio providers would return 5xx; groq + openrouter_free unaffected |
| `:8091` orchestra-truthful | 8091 | depends on `:8890` upstream | degrades but doesn't crash |
| `:8891` artweb-runtime | 8891 | depends on `:8890` | degrades but doesn't crash |

### What I did NOT do (out of scope / requires user)

- ❌ Did NOT stop any service
- ❌ Did NOT move/delete Ollama blobs (8.37 GB)
- ❌ Did NOT move LM Studio models
- ❌ Did NOT reconfigure proxy to skip ollama/lmstudio providers

### What I CAN do safely

1. **Stop ollama process** if you want — frees ~8.4 GB on C: and disables one provider on `:8890`
2. **Stop LM Studio server** (if running) — frees models dir but I don't know how big it is
3. **Move Ollama models** to D:/ollama_models + set `OLLAMA_MODELS=D:\ollama_models` env var + restart ollama
4. **Move LM Studio models** to D: via LM Studio UI (Settings → Models → Change directory) — **must be done in UI**, agent cannot do this safely
5. **Edit `:8890` proxy config** to disable ollama + lmstudio providers, leaving only groq + openrouter_free (this is the simplest path, ~5 min, no data loss)

### Recommendation to user

If you want me to take action, **pick one**:
- **A.** Stop ollama process + edit proxy config to disable ollama/lmstudio (5 min, no data loss, frees ~8.4 GB on C: after manually moving ollama models)
- **B.** Wait for you to move LM Studio models via UI, then I disable lmstudio provider in proxy
- **C.** Document only, no action

I am waiting for your choice before changing runtime state.

## Operator

MIMO (WORKER_A), DeepSeek V4-Pro 0813, `D:\4` working dir.
Will obey "не запускаем нейронки с C:" — but need user pick from options above
to avoid destructive actions on C:.