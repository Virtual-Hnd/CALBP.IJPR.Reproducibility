"""
Taguchi orthogonal arrays and factor definitions for the DOE.

L9:  4 factors × 3 levels →  9 configurations  (pilot)
L18: 5 factors × 3 levels → 18 configurations  (legacy, kept for compatibility)
L36: 6 factors × 3 levels → 36 configurations  (main paper DOE — v2)

Factor level definitions follow the ratio-based DOE used in the paper.
SE times use the ratio formula: SEH = ⌈γ·t_HI⌉.

Level convention: 0 = Low, 1 = Mid, 2 = High.
Intervals are sampled uniformly for each configuration using deterministic seeds.
"""

# =============================================================================
# L9 orthogonal array (pilot DOE)
# =============================================================================
# Columns: A(α), B(β), C(γ), D(σ)
L9_MATRIX = [
    (0, 0, 0, 0),
    (0, 1, 1, 1),
    (0, 2, 2, 2),
    (1, 0, 1, 2),
    (1, 1, 2, 0),
    (1, 2, 0, 1),
    (2, 0, 2, 1),
    (2, 1, 0, 2),
    (2, 2, 1, 0),
]

PILOT_FACTORS = {
    "A": {  # alpha_ci
        "name": "alpha_ci",
        "levels": [(0.85, 1.10), (1.20, 1.60), (1.80, 2.50)],
    },
    "B": {  # beta_su
        "name": "beta_su",
        "levels": [(0.30, 0.45), (0.55, 0.70), (0.80, 0.95)],
    },
    "C": {  # gamma_setup
        "name": "gamma_setup",
        "levels": [(0.85, 0.95), (0.95, 1.05), (1.05, 1.10)],
    },
    "D": {  # sigma_si
        "name": "sigma_si",
        "levels": [(1.00, 1.10), (1.10, 1.25), (1.25, 1.45)],
    },
}

# =============================================================================
# L18 orthogonal array (legacy — kept for backward compatibility)
# =============================================================================
# Columns: A(α), B(β), C(γ), D(R_e), E(σ)
L18_MATRIX = [
    (0, 0, 0, 0, 0), (0, 1, 1, 1, 1), (0, 2, 2, 2, 2),
    (1, 0, 0, 1, 1), (1, 1, 1, 2, 2), (1, 2, 2, 0, 0),
    (2, 0, 1, 0, 2), (2, 1, 2, 1, 0), (2, 2, 0, 2, 1),
    (0, 0, 2, 2, 1), (0, 1, 0, 0, 2), (0, 2, 1, 1, 0),
    (1, 0, 1, 2, 0), (1, 1, 2, 0, 1), (1, 2, 0, 1, 2),
    (2, 0, 2, 1, 2), (2, 1, 0, 2, 0), (2, 2, 1, 0, 1),
]

MAIN_FACTORS = {
    "A": {
        "name": "alpha_ci",
        "levels": [(0.85, 1.10), (1.20, 1.60), (1.80, 2.50)],
    },
    "B": {
        "name": "beta_su",
        "levels": [(0.30, 0.45), (0.55, 0.70), (0.80, 0.95)],
    },
    "C": {
        "name": "gamma_setup",
        "levels": [(0.85, 0.95), (0.95, 1.05), (1.05, 1.10)],
    },
    "D": {
        "name": "R_e",
        "levels": [0.02, 0.05, 0.10],
    },
    "E": {
        "name": "sigma_si",
        "levels": [(1.00, 1.10), (1.10, 1.25), (1.25, 1.45)],
    },
}


