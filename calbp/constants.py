"""
Mode constants and default parameters for the CALBP.

Mode encoding:
  1 = HI   (Human Independent)
  2 = CI   (Cobot Independent)
  3 = SEH  (Sequential — human side)
  4 = SEC  (Sequential — cobot side)
  5 = SU   (Supportive)
  6 = SIH  (Simultaneous — human side)
  7 = SIC  (Simultaneous — cobot side)
"""

# --- Mode integer codes -------------------------------------------------------
HI, CI, SEH, SEC, SU, SIH, SIC = 1, 2, 3, 4, 5, 6, 7

MODE_NAMES = {HI: "HI", CI: "CI", SEH: "SEH", SEC: "SEC",
              SU: "SU", SIH: "SIH", SIC: "SIC"}
MODE_IDS = {v: k for k, v in MODE_NAMES.items()}
ALL_MODES = [HI, CI, SEH, SEC, SU, SIH, SIC]
ALL_MODE_NAMES = ["HI", "CI", "SEH", "SEC", "SU", "SIH", "SIC"]

# --- Mode subsets -------------------------------------------------------------
M_H = frozenset({HI, SEH, SU, SIH})       # require a human worker
M_C = frozenset({CI, SEC, SU, SIC})        # require a cobot
M_SE = frozenset({SEH, SEC})               # sequential family
M_SI = frozenset({SIH, SIC})               # simultaneous family
M_OTHER = frozenset({HI, CI, SU})          # independent modes
M_NS = frozenset({HI, CI, SEH, SEC, SU})   # non-simultaneous (used in C5a)

# --- Cost defaults (Weckenborg & Spengler, 2019) -----------------------------
DEFAULT_C_S = 4.0    # €/h station opening
DEFAULT_C_W = 36.0   # €/h human worker
DEFAULT_C_C = 5.0    # €/h cobot

# --- Energy power ranges (W) for cobot-involved modes -------------------------
# Source: calibrated from Heredia et al. (2023) UR-series cobot measurements.
# HI / SEH / SIH → 0 (no cobot energy for human-only execution)
DEFAULT_POWER_RANGES = {
    "HI":  (0, 0),
    "CI":  (220, 300),
    "SEH": (0, 0),
    "SEC": (180, 220),
    "SU":  (140, 160),
    "SIH": (0, 0),
    "SIC": (120, 150),
}
