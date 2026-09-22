"""Sector trade-off scatter: max heat served vs max savings.

Steam cracking, iron & steel, aluminium — 5 km and 15 km side by side.
Filled = max heat under gas price; open = max savings (vs €93/MWh gas heat).

    python outputs/multiband/analysis/plot_sector_scatter_gascap_vs_maxsavings.py
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
OUT_STEM = "sector_scatter_gascap_vs_maxsavings"

GAS93 = 63.25 / 0.85 + (0.202 / 0.85) * 79
EURUSD = 1.08

SECS = [
    ("petrochemical-steam-cracking", "Steam cracking", "#0072B2", "o"),
    ("iron-and-steel", "Iron & steel", "#E69F00", "s"),
    ("aluminum", "Aluminium", "#009E73", "^"),
]


def max_savings_sites(km: int) -> pd.DataFrame:
    long = pd.read_csv(OUT / f"fleet_availability_sweep_{km}km_long.csv", low_memory=False)
    if "status" in long.columns:
        long = long[long["status"] == "ok"].copy()
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    if long["lcoh"].isna().all():
        long["lcoh"] = pd.to_numeric(long["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    long["served"] = long["heat"] * long["rel"] / 100.0
    long["surplus"] = long["served"] * (GAS93 - long["lcoh"])
    long = long.dropna(subset=["source_id", "surplus", "served", "lcoh", "subsector"])
    return long.loc[long.groupby("source_id")["surplus"].idxmax()].copy()


def gas_capped_sites(km: int) -> pd.DataFrame:
    gc = pd.read_csv(OUT / f"gas_capped_step90_{km}km.csv")
    ok = gc[gc["status"] == "ok"].copy() if "status" in gc.columns else gc.copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["served"] = pd.to_numeric(ok["served_mwh"], errors="coerce")
    ok["lcoh"] = pd.to_numeric(ok["LCOH_served_eur_perMWh"], errors="coerce")
    return ok


def sector_stats(df: pd.DataFrame, sec: str) -> dict:
    g = df[df["subsector"] == sec]
    dem = float(g["heat"].sum())
    srv = float(g["served"].fillna(0).sum())
    mask = g["served"].fillna(0) > 0
    hw = float(
        (g.loc[mask, "lcoh"] * g.loc[mask, "served"]).sum() / g.loc[mask, "served"].sum()
    )
    return {
        "demand_twh": dem / 1e6,
        "avail": 100.0 * srv / dem,
        "lcoh": hw,
        "served_twh": srv / 1e6,
    }


def main() -> None:
    rows: list[dict] = []
    panels: dict[int, list] = {}
    for km in (5, 15):
        gc, ms = gas_capped_sites(km), max_savings_sites(km)
        pts = []
        for sid, label, color, marker in SECS:
            g, m = sector_stats(gc, sid), sector_stats(ms, sid)
            pts.append(
                {"sec": sid, "label": label, "color": color, "marker": marker, "gc": g, "ms": m}
            )
            rows.append(
                {
                    "buffer_km": km,
                    "sector": label,
                    "demand_twh": g["demand_twh"],
                    "gc_avail": g["avail"],
                    "gc_lcoh": g["lcoh"],
                    "gc_served_twh": g["served_twh"],
                    "ms_avail": m["avail"],
                    "ms_lcoh": m["lcoh"],
                    "ms_served_twh": m["served_twh"],
                }
            )
            print(
                f"{km} km {label:16s}  GC {g['avail']:.0f}% €{g['lcoh']:.0f}  "
                f"MS {m['avail']:.0f}% €{m['lcoh']:.0f}"
            )
        panels[km] = pts

    pd.DataFrame(rows).to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.4), sharey=True)
    xlim, ylim = (20, 95), (30, 75)

    for ax, km in zip(axes, (5, 15)):
        for p in panels[km]:
            g, m = p["gc"], p["ms"]
            ax.plot(
                [m["avail"], g["avail"]],
                [m["lcoh"], g["lcoh"]],
                color="#bbbbbb",
                lw=1.0,
                zorder=1,
            )
            s = 90 + 2.2 * g["demand_twh"]
            ax.scatter(
                m["avail"],
                m["lcoh"],
                s=s,
                facecolors="white",
                edgecolors=p["color"],
                marker=p["marker"],
                linewidths=1.6,
                zorder=3,
            )
            ax.scatter(
                g["avail"],
                g["lcoh"],
                s=s,
                c=p["color"],
                marker=p["marker"],
                edgecolors="#222",
                linewidths=0.5,
                zorder=4,
            )
            ax.annotate(
                p["label"],
                (g["avail"], g["lcoh"]),
                textcoords="offset points",
                xytext=(6, 5),
                fontsize=7.5,
                color="#222",
            )
            ax.annotate(
                f'{g["avail"]:.0f}% · €{g["lcoh"]:.0f}',
                (g["avail"], g["lcoh"]),
                textcoords="offset points",
                xytext=(6, -9),
                fontsize=6.5,
                color="#000",
            )
            ax.annotate(
                f'{m["avail"]:.0f}% · €{m["lcoh"]:.0f}',
                (m["avail"], m["lcoh"]),
                textcoords="offset points",
                xytext=(-52, -10) if km == 15 else (-48, 6),
                fontsize=6.5,
                color="#666",
            )

        ax.set_title(f"{km} km land buffer", fontsize=11, loc="left")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.grid(True, ls=":", alpha=0.4, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xlabel("Heat served / demand (%)", fontsize=9)

    axes[0].set_ylabel("LCOH of served heat (€/MWh)", fontsize=9)

    leg = [
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor="#0072B2",
            markeredgecolor="#222", markersize=8, label="Steam cracking",
        ),
        Line2D(
            [0], [0], marker="s", color="w", markerfacecolor="#E69F00",
            markeredgecolor="#222", markersize=7.5, label="Iron & steel",
        ),
        Line2D(
            [0], [0], marker="^", color="w", markerfacecolor="#009E73",
            markeredgecolor="#222", markersize=8, label="Aluminium",
        ),
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor="#555",
            markersize=8, label="Max heat (filled)",
        ),
        Line2D(
            [0], [0], marker="o", color="w", markerfacecolor="white",
            markeredgecolor="#555", markeredgewidth=1.5, markersize=8,
            label="Max savings (open)",
        ),
    ]
    fig.suptitle(
        "Sector trade-off — max heat served vs max savings\n"
        f"(under country gas heat price · 2030 costs · max savings vs €{GAS93:.0f}/MWh)",
        fontsize=11.5,
        y=0.98,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.84, bottom=0.24, wspace=0.12)

    leg_artist = fig.legend(
        handles=leg,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.12),
        ncol=3,
        frameon=False,
        fontsize=7.5,
        columnspacing=1.1,
        handletextpad=0.35,
    )
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = fig.transFigure.inverted()
    bb = leg_artist.get_window_extent(renderer)
    leg_bottom = float(inv.transform((bb.x0, bb.y0))[1])

    fig.text(
        0.5,
        leg_bottom - 0.035,
        "Max heat = highest availability with LCOH ≤ country gas heat price.  "
        "Size ∝ demand.  Line: max savings → max heat.\n"
        "5 km: land-bound.  15 km: max heat +8–10 pp heat at +€12–18/MWh vs max savings.",
        ha="center",
        va="top",
        fontsize=7,
        color="#555",
        linespacing=1.3,
    )

    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")


if __name__ == "__main__":
    main()
