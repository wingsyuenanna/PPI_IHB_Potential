"""Side-by-side NUTS2 choropleths: heat-weighted availability & LCOH (5 km).

Facilities lack NUTS2 codes — assign via lat/lon point-in-polygon (GISCO 2021),
with a small buffer join for coastal misses.

Aggregation (same as country maps):
  availability = 100 * Σserved / Σdemand
  LCOH (€/MWh) = Σ(LCOH_served × served) / Σserved   [EURUSD=1.08]

    python outputs/multiband/analysis/plot_nuts2_choropleth_5km.py
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import cm
from matplotlib.colors import Normalize

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SCENARIO = "land_5km_ss_2030_liion"
EURUSD = 1.08
OUT_STEM = "nuts2_choropleth_avail_lcoh_5km"
NUTS_CACHE = OUT / "NUTS_RG_10M_2021_4326_LEVL_2.geojson"
NUTS_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
    "NUTS_RG_10M_2021_4326_LEVL_2.geojson"
)

# Compact Europe frame (less empty sea)
XLIM = (-11, 30)
YLIM = (35, 70)


def load_nuts2() -> gpd.GeoDataFrame:
    if not NUTS_CACHE.exists():
        print(f"Downloading NUTS2 → {NUTS_CACHE.name}")
        req = urllib.request.Request(NUTS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            NUTS_CACHE.write_bytes(r.read())
    nuts = gpd.read_file(NUTS_CACHE)
    return nuts[["NUTS_ID", "NAME_LATN", "CNTR_CODE", "geometry"]].copy()


def load_sites() -> gpd.GeoDataFrame:
    df = pd.read_csv(ROOT / f"outputs/multiband/{SCENARIO}/by_facility.csv")
    ok = df[df["status"] == "ok"].copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["rel"] = pd.to_numeric(ok["Reliability_%"], errors="coerce")
    ok["served"] = ok["rel"] / 100.0 * ok["heat"]
    ok["lcoh_eur"] = pd.to_numeric(ok["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    return gpd.GeoDataFrame(
        ok,
        geometry=gpd.points_from_xy(ok["lon"], ok["lat"]),
        crs="EPSG:4326",
    )


def assign_nuts2(sites: gpd.GeoDataFrame, nuts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Within-join, then nearest within ~15 km for unmatched coastal points."""
    joined = gpd.sjoin(sites, nuts, how="left", predicate="within")
    miss = joined["NUTS_ID"].isna()
    n_miss = int(miss.sum())
    if n_miss:
        miss_idx = joined.index[miss]
        miss_pts = sites.loc[miss_idx].to_crs(3035)
        nuts_p = nuts.to_crs(3035)
        near = gpd.sjoin_nearest(
            miss_pts,
            nuts_p,
            how="left",
            max_distance=15_000,  # metres
            distance_col="_dist_m",
        )
        if "index_right" in near.columns:
            near = near.drop(columns="index_right")
        # align back to joined row order
        near = near.reindex(miss_idx)
        joined.loc[miss_idx, ["NUTS_ID", "NAME_LATN", "CNTR_CODE"]] = near[
            ["NUTS_ID", "NAME_LATN", "CNTR_CODE"]
        ].to_numpy()
        still = int(joined["NUTS_ID"].isna().sum())
        print(
            f"NUTS2 join: {len(sites) - n_miss} within, "
            f"{n_miss - still} buffered (≤15 km), {still} unmatched"
        )
    else:
        print(f"NUTS2 join: {len(sites)} within, 0 unmatched")
    return joined


def nuts2_aggregates(joined: gpd.GeoDataFrame) -> pd.DataFrame:
    g = joined.dropna(subset=["NUTS_ID"]).copy()
    rows = []
    for nuts_id, sub in g.groupby("NUTS_ID"):
        demand = float(sub["heat"].sum())
        served = float(sub["served"].sum())
        lcoh = (
            float((sub["lcoh_eur"] * sub["served"]).sum() / served) if served > 0 else float("nan")
        )
        rows.append(
            {
                "NUTS_ID": nuts_id,
                "NAME_LATN": sub["NAME_LATN"].iloc[0],
                "CNTR_CODE": sub["CNTR_CODE"].iloc[0],
                "demand_twh": demand / 1e6,
                "served_twh": served / 1e6,
                "availability_pct": 100.0 * served / demand if demand > 0 else float("nan"),
                "lcoh_eur_per_mwh": lcoh,
                "n_sites": len(sub),
            }
        )
    return pd.DataFrame(rows).sort_values("demand_twh", ascending=False)


