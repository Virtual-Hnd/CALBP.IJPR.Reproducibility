"""
MILP_Audrey.py — Audrey's compact reformulation of the bi-objective CALBP.

By default, this implementation uses a "competitive" tightened profile:
  - Compact Audrey core constraints
  - + C2a valid inequality: o[k] <= sum_j,m x[j,k,m]
  - + C4wy valid inequalities: w[k] <= o[k], y[k] <= o[k]

These valid inequalities keep the same Pareto front while reducing the number of
dominated epsilon iterations compared with the legacy compact model.

Optional:
  - C5bc cuts for SI timelines can be enabled (add_C5bc=True)
  - Legacy compact behavior is available by disabling all added VI

Collaboration modes (same encoding as MILP_V1):
  1=HI  2=CI  3=SEH  4=SEC  5=SU  6=SIH  7=SIC

Usage:
  python MILP_Audrey.py <instance_file>
"""

import pulp
from pulp import CPLEX_CMD
import re, os, sys, time, math, tempfile, shutil


# ═══════════════════════════════════════════════════════════════════════
# Data loading (reused from MILP_V1 — same instance format)
# ═══════════════════════════════════════════════════════════════════════

def load_data(file_path):
    data = {
        'J': [], 'K': [], 'M': [],
        't_jm': {}, 'E_jm': {}, 'P': [],
        'R_e': 0.0, 'T': 0.0,
        'C_s': 0.0, 'C_w': 0.0, 'C_c': 0.0
    }
    current_section = None
    with open(file_path, 'r') as f:
        for line in f:
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
                    data['t_jm'][(int(parts[0]), int(parts[1]))] = float(parts[2])
            elif current_section == 'E_jm':
                parts = line.split()
                if len(parts) >= 3:
                    data['E_jm'][(int(parts[0]), int(parts[1]))] = float(parts[2])
            elif current_section == 'P':
                parts = re.split(r'[, ]+', line)
                if len(parts) >= 2:
                    data['P'].append((int(parts[0]), int(parts[1])))
            elif current_section == 'Parameters':
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    if key in ('R_e', 'T', 'C_s', 'C_w', 'C_c'):
                        data[key] = float(value.strip())

    # basic verification
    assert len(data['M']) == 7, f"Expected 7 modes, got {len(data['M'])}"
    for j in data['J']:
        for m in data['M']:
            assert (j, m) in data['t_jm'], f"Missing t_jm[{j},{m}]"
            assert (j, m) in data['E_jm'], f"Missing E_jm[{j},{m}]"
    return data


# ═══════════════════════════════════════════════════════════════════════
# Audrey compact model
# ═══════════════════════════════════════════════════════════════════════

