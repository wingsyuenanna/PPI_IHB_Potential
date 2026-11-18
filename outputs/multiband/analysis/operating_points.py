"""Max-savings and max-heat operating points per site from the fleet availability sweep.

Methods Eqs. maxheat and maxsav, evaluated on the 10-100% floor grid. Every runnable site in the
site assessment is returned: a site with no floor at or below its country gas heat cost, or whose
solves all failed (e.g. no eligible land), serves no heat but still counts as demand.

    from operating_points import points, fleet_stats
    p = points(15)            # one row per site: demand, served_heat, lcoh_heat, served_sav, lcoh_sav
    fleet_stats(p, "heat")    # (heat met %, heat-weighted LCOH)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from gas_benchmark import max_heat_sites, max_savings_sites

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def sweep_long(km: int) -> pd.DataFrame:
    """All solved (status ok) site x floor rows, from the per-site sweep CSVs."""
    files = [f for f in OUT.glob(f"lcoh_vs_availability_*_{km}km.csv") if f.stem.split("_")[-2].isdigit()]
    if files:
        d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    else:  # per-site files not present: fall back to the sweep's long file (complete sites only)
        d = pd.read_csv(OUT / f"fleet_availability_sweep_{km}km_long.csv", low_memory=False)
    d = d[d["status"] == "ok"].copy()
    d["availability_floor"] = d["availability_floor"].round(2)
    d["served"] = d["replaceable_heat_mwh_th"] * d["Reliability_%"] / 100.0
    d["lcoh"] = d["LCOH_served_eur_perMWh"]
    return d


def points(km: int) -> pd.DataFrame:
    sites = pd.read_csv(ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv", low_memory=False)
    sites = sites[sites["has_solar_data"] & sites["has_replaceable_heat"]]
    out = sites[["source_id", "source_name", "subsector", "iso3_country"]].copy()
    out["demand"] = sites["replaceable_heat_mwh_th"].to_numpy()
    long = sweep_long(km)
    cols = ["source_id", "iso3_country", "availability_floor", "served", "lcoh"]
    for tag, fn in (("heat", max_heat_sites), ("sav", max_savings_sites)):
        p = fn(long[cols]).set_index("source_id")
        out[f"served_{tag}"] = out["source_id"].map(p["served"]).fillna(0.0).clip(lower=0.0)
        out[f"lcoh_{tag}"] = out["source_id"].map(p["lcoh"]).where(out[f"served_{tag}"] > 0)
        out[f"floor_{tag}"] = out["source_id"].map(p["availability_floor"]).where(out[f"served_{tag}"] > 0)
    return out


def fleet_stats(p: pd.DataFrame, tag: str) -> tuple[float, float]:
    """(heat met as % of total demand, LCOH weighted by heat served)."""
    s = p[f"served_{tag}"]
    m = s > 0
    return 100.0 * s.sum() / p["demand"].sum(), float((p.loc[m, f"lcoh_{tag}"] * s[m]).sum() / s[m].sum())
