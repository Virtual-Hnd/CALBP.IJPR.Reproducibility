"""
Pareto-front quality indicators for bi-objective minimisation.

References
----------
- Zitzler & Thiele (1999). Multiobjective evolutionary algorithms: A
  comparative case study and the strength Pareto approach. IEEE TEC 3(4).
- Zitzler, Thiele, Laumanns, Fonseca & da Fonseca (2003). Performance
  assessment of multiobjective optimizers: An analysis and review.
  IEEE TEC 7(2).
- Schott (1995). Fault tolerant design using single and multicriteria
  genetic algorithm optimization. AFIT thesis.
- Deb, Pratap, Agarwal & Meyarivan (2002). A fast and elitist
  multiobjective genetic algorithm: NSGA-II. IEEE TEC 6(2).
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────

def dominated(a: np.ndarray, b: np.ndarray) -> bool:
    """True if *a* is dominated by *b* (both minimised)."""
    return bool(np.all(b <= a) and np.any(b < a))


def pareto_front(points: np.ndarray) -> np.ndarray:
    """Extract the non-dominated subset (minimisation)."""
    n = len(points)
    is_pareto = np.ones(n, dtype=bool)
    for i in range(n):
        if not is_pareto[i]:
            continue
        for j in range(n):
            if i == j or not is_pareto[j]:
                continue
            if dominated(points[i], points[j]):
                is_pareto[i] = False
                break
    return points[is_pareto]


# ───────────────────────────────────────────────────────────────────
# Reference point  (Zitzler et al., 2003)
# ───────────────────────────────────────────────────────────────────

def nadir_point(costs: Sequence[float],
                energies: Sequence[float]) -> tuple[float, float]:
    """Nadir = component-wise worst values on the Pareto front."""
    return (max(costs), max(energies))


def reference_point(costs: Sequence[float],
                    energies: Sequence[float],
                    delta: float = 0.10) -> tuple[float, float]:
    """
    Reference point for hypervolume = Nadir × (1 + δ).

    When a Nadir component is 0, a small absolute margin (1 % of the
    other component, minimum 1.0) is used so the dominated hypervolume
    is non-degenerate.
    """
    nadir_c, nadir_e = nadir_point(costs, energies)

    # Absolute fallback for zero components
    fallback = max(abs(nadir_c), abs(nadir_e), 1.0) * 0.01

    ref_c = nadir_c * (1 + delta) if nadir_c > 0 else fallback
    ref_e = nadir_e * (1 + delta) if nadir_e > 0 else fallback

    return (ref_c, ref_e)


# ───────────────────────────────────────────────────────────────────
# Hypervolume  (Zitzler & Thiele, 1999 — exact 2-D sweep)
# ───────────────────────────────────────────────────────────────────

def hypervolume_2d(pf: np.ndarray, ref: np.ndarray) -> float:
    """
    Exact 2-D hypervolume (S-metric).

    Parameters
    ----------
    pf  : (k, 2) non-dominated points (minimisation).
    ref : (2,)   reference point that is strictly dominated by no point.

    Returns
    -------
    float – area of the objective space dominated by *pf* and bounded
            by *ref*.
    """
    pf = np.asarray(pf, dtype=float)
    ref = np.asarray(ref, dtype=float)

    if pf.ndim != 2 or pf.shape[1] != 2:
        return 0.0

    # keep only points strictly dominated by ref
    mask = np.all(pf < ref, axis=1)
    pf = pf[mask]
    if len(pf) == 0:
        return 0.0

    # sort ascending by obj-1 (cost)
    pf = pf[np.argsort(pf[:, 0])]

    hv = 0.0
    for i in range(len(pf)):
        width = (pf[i + 1, 0] if i + 1 < len(pf) else ref[0]) - pf[i, 0]
        height = ref[1] - pf[i, 1]
        hv += width * height

    return float(hv)


def hypervolume_normalized(costs: Sequence[float],
                           energies: Sequence[float],
                           delta: float = 0.10) -> dict:
    """
    Compute HV, normalised HV, and reference point from a Pareto front.

    Returns dict with keys:
        HV_abs, HV_norm, ref_cost, ref_energy, ideal_cost, ideal_energy,
        nadir_cost, nadir_energy.
    """
    costs = list(costs)
    energies = list(energies)

    if not costs:
        return {k: 0.0 for k in (
            "HV_abs", "HV_norm", "ref_cost", "ref_energy",
            "ideal_cost", "ideal_energy", "nadir_cost", "nadir_energy",
        )}

    ref = reference_point(costs, energies, delta)
    ideal = (min(costs), min(energies))
    nadir = nadir_point(costs, energies)
    pf = np.column_stack([costs, energies])

    hv_abs = hypervolume_2d(pf, np.array(ref))

    # Normalised HV = HV / area(ideal → ref)
    max_area = (ref[0] - ideal[0]) * (ref[1] - ideal[1])
    hv_norm = (hv_abs / max_area) if max_area > 1e-12 else 0.0

    return {
        "HV_abs": round(hv_abs, 6),
        "HV_norm": round(hv_norm, 6),
        "ref_cost": round(ref[0], 4),
        "ref_energy": round(ref[1], 4),
        "ideal_cost": round(ideal[0], 4),
        "ideal_energy": round(ideal[1], 4),
        "nadir_cost": round(nadir[0], 4),
        "nadir_energy": round(nadir[1], 4),
    }


# ───────────────────────────────────────────────────────────────────
# Spacing  (Schott, 1995)
# ───────────────────────────────────────────────────────────────────

def spacing(pf: np.ndarray) -> float:
    """
    SP = sqrt( (1/(|PF|-1)) · Σ (d̄ − dᵢ)² )

    where dᵢ = min_{j≠i} ‖fᵢ − fⱼ‖₁  (nearest-neighbour L1).
    Lower → more uniform.
    """
    pf = np.asarray(pf, dtype=float)
    n = len(pf)
    if n < 2:
        return 0.0

    # nearest-neighbour distances
    d = np.full(n, np.inf)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dist = np.abs(pf[i] - pf[j]).sum()
            if dist < d[i]:
                d[i] = dist

    d_bar = np.mean(d)
    sp = math.sqrt(np.sum((d - d_bar) ** 2) / (n - 1))
    return round(float(sp), 6)


# ───────────────────────────────────────────────────────────────────
# Spread Δ  (Deb et al., 2002)
# ───────────────────────────────────────────────────────────────────

def spread_delta(pf: np.ndarray) -> float:
    """
    Δ = (d_f + d_l + Σ|dᵢ − d̄|) / (d_f + d_l + (N−1)·d̄)

    d_f, d_l : distances between the extreme PF solutions and
               the two boundary solutions of the PF bounding box:
               (min cost, max energy) and (max cost, min energy).
    dᵢ       : consecutive Euclidean distances (sorted by obj-1).
    Lower → more uniform and diverse.  Δ = 0 is ideal.
    """
    pf = np.asarray(pf, dtype=float)
    n = len(pf)
    if n < 2:
        return 1.0  # degenerate

    pf = pf[np.argsort(pf[:, 0])]
    dists = np.sqrt(np.sum(np.diff(pf, axis=0) ** 2, axis=1))

    d_bar = np.mean(dists)
    if d_bar < 1e-12:
        return 0.0

    boundary_left = np.array([np.min(pf[:, 0]), np.max(pf[:, 1])], dtype=float)
    boundary_right = np.array([np.max(pf[:, 0]), np.min(pf[:, 1])], dtype=float)
    d_f = float(np.linalg.norm(pf[0] - boundary_left))
    d_l = float(np.linalg.norm(pf[-1] - boundary_right))

    numerator = d_f + d_l + np.sum(np.abs(dists - d_bar))
    denominator = d_f + d_l + (n - 1) * d_bar

    return round(float(numerator / denominator), 6) if denominator > 0 else 1.0


# ───────────────────────────────────────────────────────────────────
# Maximum Spread  (Zitzler et al., 2000)
# ───────────────────────────────────────────────────────────────────

def maximum_spread(pf: np.ndarray) -> float:
    """
    MS = sqrt( Σ_m (max f_m − min f_m)² )

    Diagonal of the bounding box in objective space.
    """
    pf = np.asarray(pf, dtype=float)
    if len(pf) < 2:
        return 0.0
    ranges = np.ptp(pf, axis=0)
    return round(float(np.sqrt(np.sum(ranges ** 2))), 6)


# ───────────────────────────────────────────────────────────────────
# Coverage C-metric  (Zitzler & Thiele, 1999)
# ───────────────────────────────────────────────────────────────────

def c_metric(A: np.ndarray, B: np.ndarray) -> float:
    """
    C(A, B) = |{b ∈ B : ∃ a ∈ A with a ≼ b}| / |B|

    Fraction of B that is weakly dominated by at least one point in A.
    C(A,B) = 1 means A completely covers B.
    Not symmetric: C(A,B) ≠ C(B,A) in general.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    if len(B) == 0:
        return 1.0
    if len(A) == 0:
        return 0.0

    count = 0
    for b in B:
        for a in A:
            if np.all(a <= b) and np.any(a < b):  # a dominates b
                count += 1
                break

    return round(count / len(B), 6)


