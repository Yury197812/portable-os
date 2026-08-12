# ULTIMATE MASTER GUIDE — ALL 50 IDE + ALL SKILLS + ACCELERATION

---
## PART 1: CREDENTIALS

## GitHub Account
- **Username:** {USER}
- **Email:** {EMAIL}
- **Password:** Klin120478!+123
- **Token:** `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`

## Universal Clone URL
```
https://{TOKEN}@github.com/{USER}/REPO_NAME.git

## Browser Login
→ https://github.com/login
→ "Continue with Google"
→ Email: {EMAIL}
→ Password: Klin120478!+123
→ Confirm 2FA on phone (Tecno SPARK 20C)

## PART 2: QUICK COMMANDS

```
# Clone
git clone https://{TOKEN}@github.com/{USER}/REPO.git

# Set remote
git remote set-url origin https://{TOKEN}@github.com/{USER}/REPO.git

# Check auth
curl -H "Authorization: token {TOKEN}" https://api.github.com/user

# List repos
curl -H "Authorization: token {TOKEN}" https://api.github.com/user/repos

# Create repo
curl -X POST -H "Authorization: token {TOKEN}" https://api.github.com/user/repos -d '{"name":"REPO","private":true}'

# Upload file
curl -X PUT -H "Authorization: token {TOKEN}" https://api.github.com/repos/{USER}/REPO/contents/PATH -d '{"message":"add","content":"BASE64"}'

# Config
git config --global user.name "{USER}"
git config --global user.email "{EMAIL}"

## PART 3: ACCELERATION SKILLS

## Skill: Recursive Acceleration Protocol
**Principle:** Every Python function >1000 calls| Task | Lang | Why |
|------|------|-----|
| HTTP fetch | Rust (reqwest) | Connection pool, HTTP/2 |
| HTML parse | Rust (scraper) | 20-50x vs BeautifulSoup |
| Hash/SHA | Rust (sha2) | 10x vs hashlib |
| SQLite | Rust (rusqlite) | WAL mode, batch |
| Rate limit | Rust (atomic) | 100x vs asyncio |
| Graph algo | C (BFS/DFS) | Minimal overhead |
| Concurrency | Go (goroutines) | Channels, worker pools |
| Pipeline | Go (channels) | Natural data flow |
| Logging | Go (zerolog) | Structured, fast |
| Caching | Go (sync.Map) | Thread-safe LRU |
| LLM inference | C (llama.cpp) | Native, no Python |
| Training | Python (transformers) | Only option for LoRA |
| Hot loops | MASM (AVX2) | SIMD vectorization |

**Workflow:**
→ Is this a hot path? → Check speed_blocks/
   YES → Use existing block| Tool | Purpose | Speed |
|------|---------|-------|
| Speed Block | Rust/Go/C for hot paths | 10-100x |
| Batch Processor | Parallel file operations | 5-20x |
| Pipeline | Sequential automation | 3-10x |
| Cache | Memoization | 2-10x |

**Auto-Acceleration Checklist:**
□ Called >1000 times? → Speed block
□ Processing text? → Rust scraper
□ HTTP? → Rust reqwest
□ Concurrency? → Go goroutines
□ Hot loop? → MASM AVX2
□ I/O bound? → Rust tokio
□ Data transformation? → Go pipeline

## Skill: 32 Optimization Iterations
**Iterations 1-8: Generator Optimization**
| # | Optimization | Result |
|---|--------------|--------|
| 1 | Caching results | +15% speed |
| 2 | Precompute constants | +10% speed |
| 3 | Reduce function calls | +8% speed |
| 4 | Local variables | +5% speed |
| 5 | String optimization | +12% speed |
| 6 | Minimize allocations | +7% speed |
| 7 | Loop optimization | +6% speed |
| 8 | Batch operations | +9% speed |

