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

# Okabe–Ito; region encoded by colour AND marker (colour-blind).
# Line patterns match Figs 2–3: dash-dot vs dense dots, not two dashes.
STYLE = {
    "nordic": {"color": "#E69F00", "marker": "^"},
    "south": {"color": "#009E73", "marker": "s"},
    "other": {"color": "#0072B2", "marker": "o"},
}
C_MH = "#CC79A7"  # max heat — same pink as Fig. 2
C_MS = "#D55E00"  # max savings — vermillion (green is already Southern Europe)
C_GAS = "#6A3D9A"
LS_GAS = (0, (5.5, 1.6, 1.2, 1.6))  # dash-dot
LS_MH = (0, (5.0, 1.8))  # long dash
LS_MS = (0, (1.1, 1.3))  # dense dots

# Nudge ISO labels off neighbouring bubbles (offset points)
LABEL_ISO = {"DEU", "FRA", "ITA", "ESP", "NLD", "GBR", "POL", "BEL"}
LABEL_XY = {  # tuned to the 2026-11-17 sweep positions
    (5, "NLD"): (4, 9),
    (5, "BEL"): (-4, -13),
    (5, "DEU"): (-8, 13),
    (5, "GBR"): (9, 9),
    (5, "FRA"): (-3, -13),
    (5, "ESP"): (9, -6),
    (5, "POL"): (2, 11),
    (5, "ITA"): (11, 8),
    (15, "GBR"): (-17, -2),
    (15, "BEL"): (-14, -11),
    (15, "POL"): (-12, 10),
    (15, "DEU"): (-4, 15),
    (15, "NLD"): (13, 4),
    (15, "FRA"): (2, -13),
    (15, "ITA"): (9, 9),
    (15, "ESP"): (9, -8),
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


def plot_panel(
    ax,
    agg: pd.DataFrame,
    fa_mh: float,
    fl_mh: float,
    fa_ms: float,
    fl_ms: float,
    title: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    km: int,
    show_xlabel: bool,
) -> None:
    plot = agg[agg["demand_twh"] >= 0.5].copy()

    ax.axhline(GAS_EU, color=C_GAS, ls=LS_GAS, lw=1.2, zorder=1)
    ax.axvline(fa_mh, color=C_MH, ls=LS_MH, lw=1.2, zorder=1)
    ax.axhline(fl_mh, color=C_MH, ls=LS_MH, lw=1.2, zorder=1)
    ax.axvline(fa_ms, color=C_MS, ls=LS_MS, lw=1.2, zorder=1)
    ax.axhline(fl_ms, color=C_MS, ls=LS_MS, lw=1.2, zorder=1)

    for _, r in plot.iterrows():
        st = STYLE[region(r["iso3"])]
        ax.scatter(
            r["avail"],
            r["lcoh"],
            s=14 + 4.0 * r["demand_twh"],
            facecolors=st["color"],
            edgecolors="white",
            marker=st["marker"],
            linewidths=0.5,
            alpha=0.92,
            zorder=3,
        )

    for _, r in plot.iterrows():
        if r["iso3"] not in LABEL_ISO:
            continue
        dx, dy = LABEL_XY.get((km, r["iso3"]), (4, 3))
        ax.annotate(
            LABEL.get(r["iso3"], r["iso3"]),
            (r["avail"], r["lcoh"]),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=6.5,
            fontweight="bold",
            color="#111",
            zorder=6,
        )

    mh_kw = (
        dict(xytext=(4, -8), ha="left", va="top")
        if km == 15
        else dict(xytext=(-4, -8), ha="right", va="top")
    )
    ax.annotate(
        f"{fa_mh:.0f}% · €{fl_mh:.0f}",
        (fa_mh, ylim[1]),
        textcoords="offset points",
        fontsize=6.5,
        color=C_MH,
        fontweight="bold",
        zorder=5,
        **mh_kw,
    )
    ax.annotate(
        f"{fa_ms:.0f}% · €{fl_ms:.0f}",
        (fa_ms, ylim[0]),
        xytext=(4, 6),
        textcoords="offset points",
        fontsize=6.5,
        color=C_MS,
        fontweight="bold",
        ha="left",
        va="bottom",
        zorder=5,
    )

    ax.set_title(title, fontsize=8, loc="left", pad=2)
    if show_xlabel:
        ax.set_xlabel("Heat served / demand (%)", fontsize=8, labelpad=2)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.tick_params(labelsize=7)
    ax.grid(True, ls=":", alpha=0.35, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def main() -> None:
    panels = {}
    rows_out = []
    for km in (5, 15):
        mh, fa_mh, fl_mh = country_agg_max_heat_under_gas(km)
        fa_ms, fl_ms = fleet_max_savings(km)
        panels[km] = (mh, fa_mh, fl_mh, fa_ms, fl_ms)
        rows_out.append(mh.assign(buffer_km=km, policy="max_heat_under_gas"))
        print(
            f"{km} km  max-heat-under-gas {fa_mh:.1f}% / €{fl_mh:.0f}   "
            f"max-savings {fa_ms:.1f}% / €{fl_ms:.0f}"
        )

    pd.concat(rows_out, ignore_index=True).to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    p5 = panels[5][0][panels[5][0]["demand_twh"] >= 0.5]
    p15 = panels[15][0][panels[15][0]["demand_twh"] >= 0.5]
    xmin = min(float(p5["avail"].min()), float(p15["avail"].min())) - 1
    xmax = max(float(p5["avail"].max()), float(p15["avail"].max())) + 1
    xlim = (xmin, xmax)
    ymax = float(np.ceil(max(p5["lcoh"].max(), p15["lcoh"].max()) / 5) * 5) + 5
    ymin = min(25.0, float(np.floor(min(p5["lcoh"].min(), p15["lcoh"].min()) / 5) * 5) - 2)
    ylim = (ymin, max(ymax, 110.0))

    fig, axes = plt.subplots(2, 1, figsize=(3.44, 3.75), sharex=True, layout="constrained")
    for ax, km, show_x in ((axes[0], 5, False), (axes[1], 15, True)):
        mh, fa_mh, fl_mh, fa_ms, fl_ms = panels[km]
        plot_panel(
            ax, mh, fa_mh, fl_mh, fa_ms, fl_ms,
            f"({'a' if km == 5 else 'b'}) {km} km",
            xlim, ylim, km, show_x,
        )

    fig.supylabel("LCOH of served heat (€/MWh)", fontsize=8)

    leg_handles = [
        Line2D(
            [0], [0], marker="^", color="w",
            markerfacecolor=STYLE["nordic"]["color"],
            markeredgecolor="white", markeredgewidth=0.5,
            markersize=6, label="Nordic / Baltic",
        ),
        Line2D(
            [0], [0], marker="s", color="w",
            markerfacecolor=STYLE["south"]["color"],
            markeredgecolor="white", markeredgewidth=0.5,
            markersize=6, label="Southern Europe",
        ),
        Line2D(
            [0], [0], marker="o", color="w",
            markerfacecolor=STYLE["other"]["color"],
            markeredgecolor="white", markeredgewidth=0.5,
            markersize=6, label="Other",
        ),
        Line2D([0], [0], color=C_GAS, ls=LS_GAS, lw=1.2, label=f"Gas €{GAS_EU:.0f}"),
        Line2D([0], [0], color=C_MH, ls=LS_MH, lw=1.2, label="Fleet max heat"),
        Line2D([0], [0], color=C_MS, ls=LS_MS, lw=1.2, label="Fleet max savings"),
    ]
    fig.legend(
        handles=leg_handles,
        loc="outside upper center",
        ncol=3,
        frameon=False,
        fontsize=6.5,
        handlelength=2.0,
        columnspacing=1.0,
        handletextpad=0.35,
        labelspacing=0.22,
        borderaxespad=0.15,
    )

    png = OUT / f"{OUT_STEM}.png"
    pdf = OUT / f"{OUT_STEM}.pdf"
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Wrote {png}")


if __name__ == "__main__":
    main()
