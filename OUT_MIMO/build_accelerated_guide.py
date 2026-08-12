#!/usr/bin/env python3
"""
Accelerated GitHub Setup Guide Builder
Uses speed patterns for fast generation
"""
import json
import os
from pathlib import Path

# GitHub credentials
CREDS = {
    "username": "Yury197812",
    "email": "apohob5@gmail.com",
    "password": "Klin120478!+123",
    "token": "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"
}

CLONE_URL = f"https://{CREDS['token']}@github.com/{CREDS['username']}/REPO_NAME.git"

# IDE definitions with metadata
IDES = [
    # (name, category, platform, git_location, clone_method, plugin_needed)
    ("VSCode", "editor", "all", "Sidebar → Source Control (Ctrl+Shift+G)", "Ctrl+Shift+P → Git: Clone", "GitHub extension"),
    ("Cursor", "editor", "all", "Same as VSCode", "Ctrl+Shift+P → Git: Clone", "Built-in"),
    ("Windsurf", "editor", "all", "Same as VSCode", "Ctrl+Shift+P → Git: Clone", "Built-in"),
    ("JetBrains (IntelliJ, PyCharm, WebStorm, CLion, Rider, GoLand, PhpStorm, RubyMine, DataGrip, RustRover, Aqua)", "ide", "all", "Bottom panel → Version Control", "File → New → Project from Version Control", "GitHub plugin"),
    ("Sublime Text", "editor", "all", "Command Palette → Git", "Ctrl+Shift+P → Package Control → Git", "Git package"),
    ("Vim / Neovim", "editor", "all", "Status line (fugitive)", ":terminal → git clone URL", "vim-fugitive, neogit"),
    ("Emacs / Doom Emacs / Spacemacs", "editor", "all", "Mode line", "M-x magit-clone", "magit"),
    ("Atom (archived)", "editor", "all", "Bottom status bar", "Ctrl+Shift+P → Git: Clone", "git-plus"),
    ("Brackets", "editor", "all", "Sidebar extensions", "File → Clone", "Git extension"),
    ("Eclipse", "ide", "all", "Package Explorer → Team", "File → Import → Git", "EGit"),
    ("NetBeans", "ide", "all", "Team menu", "Team → Git → Clone", "Built-in"),
    ("Qt Creator", "ide", "all", "Tools → Git", "Tools → Git → Clone Repository", "Built-in"),
    ("Xcode", "ide", "macos", "Source Control menu", "Source Control → Clone", "Built-in"),
    ("Android Studio", "ide", "all", "Bottom panel → Version Control", "File → New → Project from Version Control", "Built-in"),
    ("Visual Studio", "ide", "windows", "Team Explorer panel", "Team → Clone", "GitHub extension"),
    ("Unity", "ide", "all", "Window → Package Manager", "git clone URL in project folder", "Git package"),
    ("Unreal Engine", "ide", "all", "Source Control menu (bottom-right)", "Source Control → Connect to Source Control", "Git plugin"),
    ("Godot", "ide", "all", "Project → Version Control", "git clone URL in project folder", "Built-in"),
    ("Zed", "editor", "all", "Sidebar", "File → Clone Repository", "Built-in"),
    ("Lapce", "editor", "all", "Sidebar", "File → Clone Repository", "Built-in"),
    ("Helix", "editor", "all", "Shell commands", ":sh git clone URL", "None"),
    ("Pulsar (Atom fork)", "editor", "all", "Same as Atom", "Ctrl+Shift+P → Git: Clone", "git-plus"),
    ("Lite XL", "editor", "all", "Terminal", "git clone URL in terminal", "None"),
    ("Notepad++", "editor", "windows", "Plugins menu", "Plugins → NppGit → Clone", "NppGit"),
    ("Kate (KDE)", "editor", "linux", "Project menu", "Project → Open Project → Git", "Built-in"),
    ("Geany", "editor", "all", "Build menu", "git clone URL in terminal", "None"),
    ("Code::Blocks", "ide", "all", "Terminal", "git clone URL in terminal", "None"),
    ("Dev-C++", "ide", "windows", "Terminal", "git clone URL in terminal", "None"),
    ("CodeLite", "ide", "all", "Git menu", "Git → Clone Repository", "Built-in"),
    ("KDevelop", "ide", "linux", "Project menu", "Project → Open Project → Git", "Built-in"),
    ("Jupyter Notebook", "notebook", "all", "Terminal cell", "!git clone URL", "Git extension"),
    ("JupyterLab", "notebook", "all", "Git menu", "Git → Clone", "Git extension"),
    ("Google Colab", "cloud", "browser", "Code cell", "!git clone URL", "None"),
    ("Replit", "cloud", "browser", "Import menu", "Import from GitHub", "None"),
    ("CodeSandbox", "cloud", "browser", "Import menu", "Import from GitHub", "None"),
    ("StackBlitz", "cloud", "browser", "Import menu", "Import from GitHub", "None"),
    ("Gitpod", "cloud", "browser", "Import menu", "Import from GitHub", "None"),
    ("GitHub Codespaces", "cloud", "browser", "Built-in", "Create codespace on repo", "None"),
    ("AWS Cloud9", "cloud", "browser", "Terminal", "git clone URL in terminal", "None"),
    ("Theia", "editor", "all", "Same as VSCode", "File → Clone Repository", "Built-in"),
    ("Eclipse Che", "cloud", "browser", "Import menu", "Import from GitHub", "None"),
    ("Nova (Panic)", "editor", "macos", "Source Control menu", "Source Control → Clone Repository", "Built-in"),
    ("BBEdit", "editor", "macos", "Window → Show Terminal", "git clone URL in terminal", "None"),
    ("TextMate", "editor", "macos", "Bundles menu", "git clone URL in terminal", "None"),
    ("Lazarus / Free Pascal", "ide", "all", "Terminal", "git clone URL in terminal", "lazarus_git"),
    ("BlueJ", "ide", "all", "Project menu", "git clone URL in terminal", "None"),
    ("Greenfoot", "ide", "all", "Terminal", "git clone URL in terminal", "None"),
    ("Thonny", "ide", "rpi", "Tools menu", "git clone URL in system shell", "None"),
    ("Mu", "ide", "all", "Tools menu", "git clone URL in system shell", "None"),
    ("Arduino IDE", "ide", "all", "Sketch menu", "git clone URL in terminal", "None"),
]

