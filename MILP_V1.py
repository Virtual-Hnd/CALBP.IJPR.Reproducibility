"""
CALBP Bi-Objective with Human-Cobot Collaboration
Epsilon-constraint method with CPLEX

Collaboration modes:
  1. HI  - Human Independent
  2. CI  - Cobot Independent
  3. SEH - Sequential Human (human part)
  4. SEC - Sequential Cobot (cobot part)
  5. SU  - Supportive
  6. SIH - Simultaneous Human (human part)
  7. SIC - Simultaneous Cobot (cobot part)

Usage:
  python CALBP_BiObj_CPLEX.py <instance_file>
  python CALBP_BiObj_CPLEX.py converted_instances_small/instance_n=20_1.txt
"""

import pulp
from pulp import CPLEX_CMD
import re
import os
import sys
import time
import math
import matplotlib.pyplot as plt



# =============================================================================
# Data Loading
# =============================================================================

def verify_data(data):
    """Verify data integrity."""
    required_keys = ['J', 'K', 'M', 't_jm', 'E_jm', 'P', 'R_e', 'T', 'C_s', 'C_w', 'C_c']
    missing = [key for key in required_keys if key not in data or not data[key]]
    if missing:
        raise ValueError(f"Missing data: {missing}")
    
    if len(data['M']) != 7:
        raise ValueError(f"7 modes required, {len(data['M'])} found")
    
    for j in data['J']:
        for m in data['M']:
            if (j, m) not in data['t_jm']:
                raise ValueError(f"Missing processing time: task {j}, mode {m}")
            if (j, m) not in data['E_jm']:
                raise ValueError(f"Missing energy: task {j}, mode {m}")
    
    return True


def load_data(file_path):
    """Load data from text file."""
    data = {
        'J': [], 'K': [], 'M': [],
        't_jm': {}, 'E_jm': {}, 'P': [],
        'R_e': 0.0, 'T': 0.0,
        'C_s': 0.0, 'C_w': 0.0, 'C_c': 0.0
    }
    
    current_section = None
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                header = line.lstrip('#').strip().lower()
                if 'tasks' in header:
                    current_section = 'J'
                elif 'workstations' in header:
                    current_section = 'K'
                elif 'modes' in header:
                    current_section = 'M'
                elif 'processing times' in header:
                    current_section = 't_jm'
                elif 'energy consumption' in header:
                    current_section = 'E_jm'
                elif 'precedence relations' in header:
                    current_section = 'P'
                elif 'parameters' in header:
                    current_section = 'Parameters'
                continue
            
            if current_section == 'J':
                data['J'] = list(map(int, line.split()))
            elif current_section == 'K':
                data['K'] = list(map(int, line.split()))
            elif current_section == 'M':
                data['M'] = list(map(int, line.split()))
            elif current_section == 't_jm':
                parts = line.split()
                if len(parts) >= 3:
                    j, m, t = int(parts[0]), int(parts[1]), float(parts[2])
                    data['t_jm'][(j, m)] = t
            elif current_section == 'E_jm':
                parts = line.split()
                if len(parts) >= 3:
                    j, m, e = int(parts[0]), int(parts[1]), float(parts[2])
                    data['E_jm'][(j, m)] = e
            elif current_section == 'P':
                parts = re.split('[, ]+', line)
                if len(parts) >= 2:
                    data['P'].append((int(parts[0]), int(parts[1])))
            elif current_section == 'Parameters':
                if '=' in line:
                    key, value = line.split('=')
                    key = key.strip()
                    if key in ['R_e', 'T', 'C_s', 'C_w', 'C_c']:
                        data[key] = float(value.strip())
    
    verify_data(data)
    return data


# =============================================================================
# Model Building
# =============================================================================

