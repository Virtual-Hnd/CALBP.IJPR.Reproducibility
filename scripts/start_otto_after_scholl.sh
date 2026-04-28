#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STOP_FILE="$ROOT/run_control/STOP_OTTO_AFTER_SCHOLL"
LOG_FILE="$ROOT/logs/otto_after_scholl.log"
WATCHER="$ROOT/scripts/watch_otto_after_scholl.sh"
SESSION_NAME="amine-otto-after-scholl"

mkdir -p "$ROOT/logs" "$ROOT/run_control"
rm -f "$STOP_FILE"

if screen -list | grep -q "[.]$SESSION_NAME[[:space:]]"; then
  echo "Otto-after-Scholl watcher already running (screen session: $SESSION_NAME)"
  echo "Log: $LOG_FILE"
  exit 0
fi

screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT' && '$WATCHER' >> '$LOG_FILE' 2>&1"

echo "Otto-after-Scholl watcher started (screen session: $SESSION_NAME)"
echo "Log: $LOG_FILE"
