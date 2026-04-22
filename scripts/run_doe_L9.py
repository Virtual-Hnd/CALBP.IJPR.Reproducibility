#!/usr/bin/env python3
"""
run_doe_L9.py — Execute the L9 Taguchi DOE (MILP only) for the IJPR paper.

Design:  9 configs (L9 OA, 4 factors A-D) × 28 instances = 252 MILP runs
         14 representative Scholl + 14 representative Otto n=20
         Audrey competitive MILP, 300 s per ε-iteration (configurable)

Output:
    results_doe_L9/
    ├── doe_manifest.csv           Config × instance matrix
    ├── doe_results.csv            Master CSV (1 row/run, paper-ready)
    ├── solutions/
    │   └── {instance}_{config}/
    │       ├── instance.txt       Generated CAL instance (solver input)
    │       ├── pareto_front.csv   Per-point metrics (cost, energy, gap…)
    │       ├── assignments.json   Decision variables per Pareto point
    │       └── run_info.json      Metadata (config, timing, status)

Usage:
    python scripts/run_doe_L9.py                        # full DOE (252 runs)
    python scripts/run_doe_L9.py --smoke                # 1 config × 1 instance
    python scripts/run_doe_L9.py --configs c01 c03      # specific configs
    python scripts/run_doe_L9.py --instances Scholl_BOWMAN8 instance_n=20_1
    python scripts/run_doe_L9.py --resume               # skip completed runs
    python scripts/run_doe_L9.py --time-limit 600       # 600 s per ε-step
"""

import argparse
import csv
import json
import signal
import sys
import time
import math
import importlib.util
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Prevent BrokenPipeError from corrupting results when stdout is piped
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

import numpy as np

# ═══════════════════════════════════════════════════════════════════════
# Project setup
# ═══════════════════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from calbp.doe.taguchi import L9_MATRIX, PILOT_FACTORS
from calbp.doe.scenario import build_scenarios, Scenario, write_manifest
from calbp.generation.instance_builder import build_cal_instance
from calbp.data.instance_io import write_txt, read_txt
from calbp.data.scholl_parser import SchollInstance
from calbp.constants import ALL_MODE_NAMES, MODE_IDS
from calbp.analysis.indicators import compute_all_indicators

# Import MILP solver directly (avoid wrapper overhead, get raw dicts)
_spec = importlib.util.spec_from_file_location(
    "MILP_Audrey", str(PROJECT_ROOT / "MILP_Audrey.py")
)
_milp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_milp)

# ═══════════════════════════════════════════════════════════════════════
# Paths & benchmark definition
# ═══════════════════════════════════════════════════════════════════════
RESULTS_DIR   = PROJECT_ROOT / "results_doe_L9"
SOLUTIONS_DIR = RESULTS_DIR / "solutions"

# Scholl instances — base .txt in CAL-instances/txt/
SCHOLL_TXT_DIR = PROJECT_ROOT / "CAL-instances" / "txt"
SCHOLL_SELECTED_NAMES = [
    "Scholl_MERTENS",
    "Scholl_JAESCHKE",
    "Scholl_MANSOOR",
    "Scholl_MITCHELL",
    "Scholl_BUXEY",
    "Scholl_SAWYER30",
    "Scholl_GUNTHER",
    "Scholl_KILBRID",
    "Scholl_HAHN",
    "Scholl_WEE-MAG",
    "Scholl_ARC83",
    "Scholl_LUTZ2",
    "Scholl_MUKHERJE",
    "Scholl_ARC111",
]

# Otto n=20 representative subset
OTTO_TXT_DIR = (
    PROJECT_ROOT / "SALBP-data-sets" / "converted_instances_small_updated"
)
OTTO_SELECTED_IDS = [
    63, 1, 10, 77, 97, 87, 69, 74, 68, 73, 99, 88, 91, 82,
]

# Fixed parameters (not DOE factors)
FIXED_R_E = 0.05   # kW
FIXED_C_C = 5.0    # €/h


# ═══════════════════════════════════════════════════════════════════════
# Instance loading helpers
# ═══════════════════════════════════════════════════════════════════════