def build_model(data, cost_constraint=None):
    """Build MILP model for bi-objective CALBP."""
    
    J = data['J']
    K = data['K']
    M = data['M']
    t_jm = data['t_jm']
    E_jm = data['E_jm']
    P = data['P']
    R_e = data['R_e']
    T = data['T']
    C_s = data['C_s']
    C_w = data['C_w']
    C_c = data['C_c']

    model = pulp.LpProblem("CALBP_BiObj", pulp.LpMinimize)

    # Decision variables
    x = pulp.LpVariable.dicts("x", [(j, k, m) for j in J for k in K for m in M], cat='Binary')
    s = pulp.LpVariable.dicts("s", [(k, m) for k in K for m in M], cat='Binary')
    o = pulp.LpVariable.dicts("o", K, cat='Binary')
    w = pulp.LpVariable.dicts("w", K, cat='Binary')
    y = pulp.LpVariable.dicts("y", K, cat='Binary')
    l = pulp.LpVariable.dicts("l", K, lowBound=0, cat='Continuous')
    r = pulp.LpVariable.dicts("r", J, lowBound=0, upBound=T, cat='Continuous')
    
    # Binary variable for relative ordering of SI tasks
    pairs_SI = [(j, j_prime) for j in J for j_prime in J if j < j_prime]
    delta = pulp.LpVariable.dicts("delta", pairs_SI, cat='Binary')

    # Mode sets
    M_H = [1, 3, 5, 6]      # Human modes
    M_C = [2, 4, 5, 7]      # Cobot modes
    M_SE = [3, 4]           # Sequential modes
    M_SI = [6, 7]           # Simultaneous modes
    M_OTHER = [1, 2, 5]     # Other modes (HI, CI, SU)
    M_NS = [1, 2, 3, 4, 5]  # Non-simultaneous modes

    Q = T + max(t_jm.values())  # Big-M constant

    # Objective functions
    z_e = (pulp.lpSum([E_jm[(j, m)] * x[(j, k, m)] for j in J for k in K for m in M]) + 
           R_e * pulp.lpSum([l[k] for k in K]))
    
    z_c = pulp.lpSum([C_s * o[k] + C_w * w[k] + C_c * y[k] for k in K])
    
    model += z_e, "Minimize_Energy"

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    
    # C1: Each task assigned exactly once
    for j in J:
        model += pulp.lpSum([x[(j, k, m)] for k in K for m in M]) == 1, f"C1_{j}"

    # C2: Station-task linkage
    for k in K:
        model += o[k] <= pulp.lpSum([x[(j, k, m)] for j in J for m in M]), f"C2a_{k}"
        for j in J:
            for m in M:
                model += x[(j, k, m)] <= o[k], f"C2b_{j}_{k}_{m}"

    # C3: Mode-station linkage
    for k in K:
        for m in M:
            model += s[(k, m)] <= o[k], f"C3a_{k}_{m}"
    for j in J:
        for k in K:
            for m in M:
                model += x[(j, k, m)] <= s[(k, m)], f"C3b_{j}_{k}_{m}"

    # C4: Resource assignment
    for k in K:
        # Worker and cobot can only exist in open stations
        model += w[k] <= o[k], f"C4_w_{k}" #added
        model += y[k] <= o[k], f"C4_y_{k}" #added
        for j in J:
            for m in M_H:
                model += x[(j, k, m)] <= w[k], f"C4a_{j}_{k}_{m}"
            for m in M_C:
                model += x[(j, k, m)] <= y[k], f"C4b_{j}_{k}_{m}"

    # C5: Cycle time constraints
    for k in K:
        # C5a: Non-simultaneous modes
        model += pulp.lpSum([t_jm[(j, m)] * x[(j, k, m)] for j in J for m in M_NS]) <= T * o[k], f"C5a_{k}"
        # C5b: SIH timeline
        model += pulp.lpSum([t_jm[(j, 6)] * x[(j, k, 6)] for j in J]) <= T * s[(k, 6)], f"C5b_{k}"
        # C5c: SIC timeline
        model += pulp.lpSum([t_jm[(j, 7)] * x[(j, k, 7)] for j in J]) <= T * s[(k, 7)], f"C5c_{k}"

    # C6: Precedence constraints (station order)
    for (j, j_prime) in P:
        model += (pulp.lpSum([k * x[(j, k, m)] for k in K for m in M]) <= 
                  pulp.lpSum([k * x[(j_prime, k, m)] for k in K for m in M]), f"C6_{j}_{j_prime}")

    # C7: Temporal precedence for SI modes
    for (j, j_prime) in P:
        for k in K:
            in_SI_j = pulp.lpSum([x[(j, k, m)] for m in M_SI])
            in_SI_jp = pulp.lpSum([x[(j_prime, k, m)] for m in M_SI])
            proc_j_SI = pulp.lpSum([t_jm[(j, m)] * x[(j, k, m)] for m in M_SI])
            model += r[j] + proc_j_SI <= r[j_prime] + Q * (2 - in_SI_j - in_SI_jp), f"C7_{j}_{j_prime}_{k}"

    # C7bis: Non-overlap for SI tasks on same agent
    for j in J:
        for j_prime in J:
            if j >= j_prime:
                continue
            pair = (j, j_prime)
            for k in K:
                # SIH (mode 6) - same human
                both_SIH = x[(j, k, 6)] + x[(j_prime, k, 6)]
                model += r[j] + t_jm[(j, 6)] <= r[j_prime] + Q * (3 - both_SIH - delta[pair]), f"C7bis_SIH_a_{j}_{j_prime}_{k}"
                model += r[j_prime] + t_jm[(j_prime, 6)] <= r[j] + Q * (2 - both_SIH + delta[pair]), f"C7bis_SIH_b_{j}_{j_prime}_{k}"
                
                # SIC (mode 7) - same cobot
                both_SIC = x[(j, k, 7)] + x[(j_prime, k, 7)]
                model += r[j] + t_jm[(j, 7)] <= r[j_prime] + Q * (3 - both_SIC - delta[pair]), f"C7bis_SIC_a_{j}_{j_prime}_{k}"
                model += r[j_prime] + t_jm[(j_prime, 7)] <= r[j] + Q * (2 - both_SIC + delta[pair]), f"C7bis_SIC_b_{j}_{j_prime}_{k}"

    # C7ter: SI tasks must finish before cycle time
    for j in J:
        for k in K:
            model += r[j] + t_jm[(j, 6)] <= T + Q * (1 - x[(j, k, 6)]), f"C7ter_SIH_{j}_{k}"
            model += r[j] + t_jm[(j, 7)] <= T + Q * (1 - x[(j, k, 7)]), f"C7ter_SIC_{j}_{k}"

    # C8: Idle time cobot
    for k in K:
        model += l[k] == T * y[k] - pulp.lpSum([t_jm[(j, m)] * x[(j, k, m)] for j in J for m in M_C]), f"C8_{k}"

    # C9: Sequential station opening
    for idx in range(1, len(K)):
        model += o[K[idx]] <= o[K[idx-1]], f"C9_{K[idx]}"

    # C10: SE/SI mode coupling
    for k in K:
        model += s[(k, 3)] == s[(k, 4)], f"C10a_{k}"
        model += s[(k, 6)] == s[(k, 7)], f"C10b_{k}"

    # C11: One mode type per station
    for k in K:
        model += (pulp.lpSum([s[(k, m)] for m in M_OTHER]) +
                  0.5 * pulp.lpSum([s[(k, m)] for m in M_SE]) +
                  0.5 * pulp.lpSum([s[(k, m)] for m in M_SI]) <= 1), f"C11_{k}"

    # C12: SE/SI mode coherence
    for k in K:
        model += pulp.lpSum([x[(j, k, 3)] for j in J]) >= s[(k, 3)], f"C12a_{k}"
        model += pulp.lpSum([x[(j, k, 4)] for j in J]) >= s[(k, 4)], f"C12b_{k}"
        model += pulp.lpSum([x[(j, k, 6)] for j in J]) >= s[(k, 6)], f"C12c_{k}"
        model += pulp.lpSum([x[(j, k, 7)] for j in J]) >= s[(k, 7)], f"C12d_{k}"

    # C13: Epsilon constraint
    if cost_constraint is not None:
        model += z_c <= cost_constraint, "C13_Cost"

    return model, x, s, o, w, y, l, r, z_e, z_c


