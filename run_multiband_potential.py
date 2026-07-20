"""Fleet runner for the multi-band heat-pump + IHB hourly optimizer.

For every runnable site (solar profile + positive replaceable heat), splits replaceable
heat into temperature bands, sizes one shared on-site solar array + per-band heat pumps
(<200 C) / resistive+thermal-battery (>200 C) over representative days, capped by land,
and writes per-site LCOH / reliability / sizing to outputs/multiband_hp_ihb_by_facility.csv.

Base case: 4x converter (daily solar cycling), COP 2.7/1.8, 50 MWdc/km2, 16 h storage,
92% RTE, 16 representative days, 2025 costs. Edit CONFIG for sensitivity runs.

    python run_multiband_potential.py                 # full fleet
    python run_multiband_potential.py --limit 50      # quick subset
    python run_multiband_potential.py --subsector cement
"""
from __future__ import annotations

import argparse
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "flatblock_optimization"))

BANDS = ["heat_below100C_tj", "heat_100C-200C_tj", "heat_200C-500C_tj",
         "heat_500C-1000C_tj", "heat_above1000C_tj"]

CONFIG = {
    "sites_csv": "outputs/eu_ihb_site_assessment_2024.csv",
    "bnef_costs_csv": "Input/bnef_country_costs.csv",
    "battery_costs_csv": "flatblock_optimization/inputs/input_heat_battery_cost.csv",
    "solar_hourly_dir": "solar_radiation/outputs/hourly_profiles",
    "solar_year": 2023,
    "project_start": "2025",
    "gbr_proxy": "IRL",                 # GBR not in EU cost tables; proxy to Ireland
    # optimizer parameters (base case)
    "availability": 0.90,
    "mw_per_km2": 50.0,
    "round_trip_efficiency": 0.92,
    "max_storage_hours": 16.0,
    "charge_discharge_ratio_min": 4.0,
    "n_representative_days": 16,
    "VoLL": 2000.0,
    "output": "outputs/multiband_hp_ihb_by_facility.csv",
    "max_workers": 8,
}


def band_loads_for(row: dict) -> dict:
    total = sum(float(row.get(b, 0) or 0) for b in BANDS)
    repl = float(row.get("replaceable_heat_mwh_th", 0) or 0)
    if total <= 0 or repl <= 0:
        return {}
    return {b: repl * (float(row.get(b, 0) or 0) / total) / 8760.0 for b in BANDS}


def run_one_site(row: dict, cfg: dict) -> dict:
    from utils.loaders.load_re_costs import load_re_costs
    from solvers.optimize_flatblock_multiband_heatpump import run_multiband_heatpump_optimization

    sid = int(row["source_id"])
    iso = str(row["iso3_country"])
    price_iso = cfg["gbr_proxy"] if (iso == "GBR" and cfg["gbr_proxy"]) else iso
    base = {"source_id": sid, "source_name": row.get("source_name", ""), "iso3_country": iso,
            "subsector": row.get("subsector", "")}
    bl = band_loads_for(row)
    if not bl:
        return {**base, "status": "no_load"}
    try:
        solar = pd.read_parquet(_ROOT / cfg["solar_hourly_dir"] / f"{sid}_{cfg['solar_year']}.parquet",
                                columns=["timestamp", "year", "P_kWperkWp"])
        solar["timestamp"] = pd.to_datetime(solar["timestamp"])
        costs = load_re_costs(str(_ROOT / cfg["bnef_costs_csv"]), str(_ROOT / cfg["battery_costs_csv"]),
                              price_iso, cfg["project_start"])
        land_km2 = float(row.get("available_land_km2", 0) or 0)
        res, _, ok = run_multiband_heatpump_optimization(
            sid, cfg["availability"], solar, costs, bl,
            round_trip_efficiency=cfg["round_trip_efficiency"],
            max_storage_hours=cfg["max_storage_hours"],
            charge_discharge_ratio_min=cfg["charge_discharge_ratio_min"],
            n_representative_days=cfg["n_representative_days"],
            max_solar_mw=land_km2 * cfg["mw_per_km2"] if land_km2 > 0 else None,
            VoLL=cfg["VoLL"], project_start_year=int(cfg["project_start"]))
        if not ok:
            return {**base, "status": "not_optimal"}
        keep = {k: v for k, v in res.items() if k != "bands"}
        return {**base, "status": "ok", "available_land_km2": land_km2,
                "replaceable_heat_mwh_th": float(row["replaceable_heat_mwh_th"]), **keep}
    except Exception as e:
        return {**base, "status": "error", "error": f"{e}", "trace": traceback.format_exc()[-400:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--subsector", type=str, default=None)
    ap.add_argument("--max-workers", type=int, default=CONFIG["max_workers"])
    ap.add_argument("--output", type=str, default=CONFIG["output"])
    args = ap.parse_args()

    df = pd.read_csv(_ROOT / CONFIG["sites_csv"], low_memory=False)
    run = df[df["has_solar_data"] & df["has_replaceable_heat"]].copy()
    if args.subsector:
        run = run[run["subsector"] == args.subsector]
    if args.limit:
        run = run.sort_values("replaceable_heat_mwh_th", ascending=False).head(args.limit)
    rows = run.to_dict("records")
    print(f"Running multi-band optimizer on {len(rows)} sites "
          f"({CONFIG['n_representative_days']} rep-days, {args.max_workers} workers)...")

    results = []
    with ProcessPoolExecutor(max_workers=args.max_workers) as ex:
        futs = {ex.submit(run_one_site, r, CONFIG): int(r["source_id"]) for r in rows}
        done = 0
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(rows)}")

    out = pd.DataFrame(results)
    out_path = _ROOT / args.output
    out.to_csv(out_path, index=False)
    ok = out[out["status"] == "ok"]
    print(f"\nWrote {len(out)} rows to {args.output}  (ok: {len(ok)}, "
          f"failed: {len(out) - len(ok)})")
    if len(ok):
        w = ok["replaceable_heat_mwh_th"]
        print(f"Heat-weighted LCOH_served: ${(ok['LCOH_served_$perMWh'] * w).sum() / w.sum():,.0f}/MWh")
        print(f"Heat-weighted reliability: {(ok['Reliability_%'] * w).sum() / w.sum():.0f}%")
        print(f"Median solar intensity: {ok['solar_per_load_MWdc_per_MWth'].median():.1f} MWdc/MWth")
        print("\nstatus counts:")
        print(out["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