def build_model(data, cost_constraint=None,
                add_C2a=True, add_C4wy=True, add_C5bc=False):
    """
    Build Audrey MILP for bi-objective CALBP.

    Default profile is competitive:
      - add_C2a=True
      - add_C4wy=True
      - add_C5bc=False

    Set all to False to recover the legacy compact model.
    """

    J    = data['J']
    K    = data['K']
    M    = data['M']       # [1..7]
    t_jm = data['t_jm']
    E_jm = data['E_jm']
    P    = data['P']
    R_e  = data['R_e']
    T    = data['T']
    C_s  = data['C_s']
    C_w  = data['C_w']
    C_c  = data['C_c']

    model = pulp.LpProblem("CALBP_Audrey", pulp.LpMinimize)

    # ── Decision variables ────────────────────────────────────────────
    x = pulp.LpVariable.dicts("x",
            [(j, k, m) for j in J for k in K for m in M], cat='Binary')
    s = pulp.LpVariable.dicts("s",
            [(k, m) for k in K for m in M], cat='Binary')
    o = pulp.LpVariable.dicts("o", K, cat='Binary')
    w = pulp.LpVariable.dicts("w", K, cat='Binary')
    y = pulp.LpVariable.dicts("y", K, cat='Binary')
    l = pulp.LpVariable.dicts("l", K, lowBound=0, cat='Continuous')
    r = pulp.LpVariable.dicts("r", J, lowBound=0, upBound=T, cat='Continuous')

    pairs_SI = [(j, jp) for j in J for jp in J if j < jp]
    delta = pulp.LpVariable.dicts("delta", pairs_SI, cat='Binary')

    # ── Mode subsets ──────────────────────────────────────────────────
    M_H     = [1, 3, 5, 6]       # modes involving human
    M_C     = [2, 4, 5, 7]       # modes involving cobot
    M_SE    = [3, 4]              # sequential sub-modes
    M_SI    = [6, 7]              # simultaneous sub-modes
    M_OTHER = [1, 2, 5]          # HI, CI, SU
    M_NS    = [1, 2, 3, 4, 5]    # non-simultaneous (for C5a)

    Q = T + max(t_jm.values())    # Big-M

    # ── Objectives ────────────────────────────────────────────────────
    z_e = (pulp.lpSum(E_jm[(j, m)] * x[(j, k, m)]
                      for j in J for k in K for m in M)
           + R_e * pulp.lpSum(l[k] for k in K))

    z_c = pulp.lpSum(C_s * o[k] + C_w * w[k] + C_c * y[k] for k in K)

    model += z_e, "Minimize_Energy"

    # ══════════════════════════════════════════════════════════════════
    # Constraints — Audrey compact formulation
    # ══════════════════════════════════════════════════════════════════

    # C1: each task assigned exactly once
    for j in J:
        model += (pulp.lpSum(x[(j, k, m)] for k in K for m in M) == 1,
                  f"C1_{j}")

    # C3a: mode ⇒ station open
    for k in K:
        for m in M:
            model += s[(k, m)] <= o[k], f"C3a_{k}_{m}"

    # C3b: task assignment ⇒ mode active
    for j in J:
        for k in K:
            for m in M:
                model += x[(j, k, m)] <= s[(k, m)], f"C3b_{j}_{k}_{m}"

    # C4a: human modes ⇒ worker
    for j in J:
        for k in K:
            for m in M_H:
                model += x[(j, k, m)] <= w[k], f"C4a_{j}_{k}_{m}"

    # C4b: cobot modes ⇒ cobot
    for j in J:
        for k in K:
            for m in M_C:
                model += x[(j, k, m)] <= y[k], f"C4b_{j}_{k}_{m}"

    # C5a: cycle-time for non-simultaneous modes {HI, CI, SEH, SEC, SU}
    for k in K:
        model += (pulp.lpSum(t_jm[(j, m)] * x[(j, k, m)]
                             for j in J for m in M_NS) <= T * o[k],
                  f"C5a_{k}")
    # NOTE: No C5b/C5c — SI timelines governed by C7bis + C7ter

    # C6: precedence (station ordering)
    for (j, jp) in P:
        model += (pulp.lpSum(k * x[(j, k, m)] for k in K for m in M)
                  <= pulp.lpSum(k * x[(jp, k, m)] for k in K for m in M),
                  f"C6_{j}_{jp}")

    # C7: temporal precedence inside SI station
    for (j, jp) in P:
        for k in K:
            in_SI_j  = pulp.lpSum(x[(j,  k, m)] for m in M_SI)
            in_SI_jp = pulp.lpSum(x[(jp, k, m)] for m in M_SI)
            proc_j   = pulp.lpSum(t_jm[(j, m)] * x[(j, k, m)] for m in M_SI)
            model += (r[j] + proc_j
                      <= r[jp] + Q * (2 - in_SI_j - in_SI_jp),
                      f"C7_{j}_{jp}_{k}")

    # C7bis: non-overlap for SI tasks (generalised ∀i ∈ SI)
    for j in J:
        for jp in J:
            if j >= jp:
                continue
            pair = (j, jp)
            for k in K:
                for i in M_SI:                          # i ∈ {6=SIH, 7=SIC}
                    both = x[(j, k, i)] + x[(jp, k, i)]
                    model += (r[j]  + t_jm[(j,  i)] <= r[jp] + Q * (3 - both - delta[pair]),
                              f"C7bis_a_{i}_{j}_{jp}_{k}")
                    model += (r[jp] + t_jm[(jp, i)] <= r[j]  + Q * (2 - both + delta[pair]),
                              f"C7bis_b_{i}_{j}_{jp}_{k}")

    # C7ter: SI tasks finish before T (generalised ∀i ∈ SI)
    for j in J:
        for k in K:
            for i in M_SI:
                model += (r[j] + t_jm[(j, i)] <= T + Q * (1 - x[(j, k, i)]),
                          f"C7ter_{i}_{j}_{k}")

    # C8: cobot idle time
    for k in K:
        model += (l[k] == T * y[k]
                  - pulp.lpSum(t_jm[(j, m)] * x[(j, k, m)]
                               for j in J for m in M_C),
                  f"C8_{k}")

    # C9: sequential station opening (symmetry breaker)
    for idx in range(1, len(K)):
        model += o[K[idx]] <= o[K[idx - 1]], f"C9_{K[idx]}"

    # C11: one mode family per station
    for k in K:
        model += (pulp.lpSum(s[(k, m)] for m in M_OTHER)
                  + 0.5 * pulp.lpSum(s[(k, m)] for m in M_SE)
                  + 0.5 * pulp.lpSum(s[(k, m)] for m in M_SI)
                  <= 1, f"C11_{k}")

    # C10: SE/SI coupling (generalised)  s_{k,iH} = s_{k,iC}
    for k in K:
        model += s[(k, 3)] == s[(k, 4)], f"C10_SE_{k}"   # SEH ↔ SEC
        model += s[(k, 6)] == s[(k, 7)], f"C10_SI_{k}"   # SIH ↔ SIC

    # C12: if SE/SI mode active → at least one task assigned to each sub-mode
    for k in K:
        for i in M_SE + M_SI:                             # i ∈ {3,4,6,7}
            model += (pulp.lpSum(x[(j, k, i)] for j in J) >= s[(k, i)],
                      f"C12_{i}_{k}")

    # Optional valid inequalities to improve practical competitiveness
    if add_C2a:
        for k in K:
            model += (o[k] <= pulp.lpSum(x[(j, k, m)] for j in J for m in M),
                      f"VI_C2a_{k}")

    if add_C4wy:
        for k in K:
            model += w[k] <= o[k], f"VI_C4w_{k}"
            model += y[k] <= o[k], f"VI_C4y_{k}"

    if add_C5bc:
        for k in K:
            model += (pulp.lpSum(t_jm[(j, 6)] * x[(j, k, 6)] for j in J)
                      <= T * s[(k, 6)], f"VI_C5b_{k}")
            model += (pulp.lpSum(t_jm[(j, 7)] * x[(j, k, 7)] for j in J)
                      <= T * s[(k, 7)], f"VI_C5c_{k}")

    # ── ε-constraint on cost ──────────────────────────────────────────
    if cost_constraint is not None:
        model += z_c <= cost_constraint, "EpsCost"

    return model, x, s, o, w, y, l, r, z_e, z_c