def build_model_zero_energy(data):
    """Simplified model to find minimum cost with E=0 (HI mode only)."""
    
    J = data['J']
    K = data['K']
    t_jm = data['t_jm']
    P = data['P']
    T = data['T']
    C_s = data['C_s']
    C_w = data['C_w']

    model = pulp.LpProblem("CALBP_ZeroEnergy", pulp.LpMinimize)

    x = pulp.LpVariable.dicts("x", [(j, k) for j in J for k in K], cat='Binary')
    o = pulp.LpVariable.dicts("o", K, cat='Binary')

    z_c = pulp.lpSum([(C_s + C_w) * o[k] for k in K])
    model += z_c, "Minimize_Cost"

    for j in J:
        model += pulp.lpSum([x[(j, k)] for k in K]) == 1, f"C1_{j}"

    for j in J:
        for k in K:
            model += x[(j, k)] <= o[k], f"C2_{j}_{k}"

    for k in K:
        model += pulp.lpSum([t_jm[(j, 1)] * x[(j, k)] for j in J]) <= T * o[k], f"C5_{k}"

    for (j, j_prime) in P:
        model += (pulp.lpSum([k * x[(j, k)] for k in K]) <= 
                  pulp.lpSum([k * x[(j_prime, k)] for k in K]), f"C6_{j}_{j_prime}")

    for idx in range(1, len(K)):
        model += o[K[idx]] <= o[K[idx-1]], f"C9_{K[idx]}"

    return model, x, o, z_c


# =============================================================================
# Solving
# =============================================================================

def _parse_cplex_log(log_path):
    """Parse CPLEX log robustly."""

    lb, ub, gap_pct, n_nodes = None, None, None, None
    log_certified = False

    try:
        with open(log_path, 'r', errors='ignore') as f:
            lines = f.readlines()

        # Garde seulement le DERNIER run (après le dernier "Log started")
        last_run_start = 0
        for i, line in enumerate(lines):
            if 'Log started' in line:
                last_run_start = i
        lines = lines[last_run_start:]

        # Reverse scan = LAST values (important)
        for line in reversed(lines):

            # UB (best integer)
            if ub is None and 'MIP - Integer optimal solution' in line and 'Objective =' in line:
                try:
                    ub = float(line.split('=')[1].strip().split()[0])
                except:
                    pass
             # UB non-certifié (time limit)
            if ub is None and 'Time limit exceeded' in line and 'Objective =' in line:
                try:
                    ub = float(line.split('Objective =')[1].strip().split(',')[0].strip())
                except:
                    pass

            # Si le "Time limit exceeded" ne contient pas l'objectif, 
            # mais qu'on a la ligne qui liste Solution time, Iterations, etc.
            if ub is None and 'MIP - Time limit exceeded' in line and 'Objective =' in line:
                 try:
                    ub = float(line.split('Objective =')[1].strip().split(',')[0].strip())
                 except:
                    pass

            # LB depuis la ligne explicite de Time limit (Current MIP best bound)
            if lb is None and 'Current MIP best bound =' in line:
                try:
                    # Format: "Current MIP best bound = 1154.5536 (gap = 3.79%)" ou "... , Current MIP best bound = 1154.5536"
                    part = line.split('Current MIP best bound =')[1].split('(')[0]
                    # Retirer la virgule potentielle ou le texte de fin si le format varie
                    lb = float(part.replace(',', '').strip())
                except:
                    pass

            # Si le gap est explicitement donné sur cette même ligne (gap = 3.79%)
            if gap_pct is None and '(gap =' in line:
                try:
                    gap_str = line.split('(gap =')[1].split('%')[0].strip()
                    gap_pct = float(gap_str)
                except:
                    pass

            # BestBound depuis la table d'exploration.
            # CPLEX table a des lignes se terminant par un pourcentage (le gap).
            # En lisant la ligne par la droite, on peut esquiver les problèmes 
            # de colonnes manquantes (comme les entiers `*` qui font sauter "ItCnt").
            if lb is None and not log_certified and line.strip().endswith('%'):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        # Le dernier mot est le gap (ex: "3.79%")
                        gap_candidate = float(parts[-1].replace('%', ''))
                        
                        # On trouve le BestBound en remontant depuis la droite:
                        # Si `parts[-2]` n'a pas de '.', c'est probablement `ItCnt` (ex: 14380), 
                        # donc `BestBound` est encore avant (`parts[-3]`).
                        # Si `parts[-2]` a un '.', c'est `BestBound` (la colonne ItCnt est vide).
                        bound_str = parts[-3] if '.' not in parts[-2] else parts[-2]
                        val = float(bound_str)
                        
                        if 0 < val and 0 <= gap_candidate <= 100:
                            lb = val
                            # Garde le premier gap qu'on trouve (le plus bas dans le log)
                            if gap_pct is None:
                                gap_pct = gap_candidate
                    except:
                        pass

            # Nodes
            if n_nodes is None and 'Nodes =' in line:
                try:
                    n_nodes = int(line.split('Nodes =')[1].strip().split()[0])
                except:
                    pass

            # Certified
            if 'MIP - Integer optimal' in line:
                log_certified = True

        

    except:
        pass

    return lb, ub, gap_pct, n_nodes, log_certified


