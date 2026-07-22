"""Fleet runner for the multi-band heat-pump + IHB hourly optimizer.

For every runnable site (solar profile + positive replaceable heat), splits replaceable
heat into temperature bands, sizes one shared on-site solar array + per-band heat pumps
(<200 C) / resistive+thermal-battery (>200 C) over representative days, capped by land,
and writes per-site LCOH / reliability / sizing under outputs/multiband/<scenario>/.

Solar + thermal-storage LCOH only (no VoLL). Hard 90% availability floor; land-limited
sites get max-serve then cost-min. COP 2.7/1.8/1.0, 50 MWdc/km2, 16 h storage, 92% RTE,
16 rep-days, 2025 costs.

Heat sensitivity (sector low/base/high bounds on assessment CSV):

    python heat_demand/facilities/heat_sensitivity_bounds.py
    python run_multiband_potential.py --scenario land_5km_ss --heat-case base
    python run_multiband_potential.py --scenario land_5km_ss --heat-case low
    python run_multiband_potential.py --scenario land_5km_ss --heat-case high
    python run_multiband_potential.py --scenario land_15km_ss --heat-case low \\
        --land-csv land_availability/outputs/land_availability_by_facility_15km.csv
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

HEAT_CASE_COL = {
    "base": "replaceable_heat_mwh_th",
    "low": "replaceable_heat_mwh_th_low",
    "high": "replaceable_heat_mwh_th_high",
}

CONFIG = {
    "sites_csv": "outputs/eu_ihb_site_assessment_2024.csv",
    "bnef_costs_csv": "Input/bnef_country_costs.csv",
    "battery_costs_csv": "flatblock_optimization/inputs/input_heat_battery_cost.csv",
    "solar_hourly_dir": "solar_radiation/outputs/hourly_profiles",
    "solar_year": 2023,
    "project_start": "2025",
    "gbr_proxy": "IRL",
    "availability": 0.90,
    "mw_per_km2": 50.0,
    "round_trip_efficiency": 0.92,
    "max_storage_hours": 16.0,
    "n_representative_days": 16,
    "VoLL": 0.0,
    "output": "outputs/multiband/land_5km_ss/by_facility.csv",
    "max_workers": 8,
}


def band_loads_for(row: dict) -> dict:
    total = sum(float(row.get(b, 0) or 0) for b in BANDS)
    repl = float(row.get("replaceable_heat_mwh_th", 0) or 0)
    if total <= 0 or repl <= 0:
        return {}
    return {b: repl * (float(row.get(b, 0) or 0) / total) / 8760.0 for b in BANDS}


def apply_heat_case(df: pd.DataFrame, heat_case: str) -> pd.DataFrame:
    """Set working replaceable_heat_mwh_th from low/base/high bound columns."""
    if heat_case not in HEAT_CASE_COL:
        raise ValueError(f"heat_case must be one of {list(HEAT_CASE_COL)}")
    col = HEAT_CASE_COL[heat_case]
    out = df.copy()
    if heat_case == "base":
        if "replaceable_heat_mwh_th" not in out.columns:
            raise KeyError("replaceable_heat_mwh_th missing")
        out["heat_case"] = "base"
        return out
    if col not in out.columns:
        raise KeyError(
            f"{col} missing — run: python heat_demand/facilities/heat_sensitivity_bounds.py"
        )
    out["replaceable_heat_mwh_th_base"] = out["replaceable_heat_mwh_th"]
    out["replaceable_heat_mwh_th"] = pd.to_numeric(out[col], errors="coerce")
    out["has_replaceable_heat"] = out["replaceable_heat_mwh_th"].fillna(0) > 0
    out["heat_case"] = heat_case
    return out


def run_one_site(row: dict, cfg: dict) -> dict:
    from utils.loaders.load_re_costs import load_re_costs
    from solvers.optimize_flatblock_multiband_heatpump import run_multiband_heatpump_optimization

    sid = int(row["source_id"])
    iso = str(row["iso3_country"])
    price_iso = cfg["gbr_proxy"] if (iso == "GBR" and cfg["gbr_proxy"]) else iso
    base = {"source_id": sid, "source_name": row.get("source_name", ""), "iso3_country": iso,
            "subsector": row.get("subsector", ""),
            "heat_case": row.get("heat_case", "base")}
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
            n_representative_days=cfg["n_representative_days"],
            max_solar_mw=(land_km2 * cfg["mw_per_km2"]) if land_km2 >= 0 else None,
            VoLL=cfg["VoLL"],
            project_start_year=int(cfg["project_start"]))
        if not ok:
            return {**base, "status": "not_optimal"}
        keep = {k: v for k, v in res.items() if k != "bands"}
        return {**base, "status": "ok", "available_land_km2": land_km2,
                "replaceable_heat_mwh_th": float(row["replaceable_heat_mwh_th"]),
                "lat": row.get("lat"), "lon": row.get("lon"), **keep}
    except Exception as e:
        return {**base, "status": "error", "error": f"{e}", "trace": traceback.format_exc()[-400:]}


def apply_land_override(df: pd.DataFrame, land_csv: Path) -> pd.DataFrame:
    """Replace available_land_km2 (+ optional cover cols) from a land-availability CSV."""
    land = pd.read_csv(land_csv)
    if "source_id" not in land.columns or "available_land_km2" not in land.columns:
        raise ValueError(f"{land_csv} must include source_id and available_land_km2")
    cover = [c for c in land.columns if c.endswith("_km2")]
    keep = ["source_id"] + cover
    land = land[keep].drop_duplicates("source_id")
    out = df.drop(columns=[c for c in cover if c in df.columns], errors="ignore")
    out = out.merge(land, on="source_id", how="left")
    out["has_land_data"] = out["available_land_km2"].notna()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--subsector", type=str, default=None)
    ap.add_argument("--max-workers", type=int, default=CONFIG["max_workers"])
    ap.add_argument("--output", type=str, default=None,
                    help="Results CSV path (default: outputs/multiband/<scenario>/by_facility.csv)")
    ap.add_argument("--scenario", type=str, default="land_5km_ss",
                    help="Scenario folder name under outputs/multiband/")
    ap.add_argument("--land-csv", type=str, default=None,
                    help="Override available_land_km2 from this land-availability CSV")
    ap.add_argument("--heat-case", type=str, default="base", choices=["base", "low", "high"],
                    help="Use replaceable_heat_mwh_th{,_low,_high} from assessment CSV")
    args = ap.parse_args()

    scenario = args.scenario
    if args.heat_case != "base" and not scenario.endswith(f"_heat_{args.heat_case}"):
        scenario = f"{scenario}_heat_{args.heat_case}"

    scenario_dir = _ROOT / "outputs" / "multiband" / scenario
    scenario_dir.mkdir(parents=True, exist_ok=True)
    out_rel = args.output or str(scenario_dir.relative_to(_ROOT) / "by_facility.csv")

    df = pd.read_csv(_ROOT / CONFIG["sites_csv"], low_memory=False)
    df = apply_heat_case(df, args.heat_case)
    if args.land_csv:
        land_path = _ROOT / args.land_csv
        print(f"Overriding land from {args.land_csv}")
        df = apply_land_override(df, land_path)
    run = df[df["has_solar_data"] & df["has_replaceable_heat"]].copy()
    if args.subsector:
        run = run[run["subsector"] == args.subsector]
    if args.limit:
        run = run.sort_values("replaceable_heat_mwh_th", ascending=False).head(args.limit)
    rows = run.to_dict("records")
    heat_twh = float(run["replaceable_heat_mwh_th"].sum() / 1e6)
    print(f"Running multi-band optimizer on {len(rows)} sites "
          f"(scenario={scenario}, heat_case={args.heat_case}, {heat_twh:.1f} TWh, "
          f"{CONFIG['n_representative_days']} rep-days, {args.max_workers} workers)...")

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
    out_path = _ROOT / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    ok = out[out["status"] == "ok"]
    print(f"\nWrote {len(out)} rows to {out_rel}  (ok: {len(ok)}, "
          f"failed: {len(out) - len(ok)})")
    if len(ok):
        w = ok["replaceable_heat_mwh_th"]
        print(f"Heat-weighted LCOH_served: ${(ok['LCOH_served_$perMWh'] * w).sum() / w.sum():,.0f}/MWh")
        print(f"Heat-weighted reliability: {(ok['Reliability_%'] * w).sum() / w.sum():.0f}%")
        print(f"Median solar intensity: {ok['solar_per_load_MWdc_per_MWth'].median():.1f} MWdc/MWth")
        if "met_availability_target" in ok.columns:
            met = ok["met_availability_target"].astype(bool)
            print(f"Met {CONFIG['availability']:.0%} availability: "
                  f"{met.sum()}/{len(ok)} sites "
                  f"({100*ok.loc[met,'replaceable_heat_mwh_th'].sum()/w.sum():.0f}% of heat)")
        print("\nstatus counts:")
        print(out["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
