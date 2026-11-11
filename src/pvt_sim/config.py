"""
Central configuration for the Istanbul PV/T annual simulation.

All physical/system parameters live here (matches Table 1 of the
manuscript) so that every module (baseline run, sensitivity analysis,
inlet-temperature scenarios, PVGIS validation) shares one source of
truth instead of re-declaring constants.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SystemParams:
    # --- Location ---------------------------------------------------
    latitude: float = 41.0082     # degrees N
    longitude: float = 28.9784    # degrees E  (rounds to 28.98, not 28.97 -- see Table 1 note)

    # --- Panel geometry ----------------------------------------------
    surface_tilt: float = 30      # degrees from horizontal
    surface_azimuth: float = 180  # degrees (180 = south-facing, pvlib convention)
    panel_area: float = 1.65      # m^2

    # --- Electrical parameters ---------------------------------------
    eta_ref: float = 0.18         # reference STC efficiency [-]
    pdc0: float = 300             # nominal DC power at STC [W]
    gamma_pdc: float = -0.004     # temperature power coefficient [1/degC]
    temp_ref: float = 25          # reference temperature [degC]

    # --- PVWatts v5 system-level parameters (Dobos 2014) --------------
    l_sys: float = 0.14           # total DC system loss (soiling 2%, shading 3%,
                                   # mismatch 2%, wiring 2%, connections 0.5%,
                                   # LID 1.5%, nameplate 1%, availability 3%)
    eta_inv: float = 0.96         # nominal inverter efficiency [-]

    # --- PVsyst cell-temperature model ---------------------------------
    u_c: float = 29.0             # constant heat-loss coefficient [W/m^2/K]
    u_v: float = 0.0              # wind-speed heat-loss coefficient (0 = glazed)
    alpha_abs: float = 0.90       # absorber absorption coefficient [-]
    ground_albedo: float = 0.20   # ground reflectance [-]

    # --- Thermal model: linear collector curve (EN ISO 9806) -----------
    eta_0: float = 0.55           # zero-loss (optical) thermal efficiency [-]
    a1: float = 5.0                # first-order heat-loss coefficient [W/m^2/K]
    eta_th_fixed_baseline: float = 0.40  # constant-efficiency comparison baseline (Sec 3.3.4)

    # --- Hydraulic parameters -------------------------------------------
    mass_flow: float = 0.02       # fluid mass-flow rate [kg/s]
    cp_water: float = 4182        # specific heat of water [J/kg/K]

    # --- Fluid inlet temperature model -----------------------------------
    # T_in = T_a + inlet_offset_degc  (baseline: offset = 0, i.e. T_in = T_a)
    inlet_offset_degc: float = 0.0

    # --- Solar-geometry timestamp shift ------------------------------------
    # Solar position is evaluated at (timestamp + shift). Baseline = 0, i.e.
    # the nominal hourly UTC timestamps of the PVGIS TMY are used as they are.
    # Only diagnostics.py changes this, to test sensitivity to the timestamp
    # convention (Section 3.4 of the manuscript).
    solar_time_shift_min: float = 0.0

    # --- Iterative solver for the thermal balance --------------------------
    max_iter: int = 20
    convergence_tol_degc: float = 1e-4  # stop when max |dT change| < tol

    # --- External validation reference (fallback only; validation.py
    #     fetches the *real* PVGIS number/monthly series at runtime) -------
    pvgis_annual_kwh_per_kwp_fallback: float = 1349.5

    def with_overrides(self, **kwargs) -> "SystemParams":
        """Return a copy of this parameter set with the given fields overridden.

        Used by sensitivity.py / scenarios.py to run one-at-a-time (OAT)
        perturbations without mutating the shared baseline config.
        """
        return replace(self, **kwargs)


BASELINE = SystemParams()

# Random-ish but fixed seed not needed: model is fully deterministic given
# the weather input, so no RNG is used anywhere in this package.
