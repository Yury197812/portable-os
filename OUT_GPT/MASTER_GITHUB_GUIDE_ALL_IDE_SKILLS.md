# MASTER GitHub Guide — ALL 50 IDE + ALL SKILLS

---

## PART 1: CREDENTIALS & QUICK ACCESS

### Universal Credentials
- **Username:** Yury197812
- **Email:** apohob5@gmail.com
- **Password:** Klin120478!+123
- **Token:** `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`

### Universal Clone URL
```
https://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@github.com/Yury197812/REPO_NAME.git
```

### Quick Commands (any terminal)
```bash
# Clone
git clone https://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@github.com/Yury197812/REPO.git

# Set remote
git remote set-url origin https://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@github.com/Yury197812/REPO.git

# Check auth
curl -H "Authorization: token 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" https://api.github.com/user

# List repos
curl -H "Authorization: token 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" https://api.github.com/user/repos

# Create repo
curl -X POST -H "Authorization: token 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" https://api.github.com/user/repos -d '{"name":"REPO_NAME","private":true}'

# Config
git config --global user.name "Yury197812"
git config --global user.email "apohob5@gmail.com"
```

### Browser Quick Login
1. Go to https://github.com/login
2. Click "Continue with Google"
3. Email: apohob5@gmail.com
4. Password: Klin120478!+123
5. Confirm 2FA on phone (Tecno SPARK 20C)

### Repositories
- `portable-os` (private)
- `science-books-1001-proofs`
- `cdp_rs`
- `portable-blocks`

---

## PART 2: SKILLS

### Skill: GitHub Quick Login
```bash
# Clone any repo
git clone https://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@github.com/Yury197812/REPO_NAME.git

# Push to repo
cd REPO_NAME
git remote set-url origin https://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@github.com/Yury197812/REPO_NAME.git
git push

# Check API status
curl -H "Authorization: token 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" https://api.github.com/user

# List repos
curl -H "Authorization: token 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" https://api.github.com/user/repos

# Create new repo
curl -X POST -H "Authorization: token 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" https://api.github.com/user/repos -d '{"name":"REPO_NAME","private":true}'
```

### Skill: VSCode / Cursor / Windsurf Git Setup
1. `Ctrl+Shift+P` → "Git: Clone"
2. Paste URL: `https://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@github.com/Yury197812/REPO.git`
3. Terminal: `git remote set-url origin https://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@github.com/Yury197812/REPO.git`
4. Install "GitHub" extension for extra features

### Skill: JetBrains Git Setup
1. File → New → Project from Version Control
2. Paste URL: `https://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@github.com/Yury197812/REPO.git`
3. Settings → Version Control → GitHub → Add token: `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`

### Skill: Vim / Neovim Git Setup
```vim
:terminal
git clone https://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@github.com/Yury197812/REPO.git
```
Plugins: vim-fugitive, neogit, octo.nvim, gitsigns.nvim

### Skill: Emacs / Doom Emacs Git Setup
```elisp
M-x magit-clone
```
Paste URL. Use `M-x magit-status` (Ctrl+x g in Doom) for push/pull.

### Skill: Sublime Text Git Setup
1. Ctrl+Shift+P → "Package Control: Install Package" → "Git"
2. Command Palette → "Git: Clone"
3. Paste URL

### Skill: Eclipse / NetBeans Git Setup
1. File → Import → Git → Projects from Git
2. Clone URI → paste URL
3. Team → Share Project → Git

### Skill: Xcode Git Setup
1. Source Control → Clone
2. Paste URL: `https://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@github.com/Yury197812/REPO.git`
3. Xcode → Settings → Source Control → Accounts → Add token

### Skill: Android Studio Git Setup
1. File → New → Project from Version Control
2. Paste URL
3. File → Settings → Version Control → GitHub → Add token

### Skill: Visual Studio Git Setup
1. Team → Clone
2. Paste URL
3. File → Account Settings → Connected Services → GitHub → Add token

### Skill: Unity / Unreal / Godot Git Setup
```bash
git clone https://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@github.com/Yury197812/REPO.git
```
Then open project folder in IDE.

### Skill: Jupyter / JupyterLab Git Setup
```python
!git clone https://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@github.com/Yury197812/REPO.git
```
Install JupyterLab Git extension for GUI.

### Skill: Cloud IDEs (Replit, CodeSandbox, StackBlitz, Gitpod, Codespaces)
1. Import from GitHub → paste URL
2. Or create new project from URL

