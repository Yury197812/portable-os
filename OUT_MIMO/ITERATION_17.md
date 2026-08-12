# Platform Software — 4 Directions (VK, Дзен, ТГ, Яндекс+Google)

## Overview
Portable modular software for 4 social media/platform directions.

---

## D1: VK (ВКонтакте)

## vk/
**P:** VK API

**C:**
`api.js` — VK API wrapper
`auth.js` — VK OAuth
`posts.js` — Публикация постов
`analytics.js` — Сбор статистики

**S:**
Pub content
Analytics
Communities

**A:**
- Rust для HTTP запросов (reqwest)
- Go для параллельной обработки

---

## D2: Дзен (Yandex Dzen)

## dzen/
**P:** Dzen API

**C:**
`api.js` — Dzen API wrapper
`auth.js` — Yandex OAuth
`publish.js` — Публикация статей
`seo.js` — Оптимизация

**S:**
Pub articles
SEO
Analytics

**A:**
- Rust для парсинга HTML
- Go для обработки контента

---

## D3: Telegram

## telegram/
**P:** TG Bot API

**C:**
`bot.js` — Telegram Bot API
`auth.js` — Bot token auth
`messages.js` — Отправка сообщений
`media.js` — Работа с медиа

**S:**
Bots
Messages
Media

**A:**
- Rust для HTTP (reqwest)
- Go для параллельных сообщений

---

## D4: Яндекс + Google

## yandex_google/
**P:** Yandex+Google API

**C:**
`yandex/api.js` — Yandex API
`google/api.js` — Google API
`auth.js` — OAuth для обоих
`search.js` — Поиск и индексация

**S:**
Yandex search
Google Analytics
SEO

**A:**
- Rust для HTTP запросов
- Go для параллельного поиска

---

## Arch

```
platform-software/
├── vk/              # Direction 1: VK
│   ├── api.js
│   ├── auth.js
│   ├── posts.js
│   └── analytics.js
├── dzen/            # Direction 2: Дзен
│   ├── api.js
│   ├── auth.js
│   ├── publish.js
│   └── seo.js
├── telegram/        # Direction 3: Telegram
│   ├── bot.js
│   ├── auth.js
│   ├── messages.js
│   └── media.js
├── yandex_google/   # Direction 4: Яндекс + Google
│   ├── yandex/
│   ├── google/
│   ├── auth.js
│   └── search.js
├── engine/          # Core engine
├── skills/          # Skill system
└── api/             # API layer
```

---

## Acc Patterns

| Pattern | Speed | Where |
|---------|-------|-------|
| Rust HTTP | 10x | Все модули |
| Go parallel | 5x | Обработка контента |
| Rust HTML parse | 20x | Дзен, SEO |
| C auth | 50x | OAuth flows |

---

## Book

## Chapter 1: Introduction
- What is Platform Software
- 4 Directions overview
- Architecture

## Chapter 2: VK
VK API setup
- Authentication
- Posting and analytics

## Chapter 3: Дзен
Dzen API setup
- Article publishing
- SEO optimization

## Chapter 4: Telegram
- Bot API setup
- Message handling
- Media processing

## Chapter 5: Яндекс + Google
Yandex API
Google API
- Cross-platform search

## Chapter 6: Acceleration
- Speed blocks
- Language selection
- Performance optimization

---

## Workflow

1. GPT writes module code → `OUT_GPT/`
2. MIMO reviews and optimizes → `OUT_MIMO/`
3. Iter until production-ready
4. Book documents patterns and skills

---

*4 Directions: VK, Дзен, ТГ, Яндекс+Google | Modular Design | Accelerated Development*
