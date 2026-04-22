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

    Returns
    -------
    CALInstance
        Complete, validated instance.
    """
    tasks = list(range(1, base.n_tasks + 1))
    stations = list(range(1, base.n_tasks + 1))  # K_max = n (conservative)

    # Cycle time: use Scholl's recommended T if available, else heuristic
    if T is None:
        # Heuristic: T = max task time × α (ensures CI feasibility)
        T = max(base.task_times) * max(alpha_ci, 1.0) * 1.5

    # Generate times
    t_jm = generate_mode_times(
        base.task_times, alpha_ci, beta_su, gamma_setup, sigma_si
    )

    # Generate energies (with reproducible RNG)
    rng = np.random.default_rng(seed)
    E_jm = generate_mode_energies(tasks, t_jm, rng)

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
        alpha_ci=alpha_ci,
        beta_su=beta_su,
        gamma_setup=gamma_setup,
        sigma_si=sigma_si,
        seed=seed,
    )
