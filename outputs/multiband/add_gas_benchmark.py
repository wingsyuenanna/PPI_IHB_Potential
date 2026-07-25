"""Attach country gas-boiler heat cost to multiband results and plot HT non-viable sites.

Gas boiler LCOH by country comes from Input/industrial_heat_pump_costs/
(eu_heat_pump_costs_by_country.csv): industrial gas price / 0.85 boiler efficiency
plus EUA carbon (see eu_heat_pump_cost_assumptions.csv). Converted to USD at
EURUSD for comparison with LCOH_served_$perMWh.

Published EU range for citation: Agora Industry / Agora Energiewende,
"The business case for electrifying industrial heat"
https://www.agora-industry.org/fileadmin/Projekte/2023/2023-36_IND_Electrification_low_heat/A-IND_396_The_business_case_for_electrifying_industrial_heat_WEB.pdf
(~EUR 43–100/MWh_th gas-boiler LCOH across fuel/carbon scenarios; central ~EUR 65–72).

    python outputs/multiband/add_gas_benchmark.py
    python outputs/multiband/add_gas_benchmark.py --scenario land_15km_ss
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
ASS = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"
GAS = ROOT / "Input" / "industrial_heat_pump_costs" / "eu_heat_pump_costs_by_country.csv"
BANDS = [
    "heat_below100C_tj",
    "heat_100C-200C_tj",
    "heat_200C-500C_tj",
    "heat_500C-1000C_tj",
    "heat_above1000C_tj",
]
HT = BANDS[2:]
EURUSD = 1.08
GBR_PROXY = "IRL"


def hw(series: pd.Series, weights: pd.Series) -> float:
    m = series.notna() & weights.notna() & (weights > 0)
    return float((series[m] * weights[m]).sum() / weights[m].sum())


def load_gas_map() -> dict[str, float]:
    g = pd.read_csv(GAS).rename(columns={"iso3": "iso3_country"})
    m = g.set_index("iso3_country")["gas_heat_cost_eur_mwh"].to_dict()
    m["GBR"] = m.get(GBR_PROXY, float("nan"))
    return m


def enrich(scenario: str) -> pd.DataFrame:
    opt = pd.read_csv(MULTIBAND / scenario / "by_facility.csv")
    ass = pd.read_csv(ASS, low_memory=False)
    gas_map = load_gas_map()
    keep = ["source_id", "solar_capacity_factor"] + BANDS
    df = opt.merge(ass[keep], on="source_id", how="left")
    ok_mask = df["status"] == "ok"
    df["met_availability_target"] = (
        df["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
    )
    for c in BANDS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    tot = df[BANDS].sum(axis=1).replace(0, np.nan)
    df["ht_share"] = df[HT].sum(axis=1) / tot
    df["gas_heat_cost_eur_mwh"] = df["iso3_country"].map(gas_map)
    df["gas_heat_cost_$perMWh"] = df["gas_heat_cost_eur_mwh"] * EURUSD
    df["below_gas_benchmark"] = df["LCOH_served_$perMWh"] < df["gas_heat_cost_$perMWh"]
    df["viable_90pct_below_gas"] = df["met_availability_target"] & df["below_gas_benchmark"]
    out = MULTIBAND / scenario / "by_facility_with_gas.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(ROOT)}  (ok rows: {int(ok_mask.sum())})")
    return df[ok_mask].copy()


def plot_ht(ok: pd.DataFrame, scenario: str) -> None:
    ht = ok[ok["ht_share"] >= 0.5].copy()
    ht["met"] = ht["met_availability_target"]
    ht["below"] = ht["below_gas_benchmark"]
    ht["viable"] = ht["viable_90pct_below_gas"]
    ht["land_per_load"] = ht["available_land_km2"] / ht["total_load_MW"].replace(0, np.nan)

    out_dir = MULTIBAND / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    groups = [
        ("Fail 90%", ~ht["met"], "#c0392b", "o"),
        ("Met, above gas", ht["met"] & ~ht["below"], "#e67e22", "s"),
        ("Met, below gas", ht["viable"], "#27ae60", "^"),
    ]

    ax = axes[0]
    for label, mask, color, marker in groups:
        d = ht[mask]
        ax.scatter(
            d["solar_capacity_factor"] * 100,
            d["LCOH_served_$perMWh"],
            s=np.sqrt(d["replaceable_heat_mwh_th"].clip(lower=1)) / 8,
            c=color,
            alpha=0.55,
            label=f"{label} (n={len(d)})",
            marker=marker,
            edgecolors="none",
        )
    ax.axhspan(
        ok["gas_heat_cost_$perMWh"].quantile(0.1),
        ok["gas_heat_cost_$perMWh"].quantile(0.9),
        color="gray",
        alpha=0.15,
        label="Gas boiler P10–P90",
    )
    ax.set_xlabel("Solar capacity factor (%)")
    ax.set_ylabel("LCOH served ($/MWh)")
    ax.set_title(f"HT-majority sites ({scenario}): cost vs solar CF")
    ax.set_ylim(0, 250)
    ax.legend(fontsize=8, loc="upper right")

    ax = axes[1]
    for label, mask, color, marker in groups:
        d = ht[mask]
        ax.scatter(
            d["land_per_load"],
            d["Reliability_%"],
            s=np.sqrt(d["replaceable_heat_mwh_th"].clip(lower=1)) / 8,
            c=color,
            alpha=0.55,
            label=label,
            marker=marker,
            edgecolors="none",
        )
    ax.axhline(90, color="k", ls="--", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("Available land per MW load (km² / MW_th)")
    ax.set_ylabel("Reliability (%)")
    ax.set_title("HT-majority: reliability vs land intensity")
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig_path = out_dir / f"ht_fail_cf_land_gas_{scenario}.png"
    fig.savefig(fig_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {fig_path.relative_to(ROOT)}")

    fail = ht[~ht["met"]]
    met = ht[ht["met"]]
    lines = [
        f"Scenario: {scenario}",
        f"EURUSD={EURUSD}; GBR gas proxied to {GBR_PROXY}",
        f"Gas boiler country range: "
        f"${ok['gas_heat_cost_$perMWh'].min():.0f}–${ok['gas_heat_cost_$perMWh'].max():.0f}/MWh "
        f"(HW ${hw(ok['gas_heat_cost_$perMWh'], ok['replaceable_heat_mwh_th']):.0f})",
        f"HT-majority n={len(ht)}, heat={ht['replaceable_heat_mwh_th'].sum()/1e6:.1f} TWh",
        f"  Fail 90%: n={len(fail)}, heat={fail['replaceable_heat_mwh_th'].sum()/1e6:.1f} TWh, "
        f"HW CF {hw(fail['solar_capacity_factor'], fail['replaceable_heat_mwh_th'])*100:.1f}%, "
        f"med CF {fail['solar_capacity_factor'].median()*100:.1f}%",
        f"  Met & below gas: n={ht['viable'].sum()}, "
        f"heat={ht.loc[ht['viable'], 'replaceable_heat_mwh_th'].sum()/1e6:.1f} TWh, "
        f"HW CF {hw(ht.loc[ht['viable'], 'solar_capacity_factor'], ht.loc[ht['viable'], 'replaceable_heat_mwh_th'])*100:.1f}%",
        f"  HT fail med CF {fail['solar_capacity_factor'].median()*100:.1f}% vs HT met "
        f"{met['solar_capacity_factor'].median()*100:.1f}% — solar is not the main separator",
        "Cite: Agora Industry & Agora Energiewende, The business case for electrifying industrial heat "
        "(PDF linked in script docstring).",
    ]
    (out_dir / f"ht_nonviable_vs_gas_{scenario}.txt").write_text("\n".join(lines) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="land_5km_ss_2030")
    args = p.parse_args()
    ok = enrich(args.scenario)
    plot_ht(ok, args.scenario)


if __name__ == "__main__":
    main()
