#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"
DOE_DESIGN="${DOE_DESIGN:-l36}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_scholl_${DOE_DESIGN}}"
DOE_FIXED_R_E="${DOE_FIXED_R_E:-0.05}"
DOE_FIXED_C_C="${DOE_FIXED_C_C:-5.0}"
TIME_LIMIT="${TIME_LIMIT:-300}"
STOP_FILE="$ROOT/run_control/STOP_SCHOLL_WATCHDOG"
HEARTBEAT_FILE="$ROOT/run_control/scholl_watchdog.heartbeat"

INSTANCES=(
  Scholl_MERTENS
  Scholl_JAESCHKE
  Scholl_MANSOOR
  Scholl_MITCHELL
  Scholl_BUXEY
  Scholl_SAWYER30
  Scholl_GUNTHER
  Scholl_KILBRID
  Scholl_HAHN
  Scholl_WEE-MAG
  Scholl_ARC83
  Scholl_LUTZ2
  Scholl_MUKHERJE
  Scholl_ARC111
)

mkdir -p "$ROOT/logs" "$ROOT/run_control"

if ! PYTHON_BIN="$(resolve_python_bin)"; then
  echo "[watchdog] Python executable not found. Set PYTHON_BIN or install python3 / .venv."
  exit 1
fi

if ! CPLEX_CMD="$(resolve_cplex_cmd)"; then
  echo "[watchdog] CPLEX executable not found. Set CPLEX_CMD, CPLEX_BIN, or CPLEX_STUDIO_DIR."
  exit 1
fi

echo "[watchdog] starting Scholl-only campaign"
echo "[watchdog] python=$PYTHON_BIN"
echo "[watchdog] cplex=$CPLEX_CMD"
echo "[watchdog] design=$DOE_DESIGN"
echo "[watchdog] results_dir=$RESULTS_DIR"
echo "[watchdog] fixed_r_e=$DOE_FIXED_R_E"
echo "[watchdog] fixed_c_c=$DOE_FIXED_C_C"
echo "[watchdog] time_limit=${TIME_LIMIT}s"

while true; do
  date "+%Y-%m-%d %H:%M:%S" > "$HEARTBEAT_FILE"

  if [ -f "$STOP_FILE" ]; then
    echo "[watchdog] stop file detected: $STOP_FILE"
    exit 0
  fi

  echo "[watchdog] $(date '+%Y-%m-%d %H:%M:%S') launching/resuming DOE"
  CPLEX_CMD="$CPLEX_CMD" DOE_FIXED_R_E="$DOE_FIXED_R_E" DOE_FIXED_C_C="$DOE_FIXED_C_C" "$PYTHON_BIN" "$ROOT/scripts/run_doe_L9.py" \
    --design "$DOE_DESIGN" \
    --results-dir "$RESULTS_DIR" \
    --fixed-r-e "$DOE_FIXED_R_E" \
    --fixed-c-c "$DOE_FIXED_C_C" \
    --resume \
    --time-limit "$TIME_LIMIT" \
    --instances "${INSTANCES[@]}"
  status=$?

  date "+%Y-%m-%d %H:%M:%S" > "$HEARTBEAT_FILE"

  if [ "$status" -eq 0 ]; then
    echo "[watchdog] campaign completed successfully"
    exit 0
  fi

  echo "[watchdog] DOE exited with status $status; retrying in 30s"
  sleep 30
done
