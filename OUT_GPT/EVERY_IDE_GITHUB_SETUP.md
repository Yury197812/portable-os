# EVERY IDE + GitHub Setup — Master Guide

## Universal Credentials
- **Username**: Yury197812
- **Email**: apohob5@gmail.com
- **Password**: Klin120478!+123
- **Token**: `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`

## Universal Clone URL
```
https://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@github.com/Yury197812/REPO_NAME.git
```

## Quick Commands (any terminal)
```bash
# Clone
git clone https://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@github.com/Yury197812/REPO.git

# Set remote
git remote set-url origin https://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@github.com/Yury197812/REPO.git

# Check auth
curl -H "Authorization: token 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" https://api.github.com/user

# Config
git config --global user.name "Yury197812"
git config --global user.email "apohob5@gmail.com"
```

---

## IDE-by-IDE Cheat Sheets

### 1. VSCode
**Where to find Git:** Sidebar → Source Control (Ctrl+Shift+G)
**Clone:** Ctrl+Shift+P → "Git: Clone"
**Push/Pull:** Bottom status bar sync icon
**Terminal:** Ctrl+`
**Settings:** File → Preferences → Settings → search "git"
**GitHub extension:** Extensions → search "GitHub" → Install
**Auth:** Use token in clone URL or Settings → Git → Paths → Git credential helper

### 2. Cursor
**Where to find Git:** Same as VSCode (Cursor = VSCode fork)
**Clone:** Ctrl+Shift+P → "Git: Clone"
**AI features:** Ctrl+K (generate), Ctrl+L (chat)
**Terminal:** Ctrl+`
**Settings:** File → Preferences → Settings

### 3. Windsurf
**Where to find Git:** Same as VSCode
**Clone:** Ctrl+Shift+P → "Git: Clone"
**Cascade AI:** Ctrl+L
**Terminal:** Ctrl+`

### 4. JetBrains (IntelliJ, PyCharm, WebStorm, CLion, Rider, GoLand, PhpStorm, RubyMine, DataGrip, RustRover, Aqua)
**Where to find Git:** Bottom panel → Version Control
**Clone:** File → New → Project from Version Control
**Push/Pull:** VCS → Git → Push/Pull
**Auth:** Settings → Version Control → GitHub → + → Add token
**Terminal:** Alt+F12
**Branches:** Bottom-right branch name

### 5. Sublime Text
**Where to find Git:** Install "Git" package first
**Install:** Ctrl+Shift+P → "Package Control: Install Package" → "Git"
**Clone:** Command Palette → "Git: Clone"
**Commands:** Command Palette → "Git:" + command name
**Terminal:** Install "Terminall" package

### 6. Vim / Neovim
**Where to find Git:** Status line (with vim-fugitive)
**Clone:** `:terminal` then `git clone URL`
**Commands:** `:Git` (fugitive), `:Git push`, `:Git pull`
**Plugins:** vim-fugitive, neogit, octo.nvim, gitsigns.nvim
**Status:** `:Git status`, `:Git diff`

### 7. Emacs / Doom Emacs / Spacemacs
**Where to find Git:** Mode line shows branch
**Clone:** `M-x magit-clone`
**Commands:** `M-x magit-status` (Ctrl+x g in Doom)
**Push/Pull:** In magit buffer: `P` push, `F` pull
**Package:** magit (built-in in Doom)

### 8. Atom (archived)
**Where to find Git:** Bottom status bar
**Clone:** Ctrl+Shift+P → "Git: Clone"
**Packages:** git-plus, git-control, merge-conflicts
**Push/Pull:** Packages → Git Plus → Push/Pull

### 9. Brackets
**Where to find Git:** Sidebar extensions
**Clone:** Install "Git" extension → File → Clone
**Commands:** File → Git menu

### 10. Eclipse
**Where to find Git:** Package Explorer → Team
**Clone:** File → Import → Git → Projects from Git
**Push/Pull:** Team → Push/Pull
**Auth:** Window → Preferences → Team → Git → Configuration

### 11. NetBeans
**Where to find Git:** Team menu
**Clone:** Team → Git → Clone
**Push/Pull:** Team → Push/Pull
**Auth:** Tools → Options → Version Control → Git

### 12. Qt Creator
**Where to find Git:** Tools → Git
**Clone:** Tools → Git → Clone Repository
**Push/Pull:** Tools → Git → Push/Pull
**Auth:** Tools → Options → Version Control → Git

### 13. Xcode
**Where to find Git:** Source Control menu
**Clone:** Source Control → Clone
**Push/Pull:** Source Control → Push/Pull
**Auth:** Xcode → Settings → Source Control → Accounts

### 14. Android Studio
**Where to find Git:** Bottom panel → Version Control
**Clone:** File → New → Project from Version Control
**Push/Pull:** VCS → Git → Push/Pull
**Auth:** File → Settings → Version Control → GitHub

### 15. Visual Studio (not VSCode)
**Where to find Git:** Team Explorer panel
**Clone:** Team → Clone
**Push/Pull:** Team Explorer → Sync
**Auth:** File → Account Settings → Connected Services → GitHub

### 16. Unity
**Where to find Git:** Window → Package Manager
**Clone:** Window → Package Manager → + → Add package from git URL
**Manual:** `git clone URL` in project folder
**Auth:** Edit → Preferences → External Tools → Git

### 17. Unreal Engine
**Where to find Git:** Source Control menu (bottom-right)
**Connect:** Source Control → Connect to Source Control → Git
**Push/Pull:** Source Control menu
**Auth:** Project Settings → Plugins → Git

### 18. Godot
**Where to find Git:** Project → Version Control
**Clone:** `git clone URL` in project folder
**Auth:** Project → Project Settings → Version Control → Git

### 19. Zed
**Where to find Git:** Sidebar
**Clone:** File → Clone Repository
**Commands:** Ctrl+Shift+P → Git commands
**Terminal:** Ctrl+`

