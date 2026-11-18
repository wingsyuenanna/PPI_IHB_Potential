"""Stacked country trade-off scatters: 5 km vs 15 km.

Country bubbles = max heat served under country gas heat price
(LCOH ≤ country gas-boiler cost: fuel/η + EUA).
Crosshairs = fleet HW averages for that policy and max savings.
Region = colour + marker (not colour-only); size ∝ national heat demand.

    python outputs/multiband/analysis/plot_country_scatter_avail_lcoh_5km_15km.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OUT_STEM = "country_scatter_avail_lcoh_5km_15km"

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from gas_benchmark import GAS_EU  # EU-27 gas heat cost from input files (see gas_benchmark.py)
from operating_points import fleet_stats, points
EURUSD = 1.08

LABEL = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI",
    "ESP": "ES", "SWE": "SE", "GBR": "UK",
}
NORDIC = {"SWE", "FIN", "DNK", "EST", "LVA", "LTU"}
SOUTH = {"ESP", "PRT", "ITA", "GRC", "CYP"}

# Paper figure style (manuscript/figures/make_fig_validation.py): 7 in wide, default font sizes,
# 8 pt frameless legend, no top/right spines, 300 dpi. Region = colour AND marker; the validated
# palette's aqua is below 3:1 contrast, so the marker shape and country labels carry it too.
STYLE = {
    "other": {"color": "#2a78d6", "marker": "o"},
    "nordic": {"color": "#eb6834", "marker": "^"},
    "south": {"color": "#1baf7a", "marker": "s"},
}
INK = "#0b0b0b"
MUTED = "#6f6e69"
LS_GAS = (0, (6, 2, 1.5, 2))  # dash-dot
LS_MH = (0, (5, 2))  # dashed
LS_MS = (0, (1, 1.5))  # dotted

# ISO labels, offset in points (ha follows the sign of dx)
LABEL_ISO = {"DEU", "FRA", "ITA", "ESP", "NLD", "GBR", "POL", "BEL"}
LABEL_XY = {  # tuned to the 2026-11-17 sweep positions
    (5, "NLD"): (6, 5),
    (5, "BEL"): (0, -12),
    (5, "DEU"): (0, 9),
    (5, "GBR"): (5, 6),
    (5, "FRA"): (0, -12),
    (5, "ESP"): (6, 0),
    (5, "POL"): (0, 8),
    (5, "ITA"): (7, 0),
    (15, "GBR"): (-7, -1),
    (15, "BEL"): (-7, -3),
    (15, "POL"): (-6, 7),
    (15, "DEU"): (-3, 10),
    (15, "NLD"): (7, 3),
    (15, "FRA"): (-8, -6),
    (15, "ITA"): (7, 1),
    (15, "ESP"): (7, -2),
}


def region(iso: str) -> str:
    if iso in NORDIC:
        return "nordic"
    if iso in SOUTH:
        return "south"
    return "other"


def _fleet_stats(demand: pd.Series, served: pd.Series, lcoh: pd.Series) -> tuple[float, float]:
    dem = float(demand.sum())
    srv = float(served.fillna(0).sum())
    avail = 100.0 * srv / dem if dem > 0 else float("nan")
    w = served.fillna(0)
    mask = (w > 0) & lcoh.notna()
    fleet_lcoh = float((lcoh[mask] * w[mask]).sum() / w[mask].sum()) if mask.any() else float("nan")
    return avail, fleet_lcoh


def country_agg_max_heat_under_gas(km: int) -> tuple[pd.DataFrame, float, float]:
    """Country aggregates at each site's max-heat point (Methods Eq. maxheat) from the sweep."""
    p = points(km)
    rows = []
    for iso, g in p.groupby("iso3_country"):
        demand = float(g["demand"].sum())
        served = float(g["served_heat"].sum())
        if demand <= 0 or served <= 0:
            continue
        m = g["served_heat"] > 0
        lcoh = float((g.loc[m, "lcoh_heat"] * g.loc[m, "served_heat"]).sum() / served)
        rows.append({"iso3": iso, "demand_twh": demand / 1e6, "avail": 100.0 * served / demand, "lcoh": lcoh})
    fa, fl = fleet_stats(p, "heat")
    return pd.DataFrame(rows), fa, fl


def fleet_max_savings(km: int) -> tuple[float, float]:
    """Fleet max-savings point (Methods Eq. maxsav) from the sweep."""
    return fleet_stats(points(km), "sav")


