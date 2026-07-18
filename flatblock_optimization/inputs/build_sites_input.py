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
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPLACEABLE = ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_replaceable.csv"
LAND = ROOT / "land_availability" / "outputs" / "land_availability_by_facility.csv"
SOLAR_DIR = ROOT / "solar_radiation" / "outputs" / "hourly_profiles"
SOLAR_SUMMARY = ROOT / "solar_radiation" / "outputs" / "solar_radiation_by_facility.csv"
PREV_ASSESSMENT = ROOT / "outputs" / "eu_pulp_paper_ihb_site_assessment_2024.csv"
OUTPUT = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"

# Representative temperature (°C) of each heat-demand temperature band, used to
# derive one demand-weighted process temperature per facility from the heat_*_tj
# band columns. The open-ended top band uses a representative sintering-range value.
BAND_MIDPOINTS = {
    "heat_below100C_tj": 60.0,
    "heat_100C-200C_tj": 150.0,
    "heat_200C-500C_tj": 350.0,
    "heat_500C-1000C_tj": 750.0,
    "heat_above1000C_tj": 1300.0,
}


def solar_source_ids() -> set[int]:
    return {int(p.stem.split("_")[0]) for p in SOLAR_DIR.glob("*.parquet")}


def demand_weighted_process_temp(fac: pd.DataFrame) -> pd.Series:
    """One representative process temperature (°C) per facility, weighting each
    heat temperature band by its heat and the band's midpoint. Gives every
    subsector a physically-appropriate TES floor (T_min) rather than a single
    pulp-oriented fallback. NaN where a site has no band data."""
    present = [b for b in BAND_MIDPOINTS if b in fac.columns]
    heat = fac[present].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    total = heat.sum(axis=1)
    weighted = sum(heat[b] * BAND_MIDPOINTS[b] for b in present)
    return (weighted / total.where(total > 0)).where(total > 0)


def main() -> None:
    fac = pd.read_csv(REPLACEABLE, low_memory=False)
    land = pd.read_csv(LAND)
    prev = pd.read_csv(PREV_ASSESSMENT)

    land_cols = ["source_id", "available_land_km2"] + [
        c for c in land.columns if c.endswith("_km2") and c != "available_land_km2"
    ]
    df = fac.merge(land[land_cols], on="source_id", how="left")

    # Carry the curated classification label from the prior pulp assessment
    # (steam-temperature bucket / reporting); only populated for pulp sites.
    carry = ["source_id"] + [c for c in ["classification"] if c in prev.columns]
    df = df.merge(prev[carry], on="source_id", how="left")

    # Solar capacity factor for ALL sites from the PVGIS summary (previously only
    # carried for the 79 pulp sites from the prior assessment).
    if SOLAR_SUMMARY.exists():
        sol_sum = pd.read_csv(SOLAR_SUMMARY)[["source_id", "capacity_factor"]].rename(
            columns={"capacity_factor": "solar_capacity_factor"}
        )
        df = df.merge(sol_sum, on="source_id", how="left")
    else:
        df["solar_capacity_factor"] = np.nan

    # Per-facility process temperature (TES T_min) from the heat temperature bands,
    # so every subsector is set up with a physically-appropriate floor instead of
    # the pulp-oriented 200 °C fallback in the optimizer.
    temp = pd.DataFrame(
        {"source_id": fac["source_id"], "process_temp_c": demand_weighted_process_temp(fac)}
    )
    df = df.merge(temp, on="source_id", how="left")

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
    print(f"  with solar capacity factor: {int(runnable['solar_capacity_factor'].notna().sum())}")
    print(f"  with process temperature: {int(runnable['process_temp_c'].notna().sum())}")
    print("  median process_temp_c by subsector:")
    print(
        runnable.groupby("subsector")["process_temp_c"].median().round(0)
        .sort_values().to_string()
    )


if __name__ == "__main__":
    main()
