"""Heatmap of hotmaps industry-benchmark process heat by temperature band.

Visualizes Input/industryBenchmarks_2014.csv — the per-process recipe table
that heat_demand/facilities/heat_temperature_bands.py uses to split each
facility's heat demand into temperature bands. One row per benchmark process,
grouped by subsector; cell = share of that process's heat in each band.

    python outputs/multiband/analysis/plot_industry_benchmark_heat_bands.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BENCHMARKS = ROOT / "Input" / "industryBenchmarks_2014.csv"

BANDS = [
    "Process_heat_below100C",
    "Process_heat_100C-200C",
    "Process_heat_200C-500C",
    "Process_heat_500C-1000C",
    "Process_heat_above1000C",
]
BAND_LABELS = ["<100°C", "100–200°C", "200–500°C", "500–1000°C", ">1000°C"]

# Single-hue sequential ramp (light -> dark), colorblind-safe (monotonic lightness).
CMAP = LinearSegmentedColormap.from_list("heat_seq", ["#fff3e6", "#fcae72", "#e4572e", "#9e1f1f"])

INK = "#1a1a1a"
MUTED = "#6b6b6b"


def main() -> None:
    df = pd.read_csv(BENCHMARKS)
    df[BANDS] = df[BANDS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    df["row_sum"] = df[BANDS].sum(axis=1)
    df = df[df["row_sum"] > 0].copy()

    # Weighted mean band index (0..4) for a low->high temperature sort within subsector.
    band_idx = np.arange(len(BANDS))
    df["mean_band"] = (df[BANDS].to_numpy() * band_idx).sum(axis=1) / df["row_sum"]

    subsector_order = df.groupby("Subsector")["row_sum"].count().sort_values(ascending=False).index.tolist()
    df["Subsector"] = pd.Categorical(df["Subsector"], categories=subsector_order, ordered=True)
    df = df.sort_values(["Subsector", "mean_band"]).reset_index(drop=True)

    n = len(df)
    mat = df[BANDS].to_numpy()
    labels = df["Process"].tolist()
    subsectors = df["Subsector"].tolist()

    fig_h = 0.235 * n + 1.6
    fig, ax = plt.subplots(figsize=(8.8, fig_h))

    im = ax.imshow(mat, aspect="auto", cmap=CMAP, vmin=0, vmax=1, interpolation="nearest")

    # Cell gaps (2px surface gap convention) via white grid lines.
    ax.set_xticks(np.arange(len(BANDS) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(n + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", length=0)

    ax.set_xticks(range(len(BANDS)))
    ax.set_xticklabels(BAND_LABELS, fontsize=9, color=INK)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")

    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=7.2, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Direct value labels on non-trivial cells; ink flips for contrast.
    for i in range(n):
        for j in range(len(BANDS)):
            v = mat[i, j]
            if v < 0.12:
                continue
            txt_color = "white" if v > 0.55 else INK
            ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=6.3, color=txt_color)

    # Subsector dividers (left margin) + labels placed in figure space so they
    # never collide with the process-name tick labels.
    fig.canvas.draw()
    inv = fig.transFigure.inverted()
    prev = subsectors[0]
    start = 0
    for i in range(1, n + 1):
        cur = subsectors[i] if i < n else None
        if cur != prev:
            ax.axhline(i - 0.5, color=INK, linewidth=0.9, xmin=-0.62, clip_on=False)
            mid = (start + i - 1) / 2
            _, y_fig = inv.transform(ax.transData.transform((0, mid)))
            fig.text(0.01, y_fig, prev, ha="left", va="center", fontsize=8.5,
                      color=INK, fontweight="bold")
            start = i
            prev = cur

    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, shrink=0.5)
    cb.set_label("Share of process heat", fontsize=8, color=MUTED)
    cb.ax.tick_params(labelsize=7, color=MUTED)
    cb.outline.set_visible(False)

    ax.set_title(
        "Industrial process heat by temperature — hotmaps benchmark processes",
        fontsize=12.5, color=INK, loc="left", pad=14, x=-0.42,
    )
    fig.text(
        0.01, 0.005,
        "Source: hotmaps industryBenchmarks_2014.csv (per-process citations in file). "
        "Used by heat_demand/facilities/heat_temperature_bands.py to band facility heat demand.",
        fontsize=7, color=MUTED,
    )

    fig.subplots_adjust(left=0.48, right=0.86, top=1 - 1.1 / fig_h, bottom=0.25 / fig_h)
    fig.savefig(OUT / "industry_benchmark_heat_bands.png", dpi=200, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"Wrote {OUT / 'industry_benchmark_heat_bands.png'}  ({n} processes)")


if __name__ == "__main__":
    main()