def load_base_from_txt(txt_path: Path) -> tuple[SchollInstance, float]:
    """
    Read an existing CAL .txt file and extract the base instance
    (HI processing times + precedence + cycle time T).

    This works for both Scholl and Otto instances.  The HI times
    (mode 1) are the fundamental task durations; other modes are
    regenerated per DOE config.
    """
    cal = read_txt(txt_path)
    hi_times = [int(round(cal.t_jm[(j, "HI")])) for j in cal.tasks]

    base = SchollInstance(
        name=txt_path.stem,
        n_tasks=len(cal.tasks),
        task_times=hi_times,
        precedence=cal.precedence,
        source_path=str(txt_path),
    )
    return base, cal.T


def _count_tasks(txt_path: Path) -> int:
    """Quick task count from a CAL .txt file (line 2 = task list)."""
    with open(txt_path, encoding="utf-8") as f:
        f.readline()  # skip "# Tasks"
        return len(f.readline().split())


def collect_benchmark() -> list[tuple[str, Path, str]]:
    """
    Return [(instance_name, txt_path, source), ...] for the full benchmark,
    sorted by ascending number of tasks (smallest first).
    source ∈ {"Scholl", "Otto"}.
    """
    instances = []

    wanted_scholl = set(SCHOLL_SELECTED_NAMES)

    # 14 representative Scholl instances
    for p in sorted(SCHOLL_TXT_DIR.glob("Scholl_*.txt")):
        if p.stem in wanted_scholl:
            instances.append((p.stem, p, "Scholl"))

    # 14 representative Otto n=20 instances
    for oid in OTTO_SELECTED_IDS:
        name = f"instance_n=20_{oid}"
        p = OTTO_TXT_DIR / f"{name}.txt"
        if p.exists():
            instances.append((name, p, "Otto"))
        else:
            print(f"[WARN] Otto instance not found: {p}")

    found_scholl = {name for name, _, src in instances if src == "Scholl"}
    missing_scholl = sorted(wanted_scholl - found_scholl)
    if missing_scholl:
        print(f"[WARN] Missing Scholl instances: {missing_scholl}")

    found_otto = {name for name, _, src in instances if src == "Otto"}
    wanted_otto = {f"instance_n=20_{oid}" for oid in OTTO_SELECTED_IDS}
    missing_otto = sorted(wanted_otto - found_otto)
    if missing_otto:
        print(f"[WARN] Missing Otto instances: {missing_otto}")

    # Sort by number of tasks (ascending) — small instances first
    instances.sort(key=lambda x: _count_tasks(x[1]))

    return instances


# ═══════════════════════════════════════════════════════════════════════
# Instance generation
# ═══════════════════════════════════════════════════════════════════════

def generate_instance(
    base: SchollInstance,
    T_base: float,
    scenario: Scenario,
    output_path: Path,
) -> Path:
    """Generate a DOE-parametrised CAL instance and write it to disk."""
    inst = build_cal_instance(
        base=base,
        alpha_ci=scenario.alpha_ci,
        beta_su=scenario.beta_su,
        gamma_setup=scenario.gamma_setup,
        sigma_si=scenario.sigma_si,
        R_e=scenario.R_e,
        T=T_base,
        seed=scenario.seed,
        config_name=scenario.config_name,
        C_s=4.0,
        C_w=36.0,
        C_c=scenario.C_c,
    )

    # Ensure T covers all mode times
    max_time = max(
        inst.t_jm[(j, m)] for j in inst.tasks for m in ALL_MODE_NAMES
    )
    if max_time > inst.T:
        inst.T = float(max_time) * 1.05

    write_txt(inst, output_path)
    return output_path


# ═══════════════════════════════════════════════════════════════════════
# Output savers
# ═══════════════════════════════════════════════════════════════════════

