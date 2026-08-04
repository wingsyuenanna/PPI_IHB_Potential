"""Full-fleet LCOH vs availability sweep (15 km): all sites × 10 floors.

Floors: 10%, 20%, …, 100%. Checkpoint per site; resume-safe.

    python outputs/multiband/analysis/fleet_availability_sweep_15km.py --max-workers 12
    python outputs/multiband/analysis/fleet_availability_sweep_15km.py --analyze-only
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flatblock_optimization"))

from outputs.multiband.analysis.lcoh_vs_availability_sweep import (  # noqa: E402
    EURUSD,
    PRIOR,
    country_gas_eur,
    sweep,
)

OUT = Path(__file__).resolve().parent
LAND_KM = 15
FLOORS = [round(x, 2) for x in np.arange(0.1, 1.01, 0.1)]
LONG_CSV = OUT / "fleet_availability_sweep_15km_long.csv"
KNEE_CSV = OUT / "fleet_availability_knee_15km.csv"
SUMMARY_TXT = OUT / "fleet_availability_sweep_15km_summary.txt"
PNG = OUT / "fleet_availability_sweep_15km_curve.png"


def site_csv(sid: int) -> Path:
    return OUT / f"lcoh_vs_availability_{sid}_{LAND_KM}km.csv"


def floors_complete(df: pd.DataFrame) -> bool:
    if df.empty or "availability_floor" not in df.columns:
        return False
    ok = df[df["status"] == "ok"] if "status" in df.columns else df
    have = set(np.round(pd.to_numeric(ok["availability_floor"], errors="coerce"), 2))
    return set(FLOORS).issubset(have)


def _job(args: tuple) -> tuple[int, pd.DataFrame | None, str]:
    sid, = args
    try:
        # Quieter: monkeypatch print in worker? keep status from parent only.
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
        futs = {ex.submit(_job, (sid,)): sid for sid in todo}
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


def load_long() -> pd.DataFrame:
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
    return long


def per_site_knee(g: pd.DataFrame) -> dict:
    """Availability just before the sharpest LCOH upturn.

    Among consecutive floors, find the largest ΔLCOH/Δα. If that jump is
    ≥ max(€15/MWh, 25% of prior LCOH), the knee is the floor *before* the jump.
    Otherwise use the highest floor with LCOH ≤ country gas (else max floor).
    """
    g = g.sort_values("availability_floor").copy()
    g["floor"] = pd.to_numeric(g["availability_floor"], errors="coerce")
    g["rel"] = pd.to_numeric(g["Reliability_%"], errors="coerce")
    g["lcoh"] = pd.to_numeric(g["LCOH_served_eur_perMWh"], errors="coerce")
    if "LCOH_served_eur_perMWh" not in g.columns or g["lcoh"].isna().all():
        if "LCOH_served_$perMWh" in g.columns:
            g["lcoh"] = pd.to_numeric(g["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    g["heat"] = pd.to_numeric(g["replaceable_heat_mwh_th"], errors="coerce")
    g = g.dropna(subset=["floor", "rel", "lcoh"])
    if g.empty:
        return {}

    iso = str(g["iso3_country"].iloc[0]) if "iso3_country" in g.columns else ""
    gas = country_gas_eur(iso) if iso else float("nan")

    floors = g["floor"].to_numpy()
    lcoh = g["lcoh"].to_numpy()
    rel = g["rel"].to_numpy()
    heat = float(g["heat"].iloc[0])

    # slope between consecutive points
    d_floor = np.diff(floors)
    d_lcoh = np.diff(lcoh)
    slope = np.where(d_floor > 0, d_lcoh / d_floor, 0.0)
    i_jump = int(np.argmax(slope)) if len(slope) else 0
    jump = float(d_lcoh[i_jump]) if len(d_lcoh) else 0.0
    prior_lcoh = float(lcoh[i_jump]) if len(lcoh) else float("nan")
    significant = jump >= max(15.0, 0.25 * max(prior_lcoh, 1.0))

    if significant:
        knee_floor = float(floors[i_jump])  # before the jump
        method = "before_max_jump"
    else:
        # fall back: highest floor with LCOH ≤ gas, else highest
        below = g["lcoh"] <= gas + 1e-6 if np.isfinite(gas) else pd.Series(False, index=g.index)
        if below.any():
            knee_floor = float(g.loc[below, "floor"].max())
            method = "max_below_gas"
        else:
            knee_floor = float(floors[np.argmin(lcoh)])
            method = "min_lcoh"

    row = g.loc[(g["floor"] - knee_floor).abs().idxmin()]
    return {
        "source_id": int(g["source_id"].iloc[0]),
        "source_name": g["source_name"].iloc[0] if "source_name" in g.columns else "",
        "iso3_country": iso,
        "subsector": g["subsector"].iloc[0] if "subsector" in g.columns else "",
        "replaceable_heat_mwh_th": heat,
        "gas_heat_cost_eur_mwh": gas,
        "knee_floor": knee_floor,
        "knee_method": method,
        "knee_Reliability_%": float(row["rel"]),
        "knee_LCOH_eur": float(row["lcoh"]),
        "knee_served_mwh": heat * float(row["rel"]) / 100.0,
        "max_jump_eur": jump,
        "LCOH_at_90": float(g.loc[(g["floor"] - 0.9).abs().idxmin(), "lcoh"]) if (g["floor"] - 0.9).abs().min() < 0.02 else float("nan"),
        "Reliability_at_90": float(g.loc[(g["floor"] - 0.9).abs().idxmin(), "rel"]) if (g["floor"] - 0.9).abs().min() < 0.02 else float("nan"),
    }


def analyze(long: pd.DataFrame) -> None:
    long = long.copy()
    if "LCOH_served_eur_perMWh" not in long.columns or long["LCOH_served_eur_perMWh"].isna().all():
        long["LCOH_served_eur_perMWh"] = (
            pd.to_numeric(long["LCOH_served_$perMWh"], errors="coerce") / EURUSD
        )
    long["floor"] = np.round(pd.to_numeric(long["availability_floor"], errors="coerce"), 2)
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    long["served"] = long["heat"] * long["rel"] / 100.0
    long = long[long["status"] == "ok"].copy() if "status" in long.columns else long

    # One row per site×floor (prefer last if duplicates)
    long = long.sort_values(["source_id", "floor"]).drop_duplicates(["source_id", "floor"], keep="last")
    long.to_csv(LONG_CSV, index=False)

    # Fleet curve at each fixed floor
    rows = []
    for fl, g in long.groupby("floor"):
        # one observation per site at this floor
        demand = g["heat"].sum()
        served = g["served"].sum()
        hw_lcoh = float((g["lcoh"] * g["served"]).sum() / g["served"].sum()) if served > 0 else float("nan")
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
    curve.to_csv(OUT / "fleet_availability_sweep_15km_by_floor.csv", index=False)

    # Per-site knee
    knees = []
    for sid, g in long.groupby("source_id"):
        k = per_site_knee(g)
        if k:
            knees.append(k)
    knee_df = pd.DataFrame(knees)
    knee_df.to_csv(KNEE_CSV, index=False)

    k_demand = knee_df["replaceable_heat_mwh_th"].sum()
    k_served = knee_df["knee_served_mwh"].sum()
    k_pct = 100.0 * k_served / k_demand
    k_lcoh = float(
        (knee_df["knee_LCOH_eur"] * knee_df["knee_served_mwh"]).sum() / knee_df["knee_served_mwh"].sum()
    )
    k_hw_floor = float(
        (knee_df["knee_floor"] * knee_df["replaceable_heat_mwh_th"]).sum() / k_demand
    )

    # Compare to prior 90% and gas-capped
    prior = pd.read_csv(PRIOR[LAND_KM])
    pok = prior[prior["status"] == "ok"].copy()
    pok["heat"] = pd.to_numeric(pok["replaceable_heat_mwh_th"], errors="coerce")
    pok["rel"] = pd.to_numeric(pok["Reliability_%"], errors="coerce")
    p90 = 100.0 * (pok["rel"] / 100 * pok["heat"]).sum() / pok["heat"].sum()

    gas_path = OUT / "gas_capped_step90_15km.csv"
    if gas_path.exists():
        gc = pd.read_csv(gas_path)
        g_served = pd.to_numeric(gc["served_mwh"], errors="coerce").fillna(0).sum()
        g_heat = pd.to_numeric(gc["replaceable_heat_mwh_th"], errors="coerce").sum()
        g_pct = 100.0 * g_served / g_heat
    else:
        g_pct = float("nan")

    lines = [
        "Full-fleet availability sweep — 15 km, floors 10–100% (step 10 pp)",
        f"Sites with complete sweeps: {knee_df['source_id'].nunique()}",
        "",
        "Fleet heat-weighted served % by *fixed* availability floor:",
        curve[["availability_floor", "served_pct", "served_twh", "hw_LCOH_eur"]].to_string(
            index=False, float_format=lambda x: f"{x:.1f}"
        ),
        "",
        "Per-site LCOH knee (floor before sharpest upturn; else max≤gas / min LCOH):",
        f"  Heat-weighted knee floor: {100*k_hw_floor:.1f}%",
        f"  Fleet served at knee:     {k_pct:.1f}%  ({k_served/1e6:.1f} TWh)",
        f"  HW LCOH at knee:          €{k_lcoh:.1f}/MWh",
        f"  Knee methods: {knee_df['knee_method'].value_counts().to_dict()}",
        "",
        "Comparison:",
        f"  Fixed 90% floor (main fleet): {p90:.1f}%",
        f"  Gas-capped step-from-90:      {g_pct:.1f}%",
        f"  Per-site LCOH knee:           {k_pct:.1f}%",
        "",
        f"Wrote {LONG_CSV}",
        f"Wrote {KNEE_CSV}",
        f"Wrote {OUT / 'fleet_availability_sweep_15km_by_floor.csv'}",
    ]
    SUMMARY_TXT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    # Plot fleet curve
    fig, ax1 = plt.subplots(figsize=(8.0, 4.8))
    x = 100 * curve["availability_floor"]
    ax1.plot(x, curve["served_pct"], "o-", color="#4C78A8", lw=2, label="Fleet heat served %")
    ax1.axhline(k_pct, color="#27ae60", ls="--", lw=1.5, label=f"At per-site knee ({k_pct:.0f}%)")
    ax1.axhline(p90, color="#7f8c8d", ls=":", lw=1.5, label=f"Fixed 90% floor ({p90:.0f}%)")
    if np.isfinite(g_pct):
        ax1.axhline(g_pct, color="#F58518", ls=":", lw=1.5, label=f"Gas-capped ({g_pct:.0f}%)")
    ax1.set_xlabel("Availability floor target (%)")
    ax1.set_ylabel("Fleet process heat served (%)", color="#4C78A8")
    ax1.set_xlim(0, 105)
    ax1.set_ylim(0, 100)
    ax1.grid(True, ls=":", alpha=0.5)

    ax2 = ax1.twinx()
    ax2.plot(x, curve["hw_LCOH_eur"], "s--", color="#d62728", lw=1.6, label="HW LCOH")
    ax2.set_ylabel("Heat-weighted LCOH (€/MWh)", color="#d62728")

    ax1.set_title("15 km fleet: served heat & LCOH vs availability floor")
    # combine legends
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(PNG, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {PNG}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-workers", type=int, default=12)
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    if not args.analyze_only:
        run_sweep(args.max_workers)
    long = load_long()
    analyze(long)


if __name__ == "__main__":
    main()
