"""EU-27 industrial heat pathways bar chart (2025 Eurostat prices).

Operating LCOH only: gas boiler (fuel/η + EUA) vs industrial heat battery
on grid electricity.

    python outputs/multiband/analysis/plot_eu_industrial_lcoh_elec_vs_gas_2025.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = Path(__file__).resolve().parent
OUT_STEM = "eu_industrial_lcoh_elec_vs_gas_2025"

# Eurostat 2025 EU-27 industrial (nrg_pc_205 / nrg_pc_203, X_VAT)
ELEC = 162.0  # €/MWh
GAS = 63.25  # €/MWh (matches GAS93 construction used elsewhere)
ETA = 0.85
EUA = 79.0  # €/tCO2
EF_GAS = 0.202  # tCO2 / MWh_fuel
RTE = 0.95

# Shared palette (also used on LCOH–availability plot)
# Gas purple · grid elec medium gray · 15 km vermillion on hockey stick
C_GAS_FUEL = "#6A3D9A"
C_GAS_CO2 = "#C9B1E0"
C_BATT = "#949494"
C_NOTE = "#555555"


def main() -> None:
    gas_fuel = GAS / ETA
    gas_co2 = (EF_GAS / ETA) * EUA
    gas_tot = gas_fuel + gas_co2
    batt = ELEC / RTE

    labels = [
        "Natural gas\nboiler",
        "Industrial heat\nbattery",
    ]
    totals = [gas_tot, batt]
    delta_batt = batt - gas_tot

    fig, ax = plt.subplots(figsize=(6.2, 5.0))
    x = np.arange(len(labels))
    w = 0.55

    ax.bar(x[0], gas_fuel, width=w, color=C_GAS_FUEL, zorder=3)
    ax.bar(x[0], gas_co2, width=w, bottom=gas_fuel, color=C_GAS_CO2, zorder=3)
    ax.bar(x[1], batt, width=w, color=C_BATT, zorder=3)

    ax.axhline(gas_tot, color="#666666", ls="--", lw=1.2, zorder=2)

    for i, tot in enumerate(totals):
        ax.text(
            x[i],
            tot + 4,
            f"{tot:.0f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color="#222",
        )

    ax.text(
        x[0],
        gas_fuel + gas_co2 / 2,
        f"+{gas_co2:.0f} CO₂",
        ha="center",
        va="center",
        fontsize=7.5,
        color="#333",
        fontweight="bold",
    )

    def add_bracket(i: int, y_lo: float, y_hi: float, label: str) -> None:
        xb = x[i] - w / 2 - 0.08
        tick = 0.06
        ax.plot([xb, xb], [y_lo, y_hi], color="#444", lw=1.1, clip_on=False, zorder=4)
        ax.plot([xb, xb + tick], [y_lo, y_lo], color="#444", lw=1.1, clip_on=False, zorder=4)
        ax.plot([xb, xb + tick], [y_hi, y_hi], color="#444", lw=1.1, clip_on=False, zorder=4)
        ax.text(
            xb - 0.04,
            0.5 * (y_lo + y_hi),
            label,
            ha="right",
            va="center",
            fontsize=8,
            color="#333",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#bbb", lw=0.6),
            zorder=5,
        )

    add_bracket(1, gas_tot, batt, f"{delta_batt:+.0f} €/MWh")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("LCOH — operating cost of heat (€/MWh_th)", fontsize=10)
    ax.set_ylim(0, 200)
    ax.set_xlim(-0.55, 1.55)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", ls=":", alpha=0.35, zorder=0)
    ax.tick_params(axis="x", length=0, pad=4)

    leg = [
        mpatches.Patch(facecolor=C_GAS_FUEL, label=f"Gas fuel ÷ {ETA:g}"),
        mpatches.Patch(facecolor=C_GAS_CO2, label=f"EUA carbon ({EUA:.0f} €/tCO₂)"),
        mpatches.Patch(facecolor=C_BATT, label=f"Grid electricity ÷ {RTE:g} RTE"),
    ]

    # Title + horizontal legend stacked above the axes
    fig.suptitle(
        "EU-27 Grid electricity vs natural gas boiler LCOH 2025",
        fontsize=12,
        fontweight="semibold",
        y=0.98,
    )
    fig.legend(
        handles=leg,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.935),
        ncol=3,
        frameon=False,
        fontsize=8,
        columnspacing=1.4,
        handlelength=1.2,
    )

    fig.text(
        0.5,
        0.02,
        f"Eurostat 2025 EU-27 industrial — electricity €{ELEC:.0f}/MWh, gas €{GAS:.0f}/MWh.\n"
        f"Gas = price/{ETA:g} + ({EF_GAS} tCO₂/MWh_fuel)/{ETA:g} × €{EUA:.0f}/t.  "
        f"Industrial heat battery = grid elec/{RTE:g} RTE.\n"
        "Energy operating cost only (no CAPEX).  Bracket shows Δ vs gas boiler.",
        ha="center",
        va="bottom",
        fontsize=7.0,
        color=C_NOTE,
        linespacing=1.3,
    )

    fig.subplots_adjust(left=0.12, right=0.96, top=0.82, bottom=0.18)
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(OUT / f"{OUT_STEM}.pdf", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")
    print(
        f"gas {gas_tot:.0f} (fuel {gas_fuel:.0f} + CO2 {gas_co2:.0f}) | "
        f"batt {batt:.0f} (grid elec/{RTE:g})"
    )


if __name__ == "__main__":
    main()
