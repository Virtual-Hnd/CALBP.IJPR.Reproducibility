#!/usr/bin/env python3
"""
export_archive_v1_bundle.py — Upgrade archived DOE result folders to the
current dashboard/result format and package co-author-friendly analysis files.

The historical V1 archive stores solver outputs in an older schema. This
script copies those archived campaigns into `published_results/`, augments
their metadata to the current format, generates `instance.json` files, and
adds flat CSV exports that make interpretation easier for co-authors.

Usage
-----
    python scripts/export_archive_v1_bundle.py
    python scripts/export_archive_v1_bundle.py --campaigns results_doe_scholl_l9
    python scripts/export_archive_v1_bundle.py --bundle-name archive_v1_manual
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from calbp.analysis.indicators import compute_all_indicators
from calbp.data.instance_io import read_txt, write_json
from calbp.doe.taguchi import L36_FACTORS, PILOT_FACTORS


LEVEL_LABELS = ("low", "mid", "high")

LEVEL_SPECS = {
    "alpha_ci": PILOT_FACTORS["A"]["levels"],
    "beta_su": PILOT_FACTORS["B"]["levels"],
    "gamma_setup": PILOT_FACTORS["C"]["levels"],
    "sigma_si": PILOT_FACTORS["D"]["levels"],
    "R_e": L36_FACTORS["F"]["levels"],
    "C_c": L36_FACTORS["E"]["levels"],
}

MANIFEST_FIELDS = [
    "instance_name",
    "base_instance",
    "config_name",
    "config_id",
    "subscenario",
    "alpha_level",
    "beta_level",
    "gamma_level",
    "sigma_level",
    "R_e_level",
    "C_c_level",
    "R_e",
    "C_c",
    "factor_granularity",
    "seed",
]

MASTER_FIELDS = [
    "run_name",
    "base_instance",
    "source",
    "n_tasks",
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
    "T",
    "factor_granularity",
    "seed",
    "status",
    "n_pareto",
    "n_certified",
    "min_stations",
    "max_stations",
    "solver_iterations_total",
    "solver_iterations_mean",
    "solver_iterations_max",
    "total_cpu_s",
    "min_cost",
    "max_cost",
    "min_energy",
    "max_energy",
    "cost_range",
    "energy_range",
    "HV_abs",
    "HV_norm",
    "ref_cost",
    "ref_energy",
    "spacing",
    "spread_delta",
    "max_spread",
    "gap_mean_pct",
    "gap_max_pct",
    "pct_HI",
    "pct_CI",
    "pct_SEH",
    "pct_SEC",
    "pct_SU",
    "pct_SIH",
    "pct_SIC",
]

RUN_INFO_FLAT_FIELDS = [
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
    "min_stations",
    "max_stations",
    "solver_iterations_total",
    "solver_iterations_mean",
    "solver_iterations_max",
    "total_cpu_s",
    "gap_mean_pct",
    "gap_max_pct",
    "timestamp",
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
    "results_dir",
    "run_info_path",
]

POINT_FIELDS = [
    "run_name",
    "base_instance",
    "source",
    "config_name",
    "config_id",
    "point_idx",
    "cost",
    "energy",
    "stations",
    "workers",
    "cobots",
    "certified",
    "lb",
    "ub",
    "mip_gap_pct",
    "n_nodes",
    "cpu_s",
    "energy_tasks",
    "energy_idle",
    "cobot_util",
    "solver_iterations",
    "HI",
    "CI",
    "SEH",
    "SEC",
    "SU",
    "SIH",
    "SIC",
]

ASSET_FIELDS = [
    "campaign_name",
    "run_name",
    "base_instance",
    "source",
    "config_name",
    "config_id",
    "status",
    "n_tasks",
    "n_pareto",
    "instance_txt",
    "instance_json",
    "run_info_json",
    "pareto_front_csv",
    "assignments_json",
]


def parse_scalar(value: str):
    """Convert CSV text to a bool / int / float / None when possible."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if text == "True":
        return True
    if text == "False":
        return False
    try:
        num = float(text)
    except ValueError:
        return text
    return int(num) if num.is_integer() and "." not in text else num


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into a list of rows."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write rows to a UTF-8 CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def cfg_sort_key(cfg_name: str) -> tuple[int, str]:
    """Sort config names numerically when they contain digits."""
    digits = "".join(ch for ch in str(cfg_name) if ch.isdigit())
    return (int(digits) if digits else 10**9, str(cfg_name))


