#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"
DOE_DESIGN="${DOE_DESIGN:-l9}"
DOE_FACTOR_GRANULARITY="${DOE_FACTOR_GRANULARITY:-task}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_${DOE_DESIGN}_${DOE_FACTOR_GRANULARITY}}"
POLL_SECONDS="${POLL_SECONDS:-60}"
STOP_FILE="$ROOT/run_control/STOP_EXPORT_WATCH"
HEARTBEAT_FILE="$ROOT/run_control/export_watch.heartbeat"
SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-$(basename "$RESULTS_DIR")}"

mkdir -p "$ROOT/logs" "$ROOT/run_control"

if ! PYTHON_BIN="$(resolve_python_bin)"; then
  echo "[export-watch] Python executable not found. Set PYTHON_BIN or install python3 / .venv."
  exit 1
fi

echo "[export-watch] watching $RESULTS_DIR"
echo "[export-watch] snapshot_label=$SNAPSHOT_LABEL"
echo "[export-watch] poll_seconds=$POLL_SECONDS"

while true; do
  date "+%Y-%m-%d %H:%M:%S" > "$HEARTBEAT_FILE"

  if [ -f "$STOP_FILE" ]; then
    echo "[export-watch] stop file detected: $STOP_FILE"
    exit 0
  fi

  status_line="$(RESULTS_DIR="$RESULTS_DIR" "$PYTHON_BIN" - <<'PY'
import csv
import json
import os
from pathlib import Path

results_dir = Path(os.environ["RESULTS_DIR"])
manifest = results_dir / "doe_manifest.csv"
solutions = results_dir / "solutions"

total = 0
if manifest.exists():
    with open(manifest, encoding="utf-8") as f:
        total = max(sum(1 for _ in csv.DictReader(f)), 0)

completed = successful = failed = 0
if solutions.exists():
    for path in solutions.glob("*/run_info.json"):
        completed += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            failed += 1
            continue
        if data.get("status") == "OK":
            successful += 1
        else:
            failed += 1

print(f"{total} {completed} {successful} {failed}")
PY
)"

  read -r total completed successful failed <<<"$status_line"
  echo "[export-watch] $(date '+%Y-%m-%d %H:%M:%S') total=$total completed=$completed successful=$successful failed=$failed"

  if [ "${total:-0}" -gt 0 ] && [ "${completed:-0}" -ge "${total:-0}" ] && [ "${failed:-0}" -eq 0 ]; then
    echo "[export-watch] benchmark complete, exporting snapshot"
    RESULTS_DIR="$RESULTS_DIR" SNAPSHOT_LABEL="$SNAPSHOT_LABEL" "$ROOT/scripts/export_results_snapshot.sh"
    exit $?
  fi

  sleep "$POLL_SECONDS"
done
