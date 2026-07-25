"""Compare old thermal-storage LCOH vs new Li-ion/EI-IHB runs; plot daily dispatch.

    python outputs/multiband/analysis/compare_liion_vs_thermal.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "flatblock_optimization"))
sys.path.insert(0, str(ROOT))

from run_multiband_potential import CONFIG, band_loads_for  # noqa: E402
from solvers.optimize_flatblock_multiband_heatpump import (  # noqa: E402
    run_multiband_heatpump_optimization,
)
from utils.loaders.load_re_costs import load_re_costs  # noqa: E402

OUT = ROOT / "outputs/multiband/analysis"
OUT.mkdir(parents=True, exist_ok=True)


def hw(s: pd.Series, w: pd.Series) -> float:
    m = s.notna() & w.notna() & (w > 0)
    return float((s[m] * w[m]).sum() / w[m].sum()) if m.any() else float("nan")


def load_ok(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    ok = df[df["status"] == "ok"].copy()
    ok["met"] = ok["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
    return ok


def summarize(ok: pd.DataFrame, label: str) -> dict:
    w = ok["replaceable_heat_mwh_th"]
    met = ok[ok["met"]]
    wm = met["replaceable_heat_mwh_th"]
    row = {
        "case": label,
        "n_sites": len(ok),
        "met_sites": int(met["met"].sum()),
        "met_heat_pct": 100.0 * wm.sum() / w.sum(),
        "hw_reliability": hw(ok["Reliability_%"], w),
        "hw_lcoh_all": hw(ok["LCOH_served_$perMWh"], w),
        "hw_lcoh_met": hw(met["LCOH_served_$perMWh"], wm) if len(met) else np.nan,
        "median_lcoh_met": float(met["LCOH_served_$perMWh"].median()) if len(met) else np.nan,
    }
    if "LCOH_liion_$perMWh" in ok.columns:
        row["hw_lcoh_liion_met"] = hw(met["LCOH_liion_$perMWh"], wm) if len(met) else np.nan
        row["hw_lcoh_ihb_met"] = hw(met["LCOH_ihb_$perMWh"], wm) if len(met) else np.nan
        row["hw_lcoh_solar_met"] = hw(met["LCOH_solar_$perMWh"], wm) if len(met) else np.nan
    return row


def compare_fleet() -> pd.DataFrame:
    pairs = [
        ("land_5km_ss_2030", "land_5km_ss_2030_liion", "5 km"),
        ("land_15km_ss_2030", "land_15km_ss_2030_liion", "15 km"),
    ]
    rows = []
    for old_sc, new_sc, land in pairs:
        old_p = ROOT / f"outputs/multiband/{old_sc}/by_facility.csv"
        new_p = ROOT / f"outputs/multiband/{new_sc}/by_facility.csv"
        if not old_p.exists() or not new_p.exists():
            print("MISSING", old_p.exists(), new_p.exists(), old_sc, new_sc)
            continue
        old = load_ok(old_p)
        new = load_ok(new_p)
        rows.append(summarize(old, f"{land} · thermal store (old)"))
        rows.append(summarize(new, f"{land} · Li-ion HP + EI IHB (new)"))

        # site-level delta on met sites in both
        m = old[["source_id", "LCOH_served_$perMWh", "replaceable_heat_mwh_th", "met"]].merge(
            new[["source_id", "LCOH_served_$perMWh", "met"]],
            on="source_id",
            suffixes=("_old", "_new"),
        )
        both = m[m["met_old"] & m["met_new"]].copy()
        both["dLCOH"] = both["LCOH_served_$perMWh_new"] - both["LCOH_served_$perMWh_old"]
        print(
            f"\n{land}: sites met in both={len(both)}; "
            f"HW ΔLCOH ${hw(both['dLCOH'], both['replaceable_heat_mwh_th']):+.1f}/MWh; "
            f"median Δ ${both['dLCOH'].median():+.1f}/MWh"
        )
    return pd.DataFrame(rows)


def pick_sites(assessment: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    """One HP-heavy food site and one IHB-only cement site that meet 90% if possible."""
    new = load_ok(ROOT / "outputs/multiband/land_5km_ss_2030_liion/by_facility.csv")
    food = new[(new["subsector"] == "food-beverage-tobacco") & new["met"]].sort_values(
        "replaceable_heat_mwh_th", ascending=False
    )
    cement = new[(new["subsector"] == "cement") & new["met"]].sort_values(
        "replaceable_heat_mwh_th", ascending=False
    )
    if cement.empty:
        cement = new[(new["subsector"] == "cement")].sort_values(
            "Reliability_%", ascending=False
        )
    picks = []
    if len(food):
        sid = int(food.iloc[0]["source_id"])
        picks.append(("Food (HP + Li-ion)", assessment[assessment["source_id"] == sid].iloc[0]))
    if len(cement):
        sid = int(cement.iloc[0]["source_id"])
        picks.append(("Cement (IHB)", assessment[assessment["source_id"] == sid].iloc[0]))
    return picks


def solve_hourly(row: pd.Series) -> tuple[dict, pd.DataFrame]:
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
        VoLL=CONFIG["VoLL"],
        project_start_year=2030,
        return_hourly=True,
    )
    if not ok or hourly is None:
        raise RuntimeError(f"optimize failed for {sid}")
    return res, hourly


def plot_daily(res: dict, hourly: pd.DataFrame, title: str, outfile: Path) -> None:
    # Weight-heaviest representative day (most common cluster)
    c = int(hourly.groupby("rep_day")["weight_days"].first().idxmax())
    d = hourly[hourly["rep_day"] == c].sort_values("hour")
    hours = d["hour"].to_numpy()

    fig, axes = plt.subplots(3, 1, figsize=(10, 8.5), sharex=True, gridspec_kw={"height_ratios": [1.2, 1, 0.7]})

    ax = axes[0]
    ax.fill_between(hours, 0, d["solar_available_MW"], color="#f4d35e", alpha=0.35, label="Solar available")
    ax.plot(hours, d["solar_to_hp_direct_MW"], color="#2a9d8f", lw=2, label="Solar → HP (direct)")
    ax.plot(hours, d["solar_to_liion_charge_MW"], color="#264653", lw=2, label="Solar → Li-ion charge")
    ax.plot(hours, d["solar_to_ihb_charge_MW"], color="#e76f51", lw=2, label="Solar → IHB charge")
    ax.set_ylabel("Power (MW$_e$)")
    ax.set_title(title + f"  ·  representative day (cluster {c}, {d['weight_days'].iloc[0]:.0f} days/yr)")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.set_xlim(0, 23)

    ax = axes[1]
    ax.plot(hours, d["hp_load_MW"], color="#1d3557", lw=2, ls="--", label="HP heat load")
    ax.plot(hours, d["hp_heat_out_MW"], color="#2a9d8f", lw=2, label="HP heat delivered")
    ax.plot(hours, d["liion_discharge_to_hp_MW"], color="#264653", lw=1.8, label="Li-ion → HP (elec)")
    ax.plot(hours, d["ihb_load_MW"], color="#6d4c41", lw=2, ls="--", label="IHB heat load")
    ax.plot(hours, d["ihb_discharge_heat_MW"], color="#e76f51", lw=2, label="IHB heat discharged")
    ax.set_ylabel("MW$_{th}$ / MW$_e$")
    ax.legend(loc="upper right", fontsize=8, frameon=False, ncol=2)

    ax = axes[2]
    ax.plot(hours, d["liion_soc_MWh"], color="#264653", lw=2, label="Li-ion SOC")
    ax.plot(hours, d["ihb_soc_MWh"], color="#e76f51", lw=2, label="IHB SOC")
    ax.set_ylabel("SOC (MWh)")
    ax.set_xlabel("Hour of day")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.set_xticks(range(0, 24, 2))

    lcoh = res["LCOH_served_$perMWh"]
    rel = res["Reliability_%"]
    fig.text(
        0.01,
        0.01,
        f"LCOH_served ${lcoh:.0f}/MWh · reliability {rel:.0f}% · "
        f"Li-ion {res['liion_energy_MWh']:.0f} MWh / IHB {res['ihb_energy_MWh']:.0f} MWh",
        fontsize=8,
        color="#444",
    )
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(outfile, dpi=160)
    fig.savefig(outfile.with_suffix(".pdf"))
    plt.close(fig)
    print("Wrote", outfile)


def main() -> None:
    summary = compare_fleet()
    if summary.empty:
        print("Fleet outputs not ready yet.")
        return
    summary.to_csv(OUT / "compare_liion_vs_thermal_2030.csv", index=False)
    txt = OUT / "compare_liion_vs_thermal_2030.txt"
    lines = [
        "LCOH comparison: old thermal-storage-for-all-bands vs Li-ion HP + Energy Innovation IHB",
        "Both use 2030 BNEF solar; new case uses BNEF Li-ion + EI IHB CAPEX ($100/$300/$5), country BNEF CRF.",
        "",
        summary.to_string(index=False, float_format=lambda x: f"{x:.1f}"),
        "",
    ]
    txt.write_text("\n".join(lines) + "\n")
    print(txt.read_text())

    # Bar chart of HW LCOH met
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = summary["case"].tolist()
    vals = summary["hw_lcoh_met"].tolist()
    colors = ["#8d99ae" if "old" in c else "#2a9d8f" for c in labels]
    ax.barh(range(len(labels)), vals, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Heat-weighted LCOH among ≥90% sites ($/MWh)")
    ax.set_title("2030 LCOH: thermal store (old) vs Li-ion + EI IHB (new)")
    for i, v in enumerate(vals):
        if np.isfinite(v):
            ax.text(v + 1, i, f"${v:.0f}", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "compare_liion_vs_thermal_lcoh.png", dpi=160)
    plt.close(fig)

    ass = pd.read_csv(ROOT / CONFIG["sites_csv"], low_memory=False)
    for title, row in pick_sites(ass):
        res, hourly = solve_hourly(row)
        safe = title.split("(")[0].strip().lower().replace(" ", "_")
        hourly.to_csv(OUT / f"dispatch_hourly_{safe}_{int(row['source_id'])}.csv", index=False)
        plot_daily(
            res,
            hourly,
            f"{title} · {row.get('source_name', '')[:40]}",
            OUT / f"dispatch_daily_{safe}_{int(row['source_id'])}.png",
        )


if __name__ == "__main__":
    main()