### Skill: Zed / Lapce / Helix Git Setup
```bash
git clone https://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@github.com/Yury197812/REPO.git
```
Open folder in IDE.

### Skill: Notepad++ Git Setup
1. Install NppGit plugin
2. Plugins → NppGit → Clone → paste URL

### Skill: Kate (KDE) Git Setup
1. Project → Open Project → Git
2. Paste URL

### Skill: Code::Blocks / Dev-C++ / CodeLite Git Setup
```bash
git clone https://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@github.com/Yury197812/REPO.git
```
Open project folder.

### Skill: Arduino IDE Git Setup
```bash
git clone https://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@github.com/Yury197812/REPO.git
```
Open .ino file from cloned folder.

### Skill: Raspberry Pi (Thonny, Mu, Geany) Git Setup
```bash
git clone https://ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw@github.com/Yury197812/REPO.git
```

### Skill: AWS Cloud9 Git Setup
1. Open Cloud9 IDE
2. Terminal: `git clone https://ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw@github.com/Yury197812/REPO.git`

### Skill: GitHub API Automation
```bash
# Create repo
curl -X POST -H "Authorization: token ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw" https://api.github.com/user/repos -d '{"name":"NEW_REPO","private":true}'

# Upload file
curl -X PUT -H "Authorization: token ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw" https://api.github.com/repos/Yury197812/REPO/contents/PATH/FILE -d '{"message":"add file","content":"BASE64_CONTENT"}'

# List issues
curl -H "Authorization: token ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw" https://api.github.com/repos/Yury197812/REPO/issues

# Create issue
curl -X POST -H "Authorization: token ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw" https://api.github.com/repos/Yury197812/REPO/issues -d '{"title":"Issue Title","body":"Description"}'
```

---

## PART 3: ALL 50 IDE CHEAT SHEETS

### 1. VSCode
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Sidebar → Source Control (Ctrl+Shift+G)
**Клонировать:** Ctrl+Shift+P → "Git: Clone" → paste URL
**Пуш/Пулл:** Bottom status bar sync icon or Ctrl+Shift+P → "Git: Push/Pull"
**Терминал:** Ctrl+`
**Настройки:** File → Preferences → Settings → search "git"
**Плагины:** GitHub extension, GitLens, Git Graph
**Авторизация:** Токен в URL или Settings → Git → Credential helper

### 2. Cursor
**Категория:** 📝 Editor (AI)
**Платформа:** 🌍 All
**Где Git:** Same as VSCode (Cursor = VSCode fork)
**Клонировать:** Ctrl+Shift+P → "Git: Clone"
**AI:** Ctrl+K (generate), Ctrl+L (chat)
**Терминал:** Ctrl+`