def build_model_zero_energy(data):
    """HI-only model for E=0 extreme point (identical logic)."""
    J  = data['J']
    K  = data['K']
    T  = data['T']
    C_s, C_w = data['C_s'], data['C_w']
    t_jm = data['t_jm']
    P  = data['P']

    model = pulp.LpProblem("CALBP_Audrey_E0", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", [(j, k) for j in J for k in K], cat='Binary')
    o = pulp.LpVariable.dicts("o", K, cat='Binary')

    z_c = pulp.lpSum((C_s + C_w) * o[k] for k in K)
    model += z_c, "MinCost"

    for j in J:
        model += pulp.lpSum(x[(j, k)] for k in K) == 1, f"C1_{j}"
    for j in J:
        for k in K:
            model += x[(j, k)] <= o[k], f"C2_{j}_{k}"
    for k in K:
        model += (pulp.lpSum(t_jm[(j, 1)] * x[(j, k)] for j in J)
                  <= T * o[k], f"C5_{k}")
    for (j, jp) in P:
        model += (pulp.lpSum(k * x[(j, k)] for k in K)
                  <= pulp.lpSum(k * x[(jp, k)] for k in K), f"C6_{j}_{jp}")
    for idx in range(1, len(K)):
        model += o[K[idx]] <= o[K[idx - 1]], f"C9_{K[idx]}"

    return model, x, o, z_c


# ═══════════════════════════════════════════════════════════════════════
# Solver wrapper
# ═══════════════════════════════════════════════════════════════════════

def _find_cplex():
    env_path = os.environ.get("CPLEX_CMD")
    if env_path and os.path.isfile(env_path):
        return env_path

    env_bin = os.environ.get("CPLEX_BIN")
    if env_bin:
        candidate = os.path.join(env_bin, "cplex")
        if os.path.isfile(candidate):
            return candidate

    studio_dir = os.environ.get("CPLEX_STUDIO_DIR")
    paths = []
    if studio_dir:
        paths.extend([
            os.path.join(studio_dir, "cplex", "bin", "arm64_osx", "cplex"),
            os.path.join(studio_dir, "cplex", "bin", "x86-64_osx", "cplex"),
            os.path.join(studio_dir, "cplex", "bin", "x86-64_linux", "cplex"),
            os.path.join(studio_dir, "cplex", "bin", "x64_win64", "cplex.exe"),
        ])

    # Prefer known local installs before falling back to PATH.
    paths.extend([
        "/Users/admin/Applications/CPLEX_Studio2212/cplex/bin/arm64_osx/cplex",
        "/Applications/CPLEX_Studio2212/cplex/bin/arm64_osx/cplex",
        "/Applications/CPLEX_Studio2212/cplex/bin/x86-64_osx/cplex",
        "/Applications/CPLEX_Studio2211/cplex/bin/arm64_osx/cplex",
        "/Applications/CPLEX_Studio2211/cplex/bin/x86-64_osx/cplex",
        "/home/hind.bahir/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex",
        "/opt/ibm/ILOG/CPLEX_Studio2212/cplex/bin/x86-64_linux/cplex",
        "/opt/ibm/ILOG/CPLEX_Studio2211/cplex/bin/x86-64_linux/cplex",
        "C:/Program Files/IBM/ILOG/CPLEX_Studio2212/cplex/bin/x64_win64/cplex.exe",
        "C:/Program Files/IBM/ILOG/CPLEX_Studio2211/cplex/bin/x64_win64/cplex.exe",
    ])
    for p in paths:
        if os.path.isfile(p):
            return p
    if shutil.which("cplex"):
        return "cplex"
    return None


def _parse_cplex_log(log_path):
    lb = ub = gap_pct = n_nodes = None
    certified = False
    try:
        with open(log_path, 'r', errors='ignore') as f:
            lines = f.readlines()
        last = 0
        for i, ln in enumerate(lines):
            if 'Log started' in ln:
                last = i
        lines = lines[last:]
        for ln in reversed(lines):
            if ub is None and 'Integer optimal solution' in ln and 'Objective =' in ln:
                try: ub = float(ln.split('=')[1].strip().split()[0])
                except: pass
            if ub is None and 'Time limit exceeded' in ln and 'Objective =' in ln:
                try: ub = float(ln.split('Objective =')[1].split(',')[0].strip())
                except: pass
            if lb is None and 'Current MIP best bound =' in ln:
                try: lb = float(ln.split('Current MIP best bound =')[1].split('(')[0].replace(',','').strip())
                except: pass
            if gap_pct is None and '(gap =' in ln:
                try: gap_pct = float(ln.split('(gap =')[1].split('%')[0].strip())
                except: pass
            if lb is None and not certified and ln.strip().endswith('%'):
                parts = ln.split()
                if len(parts) >= 4:
                    try:
                        gc = float(parts[-1].replace('%',''))
                        bs = parts[-3] if '.' not in parts[-2] else parts[-2]
                        val = float(bs)
                        if 0 < val and 0 <= gc <= 100:
                            lb = val
                            if gap_pct is None: gap_pct = gc
                    except: pass
            if n_nodes is None and 'Nodes =' in ln:
                try: n_nodes = int(ln.split('Nodes =')[1].strip().split()[0])
                except: pass
            if 'Integer optimal' in ln:
                certified = True
    except: pass
    return lb, ub, gap_pct, n_nodes, certified


def solve_model(model, time_limit=3600):
    cplex_path = _find_cplex()
    tmp_dir = tempfile.mkdtemp(prefix="cplex_audrey_")
    fd, log_file = tempfile.mkstemp(suffix=".log", prefix="cplex_", dir=tmp_dir)
    os.close(fd)

    if cplex_path:
        solver = CPLEX_CMD(path=cplex_path, msg=1, timeLimit=time_limit,
                           options=[f"set logfile {log_file}",
                                    f"set workdir {tmp_dir}"])
    else:
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)

    orig = os.getcwd()
    os.chdir(tmp_dir)
    try:
        t0 = time.time()
        model.solve(solver)
        exec_time = time.time() - t0
    finally:
        os.chdir(orig)

    obj_val = pulp.value(model.objective)
    lb, ub, mip_gap, n_nodes, certified = _parse_cplex_log(log_file)

    feasible = obj_val is not None
    if feasible:
        if ub is None: ub = obj_val
        if certified:
            lb = ub; mip_gap = 0.0
        if lb is None and certified: lb = obj_val
        if mip_gap is None and ub is not None and lb is not None and abs(ub) > 1e-9:
            mip_gap = round((ub - lb) / abs(ub) * 100, 4)
    if mip_gap is not None and abs(mip_gap) < 1e-6:
        mip_gap = 0.0

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return feasible, certified, exec_time, lb, ub, mip_gap, n_nodes


