"""
Parser for Scholl .IN2 benchmark files.

Format (BOWMAN8.IN2 example):
  Line 1:        number of tasks (n)
  Lines 2..n+1:  task processing time (one per line)
  Remaining:     precedence arcs as "i,j" until "-1,-1"
"""

import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class SchollInstance:
    """Raw data parsed from a Scholl .IN2 file."""
    name: str
    n_tasks: int
    task_times: list[int]          # 1-indexed: task_times[0] = time of task 1
    precedence: list[tuple[int, int]]
    source_path: str = ""
    order_strength: float = 0.0

    def __post_init__(self):
        max_possible = self.n_tasks * (self.n_tasks - 1) / 2
        if max_possible > 0:
            self.order_strength = len(self.precedence) / max_possible


def parse_in2(path: Path | str) -> SchollInstance:
    """Parse a single .IN2 file and return a SchollInstance."""
    path = Path(path)
    raw = path.read_text(encoding="latin-1", errors="ignore")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    it = iter(lines)
    n = int(next(it))

    times: list[int] = []
    for _ in range(n):
        # Some files have "time  station_limit" — take first token
        tok = next(it).split()[0]
        times.append(int(tok))

    arcs: list[tuple[int, int]] = []
    for ln in it:
        if "-1,-1" in ln.replace(" ", ""):
            break
        m = re.search(r"(\d+)\s*,\s*(\d+)", ln)
        if m:
            i, j = int(m.group(1)), int(m.group(2))
            arcs.append((i, j))

    return SchollInstance(
        name=path.stem,
        n_tasks=n,
        task_times=times,
        precedence=arcs,
        source_path=str(path),
    )


def load_all_scholl(directory: Path | str) -> list[SchollInstance]:
    """Load all .IN2 files from a directory, sorted by name."""
    directory = Path(directory)
    instances = []
    for f in sorted(directory.glob("*.IN2")):
        try:
            instances.append(parse_in2(f))
        except Exception as e:
            print(f"[WARN] Failed to parse {f.name}: {e}")
    return instances
