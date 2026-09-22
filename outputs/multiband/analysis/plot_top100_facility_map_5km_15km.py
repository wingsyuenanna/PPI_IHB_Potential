"""Static dual map: top-100 heat facilities — LCOH fill, availability outline.

Stacked 5 km / 15 km panels (avoids double-Atlantic side-by-side gap).
Cropped to European industrial core where most large sites sit.

    python outputs/multiband/analysis/plot_top100_facility_map_5km_15km.py
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
EURUSD = 1.08
TOP_N = 100
OUT_STEM = "top100_facility_map_lcoh_avail_5km_15km"

# Industrial-core crop (most top-100 heat); a few Nordic/Iberian sites sit on the edge
XLIM = (-8, 24)
YLIM = (40, 60)

SIZE_BINS = [
    (3.0, "< 3 TWh", 55),
    (6.0, "3–6 TWh", 160),
    (np.inf, "≥ 6 TWh", 380),
]


def load_scenario(scenario: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / f"outputs/multiband/{scenario}/by_facility.csv")
    ok = df[df["status"] == "ok"].copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["land"] = pd.to_numeric(ok["available_land_km2"], errors="coerce")
    ok["rel"] = pd.to_numeric(ok["Reliability_%"], errors="coerce")
    ok["lcoh"] = pd.to_numeric(ok["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    ok["lat"] = pd.to_numeric(ok["lat"], errors="coerce")
    ok["lon"] = pd.to_numeric(ok["lon"], errors="coerce")
    return ok.dropna(subset=["lat", "lon", "heat", "rel", "lcoh"])


def europe_basemap() -> gpd.GeoDataFrame:
    shp = shpreader.natural_earth(resolution="50m", category="cultural", name="admin_0_countries")
    return gpd.read_file(shp).cx[XLIM[0] - 2 : XLIM[1] + 2, YLIM[0] - 2 : YLIM[1] + 2]


def size_for_heat(heat_mwh: np.ndarray) -> np.ndarray:
    twh = np.asarray(heat_mwh, dtype=float) / 1e6
    out = np.empty(twh.shape, dtype=float)
    for i, v in enumerate(twh):
        for upper, _, s in SIZE_BINS:
            if v < upper:
                out[i] = s
                break
    return out


def plot_panel(ax, df: pd.DataFrame, world, lcoh_norm, avail_norm, title: str) -> None:
    ax.axis("off")
    world.plot(ax=ax, color="#e8e8e8", edgecolor="white", linewidth=0.4)
    ax.set_aspect("auto")
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)

    d = df.sort_values("heat", ascending=True)
    sizes = size_for_heat(d["heat"].to_numpy())
    fills = cm.RdYlGn_r(lcoh_norm(d["lcoh"].to_numpy()))
    edges = cm.coolwarm_r(avail_norm(d["rel"].to_numpy()))
    lw = np.where(d["rel"].to_numpy() < 50, 1.8, 1.2)

    ax.scatter(
        d["lon"],
        d["lat"],
        s=sizes,
        c=fills,
        edgecolors=edges,
        linewidths=lw,
        alpha=0.88,
        zorder=3,
    )
    ax.set_title(title, fontsize=11, loc="left", pad=4)


def main() -> None:
    s5 = load_scenario("land_5km_ss_2030_liion")
    s15 = load_scenario("land_15km_ss_2030_liion")

    top_ids = s5.nlargest(TOP_N, "heat")["source_id"]
    t5 = s5[s5["source_id"].isin(top_ids)].copy()
    t15 = s15[s15["source_id"].isin(top_ids)].copy()
    common = set(t5["source_id"]) & set(t15["source_id"])
    t5 = t5[t5["source_id"].isin(common)]
    t15 = t15[t15["source_id"].isin(common)]

    summary = (
        t5[["source_id", "source_name", "iso3_country", "subsector", "heat", "lat", "lon"]]
        .merge(
            t5[["source_id", "land", "rel", "lcoh"]].rename(
                columns={"land": "land_5km", "rel": "avail_5km", "lcoh": "lcoh_5km"}
            ),
            on="source_id",
        )
        .merge(
            t15[["source_id", "land", "rel", "lcoh"]].rename(
                columns={"land": "land_15km", "rel": "avail_15km", "lcoh": "lcoh_15km"}
            ),
            on="source_id",
        )
    )
    summary["heat_twh"] = summary["heat"] / 1e6
    summary = summary.sort_values("heat", ascending=False)
    summary.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    lcoh_all = pd.concat([t5["lcoh"], t15["lcoh"]])
    vmin_l = float(np.floor(np.percentile(lcoh_all, 5) / 5) * 5)
    vmax_l = float(np.ceil(np.percentile(lcoh_all, 95) / 5) * 5)
    vmax_l = max(vmax_l, vmin_l + 20)
    lcoh_norm = Normalize(vmin=vmin_l, vmax=vmax_l)
    avail_norm = Normalize(vmin=0, vmax=100)
    world = europe_basemap()

    # Stacked panels: same geography aligned for easy 5↔15 comparison
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 9.0), sharex=True, sharey=True)
    plot_panel(axes[0], t5, world, lcoh_norm, avail_norm, f"5 km land buffer — top {len(t5)} sites by heat demand")
    plot_panel(axes[1], t15, world, lcoh_norm, avail_norm, "15 km land buffer — same sites")

    hw5 = 100 * (t5["rel"] / 100 * t5["heat"]).sum() / t5["heat"].sum()
    hw15 = 100 * (t15["rel"] / 100 * t15["heat"]).sum() / t15["heat"].sum()
    fig.suptitle(
        "Largest industrial heat sites: LCOH vs availability\n(2030 costs, solar + HP + Li-ion + IHB)",
        fontsize=12,
        y=0.98,
    )

    fig.subplots_adjust(left=0.04, right=0.72, top=0.90, bottom=0.08, hspace=0.12)

    # Legends in right margin (no overlap with maps)
    sm_l = cm.ScalarMappable(norm=lcoh_norm, cmap="RdYlGn_r")
    sm_l.set_array([])
    cax_l = fig.add_axes([0.78, 0.62, 0.035, 0.22])
    cb_l = fig.colorbar(sm_l, cax=cax_l, orientation="vertical")
    cb_l.set_label("Fill: LCOH (€/MWh)", fontsize=8)
    cb_l.ax.tick_params(labelsize=7)

    sm_a = cm.ScalarMappable(norm=avail_norm, cmap="coolwarm_r")
    sm_a.set_array([])
    cax_a = fig.add_axes([0.78, 0.32, 0.035, 0.22])
    cb_a = fig.colorbar(sm_a, cax=cax_a, orientation="vertical")
    cb_a.set_label("Outline: availability (%)", fontsize=8)
    cb_a.ax.tick_params(labelsize=7)

    sax = fig.add_axes([0.76, 0.08, 0.22, 0.18])
    sax.set_xlim(0, 1)
    sax.set_ylim(0, 1)
    sax.axis("off")
    sax.text(0.05, 0.95, "Marker size\n(heat demand)", fontsize=8, fontweight="bold", va="top")
    for y, (_, lab, s) in zip([0.62, 0.38, 0.14], SIZE_BINS):
        sax.scatter([0.18], [y], s=s, facecolors="#dddddd", edgecolors="#333", linewidths=1.1)
        sax.text(0.38, y, lab, va="center", fontsize=8, color="#333")

    fig.text(
        0.38,
        0.015,
        f"Top {len(t5)} by heat (~{100 * summary.heat.sum() / s5.heat.sum():.0f}% of fleet).  "
        f"Heat-weighted availability: {hw5:.0f}% → {hw15:.0f}%.  "
        "Map cropped to industrial core; thicker outline if availability <50%.",
        ha="center",
        fontsize=7.5,
        color="#555",
    )

    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=220)
    plt.close(fig)

    in_frame = (
        summary["lon"].between(XLIM[0], XLIM[1]) & summary["lat"].between(YLIM[0], YLIM[1])
    ).sum()
    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")
    print(f"n={len(t5)} in-frame={in_frame}  HW avail {hw5:.1f}% → {hw15:.1f}%")


if __name__ == "__main__":
    main()
