# run_ihb_potential.py
# Single-script optimization runner for EU pulp & paper industrial heat battery potential.
#
# Replaces: generate_scenarios.py + run_all_jobs.sh + run_scenario.py
#
# Usage (from project root):
#   python run_ihb_potential.py
#   python run_ihb_potential.py --no-resume     # re-run all sites, ignore existing output
#   python run_ihb_potential.py --workers 4     # parallel execution

from __future__ import annotations

import sys
import os
import argparse
import traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np

# Make solvers/utils importable from subprocesses (ProcessPoolExecutor re-imports this module)
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "flatblock_optimization"))


# ── CONFIG ─────────────────────────────────────────────────────────────────────
# Edit these settings before running. All paths are relative to the project root.
CONFIG = {
    # ── Input data ────────────────────────────────────────────────────────────
    # Merged site assessment CSV — contains heat demand, land availability, solar metadata
    # Built by flatblock_optimization/inputs/build_sites_input.py from the new
    # heat-demand + Eurostat fossil-share pipeline (replaceable_heat_mwh_th) plus
    # land availability and solar-profile presence. Run that script to refresh.
    "sites_csv": "outputs/eu_ihb_site_assessment_2024.csv",
    # BNEF costs by country and year (solar CAPEX/FOM, battery FOM, CRF)
    "bnef_costs_csv": "Input/bnef_country_costs.csv",
    # Thermal energy storage cost table (rows: cost components; cols: years 2025/2030/2035)
    "battery_costs_csv": "flatblock_optimization/inputs/input_heat_battery_cost.csv",
    # Local hourly solar profiles — files named <source_id>_<year>.parquet
    "solar_hourly_dir": "solar_radiation/outputs/hourly_profiles",

    # ── Site filters ──────────────────────────────────────────────────────────
    # Skip sites with no fossil heat to replace (replaceable_heat_mwh_th == 0)
    "filter_has_replaceable_heat": True,
    # Skip sites with no local solar profile parquet file
    "filter_has_solar_data": True,

    # ── Optimization parameters ───────────────────────────────────────────────
    "storage_type": "heat",    # "heat" (thermal energy storage) or "liion" (Li-ion BESS)
    "project_start": 2025,     # year for BNEF solar/battery cost lookup
    "solar_year": 2023,        # year of hourly solar profile to use
    # Availability target: fraction of annual load-hours that must be served.
    # Unserved energy budget = (1 - availability) × annual_load_MWh.
    "availability": 0.90,

    # Thermal energy storage (TES) parameters — only used when storage_type = "heat":
    #
    # T_max: maximum tank temperature (°C). Ceiling of stored energy.
    #   Rondo-style resistive brick: ~1500 °C.
    #   Steam-based TES: ~300–400 °C.
    "heat_tmax_c": 1500.0,
    #
    # T_min: minimum usable/process temperature (°C), set per site classification.
    #   Only heat above T_min can be delivered to the process.
    #   Usable stored-energy fraction ≈ 1 − T_min / T_max.
    #
    # SCOPE — fossil *steam* replacement only. All served demand is modeled as
    # process steam (kraft digesters ~170 °C, paper drying ~180 °C). Lime-kiln
    # fuel at kraft mills (~900 °C direct firing, roughly 8–12% of mill fuel
    # input) is NOT servable by a steam-delivering heat battery and is not
    # modeled separately. To the extent country-average fossil shares include
    # kiln fuel, addressable demand at fossil-fired kraft sites is somewhat
    # overstated; at Nordic mills the kiln typically already burns biomass and
    # is outside the fossil share. Stated as a scope caveat, not modeled.
    "steam_temp_by_classification": {
        "Pulp": 175.0,
        "Integrated": 180.0,
        "Paper/Board": 180.0,
        "Tissue": 180.0,
    },
    # Fallback T_min (°C) for sites with a missing/unmapped classification.
    "heat_tmin_default_c": 200.0,
    #
    # Round-trip efficiency: electrical energy in → useful heat out (0–1).
    "heat_rte": 0.97,
    #
    # Maximum storage duration (hours): E_TES ≤ heat_max_hours × P_discharge.
    "heat_max_hours": 12.0,
    #
    # Minimum charge/discharge power ratio (P_charge ≥ cd_ratio × P_discharge).
    #   Solar peaks last ~6–8 h/day; industrial heat demand is continuous 24 h/day.
    #   cd_ratio = 4 means: to supply 10 MW continuously you must charge at ≥ 40 MW
    #   during solar hours, covering overnight discharge from stored energy.
    "heat_cd_ratio": 4.0,

    # ── Land limit ────────────────────────────────────────────────────────────
    # MW of solar per km² of available land (utility-scale ground-mount ~80–100 MW/km²).
    # Solar capacity is hard-capped at available_land_km2 × mw_per_km2 in the solver.
    "mw_per_km2": 100.0,
    # When a site cannot reach the availability target within its land cap, re-solve
    # with the reliability floor removed and this high unserved penalty ($/MWh), so
    # the model builds the max solar the land allows and we report the ACHIEVABLE
    # reliability instead of returning infeasible. Large enough to dominate capex.
    "maxserve_voll": 100000.0,

    # ── Output ────────────────────────────────────────────────────────────────
    "output_dir": "flatblock_optimization/output",
    # If True: on startup, read the existing summary CSV and skip sites already present.
    # Override with --no-resume on the command line.
    "resume": True,
    # Number of parallel worker processes. 1 = sequential (easier to debug).
    "n_workers": 1,
}
# ──────────────────────────────────────────────────────────────────────────────