def copy_campaign(src: Path, dst: Path) -> None:
    """Copy one archived results folder into the export bundle."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def build_varied_factor_map(manifest_rows: list[dict[str, str]]) -> dict[str, bool]:
    """Detect whether each factor was actually varied in the historical campaign."""
    factors = ("alpha_ci", "beta_su", "gamma_setup", "sigma_si", "R_e", "C_c")
    varied: dict[str, bool] = {}
    for factor in factors:
        values = {
            str(row.get(factor, "")).strip()
            for row in manifest_rows
            if str(row.get(factor, "")).strip() != ""
        }
        varied[factor] = len(values) > 1
    return varied


def infer_level(factor: str, value, varied: bool) -> str:
    """Infer low/mid/high/fixed from a numeric factor value."""
    if value is None or value == "":
        return ""
    if not varied:
        return "fixed"

    specs = LEVEL_SPECS[factor]
    if factor == "R_e":
        for idx, target in enumerate(specs):
            if abs(float(value) - float(target)) <= 1e-6:
                return LEVEL_LABELS[idx]
        return "unknown"

    for idx, interval in enumerate(specs):
        lo, hi = float(interval[0]), float(interval[1])
        if lo - 1e-6 <= float(value) <= hi + 1e-6:
            return LEVEL_LABELS[idx]
    return "unknown"


def load_points(path: Path) -> list[dict]:
    """Load a Pareto front CSV with typed values."""
    rows = read_csv_rows(path)
    return [{key: parse_scalar(value) for key, value in row.items()} for row in rows]


def summarize_front(points: list[dict]) -> dict[str, float | int | None]:
    """Compute run-level summaries from per-point Pareto data."""
    stations = [
        int(point["stations"])
        for point in points
        if isinstance(point.get("stations"), (int, float))
    ]
    iterations = [
        int(point["solver_iterations"])
        for point in points
        if isinstance(point.get("solver_iterations"), (int, float))
    ]
    return {
        "min_stations": min(stations) if stations else None,
        "max_stations": max(stations) if stations else None,
        "solver_iterations_total": sum(iterations) if iterations else None,
        "solver_iterations_mean": (
            round(sum(iterations) / len(iterations), 2) if iterations else None
        ),
        "solver_iterations_max": max(iterations) if iterations else None,
    }


def compute_mode_shares(points: list[dict]) -> dict[str, float]:
    """Aggregate mode shares across the full Pareto front."""
    totals = defaultdict(float)
    grand_total = 0.0
    for point in points:
        for mode in ("HI", "CI", "SEH", "SEC", "SU", "SIH", "SIC"):
            count = float(point.get(mode) or 0)
            totals[mode] += count
            grand_total += count
    if grand_total <= 0:
        return {f"pct_{mode}": 0.0 for mode in ("HI", "CI", "SEH", "SEC", "SU", "SIH", "SIC")}
    return {
        f"pct_{mode}": round(totals[mode] / grand_total * 100, 2)
        for mode in ("HI", "CI", "SEH", "SEC", "SU", "SIH", "SIC")
    }


def build_point_rows(
    run_name: str,
    base_instance: str,
    source: str,
    config: dict,
    points: list[dict],
) -> list[dict]:
    """Flatten one run's Pareto front into shareable rows."""
    rows: list[dict] = []
    for point in points:
        row = {
            "run_name": run_name,
            "base_instance": base_instance,
            "source": source,
            "config_name": config.get("config_name"),
            "config_id": config.get("config_id"),
        }
        for field in POINT_FIELDS:
            if field in row:
                continue
            row[field] = point.get(field)
        rows.append(row)
    return rows


def write_instance_json(
    solution_dir: Path,
    run_name: str,
    base_instance: str,
    config: dict,
) -> None:
    """Generate an `instance.json` companion file for a historical `instance.txt`."""
    txt_path = solution_dir / "instance.txt"
    if not txt_path.exists():
        return

    inst = read_txt(txt_path)
    inst.name = run_name
    inst.base_instance = base_instance
    inst.config_name = str(config.get("config_name") or "")
    inst.alpha_ci = float(config.get("alpha_ci") or 0.0)
    inst.beta_su = float(config.get("beta_su") or 0.0)
    inst.gamma_setup = float(config.get("gamma_setup") or 0.0)
    inst.sigma_si = float(config.get("sigma_si") or 0.0)
    inst.alpha_ci_std = float(config.get("alpha_ci_std") or 0.0)
    inst.beta_su_std = float(config.get("beta_su_std") or 0.0)
    inst.gamma_setup_std = float(config.get("gamma_setup_std") or 0.0)
    inst.sigma_si_std = float(config.get("sigma_si_std") or 0.0)
    inst.alpha_level = str(config.get("alpha_level") or "")
    inst.beta_level = str(config.get("beta_level") or "")
    inst.gamma_level = str(config.get("gamma_level") or "")
    inst.sigma_level = str(config.get("sigma_level") or "")
    inst.R_e_level = str(config.get("R_e_level") or "")
    inst.C_c_level = str(config.get("C_c_level") or "")
    inst.factor_granularity = str(config.get("factor_granularity") or "instance")
    inst.seed = int(config.get("seed") or 0)
    inst.task_parameters = {
        "alpha_ci": [inst.alpha_ci] * len(inst.tasks),
        "beta_su": [inst.beta_su] * len(inst.tasks),
        "gamma_setup": [inst.gamma_setup] * len(inst.tasks),
        "sigma_si": [inst.sigma_si] * len(inst.tasks),
    }
    write_json(inst, solution_dir / "instance.json")


