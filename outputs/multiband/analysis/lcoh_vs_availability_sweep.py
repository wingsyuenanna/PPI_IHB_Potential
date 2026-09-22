"""LCOH vs availability sweep (site hockey-stick + fleet-average curve).

Site example (ArcelorMittal Duisburg, DEU gas):

    python outputs/multiband/analysis/lcoh_vs_availability_sweep.py \\
        --source-id 1566778 --land-km 15 --gas-mode country --plot-only

Fleet heat-weighted mean LCOH at each availability floor + EU avg gas:

    python outputs/multiband/analysis/lcoh_vs_availability_sweep.py \\
        --fleet-avg --land-km 15 --per-sector 2 --max-workers 8
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

from run_multiband_potential import (  # noqa: E402
    CONFIG,
    HEAT_CASE_COL,
    apply_heat_case,
    run_one_site,
)

EURUSD = 1.08
SITES = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"
GAS = ROOT / "Input" / "industrial_heat_pump_costs" / "eu_heat_pump_costs_by_country.csv"
LAND = {
    5: ROOT / "land_availability" / "outputs" / "land_availability_by_facility_5km.csv",
    15: ROOT / "land_availability" / "outputs" / "land_availability_by_facility_15km.csv",
}
PRIOR = {
    5: ROOT / "outputs" / "multiband" / "land_5km_ss_2030_liion" / "by_facility.csv",
    15: ROOT / "outputs" / "multiband" / "land_15km_ss_2030_liion" / "by_facility.csv",
}


def country_gas_eur(iso3: str) -> float:
    g = pd.read_csv(GAS)
    m = g.set_index("iso3")["gas_heat_cost_eur_mwh"].to_dict()
    m["GBR"] = m.get("IRL", float("nan"))
    return float(m.get(str(iso3), float("nan")))


def eu_hw_gas_eur(scenario: str = "land_15km_ss_2030_liion") -> float:
    """Heat-weighted EU average gas boiler heat cost (€/MWh) from fleet results."""
    path = ROOT / "outputs" / "multiband" / scenario / "by_facility_with_gas.csv"
    if not path.exists():
        g = pd.read_csv(GAS)
        return float(g["gas_heat_cost_eur_mwh"].mean())
    df = pd.read_csv(path)
    ok = df[df["status"] == "ok"].copy()
    w = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    g = pd.to_numeric(ok["gas_heat_cost_eur_mwh"], errors="coerce")
    m = w.notna() & g.notna() & (w > 0)
    return float((g[m] * w[m]).sum() / w[m].sum())


def _compact_legend(ax) -> None:
    """Horizontal legend under the x-axis — small footprint, no title/data overlap."""
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=3,
        frameon=False,
        fontsize=8,
        handlelength=1.5,
        columnspacing=1.0,
        handletextpad=0.4,
        borderaxespad=0.0,
    )


def load_site(source_id: int, land_km: int, heat_case: str = "base") -> dict:
    sites = pd.read_csv(SITES, low_memory=False)
    sites = apply_heat_case(sites, heat_case)
    row = sites[sites["source_id"] == source_id]
    if row.empty:
        raise SystemExit(f"source_id {source_id} not in {SITES}")
    r = row.iloc[0].to_dict()
    land_csv = LAND[land_km]
    land = pd.read_csv(land_csv)
    id_col = "source_id" if "source_id" in land.columns else "SiteID"
    land_col = "available_land_km2" if "available_land_km2" in land.columns else None
    if land_col is None:
        for c in land.columns:
            if "available_land" in c.lower() or c == "land_km2":
                land_col = c
                break
    hit = land[land[id_col] == source_id]
    if hit.empty:
        raise SystemExit(f"source_id {source_id} not in {land_csv}")
    r["available_land_km2"] = float(hit.iloc[0][land_col])
    r["heat_case"] = heat_case
    return r


def sweep(
    source_id: int,
    land_km: int,
    floors: list[float],
    project_start: str = "2030",
    n_rep_days: int = 16,
    heat_case: str = "base",
) -> pd.DataFrame:
    if heat_case not in HEAT_CASE_COL:
        raise ValueError(f"heat_case must be one of {list(HEAT_CASE_COL)}")
    site = load_site(source_id, land_km, heat_case=heat_case)
    cfg = dict(CONFIG)
    cfg["project_start"] = project_start
    cfg["n_representative_days"] = n_rep_days

    rows = []
    for af in floors:
        cfg["availability"] = float(af)
        print(f"  availability floor {100*af:.0f}% …", flush=True)
        res = run_one_site(site, cfg)
        if res.get("status") != "ok":
            print(f"    → {res.get('status')}")
            rows.append(
                {
                    "availability_floor": af,
                    "status": res.get("status"),
                    "source_id": source_id,
                    "heat_case": heat_case,
                }
            )
            continue
        rel = float(res["Reliability_%"])
        lcoh_usd = float(res["LCOH_served_$perMWh"])
        rows.append(
            {
                "source_id": source_id,
                "source_name": res.get("source_name"),
                "iso3_country": res.get("iso3_country"),
                "subsector": res.get("subsector"),
                "land_km": land_km,
                "heat_case": heat_case,
                "available_land_km2": res.get("available_land_km2"),
                "replaceable_heat_mwh_th": float(
                    site.get("replaceable_heat_mwh_th") or res.get("replaceable_heat_mwh_th") or 0
                ),
                "availability_floor": af,
                "Reliability_%": rel,
                "met_availability_target": res.get("met_availability_target"),
                "LCOH_served_$perMWh": lcoh_usd,
                "LCOH_served_eur_perMWh": lcoh_usd / EURUSD,
                "S_opt_MW": float(res["S_opt_MW"]),
                "solar_per_load_MWdc_per_MWth": float(res["solar_per_load_MWdc_per_MWth"]),
                "ihb_energy_MWh": float(res.get("ihb_energy_MWh", 0) or 0),
                "liion_energy_MWh": float(res.get("liion_energy_MWh", 0) or 0),
                "total_load_MW": float(res["total_load_MW"]),
                "status": "ok",
            }
        )
        print(
            f"    → served {rel:.1f}%  LCOH €{lcoh_usd/EURUSD:.0f}/MWh  "
            f"solar {res['S_opt_MW']:.0f} MWdc"
        )
    return pd.DataFrame(rows)


def _sweep_one(args: tuple) -> pd.DataFrame:
    if len(args) == 5:
        sid, land_km, floors, project_start, n_rep = args
        heat_case = "base"
    else:
        sid, land_km, floors, project_start, n_rep, heat_case = args
    return sweep(
        sid, land_km, floors, project_start=project_start, n_rep_days=n_rep, heat_case=heat_case
    )


def pick_sample(
    land_km: int,
    per_sector: int = 2,
    n_total: int | None = None,
    seed: int = 0,
) -> list[int]:
    """Heat-representative site sample matching fleet met/miss mix.

    Previous "top-N per sector" samples were dominated by giant land-capped
    steam-cracking / steel plants, so HW availability plateaued ~80% and never
    reached the full-fleet ~86% (15 km @ 90% floor). This sampler:

    1. Allocates site counts ∝ sector heat share
    2. Within each sector, splits met vs miss-90% ∝ heat in each bucket
    3. Draws heat-weighted without replacement
    """
    prior = pd.read_csv(PRIOR[land_km])
    ok = prior[prior["status"] == "ok"].copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["land"] = pd.to_numeric(ok["available_land_km2"], errors="coerce")
    ok["met"] = ok["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
    ok = ok[(ok["heat"] > 0) & (ok["land"].fillna(0) > 0)]
    if ok.empty:
        return []

    if n_total is None:
        # Default: ~4× per-sector legacy size, capped
        n_total = int(np.clip(per_sector * ok["subsector"].nunique() * 2, 30, 80))

    sector_heat = ok.groupby("subsector")["heat"].sum()
    shares = sector_heat / sector_heat.sum()
    alloc = (shares * n_total).round().astype(int).clip(lower=2)
    # Fix rounding to exact n_total
    while int(alloc.sum()) > n_total:
        alloc[alloc.idxmax()] -= 1
    while int(alloc.sum()) < n_total:
        alloc[alloc.idxmax()] += 1

    rng = np.random.default_rng(seed)
    ids: list[int] = []

    def _draw(g: pd.DataFrame, n: int) -> list[int]:
        if g.empty or n <= 0:
            return []
        n = min(n, len(g))
        p = (g["heat"] / g["heat"].sum()).to_numpy()
        chosen = rng.choice(g["source_id"].to_numpy(), size=n, replace=False, p=p)
        return [int(x) for x in chosen]

    for sec, n_sec in alloc.items():
        g = ok[ok["subsector"] == sec]
        met_h = float(g.loc[g["met"], "heat"].sum())
        miss_h = float(g.loc[~g["met"], "heat"].sum())
        tot = met_h + miss_h
        if tot <= 0:
            ids.extend(_draw(g, int(n_sec)))
            continue
        n_met = int(round(n_sec * met_h / tot))
        n_miss = int(n_sec) - n_met
        # Keep at least one of each bucket when both have heat and n_sec>=2
        if met_h > 0 and miss_h > 0 and n_sec >= 2:
            n_met = max(1, n_met)
            n_miss = max(1, int(n_sec) - n_met)
        ids.extend(_draw(g[g["met"]], n_met))
        ids.extend(_draw(g[~g["met"]], n_miss))

    return sorted(set(ids))


def plot_site(
    df: pd.DataFrame,
    out_png: Path,
    *,
    gas_mode: str = "country",
) -> None:
    ok = df[df["status"] == "ok"].copy()
    if ok.empty:
        raise SystemExit("no successful solves to plot")

    name = str(ok["source_name"].iloc[0])
    land_km = int(ok["land_km"].iloc[0])
    iso = str(ok["iso3_country"].iloc[0]) if "iso3_country" in ok.columns else ""
    gas_country = country_gas_eur(iso) if iso else float("nan")
    gas_eu = eu_hw_gas_eur()
    x = 100 * ok["availability_floor"].astype(float)
    y = ok["LCOH_served_eur_perMWh"].astype(float)

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.plot(x, y, "o-", color="#1f4e79", lw=2, ms=6, label="LCOH served")

    gas_ref = float("nan")
    if gas_mode in ("country", "both") and np.isfinite(gas_country):
        ax.axhline(
            gas_country, color="#e67e22", ls="--", lw=1.8,
            label=f"DEU gas €{gas_country:.0f}" if iso == "DEU" else f"{iso} gas €{gas_country:.0f}",
        )
        gas_ref = gas_country
    if gas_mode in ("eu_avg", "both") and np.isfinite(gas_eu):
        ax.axhline(
            gas_eu, color="#8e44ad", ls=":", lw=1.8,
            label=f"EU avg gas €{gas_eu:.0f}",
        )
        if gas_mode == "eu_avg":
            gas_ref = gas_eu

    if np.isfinite(gas_ref):
        below = y <= gas_ref + 1e-6
        if below.any():
            i = int(np.where(below.to_numpy())[0][-1])
            ax.scatter(
                [x.iloc[i]], [y.iloc[i]], s=55, zorder=5, color="#27ae60",
                label=f"Last ≤ gas (~{x.iloc[i]:.0f}%)",
            )

    ax.set_xlabel("Availability floor (%)")
    ax.set_ylabel("LCOH of served heat (€/MWh)")
    ax.set_title(f"{name} — LCOH vs availability ({land_km} km)")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 105)
    gas_hi = max(
        gas_country if np.isfinite(gas_country) else 0,
        gas_eu if np.isfinite(gas_eu) else 0,
    )
    ax.set_ylim(0, max(float(y.max()), gas_hi) * 1.12)
    _compact_legend(ax)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")


def _fleet_bucket_heat(land_km: int) -> pd.DataFrame:
    """Fleet heat (MWh) by subsector × met_availability_target."""
    prior = pd.read_csv(PRIOR[land_km])
    ok = prior[prior["status"] == "ok"].copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["met"] = ok["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
    g = (
        ok.groupby(["subsector", "met"], as_index=False)["heat"]
        .sum()
        .rename(columns={"heat": "fleet_heat"})
    )
    return g


def plot_fleet_avg(long_df: pd.DataFrame, out_png: Path, gas_eu: float) -> pd.DataFrame:
    """Heat-weighted mean LCOH vs achieved availability + EU avg gas.

    Site weights are scaled so each (subsector × met/miss) bucket carries the
    *full fleet* heat of that bucket. That way a small sample still tracks the
    fleet HW-availability statistic (~86% at 15 km / 90% floor) instead of
    plateauing near 80% from giant land-capped plants.
    """
    ok = long_df[long_df["status"] == "ok"].copy()
    if "replaceable_heat_mwh_th" not in ok.columns:
        raise SystemExit("fleet avg needs replaceable_heat_mwh_th on long CSV")
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["lcoh"] = pd.to_numeric(ok["LCOH_served_eur_perMWh"], errors="coerce")
    ok["floor"] = pd.to_numeric(ok["availability_floor"], errors="coerce")
    ok["rel"] = pd.to_numeric(ok["Reliability_%"], errors="coerce")
    land_km = int(ok["land_km"].iloc[0]) if "land_km" in ok.columns else 15

    # Met/miss label from the standard 90% fleet run (not from each floor).
    prior = pd.read_csv(PRIOR[land_km])
    meta = prior[["source_id", "subsector", "met_availability_target"]].drop_duplicates("source_id")
    meta["met"] = meta["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
    ok = ok.merge(meta[["source_id", "subsector", "met"]], on="source_id", how="left", suffixes=("", "_m"))
    if "subsector" not in ok.columns or ok["subsector"].isna().all():
        ok["subsector"] = ok.get("subsector_m", ok.get("subsector"))
    buckets = _fleet_bucket_heat(land_km)

    # Per-site base weight from 90%-floor row heat, scaled to fleet bucket heat.
    base = ok[np.isclose(ok["floor"], 0.9)].drop_duplicates("source_id")[
        ["source_id", "subsector", "met", "heat"]
    ].copy()
    if base.empty:
        base = ok.sort_values("floor").drop_duplicates("source_id")[
            ["source_id", "subsector", "met", "heat"]
        ].copy()
    base = base.merge(buckets, on=["subsector", "met"], how="left")
    sample_bucket = base.groupby(["subsector", "met"])["heat"].transform("sum")
    base["w"] = base["heat"] * (base["fleet_heat"] / sample_bucket.replace(0, np.nan))
    base["w"] = base["w"].fillna(base["heat"])
    wmap = base.set_index("source_id")["w"].to_dict()
    ok["w"] = ok["source_id"].map(wmap).astype(float)

    rows = []
    for fl, g in ok.groupby("floor"):
        w = g["w"]
        rows.append(
            {
                "availability_floor": float(fl),
                "floor_pct": 100 * float(fl),
                "hw_LCOH_eur": float((g["lcoh"] * w).sum() / w.sum()),
                "mean_LCOH_eur": float(g["lcoh"].mean()),
                "hw_Reliability_%": float((g["rel"] * w).sum() / w.sum()),
                "n_sites": int(g["source_id"].nunique()),
                "sample_heat_TWh": float(
                    g.drop_duplicates("source_id")["heat"].sum() / 1e6
                ),
                "reweighted_heat_TWh": float(
                    g.drop_duplicates("source_id")
                    .assign(w=lambda d: d["source_id"].map(wmap))
                    ["w"]
                    .sum()
                    / 1e6
                ),
            }
        )
    avg = pd.DataFrame(rows).sort_values("availability_floor")

    fleet_hw_avail = float("nan")
    if PRIOR[land_km].exists():
        fdf = pd.read_csv(PRIOR[land_km])
        fok = fdf[fdf["status"] == "ok"].copy()
        fw = pd.to_numeric(fok["replaceable_heat_mwh_th"], errors="coerce")
        fr = pd.to_numeric(fok["Reliability_%"], errors="coerce")
        m = fw.notna() & fr.notna() & (fw > 0)
        fleet_hw_avail = float((fr[m] * fw[m]).sum() / fw[m].sum())

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    x = avg["hw_Reliability_%"]
    y = avg["hw_LCOH_eur"]
    ax.plot(x, y, "o-", color="#1f4e79", lw=2, ms=6, label="HW-avg LCOH")
    ax.axhline(
        gas_eu, color="#e67e22", ls="--", lw=1.8,
        label=f"EU avg gas €{gas_eu:.0f}",
    )
    if np.isfinite(fleet_hw_avail):
        ax.axvline(
            fleet_hw_avail, color="#7f8c8d", ls=":", lw=1.6,
            label=f"Fleet HW avail. @90% floor ({fleet_hw_avail:.0f}%)",
        )
    below = y <= gas_eu + 1e-6
    if below.any():
        i = int(np.where(below.to_numpy())[0][-1])
        ax.scatter(
            [x.iloc[i]], [y.iloc[i]],
            s=55, zorder=5, color="#27ae60",
            label=f"Last ≤ gas (~{x.iloc[i]:.0f}% achieved)",
        )
    n = int(avg["n_sites"].iloc[0])
    heat = float(avg["reweighted_heat_TWh"].iloc[0])
    ax.set_xlabel("Heat-weighted average availability achieved (%)")
    ax.set_ylabel("Heat-weighted avg LCOH (€/MWh)")
    ax.set_title(
        f"Fleet-sample LCOH vs achieved availability ({land_km} km; n={n}, {heat:.0f} TWh reweighted)"
    )
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 105)
    ax.set_ylim(0, max(float(y.max()), gas_eu) * 1.15)
    _compact_legend(ax)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.24)
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")
    print(
        f"  @90% floor: sample reweighted HW avail={avg.loc[np.isclose(avg.availability_floor, 0.9), 'hw_Reliability_%'].iloc[0]:.1f}% "
        f"(fleet {fleet_hw_avail:.1f}%)"
    )
    return avg


def run_fleet_avg(
    land_km: int,
    floors: list[float],
    per_sector: int,
    project_start: str,
    n_rep_days: int,
    max_workers: int,
    out_dir: Path,
    n_total: int | None = None,
) -> None:
    ids = pick_sample(land_km, per_sector=per_sector, n_total=n_total)
    # Validate sample reproduces fleet HW availability at the standard 90% floor.
    prior = pd.read_csv(PRIOR[land_km])
    pok = prior[prior["status"] == "ok"].copy()
    pok["heat"] = pd.to_numeric(pok["replaceable_heat_mwh_th"], errors="coerce")
    pok["rel"] = pd.to_numeric(pok["Reliability_%"], errors="coerce")
    fleet_hw = float((pok["rel"] * pok["heat"]).sum() / pok["heat"].sum())
    samp = pok[pok["source_id"].isin(ids)]
    samp_hw = float((samp["rel"] * samp["heat"]).sum() / samp["heat"].sum())
    print(
        f"Fleet-avg sample: {len(ids)} sites | "
        f"prior@90% floor HW avail sample={samp_hw:.1f}% vs fleet={fleet_hw:.1f}%"
    )
    print(f"floors={floors}")
    long_path = out_dir / f"lcoh_vs_availability_fleet_sample_{land_km}km.csv"
    avg_path = out_dir / f"lcoh_vs_availability_fleet_avg_{land_km}km.csv"
    png_path = out_dir / f"lcoh_vs_availability_fleet_avg_{land_km}km.png"

    # Only keep sweeps for sites in this sample (ignore prior top-N CSVs).
    parts: list[pd.DataFrame] = []
    todo: list[int] = []
    for sid in ids:
        p = out_dir / f"lcoh_vs_availability_{sid}_{land_km}km.csv"
        if p.exists():
            d = pd.read_csv(p)
            if "replaceable_heat_mwh_th" not in d.columns or d["replaceable_heat_mwh_th"].isna().all():
                site = load_site(sid, land_km)
                d["replaceable_heat_mwh_th"] = float(site.get("replaceable_heat_mwh_th") or 0)
            # Require full floor set
            have = set(np.round(d.loc[d["status"] == "ok", "availability_floor"], 4))
            need = set(np.round(floors, 4))
            if need.issubset(have):
                parts.append(d)
                continue
        todo.append(sid)

    if todo:
        print(f"Sweeping {len(todo)} sites …")
        jobs = [
            (sid, land_km, floors, project_start, n_rep_days) for sid in todo
        ]
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_sweep_one, j): j[0] for j in jobs}
            for fut in as_completed(futs):
                sid = futs[fut]
                try:
                    d = fut.result()
                except Exception as e:
                    print(f"  site {sid} failed: {e}")
                    continue
                d.to_csv(out_dir / f"lcoh_vs_availability_{sid}_{land_km}km.csv", index=False)
                parts.append(d)
                print(f"  done {sid} ({len(parts)}/{len(ids)})")

    if not parts:
        raise SystemExit("no site sweeps available for fleet average")
    long_df = pd.concat(parts, ignore_index=True)
    # Safety: only sample sites
    long_df = long_df[long_df["source_id"].isin(ids)].copy()
    long_df.to_csv(long_path, index=False)
    print(f"Wrote {long_path}")
    gas_eu = eu_hw_gas_eur()
    avg = plot_fleet_avg(long_df, png_path, gas_eu)
    avg.to_csv(avg_path, index=False)
    print(f"Wrote {avg_path}")
    print(avg.to_string(index=False, float_format=lambda x: f"{x:.1f}"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-id", type=int, default=1566778)
    ap.add_argument("--land-km", type=int, default=15, choices=[5, 15])
    ap.add_argument("--step", type=float, default=10.0)
    ap.add_argument("--project-start", type=str, default="2030")
    ap.add_argument("--n-representative-days", type=int, default=16)
    ap.add_argument("--gas-mode", choices=["country", "eu_avg", "both"], default="country")
    ap.add_argument("--plot-only", action="store_true")
    ap.add_argument("--fleet-avg", action="store_true",
                    help="Heat-weighted mean LCOH across a sector sample + EU avg gas")
    ap.add_argument("--per-sector", type=int, default=2,
                    help="Legacy scale hint for --fleet-avg sample size")
    ap.add_argument("--n-sample", type=int, default=50,
                    help="Target number of sites for --fleet-avg (heat+met/miss stratified)")
    ap.add_argument("--max-workers", type=int, default=8)
    args = ap.parse_args()

    floors = list(np.arange(args.step, 100.0 + 1e-9, args.step) / 100.0)
    if 0.95 not in floors and args.step >= 5:
        floors.append(0.95)
        floors = sorted(set(floors))

    out_dir = ROOT / "outputs" / "multiband" / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.fleet_avg:
        run_fleet_avg(
            args.land_km,
            floors,
            args.per_sector,
            args.project_start,
            args.n_representative_days,
            args.max_workers,
            out_dir,
            n_total=args.n_sample,
        )
        return

    tag = f"lcoh_vs_availability_{args.source_id}_{args.land_km}km"
    csv_path = out_dir / f"{tag}.csv"
    png_path = out_dir / f"{tag}.png"

    if args.plot_only:
        if not csv_path.exists():
            raise SystemExit(f"--plot-only but missing {csv_path}")
        df = pd.read_csv(csv_path)
        print(f"Replotting from {csv_path}")
    else:
        print(f"Sweep source_id={args.source_id} land={args.land_km} km  floors={floors}")
        df = sweep(
            args.source_id,
            args.land_km,
            floors,
            project_start=args.project_start,
            n_rep_days=args.n_representative_days,
        )
        df.to_csv(csv_path, index=False)
        print(f"Wrote {csv_path}")
    plot_site(df, png_path, gas_mode=args.gas_mode)

if __name__ == "__main__":
    main()
