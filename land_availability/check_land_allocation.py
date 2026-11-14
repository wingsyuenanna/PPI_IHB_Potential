"""Sanity-check heat-weighted (allocated) land against independent-buffer land.

Expected:
  1. allocated <= independent for every facility (small tolerance for pixel edges);
  2. facilities with no neighbour within 2 x radius: allocated ~= independent;
  3. total allocated < total independent, the gap being land previously counted twice.

    python land_availability/check_land_allocation.py --radius-km 5 \
        --allocated land_availability/outputs/land_availability_allocated_5km.csv \
        --independent land_availability/outputs/land_availability_by_facility_5km.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEAT = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_replaceable.csv"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radius-km", type=float, required=True)
    ap.add_argument("--allocated", type=Path, required=True)
    ap.add_argument("--independent", type=Path, required=True)
    args = ap.parse_args()

    heat = pd.read_csv(HEAT)
    heat = heat[heat["replaceable_heat_mwh"].fillna(0) > 0][["source_id", "lat", "lon", "subsector", "replaceable_heat_mwh"]]
    alloc = pd.read_csv(args.allocated)[["source_id", "available_land_km2"]].rename(columns={"available_land_km2": "alloc_km2"})
    indep = pd.read_csv(args.independent)[["source_id", "available_land_km2"]].rename(columns={"available_land_km2": "indep_km2"})
    df = heat.merge(alloc, on="source_id", how="left").merge(indep, on="source_id", how="left")
    print(f"facilities with heat: {len(df)}  missing allocated: {df.alloc_km2.isna().sum()}  missing independent: {df.indep_km2.isna().sum()}")
    df = df.dropna(subset=["alloc_km2", "indep_km2"])

    lat, lon = np.radians(df.lat.values), np.radians(df.lon.values)
    a = np.sin((lat[:, None] - lat[None, :]) / 2) ** 2 + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin((lon[:, None] - lon[None, :]) / 2) ** 2
    dist = 6371 * 2 * np.arcsin(np.sqrt(a))
    np.fill_diagonal(dist, np.inf)
    df["has_neighbour"] = (dist < 2 * args.radius_km).any(axis=1)

    tol = 0.01 * df.indep_km2 + 0.01  # 1% + 0.01 km2 for pixel-edge effects
    over = df[df.alloc_km2 > df.indep_km2 + tol]
    iso = df[~df.has_neighbour]
    iso_diff = (iso.alloc_km2 - iso.indep_km2).abs() / iso.indep_km2.replace(0, np.nan)
    print(f"1. allocated > independent (beyond tolerance): {len(over)} facilities")
    print(f"2. isolated facilities: {len(iso)}, max relative difference {np.nanmax(iso_diff) if len(iso) else 0:.2%}")
    print(f"3. total independent {df.indep_km2.sum():,.0f} km2, total allocated {df.alloc_km2.sum():,.0f} km2 "
          f"({1 - df.alloc_km2.sum() / df.indep_km2.sum():.1%} less)")
    s = df.groupby("subsector")[["indep_km2", "alloc_km2"]].sum()
    s["reduction"] = 1 - s.alloc_km2 / s.indep_km2
    print(s.round(1).sort_values("reduction", ascending=False).to_string())


if __name__ == "__main__":
    main()
