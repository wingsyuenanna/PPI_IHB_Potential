# load_re_costs.py

import pandas as pd

# Technology labels in the unified BNEF output (bnef_solar_pv_costs_v4.csv)
SOLAR_TECH = "PV fixed-axis"
BATTERY_TECH = "Utility-scale battery (4h)"

# Optional thermal / IHB rows in heat-battery CSV (year-specific).
THERMAL_ROW_CAPEX_KWH = "Thermal CAPEX $/kWh"
THERMAL_ROW_OPEX_PCT = "Thermal OPEX frac/yr"
THERMAL_ROW_LIFETIME_Y = "Thermal Lifetime yr"
THERMAL_ROW_DISCOUNT = "Thermal Discount rate"
THERMAL_ROW_EFF_LE_200 = "Thermal Eff <=200C"
THERMAL_ROW_EFF_GT_200 = "Thermal Eff >200C"
THERMAL_ROW_T_MAX_C = "Thermal T_max C"
THERMAL_ROW_T_MIN_C = "Thermal T_min C"
THERMAL_ROW_CD_RATIO = "Thermal Charge/Discharge ratio min"

# Energy Innovation industrial thermal battery (IHB) power + energy CAPEX.
IHB_ROW_INPUT_CAPEX_KW = "IHB input CAPEX $/kW"
IHB_ROW_DELIVERY_CAPEX_KW = "IHB delivery CAPEX $/kW"
IHB_ROW_STORAGE_CAPEX_KWH = "IHB storage CAPEX $/kWh"
IHB_ROW_RTE = "IHB RTE"
IHB_ROW_OPEX = "IHB OPEX frac/yr"

# Industrial heat pump CAPEX/FOM inflated to project-start USD
# (see COST_YEAR_INFLATION.md). Source: Rissman 2022 / 2021 basis.
# FOM is absolute $/kWth-yr (not % of CAPEX).
HP_ROW_CAPEX_LT = "HP CAPEX below100C $/kWth"
HP_ROW_CAPEX_MT = "HP CAPEX 100C-200C $/kWth"
HP_ROW_FOM_LT = "HP FOM below100C $/kWth/yr"
HP_ROW_FOM_MT = "HP FOM 100C-200C $/kWth/yr"
HP_ROW_VOM = "HP VOM $/MWhth"
HP_ROW_LIFE = "HP lifetime yr"

# BNEF 4h utility battery embeds energy in the $/kW price; implied $/kWh = capex/duration.
LIION_DURATION_H = 4.0


