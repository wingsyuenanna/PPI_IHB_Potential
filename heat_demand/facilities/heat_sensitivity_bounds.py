"""Build low / base / high replaceable-heat bounds by subsector.

Sector multipliers encode different physical/methodological uncertainties
(METHODS.md, crosscheck3 SEC sensitivity, fossil-share spans). Base case = 1.0
(= current ``replaceable_heat_mwh_th``).

    python heat_demand/facilities/heat_sensitivity_bounds.py
    python heat_demand/facilities/heat_sensitivity_bounds.py --dry-run

Writes/updates columns on the site assessment CSV:
  replaceable_heat_mwh_th_low
  replaceable_heat_mwh_th_high
  heat_bound_low_factor
  heat_bound_high_factor
  heat_bound_rationale
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SITES = PROJECT_ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"

# (low_factor, high_factor, short rationale)
# Factors multiply base replaceable_heat_mwh_th. Band *shares* stay fixed;
# absolute band loads scale with total heat in the optimizer.
SECTOR_HEAT_BOUNDS: dict[str, tuple[float, float, str]] = {
    "cement": (
        0.85,
        1.60,
        "Kiln η 50–60% (low); high ≈ Hotmaps/METHODS SEC gap (~+60%)",
    ),
    "lime": (
        0.80,
        1.50,
        "SEC literature 3.6–7.5 GJ/t around base 4.5; kiln η mix",
    ),
    "glass": (
        0.85,
        2.00,
        "Furnace η 40–50% (low); high capped Hotmaps/METHODS gap (~2.7× raw)",
    ),
    "iron-and-steel": (
        0.90,
        1.55,
        "Low: lean final-consumption scope; high: SEC ~7.5 GJ/t to close Eurostat gap",
    ),
    "petrochemical-steam-cracking": (
        0.47,
        1.00,
        "Low: external fuel only 17 GJ/t vs base total duty 35.9; high = base",
    ),
    "chemicals": (
        0.85,
        1.40,
        "SEC/η uncertainty; high ≈ Hotmaps/METHODS gap (~+40%)",
    ),
    "pulp-and-paper": (
        0.70,
        1.15,
        "Low: high-biomass countries (fossil share); high: SEC + fossil-share upside",
    ),
    "food-beverage-tobacco": (
        0.85,
        1.40,
        "Country-rescale residual uncertainty (not full unscaled CT; that blows PT/ES)",
    ),
    "textiles-leather-apparel": (
        0.85,
        1.20,
        "Fuel EF / gas–oil mix (±); no food-style country rescale",
    ),
    "aluminum": (
        0.90,
        1.15,
        "Smaller METHODS vs Hotmaps gap (~+11%)",
    ),
    "other-metals": (
        0.85,
        1.25,
        "Default ± band; sparse SEC coverage",
    ),
}
DEFAULT_BOUNDS = (0.85, 1.25, "Default ± when subsector not listed")


def bounds_for(subsector: str) -> tuple[float, float, str]:
    return SECTOR_HEAT_BOUNDS.get(str(subsector), DEFAULT_BOUNDS)


def apply_bounds(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "replaceable_heat_mwh_th" not in out.columns:
        raise KeyError("replaceable_heat_mwh_th missing — build assessment first")

    lows, highs, rats = [], [], []
    for sub in out["subsector"]:
        lo, hi, rat = bounds_for(sub)
        lows.append(lo)
        highs.append(hi)
        rats.append(rat)

    out["heat_bound_low_factor"] = lows
    out["heat_bound_high_factor"] = highs
    out["heat_bound_rationale"] = rats
    base = pd.to_numeric(out["replaceable_heat_mwh_th"], errors="coerce")
    out["replaceable_heat_mwh_th_low"] = base * out["heat_bound_low_factor"]
    out["replaceable_heat_mwh_th_high"] = base * out["heat_bound_high_factor"]
    return out


def summarize(df: pd.DataFrame) -> None:
    w = pd.to_numeric(df["replaceable_heat_mwh_th"], errors="coerce").fillna(0.0)
    lo = pd.to_numeric(df["replaceable_heat_mwh_th_low"], errors="coerce").fillna(0.0)
    hi = pd.to_numeric(df["replaceable_heat_mwh_th_high"], errors="coerce").fillna(0.0)
    print(f"Fleet replaceable heat (TWh/y):")
    print(f"  low  {lo.sum()/1e6:7.1f}")
    print(f"  base {w.sum()/1e6:7.1f}")
    print(f"  high {hi.sum()/1e6:7.1f}")
    print("\nBy subsector (TWh/y):")
    rows = []
    for sub, g in df.groupby("subsector"):
        b = pd.to_numeric(g["replaceable_heat_mwh_th"], errors="coerce").fillna(0.0)
        rows.append({
            "subsector": sub,
            "n": len(g),
            "low": pd.to_numeric(g["replaceable_heat_mwh_th_low"], errors="coerce").fillna(0).sum() / 1e6,
            "base": b.sum() / 1e6,
            "high": pd.to_numeric(g["replaceable_heat_mwh_th_high"], errors="coerce").fillna(0).sum() / 1e6,
            "lo_x": g["heat_bound_low_factor"].iloc[0],
            "hi_x": g["heat_bound_high_factor"].iloc[0],
        })
    tab = pd.DataFrame(rows).sort_values("base", ascending=False)
    print(tab.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sites", type=Path, default=DEFAULT_SITES)
    ap.add_argument("--dry-run", action="store_true", help="Print summary; do not write")
    args = ap.parse_args()

    df = pd.read_csv(args.sites, low_memory=False)
    out = apply_bounds(df)
    summarize(out)
    if args.dry_run:
        print("\n(dry-run — not written)")
        return
    out.to_csv(args.sites, index=False)
    print(f"\nWrote bounds columns to {args.sites}")


if __name__ == "__main__":
    main()