def build_manifest_rows(
    original_rows: list[dict[str, str]],
    varied: dict[str, bool],
) -> list[dict]:
    """Convert the old manifest schema to the current manifest schema."""
    rows: list[dict] = []
    for original in original_rows:
        alpha = parse_scalar(original.get("alpha_ci"))
        beta = parse_scalar(original.get("beta_su"))
        gamma = parse_scalar(original.get("gamma_setup"))
        sigma = parse_scalar(original.get("sigma_si"))
        r_e = parse_scalar(original.get("R_e"))
        c_c = parse_scalar(original.get("C_c"))
        rows.append(
            {
                "instance_name": original.get("instance_name", ""),
                "base_instance": original.get("base_instance", ""),
                "config_name": original.get("config_name", ""),
                "config_id": original.get("config_id", ""),
                "subscenario": original.get("subscenario", ""),
                "alpha_level": infer_level("alpha_ci", alpha, varied["alpha_ci"]),
                "beta_level": infer_level("beta_su", beta, varied["beta_su"]),
                "gamma_level": infer_level("gamma_setup", gamma, varied["gamma_setup"]),
                "sigma_level": infer_level("sigma_si", sigma, varied["sigma_si"]),
                "R_e_level": infer_level("R_e", r_e, varied["R_e"]),
                "C_c_level": infer_level("C_c", c_c, varied["C_c"]),
                "R_e": r_e,
                "C_c": c_c,
                "factor_granularity": "instance",
                "seed": parse_scalar(original.get("seed")),
            }
        )
    return rows


def augment_run_info(
    info: dict,
    manifest_row: dict[str, str] | None,
    points: list[dict],
    varied: dict[str, bool],
) -> dict:
    """Upgrade one historical run_info payload to the current schema."""
    config = dict(info.get("config", {}))
    if manifest_row:
        config.setdefault("config_name", manifest_row.get("config_name"))
        config.setdefault("config_id", parse_scalar(manifest_row.get("config_id")))
        config.setdefault("seed", parse_scalar(manifest_row.get("seed")))
        for key in ("alpha_ci", "beta_su", "gamma_setup", "sigma_si", "R_e", "C_c"):
            if key in manifest_row and str(manifest_row.get(key, "")).strip() != "":
                config[key] = parse_scalar(manifest_row.get(key))

    for std_field in (
        "alpha_ci_std",
        "beta_su_std",
        "gamma_setup_std",
        "sigma_si_std",
    ):
        config[std_field] = 0.0

    for factor in ("alpha_ci", "beta_su", "gamma_setup", "sigma_si", "R_e", "C_c"):
        config[factor] = parse_scalar(config.get(factor))

    config["alpha_level"] = infer_level(
        "alpha_ci", config.get("alpha_ci"), varied["alpha_ci"]
    )
    config["beta_level"] = infer_level(
        "beta_su", config.get("beta_su"), varied["beta_su"]
    )
    config["gamma_level"] = infer_level(
        "gamma_setup", config.get("gamma_setup"), varied["gamma_setup"]
    )
    config["sigma_level"] = infer_level(
        "sigma_si", config.get("sigma_si"), varied["sigma_si"]
    )
    config["R_e_level"] = infer_level("R_e", config.get("R_e"), varied["R_e"])
    config["C_c_level"] = infer_level("C_c", config.get("C_c"), varied["C_c"])
    config["factor_granularity"] = "instance"

    front_stats = summarize_front(points)
    certified = sum(1 for point in points if point.get("certified") is True)
    gaps = [
        float(point["mip_gap_pct"])
        for point in points
        if isinstance(point.get("mip_gap_pct"), (int, float))
    ]

    upgraded = dict(info)
    upgraded["config"] = config
    upgraded["n_pareto"] = int(upgraded.get("n_pareto") or len(points))
    upgraded["n_certified"] = int(upgraded.get("n_certified") or certified)
    upgraded["min_stations"] = front_stats["min_stations"]
    upgraded["max_stations"] = front_stats["max_stations"]
    upgraded["solver_iterations_total"] = front_stats["solver_iterations_total"]
    upgraded["solver_iterations_mean"] = front_stats["solver_iterations_mean"]
    upgraded["solver_iterations_max"] = front_stats["solver_iterations_max"]
    if gaps:
        upgraded["gap_mean_pct"] = round(sum(gaps) / len(gaps), 4)
        upgraded["gap_max_pct"] = round(max(gaps), 4)

    if points:
        costs = [float(point["cost"]) for point in points]
        energies = [float(point["energy"]) for point in points]
        upgraded["indicators"] = compute_all_indicators(costs, energies, delta=0.10)

    return upgraded


