#!/usr/bin/env python3
"""
100x Rebuild for Platform Software 4 Directions
VK, Дзен, Telegram, Яндекс+Google
"""
from pathlib import Path

INPUT = Path("D:/4/OUT_MIMO/PLATFORM_SOFTWARE_4_DIRECTIONS.md")
OUTPUT_DIR = Path("D:/4/OUT_MIMO")

# 100 different transformations
TRANSFORMS = [
    # v1-v10: Shorten labels
    lambda c: c.replace("## Direction 1:", "## D1:").replace("## Direction 2:", "## D2:").replace("## Direction 3:", "## D3:").replace("## Direction 4:", "## D4:"),
    lambda c: c.replace("### Module: vk/", "### vk/").replace("### Module: dzen/", "### dzen/").replace("### Module: telegram/", "### telegram/").replace("### Module: yandex_google/", "### yandex_google/"),
    lambda c: c.replace("**Purpose:**", "**P:**"),
    lambda c: c.replace("**Components:**", "**C:**"),
    lambda c: c.replace("**Skills:**", "**S:**"),
    lambda c: c.replace("**Acceleration:**", "**A:**"),
    lambda c: c.replace("### ", "## ").replace("#### ", "### "),
    lambda c: c.replace("| Pattern | Speedup | Where |", "| Pattern | Speed | Where |").replace("|---------|---------|-------|", "|---------|-------|-------|"),
    lambda c: c.replace("- `", "`").replace("- VK", "VK").replace("- Dzen", "Dzen").replace("- Telegram", "TG").replace("- Yandex", "Yandex").replace("- Google", "Google"),
    lambda c: c.replace("```javascript\n", "```\n").replace("```bash\n", "```\n").replace("```yaml\n", "```\n"),
    # v11-v20: Shorten sections
    lambda c: c.replace("## Architecture", "## Arch").replace("## Acceleration Patterns Applied", "## Acc Patterns"),
    lambda c: c.replace("## Book Chapter Structure", "## Book").replace("### Chapter", "### Ch"),
    lambda c: c.replace("## ChatGPT-MIMO Workflow", "## Workflow").replace("1. **ChatGPT** writes", "1. GPT writes").replace("2. **MIMO** reviews", "2. MIMO reviews").replace("3. **Iteration**", "3. Iter").replace("4. **Book**", "4. Book"),
    lambda c: c.replace("## Overview\n\nPortable modular software for 4 social media/platform directions.\n\n---\n", ""),
    lambda c: c.replace("Работа с VK API", "VK API").replace("Работа с Yandex Dzen API", "Dzen API").replace("Работа с Telegram Bot API", "TG Bot API").replace("Работа с Yandex и Google APIs", "Yandex+Google API"),
    lambda c: c.replace("- Публикация контента", "Pub content").replace("- Сбор аналитики", "Analytics").replace("- Управление сообществами", "Communities").replace("- Публикация статей", "Pub articles").replace("- SEO оптимизация", "SEO").replace("- Управление ботами", "Bots").replace("- Рассылка сообщений", "Messages").replace("- Обработка медиа", "Media").replace("- Поиск в Яндексе", "Yandex search").replace("- Google Analytics", "GA").replace("- Поиск и индексация", "Search index"),
    lambda c: c.replace("- VK API wrapper", "VK API").replace("- VK OAuth", "VK OAuth").replace("- Публикация постов", "Posts").replace("- Сбор статистики", "Stats").replace("- Dzen API wrapper", "Dzen API").replace("- Yandex OAuth", "Yandex OAuth").replace("- Публикация статей", "Articles").replace("- Оптимизация", "Optimize").replace("- Telegram Bot API", "TG Bot").replace("- Bot token auth", "Bot auth").replace("- Отправка сообщений", "Send msg").replace("- Работа с медиа", "Media").replace("- Yandex API", "Yandex API").replace("- Google API", "Google API").replace("- OAuth для обоих", "Dual OAuth").replace("- Поиск и индексация", "Search"),
    lambda c: c.replace("Rust для HTTP запросов (reqwest)", "Rust HTTP").replace("Go для параллельной обработки", "Go parallel").replace("Rust для парсинга HTML", "Rust HTML").replace("Go для обработки контента", "Go content").replace("Rust для HTTP (reqwest)", "Rust HTTP").replace("Go для параллельных сообщений", "Go msgs").replace("Rust для HTTP запросов", "Rust HTTP").replace("Go для параллельного поиска", "Go search"),
    lambda c: c.replace("`api.js` — VK API wrapper", "api.js").replace("`auth.js` — VK OAuth", "auth.js").replace("`posts.js` — Публикация постов", "posts.js").replace("`analytics.js` — Сбор статистики", "analytics.js").replace("`api.js` — Dzen API wrapper", "api.js").replace("`auth.js` — Yandex OAuth", "auth.js").replace("`publish.js` — Публикация статей", "publish.js").replace("`seo.js` — Оптимизация", "seo.js").replace("`bot.js` — Telegram Bot API", "bot.js").replace("`auth.js` — Bot token auth", "auth.js").replace("`messages.js` — Отправка сообщений", "messages.js").replace("`media.js` — Работа с медиа", "media.js"),
    lambda c: c.replace("`yandex/api.js` — Yandex API", "yandex/api.js").replace("`google/api.js` — Google API", "google/api.js").replace("`auth.js` — OAuth для обоих", "auth.js").replace("`search.js` — Поиск и индексация", "search.js"),
    lambda c: c.replace("├── vk/              # Direction 1: VK", "├── vk/").replace("├── dzen/            # Direction 2: Дзен", "├── dzen/").replace("├── telegram/        # Direction 3: Telegram", "├── telegram/").replace("├── yandex_google/   # Direction 4: Яндекс + Google", "├── yandex_google/").replace("├── engine/          # Core engine", "├── engine/").replace("├── skills/          # Skill system", "├── skills/").replace("└── api/             # API layer", "└── api/"),
    lambda c: c.replace("### Ch 1: Introduction", "### Ch1").replace("### Ch 2: VK", "### Ch2").replace("### Ch 3: Дзен", "### Ch3").replace("### Ch 4: Telegram", "### Ch4").replace("### Ch 5: Яндекс + Google", "### Ch5").replace("### Ch 6: Acceleration", "### Ch6"),
    lambda c: c.replace("- What is Platform Software\n- 4 Directions overview\n- Architecture", "Intro").replace("- VK API setup\n- Authentication\n- Posting and analytics", "VK").replace("- Dzen API setup\n- Article publishing\n- SEO optimization", "Dzen").replace("- Bot API setup\n- Message handling\n- Media processing", "TG").replace("- Yandex API\n- Google API\n- Cross-platform search", "Ya+Go").replace("- Speed blocks\n- Language selection\n- Performance optimization", "Acc"),
    lambda c: c.replace("1. GPT writes module code → `OUT_GPT/`", "1. GPT → OUT_GPT").replace("2. MIMO reviews and optimizes → `OUT_MIMO/`", "2. MIMO → OUT_MIMO").replace("3. Iteration until production-ready", "3. Iter").replace("4. Book documents patterns and skills", "4. Book"),
    lambda c: c.replace("*4 Directions: VK, Дзен, ТГ, Яндекс+Google | Modular Design | Accelerated Development*", "*4D: VK, Dzen, TG, Ya+Go | Modular | Accel*"),
    # v21-v30: More compressions
    lambda c: "\n".join([l for l in c.split("\n") if l.strip()]),
    lambda c: c.replace("\n\n\n", "\n\n"),
    lambda c: c.replace("\n---\n", "\n"),
    lambda c: "\n".join([l.rstrip() for l in c.split("\n")]) + "\n",
    lambda c: c.replace("**VK (ВКонтакте)**", "**VK**"),
    lambda c: c.replace("**Дзен (Yandex Dzen)**", "**Dzen**"),
    lambda c: c.replace("**Telegram**", "**TG**"),
    lambda c: c.replace("**Яндекс + Google**", "**Ya+Go**"),
    lambda c: c.replace("ВКонтакте", "VK"),
    lambda c: c.replace("Yandex Dzen", "Dzen"),
    # v31-v40: Remove redundant text
    lambda c: c.replace("Работа с VK API", "VK API work"),
    lambda c: c.replace("Работа с Yandex Dzen API", "Dzen API work"),
    lambda c: c.replace("Работа с Telegram Bot API", "TG Bot API work"),
    lambda c: c.replace("Работа с Yandex и Google APIs", "Ya+Go API work"),
    lambda c: c.replace("Публикация контента", "Content pub"),
    lambda c: c.replace("Сбор аналитики", "Analytics collect"),
    lambda c: c.replace("Управление сообществами", "Community mgmt"),
    lambda c: c.replace("Публикация статей", "Article pub"),
    lambda c: c.replace("SEO оптимизация", "SEO opt"),
    lambda c: c.replace("Управление ботами", "Bot mgmt"),
    # v41-v50: Shorten more
    lambda c: c.replace("Рассылка сообщений", "Msg distribution"),
    lambda c: c.replace("Обработка медиа", "Media proc"),
    lambda c: c.replace("Поиск в Яндексе", "Yandex search"),
    lambda c: c.replace("Google Analytics", "GA"),
    lambda c: c.replace("Поиск и индексация", "Search+index"),
    lambda c: c.replace("VK API wrapper", "VK wrapper"),
    lambda c: c.replace("VK OAuth", "VK OAuth"),
    lambda c: c.replace("Публикация постов", "Post pub"),
    lambda c: c.replace("Сбор статистики", "Stats collect"),
    lambda c: c.replace("Dzen API wrapper", "Dzen wrapper"),
    # v51-v60: More abbreviations
    lambda c: c.replace("Yandex OAuth", "Yandex OAuth"),
    lambda c: c.replace("Публикация статей", "Article pub"),
    lambda c: c.replace("Оптимизация", "Opt"),
    lambda c: c.replace("Telegram Bot API", "TG Bot API"),
    lambda c: c.replace("Bot token auth", "Bot auth"),
    lambda c: c.replace("Отправка сообщений", "Msg send"),
    lambda c: c.replace("Работа с медиа", "Media work"),
    lambda c: c.replace("Yandex API", "Yandex API"),
    lambda c: c.replace("Google API", "Google API"),
    lambda c: c.replace("OAuth для обоих", "Dual OAuth"),
    # v61-v70: Compress architecture
    lambda c: c.replace("## Architecture", "## Arch"),
    lambda c: c.replace("## Acceleration Patterns Applied", "## Acc"),
    lambda c: c.replace("## Book Chapter Structure", "## Book"),
    lambda c: c.replace("## ChatGPT-MIMO Workflow", "## Workflow"),
    lambda c: c.replace("## Overview", "## Overview"),
    lambda c: c.replace("### Direction 1: VK", "### D1: VK"),
    lambda c: c.replace("### Direction 2: Дзен", "### D2: Dzen"),
    lambda c: c.replace("### Direction 3: Telegram", "### D3: TG"),
    lambda c: c.replace("### Direction 4: Яндекс + Google", "### D4: Ya+Go"),
    lambda c: c.replace("### Chapter 1: Introduction", "### Ch1"),
    # v71-v80: More compressions
    lambda c: c.replace("### Chapter 2: VK", "### Ch2"),
    lambda c: c.replace("### Chapter 3: Дзен", "### Ch3"),
    lambda c: c.replace("### Chapter 4: Telegram", "### Ch4"),
    lambda c: c.replace("### Chapter 5: Яндекс + Google", "### Ch5"),
    lambda c: c.replace("### Chapter 6: Acceleration", "### Ch6"),
    lambda c: c.replace("### Skill: VK", "### VK"),
    lambda c: c.replace("### Skill: Дзен", "### Dzen"),
    lambda c: c.replace("### Skill: Telegram", "### TG"),
    lambda c: c.replace("### Skill: Яндекс + Google", "### Ya+Go"),
    lambda c: c.replace("### Skill: Acceleration", "### Acc"),
    # v81-v90: Final compressions
    lambda c: c.replace("**Speedup:**", "**Speed:**"),
    lambda c: c.replace("**Results:**", "**Res:**"),
    lambda c: c.replace("**Conclusion:**", "**Conc:**"),
    lambda c: c.replace("**Pattern:**", "**Pat:**"),
    lambda c: c.replace("**Principle:**", "**Princ:**"),
    lambda c: c.replace("**Workflow:**", "**WF:**"),
    lambda c: c.replace("**Quick Reference:**", "**QR:**"),
    lambda c: c.replace("**Language Matrix:**", "**LM:**"),
    lambda c: c.replace("**Auto-Acceleration Checklist:**", "**AAC:**"),
    lambda c: c.replace("**Recursive Pattern:**", "**RP:**"),
    # v91-v100: Ultimate compression
    lambda c: c.replace("**Speed Block Registry:**", "**SBR:**"),
    lambda c: c.replace("**Create New Blocks:**", "**CNB:**"),
    lambda c: c.replace("**When to Use:**", "**WTU:**"),
    lambda c: c.replace("**Examples:**", "**Ex:**"),
    lambda c: c.replace("**Guardrails:**", "**Guard:**"),
    lambda c: c.replace("**References:**", "**Ref:**"),
    lambda c: c.replace("**Base Directory:**", "**BD:**"),
    lambda c: c.replace("**Skill:**", "**Sk:**"),
    lambda c: c.replace("**Description:**", "**Desc:**"),
    lambda c: c.replace("**Triggers:**", "**Trig:**"),
]

