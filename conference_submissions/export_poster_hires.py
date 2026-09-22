#!/usr/bin/env python3
"""Re-export W&S poster charts at print resolution and rebuild the PPTX.

Poster slots are large (A0). Effective DPI = pixels / on-slide inches.
Target ≥200 DPI of the displayed size so PDF export still clears 150 DPI.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "outputs" / "multiband" / "analysis"
OUT = Path(__file__).resolve().parent / "poster_figures"
SRC_PPTX = Path(__file__).resolve().parent / "W&S_Integration_poster_final.pptx"
DST_PPTX = Path(__file__).resolve().parent / "W&S_Integration_poster_final_v2.pptx"
SRC_PDF = Path(__file__).resolve().parent / "W&S_Integration_poster_final.pdf"
DST_PDF = Path(__file__).resolve().parent / "W&S_Integration_poster_final_v2.pdf"

# Pixel size of each chart in the original Quartz PDF (defines the PDF image box).
PDF_BOX_PX = {
    "country": (1294, 1344),
    "fleet": (916, 603),
    "bar": (916, 766),
    "donut": (733, 854),
    "steel": (1833, 878),
}

# On-slide size of each picture (inches), from the final PPTX.
DISPLAY_IN = {
    "country": (15.78, 15.53),  # image1
    "fleet": (14.14, 8.83),  # image7
    "bar": (8.32, 7.06),  # image8
    "donut": (6.09, 7.06),  # image9
    "steel": (16.29, 7.35),  # image10
}
MEDIA = {
    "country": "ppt/media/image1.png",
    "fleet": "ppt/media/image7.png",
    "bar": "ppt/media/image8.png",
    "donut": "ppt/media/image9.png",
    "steel": "ppt/media/image10.png",
}
TARGET_DPI = 220  # headroom over the 150 DPI floor
RENDER_DPI = 420  # matplotlib save dpi; bbox-tight output is smaller than figsize

GAS93 = 63.25 / 0.85 + (0.202 / 0.85) * 79
ELEC171 = 162.0 / 0.95
EURUSD = 1.08
C5 = "#0072B2"
C15 = "#F58518"
C_MS = "#009E73"
C_MH = "#CC79A7"
C_GAS = "#6A3D9A"
C_ELEC = "#949494"
C_GAS_FUEL = "#6A3D9A"
C_GAS_CO2 = "#C9B1E0"
C_BATT = "#949494"


def load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def flatten_white_png(path: Path, dpi: int) -> None:
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[-1])
    bg.save(path, dpi=(dpi, dpi), optimize=True)


def pad_to_aspect(path: Path, aspect_w_over_h: float, dpi: int) -> None:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    current = w / h
    if abs(current - aspect_w_over_h) / aspect_w_over_h < 0.008:
        im.save(path, dpi=(dpi, dpi), optimize=True)
        return
    if current > aspect_w_over_h:
        new_h = int(round(w / aspect_w_over_h))
        canvas = Image.new("RGB", (w, new_h), (255, 255, 255))
        canvas.paste(im, (0, (new_h - h) // 2))
    else:
        new_w = int(round(h * aspect_w_over_h))
        canvas = Image.new("RGB", (new_w, h), (255, 255, 255))
        canvas.paste(im, ((new_w - w) // 2, 0))
    canvas.save(path, dpi=(dpi, dpi), optimize=True)


def ensure_min_pixels(path: Path, min_w: int, min_h: int, dpi: int) -> None:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    scale = max(min_w / w, min_h / h, 1.0)
    if scale > 1.001:
        im = im.resize((int(round(w * scale)), int(round(h * scale))), Image.Resampling.LANCZOS)
    im.save(path, dpi=(dpi, dpi), optimize=True)


def finish_variant(src: Path, dest: Path, key: str, aspect: float, min_w: int, min_h: int, label: str) -> None:
    shutil.copyfile(src, dest)
    pad_to_aspect(dest, aspect, TARGET_DPI)
    ensure_min_pixels(dest, min_w, min_h, TARGET_DPI)
    im = Image.open(dest)
    print(f"  {label} {dest.name}: {im.size[0]}×{im.size[1]}")


def finish(path: Path, key: str) -> tuple[Path, Path]:
    """Return (pptx_png, pdf_png) padded to the correct box so neither target stretches."""
    flatten_white_png(path, TARGET_DPI)
    w_in, h_in = DISPLAY_IN[key]
    pptx_png = path.with_name(path.stem + "_pptx.png")
    pdf_png = path.with_name(path.stem + "_pdf.png")
    pw, ph = PDF_BOX_PX[key]
    finish_variant(path, pptx_png, key, w_in / h_in, int(w_in * TARGET_DPI), int(h_in * TARGET_DPI), "pptx")
    finish_variant(path, pdf_png, key, pw / ph, int(w_in * TARGET_DPI), int(h_in * TARGET_DPI), "pdf")
    return pptx_png, pdf_png


def plot_fleet(fleet, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 5.05))
    style = {
        5: {"color": C5, "ls": "-", "marker": "o", "ms": 5.5},
        15: {"color": C15, "ls": "--", "marker": "s", "ms": 5.5},
    }
    for km in (5, 15):
        c = fleet.load_curve(km).sort_values("served_pct")
        st = style[km]
        ax.plot(
            c["served_pct"], c["hw_LCOH_eur"],
            color=st["color"], ls=st["ls"], marker=st["marker"],
            ms=st["ms"], lw=2.0, zorder=2,
        )
        end = c.iloc[-1]
        ax.annotate(
            f'{end["hw_LCOH_eur"]:.0f}',
            (end["served_pct"], end["hw_LCOH_eur"]),
            textcoords="offset points", xytext=(4, 4),
            fontsize=8, fontweight="bold", color=st["color"],
        )
        a_ms, l_ms = fleet.max_savings_point(km)
        a_mh, l_mh = fleet.max_heat_point(km)
        mk = "o" if km == 5 else "s"
        ax.scatter([a_ms], [l_ms], s=70, c=C_MS, marker=mk, edgecolors="#222",
                   linewidths=0.5, zorder=5)
        ax.scatter([a_mh], [l_mh], s=70, facecolors="white", edgecolors=C_MH,
                   marker=mk, linewidths=1.8, zorder=5)
        if km == 5:
            ax.annotate(
                f"5 km max sav.\n{a_ms:.0f}% · €{l_ms:.0f}",
                (a_ms, l_ms), textcoords="offset points", xytext=(-18, -36),
                fontsize=8, fontweight="bold", color=C_MS, ha="center",
                arrowprops=dict(arrowstyle="->", color=C_MS, lw=1.0),
            )
            ax.annotate(
                f"5 km max heat\n{a_mh:.0f}% · €{l_mh:.0f}",
                (a_mh, l_mh), textcoords="offset points", xytext=(28, -32),
                fontsize=8, fontweight="bold", color=C_MH, ha="left",
                arrowprops=dict(arrowstyle="->", color=C_MH, lw=1.0),
            )
        else:
            ax.annotate(
                f"15 km max sav.\n{a_ms:.0f}% · €{l_ms:.0f}",
                (a_ms, l_ms), textcoords="offset points", xytext=(28, -36),
                fontsize=8, fontweight="bold", color=C_MS, ha="left",
                arrowprops=dict(arrowstyle="->", color=C_MS, lw=1.0),
            )
            ax.annotate(
                f"15 km max heat\n{a_mh:.0f}% · €{l_mh:.0f}",
                (a_mh, l_mh), textcoords="offset points", xytext=(-8, 28),
                fontsize=8, fontweight="bold", color=C_MH, ha="right",
                arrowprops=dict(arrowstyle="->", color=C_MH, lw=1.0),
            )

    ax.axhline(GAS93, color=C_GAS, ls=":", lw=1.4, zorder=1)
    ax.axhline(ELEC171, color=C_ELEC, ls=":", lw=1.4, zorder=1)
    ax.text(2, GAS93 + 3, f"Gas €{GAS93:.0f}", color=C_GAS, fontsize=8,
            fontweight="bold", va="bottom")
    ax.text(2, ELEC171 + 3, f"Grid elec. €{ELEC171:.0f}", color=C_ELEC,
            fontsize=8, fontweight="bold", va="bottom")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 225)
    ax.set_xlabel("Heat-weighted availability achieved (%)", fontsize=10, labelpad=4)
    ax.set_ylabel("Heat-weighted avg LCOH (€/MWh)", fontsize=10)
    ax.grid(True, ls=":", alpha=0.35, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title(
        "EU fleet — LCOH vs availability (5 km vs 15 km)\n"
        f"Max € savings vs max heat · gas €{GAS93:.0f} · grid elec €{ELEC171:.0f}/MWh",
        fontsize=12, fontweight="semibold", pad=8,
    )
    leg = [
        Line2D([0], [0], color=C5, marker="o", lw=2, label="5 km (fixed floor)"),
        Line2D([0], [0], color=C15, marker="s", ls="--", lw=2, label="15 km (fixed floor)"),
        Line2D([0], [0], color=C_GAS, ls=":", lw=1.4, label=f"Gas heat €{GAS93:.0f}/MWh"),
        Line2D([0], [0], color=C_ELEC, ls=":", lw=1.4, label=f"Grid elec. (IHB) €{ELEC171:.0f}/MWh"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=C_MS,
               markeredgecolor="#222", markersize=8, label="Max € savings"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
               markeredgecolor=C_MH, markeredgewidth=1.8, markersize=8, label="Max heat"),
    ]
    fig.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, 0.14),
               ncol=3, frameon=False, fontsize=8)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.86, bottom=0.28)
    fig.text(
        0.5, 0.02,
        "Curves: all sites forced to the same availability floor, then plotted at fleet heat "
        "actually served (n=2192).\n"
        "Circle = 5 km, square = 15 km. Gas = Eurostat 2025 industrial / 0.85 + EUA; "
        "grid elec. = €162/MWh ÷ 0.95 RTE.",
        ha="center", va="bottom", fontsize=7.0, color="#555", linespacing=1.25,
    )
    fig.savefig(path, dpi=RENDER_DPI, bbox_inches="tight", pad_inches=0.05, facecolor="white")
    plt.close(fig)


def plot_country(cs, path: Path) -> None:
    LABEL = cs.LABEL
    NORDIC, SOUTH = cs.NORDIC, cs.SOUTH
    STYLE = {"nordic": "#E69F00", "south": "#009E73", "other": "#0072B2"}
    LABEL_ISO = {"DEU", "FRA", "ITA", "ESP", "NLD", "GBR", "POL", "BEL"}
    LABEL_XY = {
        (5, "BEL"): (-7, -8), (5, "DEU"): (5, 5), (5, "FRA"): (4, -9),
        (5, "ESP"): (4, -8), (5, "ITA"): (4, 4), (5, "POL"): (4, 4),
        (5, "GBR"): (4, 3), (5, "NLD"): (4, 3),
        (15, "BEL"): (4, -8), (15, "DEU"): (-8, 4), (15, "NLD"): (4, 3),
        (15, "GBR"): (-8, -8), (15, "POL"): (4, 4), (15, "FRA"): (4, -8),
        (15, "ITA"): (4, 3), (15, "ESP"): (4, -8),
    }
    C_MH_LINE, C_MS_LINE = "#333333", "#D55E00"

    panels = {}
    for km in (5, 15):
        mh, fa_mh, fl_mh = cs.country_agg_max_heat_under_gas(cs.GAS_CAPPED[km])
        fa_ms, fl_ms = cs.fleet_max_savings(cs.SWEEP_LONG[km])
        panels[km] = (mh, fa_mh, fl_mh, fa_ms, fl_ms)

    p5 = panels[5][0][panels[5][0]["demand_twh"] >= 0.5]
    p15 = panels[15][0][panels[15][0]["demand_twh"] >= 0.5]
    xlim = (
        min(float(p5["avail"].min()), float(p15["avail"].min())) - 1,
        max(float(p5["avail"].max()), float(p15["avail"].max())) + 1,
    )
    ymax = float(np.ceil(max(p5["lcoh"].max(), p15["lcoh"].max()) / 5) * 5) + 5
    ymin = min(25.0, float(np.floor(min(p5["lcoh"].min(), p15["lcoh"].min()) / 5) * 5) - 2)
    ylim = (ymin, max(ymax, 110.0))

    def wash(ax):
        nx, ny = 80, 80
        x = np.linspace(xlim[0], xlim[1], nx)
        y = np.linspace(ylim[0], ylim[1], ny)
        xx, yy = np.meshgrid(x, y)
        xn = (xx - xlim[0]) / max(xlim[1] - xlim[0], 1e-9)
        yn = (yy - ylim[0]) / max(ylim[1] - ylim[0], 1e-9)
        ax.imshow(
            0.5 * (xn + (1.0 - yn)),
            extent=[xlim[0], xlim[1], ylim[0], ylim[1]],
            origin="lower", aspect="auto", cmap="RdYlGn",
            vmin=0, vmax=1, alpha=0.14, interpolation="bilinear", zorder=0,
        )

    fig, axes = plt.subplots(2, 1, figsize=(7.8, 7.7), sharex=True)
    for ax, km, show_x in ((axes[0], 5, False), (axes[1], 15, True)):
        mh, fa_mh, fl_mh, fa_ms, fl_ms = panels[km]
        plot = mh[mh["demand_twh"] >= 0.5]
        wash(ax)
        ax.axvline(fa_mh, color=C_MH_LINE, ls="--", lw=1.35, zorder=1)
        ax.axhline(fl_mh, color=C_MH_LINE, ls="--", lw=1.35, zorder=1)
        ax.axvline(fa_ms, color=C_MS_LINE, ls=":", lw=1.5, zorder=1)
        ax.axhline(fl_ms, color=C_MS_LINE, ls=":", lw=1.5, zorder=1)
        for _, r in plot.iterrows():
            color = STYLE[cs.region(r["iso3"])]
            ax.scatter(
                r["avail"], r["lcoh"], s=50 + 18 * r["demand_twh"],
                facecolors=color, edgecolors="white", marker="o",
                linewidths=0.6, alpha=0.92, zorder=3,
            )
        for _, r in plot.iterrows():
            if r["iso3"] not in LABEL_ISO:
                continue
            dx, dy = LABEL_XY.get((km, r["iso3"]), (4, 3))
            ax.annotate(
                LABEL.get(r["iso3"], r["iso3"]), (r["avail"], r["lcoh"]),
                textcoords="offset points", xytext=(dx, dy),
                fontsize=8, fontweight="bold", color="#111", zorder=6,
            )
        ax.annotate(
            f"Max heat {fa_mh:.0f}% · €{fl_mh:.0f}",
            (fa_mh, ylim[1]), xytext=(4, -11), textcoords="offset points",
            fontsize=7.5, color=C_MH_LINE, fontweight="bold", va="top", zorder=5,
        )
        ax.annotate(
            f"Max sav. {fa_ms:.0f}% · €{fl_ms:.0f}",
            (fa_ms, ylim[0]), xytext=(4, 8), textcoords="offset points",
            fontsize=7.5, color=C_MS_LINE, fontweight="bold", va="bottom", zorder=5,
        )
        ax.set_title(f"{km} km land buffer", fontsize=11, loc="left")
        ax.set_ylabel("LCOH of served heat (€/MWh)", fontsize=10)
        if show_x:
            ax.set_xlabel("Heat served / demand (%)", fontsize=10, labelpad=4)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.grid(True, ls=":", alpha=0.35, zorder=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle(
        "Country trade-off — max heat served\n"
        "(under country gas heat price · 2030 costs)",
        fontsize=12, y=0.99,
    )
    fig.subplots_adjust(left=0.09, right=0.985, top=0.90, bottom=0.11, hspace=0.14)
    leg_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=STYLE["nordic"],
               markeredgecolor="white", markeredgewidth=0.6, markersize=8, label="Nordic / Baltic"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=STYLE["south"],
               markeredgecolor="white", markeredgewidth=0.6, markersize=8, label="Southern Europe"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=STYLE["other"],
               markeredgecolor="white", markeredgewidth=0.6, markersize=8, label="Other"),
        Line2D([0], [0], color=C_MH_LINE, ls="--", lw=1.5, label="Fleet max heat"),
        Line2D([0], [0], color=C_MS_LINE, ls=":", lw=1.6, label="Fleet max savings"),
    ]
    fig.legend(
        handles=leg_handles, loc="lower center", bbox_to_anchor=(0.54, 0.005),
        ncol=5, frameon=False, fontsize=7.5, columnspacing=0.9, handletextpad=0.3,
        borderaxespad=0.0,
    )
    fig.savefig(path, dpi=RENDER_DPI, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def plot_bar(path: Path) -> None:
    elec, gas, eta, eua, ef, rte = 162.0, 63.25, 0.85, 79.0, 0.202, 0.95
    gas_fuel = gas / eta
    gas_co2 = (ef / eta) * eua
    gas_tot = gas_fuel + gas_co2
    batt = elec / rte
    fig, ax = plt.subplots(figsize=(6.2, 5.0))
    x = np.arange(2)
    w = 0.55
    ax.bar(x[0], gas_fuel, width=w, color=C_GAS_FUEL, zorder=3)
    ax.bar(x[0], gas_co2, width=w, bottom=gas_fuel, color=C_GAS_CO2, zorder=3)
    ax.bar(x[1], batt, width=w, color=C_BATT, zorder=3)
    ax.axhline(gas_tot, color="#666666", ls="--", lw=1.2, zorder=2)
    for i, tot in enumerate([gas_tot, batt]):
        ax.text(x[i], tot + 4, f"{tot:.0f}", ha="center", va="bottom",
                fontsize=10, fontweight="bold", color="#222")
    ax.text(x[0], gas_fuel + gas_co2 / 2, f"+{gas_co2:.0f} CO₂",
            ha="center", va="center", fontsize=7.5, color="#333", fontweight="bold")
    xb, tick = x[1] - w / 2 - 0.08, 0.06
    ax.plot([xb, xb], [gas_tot, batt], color="#444", lw=1.1, clip_on=False, zorder=4)
    ax.plot([xb, xb + tick], [gas_tot, gas_tot], color="#444", lw=1.1, clip_on=False, zorder=4)
    ax.plot([xb, xb + tick], [batt, batt], color="#444", lw=1.1, clip_on=False, zorder=4)
    ax.text(
        xb - 0.04, 0.5 * (gas_tot + batt), f"{batt - gas_tot:+.0f} €/MWh",
        ha="right", va="center", fontsize=8, color="#333", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#bbb", lw=0.6), zorder=5,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["Natural gas\nboiler", "Industrial heat\nbattery"], fontsize=9)
    ax.set_ylabel("LCOH — operating cost of heat (€/MWh_th)", fontsize=10)
    ax.set_ylim(0, 200)
    ax.set_xlim(-0.55, 1.55)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", ls=":", alpha=0.35, zorder=0)
    ax.tick_params(axis="x", length=0, pad=4)
    fig.suptitle(
        "EU-27 Grid electricity vs natural gas boiler LCOH 2025",
        fontsize=12, fontweight="semibold", y=0.98,
    )
    fig.legend(
        handles=[
            mpatches.Patch(facecolor=C_GAS_FUEL, label=f"Gas fuel ÷ {eta:g}"),
            mpatches.Patch(facecolor=C_GAS_CO2, label=f"EUA carbon ({eua:.0f} €/tCO₂)"),
            mpatches.Patch(facecolor=C_BATT, label=f"Grid electricity ÷ {rte:g} RTE"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, 0.935), ncol=3, frameon=False,
        fontsize=8, columnspacing=1.4, handlelength=1.2,
    )
    fig.text(
        0.5, 0.02,
        f"Eurostat 2025 EU-27 industrial — electricity €{elec:.0f}/MWh, gas €{gas:.0f}/MWh.\n"
        f"Gas = price/{eta:g} + ({ef} tCO₂/MWh_fuel)/{eta:g} × €{eua:.0f}/t.  "
        f"Industrial heat battery = grid elec/{rte:g} RTE.\n"
        "Energy operating cost only (no CAPEX).  Bracket shows Δ vs gas boiler.",
        ha="center", va="bottom", fontsize=7.0, color="#555", linespacing=1.3,
    )
    fig.subplots_adjust(left=0.12, right=0.96, top=0.82, bottom=0.18)
    fig.savefig(path, dpi=RENDER_DPI, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


def plot_donut(path: Path) -> None:
    segments = [
        (">500 °C", 50, "#E878D8"),
        ("200–500 °C", 11, "#C9A0E8"),
        ("150–200 °C", 11, "#4A7FB8"),
        ("100–150 °C", 15, "#5AA8D4"),
        ("<100 °C", 13, "#5BCFE8"),
    ]
    legend_order = [
        ("<100 °C", "#5BCFE8"),
        ("100–150 °C", "#5AA8D4"),
        ("150–200 °C", "#4A7FB8"),
        ("200–500 °C", "#C9A0E8"),
        (">500 °C", "#E878D8"),
    ]
    sizes = [s[1] for s in segments]
    colors = [s[2] for s in segments]
    fig = plt.figure(figsize=(4.2, 4.55), facecolor="white")
    gs = fig.add_gridspec(
        3, 1, height_ratios=[0.07, 1.0, 0.16], hspace=0.04,
        left=0.02, right=0.98, top=0.98, bottom=0.02,
    )
    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    ax_t.text(
        0.5, 0.5, "EU industrial process heat by temperature",
        ha="center", va="center", fontsize=11, fontweight="semibold", color="#222",
    )
    ax = fig.add_subplot(gs[1])
    _wedges, texts, _ = ax.pie(
        sizes, colors=colors, startangle=90, counterclock=True,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2.0),
        autopct=lambda pct: f"{pct:.0f}", pctdistance=0.78,
        textprops=dict(color="#222222", fontsize=10.5, fontweight="bold"),
    )
    for t in texts:
        t.set_visible(False)
    ax.text(0.0, 0.0, "[%]", ha="center", va="center", fontsize=11,
            color="#666", fontweight="semibold")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal")
    ax.axis("off")
    ax_b = fig.add_subplot(gs[2])
    ax_b.axis("off")
    ax_b.legend(
        handles=[
            mpatches.Patch(facecolor=c, edgecolor="white", linewidth=0.8, label=lab)
            for lab, c in legend_order
        ],
        loc="lower center", bbox_to_anchor=(0.5, 0.38), ncol=5, frameon=False,
        fontsize=7.5, handlelength=0.8, columnspacing=0.55, handletextpad=0.25,
        borderaxespad=0.0,
    )
    ax_b.text(
        0.5, 0.08, "Source: Fraunhofer ISI (2024) based on FORECAST model.",
        ha="center", va="bottom", fontsize=7.0, color="#555",
    )
    fig.savefig(path, dpi=RENDER_DPI, facecolor="white")
    plt.close(fig)


def plot_steel(ss, path: Path) -> None:
    color = {"iron-and-steel": "#E69F00", "petrochemical-steam-cracking": "#0072B2"}
    marker = {"iron-and-steel": "s", "petrochemical-steam-cracking": "o"}
    style = {5: {"ls": "-", "fill": True}, 15: {"ls": "--", "fill": False}}
    ymax = 200.0
    curves = {}
    for km in (5, 15):
        for sec, label in ss.SECS.items():
            c = ss.sector_curve(km, sec)
            if "surplus" not in c.columns:
                c = c.copy()
                c["surplus"] = c["served_twh"] * (GAS93 - c["hw_LCOH_eur"])
            curves[(sec, km)] = c

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.2), sharey=True)
    for ax, sec in zip(axes, ss.SECS):
        label = ss.SECS[sec]
        ms15 = ss.max_savings_row(curves[(sec, 15)])
        ms_x = float(ms15["served_pct"])
        ax.axvline(ms_x, color=C_MS, ls=":", lw=1.3, zorder=1)
        ax.annotate(
            f"max € savings\n{ms_x:.0f}%",
            (ms_x, 55), textcoords="offset points", xytext=(-8, 0),
            ha="right", va="bottom", fontsize=7, color=C_MS, fontweight="bold", zorder=5,
        )
        for km in (5, 15):
            c = curves[(sec, km)]
            st = style[km]
            plot_vis = c[c["hw_LCOH_eur"] <= ymax]
            ax.plot(
                plot_vis["served_pct"], plot_vis["hw_LCOH_eur"],
                color=color[sec], ls=st["ls"], lw=2.0, marker=marker[sec], ms=5.5,
                markerfacecolor=color[sec] if st["fill"] else "white",
                markeredgecolor=color[sec], markeredgewidth=1.2, zorder=3,
            )
            if km == 15:
                ms = ss.max_savings_row(c)
                ax.scatter(
                    [ms["served_pct"]], [ms["hw_LCOH_eur"]], s=55, c=C_MS,
                    marker=marker[sec], edgecolors="#222", linewidths=0.5, zorder=5,
                )
            end = plot_vis.iloc[-1]
            ax.annotate(
                f'{end["served_pct"]:.0f}%',
                (end["served_pct"], end["hw_LCOH_eur"]),
                textcoords="offset points",
                xytext=(5, 4) if km == 15 else (5, -11),
                fontsize=7.5, color=color[sec], fontweight="bold",
            )
        ax.axhline(GAS93, color=C_GAS, ls=":", lw=1.3, zorder=1)
        ax.axhline(ELEC171, color=C_ELEC, ls=":", lw=1.3, zorder=1)
        ax.text(8, GAS93 + 2.5, f"Gas €{GAS93:.0f}", ha="left", va="bottom",
                fontsize=7.5, fontweight="bold", color=C_GAS, zorder=4)
        ax.text(8, ELEC171 + 2.5, f"Grid elec. €{ELEC171:.0f}", ha="left", va="bottom",
                fontsize=7.5, fontweight="bold", color=C_ELEC, zorder=4)
        ax.set_title(label, fontsize=11, loc="left")
        ax.set_xlabel("Heat served / demand (%)", fontsize=9)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, ymax)
        ax.grid(True, ls=":", alpha=0.4, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("LCOH of served heat (€/MWh)", fontsize=9)
    fig.suptitle(
        "Land-capped industries — LCOH vs achieved availability\n"
        "(heat-weighted · 2030 costs · solar + HP + Li-ion + IHB)",
        fontsize=11.5, y=0.98,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color="#555", ls="-", lw=2, marker="o", markersize=6,
                   markerfacecolor="#555", markeredgecolor="#555", label="5 km (land-tight)"),
            Line2D([0], [0], color="#555", ls="--", lw=2, marker="o", markersize=6,
                   markerfacecolor="white", markeredgecolor="#555", label="15 km"),
            Line2D([0], [0], color=C_GAS, ls=":", lw=1.4, label=f"Gas heat €{GAS93:.0f}/MWh"),
            Line2D([0], [0], color=C_ELEC, ls=":", lw=1.4,
                   label=f"Grid elec. (IHB) €{ELEC171:.0f}/MWh"),
            Line2D([0], [0], color=C_MS, ls=":", lw=1.4, marker="o", markersize=6,
                   markerfacecolor=C_MS, markeredgecolor="#222", label="Max € savings"),
        ],
        loc="upper center", bbox_to_anchor=(0.5, 0.11), ncol=5, frameon=False,
        fontsize=7.5, columnspacing=1.0, handletextpad=0.35,
    )
    s_dem = curves[("iron-and-steel", 5)].iloc[0]["demand_twh"]
    c_dem = curves[("petrochemical-steam-cracking", 5)].iloc[0]["demand_twh"]
    fig.subplots_adjust(left=0.08, right=0.98, top=0.84, bottom=0.24, wspace=0.12)
    fig.text(
        0.5, 0.02,
        "X = achieved served share (not the availability floor).  "
        "Green line = max € savings vs gas (last point before overbuilding).  "
        f"Demand: steel {s_dem:.0f} TWh · steam {c_dem:.0f} TWh.",
        ha="center", va="bottom", fontsize=7.2, color="#555",
    )
    fig.savefig(path, dpi=RENDER_DPI, bbox_inches="tight", pad_inches=0.05, facecolor="white")
    plt.close(fig)


def rebuild_pdf(pngs: dict[str, Path]) -> None:
    import pikepdf
    from pikepdf import Name, Stream

    swap = {PDF_BOX_PX[k]: pngs[k] for k in PDF_BOX_PX}
    pdf = pikepdf.open(SRC_PDF)
    xobj = pdf.pages[0].Resources.XObject
    n = 0
    for key in list(xobj.keys()):
        obj = xobj[key]
        if str(obj.get("/Subtype")) != "/Image":
            continue
        size = (int(obj.Width), int(obj.Height))
        if size not in swap:
            continue
        im = Image.open(swap[size]).convert("RGB")
        w, h = im.size
        extra = {
            "/Type": Name.XObject,
            "/Subtype": Name.Image,
            "/Width": w,
            "/Height": h,
            "/BitsPerComponent": 8,
            "/ColorSpace": obj.ColorSpace,
        }
        xobj[key] = Stream(pdf, im.tobytes(), extra)
        print(f"  pdf {key} {size} → {w}×{h}")
        n += 1
    if n != 5:
        raise SystemExit(f"expected 5 PDF image replacements, got {n}")
    pdf.save(DST_PDF, compress_streams=True)
    print(f"Wrote {DST_PDF} ({DST_PDF.stat().st_size/1e6:.1f} MB)")


def rebuild_pptx(pngs: dict[str, Path]) -> None:
    if not SRC_PPTX.exists():
        raise SystemExit(f"Missing {SRC_PPTX}")
    replacements = {MEDIA[k]: pngs[k] for k in MEDIA}
    tmp = DST_PPTX.with_suffix(".building.pptx")
    with zipfile.ZipFile(SRC_PPTX, "r") as zin, zipfile.ZipFile(
        tmp, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in replacements:
                data = replacements[item.filename].read_bytes()
            if item.filename == "ppt/slides/slide1.xml":
                data = re.sub(rb"<a:srcRect\b[^/]*/>", b"", data)
                data = re.sub(rb"<a:srcRect\b[^>]*>.*?</a:srcRect>", b"", data, flags=re.DOTALL)
            zout.writestr(item, data)
    tmp.replace(DST_PPTX)
    print(f"Wrote {DST_PPTX} ({DST_PPTX.stat().st_size/1e6:.1f} MB)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fleet = load_mod("fleet_plot", ANALYSIS / "plot_lcoh_vs_availability_fleet_5km_15km.py")
    cs = load_mod("country_plot", ANALYSIS / "plot_country_scatter_avail_lcoh_5km_15km.py")
    ss = load_mod("steel_plot", ANALYSIS / "plot_lcoh_vs_availability_steel_steam.py")

    raw = {
        "fleet": OUT / "eu_fleet_lcoh_vs_availability.png",
        "country": OUT / "country_tradeoff_bubble.png",
        "bar": OUT / "eu27_grid_vs_gas_boiler.png",
        "donut": OUT / "eu_industrial_heat_by_temperature.png",
        "steel": OUT / "land_capped_steel_steam.png",
    }
    print("Rendering poster figures…")
    if not all(raw[k].exists() for k in raw if k != "country"):
        plot_fleet(fleet, raw["fleet"])
        plot_bar(raw["bar"])
        plot_donut(raw["donut"])
        plot_steel(ss, raw["steel"])
    plot_country(cs, raw["country"])
    pptx_pngs, pdf_pngs = {}, {}
    for key, path in raw.items():
        pptx_pngs[key], pdf_pngs[key] = finish(path, key)
    rebuild_pptx(pptx_pngs)
    rebuild_pdf(pdf_pngs)


if __name__ == "__main__":
    main()