def save_pareto_csv(pareto_points: list[dict], path: Path) -> None:
    """Save Pareto front as CSV (one row per point, all metrics)."""
    if not pareto_points:
        return

    fieldnames = [
        "point_idx", "cost", "energy",
        "stations", "workers", "cobots",
        "certified", "lb", "ub", "mip_gap_pct", "n_nodes", "cpu_s",
        "energy_tasks", "energy_idle", "cobot_util",
        "HI", "CI", "SEH", "SEC", "SU", "SIH", "SIC",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, p in enumerate(pareto_points):
            modes = p.get("mode_distrib", {})
            writer.writerow({
                "point_idx": i,
                "cost": p["cost"],
                "energy": p["energy"],
                "stations": int(p["stations"]),
                "workers": int(p["workers"]),
                "cobots": int(p["cobots"]),
                "certified": p.get("certified", False),
                "lb": p.get("lb"),
                "ub": p.get("ub"),
                "mip_gap_pct": p.get("mip_gap"),
                "n_nodes": p.get("n_nodes"),
                "cpu_s": round(p.get("cpu_point", 0), 2),
                "energy_tasks": round(p.get("energy_tasks", 0), 2),
                "energy_idle": round(p.get("energy_idle", 0), 2),
                "cobot_util": p.get("cobot_util"),
                "HI": modes.get("HI", 0),
                "CI": modes.get("CI", 0),
                "SEH": modes.get("SEH", 0),
                "SEC": modes.get("SEC", 0),
                "SU": modes.get("SU", 0),
                "SIH": modes.get("SIH", 0),
                "SIC": modes.get("SIC", 0),
            })


def save_assignments_json(pareto_points: list[dict], path: Path) -> None:
    """Save full decision variable values per Pareto point as JSON."""
    points_data = []
    for i, p in enumerate(pareto_points):
        point_obj = {
            "point_idx": i,
            "cost": p["cost"],
            "energy": p["energy"],
            "assignments": p.get("assignments", []),
            "station_info": p.get("station_info", []),
            "mode_distrib": p.get("mode_distrib", {}),
        }
        points_data.append(point_obj)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"points": points_data}, indent=2, default=str),
        encoding="utf-8",
    )


def save_run_info(
    run_name: str,
    base_name: str,
    source: str,
    n_tasks: int,
    T: float,
    scenario: Scenario,
    pareto_points: list[dict],
    total_cpu: float,
    status: str,
    path: Path,
    error_message: str | None = None,
) -> None:
    """Save run metadata as JSON."""
    n_certified = sum(
        1 for p in pareto_points if p.get("certified", False)
    )
    gaps = [
        p["mip_gap"]
        for p in pareto_points
        if isinstance(p.get("mip_gap"), (int, float))
    ]

    info = {
        "run_name": run_name,
        "base_instance": base_name,
        "source": source,
        "n_tasks": n_tasks,
        "T": T,
        "config": {
            "config_name": scenario.config_name,
            "config_id": scenario.config_id,
            "alpha_ci": scenario.alpha_ci,
            "beta_su": scenario.beta_su,
            "gamma_setup": scenario.gamma_setup,
            "sigma_si": scenario.sigma_si,
            "R_e": scenario.R_e,
            "C_c": scenario.C_c,
            "seed": scenario.seed,
        },
        "status": status,
        "n_pareto": len(pareto_points),
        "n_certified": n_certified,
        "total_cpu_s": round(total_cpu, 2),
        "gap_mean_pct": round(sum(gaps) / len(gaps), 4) if gaps else None,
        "gap_max_pct": round(max(gaps), 4) if gaps else None,
        "timestamp": datetime.now().isoformat(),
    }

    if error_message:
        info["error_message"] = error_message

    # Add quality indicators
    if pareto_points:
        costs = [p["cost"] for p in pareto_points]
        energies = [p["energy"] for p in pareto_points]
        ind = compute_all_indicators(costs, energies, delta=0.10)
        info["indicators"] = ind

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2, default=str), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# Master CSV row builder
# ═══════════════════════════════════════════════════════════════════════

MASTER_FIELDS = [
    # Identification
    "run_name", "base_instance", "source", "n_tasks",
    "config_name", "config_id",
    # DOE factors
    "alpha_ci", "beta_su", "gamma_setup", "sigma_si",
    # Fixed params (recorded for traceability)
    "R_e", "C_c", "T", "seed",
    # Result summary
    "status", "n_pareto", "n_certified", "total_cpu_s",
    # Pareto range
    "min_cost", "max_cost", "min_energy", "max_energy",
    "cost_range", "energy_range",
    # Quality indicators (Zitzler et al.)
    "HV_abs", "HV_norm", "ref_cost", "ref_energy",
    "spacing", "spread_delta", "max_spread",
    # MILP quality
    "gap_mean_pct", "gap_max_pct",
    # Mode shares (%)
    "pct_HI", "pct_CI", "pct_SEH", "pct_SEC",
    "pct_SU", "pct_SIH", "pct_SIC",
]


