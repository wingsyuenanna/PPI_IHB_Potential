"""Share of sector process heat served: 5 km vs 15 km (2030 Li-ion + IHB + HP).

Bars = served / demand (%) from solar + storage (all sites; not a 90% filter).
Y-labels show sector replaceable-heat demand.

    python outputs/multiband/analysis/plot_sector_met90_5km_15km.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

S5 = "land_5km_ss_2030_liion"
S15 = "land_15km_ss_2030_liion"

# Climate TRACE subsector IDs → display labels (CT-style wording)
SECTOR_LABEL = {
    "petrochemical-steam-cracking": "Petrochemical steam cracking",
    "iron-and-steel": "Iron and steel",
    "cement": "Cement",
    "lime": "Lime",
    "glass": "Glass",
    "chemicals": "Chemicals",
    "aluminum": "Aluminum",
    "food-beverage-tobacco": "Food, beverage, and tobacco",
    "textiles-leather-apparel": "Textiles, leather, and apparel",
    "pulp-and-paper": "Pulp and paper",
    "other-metals": "Other metals",
}

OUT_STEM = "sector_met90_heat_share_5km_15km"  # keep path stable for open editors


def load_ok(scenario: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / f"outputs/multiband/{scenario}/by_facility.csv")
    ok = df[df["status"] == "ok"].copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["rel"] = pd.to_numeric(ok["Reliability_%"], errors="coerce")
    ok["served"] = ok["rel"] / 100.0 * ok["heat"]
    return ok


def main() -> None:
    rows = []
    for scen, col in [(S15, "15km"), (S5, "5km")]:
        ok = load_ok(scen)
        for sub, g in ok.groupby("subsector", dropna=False):
            demand = float(g["heat"].sum())
            served = float(g["served"].sum())
            share = 100.0 * served / demand if demand > 0 else float("nan")
            rows.append(
                {
                    "subsector": sub,
                    "radius": col,
                    "served_pct": share,
                    "served_twh": served / 1e6,
                    "demand_twh": demand / 1e6,
                }
            )

    long = pd.DataFrame(rows)
    wide = (
        long.pivot(index="subsector", columns="radius", values="served_pct")
        .join(
            long.query("radius == '5km'")
            .set_index("subsector")[["demand_twh", "served_twh"]]
            .rename(columns={"served_twh": "served_twh_5km"})
        )
        .join(
            long.query("radius == '15km'")
            .set_index("subsector")[["served_twh"]]
            .rename(columns={"served_twh": "served_twh_15km"})
        )
        .reset_index()
        .sort_values("demand_twh")
    )
    wide = wide[wide["demand_twh"] >= 0.5].copy()
    wide.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 5.8))
    y = np.arange(len(wide))
    h = 0.38
    ax.barh(y - h / 2, wide["5km"], height=h, color="#4C78A8", label="5 km")
    ax.barh(y + h / 2, wide["15km"], height=h, color="#F58518", label="15 km")
    ax.set_yticks(y)
    ax.set_yticklabels(
        [
            f"{SECTOR_LABEL.get(s, s)}  ({r['demand_twh']:.0f} TWh)"
            for s, (_, r) in zip(wide["subsector"], wide.iterrows())
        ]
    )
    ax.set_xlabel("Share of sector process heat served by solar + storage (%)")
    ax.set_title("Served process heat by Climate TRACE sector (2030 costs, Li-ion + IHB + HP)")
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, len(wide) - 0.4)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=False,
    )
    fig.tight_layout()
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")
    print(wide.to_string(index=False, float_format=lambda x: f"{x:.1f}"))


if __name__ == "__main__":
    main()
