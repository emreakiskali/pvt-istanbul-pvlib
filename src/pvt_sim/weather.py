"""
Retrieval and local caching of PVGIS TMY meteorological data.

Caching matters for reproducibility: the manuscript's results must not
silently change if PVGIS revises its dataset, and reviewers/readers
without reliable network access should still be able to regenerate the
figures/tables from the cached CSV shipped in data/.
"""

import json
from pathlib import Path

import pandas as pd
import pvlib

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_FILE = DATA_DIR / "istanbul_pvgis_tmy_cache.csv"
META_FILE = DATA_DIR / "istanbul_pvgis_tmy_meta.json"


def get_tmy_weather(latitude: float, longitude: float, use_cache: bool = True,
                     refresh_cache: bool = False) -> pd.DataFrame:
    """Return an 8760-row hourly TMY DataFrame (UTC index) for the given site.

    Parameters
    ----------
    use_cache : if True and a cache file exists, read from disk instead of
        calling the PVGIS API.
    refresh_cache : if True, always hit the API and overwrite the cache.
    """
    if use_cache and CACHE_FILE.exists() and not refresh_cache:
        weather = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        weather.index = weather.index.tz_localize("UTC") if weather.index.tz is None else weather.index.tz_convert("UTC")
    else:
        print("Retrieving PVGIS TMY data from the live API...")
        weather, meta = pvlib.iotools.get_pvgis_tmy(
            latitude=latitude,
            longitude=longitude,
            outputformat="json",
            map_variables=True,
        )
        # Keep UTC to avoid DST boundary artefacts that reduce 8760 -> 8758
        # records when converting to Europe/Istanbul.
        weather.index = weather.index.tz_convert("UTC")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        weather.to_csv(CACHE_FILE)
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, default=str)
        print(f"  Cached to {CACHE_FILE} (metadata: {META_FILE.name})")

    n = len(weather)
    if n != 8760:
        raise AssertionError(
            f"Expected 8760 hourly TMY records, got {n}. "
            "Check the PVGIS response / cache file for corruption."
        )
    print(f"  Loaded {n} hourly TMY records.")
    return weather


def get_tmy_metadata(latitude: float, longitude: float) -> dict:
    """Return the PVGIS metadata of the cached TMY (radiation database,
    period, horizon setting, selected TMY months, irradiance time offset),
    as reported in Section 3.1 of the manuscript.

    If the weather cache exists but the metadata file does not (caches
    created by an earlier version of this code), the metadata are fetched
    again from PVGIS. The TMY data themselves are not replaced.
    """
    if not META_FILE.exists():
        _, meta = pvlib.iotools.get_pvgis_tmy(
            latitude=latitude, longitude=longitude,
            outputformat="json", map_variables=True,
        )
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, default=str)
    with open(META_FILE, encoding="utf-8") as f:
        meta = json.load(f)
    md = meta["inputs"]["meteo_data"]
    months = ", ".join(f"{m['month']:02d}/{m['year']}" for m in meta["months_selected"])
    return {
        "radiation_db": md.get("radiation_db"),
        "meteo_db": md.get("meteo_db"),
        "period": f"{md.get('year_min')}-{md.get('year_max')}",
        "use_horizon": md.get("use_horizon"),
        "horizon_db": md.get("horizon_db"),
        "months_selected (MM/YYYY)": months,
        "irradiance_time_offset_h": meta["inputs"]["location"].get("irradiance_time_offset"),
        "elevation_m": meta["inputs"]["location"].get("elevation"),
    }