def build_master_row(info: dict, points: list[dict]) -> dict:
    """Create one current-format `doe_results.csv` row from upgraded metadata."""
    config = info.get("config", {})
    indicators = info.get("indicators", {})
    front_stats = summarize_front(points)
    row = {
        "run_name": info.get("run_name"),
        "base_instance": info.get("base_instance"),
        "source": info.get("source"),
        "n_tasks": info.get("n_tasks"),
        "config_name": config.get("config_name"),
        "config_id": config.get("config_id"),
        "alpha_level": config.get("alpha_level"),
        "beta_level": config.get("beta_level"),
        "gamma_level": config.get("gamma_level"),
        "sigma_level": config.get("sigma_level"),
        "R_e_level": config.get("R_e_level"),
        "C_c_level": config.get("C_c_level"),
        "alpha_ci": config.get("alpha_ci"),
        "beta_su": config.get("beta_su"),
        "gamma_setup": config.get("gamma_setup"),
        "sigma_si": config.get("sigma_si"),
        "alpha_ci_std": config.get("alpha_ci_std"),
        "beta_su_std": config.get("beta_su_std"),
        "gamma_setup_std": config.get("gamma_setup_std"),
        "sigma_si_std": config.get("sigma_si_std"),
        "R_e": config.get("R_e"),
        "C_c": config.get("C_c"),
        "T": info.get("T"),
        "factor_granularity": config.get("factor_granularity"),
        "seed": config.get("seed"),
        "status": info.get("status"),
        "n_pareto": info.get("n_pareto"),
        "n_certified": info.get("n_certified"),
        "min_stations": front_stats["min_stations"],
        "max_stations": front_stats["max_stations"],
        "solver_iterations_total": front_stats["solver_iterations_total"],
        "solver_iterations_mean": front_stats["solver_iterations_mean"],
        "solver_iterations_max": front_stats["solver_iterations_max"],
        "total_cpu_s": info.get("total_cpu_s"),
        "gap_mean_pct": info.get("gap_mean_pct"),
        "gap_max_pct": info.get("gap_max_pct"),
    }

    if points:
        costs = [float(point["cost"]) for point in points]
        energies = [float(point["energy"]) for point in points]
        row["min_cost"] = round(min(costs), 2)
        row["max_cost"] = round(max(costs), 2)
        row["min_energy"] = round(min(energies), 2)
        row["max_energy"] = round(max(energies), 2)
        row["cost_range"] = indicators.get("cost_range")
        row["energy_range"] = indicators.get("energy_range")
        row["HV_abs"] = indicators.get("HV_abs")
        row["HV_norm"] = indicators.get("HV_norm")
        row["ref_cost"] = indicators.get("ref_cost")
        row["ref_energy"] = indicators.get("ref_energy")
        row["spacing"] = indicators.get("spacing")
        row["spread_delta"] = indicators.get("spread_delta")
        row["max_spread"] = indicators.get("max_spread")
    else:
        for field in (
            "min_cost",
            "max_cost",
            "min_energy",
            "max_energy",
            "cost_range",
            "energy_range",
            "HV_abs",
            "HV_norm",
            "ref_cost",
            "ref_energy",
            "spacing",
            "spread_delta",
            "max_spread",
        ):
            row[field] = ""

    row.update(compute_mode_shares(points))
    return row


def build_run_info_flat_row(campaign_root: Path, info: dict) -> dict:
    """Flatten upgraded run_info.json into a one-row analysis CSV record."""
    config = info.get("config", {})
    indicators = info.get("indicators", {})
    n_pareto = int(info.get("n_pareto") or 0)
    n_certified = int(info.get("n_certified") or 0)
    cert_rate = round(n_certified / n_pareto, 6) if n_pareto else 0.0
    run_info_path = campaign_root / "solutions" / str(info.get("run_name")) / "run_info.json"
    return {
        "instance_name": info.get("base_instance", ""),
        "config_id": config.get("config_id", ""),
        "config_name": config.get("config_name", ""),
        "run_name": info.get("run_name", ""),
        "source": info.get("source", ""),
        "n_tasks": info.get("n_tasks", ""),
        "T": info.get("T", ""),
        "status": info.get("status", ""),
        "n_pareto": n_pareto,
        "n_certified": n_certified,
        "cert_rate": cert_rate,
        "min_stations": info.get("min_stations", ""),
        "max_stations": info.get("max_stations", ""),
        "solver_iterations_total": info.get("solver_iterations_total", ""),
        "solver_iterations_mean": info.get("solver_iterations_mean", ""),
        "solver_iterations_max": info.get("solver_iterations_max", ""),
        "total_cpu_s": info.get("total_cpu_s", ""),
        "gap_mean_pct": info.get("gap_mean_pct", ""),
        "gap_max_pct": info.get("gap_max_pct", ""),
        "timestamp": info.get("timestamp", ""),
        "alpha_level": config.get("alpha_level", ""),
        "beta_level": config.get("beta_level", ""),
        "gamma_level": config.get("gamma_level", ""),
        "sigma_level": config.get("sigma_level", ""),
        "R_e_level": config.get("R_e_level", ""),
        "C_c_level": config.get("C_c_level", ""),
        "alpha_ci": config.get("alpha_ci", ""),
        "beta_su": config.get("beta_su", ""),
        "gamma_setup": config.get("gamma_setup", ""),
        "sigma_si": config.get("sigma_si", ""),
        "alpha_ci_std": config.get("alpha_ci_std", ""),
        "beta_su_std": config.get("beta_su_std", ""),
        "gamma_setup_std": config.get("gamma_setup_std", ""),
        "sigma_si_std": config.get("sigma_si_std", ""),
        "R_e": config.get("R_e", ""),
        "C_c": config.get("C_c", ""),
        "factor_granularity": config.get("factor_granularity", ""),
        "seed": config.get("seed", ""),
        "HV_abs": indicators.get("HV_abs", ""),
        "HV_norm": indicators.get("HV_norm", ""),
        "ref_cost": indicators.get("ref_cost", ""),
        "ref_energy": indicators.get("ref_energy", ""),
        "ideal_cost": indicators.get("ideal_cost", ""),
        "ideal_energy": indicators.get("ideal_energy", ""),
        "nadir_cost": indicators.get("nadir_cost", ""),
        "nadir_energy": indicators.get("nadir_energy", ""),
        "spacing": indicators.get("spacing", ""),
        "spread_delta": indicators.get("spread_delta", ""),
        "max_spread": indicators.get("max_spread", ""),
        "cost_range": indicators.get("cost_range", ""),
        "energy_range": indicators.get("energy_range", ""),
        "PF_size": indicators.get("PF_size", ""),
        "results_dir": str(campaign_root),
        "run_info_path": str(run_info_path),
    }


