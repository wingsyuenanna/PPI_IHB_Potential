"""Quick screen: flat vs Hotmaps diurnal heat shape on a sample of sites.

For each Climate TRACE subsector with a Hotmaps profile, sample a few sites,
re-solve flat and with mean diurnal shape (normalized mean=1), compare LCOH.

    python outputs/multiband/screen_heat_profiles.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flatblock_optimization"))

from run_multiband_potential import CONFIG, band_loads_for  # noqa: E402
from solvers.optimize_flatblock_multiband_heatpump import (  # noqa: E402
    run_multiband_heatpump_optimization,
)
from utils.loaders.load_re_costs import load_re_costs  # noqa: E402

BANDS = ["heat_below100C_tj", "heat_100C-200C_tj", "heat_200C-500C_tj",
         "heat_500C-1000C_tj", "heat_above1000C_tj"]
LT_BANDS = {"heat_below100C_tj", "heat_100C-200C_tj"}

ISO3_TO_NUTS0 = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "EL",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
    "SVN": "SI", "ESP": "ES", "SWE": "SE", "GBR": "UK",
}

N_PER_SECTOR = 3
PROFILE_DIR = ROOT / "Input" / "hotmaps_load_profiles" / "yearlong_2018"
MAP_CSV = ROOT / "Input" / "hotmaps_load_profiles" / "sector_mapping.csv"
SITES = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"
BASE_RES = ROOT / "outputs" / "multiband" / "land_5km_ss" / "by_facility.csv"
OUT = ROOT / "outputs" / "multiband" / "analysis" / "heat_profile_screen.csv"


def diurnal_shape(process: str, nuts0: str) -> np.ndarray:
    path = PROFILE_DIR / f"{process}.csv"
    df = pd.read_csv(path)
    g = df[df["NUTS0_code"] == nuts0]
    if g.empty:
        g = df[df["NUTS0_code"] == "DE"]
    if g.empty:
        g = df[df["NUTS0_code"] == df["NUTS0_code"].iloc[0]]
    load = g["load"].to_numpy(dtype=float)
    # Hotmaps hour 1..8760; reshape to days × 24
    n = (len(load) // 24) * 24
    day = load[:n].reshape(-1, 24).mean(axis=0)
    return day / day.mean()


def lt_share(row: dict) -> float:
    tot = sum(float(row.get(b, 0) or 0) for b in BANDS)
    if tot <= 0:
        return 0.0
    return sum(float(row.get(b, 0) or 0) for b in LT_BANDS) / tot


def solve_one(row: dict, shape: np.ndarray | None) -> dict:
    sid = int(row["source_id"])
    iso = str(row["iso3_country"])
    price_iso = CONFIG["gbr_proxy"] if iso == "GBR" else iso
    bl = band_loads_for(row)
    solar = pd.read_parquet(
        ROOT / CONFIG["solar_hourly_dir"] / f"{sid}_{CONFIG['solar_year']}.parquet",
        columns=["timestamp", "year", "P_kWperkWp"],
    )
    solar["timestamp"] = pd.to_datetime(solar["timestamp"])
    costs = load_re_costs(
        str(ROOT / CONFIG["bnef_costs_csv"]),
        str(ROOT / CONFIG["battery_costs_csv"]),
        price_iso,
        CONFIG["project_start"],
    )
    land = float(row.get("available_land_km2", 0) or 0)
    res, _, ok = run_multiband_heatpump_optimization(
        sid, CONFIG["availability"], solar, costs, bl,
        round_trip_efficiency=CONFIG["round_trip_efficiency"],
        max_storage_hours=CONFIG["max_storage_hours"],
        n_representative_days=CONFIG["n_representative_days"],
        max_solar_mw=(land * CONFIG["mw_per_km2"]) if land >= 0 else None,
        VoLL=CONFIG["VoLL"],
        project_start_year=int(CONFIG["project_start"]),
        diurnal_shape_24=shape,
    )
    if not ok or res is None:
        return {"status": "fail"}
    return {
        "status": "ok",
        "LCOH": float(res["LCOH_served_$perMWh"]),
        "rel": float(res["Reliability_%"]),
        "met": bool(res["met_availability_target"]),
        "S": float(res["S_opt_MW"]),
        "E": float(res["storage_energy_MWh_total"]),
        "S_per_load": float(res["solar_per_load_MWdc_per_MWth"]),
    }


def main() -> None:
    mapping = pd.read_csv(MAP_CSV)
    mapping = mapping[mapping["hotmaps_process"].notna() & (mapping["hotmaps_process"] != "")]
    sites = pd.read_csv(SITES, low_memory=False)
    base = pd.read_csv(BASE_RES)
    base = base[base["status"] == "ok"][["source_id", "met_availability_target",
                                          "LCOH_served_$perMWh", "Reliability_%"]].rename(
        columns={"LCOH_served_$perMWh": "lcoh_base_csv", "Reliability_%": "rel_base_csv"}
    )
    df = sites.merge(base, on="source_id", how="inner")
    df = df[df["has_solar_data"] & df["has_replaceable_heat"]].copy()
    df["lt_share"] = df.apply(lambda r: lt_share(r.to_dict()), axis=1)
    df = df.merge(mapping, left_on="subsector", right_on="climate_trace_subsector", how="inner")
    df["nuts0"] = df["iso3_country"].map(ISO3_TO_NUTS0)
    df = df[df["nuts0"].notna()]

    # Sample: prefer met-90% sites with mid heat; 3 per subsector
    samples = []
    for sec, g in df.groupby("subsector"):
        g = g.sort_values("replaceable_heat_mwh_th", ascending=False)
        met = g[g["met_availability_target"].astype(str).str.lower().isin(["true", "1"])]
        pool = met if len(met) >= N_PER_SECTOR else g
        # spread: take high / mid / lower heat among pool
        idx = np.linspace(0, len(pool) - 1, num=min(N_PER_SECTOR, len(pool)), dtype=int)
        samples.append(pool.iloc[idx])
    sample = pd.concat(samples, ignore_index=True)
    print(f"Screening {len(sample)} sites across {sample['subsector'].nunique()} subsectors...")

    rows = []
    for i, r in sample.iterrows():
        row = r.to_dict()
        process = row["hotmaps_process"]
        nuts0 = row["nuts0"]
        shape = diurnal_shape(process, nuts0)
        day_night = float(shape[8:18].mean() / np.concatenate([shape[0:6], shape[22:24]]).mean())
        print(f"  {row['subsector'][:22]:22s} {row['source_id']} "
              f"LT={100*row['lt_share']:.0f}% day/night={day_night:.3f} ...", flush=True)
        flat = solve_one(row, None)
        prof = solve_one(row, shape)
        if flat["status"] != "ok" or prof["status"] != "ok":
            print("    FAIL", flat.get("status"), prof.get("status"))
            continue
        rows.append({
            "source_id": row["source_id"],
            "source_name": row.get("source_name", ""),
            "subsector": row["subsector"],
            "iso3": row["iso3_country"],
            "hotmaps_process": process,
            "lt_share": row["lt_share"],
            "heat_mwh": row["replaceable_heat_mwh_th"],
            "shape_day_night": day_night,
            "shape_cv": float(shape.std() / shape.mean()),
            "lcoh_flat": flat["LCOH"],
            "lcoh_profile": prof["LCOH"],
            "dlcoh": prof["LCOH"] - flat["LCOH"],
            "dlcoh_pct": 100 * (prof["LCOH"] - flat["LCOH"]) / flat["LCOH"] if flat["LCOH"] else np.nan,
            "rel_flat": flat["rel"],
            "rel_profile": prof["rel"],
            "met_flat": flat["met"],
            "met_profile": prof["met"],
            "S_flat": flat["S"],
            "S_profile": prof["S"],
            "E_flat": flat["E"],
            "E_profile": prof["E"],
            "dE_pct": 100 * (prof["E"] - flat["E"]) / flat["E"] if flat["E"] else np.nan,
        })

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"\nWrote {OUT} ({len(out)} rows)")

    # Summary by subsector
    print("\n=== Mean ΔLCOH (profile − flat) by subsector ===")
    summ = out.groupby("subsector").agg(
        n=("source_id", "count"),
        mean_lt=("lt_share", "mean"),
        mean_day_night=("shape_day_night", "mean"),
        mean_dlcoh=("dlcoh", "mean"),
        mean_dlcoh_pct=("dlcoh_pct", "mean"),
        mean_dE_pct=("dE_pct", "mean"),
        med_lcoh_flat=("lcoh_flat", "median"),
    ).sort_values("mean_lt", ascending=False)
    print(summ.to_string(float_format=lambda x: f"{x:.2f}"))

    lt = out[out["lt_share"] >= 0.5]
    ht = out[out["lt_share"] < 0.5]
    print(f"\nLT-majority sites (lt_share≥50%, n={len(lt)}): "
          f"mean ΔLCOH ${lt['dlcoh'].mean():.2f}/MWh ({lt['dlcoh_pct'].mean():.2f}%)")
    print(f"HT-majority sites (lt_share<50%, n={len(ht)}): "
          f"mean ΔLCOH ${ht['dlcoh'].mean():.2f}/MWh ({ht['dlcoh_pct'].mean():.2f}%)")
    print(f"Overall mean ΔLCOH ${out['dlcoh'].mean():.2f}/MWh; "
          f"sites with LCOH drop: {(out['dlcoh'] < -0.05).sum()}/{len(out)}")


if __name__ == "__main__":
    main()
