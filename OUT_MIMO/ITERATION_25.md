# Platform Software — 4 Directions (VK, Дзен, ТГ, Яндекс+Google)

## Overview
Portable modular software for 4 social media/platform directions.

---

## D1: VK (ВКонтакте)

## vk/
**P:** VK API

**C:**
api.js
auth.js
posts.js
analytics.js

**S:**
Pub content
Analytics
Communities

**A:**
- Rust HTTP
- Go parallel

---

## D2: Дзен (Yandex Dzen)

## dzen/
**P:** Dzen API

**C:**
api.js
auth.js
publish.js
seo.js

**S:**
Pub articles
SEO
Analytics

**A:**
- Rust HTML
- Go content

---

## D3: Telegram

## telegram/
**P:** TG Bot API

**C:**
bot.js
auth.js
messages.js
media.js

**S:**
Bots
Messages
Media

**A:**
- Rust HTTP
- Go msgs

---

## D4: Яндекс + Google

## yandex_google/
**P:** Yandex+Google API

**C:**
yandex/api.js
google/api.js
auth.js
search.js

**S:**
Yandex search
Google Analytics
SEO

**A:**
- Rust HTTP
- Go search

---

## Arch

```
platform-software/
├── vk/
│   ├── api.js
│   ├── auth.js
│   ├── posts.js
│   └── analytics.js
├── dzen/
│   ├── api.js
│   ├── auth.js
│   ├── publish.js
│   └── seo.js
├── telegram/
│   ├── bot.js
│   ├── auth.js
│   ├── messages.js
│   └── media.js
├── yandex_google/
│   ├── yandex/
│   ├── google/
│   ├── auth.js
│   └── search.js
├── engine/
├── skills/
└── api/
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
Intro

## Chapter 2: VK
VK API setup
- Authentication
- Posting and analytics

## Chapter 3: Дзен
Dzen API setup
- Article publishing
- SEO optimization

## Chapter 4: Telegram
TG

## Chapter 5: Яндекс + Google
Yandex API
Google API
- Cross-platform search

## Chapter 6: Acceleration
Acc

---

## Workflow

1. GPT → OUT_GPT
2. MIMO → OUT_MIMO
3. Iter until production-ready
4. Book

---

*4D: VK, Dzen, TG, Ya+Go | Modular | Accel*
