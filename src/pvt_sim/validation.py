"""
Genuine PVGIS cross-validation data.

IMPORTANT -- this replaces a serious bug in the original script: the old
code hard-coded a `PVGIS_MONTHLY` array that was NOT queried from PVGIS at
all. Per its own comment it was "the annual PVGIS number redistributed by
typical monthly fractions" -- i.e. synthetic data dressed up as an
independent monthly reference, then plotted next to the simulation in
Figure 4 as if it validated the seasonal shape. It only ever validated the
annual total.

This module calls PVGIS's own "PVcalc" tool (via
`pvlib.iotools.get_pvgis_hourly(..., pvcalculation=True)`), which runs
PVGIS's internal PV performance model with the *same* loss assumptions as
our PVWatts-v5 pipeline, and returns genuine hourly/monthly AC output for
the same system. That is what Figure 4's caption in the manuscript already
claims to be showing -- now the code actually produces it.

Network note: this hits PVGIS's live API (re.jrc.ec.europa.eu), which is
not reachable from every sandboxed environment. Run this on a machine with
normal internet access.
"""

from pathlib import Path

import pandas as pd
import pvlib

from .config import SystemParams

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_FILE = DATA_DIR / "pvgis_pvcalc_monthly_cache.csv"


def get_pvgis_monthly_ac(p: SystemParams, use_cache: bool = True,
                          refresh_cache: bool = False) -> pd.Series:
    """Return real PVGIS-modelled monthly AC energy [kWh] for this exact
    system configuration (same peak power, tilt, azimuth, and total loss
    as the PVlib/PVWatts-v5 simulation), via PVGIS's PVcalc tool.

    Returns a 12-element Series indexed Jan..Dec.
    """
    if use_cache and CACHE_FILE.exists() and not refresh_cache:
        s = pd.read_csv(CACHE_FILE, index_col=0)["e_ac_kwh"]
        s.index = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return s

    # PVGIS "aspect" convention: 0 = south (opposite offset from pvlib's
    # compass-bearing surface_azimuth, where 180 = south). Confirmed from
    # pvlib source (get_pvgis_hourly builds params['aspect'] =
    # surface_azimuth - 180), so passing surface_azimuth=180 here correctly
    # maps to PVGIS aspect=0 (south). No manual conversion needed.
    total_loss_pct = (1 - (1 - p.l_sys) * p.eta_inv) * 100  # combine DC-side + inverter loss

    print("Querying PVGIS PVcalc for genuine monthly AC output "
          "(this is the real Figure 4 reference, not a synthetic split). "
          "This pulls the full multi-year hourly database (~15-20 years "
          "for most European sites), so it's slower than the TMY fetch "
          "and will be cached after the first run...")
    # pvlib>=0.13 returns a 2-tuple (data, meta); the "inputs" dict PVGIS
    # echoes back is nested inside meta["inputs"], not returned separately.
    data, meta = pvlib.iotools.get_pvgis_hourly(
        latitude=p.latitude,
        longitude=p.longitude,
        surface_tilt=p.surface_tilt,
        surface_azimuth=p.surface_azimuth,
        pvcalculation=True,
        peakpower=p.pdc0 / 1000,       # kWp
        pvtechchoice="crystSi",
        mountingplace="free",
        loss=total_loss_pct,
        outputformat="json",
        map_variables=True,
    )

    if "P" not in data.columns:
        raise RuntimeError(
            "PVGIS response did not include AC power ('P'). Check that "
            "pvcalculation=True was honoured by this pvlib version."
        )

    # get_pvgis_hourly's 'seriescalc' endpoint returns the FULL multi-year
    # hourly database by default (e.g. ~19 years for Istanbul's SARAH2
    # coverage), not a single representative year the way get_pvgis_tmy
    # does. This actually matches how PVGIS's own website "PVcalc" tool
    # reports monthly figures: a long-term average across all available
    # years, not a single TMY year. So: sum to monthly energy per
    # (year, calendar-month), then average across years for each
    # calendar month -- this is the "typical monthly yield" PVGIS itself
    # would show, and it's what the annual reference number
    # (e.g. the manuscript's PVGIS comparison) is actually built from.
    e_ac_kwh_hourly = data["P"] / 1000  # W -> kWh per hour
    monthly_by_year = e_ac_kwh_hourly.groupby(
        [e_ac_kwh_hourly.index.year, e_ac_kwh_hourly.index.month]
    ).sum()
    monthly_by_year.index.names = ["year", "month"]
    n_years = monthly_by_year.index.get_level_values("year").nunique()
    monthly = monthly_by_year.groupby(level="month").mean()
    monthly.index = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    print(f"  Averaged monthly AC yield across {n_years} years of PVGIS "
          "hourly data (long-term typical-month reference).")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    monthly.rename("e_ac_kwh").to_csv(CACHE_FILE)
    print(f"  Cached to {CACHE_FILE}")
    return monthly


def get_pvgis_annual_reference_per_kwp(p: SystemParams, **kwargs) -> float:
    """Annual PVGIS AC yield per kWp, derived from the same real monthly
    query used for Figure 4 (so the annual deviation number and the
    monthly comparison plot are guaranteed to be mutually consistent)."""
    monthly = get_pvgis_monthly_ac(p, **kwargs)
    annual_kwh = monthly.sum()
    return annual_kwh / (p.pdc0 / 1000)
