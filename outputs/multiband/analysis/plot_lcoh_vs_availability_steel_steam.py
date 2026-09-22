"""LCOH vs availability: iron & steel and steam cracking (5 vs 15 km).

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
GAS93 = 63.25 / 0.85 + (0.202 / 0.85) * 79
ELEC171 = 162.0 / 0.95  # grid electricity ÷ 0.95 RTE (industrial heat battery)
YMAX = 200.0  # show gas + grid-elec reference lines; clip extreme 100%-floor spikes

# Same encoding as fleet Fig. 2 (Okabe–Ito; pattern + marker, not colour-only)
C5 = "#0072B2"
C15 = "#D55E00"
C_MS = "#009E73"
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


def sector_curve(km: int, sec: str) -> pd.DataFrame:
    long = pd.read_csv(OUT / f"fleet_availability_sweep_{km}km_long.csv", low_memory=False)
    if "status" in long.columns:
        long = long[long["status"] == "ok"].copy()
    long = long[long["subsector"] == sec].copy()
    long["floor"] = np.round(pd.to_numeric(long["availability_floor"], errors="coerce"), 2)
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    if long["lcoh"].isna().all():
        long["lcoh"] = pd.to_numeric(long["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    long["served"] = long["heat"] * long["rel"] / 100.0
    long = long.dropna(subset=["floor", "heat", "rel", "lcoh"])

    rows = []
    for fl, g in long.groupby("floor"):
        dem = float(g["heat"].sum())
        srv = float(g["served"].sum())
        mask = g["served"] > 0
        hw = float(
            (g.loc[mask, "lcoh"] * g.loc[mask, "served"]).sum() / g.loc[mask, "served"].sum()
        )
        rows.append(
            {
                "availability_floor": fl,
                "served_pct": 100.0 * srv / dem,
                "hw_LCOH_eur": hw,
                "served_twh": srv / 1e6,
                "demand_twh": dem / 1e6,
                "n_sites": len(g),
            }
        )
    out = pd.DataFrame(rows).sort_values("availability_floor")
    # Fleet surplus vs gas at each floor (max = last point before overbuilding)
    out["surplus"] = out["served_twh"] * (GAS93 - out["hw_LCOH_eur"])
    return out


def max_savings_row(c: pd.DataFrame) -> pd.Series:
    return c.loc[c["surplus"].idxmax()]


def main() -> None:
    curves: dict[tuple[str, int], pd.DataFrame] = {}
    all_rows = []
    for km in (5, 15):
        for sec, label in SECS.items():
            c = sector_curve(km, sec)
            curves[(sec, km)] = c
            all_rows.append(c.assign(sector=label, buffer_km=km))
            ms = max_savings_row(c)
            print(
                f"{km} km {label:22s}  served {c['served_pct'].min():.0f}–"
                f"{c['served_pct'].max():.0f}%  "
                f"LCOH €{c['hw_LCOH_eur'].min():.0f}–{c['hw_LCOH_eur'].iloc[-1]:.0f}  "
                f"max-sav {ms['served_pct']:.0f}% €{ms['hw_LCOH_eur']:.0f}"
            )
    pd.concat(all_rows).to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    # IET single-column width; stack (a)/(b) so the figure is readable at 88 mm.
    fig, axes = plt.subplots(2, 1, figsize=(3.44, 3.55), sharex=True, layout="constrained")

    callouts = {
        ("iron-and-steel", 5, "end"): dict(xytext=(-7, -1), ha="right", va="center"),
        ("iron-and-steel", 15, "end"): dict(xytext=(3, 3), ha="left", va="bottom"),
        ("iron-and-steel", 15, "ms"): dict(xytext=(4, -9), ha="left", va="top"),
        ("petrochemical-steam-cracking", 5, "end"): dict(xytext=(-4, -8), ha="right", va="top"),
        ("petrochemical-steam-cracking", 15, "end"): dict(xytext=(3, 3), ha="left", va="bottom"),
        ("petrochemical-steam-cracking", 15, "ms"): dict(xytext=(4, -9), ha="left", va="top"),
    }

    for ax, sec in zip(axes, SECS):
        ax.axhline(GAS93, color=C_GAS, ls=LS_GAS, lw=1.2, zorder=1)
        ax.axhline(ELEC171, color=C_ELEC, ls=LS_ELEC, lw=1.2, zorder=1)

        for km in (5, 15):
            c = curves[(sec, km)]
            st = KM_STYLE[km]
            plot_vis = c[c["hw_LCOH_eur"] <= YMAX]
            ax.plot(
                plot_vis["served_pct"],
                plot_vis["hw_LCOH_eur"],
                color=st["color"],
                ls=st["ls"],
                lw=1.6,
                marker=st["marker"],
                ms=st["ms"],
                zorder=3,
            )
            end = plot_vis.iloc[-1]
            ax.annotate(
                f'{end["served_pct"]:.0f}% · €{end["hw_LCOH_eur"]:.0f}'
                if km == 5
                else f'{end["hw_LCOH_eur"]:.0f}',
                (end["served_pct"], end["hw_LCOH_eur"]),
                textcoords="offset points",
                fontsize=6.5,
                fontweight="bold",
                color=st["color"],
                zorder=6,
                **callouts[(sec, km, "end")],
            )

        ms = max_savings_row(curves[(sec, 15)])
        ax.scatter(
            [ms["served_pct"]],
            [ms["hw_LCOH_eur"]],
            s=42,
            c=C_MS,
            marker="s",
            edgecolors="#222",
            linewidths=0.4,
            zorder=5,
        )
        ax.annotate(
            f"{ms['served_pct']:.0f}% · €{ms['hw_LCOH_eur']:.0f}",
            (ms["served_pct"], ms["hw_LCOH_eur"]),
            textcoords="offset points",
            fontsize=6.5,
            fontweight="bold",
            color=C_MS,
            zorder=6,
            **callouts[(sec, 15, "ms")],
        )

        ax.set_title(PANEL[sec], fontsize=8, loc="left", pad=2)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 215)
        ax.tick_params(labelsize=7)
        ax.grid(True, ls=":", alpha=0.35, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[-1].set_xlabel("Heat-weighted availability achieved (%)", fontsize=8, labelpad=2)
    fig.supylabel("Heat-weighted avg LCOH (€/MWh)", fontsize=8)

    leg = [
        Line2D([0], [0], color=C5, marker="o", lw=1.6, label="5 km"),
        Line2D([0], [0], color=C15, marker="s", ls="--", lw=1.6, label="15 km"),
        Line2D([0], [0], color=C_GAS, ls=LS_GAS, lw=1.2, label=f"Gas €{GAS93:.0f}"),
        Line2D([0], [0], color=C_ELEC, ls=LS_ELEC, lw=1.2, label=f"Grid elec. €{ELEC171:.0f}"),
        Line2D(
            [0], [0], marker="s", color="w", markerfacecolor=C_MS,
            markeredgecolor="#222", markersize=6, label="Max € savings",
        ),
    ]
    axes[0].legend(
        handles=leg,
        loc="upper left",
        ncol=2,
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