# ═══════════════════════════════════════════════════════════════════════
# Solution extraction helpers
# ═══════════════════════════════════════════════════════════════════════

MODE_NAMES = {1: 'HI', 2: 'CI', 3: 'SEH', 4: 'SEC', 5: 'SU', 6: 'SIH', 7: 'SIC'}


def extract_solution(data, x, s, o, w, y, l, r, z_e, z_c):
    """Extract solution values into a dict."""
    J, K, M = data['J'], data['K'], data['M']
    M_C = [2, 4, 5, 7]
    T = data['T']

    total_energy = pulp.value(z_e)
    total_cost   = pulp.value(z_c)
    stations = sum((o[k].varValue or 0) > 0.5 for k in K)
    workers  = sum((w[k].varValue or 0) > 0.5 for k in K)
    cobots   = sum((y[k].varValue or 0) > 0.5 for k in K)

    # mode distribution
    mode_dist = {n: 0 for n in MODE_NAMES.values()}
    for j in J:
        for k in K:
            for m in M:
                if (x[(j, k, m)].varValue or 0) > 0.5:
                    mode_dist[MODE_NAMES[m]] += 1

    # energy breakdown
    e_tasks = sum(data['E_jm'][(j, m)] * (x[(j, k, m)].varValue or 0)
                  for j in J for k in K for m in M)
    e_idle  = data['R_e'] * sum((l[k].varValue or 0) for k in K)

    # cobot utilisation
    utils = []
    for k in K:
        if (y[k].varValue or 0) > 0.5:
            work = sum(data['t_jm'][(j, m)] * (x[(j, k, m)].varValue or 0)
                       for j in J for m in M_C)
            utils.append(min(work / T, 1.0))
    cobot_util = round(sum(utils) / len(utils), 4) if utils else None

    # assignments
    assignments = []
    for j in J:
        for k in K:
            for m in M:
                if (x[(j, k, m)].varValue or 0) > 0.5:
                    assignments.append({
                        'task': j, 'station': k,
                        'mode': MODE_NAMES[m], 'mode_id': m,
                        'time': data['t_jm'][(j, m)],
                        'energy': data['E_jm'][(j, m)],
                    })

    station_info = []
    for k in K:
        if (o[k].varValue or 0) > 0.5:
            station_info.append({
                'station': k,
                'worker': bool((w[k].varValue or 0) > 0.5),
                'cobot':  bool((y[k].varValue or 0) > 0.5),
                'idle_time': round(l[k].varValue or 0, 2),
            })

    return {
        'cost': total_cost, 'energy': total_energy,
        'stations': stations, 'workers': workers, 'cobots': cobots,
        'mode_distrib': mode_dist,
        'energy_tasks': e_tasks, 'energy_idle': e_idle,
        'cobot_util': cobot_util,
        'assignments': assignments,
        'station_info': station_info,
    }


