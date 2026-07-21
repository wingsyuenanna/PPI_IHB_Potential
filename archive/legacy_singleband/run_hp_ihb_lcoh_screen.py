"""Per-facility heat-pump / IHB LCOH screen (paper-style annual energy matching).

Every technology is powered by ON-SITE SOLAR (renewable_power_price), not the grid.
For each facility, replaceable heat is split across temperature bands and each band is
assigned a technology; its LCOH is rebuilt on solar from the cost structure implied by
Input/industrial_heat_pump_costs/eu_heat_pump_costs_by_country.csv:

    < 100 °C     -> low-temperature heat pump   (COP 2.7)
    100-200 °C   -> steam heat pump             (COP 1.8)
    > 200 °C     -> IHB / thermal battery       (direct electric, COP 1.0)

On-site solar is intermittent, so every block (heat pumps included) is paired with the
thermal store, matching the manuscript. Per-band LCOH on solar:

    LCOH_b = renewable_power_price / (COP_b * RTE) + hp_capex_b + storage_capex

where the fixed capex adders are DERIVED from the supplied tables (hp_low 12, hp_steam 18,
storage 18 EUR/MWh). The IHB is COP 1.0 with no separate hp_capex, reproducing the table's
thermal_storage_lcoh = renewable/RTE + 18. The facility green LCOH is the heat-weighted
average of its band LCOHs, compared to the country gas benchmark. Land matching separate.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SITES = ROOT / "outputs" / "eu_ihb_site_assessment_2024.csv"
HP_COUNTRY = ROOT / "Input" / "industrial_heat_pump_costs" / "eu_heat_pump_costs_by_country.csv"
OUT = ROOT / "outputs" / "hp_ihb_lcoh_by_facility.csv"

# Efficiencies from Input/industrial_heat_pump_costs/eu_heat_pump_cost_assumptions.csv.
COP_LOW, COP_STEAM, COP_IHB = 2.7, 1.8, 1.0
RTE = 0.92
# On-site solar is intermittent -> heat pumps also need the thermal store (manuscript
# pairs every block with 16 h storage). Set False to treat solar as firm (no HP storage).
HP_WITH_STORAGE = True

# GBR is not in the EU27 cost tables; proxy it with the nearest-market EU27 country
# (Ireland: similar island grid and northern-European solar resource). None = exclude.
GBR_PROXY = "IRL"

# Land matching (mirrors run_ihb_potential density and the manuscript's PV sizing).
PV_DENSITY_MW_KM2 = 50.0    # solar MWdc per km2 of available land
ETA_PV_SIZING = 0.95        # storage delivery efficiency used when sizing PV
COP_BY_BAND = {
    "heat_below100C_tj": COP_LOW,
    "heat_100C-200C_tj": COP_STEAM,
    "heat_200C-500C_tj": COP_IHB,
    "heat_500C-1000C_tj": COP_IHB,
    "heat_above1000C_tj": COP_IHB,
}

# Temperature band -> technology solar-LCOH column (built below).
BAND_TECH = {
    "heat_below100C_tj": "low_temp_hp_solar",    # < 100 C -> low-temp heat pump
    "heat_100C-200C_tj": "steam_hp_solar",       # 100-200 -> steam heat pump
    "heat_200C-500C_tj": "ihb_solar",            # > 200 C -> IHB
    "heat_500C-1000C_tj": "ihb_solar",
    "heat_above1000C_tj": "ihb_solar",
}
BANDS = list(BAND_TECH)
HP_BANDS = ["heat_below100C_tj", "heat_100C-200C_tj"]           # heat-pump-served
IHB_BANDS = ["heat_200C-500C_tj", "heat_500C-1000C_tj", "heat_above1000C_tj"]


def build_solar_lcoh(cc: pd.DataFrame) -> pd.DataFrame:
    """Rebuild each technology's LCOH powered by on-site solar (renewable_power_price)."""
    cc = cc.copy()
    ren = cc["renewable_power_price_eur_mwh"]
    # Fixed capex adders implied by the supplied grid-based tables (constant across countries).
    hp_low_capex = cc["low_temp_hp_lcoh_eur_mwh"] - cc["electricity_price_eur_mwh"] / COP_LOW
    hp_steam_capex = cc["steam_hp_lcoh_eur_mwh"] - cc["electricity_price_eur_mwh"] / COP_STEAM
    storage_capex = cc["thermal_storage_lcoh_eur_mwh"] - ren / RTE
    store = storage_capex if HP_WITH_STORAGE else 0.0
    cc["low_temp_hp_solar"] = ren / (COP_LOW * RTE) + hp_low_capex + store
    cc["steam_hp_solar"] = ren / (COP_STEAM * RTE) + hp_steam_capex + store
    cc["ihb_solar"] = ren / (COP_IHB * RTE) + storage_capex   # == thermal_storage_lcoh
    return cc


