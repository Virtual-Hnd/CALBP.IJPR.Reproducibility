#!/usr/bin/env python3
"""
collect_run_info.py — Flatten DOE run_info.json files into one summary CSV.

This is useful when results are spread across current runs and archived
campaigns. Each row corresponds to one (instance_name, config_id) pair,
with `config` and `indicators` fields flattened into top-level columns.

Examples
--------
    python scripts/collect_run_info.py
    python scripts/collect_run_info.py --roots results_doe_L9
    python scripts/collect_run_info.py --roots archive --output archive/run_info_flat.csv
    python scripts/collect_run_info.py --dedupe none
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


BASE_FIELDS = [
    "instance_name",
    "config_id",
    "config_name",
    "run_name",
    "source",
    "n_tasks",
    "T",
    "status",
    "n_pareto",
    "n_certified",
    "cert_rate",
    "total_cpu_s",
    "gap_mean_pct",
    "gap_max_pct",
    "timestamp",
]

CONFIG_FIELDS = [
    "alpha_level",
    "beta_level",
    "gamma_level",
    "sigma_level",
    "R_e_level",
    "C_c_level",
    "alpha_ci",
    "beta_su",
    "gamma_setup",
    "sigma_si",
    "alpha_ci_std",
    "beta_su_std",
    "gamma_setup_std",
    "sigma_si_std",
    "R_e",
    "C_c",
    "factor_granularity",
    "seed",
]

INDICATOR_FIELDS = [
    "HV_abs",
    "HV_norm",
    "ref_cost",
    "ref_energy",
    "ideal_cost",
    "ideal_energy",
    "nadir_cost",
    "nadir_energy",
    "spacing",
    "spread_delta",
    "max_spread",
    "cost_range",
    "energy_range",
    "PF_size",
]

TRACE_FIELDS = [
    "results_dir",
    "run_info_path",
]


def find_run_infos(roots: list[Path]) -> list[Path]:
    """Return all run_info.json files under the provided roots."""
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.name == "run_info.json":
            paths.append(root)
            continue
        paths.extend(root.glob("**/run_info.json"))
    return sorted(set(p.resolve() for p in paths))


def detect_results_dir(path: Path) -> str:
    """Best-effort label for the results folder containing this run."""
    for parent in path.parents:
        if parent.name.startswith("results_"):
            return str(parent)
    return str(path.parent)


def flatten_run_info(path: Path) -> dict:
    """Flatten one run_info.json file into a CSV row."""
    data = json.loads(path.read_text(encoding="utf-8"))
    config = data.get("config", {})
    indicators = data.get("indicators", {})

    n_pareto = data.get("n_pareto", 0) or 0
    n_certified = data.get("n_certified", 0) or 0
    cert_rate = (n_certified / n_pareto) if n_pareto else 0.0

    row = {
        "instance_name": data.get("base_instance", ""),
        "config_id": config.get("config_id", ""),
        "config_name": config.get("config_name", ""),
        "run_name": data.get("run_name", ""),
        "source": data.get("source", ""),
        "n_tasks": data.get("n_tasks", ""),
        "T": data.get("T", ""),
        "status": data.get("status", ""),
        "n_pareto": n_pareto,
        "n_certified": n_certified,
        "cert_rate": round(cert_rate, 6),
        "total_cpu_s": data.get("total_cpu_s", ""),
        "gap_mean_pct": data.get("gap_mean_pct", ""),
        "gap_max_pct": data.get("gap_max_pct", ""),
        "timestamp": data.get("timestamp", ""),
        "results_dir": detect_results_dir(path),
        "run_info_path": str(path),
    }

    for field in CONFIG_FIELDS:
        row[field] = config.get(field, "")
    for field in INDICATOR_FIELDS:
        row[field] = indicators.get(field, "")

    return row


def dedupe_latest(rows: list[dict]) -> list[dict]:
    """Keep the latest row for each (instance_name, config_id) pair."""
    best: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (str(row.get("instance_name", "")), str(row.get("config_id", "")))
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        cur_ts = str(current.get("timestamp", ""))
        new_ts = str(row.get("timestamp", ""))
        if (new_ts, row["run_info_path"]) >= (cur_ts, current["run_info_path"]):
            best[key] = row
    return sorted(
        best.values(),
        key=lambda r: (
            str(r.get("instance_name", "")),
            int(r.get("config_id", 0) or 0),
        ),
    )


def write_csv(rows: list[dict], output_path: Path) -> None:
    """Write rows to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = BASE_FIELDS + CONFIG_FIELDS + INDICATOR_FIELDS + TRACE_FIELDS
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flatten DOE run_info.json files into a summary CSV."
    )
    parser.add_argument(
        "--roots",
        nargs="+",
        default=["results_doe_L9", "archive"],
        help="Directories to scan for run_info.json files.",
    )
    parser.add_argument(
        "--output",
        default="run_info_flat.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--dedupe",
        choices=("latest", "none"),
        default="latest",
        help="Whether to keep only the latest row per (instance_name, config_id).",
    )
    args = parser.parse_args()

    roots = [Path(p) for p in args.roots]
    run_infos = find_run_infos(roots)
    rows = [flatten_run_info(p) for p in run_infos]

    if args.dedupe == "latest":
        rows = dedupe_latest(rows)
    else:
        rows = sorted(
            rows,
            key=lambda r: (
                str(r.get("instance_name", "")),
                int(r.get("config_id", 0) or 0),
                str(r.get("timestamp", "")),
            ),
        )

    output_path = Path(args.output)
    write_csv(rows, output_path)

    print(f"[collect_run_info] scanned {len(run_infos)} run_info.json files")
    print(f"[collect_run_info] wrote {len(rows)} rows -> {output_path}")


if __name__ == "__main__":
    main()
