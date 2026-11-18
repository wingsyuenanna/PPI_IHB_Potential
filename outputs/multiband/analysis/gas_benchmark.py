"""EU-27 gas heat and grid-electricity benchmarks for plots, computed from the model's input files.

Replaces the hard-coded GAS93 = 63.25 / 0.85 + (0.202 / 0.85) * 79 (poster value).
Uses the same inputs and formula as the country benchmarks in
Input/industrial_heat_pump_costs/eu_heat_pump_costs_by_country.csv (Methods eq. gas):

    gas heat cost = (gas price + EUA x EF_NG) / boiler efficiency

  gas price          Eurostat nrg_pc_203, band I4, X_VAT, EU27_2020, mean of 2025-S1/S2
                     (Input/industrial_heat_pump_costs/eurostat_nrg_pc_203_I4_XVAT_2025.csv)
  EUA, efficiency    Input/industrial_heat_pump_costs/eu_heat_pump_cost_assumptions.csv
  EF_NG              56.1 tCO2/TJ NCV (IPCC 2006) = 0.202 tCO2/MWh_fuel,NCV

Net calorific basis throughout (2026-11-11): the 0.94 boiler efficiency is treated as a net
(LHV) value, like all heat-side data (IPCC factors, Hotmaps SEC, JRC-IDEES). Eurostat gas prices
are per kWh of gross calorific value, so they are converted to net with NCV = 0.9 x GCV for
natural gas (IPCC 2006 Vol. 2 Ch. 1, s. 1.4.1.2: NCV about 10% below GCV for gas).
GAS_PRICE_EU is the net-basis price (EUR/MWh_NCV); GAS_PRICE_EU_GCV is the Eurostat value.

Grid electricity reference (replaces hard-coded ELEC171 = 162.0 / 0.95):

    ELEC_EU = electricity price / IHB round-trip efficiency

  electricity price  Eurostat nrg_pc_205, X_VAT, EU27_2020, mean of 2025-S1/S2, band set in
                     eu_heat_pump_cost_assumptions.csv ("Grid electricity band (nrg_pc_205)")
                     (Input/industrial_heat_pump_costs/eurostat_nrg_pc_205_XVAT_2025_EU27.csv)
  RTE                "IHB round-trip efficiency (grid reference)" in the assumptions CSV

Change an input file and every plot that imports GAS_EU or ELEC_EU follows.
"""

from pathlib import Path

import pandas as pd

_INPUTS = Path(__file__).resolve().parents[3] / "Input" / "industrial_heat_pump_costs"
EF_NG = 56.1 * 3.6 / 1000  # tCO2 per MWh_fuel (NCV)
NCV_PER_GCV_NG = 0.9  # IPCC 2006 Vol. 2 Ch. 1, s. 1.4.1.2


def _assumption(name: str, as_float: bool = True):
    a = pd.read_csv(_INPUTS / "eu_heat_pump_cost_assumptions.csv")
    v = a.loc[a["assumption"] == name, "value"].iloc[0]
    return float(v) if as_float else str(v)


EUA = _assumption("EUA carbon price")  # EUR/tCO2
ETA_BOILER = _assumption("Gas boiler efficiency (baseline)")
_eurostat = pd.read_csv(_INPUTS / "eurostat_nrg_pc_203_I4_XVAT_2025.csv")
GAS_PRICE_EU_GCV = float(_eurostat.loc[_eurostat["geo"] == "EU27_2020", "eur_mwh"].mean())  # EUR/MWh_GCV (Eurostat)
GAS_PRICE_EU = GAS_PRICE_EU_GCV / NCV_PER_GCV_NG  # EUR/MWh_NCV
GAS_EU = (GAS_PRICE_EU + EUA * EF_NG) / ETA_BOILER  # EUR/MWh_th

ELEC_BAND = _assumption("Grid electricity band (nrg_pc_205)", as_float=False)
RTE_GRID = _assumption("IHB round-trip efficiency (grid reference)")
_elec = pd.read_csv(_INPUTS / "eurostat_nrg_pc_205_XVAT_2025_EU27.csv")
ELEC_PRICE_EU = float(_elec.loc[(_elec["geo"] == "EU27_2020") & (_elec["nrg_cons"] == ELEC_BAND), "eur_mwh"].mean())
ELEC_EU = ELEC_PRICE_EU / RTE_GRID  # EUR/MWh_th


def country_gas_heat() -> dict:
    """Gas heat cost by country (EUR/MWh_th), iso3 -> value. The UK uses the Irish value."""
    g = pd.read_csv(_INPUTS / "eu_heat_pump_costs_by_country.csv")
    m = g.set_index("iso3")["gas_heat_cost_eur_mwh"].to_dict()
    m["GBR"] = m["IRL"]
    return m


def max_savings_sites(long: pd.DataFrame) -> pd.DataFrame:
    """Maximum-savings operating point per site (Methods, Eq. maxsav).

    `long` has one row per site and availability floor, with columns source_id,
    iso3_country, served (MWh) and lcoh (EUR/MWh). The saving is
    served x (country gas heat cost - LCOH), evaluated only at floors with
    LCOH <= the country's gas heat cost. A site with no such floor serves no heat
    (served = 0). Returns one row per site; aggregate after this step.
    """
    d = long.copy()
    d["gas"] = d["iso3_country"].map(country_gas_heat())
    d["surplus"] = d["served"] * (d["gas"] - d["lcoh"])
    d.loc[d["lcoh"] > d["gas"], "surplus"] = -1.0
    d = d.dropna(subset=["source_id", "surplus"])
    best = d.loc[d.groupby("source_id")["surplus"].idxmax()].copy()
    best.loc[best["surplus"] < 0, "served"] = 0.0
    return best


def max_heat_sites(long: pd.DataFrame) -> pd.DataFrame:
    """Maximum-heat operating point per site (Methods, Eq. maxheat).

    The highest availability floor with LCOH <= the country's gas heat cost. Same input
    as max_savings_sites. A site with no such floor serves no heat (served = 0).
    Returns one row per site.
    """
    d = long.copy()
    d["gas"] = d["iso3_country"].map(country_gas_heat())
    below = d[d["lcoh"] <= d["gas"]]
    best = below.loc[below.groupby("source_id")["availability_floor"].idxmax()].copy()
    rest = d[~d["source_id"].isin(best["source_id"])].drop_duplicates("source_id").copy()
    rest["served"] = 0.0
    rest["lcoh"] = float("nan")
    return pd.concat([best, rest], ignore_index=True)


if __name__ == "__main__":
    print(f"EU-27 gas price {GAS_PRICE_EU_GCV:.2f} EUR/MWh_GCV = {GAS_PRICE_EU:.2f} EUR/MWh_NCV, EUA {EUA} EUR/t, "
          f"eta {ETA_BOILER} -> gas heat {GAS_EU:.1f} EUR/MWh_th")
    print(f"EU-27 electricity {ELEC_PRICE_EU:.2f} EUR/MWh (band {ELEC_BAND}), RTE {RTE_GRID} "
          f"-> grid-electric heat {ELEC_EU:.1f} EUR/MWh_th")
