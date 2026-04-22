"""
Energy generation for CALBP collaboration modes.

Model (provisional, documented in EXPERIMENTAL_DESIGN.md §A3):

  E(j, m) = ceil( P_mode(m) × t(j,m) / 1000 )   [kJ]

  where P_mode is the average power draw (W) of the cobot under mode m,
  drawn once per task from a uniform distribution within the mode's range.

  Human-only modes (HI, SEH, SIH) have E = 0 (no cobot energy).

This creates partial task-level variability in energy while keeping the
overall mode ranking deterministic (CI most expensive, SIC cheapest among
cobot modes).

Labelling: This is a *provisional* energy model.  The paper should
discuss it as a modelling assumption, not as empirical data.
"""

import math
import numpy as np
from calbp.constants import DEFAULT_POWER_RANGES, ALL_MODE_NAMES


def generate_mode_energies(
    tasks: list[int],
    t_jm: dict[tuple[int, str], float],
    rng: np.random.Generator,
    power_ranges: dict[str, tuple[int, int]] | None = None,
) -> dict[tuple[int, str], int]:
    """
    Generate mode-dependent energy values for all tasks.

    Parameters
    ----------
    tasks : list[int]
        1-based task ids.
    t_jm : dict[(task, mode_name), float]
        Processing times (already generated).
    rng : numpy Generator
        For reproducibility.
    power_ranges : dict, optional
        Override default power ranges per mode.

    Returns
    -------
    dict[(task_id, mode_name), int]
        Energy consumption keyed by (task_id, mode_name).
    """
    if power_ranges is None:
        power_ranges = DEFAULT_POWER_RANGES

    E_jm: dict[tuple[int, str], int] = {}

    for j in tasks:
        for m in ALL_MODE_NAMES:
            lo, hi = power_ranges[m]
            if lo == 0 and hi == 0:
                E_jm[(j, m)] = 0
                continue

            # Draw power (W) for this task × mode combination
            power_w = rng.uniform(lo, hi)
            t = t_jm[(j, m)]
            # Energy in kJ: power(W) × time(s) / 1000
            E_jm[(j, m)] = math.ceil(power_w * t / 1000)

    return E_jm
