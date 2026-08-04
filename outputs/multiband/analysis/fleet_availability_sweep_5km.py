"""Full-fleet LCOH vs availability sweep (5 km): all sites × 10 floors.

Floors: 10%, 20%, …, 100%. Checkpoint per site; resume-safe.

    python outputs/multiband/analysis/fleet_availability_sweep_5km.py --max-workers 12
    python outputs/multiband/analysis/fleet_availability_sweep_5km.py --analyze-only
"""
from __future__ import annotations

import argparse
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
LAND_KM = 5
FLOORS = [round(x, 2) for x in np.arange(0.1, 1.01, 0.1)]
LONG_CSV = OUT / "fleet_availability_sweep_5km_long.csv"
BY_FLOOR_CSV = OUT / "fleet_availability_sweep_5km_by_floor.csv"
SUMMARY_TXT = OUT / "fleet_availability_sweep_5km_summary.txt"


def site_csv(sid: int) -> Path:
    return OUT / f"lcoh_vs_availability_{sid}_{LAND_KM}km.csv"


def floors_complete(df: pd.DataFrame) -> bool:
    if df.empty or "availability_floor" not in df.columns:
        return False
    ok = df[df["status"] == "ok"] if "status" in df.columns else df
    have = set(np.round(pd.to_numeric(ok["availability_floor"], errors="coerce"), 2))
    return set(FLOORS).issubset(have)


def _job(sid: int) -> tuple[int, pd.DataFrame | None, str]:
    try:
        import builtins

        _print = builtins.print

        def _quiet(*a, **k):
            if a and isinstance(a[0], str) and (
                a[0].startswith("  availability") or a[0].startswith("    →")
            ):
                return
            _print(*a, **k)

        builtins.print = _quiet
        try:
            d = sweep(sid, LAND_KM, FLOORS, project_start="2030", n_rep_days=16)
        finally:
            builtins.print = _print
        return sid, d, ""
    except Exception as e:
        return sid, None, str(e)


def run_sweep(max_workers: int) -> None:
    prior = pd.read_csv(PRIOR[LAND_KM])
    ids = sorted(int(x) for x in prior.loc[prior["status"] == "ok", "source_id"].unique())
    print(f"Fleet sites: {len(ids)}  floors: {FLOORS}  workers: {max_workers}")

    todo: list[int] = []
    done = 0
    for sid in ids:
        p = site_csv(sid)
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
        futs = {ex.submit(_job, sid): sid for sid in todo}
        for fut in as_completed(futs):
            sid = futs[fut]
            sid2, d, err = fut.result()
            n_fin += 1
            if d is None:
                print(f"  FAIL {sid}: {err}", flush=True)
                continue
            d.to_csv(site_csv(sid), index=False)
            if n_fin % 25 == 0 or n_fin == len(todo):
                elapsed = time.time() - t0
                rate = n_fin / max(elapsed, 1e-6)
                eta = (len(todo) - n_fin) / max(rate, 1e-6)
                print(
                    f"  {n_fin}/{len(todo)} done  ({rate*60:.1f} sites/min, ETA {eta/60:.1f} min)",
                    flush=True,
                )


def analyze() -> None:
    prior = pd.read_csv(PRIOR[LAND_KM])
    ids = set(int(x) for x in prior.loc[prior["status"] == "ok", "source_id"].unique())
    parts = []
    missing = 0
    for sid in sorted(ids):
        p = site_csv(sid)
        if not p.exists():
            missing += 1
            continue
        d = pd.read_csv(p)
        if not floors_complete(d):
            missing += 1
            continue
        d = d[np.round(pd.to_numeric(d["availability_floor"], errors="coerce"), 2).isin(FLOORS)].copy()
        parts.append(d)
    if not parts:
        raise SystemExit("no complete site sweeps found")
    long = pd.concat(parts, ignore_index=True)
    print(f"Loaded {long['source_id'].nunique()} sites  ({missing} incomplete/missing)")

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
    long.to_csv(LONG_CSV, index=False)

    rows = []
    for fl, g in long.groupby("floor"):
        demand = g["heat"].sum()
        served = g["served"].sum()
        hw_lcoh = (
            float((g["lcoh"] * g["served"]).sum() / g["served"].sum()) if served > 0 else float("nan")
        )
        rows.append(
            {
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
    curve.to_csv(BY_FLOOR_CSV, index=False)

    lines = [
        "Full-fleet availability sweep — 5 km, floors 10–100% (step 10 pp)",
        f"Sites with complete sweeps: {long['source_id'].nunique()}",
        "",
        curve[["availability_floor", "served_pct", "served_twh", "hw_LCOH_eur"]].to_string(
            index=False, float_format=lambda x: f"{x:.1f}"
        ),
        "",
        f"Wrote {LONG_CSV}",
        f"Wrote {BY_FLOOR_CSV}",
    ]
    SUMMARY_TXT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-workers", type=int, default=12)
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()
    if not args.analyze_only:
        run_sweep(args.max_workers)
    analyze()


if __name__ == "__main__":
    main()
