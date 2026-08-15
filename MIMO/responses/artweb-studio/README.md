# ArtWeb Studio

Командный центр конструктора сайтов и оркестра моделей. Тёмный премиум-интерфейс, icon-first язык способностей, живые подключения к локальным и облачным моделям.

## Версии
- **Next.js** (`artweb-studio-next/`): 11 маршрутов (9 модулей + `/about` + `/compare`), App Router + TypeScript.
  Запуск: `cd artweb-next && npm install && npm run dev` (или `npm run build && npm run start`).
- **Ванильный** (`artweb-studio-app.html`): один HTML-файл, hash-роутер, без сборки и зависимостей.

## Модули (11)
Model Compare · Routing Lab · Skills Registry · Agents Studio · Workflow Builder · Playground · MIMO Sync · Observatory · Task Board · Сравнить · О проекте.

## Бэкенд (прокси `:8890`)
`playground_proxy.py` — локальный CORS-прокси (ключи хранятся серверно):
`/api/health` · `/api/models` · `/api/chat` · `/api/orchestra` · `/api/skills` · `/api/catalog` · `/api/openrouter` · `/api/reviews`.

## Отзывы (SQLite)
- `GET    /api/reviews?model=<id>` — список отзывов модели.
- `POST   /api/reviews` — `{model, author, rating 1–5, text}` (валидация).
- `DELETE /api/reviews/<id>` — удалить отзыв.
- Хранение: `reviews.db` (таблица `reviews`, stdlib `sqlite3`, `AUTOINCREMENT` + `CHECK(rating)` + индекс по `model`).
- «Свои» отзывы определяются на клиенте (localStorage `my_review_ids`), без авторизации.

## Каталог и скиллы
- `models.seed.json` — 400 моделей (детерминированный генератор `generate_models.py`).
- `skills.seed.json` — 141 реальный скилл (`extract_skills.py` из WORKER-REGISTRY.json).
- `models.schema.json` — JSON-schema; `capability-icons.svg` — спрайт 10 способностей.

## Routing
- `router.py` — 8-осевой динамический роутер (stdlib): quality / latency / cost / context / privacy / availability / tool_use / free.
  CLI: `python router.py route --top 5 --require tool_use,vision --json`.

## Failure isolation
- `orchestra_daemon.py` (D:\4\OUT\MIMO) следит за supervisor `:8091` + dashboard + прокси `:8890` и перезапускает упавшие.

## Связь MIMO↔GPT (заморожена)
- GPT→MIMO = ntfy `artweb-mimo-bus-20260814-8d3f2a761c4e`.
- MIMO→GPT = `Yury197812/portable-os` ветка `master`, папка `MIMO/responses/`.
