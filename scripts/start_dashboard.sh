#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8050}"
DOE_DESIGN="${DOE_DESIGN:-l9}"
DOE_FACTOR_GRANULARITY="${DOE_FACTOR_GRANULARITY:-task}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_${DOE_DESIGN}_${DOE_FACTOR_GRANULARITY}}"
LOG_FILE="$ROOT/logs/dashboard.log"
SESSION_NAME="amine-dashboard"

mkdir -p "$ROOT/logs" "$ROOT/run_control"

if ! PYTHON_BIN="$(resolve_python_bin)"; then
  echo "Python executable not found. Set PYTHON_BIN or install python3 / .venv."
  exit 1
fi

if ! require_screen; then
  exit 1
fi

if screen -list | grep -q "[.]$SESSION_NAME[[:space:]]"; then
  echo "Dashboard already running (screen session: $SESSION_NAME)"
  echo "Log: $LOG_FILE"
  exit 0
fi

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use."
  lsof -iTCP:"$PORT" -sTCP:LISTEN
  exit 1
fi

screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT' && DOE_RESULTS_DIR='$RESULTS_DIR' '$PYTHON_BIN' '$ROOT/scripts/dashboard.py' --host '$HOST' --port '$PORT' --no-open >> '$LOG_FILE' 2>&1"

echo "Dashboard started (screen session: $SESSION_NAME)"
echo "Log: $LOG_FILE"
echo "Results: $RESULTS_DIR"
echo "URL: http://localhost:$PORT/"
