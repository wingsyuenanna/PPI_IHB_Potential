"""Write fleet summary txt + figures for a multiband scenario folder.

    python outputs/multiband/summarize_scenario.py land_5km
    python outputs/multiband/summarize_scenario.py land_15km
    python outputs/multiband/summarize_scenario.py land_15km --compare land_5km
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MULTIBAND = ROOT / "outputs" / "multiband"


def hw(series: pd.Series, weights: pd.Series) -> float:
    m = series.notna() & weights.notna() & (weights > 0)
    return float((series[m] * weights[m]).sum() / weights[m].sum())


def load_ok(scenario: str) -> pd.DataFrame:
    path = MULTIBAND / scenario / "by_facility.csv"
    df = pd.read_csv(path)
    ok = df[df["status"] == "ok"].copy()
    ok["served_mwh"] = ok["Reliability_%"] / 100.0 * ok["replaceable_heat_mwh_th"]
    ok["hp_share"] = ok["hp_load_MW"] / ok["total_load_MW"].replace(0, np.nan)
    ok["ihb_share"] = ok["ihb_load_MW"] / ok["total_load_MW"].replace(0, np.nan)
    return ok


def summarize(scenario: str, compare: str | None = None) -> Path:
    ok = load_ok(scenario)
    w = ok["replaceable_heat_mwh_th"]
    out_dir = MULTIBAND / scenario / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def add(s: str = "") -> None:
        lines.append(s)

    add("=" * 72)
    add(f"MULTI-BAND HP + IHB — SCENARIO: {scenario}")
    add("Base params: 16 rep-days, 16 h storage, 92% RTE, 4x converter, 50 MWdc/km2, 2025 costs")
    add("=" * 72)
    add("")
    add("HEAT")
    add(f"  Sites ok:                 {len(ok):,}")
    add(f"  Replaceable heat:         {w.sum()/1e6:,.1f} TWh/y")
    add(f"  Served heat:              {ok['served_mwh'].sum()/1e6:,.1f} TWh/y")
    add(f"  Unserved:                 {ok['Unserved_MWh'].sum()/1e6:,.1f} TWh/y")
    add(f"  Heat-weighted reliability:{hw(ok['Reliability_%'], w):.1f}%")
    add(f"  Median reliability:       {ok['Reliability_%'].median():.1f}%")
    add("")
    add("COST (LCOH of served heat)")
    add(f"  Heat-weighted LCOH:       ${hw(ok['LCOH_served_$perMWh'], w):,.0f}/MWh")
    add(f"  Median LCOH:              ${ok['LCOH_served_$perMWh'].median():,.0f}/MWh")
    add(f"  P10 / P90:                ${ok['LCOH_served_$perMWh'].quantile(0.1):,.0f} / "
        f"${ok['LCOH_served_$perMWh'].quantile(0.9):,.0f}/MWh")
    add("")
    add("SIZING")
    add(f"  Total solar capacity:     {ok['S_opt_MW'].sum()/1e3:,.1f} GWdc")
    add(f"  Total storage energy:     {ok['storage_energy_MWh_total'].sum()/1e3:,.1f} GWh_th")
    add(f"  Median solar intensity:   {ok['solar_per_load_MWdc_per_MWth'].median():.1f} MWdc/MWth")
    add(f"  HW solar intensity:       {hw(ok['solar_per_load_MWdc_per_MWth'], w):.1f} MWdc/MWth")
    add(f"  Median available land:    {ok['available_land_km2'].median():.1f} km2")
    add(f"  HP / IHB load share (HW): {hw(ok['hp_share'], w)*100:.0f}% / {hw(ok['ihb_share'], w)*100:.0f}%")

    if compare:
        base = load_ok(compare)
        bw = base["replaceable_heat_mwh_th"]
        add("")
        add(f"DELTA vs {compare}")
        add(f"  Served heat:              {ok['served_mwh'].sum()/1e6 - base['served_mwh'].sum()/1e6:+.1f} TWh/y")
        add(f"  HW reliability:           {hw(ok['Reliability_%'], w) - hw(base['Reliability_%'], bw):+.1f} pp")
        add(f"  Median reliability:       {ok['Reliability_%'].median() - base['Reliability_%'].median():+.1f} pp")
        add(f"  HW LCOH:                  ${hw(ok['LCOH_served_$perMWh'], w) - hw(base['LCOH_served_$perMWh'], bw):+.0f}/MWh")
        add(f"  Total solar:              {(ok['S_opt_MW'].sum() - base['S_opt_MW'].sum())/1e3:+.1f} GWdc")

    def sector_table(g: pd.DataFrame) -> pd.Series:
        wt = g["replaceable_heat_mwh_th"]
        return pd.Series({
            "n_sites": len(g),
            "heat_TWh": wt.sum() / 1e6,
            "served_TWh": g["served_mwh"].sum() / 1e6,
            "hw_LCOH": (g["LCOH_served_$perMWh"] * wt).sum() / wt.sum(),
            "hw_reliability_%": (g["Reliability_%"] * wt).sum() / wt.sum(),
        })

    sec = (ok.groupby("subsector", group_keys=False)
           .apply(sector_table, include_groups=False)
           .sort_values("heat_TWh", ascending=False)
           .round(2))
    add("")
    add("BY SUBSECTOR (heat-weighted)")
    add(f"  {'subsector':<32} {'n':>5} {'heat_TWh':>9} {'served':>8} {'LCOH':>7} {'rel%':>6}")
    for s, r in sec.iterrows():
        add(f"  {s:<32} {int(r.n_sites):5d} {r.heat_TWh:9.1f} {r.served_TWh:8.1f} "
            f"{r.hw_LCOH:7.0f} {r['hw_reliability_%']:6.0f}")
    add("=" * 72)

    summary_path = out_dir / "summary.txt"
    summary_path.write_text("\n".join(lines) + "\n")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(ok["LCOH_served_$perMWh"].clip(upper=500), bins=40, color="#2c7fb8", edgecolor="white")
    axes[0].axvline(hw(ok["LCOH_served_$perMWh"], w), color="#e34a33", lw=2,
                    label=f"HW ${hw(ok['LCOH_served_$perMWh'], w):.0f}")
    axes[0].set_xlabel("LCOH served ($/MWh)"); axes[0].set_title(f"{scenario}: LCOH")
    axes[0].legend(frameon=False)
    axes[1].hist(ok["Reliability_%"], bins=40, color="#31a354", edgecolor="white")
    axes[1].axvline(hw(ok["Reliability_%"], w), color="#e34a33", lw=2,
                    label=f"HW {hw(ok['Reliability_%'], w):.0f}%")
    axes[1].axvline(ok["Reliability_%"].median(), color="#fdae61", lw=2, ls="--",
                    label=f"median {ok['Reliability_%'].median():.0f}%")
    axes[1].set_xlabel("Reliability (%)"); axes[1].set_title(f"{scenario}: reliability")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / "lcoh_reliability_hist.png", dpi=150, bbox_inches="tight")
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 4.5))
    plot = sec.sort_values("hw_LCOH")
    ax.barh(plot.index, plot["hw_LCOH"], color="#2c7fb8")
    ax.set_xlabel("Heat-weighted LCOH served ($/MWh)")
    ax.set_title(f"{scenario}: LCOH by subsector")
    fig.tight_layout()
    fig.savefig(out_dir / "lcoh_by_subsector.png", dpi=150, bbox_inches="tight")
    plt.close()

    print(summary_path.read_text())
    print(f"Wrote {summary_path}")
    return summary_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", help="Scenario folder under outputs/multiband/")
    ap.add_argument("--compare", default=None, help="Baseline scenario for deltas")
    args = ap.parse_args()
    summarize(args.scenario, compare=args.compare)


if __name__ == "__main__":
    main()
