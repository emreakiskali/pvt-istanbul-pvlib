"""
One-at-a-time (OAT) sensitivity analysis -- reproduces Table 4 of the
manuscript (Sec. 4.6.1) with an actual implementation.

Each parameter is perturbed individually from the baseline while holding
all others fixed, and the resulting % change in annual AC electrical
yield (E_PV) and combined yield (E_PVT) is reported.
"""

import pandas as pd

from .config import SystemParams
from .model import run_hourly_simulation


def _annual_yields(weather_raw: pd.DataFrame, p: SystemParams) -> tuple[float, float]:
    w = run_hourly_simulation(weather_raw, p)
    e_pv = w["e_pv_kwh"].sum()
    e_pvt = e_pv + w["e_thermal_kwh"].sum()
    return e_pv, e_pvt


# (field name, baseline value, perturbation, label) -- matches Table 4 rows.
# eta_0 / a1 are thermal-only parameters (no direct DC electrical pathway),
# so their ΔE_PV is reported as "--" exactly as in the manuscript table.
PERTURBATIONS = [
    ("surface_tilt", +5, "Tilt beta", "deg", True),
    ("surface_tilt", -5, "Tilt beta", "deg", True),
    ("gamma_pdc", +0.001, "gamma_pdc", "1/degC", True),
    ("gamma_pdc", -0.001, "gamma_pdc", "1/degC", True),
    ("u_c", +3, "u_c", "W/m2/K", True),
    ("u_c", -3, "u_c", "W/m2/K", True),
    ("eta_0", +0.05, "eta_0", "-", False),
    ("eta_0", -0.05, "eta_0", "-", False),
    ("a1", +1.0, "a1", "W/m2/K", False),
    ("a1", -1.0, "a1", "W/m2/K", False),
]


def run_sensitivity_table(weather_raw: pd.DataFrame, baseline: SystemParams) -> pd.DataFrame:
    e_pv_base, e_pvt_base = _annual_yields(weather_raw, baseline)

    rows = []
    for field, delta, label, unit, affects_pv in PERTURBATIONS:
        base_val = getattr(baseline, field)
        new_val = base_val + delta
        p_perturbed = baseline.with_overrides(**{field: new_val})
        e_pv, e_pvt = _annual_yields(weather_raw, p_perturbed)

        d_pv_pct = 100 * (e_pv - e_pv_base) / e_pv_base if affects_pv else float("nan")
        d_pvt_pct = 100 * (e_pvt - e_pvt_base) / e_pvt_base

        rows.append({
            "Parameter": label,
            "Baseline": base_val,
            "Perturbation": f"{delta:+g} {unit}",
            "dE_PV_pct": round(d_pv_pct, 1) if affects_pv else "--",
            "dE_PVT_pct": round(d_pvt_pct, 1),
        })

    return pd.DataFrame(rows)


def combined_upper_lower_bound(table: pd.DataFrame) -> dict:
    """Compounded bounds of Section 4.6.1: the positive and the negative
    one-at-a-time changes are summed separately (root-sum-of-squares is NOT
    used). Gives the -2.6 %/+1.8 % (E_PV) and -8.9 %/+8.3 % (E_PVT) values."""
    positive_pv = table[table["dE_PV_pct"] != "--"]
    pv_pos = sum(v for v in positive_pv["dE_PV_pct"] if v > 0)
    pv_neg = sum(v for v in positive_pv["dE_PV_pct"] if v < 0)

    pvt_pos = sum(v for v in table["dE_PVT_pct"] if v > 0)
    pvt_neg = sum(v for v in table["dE_PVT_pct"] if v < 0)

    return {
        "E_PV_upper_pct": round(pv_pos, 1),
        "E_PV_lower_pct": round(pv_neg, 1),
        "E_PVT_upper_pct": round(pvt_pos, 1),
        "E_PVT_lower_pct": round(pvt_neg, 1),
    }