# =============================================================================
# Indicator helpers (pure reads — no logic change)
# =============================================================================

def compute_mode_distribution(data, x):
    """Count tasks assigned to each mode across the whole solution."""
    mode_names = {1:'HI', 2:'CI', 3:'SEH', 4:'SEC', 5:'SU', 6:'SIH', 7:'SIC'}
    counts = {name: 0 for name in mode_names.values()}
    for j in data['J']:
        for k in data['K']:
            for m in data['M']:
                if (x[(j, k, m)].varValue or 0) > 0.5:
                    counts[mode_names[m]] += 1
    return counts


def compute_cobot_utilization(data, x, y):
    """
    Average cobot utilisation across open cobot-stations.
    util_k = sum(t_jm * x_jkm for cobot modes) / T
    Returns mean utilisation in [0,1] or None if no cobot station.
    """
    M_C = [2, 4, 5, 7]
    T   = data['T']
    utils = []
    for k in data['K']:
        if (y[k].varValue or 0) > 0.5:
            work = sum(data['t_jm'][(j, m)] * (x[(j, k, m)].varValue or 0)
                       for j in data['J'] for m in M_C)
            utils.append(min(work / T, 1.0))
    return round(sum(utils) / len(utils), 4) if utils else None


# ── Quality indicators (Zitzler et al., 2003) ───────────────────────
from calbp.analysis.indicators import compute_all_indicators as _compute_all_indicators


def compute_global_indicators(pareto_points):
    """Compute instance-level quality indicators from the Pareto front."""
    if not pareto_points:
        return {}

    costs    = [p['cost']   for p in pareto_points]
    energies = [p['energy'] for p in pareto_points]
    gaps     = [p['mip_gap'] for p in pareto_points
                if isinstance(p.get('mip_gap'), float)]

    ind = _compute_all_indicators(costs, energies, delta=0.10)

    n_optimal = sum(1 for p in pareto_points
                    if p.get('certified', False))

    return {
        'PF_size'       : ind['PF_size'],
        'HV_abs'        : ind['HV_abs'],
        'HV_norm'       : ind['HV_norm'],
        'ref_cost'      : ind['ref_cost'],
        'ref_energy'    : ind['ref_energy'],
        'spacing'       : ind['spacing'],
        'spread_delta'  : ind['spread_delta'],
        'max_spread'    : ind['max_spread'],
        'cost_range'    : ind['cost_range'],
        'energy_range'  : ind['energy_range'],
        'gap_mean'      : round(sum(gaps) / len(gaps), 4) if gaps else None,
        'gap_max'       : round(max(gaps), 4)             if gaps else None,
        'n_optimal_pts' : n_optimal,
    }


def solve_model(model, time_limit=3600):
    """Solve model with CPLEX (or CBC fallback)."""

    cplex_paths = [
        "/home/hind.bahir/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex",
        "/Applications/CPLEX_Studio2211/cplex/bin/arm64_osx/cplex",
        "/Applications/CPLEX_Studio2211/cplex/bin/x86-64_osx/cplex",
        "/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex",
        "C:/Program Files/IBM/ILOG/CPLEX_Studio2211/cplex/bin/x64_win64/cplex.exe",
        "cplex"
    ]

    cplex_path = None
    for path in cplex_paths:
        if path == "cplex":
            import shutil
            if shutil.which("cplex") is not None:
                cplex_path = "cplex"
                break
        elif os.path.isfile(path):
            cplex_path = path
            break

    import tempfile
    _tmp_dir = tempfile.mkdtemp(prefix="cplex_work_")
    _log_fd, log_file = tempfile.mkstemp(suffix=".log", prefix="cplex_", dir=_tmp_dir)
    os.close(_log_fd)

    start_time = time.time()

    if cplex_path:
        solver = CPLEX_CMD(
            path=cplex_path,
            msg=1,
            timeLimit=time_limit,
            options=[f"set logfile {log_file}",
                     f"set workdir {_tmp_dir}"]
        )
    else:
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)

    # Solve in temp dir so CPLEX clone*.log files don't pollute the project
    _orig_cwd = os.getcwd()
    os.chdir(_tmp_dir)
    try:
        model.solve(solver)
    finally:
        os.chdir(_orig_cwd)
    exec_time = time.time() - start_time

    obj_val = pulp.value(model.objective)

    # -------------------------------
    # Parse log
    # -------------------------------
    lb, ub, mip_gap, n_nodes, log_certified = _parse_cplex_log(log_file)
    log_available = os.path.exists(log_file)

    # Clean up temp dir (log + clone*.log + any CPLEX scratch)
    import shutil
    try:
        shutil.rmtree(_tmp_dir, ignore_errors=True)
    except Exception:
        pass

    # -------------------------------
    # Certified (ONLY FROM CPLEX)
    # -------------------------------
    certified = log_certified

    # -------------------------------
    # Feasible
    # -------------------------------
    feasible = obj_val is not None

    # -------------------------------
    # Fallbacks (SAFE)
    # -------------------------------
    if obj_val is not None:

        if ub is None:
            ub = obj_val

        # Si l'optimalite est certifiée par CPLEX, par définition LB = UB et le gap est 0.
        if certified and ub is not None:
            lb = ub
            mip_gap = 0.0

        if lb is None and certified:
            lb = obj_val

        # seulement si log existait
        if mip_gap is None and log_available:
            if ub is not None and lb is not None and abs(ub) > 1e-9:
                mip_gap = round((ub - lb) / abs(ub) * 100, 4)

    # -------------------------------
    # Clean numerical noise
    # -------------------------------
    if mip_gap is not None and abs(mip_gap) < 1e-6:
        mip_gap = 0.0

    # -------------------------------
    # Clean log
    # -------------------------------
    try:
        if os.path.exists(log_file):
            os.remove(log_file)
    except:
        pass

    return feasible, certified, exec_time, lb, ub, mip_gap, n_nodes


