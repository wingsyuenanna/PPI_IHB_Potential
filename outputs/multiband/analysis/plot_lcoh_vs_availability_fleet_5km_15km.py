"""EU fleet LCOH vs heat met: 5 km and 15 km.

Every site is asked to reach the same availability target, 10% then 20% ... 100% (one dot each).
A site moves up only while that level costs no more than its country's gas heat cost, otherwise it
stays at its last level below gas. At the 100% target every site is at its own max-heat point, so
each curve ends on the fleet max-heat point. Markers: max savings and max heat.

    python outputs/multiband/analysis/plot_lcoh_vs_availability_fleet_5km_15km.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
OUT_STEM = "lcoh_vs_availability_fleet_avg_5km_15km"

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from gas_benchmark import GAS_EU  # EU-27 gas heat cost from input files (see gas_benchmark.py)
from operating_points import fleet_stats, points, target_curve
EURUSD = 1.08
Y_MAX = 125  # €/MWh; room above the gas line for the legend

# Shared gas / grid-elec colors with EU-27 bar chart; curve markers distinct
C5 = "#0072B2"  # blue — 5 km
C15 = "#D55E00"  # vermillion — 15 km
C_MS = "#009E73"  # green — max € savings
C_MH = "#CC79A7"  # pink — max heat
C_GAS = "#6A3D9A"  # purple — gas heat
C_ELEC = "#949494"  # light medium gray — grid electricity / IHB (soft, fully opaque)


def _fleet(demand: pd.Series, served: pd.Series, lcoh: pd.Series) -> tuple[float, float]:
    dem = float(demand.sum())
    srv = float(served.fillna(0).sum())
    avail = 100.0 * srv / dem if dem > 0 else float("nan")
    w = served.fillna(0)
    mask = (w > 0) & lcoh.notna()
    hw = float((lcoh[mask] * w[mask]).sum() / w[mask].sum()) if mask.any() else float("nan")
    return avail, hw


def load_curve(km: int) -> pd.DataFrame:
    return pd.read_csv(OUT / f"fleet_availability_sweep_{km}km_by_floor.csv")


def max_heat_point(km: int) -> tuple[float, float]:
    """Fleet max-heat point on the sweep grid (Methods Eq. maxheat), all 2,192 sites as demand."""
    return fleet_stats(points(km), "heat")


def max_savings_point(km: int) -> tuple[float, float]:
    """Fleet max-savings point on the sweep grid (Methods Eq. maxsav), all 2,192 sites as demand."""
    return fleet_stats(points(km), "sav")


Y_LIM = (0, 125)  # €/MWh; room above the gas line for the legend


def main() -> None:
    # IET single-column width (~88 mm). 600 dpi line art for print.
    fig, ax = plt.subplots(figsize=(3.44, 2.32), layout="constrained")
    style = {5: {"color": C5, "ls": "-", "marker": "o"}, 15: {"color": C15, "ls": "--", "marker": "s"}}
    callouts = {  # max savings / max heat value labels (offset points)
        (5, "ms"): dict(xytext=(-2, 14), ha="right", va="bottom"),
        (5, "mh"): dict(xytext=(-2, 19), ha="right", va="bottom"),
        (15, "ms"): dict(xytext=(5, -9), ha="left", va="top"),
        (15, "mh"): dict(xytext=(5, -9), ha="left", va="top"),
    }
    for km in (5, 15):
        st = style[km]
        tc = target_curve(km)
        ax.plot(tc["served_pct"], tc["lcoh"], color=st["color"], ls=st["ls"], marker=st["marker"], ms=3,
                lw=1.5, zorder=3)
        if km == 15:  # label the target of each dot (100% is the max-heat point)
            for _, r in tc[tc["target"] < 0.95].iterrows():
                low = r["target"] < 0.55  # below the curve where the 5 km curve runs just above
                ax.annotate(f"{r['target']*100:.0f}%", (r["served_pct"], r["lcoh"]), textcoords="offset points",
                            xytext=(0, -5) if low else (-2, 4), ha="center" if low else "right",
                            va="top" if low else "bottom", fontsize=5, color="#555")

        a_ms, l_ms = max_savings_point(km)
        a_mh, l_mh = max_heat_point(km)
        print(f"{km} km  max-sav {a_ms:.1f}% EUR {l_ms:.0f}  max-heat {a_mh:.1f}% EUR {l_mh:.0f}")
        mk = st["marker"]
        ax.scatter([a_ms], [l_ms], s=42, c=C_MS, marker=mk, edgecolors="#222", linewidths=0.4, zorder=5)
        ax.scatter([a_mh], [l_mh], s=42, facecolors="white", edgecolors=C_MH, marker=mk, linewidths=1.4, zorder=5)
        for kind, pt, color in (("ms", (a_ms, l_ms), C_MS), ("mh", (a_mh, l_mh), C_MH)):
            ax.annotate(f"{pt[0]:.0f}% · €{pt[1]:.0f}", xy=pt, textcoords="offset points", fontsize=6.5,
                        fontweight="bold", color=color, zorder=6, **callouts[(km, kind)])

    LS_GAS = (0, (5.5, 1.6, 1.2, 1.6))
    ax.axhline(GAS_EU, color=C_GAS, ls=LS_GAS, lw=1.2, zorder=1)
    ax.set_xlim(0, 100)
    ax.set_ylim(*Y_LIM)
    ax.set_xlabel("Heat-weighted availability achieved (%)", fontsize=8, labelpad=2)
    ax.set_ylabel("Fleet LCOH (€/MWh)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, ls=":", alpha=0.35, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    leg = [
        Line2D([0], [0], color=C5, marker="o", ms=3, lw=1.5, label="5 km"),
        Line2D([0], [0], color=C15, marker="s", ms=3, ls="--", lw=1.5, label="15 km"),
        Line2D([0], [0], color=C_GAS, ls=LS_GAS, lw=1.2, label=f"Gas €{GAS_EU:.0f}"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=C_MS, markeredgecolor="#222", markersize=6,
               label="Max € savings"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="white", markeredgecolor=C_MH,
               markeredgewidth=1.4, markersize=6, label="Max heat"),
    ]
    ax.legend(handles=leg, loc="upper left", ncol=2, frameon=False, fontsize=6.5, handlelength=2.2,
              columnspacing=0.8, handletextpad=0.35, borderaxespad=0.35, labelspacing=0.22)
    ax.annotate("Dot labels: availability target asked of every site", (0.99, 0.02), xycoords="axes fraction",
                ha="right", va="bottom", fontsize=5, color="#555")

    png = OUT / f"{OUT_STEM}.png"
    pdf = OUT / f"{OUT_STEM}.pdf"
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Wrote {png}")


if __name__ == "__main__":
    main()
