#!/bin/zsh
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

cd "$PROJECT_ROOT" || exit 1
exec "$PYTHON_BIN" -m uvicorn dashboard_server:app --host "$HOST" --port "$PORT"
