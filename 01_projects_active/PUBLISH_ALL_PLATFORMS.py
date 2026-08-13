#!/usr/bin/env python3
"""
PUBLISH ALL PLATFORMS
Экспорт книг на все доступные площадки
"""
import os
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

BOOKS_DIR = Path("D:/4/01_projects_active/factory/public/book2_proofs/chapters")
OUTPUT_BASE = Path("D:/4/PUBLICATIONS")
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

# ============================================================
# ПЛОЩАДКИ ДЛЯ ПУБЛИКАЦИИ
# ============================================================

PLATFORMS = {
    "habr": {
        "name": "Habr",
        "url": "https://habr.com/ru/users/Yury197812/",
        "format": "html",
        "tags": ["mathematics", "millennium-problems", "proof-theory", "computer-science"],
        "description": "Публикация на русскоязычном техническом портале"
    },
    "github_pages": {
        "name": "GitHub Pages",
        "url": "https://yury197812.github.io/portable-os/",
        "format": "html",
        "tags": ["documentation", "mathematics"],
        "description": "Публикация на GitHub Pages как документация"
    },
    "osf": {
        "name": "Open Science Framework",
        "url": "https://osf.io/",
        "format": "markdown",
        "tags": ["preprint", "mathematics", "open-science"],
        "description": "Публикация препринта на OSF"
    },
    "arxiv": {
        "name": "arXiv",
        "url": "https://arxiv.org/",
        "format": "pdf",
        "tags": ["math.CO", "math.LO", "cs.AI"],
        "description": "Публикация на arXiv (требует эндорсмента)"
    },
    "medium": {
        "name": "Medium",
        "url": "https://medium.com/",
        "format": "markdown",
        "tags": ["mathematics", "science", "education"],
        "description": "Публикация на Medium для широкой аудитории"
    },
    "personal_site": {
        "name": "Personal Site",
        "url": "https://yury197812.github.io/",
        "format": "html",
        "tags": ["portfolio", "mathematics"],
        "description": "Публикация на персональном сайте"
    }
}

# ============================================================
# ЭКСПОРТЕРЫ
# ============================================================

class HTMLExporter:
    """Экспорт в HTML"""
    
    def export(self, source_file: Path, output_dir: Path, platform: dict) -> Path:
        # Чтение исходного файла
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Добавление метаданных платформы
        html_content = self.add_metadata(content, platform, source_file.stem)
        
        # Сохранение
        output_file = output_dir / f"{source_file.stem}.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return output_file
    
    def add_metadata(self, content: str, platform: dict, title: str) -> str:
        """Добавление метаданных"""
        # Добавление заголовка и тегов
        metadata_html = f"""
<!--
Platform: {platform['name']}
Title: {title}
Tags: {', '.join(platform['tags'])}
Published: {datetime.now().isoformat()}
-->
"""
        return metadata_html + content

class MarkdownExporter:
    """Экспорт в Markdown"""
    
    def export(self, source_file: Path, output_dir: Path, platform: dict) -> Path:
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Конвертация HTML в Markdown (упрощённо)
        md_content = self.html_to_markdown(content)
        
        # Добавление метаданных
        md_content = self.add_frontmatter(md_content, platform, source_file.stem)
        
        output_file = output_dir / f"{source_file.stem}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        return output_file
    
    def html_to_markdown(self, html: str) -> str:
        """Простая конвертация HTML в Markdown"""
        import re
        
        # Удаление HTML тегов
        text = re.sub(r'<[^>]+>', '', html)
        
        # Замена HTML entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        
        return text
    
    def add_frontmatter(self, content: str, platform: dict, title: str) -> str:
        """Добавление frontmatter"""
        frontmatter = f"""---
title: "{title}"
platform: "{platform['name']}"
tags: {json.dumps(platform['tags'])}
date: "{datetime.now().isoformat()}"
---

"""
        return frontmatter + content

class PDFExporter:
    """Экспорт в PDF"""
    
    def export(self, source_file: Path, output_dir: Path, platform: dict) -> Path:
        # PDF требует wkhtmltopdf или другой инструмент
        # Пока создаём заглушку
        output_file = output_dir / f"{source_file.stem}.pdf"
        
        # Создание простого PDF через HTML
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Сохранение как HTML с расширением .pdf (заглушка)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"<!-- PDF Export Placeholder -->\n{content}")
        
        return output_file

# ============================================================
# ПАЙПЛАЙН ПУБЛИКАЦИИ
# ============================================================

class PublicationPipeline:
    """Пайплайн публикации на все площадки"""
    
    def __init__(self):
        self.exporters = {
            "html": HTMLExporter(),
            "markdown": MarkdownExporter(),
            "pdf": PDFExporter()
        }
        self.results = {}
    
    def run(self):
        """Запуск пайплайна"""
        print("=" * 60)
        print("PUBLICATION PIPELINE")
        print("=" * 60)
        
        # Получение списка глав
        chapters = list(BOOKS_DIR.glob("chapter_*.html"))
        print(f"\nНайдено глав: {len(chapters)}")
        
        # Экспорт на каждую площадку
        for platform_id, platform in PLATFORMS.items():
            print(f"\n[{platform_id.upper()}] Экспорт на {platform['name']}...")
            
            # Создание директории для площадки
            platform_dir = OUTPUT_BASE / platform_id
            platform_dir.mkdir(parents=True, exist_ok=True)
            
            # Экспорт глав
            exported_files = []
            for chapter in chapters:
                exporter = self.exporters[platform["format"]]
                output_file = exporter.export(chapter, platform_dir, platform)
                exported_files.append(output_file)
            
            self.results[platform_id] = {
                "platform": platform["name"],
                "files": len(exported_files),
                "directory": str(platform_dir)
            }
            
            print(f"  Экспортировано: {len(exported_files)} файлов")
        
        # Сохранение результатов
        self.save_results()
        
        print("\n" + "=" * 60)
        print("ГОТОВО!")
        print("=" * 60)
    
    def save_results(self):
        """Сохранение результатов"""
        results_file = OUTPUT_BASE / "publication_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # Создание README
        readme_content = self.generate_readme()
        readme_file = OUTPUT_BASE / "README.md"
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(readme_content)
    
    def generate_readme(self) -> str:
        """Генерация README"""
        content = """# Publication Results

## Площадки для публикации

"""
        for platform_id, result in self.results.items():
            content += f"### {result['platform']}\n"
            content += f"- Файлов: {result['files']}\n"
            content += f"- Директория: `{result['directory']}`\n\n"
        
        content += """
## Инструкция по публикации

### Habr
1. Скопировать HTML файлы из `habr/`
2. Отредактировать под стиль Habr
3. Опубликовать через интерфейс

### GitHub Pages
1. Скопировать файлы в `docs/` репозитория
2. Включить GitHub Pages в настройках
3. Файлы будут доступны по URL

### OSF
1. Загрузить Markdown файлы на osf.io
2. Заполнить метаданные
3. Опубликовать как препринт

### arXiv
1. Подготовить PDF (требуется LaTeX)
2. Получить эндорсмент
3. Загрузить через интерфейс

### Medium
1. Скопировать Markdown файлы
2. Опубликовать через интерфейс
3. Добавить теги

"""
        return content

# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    pipeline = PublicationPipeline()
    pipeline.run()
