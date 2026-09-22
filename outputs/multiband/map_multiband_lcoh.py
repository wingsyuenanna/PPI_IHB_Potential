"""Interactive Folium map comparing 5 km vs 15 km solar+storage multiband results.

Costs are shown in EUR (converted from model USD outputs at EURUSD=1.08).

Optimization shown on the map is lexicographic:
  1. Maximize served heat (hard 90% floor when land allows; else land-limited max-serve)
  2. Minimize LCOH (annual cost / served MWh) at that serve level

Visual encoding:
  Fill color = LCOH of served heat (€/MWh)
  Outline color = availability met (Reliability_%, continuous)
  Size ∝ annual replaceable heat demand

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
DEFAULT_5 = ROOT / "outputs" / "multiband" / "land_5km_ss_2030_liion" / "by_facility.csv"
DEFAULT_15 = ROOT / "outputs" / "multiband" / "land_15km_ss_2030_liion" / "by_facility.csv"
DEFAULT_OUT = ROOT / "outputs" / "multiband" / "map_lcoh_5km_15km_ss.html"

# Same FX as add_gas_benchmark.py: 1 EUR = 1.08 USD → € = $ / 1.08
EURUSD = 1.08
LCOH_USD_COLS = (
    "LCOH_served_$perMWh",
    "LCOH_solar_$perMWh",
    "LCOH_storage_$perMWh",
    "LCOH_liion_$perMWh",
    "LCOH_ihb_$perMWh",
    "LCOH_hp_$perMWh",
    "LCOH_total_$perMWh",
)
# Outline: low availability → high (warm → cool blue)
AVAIL_COLORS = ["#fddbc7", "#f4a582", "#d6604d", "#4393c3", "#2166ac"]
AVAIL_VMIN = 0.0
AVAIL_VMAX = 100.0


def usd_to_eur(x: float) -> float:
    return float(x) / EURUSD


def _is_met(val) -> bool:
    return bool(val) in (True, "True", "true", 1) or str(val).lower() in ("true", "1")


def load_scenario(path: Path, sites: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(path)
    ok = df[df["status"] == "ok"].copy()
    if "lat" not in ok.columns or ok["lat"].isna().all():
        ok = ok.drop(columns=[c for c in ("lat", "lon") if c in ok.columns], errors="ignore")
        ok = ok.merge(sites[["source_id", "lat", "lon"]], on="source_id", how="left")
    ok = ok.dropna(subset=["lat", "lon", "LCOH_served_$perMWh"])
    for c in (
        "LCOH_solar_$perMWh",
        "LCOH_storage_$perMWh",
        "LCOH_liion_$perMWh",
        "LCOH_ihb_$perMWh",
        "Unserved_MWh",
        "liion_energy_MWh",
        "ihb_energy_MWh",
        "hp_load_MW",
        "ihb_load_MW",
    ):
        if c not in ok.columns:
            ok[c] = 0.0
        ok[c] = pd.to_numeric(ok[c], errors="coerce").fillna(0.0)
    # Display currency: EUR (model internals remain USD)
    for c in LCOH_USD_COLS:
        if c in ok.columns:
            ok[c] = pd.to_numeric(ok[c], errors="coerce") / EURUSD
    demand = ok["replaceable_heat_mwh_th"].astype(float)
    unserved = ok["Unserved_MWh"].astype(float).clip(lower=0)
    ok["served_MWh"] = (demand - unserved).clip(lower=0)
    ok["serve_frac"] = np.where(demand > 0, ok["served_MWh"] / demand, 0.0)
    if "Reliability_%" in ok.columns:
        ok["availability_pct"] = pd.to_numeric(ok["Reliability_%"], errors="coerce")
    else:
        ok["availability_pct"] = np.nan
    ok["availability_pct"] = (
        ok["availability_pct"].fillna(100.0 * ok["serve_frac"]).clip(0, 100)
    )
    return ok


def popup_html(r: pd.Series, land_label: str) -> str:
    lcoh = float(r["LCOH_served_$perMWh"])
    sol = float(r["LCOH_solar_$perMWh"])
    li = float(r.get("LCOH_liion_$perMWh", 0) or 0)
    ihb_c = float(r.get("LCOH_ihb_$perMWh", 0) or 0)
    hp_c = float(r.get("LCOH_hp_$perMWh", 0) or 0)
    stor = float(r.get("LCOH_storage_$perMWh", 0) or 0)
    if li == 0 and ihb_c == 0 and hp_c == 0 and stor:
        stor_rows = (
            f"<tr><td>Storage</td><td style='text-align:right'><b>€{stor:,.0f}</b></td></tr>"
        )
    else:
        stor_rows = (
            f"<tr><td>Heat pump</td><td style='text-align:right'><b>€{hp_c:,.0f}</b></td></tr>"
            f"<tr><td>Li-ion</td><td style='text-align:right'><b>€{li:,.0f}</b></td></tr>"
            f"<tr><td>IHB</td><td style='text-align:right'><b>€{ihb_c:,.0f}</b></td></tr>"
        )
    met = _is_met(r.get("met_availability_target", True))
    avail = float(r["availability_pct"])
    demand = float(r["replaceable_heat_mwh_th"])
    served = float(r["served_MWh"])
    if met:
        serve_note = "met 90% floor → then min LCOH"
    else:
        serve_note = "land-capped: max serve → then min LCOH"
    hp = float(r.get("hp_load_MW", 0) or 0)
    ihb = float(r.get("ihb_load_MW", 0) or 0)
    tot = hp + ihb
    hp_pct = 100 * hp / tot if tot > 0 else 0
    return (
        f"<div style='font-family:sans-serif;font-size:12px;min-width:260px'>"
        f"<b>{r.get('source_name', r['source_id'])}</b><br>"
        f"{r.get('subsector', '')} — {r['iso3_country']} "
        f"<span style='color:#666'>({land_label})</span><br>"
        f"<hr style='margin:4px 0'>"
        f"<div style='display:flex;gap:12px;margin:6px 0'>"
        f"<div style='flex:1;background:#f3f6fa;padding:8px;border-radius:4px;text-align:center'>"
        f"<div style='font-size:10px;color:#555;text-transform:uppercase'>Availability met</div>"
        f"<div style='font-size:20px;font-weight:700;color:#053061'>{avail:.0f}%</div>"
        f"</div>"
        f"<div style='flex:1;background:#f3f6fa;padding:8px;border-radius:4px;text-align:center'>"
        f"<div style='font-size:10px;color:#555;text-transform:uppercase'>LCOH served</div>"
        f"<div style='font-size:20px;font-weight:700;color:#1f4e79'>€{lcoh:,.0f}</div>"
        f"<div style='font-size:10px;color:#666'>/MWh</div>"
        f"</div>"
        f"</div>"
        f"<span style='color:#555'>{serve_note}</span><br>"
        f"<hr style='margin:4px 0'>"
        f"<b>Served: {served/1e3:,.0f} / {demand/1e3:,.0f} GWh/yr "
        f"({100*float(r['serve_frac']):.0f}%)</b><br>"
        f"<table style='width:100%;border-collapse:collapse;margin-top:4px'>"
        f"<tr><td>Solar</td><td style='text-align:right'><b>€{sol:,.0f}</b></td></tr>"
        f"{stor_rows}"
        f"</table>"
        f"<hr style='margin:4px 0'>"
        f"Load: {float(r['total_load_MW']):.1f} MW_th · "
        f"HP / IHB: {hp_pct:.0f}% / {100-hp_pct:.0f}%<br>"
        f"Solar: {float(r['S_opt_MW']):,.0f} MWdc "
        f"({float(r['solar_per_load_MWdc_per_MWth']):.1f} MWdc/MWth)<br>"
        f"Li-ion / IHB store: "
        f"{float(r.get('liion_energy_MWh', 0) or 0):,.0f} / "
        f"{float(r.get('ihb_energy_MWh', 0) or 0):,.0f} MWh<br>"
        f"Land: {float(r.get('available_land_km2', float('nan'))):.1f} km²"
        f"</div>"
    )


def add_markers(
    fmap,
    df: pd.DataFrame,
    lcoh_cmap,
    avail_cmap,
    land_label: str,
    vmin: float,
    vmax: float,
) -> None:
    heat = df["replaceable_heat_mwh_th"].astype(float)
    radius = 4 + 14 * np.sqrt(heat / heat.max())
    for (_, r), rad in zip(df.iterrows(), radius):
        lcoh = float(r["LCOH_served_$perMWh"])
        avail = float(r["availability_pct"])
        # Thicker stroke when availability is low so land-capped sites stand out
        weight = 2.4 if avail < 90 else 1.4
        folium.CircleMarker(
            location=[float(r["lat"]), float(r["lon"])],
            radius=float(rad),
            color=avail_cmap(min(max(avail, AVAIL_VMIN), AVAIL_VMAX)),
            weight=weight,
            fill=True,
            fill_color=lcoh_cmap(min(max(lcoh, vmin), vmax)),
            fill_opacity=0.88,
            popup=folium.Popup(popup_html(r, land_label), max_width=340),
            tooltip=folium.Tooltip(
                (
                    f"<b>{r.get('source_name', r['source_id'])}</b><br>"
                    f"Availability met: <b>{avail:.0f}%</b><br>"
                    f"LCOH: <b>€{lcoh:,.0f}/MWh</b>"
                ),
                sticky=True,
            ),
        ).add_to(fmap)


class MapLegend(MacroElement):
    """Fixed HTML legend: LCOH fill + continuous availability outline."""

    def __init__(self, vmin: float, vmax: float):
        super().__init__()
        self._template = Template(
            """
            {% macro html(this, kwargs) %}
            <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
                        background: white; padding: 12px 14px; border-radius: 6px;
                        box-shadow: 0 1px 4px rgba(0,0,0,.25); font-family: sans-serif;
                        font-size: 12px; line-height: 1.4; min-width: 270px; max-width: 310px;">
              <div style="font-weight: 700; margin-bottom: 8px; font-size: 13px;">How to read the map</div>

              <div style="font-weight: 600; margin-bottom: 3px;">Fill = LCOH of served heat</div>
              <div style="color:#555; font-size: 11px; margin-bottom: 4px;">
                €/MWh of heat actually delivered (not unmet demand). Green = cheaper, red = costlier.
              </div>
              <div style="height: 12px; border-radius: 2px;
                          background: linear-gradient(to right, #1a9850, #fee08b, #d73027);"></div>
              <div style="display: flex; justify-content: space-between; margin: 2px 0 10px 0; color: #444;">
                <span>€{{ '%.0f'|format(this.vmin) }}</span>
                <span>€{{ '%.0f'|format(this.vmax) }}/MWh</span>
              </div>

              <div style="font-weight: 600; margin-bottom: 3px;">Outline = availability met</div>
              <div style="color:#555; font-size: 11px; margin-bottom: 4px;">
                Share of annual demand served. Warm/red = low; dark blue = high (≥90%).
                Low-availability sites also get a thicker outline.
              </div>
              <div style="height: 12px; border-radius: 2px;
                          background: linear-gradient(to right, #fddbc7, #f4a582, #d6604d, #4393c3, #2166ac);"></div>
              <div style="display: flex; justify-content: space-between; margin: 2px 0 10px 0; color: #444;">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>

              <div style="font-weight: 600; margin-bottom: 2px;">Marker size</div>
              <div style="color:#555; font-size: 11px;">
                Larger = more annual replaceable heat demand.
              </div>
              <div style="margin-top: 8px; color:#666; font-size: 11px; border-top: 1px solid #eee; padding-top: 6px;">
                Hover for availability + LCOH · click for details.
                Left = 5&nbsp;km · Right = 15&nbsp;km. Costs € at EURUSD={{ '%.2f'|format(this.eurusd) }}.
              </div>
            </div>
            {% endmacro %}
            """
        )
        self.vmin = vmin
        self.vmax = vmax
        self.eurusd = EURUSD


class PanelLabel(MacroElement):
    """Fixed label pinned to one DualMap pane (left or right)."""

    def __init__(self, text: str, side: str = "left"):
        super().__init__()
        self.text = text
        if side == "left":
            pos = "left: 12px;"
        else:
            pos = "right: 12px;"
        self._template = Template(
            f"""
            {{% macro html(this, kwargs) %}}
            <div style="position: fixed; top: 168px; {pos} z-index: 9999;
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
    vmax = float(min(all_lcoh.quantile(0.98), usd_to_eur(250)))
    lcoh_cmap = LinearColormap(["#1a9850", "#fee08b", "#d73027"], vmin=vmin, vmax=vmax)
    avail_cmap = LinearColormap(AVAIL_COLORS, vmin=AVAIL_VMIN, vmax=AVAIL_VMAX)

    center = [float(df5["lat"].mean()), float(df5["lon"].mean())]
    dm = DualMap(location=center, zoom_start=4, tiles="cartodbpositron")

    def hw(df, col="LCOH_served_$perMWh", weight="replaceable_heat_mwh_th"):
        w = df[weight].astype(float)
        return float((df[col] * w).sum() / w.sum())

    def hw_served(df, col="LCOH_served_$perMWh"):
        """Heat-weight by served MWh (matches LCOH-of-served framing)."""
        w = df["served_MWh"].astype(float)
        if w.sum() <= 0:
            return float("nan")
        return float((df[col] * w).sum() / w.sum())

    def stats(df):
        met = df["met_availability_target"].map(_is_met)
        l_all = hw_served(df)
        r_all = hw(df, "Reliability_%")
        serve_all = 100 * df["served_MWh"].sum() / df["replaceable_heat_mwh_th"].sum()
        if met.any():
            l_met = hw_served(df.loc[met])
            n_met = int(met.sum())
            heat_met = 100 * df.loc[met, "replaceable_heat_mwh_th"].sum() / df["replaceable_heat_mwh_th"].sum()
        else:
            l_met, n_met, heat_met = float("nan"), 0, 0.0
        return l_all, r_all, serve_all, l_met, n_met, heat_met

    l5, r5, s5, l5m, n5m, h5m = stats(df5)
    l15, r15, s15, l15m, n15m, h15m = stats(df15)
    title = (
        f"<div style='position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;"
        f"background:white;padding:10px 16px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.25);"
        f"font-family:sans-serif;font-size:12.5px;text-align:left;max-width:980px;line-height:1.45'>"
        f"<div style='font-size:14px;font-weight:700;margin-bottom:4px'>"
        f"Co-located solar + storage for industrial heat (2030 costs, €)</div>"
        f"<div style='color:#444;margin-bottom:8px'>"
        f"Each site: solar PV with heat pumps + Li-ion (&lt;200 °C) or industrial heat batteries (≥200 °C). "
        f"Optimizer first maximizes heat served, then minimizes €/MWh of that served heat. "
        f"Costs converted from USD at EURUSD={EURUSD:.2f}."
        f"</div>"
        f"<table style='width:100%;border-collapse:collapse;font-size:12px'>"
        f"<tr style='background:#f3f6fa'>"
        f"<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Land buffer</th>"
        f"<th style='text-align:right;padding:4px 8px;border-bottom:1px solid #ddd'>Heat served<br>"
        f"<span style='font-weight:400;color:#666'>(of fleet demand)</span></th>"
        f"<th style='text-align:right;padding:4px 8px;border-bottom:1px solid #ddd'>Avg cost<br>"
        f"<span style='font-weight:400;color:#666'>(all served heat)</span></th>"
        f"<th style='text-align:right;padding:4px 8px;border-bottom:1px solid #ddd'>High-reliability sites (≥90%)<br>"
        f"<span style='font-weight:400;color:#666'>avg cost · share of demand</span></th>"
        f"</tr>"
        f"<tr>"
        f"<td style='padding:4px 8px'><b>5 km</b> (left)</td>"
        f"<td style='text-align:right;padding:4px 8px'>{s5:.0f}%</td>"
        f"<td style='text-align:right;padding:4px 8px'>€{l5:,.0f}/MWh</td>"
        f"<td style='text-align:right;padding:4px 8px'>€{l5m:,.0f}/MWh · {n5m:,} sites · {h5m:.0f}% of demand</td>"
        f"</tr>"
        f"<tr>"
        f"<td style='padding:4px 8px'><b>15 km</b> (right)</td>"
        f"<td style='text-align:right;padding:4px 8px'>{s15:.0f}%</td>"
        f"<td style='text-align:right;padding:4px 8px'>€{l15:,.0f}/MWh</td>"
        f"<td style='text-align:right;padding:4px 8px'>€{l15m:,.0f}/MWh · {n15m:,} sites · {h15m:.0f}% of demand</td>"
        f"</tr>"
        f"</table>"
        f"<div style='color:#666;font-size:11px;margin-top:6px'>"
        f"Marker fill = LCOH · outline = availability met (% of demand served). "
        f"Hover a site for both values; see legend (bottom left)."
        f"</div></div>"
    )

    add_markers(dm.m1, df5, lcoh_cmap, avail_cmap, "5 km land", vmin, vmax)
    add_markers(dm.m2, df15, lcoh_cmap, avail_cmap, "15 km land", vmin, vmax)

    dm.get_root().add_child(PanelLabel("Left: 5 km land buffer", side="left"))
    dm.get_root().add_child(PanelLabel("Right: 15 km land buffer", side="right"))
    dm.m1.get_root().add_child(MapLegend(vmin, vmax))

    out_html.parent.mkdir(parents=True, exist_ok=True)
    dm.save(str(out_html))
    html = out_html.read_text()
    html = html.replace("<body>", f"<body>{title}", 1)
    out_html.write_text(html)

    print(f"Wrote {out_html}")
    print(f"  5 km:  {len(df5)} sites  served {s5:.0f}%  HW €{l5:,.0f}/MWh  rel {r5:.0f}%  "
          f"met90 €{l5m:,.0f}/MWh ({n5m} sites)")
    print(f"  15 km: {len(df15)} sites  served {s15:.0f}%  HW €{l15:,.0f}/MWh  rel {r15:.0f}%  "
          f"met90 €{l15m:,.0f}/MWh ({n15m} sites)")
    print(f"  Color scale €{vmin:,.0f}–€{vmax:,.0f}/MWh  (EURUSD={EURUSD})")

    summary = ROOT / "outputs" / "multiband" / "analysis" / "headline_results_eur.txt"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        "\n".join(
            [
                "Headline multiband results (EUR)",
                f"FX: EURUSD = {EURUSD:.2f}  →  € = $ / {EURUSD:.2f}",
                "Scenarios: land_5km_ss_2030_liion / land_15km_ss_2030_liion",
                "",
                "5 km land:",
                f"  Heat served:              {s5:.0f}% of fleet demand",
                f"  Avg LCOH (all served):    €{l5:,.0f}/MWh",
                f"  ≥90% reliability cohort:  €{l5m:,.0f}/MWh · {n5m:,} sites · {h5m:.0f}% of demand",
                "",
                "15 km land:",
                f"  Heat served:              {s15:.0f}% of fleet demand",
                f"  Avg LCOH (all served):    €{l15:,.0f}/MWh",
                f"  ≥90% reliability cohort:  €{l15m:,.0f}/MWh · {n15m:,} sites · {h15m:.0f}% of demand",
                "",
                "USD equivalents (model native):",
                f"  5 km:  ${l5 * EURUSD:,.0f}/MWh all-served · ${l5m * EURUSD:,.0f}/MWh ≥90%",
                f"  15 km: ${l15 * EURUSD:,.0f}/MWh all-served · ${l15m * EURUSD:,.0f}/MWh ≥90%",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {summary}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--five", type=Path, default=DEFAULT_5)
    ap.add_argument("--fifteen", type=Path, default=DEFAULT_15)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    build_dual_map(args.five, args.fifteen, args.output)


if __name__ == "__main__":
    main()
