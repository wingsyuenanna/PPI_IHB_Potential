"""Severe land shortfall: sites with max achieved availability < 50%.

At 15 km almost no sites remain below 50% (Duisburg is the only large one).
The severe pattern is visible at 5 km; most of those sites recover when the
land buffer expands to 15 km.

    python outputs/multiband/analysis/plot_severe_shortfall_lt50.py
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
STEM = "severe_shortfall_lt50"
CAP = 50.0  # MWdc / km²
BINS = [0, 50, 70, 90, 100.01]
BIN_LABELS = ["<50%", "50–70%", "70–90%", "≥90%"]
# Okabe–Ito; colour AND marker (not colour-only)
BIN_STYLE = {
    "<50%": {"color": "#D55E00", "marker": "s", "zorder": 4, "alpha": 0.92, "edge": "#222", "lw": 0.35},
    "50–70%": {"color": "#E69F00", "marker": "^", "zorder": 3, "alpha": 0.9, "edge": "none", "lw": 0},
    "70–90%": {"color": "#0072B2", "marker": "D", "zorder": 2, "alpha": 0.85, "edge": "none", "lw": 0},
    "≥90%": {"color": "#949494", "marker": "o", "zorder": 1, "alpha": 0.40, "edge": "none", "lw": 0},
}


def load_floor100(buf: str, meta: pd.DataFrame) -> pd.DataFrame:
    long = pd.read_csv(OUT / f"fleet_availability_sweep_{buf}_long.csv", low_memory=False)
    if "status" in long.columns:
        long = long[long["status"] == "ok"].copy()
    long["floor"] = np.round(pd.to_numeric(long["availability_floor"], errors="coerce"), 2)
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["S"] = pd.to_numeric(long["S_opt_MW"], errors="coerce")
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["land"] = pd.to_numeric(long["available_land_km2"], errors="coerce")
    f = long[long["floor"] == 1.0][
        ["source_id", "source_name", "rel", "S", "heat", "land"]
    ].copy()
    f["S_max"] = f["land"] * CAP
    f["land_use"] = f["S"] / f["S_max"].replace(0, np.nan)
    f["land_per_twh"] = f["land"] / (f["heat"] / 1e6)
    f["heat_twh"] = f["heat"] / 1e6
    f = f.merge(meta, on="source_id", how="left")
    f["tier"] = pd.cut(f["rel"], bins=BINS, right=False, labels=BIN_LABELS)
    return f


def main() -> None:
    sites = pd.read_csv(
        OUT.parents[2] / "outputs" / "eu_ihb_site_assessment_2024.csv", low_memory=False
    )
    meta = sites[
        ["source_id", "iso3_country", "subsector", "lat", "lon", "solar_capacity_factor"]
    ].copy()
    meta["cf"] = pd.to_numeric(meta["solar_capacity_factor"], errors="coerce")
    meta["lat"] = pd.to_numeric(meta["lat"], errors="coerce")
    meta["lon"] = pd.to_numeric(meta["lon"], errors="coerce")

    f5 = load_floor100("5km", meta)
    f15 = load_floor100("15km", meta)

    low5 = f5[f5["rel"] < 50].copy()
    low15 = f15[f15["rel"] < 50].copy()
    dem5 = float(f5["heat_twh"].sum())
    dem15 = float(f15["heat_twh"].sum())

    # Crosswalk: severe @5 → outcome @15
    x = low5[["source_id", "heat_twh", "rel", "land_per_twh", "cf", "iso3_country", "subsector", "source_name"]].rename(
        columns={"rel": "rel5", "land_per_twh": "land5", "heat_twh": "heat5"}
    )
    x = x.merge(
        f15[["source_id", "rel", "land_per_twh", "heat_twh"]].rename(
            columns={"rel": "rel15", "land_per_twh": "land15", "heat_twh": "heat15"}
        ),
        on="source_id",
        how="left",
    )

    print("=== Severe shortfall (max achieved availability < 50%) ===")
    print(
        f"5 km:  {len(low5)} sites, {low5['heat_twh'].sum():.1f} TWh "
        f"({100 * low5['heat_twh'].sum() / dem5:.0f}% of fleet) · "
        f"HW served {(low5['rel'] * low5['heat']).sum() / low5['heat'].sum():.0f}%"
    )
    print(
        f"15 km: {len(low15)} sites, {low15['heat_twh'].dropna().sum():.1f} TWh "
        f"({100 * low15['heat_twh'].dropna().sum() / dem15:.1f}% of fleet)"
    )
    print("Of <50% @ 5 km sites at 15 km:")
    print(f"  still <50%: {(x['rel15'] < 50).sum()} sites, {x.loc[x['rel15'] < 50, 'heat5'].sum():.1f} TWh")
    print(f"  still <90%: {(x['rel15'] < 90).sum()} sites, {x.loc[x['rel15'] < 90, 'heat5'].sum():.1f} TWh")
    print(f"  reach ≥90%: {(x['rel15'] >= 90).sum()} sites, {x.loc[x['rel15'] >= 90, 'heat5'].sum():.1f} TWh")

    # Site table
    out = f5[
        [
            "source_id",
            "source_name",
            "iso3_country",
            "subsector",
            "lat",
            "lon",
            "heat_twh",
            "land_per_twh",
            "cf",
            "rel",
            "tier",
        ]
    ].rename(columns={"rel": "rel5", "land_per_twh": "land5", "tier": "tier5"})
    out = out.merge(
        f15[["source_id", "rel", "land_per_twh", "tier"]].rename(
            columns={"rel": "rel15", "land_per_twh": "land15", "tier": "tier15"}
        ),
        on="source_id",
        how="left",
    )
    out["severe5"] = out["rel5"] < 50
    out["severe15"] = out["rel15"] < 50
    out.to_csv(OUT / f"{STEM}_by_site.csv", index=False)

    # Country rollup for severe @5
    rows = []
    for iso, g in low5.groupby("iso3_country"):
        rows.append(
            {
                "iso3": iso,
                "severe5_twh": g["heat_twh"].sum(),
                "n": len(g),
                "hw_rel5": (g["rel"] * g["heat"]).sum() / g["heat"].sum(),
                "med_land5": g["land_per_twh"].median(),
                "med_cf": g["cf"].median(),
                "national_twh": f5.loc[f5["iso3_country"] == iso, "heat_twh"].sum(),
            }
        )
    cagg = pd.DataFrame(rows)
    cagg["share_pct"] = 100 * cagg["severe5_twh"] / cagg["national_twh"]
    cagg = cagg.sort_values("severe5_twh", ascending=False)
    cagg.to_csv(OUT / f"{STEM}_by_country.csv", index=False)

    n15 = int((f15["rel"] < 50).sum())
    twh15 = float(f15.loc[f15["rel"] < 50, "heat_twh"].dropna().sum())
    # Stacked, column width. Tall enough that equal-aspect maps fill the width
    # (short canvas letterboxed the maps and left side gaps).
    fig, axes = plt.subplots(
        2, 1, figsize=(3.44, 4.35), sharex=True, sharey=True, layout="constrained"
    )

    def map_panel(ax, df: pd.DataFrame, title: str, show_xlabel: bool) -> None:
        plot = df.dropna(subset=["lat", "lon", "rel"])
        for lab in reversed(BIN_LABELS):
            st = BIN_STYLE[lab]
            sub = plot[plot["tier"] == lab]
            if not len(sub):
                continue
            scale = 2.4 if lab == "≥90%" else 3.4
            ax.scatter(
                sub["lon"],
                sub["lat"],
                s=6 + scale * sub["heat_twh"].fillna(0),
                c=st["color"],
                marker=st["marker"],
                alpha=st["alpha"],
                edgecolors=st["edge"],
                linewidths=st["lw"],
                zorder=st["zorder"],
            )
        ax.set_xlim(-11, 31)
        ax.set_ylim(35, 61)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, loc="left", fontsize=8, pad=2)
        ax.set_ylabel("Latitude", fontsize=8)
        if show_xlabel:
            ax.set_xlabel("Longitude", fontsize=8, labelpad=2)
        ax.tick_params(labelsize=7)
        ax.grid(True, ls=":", alpha=0.35, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    map_panel(
        axes[0],
        f5,
        f"(a) 5 km  ·  {len(low5)} sites <50% ({low5['heat_twh'].sum():.0f} TWh)",
        False,
    )
    map_panel(
        axes[1],
        f15,
        f"(b) 15 km  ·  {n15} sites <50% ({twh15:.0f} TWh)",
        True,
    )

    fig.legend(
        handles=[
            Line2D(
                [0], [0],
                marker=BIN_STYLE[lab]["marker"],
                color="w",
                markerfacecolor=BIN_STYLE[lab]["color"],
                markeredgecolor="#222" if lab == "<50%" else "none",
                markeredgewidth=0.4,
                markersize=6,
                label=lab,
            )
            for lab in BIN_LABELS
        ],
        loc="outside upper center",
        ncol=4,
        frameon=False,
        fontsize=6.5,
        handletextpad=0.3,
        columnspacing=1.0,
        borderaxespad=0.12,
    )

    png = OUT / f"{STEM}.png"
    pdf = OUT / f"{STEM}.pdf"
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Wrote {png}")
    print(f"Wrote {OUT / f'{STEM}_by_site.csv'}")
    print(f"Wrote {OUT / f'{STEM}_by_country.csv'}")


if __name__ == "__main__":
    main()
