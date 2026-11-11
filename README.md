# PVT Istanbul — Annual Energy Simulation

Annual performance simulation of a water-cooled Photovoltaic–Thermal
(PV/T) system under Istanbul TMY climate conditions, using
[PVlib](https://pvlib-python.readthedocs.io/) and PVGIS meteorological
data.

Companion code for:

> Gülcü, M., Akıskalıoğlu, E., Atmaca, M. (2026). *Annual Energy Analysis
> and Performance Simulation of Photovoltaic–Thermal (PV/T) Systems
> Under Istanbul Climate Conditions Using Python and PVlib.* Submitted

This is a refactor of an earlier version of the simulation.
The code now can do:

- **`validation.py`** now queries PVGIS's own PVcalc tool for a genuine
  monthly AC-yield reference, instead of redistributing a single annual
  number across months using unstated fractions.
- **`sensitivity.py`** implements the Table 4 one-at-a-time sensitivity
  analysis (tilt, γ_pdc, u_c, η₀, a₁) as actual perturbation runs.
- **`scenarios.py`** implements the Table 5 inlet-temperature scenarios
  (T_a, T_a+10°C, T_a+20°C) as actual reruns of the thermal model, and
  reports the annual thermal efficiency of each scenario.
- **`diagnostics.py`** reproduces the supporting values quoted in the
  text of the revised manuscript (timestamp check, solar-geometry time
  shift sensitivity, monthly extremes of Sections 4.1 and 4.7).
- **`model.py`**'s thermal solver now iterates to an explicit convergence
  tolerance (`config.convergence_tol_degc`) instead of a fixed 3-pass
  loop, and reports the iteration count/residual.
- All four analyses share one physics implementation (`model.py`) driven
  by one parameter set (`config.py`), so the baseline run, the
  sensitivity table, and the scenario table cannot silently drift out of
  sync with each other the way they had in the manuscript draft.
- PVGIS TMY weather is cached locally (`data/`) after first download, so
  results are reproducible even without live network access on
  subsequent runs.

## Requirements

```bash
pip install -r requirements.txt
```

Tested with Python 3.12 and the pinned versions in `requirements.txt`
(pandas ≥ 2.2 is required for the `"ME"` resample alias used throughout;
older pandas needs `"M"` instead).

## Usage

```bash
python run_simulation.py
```

This will:
1. Fetch (or load cached) PVGIS TMY weather for Istanbul
   and print its PVGIS metadata (database, period, horizon setting,
   selected TMY months; Section 3.1).
2. Run the baseline hourly simulation and print Table 3 (annual
   performance summary).
3. Run the OAT sensitivity analysis and print Table 4.
4. Run the inlet-temperature scenarios and print Table 5.
5. Print the supporting values of Sections 3.4, 4.1 and 4.7, and export
   hourly/monthly/table/supporting results to `outputs/*.xlsx`.
6. Generate Figures 2–6 into `figures/*.png`, including a Figure 4 built
   from a **real** PVGIS PVcalc monthly query.

**Network note:** step 1 and the PVGIS validation in step 2 call the live
PVGIS API (`re.jrc.ec.europa.eu`). Run this somewhere with normal
internet access — some sandboxed/CI environments block this domain.

## Revision of November 2026 (response to reviewers)

- **Annual efficiencies are now energy-based.** Each annual energy yield
  is divided by the annual solar energy incident on the collector
  aperture, H_in = Σ G_POA·A·Δt / 1000 (Section 3.3.5). The earlier
  output added a daylight-hour mean electrical efficiency to an all-hour
  mean thermal efficiency (40.50 %), which is not a meaningful quantity
  and has been removed. The corrected values are 14.34 % (AC electrical),
  52.41 % (thermal) and 66.76 % (combined). Monthly efficiencies use the
  same definition.
- **Closed-form thermal efficiency.** With T_in = T_a, the collector curve
  gives η_th = η₀ / [1 + a₁A/(2ṁc_p)] = 52.41 % in every daylight hour;
  `annual_summary` reports this value next to the simulated one.
- **Table numbers follow the revised manuscript**: annual summary =
  Table 3, sensitivity = Table 4, inlet scenarios = Table 5.
- **PVGIS metadata** returned with the TMY are cached in
  `data/istanbul_pvgis_tmy_meta.json` and printed at the start of a run.

## Fixed since the first version of this package

- **`get_pvgis_hourly` return-value unpacking.** Current pvlib (0.13+)
  returns a 2-tuple `(data, meta)` from `get_pvgis_hourly`, not the
  3-tuple `(data, inputs, meta)` shown in some older examples floating
  around online. `validation.py` now unpacks it correctly — if you see
  `ValueError: not enough values to unpack`, you're on an old copy of
  this file.
- **Azimuth convention**, confirmed by reading the installed pvlib's
  source directly: `get_pvgis_hourly` builds PVGIS's `aspect` parameter
  as `surface_azimuth - 180`, so passing `surface_azimuth=180` (south, in
  pvlib's compass-bearing convention used everywhere else in this
  codebase) correctly maps to PVGIS's `aspect=0` (its own south
  convention). No manual conversion needed — this was flagged as a
  caveat to verify in the first version of this package and has now been
  confirmed correct against the pvlib 0.13.1 source.
- **Multi-year hourly data, not a single year.** `get_pvgis_hourly`'s
  `seriescalc` endpoint returns the *entire* multi-year hourly database
  (~15–20 years, depending on site) unless you pass explicit `start`/
  `end` years — it is not a TMY-style single representative year the way
  `get_pvgis_tmy` is. `get_pvgis_monthly_ac` now sums to monthly energy
  per (year, calendar-month) and averages across years, which is also
  what PVGIS's own website "PVcalc" tool does internally to produce its
  headline monthly/annual figures — so this is the correct reference,
  not just a workaround for the crash it originally caused.

## Repository structure

```
run_simulation.py          # main entry point — run this
src/pvt_sim/
  config.py                 # all system/model parameters (Table 1)
  weather.py                 # PVGIS TMY fetch + local cache + PVGIS metadata
  model.py                   # core hourly physics (irradiance -> cell temp -> electrical -> thermal)
  validation.py               # real PVGIS PVcalc monthly/annual reference
  sensitivity.py               # Table 4: OAT sensitivity analysis
  scenarios.py                  # Table 5: inlet-temperature scenarios
  diagnostics.py                 # supporting values quoted in Sections 3.4, 4.1 and 4.7
  plotting.py                    # Figures 2-6
data/                       # cached PVGIS TMY + PVcalc responses (gitignored, regenerated on first run)
outputs/                    # Excel exports (gitignored)
figures/                    # PNG figures (gitignored)
requirements.txt
LICENSE
```

## Data availability

Raw meteorological data are sourced from the [PVGIS
API](https://re.jrc.ec.europa.eu/pvg_tools/en/) (Huld et al., 2012).
All simulation code in this repository is original work by the authors.

## Citing

If you use this code, please cite the manuscript above and this
repository.

## License

MIT — see `LICENSE`.