# ── Solar loading (local parquet, no S3) ──────────────────────────────────────

def load_solar_local(source_id: int, year: int, solar_hourly_dir: str) -> pd.DataFrame:
    """Read local parquet solar profile (columns: source_id, year, timestamp, P_kWperkWp)."""
    path = Path(solar_hourly_dir) / f"{source_id}_{year}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No local solar profile: {path}")
    df = pd.read_parquet(path)
    if "P_kWperkWp" not in df.columns:
        raise ValueError(f"Expected 'P_kWperkWp' column in {path}")
    if "timestamp" not in df.columns:
        raise ValueError(f"Expected 'timestamp' column in {path}")
    df["P_kWperkWp"] = df["P_kWperkWp"].astype(float)
    return df


# ── Per-site process temperatures ──────────────────────────────────────────────

def site_steam_temp(classification, cfg: dict) -> float:
    """
    Steam delivery temperature (°C) for a site classification. Sets both the TES
    usable-window floor (T_min) and the electricity→heat efficiency bucket.
    See the SCOPE note in CONFIG: lime-kiln heat is excluded by scope statement,
    so all served demand is steam.
    """
    key = None if pd.isna(classification) else str(classification)
    return float(cfg["steam_temp_by_classification"].get(key, cfg["heat_tmin_default_c"]))


# ── Per-site worker (must be module-level for multiprocessing pickling) ────────

