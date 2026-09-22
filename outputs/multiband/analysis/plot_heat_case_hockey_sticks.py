"""Hockey-stick LCOH vs availability for heat demand low / base / high.

X = fleet heat-weighted availability (served / demand).
Y = heat-weighted LCOH (€/MWh served).
Dots = availability floor targets (10–100%).

Uses:
  fleet_availability_sweep_{5,15}km_by_floor.csv              (base)
  fleet_availability_sweep_{5,15}km_heat_{low,high}_by_floor.csv

    python outputs/multiband/analysis/plot_heat_case_hockey_sticks.py
    python outputs/multiband/analysis/plot_heat_case_hockey_sticks.py --land-km 15
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parent
OUT_STEM = "heat_case_hockey_sticks_lcoh_availability"

CASE_STYLE = {
    "low": {"color": "#009E73", "marker": "o", "label": "Low demand (388 TWh)", "lw": 2.0},
    "base": {"color": "#0072B2", "marker": "s", "label": "Base (522 TWh)", "lw": 2.0},
    "high": {"color": "#D55E00", "marker": "^", "label": "High demand (697 TWh)", "lw": 2.0},
}
EURUSD = 1.08
YMAX = 160.0  # clip 100%-floor spikes for readability


def load_curve(land_km: int, heat_case: str) -> pd.DataFrame | None:
    if heat_case == "base":
        path = OUT / f"fleet_availability_sweep_{land_km}km_by_floor.csv"
    else:
        path = OUT / f"fleet_availability_sweep_{land_km}km_heat_{heat_case}_by_floor.csv"
    if not path.is_file():
        return None
    df = pd.read_csv(path)
    df["heat_case"] = heat_case
    df["buffer_km"] = land_km
    # Prefer €; fall back if only $ present in older files
    if "hw_LCOH_eur" not in df.columns and "hw_LCOH" in df.columns:
        df["hw_LCOH_eur"] = pd.to_numeric(df["hw_LCOH"], errors="coerce")
    return df


def plot_panel(ax, land_km: int, curves: dict[str, pd.DataFrame]) -> None:
    for case, st in CASE_STYLE.items():
        if case not in curves:
            continue
        c = curves[case].sort_values("served_pct")
        y = c["hw_LCOH_eur"].clip(upper=YMAX)
        ax.plot(
            c["served_pct"],
            y,
            color=st["color"],
            marker=st["marker"],
            ms=6,
            lw=st["lw"],
            label=st["label"],
            zorder=3,
        )
        # annotate 90% floor point
        near90 = c.iloc[(c["availability_floor"] - 0.9).abs().argmin()]
        if float(near90["hw_LCOH_eur"]) <= YMAX:
            ax.annotate(
                "90%",
                (near90["served_pct"], min(float(near90["hw_LCOH_eur"]), YMAX)),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=7,
                color=st["color"],
            )

    ax.set_xlabel("Heat-weighted availability (% served / demand)")
    ax.set_xlim(0, 100)
    ax.set_ylim(20, YMAX)
    ax.set_title(f"{land_km} km land buffer", fontsize=11, loc="left")
    ax.grid(True, ls=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--land-km", type=int, nargs="*", default=[5, 15], choices=[5, 15])
    args = ap.parse_args()
    land_kms = list(dict.fromkeys(args.land_km))  # preserve order, unique

    all_rows = []
    panels: dict[int, dict[str, pd.DataFrame]] = {}
    for km in land_kms:
        curves = {}
        for case in CASE_STYLE:
            c = load_curve(km, case)
            if c is not None:
                curves[case] = c
                all_rows.append(c)
        panels[km] = curves
        missing = [c for c in CASE_STYLE if c not in curves]
        if missing:
            print(f"{km} km: missing heat cases {missing} — run fleet_availability_sweep_heat_cases.py")

    if not all_rows:
        raise SystemExit("No by_floor curves found.")

    pd.concat(all_rows, ignore_index=True).to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    n = len(land_kms)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n, 4.4), sharey=True, squeeze=False)
    for ax, km in zip(axes[0], land_kms):
        plot_panel(ax, km, panels[km])
    axes[0][0].set_ylabel("Heat-weighted LCOH (€/MWh served)")
    axes[0][0].legend(frameon=False, loc="upper left", fontsize=8)

    fig.suptitle(
        "Heat-demand sensitivity · LCOH vs availability (floor sweep)",
        fontsize=12,
        fontweight="semibold",
    )
    fig.tight_layout()
    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=180)
    fig.savefig(OUT / f"{OUT_STEM}.pdf")
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")
    print(f"Wrote {OUT / (OUT_STEM + '.pdf')}")
    print(f"Wrote {OUT / (OUT_STEM + '.csv')}")


if __name__ == "__main__":
    main()
