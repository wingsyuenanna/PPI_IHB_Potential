"""Full-fleet availability sweeps for heat demand cases (low / high).

Base curves already live in fleet_availability_sweep_{5,15}km_by_floor.csv.
This re-optimizes each site × floor under sector low/high heat bounds.

Checkpoints: lcoh_vs_availability_{sid}_{km}km_heat_{low|high}.csv

    python outputs/multiband/analysis/fleet_availability_sweep_heat_cases.py \\
        --land-km 15 --heat-case low --max-workers 10
    python outputs/multiband/analysis/fleet_availability_sweep_heat_cases.py \\
        --land-km 15 --heat-case high --max-workers 10
    python outputs/multiband/analysis/fleet_availability_sweep_heat_cases.py \\
        --land-km 5 --heat-case low --max-workers 10
    python outputs/multiband/analysis/fleet_availability_sweep_heat_cases.py \\
        --land-km 5 --heat-case high --max-workers 10

Analyze / plot only (after sweeps):

    python outputs/multiband/analysis/plot_heat_case_hockey_sticks.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flatblock_optimization"))

from outputs.multiband.analysis.lcoh_vs_availability_sweep import (  # noqa: E402
    EURUSD,
    PRIOR,
    sweep,
)

OUT = Path(__file__).resolve().parent
FLOORS = [round(x, 2) for x in np.arange(0.1, 1.01, 0.1)]


def site_csv(sid: int, land_km: int, heat_case: str) -> Path:
    return OUT / f"lcoh_vs_availability_{sid}_{land_km}km_heat_{heat_case}.csv"


def floors_complete(df: pd.DataFrame) -> bool:
    if df.empty or "availability_floor" not in df.columns:
        return False
    ok = df[df["status"] == "ok"] if "status" in df.columns else df
    have = set(np.round(pd.to_numeric(ok["availability_floor"], errors="coerce"), 2))
    return set(FLOORS).issubset(have)


def _job(args: tuple) -> tuple[int, pd.DataFrame | None, str]:
    sid, land_km, heat_case = args
    try:
        import builtins

        _print = builtins.print

        def _quiet(*a, **k):
            if a and isinstance(a[0], str) and a[0].startswith("  availability"):
                return
            if a and isinstance(a[0], str) and a[0].startswith("    →"):
                return
            _print(*a, **k)

        builtins.print = _quiet
        try:
            d = sweep(
                sid,
                land_km,
                FLOORS,
                project_start="2030",
                n_rep_days=16,
                heat_case=heat_case,
            )
        finally:
            builtins.print = _print
        return sid, d, ""
    except Exception as e:
        return sid, None, str(e)


def run_sweep(land_km: int, heat_case: str, max_workers: int) -> None:
    # HiGHS/BLAS otherwise take one thread pool per worker and oversubscribe.
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(key, "1")
    prior = pd.read_csv(PRIOR[land_km])
    ids = sorted(int(x) for x in prior.loc[prior["status"] == "ok", "source_id"].unique())
    print(
        f"Heat-case fleet sweep: {land_km} km · heat={heat_case} · "
        f"{len(ids)} sites · floors={FLOORS} · workers={max_workers}"
    )

    todo: list[int] = []
    done = 0
    for sid in ids:
        p = site_csv(sid, land_km, heat_case)
        if p.exists():
            d = pd.read_csv(p)
            if floors_complete(d):
                done += 1
                continue
        todo.append(sid)
    print(f"Already complete: {done}  remaining: {len(todo)}")
    if not todo:
        return

    t0 = time.time()
    n_fin = 0
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_job, (sid, land_km, heat_case)): sid for sid in todo}
        for fut in as_completed(futs):
            sid = futs[fut]
            sid2, d, err = fut.result()
            n_fin += 1
            if d is None:
                print(f"  FAIL {sid}: {err}", flush=True)
                continue
            d.to_csv(site_csv(sid, land_km, heat_case), index=False)
            if n_fin % 25 == 0 or n_fin == len(todo):
                elapsed = time.time() - t0
                rate = n_fin / max(elapsed, 1e-6)
                eta = (len(todo) - n_fin) / max(rate, 1e-6)
                print(
                    f"  {n_fin}/{len(todo)} done  ({rate*60:.1f} sites/min, ETA {eta/60:.1f} min)",
                    flush=True,
                )


def analyze(land_km: int, heat_case: str) -> pd.DataFrame:
    prior = pd.read_csv(PRIOR[land_km])
    ids = set(int(x) for x in prior.loc[prior["status"] == "ok", "source_id"].unique())
    parts = []
    missing = 0
    for sid in sorted(ids):
        p = site_csv(sid, land_km, heat_case)
        if not p.exists():
            missing += 1
            continue
        d = pd.read_csv(p)
        if not floors_complete(d):
            missing += 1
            continue
        d = d[
            np.round(pd.to_numeric(d["availability_floor"], errors="coerce"), 2).isin(FLOORS)
        ].copy()
        parts.append(d)
    if not parts:
        raise SystemExit(f"no complete site sweeps for {land_km} km heat={heat_case}")
    long = pd.concat(parts, ignore_index=True)
    print(
        f"Loaded {long['source_id'].nunique()} sites for {land_km} km / {heat_case} "
        f"({missing} incomplete/missing)"
    )

    if "LCOH_served_eur_perMWh" not in long.columns or long["LCOH_served_eur_perMWh"].isna().all():
        long["LCOH_served_eur_perMWh"] = (
            pd.to_numeric(long["LCOH_served_$perMWh"], errors="coerce") / EURUSD
        )
    long["floor"] = np.round(pd.to_numeric(long["availability_floor"], errors="coerce"), 2)
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    long["served"] = long["heat"] * long["rel"] / 100.0
    if "status" in long.columns:
        long = long[long["status"] == "ok"].copy()
    long = long.sort_values(["source_id", "floor"]).drop_duplicates(
        ["source_id", "floor"], keep="last"
    )
    long_path = OUT / f"fleet_availability_sweep_{land_km}km_heat_{heat_case}_long.csv"
    long.to_csv(long_path, index=False)

    rows = []
    for fl, g in long.groupby("floor"):
        demand = g["heat"].sum()
        served = g["served"].sum()
        hw_lcoh = (
            float((g["lcoh"] * g["served"]).sum() / g["served"].sum())
            if served > 0
            else float("nan")
        )
        rows.append(
            {
                "heat_case": heat_case,
                "buffer_km": land_km,
                "availability_floor": fl,
                "n_sites": g["source_id"].nunique(),
                "demand_twh": demand / 1e6,
                "served_twh": served / 1e6,
                "served_pct": 100.0 * served / demand,
                "hw_LCOH_eur": hw_lcoh,
                "hw_Reliability_%": 100.0 * served / demand,
            }
        )
    curve = pd.DataFrame(rows).sort_values("availability_floor")
    by_floor = OUT / f"fleet_availability_sweep_{land_km}km_heat_{heat_case}_by_floor.csv"
    curve.to_csv(by_floor, index=False)
    print(f"Wrote {long_path}")
    print(f"Wrote {by_floor}")
    print(curve.to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    return curve


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--land-km", type=int, required=True, choices=[5, 15])
    ap.add_argument("--heat-case", type=str, required=True, choices=["low", "high"])
    ap.add_argument("--max-workers", type=int, default=10)
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    if not args.analyze_only:
        run_sweep(args.land_km, args.heat_case, args.max_workers)
    analyze(args.land_km, args.heat_case)


if __name__ == "__main__":
    main()