def build_asset_row(campaign_name: str, info: dict) -> dict:
    """Create a compact file inventory row for one run."""
    run_name = str(info.get("run_name"))
    rel_root = Path("solutions") / run_name
    config = info.get("config", {})
    return {
        "campaign_name": campaign_name,
        "run_name": run_name,
        "base_instance": info.get("base_instance"),
        "source": info.get("source"),
        "config_name": config.get("config_name"),
        "config_id": config.get("config_id"),
        "status": info.get("status"),
        "n_tasks": info.get("n_tasks"),
        "n_pareto": info.get("n_pareto"),
        "instance_txt": str(rel_root / "instance.txt"),
        "instance_json": str(rel_root / "instance.json"),
        "run_info_json": str(rel_root / "run_info.json"),
        "pareto_front_csv": str(rel_root / "pareto_front.csv"),
        "assignments_json": str(rel_root / "assignments.json"),
    }


def build_dashboard_snapshot(
    campaign_root: Path,
    master_rows: list[dict],
    pareto_fronts: dict[str, list[dict]],
) -> dict:
    """Build the JSON payload that feeds the dashboard."""
    runs = {row["run_name"]: dict(row) for row in master_rows}
    instances = sorted({str(row["base_instance"]) for row in master_rows})
    configs = sorted({str(row["config_name"]) for row in master_rows}, key=cfg_sort_key)
    ok_rows = [row for row in master_rows if row.get("status") == "OK"]
    cpu_values = [
        float(row["total_cpu_s"])
        for row in ok_rows
        if isinstance(row.get("total_cpu_s"), (int, float))
    ]
    pf_sizes = [
        int(row["n_pareto"])
        for row in ok_rows
        if isinstance(row.get("n_pareto"), (int, float))
    ]
    min_stations = [
        int(row["min_stations"])
        for row in ok_rows
        if isinstance(row.get("min_stations"), (int, float))
    ]
    max_stations = [
        int(row["max_stations"])
        for row in ok_rows
        if isinstance(row.get("max_stations"), (int, float))
    ]
    completed = len(master_rows)
    total_expected = len(instances) * len(configs)
    avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0.0
    return {
        "timestamp": datetime.now().isoformat(),
        "results_dir": str(campaign_root),
        "configs": configs,
        "instances": instances,
        "total_expected": total_expected,
        "runs": runs,
        "pareto_fronts": pareto_fronts,
        "summary": {
            "completed": completed,
            "successful": len(ok_rows),
            "failed": len([row for row in master_rows if row.get("status") not in ("OK", None)]),
            "pending": max(0, total_expected - completed),
            "total_cpu_s": round(sum(cpu_values), 1),
            "avg_cpu_s": round(avg_cpu, 1),
            "avg_pf_size": round(sum(pf_sizes) / len(pf_sizes), 2) if pf_sizes else 0.0,
            "global_min_stations": min(min_stations) if min_stations else None,
            "global_max_stations": max(max_stations) if max_stations else None,
            "eta_s": 0,
        },
    }


def build_campaign_summary(
    campaign_name: str,
    campaign_root: Path,
    master_rows: list[dict],
    points_rows: list[dict],
) -> dict:
    """Create a compact JSON summary for one exported campaign."""
    sources = Counter(str(row.get("source") or "unknown") for row in master_rows)
    statuses = Counter(str(row.get("status") or "unknown") for row in master_rows)
    config_names = sorted({str(row["config_name"]) for row in master_rows}, key=cfg_sort_key)
    base_instances = sorted({str(row["base_instance"]) for row in master_rows})
    n_tasks = [
        int(row["n_tasks"])
        for row in master_rows
        if isinstance(row.get("n_tasks"), (int, float))
    ]
    cpu_values = [
        float(row["total_cpu_s"])
        for row in master_rows
        if isinstance(row.get("total_cpu_s"), (int, float))
    ]
    return {
        "campaign_name": campaign_name,
        "campaign_root": str(campaign_root),
        "exported_at": datetime.now().isoformat(),
        "n_runs": len(master_rows),
        "n_points": len(points_rows),
        "n_configs": len(config_names),
        "n_instances": len(base_instances),
        "config_names": config_names,
        "base_instances": base_instances,
        "sources": dict(sources),
        "statuses": dict(statuses),
        "n_tasks_min": min(n_tasks) if n_tasks else None,
        "n_tasks_max": max(n_tasks) if n_tasks else None,
        "total_cpu_s": round(sum(cpu_values), 2),
        "raw_solver_console_logs_archived": False,
        "available_execution_traces": [
            "run_info.json",
            "pareto_front.csv",
            "assignments.json",
            "instance.txt",
            "instance.json",
        ],
    }


