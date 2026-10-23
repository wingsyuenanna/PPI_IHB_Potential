"""Solve a few sites and plot flat heat load vs storage charge/discharge.

Uses updated band shares on eu_ihb_site_assessment_2024.csv and 2030 Li-ion + IHB costs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flatblock_optimization"))

from run_multiband_potential import CONFIG, band_loads_for  # noqa: E402
from solvers.optimize_flatblock_multiband_heatpump import (  # noqa: E402
    run_multiband_heatpump_optimization,
)
from utils.loaders.load_re_costs import load_re_costs  # noqa: E402

OUT = Path(__file__).resolve().parent
SITES = ROOT / CONFIG["sites_csv"]


def solve(row: pd.Series) -> tuple[dict, pd.DataFrame]:
    r = row.to_dict()
    sid = int(r["source_id"])
    iso = str(r["iso3_country"])
    if iso == "GBR":
        iso = CONFIG["gbr_proxy"]
    bl = band_loads_for(r)
    solar = pd.read_parquet(
        ROOT / CONFIG["solar_hourly_dir"] / f"{sid}_{CONFIG['solar_year']}.parquet",
        columns=["timestamp", "year", "P_kWperkWp"],
    )
    solar["timestamp"] = pd.to_datetime(solar["timestamp"])
    costs = load_re_costs(
        str(ROOT / CONFIG["bnef_costs_csv"]),
        str(ROOT / CONFIG["battery_costs_csv"]),
        iso,
        2030,
    )
    land = float(r.get("available_land_km2") or 0)
    res, hourly, ok = run_multiband_heatpump_optimization(
        sid,
        CONFIG["availability"],
        solar,
        costs,
        bl,
        round_trip_efficiency=CONFIG["round_trip_efficiency"],
        max_storage_hours=CONFIG["max_storage_hours"],
        n_representative_days=CONFIG["n_representative_days"],
        max_solar_mw=(land * CONFIG["mw_per_km2"]) if land >= 0 else None,
        project_start_year=2030,
        return_hourly=True,
    )
    if not ok or hourly is None:
        raise RuntimeError(f"optimize failed for {sid}")
    return res, hourly


def pick_sites(ass: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    """One HP-only (paper or dairy food) and one IHB (cement)."""
    picks: list[tuple[str, pd.Series]] = []

    paper = ass[ass["subsector"] == "pulp-and-paper"].sort_values(
        "replaceable_heat_mwh_th", ascending=False
    )
    if len(paper):
        picks.append(("Pulp & paper (HP + Li-ion)", paper.iloc[0]))

    food = ass[ass["subsector"] == "food-beverage-tobacco"].copy()
    # Prefer HP-only: no ≥200 °C band heat
    ht = (
        food["heat_200C-500C_tj"].fillna(0)
        + food["heat_500C-1000C_tj"].fillna(0)
        + food["heat_above1000C_tj"].fillna(0)
    )
    dairyish = food[ht <= 0].sort_values("replaceable_heat_mwh_th", ascending=False)
    if len(dairyish):
        picks.append(("Food HP-only (Li-ion)", dairyish.iloc[0]))

    cement = ass[ass["subsector"] == "cement"].sort_values(
        "replaceable_heat_mwh_th", ascending=False
    )
    if len(cement):
        picks.append(("Cement (IHB)", cement.iloc[0]))

    sugar = food[ht > 0].sort_values("replaceable_heat_mwh_th", ascending=False)
    if len(sugar):
        picks.append(("Food sugar/bakery (HP + IHB)", sugar.iloc[0]))
    return picks


def plot_flat_charge_discharge(
    res: dict, hourly: pd.DataFrame, title: str, outfile: Path
) -> None:
    c = int(hourly.groupby("rep_day")["weight_days"].first().idxmax())
    d = hourly[hourly["rep_day"] == c].sort_values("hour")
    hours = d["hour"].to_numpy()

    flat_load = (d["hp_load_MW"] + d["ihb_load_MW"]).to_numpy()
    charge = (d["solar_to_liion_charge_MW"] + d["solar_to_ihb_charge_MW"]).to_numpy()
    # Heat-side discharge: Li-ion elec × implied via hp path is messy; show
    # Li-ion discharge (elec) and IHB heat discharge, plus net storage flow.
    li_dis = d["liion_discharge_to_hp_MW"].to_numpy()
    ihb_dis = d["ihb_discharge_heat_MW"].to_numpy()
    hp_heat = d["hp_heat_out_MW"].to_numpy()
    solar_direct = d["solar_to_hp_direct_MW"].to_numpy()

    fig, axes = plt.subplots(
        2, 1, figsize=(9.5, 6.2), sharex=True, gridspec_kw={"height_ratios": [1.15, 1]}
    )

    ax = axes[0]
    ax.axhline(flat_load[0], color="#1d3557", lw=2.4, label=f"Flat heat load ({flat_load[0]:.1f} MW$_{{th}}$)")
    ax.fill_between(hours, 0, d["solar_available_MW"], color="#f4d35e", alpha=0.35, label="Solar available (MW$_e$)")
    ax.plot(hours, solar_direct, color="#2a9d8f", lw=1.8, label="Solar → HP direct (MW$_e$)")
    ax.plot(hours, charge, color="#e9c46a", lw=2, label="Storage charge (Li-ion + IHB)")
    ax.set_ylabel("MW")
    ax.set_title(
        title
        + f"  ·  rep. day cluster {c} ({d['weight_days'].iloc[0]:.0f} days/yr)"
    )
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.set_xlim(0, 23)

    ax = axes[1]
    ax.axhline(flat_load[0], color="#1d3557", lw=1.5, ls=":", alpha=0.8, label="Flat heat load")
    ax.plot(hours, charge, color="#e9c46a", lw=2, label="Charge (to storage)")
    ax.plot(hours, -li_dis, color="#264653", lw=2, label="Li-ion discharge (elec → HP)")
    ax.plot(hours, -ihb_dis, color="#e76f51", lw=2, label="IHB discharge (heat)")
    if hp_heat.max() > 0.05:
        ax.plot(hours, hp_heat, color="#2a9d8f", lw=1.6, ls="--", label="HP heat delivered")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_ylabel("MW (discharge negative)")
    ax.set_xlabel("Hour of day")
    ax.legend(loc="upper right", fontsize=8, frameon=False, ncol=2)
    ax.set_xticks(range(0, 24, 2))

    fig.text(
        0.01,
        0.01,
        f"LCOH_served ${res['LCOH_served_$perMWh']:.0f}/MWh · reliability {res['Reliability_%']:.0f}% · "
        f"Li-ion {res['liion_energy_MWh']:.0f} MWh · IHB {res['ihb_energy_MWh']:.0f} MWh",
        fontsize=8,
        color="#444",
    )
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(outfile, dpi=160)
    plt.close(fig)
    print("Wrote", outfile)


def main() -> None:
    ass = pd.read_csv(SITES, low_memory=False)
    for title, row in pick_sites(ass):
        print(f"Solving {int(row['source_id'])}: {title} — {str(row.get('source_name',''))[:50]}")
        res, hourly = solve(row)
        safe = (
            title.split("(")[0]
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("&", "and")
            .replace("/", "_")
        )
        sid = int(row["source_id"])
        hourly.to_csv(OUT / f"dispatch_hourly_{safe}_{sid}.csv", index=False)
        plot_flat_charge_discharge(
            res,
            hourly,
            f"{title} · {str(row.get('source_name', ''))[:36]}",
            OUT / f"dispatch_flat_cd_{safe}_{sid}.png",
        )


if __name__ == "__main__":
    main()
