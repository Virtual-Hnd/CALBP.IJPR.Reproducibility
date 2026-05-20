#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/published_results/l9_task_progress_220of252_2026-05-13_19-21-43}"
POLL_SECONDS="${POLL_SECONDS:-60}"
LOG_FILE="${LOG_FILE:-$ROOT/logs/task_standalone_export_watch.log}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$ROOT/run_control/task_standalone_export.heartbeat}"
STOP_FILE="${STOP_FILE:-$ROOT/run_control/STOP_TASK_STANDALONE_EXPORT}"
EXPORTER="$ROOT/exports/export_task_dashboard_standalone.py"

mkdir -p "$ROOT/logs" "$ROOT/run_control" "$ROOT/exports"

echo "[task-standalone-watch] watching $RESULTS_DIR"
echo "[task-standalone-watch] poll_seconds=$POLL_SECONDS"
echo "[task-standalone-watch] log=$LOG_FILE"

while true; do
  date "+%Y-%m-%d %H:%M:%S" > "$HEARTBEAT_FILE"

  if [ -f "$STOP_FILE" ]; then
    echo "[task-standalone-watch] stop file detected: $STOP_FILE"
    exit 0
  fi

  status_line="$(RESULTS_DIR="$RESULTS_DIR" ROOT="$ROOT" python3 - <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ROOT"])
import scripts.dashboard as dashboard

results_dir = Path(os.environ["RESULTS_DIR"])
dashboard.RESULTS_DIR = results_dir
dashboard.SOLUTIONS_DIR = results_dir / "solutions"
data = dashboard.scan_results()

total = data["total_expected"]
completed = data["summary"]["completed"]
successful = data["summary"]["successful"]
failed = data["summary"]["failed"]
print(f"{total} {completed} {successful} {failed}")
PY
)"

  read -r total completed successful failed <<<"$status_line"
  echo "[task-standalone-watch] $(date '+%Y-%m-%d %H:%M:%S') total=$total completed=$completed successful=$successful failed=$failed"

  if [ "${total:-0}" -gt 0 ] && [ "${completed:-0}" -ge "${total:-0}" ] && [ "${failed:-0}" -eq 0 ]; then
    echo "[task-standalone-watch] campaign complete, exporting standalone dashboard"
    RESULTS_DIR="$RESULTS_DIR" python3 "$EXPORTER"
    exit $?
  fi

  sleep "$POLL_SECONDS"
done
