"""Fleet served share: 90% availability floor vs gas-capped (5 km & 15 km).

Shows that imposing LCOH ≤ country gas barely moves 5 km results.

    python outputs/multiband/analysis/plot_gas_vs_floor_served_share.py
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
OUT_STEM = "gas_vs_floor_served_share"
EURUSD = 1.08

SCENARIOS = {
    5: ROOT / "outputs/multiband/land_5km_ss_2030_liion/by_facility.csv",
    15: ROOT / "outputs/multiband/land_15km_ss_2030_liion/by_facility.csv",
}
GAS = {
    5: ROOT / "outputs/multiband/analysis/gas_capped_step90_5km.csv",
    15: ROOT / "outputs/multiband/analysis/gas_capped_step90_15km.csv",
}


def floor_share(path: Path) -> tuple[float, float, float]:
    df = pd.read_csv(path)
    heat = pd.to_numeric(df["replaceable_heat_mwh_th"], errors="coerce")
    rel = pd.to_numeric(df["Reliability_%"], errors="coerce")
    served = rel / 100.0 * heat
    return float(served.sum() / 1e6), float(heat.sum() / 1e6), float(100 * served.sum() / heat.sum())


def gas_share(path: Path) -> tuple[float, float, float]:
    df = pd.read_csv(path)
    heat = pd.to_numeric(df["replaceable_heat_mwh_th"], errors="coerce")
    served = pd.to_numeric(df["served_mwh"], errors="coerce").fillna(0.0)
    return float(served.sum() / 1e6), float(heat.sum() / 1e6), float(100 * served.sum() / heat.sum())


def main() -> None:
    rows = []
    for km in (5, 15):
        s_f, d_f, p_f = floor_share(SCENARIOS[km])
        s_g, d_g, p_g = gas_share(GAS[km])
        rows.append(
            {
                "buffer_km": km,
                "floor_pct": p_f,
                "gas_pct": p_g,
                "floor_twh": s_f,
                "gas_twh": s_g,
                "demand_twh": d_f,
                "delta_pp": p_g - p_f,
            }
        )
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    x = np.arange(len(tab))
    w = 0.36
    b1 = ax.bar(
        x - w / 2,
        tab["floor_pct"],
        w,
        label="90% availability floor",
        color="#4C78A8",
        zorder=3,
    )
    b2 = ax.bar(
        x + w / 2,
        tab["gas_pct"],
        w,
        label="Gas-capped (LCOH ≤ country gas)",
        color="#F58518",
        zorder=3,
    )

    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 1.2,
                f"{h:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color="#333",
            )

    # Delta annotations
    for i, r in tab.iterrows():
        y = max(r["floor_pct"], r["gas_pct"]) + 6
        ax.annotate(
            f"Δ {r['delta_pp']:+.1f} pp\n({r['gas_twh']:.0f} vs {r['floor_twh']:.0f} TWh)",
            xy=(i, y),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#555",
        )

    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(k)} km land buffer" for k in tab["buffer_km"]])
    ax.set_ylabel("Fleet process heat served (%)")
    ax.set_ylim(0, 110)
    ax.set_title(
        "Gas cost constraint barely changes 5 km results\n"
        "(fleet heat-weighted served share, 2030 costs)"
    )
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    ax.yaxis.grid(True, ls=":", alpha=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT / f'{OUT_STEM}.png'}")
    print(tab.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
