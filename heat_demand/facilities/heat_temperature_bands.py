"""Split facility heat demand into temperature bands using the hotmaps
industry benchmarks (Input/industryBenchmarks_2014.csv).

Each facility is mapped to a recipe of benchmark processes (process,
weight = tonnes of process throughput per tonne of facility product).
For facilities with production (tiers 1-2):

    band_heat_TJ = production_t * sum_p( weight_p * SEC_Fuels_p *
                   band_share_p ) / 1000

For tier-3 facilities (emissions-derived heat, no production), the
benchmark band shares are applied to the existing useful_heat_tj from
merge_production.py.

Process recipes, external (non-benchmark) band splits, and caveats are
documented in METHODS.md section 5. Keep that file in sync.

Run merge_production.py first; this script consumes its output.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MERGED = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_merged.csv"
)
DEFAULT_BENCHMARKS = PROJECT_ROOT / "Input" / "industryBenchmarks_2014.csv"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_heat_bands.csv"
)
DEFAULT_XLSX = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu_heat_bands.xlsx"
)

BANDS = ["below100C", "100C-200C", "200C-500C", "500C-1000C", "above1000C"]
BAND_COLUMNS = {
    "below100C": "Process_heat_below100C",
    "100C-200C": "Process_heat_100C-200C",
    "200C-500C": "Process_heat_200C-500C",
    "500C-1000C": "Process_heat_500C-1000C",
    "above1000C": "Process_heat_above1000C",
}
TJ_TO_MWH = 1e6 / 3600

# Recipes: facility (subsector, optionally source_type) -> list of
# (benchmark Subsector, Process, weight in t process per t product).
# Steel intermediate ratios per t crude steel: worldsteel typical BF-BOF
# inputs (coke 0.30 t, sinter 1.20 t, hot metal 0.95 t, rolled 0.90 t).
# Cement: EU clinker-to-cement ratio ~0.77 (Cembureau), dry kilns dominant.
# Glass: EU production mix ~55% container / 30% flat / 5% fiber / 10% other
# (FEVE / Glass Alliance Europe).
STEEL_RECIPES: dict[str, list[tuple[str, str, float]]] = {
    # Coke ovens and blast furnaces are excluded from BF/BOF: Eurostat books
    # them in the TRANSFORMATION sector, not iron & steel final consumption,
    # so keeping them made the bottom-up incomparable to the top-down.
    # (Whole-route recipe was coke 0.30 / sinter 1.20 / BF 0.95 / rolled 0.90.)
    "BF/BOF": [
        ("Iron and steel", "Sinter", 1.20),
        ("Iron and steel", "Rolled steel", 0.90),
    ],
    "EAF": [
        ("Iron and steel", "Electric arc furnace", 1.0),
        ("Iron and steel", "Rolled steel", 0.90),
    ],
    "DRI-EAF": [
        ("Iron and steel", "Direct reduction", 1.0),
        ("Iron and steel", "Electric arc furnace", 1.0),
        ("Iron and steel", "Rolled steel", 0.90),
    ],
}
STEEL_RECIPES["BOF"] = STEEL_RECIPES["BF/BOF"]
STEEL_RECIPES["BOF,EAF"] = [
    (s, p, w / 2) for s, p, w in STEEL_RECIPES["BF/BOF"] + STEEL_RECIPES["EAF"]
]
STEEL_RECIPES["DRI-EAF,BF/BOF"] = [
    (s, p, w / 2) for s, p, w in STEEL_RECIPES["DRI-EAF"] + STEEL_RECIPES["BF/BOF"]
]

GLASS_RECIPE = [
    ("Non-metallic minerals", "Container glass", 0.55),
    ("Non-metallic minerals", "Flat glass", 0.30),
    ("Non-metallic minerals", "Fiber glass", 0.05),
    ("Non-metallic minerals", "Other glass", 0.10),
]

# Pulp & paper: production is "t of pulp & paper"; assume half pulp, half
# paper (coarse - the corrected workbook is authoritative for this sector).
# The pulp half is split by keywords in source_type; "Pulp misc." defaults
# to the EU mix ~70% chemical / 30% mechanical (CEPI).
PAPER_HALF = ("Paper and Printing", "Paper", 0.5)

# Food band profile: source_type is generic for 880/886 sites, so bands use
# an equal-weight blend of the six benchmark food processes.
FOOD_PROCESSES = [
    "Sugar", "Dairy", "Brewing", "Meat processing", "Bread & bakery", "Starch",
]

# External band splits for sectors/processes missing from the benchmarks
# (flagged band_source = "external"). See METHODS.md section 5.
EXTERNAL_BANDS: dict[str, dict[str, float]] = {
    # Bayer process: steam digestion ~150-250C + calcination ~1000C (IAI).
    "alumina-refinery": {"100C-200C": 0.75, "500C-1000C": 0.25},
    # Textile finishing/dyeing: mostly hot water/steam (Rehfeldt et al. 2018).
    "textiles": {"below100C": 0.55, "100C-200C": 0.35, "200C-500C": 0.10},
}


def load_benchmarks(path: Path) -> pd.DataFrame:
    bench = pd.read_csv(path, encoding="utf-8-sig")
    bench.columns = [c.strip() for c in bench.columns]
    bench["Subsector"] = bench["Subsector"].str.strip()
    bench["Process"] = bench["Process"].str.strip()
    for col in BAND_COLUMNS.values():
        bench[col] = bench[col].fillna(0.0)
    # Mechanical pulp has a negative fuel SEC (net heat producer); clamp so
    # recipes never subtract heat.
    bench["SEC_Fuels_GJ/t"] = bench["SEC_Fuels_GJ/t"].clip(lower=0).fillna(0.0)
    return bench.set_index(["Subsector", "Process"])


def pulp_recipe(source_type: str) -> list[tuple[str, str, float]]:
    text = str(source_type).lower()
    chem = "chemical wood pulp" in text or "semi-chemical" in text
    mech = "mechanical" in text
    if chem and mech:
        pulp = [("Paper and Printing", "Chemical pulp", 0.25),
                ("Paper and Printing", "Mechanical pulp", 0.25)]
    elif mech:
        pulp = [("Paper and Printing", "Mechanical pulp", 0.5)]
    elif chem:
        pulp = [("Paper and Printing", "Chemical pulp", 0.5)]
    else:  # "Pulp misc." and unknowns: EU mix ~70/30 chemical/mechanical
        pulp = [("Paper and Printing", "Chemical pulp", 0.35),
                ("Paper and Printing", "Mechanical pulp", 0.15)]
    return pulp + [PAPER_HALF]


def facility_recipe(row: pd.Series) -> list[tuple[str, str, float]] | None:
    subsector = row["subsector"]
    source_type = str(row["source_type"])
    if subsector == "cement":
        return [("Non-metallic minerals", "Clinker calcination-dry", 0.77)]
    if subsector == "lime":
        return [("Non-metallic minerals", "Lime burning", 1.0)]
    if subsector == "glass":
        return GLASS_RECIPE
    if subsector == "iron-and-steel":
        return STEEL_RECIPES.get(source_type, STEEL_RECIPES["BF/BOF"])
    if subsector == "petrochemical-steam-cracking":
        return [("Basic chemicals", "Ethylene", 1.0)]
    if subsector == "chemicals":
        process = {"ammonia": "Ammonia", "soda_ash": "Soda ash",
                   "methanol": "Methanol"}.get(source_type)
        return [("Basic chemicals", process, 1.0)] if process else None
    if subsector == "aluminum" and source_type == "Smelting":
        return [("Non-ferrous metals", "Aluminum primary", 1.0)]
    if subsector == "pulp-and-paper":
        return pulp_recipe(source_type)
    return None


def band_shares_from_recipe(
    bench: pd.DataFrame, recipe: list[tuple[str, str, float]]
) -> tuple[float, dict[str, float]]:
    """Return (heat GJ per t product, normalized band shares) for a recipe."""
    band_heat = dict.fromkeys(BANDS, 0.0)
    for subsector, process, weight in recipe:
        sec = bench.at[(subsector, process), "SEC_Fuels_GJ/t"] * weight
        shares = np.array(
            [bench.at[(subsector, process), BAND_COLUMNS[b]] for b in BANDS]
        )
        if shares.sum() > 0:
            shares = shares / shares.sum()
        for band, share in zip(BANDS, shares, strict=True):
            band_heat[band] += sec * share
    total = sum(band_heat.values())
    if total <= 0:
        return 0.0, dict.fromkeys(BANDS, 0.0)
    return total, {b: h / total for b, h in band_heat.items()}


def food_band_shares(bench: pd.DataFrame) -> dict[str, float]:
    recipe = [("Food and tobacco", p, 1.0) for p in FOOD_PROCESSES]
    _, shares = band_shares_from_recipe(bench, recipe)
    return shares


def apply_bands(merged: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    out = merged.copy()
    out["bench_heat_tj"] = np.nan
    out["band_source"] = pd.NA
    for band in BANDS:
        out[f"heat_{band}_tj"] = np.nan

    food_shares = food_band_shares(bench)

    for idx, row in out.iterrows():
        subsector = row["subsector"]

        # Tier 3 and non-benchmark processes: split existing heat.
        if subsector == "food-beverage-tobacco":
            heat, shares, source = row["useful_heat_tj"], food_shares, "benchmark"
        elif subsector == "textiles-leather-apparel":
            heat, shares, source = (
                row["useful_heat_tj"], EXTERNAL_BANDS["textiles"], "external",
            )
        elif subsector == "aluminum" and row["source_type"] == "Refinery":
            heat, shares, source = (
                row["useful_heat_tj"], EXTERNAL_BANDS["alumina-refinery"], "external",
            )
        else:
            # Tiers 1-2: benchmark SEC x production.
            recipe = facility_recipe(row)
            if recipe is None or not row["production_t"] > 0:
                continue
            sec_gj_t, shares = band_shares_from_recipe(bench, recipe)
            heat, source = row["production_t"] * sec_gj_t / 1000, "benchmark"

        if pd.isna(heat):
            continue
        out.at[idx, "bench_heat_tj"] = heat
        out.at[idx, "band_source"] = source
        for band in BANDS:
            out.at[idx, f"heat_{band}_tj"] = heat * shares.get(band, 0.0)

    out["bench_heat_mwh"] = out["bench_heat_tj"] * TJ_TO_MWH
    return out


def summarize(out: pd.DataFrame) -> None:
    with_bands = out[out["bench_heat_tj"].notna()]
    print(
        f"Facilities with banded heat: {len(with_bands)} of {len(out)}, "
        f"total {with_bands['bench_heat_tj'].sum() / 3600:.0f} TWh/yr"
    )
    band_cols = [f"heat_{b}_tj" for b in BANDS]
    table = with_bands.groupby("subsector")[band_cols].sum() / 3600  # TWh
    table.columns = BANDS
    table["total"] = table.sum(axis=1)
    print("\nHeat demand by temperature band (TWh/yr):")
    print(table.round(1).to_string())
    totals = table[BANDS].sum()
    print("\nEU total by band (TWh/yr and share):")
    for band in BANDS:
        print(f"  {band:>11}: {totals[band]:7.1f}  ({totals[band] / totals.sum():.0%})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split facility heat demand into temperature bands."
    )
    parser.add_argument("--merged", type=Path, default=DEFAULT_MERGED)
    parser.add_argument("--benchmarks", type=Path, default=DEFAULT_BENCHMARKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()

    merged = pd.read_csv(args.merged)
    bench = load_benchmarks(args.benchmarks)
    out = apply_bands(merged, bench)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    out.to_excel(args.xlsx, sheet_name="Facilities", index=False)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.xlsx}\n")
    summarize(out)


if __name__ == "__main__":
    main()
