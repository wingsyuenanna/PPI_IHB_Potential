"""Heat pump break-even cost test with the hybrid low-temperature option.

For a set of sites, re-solve with the hybrid option (heat pump + Li-ion + heat battery for heat below
200 C) while scaling the heat pump CAPEX: 100%, 75%, 50% and 25% of the DEA 2030 values, plus
Rissman (2020) values in 2025 USD. Records how much heat pump capacity the optimiser builds and the
share of low-temperature heat it supplies, to find the cost at which heat pumps take over.

    python outputs/multiband/analysis/hp_cost_breakeven.py --workers 90
Output: outputs/multiband/analysis/hp_cost_breakeven.csv
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

SITES = {
    38481070: "Arla Goteborg (SWE, food)",
    38480516: "Pfeifer & Langen Lage (DEU, food)",
    38478497: "A.L. Di Pagnini (ITA, textiles)",
    44375526: "Metsa Fibre Joutseno (FIN, pulp)",
    38481043: "Nanta Las Palas (ESP, food)",
    38469177: "Sisecam Flat Glass (ITA, glass)",
}
TARGETS = [0.5, 0.7, 0.9]
LT, MT = "HP CAPEX below100C $/kWth", "HP CAPEX 100C-200C $/kWth"
# Cost cases: (label, multiplier on DEA values) or (label, absolute $/kWth below 100 C, 100-200 C).
# Rissman (2020): 700 and 870 USD-2021/kWth, 832 and 1,034 in 2025 USD (manuscript Suppl. Note 7).
CASES = [("DEA 100%", 1.0), ("DEA 75%", 0.75), ("DEA 50%", 0.5), ("DEA 25%", 0.25),
         ("Rissman", (832.0, 1034.0))]


def _r(x, n=1):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


def one(job: tuple) -> dict:
    sid, target, label, case = job
    sys.path[:0] = [str(ROOT), str(ROOT / "flatblock_optimization"), str(OUT)]
    import utils.loaders.load_re_costs as lrc

    orig = lrc.load_re_costs

    def scaled(*a, **k):
        c = orig(*a, **k)
        b = c["battery"]
        base_lt, base_mt = float(b[LT]), float(b[MT])
        if isinstance(case, tuple):
            b[LT], b[MT] = case
        else:
            b[LT], b[MT] = base_lt * case, base_mt * case
        return c

    lrc.load_re_costs = scaled
    from lcoh_vs_availability_sweep import load_site
    from run_multiband_potential import CONFIG, run_one_site

    cfg = dict(CONFIG)
    cfg["availability"] = target
    cfg["hybrid_low_temp"] = True
    t = time.time()
    r = run_one_site(load_site(sid, 15), cfg)
    hp = r.get("low_temp_heat_from_hp_MWh") or 0.0
    ih = r.get("low_temp_heat_from_ihb_MWh") or 0.0
    lc = r.get("LCOH_served_$perMWh")
    return {
        "source_id": sid, "site": SITES[sid], "target": target, "hp_cost_case": label,
        "status": r.get("status"), "served_pct": _r(r.get("Reliability_%")),
        "lcoh_eur_mwh": _r(lc / 1.08 if lc is not None else None),
        "hp_capacity_mw_th": _r(r.get("hp_capacity_MW_th"), 2), "hp_load_mw": _r(r.get("hp_load_MW"), 2),
        "low_temp_share_from_hp_pct": _r(100 * hp / (hp + ih)) if hp + ih > 0 else None,
        "solar_mw": _r(r.get("S_opt_MW"), 0), "liion_mwh": _r(r.get("liion_energy_MWh"), 0),
        "ihb_mwh": _r(r.get("ihb_energy_MWh"), 0), "solve_s": round(time.time() - t),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    jobs = [(s, t, lab, case) for s in SITES for t in TARGETS for lab, case in CASES]
    print(f"{len(jobs)} solves, {args.workers} workers", flush=True)
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, j): j for j in jobs}
        for f in as_completed(futs):
            try:
                row = f.result()
            except Exception as e:  # keep going; record the failure
                sid, t, lab, _ = futs[f]
                row = {"source_id": sid, "site": SITES[sid], "target": t, "hp_cost_case": lab,
                       "status": f"exception: {e!r}"[:200]}
            rows.append(row)
            print(row, flush=True)
    out = pd.DataFrame(rows).sort_values(["source_id", "target", "hp_cost_case"])
    out.to_csv(OUT / "hp_cost_breakeven.csv", index=False)
    print(f"Wrote {OUT / 'hp_cost_breakeven.csv'}", flush=True)


if __name__ == "__main__":
    main()
