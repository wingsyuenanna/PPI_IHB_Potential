"""Export facility data from Climate TRACE and sync annual output into the heat demand workbook."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "Input" / "pulp-and-paper_emissions_sources_v5_7_0.xlsm"
DEFAULT_OUTPUT = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
DEFAULT_WORKBOOK = (
    PROJECT_ROOT / "heat_demand" / "pulp_paper_heat_demand_corrected.xlsx"
)
SOURCE_SHEET = "pulp-and-paper_emissions_source"
FACILITIES_SHEET = "Facilities"
ANNUAL_OUTPUT_COLUMN = 6  # column F: annual_output_t
HEADER_ROW = 2
DATA_START_ROW = 3

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
    eu_only: bool = True,
) -> pd.DataFrame:
    """Return one row per facility for the requested year."""
    data = load_emissions_source(path, sheet_name=sheet_name)
    data["year"] = data["start_time"].dt.year
    year_data = data[data["year"] == year].copy()

    if year_data.empty:
        raise ValueError(f"No records found for year {year} in {path}")

    site_info = year_data.groupby("source_id", as_index=False).first()[SITE_COLUMNS]
    annual_metrics = (
        year_data.groupby("source_id", as_index=False)
        .agg(
            year=("year", "first"),
            months_reported=("start_time", "count"),
            annual_output=("activity", "sum"),
            annual_emissions_co2e=("emissions_quantity", "sum"),
            annual_capacity=("capacity", "sum"),
            capacity_factor=("capacity_factor", "first"),
        )
    )

    facilities = site_info.merge(annual_metrics, on="source_id", how="inner")
    facilities = facilities.rename(
        columns={
            "annual_output": "annual_output_t",
            "annual_emissions_co2e": "annual_emissions_co2e_t",
            "annual_capacity": "annual_capacity_t",
        }
    )

    if eu_only:
        facilities = facilities[facilities["iso3_country"].isin(EU_ISO3_COUNTRIES)]

    return facilities.sort_values(["iso3_country", "source_name"]).reset_index(drop=True)


def sync_annual_output_to_workbook(
    workbook_path: Path,
    facilities: pd.DataFrame,
    sheet_name: str = FACILITIES_SHEET,
) -> tuple[int, int, list[int]]:
    """
    Write annual_output_t into the Facilities sheet by source_id.

    Returns (rows_updated, rows_missing_output, source_ids_not_in_workbook).
    """
    output_by_id = dict(
        zip(facilities["source_id"], facilities["annual_output_t"], strict=False)
    )
    workbook = load_workbook(workbook_path)
    worksheet = workbook[sheet_name]

    updated = 0
    missing_output: list[int] = []
    not_in_workbook: list[int] = []

    workbook_ids: set[int] = set()
    for row in range(DATA_START_ROW, worksheet.max_row + 1):
        source_id = worksheet.cell(row, 1).value
        if source_id is None or str(source_id).strip() == "":
            continue
        source_id = int(source_id)
        workbook_ids.add(source_id)

        if source_id not in output_by_id:
            continue

        annual_output = output_by_id[source_id]
        if pd.isna(annual_output):
            missing_output.append(source_id)
            continue

        worksheet.cell(row, ANNUAL_OUTPUT_COLUMN).value = float(annual_output)
        updated += 1

    for source_id in output_by_id:
        if source_id not in workbook_ids:
            not_in_workbook.append(source_id)

    workbook.save(workbook_path)
    return updated, len(missing_output), not_in_workbook


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export EU pulp-and-paper facilities from Climate TRACE and optionally "
            "sync annual_output_t into pulp_paper_heat_demand_corrected.xlsx."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to the Climate TRACE emissions source workbook.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the EU facilities CSV.",
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=DEFAULT_WORKBOOK,
        help="Path to the formula-driven heat demand workbook.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Calendar year to export.",
    )
    parser.add_argument(
        "--no-sync-workbook",
        action="store_true",
        help="Export CSV only; do not update the heat demand workbook.",
    )
    args = parser.parse_args()

    facilities = export_facilities_2024(args.input, year=args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    facilities.to_csv(args.output, index=False)
    print(f"Wrote {len(facilities)} EU facilities to {args.output}")

    if not args.no_sync_workbook:
        if not args.workbook.exists():
            raise FileNotFoundError(f"Workbook not found: {args.workbook}")

        updated, missing, not_in_wb = sync_annual_output_to_workbook(
            args.workbook, facilities
        )
        print(
            f"Updated annual_output_t for {updated} facilities in {args.workbook.name}"
        )
        if missing:
            print(f"Skipped {missing} facilities with missing annual output")
        if not_in_wb:
            print(
                f"Note: {len(not_in_wb)} exported facilities are not in the workbook "
                f"(e.g. {not_in_wb[:5]})"
            )
        print("Open the workbook to view formula-driven heat demand results.")


if __name__ == "__main__":
    main()
