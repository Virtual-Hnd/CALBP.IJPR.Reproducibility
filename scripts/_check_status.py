#!/usr/bin/env python3
"""Quick diagnostic: count run statuses in DOE results."""
import json
from pathlib import Path
from collections import Counter

sols = Path(__file__).resolve().parent.parent / "results_doe_L9" / "solutions"
statuses = Counter()
non_ok = []

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