def build_master_row(
    run_name: str,
    base_name: str,
    source: str,
    n_tasks: int,
    T: float,
    scenario: Scenario,
    pareto_points: list[dict],
    total_cpu: float,
    status: str,
) -> dict:
    """Build one row for the master results CSV."""
    row = {
        "run_name": run_name,
        "base_instance": base_name,
        "source": source,
        "n_tasks": n_tasks,
        "config_name": scenario.config_name,
        "config_id": scenario.config_id,
        "alpha_ci": scenario.alpha_ci,
        "beta_su": scenario.beta_su,
        "gamma_setup": scenario.gamma_setup,
        "sigma_si": scenario.sigma_si,
        "R_e": scenario.R_e,
        "C_c": scenario.C_c,
        "T": T,
        "seed": scenario.seed,
        "status": status,
        "n_pareto": len(pareto_points),
        "total_cpu_s": round(total_cpu, 2),
    }

    # Certified count
    row["n_certified"] = sum(
        1 for p in pareto_points if p.get("certified", False)
    )

    # Quality indicators
    if pareto_points:
        costs = [p["cost"] for p in pareto_points]
        energies = [p["energy"] for p in pareto_points]
        row["min_cost"] = round(min(costs), 2)
        row["max_cost"] = round(max(costs), 2)
        row["min_energy"] = round(min(energies), 2)
        row["max_energy"] = round(max(energies), 2)

        ind = compute_all_indicators(costs, energies, delta=0.10)
        row["cost_range"] = ind["cost_range"]
        row["energy_range"] = ind["energy_range"]
        row["HV_abs"] = ind["HV_abs"]
        row["HV_norm"] = ind["HV_norm"]
        row["ref_cost"] = ind["ref_cost"]
        row["ref_energy"] = ind["ref_energy"]
        row["spacing"] = ind["spacing"]
        row["spread_delta"] = ind["spread_delta"]
        row["max_spread"] = ind["max_spread"]
    else:
        for k in ("min_cost", "max_cost", "min_energy", "max_energy",
                   "cost_range", "energy_range",
                   "HV_abs", "HV_norm", "ref_cost", "ref_energy",
                   "spacing", "spread_delta", "max_spread"):
            row[k] = ""

    # MIP gap
    gaps = [
        p["mip_gap"]
        for p in pareto_points
        if isinstance(p.get("mip_gap"), (int, float))
    ]
    row["gap_mean_pct"] = round(sum(gaps) / len(gaps), 4) if gaps else ""
    row["gap_max_pct"] = round(max(gaps), 4) if gaps else ""

    # Mode shares (average % across Pareto front)
    mode_sums = defaultdict(float)
    total_assign = 0
    for p in pareto_points:
        distrib = p.get("mode_distrib", {})
        for m, cnt in distrib.items():
            mode_sums[m] += cnt
            total_assign += cnt

    for m in ALL_MODE_NAMES:
        if total_assign > 0:
            row[f"pct_{m}"] = round(mode_sums.get(m, 0) / total_assign * 100, 2)
        else:
            row[f"pct_{m}"] = 0.0

    return row


# ═══════════════════════════════════════════════════════════════════════
# Main DOE loop
# ═══════════════════════════════════════════════════════════════════════

