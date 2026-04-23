#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
CPLEX_BIN_DEFAULT="/Users/admin/Applications/CPLEX_Studio2212/cplex/bin/arm64_osx/cplex"
CPLEX_CMD="${CPLEX_CMD:-$CPLEX_BIN_DEFAULT}"
DOE_DESIGN="${DOE_DESIGN:-l9}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_otto_${DOE_DESIGN}}"
DOE_FIXED_R_E="${DOE_FIXED_R_E:-0.05}"
DOE_FIXED_C_C="${DOE_FIXED_C_C:-5.0}"
TIME_LIMIT="${TIME_LIMIT:-300}"
STOP_FILE="$ROOT/run_control/STOP_OTTO_WATCHDOG"
HEARTBEAT_FILE="$ROOT/run_control/otto_watchdog.heartbeat"

INSTANCES=(
  instance_n=20_63
  instance_n=20_1
  instance_n=20_10
  instance_n=20_77
  instance_n=20_97
  instance_n=20_87
  instance_n=20_69
  instance_n=20_74
  instance_n=20_68
  instance_n=20_73
  instance_n=20_99
  instance_n=20_88
  instance_n=20_91
  instance_n=20_82
)

mkdir -p "$ROOT/logs" "$ROOT/run_control"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[watchdog] Python executable not found: $PYTHON_BIN"
  exit 1
fi

if [ ! -x "$CPLEX_CMD" ]; then
  echo "[watchdog] CPLEX executable not found: $CPLEX_CMD"
  exit 1
fi

echo "[watchdog] starting Otto-only campaign"
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