def plot_panel(ax, agg, fa_mh, fl_mh, fa_ms, fl_ms, title, km) -> None:
    plot = agg[agg["demand_twh"] >= 0.5]
    ax.axhline(GAS_EU, color=MUTED, ls=LS_GAS, lw=1.1, zorder=1)
    ax.axvline(fa_mh, color=INK, ls=LS_MH, lw=0.9, zorder=1)
    ax.axvline(fa_ms, color=INK, ls=LS_MS, lw=0.9, zorder=1)
    for _, r in plot.iterrows():
        st = STYLE[region(r["iso3"])]
        ax.scatter(r["avail"], r["lcoh"], s=12 + 1.2 * r["demand_twh"], color=st["color"],
                   marker=st["marker"], edgecolors="white", linewidths=0.6, zorder=3)
        if r["iso3"] in LABEL_ISO:
            dx, dy = LABEL_XY.get((km, r["iso3"]), (6, 3))
            ax.annotate(LABEL.get(r["iso3"], r["iso3"]), (r["avail"], r["lcoh"]), textcoords="offset points",
                        xytext=(dx, dy), ha="right" if dx < 0 else ("center" if dx == 0 else "left"),
                        va="center", fontsize=8, color=INK, zorder=6)
    ax.annotate(f"Fleet max heat\n{fa_mh:.0f}%, €{fl_mh:.0f}", (fa_mh, 1), xycoords=("data", "axes fraction"),
                textcoords="offset points", xytext=(4, -2), ha="left", va="top", fontsize=8, color=INK)
    ax.annotate(f"Fleet max savings\n{fa_ms:.0f}%, €{fl_ms:.0f}", (fa_ms, 1), xycoords=("data", "axes fraction"),
                textcoords="offset points", xytext=(-4, -2), ha="right", va="top", fontsize=8, color=INK)
    ax.set_title(title, loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)


def main() -> None:
    panels = {}
    rows_out = []
    for km in (5, 15):
        mh, fa_mh, fl_mh = country_agg_max_heat_under_gas(km)
        fa_ms, fl_ms = fleet_max_savings(km)
        panels[km] = (mh, fa_mh, fl_mh, fa_ms, fl_ms)
        rows_out.append(mh.assign(buffer_km=km, policy="max_heat_under_gas"))
        print(f"{km} km  max heat {fa_mh:.1f}% / EUR {fl_mh:.0f}   max savings {fa_ms:.1f}% / EUR {fl_ms:.0f}")
    pd.concat(rows_out, ignore_index=True).to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(7, 6), sharex=True, sharey=True)
    for ax, km in zip(axes, (5, 15)):
        plot_panel(ax, *panels[km], f"({'a' if km == 5 else 'b'}) {km} km land buffer", km)
    shown = pd.concat([panels[k][0][panels[k][0]["demand_twh"] >= 0.5] for k in (5, 15)])
    axes[0].set_xlim(np.floor(shown["avail"].min() / 5) * 5 - 2, np.ceil(shown["avail"].max() / 5) * 5 + 3)
    axes[0].set_ylim(np.floor(shown["lcoh"].min() / 10) * 10 - 5, max(GAS_EU, shown["lcoh"].max()) + 15)
    axes[1].set_xlabel("Share of replaceable heat met at max heat (%)")
    for ax in axes:
        ax.set_ylabel("LCOH (€/MWh)")

    handles = [
        Line2D([0], [0], ls="", marker=STYLE[k]["marker"], color=STYLE[k]["color"], markersize=7, label=lab)
        for k, lab in (("other", "Other"), ("nordic", "Nordic and Baltic"), ("south", "Southern Europe"))
    ] + [
        Line2D([0], [0], color=MUTED, ls=LS_GAS, lw=1.1, label=f"EU-27 gas heat €{GAS_EU:.0f}/MWh"),
        Line2D([0], [0], color=INK, ls=LS_MH, lw=0.9, label="Fleet max heat"),
        Line2D([0], [0], color=INK, ls=LS_MS, lw=0.9, label="Fleet max savings"),
    ]
    axes[1].legend(handles=handles, frameon=False, fontsize=8, loc="lower left", ncol=2)
    fig.text(0.99, 0.005, "Bubble area proportional to national replaceable heat demand.", ha="right",
             fontsize=7, color=MUTED)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{OUT_STEM}.{ext}", dpi=300)
    plt.close(fig)
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")


if __name__ == "__main__":
    main()
