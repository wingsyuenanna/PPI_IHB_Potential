"""Export 2024 pulp and paper facilities with annual output and site metadata."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    PROJECT_ROOT / "Input" / "pulp-and-paper_emissions_sources_v5_7_0.xlsm"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024.csv"
DEFAULT_EU_OUTPUT = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
SOURCE_SHEET = "pulp-and-paper_emissions_source"

# European Union member states (EU-27, ISO 3166-1 alpha-3).
EU_ISO3_COUNTRIES = {
    "AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA",
    "DEU", "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD",
    "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE",
}

SITE_COLUMNS = [
    "source_id",
    "source_name",
    "source_type",
    "iso3_country",
    "sector",
    "subsector",
    "lat",
    "lon",
    "gas",
    "activity_units",
    "capacity_units",
    "emissions_factor",
    "emissions_factor_units",
    "temporal_granularity",
]


def load_emissions_source(path: Path, sheet_name: str = SOURCE_SHEET) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, header=0, engine="openpyxl")


def export_facilities_2024(
    path: Path,
    year: int = 2024,
    sheet_name: str = SOURCE_SHEET,
    eu_only: bool = False,
) -> pd.DataFrame:
    """Return one row per facility for the requested year."""
    data = load_emissions_source(path, sheet_name=sheet_name)
    data["year"] = data["start_time"].dt.year
    year_data = data[data["year"] == year].copy()

    if year_data.empty:
        raise ValueError(f"No records found for year {year} in {path}")

    site_info = (
        year_data.groupby("source_id", as_index=False)
        .first()[SITE_COLUMNS]
    )

    annual_metrics = (
        year_data.groupby("source_id", as_index=False)
        .agg(
            year=("year", "first"),
            months_reported=("start_time", "count"),
            annual_output=("activity", "sum"),
            annual_emissions_co2e=("emissions_quantity", "sum"),
            avg_monthly_capacity=("capacity", "mean"),
            avg_capacity_factor=("capacity_factor", "mean"),
        )
    )

    facilities = site_info.merge(annual_metrics, on="source_id", how="inner")
    facilities = facilities.rename(
        columns={
            "annual_output": "annual_output_t",
            "annual_emissions_co2e": "annual_emissions_co2e_t",
            "avg_monthly_capacity": "avg_monthly_capacity_t",
        }
    )

    if eu_only:
        facilities = facilities[facilities["iso3_country"].isin(EU_ISO3_COUNTRIES)]

    return facilities.sort_values(["iso3_country", "source_name"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export pulp and paper facilities for a given year with annual output "
            "and site metadata from Climate TRACE emissions source data."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to the pulp-and-paper emissions source workbook.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the facilities CSV.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Calendar year to export.",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=SOURCE_SHEET,
        help="Worksheet name containing facility-level emissions source data.",
    )
    parser.add_argument(
        "--eu-only",
        action="store_true",
        help="Export only facilities in EU member states (EU-27).",
    )
    args = parser.parse_args()

    output = args.output
    if args.eu_only and output == DEFAULT_OUTPUT:
        output = DEFAULT_EU_OUTPUT

    facilities = export_facilities_2024(
        args.input,
        year=args.year,
        sheet_name=args.sheet,
        eu_only=args.eu_only,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    facilities.to_csv(output, index=False)

    region = "EU " if args.eu_only else ""
    print(f"Wrote {len(facilities)} {region}facilities for {args.year} to {output}")
    preview = facilities[
        [
            "source_name",
            "iso3_country",
            "source_type",
            "annual_output_t",
            "lat",
            "lon",
        ]
    ].head(10)
    print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
