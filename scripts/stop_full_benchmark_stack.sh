#!/bin/bash

set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

touch "$ROOT/run_control/STOP_FULL_WATCHDOG"
touch "$ROOT/run_control/STOP_EXPORT_WATCH"

if command -v screen >/dev/null 2>&1; then
  screen -S amine-full-benchmark -X quit >/dev/null 2>&1 || true
  screen -S amine-export-watch -X quit >/dev/null 2>&1 || true
  screen -S amine-dashboard -X quit >/dev/null 2>&1 || true
fi

echo "Stop signals sent to benchmark watchdog, export watcher, and dashboard."