# ───────────────────────────────────────────────────────────────────
# Convenience: compute all single-front indicators at once
# ───────────────────────────────────────────────────────────────────

def compute_all_indicators(costs: Sequence[float],
                           energies: Sequence[float],
                           delta: float = 0.10) -> dict:
    """
    Compute all quality indicators for a single Pareto front.

    Returns a flat dict suitable for CSV export.
    """
    costs = list(costs)
    energies = list(energies)
    n = len(costs)

    out: dict = {"PF_size": n}

    if n == 0:
        for k in ("HV_abs", "HV_norm", "ref_cost", "ref_energy",
                   "ideal_cost", "ideal_energy", "nadir_cost", "nadir_energy",
                   "spacing", "spread_delta", "max_spread",
                   "cost_range", "energy_range"):
            out[k] = 0.0
        return out

    # HV
    hv = hypervolume_normalized(costs, energies, delta)
    out.update(hv)

    # Spacing, Spread, Max Spread
    pf = np.column_stack([costs, energies])
    out["spacing"] = spacing(pf)
    out["spread_delta"] = spread_delta(pf)
    out["max_spread"] = maximum_spread(pf)

    # Ranges
    out["cost_range"] = round(max(costs) - min(costs), 4)
    out["energy_range"] = round(max(energies) - min(energies), 4)

    return out
