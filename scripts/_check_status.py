#!/usr/bin/env python3
"""Quick diagnostic: count run statuses in DOE results."""
import json
import os
import sys
from pathlib import Path
from collections import Counter

results_dir = Path(
    os.environ.get(
        "DOE_RESULTS_DIR",
        str(Path(__file__).resolve().parent.parent / "results_doe_L9"),
    )
)
sols = results_dir / "solutions"
statuses = Counter()
non_ok = []

if not sols.exists():
    print(f"Aucun dossier de solutions: {sols}")
    sys.exit(0)

for d in sorted(sols.iterdir()):
    if not d.is_dir():
        continue
    ri = d / "run_info.json"
    if ri.exists():
        info = json.loads(ri.read_text())
        s = info.get("status", "MISSING_STATUS")
        statuses[s] += 1
        if s != "OK":
            non_ok.append((d.name, s))

print("=== Statuts ===")
for s, c in statuses.most_common():
    print(f"  {s}: {c}")
print(f"\nTotal runs: {sum(statuses.values())}")
print(f"Non-OK: {len(non_ok)}")
for name, s in non_ok[:10]:
    print(f"  {name}: {s}")
if len(non_ok) > 10:
    print(f"  ... et {len(non_ok)-10} de plus")