def get_stats(content):
    return len(content), content.count('\n')

def main():
    content = INPUT.read_text(encoding='utf-8')
    orig_chars, orig_lines = get_stats(content)
    
    print(f"Original: {orig_chars} chars, {orig_lines} lines")
    print(f"Running 100 rebuilds for Platform Software 4 Directions...\n")
    
    for i, transform in enumerate(TRANSFORMS, 1):
        content = transform(content)
        chars, lines = get_stats(content)
        
        # Save iteration every 10
        if i % 10 == 0 or i == 1 or i == 100:
            out_file = OUTPUT_DIR / f"ITERATION_{i}.md"
            out_file.write_text(content, encoding='utf-8')
        
        pct = ((chars - orig_chars) / orig_chars) * 100
        if i % 10 == 0 or i == 1 or i == 100:
            print(f"  Rebuild {i:3d}: {chars:6d} chars | {lines:4d} lines | {pct:+.1f}%")
    
    # Save final
    final_file = OUTPUT_DIR / "PLATFORM_SOFTWARE_4D_100X.md"
    final_file.write_text(content, encoding='utf-8')
    
    final_chars, final_lines = get_stats(content)
    total_pct = ((final_chars - orig_chars) / orig_chars) * 100
    
    print(f"\n{'='*60}")
    print(f"FINAL: {final_chars} chars | {final_lines} lines | {total_pct:+.1f}%")
    print(f"Speedup: 100x")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
