"""Apply the validated duplicate-site decisions to the heat-bands output.

Pipeline step 5: reads facilities_2024_eu_heat_bands.csv and the reviewed
decision list heat_demand/analysis_outputs/duplicate_sites_flagged.csv, then

1. deletes every source_id named in a "Delete ..." clause of the outcome
   column (clauses are split on ";"; "keep"/"review" clauses are ignored,
   and lowercase "lean delete" review suggestions are NOT executed);
2. merges the Ardagh Glass Barnsley pair (GL-2): the duplicate row's
   production/heat/band columns are summed into the kept row instead of
   dropped, because glass is under-counted vs the top-down and the two
   rows are believed to be split reporting units of one site;
3. applies sourced capacity corrections (San Ciprian smelter 228 kt per
   ASI audit; Laakirchen 570 kt / Steyrermuhl 320 kt per Heinzel/UPM).
   Production and heat on those rows are NOT recomputed.

Output: facilities_2024_eu_deduplicated.csv / .xlsx
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_BANDS = HERE / "facilities_2024_eu_heat_bands.csv"
DEFAULT_FLAGS = HERE / ".." / "analysis_outputs" / "duplicate_sites_flagged.csv"
DEFAULT_OUTPUT = HERE / "facilities_2024_eu_deduplicated.csv"
DEFAULT_XLSX = HERE / "facilities_2024_eu_deduplicated.xlsx"

# GL-2: sum duplicate row into kept row before deletion (see module docstring).
MERGE_PAIRS = [(38469301, 38469338)]
MERGE_COLS = [
    "production_t", "fuel_energy_tj", "useful_heat_tj", "useful_heat_mwh",
    "annual_output_t", "production_2014_t", "bench_heat_tj", "bench_heat_mwh",
    "heat_below100C_tj", "heat_100C-200C_tj", "heat_200C-500C_tj",
    "heat_500C-1000C_tj", "heat_above1000C_tj",
]

# Sourced capacity corrections from duplicate_sites_flagged.csv outcomes.
CAPACITY_CORRECTIONS = {
    43765124: 228_000.0,  # AL-1 San Ciprian smelter (ASI audit)
    44375328: 570_000.0,  # PP-8 Laakirchen Papier (Heinzel)
    44375329: 320_000.0,  # PP-8 Steyrermuhl (UPM newsprint, until 2023)
}


def delete_ids(flags: pd.DataFrame) -> set[int]:
    """source_ids named in capital-D 'Delete ...' clauses of the outcomes."""
    ids: set[int] = set()
    for outcome in flags["outcome"].dropna():
        for clause in str(outcome).split(";"):
            if clause.strip().startswith("Delete"):
                ids |= {int(x) for x in re.findall(r"\d{6,}", clause)}
    return ids


def apply_dedup(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    for src_id, dst_id in MERGE_PAIRS:
        src = df.loc[df["source_id"] == src_id]
        if src.empty:
            continue
        src = src.iloc[0]
        for col in MERGE_COLS:
            if pd.notna(src[col]):
                cur = df.loc[df["source_id"] == dst_id, col].iloc[0]
                df.loc[df["source_id"] == dst_id, col] = (
                    cur if pd.notna(cur) else 0.0
                ) + src[col]

    for sid, cap in CAPACITY_CORRECTIONS.items():
        df.loc[df["source_id"] == sid, "annual_capacity_t"] = cap

    drop = delete_ids(flags)
    missing = drop - set(df["source_id"])
    if missing:
        raise SystemExit(f"delete ids not present in input: {sorted(missing)}")
    return df[~df["source_id"].isin(drop)].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bands", type=Path, default=DEFAULT_BANDS)
    parser.add_argument("--flags", type=Path, default=DEFAULT_FLAGS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()

    df = pd.read_csv(args.bands)
    flags = pd.read_csv(args.flags)
    out = apply_dedup(df, flags)
    out.to_csv(args.output, index=False)
    out.to_excel(args.xlsx, sheet_name="Facilities", index=False)
    print(f"{len(df)} -> {len(out)} facilities "
          f"({len(df) - len(out)} duplicates removed)")


if __name__ == "__main__":
    main()
