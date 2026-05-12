#!/bin/bash

set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/_common.sh"

DOE_DESIGN="${DOE_DESIGN:-l9}"
DOE_FACTOR_GRANULARITY="${DOE_FACTOR_GRANULARITY:-task}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT/results_doe_${DOE_DESIGN}_${DOE_FACTOR_GRANULARITY}}"
PORT="${PORT:-8050}"
PYTHON_BIN="$(resolve_python_bin)"

echo "[status] results_dir=$RESULTS_DIR"
echo "[status] dashboard_port=$PORT"

if command -v screen >/dev/null 2>&1; then
  echo "[status] screen sessions:"
  screen -list || true
else
  echo "[status] screen not available"
fi

echo "[status] progress:"
RESULTS_DIR="$RESULTS_DIR" "$PYTHON_BIN" - <<'PY'
import csv
import json
import os
from pathlib import Path

results = Path(os.environ["RESULTS_DIR"])
manifest = results / "doe_manifest.csv"
solutions = results / "solutions"

total = 0
if manifest.exists():
    with open(manifest, encoding="utf-8") as f:
        total = sum(1 for _ in csv.DictReader(f))

completed = ok = failed = 0
for path in solutions.glob("*/run_info.json"):
    completed += 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        failed += 1
        continue
    if data.get("status") == "OK":
        ok += 1
    else:
        failed += 1

pending = max(total - completed, 0)
print({
    "total": total,
    "completed": completed,
    "ok": ok,
    "failed": failed,
    "pending": pending,
})
PY

if [ -f "$ROOT/logs/full_watchdog.log" ]; then
  echo "[status] watchdog tail:"
  tail -n 10 "$ROOT/logs/full_watchdog.log"
fi

if [ -f "$ROOT/logs/export_watch.log" ]; then
  echo "[status] export tail:"
  tail -n 5 "$ROOT/logs/export_watch.log"
fi

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[status] dashboard listening on http://localhost:$PORT/"
else
  echo "[status] dashboard is not listening on port $PORT"
fi
