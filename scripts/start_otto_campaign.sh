#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STOP_FILE="$ROOT/run_control/STOP_OTTO_WATCHDOG"
LOG_FILE="$ROOT/logs/otto_watchdog.log"
WATCHDOG="$ROOT/scripts/watch_otto_campaign.sh"
SESSION_NAME="amine-otto"

mkdir -p "$ROOT/logs" "$ROOT/run_control"
rm -f "$STOP_FILE"

if screen -list | grep -q "[.]$SESSION_NAME[[:space:]]"; then
  echo "Otto watchdog already running (screen session: $SESSION_NAME)"
  echo "Log: $LOG_FILE"
  exit 0
fi

screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT' && '$WATCHDOG' >> '$LOG_FILE' 2>&1"

echo "Otto watchdog started (screen session: $SESSION_NAME)"
echo "Log: $LOG_FILE"