def verify_solution(data, x, s, o, w, y, l, r):
    """Check constraint satisfaction. Returns (violations_dict, objectives_dict)."""
    J, K, M = data['J'], data['K'], data['M']
    t_jm, T = data['t_jm'], data['T']
    P = data['P']
    M_NS = [1, 2, 3, 4, 5]
    M_SI = [6, 7]

    violations = {}

    # C1: unique assignment
    for j in J:
        tot = sum((x[(j, k, m)].varValue or 0) for k in K for m in M)
        if abs(tot - 1) > 0.01:
            violations[f"C1_{j}"] = f"task {j}: {tot:.2f} assignments"

    # C5a: cycle time (non-SI)
    for k in K:
        if (o[k].varValue or 0) > 0.5:
            wl = sum(t_jm[(j, m)] * (x[(j, k, m)].varValue or 0)
                     for j in J for m in M_NS)
            if wl > T + 0.01:
                violations[f"C5a_{k}"] = f"workload {wl:.2f} > T={T}"

    # C6: station precedences
    for (j, jp) in P:
        sj  = sum(k * (x[(j,  k, m)].varValue or 0) for k in K for m in M)
        sjp = sum(k * (x[(jp, k, m)].varValue or 0) for k in K for m in M)
        if sj > sjp + 0.01:
            violations[f"C6_{j}_{jp}"] = f"station {sj:.1f} > {sjp:.1f}"

    # C7: SI temporal precedences
    for (j, jp) in P:
        for k in K:
            in_si_j  = sum((x[(j,  k, m)].varValue or 0) for m in M_SI)
            in_si_jp = sum((x[(jp, k, m)].varValue or 0) for m in M_SI)
            if in_si_j > 0.5 and in_si_jp > 0.5:
                proc = sum(t_jm[(j, m)] * (x[(j, k, m)].varValue or 0) for m in M_SI)
                rj  = r[j].varValue  or 0
                rjp = r[jp].varValue or 0
                if rj + proc > rjp + 0.01:
                    violations[f"C7_{j}_{jp}_{k}"] = f"r[{j}]+t > r[{jp}]"

    # objectives
    e_tasks = sum(data['E_jm'][(j, m)] * (x[(j, k, m)].varValue or 0)
                  for j in J for k in K for m in M)
    e_idle  = data['R_e'] * sum((l[k].varValue or 0) for k in K)
    cost    = sum(data['C_s'] * (o[k].varValue or 0)
                  + data['C_w'] * (w[k].varValue or 0)
                  + data['C_c'] * (y[k].varValue or 0) for k in K)

    return violations, {
        'energy_tasks': e_tasks,
        'energy_idle': e_idle,
        'total_energy': e_tasks + e_idle,
        'total_cost': cost,
    }


