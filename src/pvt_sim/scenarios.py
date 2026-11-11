"""
Inlet fluid-temperature scenarios -- reproduces Table 5 of the manuscript
(Sec. 4.6.2): baseline T_in = T_a, plus T_a + 10 degC and T_a + 20 degC to
represent partial/full storage-return operating modes.
"""

import pandas as pd

from .config import SystemParams
from .model import run_hourly_simulation

SCENARIOS = [
    ("Baseline", 0.0),
    ("Scenario A", 10.0),
    ("Scenario B", 20.0),
]


def run_inlet_scenarios(weather_raw: pd.DataFrame, baseline: SystemParams) -> pd.DataFrame:
    rows = []
    e_th_baseline = None
    for label, offset in SCENARIOS:
        p = baseline.with_overrides(inlet_offset_degc=offset)
        w = run_hourly_simulation(weather_raw, p)
        e_th = w["e_thermal_kwh"].sum()
        h_in = w["solar_input_w"].sum() / 1000
        daylight = w["solar_input_w"] > 0
        zero_heat_hours = int(((w["q_thermal_w"] <= 0) & daylight).sum())
        if label == "Baseline":
            e_th_baseline = e_th
        change_pct = 0.0 if label == "Baseline" else 100 * (e_th - e_th_baseline) / e_th_baseline
        rows.append({
            "Scenario": label,
            "T_in": "T_a" if offset == 0 else f"T_a + {offset:g} degC",
            "E_th_kWh_per_yr": round(e_th, 1),
            "Change_vs_baseline_pct": round(change_pct, 1) if label != "Baseline" else "--",
            "eta_th_annual_pct": round(100 * e_th / h_in, 2),
            "daylight_hours_without_useful_heat": zero_heat_hours,
            "daylight_hours": int(daylight.sum()),
        })
    return pd.DataFrame(rows)
