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
from gas_benchmark import GAS_EU, ELEC_EU  # EU-27 gas heat cost from input files (see gas_benchmark.py)
from operating_points import fleet_stats, points
EURUSD = 1.08
Y_MAX = 215  # €/MWh; higher fixed-floor points are labelled at the top edge

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


def main() -> None:
    # IET single-column width (~88 mm). 600 dpi line art for print.
    fig, ax = plt.subplots(figsize=(3.44, 2.32), layout="constrained")

    style = {
        5: {"color": C5, "ls": "-", "marker": "o", "ms": 4},
        15: {"color": C15, "ls": "--", "marker": "s", "ms": 4},
    }
    # Compact number labels next to markers (shape already encodes 5 vs 15 km)
    callouts = {
        (5, "ms"): dict(xytext=(-4, -9), ha="right", va="top"),
        (5, "mh"): dict(xytext=(-5, 8), ha="right", va="bottom"),
        (15, "ms"): dict(xytext=(5, -9), ha="left", va="top"),
        (15, "mh"): dict(xytext=(4, -10), ha="left", va="top"),
    }
    for km in (5, 15):
        c = load_curve(km).sort_values("served_pct")
        st = style[km]
        ax.plot(
            c["served_pct"],
            c["hw_LCOH_eur"],
            color=st["color"],
            ls=st["ls"],
            marker=st["marker"],
            ms=st["ms"],
            lw=1.6,
            zorder=2,
            label=f"{km} km (fixed floor)",
        )
        # Label where the curve leaves the plot (fixed floors that sites cannot reach are solved
        # as max-serve, so fleet LCOH jumps off scale), else the last point.
        off = c[c["hw_LCOH_eur"] > Y_MAX]
        if len(off):
            first = off.iloc[0]
            ax.annotate(
                f'↑ €{first["hw_LCOH_eur"]:.0f} at {first["served_pct"]:.0f}%',
                (first["served_pct"], Y_MAX),
                textcoords="offset points",
                xytext=(-6, -10) if km == 5 else (6, -24),
                ha="right" if km == 5 else "left",
                fontsize=6.5,
                fontweight="bold",
                color=st["color"],
                annotation_clip=False,
            )
        else:
            end = c.iloc[-1]
            ax.annotate(
                f'{end["hw_LCOH_eur"]:.0f}',
                (end["served_pct"], end["hw_LCOH_eur"]),
                textcoords="offset points",
                xytext=(3, 3),
                fontsize=7,
                fontweight="bold",
                color=st["color"],
            )

        a_ms, l_ms = max_savings_point(km)
        a_mh, l_mh = max_heat_point(km)
        print(f"{km} km  max-sav {a_ms:.1f}% €{l_ms:.0f}  max-heat {a_mh:.1f}% €{l_mh:.0f}")

        mk = "o" if km == 5 else "s"
        ax.scatter(
            [a_ms], [l_ms], s=42, c=C_MS, marker=mk, edgecolors="#222",
            linewidths=0.4, zorder=5,
        )
        ax.scatter(
            [a_mh], [l_mh], s=42, facecolors="white", edgecolors=C_MH, marker=mk,
            linewidths=1.4, zorder=5,
        )
        for kind, pt, color in (
            ("ms", (a_ms, l_ms), C_MS),
            ("mh", (a_mh, l_mh), C_MH),
        ):
            kw = callouts[(km, kind)]
            ax.annotate(
                f"{pt[0]:.0f}% · €{pt[1]:.0f}",
                xy=pt,
                textcoords="offset points",
                fontsize=6.5,
                fontweight="bold",
                color=color,
                zorder=6,
                **kw,
            )

    # Distinct dash patterns (not colour-only): gas dash-dot, grid densely dotted.
    LS_GAS = (0, (5.5, 1.6, 1.2, 1.6))
    LS_ELEC = (0, (1.1, 1.3))
    ax.axhline(GAS_EU, color=C_GAS, ls=LS_GAS, lw=1.2, zorder=1)
    ax.axhline(ELEC_EU, color=C_ELEC, ls=LS_ELEC, lw=1.2, zorder=1)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, Y_MAX)
    ax.set_xlabel("Heat-weighted availability achieved (%)", fontsize=8, labelpad=2)
    ax.set_ylabel("Fleet LCOH (€/MWh)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, ls=":", alpha=0.35, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    leg = [
        Line2D([0], [0], color=C5, marker="o", lw=1.6, label="5 km"),
        Line2D([0], [0], color=C15, marker="s", ls="--", lw=1.6, label="15 km"),
        Line2D([0], [0], color=C_GAS, ls=LS_GAS, lw=1.2, label=f"Gas €{GAS_EU:.0f}"),
        Line2D([0], [0], color=C_ELEC, ls=LS_ELEC, lw=1.2, label=f"Grid elec. €{ELEC_EU:.0f}"),
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor=C_MS,
            markeredgecolor="#222", markersize=6, label="Max € savings",
        ),
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor="white",
            markeredgecolor=C_MH, markeredgewidth=1.4, markersize=6, label="Max heat",
        ),
    ]
    ax.legend(
        handles=leg,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),  # below the axes, clear of the off-scale labels
        ncol=3,
        frameon=False,
        fontsize=6.5,
        handlelength=2.2,
        columnspacing=0.8,
        handletextpad=0.35,
        borderaxespad=0.35,
        labelspacing=0.22,
    )

    png = OUT / f"{OUT_STEM}.png"
    pdf = OUT / f"{OUT_STEM}.pdf"
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Wrote {png}")


if __name__ == "__main__":
    main()
