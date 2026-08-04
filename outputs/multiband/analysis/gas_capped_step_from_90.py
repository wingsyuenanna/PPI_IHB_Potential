"""Gas-capped availability via discrete steps from the existing 90% fleet solve.

For each site, reuse the 90% floor result from by_facility_with_gas.csv, then:
  • if LCOH@90% ≤ country gas → step UP (90, 95, 100, …) while still ≤ gas
  • if LCOH@90% > country gas → step DOWN (85, 80, …) until ≤ gas

α* = last floor with LCOH ≤ gas; served heat uses achieved Reliability_% at that solve.

    python outputs/multiband/analysis/gas_capped_step_from_90.py --land-km 15 --max-workers 8
    python outputs/multiband/analysis/gas_capped_step_from_90.py --land-km 5 --max-workers 8
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flatblock_optimization"))

from run_multiband_potential import CONFIG, run_one_site  # noqa: E402

EURUSD = 1.08
SITES = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"
GAS = ROOT / "Input" / "industrial_heat_pump_costs" / "eu_heat_pump_costs_by_country.csv"
LAND = {
    5: ROOT / "land_availability" / "outputs" / "land_availability_by_facility_5km.csv",
    15: ROOT / "land_availability" / "outputs" / "land_availability_by_facility_15km.csv",
}
PRIOR = {
    5: ROOT / "outputs" / "multiband" / "land_5km_ss_2030_liion" / "by_facility_with_gas.csv",
    15: ROOT / "outputs" / "multiband" / "land_15km_ss_2030_liion" / "by_facility_with_gas.csv",
}


def load_gas_eur() -> dict[str, float]:
    g = pd.read_csv(GAS)
    m = g.set_index("iso3")["gas_heat_cost_eur_mwh"].to_dict()
    m["GBR"] = m.get("IRL", float("nan"))
    return m


def _solve(site: dict, availability: float, cfg: dict) -> dict | None:
    c = dict(cfg)
    c["availability"] = float(availability)
    res = run_one_site(site, c)
    if res.get("status") != "ok":
        return None
    return {
        "Reliability_%": float(res["Reliability_%"]),
        "LCOH_served_eur_perMWh": float(res["LCOH_served_$perMWh"]) / EURUSD,
        "LCOH_served_$perMWh": float(res["LCOH_served_$perMWh"]),
        "S_opt_MW": float(res["S_opt_MW"]),
        "solar_per_load_MWdc_per_MWth": float(res["solar_per_load_MWdc_per_MWth"]),
        "met_availability_target": bool(res.get("met_availability_target")),
        "availability_floor": float(availability),
    }


def step_from_90(
    site: dict,
    gas_eur: float,
    cfg: dict,
    prior90: dict,
    step: float = 0.05,
) -> dict:
    """Discrete step search from the reused 90% solve."""
    n_new = 0
    r90 = {
        "Reliability_%": float(prior90["Reliability_%"]),
        "LCOH_served_eur_perMWh": float(prior90["LCOH_served_$perMWh"]) / EURUSD,
        "LCOH_served_$perMWh": float(prior90["LCOH_served_$perMWh"]),
        "S_opt_MW": float(prior90.get("S_opt_MW", 0) or 0),
        "solar_per_load_MWdc_per_MWth": float(
            prior90.get("solar_per_load_MWdc_per_MWth", 0) or 0
        ),
        "met_availability_target": bool(
            str(prior90.get("met_availability_target", "")).lower() in ("true", "1")
        ),
        "availability_floor": 0.90,
    }

    def solve(af: float) -> dict | None:
        nonlocal n_new
        if abs(af - 0.90) < 1e-9:
            return r90
        n_new += 1
        return _solve(site, af, cfg)

    if r90["LCOH_served_eur_perMWh"] <= gas_eur + 1e-9:
        # Step up while still ≤ gas
        best = r90
        af = 0.90 + step
        while af <= 1.0 + 1e-9:
            r = solve(min(af, 1.0))
            if r is None:
                break
            if r["LCOH_served_eur_perMWh"] <= gas_eur + 1e-9:
                best = r
                af += step
            else:
                break
    else:
        # Step down until ≤ gas
        best = None
        af = 0.90 - step
        while af >= 0.05 - 1e-9:
            r = solve(max(af, 0.05))
            if r is not None and r["LCOH_served_eur_perMWh"] <= gas_eur + 1e-9:
                best = r
                break
            af -= step
        if best is None:
            demand = float(site["replaceable_heat_mwh_th"])
            return {
                "status": "above_gas_all",
                "alpha_star": 0.0,
                "Reliability_%": 0.0,
                "served_frac": 0.0,
                "served_mwh": 0.0,
                "LCOH_served_eur_perMWh": r90["LCOH_served_eur_perMWh"],
                "LCOH_at_90_eur_perMWh": r90["LCOH_served_eur_perMWh"],
                "gas_heat_cost_eur_mwh": gas_eur,
                "direction": "down",
                "S_opt_MW": 0.0,
                "solar_per_load_MWdc_per_MWth": 0.0,
                "n_solves_new": n_new,
                "below_gas_at_90": False,
            }

    demand = float(site["replaceable_heat_mwh_th"])
    served_frac = best["Reliability_%"] / 100.0
    return {
        "status": "ok",
        "alpha_star": best["availability_floor"],
        "Reliability_%": best["Reliability_%"],
        "served_frac": served_frac,
        "served_mwh": demand * served_frac,
        "LCOH_served_eur_perMWh": best["LCOH_served_eur_perMWh"],
        "LCOH_at_90_eur_perMWh": r90["LCOH_served_eur_perMWh"],
        "gas_heat_cost_eur_mwh": gas_eur,
        "direction": "up" if r90["LCOH_served_eur_perMWh"] <= gas_eur + 1e-9 else "down",
        "S_opt_MW": best["S_opt_MW"],
        "solar_per_load_MWdc_per_MWth": best["solar_per_load_MWdc_per_MWth"],
        "n_solves_new": n_new,
        "below_gas_at_90": bool(r90["LCOH_served_eur_perMWh"] <= gas_eur + 1e-9),
    }


def _worker(payload: dict) -> dict:
    site = payload["site"]
    out = step_from_90(
        site,
        payload["gas_eur"],
        payload["cfg"],
        payload["prior90"],
        step=payload["step"],
    )
    return {
        "source_id": int(site["source_id"]),
        "source_name": site.get("source_name", ""),
        "iso3_country": site.get("iso3_country", ""),
        "subsector": site.get("subsector", ""),
        "replaceable_heat_mwh_th": float(site["replaceable_heat_mwh_th"]),
        "available_land_km2": float(site.get("available_land_km2", 0) or 0),
        **out,
    }


def summarize(out: pd.DataFrame, land_km: int, step: float) -> list[str]:
    ok = out[out["status"] == "ok"]
    demand_all = float(out["replaceable_heat_mwh_th"].sum())
    served = ok["served_mwh"].astype(float) if len(ok) else pd.Series(dtype=float)
    demand_ok = ok["replaceable_heat_mwh_th"].astype(float) if len(ok) else pd.Series(dtype=float)
    above = int((out["status"] == "above_gas_all").sum())
    n_up = int((out.get("direction") == "up").sum()) if "direction" in out.columns else 0
    n_down = int((out.get("direction") == "down").sum()) if "direction" in out.columns else 0
    hw_alpha = (
        float((ok["alpha_star"] * demand_ok).sum() / demand_ok.sum()) if len(ok) and demand_ok.sum() else 0.0
    )
    hw_rel = float(served.sum() / demand_all) if demand_all else 0.0
    lines = [
        f"Gas-capped step-from-90% ({land_km} km, step={100*step:.0f} pp, 2030 costs)",
        f"Sites: {len(out)}  ok: {len(ok)}  above_gas_all: {above}",
        f"Direction: stepped up {n_up} | stepped down {n_down}",
        f"Fleet process heat: {demand_all/1e6:.1f} TWh",
        f"Heat served at α* (LCOH≤country gas): {served.sum()/1e6:.1f} TWh "
        f"({100*hw_rel:.1f}% of fleet)",
        f"Heat-weighted α* (floor): {100*hw_alpha:.1f}%",
        f"Heat-weighted achieved availability: {100*hw_rel:.1f}%",
        f"Mean α* (site): {100*ok['alpha_star'].mean():.1f}%" if len(ok) else "Mean α*: n/a",
        f"New solves (excl. reused 90%): {int(out['n_solves_new'].sum())}",
    ]
    return lines


def run_land(land_km: int, step: float, max_workers: int, project_start: str, limit: int | None) -> Path:
    gas_map = load_gas_eur()
    prior = pd.read_csv(PRIOR[land_km])
    prior_ok = prior[prior["status"] == "ok"].copy()
    land = pd.read_csv(LAND[land_km])[["source_id", "available_land_km2"]]
    sites = pd.read_csv(SITES, low_memory=False)
    sites = sites.merge(land, on="source_id", how="inner", suffixes=("", "_land"))
    if "available_land_km2_land" in sites.columns:
        sites["available_land_km2"] = sites["available_land_km2_land"]
    # Keep only sites present in prior 90% fleet
    sites = sites.merge(
        prior_ok[
            [
                "source_id",
                "Reliability_%",
                "LCOH_served_$perMWh",
                "S_opt_MW",
                "solar_per_load_MWdc_per_MWth",
                "met_availability_target",
                "replaceable_heat_mwh_th",
            ]
        ],
        on="source_id",
        how="inner",
        suffixes=("", "_prior"),
    )
    if "replaceable_heat_mwh_th_prior" in sites.columns:
        sites["replaceable_heat_mwh_th"] = sites["replaceable_heat_mwh_th_prior"]
    if limit:
        sites = sites.head(limit)

    cfg = dict(CONFIG)
    cfg["project_start"] = project_start

    payloads = []
    for _, row in sites.iterrows():
        site = row.to_dict()
        iso = str(site["iso3_country"])
        gas_eur = float(gas_map.get(iso, np.nan))
        if not np.isfinite(gas_eur):
            continue
        prior90 = {
            "Reliability_%": row["Reliability_%"],
            "LCOH_served_$perMWh": row["LCOH_served_$perMWh"],
            "S_opt_MW": row["S_opt_MW"],
            "solar_per_load_MWdc_per_MWth": row["solar_per_load_MWdc_per_MWth"],
            "met_availability_target": row["met_availability_target"],
        }
        payloads.append(
            {
                "site": site,
                "gas_eur": gas_eur,
                "cfg": cfg,
                "prior90": prior90,
                "step": step,
            }
        )

    print(
        f"Step-from-90% gas-capped: {len(payloads)} sites, {land_km} km, "
        f"step={100*step:.0f}pp, workers={max_workers}",
        flush=True,
    )

    results = []
    if max_workers <= 1 or len(payloads) <= 1:
        for i, p in enumerate(payloads, 1):
            r = _worker(p)
            results.append(r)
            if i % 50 == 0 or i == len(payloads):
                print(f"  … {i}/{len(payloads)}", flush=True)
    else:
        done = 0
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_worker, p): p for p in payloads}
            for fut in as_completed(futs):
                results.append(fut.result())
                done += 1
                if done % 50 == 0 or done == len(payloads):
                    print(f"  … {done}/{len(payloads)}", flush=True)

    out = pd.DataFrame(results)
    out_dir = ROOT / "outputs" / "multiband" / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"gas_capped_step90_{land_km}km"
    csv_path = out_dir / f"{tag}.csv"
    out.to_csv(csv_path, index=False)
    lines = summarize(out, land_km, step)
    lines.append(f"Wrote {csv_path}")
    (out_dir / f"{tag}_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return csv_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--land-km", type=int, nargs="+", default=[5, 15], choices=[5, 15])
    ap.add_argument("--step", type=float, default=0.05, help="Availability step (default 5 pp)")
    ap.add_argument("--max-workers", type=int, default=8)
    ap.add_argument("--project-start", type=str, default="2030")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    for km in args.land_km:
        run_land(km, args.step, args.max_workers, args.project_start, args.limit)


if __name__ == "__main__":
    main()
