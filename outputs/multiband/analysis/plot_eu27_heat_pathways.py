"""EU-27 heat pathways summary table: 5 km vs 15 km.

Max heat served = highest availability with LCOH ≤ country gas heat price.
Max € savings = per-site floor maximizing served × (gas − LCOH).

    python outputs/multiband/analysis/plot_eu27_heat_pathways.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parent
OUT_STEM = "buffer_served_lcoh_gascap_vs_maxsavings_5km_15km"

GAS93 = 63.25 / 0.85 + (0.202 / 0.85) * 79
EURUSD = 1.08

# Okabe–Ito-adjacent neutrals for a clean table
HDR = "#0072B2"
ROW = "#3D5A80"
CELL = "#F4F6F8"
LINE = "#FFFFFF"
NOTE = "#555555"


def _fleet(demand: pd.Series, served: pd.Series, lcoh: pd.Series) -> tuple[float, float, float]:
    dem = float(demand.sum())
    srv = float(served.fillna(0).sum())
    avail = 100.0 * srv / dem if dem > 0 else float("nan")
    w = served.fillna(0)
    mask = (w > 0) & lcoh.notna()
    hw = float((lcoh[mask] * w[mask]).sum() / w[mask].sum()) if mask.any() else float("nan")
    return avail, srv / 1e6, hw


def max_heat_under_gas(km: int) -> tuple[float, float, float]:
    df = pd.read_csv(OUT / f"gas_capped_step90_{km}km.csv")
    return _fleet(
        pd.to_numeric(df["replaceable_heat_mwh_th"], errors="coerce"),
        pd.to_numeric(df["served_mwh"], errors="coerce"),
        pd.to_numeric(df["LCOH_served_eur_perMWh"], errors="coerce"),
    )


def max_savings(km: int) -> tuple[float, float, float]:
    long = pd.read_csv(OUT / f"fleet_availability_sweep_{km}km_long.csv", low_memory=False)
    if "status" in long.columns:
        long = long[long["status"] == "ok"].copy()
    long["heat"] = pd.to_numeric(long["replaceable_heat_mwh_th"], errors="coerce")
    long["rel"] = pd.to_numeric(long["Reliability_%"], errors="coerce")
    long["lcoh"] = pd.to_numeric(long["LCOH_served_eur_perMWh"], errors="coerce")
    if long["lcoh"].isna().all():
        long["lcoh"] = pd.to_numeric(long["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    long["served"] = long["heat"] * long["rel"] / 100.0
    long["surplus"] = long["served"] * (GAS93 - long["lcoh"])
    long = long.dropna(subset=["source_id", "surplus", "served", "lcoh"])
    best = long.loc[long.groupby("source_id")["surplus"].idxmax()]
    return _fleet(best["heat"], best["served"], best["lcoh"])


def main() -> None:
    rows_csv = []
    cell = {}
    for km in (5, 15):
        a_mh, t_mh, l_mh = max_heat_under_gas(km)
        a_ms, t_ms, l_ms = max_savings(km)
        cell[km] = {
            "served_mh": f"{a_mh:.1f}% ({t_mh:.0f} TWh)",
            "lcoh_mh": f"€{l_mh:.0f}/MWh",
            "served_ms": f"{a_ms:.1f}% ({t_ms:.0f} TWh)",
            "lcoh_ms": f"€{l_ms:.0f}/MWh",
        }
        rows_csv.append(
            {
                "buffer_km": km,
                "served_pct_max_heat": a_mh,
                "served_twh_max_heat": t_mh,
                "lcoh_max_heat": l_mh,
                "served_pct_max_savings": a_ms,
                "served_twh_max_savings": t_ms,
                "lcoh_max_savings": l_ms,
            }
        )
        print(f"{km} km  max-heat {a_mh:.1f}% / €{l_mh:.0f}   max-sav {a_ms:.1f}% / €{l_ms:.0f}")

    # Compact table body (4 data rows)
    row_labels = [
        "Max heat served — share",
        "Max heat served — LCOH",
        "Max € savings — share",
        "Max € savings — LCOH",
    ]
    keys = ["served_mh", "lcoh_mh", "served_ms", "lcoh_ms"]
    table = [[row_labels[i], cell[5][keys[i]], cell[15][keys[i]]] for i in range(4)]

    # Narrower figure; notes wrap to full width so sides are not empty
    fig, ax = plt.subplots(figsize=(5.8, 3.55))
    ax.axis("off")
    ax.set_title("EU-27 heat pathways", fontsize=13, fontweight="semibold", pad=10, color="#222")

    tbl = ax.table(
        cellText=table,
        colLabels=["", "5 km", "15 km"],
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9.5)
    tbl.scale(1.0, 1.55)

    for (r, c), cell_obj in tbl.get_celld().items():
        cell_obj.set_edgecolor(LINE)
        cell_obj.set_linewidth(1.2)
        if r == 0:
            cell_obj.set_facecolor(HDR)
            cell_obj.get_text().set_color("white")
            cell_obj.get_text().set_fontweight("bold")
            if c == 0:
                cell_obj.get_text().set_text("")
        elif c == 0:
            cell_obj.set_facecolor(ROW)
            cell_obj.get_text().set_color("white")
            cell_obj.get_text().set_fontweight("bold")
            cell_obj.get_text().set_ha("left")
            cell_obj.PAD = 0.04
        else:
            cell_obj.set_facecolor(CELL)
            cell_obj.get_text().set_color("#222")
            cell_obj.get_text().set_fontweight("bold" if r in (1, 3) else "normal")

        if c == 0:
            cell_obj.set_width(0.46)
        else:
            cell_obj.set_width(0.27)

    # Multi-line footnote matched to table width (reduces side white space)
    fig.text(
        0.5,
        0.08,
        "Max heat served = highest availability with LCOH ≤ country gas heat price\n"
        f"(fuel/η + EUA; EU avg ~€{GAS93:.0f}/MWh).\n"
        "Max € savings = per-site floor maximizing served × (gas − LCOH)\n"
        "at that EU-average gas heat cost.",
        ha="center",
        va="bottom",
        fontsize=7.0,
        color=NOTE,
        linespacing=1.3,
    )

    fig.subplots_adjust(left=0.06, right=0.94, top=0.84, bottom=0.28)
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT / f"{OUT_STEM}.pdf", bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)

    # Keep a simple 5/15 display CSV matching prior stem
    display = pd.DataFrame(
        {
            "metric": [
                "served_max_heat",
                "lcoh_max_heat",
                "served_max_savings",
                "lcoh_max_savings",
            ],
            "5km": [cell[5][k] for k in keys],
            "15km": [cell[15][k] for k in keys],
        }
    )
    display.to_csv(OUT / f"{OUT_STEM}.csv", index=False)
    pd.DataFrame(rows_csv).to_csv(OUT / f"{OUT_STEM}_numeric.csv", index=False)
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")


if __name__ == "__main__":
    main()