### 3. Windsurf
**Категория:** 📝 Editor (AI)
**Платформа:** 🌍 All
**Где Git:** Same as VSCode
**Клонировать:** Ctrl+Shift+P → "Git: Clone"
**AI:** Ctrl+L (Cascade)
**Терминал:** Ctrl+`

### 4. JetBrains (IntelliJ, PyCharm, WebStorm, CLion, Rider, GoLand, PhpStorm, RubyMine, DataGrip, RustRover, Aqua)
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Bottom panel → Version Control
**Клонировать:** File → New → Project from Version Control → paste URL
**Пуш/Пулл:** VCS → Git → Push/Pull or Ctrl+Shift+K
**Терминал:** Alt+F12
**Ветки:** Bottom-right branch name
**Авторизация:** Settings → Version Control → GitHub → + → Add token

### 5. Sublime Text
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Установка Git:** Ctrl+Shift+P → "Package Control: Install Package" → "Git"
**Клонировать:** Command Palette → "Git: Clone" → paste URL
**Команды:** Command Palette → "Git:" + command
**Терминал:** Install "Terminall" package

### 6. Vim / Neovim
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Status line (with vim-fugitive)
**Клонировать:** `:terminal` → `git clone URL`
**Команды:** `:Git` (fugitive), `:Git push`, `:Git pull`
**Плагины:** vim-fugitive, neogit, octo.nvim, gitsigns.nvim
**Статус:** `:Git status`, `:Git diff`

### 7. Emacs / Doom Emacs / Spacemacs
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Mode line shows branch
**Клонировать:** `M-x magit-clone`
**Команды:** `M-x magit-status` (Ctrl+x g in Doom)
**Push/Pull:** In magit buffer: `P` push, `F` pull
**Пакет:** magit (built-in in Doom)

### 8. Atom (archived)
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Bottom status bar
**Клонировать:** Ctrl+Shift+P → "Git: Clone"
**Плагины:** git-plus, git-control, merge-conflicts
**Push/Pull:** Packages → Git Plus → Push/Pull

### 9. Brackets
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Sidebar extensions
**Клонировать:** Install "Git" extension → File → Clone
**Команды:** File → Git menu

### 10. Eclipse
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Package Explorer → Team
**Клонировать:** File → Import → Git → Projects from Git → Clone URI
**Push/Pull:** Team → Push/Pull
**Авторизация:** Window → Preferences → Team → Git → Configuration

### 11. NetBeans
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Team menu
**Клонировать:** Team → Git → Clone → paste URL
**Push/Pull:** Team → Push/Pull
**Авторизация:** Tools → Options → Version Control → Git

### 12. Qt Creator
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Tools → Git
**Клонировать:** Tools → Git → Clone Repository → paste URL
**Push/Pull:** Tools → Git → Push/Pull
**Авторизация:** Tools → Options → Version Control → Git

### 13. Xcode
**Категория:** ⚙️ IDE
**Платформа:** 🍎 macOS
**Где Git:** Source Control menu
**Клонировать:** Source Control → Clone → paste URL
**Push/Pull:** Source Control → Push/Pull
**Авторизация:** Xcode → Settings → Source Control → Accounts

### 14. Android Studio
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Bottom panel → Version Control
**Клонировать:** File → New → Project from Version Control → paste URL
**Push/Pull:** VCS → Git → Push/Pull
**Авторизация:** File → Settings → Version Control → GitHub

### 15. Visual Studio
**Категория:** ⚙️ IDE
**Платформа:** 🪟 Windows
**Где Git:** Team Explorer panel
**Клонировать:** Team → Clone → paste URL
**Push/Pull:** Team Explorer → Sync
**Авторизация:** File → Account Settings → Connected Services → GitHub

### 16. Unity
**Категория:** ⚙️ IDE (Game Engine)
**Платформа:** 🌍 All
**Где Git:** Window → Package Manager
**Клонировать:** `git clone URL` in project folder
**Плагины:** Git package (Unity Package Manager)
**Авторизация:** Edit → Preferences → External Tools → Git

### 17. Unreal Engine
**Категория:** ⚙️ IDE (Game Engine)
**Платформа:** 🌍 All
**Где Git:** Source Control menu (bottom-right)
**Подключение:** Source Control → Connect to Source Control → Git
**Push/Pull:** Source Control menu
**Авторизация:** Project Settings → Plugins → Git

### 18. Godot
**Категория:** ⚙️ IDE (Game Engine)
**Платформа:** 🌍 All
**Где Git:** Project → Version Control
**Клонировать:** `git clone URL` in project folder
**Авторизация:** Project → Project Settings → Version Control → Git

### 19. Zed
**Категория:** 📝 Editor (AI)
**Платформа:** 🌍 All
**Где Git:** Sidebar
**Клонировать:** File → Clone Repository → paste URL
**Команды:** Ctrl+Shift+P → Git commands
**Терминал:** Ctrl+`

