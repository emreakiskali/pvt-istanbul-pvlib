"""
Core hourly PV/T physics model.

Every function takes a `SystemParams` instance explicitly (see config.py)
so the same code path can be reused, unmodified, by:
  - the baseline annual simulation (run_simulation.py)
  - the one-at-a-time sensitivity analysis (sensitivity.py, Table 4)
  - the inlet-temperature scenarios (scenarios.py, Table 5)

This avoids the failure mode of the original script, where the baseline
run, the sensitivity table, and the inlet-scenario table were computed by
three different, partially-duplicated code paths that could (and did)
drift out of sync with each other and with the manuscript text.
"""

import numpy as np
import pandas as pd
import pvlib

from .config import SystemParams


def compute_irradiance_and_cell_temp(weather: pd.DataFrame, p: SystemParams) -> pd.DataFrame:
    """Add solar position, POA irradiance, and PVsyst cell temperature columns."""
    w = weather.copy()

    location = pvlib.location.Location(
        latitude=p.latitude, longitude=p.longitude, tz="UTC", name="Istanbul",
    )
    shift = pd.Timedelta(minutes=p.solar_time_shift_min)
    solar_pos = location.get_solarposition(w.index + shift)
    solar_pos.index = w.index

    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=p.surface_tilt,
        surface_azimuth=p.surface_azimuth,
        solar_zenith=solar_pos["apparent_zenith"],
        solar_azimuth=solar_pos["azimuth"],
        dni=w["dni"],
        ghi=w["ghi"],
        dhi=w["dhi"],
        albedo=p.ground_albedo,
    )
    w["poa_global"] = poa["poa_global"].clip(lower=0)
    w["solar_elevation"] = solar_pos["apparent_elevation"]

    w["temp_cell"] = pvlib.temperature.pvsyst_cell(
        poa_global=w["poa_global"],
        temp_air=w["temp_air"],
        wind_speed=w["wind_speed"],
        u_c=p.u_c,
        u_v=p.u_v,
        module_efficiency=p.eta_ref,
        alpha_absorption=p.alpha_abs,
    )
    return w


def compute_electrical(w: pd.DataFrame, p: SystemParams) -> pd.DataFrame:
    """Add DC power (PVWatts v5), system losses, inverter (AC), and hourly energy."""
    w = w.copy()

    w["p_dc"] = pvlib.pvsystem.pvwatts_dc(
        effective_irradiance=w["poa_global"],
        temp_cell=w["temp_cell"],
        pdc0=p.pdc0,
        gamma_pdc=p.gamma_pdc,
        temp_ref=p.temp_ref,
    ).clip(lower=0)

    w["p_dc_net"] = w["p_dc"] * (1 - p.l_sys)
    w["p_ac"] = (w["p_dc_net"] * p.eta_inv).clip(lower=0)
    w["e_pv_dc_kwh"] = w["p_dc"] / 1000
    w["e_pv_kwh"] = w["p_ac"] / 1000  # AC energy, kWh -- this is the delivered/comparable quantity
    return w


def compute_thermal(w: pd.DataFrame, p: SystemParams) -> pd.DataFrame:
    """Add fluid temperatures and thermal output using the linear EN ISO 9806
    collector curve, solved iteratively to convergence (not a fixed
    iteration count -- see config.max_iter / convergence_tol_degc).
    """
    w = w.copy()

    G = w["poa_global"]
    T_a = w["temp_air"]
    w["t_in"] = T_a + p.inlet_offset_degc

    dT = pd.Series(0.0, index=w.index)
    n_iter = 0
    for n_iter in range(1, p.max_iter + 1):
        red_temp = dT / G.clip(lower=1e-6)
        eta_th = (p.eta_0 - p.a1 * red_temp).clip(lower=0)
        eta_th[G <= 0] = 0.0

        solar_input_w = G * p.panel_area
        q_thermal_w = solar_input_w * eta_th
        delta_t_water = q_thermal_w / (p.mass_flow * p.cp_water)
        t_out = w["t_in"] + delta_t_water
        T_m = (w["t_in"] + t_out) / 2
        dT_new = T_m - T_a

        max_change = float((dT_new - dT).abs().max())
        dT = dT_new
        if max_change < p.convergence_tol_degc:
            break

    w["solar_input_w"] = solar_input_w
    w["q_thermal_w"] = q_thermal_w
    w["t_out"] = t_out
    w["eta_th_var"] = eta_th
    w["e_thermal_kwh"] = q_thermal_w / 1000

    w.attrs["thermal_solver_iterations"] = n_iter
    w.attrs["thermal_solver_max_change_degc"] = max_change
    return w


