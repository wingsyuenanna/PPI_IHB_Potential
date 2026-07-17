"""Apply subsector x country fossil share to facility useful heat.

Reads the facility heat table and the fossil-share lookup, joins on
(country, Climate TRACE subsector), and adds:

    fossil_share            fossil fraction used (country value or EU-27 fallback)
    fossil_share_basis      "country" | "eu27_fallback"
    replaceable_heat_mwh    useful_heat_mwh * fossil_share
        = the process heat that is fossil-fired today and therefore a target for
          electrified heat batteries (biomass / black-liquor heat excluded).

This is the FLAT (subsector-level) application. A temperature-band-resolved
version would additionally multiply by fossil_share_by_band.csv per band; left
out here by choice — the flat share is the data-driven, validated layer.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FACILITIES = ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_deduplicated.csv"
FOSSIL = Path(__file__).resolve().parent / "fossil_share_by_subsector.csv"
OUTPUT = ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_replaceable.csv"

# Facility ISO3 -> Eurostat geo (2-letter; note EL for Greece). GBR/UK is absent
# from nrg_d_indq, so it resolves to the EU-27 fallback.
ISO3_TO_GEO = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "CYP": "CY", "CZE": "CZ", "DEU": "DE",
    "DNK": "DK", "ESP": "ES", "EST": "EE", "FIN": "FI", "FRA": "FR", "GRC": "EL",
    "HRV": "HR", "HUN": "HU", "IRL": "IE", "ITA": "IT", "LTU": "LT", "LUX": "LU",
    "LVA": "LV", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
    "SVN": "SI", "SWE": "SE",
}


def main() -> None:
    fac = pd.read_csv(FACILITIES, low_memory=False)
    fs = pd.read_csv(FOSSIL)

    country = fs[fs["geo"] != "EU27"].set_index(["geo", "subsector"])["fossil_share_final"]
    eu27 = fs[fs["geo"] == "EU27"].set_index("subsector")["fossil_share_final"]

    geo = fac["iso3_country"].map(ISO3_TO_GEO)
    country_val = pd.Series(
        list(zip(geo, fac["subsector"])), index=fac.index
    ).map(country)
    eu_val = fac["subsector"].map(eu27)

    fac["fossil_share"] = country_val.fillna(eu_val)
    fac["fossil_share_basis"] = country_val.notna().map(
        {True: "country", False: "eu27_fallback"}
    )
    fac["replaceable_heat_mwh"] = fac["useful_heat_mwh"] * fac["fossil_share"]

    fac.to_csv(OUTPUT, index=False)

    total_useful = fac["useful_heat_mwh"].sum() / 1e6
    total_repl = fac["replaceable_heat_mwh"].sum() / 1e6
    print(f"Wrote {len(fac)} facilities to {OUTPUT.name}")
    print(f"Total useful heat:       {total_useful:8.1f} TWh")
    print(f"Total replaceable heat:  {total_repl:8.1f} TWh "
          f"({100*total_repl/total_useful:.0f}% of useful)")
    print(f"EU-27 fallback used for: {(fac['fossil_share_basis']=='eu27_fallback').sum()} facilities")
    print("\nBy subsector (TWh):")
    g = fac.groupby("subsector").agg(
        useful=("useful_heat_mwh", "sum"), repl=("replaceable_heat_mwh", "sum")
    ) / 1e6
    g["fossil_%"] = (100 * g["repl"] / g["useful"]).round(0)
    print(g.round(1).to_string())


if __name__ == "__main__":
    main()
