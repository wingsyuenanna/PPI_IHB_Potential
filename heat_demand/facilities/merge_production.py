"""Build a merged EU facility production dataset from Climate TRACE and
Fraunhofer hotmaps (Industrial_Database_2014).

Source-selection rules, applied per facility to fill ``production_t``:
1. Climate TRACE capacity-derived output (annual_output_t) is the default.
2. Where the Climate TRACE value is a country-level artifact (the same
   annual_output_t duplicated across facilities within one country and
   subsector) and a high/medium-confidence hotmaps match reports 2014
   production, the hotmaps value replaces it.
3. Where Climate TRACE has no capacity at all (glass, food-beverage,
   textiles, other-metals), a high/medium-confidence hotmaps production
   fills the gap.
4. Low-confidence (location-only) matches are never used to fill.

Tier 3 — emissions-derived heat for the food industry: facilities with
no production in either source but reported CO2e get a process-heat
estimate by inverting combustion emissions to fuel energy
(Q = E_CO2 / fuel_EF, per estimating_heat_demand.md) and applying a
boiler efficiency. Only applied to sectors where emissions are ~100%
fuel combustion and heat is boiler-dominated (food-beverage-tobacco);
not valid for sectors with large process emissions (cement, lime) or
mixed routes (iron-and-steel).

``production_source`` records the provenance of every value
(climate_trace / hotmaps / none) and ``production_year`` its vintage
(2024 for Climate TRACE, 2014 for hotmaps) — mind the decade gap when
comparing across sources. ``data_tier`` is 1 (Climate TRACE production),
2 (hotmaps production), or 3 (emissions-derived heat only).
``ct_country_artifact`` flags facilities whose Climate TRACE output is a
duplicated country-level value that could not be replaced.

Run combine_hotmaps_2014.py first; this script consumes its output.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATCHED = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_matched_hotmaps_2014.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_merged.csv"
)
DEFAULT_XLSX = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_merged.xlsx"
)

FILL_CONFIDENCE = {"high", "medium"}

# Food heat is rescaled per country to the useful-energy reference: Climate
# TRACE food emissions are modeled and badly mis-allocated between countries
# (Portugal ~20x too high, Spain ~2.6x), so they serve only as within-country
# allocation weights. Reference = non-electric process heat + steam rows of
# References/industry_useful_energy_demand_<CC>.csv. Countries without a
# reference file (GBR) use the aggregate EU-26 factor.
FOOD_REF_DIR = PROJECT_ROOT / "References" / "industry_useful_energy_demand"
FOOD_REF_COLUMN = "Food, Beverages and Tobacco (TWh)"
FOOD_REF_HEAT_ROWS = [
    "Non-electric process heat (<100 C)",
    "Non-electric process heat (100-400 C)",
    "Non-electric process heat (400-1000 C)",
    "Non-electric process heat (>1000 C)",
    "Steam (non-electric boilers)",
]
ISO3_TO_REF_CC = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "CYP": "CY", "CZE": "CZ",
    "DEU": "DE", "DNK": "DK", "ESP": "ES", "EST": "EE", "FIN": "FI",
    "FRA": "FR", "GRC": "EL", "HRV": "HR", "HUN": "HU", "IRL": "IE",
    "ITA": "IT", "LTU": "LT", "LUX": "LU", "LVA": "LV", "NLD": "NL",
    "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI",
    "SWE": "SE",
}

TJ_TO_MWH = 1e6 / 3600  # 277.78 MWh per TJ

# All emission factors, SEC values, and their literature sources are
# documented in heat_demand/facilities/METHODS.md. Keep that file in sync
# with any change made here.

# Emissions-inversion parameters (heat_method = emissions_fuel_inversion),
# per subsector. Only valid where emissions are ~100% fuel combustion and
# heat is boiler-dominated. See METHODS.md section 3.
HEAT_ESTIMATE_PARAMS: dict[str, dict[str, float]] = {
    "food-beverage-tobacco": {
        # Level is superseded by the per-country rescaling below (Climate
        # TRACE food emissions only provide within-country allocation
        # weights), so the share is left at the physical 1.0. NOTE: because
        # each country's food heat is rescaled to the JRC reference, the EF
        # here is absorbed by the rescale and has no effect on food output.
        "combustion_share": 1.0,
        # 90% gas / 10% oil, matching the Eurostat nrg_d_indq energy-weighted
        # fossil mix for EU food & textiles (implied EF ~58-60, vs the earlier
        # 75/25 blend's 61.4 which is a few % too high for the gas-heavy mix).
        "fuel_ef_tco2_per_tj": 0.90 * 56.1 + 0.10 * 77.4,  # 58.2
        "boiler_efficiency": 0.85,
    },
    "textiles-leather-apparel": {
        "combustion_share": 1.0,
        "fuel_ef_tco2_per_tj": 0.90 * 56.1 + 0.10 * 77.4,  # 58.2
        "boiler_efficiency": 0.85,
    },
}

# SEC-based parameters (heat_method = production_sec), applied where a
# tier-1/2 production value exists: fuel_energy = production_t * sec / 1000,
# useful_heat = fuel_energy * eff.
# `sec` is FUEL INPUT for process heat (GJ per tonne of the product named by
# capacity_units); `eff` is the process's USEFUL THERMAL EFFICIENCY (useful
# heat delivered to the process / fuel input), taken from independent
# engineering literature — NOT from the JRC-IDEES / IndustryHeat-EU
# useful-energy reference we validate against, so the comparison stays
# non-circular. Earlier revisions used eff = 1.0 for direct-fired kilns
# (a fuel-accounting convention that reports fuel input, not the useful heat
# an electrified furnace must supply); each eff below is now a sourced
# furnace/boiler efficiency. Keyed by subsector, then source_type
# ("default" catches the rest). Full sources in METHODS.md section 4.
SEC_PARAMS: dict[str, dict[str, dict[str, float]]] = {
    # eff = cement pyroprocessing first-law efficiency; hot clinker, hot
    # calcination-CO2 exhaust and shell radiation are the losses. 0.60:
    # Madlool et al. 2011 (Renew. Sustain. Energy Rev. 15:2042) report
    # 50-60% kiln-system energy efficiency; consistent with BAT ~3.0 vs
    # theoretical ~1.8 GJ/t clinker (IEA Cement Roadmap).
    "cement": {"default": {"sec_gj_t": 2.8, "eff": 0.60}},  # t of cement
    # eff = lime kiln efficiency, EU mix of shaft (~0.80) and rotary (~0.55)
    # kilns; EU BREF Cement/Lime/MgO (typical 4-5 GJ/t vs theoretical ~3.2).
    "lime": {"default": {"sec_gj_t": 4.5, "eff": 0.65}},  # t of lime
    # eff = glass melting-furnace efficiency; large flue-gas + structural
    # losses. 0.45: Beerkens 2008 (energy benchmarking of glass furnaces);
    # Schmitz et al. 2011 (regenerative melting 40-50%).
    "glass": {"default": {"sec_gj_t": 6.5, "eff": 0.45}},  # t of glass
    "pulp-and-paper": {"default": {"sec_gj_t": 10.5, "eff": 0.85}},
    "petrochemical-steam-cracking": {
        # t of ethylene. 35.9 = total cracking-furnace duty (external fuel +
        # byproduct fuel-gas firing), the hotmaps benchmark ethylene SEC
        # (earlier 17.0 counted external fuel only, halving cracker heat and
        # understating the duty an electrified furnace must supply — the
        # byproduct methane/H2 tail gas is fossil-derived and must also be
        # decarbonized). eff = 0.90: a fired heater with strong convection-
        # section heat recovery (feed preheat + HP process steam), so the
        # useful fraction is high (Ren, Patel & Blok 2006, Energy 31:425;
        # Ullmann's "Ethylene"). Least-certain efficiency here — see METHODS.
        "default": {"sec_gj_t": 35.9, "eff": 0.90}
    },
    "iron-and-steel": {  # t of crude steel, by route
        # Final-consumption scope: coke ovens and blast furnaces are booked
        # in the Eurostat TRANSFORMATION sector, not iron & steel industry
        # final energy, so they are excluded here to match the top-down.
        # BF/BOF 4.8 = sinter 1.20 t x 2.24 GJ/t + rolled 0.90 t x 2.39 GJ/t
        # (hotmaps benchmarks); whole-route value incl. coke ovens + BF was
        # 19.0. Mixed routes are averages of the constituent routes.
        # eff = 0.70: reheating/sinter furnaces with recuperation, 65-75%
        # (IEA Iron & Steel Roadmap; worldsteel energy statistics).
        "BF/BOF": {"sec_gj_t": 4.8, "eff": 0.70},
        "BOF": {"sec_gj_t": 4.8, "eff": 0.70},
        "EAF": {"sec_gj_t": 2.5, "eff": 0.70},
        "DRI-EAF": {"sec_gj_t": 12.0, "eff": 0.70},
        "BOF,EAF": {"sec_gj_t": 3.7, "eff": 0.70},
        "DRI-EAF,BF/BOF": {"sec_gj_t": 8.4, "eff": 0.70},
        "default": {"sec_gj_t": 4.8, "eff": 0.70},
    },
    "chemicals": {  # t of chemical, by product
        # ammonia/methanol reformers are fired heaters with heat recovery,
        # eff 0.90 (as steam cracking); soda-ash is steam-boiler-led, 0.85.
        "ammonia": {"sec_gj_t": 9.0, "eff": 0.90},
        "soda_ash": {"sec_gj_t": 10.0, "eff": 0.85},
        "methanol": {"sec_gj_t": 9.0, "eff": 0.90},
    },
    "aluminum": {  # t of alumina (Refinery) / t of aluminum (Smelting)
        # Refinery = Bayer digestion/calcination steam (0.85 boiler); Smelting
        # = anode-bake + cast-house fired furnaces, eff 0.65 (IAI energy data).
        "Refinery": {"sec_gj_t": 11.0, "eff": 0.85},
        "Smelting": {"sec_gj_t": 3.0, "eff": 0.65},
    },
}

OUTPUT_COLUMNS = [
    "source_id",
    "source_name",
    "source_type",
    "iso3_country",
    "sector",
    "subsector",
    "lat",
    "lon",
    "year",
    "capacity_units",
    "annual_capacity_t",
    "capacity_factor",
    "annual_emissions_co2e_t",
    "production_t",
    "production_source",
    "production_year",
    "data_tier",
    "fuel_energy_tj",
    "useful_heat_tj",
    "useful_heat_mwh",
    "heat_method",
    "food_country_scale",
    "ct_country_artifact",
    # hotmaps match context for auditing
    "SiteID",
    "SiteName",
    "CompanyName",
    "match_confidence",
    "distance_km",
    "name_similarity",
    "annual_output_t",
    "production_2014_t",
]


def flag_country_artifacts(matched: pd.DataFrame) -> pd.Series:
    """True where annual_output_t repeats within a country+subsector group."""
    has_output = matched["annual_output_t"].notna()
    duplicated = (
        matched.loc[has_output]
        .groupby(["iso3_country", "subsector"])["annual_output_t"]
        .transform(lambda s: s.duplicated(keep=False))
    )
    return duplicated.reindex(matched.index, fill_value=False)


def merge_production(matched: pd.DataFrame) -> pd.DataFrame:
    merged = matched.copy()

    artifact = flag_country_artifacts(merged)
    hotmaps_usable = merged["production_2014_t"].gt(0) & merged[
        "match_confidence"
    ].isin(FILL_CONFIDENCE)
    ct_usable = merged["annual_output_t"].notna()

    use_hotmaps = hotmaps_usable & (~ct_usable | artifact)
    use_ct = ct_usable & ~use_hotmaps

    merged["production_t"] = np.select(
        [use_hotmaps, use_ct],
        [merged["production_2014_t"], merged["annual_output_t"]],
        default=np.nan,
    )
    merged["production_source"] = np.select(
        [use_hotmaps, use_ct], ["hotmaps", "climate_trace"], default="none"
    )
    merged["production_year"] = np.select(
        [use_hotmaps, use_ct], [2014, 2024], default=pd.NA
    )
    # Artifact values that survive because hotmaps had nothing better.
    merged["ct_country_artifact"] = artifact & use_ct

    merged = estimate_heat_from_emissions(merged)
    merged["data_tier"] = np.select(
        [use_ct, use_hotmaps, merged["heat_method"].notna()],
        [1, 2, 3],
        default=pd.NA,
    )
    return merged[OUTPUT_COLUMNS]


def estimate_heat_from_emissions(merged: pd.DataFrame) -> pd.DataFrame:
    """Fill fuel_energy / useful_heat for every facility that allows it.

    Production-covered facilities (tiers 1-2) get production_t * SEC
    (heat_method = production_sec). Facilities without production in
    subsectors where emissions are all combustion get the CO2e inversion
    (heat_method = emissions_fuel_inversion), so the two methods never
    overlap.
    """
    merged["fuel_energy_tj"] = np.nan
    merged["useful_heat_tj"] = np.nan
    merged["heat_method"] = pd.NA

    # SEC route: fuel input for heat per tonne of product.
    for subsector, by_type in SEC_PARAMS.items():
        for m_idx in merged.index[
            (merged["subsector"] == subsector) & merged["production_t"].gt(0)
        ]:
            params = by_type.get(merged.at[m_idx, "source_type"]) or by_type.get(
                "default"
            )
            if params is None:
                continue
            fuel_tj = merged.at[m_idx, "production_t"] * params["sec_gj_t"] / 1000
            merged.at[m_idx, "fuel_energy_tj"] = fuel_tj
            merged.at[m_idx, "useful_heat_tj"] = fuel_tj * params["eff"]
            merged.at[m_idx, "heat_method"] = "production_sec"

    # Emissions-inversion route for facilities without production.
    for subsector, params in HEAT_ESTIMATE_PARAMS.items():
        rows = (
            (merged["subsector"] == subsector)
            & (merged["production_source"] == "none")
            & merged["annual_emissions_co2e_t"].gt(0)
        )
        combustion_co2e = (
            merged.loc[rows, "annual_emissions_co2e_t"] * params["combustion_share"]
        )
        fuel_tj = combustion_co2e / params["fuel_ef_tco2_per_tj"]
        merged.loc[rows, "fuel_energy_tj"] = fuel_tj
        merged.loc[rows, "useful_heat_tj"] = fuel_tj * params["boiler_efficiency"]
        merged.loc[rows, "heat_method"] = "emissions_fuel_inversion"

    merged = rescale_food_to_country_reference(merged)
    merged["useful_heat_mwh"] = merged["useful_heat_tj"] * TJ_TO_MWH
    return merged


def food_reference_heat_tj(cc: str) -> float | None:
    """Country food heat (TJ) from the useful-energy reference, or None."""
    path = FOOD_REF_DIR / f"industry_useful_energy_demand_{cc}.csv"
    if not path.exists():
        return None
    ref = pd.read_csv(path)
    heat_twh = ref.loc[
        ref["energy_demand_type"].isin(FOOD_REF_HEAT_ROWS), FOOD_REF_COLUMN
    ].sum()
    return float(heat_twh) * 3600.0


def rescale_food_to_country_reference(merged: pd.DataFrame) -> pd.DataFrame:
    """Scale food heat so each country total matches the reference.

    Climate TRACE food emissions keep only their within-country allocation
    role; the level comes from the useful-energy reference (see the
    FOOD_REF_DIR comment and METHODS.md section 3). The applied factor is
    recorded in `food_country_scale`.
    """
    food = (merged["subsector"] == "food-beverage-tobacco") & merged[
        "useful_heat_tj"
    ].gt(0)
    merged["food_country_scale"] = np.nan

    target_total_tj = 0.0
    original_total_tj = 0.0
    for iso3, group in merged[food].groupby("iso3_country"):
        cc = ISO3_TO_REF_CC.get(str(iso3))
        ref_tj = food_reference_heat_tj(cc) if cc else None
        if ref_tj is None:
            continue
        original_tj = group["useful_heat_tj"].sum()
        factor = ref_tj / original_tj
        idx = group.index
        merged.loc[idx, ["fuel_energy_tj", "useful_heat_tj"]] *= factor
        merged.loc[idx, "food_country_scale"] = factor
        target_total_tj += ref_tj
        original_total_tj += original_tj

    # Countries without a reference file (GBR): EU-26 aggregate factor.
    if original_total_tj > 0:
        eu_factor = target_total_tj / original_total_tj
        rest = food & merged["food_country_scale"].isna()
        merged.loc[rest, ["fuel_energy_tj", "useful_heat_tj"]] *= eu_factor
        merged.loc[rest, "food_country_scale"] = eu_factor
    return merged


def summarize(merged: pd.DataFrame) -> None:
    print("production_source by subsector:")
    print(
        merged.pivot_table(
            index="subsector",
            columns="production_source",
            values="source_id",
            aggfunc="count",
            fill_value=0,
        ).to_string()
    )
    covered = (merged["production_source"] != "none").sum()
    print(f"\nFacilities with production: {covered} of {len(merged)}")
    replaced = (merged["production_source"] == "hotmaps").sum()
    print(f"Values taken from hotmaps 2014: {replaced}")
    print(
        "Remaining country-artifact values (flagged): "
        f"{int(merged['ct_country_artifact'].sum())}"
    )

    with_heat = merged[merged["heat_method"].notna()]
    print(
        f"\nFacilities with heat estimate: {len(with_heat)} of {len(merged)}, "
        f"total useful heat {with_heat['useful_heat_mwh'].sum() / 1e6:.1f} TWh/yr"
    )
    print("\nUseful heat (TWh/yr) by subsector and method:")
    print(
        (
            with_heat.pivot_table(
                index="subsector",
                columns="heat_method",
                values="useful_heat_mwh",
                aggfunc="sum",
                fill_value=0,
            )
            / 1e6
        )
        .round(1)
        .to_string()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Climate TRACE and hotmaps production into one dataset."
    )
    parser.add_argument("--matched", type=Path, default=DEFAULT_MATCHED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()

    matched = pd.read_csv(args.matched)
    merged = merge_production(matched)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False)
    merged.to_excel(args.xlsx, sheet_name="Facilities", index=False)
    print(f"Wrote {len(merged)} facilities to {args.output}")
    print(f"Wrote spreadsheet to {args.xlsx}\n")
    summarize(merged)


if __name__ == "__main__":
    main()