def run_one_site(row: dict, cfg: dict) -> tuple[dict, pd.DataFrame | None]:
    """Run optimization for a single site. Returns (summary_row, hourly_df)."""
    source_id = int(row["source_id"])
    iso3 = str(row["iso3_country"])
    replaceable_mwh = float(row.get("replaceable_heat_mwh_th", 0) or 0)
    available_land_km2 = float(row.get("available_land_km2", 0) or 0)
    classification = row.get("classification")
    steam_temp_c = site_steam_temp(classification, cfg)

    base = {
        "source_id": source_id,
        "source_name": row.get("source_name", ""),
        "iso3_country": iso3,
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "classification": classification,
        "replaceable_heat_mwh_th": replaceable_mwh,
        "available_land_km2": available_land_km2,
        "solar_capacity_factor": row.get("solar_capacity_factor"),
        "storage_type": cfg["storage_type"],
        "project_start": cfg["project_start"],
        "steam_temp_c": steam_temp_c,
    }

    load_target_mw = replaceable_mwh / 8760.0
    if load_target_mw <= 0:
        return {**base, "status": "skipped_no_load", "load_target_mw": 0}, None

    # Load local solar profile
    try:
        solar_df = load_solar_local(source_id, cfg["solar_year"], cfg["solar_hourly_dir"])
    except FileNotFoundError as e:
        return {**base, "status": "no_solar_file", "error": str(e), "load_target_mw": load_target_mw}, None

    # Load BNEF + battery costs
    try:
        from utils.loaders.load_re_costs import load_re_costs
        input_costs = load_re_costs(
            str(_ROOT / cfg["bnef_costs_csv"]),
            str(_ROOT / cfg["battery_costs_csv"]),
            iso3,
            str(cfg["project_start"]),
        )
    except Exception as e:
        return {**base, "status": "cost_load_error", "error": str(e), "load_target_mw": load_target_mw}, None

    results = None
    hourly_df = None
    feasible = False
    meets_availability = False

    try:
        if cfg["storage_type"] == "heat":
            from solvers.optimize_flatblock_highs_heat_battery import (
                run_flatblock_optimization_heat_battery_highs,
            )
            def _run(**kw):
                return run_flatblock_optimization_heat_battery_highs(
                    **kw,
                    round_trip_efficiency=cfg["heat_rte"],
                    project_start_year=cfg["project_start"],
                    process_temperature_c=steam_temp_c,
                    max_storage_hours=cfg["heat_max_hours"],
                    tes_temp_max_c=cfg["heat_tmax_c"],
                    tes_temp_min_c=steam_temp_c,
                    charge_discharge_ratio_min=cfg["heat_cd_ratio"],
                    # Hard land cap: solar MW ≤ available land × density. 0/missing
                    # land data leaves solar unbounded (see solver guard).
                    max_solar_mw=available_land_km2 * cfg["mw_per_km2"],
                )
        else:
            from solvers.optimize_flatblock_highs_unserved_v2 import run_flatblock_optimization_highs
            def _run(**kw):
                return run_flatblock_optimization_highs(**kw)

        # Stage 1: full load, must meet the availability target within the land cap.
        results, hourly_df, feasible = _run(
            site_id=source_id,
            availability_factor=cfg["availability"],
            site_params=row,
            solar_profile_df=solar_df,
            demand_profile=None,
            input_costs=input_costs,
            load_target=load_target_mw,
        )
        meets_availability = feasible

        # Stage 2: if the land cap (or low solar CF) prevents hitting the target,
        # drop the reliability floor and maximise served energy instead of failing.
        # We keep the SAME full load and report the achievable reliability.
        if not feasible:
            results, hourly_df, feasible = _run(
                site_id=source_id,
                availability_factor=0.0,          # no hard unserved cap
                site_params=row,
                solar_profile_df=solar_df,
                demand_profile=None,
                input_costs=input_costs,
                load_target=load_target_mw,
                VoLL=cfg["maxserve_voll"],         # penalise unserved -> build to land cap
            )

    except Exception as e:
        return {
            **base,
            "status": "solver_error",
            "error": traceback.format_exc(),
            "load_target_mw": load_target_mw,
        }, None

    if not feasible or results is None:
        return {**base, "status": "infeasible", "load_target_mw": load_target_mw}, None

    # Solar is now hard-capped at the land limit inside the solver, so instead
    # of flagging violations we flag when that cap is BINDING (the site would
    # have built more solar if it had the land — a sign land is constraining it).
    max_land_mw = available_land_km2 * cfg["mw_per_km2"]
    s_opt = results.get("S_opt_MW", 0)
    exceeds_land = (max_land_mw > 0) and (s_opt >= max_land_mw * 0.999)

    # Reliability achieved at full load (stage 1 ≥ target; stage 2 may be below).
    achieved_reliability = results.get("Reliability_%", None)
    summary = {
        **base,
        "status": "completed" if meets_availability else "below_availability_target",
        "load_target_mw": load_target_mw,
        "meets_availability_target": meets_availability,
        "availability_target_pct": cfg["availability"] * 100,
        "achieved_reliability_pct": achieved_reliability,
        "max_solar_land_mw": round(max_land_mw, 1),
        "land_cap_binding": exceeds_land,
        "exceeds_land_limit": exceeds_land,  # kept for backward-compat (maps/CSV)
        **results,
    }
    return summary, hourly_df


# ── Output helpers ─────────────────────────────────────────────────────────────

def _site_result_path(source_id: int, output_dir: Path) -> Path:
    return output_dir / "sites" / f"site_{source_id}.csv"


def _write_site_result(summary: dict, hourly_df: pd.DataFrame | None, output_dir: Path):
    """Write per-site result files. Each site gets its own CSV so schema is always consistent."""
    sites_dir = output_dir / "sites"
    sites_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([summary]).to_csv(_site_result_path(summary["source_id"], output_dir), index=False)
    if hourly_df is not None:
        hourly_dir = output_dir / "hourly"
        hourly_dir.mkdir(parents=True, exist_ok=True)
        hourly_df.to_csv(hourly_dir / f"hourly_{summary['source_id']}.csv", index=False)


