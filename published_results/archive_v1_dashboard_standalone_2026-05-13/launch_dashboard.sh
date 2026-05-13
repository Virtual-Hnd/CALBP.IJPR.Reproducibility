#!/bin/bash
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_ROOT="$ROOT/results"
CAMPAIGN="${1:-results_doe_scholl_l9}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8050}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "$RESULTS_ROOT/$CAMPAIGN" ]; then
  echo "Unknown campaign: $CAMPAIGN"
  echo ""
  echo "Available campaigns:"
  find "$RESULTS_ROOT" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; | sort
  exit 1
fi

echo "[dashboard] campaign=$CAMPAIGN"
echo "[dashboard] url=http://$HOST:$PORT/"
DOE_RESULTS_DIR="$RESULTS_ROOT/$CAMPAIGN" \
  "$PYTHON_BIN" "$ROOT/dashboard.py" --host "$HOST" --port "$PORT" --no-open
