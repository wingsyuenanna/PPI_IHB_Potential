"""Match EU facilities (facility master 2024) against Fraunhofer hotmaps
Industrial_Database_2014 and compare production numbers.

Matching process (no shared facility ID between the datasets):
1. Map the two subsector taxonomies onto each other (e.g. master
   "pulp-and-paper" <-> hotmaps "Paper and printing").
2. Within each mapped subsector, match facilities by spatial proximity
   (haversine distance between master lat/lon and hotmaps geom point),
   assigning greedily nearest-first so each hotmaps site is used once.
3. Score every match with a name-similarity ratio (difflib on
   source_name vs SiteName/CompanyName) as an independent check.
4. Classify confidence: "high" when the sites are within 1 km, "medium"
   within the max radius (default 5 km) with a name similarity >= 0.4,
   otherwise "low" (kept, but flagged for manual review).
5. Compare production: ratio_2024_2014 = annual_output_t / Production.

Hotmaps only reports Production for Cement, Iron and steel, Paper and
printing, and Glass; 515 hotmaps rows have no coordinates and cannot be
matched spatially.
"""

from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MASTER = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
DEFAULT_HOTMAPS = PROJECT_ROOT / "Input" / "Industrial_Database_2014.csv"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_matched_hotmaps_2014.csv"
)

EARTH_RADIUS_KM = 6371.0

# facility master subsector -> hotmaps Subsector(s)
SUBSECTOR_MAP: dict[str, list[str]] = {
    "cement": ["Cement"],
    "iron-and-steel": ["Iron and steel"],
    "pulp-and-paper": ["Paper and printing"],
    "glass": ["Glass"],
    "chemicals": ["Chemical industry"],
    "petrochemical-steam-cracking": ["Chemical industry", "Refineries"],
    "aluminum": ["Non-ferrous metals"],
    "other-metals": ["Non-ferrous metals"],
    "lime": ["Non-metallic mineral products"],
    "food-beverage-tobacco": ["Other non-classified"],
    "textiles-leather-apparel": ["Other non-classified"],
}

HOTMAPS_KEEP_COLUMNS = [
    "SiteID",
    "CompanyName",
    "SiteName",
    "City",
    "Country",
    "Subsector",
    "Emissions_ETS_2014",
    "Production",
    "Fuel_Demand",
    "Excess_Heat_Total",
]


def load_hotmaps(path: Path) -> pd.DataFrame:
    """Load the hotmaps database and parse geom -> hm_lat/hm_lon."""
    hotmaps = pd.read_csv(path, sep=";")
    coords = hotmaps["geom"].str.extract(
        r"POINT\((?P<hm_lon>[-\d.]+) (?P<hm_lat>[-\d.]+)\)"
    )
    hotmaps["hm_lon"] = pd.to_numeric(coords["hm_lon"])
    hotmaps["hm_lat"] = pd.to_numeric(coords["hm_lat"])
    return hotmaps


