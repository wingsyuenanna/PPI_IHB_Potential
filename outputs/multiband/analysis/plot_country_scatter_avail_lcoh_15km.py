"""Country scatter: heat-weighted availability vs LCOH (15 km, gas-capped).

Per-site availability chosen so LCOH ≤ country gas boiler heat cost.

    python outputs/multiband/analysis/plot_country_scatter_avail_lcoh_15km.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
GAS_CAPPED = OUT / "gas_capped_step90_15km.csv"
OUT_STEM = "country_scatter_avail_lcoh_15km"

LABEL = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI",
    "ESP": "ES", "SWE": "SE", "GBR": "UK",
}
NORDIC = {"SWE", "FIN", "DNK", "EST", "LVA", "LTU"}
SOUTH = {"ESP", "PRT", "ITA", "GRC", "CYP"}


def color(iso: str) -> str:
    if iso in NORDIC:
        return "#d62728"
    if iso in SOUTH:
        return "#2ca02c"
    return "#4C78A8"


def main() -> None:
    df = pd.read_csv(GAS_CAPPED)
    ok = df[df["status"] == "ok"].copy() if "status" in df.columns else df.copy()
    ok["heat"] = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
    ok["served"] = pd.to_numeric(ok["served_mwh"], errors="coerce")
    ok["lcoh"] = pd.to_numeric(ok["LCOH_served_eur_perMWh"], errors="coerce")

    rows = []
    for iso, g in ok.groupby("iso3_country"):
        demand = float(g["heat"].sum())
        served = float(g["served"].fillna(0).sum())
        mask = g["served"].fillna(0) > 0
        lcoh = (
            float((g.loc[mask, "lcoh"] * g.loc[mask, "served"]).sum() / g.loc[mask, "served"].sum())
            if mask.any()
            else np.nan
        )
        rows.append(
            {
                "iso3": iso,
                "demand_twh": demand / 1e6,
                "served_twh": served / 1e6,
                "avail": 100.0 * served / demand,
                "lcoh": lcoh,
                "n_sites": len(g),
            }
        )
    agg = pd.DataFrame(rows).sort_values("demand_twh", ascending=False)
    agg.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    plot = agg[agg["demand_twh"] >= 0.5].copy()
    outliers = agg[agg["demand_twh"] < 0.5]
    fleet_avail = 100.0 * ok["served"].fillna(0).sum() / ok["heat"].sum()
    w = ok["served"].fillna(0)
    mask = w > 0
    fleet_lcoh = float((ok.loc[mask, "lcoh"] * w[mask]).sum() / w[mask].sum())

    ymax = float(np.ceil(plot["lcoh"].max() / 5) * 5) + 5
    ymax = max(ymax, 110.0)

    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    for _, r in plot.iterrows():
        ax.scatter(
            r["avail"],
            r["lcoh"],
            s=40 + 18 * r["demand_twh"],
            c=color(r["iso3"]),
            alpha=0.85,
            edgecolors="white",
            linewidths=0.8,
            zorder=3,
        )

    label_set = set(plot.nlargest(10, "demand_twh")["iso3"]) | (NORDIC & set(plot["iso3"])) | (
        SOUTH & set(plot["iso3"])
    )
    for _, r in plot.iterrows():
        if r["iso3"] not in label_set:
            continue
        ax.annotate(
            LABEL.get(r["iso3"], r["iso3"]),
            (r["avail"], r["lcoh"]),
            textcoords="offset points",
            xytext=(5, 4),
            fontsize=8,
            fontweight="bold" if r["iso3"] in NORDIC | SOUTH else "normal",
            color="#222",
        )

    ax.axvline(fleet_avail, color="#888", ls=":", lw=1, zorder=1)
    ax.axhline(fleet_lcoh, color="#888", ls=":", lw=1, zorder=1)

    leg = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#d62728", markersize=8, label="Nordic / Baltic"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ca02c", markersize=8, label="Southern Europe"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#4C78A8", markersize=8, label="Other"),
    ]
    ax.legend(handles=leg, frameon=False, loc="lower left", fontsize=8, borderaxespad=0.8)

    ax.set_xlabel("Heat served / demand (%)", fontsize=10)
    ax.set_ylabel("LCOH of served heat (€/MWh)", fontsize=10)
    ax.set_title(
        "Country trade-off — 15 km, gas-capped (LCOH ≤ country gas)",
        fontsize=11,
    )
    ax.set_xlim(max(65.0, float(plot["avail"].min()) - 2), 97)
    ax.set_ylim(25, ymax)
    ax.grid(True, ls=":", alpha=0.5, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    excl = ", ".join(f"{LABEL.get(r.iso3, r.iso3)} (€{r.lcoh:.0f})" for _, r in outliers.iterrows())
    fig.subplots_adjust(left=0.10, right=0.98, top=0.90, bottom=0.16)
    fig.text(
        0.5,
        0.02,
        "Bubble size ∝ national process-heat demand.  Per-site availability stepped from 90% so LCOH ≤ country gas.\n"
        f"Dotted lines: fleet averages ({fleet_avail:.0f}%, €{fleet_lcoh:.0f}/MWh).  "
        f"Excluded <0.5 TWh: {excl}.",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color="#555",
        linespacing=1.35,
    )

    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")


if __name__ == "__main__":
    main()
