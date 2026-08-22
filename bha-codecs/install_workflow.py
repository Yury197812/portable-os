#!/usr/bin/env python
"""Install bha-codecs-ci.yml workflow at the parent portable-os repo root.

Why this is needed:
  The bha-codecs subproject lives at portable-os/bha-codecs/.
  GitHub Actions only picks up workflows from <repo_root>/.github/workflows/.
  We can't write to portable-os/.github/workflows/ from inside bha-codecs,
  so we provide this installer script. Run it once to add the workflow
  to the parent portable-os repo.

Usage:
  cd D:\\4
  python bha-codecs\\install_workflow.py
  git add .github\\workflows\\bha-codecs-ci.yml
  git commit -m "ci: add bha-codecs CI workflow"
  git push origin master
"""
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).parent / '.github' / 'workflows' / 'bha-codecs-ci.yml'
DST_PARENT = Path(__file__).parent.parent  # portable-os root
DST = DST_PARENT / '.github' / 'workflows' / 'bha-codecs-ci.yml'


def main() -> int:
    if not SRC.exists():
        print(f'ERROR: source file not found: {SRC}')
        return 1
    if not DST_PARENT.exists():
        print(f'ERROR: parent dir not found: {DST_PARENT}')
        print('Run this from inside the bha-codecs subdirectory of portable-os.')
        return 1
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, DST)
    print(f'Copied: {SRC}')
    print(f'   to: {DST}')
    print()
    print('Next steps:')
    print(f'  cd {DST_PARENT}')
    print(f'  git add .github\\workflows\\bha-codecs-ci.yml')
    print(f'  git commit -m "ci: add bha-codecs CI workflow"')
    print(f'  git push origin master')
    return 0


if __name__ == '__main__':
    sys.exit(main())