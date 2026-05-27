#!/bin/zsh
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_SECONDS="${RUN_SECONDS:-10800}"

cd "$PROJECT_ROOT" || exit 1
mkdir -p agent_runs
"$PYTHON_BIN" main_orchestrator.py &
pid=$!
echo "$pid" > agent_runs/codex_pipeline_3h.pid
sleep "$RUN_SECONDS"
kill "$pid" 2>/dev/null || true
