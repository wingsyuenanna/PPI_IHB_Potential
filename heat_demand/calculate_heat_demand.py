"""Calculate facility heat demand and replaceable heat from classified EU facilities."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLASSIFICATION_INPUT = (
    PROJECT_ROOT / "Input" / "pulp_paper_fossil_classification.xlsx"
)
DEFAULT_FACILITIES_INPUT = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "heat_demand" / "heat_demand_by_facility.csv"

# Heat intensity values chosen in README (MWhth per tonne of output).
HEAT_INTENSITY_MWH_PER_T = {
    "Pulp": 4.0,
    "Integrated": 5.0,
    "Paper/Board": 1.3,
    "Tissue": 2.6,
}

NACE_TO_SECTOR = {
    "C1711": "C1711 — Pulp only",
    "C17xP": "C17_X_C1711 — Paper excl. pulp",
    "C17": "C17 — All paper & pulp",
}


def load_classified_facilities(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Facilities", header=1, engine="openpyxl")


def load_fossil_share_lookup(path: Path) -> pd.DataFrame:
    fossil_shares = pd.read_excel(
        path, sheet_name="Fossil_Shares", header=1, engine="openpyxl"
    )
    fossil_shares = fossil_shares.rename(
        columns={
            "Country": "eurostat_country",
            "Sector": "sector",
            "Fossil Share": "fossil_share_lookup",
        }
    )
    return fossil_shares[
        ["eurostat_country", "sector", "fossil_share_lookup", "Data Available"]
    ]


def fill_missing_production(
    facilities: pd.DataFrame, facilities_path: Path
) -> pd.DataFrame:
    if not facilities_path.exists():
        return facilities

    production_lookup = pd.read_csv(facilities_path)[
        ["source_id", "annual_output_t"]
    ].rename(columns={"annual_output_t": "annual_output_from_climate_trace"})

    facilities = facilities.merge(production_lookup, on="source_id", how="left")
    facilities["annual_output_t"] = facilities["annual_output_t"].fillna(
        facilities["annual_output_from_climate_trace"]
    )
    return facilities.drop(columns=["annual_output_from_climate_trace"])


def fill_missing_fossil_share(
    facilities: pd.DataFrame, fossil_share_lookup: pd.DataFrame
) -> pd.DataFrame:
    lookup_by_nace = (
        fossil_share_lookup.assign(
            nace_used=fossil_share_lookup["sector"].map(
                {v: k for k, v in NACE_TO_SECTOR.items()}
            )
        )
        .dropna(subset=["nace_used"])
        .drop_duplicates(subset=["eurostat_country", "nace_used"])
        [["eurostat_country", "nace_used", "fossil_share_lookup"]]
    )

    facilities = facilities.merge(
        lookup_by_nace,
        on=["eurostat_country", "nace_used"],
        how="left",
    )
    facilities["fossil_share_country"] = facilities["fossil_share_country"].fillna(
        facilities["fossil_share_lookup"]
    )
    return facilities.drop(columns=["fossil_share_lookup"])


def calculate_heat_demand(
    classification_path: Path,
    facilities_path: Path | None = DEFAULT_FACILITIES_INPUT,
) -> pd.DataFrame:
    """
    Compute annual heat demand and replaceable heat per facility.

    Heat_i = Production_i × Intensity_product
    Replaceable Heat_i = Heat_i × Fossil Share_country
    """
    facilities = load_classified_facilities(classification_path)
    fossil_share_lookup = load_fossil_share_lookup(classification_path)

    if facilities_path is not None:
        facilities = fill_missing_production(facilities, facilities_path)

    facilities = fill_missing_fossil_share(facilities, fossil_share_lookup)

    unknown_classes = set(facilities["classification"].dropna()) - set(
        HEAT_INTENSITY_MWH_PER_T
    )
    if unknown_classes:
        raise ValueError(f"Unmapped facility classifications: {unknown_classes}")

    facilities["heat_intensity_mwh_per_t"] = facilities["classification"].map(
        HEAT_INTENSITY_MWH_PER_T
    )
    facilities["heat_demand_mwh_th"] = (
        facilities["annual_output_t"] * facilities["heat_intensity_mwh_per_t"]
    )
    facilities["replaceable_heat_mwh_th"] = (
        facilities["heat_demand_mwh_th"] * facilities["fossil_share_country"]
    )

    output_columns = [
        "source_id",
        "source_name",
        "iso3_corrected",
        "country_corrected",
        "classification",
        "confidence",
        "nace_used",
        "annual_output_t",
        "heat_intensity_mwh_per_t",
        "fossil_share_country",
        "heat_demand_mwh_th",
        "replaceable_heat_mwh_th",
        "lat",
        "lon",
        "status_flag",
    ]
    return facilities[output_columns].sort_values(
        ["country_corrected", "source_name"]
    ).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate heat demand and replaceable heat for classified pulp and "
            "paper facilities using README heat intensities and country fossil shares."
        )
    )
    parser.add_argument(
        "--classification-input",
        type=Path,
        default=DEFAULT_CLASSIFICATION_INPUT,
        help="Path to pulp_paper_fossil_classification workbook.",
    )
    parser.add_argument(
        "--facilities-input",
        type=Path,
        default=DEFAULT_FACILITIES_INPUT,
        help="Path to Climate TRACE facilities CSV for missing production values.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write heat demand results CSV.",
    )
    parser.add_argument(
        "--no-facilities-fallback",
        action="store_true",
        help="Do not fill missing annual output from facilities_2024.csv.",
    )
    args = parser.parse_args()

    facilities_path = None if args.no_facilities_fallback else args.facilities_input
    result = calculate_heat_demand(
        args.classification_input,
        facilities_path=facilities_path,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    complete = result["replaceable_heat_mwh_th"].notna().sum()
    print(f"Wrote {len(result)} facilities to {args.output}")
    print(f"Replaceable heat calculated for {complete} facilities")
    preview = result[
        [
            "source_name",
            "classification",
            "annual_output_t",
            "heat_demand_mwh_th",
            "fossil_share_country",
            "replaceable_heat_mwh_th",
        ]
    ].head(10)
    print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