def _build_summary(output_dir: Path):
    """Merge all per-site CSVs into a single summary.csv."""
    site_files = sorted((output_dir / "sites").glob("site_*.csv"))
    if not site_files:
        return
    combined = pd.concat([pd.read_csv(f) for f in site_files], ignore_index=True)
    combined.to_csv(output_dir / "summary.csv", index=False)
    return combined


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run IHB potential optimization for EU pulp & paper sites.")
    parser.add_argument("--no-resume", action="store_true", help="Re-run all sites, ignoring existing output.")
    parser.add_argument("--workers", type=int, default=None, help="Override n_workers from CONFIG.")
    parser.add_argument("--project-start", type=int, default=None,
                        help="Override cost year from CONFIG (BNEF + battery CSV column, e.g. 2030).")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Override output_dir from CONFIG (use a separate dir per scenario year).")
    args = parser.parse_args()

    cfg = CONFIG.copy()
    if args.no_resume:
        cfg["resume"] = False
    if args.workers is not None:
        cfg["n_workers"] = args.workers
    if args.project_start is not None:
        cfg["project_start"] = args.project_start
    if args.output_dir is not None:
        cfg["output_dir"] = args.output_dir

    output_dir = _ROOT / cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve paths relative to project root
    cfg["solar_hourly_dir"] = str(_ROOT / cfg["solar_hourly_dir"])

    # Load sites
    sites_path = _ROOT / cfg["sites_csv"]
    df = pd.read_csv(sites_path)
    print(f"Loaded {len(df)} sites from {sites_path.name}")

    if cfg["filter_has_replaceable_heat"]:
        df = df[df["has_replaceable_heat"] == True]
        print(f"  → {len(df)} sites with replaceable heat")

    if cfg["filter_has_solar_data"]:
        df = df[df["has_solar_data"] == True]
        print(f"  → {len(df)} sites with solar data")

    # Resume: check for existing per-site result files (one CSV per site)
    completed_ids: set[int] = set()
    if cfg["resume"]:
        sites_dir = output_dir / "sites"
        if sites_dir.exists():
            for f in sites_dir.glob("site_*.csv"):
                try:
                    completed_ids.add(int(f.stem.replace("site_", "")))
                except ValueError:
                    pass
        if completed_ids:
            print(f"Resuming: {len(completed_ids)} sites already done, skipping them.")

    pending = df[~df["source_id"].isin(completed_ids)]
    print(f"Running {len(pending)} sites with {cfg['n_workers']} worker(s).\n")

    rows = pending.to_dict(orient="records")
    n_done = 0

    if cfg["n_workers"] == 1:
        for row in rows:
            sid = int(row["source_id"])
            print(f"[{n_done+1}/{len(rows)}] Site {sid} ({row.get('source_name', '')})")
            summary, hourly_df = run_one_site(row, cfg)
            _write_site_result(summary, hourly_df, output_dir)
            print(f"  → status: {summary['status']}\n")
            n_done += 1
    else:
        with ProcessPoolExecutor(max_workers=cfg["n_workers"]) as pool:
            futures = {pool.submit(run_one_site, row, cfg): row for row in rows}
            for fut in as_completed(futures):
                row = futures[fut]
                sid = int(row["source_id"])
                try:
                    summary, hourly_df = fut.result()
                except Exception as e:
                    summary = {"source_id": sid, "status": "worker_error", "error": str(e)}
                    hourly_df = None
                _write_site_result(summary, hourly_df, output_dir)
                n_done += 1
                print(f"[{n_done}/{len(rows)}] Site {sid} → {summary['status']}")

    summary_df = _build_summary(output_dir)
    n_completed = 0 if summary_df is None else int((summary_df["status"] == "completed").sum())
    n_total = 0 if summary_df is None else len(summary_df)
    print(f"\nDone. {n_completed} sites completed out of {n_total} processed.")
    print(f"Summary: {output_dir}/summary.csv")
    if (output_dir / "hourly").exists():
        print(f"Hourly dispatch: {output_dir}/hourly/")


if __name__ == "__main__":
    main()
