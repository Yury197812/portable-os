# MIMO batch

Папка для пакетной обработки задач.

## Формат
- Файлы: `BATCH_*.json`
- Содержимое: массив задач для параллельной обработки

## Пример
```json
{
  "batch_id": "BATCH_001",
  "tasks": [
    {"id": "T1", "action": "create_zip", "params": {"folder": "OUT_MIMO"}},
    {"id": "T2", "action": "push_to_github", "params": {"repo": "portable-os"}}
  ]
}
```