def solve_zero_energy_model(data, time_limit=3600):
    """Solve E=0 model and return optimal cost."""
    model, x, o, z_c = build_model_zero_energy(data)
    feasible, certified, exec_time, lb, ub, mip_gap, n_nodes = solve_model(model, time_limit=time_limit)

    if not feasible:
        return None, None, None, False, None, None, None, None, None, None

    cost     = pulp.value(z_c)
    stations = sum(o[k].varValue or 0 for k in data['K'])

    return cost, stations, exec_time, certified, lb, ub, mip_gap, n_nodes, x, o


# =============================================================================
# Validation
# =============================================================================

def verify_solution(data, x, s, o, w, y, l, r):
    """Verify all solution constraints."""
    
    J, K, M = data['J'], data['K'], data['M']
    t_jm = data['t_jm']
    E_jm = data['E_jm']
    P = data['P']
    T = data['T']
    R_e = data['R_e']
    
    M_SI = [6, 7]
    M_NS = [1, 2, 3, 4, 5]
    
    violations = {}
    
    # C1: Unique assignment
    for j in J:
        total = sum((x[(j, k, m)].varValue or 0) for k in K for m in M)
        if abs(total - 1) > 0.01:
            violations[f"C1_{j}"] = f"Task {j}: {total} assignments"
    
    # C5: Cycle time
    for k in K:
        if (o[k].varValue or 0) > 0.5:
            time_non_si = sum(t_jm[(j, m)] * (x[(j, k, m)].varValue or 0) 
                             for j in J for m in M_NS)
            if time_non_si > T + 0.01:
                violations[f"C5_{k}"] = f"Station {k}: {time_non_si:.1f} > {T}"
    
    # C6: Precedences
    for (j, j_prime) in P:
        station_j = sum(k * (x[(j, k, m)].varValue or 0) for k in K for m in M)
        station_jp = sum(k * (x[(j_prime, k, m)].varValue or 0) for k in K for m in M)
        if station_j > station_jp + 0.01:
            violations[f"C6_{j}_{j_prime}"] = f"Precedence violated"
    
    # C7: SI precedences
    for (j, j_prime) in P:
        for k in K:
            in_si_j = sum((x[(j, k, m)].varValue or 0) for m in M_SI)
            in_si_jp = sum((x[(j_prime, k, m)].varValue or 0) for m in M_SI)
            if in_si_j > 0.5 and in_si_jp > 0.5:
                proc_j = sum(t_jm[(j, m)] * (x[(j, k, m)].varValue or 0) for m in M_SI)
                r_j = r[j].varValue or 0
                r_jp = r[j_prime].varValue or 0
                if r_j + proc_j > r_jp + 0.01:
                    violations[f"C7_{j}_{j_prime}_{k}"] = f"r[{j}]+t > r[{j_prime}]"
    
    # Compute objectives
    energy_tasks = sum(E_jm[(j, m)] * (x[(j, k, m)].varValue or 0) 
                       for j in J for k in K for m in M)
    energy_idle = R_e * sum((l[k].varValue or 0) for k in K)
    total_energy = energy_tasks + energy_idle
    
    total_cost = sum(data['C_s'] * (o[k].varValue or 0) + 
                     data['C_w'] * (w[k].varValue or 0) + 
                     data['C_c'] * (y[k].varValue or 0) for k in K)
    
    return violations, {
        'energy_tasks': energy_tasks,
        'energy_idle': energy_idle,
        'total_energy': total_energy,
        'total_cost': total_cost
    }


# =============================================================================
# Output
# =============================================================================

def save_pareto_points(instance_name, pareto_points, results_dir="results", gi=None):
    """Save Pareto points with all logged indicators."""
    os.makedirs(results_dir, exist_ok=True)

    if gi is None:
        gi = compute_global_indicators(pareto_points)
    file_path = os.path.join(results_dir, f"{instance_name}_pareto.txt")

    with open(file_path, 'w') as f:
        # Global indicators in header
        f.write(f"# Instance: {instance_name}\n")
        f.write(f"# PF_size={gi.get('PF_size','?')}  "
                f"HV_abs={gi.get('HV_abs','?')}  "
                f"HV_norm={gi.get('HV_norm','?')}  "
                f"ref=({gi.get('ref_cost','?')},{gi.get('ref_energy','?')})  "
                f"spacing={gi.get('spacing','?')}  "
                f"spread_delta={gi.get('spread_delta','?')}  "
                f"max_spread={gi.get('max_spread','?')}  "
                f"cost_range={gi.get('cost_range','?')}  "
                f"energy_range={gi.get('energy_range','?')}  "
                f"gap_mean={gi.get('gap_mean','?')}%  "
                f"gap_max={gi.get('gap_max','?')}%  "
                f"n_optimal_pts={gi.get('n_optimal_pts','?')}\n")
        f.write("# idx Cost Energy Stations Workers Cobots Certified "
                "LB UB MIP_gap% n_nodes cpu_s "
                "E_tasks E_idle cobot_util "
                "HI CI SEH SEC SU SIH SIC\n")

        def _f(v, fmt=".2f"):
            return format(v, fmt) if isinstance(v, (int, float)) and v is not None else "N/A"

        for i, p in enumerate(pareto_points, start=1):
            modes = p.get('mode_distrib', {})
            cert  = "Yes" if p.get('certified', False) else "No"
            f.write(
                f"{i} {p['cost']:.1f} {p['energy']:.1f} "
                f"{int(p['stations'])} {int(p['workers'])} {int(p['cobots'])} {cert} "
                f"{_f(p.get('lb'))} {_f(p.get('ub'))} {_f(p.get('mip_gap'))} "
                f"{p.get('n_nodes', 'N/A')} {_f(p.get('cpu_point'), '.2f')} "
                f"{_f(p.get('energy_tasks'), '.2f')} {_f(p.get('energy_idle'), '.2f')} "
                f"{_f(p.get('cobot_util'), '.4f')} "
                f"{modes.get('HI',0)} {modes.get('CI',0)} {modes.get('SEH',0)} "
                f"{modes.get('SEC',0)} {modes.get('SU',0)} "
                f"{modes.get('SIH',0)} {modes.get('SIC',0)}\n"
            )

    return file_path


