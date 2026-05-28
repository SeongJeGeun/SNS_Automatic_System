#!/bin/bash
set -euo pipefail

PROJECT_DIR="${SNS_AUTOMATIC_PROJECT_DIR:-$HOME/Documents/SNS_Automatic_System}"
BRANCH="${SNS_AUTOMATIC_BRANCH:-main}"
LOCK_FILE="$PROJECT_DIR/.running.lock"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/run_cycle.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

exec >> "$LOG_FILE" 2>&1

echo ""
echo "============================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] SNS automation cycle started"
echo "Project: $PROJECT_DIR"
echo "Branch: $BRANCH"

if [ -f "$LOCK_FILE" ]; then
  echo "Another cycle is already running. Skip this run."
  exit 0
fi

touch "$LOCK_FILE"
cleanup() {
  rm -f "$LOCK_FILE"
}
trap cleanup EXIT

echo "[1/7] Check git branch"
CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
  echo "Current branch is '$CURRENT_BRANCH', expected '$BRANCH'. Abort."
  exit 1
fi

echo "[2/7] Check local working tree before pull"
if [ -n "$(git status --porcelain)" ]; then
  echo "Local uncommitted changes detected. Abort to avoid overwriting work."
  git status --short
  exit 1
fi

echo "[3/7] Fetch remote updates"
git fetch origin "$BRANCH"
LOCAL_COMMIT="$(git rev-parse HEAD)"
REMOTE_COMMIT="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
  echo "Remote update found. Pull with --ff-only."
  git pull --ff-only origin "$BRANCH"
else
  echo "No remote update. Continue with current code."
fi

echo "[4/7] Activate virtual environment"
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo ".venv not found. Create it first with: python3 -m venv .venv"
  exit 1
fi

echo "[5/7] Sync Python dependencies"
python3 -m pip install -r requirements.txt

echo "[6/7] Run main orchestrator"
python3 main_orchestrator.py

echo "[7/7] Commit safe tracked output changes if any"
git add README.md docs .env.example *.py run_cycle.sh 2>/dev/null || true

if [ -n "$(git status --porcelain)" ]; then
  git commit -m "chore: update automation outputs"
  git push origin "$BRANCH"
else
  echo "No safe changes to commit."
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SNS automation cycle finished"