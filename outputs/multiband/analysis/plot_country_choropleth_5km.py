"""Side-by-side country choropleths: heat-weighted availability & LCOH (5 km).

Uses land_5km_ss_2030_liion fleet results. Aggregation:
  availability = 100 * Σserved / Σdemand
  LCOH (€/MWh) = Σ(LCOH_served × served) / Σserved   [EURUSD=1.08]

    python outputs/multiband/analysis/plot_country_choropleth_5km.py
"""
from __future__ import annotations

from pathlib import Path

import cartopy.io.shapereader as shpreader
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
OUT_STEM = "country_choropleth_avail_lcoh_5km"

# Poster-friendly Europe frame (exclude far overseas territories)
XLIM = (-12, 32)
YLIM = (34, 72)


def country_aggregates() -> pd.DataFrame:
    df = pd.read_csv(ROOT / f"outputs/multiband/{SCENARIO}/by_facility.csv")
    ok = df[df["status"] == "ok"].copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["rel"] = pd.to_numeric(ok["Reliability_%"], errors="coerce")
    ok["served"] = ok["rel"] / 100.0 * ok["heat"]
    ok["lcoh_eur"] = pd.to_numeric(ok["LCOH_served_$perMWh"], errors="coerce") / EURUSD

    rows = []
    for iso, g in ok.groupby("iso3_country"):
        demand = float(g["heat"].sum())
        served = float(g["served"].sum())
        lcoh = (
            float((g["lcoh_eur"] * g["served"]).sum() / served) if served > 0 else float("nan")
        )
        rows.append(
            {
                "iso3_country": iso,
                "demand_twh": demand / 1e6,
                "served_twh": served / 1e6,
                "availability_pct": 100.0 * served / demand if demand > 0 else float("nan"),
                "lcoh_eur_per_mwh": lcoh,
                "n_sites": len(g),
            }
        )
    return pd.DataFrame(rows).sort_values("demand_twh", ascending=False)


def europe_geodata() -> gpd.GeoDataFrame:
    """Natural Earth admin-0 via cartopy cache, filtered to modelled ISO3s."""
    shp = shpreader.natural_earth(resolution="50m", category="cultural", name="admin_0_countries")
    world = gpd.read_file(shp)
    # Natural Earth column for ISO A3
    iso_col = "ISO_A3_EH" if "ISO_A3_EH" in world.columns else "ISO_A3"
    if iso_col not in world.columns:
        # fallbacks across NE versions
        for c in ("ADM0_A3", "iso_a3", "ISO_A3"):
            if c in world.columns:
                iso_col = c
                break
    world = world.rename(columns={iso_col: "iso3_country"})
    world["iso3_country"] = world["iso3_country"].astype(str).str.upper()
    # Fix common NE quirks
    world.loc[world["NAME"] == "France", "iso3_country"] = "FRA"
    world.loc[world["NAME"] == "Norway", "iso3_country"] = "NOR"
    return world[["iso3_country", "NAME", "geometry"]].copy()


def main() -> None:
    agg = country_aggregates()
    agg.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    world = europe_geodata()
    gdf = world.merge(agg, on="iso3_country", how="inner")
    # Keep largest landmass per country (projected area) so overseas territories drop out
    gdf = gdf.explode(index_parts=False)
    gdf["_area_km2"] = gdf.to_crs(3035).geometry.area / 1e6
    gdf = gdf.sort_values("_area_km2").groupby("iso3_country", as_index=False).tail(1)
    gdf = gpd.GeoDataFrame(gdf.drop(columns="_area_km2"), geometry="geometry", crs=world.crs)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.8))

    # --- Availability ---
    ax0 = axes[0]
    ax0.set_xlim(*XLIM)
    ax0.set_ylim(*YLIM)
    ax0.set_aspect("equal")
    ax0.axis("off")
    # light basemap of neighbours (no data)
    world_clip = world.cx[XLIM[0] : XLIM[1], YLIM[0] : YLIM[1]]
    world_clip.plot(ax=ax0, color="#f0f0f0", edgecolor="white", linewidth=0.4)
    vmin_a, vmax_a = 30.0, 90.0
    gdf.plot(
        ax=ax0,
        column="availability_pct",
        cmap="YlGnBu",
        linewidth=0.6,
        edgecolor="#333333",
        vmin=vmin_a,
        vmax=vmax_a,
        legend=False,
    )
    sm0 = cm.ScalarMappable(norm=Normalize(vmin_a, vmax_a), cmap="YlGnBu")
    sm0.set_array([])
    cbar0 = fig.colorbar(sm0, ax=ax0, fraction=0.035, pad=0.02, shrink=0.78)
    cbar0.set_label("Heat served / demand (%)", fontsize=9)
    ax0.set_title("Availability (heat-weighted)", fontsize=12, pad=8)

    # --- LCOH (scale capped so tiny high-cost countries don't wash out majors) ---
    ax1 = axes[1]
    ax1.set_xlim(*XLIM)
    ax1.set_ylim(*YLIM)
    ax1.set_aspect("equal")
    ax1.axis("off")
    world_clip.plot(ax=ax1, color="#f0f0f0", edgecolor="white", linewidth=0.4)
    # Cap at ~95th percentile among countries ≥1 TWh demand
    big = agg.loc[agg["demand_twh"] >= 1.0, "lcoh_eur_per_mwh"]
    vmin_l = float(np.floor(big.min() / 5) * 5)
    vmax_l = float(np.ceil(np.percentile(big, 95) / 5) * 5)
    vmax_l = max(vmax_l, 80.0)
    gdf.plot(
        ax=ax1,
        column="lcoh_eur_per_mwh",
        cmap="YlOrRd",
        linewidth=0.6,
        edgecolor="#333333",
        vmin=vmin_l,
        vmax=vmax_l,
        legend=False,
    )
    sm1 = cm.ScalarMappable(norm=Normalize(vmin_l, vmax_l), cmap="YlOrRd")
    sm1.set_array([])
    cbar1 = fig.colorbar(sm1, ax=ax1, fraction=0.035, pad=0.02, shrink=0.78)
    cbar1.set_label(f"LCOH of served heat (€/MWh; scale ≤{vmax_l:.0f})", fontsize=9)
    ax1.set_title("LCOH (heat-weighted)", fontsize=12, pad=8)

    fig.suptitle(
        "Country aggregates — 5 km land buffer (2030 costs, solar + HP + Li-ion + IHB)",
        fontsize=13,
        y=0.98,
    )
    fig.text(
        0.5,
        0.02,
        "Availability = Σserved / Σdemand.  LCOH = Σ(LCOH×served)/Σserved.  "
        f"EURUSD={EURUSD:.2f}.  Grey = no modelled sites.",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")
    print(agg.to_string(index=False, float_format=lambda x: f"{x:.1f}"))


if __name__ == "__main__":
    main()
