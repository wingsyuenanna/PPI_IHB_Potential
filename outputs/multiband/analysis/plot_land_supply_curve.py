"""Land-lease supply curve: share of fleet heat that stays below gas at 90% availability
as a function of the PV land lease price (EUR/ha-yr).

Per-site break-even lease = (gas - LCOH_total) x annual heat / land area used, with land area
= S_opt_MW / (MW_PER_HA). Valid because the 90% floor fixes the solar build (checked by
full re-solves on 3 sites). Sites that miss 90% (land-capped) have no break-even.
"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
EURUSD = 1.08          # same as the fleet-availability plots
MW_PER_HA = 0.5        # 50 MW/km2 (model density)
BAND = (3000, 5000)    # ENLAPA, Germany 2026 ground-mounted PV lease, EUR/ha-yr
SCEN = {"5 km": "land_5km_ss_2030_liion", "15 km": "land_15km_ss_2030_liion"}
COL = {"5 km": "#d95f02", "15 km": "#1b9e77"}

def breakeven(scen):
    d = pd.read_csv(ROOT / f"outputs/multiband/{scen}/by_facility_with_gas.csv")
    d = d[d.status == "ok"].copy()
    heat = d.total_load_MW * 8760
    area_ha = d.S_opt_MW / MW_PER_HA
    d["be"] = ((d["gas_heat_cost_eur_mwh"] - d["LCOH_total_$perMWh"] / EURUSD) * heat / area_ha)
    d.loc[~d.met_availability_target.astype(bool), "be"] = -np.inf   # cannot reach 90%
    d["heat"] = d.replaceable_heat_mwh_th
    return d

def candidates(k):
    """Per-site operating points (sweep floors + gas-capped alpha*): served MWh, LCOH_served EUR, land ha."""
    A = ROOT / "outputs/multiband/analysis"
    L = pd.read_csv(A / f"fleet_availability_sweep_{k.replace(' ', '')}_long.csv")
    G = pd.read_csv(A / f"gas_capped_step90_{k.replace(' ', '')}.csv")
    L = L[L.status == "ok"]
    a = pd.DataFrame({"source_id": L.source_id, "served": L["Reliability_%"] / 100 * L.replaceable_heat_mwh_th,
                      "lcoh": L.LCOH_served_eur_perMWh, "ha": L.S_opt_MW / MW_PER_HA})
    G = G[(G.status == "ok") & (G.served_mwh > 0)]
    b = pd.DataFrame({"source_id": G.source_id, "served": G.served_mwh, "lcoh": G.LCOH_served_eur_perMWh,
                      "ha": G.S_opt_MW / MW_PER_HA})
    c = pd.concat([a, b]).merge(G[["source_id", "gas_heat_cost_eur_mwh"]], on="source_id")
    return c[c.served > 0]

def max_heat_share(c, total, p):
    ok = c[c.lcoh + p * c.ha / c.served <= c.gas_heat_cost_eur_mwh]
    return ok.groupby("source_id").served.max().sum() / total

def share_at(d, p, w=True):
    ok = d.be >= p
    return (d.heat[ok].sum() / d.heat.sum()) if w else ok.mean()

if __name__ == "__main__":
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    x = np.linspace(0, 12000, 600)
    ax.axvspan(*BAND, color="0.85", zorder=0)
    ax.text(sum(BAND) / 2, 3, "ENLAPA PV lease range\n(Germany, 2026)", ha="center", va="bottom", fontsize=8, color="0.3")
    for k, scen in SCEN.items():
        d = breakeven(scen)
        c = candidates(k); tot = d.heat.sum()
        y90 = [100 * share_at(d, p) for p in x]
        y = [100 * max_heat_share(c, tot, p) for p in x]
        ax.plot(x, y90, color=COL[k], lw=1.2, ls="--", alpha=0.7)
        ax.plot(x, y, color=COL[k], lw=2, label=f"{k}: max heat below gas")
        for p in BAND:
            s = 100 * max_heat_share(c, tot, p)
            ax.plot(p, s, "o", color=COL[k], ms=4)
            ax.annotate(f"{s:.0f}%", (p, s), textcoords="offset points", xytext=(5, 5), fontsize=8, color=COL[k])
        print(k, {p: (round(100*max_heat_share(c,tot,p),1), round(y90[0],1)) for p in [0, 1000, 3000, 5000, 10000]},
              "median be", round(d.be[np.isfinite(d.be)].median()))
    ax.set_xlim(0, 12000); ax.set_ylim(0, 102)
    ax.set_xlabel("PV land lease price (€/ha-yr)")
    ax.set_ylabel("Heat served as share of fleet\nreplaceable heat,\nserved below gas cost (%)")
    ax.set_title("Land supply curve: how much heat beats gas at a given lease price", fontsize=10)
    ax.plot([], [], color="0.4", lw=1.2, ls="--", label="dashed: only sites reaching 90%")
    ax.legend(frameon=False, loc="upper right"); ax.grid(alpha=0.25)
    fig.text(0.01, 0.005, "Gas €/MWh and solar+storage LCOH per site; 2 ha/MW (50 MW/km²); EURUSD 1.08. "
             "Lease range: ENLAPA, enlapa.de/en/magazine/photovoltaic_lease_prices", fontsize=6, color="0.4")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out = ROOT / "outputs/multiband/analysis/land_supply_curve_5km_15km.png"
    fig.savefig(out, dpi=200); print(out)
