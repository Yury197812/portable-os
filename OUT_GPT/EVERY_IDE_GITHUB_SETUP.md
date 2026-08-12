# EVERY IDE + GitHub Setup Guide

## Universal Credentials
- **Username**: Yury197812
- **Email**: apohob5@gmail.com
- **Password**: Klin120478!+123
- **Token**: `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`

## Universal Clone URL
```
https://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@github.com/Yury197812/REPO_NAME.git
```

---

## 1. VSCode / Cursor / Windsurf / VSCodium
1. `Ctrl+Shift+P` → "Git: Clone"
2. Paste URL
3. Terminal: `git remote set-url origin URL`

## 2. JetBrains (IntelliJ IDEA, PyCharm, WebStorm, CLion, Rider, GoLand, PhpStorm, RubyMine, DataGrip, RustRover, Aqua)
1. File → New → Project from Version Control
2. Paste clone URL
3. Settings → Version Control → GitHub → Add token

## 3. Sublime Text
1. Install "Git" package via Package Control
2. Command Palette → Git: Clone
3. Or use Terminal: `git clone URL`

## 4. Vim / Neovim
```vim
:terminal
git clone https://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@github.com/Yury197812/REPO.git
```
Plugins: `vim-fugitive`, `neogit`, `octo.nvim`

## 5. Emacs / Doom Emacs / Spacemacs
```elisp
(shell-command "git clone URL")
```
Package: `magit`

## 6. Atom (archived but still used)
```bash
git clone URL
```
Package: `git-plus`, `git-control`

## 7. Brackets
```bash
git clone URL
```
Extension: "Git" extension

## 8. Eclipse
1. File → Import → Git → Projects from Git
2. Clone URI → paste URL
3. Team → Share Project → Git

## 9. NetBeans
1. Team → Git → Clone
2. Paste URL
3. Team → Commit/Push

## 10. Lazarus / Free Pascal
1. Package → Install Package → lazarus_git
2. Team → Git → Clone

## 11. Qt Creator
1. Tools → Git → Clone Repository
2. Paste URL

## 12. Xcode
1. Source Control → Clone
2. Paste URL
Or: `git clone URL` in terminal

## 13. Android Studio
1. File → New → Project from Version Control
2. Paste URL

## 14. Raspberry Pi IDE (Thonny, Geany, Mu)
```bash
git clone URL
```

## 15. Arduino IDE
```bash
git clone URL
```

## 16. Unity
1. Window → Package Manager → Git package
2. Or: `git clone URL` in project folder

## 17. Unreal Engine
1. Source Control → Connect to Source Control → Git
2. Paste URL

## 18. Godot
1. Editor → Manage Editor Features → Git
2. Or: `git clone URL`

## 19. Visual Studio (not VSCode)
1. Team → Connect to GitHub
2. Or: Git → Clone → paste URL

## 20. Nova (Panic)
1. Source Control → Clone Repository
2. Paste URL

## 21. Helix
```bash
git clone URL
```

## 22. Zed
1. File → Clone Repository
2. Paste URL

## 23. Lapce
1. File → Clone Repository
2. Paste URL

## 24. Pulsar (Atom fork)
```bash
git clone URL
```

## 25. Lite XL
```bash
git clone URL
```

## 26. Notepad++ (with Git plugin)
```bash
git clone URL
```
Plugin: "NppGit"

## 27. Kate (KDE)
1. Project → Open Project → Git
2. Or: `git clone URL`

## 28. Geany
```bash
git clone URL
```

## 29. Bluefish
```bash
git clone URL
```

## 30. Coda / Nova
```bash
git clone URL
```

## 31. BBEdit
```bash
git clone URL
```

## 32. TextMate
```bash
git clone URL
```

## 33. MacroMates
```bash
git clone URL
```

## 34. Code::Blocks
```bash
git clone URL
```

## 35. Dev-C++
```bash
git clone URL
```

## 36. CodeLite
```bash
git clone URL
```

## 37. KDevelop
1. Project → Open Project → Git
2. Or: `git clone URL`

## 38. Anjuta (GNOME)
```bash
git clone URL
```

## 39. BlueJ
```bash
git clone URL
```

## 40. Greenfoot
```bash
git clone URL
```

## 41. Jupyter Notebook / JupyterLab
```bash
git clone URL
```
Extension: "Git" in JupyterLab

## 42. Google Colab
```python
!git clone URL
```

## 43. Replit
1. Import from GitHub → paste URL

## 44. CodeSandbox
1. Import from GitHub → paste URL

## 45. StackBlitz
1. Import from GitHub → paste URL

## 46. Gitpod
1. Import from GitHub → paste URL

## 47. GitHub Codespaces
1. Create codespace on repo

## 48. AWS Cloud9
```bash
git clone URL
```

## 49. Theia
1. File → Clone Repository
2. Paste URL

## 50. Che (Eclipse Che)
1. Import from GitHub → paste URL

---

## Quick Commands (any terminal)
```bash
# Clone
git clone https://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@github.com/Yury197812/REPO.git

# Set remote
git remote set-url origin https://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@github.com/Yury197812/REPO.git

# Check auth
curl -H "Authorization: token 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" https://api.github.com/user
```