### 20. Lapce
**Where to find Git:** Sidebar
**Clone:** File → Clone Repository
**Terminal:** Ctrl+`

### 21. Helix
**Where to find Git:** Shell commands
**Clone:** `:sh git clone URL`
**Commands:** `:sh git status`, `:sh git push`

### 22. Pulsar (Atom fork)
**Where to find Git:** Same as Atom
**Clone:** Ctrl+Shift+P → "Git: Clone"

### 23. Lite XL
**Where to find Git:** Terminal
**Clone:** `git clone URL` in terminal

### 24. Notepad++
**Where to find Git:** Install NppGit plugin
**Clone:** Plugins → NppGit → Clone
**Commands:** Plugins → NppGit → commands

### 25. Kate (KDE)
**Where to find Git:** Project menu
**Clone:** Project → Open Project → Git
**Terminal:** View → Tool Views → Terminal

### 26. Geany
**Where to find Git:** Build menu
**Clone:** `git clone URL` in terminal
**Terminal:** Build → Terminal

### 27. Code::Blocks
**Where to find Git:** Terminal
**Clone:** `git clone URL` in terminal

### 28. Dev-C++
**Where to find Git:** Terminal
**Clone:** `git clone URL` in terminal

### 29. CodeLite
**Where to find Git:** Git menu
**Clone:** Git → Clone Repository
**Push/Pull:** Git → Push/Pull

### 30. KDevelop
**Where to find Git:** Project menu
**Clone:** Project → Open Project → Git

### 31. Jupyter Notebook
**Where to find Git:** Terminal cell
**Clone:** `!git clone URL` in cell
**Extension:** JupyterLab Git extension

### 32. JupyterLab
**Where to find Git:** Git menu (with extension)
**Clone:** Git → Clone
**Push/Pull:** Git menu

### 33. Google Colab
**Where to find Git:** Code cell
**Clone:** `!git clone URL` in cell
**Mount:** `from google.colab import drive; drive.mount('/content/drive')`

### 34. Replit
**Where to find Git:** Import menu
**Clone:** Import from GitHub → paste URL

### 35. CodeSandbox
**Where to find Git:** Import menu
**Clone:** Import from GitHub → paste URL

### 36. StackBlitz
**Where to find Git:** Import menu
**Clone:** Import from GitHub → paste URL

### 37. Gitpod
**Where to find Git:** Import menu
**Clone:** Import from GitHub → paste URL

### 38. GitHub Codespaces
**Where to find Git:** Built-in
**Create:** Create codespace on repo
**Terminal:** Built-in terminal

### 39. AWS Cloud9
**Where to find Git:** Terminal
**Clone:** `git clone URL` in terminal

### 40. Theia
**Where to find Git:** Same as VSCode
**Clone:** File → Clone Repository

### 41. Eclipse Che
**Where to find Git:** Import menu
**Clone:** Import from GitHub → paste URL

### 42. Nova (Panic, macOS)
**Where to find Git:** Source Control menu
**Clone:** Source Control → Clone Repository
**Push/Pull:** Source Control menu

### 43. BBEdit (macOS)
**Where to find Git:** Terminal
**Clone:** `git clone URL` in terminal
**Window → Show Terminal**

### 44. TextMate (macOS)
**Where to find Git:** Bundles menu
**Clone:** `git clone URL` in terminal

### 45. Lazarus / Free Pascal
**Where to find Git:** Package → Install lazarus_git
**Clone:** `git clone URL` in terminal

### 46. BlueJ (Java)
**Where to find Git:** Project menu
**Clone:** `git clone URL` in terminal

### 47. Greenfoot (Java)
**Where to find Git:** Terminal
**Clone:** `git clone URL` in terminal

### 48. Thonny (Python, Raspberry Pi)
**Where to find Git:** Tools menu
**Clone:** `git clone URL` in tools → Open system shell

### 49. Mu (Python)
**Where to find Git:** Tools menu
**Clone:** `git clone URL` in tools → Open system shell

### 50. Arduino IDE
**Where to find Git:** Sketch menu
**Clone:** `git clone URL` in terminal
**File → Preferences → Show verbose output**

---

## Browser Quick Login
1. Go to https://github.com/login
2. Click "Continue with Google"
3. Email: apohob5@gmail.com
4. Password: Klin120478!+123
5. Confirm 2FA on phone (Tecno SPARK 20C)

## Repositories
- `portable-os` (private)
- `science-books-1001-proofs`
- `cdp_rs`
- `portable-blocks`
