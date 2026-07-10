"""Merge EU facility, heat demand, land availability, and solar resource inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FACILITIES = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
DEFAULT_WORKBOOK = PROJECT_ROOT / "heat_demand" / "pulp_paper_heat_demand_corrected.xlsx"
DEFAULT_FOSSIL_LOOKUP = PROJECT_ROOT / "heat_demand" / "fossil_share" / "fossil_share_lookup.csv"
DEFAULT_LAND = (
    PROJECT_ROOT / "land_availability" / "outputs" / "land_availability_by_facility.csv"
)
DEFAULT_SOLAR = (
    PROJECT_ROOT / "solar_radiation" / "outputs" / "solar_radiation_by_facility.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "outputs"
    / "eu_pulp_paper_ihb_site_assessment_2024.csv"
)

LAND_COLUMNS = [
    "bare_sparse_km2",
    "cropland_km2",
    "available_land_km2",
    "tree_cover_km2",
    "shrubland_km2",
    "grassland_km2",
    "built_up_km2",
    "snow_ice_km2",
    "water_km2",
    "wetland_km2",
    "mangroves_km2",
    "moss_lichen_km2",
]

SOLAR_COLUMNS = [
    "solar_year",
    "annual_yield_kwh_per_kwp",
    "solar_capacity_factor",
    "pvgis_raddatabase",
    "tilt_deg",
    "azimuth_deg",
    "system_loss_pct",
]


def load_workbook_parameters(workbook_path: Path) -> dict:
    params = pd.read_excel(workbook_path, sheet_name="Parameters", header=None)
    sec = dict(zip(params.iloc[4:8, 0], params.iloc[4:8, 1], strict=False))
    eu27_fallback = dict(zip(params.iloc[11:14, 0], params.iloc[11:14, 1], strict=False))
    replace_frac = dict(zip(params.iloc[17:21, 0], params.iloc[17:21, 1], strict=False))
    return {
        "sec_mwh_per_t": {str(k): float(v) for k, v in sec.items()},
        "eu27_fallback_share": {str(k): float(v) for k, v in eu27_fallback.items()},
        "replace_frac": {str(k): float(v) for k, v in replace_frac.items()},
    }


def resolve_fossil_share(
    lookup_key: str,
    nace_used: str,
    fossil_lookup: pd.DataFrame,
    eu27_fallback: dict[str, float],
) -> tuple[float | None, str]:
    match = fossil_lookup[fossil_lookup["lookup_key"] == lookup_key]
    if not match.empty:
        share = match.iloc[0]["fossil_share"]
        available = match.iloc[0].get("data_available")
        if pd.notna(share) and str(share).strip() != "":
            source = "country" if available == "Yes" else "country_suppressed"
            return float(share), source

    fallback = eu27_fallback.get(str(nace_used))
    if fallback is not None:
        return float(fallback), "eu27_fallback"
    return None, "missing"


def load_heat_demand_from_workbook(
    workbook_path: Path,
    fossil_lookup_path: Path,
) -> pd.DataFrame:
    """Replicate Facilities-sheet formulas when cached values are unavailable."""
    facilities = pd.read_excel(workbook_path, sheet_name="Facilities", header=1)
    fossil_lookup = pd.read_csv(fossil_lookup_path)
    params = load_workbook_parameters(workbook_path)

    records: list[dict] = []
    for _, row in facilities.iterrows():
        source_id = row.get("source_id")
        if pd.isna(source_id):
            continue

        classification = row.get("classification")
        nace_used = row.get("nace_used")
        country = row.get("country_corrected")
        lookup_key = (
            f"{country}|{nace_used}"
            if pd.notna(country) and pd.notna(nace_used)
            else None
        )

        sec = params["sec_mwh_per_t"].get(str(classification))
        replace_frac = params["replace_frac"].get(str(classification))
        fossil_share = None
        fossil_share_source = "missing"
        if lookup_key:
            fossil_share, fossil_share_source = resolve_fossil_share(
                lookup_key,
                str(nace_used),
                fossil_lookup,
                params["eu27_fallback_share"],
            )

        keep = str(row.get("keep?", "")).strip().upper() == "YES"
        annual_output = pd.to_numeric(row.get("annual_output_t"), errors="coerce")
        heat_demand = (
            float(annual_output) * float(sec)
            if keep and pd.notna(annual_output) and sec is not None
            else 0.0
        )
        replaceable_heat = (
            heat_demand * float(fossil_share) * float(replace_frac)
            if keep
            and fossil_share is not None
            and replace_frac is not None
            else pd.NA
        )

        records.append(
            {
                "source_id": int(source_id),
                "country_corrected": country,
                "classification": classification,
                "nace_used": nace_used,
                "keep_in_analysis": keep,
                "status_flag": row.get("status_flag"),
                "sec_mwh_per_t": sec,
                "fossil_share": fossil_share,
                "fossil_share_source": fossil_share_source,
                "replace_frac": replace_frac,
                "heat_demand_mwh_th": heat_demand if keep else 0.0,
                "replaceable_heat_mwh_th": replaceable_heat,
                "in_heat_workbook": True,
            }
        )

    return pd.DataFrame(records)


def load_land(path: Path) -> pd.DataFrame:
    land = pd.read_csv(path)
    keep = ["source_id"] + [c for c in LAND_COLUMNS if c in land.columns]
    return land[keep]


def load_solar(path: Path) -> pd.DataFrame:
    solar = pd.read_csv(path)
    rename = {}
    if "year" in solar.columns:
        rename["year"] = "solar_year"
    if "capacity_factor" in solar.columns:
        rename["capacity_factor"] = "solar_capacity_factor"
    solar = solar.rename(columns=rename)
    keep = ["source_id"] + [c for c in SOLAR_COLUMNS if c in solar.columns]
    return solar[keep]


def merge_eu_pulp_paper_ihb_sites(
    *,
    facilities_path: Path,
    workbook_path: Path,
    fossil_lookup_path: Path,
    land_path: Path,
    solar_path: Path,
) -> pd.DataFrame:
    facilities = pd.read_csv(facilities_path)
    heat = load_heat_demand_from_workbook(workbook_path, fossil_lookup_path)
    land = load_land(land_path)
    solar = load_solar(solar_path)

    merged = facilities.merge(heat, on="source_id", how="left")
    merged["in_heat_workbook"] = merged["in_heat_workbook"].fillna(False).astype(bool)

    merged = merged.merge(land, on="source_id", how="left", suffixes=("", "_land"))
    merged = merged.merge(solar, on="source_id", how="left", suffixes=("", "_solar"))

    for duplicate in ["source_name_land", "source_name_solar", "iso3_country_land", "iso3_country_solar"]:
        if duplicate in merged.columns:
            merged = merged.drop(columns=[duplicate])
    for coord in ["lat_land", "lon_land", "lat_solar", "lon_solar"]:
        if coord in merged.columns:
            merged = merged.drop(columns=[coord])

    merged["has_land_data"] = merged["available_land_km2"].notna() if "available_land_km2" in merged.columns else False
    merged["has_solar_data"] = merged["annual_yield_kwh_per_kwp"].notna() if "annual_yield_kwh_per_kwp" in merged.columns else False
    merged["has_replaceable_heat"] = merged["replaceable_heat_mwh_th"].notna()

    column_order = [
        "source_id",
        "source_name",
        "source_type",
        "iso3_country",
        "country_corrected",
        "classification",
        "nace_used",
        "lat",
        "lon",
        "keep_in_analysis",
        "in_heat_workbook",
        "status_flag",
        "annual_output_t",
        "annual_capacity_t",
        "capacity_factor",
        "annual_emissions_co2e_t",
        "sec_mwh_per_t",
        "fossil_share",
        "fossil_share_source",
        "replace_frac",
        "heat_demand_mwh_th",
        "replaceable_heat_mwh_th",
        "available_land_km2",
        "bare_sparse_km2",
        "cropland_km2",
        "tree_cover_km2",
        "built_up_km2",
        "solar_year",
        "annual_yield_kwh_per_kwp",
        "solar_capacity_factor",
        "pvgis_raddatabase",
        "tilt_deg",
        "azimuth_deg",
        "system_loss_pct",
        "has_replaceable_heat",
        "has_land_data",
        "has_solar_data",
    ]
    extra_cols = [c for c in merged.columns if c not in column_order]
    merged = merged[column_order + extra_cols]

    return merged.sort_values(["iso3_country", "source_name"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge EU pulp & paper facility inputs for colocated solar + IHB assessment: "
            "Climate TRACE production, workbook heat demand, GEE land availability, and PVGIS solar."
        )
    )
    parser.add_argument("--facilities", type=Path, default=DEFAULT_FACILITIES)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--fossil-lookup", type=Path, default=DEFAULT_FOSSIL_LOOKUP)
    parser.add_argument("--land", type=Path, default=DEFAULT_LAND)
    parser.add_argument("--solar", type=Path, default=DEFAULT_SOLAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    for label, path in [
        ("Facilities", args.facilities),
        ("Workbook", args.workbook),
        ("Fossil lookup", args.fossil_lookup),
        ("Land availability", args.land),
        ("Solar radiation", args.solar),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{label} file not found: {path}")

    result = merge_eu_pulp_paper_ihb_sites(
        facilities_path=args.facilities,
        workbook_path=args.workbook,
        fossil_lookup_path=args.fossil_lookup,
        land_path=args.land,
        solar_path=args.solar,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    print(f"Wrote {len(result)} rows to {args.output}")
    print(f"  In heat workbook: {result['in_heat_workbook'].sum()}")
    print(f"  Kept for analysis: {int(result['keep_in_analysis'].fillna(False).astype(bool).sum())}")
    print(f"  With replaceable heat: {result['has_replaceable_heat'].sum()}")
    print(f"  With land data: {result['has_land_data'].sum()}")
    print(f"  With solar data: {result['has_solar_data'].sum()}")

    preview_cols = [
        c
        for c in [
            "source_name",
            "iso3_country",
            "replaceable_heat_mwh_th",
            "available_land_km2",
            "annual_yield_kwh_per_kwp",
        ]
        if c in result.columns
    ]
    print(result[preview_cols].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