def generate_ide_entry(idx, name, category, platform, git_loc, clone_method, plugin):
    platform_emoji = {"all": "🌍", "windows": "🪟", "macos": "🍎", "linux": "🐧", "browser": "☁️", "rpi": "🍓"}
    category_emoji = {"editor": "📝", "ide": "⚙️", "notebook": "📓", "cloud": "☁️"}
    
    return f"""### {idx}. {name}
**Категория:** {category_emoji.get(category, '')} {category.title()}
**Платформа:** {platform_emoji.get(platform, '')} {platform.title()}
**Где Git:** {git_loc}
**Клонировать:** {clone_method}
**Плагины:** {plugin}
**Пуш/Пулл:** Меню Git или терминал
**Авторизация:** Токен в URL или настройки IDE

---

"""

def generate_full_guide():
    header = f"""# EVERY IDE + GitHub Setup — Accelerated Master Guide

## Universal Credentials
- **Username:** {CREDS['username']}
- **Email:** {CREDS['email']}
- **Password:** {CREDS['password']}
- **Token:** `{CREDS['token']}`

## Universal Clone URL
```
{CLONE_URL}
```

## Quick Commands (any terminal)
```bash
# Clone
git clone {CLONE_URL.replace('REPO_NAME', 'REPO')}

# Set remote
git remote set-url origin {CLONE_URL.replace('REPO_NAME', 'REPO')}

# Check auth
curl -H "Authorization: token {CREDS['token']}" https://api.github.com/user

# Config
git config --global user.name "{CREDS['username']}"
git config --global user.email "{CREDS['email']}"
```

## Browser Quick Login
1. Go to https://github.com/login
2. Click "Continue with Google"
3. Email: {CREDS['email']}
4. Password: {CREDS['password']}
5. Confirm 2FA on phone (Tecno SPARK 20C)

---

## 50 IDE Cheat Sheets

"""
    entries = ""
    for idx, (name, cat, plat, git_loc, clone, plugin) in enumerate(IDES, 1):
        entries += generate_ide_entry(idx, name, cat, plat, git_loc, clone, plugin)
    
    footer = """
## Repositories
- `portable-os` (private)
- `science-books-1001-proofs`
- `cdp_rs`
- `portable-blocks`

---
*Generated with acceleration patterns*
"""
    return header + entries + footer

if __name__ == "__main__":
    guide = generate_full_guide()
    out_path = Path("D:/4/OUT_MIMO/EVERY_IDE_GITHUB_SETUP.md")
    out_path.write_text(guide, encoding="utf-8")
    print(f"Generated: {out_path} ({len(guide)} bytes)")
