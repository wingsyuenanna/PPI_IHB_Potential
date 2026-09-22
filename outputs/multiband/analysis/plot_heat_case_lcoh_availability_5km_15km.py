"""Heat-demand sensitivity: LCOH vs availability (5 km ↔ 15 km).

Each heat case is a line connecting the 5 km point to the 15 km point.
Low / base / high demand form three parallel tradeoff lines.

Availability = heat-weighted served share (= HW reliability).
Data from ``outputs/multiband/heat_case_summary.txt``.

    python outputs/multiband/analysis/plot_heat_case_lcoh_availability_5km_15km.py
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUMMARY = ROOT / "outputs/multiband/heat_case_summary.txt"
OUT_STEM = "heat_case_lcoh_availability_5km_15km"

CASES = ["low", "base", "high"]
CASE_STYLE = {
    "low": {
        "color": "#009E73",
        "ls": "-",
        "lw": 2.2,
        "label": "Low demand (388 TWh)",
        "z": 3,
    },
    "base": {
        "color": "#0072B2",
        "ls": "--",
        "lw": 1.8,
        "label": "Base (522 TWh)",
        "z": 2,
    },
    "high": {
        "color": "#D55E00",
        "ls": "-",
        "lw": 2.2,
        "label": "High demand (697 TWh)",
        "z": 3,
    },
}
KM_MARKER = {5: "o", 15: "s"}  # circle = 5 km, square = 15 km

_SCEN_RE = re.compile(
    r"land_(?P<km>\d+)km_ss_2030(?:_liion)?(?P<heat>_heat_(?:low|high))?",
    re.I,
)


def parse_summary(path: Path) -> pd.DataFrame:
    rows = []
    if not path.is_file():
        return pd.DataFrame()
    for line in path.read_text().splitlines():
        m = re.search(
            r"(?P<scen>land_\d+km\S*):\s*fleet\s+(?P<fleet>[\d.]+)\s*TWh\s*\|\s*"
            r"met heat\s+(?P<met>[\d.]+)%\s*\|\s*"
            r"HW LCOH\s+\$(?P<lcoh>[\d.]+)\s*\|\s*"
            r"HW rel\s+(?P<rel>[\d.]+)%",
            line,
        )
        if not m:
            continue
        sm = _SCEN_RE.search(m.group("scen"))
        if not sm:
            continue
        heat = "base"
        if sm.group("heat"):
            heat = sm.group("heat").replace("_heat_", "")
        rows.append(
            {
                "buffer_km": int(sm.group("km")),
                "heat_case": heat,
                "fleet_twh": float(m.group("fleet")),
                "met_heat_pct": float(m.group("met")),
                "hw_lcoh": float(m.group("lcoh")),
                "hw_rel_pct": float(m.group("rel")),
                "source": "summary",
            }
        )
    return pd.DataFrame(rows)


def live_base(km: int) -> dict | None:
    for name in (f"land_{km}km_ss_2030_liion", f"land_{km}km_ss_2030"):
        path = ROOT / "outputs/multiband" / name / "by_facility.csv"
        if not path.is_file():
            continue
        df = pd.read_csv(path)
        ok = df[df["status"] == "ok"].copy()
        w = pd.to_numeric(ok["replaceable_heat_mwh_th"], errors="coerce")
        rel = pd.to_numeric(ok["Reliability_%"], errors="coerce")
        lcoh = pd.to_numeric(ok["LCOH_served_$perMWh"], errors="coerce")
        met = ok["met_availability_target"].astype(str).str.lower().isin(["true", "1"])
        return {
            "buffer_km": km,
            "heat_case": "base",
            "fleet_twh": float(w.sum() / 1e6),
            "met_heat_pct": float(100.0 * w[met].sum() / w.sum()) if w.sum() else float("nan"),
            "hw_lcoh": float((lcoh * w).sum() / w.sum()),
            "hw_rel_pct": float((rel * w).sum() / w.sum()),
            "source": name,
        }
    return None


def load_table() -> pd.DataFrame:
    df = parse_summary(SUMMARY)
    if df.empty:
        rows = [r for km in (5, 15) if (r := live_base(km)) is not None]
        df = pd.DataFrame(rows)
    return df.sort_values(["heat_case", "buffer_km"]).reset_index(drop=True)


def main() -> None:
    df = load_table()
    if df.empty:
        raise SystemExit("No heat-case summary or by_facility data found.")
    df.to_csv(OUT / f"{OUT_STEM}.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.8, 5.0), constrained_layout=True)

    for case in CASES:
        sub = df[df["heat_case"] == case].sort_values("buffer_km")
        if len(sub) < 2:
            continue
        st = CASE_STYLE[case]
        xs = sub["hw_rel_pct"].to_numpy(float)
        ys = sub["hw_lcoh"].to_numpy(float)
        ax.plot(xs, ys, color=st["color"], ls=st["ls"], lw=st["lw"], zorder=st["z"])
        for _, r in sub.iterrows():
            km = int(r["buffer_km"])
            ax.plot(
                r["hw_rel_pct"],
                r["hw_lcoh"],
                marker=KM_MARKER[km],
                ms=9,
                color=st["color"],
                markerfacecolor=st["color"] if km == 5 else "white",
                markeredgecolor=st["color"],
                markeredgewidth=1.6,
                zorder=st["z"] + 1,
            )
        # label near 15 km end (higher availability)
        end = sub.loc[sub["buffer_km"].idxmax()]
        ax.annotate(
            CASE_STYLE[case]["label"].split(" (")[0],
            (end["hw_rel_pct"], end["hw_lcoh"]),
            textcoords="offset points",
            xytext=(8, 4 if case != "high" else -12),
            fontsize=9,
            color=st["color"],
            fontweight="semibold",
        )

    # annotate 5 km / 15 km ends once (on base line)
    base = df[df["heat_case"] == "base"].set_index("buffer_km")
    if {5, 15}.issubset(base.index):
        ax.annotate(
            "5 km",
            (base.loc[5, "hw_rel_pct"], base.loc[5, "hw_lcoh"]),
            textcoords="offset points",
            xytext=(-28, -14),
            fontsize=8,
            color="#444",
        )
        ax.annotate(
            "15 km",
            (base.loc[15, "hw_rel_pct"], base.loc[15, "hw_lcoh"]),
            textcoords="offset points",
            xytext=(8, -14),
            fontsize=8,
            color="#444",
        )

    ax.set_xlabel("Heat-weighted availability (% served / demand)")
    ax.set_ylabel("Heat-weighted LCOH ($/MWh served)")
    ax.set_title("Heat-demand sensitivity · LCOH vs availability", fontsize=12)
    ax.grid(True, ls=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # pad limits
    ax.set_xlim(df["hw_rel_pct"].min() - 4, df["hw_rel_pct"].max() + 8)
    ax.set_ylim(df["hw_lcoh"].min() - 4, df["hw_lcoh"].max() + 6)

    leg = [
        Line2D([0], [0], color=CASE_STYLE[c]["color"], ls=CASE_STYLE[c]["ls"],
               lw=CASE_STYLE[c]["lw"], label=CASE_STYLE[c]["label"])
        for c in CASES if c in set(df["heat_case"])
    ]
    leg += [
        Line2D([0], [0], marker="o", color="#333", ls="none", ms=8, label="5 km"),
        Line2D([0], [0], marker="s", color="#333", ls="none", ms=8,
               markerfacecolor="white", markeredgewidth=1.4, label="15 km"),
    ]
    ax.legend(handles=leg, frameon=False, loc="upper left", fontsize=8.5)

    fig.savefig(OUT / f"{OUT_STEM}.png", dpi=180)
    fig.savefig(OUT / f"{OUT_STEM}.pdf")
    print(f"Wrote {OUT / (OUT_STEM + '.png')}")
    print(f"Wrote {OUT / (OUT_STEM + '.pdf')}")
    print(f"Wrote {OUT / (OUT_STEM + '.csv')}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