def save_solution_detail(instance_name, point_idx, data, x, o, w, y, l, r,
                         total_cost, total_energy, exec_time, cost_limit, certified,
                         lb, ub, mip_gap, n_nodes,
                         energy_tasks, energy_idle, cobot_util, mode_distrib,
                         results_dir="results"):
    """Save solution details to file."""
    os.makedirs(results_dir, exist_ok=True)

    J, K, M = data['J'], data['K'], data['M']
    mode_names = {1: 'HI', 2: 'CI', 3: 'SEH', 4: 'SEC', 5: 'SU', 6: 'SIH', 7: 'SIC'}
    M_SI = [6, 7]

    def _f(v, fmt=".2f"):
        return format(v, fmt) if isinstance(v, (int, float)) and v is not None else "N/A"

    file_path = os.path.join(results_dir, f"{instance_name}_point_{point_idx}.txt")

    with open(file_path, 'w') as f:
        f.write(f"Instance: {instance_name}\n")
        f.write(f"Point Index: {point_idx}\n")
        f.write(f"Cost limit: {cost_limit}\n")
        f.write(f"Total cost: {total_cost:.1f}\n")
        f.write(f"Total energy: {total_energy:.1f}\n")
        f.write(f"Execution time: {exec_time:.2f}s\n")
        f.write(f"Certified optimal: {'Yes' if certified else 'No (time limit)'}\n")
        f.write(f"LB: {_f(lb)}  UB: {_f(ub)}  MIP gap: {_f(mip_gap)}%\n")
        f.write(f"B&B nodes: {n_nodes if n_nodes is not None else 'N/A'}\n")
        f.write(f"Energy tasks: {_f(energy_tasks)}  Energy idle: {_f(energy_idle)}\n")
        f.write(f"Cobot utilisation: {_f(cobot_util, '.4f')}\n")
        f.write(f"Mode distribution: {mode_distrib}\n")
        f.write(f"Workers: {sum(w[k].varValue or 0 for k in K):.0f}\n")
        f.write(f"Cobots: {sum(y[k].varValue or 0 for k in K):.0f}\n")
        f.write("\n--- Assignments ---\n")

        for k in K:
            if o[k].varValue and o[k].varValue > 0.5:
                f.write(f"\nStation {k}:\n")
                for j in J:
                    for m in M:
                        if x[(j, k, m)].varValue and x[(j, k, m)].varValue > 0.5:
                            mode_name = mode_names.get(m, f'M{m}')
                            if m in M_SI:
                                r_val = r[j].varValue or 0
                                f.write(f"  Task {j} -> {mode_name} (r={r_val:.1f})\n")
                            else:
                                f.write(f"  Task {j} -> {mode_name}\n")

    return file_path

