#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"
STOP_FILE="$ROOT/run_control/STOP_FULL_WATCHDOG"
LOG_FILE="$ROOT/logs/full_watchdog.log"
WATCHDOG="$ROOT/scripts/watch_full_campaign.sh"
SESSION_NAME="${SESSION_NAME:-amine-full-benchmark}"

mkdir -p "$ROOT/logs" "$ROOT/run_control"
rm -f "$STOP_FILE"

if ! require_screen; then
  exit 1
fi

if screen -list | grep -q "[.]$SESSION_NAME[[:space:]]"; then
  echo "Full benchmark watchdog already running (screen session: $SESSION_NAME)"
  echo "Log: $LOG_FILE"
  exit 0
fi

screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT' && '$WATCHDOG' >> '$LOG_FILE' 2>&1"

echo "Full benchmark watchdog started (screen session: $SESSION_NAME)"
echo "Log: $LOG_FILE"
