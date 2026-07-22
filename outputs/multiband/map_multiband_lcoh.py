"""Interactive Folium map comparing 5 km vs 15 km solar+storage multiband results.

Popup shows LCOH split: solar + storage. Color legend + outline legend on the map.

    python outputs/multiband/map_multiband_lcoh.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import folium
import numpy as np
import pandas as pd
from branca.colormap import LinearColormap
from branca.element import MacroElement, Template
from folium.plugins import DualMap

ROOT = Path(__file__).resolve().parents[2]
SITES = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"
DEFAULT_5 = ROOT / "outputs" / "multiband" / "land_5km_ss" / "by_facility.csv"
DEFAULT_15 = ROOT / "outputs" / "multiband" / "land_15km_ss" / "by_facility.csv"
DEFAULT_OUT = ROOT / "outputs" / "multiband" / "map_lcoh_5km_15km_ss.html"


def load_scenario(path: Path, sites: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(path)
    ok = df[df["status"] == "ok"].copy()
    if "lat" not in ok.columns or ok["lat"].isna().all():
        ok = ok.drop(columns=[c for c in ("lat", "lon") if c in ok.columns], errors="ignore")
        ok = ok.merge(sites[["source_id", "lat", "lon"]], on="source_id", how="left")
    ok = ok.dropna(subset=["lat", "lon", "LCOH_served_$perMWh"])
    for c in ("LCOH_solar_$perMWh", "LCOH_storage_$perMWh"):
        if c not in ok.columns:
            ok[c] = 0.0
        ok[c] = ok[c].fillna(0.0)
    return ok


def popup_html(r: pd.Series, land_label: str) -> str:
    lcoh = float(r["LCOH_served_$perMWh"])
    sol = float(r["LCOH_solar_$perMWh"])
    stor = float(r["LCOH_storage_$perMWh"])
    met = r.get("met_availability_target", True)
    met_s = "yes" if bool(met) in (True, "True", "true", 1) else "no (land-limited)"
    hp = float(r.get("hp_load_MW", 0) or 0)
    ihb = float(r.get("ihb_load_MW", 0) or 0)
    tot = hp + ihb
    hp_pct = 100 * hp / tot if tot > 0 else 0
    return (
        f"<div style='font-family:sans-serif;font-size:12px;min-width:220px'>"
        f"<b>{r.get('source_name', r['source_id'])}</b><br>"
        f"{r.get('subsector', '')} — {r['iso3_country']} "
        f"<span style='color:#666'>({land_label})</span><br>"
        f"<hr style='margin:4px 0'>"
        f"<b>LCOH served: ${lcoh:,.0f}/MWh</b><br>"
        f"<table style='width:100%;border-collapse:collapse;margin-top:4px'>"
        f"<tr><td>Solar</td><td style='text-align:right'><b>${sol:,.0f}</b></td></tr>"
        f"<tr><td>Storage (heat battery)</td><td style='text-align:right'><b>${stor:,.0f}</b></td></tr>"
        f"</table>"
        f"<hr style='margin:4px 0'>"
        f"Reliability: {float(r['Reliability_%']):.0f}% "
        f"(90% target: {met_s})<br>"
        f"Load: {float(r['total_load_MW']):.1f} MW_th "
        f"({float(r['replaceable_heat_mwh_th'])/1e3:,.0f} GWh/yr)<br>"
        f"HP / IHB load: {hp_pct:.0f}% / {100-hp_pct:.0f}%<br>"
        f"Solar: {float(r['S_opt_MW']):,.0f} MWdc "
        f"({float(r['solar_per_load_MWdc_per_MWth']):.1f} MWdc/MWth)<br>"
        f"Storage: {float(r['storage_energy_MWh_total']):,.0f} MWh_th<br>"
        f"Land: {float(r.get('available_land_km2', float('nan'))):.1f} km²"
        f"</div>"
    )


def add_markers(fmap, df: pd.DataFrame, cmap, land_label: str, vmin: float, vmax: float) -> None:
    heat = df["replaceable_heat_mwh_th"].astype(float)
    radius = 4 + 14 * np.sqrt(heat / heat.max())
    for (_, r), rad in zip(df.iterrows(), radius):
        lcoh = float(r["LCOH_served_$perMWh"])
        met = bool(r.get("met_availability_target", True)) in (True, "True", "true", 1)
        folium.CircleMarker(
            location=[float(r["lat"]), float(r["lon"])],
            radius=float(rad),
            color="#222" if met else "#c0392b",
            weight=1.2 if not met else 0.4,
            fill=True,
            fill_color=cmap(min(max(lcoh, vmin), vmax)),
            fill_opacity=0.85,
            popup=folium.Popup(popup_html(r, land_label), max_width=300),
            tooltip=f"{r.get('source_name', r['source_id'])}: ${lcoh:,.0f}/MWh "
                    f"(rel {float(r['Reliability_%']):.0f}%)",
        ).add_to(fmap)


class MapLegend(MacroElement):
    """Fixed HTML legend: LCOH color ramp + outline meaning."""

    def __init__(self, vmin: float, vmax: float):
        super().__init__()
        self._template = Template(
            """
            {% macro html(this, kwargs) %}
            <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
                        background: white; padding: 10px 12px; border-radius: 6px;
                        box-shadow: 0 1px 4px rgba(0,0,0,.25); font-family: sans-serif;
                        font-size: 12px; line-height: 1.35; min-width: 180px;">
              <div style="font-weight: 700; margin-bottom: 6px;">Legend</div>
              <div style="margin-bottom: 4px;">LCOH served ($/MWh)</div>
              <div style="height: 12px; border-radius: 2px;
                          background: linear-gradient(to right, #1a9850, #fee08b, #d73027);"></div>
              <div style="display: flex; justify-content: space-between; margin: 2px 0 8px 0; color: #444;">
                <span>${{ '%.0f'|format(this.vmin) }}</span>
                <span>${{ '%.0f'|format(this.vmax) }}</span>
              </div>
              <div style="margin-top: 4px;">
                <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
                             border:1.5px solid #222;background:#1a9850;vertical-align:middle;"></span>
                ≥ 90% reliability
              </div>
              <div style="margin-top: 4px;">
                <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
                             border:2px solid #c0392b;background:#fee08b;vertical-align:middle;"></span>
                Below 90% (land-limited)
              </div>
              <div style="margin-top: 6px; color: #666; font-size: 11px;">
                Marker size ∝ replaceable heat
              </div>
            </div>
            {% endmacro %}
            """
        )
        self.vmin = vmin
        self.vmax = vmax


class PanelLabel(MacroElement):
    """Fixed label pinned to one DualMap pane (left or right)."""

    def __init__(self, text: str, side: str = "left"):
        super().__init__()
        self.text = text
        # DualMap panes are side-by-side; pin label to the relevant half of the viewport.
        if side == "left":
            pos = "left: 12px;"
        else:
            pos = "right: 12px;"
        self._template = Template(
            f"""
            {{% macro html(this, kwargs) %}}
            <div style="position: fixed; top: 72px; {pos} z-index: 9999;
                        background: #1f4e79; color: white; padding: 6px 12px;
                        border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.3);
                        font-family: sans-serif; font-size: 13px; font-weight: 700;
                        letter-spacing: 0.02em;">
              {{{{ this.text }}}}
            </div>
            {{% endmacro %}}
            """
        )


def build_dual_map(path_5: Path, path_15: Path, out_html: Path) -> None:
    sites = pd.read_csv(SITES, usecols=["source_id", "lat", "lon"], low_memory=False)
    df5 = load_scenario(path_5, sites)
    df15 = load_scenario(path_15, sites)

    all_lcoh = pd.concat([df5["LCOH_served_$perMWh"], df15["LCOH_served_$perMWh"]])
    vmin = float(all_lcoh.quantile(0.02))
    vmax = float(min(all_lcoh.quantile(0.98), 250))
    cmap = LinearColormap(["#1a9850", "#fee08b", "#d73027"], vmin=vmin, vmax=vmax)

    center = [float(df5["lat"].mean()), float(df5["lon"].mean())]
    dm = DualMap(location=center, zoom_start=4, tiles="cartodbpositron")

    def hw(df, col="LCOH_served_$perMWh", weight="replaceable_heat_mwh_th"):
        w = df[weight].astype(float)
        return float((df[col] * w).sum() / w.sum())

    def stats(df):
        met = df["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
        l_all = hw(df)
        r_all = hw(df, "Reliability_%")
        if met.any():
            l_met = hw(df.loc[met])
            n_met = int(met.sum())
            heat_met = 100 * df.loc[met, "replaceable_heat_mwh_th"].sum() / df["replaceable_heat_mwh_th"].sum()
        else:
            l_met, n_met, heat_met = float("nan"), 0, 0.0
        return l_all, r_all, l_met, n_met, heat_met

    l5, r5, l5m, n5m, h5m = stats(df5)
    l15, r15, l15m, n15m, h15m = stats(df15)
    title = (
        f"<div style='position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;"
        f"background:white;padding:8px 14px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.25);"
        f"font-family:sans-serif;font-size:13px;text-align:center'>"
        f"<b>Solar + storage LCOH</b> · 90% availability target<br>"
        f"<b>5 km</b>: HW ${l5:,.0f}/MWh · rel {r5:.0f}% · "
        f"at ≥90%: ${l5m:,.0f}/MWh ({n5m} sites, {h5m:.0f}% heat)"
        f"&nbsp;|&nbsp;"
        f"<b>15 km</b>: HW ${l15:,.0f}/MWh · rel {r15:.0f}% · "
        f"at ≥90%: ${l15m:,.0f}/MWh ({n15m} sites, {h15m:.0f}% heat)<br>"
        f"<span style='color:#666;font-size:11px'>Click a site for solar / storage cost split.</span></div>"
    )

    add_markers(dm.m1, df5, cmap, "5 km land", vmin, vmax)
    add_markers(dm.m2, df15, cmap, "15 km land", vmin, vmax)

    # Fixed panel labels (not geographic markers)
    dm.get_root().add_child(PanelLabel("Left: 5 km land buffer", side="left"))
    dm.get_root().add_child(PanelLabel("Right: 15 km land buffer", side="right"))

    # Legend on the left (5 km) map panel — visible for DualMap
    dm.m1.get_root().add_child(MapLegend(vmin, vmax))

    out_html.parent.mkdir(parents=True, exist_ok=True)
    dm.save(str(out_html))
    html = out_html.read_text()
    html = html.replace("<body>", f"<body>{title}", 1)
    out_html.write_text(html)

    print(f"Wrote {out_html}")
    print(f"  5 km:  {len(df5)} sites  HW ${l5:,.0f}/MWh  rel {r5:.0f}%  "
          f"met90 ${l5m:,.0f}/MWh ({n5m} sites)")
    print(f"  15 km: {len(df15)} sites  HW ${l15:,.0f}/MWh  rel {r15:.0f}%  "
          f"met90 ${l15m:,.0f}/MWh ({n15m} sites)")
    print(f"  Color scale ${vmin:,.0f}–${vmax:,.0f}/MWh")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--five", type=Path, default=DEFAULT_5)
    ap.add_argument("--fifteen", type=Path, default=DEFAULT_15)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    build_dual_map(args.five, args.fifteen, args.output)


if __name__ == "__main__":
    main()