def run_doe(args):
    """Execute the full L9 DOE campaign."""

    # ── 1. Build scenarios ────────────────────────────────────────
    scenarios = build_scenarios(
        L9_MATRIX, PILOT_FACTORS,
        seed_base=42,
        default_R_e=FIXED_R_E,
        default_C_c=FIXED_C_C,
        level_strategy="uniform",
    )
    print(f"[DOE] {len(scenarios)} configs from L9 × PILOT_FACTORS")

    # Filter configs
    if args.configs:
        cfg_set = set(args.configs)
        scenarios = [s for s in scenarios if s.config_name in cfg_set]
        print(f"[DOE] Filtered to configs: {[s.config_name for s in scenarios]}")

    # ── 2. Collect benchmark instances ────────────────────────────
    all_instances = collect_benchmark()

    # Filter instances
    if args.instances:
        inst_set = set(args.instances)
        all_instances = [(n, p, s) for n, p, s in all_instances if n in inst_set]

    if args.smoke:
        # Quick test: first config × smallest Scholl instance
        scenarios = scenarios[:1]
        # Pick BOWMAN8 (8 tasks) for fast validation
        smoke_targets = [
            (n, p, s) for n, p, s in all_instances if "BOWMAN8" in n
        ]
        if smoke_targets:
            all_instances = smoke_targets[:1]
        else:
            all_instances = all_instances[:1]
        print(f"[DOE] Smoke mode: {scenarios[0].config_name} × {all_instances[0][0]}")

    n_scholl = sum(1 for _, _, s in all_instances if s == "Scholl")
    n_otto = sum(1 for _, _, s in all_instances if s == "Otto")
    total_runs = len(scenarios) * len(all_instances)
    print(f"[DOE] Instances: {n_scholl} Scholl + {n_otto} Otto = {len(all_instances)}")
    print(f"[DOE] Total runs: {len(scenarios)} × {len(all_instances)} = {total_runs}")
    print(f"[DOE] Time limit: {args.time_limit}s per ε-step")
    print(f"[DOE] Results → {RESULTS_DIR}")

    # ── 3. Prepare output dirs ────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Write manifest
    inst_names = [n for n, _, _ in all_instances]
    write_manifest(scenarios, inst_names, RESULTS_DIR / "doe_manifest.csv")

    # ── 4. Solve loop ────────────────────────────────────────────
    #    Order: all Scholl × all configs, then all Otto × all configs.
    #    Within each group instances stay sorted by task count (ascending).
    all_rows: list[dict] = []
    done = 0
    t_campaign_start = time.time()

    scholl_instances = [(n, p, s) for n, p, s in all_instances if s == "Scholl"]
    otto_instances   = [(n, p, s) for n, p, s in all_instances if s == "Otto"]
    ordered_runs = []
    for inst_name, txt_path, source in scholl_instances:
        for sc in scenarios:
            ordered_runs.append((sc, inst_name, txt_path, source))
    for inst_name, txt_path, source in otto_instances:
        for sc in scenarios:
            ordered_runs.append((sc, inst_name, txt_path, source))

    for sc, inst_name, txt_path, source in ordered_runs:
            done += 1
            run_name = f"{inst_name}_{sc.config_name}"
            sol_dir = SOLUTIONS_DIR / run_name

            # Resume: skip if already solved
            run_info_path = sol_dir / "run_info.json"
            if args.resume and run_info_path.exists():
                try:
                    existing = json.loads(run_info_path.read_text())
                    if existing.get("status") == "OK":
                        print(
                            f"[{done}/{total_runs}] {run_name} — SKIP (already solved)"
                        )
                        # Rebuild master row from saved info
                        pf_csv = sol_dir / "pareto_front.csv"
                        if pf_csv.exists():
                            # Read pareto_front.csv to rebuild row
                            # (lightweight, no re-solve)
                            pass
                        continue
                except Exception:
                    pass  # re-solve if file is corrupt

            print(
                f"\n[{done}/{total_runs}] {run_name}  "
                f"({source}, instance={inst_name})  "
                f"α={sc.alpha_ci:.2f} β={sc.beta_su:.2f} "
                f"γ={sc.gamma_setup:.2f} σ={sc.sigma_si:.2f}"
            )

            # ── 4a. Load base instance ────────────────────────────
            try:
                base, T_base = load_base_from_txt(txt_path)
            except Exception as e:
                print(f"    ERROR loading base: {e}")
                row = build_master_row(
                    run_name, inst_name, source, 0, 0,
                    sc, [], 0, "LOAD_ERROR",
                )
                all_rows.append(row)
                continue

            # ── 4b. Generate DOE instance ─────────────────────────
            sol_dir.mkdir(parents=True, exist_ok=True)
            inst_path = sol_dir / "instance.txt"

            try:
                generate_instance(base, T_base, sc, inst_path)
            except Exception as e:
                print(f"    ERROR generating instance: {e}")
                row = build_master_row(
                    run_name, inst_name, source, base.n_tasks, T_base,
                    sc, [], 0, "GEN_ERROR",
                )
                all_rows.append(row)
                continue

            # ── 4c. Solve with MILP ───────────────────────────────
            t0 = time.time()
            try:
                pareto_points = _milp.solve_instance(
                    str(inst_path),
                    results_dir=str(sol_dir),
                    time_limit=args.time_limit,
                    save_files=False,
                    add_C2a=True,
                    add_C4wy=True,
                    add_C5bc=False,
                )
                status = "OK" if pareto_points else "INFEASIBLE"
            except Exception as e:
                import traceback as _tb
                _err_msg = f"{e}\n{''.join(_tb.format_exc())}"
                print(f"    ERROR solving: {_err_msg}")
                pareto_points = []
                status = "ERROR"
            else:
                _err_msg = None
            total_cpu = time.time() - t0

            if not pareto_points:
                pareto_points = []

            # ── 4d. Save per-solution files ───────────────────────
            save_pareto_csv(pareto_points, sol_dir / "pareto_front.csv")
            save_assignments_json(pareto_points, sol_dir / "assignments.json")
            save_run_info(
                run_name, inst_name, source, base.n_tasks, T_base,
                sc, pareto_points, total_cpu, status,
                sol_dir / "run_info.json",
                error_message=_err_msg if status == "ERROR" else None,
            )

            # ── 4e. Build master row ──────────────────────────────
            row = build_master_row(
                run_name, inst_name, source, base.n_tasks, T_base,
                sc, pareto_points, total_cpu, status,
            )
            all_rows.append(row)

            n_pts = len(pareto_points)
            print(
                f"    → {status}  PF={n_pts}  CPU={total_cpu:.1f}s  "
                f"certified={row['n_certified']}/{n_pts}"
            )

    # ── 5. Write master CSV ──────────────────────────────────────
    elapsed = time.time() - t_campaign_start

    if all_rows:
        csv_path = RESULTS_DIR / "doe_results.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n[DOE] Master CSV → {csv_path}")

    # ── 6. Print summary ─────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  DOE L9 COMPLETE — {len(all_rows)} runs in {elapsed:.0f}s")
    print(f"{'='*65}")

    ok_rows = [r for r in all_rows if r["status"] == "OK"]
    if ok_rows:
        pf_sizes = [r["n_pareto"] for r in ok_rows]
        cpus = [r["total_cpu_s"] for r in ok_rows]
        print(f"  Successful: {len(ok_rows)}/{len(all_rows)}")
        print(
            f"  |PF|: mean={np.mean(pf_sizes):.1f}  "
            f"min={min(pf_sizes)}  max={max(pf_sizes)}"
        )
        print(
            f"  CPU:  mean={np.mean(cpus):.0f}s  "
            f"total={sum(cpus):.0f}s"
        )

        # Mode shares summary
        print(f"\n  Average mode shares:")
        for m in ALL_MODE_NAMES:
            vals = [r[f"pct_{m}"] for r in ok_rows]
            print(f"    {m:3s}: {np.mean(vals):5.1f}%  (σ={np.std(vals):.1f})")

    errors = [r for r in all_rows if r["status"] != "OK"]
    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for r in errors:
            print(f"    {r['run_name']}: {r['status']}")

    print(f"\n{'='*65}")


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="L9 Taguchi DOE — MILP solver campaign"
    )
    parser.add_argument(
        "--time-limit", type=int, default=300,
        help="CPLEX time limit per ε-step in seconds (default: 300)",
    )
    parser.add_argument(
        "--configs", nargs="+", default=None,
        help="Run only these configs (e.g. c01 c05)",
    )
    parser.add_argument(
        "--instances", nargs="+", default=None,
        help="Run only these instances (e.g. Scholl_BOWMAN8 instance_n=20_1)",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Quick test: 1 config × 1 instance",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip runs that already have a run_info.json with status=OK",
    )
    args = parser.parse_args()
    run_doe(args)


if __name__ == "__main__":
    main()
