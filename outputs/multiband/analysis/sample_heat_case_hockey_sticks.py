"""Sample-based heat-case hockey sticks (fast preview of full-fleet sweeps).

Uses the same stratified sampler as lcoh_vs_availability_sweep --fleet-avg,
then re-optimizes each sample site at floors 10–100% for low / base / high.

    python outputs/multiband/analysis/sample_heat_case_hockey_sticks.py --n-sample 80 --max-workers 10
"""
from __future__ import annotations

import argparse
import sys
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
    pick_sample,
    sweep,
)

OUT = Path(__file__).resolve().parent
FLOORS = [round(x, 2) for x in np.arange(0.1, 1.01, 0.1)]
CASES = ["low", "base", "high"]
CASE_STYLE = {
    "low": {"color": "#009E73", "marker": "o", "label": "Low demand", "lw": 2.0},
    "base": {"color": "#0072B2", "marker": "s", "label": "Base", "lw": 2.0},
    "high": {"color": "#D55E00", "marker": "^", "label": "High demand", "lw": 2.0},
}
OUT_STEM = "heat_case_hockey_sticks_lcoh_availability"
YMAX = 160.0


def _job(args: tuple) -> tuple[int, int, str, pd.DataFrame | None, str]:
    sid, land_km, heat_case = args
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
            d = sweep(
                sid, land_km, FLOORS, project_start="2030", n_rep_days=16, heat_case=heat_case
            )
        finally:
            builtins.print = _print
        return sid, land_km, heat_case, d, ""
    except Exception as e:
        return sid, land_km, heat_case, None, str(e)


def aggregate(long: pd.DataFrame) -> pd.DataFrame:
    long = long[long["status"] == "ok"].copy() if "status" in long.columns else long.copy()
    long["floor"] = np.round(pd.to_numeric(long["availability_floor"], errors="coerce"), 2)
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    if "LCOH_served_eur_perMWh" in long.columns:
        long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    else:
        long["lcoh"] = pd.to_numeric(long["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    long["served"] = long["heat"] * long["rel"] / 100.0
    rows = []
    for (km, case, fl), g in long.groupby(["land_km", "heat_case", "floor"]):
        dem = float(g["heat"].sum())
        srv = float(g["served"].sum())
        hw = float((g["lcoh"] * g["served"]).sum() / srv) if srv > 0 else float("nan")
        rows.append(
            {
                "buffer_km": int(km),
                "heat_case": case,
                "availability_floor": fl,
                "n_sites": g["source_id"].nunique(),
                "demand_twh": dem / 1e6,
                "served_twh": srv / 1e6,
                "served_pct": 100.0 * srv / dem if dem > 0 else float("nan"),
                "hw_LCOH_eur": hw,
            }
        )
    return pd.DataFrame(rows).sort_values(["buffer_km", "heat_case", "availability_floor"])


def plot_curves(curve: pd.DataFrame, land_kms: list[int], n_sample: int) -> None:
    n = len(land_kms)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n, 4.4), sharey=True, squeeze=False)
    for ax, km in zip(axes[0], land_kms):
        for case, st in CASE_STYLE.items():
            c = curve[(curve["buffer_km"] == km) & (curve["heat_case"] == case)].sort_values(
                "served_pct"
            )
            if c.empty:
                continue
            y = c["hw_LCOH_eur"].clip(upper=YMAX)
            ax.plot(
                c["served_pct"],
                y,
                color=st["color"],
                marker=st["marker"],
                ms=6,
                lw=st["lw"],
                label=st["label"],
            )
            near90 = c.iloc[(c["availability_floor"] - 0.9).abs().argmin()]
            if float(near90["hw_LCOH_eur"]) <= YMAX:
                ax.annotate(
                    "90%",
                    (near90["served_pct"], min(float(near90["hw_LCOH_eur"]), YMAX)),
                    textcoords="offset points",
                    xytext=(4, 4),
                    fontsize=7,
                    color=st["color"],
                )
        ax.set_xlabel("Heat-weighted availability (% served / demand)")
        ax.set_xlim(0, 100)
        ax.set_ylim(20, YMAX)
        ax.set_title(f"{km} km land buffer", fontsize=11, loc="left")
        ax.grid(True, ls=":", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0][0].set_ylabel("Heat-weighted LCOH (€/MWh served)")
    axes[0][0].legend(frameon=False, loc="upper left", fontsize=8)
    fig.suptitle(
        f"Heat-demand hockey sticks · LCOH vs availability\n"
        f"(stratified sample n={n_sample} sites/buffer · 2030 costs)",
        fontsize=11,
        fontweight="semibold",
    )
    fig.tight_layout()
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=180)
    fig.savefig(OUT / f"{OUT_STEM}.pdf")
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sample", type=int, default=80)
    ap.add_argument("--max-workers", type=int, default=10)
    ap.add_argument("--land-km", type=int, nargs="*", default=[5, 15], choices=[5, 15])
    args = ap.parse_args()
    land_kms = list(dict.fromkeys(args.land_km))

    jobs = []
    for km in land_kms:
        ids = pick_sample(km, n_total=args.n_sample, seed=0)
        print(f"{km} km sample: {len(ids)} sites")
        for case in CASES:
            for sid in ids:
                jobs.append((sid, km, case))

    print(f"Total site×case jobs: {len(jobs)}  ({len(FLOORS)} floors each)")
    parts: list[pd.DataFrame] = []
    n_fin = 0
    with ProcessPoolExecutor(max_workers=args.max_workers) as ex:
        futs = {ex.submit(_job, j): j for j in jobs}
        for fut in as_completed(futs):
            sid, km, case, d, err = fut.result()
            n_fin += 1
            if d is None:
                print(f"  FAIL {sid} {km}km {case}: {err}", flush=True)
            else:
                parts.append(d)
            if n_fin % 40 == 0 or n_fin == len(jobs):
                print(f"  {n_fin}/{len(jobs)} jobs done", flush=True)

    if not parts:
        raise SystemExit("no successful sweeps")
    long = pd.concat(parts, ignore_index=True)
    long_path = OUT / f"{OUT_STEM}_sample_long.csv"
    long.to_csv(long_path, index=False)
    curve = aggregate(long)
    curve.to_csv(OUT / f"{OUT_STEM}.csv", index=False)
    print(f"Wrote {long_path}")
    print(f"Wrote {OUT / (OUT_STEM + '.csv')}")
    plot_curves(curve, land_kms, args.n_sample)
    print(curve.groupby(["buffer_km", "heat_case"])["served_pct"].agg(["min", "max"]).to_string())


if __name__ == "__main__":
    main()
