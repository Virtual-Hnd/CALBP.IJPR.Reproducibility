#!/usr/bin/env python3
"""Aggregate every DOE Pareto point into one collaborator-ready CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "published_results" / "l9_task_progress_220of252_2026-05-13_19-21-43"
SOLUTIONS_DIR = RESULTS_DIR / "solutions"
OUTPUT_CSV = PROJECT_ROOT / "exports" / "calbp_all_pareto_points_252_runs.csv"


RUN_FIELDS = [
    "run_name",
    "base_instance",
    "source",
    "n_tasks",
    "T",
    "status",
    "n_pareto",
    "n_certified",
    "total_cpu_s",
    "gap_mean_pct",
    "gap_max_pct",
    "timestamp",
]

CONFIG_FIELDS = [
    "config_name",
    "config_id",
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
]


def cfg_sort_key(run_dir: Path) -> tuple[str, int]:
    name = run_dir.name
    if "_c" not in name:
        return name, 0
    base, cfg = name.rsplit("_c", 1)
    try:
        return base, int(cfg)
    except ValueError:
        return base, 0


def main() -> None:
    rows: list[dict[str, object]] = []
    pareto_fields: list[str] = []

    for run_dir in sorted((p for p in SOLUTIONS_DIR.iterdir() if p.is_dir()), key=cfg_sort_key):
        info_path = run_dir / "run_info.json"
        pareto_path = run_dir / "pareto_front.csv"
        if not info_path.exists() or not pareto_path.exists():
            continue

        info = json.loads(info_path.read_text(encoding="utf-8"))
        config = info.get("config", {}) or {}
        indicators = info.get("indicators", {}) or {}

        run_values = {field: info.get(field, "") for field in RUN_FIELDS}
        config_values = {field: config.get(field, "") for field in CONFIG_FIELDS}
        indicator_values = {field: indicators.get(field, "") for field in INDICATOR_FIELDS}

        with pareto_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for field in reader.fieldnames or []:
                if field not in pareto_fields:
                    pareto_fields.append(field)
            for point in reader:
                rows.append(
                    {
                        "global_point_id": len(rows) + 1,
                        **run_values,
                        **config_values,
                        **indicator_values,
                        **point,
                    }
                )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["global_point_id", *RUN_FIELDS, *CONFIG_FIELDS, *INDICATOR_FIELDS, *pareto_fields]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    completed_runs = sum(1 for _ in SOLUTIONS_DIR.glob("*/run_info.json"))
    pareto_files = sum(1 for _ in SOLUTIONS_DIR.glob("*/pareto_front.csv"))
    print(f"runs_with_run_info={completed_runs}")
    print(f"runs_with_pareto_csv={pareto_files}")
    print(f"pareto_points={len(rows)}")
    print(f"output={OUTPUT_CSV}")


if __name__ == "__main__":
    main()
