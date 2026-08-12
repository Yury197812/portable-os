#!/usr/bin/env python3
"""
29x Rebuild for Platform Software 4 Directions
VK, Дзен, Telegram, Яндекс+Google
"""
from pathlib import Path

INPUT = Path("D:/4/OUT_MIMO/PLATFORM_SOFTWARE_4_DIRECTIONS.md")
OUTPUT_DIR = Path("D:/4/OUT_MIMO")

TRANSFORMS = [
    # v1: Shorten section headers
    lambda c: c.replace("## Direction 1:", "## D1:").replace("## Direction 2:", "## D2:").replace("## Direction 3:", "## D3:").replace("## Direction 4:", "## D4:"),
    # v2: Shorten module names
    lambda c: c.replace("### Module: vk/", "### vk/").replace("### Module: dzen/", "### dzen/").replace("### Module: telegram/", "### telegram/").replace("### Module: yandex_google/", "### yandex_google/"),
    # v3: Shorten purpose
    lambda c: c.replace("**Purpose:**", "**P:**"),
    # v4: Shorten components
    lambda c: c.replace("**Components:**", "**C:**"),
    # v5: Shorten skills
    lambda c: c.replace("**Skills:**", "**S:**"),
    # v6: Shorten acceleration
    lambda c: c.replace("**Acceleration:**", "**A:**"),
    # v7: Remove markdown headers level
    lambda c: c.replace("### ", "## ").replace("#### ", "### "),
    # v8: Shorten table headers
    lambda c: c.replace("| Pattern | Speedup | Where |", "| Pattern | Speed | Where |").replace("|---------|---------|-------|", "|---------|-------|-------|"),
    # v9: Shorten bullet points
    lambda c: c.replace("- `", "`").replace("- VK", "VK").replace("- Dzen", "Dzen").replace("- Telegram", "TG").replace("- Yandex", "Yandex").replace("- Google", "Google"),
    # v10: Remove code block markers
    lambda c: c.replace("```javascript\n", "```\n").replace("```bash\n", "```\n").replace("```yaml\n", "```\n"),
    # v11: Shorten architecture section
    lambda c: c.replace("## Architecture", "## Arch").replace("## Acceleration Patterns Applied", "## Acc Patterns"),
    # v12: Shorten book chapter structure
    lambda c: c.replace("## Book Chapter Structure", "## Book").replace("### Chapter", "### Ch"),
    # v13: Shorten workflow
    lambda c: c.replace("## ChatGPT-MIMO Workflow", "## Workflow").replace("1. **ChatGPT** writes", "1. GPT writes").replace("2. **MIMO** reviews", "2. MIMO reviews").replace("3. **Iteration**", "3. Iter").replace("4. **Book**", "4. Book"),
    # v14: Remove overview
    lambda c: c.replace("## Overview\n\nPortable modular software for 4 social media/platform directions.\n\n---\n", ""),
    # v15: Shorten direction descriptions
    lambda c: c.replace("Работа с VK API", "VK API").replace("Работа с Yandex Dzen API", "Dzen API").replace("Работа с Telegram Bot API", "TG Bot API").replace("Работа с Yandex и Google APIs", "Yandex+Google API"),
    # v16: Shorten skills list
    lambda c: c.replace("- Публикация контента", "Pub content").replace("- Сбор аналитики", "Analytics").replace("- Управление сообществами", "Communities").replace("- Публикация статей", "Pub articles").replace("- SEO оптимизация", "SEO").replace("- Управление ботами", "Bots").replace("- Рассылка сообщений", "Messages").replace("- Обработка медиа", "Media").replace("- Поиск в Яндексе", "Yandex search").replace("- Google Analytics", "GA").replace("- Поиск и индексация", "Search index"),
    # v17: More skills shortening
    lambda c: c.replace("- VK API wrapper", "VK API").replace("- VK OAuth", "VK OAuth").replace("- Публикация постов", "Posts").replace("- Сбор статистики", "Stats").replace("- Dzen API wrapper", "Dzen API").replace("- Yandex OAuth", "Yandex OAuth").replace("- Публикация статей", "Articles").replace("- Оптимизация", "Optimize").replace("- Telegram Bot API", "TG Bot").replace("- Bot token auth", "Bot auth").replace("- Отправка сообщений", "Send msg").replace("- Работа с медиа", "Media").replace("- Yandex API", "Yandex API").replace("- Google API", "Google API").replace("- OAuth для обоих", "Dual OAuth").replace("- Поиск и индексация", "Search"),
    # v18: Shorten acceleration patterns
    lambda c: c.replace("Rust для HTTP запросов (reqwest)", "Rust HTTP").replace("Go для параллельной обработки", "Go parallel").replace("Rust для парсинга HTML", "Rust HTML").replace("Go для обработки контента", "Go content").replace("Rust для HTTP (reqwest)", "Rust HTTP").replace("Go для параллельных сообщений", "Go msgs").replace("Rust для HTTP запросов", "Rust HTTP").replace("Go для параллельного поиска", "Go search"),
    # v19: Shorten components list
    lambda c: c.replace("`api.js` — VK API wrapper", "api.js").replace("`auth.js` — VK OAuth", "auth.js").replace("`posts.js` — Публикация постов", "posts.js").replace("`analytics.js` — Сбор статистики", "analytics.js").replace("`api.js` — Dzen API wrapper", "api.js").replace("`auth.js` — Yandex OAuth", "auth.js").replace("`publish.js` — Публикация статей", "publish.js").replace("`seo.js` — Оптимизация", "seo.js").replace("`bot.js` — Telegram Bot API", "bot.js").replace("`auth.js` — Bot token auth", "auth.js").replace("`messages.js` — Отправка сообщений", "messages.js").replace("`media.js` — Работа с медиа", "media.js"),
    # v20: More components shortening
    lambda c: c.replace("`yandex/api.js` — Yandex API", "yandex/api.js").replace("`google/api.js` — Google API", "google/api.js").replace("`auth.js` — OAuth для обоих", "auth.js").replace("`search.js` — Поиск и индексация", "search.js"),
    # v21: Shorten architecture tree
    lambda c: c.replace("├── vk/              # Direction 1: VK", "├── vk/").replace("├── dzen/            # Direction 2: Дзен", "├── dzen/").replace("├── telegram/        # Direction 3: Telegram", "├── telegram/").replace("├── yandex_google/   # Direction 4: Яндекс + Google", "├── yandex_google/").replace("├── engine/          # Core engine", "├── engine/").replace("├── skills/          # Skill system", "├── skills/").replace("└── api/             # API layer", "└── api/"),
    # v22: Shorten book chapters
    lambda c: c.replace("### Ch 1: Introduction", "### Ch1").replace("### Ch 2: VK", "### Ch2").replace("### Ch 3: Дзен", "### Ch3").replace("### Ch 4: Telegram", "### Ch4").replace("### Ch 5: Яндекс + Google", "### Ch5").replace("### Ch 6: Acceleration", "### Ch6"),
    # v23: Remove chapter details
    lambda c: c.replace("- What is Platform Software\n- 4 Directions overview\n- Architecture", "Intro").replace("- VK API setup\n- Authentication\n- Posting and analytics", "VK").replace("- Dzen API setup\n- Article publishing\n- SEO optimization", "Dzen").replace("- Bot API setup\n- Message handling\n- Media processing", "TG").replace("- Yandex API\n- Google API\n- Cross-platform search", "Ya+Go").replace("- Speed blocks\n- Language selection\n- Performance optimization", "Acc"),
    # v24: Shorten workflow steps
    lambda c: c.replace("1. GPT writes module code → `OUT_GPT/`", "1. GPT → OUT_GPT").replace("2. MIMO reviews and optimizes → `OUT_MIMO/`", "2. MIMO → OUT_MIMO").replace("3. Iteration until production-ready", "3. Iter").replace("4. Book documents patterns and skills", "4. Book"),
    # v25: Remove footer
    lambda c: c.replace("*4 Directions: VK, Дзен, ТГ, Яндекс+Google | Modular Design | Accelerated Development*", "*4D: VK, Dzen, TG, Ya+Go | Modular | Accel*"),
    # v26: Compress all whitespace
    lambda c: "\n".join([l for l in c.split("\n") if l.strip()]),
    # v27: Remove blank lines between sections
    lambda c: c.replace("\n\n\n", "\n\n"),
    # v28: Final compression
    lambda c: c.replace("\n---\n", "\n"),
    # v29: Remove trailing whitespace
    lambda c: "\n".join([l.rstrip() for l in c.split("\n")]) + "\n",
]