def main() -> None:
    site = pd.read_csv(SITES, low_memory=False)
    run = site[site["has_solar_data"] & site["has_replaceable_heat"]].copy()
    run[BANDS] = run[BANDS].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    cc = build_solar_lcoh(pd.read_csv(HP_COUNTRY))
    lcoh_cols = list(dict.fromkeys(BAND_TECH.values())) + ["gas_heat_cost_eur_mwh"]

    # Country used for the price join: GBR proxied to a neighbouring EU27 market.
    run["price_iso"] = run["iso3_country"]
    if GBR_PROXY:
        run.loc[run["iso3_country"] == "GBR", "price_iso"] = GBR_PROXY
    df = run.merge(cc[["iso3"] + lcoh_cols], left_on="price_iso", right_on="iso3", how="left")

    matched = df["gas_heat_cost_eur_mwh"].notna()
    unmatched_iso = sorted(df.loc[~matched, "iso3_country"].unique())
    unmatched_twh = df.loc[~matched, "replaceable_heat_mwh_th"].sum() / 1e6

    m = df[matched].copy()
    band_total = m[BANDS].sum(axis=1)

    # ── Cost screen: heat-weighted green LCOH vs gas benchmark ──────────────
    weighted = sum(m[b] * m[BAND_TECH[b]] for b in BANDS)
    m["green_lcoh_eur_mwh"] = weighted / band_total.where(band_total > 0)
    m["gas_benchmark_eur_mwh"] = m["gas_heat_cost_eur_mwh"]
    m["below_gas"] = m["green_lcoh_eur_mwh"] < m["gas_benchmark_eur_mwh"]
    m["lcoh_ratio_vs_gas"] = m["green_lcoh_eur_mwh"] / m["gas_benchmark_eur_mwh"]
    m["hp_heat_share"] = m[HP_BANDS].sum(axis=1) / band_total.where(band_total > 0)
    m["ihb_heat_share"] = m[IHB_BANDS].sum(axis=1) / band_total.where(band_total > 0)

    # ── Land screen: PV required per band (heat pumps need less via COP) ─────
    # Annual PV energy = heat / (COP * storage_eff); capacity = energy/(CF*8760).
    cf = m["solar_capacity_factor"].clip(lower=1e-6)
    pv_req = sum(
        (m["replaceable_heat_mwh_th"] * (m[b] / band_total.where(band_total > 0)))
        / (COP_BY_BAND[b] * ETA_PV_SIZING * cf * 8760.0)
        for b in BANDS
    )
    m["pv_required_mwdc"] = pv_req
    m["land_required_km2"] = m["pv_required_mwdc"] / PV_DENSITY_MW_KM2
    m["local_fit_fraction"] = np.minimum(
        1.0, m["available_land_km2"] / m["land_required_km2"].where(m["land_required_km2"] > 0)
    ).fillna(1.0)
    m["land_matched_heat_mwh"] = m["replaceable_heat_mwh_th"] * m["local_fit_fraction"]
    # Combined: heat that is BOTH below gas AND land-matched (proportional credit).
    m["green_and_local_heat_mwh"] = m["land_matched_heat_mwh"].where(m["below_gas"], 0.0)

    keep = [
        "source_id", "source_name", "iso3_country", "subsector",
        "replaceable_heat_mwh_th", "available_land_km2", "solar_capacity_factor",
        "green_lcoh_eur_mwh", "gas_benchmark_eur_mwh", "lcoh_ratio_vs_gas", "below_gas",
        "hp_heat_share", "ihb_heat_share",
        "pv_required_mwdc", "land_required_km2", "local_fit_fraction",
        "land_matched_heat_mwh", "green_and_local_heat_mwh",
    ] + list(dict.fromkeys(BAND_TECH.values()))
    m[keep].to_csv(OUT, index=False)

    # ── Aggregates (heat-weighted by replaceable heat) ──────────────────────
    w = m["replaceable_heat_mwh_th"]
    tot = w.sum()
    hw_green = float((m["green_lcoh_eur_mwh"] * w).sum() / tot)
    hw_gas = float((m["gas_benchmark_eur_mwh"] * w).sum() / tot)
    below_heat = w[m["below_gas"]].sum()
    land_matched = m["land_matched_heat_mwh"].sum()
    both = m["green_and_local_heat_mwh"].sum()

    print(f"Wrote {len(m)} sites to {OUT.relative_to(ROOT)}")
    if GBR_PROXY:
        n_gbr = int((m["iso3_country"] == "GBR").sum())
        print(f"GBR proxied to {GBR_PROXY} ({n_gbr} sites)")
    if unmatched_iso:
        print(f"Still unmatched: {unmatched_iso} ({(~matched).sum()} sites, {unmatched_twh:.1f} TWh)")
    print()
    print(f"Total replaceable heat : {tot/1e6:.1f} TWh across {len(m)} sites")
    print(f"Heat-weighted green LCOH : {hw_green:,.1f} EUR/MWh  |  gas benchmark {hw_gas:,.1f}")
    print(f"[cost]  heat below gas benchmark : {below_heat/1e6:.1f} TWh ({below_heat/tot*100:.1f}%)")
    print(f"[land]  heat locally land-matched: {land_matched/1e6:.1f} TWh ({land_matched/tot*100:.1f}%)")
    print(f"[both]  below gas AND land-matched: {both/1e6:.1f} TWh ({both/tot*100:.1f}%)")
    print(f"Heat served by heat pump (<200C): {m[HP_BANDS].sum().sum()/m[BANDS].sum().sum()*100:.1f}%  |  "
          f"IHB (>200C): {m[IHB_BANDS].sum().sum()/m[BANDS].sum().sum()*100:.1f}%")

    print("\n=== by subsector (heat-weighted) ===")
    g = m.groupby("subsector").apply(
        lambda x: pd.Series({
            "heat_TWh": x["replaceable_heat_mwh_th"].sum() / 1e6,
            "green_lcoh": (x["green_lcoh_eur_mwh"] * x["replaceable_heat_mwh_th"]).sum() / x["replaceable_heat_mwh_th"].sum(),
            "pct_below_gas": x.loc[x["below_gas"], "replaceable_heat_mwh_th"].sum() / x["replaceable_heat_mwh_th"].sum() * 100,
            "pct_land_matched": x["land_matched_heat_mwh"].sum() / x["replaceable_heat_mwh_th"].sum() * 100,
            "pct_both": x["green_and_local_heat_mwh"].sum() / x["replaceable_heat_mwh_th"].sum() * 100,
        }), include_groups=False,
    ).sort_values("heat_TWh", ascending=False)
    print(g.round(1).to_string())


if __name__ == "__main__":
    main()