**Iterations 9-16: Parallel Processing**
| 9 | ProcessPoolExecutor | +400% at 4 cores |
| 10 | Optimal distribution | +50% balance |
| 11 | Reduce overhead | +15% IPC |
| 12 | Serialization optimization | +20% speed |
| 13 | Batch data transfer | +25% throughput |
| 14 | Async writes | +30% I/O |
| 15 | Output buffering | +18% speed |
| 16 | Memory optimization | +12% RSS |

**Iterations 17-24: I/O Optimization**
| 17 | StringIO buffer | +40% write |
| 18 | Minimal allocations | +25% memory |
| 19 | Batch writes | +35% disk |
| 20 | Encoding optimization | +15% CPU |
| 21 | Synchronous writes | +10% IOPS |
| 22 | Format optimization | +20% size |
| 23 | Buffer preallocation | +12% speed |
| 24 | Flush optimization | +8% latency |

**Iterations 25-32: Scaling**
| 25 | Horizontal scaling | +100% throughput |
| 26 | Optimal batch size | +30% efficiency |
| 27 | Load balancing | +25% utilization |
| 28 | Cache optimization | +20% hit rate |
| 29 | Data compression | +40% size |
| 30 | Allocation optimization | +15% GC |
| 31 | Memory optimization | +12% RSS |
| 32 | Final optimization | +5% total |

**Results:**
| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Time | 10 sec | 0.345 sec | **29x** |
| Speed | 3,700/sec | 92,751/sec | **25x** |
| Memory | 100 MB | 50 MB | **2x** |
| Files | 100 | 32 | **3x** |

## Skill: Pipeline Orchestrator
**Structure:**
```
pipeline: article-export
stages:
  - name: extract
    parallel: true
    steps:
      - scan_files
      - extract_chapters
  - name: transform
      - convert_to_html
      - generate_tags
  - name: load
      - export_to_directory

**Python Implementation:**
```
from dataclasses import dataclass
from typing import List, Callable
from concurrent.futures import ThreadPoolExecutor

@dataclass
class Step:
    name: str
    fn: Callable
    parallel: bool = False

class Stage:
    steps: List[Step]

class Pipeline:
    def __init__(self, stages: List[Stage]):
        self.stages = stages

    def run(self, data):
        for stage in self.stages:
            data = self.run_stage(stage, data)
        return data

    def run_stage(self, stage, data):
        if any(s.parallel for s in stage.steps):
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(s.fn, data): s for s in stage.steps}
                for future in futures:
                    data = future.result()
        else:
            for step in stage.steps:
                data = step.fn(data)

## PART 4: IDE-SPECIFIC SKILLS

## Skill: VSCode / Cursor / Windsurf
→ Ctrl+Shift+P → "Git: Clone"
→ Paste URL
→ Terminal: git remote set-url origin URL
→ Install "GitHub" extension

## Skill: JetBrains (IntelliJ, PyCharm, WebStorm, CLion, Rider, GoLand, PhpStorm, RubyMine, DataGrip, RustRover, Aqua)
→ File → New → Project from Version Control
→ Settings → Version Control → GitHub → Add token

## Skill: Vim / Neovim
```
:terminal
git clone URL
Plugins: vim-fugitive, neogit, octo.nvim

## Skill: Emacs / Doom Emacs
```
M-x magit-clone
M-x magit-status for push/pull

## Skill: Sublime Text
→ Ctrl+Shift+P → "Package Control: Install Package" → "Git"
→ "Git: Clone"

## Skill: Eclipse / NetBeans
→ File → Import → Git → Projects from Git
→ Clone URI → paste URL

## Skill: Xcode
→ Source Control → Clone
→ Settings → Source Control → Accounts → Add token

## Skill: Android Studio
→ Settings → Version Control → GitHub → Add token

## Skill: Visual Studio
→ Team → Clone
→ File → Account Settings → Connected Services → GitHub

## Skill: Unity / Unreal / Godot
Open project folder in IDE

