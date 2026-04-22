"""
Time generation for CALBP collaboration modes.

Formulas follow the DOE specification used in the paper:

  HI  : t_HI  = t_H                              (human baseline)
  CI  : t_CI  = ceil(α · t_H)                     (cobot, same or slower)
  SU  : t_SU  = ceil(β · t_H)                     (supportive, faster)
  SEH : t_SEH = ceil(γ · t_HI)                   (sequential human ratio)
  SEC : t_SEC = ceil(γ · t_CI)                   (sequential cobot ratio)
  SIH : t_SIH = ceil(σ · t_HI)                   (simultaneous human ratio)
  SIC : t_SIC = ceil(σ · t_CI)                   (simultaneous cobot ratio)

In the ratio-based DOE convention, γ and σ are multiplicative factors.  Values
below 1 shorten the sequential execution time, while values above 1 create an
overhead.  For simultaneous mode, σ > 1 represents coordination overhead.

All times are rounded UP to integer (ceil) to avoid sub-unit artifacts.

Design decision: parameters (α, β, γ, σ) are FIXED per instance, not per task.
This is required for a clean DOE where factor effects are estimable.
"""

import math


def generate_mode_times(
    task_times_hi: list[int],
    alpha_ci: float,
    beta_su: float,
    gamma_setup: float,
    sigma_si: float,
) -> dict[tuple[int, str], int]:
    """
    Generate mode-dependent processing times for all tasks.

    Parameters
    ----------
    task_times_hi : list[int]
        Human baseline times, 0-indexed (task_times_hi[0] = time of task 1).
    alpha_ci : float
        CI / HI speed ratio. α ≥ 1 means cobot is slower.
    beta_su : float
        SU / HI ratio. β < 1 means supportive is faster.
    gamma_setup : float
        Sequential time ratio.
    sigma_si : float
        Simultaneous time ratio.

    Returns
    -------
    dict[(task_id, mode_name), int]
        Processing times keyed by (1-based task id, mode name string).
    """
    t_jm: dict[tuple[int, str], int] = {}

    for idx, t_h in enumerate(task_times_hi):
        j = idx + 1  # 1-based task id

        t_hi = t_h
        t_ci = math.ceil(alpha_ci * t_h)
        t_su = math.ceil(beta_su * t_h)
        t_seh = max(1, math.ceil(gamma_setup * t_hi))
        t_sec = max(1, math.ceil(gamma_setup * t_ci))
        t_sih = max(1, math.ceil(sigma_si * t_hi))
        t_sic = max(1, math.ceil(sigma_si * t_ci))

        t_jm[(j, "HI")]  = t_hi
        t_jm[(j, "CI")]  = t_ci
        t_jm[(j, "SU")]  = t_su
        t_jm[(j, "SEH")] = t_seh
        t_jm[(j, "SEC")] = t_sec
        t_jm[(j, "SIH")] = t_sih
        t_jm[(j, "SIC")] = t_sic

    return t_jm
