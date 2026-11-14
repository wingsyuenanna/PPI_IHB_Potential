"""EU fleet LCOH vs availability (base heat case): previous vs current run, 5 km & 15 km.

Current run  = fleet_availability_sweep_{km}km_by_floor.csv, *_long.csv, gas_capped_step90_{km}km.csv
Previous run = same files archived under previous_run/ (pre-HP-nameplate / shared-IHB-store model).

Max € savings : per site, floor maximising served × (gas − LCOH).
Max heat      : per site, highest floor with LCOH ≤ country gas (gas_capped_step90).

    python outputs/multiband/analysis/plot_lcoh_vs_availability_fleet_old_vs_new.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
PREV = OUT / "previous_run"
OUT_STEM = "lcoh_vs_availability_fleet_5km_15km_hp_in_optimization_vs_previous"
OUT_STEM_CUR = "lcoh_vs_availability_fleet_5km_15km_hp_in_optimization"

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from gas_benchmark import GAS_EU, ELEC_EU  # EU-27 gas heat cost from input files (see gas_benchmark.py)
EURUSD = 1.08

C = {5: "#0072B2", 15: "#F28E1B"}
MK = {5: "o", 15: "s"}
C_MS, C_MH, C_GAS, C_ELEC = "#009E73", "#CC79A7", "#6A3D9A", "#949494"


def _fleet(demand, served, lcoh) -> tuple[float, float]:
    dem = float(demand.sum())
    srv = float(served.fillna(0).sum())
    w = served.fillna(0)
    m = (w > 0) & lcoh.notna()
    hw = float((lcoh[m] * w[m]).sum() / w[m].sum()) if m.any() else float("nan")
    return 100.0 * srv / dem, hw


def _read(base: Path, name: str) -> pd.DataFrame:
    p = base / name
    if not p.exists():
        p = base / f"{name}.gz"
    return pd.read_csv(p, low_memory=False)


def curve(base: Path, km: int) -> pd.DataFrame:
    return _read(base, f"fleet_availability_sweep_{km}km_by_floor.csv").sort_values("served_pct")


def max_heat(base: Path, km: int) -> tuple[float, float]:
    d = _read(base, f"gas_capped_step90_{km}km.csv")
    return _fleet(
        pd.to_numeric(d["replaceable_heat_mwh_th"], errors="coerce"),
        pd.to_numeric(d["served_mwh"], errors="coerce"),
        pd.to_numeric(d["LCOH_served_eur_perMWh"], errors="coerce"),
    )


def max_savings(base: Path, km: int) -> tuple[float, float]:
    g = _read(base, f"fleet_availability_sweep_{km}km_long.csv")
    if "status" in g.columns:
        g = g[g["status"] == "ok"].copy()
    g["heat"] = pd.to_numeric(g["replaceable_heat_mwh_th"], errors="coerce")
    g["rel"] = pd.to_numeric(g["Reliability_%"], errors="coerce")
    g["lcoh"] = pd.to_numeric(g["LCOH_served_eur_perMWh"], errors="coerce")
    if g["lcoh"].isna().all():
        g["lcoh"] = pd.to_numeric(g["LCOH_served_$perMWh"], errors="coerce") / EURUSD
    g["served"] = g["heat"] * g["rel"] / 100.0
    g["surplus"] = g["served"] * (GAS_EU - g["lcoh"])
    g = g.dropna(subset=["source_id", "surplus", "served", "lcoh"])
    best = g.loc[g.groupby("source_id")["surplus"].idxmax()]
    return _fleet(best["heat"], best["served"], best["lcoh"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current-only", action="store_true", help="plot only the current run")
    cur_only = ap.parse_args().current_only
    stem = OUT_STEM_CUR if cur_only else OUT_STEM
    fig, ax = plt.subplots(figsize=(10, 6.2), layout="constrained")
    rows = []
    for km in (5, 15):
        for tag, base, alpha, lw, ls in (
            ("previous", PREV, 0.45, 1.8, ":"),
            ("current", OUT, 1.0, 3.0, "-" if km == 5 else "--"),
        ):
            if cur_only and tag == "previous":
                continue
            c = curve(base, km)
            ax.plot(
                c["served_pct"], c["hw_LCOH_eur"], color=C[km], ls=ls, lw=lw,
                marker=MK[km], ms=7 if tag == "current" else 5, alpha=alpha,
                mfc=C[km] if tag == "current" else "white", zorder=3 if tag == "current" else 2,
            )
            end = c.iloc[-1]
            ax.annotate(
                f'{end["hw_LCOH_eur"]:.0f}', (end["served_pct"], end["hw_LCOH_eur"]),
                textcoords="offset points", xytext=(7, 5 if tag == "current" else -11), fontsize=10,
                fontweight="bold", color=C[km], alpha=1.0 if tag == "current" else 0.6,
            )
            a_ms, l_ms = max_savings(base, km)
            a_mh, l_mh = max_heat(base, km)
            rows.append(dict(run=tag, km=km, floor100_avail=end["served_pct"], floor100_lcoh=end["hw_LCOH_eur"],
                             maxsav_avail=a_ms, maxsav_lcoh=l_ms, maxheat_avail=a_mh, maxheat_lcoh=l_mh))
            full = tag == "current"
            ax.scatter([a_ms], [l_ms], s=130 if full else 60, c=C_MS if full else "white",
                       edgecolors="#222" if full else C_MS, linewidths=0.8 if full else 1.2,
                       marker=MK[km], zorder=5, alpha=1.0 if full else 0.8)
            ax.scatter([a_mh], [l_mh], s=130 if full else 60, facecolors="white",
                       edgecolors=C_MH, linewidths=2.2 if full else 1.2, marker=MK[km],
                       zorder=5, alpha=1.0 if full else 0.8)
            if full:
                dy = -26 if km == 5 else -30
                ax.annotate(f"{km} km max sav.\n{a_ms:.0f}% · €{l_ms:.0f}", (a_ms, l_ms),
                            textcoords="offset points", xytext=(0, dy), ha="center", fontsize=9.5,
                            fontweight="bold", color=C_MS)
                ax.annotate(f"{km} km max heat\n{a_mh:.0f}% · €{l_mh:.0f}", (a_mh, l_mh),
                            textcoords="offset points", xytext=(0, 18 if km == 15 else 22), ha="center",
                            fontsize=9.5, fontweight="bold", color=C_MH)

    ax.axhline(GAS_EU, color=C_GAS, ls=(0, (5.5, 1.6, 1.2, 1.6)), lw=1.8, zorder=1)
    ax.axhline(ELEC_EU, color=C_ELEC, ls=(0, (1.1, 1.3)), lw=1.8, zorder=1)
    ax.text(1.5, GAS_EU + 3, f"Gas €{GAS_EU:.0f}", color=C_GAS, fontsize=10, fontweight="bold")
    ax.text(1.5, ELEC_EU + 3, f"Grid elec. €{ELEC_EU:.0f}", color=C_ELEC, fontsize=10, fontweight="bold")

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 225)
    ax.set_xlabel("Heat-weighted availability achieved (%)", fontsize=12)
    ax.set_ylabel("Heat-weighted avg LCOH (€/MWh)", fontsize=12)
    ax.set_title("EU fleet — LCOH vs availability, base heat case (5 km vs 15 km)" if cur_only else
                 "EU fleet — LCOH vs availability, base heat case\nprevious vs current model (5 km vs 15 km)",
                 fontsize=14, fontweight="bold")
    ax.grid(True, ls=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    leg = [
        Line2D([0], [0], color=C[5], marker="o", lw=3, label="5 km — current"),
        Line2D([0], [0], color=C[15], marker="s", ls="--", lw=3, label="15 km — current"),
        Line2D([0], [0], color=C[5], marker="o", ls=":", lw=1.8, alpha=0.5, mfc="white", label="5 km — previous"),
        Line2D([0], [0], color=C[15], marker="s", ls=":", lw=1.8, alpha=0.5, mfc="white", label="15 km — previous"),
        Line2D([0], [0], marker="o", color="w", mfc=C_MS, mec="#222", ms=10, label="Max € savings (current)"),
        Line2D([0], [0], marker="o", color="w", mfc="white", mec=C_MH, mew=2, ms=10, label="Max heat (current)"),
        Line2D([0], [0], marker="o", color="w", mfc="white", mec="#666", mew=1.2, ms=8, alpha=0.8,
               label="Small hollow = previous run"),
    ]
    ax.legend(handles=leg[:2] + leg[4:6] if cur_only else leg, loc="upper left", ncol=2, frameon=False, fontsize=9.5)
    if cur_only:
        fig.text(0.5, -0.02, "Curves: all sites forced to the same availability floor (10–100%), plotted at fleet heat actually served (n=2192).",
                 ha="center", va="top", fontsize=8.5, color="#555")
    else:
      fig.text(
        0.5, -0.02,
        "Curves: all sites forced to the same availability floor (10–100%), plotted at fleet heat actually served (n=2192).\n"
        "Previous run: HP CAPEX on average served heat, per-band IHB stores. Current: HP nameplate sized in the optimization, shared IHB store.",
        ha="center", va="top", fontsize=8.5, color="#555",
    )
    fig.savefig(OUT / f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    pd.DataFrame(rows).to_csv(OUT / f"{stem}_points.csv", index=False)
    print(pd.DataFrame(rows).round(1).to_string(index=False))
    print(f"Wrote {OUT / (stem + '.png')}")


if __name__ == "__main__":
    main()
