"""Share of country process heat served: 5 km vs 15 km (2030 Li-ion + IHB + HP).

Bars = served / demand (%) from solar + storage (all sites; not a 90% filter).
Y-labels show country replaceable-heat demand.

    python outputs/multiband/analysis/plot_country_met90_5km_15km.py
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

COUNTRY_LABEL = {
    "AUT": "Austria",
    "BEL": "Belgium",
    "BGR": "Bulgaria",
    "HRV": "Croatia",
    "CYP": "Cyprus",
    "CZE": "Czechia",
    "DNK": "Denmark",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "DEU": "Germany",
    "GRC": "Greece",
    "HUN": "Hungary",
    "IRL": "Ireland",
    "ITA": "Italy",
    "LVA": "Latvia",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "NLD": "Netherlands",
    "POL": "Poland",
    "PRT": "Portugal",
    "ROU": "Romania",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "ESP": "Spain",
    "SWE": "Sweden",
    "GBR": "United Kingdom",
}

OUT_STEM = "country_met90_heat_share_5km_15km"


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
        for iso, g in ok.groupby("iso3_country", dropna=False):
            demand = float(g["heat"].sum())
            served = float(g["served"].sum())
            share = 100.0 * served / demand if demand > 0 else float("nan")
            rows.append(
                {
                    "iso3_country": iso,
                    "radius": col,
                    "served_pct": share,
                    "served_twh": served / 1e6,
                    "demand_twh": demand / 1e6,
                }
            )

    long = pd.DataFrame(rows)
    wide = (
        long.pivot(index="iso3_country", columns="radius", values="served_pct")
        .join(
            long.query("radius == '5km'")
            .set_index("iso3_country")[["demand_twh", "served_twh"]]
            .rename(columns={"served_twh": "served_twh_5km"})
        )
        .join(
            long.query("radius == '15km'")
            .set_index("iso3_country")[["served_twh"]]
            .rename(columns={"served_twh": "served_twh_15km"})
        )
        .reset_index()
        .sort_values("demand_twh")
    )
    # Top 6 by process-heat demand (ascending so largest is at top of barh)
    wide = wide.nlargest(6, "demand_twh").sort_values("demand_twh")
    wide.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(wide))
    h = 0.38
    ax.barh(y - h / 2, wide["5km"], height=h, color="#4C78A8", label="5 km")
    ax.barh(y + h / 2, wide["15km"], height=h, color="#F58518", label="15 km")
    ax.set_yticks(y)
    ax.set_yticklabels(
        [
            f"{COUNTRY_LABEL.get(s, s)}  ({r['demand_twh']:.0f} TWh)"
            if r["demand_twh"] >= 1
            else f"{COUNTRY_LABEL.get(s, s)}  ({r['demand_twh']:.1f} TWh)"
            for s, (_, r) in zip(wide["iso3_country"], wide.iterrows())
        ]
    )
    ax.set_xlabel("Share of country process heat served by solar + storage (%)")
    ax.set_title("Served process heat by country (2030 costs, Li-ion + IHB + HP)")
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
