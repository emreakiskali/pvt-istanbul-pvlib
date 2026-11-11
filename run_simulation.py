"""
PVT Istanbul -- Annual Energy Simulation
========================================

Reproduces the numbers, tables and figures of the manuscript (revised
version):
  - Table 3  : annual performance summary, energy-based efficiencies (model.annual_summary)
  - Table 4  : OAT sensitivity analysis (sensitivity.py)
  - Table 5  : inlet-temperature scenarios (scenarios.py)
  - Section 3.1 : PVGIS database, period, horizon and selected TMY months (weather.get_tmy_metadata)
  - Sections 3.4, 4.1, 4.7 : supporting values (diagnostics.py)
  - Figures 2-6 : plotting.py (Figure 4 uses a real PVGIS PVcalc monthly query)

Run from a machine with normal internet access (the PVGIS API is not
reachable from every sandboxed environment):

    python run_simulation.py

Outputs land in outputs/ (Excel) and figures/ (PNG).
Requirements: see requirements.txt (pip install -r requirements.txt)
"""

from pathlib import Path

import pandas as pd

from src.pvt_sim.config import BASELINE
from src.pvt_sim.weather import get_tmy_weather, get_tmy_metadata
from src.pvt_sim.model import run_hourly_simulation, monthly_aggregate, annual_summary
from src.pvt_sim.validation import get_pvgis_monthly_ac, get_pvgis_annual_reference_per_kwp
from src.pvt_sim.sensitivity import run_sensitivity_table, combined_upper_lower_bound
from src.pvt_sim.scenarios import run_inlet_scenarios
from src.pvt_sim.plotting import generate_all_figures
from src.pvt_sim.diagnostics import (local_time_record_check,
                                     solar_time_shift_sensitivity, monthly_extremes)

OUTPUT_DIR = Path(__file__).parent / "outputs"


def main():
    p = BASELINE

    # ---- 1. Weather -----------------------------------------------------
    weather_raw = get_tmy_weather(p.latitude, p.longitude)

    pvgis_meta = get_tmy_metadata(p.latitude, p.longitude)
    _print_block("SECTION 3.1 -- PVGIS TMY METADATA", pvgis_meta)

    # ---- 2. Baseline hourly simulation -> Table 3 ------------------------
    print("\nRunning baseline hourly simulation...")
    w = run_hourly_simulation(weather_raw, p)
    monthly = monthly_aggregate(w)

    print("Fetching PVGIS PVcalc monthly/annual reference...")
    pvgis_monthly = get_pvgis_monthly_ac(p)
    pvgis_annual_per_kwp = get_pvgis_annual_reference_per_kwp(p)

    summary = annual_summary(w, p, pvgis_annual_per_kwp)
    _print_block("TABLE 3 -- ANNUAL PERFORMANCE SUMMARY (energy-based efficiencies)", summary)

    print("\nMonthly breakdown (efficiencies are energy-based, %):")
    print(monthly[["e_pv_kwh", "e_thermal_kwh", "e_combined_kwh", "poa_mean_w_m2",
                   "temp_air_mean", "temp_cell_mean", "t_out_mean",
                   "eta_pv_pct", "eta_th_pct"]].round(2).to_string())

    # ---- 3. Sensitivity analysis -> Table 4 -------------------------------
    print("\nRunning OAT sensitivity analysis (Table 4)... this re-runs the "
          "full hourly simulation once per row, so it takes a while.")
    table4 = run_sensitivity_table(weather_raw, p)
    print("\n" + "=" * 60)
    print("  TABLE 4 -- ONE-AT-A-TIME SENSITIVITY")
    print("=" * 60)
    print(table4.to_string(index=False))
    bounds = combined_upper_lower_bound(table4)
    print(f"\n  Compounded upper/lower bound: "
          f"E_PV {bounds['E_PV_lower_pct']:+.1f}%/{bounds['E_PV_upper_pct']:+.1f}%  "
          f"E_PVT {bounds['E_PVT_lower_pct']:+.1f}%/{bounds['E_PVT_upper_pct']:+.1f}%")

    # ---- 4. Inlet-temperature scenarios -> Table 5 -----------------------
    print("\nRunning inlet-temperature scenarios (Table 5)...")
    table5 = run_inlet_scenarios(weather_raw, p)
    print("\n" + "=" * 60)
    print("  TABLE 5 -- INLET TEMPERATURE SCENARIOS")
    print("=" * 60)
    print(table5.to_string(index=False))

    # ---- 5. Supporting values quoted in the text --------------------------
    records = local_time_record_check(weather_raw)
    _print_block("SECTION 3.4 -- TIMESTAMP CHECK", records)
    shifts = solar_time_shift_sensitivity(weather_raw, p, pvgis_meta["irradiance_time_offset_h"])
    print("\nSECTION 3.4 -- SOLAR-GEOMETRY TIME SHIFT SENSITIVITY")
    print(shifts.to_string(index=False))
    extremes = monthly_extremes(monthly)
    _print_block("SECTIONS 4.1 / 4.7 -- MONTHLY EXTREMES", extremes)

    # ---- 6. Export to Excel ------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    w_xl = w.copy()
    w_xl.index = w_xl.index.tz_localize(None)
    w_xl.to_excel(OUTPUT_DIR / "istanbul_pvt_hourly_results.xlsx")
    monthly.to_excel(OUTPUT_DIR / "istanbul_pvt_monthly_results.xlsx")
    pd.Series(summary).to_excel(OUTPUT_DIR / "table3_annual_summary.xlsx")
    table4.to_excel(OUTPUT_DIR / "table4_sensitivity.xlsx", index=False)
    table5.to_excel(OUTPUT_DIR / "table5_inlet_scenarios.xlsx", index=False)
    with pd.ExcelWriter(OUTPUT_DIR / "supporting_values.xlsx") as xw:
        pd.Series(pvgis_meta).to_excel(xw, sheet_name="pvgis_metadata")
        pd.Series(records).to_excel(xw, sheet_name="timestamp_check")
        shifts.to_excel(xw, sheet_name="time_shift", index=False)
        pd.Series(extremes).to_excel(xw, sheet_name="monthly_extremes")
    print(f"\nExported hourly, monthly, table and supporting results to {OUTPUT_DIR}/")

    # ---- 7. Figures ---------------------------------------------------------
    generate_all_figures(monthly, pvgis_monthly, summary["E_PV_AC_ANNUAL_kWh"])
    print("\nDone.")


def _print_block(title: str, values: dict) -> None:
    print("\n" + "=" * 60)
    print("  " + title)
    print("=" * 60)
    for k, v in values.items():
        if isinstance(v, float):
            print(f"  {k:48s}: {v:12.4f}")
        else:
            print(f"  {k:48s}: {v}")


if __name__ == "__main__":
    main()
