"""EU industrial process-heat share by temperature (donut).

Remake of Agora / Fraunhofer ISI FORECAST pie (temperature bands only).

    python outputs/multiband/analysis/plot_eu_process_heat_temp_donut.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent
OUT_STEM = "eu_process_heat_by_temperature_donut"

SEGMENTS = [
    (">500 °C", 50, "#E878D8"),
    ("200–500 °C", 11, "#C9A0E8"),
    ("150–200 °C", 11, "#4A7FB8"),
    ("100–150 °C", 15, "#5AA8D4"),
    ("<100 °C", 13, "#5BCFE8"),
]

LEGEND_ORDER = [
    ("<100 °C", "#5BCFE8"),
    ("100–150 °C", "#5AA8D4"),
    ("150–200 °C", "#4A7FB8"),
    ("200–500 °C", "#C9A0E8"),
    (">500 °C", "#E878D8"),
]


def _crop_whitespace(path: Path, pad: int = 3) -> None:
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im)
    content = np.any(arr < 250, axis=2)
    rows = np.where(content.any(axis=1))[0]
    cols = np.where(content.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return
    r0, r1 = max(0, rows[0] - pad), min(arr.shape[0], rows[-1] + 1 + pad)
    c0, c1 = max(0, cols[0] - pad), min(arr.shape[1], cols[-1] + 1 + pad)
    Image.fromarray(arr[r0:r1, c0:c1]).save(path)


def main() -> None:
    labels = [s[0] for s in SEGMENTS]
    sizes = [s[1] for s in SEGMENTS]
    colors = [s[2] for s in SEGMENTS]

    fig = plt.figure(figsize=(4.2, 4.35), facecolor="white")
    # title / donut / legend+source — minimal hspace
    gs = fig.add_gridspec(
        3,
        1,
        height_ratios=[0.045, 1.0, 0.095],
        hspace=0.015,
        left=0.02,
        right=0.98,
        top=0.995,
        bottom=0.01,
    )

    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    ax_t.text(
        0.5,
        0.5,
        "EU industrial process heat by temperature",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="semibold",
        color="#222222",
        transform=ax_t.transAxes,
    )

    ax = fig.add_subplot(gs[1])
    ax.set_facecolor("white")
    _wedges, texts, _ = ax.pie(
        sizes,
        colors=colors,
        startangle=90,
        counterclock=True,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2.0),
        autopct=lambda pct: f"{pct:.0f}",
        pctdistance=0.78,
        textprops=dict(color="#222222", fontsize=10.5, fontweight="bold"),
    )
    for t in texts:
        t.set_visible(False)
    ax.text(
        0.0,
        0.0,
        "[%]",
        ha="center",
        va="center",
        fontsize=11,
        color="#666666",
        fontweight="semibold",
    )
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal")
    ax.axis("off")

    ax_b = fig.add_subplot(gs[2])
    ax_b.axis("off")
    leg = [
        mpatches.Patch(facecolor=c, edgecolor="white", linewidth=0.8, label=lab)
        for lab, c in LEGEND_ORDER
    ]
    ax_b.legend(
        handles=leg,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=5,
        frameon=False,
        fontsize=7.5,
        handlelength=0.8,
        columnspacing=0.55,
        handletextpad=0.25,
        borderaxespad=0.0,
    )
    ax_b.text(
        0.5,
        0.22,
        "Source: Fraunhofer ISI (2024) based on FORECAST model.",
        ha="center",
        va="center",
        fontsize=7.0,
        color="#555555",
        transform=ax_b.transAxes,
    )

    png = OUT / f"{OUT_STEM}.png"
    pdf = OUT / f"{OUT_STEM}.pdf"
    fig.savefig(png, dpi=200, facecolor="white")
    fig.savefig(pdf, facecolor="white")
    plt.close(fig)
    _crop_whitespace(png, pad=3)
    print(f"Wrote {png}")
    print("shares:", dict(zip(labels, sizes)), "sum", sum(sizes))


if __name__ == "__main__":
    main()