def write_campaign_readme(campaign_root: Path, summary: dict) -> None:
    """Write a short guide for co-authors inside one exported campaign."""
    text = f"""# {summary['campaign_name']}

This snapshot was exported from `archive/V1_experimentation` and upgraded to the
current dashboard/result schema without modifying the archived source folder.

## What is inside

- `doe_manifest.csv`: current manifest format used by the dashboard
- `doe_manifest_legacy.csv`: original archive manifest kept for traceability
- `doe_results.csv`: regenerated current-format run summary
- `doe_results_legacy.csv`: original archive summary when it existed
- `run_info_flat.csv`: one row per run, flattened from `run_info.json`
- `pareto_points_flat.csv`: one row per Pareto point across the campaign
- `solution_assets.csv`: direct pointers to the per-run files
- `dashboard_data.json`: precomputed dashboard payload for this snapshot
- `campaign_summary.json`: compact campaign-level summary
- `solutions/<run>/...`: detailed artifacts used for interpretation

## Per-run detailed files

- `instance.txt`: solver input instance
- `instance.json`: JSON companion with generation metadata
- `run_info.json`: run-level metadata and quality indicators
- `pareto_front.csv`: detailed Pareto points and mode counts
- `assignments.json`: assignment-level details for each Pareto point

## About execution logs

The historical archive does not contain raw MILP console logs (`.log`, `.out`,
`.err`). The closest execution traces that remain available are
`run_info.json`, `pareto_front.csv`, and `assignments.json`.

## Launch the dashboard on this snapshot

```bash
DOE_RESULTS_DIR="{campaign_root}" ./.venv/bin/python scripts/dashboard.py --host 0.0.0.0 --port 8050 --no-open
```

## Quick figures

- Runs: `{summary['n_runs']}`
- Pareto points: `{summary['n_points']}`
- Configs: `{summary['n_configs']}`
- Instances: `{summary['n_instances']}`
"""
    (campaign_root / "README.md").write_text(text, encoding="utf-8")


