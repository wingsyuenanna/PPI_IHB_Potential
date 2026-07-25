"""Compare LCOH before vs after industrial HP CAPEX/FOM (+ IHB CPI inflation)."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

PRE = {
    "5km": OUT / "by_facility_5km_2030_liion_pre_hp.csv",
    "15km": OUT / "by_facility_15km_2030_liion_pre_hp.csv",
}
POST = {
    "5km": ROOT / "outputs/multiband/land_5km_ss_2030_liion/by_facility.csv",
    "15km": ROOT / "outputs/multiband/land_15km_ss_2030_liion/by_facility.csv",
}


def _met(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true", "1"])


def hw(df: pd.DataFrame, col: str, weight: str = "replaceable_heat_mwh_th") -> float:
    w = df[weight].astype(float)
    if w.sum() <= 0:
        return float("nan")
    return float((df[col].astype(float) * w).sum() / w.sum())


def summarize(label: str, pre: pd.DataFrame, post: pd.DataFrame) -> dict:
    pre_ok = pre[pre["status"] == "ok"].copy()
    post_ok = post[post["status"] == "ok"].copy()
    pre_ok["met"] = _met(pre_ok["met_availability_target"])
    post_ok["met"] = _met(post_ok["met_availability_target"])

    def block(df, tag):
        met = df[df["met"]]
        row = {
            f"{tag}_n": len(df),
            f"{tag}_n_met": len(met),
            f"{tag}_hw_lcoh_all": hw(df, "LCOH_served_$perMWh"),
            f"{tag}_hw_rel_all": hw(df, "Reliability_%"),
            f"{tag}_hw_lcoh_met": hw(met, "LCOH_served_$perMWh") if len(met) else np.nan,
            f"{tag}_heat_met_pct": (
                100 * met["replaceable_heat_mwh_th"].sum() / df["replaceable_heat_mwh_th"].sum()
                if len(df) else np.nan
            ),
        }
        if "LCOH_hp_$perMWh" in df.columns:
            row[f"{tag}_hw_lcoh_hp_met"] = hw(met, "LCOH_hp_$perMWh") if len(met) else np.nan
            row[f"{tag}_hw_lcoh_solar_met"] = hw(met, "LCOH_solar_$perMWh") if len(met) else np.nan
            row[f"{tag}_hw_lcoh_liion_met"] = hw(met, "LCOH_liion_$perMWh") if len(met) else np.nan
            row[f"{tag}_hw_lcoh_ihb_met"] = hw(met, "LCOH_ihb_$perMWh") if len(met) else np.nan
        return row

    out = {"case": label, **block(pre_ok, "pre"), **block(post_ok, "post")}
    out["d_hw_lcoh_met"] = out["post_hw_lcoh_met"] - out["pre_hw_lcoh_met"]
    out["d_hw_lcoh_all"] = out["post_hw_lcoh_all"] - out["pre_hw_lcoh_all"]

    # Site-level delta among met sites in both
    m = pre_ok[["source_id", "LCOH_served_$perMWh", "replaceable_heat_mwh_th", "met", "subsector"]].merge(
        post_ok[["source_id", "LCOH_served_$perMWh", "met", "LCOH_hp_$perMWh"]],
        on="source_id",
        suffixes=("_pre", "_post"),
    )
    both = m[m["met_pre"] & m["met_post"]].copy()
    both["dLCOH"] = both["LCOH_served_$perMWh_post"] - both["LCOH_served_$perMWh_pre"]
    out["n_both_met"] = len(both)
    out["hw_dLCOH_both_met"] = hw(both, "dLCOH") if len(both) else np.nan
    out["median_dLCOH_both_met"] = float(both["dLCOH"].median()) if len(both) else np.nan
    return out, both


def sector_delta(both: pd.DataFrame) -> pd.DataFrame:
    if both.empty:
        return pd.DataFrame()
    rows = []
    for sec, g in both.groupby("subsector"):
        rows.append({
            "subsector": sec,
            "n": len(g),
            "hw_dLCOH": hw(g, "dLCOH"),
            "hw_lcoh_hp": hw(g, "LCOH_hp_$perMWh") if "LCOH_hp_$perMWh" in g else np.nan,
            "median_dLCOH": float(g["dLCOH"].median()),
        })
    return pd.DataFrame(rows).sort_values("hw_dLCOH", ascending=False)


def main() -> None:
    summaries = []
    both_5 = None
    lines = [
        "Impact of adding industrial HP CAPEX/FOM (2030 USD) + IHB CPI inflation",
        "Pre = land_*_ss_2030_liion without HP equipment cost",
        "Post = same scenario with HP CAPEX/FOM + inflated IHB",
        "",
    ]
    for label in ("5km", "15km"):
        if not PRE[label].exists() or not POST[label].exists():
            lines.append(f"{label}: missing pre or post CSV — skip")
            continue
        pre = pd.read_csv(PRE[label])
        post = pd.read_csv(POST[label])
        summ, both = summarize(label, pre, post)
        summaries.append(summ)
        if label == "5km":
            both_5 = both
        lines += [
            f"=== {label} ===",
            f"  Pre  HW LCOH (all / ≥90%): ${summ['pre_hw_lcoh_all']:.0f} / ${summ['pre_hw_lcoh_met']:.0f}/MWh"
            f"  (rel {summ['pre_hw_rel_all']:.0f}%, met heat {summ['pre_heat_met_pct']:.0f}%)",
            f"  Post HW LCOH (all / ≥90%): ${summ['post_hw_lcoh_all']:.0f} / ${summ['post_hw_lcoh_met']:.0f}/MWh"
            f"  (rel {summ['post_hw_rel_all']:.0f}%, met heat {summ['post_heat_met_pct']:.0f}%)",
            f"  Δ HW LCOH ≥90%: ${summ['d_hw_lcoh_met']:+.1f}/MWh"
            f"  (site HW Δ ${summ['hw_dLCOH_both_met']:+.1f}, median ${summ['median_dLCOH_both_met']:+.1f})",
        ]
        if "post_hw_lcoh_hp_met" in summ and np.isfinite(summ["post_hw_lcoh_hp_met"]):
            lines.append(
                f"  Post ≥90% split: solar ${summ['post_hw_lcoh_solar_met']:.0f} · "
                f"HP ${summ['post_hw_lcoh_hp_met']:.0f} · "
                f"Li-ion ${summ['post_hw_lcoh_liion_met']:.0f} · "
                f"IHB ${summ['post_hw_lcoh_ihb_met']:.0f}/MWh"
            )
        lines.append("")

    if both_5 is not None and len(both_5):
        sec = sector_delta(both_5)
        sec.to_csv(OUT / "compare_hp_cost_impact_by_sector_5km.csv", index=False)
        lines.append("5 km ΔLCOH by subsector (≥90% sites in both):")
        for _, r in sec.iterrows():
            lines.append(
                f"  {r.subsector:<32} n={int(r.n):4d}  HW Δ ${r.hw_dLCOH:+6.1f}  "
                f"HP share ${r.hw_lcoh_hp:5.1f}/MWh"
            )

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "compare_hp_cost_impact_2030.csv", index=False)
    txt = OUT / "compare_hp_cost_impact_2030.txt"
    txt.write_text("\n".join(lines) + "\n")
    print(txt.read_text())

    # Bar chart
    if not summary_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        labels, pre_v, post_v = [], [], []
        for _, r in summary_df.iterrows():
            labels.append(f"{r['case']} ≥90%")
            pre_v.append(r["pre_hw_lcoh_met"])
            post_v.append(r["post_hw_lcoh_met"])
        y = np.arange(len(labels))
        ax.barh(y - 0.18, pre_v, 0.35, color="#8d99ae", label="Pre (no HP equip.)")
        ax.barh(y + 0.18, post_v, 0.35, color="#2a9d8f", label="Post (+ HP CAPEX/FOM)")
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Heat-weighted LCOH among ≥90% sites ($/MWh)")
        ax.set_title("2030 LCOH impact of industrial HP CAPEX/FOM")
        for i, (a, b) in enumerate(zip(pre_v, post_v)):
            if np.isfinite(a) and np.isfinite(b):
                ax.text(max(a, b) + 1, i, f"{b-a:+.0f}", va="center", fontsize=9)
        ax.legend(loc="lower right", fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(OUT / "compare_hp_cost_impact_lcoh.png", dpi=160)
        fig.savefig(OUT / "compare_hp_cost_impact_lcoh.pdf")
        plt.close(fig)
        print("Wrote", OUT / "compare_hp_cost_impact_lcoh.png")


if __name__ == "__main__":
    main()
