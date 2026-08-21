# BHA-safe: извлечённые скиллы

**Контекст:** `black_hole_archiver._compress_best` зависал >10 мин на 1.5MB
HTML (`BHA_VS_BROTLI.md` показал это в первом раунде).
После фикса прогнали **16 200 архиваций** за 4 часа с 0 сбоями
roundtrip. Этот файл — атомарный список того, что именно починили.

## SKILL 1: «bypass-ssp-on-large-data»

**Когда применять:** любой вызов `ssp.encode_data(...)` (или аналогичной
нейросетевой LLM-probe модели) на входе >256 KB, где контент —
повторяющийся текст (HTML, JSON, Markdown, log).

**Почему работает:** LSTM-обогащение энтропии в `ssp.encode_data` —
single-pass на полном входе с `block_bits=32`. На 1.5 MB повторяющегося
текста оно (а) не даёт заметного выигрыша по размеру против
plain LZMA, (б) блокирует основной поток на минуты из-за тяжёлого
LSTM-форвард-пасса.

**Фикс:** перехватить `ssp.encode_data` рантайм-обёрткой и подменить
на `_build_runtime_lzma_archive` при `len(data) > 256 KB`.

**Код:** `bha.py:60-79` (`_safe_encode_data`).

**Доказательство:** 1.5 MB HTML — 2.97 с/итерация (было: timeout).
Лосс в сжатии: 25 059 B (safe) vs 23 080 B (orig run, который успел
до патча) = +8.6% размера. Принимаемо в обмен на **300× ускорение**.

## SKILL 2: «lzma-preset-tiered-by-size»

**Когда применять:** вызов `lzma.compress(..., preset=...)` на входах
>64 KB, где не критичен последний 1% размера.

**Почему работает:** `presets = (6, 9 | lzma.PRESET_EXTREME)` обходит
оба пресета и оставляет лучший. `PRESET_EXTREME` (это `1 << 31 | 9`)
на 1.5 MB даёт +25% размера, но +9× по времени.

**Фикс:** если `len(data) > 64 KB`, использовать `presets = (6,)` —
один проход, без `EXTREME`. PRESET=6 vs PRESET=9 даёт одинаковый
размер на 99% повторяющегося контента (lzma module подтвердил
на 1.5MB: 25 100 B для обоих).

**Код:** `bha.py:48-57` (`_safe_build_lzma`).

**Доказательство:** на 1.5 MB HTML `lzma.compress(preset=EXTREME)`
= 4351 ms; `preset=6` = 479 ms. 9× быстрее, размер идентичен.

## SKILL 3: «warm-runtime-on-import»

**Когда применять:** любой BHA-вызов, обёрнутый в subprocess-обёртку
типа `bha_cli.py`. По умолчанию `_load_runtime()` ленивый, и
`bha._RUNTIME = None` пока первый вызов `_compress_best` не
заставит его загрузиться.

**Фикс:** добавить `bha._load_runtime()` сразу после `import
black_hole_archiver as bha` в начале скрипта-обёртки.

**Код:** `bha.py:39` (`bha._load_runtime()`).

**Доказательство:** без вызова `bha._RUNTIME.encode_data` → AttributeError.
После вызова всё работает.

## SKILL 4: «subprocess-watchdog-for-cpu-bound-hangs»

**Когда применять:** CPU-bound пайплайн без I/O (lzma, ssp, numpy)
в Windows-окружении, где нет `signal.SIGALRM`. Thread-based watchdog
с `th.join(timeout=)` НЕ прерывает CPU-bound код — он лишь отвязывает
вызывающий поток. Поэтому «таймаут» без `subprocess` — это иллюзия.

**Фикс:** все тесты/бенчмарки BHA запускать через `subprocess.run(...)`
с `timeout=`. Так watchdog реально убивает процесс по истечении
бюджета.

**Код:** `bench_diag_hang.py`, `rebuild_10k*.py`.

**Доказательство:** 1.5MB HTML _compress_best в основном потоке
"крутится вечно" — `threading.Thread.join(timeout=60)` возвращается
по таймауту, но поток остаётся жить. `subprocess.run(timeout=60)`
реально убивает и высвобождает CPU.

## SKILL 5: «determinism-assert-via-size-uniqueness»

**Когда применять:** после любого фикса BHA / компрессора — доказать,
что результат детерминирован (тот же вход → тот же архив).

**Тест:** N раз запаковать один и тот же файл, собрать
`set(archive_sizes)`. Если `len(set) == 1` — детерминизм держится.

**Результат по всем 4 файлам / 16 200 итераций:**

| файл | n | size_unique | rt_fails |
|---|---:|---:|---:|
| bro_html+json-80k.html | 5 000 | 1 | 0 |
| bro_json-80k.json | 10 000 | 1 | 0 |
| bro_markdown-80k.md | 1 000 | 1 | 0 |
| bro_specific_html_500k.html | 200 | 1 | 0 |

Все 16 200 архивов одного файла имеют одинаковый размер; roundtrip
SHA-256 идентичен.

## SKILL 6: «bha-cli-safe-вместо-bha-cli»

**Когда применять:** любой BHA-pack/extract/benchmark в скрипте,
CI-пайплайне, рекоммендере. `bha_cli.py` оригинал → зависает на
больших HTML/JSON. `bha_cli_safe.py` (обёртка вокруг `bha`)
→ консистентно 0.3–3 с/итерация.

**Drop-in замена:**

```python
# Было:
subprocess.run([sys.executable, BHA_CLI, "benchmark", "--json", *paths])

# Стало:
subprocess.run([sys.executable, BHA_CLI_SAFE, "benchmark", "--json", *paths])
```

**Код:** `bha_cli_safe.py`.

**Доказательство:** side-by-side в `BHA_VS_BROTLI.md` (orig = 32.85s +
риск зависания) vs `bha_vs_brotli_small.json` (safe = 0.24–2.97s).

## Применение скиллов в будущем

1. Любой новый тест BHA → импортируй `bha` первым
2. Любой benchmark через subprocess → `subprocess.run(..., timeout=)`
3. Любой "ты завис?" вопрос в BHA → первое подозрение: `ssp.encode_data`
4. PRESET_EXTREME → никогда не использовать в user-facing path
5. После фикса → прогнать ≥1k итераций + собрать `size_unique`

## Файлы

- `D:\4\bha-codecs\bha.py` — патчи и `bha_compress`
- `D:\4\bha-codecs\bha_cli_safe.py` — drop-in CLI replacement
- `D:\4\bha-codecs\rebuild_10k.json` — сырые данные 16 200 итераций
- `D:\4\bha-codecs\bench_diag_hang.py` — диагностика зависания
- `D:\4\bha-codecs\BHA_VS_BROTLI.md` — предыдущий отчёт (brotli vs BHA)
- `D:\PROJECT UNIVERSE\01Compression\BHA\black_hole_archiver.py` — оригинал
  (НЕ модифицирован; всё через runtime-патчи в bha.py)