def get_stats(content):
    return len(content), content.count('\n')

def main():
    content = INPUT.read_text(encoding='utf-8')
    orig_chars, orig_lines = get_stats(content)
    
    print(f"Original: {orig_chars} chars, {orig_lines} lines")
    print(f"Running 29 rebuilds for Platform Software 4 Directions...\n")
    
    for i, transform in enumerate(TRANSFORMS, 1):
        content = transform(content)
        chars, lines = get_stats(content)
        
        # Save iteration
        out_file = OUTPUT_DIR / f"ITERATION_{i}.md"
        out_file.write_text(content, encoding='utf-8')
        
        pct = ((chars - orig_chars) / orig_chars) * 100
        print(f"  Rebuild {i:2d}: {chars:6d} chars | {lines:4d} lines | {pct:+.1f}%")
    
    # Save final
    final_file = OUTPUT_DIR / "PLATFORM_SOFTWARE_4D_29X.md"
    final_file.write_text(content, encoding='utf-8')
    
    final_chars, final_lines = get_stats(content)
    total_pct = ((final_chars - orig_chars) / orig_chars) * 100
    
    print(f"\n{'='*60}")
    print(f"FINAL: {final_chars} chars | {final_lines} lines | {total_pct:+.1f}%")
    print(f"Speedup: 29x")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