def compute_efficiencies(w: pd.DataFrame) -> pd.DataFrame:
    """Add hourly PV, thermal, and combined efficiency columns (both
    referenced to incident solar energy on the panel aperture, per
    Eq. 6/7/11 of the manuscript)."""
    w = w.copy()
    solar_in = w["solar_input_w"]
    w["eta_pv"] = (w["p_ac"] / solar_in).where(solar_in > 0, 0)
    w["eta_th"] = (w["q_thermal_w"] / solar_in).where(solar_in > 0, 0)
    w["eta_pvt"] = w["eta_pv"] + w["eta_th"]
    return w


def compute_fixed_efficiency_baseline(w: pd.DataFrame, p: SystemParams) -> dict:
    """Compare the variable collector-curve thermal model against a
    constant-efficiency (eta_th = eta_th_fixed_baseline) baseline, for
    all hours with positive POA irradiance (Section 3.3.4: 1480.9 kWh vs
    1130.1 kWh, approximately +31 %).
    """
    daylight = w["solar_input_w"] > 0
    q_fixed_w = w.loc[daylight, "solar_input_w"] * p.eta_th_fixed_baseline
    e_fixed_kwh = (q_fixed_w / 1000).sum()
    e_variable_kwh = w.loc[daylight, "e_thermal_kwh"].sum()
    pct_diff = 100 * (e_variable_kwh - e_fixed_kwh) / e_fixed_kwh
    return {
        "e_thermal_fixed_baseline_kwh": e_fixed_kwh,
        "e_thermal_variable_kwh": e_variable_kwh,
        "pct_difference_variable_vs_fixed": pct_diff,
    }


def run_hourly_simulation(weather_raw: pd.DataFrame, p: SystemParams) -> pd.DataFrame:
    """Run the full hourly pipeline: irradiance -> cell temp -> electrical -> thermal -> efficiencies."""
    w = compute_irradiance_and_cell_temp(weather_raw, p)
    w = compute_electrical(w, p)
    w = compute_thermal(w, p)
    w = compute_efficiencies(w)
    return w


def monthly_aggregate(w: pd.DataFrame) -> pd.DataFrame:
    """Monthly sums and means. Monthly efficiencies are energy-based:
    monthly energy divided by the monthly solar energy incident on the
    aperture (same definition as the annual efficiencies)."""
    monthly = w.resample("ME").agg(
        e_pv_kwh=("e_pv_kwh", "sum"),
        e_thermal_kwh=("e_thermal_kwh", "sum"),
        p_dc=("p_dc", "sum"),
        solar_input_w=("solar_input_w", "sum"),
        poa_mean_w_m2=("poa_global", "mean"),
        temp_cell_mean=("temp_cell", "mean"),
        temp_air_mean=("temp_air", "mean"),
        t_out_mean=("t_out", "mean"),
    )
    h_in_kwh = monthly["solar_input_w"] / 1000
    monthly["e_combined_kwh"] = monthly["e_pv_kwh"] + monthly["e_thermal_kwh"]
    monthly["eta_pv_pct"] = 100 * monthly["e_pv_kwh"] / h_in_kwh
    monthly["eta_th_pct"] = 100 * monthly["e_thermal_kwh"] / h_in_kwh
    monthly["eta_pvt_pct"] = monthly["eta_pv_pct"] + monthly["eta_th_pct"]
    monthly.index = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    return monthly


def closed_form_thermal_efficiency(p: SystemParams) -> float:
    """Thermal efficiency for T_in = T_a (Section 3.3.4):
    eta_th = eta_0 / [1 + a1*A/(2*m*cp)], identical in every hour with G > 0."""
    return p.eta_0 / (1 + p.a1 * p.panel_area / (2 * p.mass_flow * p.cp_water))


