"""
Instance builder — combines Scholl base data + DOE parameters
into a complete CALInstance.
"""

import numpy as np
from calbp.data.scholl_parser import SchollInstance
from calbp.data.cal_instance import CALInstance
from calbp.generation.time_generator import generate_mode_times
from calbp.generation.energy_generator import generate_mode_energies
from calbp.constants import DEFAULT_C_S, DEFAULT_C_W, DEFAULT_C_C

FACTOR_LEVEL_INTERVALS = {
    "alpha_ci": {
        "low": (0.85, 1.10),
        "mid": (1.20, 1.60),
        "high": (1.80, 2.50),
    },
    "beta_su": {
        "low": (0.30, 0.45),
        "mid": (0.55, 0.70),
        "high": (0.80, 0.95),
    },
    "gamma_setup": {
        "low": (0.85, 0.95),
        "mid": (0.95, 1.05),
        "high": (1.05, 1.10),
    },
    "sigma_si": {
        "low": (1.00, 1.10),
        "mid": (1.10, 1.25),
        "high": (1.25, 1.45),
    },
}


def _resolve_factor_interval(
    name: str,
    nominal_value: float,
    level_label: str = "",
) -> tuple[float, float]:
    """Resolve the DOE interval from an explicit level or a numeric value."""
    if level_label in FACTOR_LEVEL_INTERVALS[name]:
        return FACTOR_LEVEL_INTERVALS[name][level_label]

    for lo, hi in FACTOR_LEVEL_INTERVALS[name].values():
        if lo - 1e-9 <= nominal_value <= hi + 1e-9:
            return lo, hi
    return nominal_value, nominal_value


def _build_task_factor_profile(
    name: str,
    nominal_value: float,
    n_tasks: int,
    rng: np.random.Generator,
    level_label: str = "",
) -> list[float]:
    """
    Sample one task-specific factor value uniformly inside the DOE level.
    """
    lo, hi = _resolve_factor_interval(name, nominal_value, level_label)
    if hi - lo <= 1e-9:
        return [round(float(nominal_value), 4)] * n_tasks
    return [
        round(float(rng.uniform(lo, hi)), 4)
        for _ in range(n_tasks)
    ]


def build_cal_instance(
    base: SchollInstance,
    alpha_ci: float,
    beta_su: float,
    gamma_setup: float,
    sigma_si: float,
    R_e: float,
    T: float | None = None,
    seed: int = 42,
    config_name: str = "",
    C_s: float = DEFAULT_C_S,
    C_w: float = DEFAULT_C_W,
    C_c: float = DEFAULT_C_C,
    factor_granularity: str = "instance",
    alpha_level: str = "",
    beta_level: str = "",
    gamma_level: str = "",
    sigma_level: str = "",
    R_e_level: str = "",
    C_c_level: str = "",
) -> CALInstance:
    """
    Build a CALInstance from a Scholl base instance and DOE parameters.

    Parameters
    ----------
    base : SchollInstance
        Parsed Scholl .IN2 data.
    alpha_ci, beta_su, gamma_setup, sigma_si : float
        Collaboration mode parameters.
    R_e : float
        Idle energy rate (kW).
    T : float or None
        Cycle time. If None, uses a default heuristic (see below).
    seed : int
        Random seed for energy generation.
    config_name : str
        DOE configuration identifier.
    factor_granularity : str
        "instance" reproduces the historical one-value-per-config DOE.
        "task" samples one factor value per task uniformly within the DOE level.

    Returns
    -------
    CALInstance
        Complete, validated instance.
    """
    tasks = list(range(1, base.n_tasks + 1))
    stations = list(range(1, base.n_tasks + 1))  # K_max = n (conservative)
    task_parameters: dict[str, list[float]] = {}

    if factor_granularity == "task":
        profile_rng = np.random.default_rng(seed + 100_003)
        task_parameters = {
            "alpha_ci": _build_task_factor_profile(
                "alpha_ci", alpha_ci, base.n_tasks, profile_rng, alpha_level
            ),
            "beta_su": _build_task_factor_profile(
                "beta_su", beta_su, base.n_tasks, profile_rng, beta_level
            ),
            "gamma_setup": _build_task_factor_profile(
                "gamma_setup", gamma_setup, base.n_tasks, profile_rng, gamma_level
            ),
            "sigma_si": _build_task_factor_profile(
                "sigma_si", sigma_si, base.n_tasks, profile_rng, sigma_level
            ),
        }
    elif factor_granularity != "instance":
        raise ValueError(
            f"Unsupported factor granularity: {factor_granularity}"
        )

    # Cycle time: use Scholl's recommended T if available, else heuristic
    if T is None:
        # Heuristic: T = max task time × α (ensures CI feasibility)
        alpha_ref = (
            max(task_parameters["alpha_ci"])
            if factor_granularity == "task"
            else alpha_ci
        )
        T = max(base.task_times) * max(alpha_ref, 1.0) * 1.5

    # Generate times
    t_jm = generate_mode_times(
        base.task_times,
        task_parameters.get("alpha_ci", alpha_ci),
        task_parameters.get("beta_su", beta_su),
        task_parameters.get("gamma_setup", gamma_setup),
        task_parameters.get("sigma_si", sigma_si),
    )

    # Generate energies (with reproducible RNG)
    rng = np.random.default_rng(seed)
    E_jm = generate_mode_energies(tasks, t_jm, rng)

    if task_parameters:
        factor_means = {
            name: round(float(np.mean(values)), 4)
            for name, values in task_parameters.items()
        }
        factor_stds = {
            name: round(float(np.std(values)), 4)
            for name, values in task_parameters.items()
        }
    else:
        factor_means = {
            "alpha_ci": round(alpha_ci, 4),
            "beta_su": round(beta_su, 4),
            "gamma_setup": round(gamma_setup, 4),
            "sigma_si": round(sigma_si, 4),
        }
        factor_stds = {
            "alpha_ci": 0.0,
            "beta_su": 0.0,
            "gamma_setup": 0.0,
            "sigma_si": 0.0,
        }

    return CALInstance(
        name=f"{base.name}_{config_name}" if config_name else base.name,
        tasks=tasks,
        stations=stations,
        precedence=base.precedence,
        t_jm=t_jm,
        E_jm=E_jm,
        T=T,
        R_e=R_e,
        C_s=C_s,
        C_w=C_w,
        C_c=C_c,
        base_instance=base.name,
        config_name=config_name,
        alpha_ci=factor_means["alpha_ci"],
        beta_su=factor_means["beta_su"],
        gamma_setup=factor_means["gamma_setup"],
        sigma_si=factor_means["sigma_si"],
        alpha_ci_std=factor_stds["alpha_ci"],
        beta_su_std=factor_stds["beta_su"],
        gamma_setup_std=factor_stds["gamma_setup"],
        sigma_si_std=factor_stds["sigma_si"],
        alpha_level=alpha_level,
        beta_level=beta_level,
        gamma_level=gamma_level,
        sigma_level=sigma_level,
        R_e_level=R_e_level,
        C_c_level=C_c_level,
        factor_granularity=factor_granularity,
        task_parameters=task_parameters,
        seed=seed,
    )