## Skill: Jupyter / JupyterLab
!git clone URL

## Skill: Cloud IDEs (Replit, CodeSandbox, StackBlitz, Gitpod, Codespaces)
Import from GitHub → paste URL

## Skill: Zed / Lapce / Helix

## Skill: Notepad++
Install NppGit plugin → Plugins → NppGit → Clone

## Skill: Kate (KDE)
Project → Open Project → Git → paste URL

## Skill: Code::Blocks / Dev-C++ / CodeLite

## Skill: Arduino IDE

## Skill: Raspberry Pi (Thonny, Mu, Geany)

## Skill: AWS Cloud9
Terminal: git clone URL

## PART 5: ALL 50 IDE CHEAT SHEETS

## VSCode
**Cat:** 📝 | **Plat:** 🌍
**Git:** Sidebar → Source Control (Ctrl+Shift+G)
**Clone:** Ctrl+Shift+P → "Git: Clone"
**Push:** Bottom status bar| **Plat:** 🌍
**Git:** =VSCode
**AI:** Ctrl+K (generate), Ctrl+L (chat)

## Windsurf
**AI:** Ctrl+L (Cascade)

## JetBrains
**Cat:** ⚙️ | **Plat:** 🌍
**Git:** Bottom panel → Version Control
**Clone:** File → New → Project from Version Control
**Push:** VCS → Git → Push/Pull| **Plat:** 🍎
**Clone:** Source Control → Clone

## Android Studio

## Visual Studio
**Cat:** ⚙️ | **Plat:** 🪟
**Clone:** Team → Clone

## Unity
**Cat:** ⚙️G | **Plat:** 🌍
**Clone:** git clone URL

## Unreal Engine
**Conn:** Source Control → Connect to Source Control → Git

## Godot

## Zed
**Clone:** File → Clone Repository

## Lapce

## Helix
**Clone:** :sh git clone URL

## Pulsar (Atom fork)

## Lite XL
**Clone:** git clone URL

## Notepad++
**Cat:** 📝 | **Plat:** 🪟
**Clone:** Plugins → NppGit → Clone

## Kate (KDE)
**Cat:** 📝 | **Plat:** 🐧
**Clone:** Project → Open Project → Git

## Geany

## Code::Blocks

## Dev-C++

## CodeLite
**Clone:** Git → Clone Repository

## KDevelop
**Cat:** ⚙️ | **Plat:** 🐧

## Jupyter Notebook
**Cat:** 📓 | **Plat:** 🌍
**Clone:** !git clone URL

## JupyterLab
**Clone:** Git → Clone (with extension)

## Google Colab
**Cat:** ☁️ | **Plat:** ☁️B

## Replit
**Clone:** Import from GitHub

## CodeSandbox

## StackBlitz

## Gitpod

## GitHub Codespaces
**Clone:** Create codespace on repo

## AWS Cloud9

## Theia

## Eclipse Che

## Nova (Panic)
**Cat:** 📝 | **Plat:** 🍎
**Clone:** Source Control → Clone Repository

## BBEdit

## TextMate

## Lazarus / Free Pascal

## BlueJ

## Greenfoot

## Thonny
**Cat:** ⚙️ | **Plat:** 🍓
**Clone:** git clone URL

## Mu

## Arduino IDE

## PART 6: TROUBLESHOOTING

## Token expired
# Generate new token:
https://github.com/settings/tokens

# Update remote:
git remote set-url origin https://NEW_TOKEN@github.com/{USER}/REPO.git

## 2FA required
- Browser → github.com/login → Continue with Google → Confirm on phone

## Permission denied

## Wrong password
- Use token instead of password
- Or login via Google SSO

## PART 7: REPOSITORIES

- `portable-os`
- `science-books-1001-proofs`
- `cdp_rs`
- `portable-blocks`

*50 IDE | ALL SKILLS | 29x*
