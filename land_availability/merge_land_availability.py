"""Process GEE land-cover export into a standalone land-availability dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAND_EXPORT = PROJECT_ROOT / "Input" / "LandCover_Area_Categorized_5km.csv"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "land_availability" / "outputs" / "land_availability_by_facility.csv"
)
DEFAULT_FACILITIES = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"

# Colocated solar: bare land and cropland only (exclude built-up — roofs/roads are not array siting).
AVAILABLE_LAND_COLUMNS = [
    "bare_sparse_km2",
    "cropland_km2",
]


def load_land_export(path: Path) -> pd.DataFrame:
    land = pd.read_csv(path)
    land["source_id"] = pd.to_numeric(land["source_id"], errors="coerce").astype("Int64")
    return land


def process_land_export(
    land_export_path: Path,
    facilities_path: Path | None = DEFAULT_FACILITIES,
) -> pd.DataFrame:
    land = summarize_available_land(load_land_export(land_export_path))

    id_columns = ["source_id"]
    if "source_name" in land.columns:
        id_columns.append("source_name")

    land_columns = (
        id_columns
        + AVAILABLE_LAND_COLUMNS
        + ["available_land_km2"]
        + [
            c
            for c in land.columns
            if c.endswith("_km2")
            and c not in AVAILABLE_LAND_COLUMNS
            and c != "available_land_km2"
        ]
    )
    result = land[land_columns].drop_duplicates(subset=["source_id"])

    if facilities_path is not None and facilities_path.exists():
        facilities = pd.read_csv(facilities_path)[["source_id", "source_name", "iso3_country", "lat", "lon"]]
        result = facilities.merge(result, on="source_id", how="left", suffixes=("", "_land"))
        if "source_name_land" in result.columns:
            result = result.drop(columns=["source_name_land"])

    return result.sort_values(["iso3_country", "source_name"], na_position="last").reset_index(drop=True)


def summarize_available_land(land: pd.DataFrame) -> pd.DataFrame:
    land = land.copy()
    for column in AVAILABLE_LAND_COLUMNS:
        if column not in land.columns:
            land[column] = 0.0
        land[column] = pd.to_numeric(land[column], errors="coerce").fillna(0.0)

    land["available_land_km2"] = land[AVAILABLE_LAND_COLUMNS].sum(axis=1)
    return land


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Process a downloaded GEE land-cover CSV into a standalone "
            "land_availability_by_facility.csv. "
            "available_land_km2 = bare_sparse + cropland."
        )
    )
    parser.add_argument(
        "--land-export",
        type=Path,
        default=DEFAULT_LAND_EXPORT,
        help="Downloaded GEE Drive CSV (LandCover_Area_Categorized_<buffer>km.csv)",
    )
    parser.add_argument(
        "--facilities",
        type=Path,
        default=DEFAULT_FACILITIES,
        help="EU facilities CSV used to attach site metadata (optional).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Standalone land availability output CSV",
    )
    parser.add_argument(
        "--no-facilities-metadata",
        action="store_true",
        help="Do not join source_name/country/lat/lon from facilities CSV.",
    )
    args = parser.parse_args()

    if not args.land_export.exists():
        raise FileNotFoundError(
            f"Land export not found: {args.land_export}\n"
            "Download the CSV from Google Drive after the GEE task completes."
        )

    facilities_path = None if args.no_facilities_metadata else args.facilities
    result = process_land_export(args.land_export, facilities_path=facilities_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    matched = result["available_land_km2"].notna().sum()
    print(f"Wrote {len(result)} rows to {args.output}")
    print(f"Land data available for {matched} facilities")
    preview_cols = [
        c
        for c in ["source_name", "iso3_country", "available_land_km2", "bare_sparse_km2", "cropland_km2"]
        if c in result.columns
    ]
    print(result[preview_cols].dropna(subset=["available_land_km2"]).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
