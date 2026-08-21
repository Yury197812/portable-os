#!/usr/bin/env bash
# Install the D:\4\ pre-commit hook on this clone.
# Re-run after fresh clone or git clean.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SRC="$REPO_ROOT/scripts/git-hooks/pre-commit"
DST="$REPO_ROOT/.git/hooks/pre-commit"

if [ ! -f "$SRC" ]; then
    echo "ERROR: source hook not found at $SRC"
    exit 1
fi

cp -f "$SRC" "$DST"
# On Windows git bash, `chmod` may be missing — git runs .sh hooks directly.
chmod +x "$DST" 2>/dev/null || true
echo "Installed: $DST"
echo "Test by staging any '_' prefixed file and running: git commit -m test"