### 20. Lapce
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Sidebar
**Клонировать:** File → Clone Repository → paste URL
**Терминал:** Ctrl+`

### 21. Helix
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Shell commands
**Клонировать:** `:sh git clone URL`
**Команды:** `:sh git status`, `:sh git push`

### 22. Pulsar (Atom fork)
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Same as Atom
**Клонировать:** Ctrl+Shift+P → "Git: Clone"
**Плагины:** git-plus

### 23. Lite XL
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Terminal
**Клонировать:** `git clone URL` in terminal

### 24. Notepad++
**Категория:** 📝 Editor
**Платформа:** 🪟 Windows
**Установка Git:** Install NppGit plugin
**Клонировать:** Plugins → NppGit → Clone → paste URL
**Команды:** Plugins → NppGit → commands

### 25. Kate (KDE)
**Категория:** 📝 Editor
**Платформа:** 🐧 Linux
**Где Git:** Project menu
**Клонировать:** Project → Open Project → Git → paste URL
**Терминал:** View → Tool Views → Terminal

### 26. Geany
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Build menu
**Клонировать:** `git clone URL` in terminal
**Терминал:** Build → Terminal

### 27. Code::Blocks
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Terminal
**Клонировать:** `git clone URL` in terminal

### 28. Dev-C++
**Категория:** ⚙️ IDE
**Платформа:** 🪟 Windows
**Где Git:** Terminal
**Клонировать:** `git clone URL` in terminal

### 29. CodeLite
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Git menu
**Клонировать:** Git → Clone Repository → paste URL
**Push/Pull:** Git → Push/Pull

### 30. KDevelop
**Категория:** ⚙️ IDE
**Платформа:** 🐧 Linux
**Где Git:** Project menu
**Клонировать:** Project → Open Project → Git → paste URL

### 31. Jupyter Notebook
**Категория:** 📓 Notebook
**Платформа:** 🌍 All
**Где Git:** Terminal cell
**Клонировать:** `!git clone URL` in cell
**Расширение:** JupyterLab Git extension

### 32. JupyterLab
**Категория:** 📓 Notebook
**Платформа:** 🌍 All
**Где Git:** Git menu (with extension)
**Клонировать:** Git → Clone → paste URL
**Push/Pull:** Git menu

### 33. Google Colab
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Code cell
**Клонировать:** `!git clone URL` in cell
**Монтирование:** `from google.colab import drive; drive.mount('/content/drive')`

### 34. Replit
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Import menu
**Клонировать:** Import from GitHub → paste URL

### 35. CodeSandbox
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Import menu
**Клонировать:** Import from GitHub → paste URL

### 36. StackBlitz
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Import menu
**Клонировать:** Import from GitHub → paste URL

### 37. Gitpod
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Import menu
**Клонировать:** Import from GitHub → paste URL

### 38. GitHub Codespaces
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Built-in
**Клонировать:** Create codespace on repo
**Терминал:** Built-in terminal

### 39. AWS Cloud9
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Terminal
**Клонировать:** `git clone URL` in terminal

### 40. Theia
**Категория:** 📝 Editor
**Платформа:** 🌍 All
**Где Git:** Same as VSCode
**Клонировать:** File → Clone Repository → paste URL

### 41. Eclipse Che
**Категория:** ☁️ Cloud
**Платформа:** ☁️ Browser
**Где Git:** Import menu
**Клонировать:** Import from GitHub → paste URL

### 42. Nova (Panic)
**Категория:** 📝 Editor
**Платформа:** 🍎 macOS
**Где Git:** Source Control menu
**Клонировать:** Source Control → Clone Repository → paste URL
**Push/Pull:** Source Control menu

### 43. BBEdit
**Категория:** 📝 Editor
**Платформа:** 🍎 macOS
**Где Git:** Window → Show Terminal
**Клонировать:** `git clone URL` in terminal

### 44. TextMate
**Категория:** 📝 Editor
**Платформа:** 🍎 macOS
**Где Git:** Bundles menu
**Клонировать:** `git clone URL` in terminal

### 45. Lazarus / Free Pascal
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Установка Git:** Package → Install lazarus_git
**Клонировать:** `git clone URL` in terminal

### 46. BlueJ
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Project menu
**Клонировать:** `git clone URL` in terminal

### 47. Greenfoot
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Terminal
**Клонировать:** `git clone URL` in terminal

### 48. Thonny
**Категория:** ⚙️ IDE
**Платформа:** 🍓 Raspberry Pi
**Где Git:** Tools menu
**Клонировать:** `git clone URL` in tools → Open system shell

### 49. Mu
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Tools menu
**Клонировать:** `git clone URL` in tools → Open system shell

### 50. Arduino IDE
**Категория:** ⚙️ IDE
**Платформа:** 🌍 All
**Где Git:** Sketch menu
**Клонировать:** `git clone URL` in terminal
**Настройки:** File → Preferences → Show verbose output

---

## PART 4: TROUBLESHOOTING

### Token expired
```bash
# Generate new token at:
https://github.com/settings/tokens

# Then update remote:
git remote set-url origin https://NEW_TOKEN@github.com/Yury197812/REPO.git
```

### 2FA required
- Open browser → github.com/login
- Continue with Google
- Confirm on phone (Tecno SPARK 20C)

### Permission denied
```bash
# Check token:
curl -H "Authorization: token ghp_YEhX7Q9YX9Ukbt8g3YaELsFZnwdUFf1S_FBw" https://api.github.com/user

# If expired, regenerate at:
https://github.com/settings/tokens
```

### Wrong password
- Use token instead of password
- Or login via Google SSO

---

*Generated: 2026-08-12 | ALL 50 IDE | ALL SKILLS*
