"""
DOE scenario definition and manifest generation.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
import csv
import numpy as np
from pathlib import Path


@dataclass
class Scenario:
    """One DOE configuration (one row of the Taguchi array, instantiated)."""
    config_id: int           # 1-based
    config_name: str         # e.g. "c01"
    alpha_ci: float
    beta_su: float
    gamma_setup: float
    sigma_si: float
    R_e: float
    C_c: float               # cobot hourly cost (€/h)
    alpha_level: str
    beta_level: str
    gamma_level: str
    sigma_level: str
    R_e_level: str
    C_c_level: str
    seed: int
    subscenario: str = "normal_equilibre"

    def as_dict(self) -> dict:
        return asdict(self)


def _resolve_level_with_rng(spec, strategy: str, rng: np.random.Generator) -> float:
    """Resolve a factor level specification using the requested strategy."""
    if isinstance(spec, tuple):
        if strategy == "uniform":
            return rng.uniform(spec[0], spec[1])
        if strategy == "midpoint":
            return (spec[0] + spec[1]) / 2.0
        raise ValueError(f"Unsupported DOE level strategy: {strategy}")
    return float(spec)


def build_scenarios(
    oa_matrix: list[tuple],
    factors: dict,
    seed_base: int = 42,
    default_R_e: float = 0.05,
    default_C_c: float = 5.0,
    level_strategy: str = "uniform",
) -> list[Scenario]:
    """
    Build concrete scenarios from a Taguchi OA matrix.

    Parameters
    ----------
    oa_matrix : list of tuples
        Each tuple is one row of the OA, with level indices.
    factors : dict
        Factor definitions (see taguchi.py).
    seed_base : int
        Base seed for reproducible scenario instantiation.
    default_R_e : float
        Fallback R_e if not a factor in the design.
    default_C_c : float
        Fallback C_c if not a factor in the design.
    level_strategy : str
        Strategy used to instantiate interval-based levels.  "uniform"
        samples one value per configuration and level interval, while
        "midpoint" uses fixed representative values.

    Returns
    -------
    list[Scenario]
    """
    factor_keys = sorted(factors.keys())  # A, B, C, D, E, F...
    scenarios = []
    level_labels = {0: "low", 1: "mid", 2: "high"}

    for cfg_idx, row in enumerate(oa_matrix, start=1):
        rng = np.random.default_rng(seed_base + cfg_idx * 1000)
        cfg_name = f"c{cfg_idx:02d}"

        params: dict[str, float] = {}
        level_by_name: dict[str, str] = {}
        for col, key in enumerate(factor_keys):
            level_idx = row[col]
            spec = factors[key]["levels"][level_idx]
            factor_name = factors[key]["name"]
            params[factor_name] = _resolve_level_with_rng(
                spec, level_strategy, rng
            )
            level_by_name[factor_name] = level_labels[level_idx]

        # Extract R_e and C_c (may or may not be DOE factors)
        R_e = params.pop("R_e", default_R_e)
        C_c = params.pop("C_c", default_C_c)

        scenarios.append(Scenario(
            config_id=cfg_idx,
            config_name=cfg_name,
            alpha_ci=round(params.get("alpha_ci", 1.0), 4),
            beta_su=round(params.get("beta_su", 0.75), 4),
            gamma_setup=round(params.get("gamma_setup", 0.10), 4),
            sigma_si=round(params.get("sigma_si", 0.15), 4),
            R_e=round(R_e, 4),
            C_c=round(C_c, 2),
            alpha_level=level_by_name.get("alpha_ci", "fixed"),
            beta_level=level_by_name.get("beta_su", "fixed"),
            gamma_level=level_by_name.get("gamma_setup", "fixed"),
            sigma_level=level_by_name.get("sigma_si", "fixed"),
            R_e_level=level_by_name.get("R_e", "fixed"),
            C_c_level=level_by_name.get("C_c", "fixed"),
            seed=seed_base + cfg_idx * 1000,
        ))

    annotate_subscenarios(scenarios)
    return scenarios


def _tercile_levels(values: list[float]) -> tuple[float, float]:
    """Return q33 and q66 thresholds for a value list."""
    arr = np.asarray(values, dtype=float)
    q33, q66 = np.percentile(arr, [33.33, 66.67])
    return float(q33), float(q66)


def _label_level(value: float, q33: float, q66: float) -> str:
    """Map a numeric value to low/mid/high using tercile thresholds."""
    if value <= q33:
        return "low"
    if value <= q66:
        return "mid"
    return "high"


def annotate_subscenarios(scenarios: list[Scenario]) -> list[Scenario]:
    """
    Attach analytical subscenario labels without changing model constraints.

    Rules (all modes remain allowed):
      - se_favorable:      gamma high and sigma low
      - humain_favorable:  alpha high and beta high and C_c high
      - cobot_favorable:   alpha low and beta low and C_c low
      - normal_equilibre:  all remaining configs
    """
    if not scenarios:
        return scenarios

    alpha_q = _tercile_levels([s.alpha_ci for s in scenarios])
    beta_q = _tercile_levels([s.beta_su for s in scenarios])
    gamma_q = _tercile_levels([s.gamma_setup for s in scenarios])
    sigma_q = _tercile_levels([s.sigma_si for s in scenarios])
    cc_q = _tercile_levels([s.C_c for s in scenarios])

    for sc in scenarios:
        alpha_lv = _label_level(sc.alpha_ci, *alpha_q)
        beta_lv = _label_level(sc.beta_su, *beta_q)
        gamma_lv = _label_level(sc.gamma_setup, *gamma_q)
        sigma_lv = _label_level(sc.sigma_si, *sigma_q)
        cc_lv = _label_level(sc.C_c, *cc_q)

        if gamma_lv == "high" and sigma_lv == "low":
            sc.subscenario = "se_favorable"
        elif alpha_lv == "high" and beta_lv == "high" and cc_lv == "high":
            sc.subscenario = "humain_favorable"
        elif alpha_lv == "low" and beta_lv == "low" and cc_lv == "low":
            sc.subscenario = "cobot_favorable"
        else:
            sc.subscenario = "normal_equilibre"

    return scenarios


def select_smoke_scenarios(scenarios: list[Scenario]) -> list[Scenario]:
    """
    Select one representative config per subscenario for smoke tests.

    Priority is low config_id to keep deterministic and simple.
    """
    wanted = [
        "normal_equilibre",
        "se_favorable",
        "humain_favorable",
        "cobot_favorable",
    ]

    selected: list[Scenario] = []
    for label in wanted:
        candidates = sorted(
            (s for s in scenarios if s.subscenario == label),
            key=lambda s: s.config_id,
        )
        if candidates:
            selected.append(candidates[0])

    return selected


def write_manifest(
    scenarios: list[Scenario],
    base_instances: list[str],
    path: Path | str,
    factor_granularity: str = "task",
) -> None:
    """Write a CSV manifest of all (scenario × instance) combinations."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "instance_name", "base_instance", "config_name", "config_id",
        "subscenario",
        "alpha_level", "beta_level", "gamma_level", "sigma_level",
        "R_e_level", "C_c_level",
        "R_e", "C_c",
        "factor_granularity", "seed",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for sc in scenarios:
            for base_name in base_instances:
                row = {
                    key: value
                    for key, value in sc.as_dict().items()
                    if key in fieldnames
                }
                row["base_instance"] = base_name
                row["instance_name"] = f"{base_name}_{sc.config_name}"
                row["factor_granularity"] = factor_granularity
                writer.writerow(row)
