"""Heat met by sector at the max-heat point, 5 km vs 15 km land buffer.

Sectors are grouped by how their heat is supplied: mostly heat battery (heat at or above 200 C)
or mostly heat pump (below 200 C, Li-ion storage limited to 4 h). More land lifts the heat-battery
sectors, while the heat-pump sectors stay near 50-58% because storage, not land, limits them.

    python outputs/multiband/analysis/plot_sector_heat_met_5km_15km.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OUT_STEM = "sector_heat_met_5km_15km"
sys.path.insert(0, str(OUT))
from operating_points import points  # noqa: E402

# Same encoding as the fleet figure (Okabe-Ito; marker shape as well as colour)
C5 = "#0072B2"
C15 = "#D55E00"
INK = "#222222"
MUTED = "#666666"
BANDS = ["heat_below100C_tj", "heat_100C-200C_tj", "heat_200C-500C_tj", "heat_500C-1000C_tj", "heat_above1000C_tj"]
NAMES = {
    "aluminum": "Aluminium",
    "cement": "Cement",
    "chemicals": "Chemicals",
    "food-beverage-tobacco": "Food and beverages",
    "glass": "Glass",
    "iron-and-steel": "Iron and steel",
    "lime": "Lime",
    "petrochemical-steam-cracking": "Steam cracking",
    "pulp-and-paper": "Pulp and paper",
    "textiles-leather-apparel": "Textiles",
}


def sector_table() -> pd.DataFrame:
    a = pd.read_csv(ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv", low_memory=False)
    a = a[a["has_solar_data"] & a["has_replaceable_heat"]]
    g = a.groupby("subsector")[BANDS].sum()
    t = pd.DataFrame({"hp_share": g[BANDS[:2]].sum(axis=1) / g.sum(axis=1)})
    for km in (5, 15):
        p = points(km).groupby("subsector")[["demand", "served_heat"]].sum()
        t[f"heat_{km}"] = 100 * p["served_heat"] / p["demand"]
        t["demand_twh"] = p["demand"] / 1e6
    t["group"] = (t["hp_share"] > 0.5).map({True: "Heat pump sectors (<200 °C)",
                                             False: "Heat battery sectors (≥200 °C)"})
    return t


def main() -> None:
    t = sector_table()
    t.round(2).to_csv(OUT / f"{OUT_STEM}.csv")
    groups = ["Heat battery sectors (≥200 °C)", "Heat pump sectors (<200 °C)"]

    # Rows top to bottom: heat-battery group, gap, heat-pump group, each sorted by 15 km share
    order, ypos, headers, y = [], [], [], 0.0
    for gname in groups:
        g = t[t["group"] == gname].sort_values("heat_15", ascending=False)
        headers.append((gname, y))
        y += 1.0
        for sec in g.index:
            order.append(sec)
            ypos.append(y)
            y += 1.0
        y += 0.4
    fig, ax = plt.subplots(figsize=(3.44, 3.0), layout="constrained")
    for sec, yy in zip(order, ypos):
        r = t.loc[sec]
        ax.plot([r["heat_5"], r["heat_15"]], [yy, yy], color="#bbbbbb", lw=1.2, zorder=1)
        ax.plot(r["heat_5"], yy, "o", color=C5, ms=4.5, zorder=3)
        ax.plot(r["heat_15"], yy, "s", color=C15, ms=4.5, zorder=3)
        ax.annotate(f"{r['heat_15']:.0f}%", (r["heat_15"], yy), textcoords="offset points", xytext=(5, 0),
                    ha="left", va="center", fontsize=5.5, color=INK)
        if r["heat_15"] - r["heat_5"] > 8:  # 5 km value only where the two points are apart
            ax.annotate(f"{r['heat_5']:.0f}%", (r["heat_5"], yy), textcoords="offset points", xytext=(-5, 0),
                        ha="right", va="center", fontsize=5.5, color=INK)
    for gname, yy in headers:
        ax.text(0, yy, gname, fontsize=6.5, fontweight="bold", color=INK, va="center", ha="left",
                transform=ax.get_yaxis_transform())
    ax.set_yticks(ypos, [""] * len(ypos))
    for s_, yy in zip(order, ypos):  # sector name with its demand just below, centred on the row
        ax.annotate(NAMES[s_], (0, yy), xycoords=("axes fraction", "data"), textcoords="offset points",
                    xytext=(-4, 2.5), ha="right", va="bottom", fontsize=6.5, color=INK, annotation_clip=False)
        ax.annotate(f"{t.loc[s_, 'demand_twh']:.0f} TWh", (0, yy), xycoords=("axes fraction", "data"),
                    textcoords="offset points", xytext=(-4, 1.5), ha="right", va="top", fontsize=5,
                    color=MUTED, annotation_clip=False)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Heat met below country gas cost (%)", fontsize=8, labelpad=2)
    ax.tick_params(axis="x", labelsize=7)
    ax.tick_params(axis="y", length=0)
    ax.grid(True, axis="x", ls=":", alpha=0.35, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    leg = [
        Line2D([0], [0], marker="o", ls="", color=C5, ms=4.5, label="5 km"),
        Line2D([0], [0], marker="s", ls="", color=C15, ms=4.5, label="15 km"),
    ]
    ax.legend(handles=leg, loc="lower right", frameon=False, fontsize=6.5, handletextpad=0.2, borderaxespad=0.2)

    png = OUT / f"{OUT_STEM}.png"
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT / f"{OUT_STEM}.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(t[["hp_share", "heat_5", "heat_15", "demand_twh"]].round(1).to_string())
    print(f"Wrote {png}")


if __name__ == "__main__":
    main()
