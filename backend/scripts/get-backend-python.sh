#!/usr/bin/env bash
# Resolve the backend virtualenv Python interpreter (macOS/Linux).
# Mirrors Get-BackendPython.ps1: prefer BACKEND_VENV_PATH, then a repo-local
# .venv. Prints the resolved interpreter path on success.
set -euo pipefail

REPO_BACKEND_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

candidates=()
if [ -n "${BACKEND_VENV_PATH:-}" ]; then
    candidates+=("$BACKEND_VENV_PATH/bin/python")
fi
candidates+=("$REPO_BACKEND_PATH/.venv/bin/python")

for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ]; then
        echo "$candidate"
        exit 0
    fi
done

echo "Could not find a backend Python interpreter. Set BACKEND_VENV_PATH to an external venv, or create one at backend/.venv." >&2
exit 1
