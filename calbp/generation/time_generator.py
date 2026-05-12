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

The generator supports two conventions:
  - scalar factors: one α/β/γ/σ value reused for every task
  - task profiles: per-task α/β/γ/σ values within the same DOE level
"""

import math
from collections.abc import Sequence


def _value_for_task(param: float | Sequence[float], idx: int) -> float:
    """Return the scalar factor value to use for task index ``idx``."""
    if isinstance(param, Sequence) and not isinstance(param, (str, bytes)):
        return float(param[idx])
    return float(param)


def generate_mode_times(
    task_times_hi: list[int],
    alpha_ci: float | Sequence[float],
    beta_su: float | Sequence[float],
    gamma_setup: float | Sequence[float],
    sigma_si: float | Sequence[float],
) -> dict[tuple[int, str], int]:
    """
    Generate mode-dependent processing times for all tasks.

    Parameters
    ----------
    task_times_hi : list[int]
        Human baseline times, 0-indexed (task_times_hi[0] = time of task 1).
    alpha_ci : float or sequence of float
        CI / HI speed ratio(s). α ≥ 1 means cobot is slower.
    beta_su : float or sequence of float
        SU / HI ratio(s). β < 1 means supportive is faster.
    gamma_setup : float or sequence of float
        Sequential time ratio(s).
    sigma_si : float or sequence of float
        Simultaneous time ratio(s).

    Returns
    -------
    dict[(task_id, mode_name), int]
        Processing times keyed by (1-based task id, mode name string).
    """
    t_jm: dict[tuple[int, str], int] = {}

    for idx, t_h in enumerate(task_times_hi):
        j = idx + 1  # 1-based task id
        alpha_j = _value_for_task(alpha_ci, idx)
        beta_j = _value_for_task(beta_su, idx)
        gamma_j = _value_for_task(gamma_setup, idx)
        sigma_j = _value_for_task(sigma_si, idx)

        t_hi = t_h
        t_ci = math.ceil(alpha_j * t_h)
        t_su = math.ceil(beta_j * t_h)
        t_seh = max(1, math.ceil(gamma_j * t_hi))
        t_sec = max(1, math.ceil(gamma_j * t_ci))
        t_sih = max(1, math.ceil(sigma_j * t_hi))
        t_sic = max(1, math.ceil(sigma_j * t_ci))

        t_jm[(j, "HI")]  = t_hi
        t_jm[(j, "CI")]  = t_ci
        t_jm[(j, "SU")]  = t_su
        t_jm[(j, "SEH")] = t_seh
        t_jm[(j, "SEC")] = t_sec
        t_jm[(j, "SIH")] = t_sih
        t_jm[(j, "SIC")] = t_sic

    return t_jm
