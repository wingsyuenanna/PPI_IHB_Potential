"""Land-constraint analysis at 15 km land buffer.

Identifies sites where on-site solar still cannot meet a 90% availability
target (hard shortfall), vs land-capped sites that can reach ≥90% but not
full demand (soft shortfall).

    python outputs/multiband/analysis/plot_land_constraint_15km.py
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
STEM = "land_constraint_15km"
CAP = 50.0  # MWdc / km²


def at_floor(long: pd.DataFrame, meta: pd.DataFrame, fl: float) -> pd.DataFrame:
    d = long[long["floor"] == fl][
        ["source_id", "rel", "lcoh", "S", "heat", "land", "spl", "met"]
    ].copy()
    d = d.merge(meta, on="source_id", how="left")
    d["mw"] = d["heat"] / 8760
    d["S_max"] = d["land"] * CAP
    d["land_use"] = d["S"] / d["S_max"].replace(0, np.nan)
    d["land_per_twh"] = d["land"] / (d["heat"] / 1e6)
    d["heat_twh"] = d["heat"] / 1e6
    return d


def main() -> None:
    long = pd.read_csv(OUT / "fleet_availability_sweep_15km_long.csv", low_memory=False)
    if "status" in long.columns:
        long = long[long["status"] == "ok"].copy()
    long["floor"] = np.round(pd.to_numeric(long["availability_floor"], errors="coerce"), 2)
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    long["S"] = pd.to_numeric(long["S_opt_MW"], errors="coerce")
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["land"] = pd.to_numeric(long["available_land_km2"], errors="coerce")
    long["spl"] = pd.to_numeric(long["solar_per_load_MWdc_per_MWth"], errors="coerce")
    long["met"] = long["met_availability_target"].astype(str).str.lower().isin(["true", "1"])

    sites = pd.read_csv(
        OUT.parents[2] / "outputs" / "eu_ihb_site_assessment_2024.csv", low_memory=False
    )
    meta = sites[
        ["source_id", "source_name", "iso3_country", "subsector", "lat", "lon", "solar_capacity_factor"]
    ].copy()
    meta["cf"] = pd.to_numeric(meta["solar_capacity_factor"], errors="coerce")
    meta["lat"] = pd.to_numeric(meta["lat"], errors="coerce")
    meta["lon"] = pd.to_numeric(meta["lon"], errors="coerce")

    f90 = at_floor(long, meta, 0.9)
    f100 = at_floor(long, meta, 1.0)

    f100["land_capped_100"] = (f100["land_use"] >= 0.95) & (f100["rel"] < 99)
    miss = f90.loc[~f90["met"], ["source_id"]].assign(miss90=True)
    f100 = f100.merge(miss, on="source_id", how="left")
    f100["miss90"] = f100["miss90"].fillna(False).astype(bool)
    f100["hard_shortfall"] = f100["miss90"]
    f100["soft_shortfall"] = f100["land_capped_100"] & ~f100["hard_shortfall"]

    dem = float(f100["heat"].sum())
    hard_twh = float(f100.loc[f100["hard_shortfall"], "heat"].sum() / 1e6)
    soft_twh = float(f100.loc[f100["soft_shortfall"], "heat"].sum() / 1e6)
    print("=== 15 km land constraint ===")
    print(f"Fleet demand: {dem/1e6:.1f} TWh")
    print(
        f"HARD (cannot meet 90%): {f100['hard_shortfall'].sum()} sites, "
        f"{hard_twh:.1f} TWh ({100*hard_twh/(dem/1e6):.0f}%)"
    )
    print(
        f"SOFT (≥90% possible, not ~100%): {f100['soft_shortfall'].sum()} sites, "
        f"{soft_twh:.1f} TWh ({100*soft_twh/(dem/1e6):.0f}%)"
    )

    rows = []
    for iso, g in f100.groupby("iso3_country"):
        h = g[g["hard_shortfall"]]
        rows.append(
            {
                "iso3": iso,
                "demand_twh": g["heat"].sum() / 1e6,
                "hard_twh": h["heat"].sum() / 1e6,
                "hard_share_pct": 100 * h["heat"].sum() / g["heat"].sum(),
                "n_hard": int(len(h)),
                "hw_max_served_hard": (
                    (h["rel"] * h["heat"]).sum() / h["heat"].sum() if len(h) else np.nan
                ),
                "med_cf": g["cf"].median(),
            }
        )
    cagg = pd.DataFrame(rows).sort_values("hard_twh", ascending=False)

    out_sites = f100[
        [
            "source_id",
            "source_name",
            "iso3_country",
            "subsector",
            "lat",
            "lon",
            "heat_twh",
            "land",
            "land_per_twh",
            "cf",
            "rel",
            "lcoh",
            "spl",
            "S",
            "S_max",
            "land_use",
            "hard_shortfall",
            "soft_shortfall",
            "land_capped_100",
        ]
    ].copy()
    out_sites = out_sites.merge(
        f90[["source_id", "met", "rel"]].rename(columns={"met": "met90", "rel": "rel90"}),
        on="source_id",
    )
    out_sites.to_csv(OUT / f"{STEM}_by_site.csv", index=False)
    cagg.to_csv(OUT / f"{STEM}_by_country.csv", index=False)

    # --- figure ---
    fig = plt.figure(figsize=(10.5, 8.0))
    gs = fig.add_gridspec(
        2, 2, height_ratios=[1.2, 1], hspace=0.32, wspace=0.28,
        left=0.07, right=0.98, top=0.88, bottom=0.08,
    )

    axm = fig.add_subplot(gs[0, :])
    plot = f100.dropna(subset=["lat", "lon"])
    axm.scatter(
        plot["lon"], plot["lat"], s=4 + 3 * plot["heat_twh"],
        c="#cccccc", alpha=0.45, linewidths=0, zorder=1,
    )
    soft = plot[plot["soft_shortfall"]]
    hardp = plot[plot["hard_shortfall"]]
    if len(soft):
        axm.scatter(
            soft["lon"], soft["lat"], s=10 + 4 * soft["heat_twh"],
            c="#E69F00", alpha=0.85, edgecolors="#333", linewidths=0.3, zorder=2,
        )
    if len(hardp):
        axm.scatter(
            hardp["lon"], hardp["lat"], s=14 + 5 * hardp["heat_twh"],
            c="#D55E00", alpha=0.9, edgecolors="#111", linewidths=0.4, zorder=3,
        )
        for _, r in hardp.nlargest(8, "heat_twh").iterrows():
            short = (
                str(r["source_name"])
                .replace(" steel plant", "")
                .replace("Chemical Co.", "")[:22]
            )
            axm.annotate(
                f"{short}\n{r['heat_twh']:.0f} TWh",
                (r["lon"], r["lat"]),
                textcoords="offset points",
                xytext=(5, 4),
                fontsize=6,
                color="#333",
            )
    axm.set_xlim(-12, 32)
    axm.set_ylim(34, 62)
    axm.set_xlabel("Longitude")
    axm.set_ylabel("Latitude")
    axm.set_title(
        "Sites that remain land-constrained even with a 15 km buffer",
        loc="left",
        fontsize=11,
    )
    axm.grid(True, ls=":", alpha=0.35)
    axm.legend(
        handles=[
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#cccccc",
                   markersize=6, label="Other sites"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#E69F00",
                   markeredgecolor="#333", markersize=7,
                   label="Soft: ≥90% possible, land caps ~100%"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#D55E00",
                   markeredgecolor="#111", markersize=8,
                   label="Hard: cannot meet 90% @ 15 km"),
        ],
        loc="upper left",
        fontsize=7.5,
        frameon=True,
        fancybox=False,
        edgecolor="#ccc",
    )

    # Land intensity vs CF
    ax1 = fig.add_subplot(gs[1, 0])
    ok = plot[(plot["land_per_twh"] > 0) & (plot["cf"] > 0)].copy()
    base = ok[~ok["land_capped_100"]]
    ax1.scatter(
        base["cf"] * 100, np.clip(base["land_per_twh"], 0, 2000),
        s=8 + 3 * base["heat_twh"], c="#bbbbbb", alpha=0.45, linewidths=0, zorder=1,
    )
    if soft is not None and len(ok[ok["soft_shortfall"]]):
        s2 = ok[ok["soft_shortfall"]]
        ax1.scatter(
            s2["cf"] * 100, np.clip(s2["land_per_twh"], 0, 2000),
            s=12 + 4 * s2["heat_twh"], c="#E69F00", alpha=0.85,
            edgecolors="#333", linewidths=0.3, zorder=2,
        )
    if len(ok[ok["hard_shortfall"]]):
        h2 = ok[ok["hard_shortfall"]]
        ax1.scatter(
            h2["cf"] * 100, np.clip(h2["land_per_twh"], 0, 2000),
            s=16 + 5 * h2["heat_twh"], c="#D55E00", alpha=0.9,
            edgecolors="#111", linewidths=0.4, zorder=3,
        )
    ax1.set_xlabel("Solar capacity factor (%)")
    ax1.set_ylabel("Land @ 15 km / TWh demand (km²/TWh)")
    ax1.set_title("High heat + low land/TWh + weaker sun", loc="left", fontsize=10)
    ax1.set_xlim(8, 24)
    ax1.set_ylim(0, 600)
    ax1.grid(True, ls=":", alpha=0.35)

    # Country bars
    ax2 = fig.add_subplot(gs[1, 1])
    top = cagg[cagg["hard_twh"] >= 1].sort_values("hard_twh", ascending=True).tail(10)
    ax2.barh(top["iso3"], top["demand_twh"], color="#dddddd", alpha=0.85, label="National demand")
    ax2.barh(top["iso3"], top["hard_twh"], color="#D55E00", alpha=0.9, label="Hard shortfall")
    for _, r in top.iterrows():
        ax2.text(
            r["hard_twh"] + 0.8, r["iso3"], f'{r["hard_share_pct"]:.0f}%',
            va="center", fontsize=7, color="#444",
        )
    ax2.set_xlabel("Process heat (TWh/y)")
    ax2.set_title("Hard shortfall by country (≥1 TWh)", loc="left", fontsize=10)
    ax2.legend(fontsize=7, loc="lower right", frameon=False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.suptitle(
        "Land constraint at 15 km — on-site solar cannot meet high availability everywhere\n"
        f"Hard shortfall: {int(f100['hard_shortfall'].sum())} sites · {hard_twh:.0f} TWh "
        f"({100*hard_twh/(dem/1e6):.0f}% of EU replaceable heat) · "
        f"HW max served ~{(f100.loc[f100.hard_shortfall,'rel']*f100.loc[f100.hard_shortfall,'heat']).sum()/f100.loc[f100.hard_shortfall,'heat'].sum():.0f}%",
        fontsize=11.5,
        y=0.98,
    )
    fig.savefig(OUT / f"{STEM}.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"Wrote {OUT / f'{STEM}.png'}")
    print(f"Wrote {OUT / f'{STEM}_by_site.csv'}")
    print(f"Wrote {OUT / f'{STEM}_by_country.csv'}")


if __name__ == "__main__":
    main()
