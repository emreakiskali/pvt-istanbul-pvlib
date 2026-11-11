"""
Figure generation, matching the manuscript's figures 2-6.
(Figure 1, the long-term sunshine-duration chart, is historical data
provided separately and is not generated here.)
"""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

FIG_DIR = Path(__file__).resolve().parents[2] / "figures"


def _setup_ax(ax, ylabel, xlabel="Month"):
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.yaxis.grid(True, alpha=0.4)
    ax.set_axisbelow(True)


def fig2_pv_monthly(monthly: pd.DataFrame) -> Path:
    months = monthly.index
    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(x, monthly["e_pv_kwh"], color="steelblue", width=0.6)
    for bar, v in zip(bars, monthly["e_pv_kwh"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{v:.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title("Monthly PV Electrical Energy Output (AC)", fontsize=13)
    _setup_ax(ax, "Energy [kWh]")
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.set_ylim(0, monthly["e_pv_kwh"].max() * 1.18)
    fig.tight_layout()
    out = FIG_DIR / "fig2_pv_monthly.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def fig3_pvt_monthly_comparison(monthly: pd.DataFrame) -> Path:
    months = monthly.index
    x = np.arange(len(months))
    w = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - w / 2, monthly["e_pv_kwh"], w, label="PV Electricity (AC)", color="steelblue")
    ax.bar(x + w / 2, monthly["e_thermal_kwh"], w, label="Thermal Energy", color="darkorange")
    ax.set_title("Monthly PV Electrical and Thermal Energy Output", fontsize=13)
    _setup_ax(ax, "Energy [kWh]")
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.legend(fontsize=10)
    fig.tight_layout()
    out = FIG_DIR / "fig3_pvt_monthly_comparison.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def fig4_pvgis_comparison(monthly: pd.DataFrame, pvgis_monthly_kwh: pd.Series,
                           e_pv_ac_annual: float) -> Path:
    """Uses the REAL PVGIS PVcalc monthly series from validation.py --
    not a redistributed annual total. See validation.py module docstring.
    """
    months = monthly.index
    x = np.arange(len(months))
    w = 0.35
    pvgis_annual = pvgis_monthly_kwh.sum()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - w / 2, monthly["e_pv_kwh"], w,
           label=f"PVlib simulation ({e_pv_ac_annual:.0f} kWh/yr)", color="steelblue")
    ax.bar(x + w / 2, pvgis_monthly_kwh.values, w,
           label=f"PVGIS PVcalc reference ({pvgis_annual:.0f} kWh/yr)", color="darkorange")
    ax.set_title("Monthly PV AC Yield: PVlib/PVWatts v5 vs. PVGIS PVcalc", fontsize=12)
    _setup_ax(ax, "Energy [kWh]")
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.legend(fontsize=10)
    fig.tight_layout()
    out = FIG_DIR / "fig4_pvgis_comparison.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def fig5_cell_temperature(monthly: pd.DataFrame) -> Path:
    months = monthly.index
    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x, monthly["temp_cell_mean"].values, marker="o", color="crimson",
            linewidth=2.5, markersize=7, label="Cell temperature")
    ax.plot(x, monthly["temp_air_mean"].values, marker="^", color="gray",
            linewidth=1.5, linestyle="--", markersize=6, label="Ambient temperature")
    for i, tc in enumerate(monthly["temp_cell_mean"].values):
        ax.text(i, tc + 0.5, f"{tc:.1f}", ha="center", va="bottom", fontsize=8, color="crimson")
    ax.set_title("Monthly Mean PV Cell Temperature", fontsize=13)
    _setup_ax(ax, "Temperature [degC]")
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.legend(fontsize=10)
    fig.tight_layout()
    out = FIG_DIR / "fig5_cell_temperature.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def fig6_fluid_temperature(monthly: pd.DataFrame) -> Path:
    months = monthly.index
    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x, monthly["t_out_mean"].values, marker="s", color="darkorange",
            linewidth=2.5, markersize=7, label="T_out -- fluid outlet (mean)")
    ax.plot(x, monthly["temp_air_mean"].values, marker="^", color="gray",
            linewidth=1.5, linestyle="--", markersize=6, label="T_a -- ambient (mean)")
    for i, (to, ta) in enumerate(zip(monthly["t_out_mean"].values, monthly["temp_air_mean"].values)):
        ax.annotate(f"+{to - ta:.1f}degC", xy=(i, (to + ta) / 2), xytext=(i + 0.1, (to + ta) / 2),
                    fontsize=7.5, color="darkorange", va="center")
    ax.set_title("Monthly Mean Fluid Outlet Temperature vs. Ambient Temperature", fontsize=13)
    _setup_ax(ax, "Temperature [degC]")
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.legend(fontsize=10)
    fig.tight_layout()
    out = FIG_DIR / "fig6_fluid_temperature.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def generate_all_figures(monthly: pd.DataFrame, pvgis_monthly_kwh: pd.Series,
                          e_pv_ac_annual: float) -> list[Path]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    paths = [
        fig2_pv_monthly(monthly),
        fig3_pvt_monthly_comparison(monthly),
        fig4_pvgis_comparison(monthly, pvgis_monthly_kwh, e_pv_ac_annual),
        fig5_cell_temperature(monthly),
        fig6_fluid_temperature(monthly),
    ]
    for p in paths:
        print(f"Saved: {p}")
    print("NOTE: fig1_sunshine.png (historical sunshine data) must be")
    print("      provided separately -- it is not generated by simulation.")
    return paths