def save_pareto_figure(instance_name, pareto_points, results_dir="results"):
    os.makedirs(results_dir, exist_ok=True)

    certified_pts   = [p for p in pareto_points if p.get('certified', False)]
    uncertified_pts = [p for p in pareto_points if not p.get('certified', False)]

    plt.figure(figsize=(8, 6))

    # Plot certified points
    if certified_pts:
        costs_c  = [p['cost'] for p in certified_pts]
        energy_c = [p['energy'] for p in certified_pts]
        plt.scatter(costs_c, energy_c, color='#0072B2', s=80, zorder=5, label='Certified optimal')

    # Plot non-certified points
    if uncertified_pts:
        costs_u  = [p['cost'] for p in uncertified_pts]
        energy_u = [p['energy'] for p in uncertified_pts]
        plt.scatter(costs_u, energy_u, color='#E69F00', s=80, marker='D',
                    zorder=5, label='Non-certified (time limit)')

    # Annotations
    for i, p in enumerate(pareto_points):
        plt.annotate(f"P{i}", (p['cost'], p['energy']),
                     textcoords="offset points", xytext=(-5, 5),
                     ha='right', fontsize=9)

    plt.xlabel("Total Cost", fontsize=12)
    plt.ylabel("Total Energy", fontsize=12)
    plt.title(f"Pareto Front – {instance_name}", fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(alpha=0.3)
    plt.tight_layout()

    file_path = os.path.join(results_dir, f"{instance_name}_pareto.png")
    plt.savefig(file_path, dpi=300)
    plt.close()
    print(f"Pareto figure saved: {file_path}")



# =============================================================================
# Main
# =============================================================================

def solve_instance(instance_file, results_dir="pareto_00", time_limit=3600, save_files=True):
    """Solve a CALBP instance and return Pareto front.
    
    When save_files=False, skip writing _pareto.txt, _pareto.png and
    _point_*.txt (useful when the caller handles output itself).
    """
    total_start = time.time()
    
    instance_name = os.path.splitext(os.path.basename(instance_file))[0]
    
    print(f"\n{'='*60}")
    print(f"  CALBP Bi-Objective - {instance_name}")
    print(f"{'='*60}")
    
    data = load_data(instance_file)
    
    epsilon = 1
    C_s, C_w, C_c = data['C_s'], data['C_w'], data['C_c']
    
    print(f"\nParameters:")
    print(f"  Tasks: {len(data['J'])}")
    print(f"  Max stations: {len(data['K'])}")
    print(f"  Precedences: {len(data['P'])}")
    print(f"  Cycle time: {data['T']}")
    print(f"  Costs: C_s={C_s}, C_w={C_w}, C_c={C_c}")
    
    # Step 1: Find E=0 point (HI mode only)
    print(f"\n{'-'*60}")
    print("Step 1: Finding E=0 point (HI mode only)")
    print(f"{'-'*60}")
    
    cost_E0, stations_E0, time_E0, cert_E0, lb_E0, ub_E0, gap_E0, nodes_E0, x_e0, o_e0 = solve_zero_energy_model(data, time_limit=time_limit)

    pareto_points = []

    if cost_E0 is not None:
        cert_str = "Certified" if cert_E0 else "Non-certified"
        print(f"  Point found: Cost={cost_E0:.0f}, Stations={int(stations_E0)}, "
              f"Time={time_E0:.2f}s [{cert_str}]")

        # Extract E=0 assignments (all tasks in HI mode)
        e0_assignments = []
        for j in data['J']:
            for k in data['K']:
                if (x_e0[(j, k)].varValue or 0) > 0.5:
                    e0_assignments.append({
                        "task": j, "station": k,
                        "mode": "HI", "mode_id": 1,
                        "time": data['t_jm'][(j, 1)],
                        "energy": 0.0,
                    })
        e0_station_info = []
        for k in data['K']:
            if (o_e0[k].varValue or 0) > 0.5:
                e0_station_info.append({
                    "station": k, "worker": True, "cobot": False, "idle_time": 0.0,
                })

        pareto_points.append({
            'cost': cost_E0, 'energy': 0.0, 'stations': stations_E0,
            'workers': stations_E0, 'cobots': 0, 'valid': True, 'certified': cert_E0,
            'lb': lb_E0, 'ub': ub_E0, 'mip_gap': gap_E0, 'n_nodes': nodes_E0,
            'cpu_point': time_E0,
            'energy_tasks': 0.0, 'energy_idle': 0.0, 'cobot_util': None,
            'mode_distrib': {'HI': len(data['J']), 'CI':0,'SEH':0,'SEC':0,'SU':0,'SIH':0,'SIC':0},
            'assignments': e0_assignments,
            'station_info': e0_station_info,
        })
        current_cost_limit = int(cost_E0 - epsilon)
    else:
        print("  No E=0 solution found")
        current_cost_limit = int(len(data['K']) * (C_s + C_w + C_c))
    
    # Step 2: Epsilon-constraint method
    print(f"\n{'-'*60}")
    print("Step 2: Epsilon-constraint method")
    print(f"{'-'*60}")
    
    point_index = len(pareto_points)
    
    while current_cost_limit >= 0:
        print(f"\n  Iteration {point_index + 1}: Cost <= {current_cost_limit}")

        model, x, s, o, w, y, l, r, z_e, z_c = build_model(data, current_cost_limit)
        feasible, certified, exec_time, lb, ub, mip_gap, n_nodes = solve_model(model, time_limit=time_limit)

        if not feasible:
            print("    No solution - stopping")
            break

        total_energy = pulp.value(z_e)
        total_cost   = pulp.value(z_c)

        if total_energy is None or total_cost is None:
            print("    No incumbent solution found within time limit - stopping")
            break

        violations, obj_detail = verify_solution(data, x, s, o, w, y, l, r)

        stations = sum(o[k].varValue or 0 for k in data['K'])
        workers  = sum(w[k].varValue or 0 for k in data['K'])
        cobots   = sum(y[k].varValue or 0 for k in data['K'])

        # Per-point indicators
        mode_dist    = compute_mode_distribution(data, x)
        cobot_util   = compute_cobot_utilization(data, x, y)
        energy_tasks = obj_detail['energy_tasks']
        energy_idle  = obj_detail['energy_idle']

        # Extract decision variable assignments
        _mode_names = {1:'HI', 2:'CI', 3:'SEH', 4:'SEC', 5:'SU', 6:'SIH', 7:'SIC'}
        point_assignments = []
        for j in data['J']:
            for k in data['K']:
                for m in data['M']:
                    if (x[(j, k, m)].varValue or 0) > 0.5:
                        point_assignments.append({
                            "task": j, "station": k,
                            "mode": _mode_names[m], "mode_id": m,
                            "time": data['t_jm'][(j, m)],
                            "energy": data['E_jm'][(j, m)],
                        })
        point_station_info = []
        for k in data['K']:
            if (o[k].varValue or 0) > 0.5:
                point_station_info.append({
                    "station": k,
                    "worker": bool((w[k].varValue or 0) > 0.5),
                    "cobot": bool((y[k].varValue or 0) > 0.5),
                    "idle_time": round(l[k].varValue or 0, 2),
                })

        def _f(v, fmt=".2f"):
            return format(v, fmt) if isinstance(v, (int, float)) and v is not None else "N/A"

        cert_str = "Certified" if certified else "Non-certified (time limit)"
        print(f"    Cost={total_cost:.1f}, Energy={total_energy:.1f}, "
              f"Stations={int(stations)}, W={int(workers)}, C={int(cobots)}, "
              f"Time={exec_time:.2f}s, Valid={'Yes' if not violations else 'No'} | "
              f"[{cert_str}] | "
              f"LB={_f(lb)}, UB={_f(ub)}, Gap={_f(mip_gap)}% | "
              f"Nodes={n_nodes} | "
              f"E_tasks={_f(energy_tasks)}, E_idle={_f(energy_idle)}, "
              f"Cobot_util={_f(cobot_util, '.4f')} | "
              f"Modes={mode_dist}")

        new_point = {
            'cost': total_cost, 'energy': total_energy,
            'stations': stations, 'workers': workers, 'cobots': cobots,
            'valid': len(violations) == 0, 'certified': certified,
            'lb': lb, 'ub': ub, 'mip_gap': mip_gap, 'n_nodes': n_nodes,
            'cpu_point': exec_time,
            'energy_tasks': energy_tasks, 'energy_idle': energy_idle,
            'cobot_util': cobot_util, 'mode_distrib': mode_dist,
            'assignments': point_assignments,
            'station_info': point_station_info,
        }

        # Check if new point is dominated by any existing point
        dominated = any(
            p['cost'] <= new_point['cost'] and p['energy'] <= new_point['energy']
            and (p['cost'] < new_point['cost'] or p['energy'] < new_point['energy'])
            for p in pareto_points
        )

        if dominated:
            print(f"    WARNING: Point dominated by existing Pareto point — skipping")
        else:
            # Remove existing points dominated by the new point
            before = len(pareto_points)
            pareto_points = [
                p for p in pareto_points
                if not (
                    new_point['cost'] <= p['cost'] and new_point['energy'] <= p['energy']
                    and (new_point['cost'] < p['cost'] or new_point['energy'] < p['energy'])
                )
            ]
            removed = before - len(pareto_points)
            if removed > 0:
                print(f"    INFO: {removed} existing point(s) removed (dominated by new point)")

            if save_files:
                save_solution_detail(
                    instance_name, point_index, data, x, o, w, y, l, r,
                    total_cost, total_energy, exec_time,
                    current_cost_limit + epsilon, certified,
                    lb, ub, mip_gap, n_nodes,
                    energy_tasks, energy_idle, cobot_util, mode_dist,
                    results_dir
                )
            pareto_points.append(new_point)

        point_index += 1
        current_cost_limit = int(total_cost - epsilon)
    
    # Summary
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")

    def _f(v, fmt=".2f"):
        return format(v, fmt) if isinstance(v, (int, float)) and v is not None else "N/A"

    print(f"\nPareto Front ({len(pareto_points)} points):")
    print(f"{'#':<4} {'Cost':<8} {'Energy':<10} {'Stn':<5} {'W':<4} {'C':<4} "
          f"{'Cert':<6} {'LB':<8} {'UB':<8} {'Gap%':<7} {'Nodes':<8} {'CPU(s)':<8} "
          f"{'E_tasks':<9} {'E_idle':<8} {'CobUtil':<8}")
    print("-" * 110)
    for i, p in enumerate(pareto_points):
        cert = "Yes" if p.get('certified', False) else "No"
        print(f"{i+1:<4} {p['cost']:<8.1f} {p['energy']:<10.1f} "
              f"{int(p['stations']):<5} {int(p['workers']):<4} {int(p['cobots']):<4} "
              f"{cert:<6} {_f(p.get('lb')):<8} {_f(p.get('ub')):<8} "
              f"{_f(p.get('mip_gap')):<7} {str(p.get('n_nodes','N/A')):<8} "
              f"{_f(p.get('cpu_point')):<8} "
              f"{_f(p.get('energy_tasks')):<9} {_f(p.get('energy_idle')):<8} "
              f"{_f(p.get('cobot_util'),'.4f'):<8}")

    # Global indicators (computed once, used for both print and file)
    gi = compute_global_indicators(pareto_points)
    print(f"\nGlobal indicators:")
    print(f"  PF size        = {gi.get('PF_size')}")
    print(f"  HV (abs)       = {gi.get('HV_abs')}")
    print(f"  HV (norm)      = {gi.get('HV_norm')}")
    print(f"  Ref point      = ({gi.get('ref_cost')}, {gi.get('ref_energy')})")
    print(f"  Spacing        = {gi.get('spacing')}")
    print(f"  Spread Δ       = {gi.get('spread_delta')}")
    print(f"  Max spread     = {gi.get('max_spread')}")
    print(f"  Cost range     = {gi.get('cost_range')}")
    print(f"  Energy range   = {gi.get('energy_range')}")
    print(f"  Gap mean/max   = {gi.get('gap_mean')}% / {gi.get('gap_max')}%")
    print(f"  Optimal pts    = {gi.get('n_optimal_pts')} / {gi.get('PF_size')}")

    # Save Pareto points
    if save_files:
        output_file = save_pareto_points(instance_name, pareto_points, results_dir, gi)
        print(f"\nResults saved: {output_file}")
    
    total_time = time.time() - total_start
    print(f"Total time: {total_time:.2f}s\n")
    
    # Save Pareto figure
    if save_files:
        save_pareto_figure(instance_name, pareto_points, results_dir)

    return pareto_points


def main():
    if len(sys.argv) < 2:
        print("Usage: python CALBP_BiObj_CPLEX.py <instance_file>")
        print("Example: python CALBP_BiObj_CPLEX.py converted_instances_small/instance_n=20_1.txt")
        sys.exit(1)
    
    instance_file = sys.argv[1]
    
    if not os.path.exists(instance_file):
        # Try relative to script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        instance_file = os.path.join(script_dir, sys.argv[1])
    
    if not os.path.exists(instance_file):
        print(f"Error: Instance file not found: {sys.argv[1]}")
        sys.exit(1)
    
    solve_instance(instance_file)


if __name__ == "__main__":
    main()