# ═══════════════════════════════════════════════════════════════════════
# ε-constraint driver
# ═══════════════════════════════════════════════════════════════════════

def solve_instance(instance_file, results_dir="results_audrey",
                   time_limit=3600, save_files=True,
                   add_C2a=True, add_C4wy=True, add_C5bc=False):
    """Run ε-constraint and return Pareto front list."""
    total_start = time.time()
    instance_name = os.path.splitext(os.path.basename(instance_file))[0]

    print(f"\n{'='*60}")
    print(f"  CALBP Audrey — {instance_name}")
    print(f"{'='*60}")

    data = load_data(instance_file)
    epsilon = 1
    C_s, C_w, C_c = data['C_s'], data['C_w'], data['C_c']

    vi_active = []
    if add_C2a:
        vi_active.append("C2a")
    if add_C4wy:
        vi_active.append("C4wy")
    if add_C5bc:
        vi_active.append("C5bc")
    vi_label = "+".join(vi_active) if vi_active else "none (legacy compact)"

    print(f"  Tasks={len(data['J'])}  Stations≤{len(data['K'])}  "
          f"Prec={len(data['P'])}  T={data['T']}  VI={vi_label}")

    # Step 1: E=0 extreme point (HI only)
    print(f"\n--- Step 1: E=0 point (HI only) ---")
    m0, x0, o0, zc0 = build_model_zero_energy(data)
    ok0, cert0, t0, lb0, ub0, gap0, nd0 = solve_model(m0, time_limit)

    pareto = []
    if ok0:
        cost0 = pulp.value(zc0)
        stations0 = sum((o0[k].varValue or 0) > 0.5 for k in data['K'])
        print(f"  Cost={cost0:.0f}  Stations={stations0}  "
              f"{'Certified' if cert0 else 'Non-certified'}  {t0:.1f}s")

        asgn0 = []
        for j in data['J']:
            for k in data['K']:
                if (x0[(j, k)].varValue or 0) > 0.5:
                    asgn0.append({'task': j, 'station': k, 'mode': 'HI',
                                  'mode_id': 1, 'time': data['t_jm'][(j, 1)],
                                  'energy': 0.0})

        pareto.append({
            'cost': cost0, 'energy': 0.0, 'stations': stations0,
            'workers': stations0, 'cobots': 0, 'valid': True,
            'certified': cert0, 'lb': lb0, 'ub': ub0, 'mip_gap': gap0,
            'n_nodes': nd0, 'cpu_point': t0,
            'energy_tasks': 0.0, 'energy_idle': 0.0, 'cobot_util': None,
            'mode_distrib': {'HI': len(data['J']), 'CI': 0, 'SEH': 0,
                             'SEC': 0, 'SU': 0, 'SIH': 0, 'SIC': 0},
            'assignments': asgn0,
        })
        cur_limit = int(cost0 - epsilon)
    else:
        print("  No E=0 solution")
        cur_limit = int(len(data['K']) * (C_s + C_w + C_c))

    # Step 2: ε-constraint
    print(f"\n--- Step 2: ε-constraint ---")
    idx = len(pareto)

    while cur_limit >= 0:
        print(f"\n  Iter {idx+1}: cost ≤ {cur_limit}")
        mdl, x, s, o, w, y, l, r, z_e, z_c = build_model(
            data, cur_limit,
            add_C2a=add_C2a, add_C4wy=add_C4wy, add_C5bc=add_C5bc
        )
        ok, cert, et, lb, ub, gap, nd = solve_model(mdl, time_limit)

        if not ok:
            print("    Infeasible — stop")
            break

        total_e = pulp.value(z_e)
        total_c = pulp.value(z_c)
        if total_e is None or total_c is None:
            print("    No incumbent — stop")
            break

        viols, obj = verify_solution(data, x, s, o, w, y, l, r)
        sol = extract_solution(data, x, s, o, w, y, l, r, z_e, z_c)
        sol.update({'valid': len(viols) == 0, 'certified': cert,
                    'lb': lb, 'ub': ub, 'mip_gap': gap, 'n_nodes': nd,
                    'cpu_point': et})

        cert_s = "Cert" if cert else "TL"
        print(f"    C={total_c:.1f} E={total_e:.1f} "
              f"S={sol['stations']} W={sol['workers']} Cob={sol['cobots']} "
              f"[{cert_s}] gap={gap}% {et:.1f}s "
              f"{'VALID' if not viols else 'VIOLATIONS: '+str(viols)}")

        # dominance check (with float tolerance)
        _tol = 0.01
        dominated = any(
            p['cost'] <= sol['cost'] + _tol and p['energy'] <= sol['energy'] + _tol
            and (p['cost'] < sol['cost'] - _tol or p['energy'] < sol['energy'] - _tol)
            for p in pareto)

        if not dominated:
            before = len(pareto)
            pareto = [p for p in pareto
                      if not (sol['cost'] <= p['cost'] + _tol
                              and sol['energy'] <= p['energy'] + _tol
                              and (sol['cost'] < p['cost'] - _tol
                                   or sol['energy'] < p['energy'] - _tol))]
            rm = before - len(pareto)
            if rm: print(f"    removed {rm} dominated point(s)")
            pareto.append(sol)
        else:
            print(f"    dominated — skip")

        idx += 1
        cur_limit = int(total_c - epsilon)

    # Summary
    print(f"\n{'='*60}")
    print(f"  Pareto front: {len(pareto)} points")
    print(f"{'='*60}")
    for i, p in enumerate(pareto):
        c = "Y" if p.get('certified') else "N"
        print(f"  {i+1}. C={p['cost']:.1f}  E={p['energy']:.1f}  "
              f"S={p['stations']}  W={p['workers']}  Cob={p['cobots']}  "
              f"cert={c}  gap={p.get('mip_gap')}%  "
              f"modes={p['mode_distrib']}")
    print(f"\n  Total time: {time.time()-total_start:.1f}s\n")

    return pareto


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Solve CALBP with Audrey MILP (competitive VI profile by default)."
    )
    parser.add_argument("instance_file", help="Path to instance file")
    parser.add_argument("--time-limit", type=int, default=3600,
                        help="Solver time limit per epsilon point (seconds)")
    parser.add_argument("--legacy-compact", action="store_true",
                        help="Disable added valid inequalities (C2a/C4wy/C5bc)")
    parser.add_argument("--add-c5bc", action="store_true",
                        help="Enable optional SI cycle-time cuts C5b/C5c")

    args = parser.parse_args()

    f = args.instance_file
    if not os.path.exists(f):
        d = os.path.dirname(os.path.abspath(__file__))
        f = os.path.join(d, args.instance_file)
    if not os.path.exists(f):
        print(f"File not found: {args.instance_file}")
        sys.exit(1)

    use_competitive = not args.legacy_compact
    solve_instance(
        f,
        time_limit=args.time_limit,
        add_C2a=use_competitive,
        add_C4wy=use_competitive,
        add_C5bc=args.add_c5bc and use_competitive
    )
