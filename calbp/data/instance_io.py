"""
Instance I/O — read and write CALBP instances in .txt and .json formats.

The .txt format is compatible with the existing MILP and GRASP solvers.
The .json format adds metadata for traceability.
"""

import json
import math
from pathlib import Path
from calbp.constants import ALL_MODE_NAMES, MODE_IDS, ALL_MODES
from calbp.data.cal_instance import CALInstance


# =============================================================================
# TXT format (solver-compatible)
# =============================================================================

def write_txt(inst: CALInstance, path: Path | str) -> None:
    """Write instance in the .txt format expected by MILP_V1 / GRASP."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Tasks",
        " ".join(str(j) for j in inst.tasks),
        "",
        "# Workstations",
        " ".join(str(k) for k in inst.stations),
        "",
        "# Modes",
        " ".join(str(MODE_IDS[m]) for m in ALL_MODE_NAMES),
        "",
        "# Processing Times",
    ]
    for j in inst.tasks:
        for m_name in ALL_MODE_NAMES:
            m_id = MODE_IDS[m_name]
            t = inst.t_jm[(j, m_name)]
            lines.append(f"{j} {m_id} {t}")

    lines.append("")
    lines.append("# Energy Consumption")
    for j in inst.tasks:
        for m_name in ALL_MODE_NAMES:
            m_id = MODE_IDS[m_name]
            e = inst.E_jm[(j, m_name)]
            lines.append(f"{j} {m_id} {e}")

    lines.append("")
    lines.append("# Precedence Relations")
    for (i, j) in inst.precedence:
        lines.append(f"{i} {j}")

    lines.append("")
    lines.append("# Parameters")
    lines.append(f"R_e = {inst.R_e:.4f}")
    lines.append(f"T = {inst.T}")
    lines.append(f"C_s = {inst.C_s}")
    lines.append(f"C_w = {inst.C_w}")
    lines.append(f"C_c = {inst.C_c}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def read_txt(path: Path | str) -> CALInstance:
    """Read instance from the .txt solver format."""
    import re
    path = Path(path)

    MODE_ID_TO_NAME = {v: k for k, v in MODE_IDS.items()}

    data: dict = {"t_jm": {}, "E_jm": {}, "P": []}
    section = None

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            header = line.lstrip("#").strip().lower()
            if "tasks" in header:
                section = "J"
            elif "workstations" in header:
                section = "K"
            elif "modes" in header:
                section = "M"
            elif "processing time" in header:
                section = "t_jm"
            elif "energy" in header:
                section = "E_jm"
            elif "precedence" in header:
                section = "P"
            elif "parameter" in header:
                section = "params"
            continue

        if section == "J":
            data["J"] = list(map(int, line.split()))
        elif section == "K":
            data["K"] = list(map(int, line.split()))
        elif section == "M":
            pass  # modes are fixed
        elif section == "t_jm":
            parts = line.split()
            if len(parts) >= 3:
                j, m_id, t = int(parts[0]), int(parts[1]), float(parts[2])
                data["t_jm"][(j, MODE_ID_TO_NAME[m_id])] = t
        elif section == "E_jm":
            parts = line.split()
            if len(parts) >= 3:
                j, m_id, e = int(parts[0]), int(parts[1]), float(parts[2])
                data["E_jm"][(j, MODE_ID_TO_NAME[m_id])] = e
        elif section == "P":
            parts = re.split(r"[, ]+", line)
            if len(parts) >= 2:
                data["P"].append((int(parts[0]), int(parts[1])))
        elif section == "params":
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                data[key] = float(val.strip())

    return CALInstance(
        name=path.stem,
        tasks=data["J"],
        stations=data["K"],
        precedence=data["P"],
        t_jm=data["t_jm"],
        E_jm=data["E_jm"],
        T=data.get("T", 0),
        R_e=data.get("R_e", 0.05),
        C_s=data.get("C_s", 4),
        C_w=data.get("C_w", 36),
        C_c=data.get("C_c", 5),
    )


# =============================================================================
# JSON format (with metadata)
# =============================================================================

def write_json(inst: CALInstance, path: Path | str) -> None:
    """Write instance as JSON with full metadata."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    obj = {
        "name": inst.name,
        "base_instance": inst.base_instance,
        "config_name": inst.config_name,
        "generation_params": {
            "alpha_ci": inst.alpha_ci,
            "beta_su": inst.beta_su,
            "gamma_setup": inst.gamma_setup,
            "sigma_si": inst.sigma_si,
            "alpha_ci_std": inst.alpha_ci_std,
            "beta_su_std": inst.beta_su_std,
            "gamma_setup_std": inst.gamma_setup_std,
            "sigma_si_std": inst.sigma_si_std,
            "alpha_level": inst.alpha_level,
            "beta_level": inst.beta_level,
            "gamma_level": inst.gamma_level,
            "sigma_level": inst.sigma_level,
            "R_e_level": inst.R_e_level,
            "C_c_level": inst.C_c_level,
            "factor_granularity": inst.factor_granularity,
            "task_parameters": inst.task_parameters,
            "seed": inst.seed,
        },
        "J": inst.tasks,
        "K": inst.stations,
        "M": ALL_MODE_NAMES,
        "P": inst.precedence,
        "t_jm": {f"{j},{m}": v for (j, m), v in inst.t_jm.items()},
        "E_jm": {f"{j},{m}": v for (j, m), v in inst.E_jm.items()},
        "R_e": inst.R_e,
        "T": inst.T,
        "C_s": inst.C_s,
        "C_w": inst.C_w,
        "C_c": inst.C_c,
    }
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def read_json(path: Path | str) -> CALInstance:
    """Read instance from JSON format."""
    path = Path(path)
    obj = json.loads(path.read_text(encoding="utf-8"))

    t_jm = {}
    for key, val in obj["t_jm"].items():
        j_str, m = key.split(",", 1)
        t_jm[(int(j_str), m)] = float(val)

    E_jm = {}
    for key, val in obj["E_jm"].items():
        j_str, m = key.split(",", 1)
        E_jm[(int(j_str), m)] = float(val)

    gen = obj.get("generation_params", {})

    return CALInstance(
        name=obj["name"],
        tasks=obj["J"],
        stations=obj["K"],
        precedence=[tuple(p) for p in obj["P"]],
        t_jm=t_jm,
        E_jm=E_jm,
        T=obj["T"],
        R_e=obj["R_e"],
        C_s=obj["C_s"],
        C_w=obj["C_w"],
        C_c=obj["C_c"],
        base_instance=obj.get("base_instance", ""),
        config_name=obj.get("config_name", ""),
        alpha_ci=gen.get("alpha_ci", 0),
        beta_su=gen.get("beta_su", 0),
        gamma_setup=gen.get("gamma_setup", 0),
        sigma_si=gen.get("sigma_si", 0),
        alpha_ci_std=gen.get("alpha_ci_std", 0),
        beta_su_std=gen.get("beta_su_std", 0),
        gamma_setup_std=gen.get("gamma_setup_std", 0),
        sigma_si_std=gen.get("sigma_si_std", 0),
        alpha_level=gen.get("alpha_level", ""),
        beta_level=gen.get("beta_level", ""),
        gamma_level=gen.get("gamma_level", ""),
        sigma_level=gen.get("sigma_level", ""),
        R_e_level=gen.get("R_e_level", ""),
        C_c_level=gen.get("C_c_level", ""),
        factor_granularity=gen.get("factor_granularity", "instance"),
        task_parameters=gen.get("task_parameters", {}),
        seed=gen.get("seed", 0),
    )
