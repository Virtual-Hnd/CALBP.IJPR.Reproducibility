#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"
STOP_FILE="$ROOT/run_control/STOP_EXPORT_WATCH"
LOG_FILE="$ROOT/logs/export_watch.log"
WATCHER="$ROOT/scripts/watch_export_on_completion.sh"
SESSION_NAME="${SESSION_NAME:-amine-export-watch}"

mkdir -p "$ROOT/logs" "$ROOT/run_control"
rm -f "$STOP_FILE"

if ! require_screen; then
  exit 1
fi

if screen -list | grep -q "[.]$SESSION_NAME[[:space:]]"; then
  echo "Export watcher already running (screen session: $SESSION_NAME)"
  echo "Log: $LOG_FILE"
  exit 0
fi

screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT' && '$WATCHER' >> '$LOG_FILE' 2>&1"

echo "Export watcher started (screen session: $SESSION_NAME)"
echo "Log: $LOG_FILE"
