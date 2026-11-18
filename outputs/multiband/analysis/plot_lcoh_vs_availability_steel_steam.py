"""LCOH vs availability: iron & steel and steam cracking (5 vs 15 km), availability-target curves.

Shows land capping — 5 km curves stop early on achieved served share;
15 km reaches much higher availability before LCOH rises.

    python outputs/multiband/analysis/plot_lcoh_vs_availability_steel_steam.py
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
OUT_STEM = "lcoh_vs_availability_steel_steam_5km_15km"

EURUSD = 1.08
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from gas_benchmark import GAS_EU  # EU-27 gas heat cost from input files (see gas_benchmark.py)
from operating_points import fleet_stats, points, target_curve
YMAX = 125.0  # €/MWh; room above the gas line for the legend

# Same encoding as fleet Fig. 2 (Okabe–Ito; pattern + marker, not colour-only)
C5 = "#0072B2"
C15 = "#D55E00"
C_MS = "#009E73"
C_MH = "#CC79A7"
C_GAS = "#6A3D9A"
C_ELEC = "#949494"
LS_GAS = (0, (5.5, 1.6, 1.2, 1.6))  # dash-dot
LS_ELEC = (0, (1.1, 1.3))  # dense dots

SECS = {
    "iron-and-steel": "Iron & steel",
    "petrochemical-steam-cracking": "Steam cracking",
}
PANEL = {
    "iron-and-steel": "(a) Iron & steel",
    "petrochemical-steam-cracking": "(b) Steam cracking",
}
KM_STYLE = {
    5: {"color": C5, "ls": "-", "marker": "o", "ms": 4},
    15: {"color": C15, "ls": "--", "marker": "s", "ms": 4},
}


def main() -> None:
    """Same rule as the fleet figure: every site in the sector is asked to reach a common availability
    target (10-100%) and follows it only while its LCOH stays at or below its country gas heat cost.
    Each curve ends at the sector's max-heat point."""
    rows = []
    fig, axes = plt.subplots(2, 1, figsize=(3.44, 3.55), sharex=True, layout="constrained")
    callouts = {  # (sector, km, kind) -> label offset
        ("iron-and-steel", 5, "mh"): dict(xytext=(-5, 8), ha="right", va="bottom"),
        ("iron-and-steel", 15, "mh"): dict(xytext=(4, 6), ha="left", va="bottom"),
        ("iron-and-steel", 15, "ms"): dict(xytext=(4, -9), ha="left", va="top"),
        ("petrochemical-steam-cracking", 5, "mh"): dict(xytext=(-5, 8), ha="right", va="bottom"),
        ("petrochemical-steam-cracking", 15, "mh"): dict(xytext=(4, 6), ha="left", va="bottom"),
        ("petrochemical-steam-cracking", 15, "ms"): dict(xytext=(4, -9), ha="left", va="top"),
    }
    for ax, sec in zip(axes, SECS):
        ax.axhline(GAS_EU, color=C_GAS, ls=LS_GAS, lw=1.2, zorder=1)
        for km in (5, 15):
            st = KM_STYLE[km]
            tc = target_curve(km, subsector=sec)
            rows.append(tc.assign(sector=SECS[sec], buffer_km=km))
            ax.plot(tc["served_pct"], tc["lcoh"], color=st["color"], ls=st["ls"], lw=1.6, marker=st["marker"],
                    ms=3, zorder=3)
            p = points(km)
            p = p[p["subsector"] == sec]
            a_ms, l_ms = fleet_stats(p, "sav")
            a_mh, l_mh = fleet_stats(p, "heat")
            print(f"{km} km {SECS[sec]:15s} max-sav {a_ms:.1f}% EUR {l_ms:.0f}  max-heat {a_mh:.1f}% EUR {l_mh:.0f}")
            mk = st["marker"]
            ax.scatter([a_ms], [l_ms], s=42, c=C_MS, marker=mk, edgecolors="#222", linewidths=0.4, zorder=5)
            ax.scatter([a_mh], [l_mh], s=42, facecolors="white", edgecolors=C_MH, marker=mk, linewidths=1.4,
                       zorder=5)
            for kind, pt, color in (("ms", (a_ms, l_ms), C_MS), ("mh", (a_mh, l_mh), C_MH)):
                kw = callouts.get((sec, km, kind))
                if kw:
                    ax.annotate(f"{pt[0]:.0f}% · €{pt[1]:.0f}", pt, textcoords="offset points", fontsize=6.5,
                                fontweight="bold", color=color, zorder=6, **kw)
        ax.set_title(PANEL[sec], fontsize=8, loc="left", pad=2)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, YMAX)
        ax.tick_params(labelsize=7)
        ax.grid(True, ls=":", alpha=0.35, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    pd.concat(rows).to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    axes[-1].set_xlabel("Heat-weighted availability achieved (%)", fontsize=8, labelpad=2)
    fig.supylabel("Sector LCOH (€/MWh)", fontsize=8)
    leg = [
        Line2D([0], [0], color=C5, marker="o", ms=3, lw=1.6, label="5 km"),
        Line2D([0], [0], color=C15, marker="s", ms=3, ls="--", lw=1.6, label="15 km"),
        Line2D([0], [0], color=C_GAS, ls=LS_GAS, lw=1.2, label=f"Gas €{GAS_EU:.0f}"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=C_MS, markeredgecolor="#222", markersize=6,
               label="Max € savings"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="white", markeredgecolor=C_MH,
               markeredgewidth=1.4, markersize=6, label="Max heat"),
    ]
    axes[0].legend(handles=leg, loc="upper left", ncol=2, frameon=False, fontsize=6.5, handlelength=2.2,
                   columnspacing=0.8, handletextpad=0.35, borderaxespad=0.35, labelspacing=0.22)
    png = OUT / f"{OUT_STEM}.png"
    pdf = OUT / f"{OUT_STEM}.pdf"
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Wrote {png}")


if __name__ == "__main__":
    main()
