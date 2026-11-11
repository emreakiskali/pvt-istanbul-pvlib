"""
Supporting values quoted in the text of the manuscript that are not part
of Tables 3-5 (added in the revision in response to the reviewers):

  - timestamp handling (Section 3.4): what happens if the 1990 TMY
    timestamps are interpreted as local Istanbul time (8758 valid records),
    and the sensitivity of the annual yields to a shift of the solar
    geometry by the PVGIS irradiance time offset and by +/-30 min;
  - monthly meteorological values of Section 4.1 (POA irradiance and
    ambient temperature extremes);
  - the range of monthly AC efficiency (Section 4.7).
"""

import pandas as pd

from .config import SystemParams
from .model import run_hourly_simulation, monthly_aggregate


def local_time_record_check(weather_raw: pd.DataFrame, tz: str = "Europe/Istanbul") -> dict:
    """Interpret the (UTC) TMY timestamps as naive local time and count the
    hours that do not exist or are ambiguous because of daylight saving time
    in the nominal TMY year. The simulation itself keeps UTC and uses all
    8760 records; this only documents where '8758' comes from."""
    naive = weather_raw.index.tz_localize(None)
    local = naive.tz_localize(tz, nonexistent="NaT", ambiguous="NaT")
    invalid = int(local.isna().sum())
    return {
        "records_in_UTC": len(weather_raw),
        "nominal_TMY_year": int(naive.year[0]),
        "invalid_hours_if_read_as_local_time": invalid,
        "valid_records_if_read_as_local_time": len(weather_raw) - invalid,
    }


def solar_time_shift_sensitivity(weather_raw: pd.DataFrame, p: SystemParams,
                                 irradiance_time_offset_h: float) -> pd.DataFrame:
    """% change of annual AC and thermal yield when the solar geometry is
    evaluated at timestamp + shift (Section 3.4)."""
    base = run_hourly_simulation(weather_raw, p)
    e_pv0, e_th0 = base["e_pv_kwh"].sum(), base["e_thermal_kwh"].sum()
    rows = []
    for label, minutes in [("PVGIS irradiance time offset", 60 * irradiance_time_offset_h),
                           ("+30 min", 30.0), ("-30 min", -30.0)]:
        w = run_hourly_simulation(weather_raw, p.with_overrides(solar_time_shift_min=minutes))
        rows.append({
            "shift": label,
            "minutes": round(minutes, 1),
            "dE_PV_pct": round(100 * (w["e_pv_kwh"].sum() / e_pv0 - 1), 2),
            "dE_th_pct": round(100 * (w["e_thermal_kwh"].sum() / e_th0 - 1), 2),
        })
    return pd.DataFrame(rows)


def monthly_extremes(monthly: pd.DataFrame) -> dict:
    """Monthly values quoted in Sections 4.1 and 4.7."""
    return {
        "POA_monthly_mean_max_W_m2": f"{monthly['poa_mean_w_m2'].max():.1f} ({monthly['poa_mean_w_m2'].idxmax()})",
        "POA_monthly_mean_min_W_m2": f"{monthly['poa_mean_w_m2'].min():.1f} ({monthly['poa_mean_w_m2'].idxmin()})",
        "Ta_monthly_mean_min_degC": f"{monthly['temp_air_mean'].min():.1f} ({monthly['temp_air_mean'].idxmin()})",
        "Ta_monthly_mean_max_degC": f"{monthly['temp_air_mean'].max():.1f} ({monthly['temp_air_mean'].idxmax()})",
        "eta_PV_monthly_max_pct": f"{monthly['eta_pv_pct'].max():.2f} ({monthly['eta_pv_pct'].idxmax()})",
        "eta_PV_monthly_min_pct": f"{monthly['eta_pv_pct'].min():.2f} ({monthly['eta_pv_pct'].idxmin()})",
    }
