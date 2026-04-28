#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
SCHOLL_RESULTS_DIR="${SCHOLL_RESULTS_DIR:-$ROOT/results_doe_scholl_l9}"
OTTO_RESULTS_DIR="${OTTO_RESULTS_DIR:-$ROOT/results_doe_otto_l9}"
DOE_DESIGN="${DOE_DESIGN:-l9}"
DOE_FIXED_R_E="${DOE_FIXED_R_E:-0.05}"
DOE_FIXED_C_C="${DOE_FIXED_C_C:-5.0}"
TIME_LIMIT="${TIME_LIMIT:-300}"
POLL_SECONDS="${POLL_SECONDS:-60}"
STOP_FILE="$ROOT/run_control/STOP_OTTO_AFTER_SCHOLL"
HEARTBEAT_FILE="$ROOT/run_control/otto_after_scholl.heartbeat"

mkdir -p "$ROOT/logs" "$ROOT/run_control"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[chain] Python executable not found: $PYTHON_BIN"
  exit 1
fi

echo "[chain] waiting for Scholl completion before launching Otto"
echo "[chain] scholl_results_dir=$SCHOLL_RESULTS_DIR"
echo "[chain] otto_results_dir=$OTTO_RESULTS_DIR"
echo "[chain] design=$DOE_DESIGN"
echo "[chain] fixed_r_e=$DOE_FIXED_R_E"
echo "[chain] fixed_c_c=$DOE_FIXED_C_C"
echo "[chain] time_limit=$TIME_LIMIT"
echo "[chain] poll_seconds=$POLL_SECONDS"

while true; do
  date "+%Y-%m-%d %H:%M:%S" > "$HEARTBEAT_FILE"

  if [ -f "$STOP_FILE" ]; then
    echo "[chain] stop file detected: $STOP_FILE"
    exit 0
  fi

  status_line="$(SCHOLL_RESULTS_DIR="$SCHOLL_RESULTS_DIR" "$PYTHON_BIN" - <<'PY'
import csv
import json
import os
from pathlib import Path

results_dir = Path(os.environ["SCHOLL_RESULTS_DIR"])
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
  echo "[chain] $(date '+%Y-%m-%d %H:%M:%S') scholl total=$total completed=$completed successful=$successful failed=$failed"

  if [ "${total:-0}" -gt 0 ] && [ "${completed:-0}" -ge "${total:-0}" ] && [ "${failed:-0}" -eq 0 ]; then
    echo "[chain] Scholl is complete. Launching Otto watchdog."
    DOE_DESIGN="$DOE_DESIGN" \
    DOE_FIXED_R_E="$DOE_FIXED_R_E" \
    DOE_FIXED_C_C="$DOE_FIXED_C_C" \
    TIME_LIMIT="$TIME_LIMIT" \
    RESULTS_DIR="$OTTO_RESULTS_DIR" \
    "$ROOT/scripts/start_otto_campaign.sh"
    exit $?
  fi

  sleep "$POLL_SECONDS"
done
