"""Compute fossil share of industrial process fuel by Climate TRACE subsector.

Source data (both in Input/):
  - nrg_d_indq_n__custom_22120962_linear_2_0.csv
      Eurostat "Disaggregated final energy consumption in industry by NACE Rev.2
      activity - quantities" (2024, TJ). Dimensions: siec (energy carrier),
      nace_r2 (industry), geo (country), OBS_VALUE.
  - eprtr_nace_mapping.csv
      E-PRTR activity -> NACE crosswalk (documents which NACE division/class each
      regulated industrial activity sits in; used here to justify the CT->NACE map).

Fossil share (per country x subsector) is the fossil fraction of COMBUSTION fuel:

    fossil_share = fossil_fuel / (fossil_fuel + biomass_renewable_fuel)

Electricity (E7000) and derived/purchased heat (H8000) are excluded from both
numerator and denominator: the facility `useful_heat` this multiplies is itself
combustion-derived (from emissions / fuel SEC), so the ratio must be over
combustion fuels only. Biomass / black liquor / renewable waste sit in the
denominator but not the numerator -> they are correctly treated as NOT
replaceable-by-battery targets.

Output: fossil_share_by_subsector.csv (country x CT subsector) and the EU-27
aggregate row per subsector (geo = "EU27").
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ENERGY_CSV = ROOT / "Input" / "nrg_d_indq_n__custom_22120962_linear_2_0.csv"
OUTPUT_CSV = Path(__file__).resolve().parent / "fossil_share_by_subsector.csv"

UNIT = "TJ_NCV"  # net calorific value; the comprehensive (granular) unit here

# Climate TRACE subsector -> Eurostat NACE Rev.2 code present in nrg_d_indq.
# Cross-checked against Input/eprtr_nace_mapping.csv.
CT_TO_NACE = {
    "food-beverage-tobacco": "C10-C12",
    "textiles-leather-apparel": "C13-C15",
    "pulp-and-paper": "C17",  # C1711 (pulp only) available for a pulp-specific cut
    "glass": "C231",
    "cement": "C235",  # C235 = cement, lime & plaster combined (not separable)
    "lime": "C235",    # shares C235 with cement
    "chemicals": "C20",           # C201 (basic chemicals) is sparse/confidential
    "petrochemical-steam-cracking": "C20",  # crackers sit in C20; not separable
    "iron-and-steel": "C241-C243_C2451_C2452",
    "aluminum": "C2442",
    "other-metals": "C244_X_C2442",
}

# Non-overlapping SIEC partition (validated to sum to TOTAL within ~2% for EU-27).
# Aggregate level so coke-oven/BF gas fall inside "gas", renewable waste inside RA000.
FOSSIL_SIEC = [
    "C0000X0350-0370",  # solid fossil fuels (coal, lignite, coke, ...)
    "G3000_C0350-370",  # gas = natural gas + manufactured gases (coke-oven, BF gas)
    "O4000",            # oil and petroleum products
    "P1100", "P1200",   # peat and peat products (fossil-like)
    "S2000",            # oil shale / oil sands
    "W6100_6220",       # non-renewable waste
]
BIOMASS_SIEC = ["RA000"]  # renewables & biofuels (incl. renewable waste)

EU27 = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
    "SE", "SI", "SK",
}


def load_energy() -> pd.DataFrame:
    df = pd.read_csv(ENERGY_CSV)
    df = df[df["unit"] == UNIT].copy()
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce").fillna(0.0)
    return df[["siec", "nace_r2", "geo", "OBS_VALUE"]]


def fossil_share_by_nace(df: pd.DataFrame) -> pd.DataFrame:
    """Return per (geo, nace_r2): fossil_tj, biomass_tj, total_tj, fossil_share.

    `reliable` is False where the country did not report a disaggregated TOTAL for
    the NACE (TOTAL <= 0) — in those slices the biomass carrier is typically
    suppressed for confidentiality, which spuriously inflates fossil_share toward
    1.0 (e.g. Sweden pulp & paper). Such slices fall back to the EU-27 value.
    """
    fossil = (
        df[df["siec"].isin(FOSSIL_SIEC)]
        .groupby(["geo", "nace_r2"])["OBS_VALUE"].sum().rename("fossil_tj")
    )
    biomass = (
        df[df["siec"].isin(BIOMASS_SIEC)]
        .groupby(["geo", "nace_r2"])["OBS_VALUE"].sum().rename("biomass_tj")
    )
    total = (
        df[df["siec"] == "TOTAL"]
        .groupby(["geo", "nace_r2"])["OBS_VALUE"].sum().rename("total_tj")
    )
    out = pd.concat([fossil, biomass, total], axis=1).fillna(0.0).reset_index()
    denom = out["fossil_tj"] + out["biomass_tj"]
    out["reliable"] = (out["total_tj"] > 0) & (denom > 0)
    out["fossil_share"] = out["fossil_tj"].where(denom > 0) / denom.where(denom > 0)
    return out


def build() -> pd.DataFrame:
    df = load_energy()
    by_nace = fossil_share_by_nace(df)

    # EU-27 aggregate rows (sum fuel across EU-27, then divide) — robust to
    # small-country confidential gaps.
    eu = df[df["geo"].isin(EU27)].copy()
    eu["geo"] = "EU27"
    by_nace_eu = fossil_share_by_nace(eu)
    by_nace = pd.concat([by_nace, by_nace_eu], ignore_index=True)

    rows = []
    for subsector, nace in CT_TO_NACE.items():
        sel = by_nace[by_nace["nace_r2"] == nace].copy()
        sel.insert(0, "subsector", subsector)
        sel["nace_r2"] = nace
        rows.append(sel)
    result = pd.concat(rows, ignore_index=True)

    # EU-27 fallback: unreliable country slices (suppressed data) inherit the
    # robust EU-27 aggregate share for their subsector.
    eu_share = (
        result[result["geo"] == "EU27"]
        .set_index("subsector")["fossil_share"]
    )
    result["fossil_share_eu27"] = result["subsector"].map(eu_share)
    result["fossil_share_final"] = result["fossil_share"].where(
        result["reliable"], result["fossil_share_eu27"]
    )
    # EU-27 rows are the reference; keep their own value as final.
    is_eu = result["geo"] == "EU27"
    result.loc[is_eu, "fossil_share_final"] = result.loc[is_eu, "fossil_share"]
    result.loc[is_eu, "reliable"] = True

    return result[
        [
            "subsector", "nace_r2", "geo", "fossil_tj", "biomass_tj",
            "reliable", "fossil_share", "fossil_share_eu27", "fossil_share_final",
        ]
    ].sort_values(["subsector", "geo"]).reset_index(drop=True)


def main() -> None:
    result = build()
    result.to_csv(OUTPUT_CSV, index=False)
    eu = result[result["geo"] == "EU27"][["subsector", "fossil_share_final"]]
    n_unreliable = (~result["reliable"]).sum()
    print(f"Wrote {len(result)} rows to {OUTPUT_CSV.name}")
    print(f"Country slices using EU-27 fallback (suppressed data): {n_unreliable}")
    print("\nEU-27 fossil share by Climate TRACE subsector:")
    print(eu.to_string(index=False, float_format=lambda x: f"{x:0.2f}"))


if __name__ == "__main__":
    main()
