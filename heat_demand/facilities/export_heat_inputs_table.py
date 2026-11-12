"""Export the inputs behind the facility heat-demand estimate, one row per sector/route.

Writes heat_demand/facilities/heat_demand_inputs.csv. Rerun after the heat pipeline
(merge_production -> heat_temperature_bands -> apply_dedup -> apply_fossil_share) so
the table matches the data actually used.

Columns: sector/route, facility count, heat method, production source(s), process recipe,
SEC and its source, efficiency and its source, temperature-band shares and their source,
fossil-share source, and resulting useful and replaceable heat (TWh).
"""

from pathlib import Path

import numpy as np
import pandas as pd

import heat_temperature_bands as htb

HERE = Path(__file__).resolve().parent
FACILITIES = HERE / "facilities_2024_eu_replaceable.csv"
MERGED = HERE / "facilities_2024_eu_merged.csv"
OUT = HERE / "heat_demand_inputs.csv"
BANDS = htb.BANDS

# Efficiency rule (merge_production.heat_efficiency): Saad et al. 2026 boiler 0.94 /
# direct 0.75, steam fraction from IndustryHeat-EU sector steam share for heat <500 C.
EFF_RULE = ("Saad et al. 2026: 0.94 boiler steam, 0.75 direct; steam fraction = "
            "IndustryHeat-EU sector steam share x heat share <500 C")
EFF_SOURCE = {"aluminum": EFF_RULE + "; alumina digestion 67% steam (Deloitte/ARENA 2022)"}


def route_key(row: pd.Series) -> str:
    sub, st = row["subsector"], str(row["source_type"])
    if sub in ("iron-and-steel", "aluminum", "chemicals"):
        return st
    if sub == "glass":
        return str(row.get("process_match") or "no production")
    if sub == "pulp-and-paper":
        recipe = htb.pulp_recipe(st)
        return "; ".join(f"{p} {w:g}" for _, p, w in recipe if p != "Paper")
    if sub == "food-beverage-tobacco":
        return str(row.get("process_match"))
    return "all"


def main() -> None:
    d = pd.read_csv(FACILITIES, low_memory=False)
    if "sec_source" not in d.columns:
        m = pd.read_csv(MERGED, low_memory=False)[["source_id", "sec_gj_t", "sec_source"]]
        d = d.merge(m, on="source_id", how="left")
    d = d[d["replaceable_heat_mwh"].fillna(0) > 0].copy()
    d["route"] = d.apply(route_key, axis=1)
    d["eff"] = d["useful_heat_tj"] / d["fuel_energy_tj"]

    rows = []
    for (sub, route), g in d.groupby(["subsector", "route"], dropna=False):
        r0 = g.iloc[0]
        recipe = htb.facility_recipe(r0) if r0["heat_method"] == "production_sec" else None
        band = g[[f"heat_{b}_tj" for b in BANDS]].sum()
        band = band / band.sum() if band.sum() > 0 else band
        sec_src = r0["sec_source"]
        rows.append({
            "subsector": sub,
            "route": route,
            "facilities": len(g),
            "heat_method": r0["heat_method"],
            "production_source": "; ".join(sorted(g["production_source"].astype(str).unique())),
            "process_recipe": "; ".join(f"{p} {w:g}" for _, p, w in recipe) if recipe else "",
            "sec_gj_t": round(float(g["sec_gj_t"].mean()), 2) if g["sec_gj_t"].notna().any() else np.nan,
            "sec_source": {"hotmaps": "Hotmaps industry benchmarks (SEC_Fuels)",
                           "sec_params": "Deloitte/ARENA alumina roadmap 2022"}.get(sec_src, "n/a (emissions route)"),
            "eff": round(float(g["eff"].median()), 2),
            "steam_frac": round(float(g["steam_frac"].median()), 2) if "steam_frac" in g else np.nan,
            "eff_source": EFF_SOURCE["aluminum"] if (sub, route) == ("aluminum", "Refinery") else EFF_RULE,
            **{f"share_{b}": round(float(band[f'heat_{b}_tj']), 3) for b in BANDS},
            "band_source": "; ".join(sorted(g["band_source"].astype(str).unique())),
            "fossil_share_source": "Eurostat nrg_d_indq_n 2024 (" + "; ".join(sorted(g["fossil_share_basis"].astype(str).unique())) + ")",
            "food_rescale": "JRC-IDEES-2023 country non-electric useful heat" if sub == "food-beverage-tobacco" else "",
            "useful_heat_twh": round(g["useful_heat_mwh"].sum() / 1e6, 2),
            "replaceable_heat_twh": round(g["replaceable_heat_mwh"].sum() / 1e6, 2),
        })
    out = pd.DataFrame(rows).sort_values(["subsector", "replaceable_heat_twh"], ascending=[True, False])
    out.to_csv(OUT, index=False)
    print(out[["subsector", "route", "facilities", "sec_gj_t", "eff", "replaceable_heat_twh"]].to_string(index=False))
    print("total replaceable TWh", round(out.replaceable_heat_twh.sum(), 1))


if __name__ == "__main__":
    main()
