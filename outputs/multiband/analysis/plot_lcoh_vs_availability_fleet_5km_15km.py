"""EU fleet LCOH vs availability: 5 km & 15 km fixed-floor curves.

Highlights max € savings and max heat served (under gas heat price).

    python outputs/multiband/analysis/plot_lcoh_vs_availability_fleet_5km_15km.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
OUT_STEM = "lcoh_vs_availability_fleet_avg_5km_15km"

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from gas_benchmark import GAS_EU  # EU-27 gas heat cost from input files (see gas_benchmark.py)
from operating_points import fleet_stats, points
EURUSD = 1.08

# Paper figure style (conference_submissions/manuscript/figures/make_fig_validation.py):
# 7 x 4.2 in, default font sizes, 8 pt frameless legend, no top/right spines, 300 dpi.
# Validated categorical pair (dataviz palette slots 1-2): blue / orange.
C5 = "#2a78d6"  # 5 km
C15 = "#eb6834"  # 15 km
INK = "#0b0b0b"
MUTED = "#6f6e69"  # gas line and neutral legend entries


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


def main() -> None:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    style = {5: dict(color=C5, marker="o", ls="-"), 15: dict(color=C15, marker="s", ls="--")}
    # Label offsets (points) for the max-savings / max-heat values
    callouts = {
        (5, "sav"): (-8, -14), (5, "heat"): (-8, 9),
        (15, "sav"): (8, -14), (15, "heat"): (8, 9),
    }
    for km in (5, 15):
        st = style[km]
        c = load_curve(km).sort_values("served_pct")
        # Keep the curve only up to the gas heat cost: above it, the forced floors that sites
        # cannot reach are solved as max-serve and fleet LCOH jumps by an order of magnitude.
        c = c[c["hw_LCOH_eur"] <= GAS_EU]
        ax.plot(c["served_pct"], c["hw_LCOH_eur"], color=st["color"], ls=st["ls"], marker=st["marker"],
                ms=4, lw=1.5, zorder=2, label=f"{km} km, all sites at the same availability")

        for tag, filled in (("sav", True), ("heat", False)):
            a, l = fleet_stats(points(km), tag)
            print(f"{km} km  max-{tag} {a:.1f}% EUR {l:.0f}")
            ax.scatter([a], [l], s=55, marker=st["marker"], zorder=5, linewidths=1.5,
                       facecolors=st["color"] if filled else "white", edgecolors=st["color"])
            dx, dy = callouts[(km, tag)]
            ax.annotate(f"{a:.0f}%, €{l:.0f}", (a, l), textcoords="offset points", xytext=(dx, dy),
                        ha="right" if dx < 0 else "left", va="center", fontsize=8, color=INK)

    ax.axhline(GAS_EU, color=MUTED, ls=(0, (6, 2, 1.5, 2)), lw=1.2, zorder=1)
    ax.annotate(f"Gas heat €{GAS_EU:.0f}/MWh", (1, GAS_EU), textcoords="offset points", xytext=(0, 4),
                fontsize=8, color=MUTED)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, GAS_EU * 1.15)
    ax.set_xlabel("Share of replaceable heat met (%)")
    ax.set_ylabel("Fleet LCOH (€/MWh)")
    ax.spines[["top", "right"]].set_visible(False)

    handles, _ = ax.get_legend_handles_labels()
    handles += [
        Line2D([0], [0], marker="o", ls="", color=MUTED, markerfacecolor=MUTED, label="Max savings (filled)"),
        Line2D([0], [0], marker="o", ls="", color=MUTED, markerfacecolor="white", markeredgewidth=1.5,
               label="Max heat (open)"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{OUT_STEM}.{ext}", dpi=300)
    plt.close(fig)
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")


if __name__ == "__main__":
    main()