def annual_summary(w: pd.DataFrame, p: SystemParams, pvgis_ac_per_kwp: float) -> dict:
    """All Table 3 metrics (and the related values quoted in the text),
    computed once from one hourly dataframe.

    Annual efficiencies are energy-based (Section 3.3.5): each annual
    energy yield divided by the annual solar energy incident on the
    collector aperture, H_in = sum(G_POA * A * dt) / 1000. Electrical and
    thermal efficiencies therefore share the same denominator and can be
    added. (An earlier version added a daylight-hour mean electrical
    efficiency to an all-hour mean thermal efficiency, which is not a
    meaningful quantity; that output has been removed.)

    `pvgis_ac_per_kwp` should come from validation.get_pvgis_annual_reference_per_kwp().
    """
    e_pv_dc_annual = w["e_pv_dc_kwh"].sum()
    e_pv_ac_annual = w["e_pv_kwh"].sum()
    e_th_annual = w["e_thermal_kwh"].sum()
    e_total_annual = e_pv_ac_annual + e_th_annual

    poa_irradiation_kwh_m2 = w["poa_global"].sum() / 1000          # dt = 1 h
    h_in_kwh = w["solar_input_w"].sum() / 1000                      # = POA irradiation * A
    eta_pv_annual = e_pv_ac_annual / h_in_kwh
    eta_pv_dc_annual = e_pv_dc_annual / h_in_kwh
    eta_th_annual = e_th_annual / h_in_kwh
    eta_pvt_annual = eta_pv_annual + eta_th_annual

    daylight = w["solar_input_w"] > 0
    eta_stc_nominal = p.pdc0 / (p.panel_area * 1000)
    temp_factor = 1 + p.gamma_pdc * (w["temp_cell"] - p.temp_ref)
    temp_factor_energy_weighted = (temp_factor * w["poa_global"]).sum() / w["poa_global"].sum()
    reduced_temp = ((w["t_in"] + w["t_out"]) / 2 - w["temp_air"]) / w["poa_global"]

    e_pv_per_kwp = e_pv_ac_annual / (p.pdc0 / 1000)
    deviation_from_pvgis_pct = (e_pv_per_kwp - pvgis_ac_per_kwp) / pvgis_ac_per_kwp * 100

    baseline_compare = compute_fixed_efficiency_baseline(w, p)

    return {
        "E_PV_DC_ANNUAL_kWh": e_pv_dc_annual,
        "system_losses_kWh": e_pv_dc_annual * p.l_sys,
        "inverter_losses_kWh": e_pv_dc_annual * (1 - p.l_sys) * (1 - p.eta_inv),
        "E_PV_AC_ANNUAL_kWh": e_pv_ac_annual,
        "E_TH_ANNUAL_kWh": e_th_annual,
        "E_TOTAL_ANNUAL_kWh": e_total_annual,
        "POA_irradiation_kWh_per_m2": poa_irradiation_kwh_m2,
        "H_in_kWh": h_in_kwh,
        "eta_PV_AC_annual_pct": eta_pv_annual * 100,
        "eta_PV_DC_annual_pct": eta_pv_dc_annual * 100,
        "eta_TH_annual_pct": eta_th_annual * 100,
        "eta_PVT_annual_pct": eta_pvt_annual * 100,
        "E_PV_per_kWp": e_pv_per_kwp,
        "PVGIS_reference_kWh_per_kWp": pvgis_ac_per_kwp,
        "deviation_from_PVGIS_pct": deviation_from_pvgis_pct,
        # --- values quoted in Sections 3.3.4, 4.3, 4.7 and 4.9 -------------
        "eta_STC_nominal_pct": eta_stc_nominal * 100,
        "eta_after_system_and_inverter_losses_pct": eta_stc_nominal * (1 - p.l_sys) * p.eta_inv * 100,
        "temperature_factor_energy_weighted": temp_factor_energy_weighted,
        "eta_TH_closed_form_pct": closed_form_thermal_efficiency(p) * 100,
        "eta_TH_hourly_min_daylight_pct": w.loc[daylight, "eta_th"].min() * 100,
        "eta_TH_hourly_max_daylight_pct": w.loc[daylight, "eta_th"].max() * 100,
        "reduced_temperature_mean_daylight_m2K_per_W": reduced_temp[daylight].mean(),
        "daylight_hours": int(daylight.sum()),
        "max_cell_temp_degC": w["temp_cell"].max(),
        "monthly_mean_cell_temp_peak_degC": w.resample("ME")["temp_cell"].mean().max(),
        "max_outlet_temp_degC": w["t_out"].max(),
        "monthly_mean_outlet_temp_peak_degC": w.resample("ME")["t_out"].mean().max(),
        "thermal_solver_iterations": w.attrs.get("thermal_solver_iterations"),
        "thermal_solver_residual_degC": w.attrs.get("thermal_solver_max_change_degc"),
        **baseline_compare,
    }