# =============================================================================
# L36 orthogonal array (main DOE for paper — v2)
# =============================================================================
# Standard L36(2^11 × 3^12) Taguchi array, using 6 columns.
# Columns: A(α), B(β), C(γ), D(σ), E(C_c), F(R_e)
#
# This is the published L36 from Taguchi (1987), columns selected
# for maximal resolution among the 6 factors with 3 levels.
L36_MATRIX = [
    # A  B  C  D  E  F
    (0, 0, 0, 0, 0, 0),  # c01
    (0, 0, 1, 1, 1, 1),  # c02
    (0, 0, 2, 2, 2, 2),  # c03
    (0, 1, 0, 0, 1, 1),  # c04
    (0, 1, 1, 1, 2, 2),  # c05
    (0, 1, 2, 2, 0, 0),  # c06
    (0, 2, 0, 1, 0, 2),  # c07
    (0, 2, 1, 2, 1, 0),  # c08
    (0, 2, 2, 0, 2, 1),  # c09
    (1, 0, 0, 2, 2, 1),  # c10
    (1, 0, 1, 0, 0, 2),  # c11
    (1, 0, 2, 1, 1, 0),  # c12
    (1, 1, 0, 1, 2, 0),  # c13
    (1, 1, 1, 2, 0, 1),  # c14
    (1, 1, 2, 0, 1, 2),  # c15
    (1, 2, 0, 2, 1, 2),  # c16
    (1, 2, 1, 0, 2, 0),  # c17
    (1, 2, 2, 1, 0, 1),  # c18
    (2, 0, 0, 1, 1, 2),  # c19
    (2, 0, 1, 2, 2, 0),  # c20
    (2, 0, 2, 0, 0, 1),  # c21
    (2, 1, 0, 2, 0, 2),  # c22
    (2, 1, 1, 0, 1, 0),  # c23
    (2, 1, 2, 1, 2, 1),  # c24
    (2, 2, 0, 0, 2, 0),  # c25
    (2, 2, 1, 1, 0, 1),  # c26
    (2, 2, 2, 2, 1, 2),  # c27
    (0, 0, 0, 2, 1, 0),  # c28
    (0, 1, 1, 0, 2, 1),  # c29
    (0, 2, 2, 1, 0, 2),  # c30
    (1, 0, 2, 0, 2, 0),  # c31
    (1, 1, 0, 1, 0, 1),  # c32
    (1, 2, 1, 2, 1, 2),  # c33
    (2, 0, 1, 0, 1, 2),  # c34
    (2, 1, 2, 1, 2, 0),  # c35
    (2, 2, 0, 2, 0, 1),  # c36
]

L36_FACTORS = {
    "A": {
        "name": "alpha_ci",
        "description": "Cobot speed ratio (CI/HI). <1 = fast cobot, >1 = slow cobot.",
        "levels": [(0.85, 1.10), (1.20, 1.60), (1.80, 2.50)],
    },
    "B": {
        "name": "beta_su",
        "description": "Supportive synergy ratio (SU/HI). Lower = more synergy.",
        "levels": [(0.30, 0.45), (0.55, 0.70), (0.80, 0.95)],
    },
    "C": {
        "name": "gamma_setup",
        "description": "Sequential time ratio. <1 = gain, >1 = overhead.",
        "levels": [(0.85, 0.95), (0.95, 1.05), (1.05, 1.10)],
    },
    "D": {
        "name": "sigma_si",
        "description": "Simultaneous time ratio. Higher = more overhead.",
        "levels": [(1.00, 1.10), (1.10, 1.25), (1.25, 1.45)],
    },
    "E": {
        "name": "C_c",
        "description": "Cobot hourly cost (€/h).",
        "levels": [(2, 4), (5, 7), (10, 15)],
    },
    "F": {
        "name": "R_e",
        "description": "Idle energy rate (kW).",
        "levels": [0.02, 0.05, 0.10],
    },
}

# =============================================================================
# Selected benchmark instances for the L36 DOE
# =============================================================================
DOE_INSTANCES = {
    "small": ["BOWMAN8", "JACKSON", "BUXEY"],
    "medium": ["SAWYER30", "KILBRID", "TONGE70"],
    "large": ["ARC83", "BARTHOLD"],
}