def main() -> None:
    nuts = load_nuts2()
    sites = load_sites()
    joined = assign_nuts2(sites, nuts)
    agg = nuts2_aggregates(joined)
    agg.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    gdf = nuts.merge(agg, on="NUTS_ID", how="left", suffixes=("", "_agg"))
    # prefer NAME from nuts file
    if "NAME_LATN_agg" in gdf.columns:
        gdf = gdf.drop(columns=["NAME_LATN_agg", "CNTR_CODE_agg"], errors="ignore")
    has_data = gdf["availability_pct"].notna()

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.5, 4.2),
        gridspec_kw={"wspace": 0.08},
    )

    # basemap: all NUTS2 in frame
    nuts_clip = nuts.cx[XLIM[0] : XLIM[1], YLIM[0] : YLIM[1]]

    # --- Availability ---
    ax0 = axes[0]
    ax0.set_xlim(*XLIM)
    ax0.set_ylim(*YLIM)
    ax0.set_aspect("equal")
    ax0.axis("off")
    nuts_clip.plot(ax=ax0, color="#f0f0f0", edgecolor="white", linewidth=0.2)
    vmin_a, vmax_a = 30.0, 90.0
    gdf.loc[has_data].plot(
        ax=ax0,
        column="availability_pct",
        cmap="YlGnBu",
        linewidth=0.2,
        edgecolor="#555555",
        vmin=vmin_a,
        vmax=vmax_a,
        legend=False,
    )
    sm0 = cm.ScalarMappable(norm=Normalize(vmin_a, vmax_a), cmap="YlGnBu")
    sm0.set_array([])
    cbar0 = fig.colorbar(
        sm0,
        ax=ax0,
        orientation="horizontal",
        fraction=0.06,
        pad=0.02,
        aspect=28,
    )
    cbar0.set_label("Heat served / demand (%)", fontsize=8)
    cbar0.ax.tick_params(labelsize=7)
    ax0.set_title("Availability (heat-weighted)", fontsize=11, pad=4)

    # --- LCOH ---
    ax1 = axes[1]
    ax1.set_xlim(*XLIM)
    ax1.set_ylim(*YLIM)
    ax1.set_aspect("equal")
    ax1.axis("off")
    nuts_clip.plot(ax=ax1, color="#f0f0f0", edgecolor="white", linewidth=0.2)
    big = agg.loc[agg["demand_twh"] >= 0.5, "lcoh_eur_per_mwh"]
    vmin_l = float(np.floor(big.min() / 5) * 5)
    vmax_l = float(np.ceil(np.percentile(big, 95) / 5) * 5)
    vmax_l = max(vmax_l, 80.0)
    gdf.loc[has_data].plot(
        ax=ax1,
        column="lcoh_eur_per_mwh",
        cmap="YlOrRd",
        linewidth=0.2,
        edgecolor="#555555",
        vmin=vmin_l,
        vmax=vmax_l,
        legend=False,
    )
    sm1 = cm.ScalarMappable(norm=Normalize(vmin_l, vmax_l), cmap="YlOrRd")
    sm1.set_array([])
    cbar1 = fig.colorbar(
        sm1,
        ax=ax1,
        orientation="horizontal",
        fraction=0.06,
        pad=0.02,
        aspect=28,
    )
    cbar1.set_label(f"LCOH of served heat (€/MWh; scale ≤{vmax_l:.0f})", fontsize=8)
    cbar1.ax.tick_params(labelsize=7)
    ax1.set_title("LCOH (heat-weighted)", fontsize=11, pad=4)

    fig.suptitle(
        "NUTS2 — 5 km buffer (2030 costs, solar + HP + Li-ion + IHB)",
        fontsize=12,
        y=0.99,
    )
    fig.text(
        0.5,
        0.01,
        "Σserved/Σdemand · LCOH=Σ(LCOH×served)/Σserved · "
        f"EURUSD={EURUSD:.2f} · Grey=no sites · {int(has_data.sum())} NUTS2 with data",
        ha="center",
        fontsize=7,
        color="#555555",
    )
    fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.14, wspace=0.06)
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)

    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")
    print(f"Regions with data: {len(agg)}  unmatched heat TWh: "
          f"{joined.loc[joined.NUTS_ID.isna(), 'heat'].sum()/1e6:.2f}")
    print(agg.head(15).to_string(index=False, float_format=lambda x: f"{x:.1f}"))


if __name__ == "__main__":
    main()
