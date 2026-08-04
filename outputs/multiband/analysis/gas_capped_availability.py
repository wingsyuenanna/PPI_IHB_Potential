"""Gas-capped availability: raise each site's serve target until LCOH hits country gas.

For site i with country gas heat cost G_i (€/MWh, fuel/η + EUA):
  find α*_i = max { α ∈ [0,1] : LCOH_served(α) ≤ G_i }
  (LCOH from the same multiband min-cost-at-floor optimizer; 15 km land default)

Then fleet heat below gas at that serve level:
  Σ_i  α*_i × replaceable_heat_i   (using achieved reliability when land-capped)

Assumes LCOH is non-decreasing in the availability floor (hockey-stick).

    # Pilot Duisburg
    python outputs/multiband/analysis/gas_capped_availability.py --source-id 1566778

    # Full 15 km fleet (~parallel)
    python outputs/multiband/analysis/gas_capped_availability.py --land-km 15 --max-workers 8
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


def load_sites(land_km: int) -> pd.DataFrame:
    sites = pd.read_csv(SITES, low_memory=False)
    land = pd.read_csv(LAND[land_km])[["source_id", "available_land_km2"]]
    df = sites.merge(land, on="source_id", how="inner", suffixes=("", "_land"))
    if "available_land_km2_land" in df.columns:
        df["available_land_km2"] = df["available_land_km2_land"]
        df = df.drop(columns=["available_land_km2_land"])
    df = df[df["has_replaceable_heat"].astype(str).str.lower().isin(["true", "1", "True"])]
    df = df[df["has_solar_data"].astype(str).str.lower().isin(["true", "1", "True"])]
    df = df[pd.to_numeric(df["replaceable_heat_mwh_th"], errors="coerce").fillna(0) > 0]
    return df.reset_index(drop=True)


def _solve(site: dict, availability: float, cfg: dict) -> dict | None:
    c = dict(cfg)
    c["availability"] = float(availability)
    res = run_one_site(site, c)
    if res.get("status") != "ok":
        return None
    lcoh_eur = float(res["LCOH_served_$perMWh"]) / EURUSD
    return {
        "Reliability_%": float(res["Reliability_%"]),
        "LCOH_served_eur_perMWh": lcoh_eur,
        "LCOH_served_$perMWh": float(res["LCOH_served_$perMWh"]),
        "S_opt_MW": float(res["S_opt_MW"]),
        "solar_per_load_MWdc_per_MWth": float(res["solar_per_load_MWdc_per_MWth"]),
        "ihb_energy_MWh": float(res.get("ihb_energy_MWh", 0) or 0),
        "met_availability_target": bool(res.get("met_availability_target")),
        "availability_floor": float(availability),
    }


def gas_capped_alpha(
    site: dict,
    gas_eur: float,
    cfg: dict,
    tol: float = 0.025,
) -> dict:
    """Binary-search highest availability floor with LCOH ≤ gas_eur."""
    cache: dict[float, dict] = {}

    def solve(af: float) -> dict | None:
        key = round(af, 4)
        if key not in cache:
            cache[key] = _solve(site, key, cfg)  # type: ignore[assignment]
        return cache[key]

    # Anchor at 90% (fleet default)
    r90 = solve(0.90)
    if r90 is None:
        return {
            "status": "solve_fail",
            "alpha_star": 0.0,
            "Reliability_%": 0.0,
            "LCOH_served_eur_perMWh": np.nan,
            "gas_heat_cost_eur_mwh": gas_eur,
            "n_solves": len(cache),
        }

    if r90["LCOH_served_eur_perMWh"] <= gas_eur:
        # May still raise α above 90% until gas or land max
        lo, hi = 0.90, 1.0
        best = r90
        r_hi = solve(1.0)
        if r_hi is not None and r_hi["LCOH_served_eur_perMWh"] <= gas_eur:
            best = r_hi
            lo = 1.0
        else:
            while hi - lo > tol:
                mid = 0.5 * (lo + hi)
                r = solve(mid)
                if r is None:
                    hi = mid
                    continue
                if r["LCOH_served_eur_perMWh"] <= gas_eur:
                    best = r
                    lo = mid
                else:
                    hi = mid
    else:
        # Search downward from 90%
        r_lo = solve(0.05)
        if r_lo is None or r_lo["LCOH_served_eur_perMWh"] > gas_eur:
            # Even cheap partial serve is above gas (or tiny serve)
            # Try a few low floors; if all above gas → alpha=0
            best = None
            for af in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80):
                r = solve(af)
                if r is not None and r["LCOH_served_eur_perMWh"] <= gas_eur:
                    best = r
            if best is None:
                return {
                    "status": "above_gas_all",
                    "alpha_star": 0.0,
                    "Reliability_%": 0.0,
                    "LCOH_served_eur_perMWh": r90["LCOH_served_eur_perMWh"],
                    "gas_heat_cost_eur_mwh": gas_eur,
                    "S_opt_MW": 0.0,
                    "solar_per_load_MWdc_per_MWth": 0.0,
                    "n_solves": len(cache),
                }
            # Refine between best.floor and 0.90
            lo = best["availability_floor"]
            hi = 0.90
            while hi - lo > tol:
                mid = 0.5 * (lo + hi)
                r = solve(mid)
                if r is not None and r["LCOH_served_eur_perMWh"] <= gas_eur:
                    best = r
                    lo = mid
                else:
                    hi = mid
        else:
            lo, hi = 0.05, 0.90
            best = r_lo
            while hi - lo > tol:
                mid = 0.5 * (lo + hi)
                r = solve(mid)
                if r is not None and r["LCOH_served_eur_perMWh"] <= gas_eur:
                    best = r
                    lo = mid
                else:
                    hi = mid

    served_frac = best["Reliability_%"] / 100.0
    demand = float(site["replaceable_heat_mwh_th"])
    return {
        "status": "ok",
        "alpha_star": best["availability_floor"],
        "Reliability_%": best["Reliability_%"],
        "served_frac": served_frac,
        "served_mwh": demand * served_frac,
        "LCOH_served_eur_perMWh": best["LCOH_served_eur_perMWh"],
        "gas_heat_cost_eur_mwh": gas_eur,
        "S_opt_MW": best["S_opt_MW"],
        "solar_per_load_MWdc_per_MWth": best["solar_per_load_MWdc_per_MWth"],
        "n_solves": len(cache),
    }


def _worker(payload: dict) -> dict:
    site = payload["site"]
    gas_eur = payload["gas_eur"]
    cfg = payload["cfg"]
    tol = payload["tol"]
    out = gas_capped_alpha(site, gas_eur, cfg, tol=tol)
    return {
        "source_id": int(site["source_id"]),
        "source_name": site.get("source_name", ""),
        "iso3_country": site.get("iso3_country", ""),
        "subsector": site.get("subsector", ""),
        "replaceable_heat_mwh_th": float(site["replaceable_heat_mwh_th"]),
        "available_land_km2": float(site.get("available_land_km2", 0) or 0),
        **out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--land-km", type=int, default=15, choices=[5, 15])
    ap.add_argument("--source-id", type=int, default=None)
    ap.add_argument("--max-workers", type=int, default=8)
    ap.add_argument("--tol", type=float, default=0.025, help="Binary-search tolerance on α")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--project-start", type=str, default="2030")
    args = ap.parse_args()

    gas_map = load_gas_eur()
    sites = load_sites(args.land_km)
    if args.source_id is not None:
        sites = sites[sites["source_id"] == args.source_id]
    if args.limit:
        sites = sites.head(args.limit)

    cfg = dict(CONFIG)
    cfg["project_start"] = args.project_start

    payloads = []
    for _, row in sites.iterrows():
        site = row.to_dict()
        iso = str(site["iso3_country"])
        gas_eur = float(gas_map.get(iso, np.nan))
        if not np.isfinite(gas_eur):
            continue
        payloads.append({"site": site, "gas_eur": gas_eur, "cfg": cfg, "tol": args.tol})

    print(f"Gas-capped availability search: {len(payloads)} sites, {args.land_km} km land, "
          f"tol={args.tol}, workers={args.max_workers}")

    results = []
    if args.max_workers <= 1 or len(payloads) == 1:
        for i, p in enumerate(payloads, 1):
            r = _worker(p)
            results.append(r)
            print(
                f"[{i}/{len(payloads)}] {r['source_name'][:40]:<40} "
                f"α*={100*r.get('alpha_star', 0):.0f}%  "
                f"served={r.get('Reliability_%', 0):.0f}%  "
                f"LCOH=€{r.get('LCOH_served_eur_perMWh', float('nan')):.0f}  "
                f"gas=€{r['gas_heat_cost_eur_mwh']:.0f}  "
                f"solves={r.get('n_solves', 0)}",
                flush=True,
            )
    else:
        done = 0
        with ProcessPoolExecutor(max_workers=args.max_workers) as ex:
            futs = {ex.submit(_worker, p): p for p in payloads}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                done += 1
                if done % 25 == 0 or done == len(payloads):
                    print(f"  … {done}/{len(payloads)} sites", flush=True)

    out = pd.DataFrame(results)
    out_dir = ROOT / "outputs" / "multiband" / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"gas_capped_availability_{args.land_km}km"
    if args.source_id:
        tag += f"_{args.source_id}"
    csv_path = out_dir / f"{tag}.csv"
    out.to_csv(csv_path, index=False)

    ok = out[out["status"] == "ok"]
    demand = ok["replaceable_heat_mwh_th"].astype(float)
    served = ok["served_mwh"].astype(float)
    fleet_demand = float(out["replaceable_heat_mwh_th"].sum())
    summary = out_dir / f"{tag}_summary.txt"
    lines = [
        f"Gas-capped availability ({args.land_km} km land, 2030 costs)",
        f"Sites attempted: {len(out)}  ok: {len(ok)}  above_gas_all: {(out.status=='above_gas_all').sum()}",
        f"Fleet replaceable heat: {fleet_demand/1e6:.1f} TWh",
        f"Heat served at α* (LCOH≤gas): {served.sum()/1e6:.1f} TWh "
        f"({100*served.sum()/fleet_demand:.1f}% of fleet)",
        f"Mean α* (site-weighted): {100*ok['alpha_star'].mean():.1f}%",
        f"Heat-weighted achieved reliability: {100*(served.sum()/demand.sum()) if demand.sum() else 0:.1f}%",
        f"Sites with α*=0: {(ok['alpha_star']<=0).sum() + (out.status=='above_gas_all').sum()}",
        f"Wrote {csv_path}",
    ]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
