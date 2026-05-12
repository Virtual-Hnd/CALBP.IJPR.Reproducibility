#!/bin/bash

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOE_DESIGN="${DOE_DESIGN:-l9}"
DOE_FACTOR_GRANULARITY="${DOE_FACTOR_GRANULARITY:-task}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_${DOE_DESIGN}_${DOE_FACTOR_GRANULARITY}}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8050}"

echo "[stack] results_dir=$RESULTS_DIR"
echo "[stack] host=$HOST port=$PORT"

RESULTS_DIR="$RESULTS_DIR" DOE_DESIGN="$DOE_DESIGN" DOE_FACTOR_GRANULARITY="$DOE_FACTOR_GRANULARITY" \
  "$ROOT/scripts/start_full_campaign.sh"

RESULTS_DIR="$RESULTS_DIR" SNAPSHOT_LABEL="$(basename "$RESULTS_DIR")" \
  "$ROOT/scripts/start_export_on_completion.sh"

RESULTS_DIR="$RESULTS_DIR" HOST="$HOST" PORT="$PORT" \
  "$ROOT/scripts/start_dashboard.sh"

echo "[stack] benchmark + dashboard launched"
