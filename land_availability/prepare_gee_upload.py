"""Prepare EU facility points CSV for upload as a Google Earth Engine asset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACILITIES = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "Input" / "facilities_2024_eu_gee_upload.csv"


def export_gee_upload_csv(facilities_path: Path) -> pd.DataFrame:
    facilities = pd.read_csv(facilities_path)
    required = ["source_id", "source_name", "lat", "lon", "iso3_country"]
    missing = [col for col in required if col not in facilities.columns]
    if missing:
        raise ValueError(f"Facilities file missing columns: {missing}")

    upload = facilities[required].dropna(subset=["lat", "lon"]).copy()
    upload = upload.rename(columns={"iso3_country": "country_iso3"})
    return upload.sort_values(["country_iso3", "source_name"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export facility points for upload to Google Earth Engine as an asset."
    )
    parser.add_argument(
        "--facilities",
        type=Path,
        default=DEFAULT_FACILITIES,
        help="EU facilities CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="CSV to upload in GEE Console (Assets > New > Table upload)",
    )
    args = parser.parse_args()

    upload = export_gee_upload_csv(args.facilities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    upload.to_csv(args.output, index=False)
    print(f"Wrote {len(upload)} facility points to {args.output}")
    print("Upload this file in GEE Console, then pass the asset id to land_availability/gee_facility_calculate_available_area.py")


if __name__ == "__main__":
    main()
