#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"
STOP_FILE="$ROOT/run_control/STOP_SCHOLL_WATCHDOG"
LOG_FILE="$ROOT/logs/scholl_watchdog.log"
WATCHDOG="$ROOT/scripts/watch_scholl_campaign.sh"
SESSION_NAME="amine-scholl"

mkdir -p "$ROOT/logs" "$ROOT/run_control"
rm -f "$STOP_FILE"

if ! require_screen; then
  exit 1
fi

if screen -list | grep -q "[.]$SESSION_NAME[[:space:]]"; then
  echo "Scholl watchdog already running (screen session: $SESSION_NAME)"
  echo "Log: $LOG_FILE"
  exit 0
fi

screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT' && '$WATCHDOG' >> '$LOG_FILE' 2>&1"

echo "Scholl watchdog started (screen session: $SESSION_NAME)"
echo "Log: $LOG_FILE"