def export_campaign(src: Path, dst: Path) -> dict:
    """Export one archived campaign into a dashboard-ready snapshot."""
    copy_campaign(src, dst)

    manifest_path = dst / "doe_manifest.csv"
    legacy_manifest_path = dst / "doe_manifest_legacy.csv"
    if manifest_path.exists():
        shutil.move(str(manifest_path), str(legacy_manifest_path))
        original_manifest_rows = read_csv_rows(legacy_manifest_path)
    else:
        original_manifest_rows = []

    varied = build_varied_factor_map(original_manifest_rows)
    manifest_rows = build_manifest_rows(original_manifest_rows, varied)
    manifest_by_run = {row["instance_name"]: row for row in original_manifest_rows}
    write_csv_rows(manifest_path, MANIFEST_FIELDS, manifest_rows)

    results_path = dst / "doe_results.csv"
    legacy_results_path = dst / "doe_results_legacy.csv"
    if results_path.exists():
        shutil.move(str(results_path), str(legacy_results_path))

    solutions_dir = dst / "solutions"
    master_rows: list[dict] = []
    flat_rows: list[dict] = []
    point_rows: list[dict] = []
    asset_rows: list[dict] = []
    pareto_fronts: dict[str, list[dict]] = {}

    for run_info_path in sorted(solutions_dir.glob("*/run_info.json")):
        solution_dir = run_info_path.parent
        run_name = solution_dir.name
        info = json.loads(run_info_path.read_text(encoding="utf-8"))
        manifest_row = manifest_by_run.get(run_name)

        points: list[dict] = []
        pf_path = solution_dir / "pareto_front.csv"
        if pf_path.exists():
            points = load_points(pf_path)
            pareto_fronts[run_name] = points

        upgraded_info = augment_run_info(info, manifest_row, points, varied)
        run_info_path.write_text(
            json.dumps(upgraded_info, indent=2, default=str),
            encoding="utf-8",
        )

        write_instance_json(
            solution_dir,
            run_name,
            str(upgraded_info.get("base_instance") or ""),
            upgraded_info.get("config", {}),
        )

        master_row = build_master_row(upgraded_info, points)
        master_rows.append(master_row)
        flat_rows.append(build_run_info_flat_row(dst, upgraded_info))
        point_rows.extend(
            build_point_rows(
                run_name,
                str(upgraded_info.get("base_instance") or ""),
                str(upgraded_info.get("source") or ""),
                upgraded_info.get("config", {}),
                points,
            )
        )
        asset_rows.append(build_asset_row(dst.name, upgraded_info))

    master_rows.sort(
        key=lambda row: (str(row.get("base_instance")), cfg_sort_key(str(row.get("config_name"))))
    )
    flat_rows.sort(
        key=lambda row: (str(row.get("instance_name")), cfg_sort_key(str(row.get("config_name"))))
    )
    point_rows.sort(
        key=lambda row: (
            str(row.get("base_instance")),
            cfg_sort_key(str(row.get("config_name"))),
            int(row.get("point_idx") or 0),
        )
    )
    asset_rows.sort(
        key=lambda row: (str(row.get("base_instance")), cfg_sort_key(str(row.get("config_name"))))
    )

    write_csv_rows(results_path, MASTER_FIELDS, master_rows)
    write_csv_rows(dst / "run_info_flat.csv", RUN_INFO_FLAT_FIELDS, flat_rows)
    write_csv_rows(dst / "pareto_points_flat.csv", POINT_FIELDS, point_rows)
    write_csv_rows(dst / "solution_assets.csv", ASSET_FIELDS, asset_rows)

    dashboard_data = build_dashboard_snapshot(dst, master_rows, pareto_fronts)
    (dst / "dashboard_data.json").write_text(
        json.dumps(dashboard_data, indent=2, default=str),
        encoding="utf-8",
    )

    summary = build_campaign_summary(dst.name, dst, master_rows, point_rows)
    (dst / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    write_campaign_readme(dst, summary)

    return {
        "campaign_name": dst.name,
        "source_dir": str(src),
        "export_dir": str(dst),
        "runs": len(master_rows),
        "points": len(point_rows),
        "configs": summary["n_configs"],
        "instances": summary["n_instances"],
    }


def export_combined_campaign(
    bundle_root: Path,
    combined_name: str,
    source_campaign_names: list[str],
) -> dict:
    """Combine several exported campaigns into one dashboard-ready snapshot."""
    dst = bundle_root / combined_name
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)

    solutions_dir = dst / "solutions"
    solutions_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict] = []
    master_rows: list[dict] = []
    flat_rows: list[dict] = []
    point_rows: list[dict] = []
    asset_rows: list[dict] = []
    pareto_fronts: dict[str, list[dict]] = {}

    for source_name in source_campaign_names:
        src = bundle_root / source_name
        if not src.exists():
            continue

        manifest_rows.extend(read_csv_rows(src / "doe_manifest.csv"))
        master_rows.extend(read_csv_rows(src / "doe_results.csv"))
        flat_rows.extend(read_csv_rows(src / "run_info_flat.csv"))
        point_rows.extend(read_csv_rows(src / "pareto_points_flat.csv"))

        for row in read_csv_rows(src / "solution_assets.csv"):
            copied = dict(row)
            copied["campaign_name"] = combined_name
            asset_rows.append(copied)

        src_solutions = src / "solutions"
        for run_dir in sorted(src_solutions.iterdir()):
            if not run_dir.is_dir():
                continue
            shutil.copytree(run_dir, solutions_dir / run_dir.name)

        dashboard_data = json.loads((src / "dashboard_data.json").read_text(encoding="utf-8"))
        pareto_fronts.update(dashboard_data.get("pareto_fronts", {}))

    manifest_rows.sort(
        key=lambda row: (str(row.get("base_instance")), cfg_sort_key(str(row.get("config_name"))))
    )
    master_rows.sort(
        key=lambda row: (str(row.get("base_instance")), cfg_sort_key(str(row.get("config_name"))))
    )
    flat_rows.sort(
        key=lambda row: (str(row.get("instance_name")), cfg_sort_key(str(row.get("config_name"))))
    )
    point_rows.sort(
        key=lambda row: (
            str(row.get("base_instance")),
            cfg_sort_key(str(row.get("config_name"))),
            int(parse_scalar(row.get("point_idx")) or 0),
        )
    )
    asset_rows.sort(
        key=lambda row: (str(row.get("base_instance")), cfg_sort_key(str(row.get("config_name"))))
    )

    write_csv_rows(dst / "doe_manifest.csv", MANIFEST_FIELDS, manifest_rows)
    write_csv_rows(dst / "doe_results.csv", MASTER_FIELDS, master_rows)
    write_csv_rows(dst / "run_info_flat.csv", RUN_INFO_FLAT_FIELDS, flat_rows)
    write_csv_rows(dst / "pareto_points_flat.csv", POINT_FIELDS, point_rows)
    write_csv_rows(dst / "solution_assets.csv", ASSET_FIELDS, asset_rows)

    typed_master_rows: list[dict] = []
    for row in master_rows:
        typed_row = {}
        for key, value in row.items():
            typed_row[key] = parse_scalar(value) if isinstance(value, str) else value
        typed_master_rows.append(typed_row)

    dashboard_data = build_dashboard_snapshot(dst, typed_master_rows, pareto_fronts)
    (dst / "dashboard_data.json").write_text(
        json.dumps(dashboard_data, indent=2, default=str),
        encoding="utf-8",
    )

    summary = build_campaign_summary(combined_name, dst, typed_master_rows, point_rows)
    (dst / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    text = f"""# {combined_name}

This combined snapshot merges the two archive L9 benchmark families:

- `results_doe_scholl_l9`
- `results_doe_otto_l9`

It corresponds to the full historical `252`-run L9 archive (`14 Scholl + 14 Otto`)
with `9` configurations each.

## Files

- `doe_manifest.csv`: combined manifest
- `doe_results.csv`: combined run summary
- `run_info_flat.csv`: one row per run
- `pareto_points_flat.csv`: one row per Pareto point
- `solution_assets.csv`: file inventory per run
- `dashboard_data.json`: precomputed dashboard payload
- `solutions/<run>/...`: detailed per-run artifacts
"""
    (dst / "README.md").write_text(text, encoding="utf-8")

    return {
        "campaign_name": combined_name,
        "source_dir": " + ".join(source_campaign_names),
        "export_dir": str(dst),
        "runs": len(master_rows),
        "points": len(point_rows),
        "configs": summary["n_configs"],
        "instances": summary["n_instances"],
    }


def write_bundle_index(bundle_root: Path, campaign_summaries: list[dict]) -> None:
    """Write the top-level guide for the whole archive export bundle."""
    lines = [
        "# Archive V1 Export Bundle",
        "",
        "This bundle contains upgraded snapshots exported from `archive/V1_experimentation`.",
        "Each subdirectory is a standalone results folder compatible with the current dashboard.",
        "",
        "## Campaigns",
        "",
    ]
    for summary in sorted(campaign_summaries, key=lambda item: item["campaign_name"]):
        lines.extend(
            [
                f"- `{summary['campaign_name']}`",
                f"  - source: `{summary['source_dir']}`",
                f"  - runs: `{summary['runs']}` | Pareto points: `{summary['points']}` | configs: `{summary['configs']}` | instances: `{summary['instances']}`",
                f"  - dashboard root: `{summary['export_dir']}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The archive did not contain raw solver console logs.",
            "- The execution traces available for interpretation are `run_info.json`, `pareto_front.csv`, `assignments.json`, `instance.txt`, and the generated `instance.json`.",
            "- `run_info_flat.csv` and `pareto_points_flat.csv` were generated to help co-authors work directly in spreadsheets.",
        ]
    )
    (bundle_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade archived DOE campaigns to the current result format."
    )
    parser.add_argument(
        "--archive-root",
        default=str(PROJECT_ROOT / "archive" / "V1_experimentation"),
        help="Folder containing historical `results_*` campaigns.",
    )
    parser.add_argument(
        "--output-root",
        default=str(PROJECT_ROOT / "published_results"),
        help="Destination parent folder for the exported bundle.",
    )
    parser.add_argument(
        "--bundle-name",
        default="",
        help="Optional export bundle name. Defaults to a timestamped label.",
    )
    parser.add_argument(
        "--campaigns",
        nargs="*",
        default=[],
        help="Optional subset of campaign directory names to export.",
    )
    args = parser.parse_args()

    archive_root = Path(args.archive_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    bundle_name = args.bundle_name.strip() or (
        "archive_v1_newformat_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )
    bundle_root = output_root / bundle_name
    bundle_root.mkdir(parents=True, exist_ok=False)

    candidates = sorted(
        p for p in archive_root.iterdir() if p.is_dir() and p.name.startswith("results_")
    )
    if args.campaigns:
        wanted = set(args.campaigns)
        candidates = [p for p in candidates if p.name in wanted]

    if not candidates:
        raise SystemExit("No archived campaigns matched the request.")

    campaign_summaries: list[dict] = []
    for campaign in candidates:
        export_dir = bundle_root / campaign.name
        summary = export_campaign(campaign, export_dir)
        campaign_summaries.append(summary)
        print(
            "[archive-export]"
            f" {campaign.name}: runs={summary['runs']} points={summary['points']}"
            f" -> {export_dir}"
        )

    exported_names = {summary["campaign_name"] for summary in campaign_summaries}
    l9_components = ["results_doe_scholl_l9", "results_doe_otto_l9"]
    if all(name in exported_names for name in l9_components):
        combined_name = "results_doe_archive_l9_252"
        summary = export_combined_campaign(bundle_root, combined_name, l9_components)
        campaign_summaries.append(summary)
        print(
            "[archive-export]"
            f" {combined_name}: runs={summary['runs']} points={summary['points']}"
            f" -> {summary['export_dir']}"
        )

    all_rows: list[dict] = []
    for campaign in sorted(bundle_root.glob("results_*")):
        flat_path = campaign / "run_info_flat.csv"
        if not flat_path.exists():
            continue
        for row in read_csv_rows(flat_path):
            tagged = {"campaign_name": campaign.name}
            tagged.update(row)
            all_rows.append(tagged)

    combined_fields = ["campaign_name"] + RUN_INFO_FLAT_FIELDS
    write_csv_rows(bundle_root / "all_run_info_flat.csv", combined_fields, all_rows)
    write_bundle_index(bundle_root, campaign_summaries)

    print(f"[archive-export] bundle ready: {bundle_root}")


if __name__ == "__main__":
    main()
