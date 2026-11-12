"""Build the JRC-IDEES-2023 validation tables used by Supplementary Note 1.

Writes, in this folder:
  heat_by_country_comparison.csv      sector, cc, reference_twh, bottom_up_twh, coverage_pct
  heat_total_vs_fossil_by_sector.csv  sector, total_twh, fossil_twh, biomass_twh, fossil_pct

Reference = JRC-IDEES-2023 "Non-electric heat useful energy demand" per country
(References/jrc_idees/extracted/2023/industry_useful_energy_demand_<CC>.csv).
Bottom-up = this study's useful heat (all fuels) and replaceable (fossil) heat from
heat_demand/facilities/facilities_2024_eu_replaceable.csv, EU-27 facilities only
(non-EU countries such as GBR are excluded so both sides cover the same area).

Run after the heat pipeline, then conference_submissions/manuscript/figures/make_fig_validation.py.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF_DIR = ROOT / "References" / "jrc_idees" / "extracted" / "2023"
FACILITIES = ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_replaceable.csv"
OUT = Path(__file__).resolve().parent
REF_ROW = "Non-electric heat useful energy demand"

# Study subsector -> comparison sector
SECTOR_OF = {
    "cement": "Cement (+lime)", "lime": "Cement (+lime)",
    "chemicals": "Chemicals", "petrochemical-steam-cracking": "Chemicals",
    "food-beverage-tobacco": "Food, Bev & Tobacco",
    "glass": "Glass",
    "aluminum": "Non-ferrous Metals", "other-metals": "Non-ferrous Metals",
    "pulp-and-paper": "Pulp & Paper",
    "iron-and-steel": "Steel",
    "textiles-leather-apparel": "Textiles & Leather",
}
# Comparison sector -> JRC-IDEES columns
REF_COLS = {
    "Cement (+lime)": ["Cement (TWh)"],
    "Chemicals": ["Chemicals (TWh)"],
    "Food, Bev & Tobacco": ["Food, Beverages and Tobacco (TWh)"],
    "Glass": ["Ceramics and Glass (TWh)"],
    "Non-ferrous Metals": ["Non-ferrous Metals (TWh)"],
    "Pulp & Paper": ["Pulp and Paper (TWh)"],
    "Steel": ["Primary Steel (TWh)", "Secondary Steel (TWh)"],
    "Textiles & Leather": ["Textiles and Leather (TWh)"],
}
ISO3_TO_CC = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "CYP": "CY", "CZE": "CZ", "DEU": "DE",
    "DNK": "DK", "ESP": "ES", "EST": "EE", "FIN": "FI", "FRA": "FR", "GRC": "EL",
    "HRV": "HR", "HUN": "HU", "IRL": "IE", "ITA": "IT", "LTU": "LT", "LUX": "LU",
    "LVA": "LV", "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO",
    "SWE": "SE", "SVN": "SI", "SVK": "SK",
}


def reference() -> pd.DataFrame:
    rows = []
    for cc in ISO3_TO_CC.values():
        ref = pd.read_csv(REF_DIR / f"industry_useful_energy_demand_{cc}.csv", index_col=0)
        for sector, cols in REF_COLS.items():
            rows.append({"sector": sector, "cc": cc,
                         "reference_twh": float(ref.loc[REF_ROW, cols].sum())})
    return pd.DataFrame(rows)


def bottom_up() -> pd.DataFrame:
    d = pd.read_csv(FACILITIES, low_memory=False)
    d = d[d["iso3_country"].isin(ISO3_TO_CC) & d["subsector"].isin(SECTOR_OF)].copy()
    d["sector"] = d["subsector"].map(SECTOR_OF)
    d["cc"] = d["iso3_country"].map(ISO3_TO_CC)
    d["total_twh"] = d["useful_heat_mwh"].fillna(0) / 1e6
    d["fossil_twh"] = d["replaceable_heat_mwh"].fillna(0) / 1e6
    return d


def main() -> None:
    ref = reference()
    d = bottom_up()
    by_cc = d.groupby(["sector", "cc"])["total_twh"].sum().rename("bottom_up_twh")
    comp = ref.merge(by_cc.reset_index(), on=["sector", "cc"], how="left").fillna({"bottom_up_twh": 0.0})
    comp["coverage_pct"] = 100 * comp["bottom_up_twh"] / comp["reference_twh"].where(comp["reference_twh"] > 0)
    comp[["sector", "reference_twh", "cc", "bottom_up_twh", "coverage_pct"]].to_csv(
        OUT / "heat_by_country_comparison.csv", index=False)

    s = d.groupby("sector")[["total_twh", "fossil_twh"]].sum()
    s["biomass_twh"] = s["total_twh"] - s["fossil_twh"]
    s["fossil_pct"] = 100 * s["fossil_twh"] / s["total_twh"]
    s = s.sort_values("total_twh", ascending=False)
    s.loc["TOTAL"] = [s.total_twh.sum(), s.fossil_twh.sum(), s.biomass_twh.sum(),
                      100 * s.fossil_twh.sum() / s.total_twh.sum()]
    s.to_csv(OUT / "heat_total_vs_fossil_by_sector.csv", index_label="sector")
    print(s.round(1).to_string())


if __name__ == "__main__":
    main()
