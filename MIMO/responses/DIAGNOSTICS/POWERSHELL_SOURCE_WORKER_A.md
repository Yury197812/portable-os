# POWERSHELL_SOURCE_WORKER_A.md

P0-HOST-001 — диагностика запусков powershell.exe/pwsh.exe (read-only).

## Вывод
Видимые периодические запуски powershell.exe имеют **известный источник** и классифицируются как **EXPECTED_PROJECT_AUTOMATION** (не SUSPICIOUS). Никаких изменений/удалений не выполнялось (по правилу DIAGNOSE FIRST).

## Найденные источники

### 1. MIMO_HEARTBEAT_B (АКТИВНА, каждые 2 минуты) — ГЛАВНЫЙ источник
- Scheduled task `\MIMO_HEARTBEAT_B`, State = Ready, Trigger = Time + Repetition `PT2M` (каждые 2 мин, 365 дней).
- Действие: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\4\OUT\MIMO_MINIMAX\status\heartbeat.ps1"`
- Это heartbeat WORKER_B / MIMO+MiniMax (пишет `status/HEARTBEAT.json` + пушит в GitHub `MIMO/workers/MIMO_MINIMAX/status/HEARTBEAT.json`).
- **Причина видимого окна**: `-File` без скрытия окна + `-ExecutionPolicy Bypass` запускается в foreground. Запускается каждые 2 минуты → интермиттентные всплывающие окна.
- Классификация: **EXPECTED_PROJECT_AUTOMATION** (легитимный heartbeat). НЕ удалять — это механизм живости WORKER_B.

### 2. SkillWatcher_FactoryGPT / SkillWatcher_Watchdog_FactoryGPT (DISABLED)
- Обе scheduled tasks: State = **Disabled** (не активны, не запускаются).
- Действия (исторические): `powershell -NoProfile -ExecutionPolicy Bypass -File D:\4\01_projects_active\_SELF_IMPROVE_20260810\watcher_one_shot.ps1` и `watcher_watchdog.ps1`.
- Классификация: **EXPECTED_PROJECT_AUTOMATION (disabled)** — не источник текущих запусков.

### 3. Run-keys (HKCU) — PowerShell НЕ найден
- YandexBrowserAutoLaunch, Skrinshoter, electron.app.LM Studio — не PowerShell.

### 4. Startup folder — PowerShell напрямую не найден
- `MiMoCode.vbs` → `cmd /k mimo` (не PowerShell; запускает MiMoCode-терминал).
- `oculus-startup.bat` → cmd/bat (LM Studio, openclaw, tsx dashboard) — не powershell напрямую.
- `MIMO_ORCHESTRA.lnk`, `Disk-O.lnk`, `Ollama.lnk`, `StartOllamaAndLMStudio.lnk` — ярлыки.

## Red flags — НЕ обнаружено
- Нет EncodedCommand/-enc, IEX/DownloadString/web-fetch, Temp/AppData-нестандартных путей, unknown parent, persistence без provenance.

## Рекомендация (не применена — ждёт консенсуса Control Tower)
Видимое окно heartbeat WORKER_B можно убрать обратимо: перевести действие на `powershell.exe -WindowStyle Hidden` ИЛИ запускать через pythonw/`-NonInteractive`. Изменение НЕ вносилось (по правилу — только по консенсусу Control Tower).

## Классификация итоговая
| Источник | Класс | Активность |
|---|---|---|
| MIMO_HEARTBEAT_B | EXPECTED_PROJECT_AUTOMATION | АКТИВНА (2 мин) |
| SkillWatcher_FactoryGPT | EXPECTED_PROJECT_AUTOMATION | Disabled |
| SkillWatcher_Watchdog_FactoryGPT | EXPECTED_PROJECT_AUTOMATION | Disabled |

## РЕШЕНО (2026-08-15T19:22Z, по прямому указанию оператора)

Применён обратимый no-window патч к `MIMO_HEARTBEAT_B`:
- **Было**: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\4\OUT\MIMO_MINIMAX\status\heartbeat.ps1"` (окно видимо, всплывает каждые 2 мин).
- **Стало**: `... -WindowStyle Hidden -File "..."` — окно больше не появляется.
- Проверено: задача Running, `HEARTBEAT.json` обновился (mtime 22:22:29Z) — heartbeat WORKER_B работает.
- Откат: `Set-ScheduledTask -TaskName MIMO_HEARTBEAT_B -Action (New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\4\OUT\MIMO_MINIMAX\status\heartbeat.ps1"')`.
- Не деструктивно: задача не удалена, только аргумент скрытия окна добавлен.
