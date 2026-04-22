"""
CALInstance — the canonical data structure for a Collaborative Assembly
Line Balancing instance, with built-in validation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from calbp.constants import ALL_MODE_NAMES, MODE_IDS


@dataclass
class CALInstance:
    """One complete CALBP instance ready for solving."""

    name: str
    tasks: list[int]                           # e.g. [1, 2, ..., n]
    stations: list[int]                        # e.g. [1, ..., K_max]
    precedence: list[tuple[int, int]]          # (i, j) means i → j
    t_jm: dict[tuple[int, str], float]         # (task, mode_name) → time
    E_jm: dict[tuple[int, str], float]         # (task, mode_name) → energy
    T: float                                   # cycle time
    R_e: float                                 # idle energy rate
    C_s: float                                 # station cost
    C_w: float                                 # worker cost
    C_c: float                                 # cobot cost

    # Generation metadata (optional, for traceability)
    base_instance: str = ""
    config_name: str = ""
    alpha_ci: float = 0.0
    beta_su: float = 0.0
    gamma_setup: float = 0.0
    sigma_si: float = 0.0
    seed: int = 0

    def n_tasks(self) -> int:
        return len(self.tasks)

    def n_stations(self) -> int:
        return len(self.stations)

    def validate(self) -> list[str]:
        """Run comprehensive validity checks. Returns list of issues (empty = OK)."""
        issues: list[str] = []

        # --- Completeness ---
        for j in self.tasks:
            for m in ALL_MODE_NAMES:
                if (j, m) not in self.t_jm:
                    issues.append(f"Missing t_jm[{j},{m}]")
                if (j, m) not in self.E_jm:
                    issues.append(f"Missing E_jm[{j},{m}]")

        # --- Non-negativity ---
        for (j, m), t in self.t_jm.items():
            if t < 0:
                issues.append(f"Negative time: t[{j},{m}] = {t}")
        for (j, m), e in self.E_jm.items():
            if e < 0:
                issues.append(f"Negative energy: E[{j},{m}] = {e}")

        # --- Structural consistency of times ---
        for j in self.tasks:
            t_hi = self.t_jm.get((j, "HI"), None)
            t_su = self.t_jm.get((j, "SU"), None)
            t_ci = self.t_jm.get((j, "CI"), None)

            if t_hi is not None and t_su is not None:
                if t_su > t_hi:
                    issues.append(
                        f"Task {j}: SU time ({t_su}) > HI time ({t_hi}) "
                        f"— supportive mode slower than human alone"
                    )

            if t_hi is not None and t_ci is not None:
                if t_ci < t_hi * 0.5:
                    issues.append(
                        f"Task {j}: CI time ({t_ci}) < 0.5 × HI time ({t_hi}) "
                        f"— cobot unrealistically faster"
                    )

        # --- Cycle time feasibility ---
        for j in self.tasks:
            for m in ALL_MODE_NAMES:
                t = self.t_jm.get((j, m), 0)
                if t > self.T:
                    issues.append(
                        f"Task {j}, mode {m}: time ({t}) exceeds cycle time ({self.T})"
                    )

        # --- Energy consistency ---
        for j in self.tasks:
            for m in ["HI", "SEH", "SIH"]:
                e = self.E_jm.get((j, m), 0)
                if e != 0:
                    issues.append(
                        f"Task {j}, mode {m}: energy ({e}) should be 0 "
                        f"for human-only execution"
                    )

        # --- Precedence graph sanity ---
        task_set = set(self.tasks)
        for (i, j) in self.precedence:
            if i not in task_set:
                issues.append(f"Precedence arc ({i},{j}): task {i} not in task set")
            if j not in task_set:
                issues.append(f"Precedence arc ({i},{j}): task {j} not in task set")
            if i == j:
                issues.append(f"Self-loop in precedence: ({i},{j})")

        # --- Parameters ---
        if self.T <= 0:
            issues.append(f"Cycle time T = {self.T} must be positive")
        if self.R_e < 0:
            issues.append(f"R_e = {self.R_e} must be non-negative")

        return issues

    def summary(self) -> dict:
        """Compute descriptive statistics for the instance."""
        import statistics

        stats = {
            "name": self.name,
            "n_tasks": self.n_tasks(),
            "n_stations_max": self.n_stations(),
            "n_arcs": len(self.precedence),
            "T": self.T,
            "R_e": self.R_e,
        }

        for m in ALL_MODE_NAMES:
            times = [self.t_jm[(j, m)] for j in self.tasks
                     if (j, m) in self.t_jm]
            energies = [self.E_jm[(j, m)] for j in self.tasks
                        if (j, m) in self.E_jm]
            if times:
                stats[f"t_{m}_mean"] = round(statistics.mean(times), 2)
                stats[f"t_{m}_min"] = min(times)
                stats[f"t_{m}_max"] = max(times)
            if energies:
                stats[f"E_{m}_mean"] = round(statistics.mean(energies), 2)

        # Lower bound on stations (HI-only)
        sum_hi = sum(self.t_jm.get((j, "HI"), 0) for j in self.tasks)
        stats["LB_stations_HI"] = max(1, -(-sum_hi // int(self.T)))  # ceil div

        return stats
