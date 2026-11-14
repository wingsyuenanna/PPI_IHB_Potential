"""Prepare EU facility points CSV for upload as a Google Earth Engine asset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACILITIES = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "Input" / "facilities_2024_eu_gee_upload.csv"
# Heat-weighted land allocation (all facilities decarbonise together): only facilities
# with a replaceable heat estimate are uploaded, each with its heat as the weight.
HEAT_FACILITIES = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_replaceable.csv"
HEAT_OUTPUT = PROJECT_ROOT / "Input" / "facilities_2024_eu_gee_upload_heat.csv"
HEAT_COLUMN = "replaceable_heat_mwh"
WEIGHT_NAME = "heat_mwh"


def export_gee_upload_csv(facilities_path: Path, with_heat: bool = False) -> pd.DataFrame:
    facilities = pd.read_csv(facilities_path)
    required = ["source_id", "source_name", "lat", "lon", "iso3_country"]
    if with_heat:
        required = required + [HEAT_COLUMN]
    missing = [col for col in required if col not in facilities.columns]
    if missing:
        raise ValueError(f"Facilities file missing columns: {missing}")

    upload = facilities[required].dropna(subset=["lat", "lon"]).copy()
    if with_heat:
        upload = upload[upload[HEAT_COLUMN].fillna(0) > 0].rename(columns={HEAT_COLUMN: WEIGHT_NAME})
    upload = upload.rename(columns={"iso3_country": "country_iso3"})
    # Collapse embedded newlines/CR and runs of whitespace in names; GEE CSV
    # ingestion treats an embedded newline as a row break and rejects the file.
    upload["source_name"] = (
        upload["source_name"]
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    return upload.sort_values(["country_iso3", "source_name"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export facility points for upload to Google Earth Engine as an asset."
    )
    parser.add_argument(
        "--facilities",
        type=Path,
        default=None,
        help=f"EU facilities CSV (default: {DEFAULT_FACILITIES.name}, or {HEAT_FACILITIES.name} with --with-heat)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="CSV to upload in GEE Console (Assets > New > Table upload)",
    )
    parser.add_argument(
        "--with-heat",
        action="store_true",
        help=f"Keep only facilities with replaceable heat and add a '{WEIGHT_NAME}' weight column "
        "for heat-weighted land allocation.",
    )
    args = parser.parse_args()
    if args.facilities is None:
        args.facilities = HEAT_FACILITIES if args.with_heat else DEFAULT_FACILITIES
    if args.output is None:
        args.output = HEAT_OUTPUT if args.with_heat else DEFAULT_OUTPUT

    upload = export_gee_upload_csv(args.facilities, with_heat=args.with_heat)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    upload.to_csv(args.output, index=False)
    print(f"Wrote {len(upload)} facility points to {args.output}")
    print("Upload this file in GEE Console, then pass the asset id to land_availability/gee_facility_calculate_available_area.py")


if __name__ == "__main__":
    main()
