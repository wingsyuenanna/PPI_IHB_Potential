# map_sites_lcoh.py
# Interactive Folium map of optimized sites colored by LCOH ($/MWh_th).
#
# Usage (from project root):
#   python flatblock_optimization/utils/maps/map_sites_lcoh.py \
#       [-i flatblock_optimization/output/summary.csv] \
#       [-o flatblock_optimization/output/map_sites_lcoh.html]

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import folium
from branca.colormap import LinearColormap

LCOH_COL = "LCOE_total_$perMWh"
# Fossil steam benchmark: Agora Industry / Fraunhofer ISI (2025), gas boiler
# LCOH ~EUR 43-100/MWh_th across low/high price scenarios (~USD 45-110).
FOSSIL_LO, FOSSIL_HI = 45.0, 110.0


def build_map(summary_csv: str, out_html: str) -> None:
    df = pd.read_csv(summary_csv)
    ok = df[df["status"] == "completed"].dropna(subset=["lat", "lon", LCOH_COL]).copy()
    skipped = df[df["status"] != "completed"]

    vmin = float(ok[LCOH_COL].quantile(0.02))
    vmax = float(ok[LCOH_COL].quantile(0.98))
    cmap = LinearColormap(
        ["#1a9850", "#fee08b", "#d73027"],
        vmin=vmin,
        vmax=vmax,
        caption=(
            f"Solar + IHB LCOH ($/MWh_th) — fossil steam benchmark "
            f"~${FOSSIL_LO:.0f}–{FOSSIL_HI:.0f}/MWh (Agora Industry 2025)"
        ),
    )

    m = folium.Map(
        location=[ok["lat"].mean(), ok["lon"].mean()],
        zoom_start=5,
        tiles="cartodbpositron",
    )

    heat = ok["replaceable_heat_mwh_th"].astype(float)
    # Marker radius scaled by sqrt of heat demand (5-22 px)
    radius = 5 + 17 * np.sqrt(heat / heat.max())

    for (_, r), rad in zip(ok.iterrows(), radius):
        lcoh = float(r[LCOH_COL])
        vs_fossil = lcoh / FOSSIL_HI
        popup_html = (
            f"<b>{r.get('source_name', r['source_id'])}</b><br>"
            f"{r.get('classification', '')} — {r['iso3_country']}<br><hr style='margin:3px'>"
            f"<b>LCOH: ${lcoh:,.0f}/MWh_th</b> "
            f"({vs_fossil:.1f}× fossil @${FOSSIL_HI:.0f})<br>"
            f"&nbsp;&nbsp;solar ${r['LCOE_solar_$perMWh']:,.0f} + "
            f"TES ${r['LCOE_TES_$perMWh']:,.0f}<br>"
            f"Load: {r['load_MW']:.1f} MW_th "
            f"({r['replaceable_heat_mwh_th']/1e3:,.0f} GWh/yr)<br>"
            f"Solar: {r['S_opt_MW']:,.0f} MW | TES: {r['Heat_TES_energy_MWh']:,.0f} MWh "
            f"/ {r['Heat_TES_discharge_power_MW']:,.0f} MW<br>"
            f"Solar CF: {r.get('solar_capacity_factor', float('nan')):.3f}<br>"
            f"Land: {'<b style=color:red>exceeds limit</b>' if r.get('exceeds_land_limit') else 'fits'} "
            f"(max {r.get('max_solar_land_mw', float('nan')):,.0f} MW)"
        )
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=float(rad),
            color="black",
            weight=1.5 if r.get("exceeds_land_limit") else 0.5,
            fill=True,
            fill_color=cmap(min(max(lcoh, vmin), vmax)),
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{r.get('source_name', r['source_id'])}: ${lcoh:,.0f}/MWh",
        ).add_to(m)

    for _, r in skipped.dropna(subset=["lat", "lon"]).iterrows():
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=4,
            color="gray",
            weight=1,
            fill=True,
            fill_color="lightgray",
            fill_opacity=0.6,
            tooltip=f"{r.get('source_name', r['source_id'])}: {r['status']}",
        ).add_to(m)

    cmap.add_to(m)
    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    m.save(out_html)
    print(f"Map written: {out_html}  ({len(ok)} sites, {len(skipped)} skipped/gray)")
    print(f"Color scale: ${vmin:,.0f}-{vmax:,.0f}/MWh (2nd-98th pct). "
          f"Bold outline = exceeds land limit.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Map optimized sites colored by LCOH.")
    ap.add_argument("-i", "--input", default="flatblock_optimization/output/summary.csv")
    ap.add_argument("-o", "--output", default="flatblock_optimization/output/map_sites_lcoh.html")
    args = ap.parse_args()
    build_map(args.input, args.output)
