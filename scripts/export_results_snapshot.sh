#!/bin/bash

set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOE_DESIGN="${DOE_DESIGN:-l9}"
DOE_FACTOR_GRANULARITY="${DOE_FACTOR_GRANULARITY:-task}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_${DOE_DESIGN}_${DOE_FACTOR_GRANULARITY}}"
DEST_ROOT="${DEST_ROOT:-$ROOT/published_results}"
SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-$(basename "$RESULTS_DIR")}"
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
DEST_DIR="$DEST_ROOT/${SNAPSHOT_LABEL}_$TIMESTAMP"

mkdir -p "$DEST_ROOT"

if [ ! -d "$RESULTS_DIR" ]; then
  echo "Results directory not found: $RESULTS_DIR"
  exit 1
fi

if command -v rsync >/dev/null 2>&1; then
  rsync -a "$RESULTS_DIR/" "$DEST_DIR/"
else
  cp -R "$RESULTS_DIR" "$DEST_DIR"
fi

echo "Snapshot exported to: $DEST_DIR"
