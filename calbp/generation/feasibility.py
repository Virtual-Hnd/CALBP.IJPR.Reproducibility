"""
Pre-solve feasibility diagnostics for generated instances.

These checks are run BEFORE sending instances to solvers, to catch
misconfigurations early and avoid wasting compute time.
"""

from calbp.data.cal_instance import CALInstance
from calbp.constants import ALL_MODE_NAMES


def check_feasibility(inst: CALInstance) -> dict:
    """
    Run feasibility diagnostics.

    Returns a dict with:
      - "valid": bool
      - "issues": list[str]  (from CALInstance.validate)
      - "warnings": list[str]  (soft issues)
      - "stats": dict of diagnostic values
    """
    issues = inst.validate()
    warnings: list[str] = []
    stats: dict = {}

    # --- Task-level cycle time violation count ---
    ct_violations = {}
    for m in ALL_MODE_NAMES:
        count = sum(1 for j in inst.tasks if inst.t_jm.get((j, m), 0) > inst.T)
        ct_violations[m] = count
    stats["cycle_time_violations"] = ct_violations

    total_violations = sum(ct_violations.values())
    if total_violations > 0:
        worst_mode = max(ct_violations, key=ct_violations.get)
        warnings.append(
            f"{total_violations} cycle-time violations across modes "
            f"(worst: {worst_mode} with {ct_violations[worst_mode]})"
        )

    # --- HI-only lower bound on stations ---
    sum_hi = sum(inst.t_jm.get((j, "HI"), 0) for j in inst.tasks)
    lb_stations = max(1, -(-int(sum_hi) // int(inst.T)))
    stats["LB_stations_HI"] = lb_stations
    if lb_stations > inst.n_stations():
        issues.append(
            f"HI-only LB ({lb_stations}) exceeds K_max ({inst.n_stations()}): "
            f"infeasible even in HI mode"
        )

    # --- Mode dominance check ---
    # If SU dominates HI for ALL tasks (faster AND same/less energy), warn
    su_dominates_hi = all(
        inst.t_jm.get((j, "SU"), float("inf")) <= inst.t_jm.get((j, "HI"), 0)
        and inst.E_jm.get((j, "SU"), float("inf")) <= inst.E_jm.get((j, "HI"), 0)
        for j in inst.tasks
    )
    if su_dominates_hi:
        warnings.append(
            "SU dominates HI for ALL tasks (faster and less/equal energy). "
            "HI mode will never be selected — check beta_su."
        )

    # --- Time ratio diagnostics ---
    ci_hi_ratios = []
    su_hi_ratios = []
    for j in inst.tasks:
        t_hi = inst.t_jm.get((j, "HI"), 1)
        if t_hi > 0:
            ci_hi_ratios.append(inst.t_jm.get((j, "CI"), 0) / t_hi)
            su_hi_ratios.append(inst.t_jm.get((j, "SU"), 0) / t_hi)

    if ci_hi_ratios:
        stats["CI_HI_ratio_mean"] = round(sum(ci_hi_ratios) / len(ci_hi_ratios), 3)
        stats["CI_HI_ratio_range"] = (
            round(min(ci_hi_ratios), 3),
            round(max(ci_hi_ratios), 3),
        )
    if su_hi_ratios:
        stats["SU_HI_ratio_mean"] = round(sum(su_hi_ratios) / len(su_hi_ratios), 3)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "stats": stats,
    }
