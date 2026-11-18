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


def price_cap_curve(km: int, ks=None) -> pd.DataFrame:
    """Fleet heat met and LCOH when each site may pay up to k x its country gas heat cost.

    For each k, every site takes the highest availability floor with LCOH <= k x gas (the
    max-heat rule with a scaled threshold), so k = 1 reproduces the max-heat point. Shares are of
    total demand of all runnable sites.
    """
    import numpy as np

    from gas_benchmark import country_gas_heat

    if ks is None:
        ks = np.round(np.arange(0.40, 1.0001, 0.02), 2)
    long = sweep_long(km)
    long = long.assign(gas=long["iso3_country"].map(country_gas_heat()))
    demand = points(km)["demand"].sum()
    rows = []
    for k in ks:
        ok = long[long["lcoh"] <= k * long["gas"]]
        best = ok.loc[ok.groupby("source_id")["availability_floor"].idxmax()]
        s = best["served"].sum()
        rows.append({"k": float(k), "served_pct": 100.0 * s / demand,
                     "lcoh": float((best["lcoh"] * best["served"]).sum() / s) if s > 0 else float("nan")})
    return pd.DataFrame(rows)


def target_curve(km: int, targets=None, subsector: str | None = None) -> pd.DataFrame:
    """Fleet heat met and LCOH when every site is asked to reach the same availability target.

    For each target (10%, 20%, ..., 100%), a site moves up to the target only while that level costs
    no more than its country's gas heat cost. Otherwise it stays at its highest level below gas
    (land-limited sites keep what they can reach). At the 100% target every site sits at its own
    max-heat point, so the curve ends on the fleet max-heat point. With subsector, the same for one
    sector (shares of that sector's demand).
    """
    import numpy as np

    from gas_benchmark import country_gas_heat

    if targets is None:
        targets = np.round(np.arange(0.1, 1.0001, 0.1), 1)
    long = sweep_long(km)
    long = long[long["lcoh"] <= long["iso3_country"].map(country_gas_heat())]
    pts = points(km)
    if subsector is not None:
        long = long[long["subsector"] == subsector]
        pts = pts[pts["subsector"] == subsector]
    demand = pts["demand"].sum()
    rows = []
    for t in targets:
        ok = long[long["availability_floor"] <= t + 1e-9]
        best = ok.loc[ok.groupby("source_id")["availability_floor"].idxmax()]
        s = best["served"].sum()
        rows.append({"target": float(t), "served_pct": 100.0 * s / demand,
                     "lcoh": float((best["lcoh"] * best["served"]).sum() / s) if s > 0 else float("nan"),
                     "sites_at_target": int((best["availability_floor"] >= t - 1e-9).sum())})
    return pd.DataFrame(rows)