def haversine_km(
    lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Distance in km from one point to arrays of points."""
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2, lon2 = np.radians(lat2), np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def normalize_name(name: str) -> str:
    """Lowercase and strip legal suffixes/punctuation for fuzzy comparison."""
    name = str(name).lower()
    name = re.sub(
        r"\b(gmbh|ag|sa|spa|s\.p\.a|srl|bv|nv|oy|ab|as|sp z o o|"
        r"co|kg|ltd|plc|inc|mill|plant|factory|werk|papierfabrik)\b",
        " ",
        name,
    )
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def name_similarity(master_name: str, site_name: str, company_name: str) -> float:
    """Best difflib ratio of the master name against site and company names."""
    a = normalize_name(master_name)
    return max(
        SequenceMatcher(None, a, normalize_name(site_name)).ratio(),
        SequenceMatcher(None, a, normalize_name(company_name)).ratio(),
    )


def match_facilities(
    master: pd.DataFrame,
    hotmaps: pd.DataFrame,
    max_distance_km: float = 5.0,
) -> pd.DataFrame:
    """Greedy nearest-first one-to-one spatial match within mapped subsectors."""
    matches: list[dict] = []

    for master_subsector, hotmaps_subsectors in SUBSECTOR_MAP.items():
        m_block = master[master["subsector"] == master_subsector]
        h_block = hotmaps[
            hotmaps["Subsector"].isin(hotmaps_subsectors)
            & hotmaps["hm_lat"].notna()
        ]
        if m_block.empty or h_block.empty:
            continue

        # All candidate pairs within the radius, nearest pairs first.
        candidates: list[tuple[float, int, int]] = []
        h_lat = h_block["hm_lat"].to_numpy()
        h_lon = h_block["hm_lon"].to_numpy()
        for m_idx, m_row in m_block.iterrows():
            dists = haversine_km(m_row["lat"], m_row["lon"], h_lat, h_lon)
            for pos in np.flatnonzero(dists <= max_distance_km):
                candidates.append((dists[pos], m_idx, h_block.index[pos]))

        used_master: set[int] = set()
        used_hotmaps: set[int] = set()
        for dist, m_idx, h_idx in sorted(candidates):
            if m_idx in used_master or h_idx in used_hotmaps:
                continue
            used_master.add(m_idx)
            used_hotmaps.add(h_idx)
            matches.append(
                {"master_index": m_idx, "hotmaps_index": h_idx, "distance_km": dist}
            )

    pairs = pd.DataFrame(matches)
    combined = master.merge(
        pairs.set_index("master_index"), left_index=True, right_index=True, how="left"
    )
    combined = combined.merge(
        hotmaps[HOTMAPS_KEEP_COLUMNS + ["hm_lat", "hm_lon"]],
        left_on="hotmaps_index",
        right_index=True,
        how="left",
    )
    combined = combined.drop(columns=["hotmaps_index"])

    matched = combined["SiteID"].notna()
    combined.loc[matched, "name_similarity"] = combined.loc[matched].apply(
        lambda r: name_similarity(r["source_name"], r["SiteName"], r["CompanyName"]),
        axis=1,
    )
    combined["match_confidence"] = np.select(
        [
            matched & (combined["distance_km"] <= 1.0),
            matched & (combined["name_similarity"] >= 0.4),
            matched,
        ],
        ["high", "medium", "low"],
        default="unmatched",
    )

    # Production comparison: 2024 capacity-derived output vs 2014 reported production.
    combined = combined.rename(columns={"Production": "production_2014_t"})
    has_both = matched & combined["production_2014_t"].gt(0)
    combined.loc[has_both, "output_ratio_2024_2014"] = (
        combined.loc[has_both, "annual_output_t"]
        / combined.loc[has_both, "production_2014_t"]
    )
    return combined


def summarize(combined: pd.DataFrame) -> None:
    matched = combined[combined["match_confidence"] != "unmatched"]
    print(f"Master facilities: {len(combined)}")
    print(f"Matched to hotmaps: {len(matched)}")
    print(matched["match_confidence"].value_counts().to_string())

    both = matched.dropna(subset=["output_ratio_2024_2014", "annual_output_t"])
    print(f"\nWith production in both years: {len(both)}")
    if not both.empty:
        stats = both.groupby("subsector")["output_ratio_2024_2014"].agg(
            ["count", "median", "mean"]
        )
        print("\noutput_ratio_2024_2014 (annual_output_t / production_2014_t):")
        print(stats.round(2).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match facility master EU export against hotmaps 2014."
    )
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--hotmaps", type=Path, default=DEFAULT_HOTMAPS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-distance-km",
        type=float,
        default=5.0,
        help="Maximum distance between sites to consider a match.",
    )
    args = parser.parse_args()

    master = pd.read_csv(args.master)
    hotmaps = load_hotmaps(args.hotmaps)
    combined = match_facilities(master, hotmaps, args.max_distance_km)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.output, index=False)
    print(f"Wrote {len(combined)} rows to {args.output}\n")
    summarize(combined)


if __name__ == "__main__":
    main()