def load_re_costs(bnef_filepath, battery_filepath, iso_country, start_year):
    """
    Load solar, Li-ion, IHB, and financial technology costs for a given ISO country
    and start year.

    - **Unified BNEF file** (bnef_filepath): solar CAPEX/O&M, financial CRF, and
      utility-scale Li-ion battery CAPEX/FOM by (iso3_country, year).
    - **Heat-battery file** (battery_filepath): Energy Innovation IHB CAPEX
      ($/kW-in, $/kW-out, $/kWh) plus legacy thermal rows.

    Returns dict with keys: ``financial``, ``solar``, ``battery`` (incl. Li-ion + IHB).
    """
    df = pd.read_csv(bnef_filepath)
    year = int(start_year)

    # Solar + financial (CRF from PV row)
    solar_mask = (
        (df["iso3_country"] == iso_country)
        & (df["year"] == year)
        & (df["technology"] == SOLAR_TECH)
    )
    solar_rows = df[solar_mask]
    if solar_rows.empty:
        raise ValueError(
            f"No BNEF solar cost row for iso3_country='{iso_country}', year={year}, "
            f"technology='{SOLAR_TECH}' in {bnef_filepath}"
        )
    pv_row = solar_rows.iloc[0]

    fin_params = {"CRF": float(pv_row["crf"])}
    pv_capex = pv_row.get("capex_$/kw")
    pv_fom = pv_row.get("fom_$/kw/yr")
    if pd.isna(pv_capex) or pd.isna(pv_fom):
        same_tech = df[(df["year"] == year) & (df["technology"] == SOLAR_TECH)]
        pv_capex = same_tech["capex_$/kw"].median() if pd.isna(pv_capex) else pv_capex
        pv_fom = same_tech["fom_$/kw/yr"].median() if pd.isna(pv_fom) else pv_fom
        if pd.isna(pv_capex) or pd.isna(pv_fom):
            raise ValueError(
                f"No valid solar cost for iso3_country='{iso_country}', year={year}. "
                f"Re-run BNEF/scripts/compile_bnef_costs.py to fill proxies."
            )
    solar_params = {
        "Capex": float(pv_capex),
        "Fixed O&M": float(pv_fom) * 1000.0,  # $/kW-yr -> $/MW-yr
    }

    batt_df = pd.read_csv(battery_filepath)
    year_col = str(year)
    if year_col not in batt_df.columns:
        available = [c for c in batt_df.columns if c.strip().isdigit()]
        raise ValueError(
            f"Year {year} not in battery cost file {battery_filepath}. "
            f"Available year columns: {available}"
        )

    def get_optional_battery_row(label: str, default: float) -> float:
        row = batt_df[batt_df["Year"] == label]
        if row.empty:
            return float(default)
        v = row[year_col].iloc[0]
        if pd.isna(v):
            return float(default)
        return float(v)

    batt_params = {
        # Legacy thermal rows (kept for older scripts / reference).
        "Thermal CAPEX $/kWh": get_optional_battery_row(THERMAL_ROW_CAPEX_KWH, 100.0),
        "Thermal OPEX frac/yr": get_optional_battery_row(THERMAL_ROW_OPEX_PCT, 0.02),
        "Thermal Lifetime yr": get_optional_battery_row(THERMAL_ROW_LIFETIME_Y, 25.0),
        "Thermal Discount rate": get_optional_battery_row(THERMAL_ROW_DISCOUNT, 0.07),
        "Thermal Eff <=200C": get_optional_battery_row(THERMAL_ROW_EFF_LE_200, 0.98),
        "Thermal Eff >200C": get_optional_battery_row(THERMAL_ROW_EFF_GT_200, 0.95),
        "Thermal T_max C": get_optional_battery_row(THERMAL_ROW_T_MAX_C, 1500.0),
        "Thermal T_min C": get_optional_battery_row(THERMAL_ROW_T_MIN_C, 1200.0),
        "Thermal Charge/Discharge ratio min": get_optional_battery_row(
            THERMAL_ROW_CD_RATIO, 4.0
        ),
        # Energy Innovation IHB CAPEX / RTE (CRF comes from country BNEF via financial['CRF']).
        "IHB input CAPEX $/kW": get_optional_battery_row(IHB_ROW_INPUT_CAPEX_KW, 116.66),
        "IHB delivery CAPEX $/kW": get_optional_battery_row(
            IHB_ROW_DELIVERY_CAPEX_KW, 349.99
        ),
        "IHB storage CAPEX $/kWh": get_optional_battery_row(
            IHB_ROW_STORAGE_CAPEX_KWH, 5.83
        ),
        "IHB RTE": get_optional_battery_row(IHB_ROW_RTE, 0.95),
        "IHB OPEX frac/yr": get_optional_battery_row(IHB_ROW_OPEX, 0.0),
        # Industrial HP — CAPEX/FOM already inflated to project-start USD in CSV year col.
        "HP CAPEX below100C $/kWth": get_optional_battery_row(HP_ROW_CAPEX_LT, 918.30),
        "HP CAPEX 100C-200C $/kWth": get_optional_battery_row(HP_ROW_CAPEX_MT, 1141.31),
        "HP FOM below100C $/kWth/yr": get_optional_battery_row(HP_ROW_FOM_LT, 15.74),
        "HP FOM 100C-200C $/kWth/yr": get_optional_battery_row(HP_ROW_FOM_MT, 23.61),
        "HP VOM $/MWhth": get_optional_battery_row(HP_ROW_VOM, 0.0),
        "HP lifetime yr": get_optional_battery_row(HP_ROW_LIFE, 25.0),
    }

    # Li-ion: country-matched BNEF utility-scale 4h battery.
    batt_mask = (
        (df["iso3_country"] == iso_country)
        & (df["year"] == year)
        & (df["technology"] == BATTERY_TECH)
    )
    batt_bnef_rows = df[batt_mask]
    if batt_bnef_rows.empty:
        raise ValueError(
            f"No BNEF battery row for iso3_country='{iso_country}', year={year}, "
            f"technology='{BATTERY_TECH}' in {bnef_filepath}"
        )
    batt_bnef = batt_bnef_rows.iloc[0]
    li_capex_kw = batt_bnef.get("capex_$/kw")
    fom_batt_kwyr = batt_bnef.get("fom_$/kw/yr")
    if pd.isna(li_capex_kw) or pd.isna(fom_batt_kwyr):
        same_batt = df[(df["year"] == year) & (df["technology"] == BATTERY_TECH)]
        if pd.isna(li_capex_kw):
            li_capex_kw = same_batt["capex_$/kw"].median()
        if pd.isna(fom_batt_kwyr):
            fom_batt_kwyr = same_batt["fom_$/kw/yr"].median()
        if pd.isna(li_capex_kw) or pd.isna(fom_batt_kwyr):
            raise ValueError(
                f"No valid Li-ion cost for iso3_country='{iso_country}', year={year}."
            )

    # Implied energy price from 4h system CAPEX; FOM stays on power.
    batt_params["Li-ion CAPEX $/kW"] = float(li_capex_kw)
    batt_params["Li-ion CAPEX $/kWh"] = float(li_capex_kw) / LIION_DURATION_H
    batt_params["Li-ion duration_h"] = LIION_DURATION_H
    batt_params["Li-ion Fixed O&M $/MW-yr"] = float(fom_batt_kwyr) * 1000.0
    batt_params["Fixed O&M"] = batt_params["Li-ion Fixed O&M $/MW-yr"]  # legacy key

    return {"financial": fin_params, "solar": solar_params, "battery": batt_params}


## Legacy code (previous calculations for WACC, this is handled at the bnef layer now)
def calc_wacc(fin_params):
    """Calculate weighted average cost of capital (WACC) and add to fin_params."""
    R = fin_params["Debt ratio (%)"]
    E = fin_params["Cost of equity (%)"]
    D = fin_params["Cost of debt (bps)"]
    WACC = E * (1 - R) + (D * 0.0001) * R
    fin_params["WACC"] = WACC
    return fin_params


def calc_crf(fin_params, project_lifetime):
    """Calculate capital recovery factor (CRF) and add to fin_params."""
    wacc = fin_params["WACC"]
    CRF = (wacc * (1 + wacc) ** project_lifetime) / ((1 + wacc) ** project_lifetime - 1)
    fin_params["CRF"] = CRF
    return fin_params
