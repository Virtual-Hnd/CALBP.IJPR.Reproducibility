#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8050}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_scholl_l36}"
LOG_FILE="$ROOT/logs/dashboard.log"
SESSION_NAME="amine-dashboard"

mkdir -p "$ROOT/logs" "$ROOT/run_control"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python executable not found: $PYTHON_BIN"
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
