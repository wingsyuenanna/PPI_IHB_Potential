"""Assemble the optimizer sites input from the new heat-demand pipeline.

Combines:
  - heat_demand/facilities/facilities_2024_eu_replaceable.csv
        useful + replaceable heat (new fossil-share methodology), all subsectors
  - land_availability/outputs/land_availability_by_facility.csv
        available_land_km2 (+ land-cover breakdown), by source_id
  - solar profile presence (solar_radiation/outputs/hourly_profiles/<id>_<yr>.parquet)
  - classification + solar_capacity_factor carried from the previous pulp/paper
        assessment (curated Pulp/Integrated/Paper-Board/Tissue labels that set the
        heat-battery steam temperature; source_type cannot reproduce them)

Writes outputs/eu_ihb_site_assessment_2024.csv — the file run_ihb_potential.py
reads. Column `replaceable_heat_mwh_th` is what the optimizer sizes load against.

Only sites with a solar profile AND positive replaceable heat run (the optimizer
filters on has_solar_data / has_replaceable_heat); today that is the 86 pulp &
paper sites, but any facility gains eligibility as soon as a solar profile exists.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPLACEABLE = ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_replaceable.csv"
LAND = ROOT / "land_availability" / "outputs" / "land_availability_by_facility.csv"
SOLAR_DIR = ROOT / "solar_radiation" / "outputs" / "hourly_profiles"
PREV_ASSESSMENT = ROOT / "outputs" / "eu_pulp_paper_ihb_site_assessment_2024.csv"
OUTPUT = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"


def solar_source_ids() -> set[int]:
    return {int(p.stem.split("_")[0]) for p in SOLAR_DIR.glob("*.parquet")}


def main() -> None:
    fac = pd.read_csv(REPLACEABLE, low_memory=False)
    land = pd.read_csv(LAND)
    prev = pd.read_csv(PREV_ASSESSMENT)

    land_cols = ["source_id", "available_land_km2"] + [
        c for c in land.columns if c.endswith("_km2") and c != "available_land_km2"
    ]
    df = fac.merge(land[land_cols], on="source_id", how="left")

    # Carry curated fields from the prior assessment by source_id.
    carry = ["source_id", "classification", "solar_capacity_factor"]
    carry = [c for c in carry if c in prev.columns]
    df = df.merge(prev[carry], on="source_id", how="left")

    # Optimizer contract columns.
    df["replaceable_heat_mwh_th"] = df["replaceable_heat_mwh"]
    sol = solar_source_ids()
    df["has_solar_data"] = df["source_id"].astype(int).isin(sol)
    df["has_land_data"] = df["available_land_km2"].notna()
    df["has_replaceable_heat"] = df["replaceable_heat_mwh_th"].fillna(0) > 0

    df.to_csv(OUTPUT, index=False)

    runnable = df[df["has_solar_data"] & df["has_replaceable_heat"]]
    print(f"Wrote {len(df)} sites to {OUTPUT.relative_to(ROOT)}")
    print(f"Runnable (solar + replaceable heat): {len(runnable)}")
    print(f"  with land data: {int(runnable['has_land_data'].sum())}")
    print("  by subsector:")
    print(runnable["subsector"].value_counts().to_string())


if __name__ == "__main__":
    main()
