#!/usr/bin/env bash
# Start the backend directly (macOS/Linux). Mirrors Start-Backend.ps1.
set -euo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-8000}"

BACKEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$("$BACKEND_ROOT/scripts/get-backend-python.sh" "$BACKEND_ROOT")"

echo "Using Python: $PY"
echo "Backend root: $BACKEND_ROOT"

exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
