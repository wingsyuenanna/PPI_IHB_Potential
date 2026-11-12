# Anna Yuen
# 2/4/2026  (extended with global benchmark — solar PV fixed-axis)
#
# compile BNEF cost based on bloomberg and IRENA
# + build global benchmark for countries without BNEF Solar PV estimates
#
# Benchmark strategy for missing countries
# ─────────────────────────────────────────
# For each missing country we know (or can look up):
#   • CRF  — from IRENA WACC + IMF inflation (already computed in main pipeline)
#   • A regional Capex proxy — mean Capex of countries in the same World Bank
#     income group AND geographic region, falling back to global mean
#
# Annual cost (benchmark) = (Capex_proxy * CRF_country) + (FOM_proxy / 1000)
#
# This means the benchmark uses country-specific financing costs while
# proxying the hardware/construction cost from similar peers.
# ─────────────────────────────────────────────────────────────────────────────

import json
from pathlib import Path
import argparse

import pandas as pd
import numpy as np

# ── Config ─────────────────────────────────────────────────────────────────────
VERSION   = 'v5'
LIFETIME  = 25
YEARS     = [2025, 2030]
BENCHMARK_TECH  = 'PV fixed-axis'   # the technology we are benchmarking
IRENA_TECH      = 'Solar PV'        # matching key in IRENA cost-of-capital data

HERE = Path(__file__).resolve().parent   # paths below are relative to this folder (Input/bnef)
bnef_file_path   = str(HERE / 'input/BNEF_raw_data_2024.xlsx')
COUNTRY2ISO_path = str(HERE / 'input/COUNTRY2ISO.json')
IRENA_path       = str(HERE / 'input/IRENA_cost_of_cap.json')
inflation_path   = str(HERE / 'input/weoapr2025all.csv')
WB_path          = str(HERE / 'input/wb_income_groups.json')
unified_output   = str(HERE / f'output/bnef_solar_pv_costs_{VERSION}.csv')
battery_input_path  = str(HERE / 'input/battery_2024_cost.csv')
battery_output_path = str(HERE / 'output/battery_2025_cost.csv')
BATTERY_TARGET_DOLLAR_YEAR = 2025  # output costs in this dollar year (USA inflation)

bnef_tech  = [
    'PV fixed-axis',
    'PV tracking',
    'Wind offshore',
    'Wind onshore',
    'Utility-scale battery (4h)',
    'Coal',
    'CCGT',
    'OCGT',
]
bnef2IRENA = {
    'PV fixed-axis':  'Solar PV',
    'PV tracking':    'Solar PV',
    'Wind offshore':  'Onshore Wind',   # NOTE: original mapping appears swapped —
    'Wind onshore':   'Offshore Wind',  #       verify against your IRENA categories
    # Use country-specific financing (CRF) even if IRENA lacks a storage category in our input
    'Utility-scale battery (4h)': 'Solar PV',
    # IRENA input has no separate fossil WACC rows; reuse Solar PV CRF per country (same as battery).
    'Coal': 'Solar PV',
    'CCGT': 'Solar PV',
    'OCGT': 'Solar PV',
}

DEFAULT_INFLATION = 0.03   # fallback when IMF data is missing

# Dollar basis. True = real 2025 USD: CRF uses IRENA's real WACC directly (no inflation uplift),
# consistent with real-dollar CAPEX/FOM. False = old nominal basis (real WACC x IMF CPI forecast).
REAL_BASIS = True


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def load_json(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


def build_crf_table(irena_path: str, inflation_path: str, lifetime: int) -> pd.DataFrame:
    """
    Compute Capital Recovery Factor (CRF) for every country × technology
    combination in IRENA using nominal WACC = real WACC inflated by IMF forecast.

    CRF = (i * (1+i)^n) / ((1+i)^n - 1)
    """
    cost_of_cap_df = pd.DataFrame(load_json(irena_path))

    imf = pd.read_csv(inflation_path)
    infl = imf[imf['WEO Subject Code'] == 'PCPIPCH'].copy()
    year_cols = ['2025', '2026', '2027', '2028', '2029', '2030']
    for col in year_cols:
        infl[col] = pd.to_numeric(infl[col], errors='coerce')
    infl['inflation_rate'] = infl[year_cols].mean(axis=1)
    infl = infl[['ISO', 'inflation_rate']].rename(columns={'ISO': 'ISO3'})

    cost_of_cap_df = cost_of_cap_df.merge(infl, on='ISO3', how='left')
    cost_of_cap_df['inflation_rate'] = cost_of_cap_df['inflation_rate'].fillna(DEFAULT_INFLATION)

    real_wacc = cost_of_cap_df['WACC_Percentage'] / 100
    cost_of_cap_df['WACC_Nominal'] = (
        (1 + real_wacc) * (1 + cost_of_cap_df['inflation_rate'] / 100) - 1
    )

    # Rate used for the CRF: real WACC on the real-dollar basis, nominal WACC otherwise.
    # (The output column is still named WACC_Nominal / wacc_nominal; it holds the rate used.)
    i_col = real_wacc if REAL_BASIS else cost_of_cap_df['WACC_Nominal']
    cost_of_cap_df['WACC_Nominal'] = i_col
    cf    = (1 + i_col) ** lifetime
    cost_of_cap_df['CRF'] = (i_col * cf) / (cf - 1)

    return cost_of_cap_df[['ISO3', 'Technology', 'WACC_Nominal', 'CRF']]


def build_bnef_wide(bnef_file_path: str, country2iso: dict) -> pd.DataFrame:
    """
    Load BNEF Excel, filter to bnef_tech + Mid scenario, pivot to wide format.
    """
    bnef    = pd.read_excel(bnef_file_path)
    bnef_RE = bnef[
        bnef['Technology'].isin(bnef_tech) & (bnef['Scenario'] == 'Mid')
    ][['Metric', 'Region', 'Technology', 'Scenario', 'Unit', 2025, 2030]]

    bnef_RE['iso3_country'] = bnef_RE['Region'].map(country2iso)

    melted = bnef_RE.melt(
        id_vars=['Metric', 'Region', 'Technology', 'Scenario', 'Unit', 'iso3_country'],
        value_vars=YEARS,
        var_name='Year',
        value_name='Value',
    )
    wide = melted.pivot_table(
        index=['iso3_country', 'Region', 'Scenario'],
        columns=['Technology', 'Metric', 'Year', 'Unit'],
        values='Value',
    )
    wide.columns = [f"{t}_{m}_{y}_{u}" for t, m, y, u in wide.columns]
    return wide.reset_index()


def calc_annual_cost(wide: pd.DataFrame, crf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorised annual cost calculation (replaces the original row-by-row loop).
    annual_cost = (Capex [$/kW] * CRF) + (Fixed O&M [$/MW/yr] / 1000)
    """
    rows = []
    for tech in bnef_tech:
        irena_tech = bnef2IRENA[tech]
        crf_sub    = crf_df[crf_df['Technology'] == irena_tech][['ISO3', 'CRF']]

        tmp = wide[['iso3_country', 'Region', 'Scenario']].copy()
        tmp = tmp.merge(crf_sub, left_on='iso3_country', right_on='ISO3', how='left')

        for yr in YEARS:
            capex_col = f'{tech}_Capex_{yr}_$/kW'
            fom_col   = f'{tech}_Fixed O&M_{yr}_$/MW/yr'

            capex = wide.get(capex_col)
            fom   = wide.get(fom_col)

            if capex is not None and fom is not None:
                tmp[f'{tech}_calc_annual_cost_{yr}_$kW/yr'] = (
                    capex.values * tmp['CRF'].values + fom.values / 1_000
                )
            else:
                tmp[f'{tech}_calc_annual_cost_{yr}_$kW/yr'] = np.nan

        rows.append(tmp.drop(columns=['ISO3', 'CRF']))

    # All sub-frames share the same index so we merge them horizontally
    cost_cols = [df.drop(columns=['iso3_country', 'Region', 'Scenario']) for df in rows]
    return pd.concat([wide] + cost_cols, axis=1)


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL BENCHMARK  (Solar PV fixed-axis)
# ══════════════════════════════════════════════════════════════════════════════

# World Bank income-group lookup — loaded from wb_income_groups.json
# Format: [{"ISO3": "USA", "income_group": "HIC", "wb_region": "North America"}, ...]
def load_wb_income_groups(path: str) -> dict:
    """Load wb_income_groups.json -> {ISO3: (income_group, wb_region)}."""
    records = load_json(path)
    return {r['ISO3']: (r['income_group'], r['wb_region']) for r in records}


def get_wb_metadata(iso3: str, wb_lookup: dict) -> tuple:
    """Return (income_group, wb_region) for a country, or ('Unknown', 'Unknown')."""
    return wb_lookup.get(iso3, ('Unknown', 'Unknown'))


def build_global_benchmark(
    bnef_wide: pd.DataFrame,
    crf_df: pd.DataFrame,
    all_iso3: list[str],
    wb_lookup: dict,
) -> pd.DataFrame:
    """
    For every ISO3 country in `all_iso3` that is NOT in bnef_wide,
    estimate Solar PV fixed-axis annual costs using:
      1. Country-specific CRF  (from IRENA WACC + IMF inflation)
      2. Regional Capex proxy  (mean of peer countries = same income group
                                + same WB region, falling back to income group,
                                then global mean)

    Returns a DataFrame with one row per missing country × year.
    """
    # ── Identify countries with BNEF data ─────────────────────────────────────
    covered = set(bnef_wide['iso3_country'].dropna().unique())
    missing = [c for c in all_iso3 if c not in covered]
    print(f"  Countries with BNEF data  : {len(covered)}")
    print(f"  Countries missing BNEF    : {len(missing)}")

    # ── Build reference table: Capex & FOM by income_group × wb_region ────────
    ref = bnef_wide[['iso3_country']].copy()
    ref[['income_group', 'wb_region']] = pd.DataFrame(
        ref['iso3_country'].apply(lambda x: get_wb_metadata(x, wb_lookup)).tolist(),
        index=ref.index,
    )

    benchmark_rows = []

    for yr in YEARS:
        capex_col = f'{BENCHMARK_TECH}_Capex_{yr}_$/kW'
        fom_col   = f'{BENCHMARK_TECH}_Fixed O&M_{yr}_$/MW/yr'

        if capex_col not in bnef_wide.columns or fom_col not in bnef_wide.columns:
            print(f"  [warn] Missing columns for {yr} — skipping benchmark year.")
            continue

        # Attach income group to bnef rows for grouping
        ref_yr = ref.copy()
        ref_yr['capex'] = bnef_wide[capex_col].values
        ref_yr['fom']   = bnef_wide[fom_col].values

        def peer_mean(iso3: str, col: str) -> float:
            """Mean of peers: region+income → income → global."""
            ig, wr = get_wb_metadata(iso3, wb_lookup)
            mask_both   = (ref_yr['income_group'] == ig) & (ref_yr['wb_region'] == wr)
            mask_income = ref_yr['income_group'] == ig

            for mask in [mask_both, mask_income]:
                vals = ref_yr.loc[mask, col].dropna()
                if not vals.empty:
                    return float(vals.mean())

            # Global fallback
            return float(ref_yr[col].dropna().mean())

        for iso3 in missing:
            capex_proxy = peer_mean(iso3, 'capex')
            fom_proxy   = peer_mean(iso3, 'fom')

            crf_row = crf_df[
                (crf_df['ISO3'] == iso3) & (crf_df['Technology'] == IRENA_TECH)
            ]

            if crf_row.empty:
                # Fall back to regional mean CRF among peers
                ig, wr = get_wb_metadata(iso3, wb_lookup)
                peer_iso3s = [
                    k for k, (grp, reg) in wb_lookup.items()
                    if grp == ig and reg == wr and k != iso3
                ]
                peer_crfs = crf_df[
                    crf_df['ISO3'].isin(peer_iso3s) &
                    (crf_df['Technology'] == IRENA_TECH)
                ]['CRF']
                crf_val = float(peer_crfs.mean()) if not peer_crfs.empty else float(
                    crf_df[crf_df['Technology'] == IRENA_TECH]['CRF'].mean()
                )
                crf_source = 'peer_mean'
            else:
                crf_val    = float(crf_row['CRF'].iloc[0])
                crf_source = 'irena'

            annual_cost = (capex_proxy * crf_val) + (fom_proxy / 1_000)
            ig, wr = get_wb_metadata(iso3, wb_lookup)

            benchmark_rows.append({
                'iso3_country':     iso3,
                'year':             yr,
                'technology':       BENCHMARK_TECH,
                'capex_proxy_$/kW': capex_proxy,
                'fom_proxy_$/MW/yr':fom_proxy,
                'crf':              crf_val,
                'crf_source':       crf_source,
                'annual_cost_$kW/yr': annual_cost,
                'income_group':     ig,
                'wb_region':        wr,
                'proxy_method':     'regional_peer_mean',
            })

    benchmark_df = pd.DataFrame(benchmark_rows)
    print(f"  Benchmark rows generated  : {len(benchmark_df)}")
    return benchmark_df



# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED OUTPUT  — one CSV, one row per country × year
# ══════════════════════════════════════════════════════════════════════════════

def build_unified_output_for_tech(
    *,
    bnef_wide: pd.DataFrame,
    crf_df: pd.DataFrame,
    wb_lookup: dict,
    tech: str,
    irena_tech_for_crf: str,
    lcoe_only: bool = False,
) -> pd.DataFrame:
    """
    Combine BNEF-sourced rows and proxied rows into a single tidy DataFrame.

    Proxy logic (for countries not in BNEF or with missing values):
      1. peer_mean_region_income — mean of countries with same WB income group and region
      2. peer_mean_income — mean of countries with same income group only
      3. global_mean — mean across all BNEF countries for this technology
    So LIC (and any group with no BNEF data for this tech, e.g. utility-scale battery)
    gets the global mean; proxy_peers lists the BNEF countries used for that mean.
    If lcoe_only=True, only LCOE is populated; CRF/Capex/FOM/annual_cost are left blank.

    Columns in final output
    ───────────────────────
    iso3_country        ISO 3166-1 alpha-3
    year                2025 or 2030
    income_group        HIC / UMIC / LMIC / LIC  (World Bank FY2025)
    wb_region           World Bank regional classification
    capex_$/kW          Capital expenditure ($/kW)
    fom_$/kW/yr         Fixed O&M converted to $/kW/yr  (= raw $/MW/yr ÷ 1000)
    wacc_nominal        Nominal WACC used for CRF calculation
    crf                 Capital Recovery Factor
    annual_cost_$/kw/yr (Capex × CRF) + FOM  — levelised annual capital+fixed cost
    data_source         'bnef'  | 'proxied'
    capex_source        'bnef'  | 'peer_mean_region_income' | 'peer_mean_income'
                        | 'global_mean'
    crf_source          'irena' | 'peer_mean'
    proxy_peers         ISO3 codes of the peer group used for Capex/FOM proxy
                        (empty string for BNEF rows)
    """

    TECH = tech
    IRENA = irena_tech_for_crf

    # ── CRF lookup: ISO3 → (nominal_wacc, crf) ───────────────────────────────
    crf_solar = crf_df[crf_df['Technology'] == IRENA].set_index('ISO3')[['WACC_Nominal', 'CRF']]

    # ── Build reference lookup for proxying: iso3 → (capex, fom) per year ────
    # We need the bnef capex/fom values with WB metadata attached for peer matching
    ref_base = bnef_wide[['iso3_country']].copy()
    ref_base[['income_group', 'wb_region']] = pd.DataFrame(
        ref_base['iso3_country'].apply(lambda x: get_wb_metadata(x, wb_lookup)).tolist(),
        index=ref_base.index,
    )

    covered_iso3 = set(bnef_wide['iso3_country'].dropna().unique())

    # Universe:
    # - normal mode: all ISO3s with IRENA WACC data + all ISO3s in wb_lookup
    # - LCOE-only mode: all ISO3s in wb_lookup + all BNEF covered ISO3s
    if lcoe_only:
        all_iso3 = sorted(set(wb_lookup.keys()) | covered_iso3)
    else:
        all_iso3 = sorted(
            set(crf_df[crf_df['Technology'] == IRENA]['ISO3'].tolist()) |
            set(wb_lookup.keys())
        )

    rows = []

    for yr in YEARS:
        capex_col = f'{TECH}_Capex_{yr}_$/kW'
        fom_col   = f'{TECH}_Fixed O&M_{yr}_$/MW/yr'
        vom_col   = f'{TECH}_Variable O&M_{yr}_$/MWh'
        lcoe_col  = f'{TECH}_LCOE_{yr}_$/MWh'

        # Reference series for proxy calculations
        ref_yr = ref_base.copy()
        ref_yr['capex'] = bnef_wide[capex_col].values if capex_col in bnef_wide.columns else np.nan
        ref_yr['fom']   = bnef_wide[fom_col].values   if fom_col   in bnef_wide.columns else np.nan
        ref_yr['vom']   = bnef_wide[vom_col].values   if vom_col   in bnef_wide.columns else np.nan
        ref_yr['lcoe']  = bnef_wide[lcoe_col].values  if lcoe_col  in bnef_wide.columns else np.nan

        def resolve_proxy(iso3: str, col: str) -> tuple[float, str, str]:
            """
            Return (value, source_label, peer_iso3s_str).
            Tries: same income_group + wb_region → same income_group → global mean.
            For groups with no BNEF data (e.g. LIC for utility-scale battery), all
            countries in that group get the global mean across BNEF countries.
            """
            ig, wr = get_wb_metadata(iso3, wb_lookup)
            candidates = [
                (ref_yr[(ref_yr['income_group'] == ig) & (ref_yr['wb_region'] == wr)],
                 'peer_mean_region_income'),
                (ref_yr[ref_yr['income_group'] == ig],
                 'peer_mean_income'),
                (ref_yr,
                 'global_mean'),
            ]
            for subset, label in candidates:
                vals = subset[col].dropna()
                if not vals.empty:
                    peers = '|'.join(subset.loc[vals.index, 'iso3_country'].tolist())
                    return float(vals.mean()), label, peers
            return np.nan, 'global_mean', ''

        for iso3 in all_iso3:
            ig, wr = get_wb_metadata(iso3, wb_lookup)

            if lcoe_only:
                if iso3 in covered_iso3 and lcoe_col in bnef_wide.columns:
                    row_mask = bnef_wide['iso3_country'] == iso3
                    lcoe_val = bnef_wide.loc[row_mask, lcoe_col].iloc[0]
                    if pd.isna(lcoe_val):
                        lcoe_val, lcoe_src, peers_str = resolve_proxy(iso3, 'lcoe')
                        data_src = 'proxied'
                    else:
                        lcoe_src = 'bnef'
                        peers_str = ''
                        data_src = 'bnef'
                else:
                    lcoe_val, lcoe_src, peers_str = resolve_proxy(iso3, 'lcoe')
                    data_src = 'proxied'

                rows.append({
                    'iso3_country':       iso3,
                    'year':               yr,
                    'technology':         TECH,
                    'income_group':       ig,
                    'wb_region':          wr,
                    'capex_$/kw':         np.nan,
                    'fom_$/kw/yr':        np.nan,
                    'vom_$/mwh':          np.nan,
                    'lcoe_$/mwh':         round(lcoe_val, 2) if pd.notna(lcoe_val) else np.nan,
                    'wacc_nominal':       np.nan,
                    'crf':                np.nan,
                    'annual_cost_$/kw/yr':np.nan,
                    'data_source':        data_src,
                    'capex_source':       lcoe_src,
                    'crf_source':         'not_used',
                    'proxy_peers':        peers_str,
                })
                continue

            # ── CRF ──────────────────────────────────────────────────────────
            if iso3 in crf_solar.index:
                crf_val   = float(crf_solar.loc[iso3, 'CRF'])
                wacc_nom  = float(crf_solar.loc[iso3, 'WACC_Nominal']) 
                crf_src   = 'irena'
            else:
                # Peer mean CRF
                ig2, wr2 = ig, wr
                peer_mask = crf_solar.index.isin([
                    k for k, (g, r) in wb_lookup.items()
                    if g == ig2 and r == wr2 and k != iso3
                ])
                peer_crfs = crf_solar.loc[peer_mask, 'CRF'] if peer_mask.any() else crf_solar['CRF']
                crf_val   = float(peer_crfs.mean())
                wacc_nom  = np.nan
                crf_src   = 'peer_mean'

            # ── Capex & FOM ──────────────────────────────────────────────────
            if iso3 in covered_iso3 and capex_col in bnef_wide.columns:
                row_mask = bnef_wide['iso3_country'] == iso3
                capex_val = bnef_wide.loc[row_mask, capex_col].iloc[0]
                fom_val   = bnef_wide.loc[row_mask, fom_col].iloc[0] if fom_col in bnef_wide.columns else np.nan
                vom_val   = bnef_wide.loc[row_mask, vom_col].iloc[0] if vom_col in bnef_wide.columns else np.nan
                lcoe_val  = bnef_wide.loc[row_mask, lcoe_col].iloc[0] if lcoe_col in bnef_wide.columns else np.nan
                # Fallback: if BNEF row exists but capex/FOM are missing (e.g. no battery data for this country), use global proxy
                if pd.isna(capex_val) or pd.isna(fom_val):
                    capex_val, capex_src, peers_str = resolve_proxy(iso3, 'capex')
                    fom_val,   _,         _          = resolve_proxy(iso3, 'fom')
                    vom_val,   _,         _          = resolve_proxy(iso3, 'vom')
                    lcoe_val,  _,         _          = resolve_proxy(iso3, 'lcoe')
                    data_src  = 'proxied'
                else:
                    data_src  = 'bnef'
                    capex_src = 'bnef'
                    peers_str = ''
            else:
                capex_val, capex_src, peers_str = resolve_proxy(iso3, 'capex')
                fom_val,   _,         _          = resolve_proxy(iso3, 'fom')
                vom_val,   _,         _          = resolve_proxy(iso3, 'vom')
                lcoe_val,  _,         _          = resolve_proxy(iso3, 'lcoe')
                data_src  = 'proxied'

            fom_per_kw = fom_val / 1_000 if pd.notna(fom_val) else np.nan
            annual_cost = (capex_val * crf_val + fom_per_kw
                           if pd.notna(capex_val) and pd.notna(fom_per_kw)
                           else np.nan)
            rows.append({
                'iso3_country':       iso3,
                'year':               yr,
                'technology':         TECH,
                'income_group':       ig,
                'wb_region':          wr,
                'capex_$/kw':         round(capex_val, 2)   if pd.notna(capex_val)  else np.nan,
                'fom_$/kw/yr':        round(fom_per_kw, 4)  if pd.notna(fom_per_kw) else np.nan,
                'vom_$/mwh':          round(vom_val, 4)     if pd.notna(vom_val)    else np.nan,
                'lcoe_$/mwh':         round(lcoe_val, 2)    if pd.notna(lcoe_val)   else np.nan,
                'wacc_nominal':       round(wacc_nom, 6),
                'crf':                round(crf_val, 6),
                'annual_cost_$/kw/yr':round(annual_cost, 2)  if pd.notna(annual_cost) else np.nan,
                'data_source':        data_src,
                'capex_source':       capex_src,
                'crf_source':         crf_src,
                'proxy_peers':        peers_str,
            })

    unified = pd.DataFrame(rows).sort_values(['iso3_country', 'year']).reset_index(drop=True)
    print(f"  Unified rows: {len(unified)}  "
          f"(bnef: {(unified['data_source']=='bnef').sum()}, "
          f"proxied: {(unified['data_source']=='proxied').sum()})")
    return unified

# ══════════════════════════════════════════════════════════════════════════════
# BATTERY COMPONENT COST (Pack, Rack, BOS+EMS, EPC, PCS+Overhead by year)
# ══════════════════════════════════════════════════════════════════════════════

def generate_battery_cost_csv(
    inflation_path: str,
    battery_input_path: str,
    battery_output_path: str,
    target_dollar_year: int = BATTERY_TARGET_DOLLAR_YEAR,
    base_dollar_year: int = 2024,
) -> None:
    """
    Convert battery component costs from base-year to target-year dollars using
    USA inflation (from WEO), and write the table used by load_re_costs.

    Replaces the logic in BNEF/notebooks/generate_battery_cost.ipynb.
    Output: Pack, Rack, BOS+EMS, EPC ($/kWh) and PCS+Overhead ($/kW) by year.
    """
    imf = pd.read_csv(inflation_path)
    infl = imf[imf['WEO Subject Code'] == 'PCPIPCH'].copy()
    year_cols = ['2025', '2026', '2027', '2028', '2029', '2030']
    for col in year_cols:
        infl[col] = pd.to_numeric(infl[col], errors='coerce')
    infl['inflation_rate'] = infl[year_cols].mean(axis=1)
    infl = infl[['ISO', 'inflation_rate']].rename(columns={'ISO': 'ISO3'})

    usd_row = infl[infl['ISO3'] == 'USA']
    if usd_row.empty:
        raise ValueError("USA not found in inflation file; cannot convert battery costs.")
    usd_inflation_rate = float(usd_row['inflation_rate'].iloc[0])

    # Convert base-year $ to target-year $: multiply by (1 + r/100)
    factor = 1 + usd_inflation_rate / 100
    battery = pd.read_csv(battery_input_path)
    year_columns = [c for c in battery.columns if str(c).strip().isdigit()]
    for col in year_columns:
        battery[col] = battery[col] * factor

    Path(battery_output_path).parent.mkdir(parents=True, exist_ok=True)
    battery.to_csv(battery_output_path, index=False)
    print(f"  Saved battery component costs (base {base_dollar_year}$ -> {target_dollar_year}$): {battery_output_path}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("Loading reference data ...")
    country2iso = load_json(COUNTRY2ISO_path)
    wb_lookup   = load_wb_income_groups(WB_path)

    print("Building CRF table ...")
    crf_df = build_crf_table(IRENA_path, inflation_path, LIFETIME)
    print(f"  CRF rows: {len(crf_df)}")

    print("Loading and pivoting BNEF data ...")
    bnef_wide = build_bnef_wide(bnef_file_path, country2iso)
    print(f"  BNEF wide rows: {len(bnef_wide)}")

    print("Calculating annualized costs for BNEF countries ...")
    bnef_wide = calc_annual_cost(bnef_wide, crf_df)

    print("\nBuilding unified global outputs (PV, battery 4h, Coal, CCGT, OCGT) ...")
    pv_unified = build_unified_output_for_tech(
        bnef_wide=bnef_wide,
        crf_df=crf_df,
        wb_lookup=wb_lookup,
        tech='PV fixed-axis',
        irena_tech_for_crf='Solar PV',
    )
    batt_unified = build_unified_output_for_tech(
        bnef_wide=bnef_wide,
        crf_df=crf_df,
        wb_lookup=wb_lookup,
        tech='Utility-scale battery (4h)',
        irena_tech_for_crf='Solar PV',
    )
    coal_unified = build_unified_output_for_tech(
        bnef_wide=bnef_wide,
        crf_df=crf_df,
        wb_lookup=wb_lookup,
        tech='Coal',
        irena_tech_for_crf='Solar PV',
        lcoe_only=True,
    )
    ccgt_unified = build_unified_output_for_tech(
        bnef_wide=bnef_wide,
        crf_df=crf_df,
        wb_lookup=wb_lookup,
        tech='CCGT',
        irena_tech_for_crf='Solar PV',
        lcoe_only=True,
    )
    ocgt_unified = build_unified_output_for_tech(
        bnef_wide=bnef_wide,
        crf_df=crf_df,
        wb_lookup=wb_lookup,
        tech='OCGT',
        irena_tech_for_crf='Solar PV',
        lcoe_only=True,
    )
    unified = pd.concat(
        [pv_unified, batt_unified, coal_unified, ccgt_unified, ocgt_unified],
        ignore_index=True,
    )

    Path(unified_output).parent.mkdir(parents=True, exist_ok=True)
    unified['country_name'] = unified['iso3_country'].map(country2iso)
    unified.to_csv(unified_output, index=False)
    print(f"  Saved: {unified_output}")

    # ── Quick diagnostic summary ───────────────────────────────────────────
    print("\nSummary (2025, by technology, data_source and income_group):")
    summary = (
        unified[unified['year'] == 2025]
        .groupby(['technology', 'data_source', 'income_group'])
        .agg(
            n_countries      =('iso3_country',       'count'),
            mean_capex     =('capex_$/kw',         'mean'),
            mean_fom       =('fom_$/kw/yr',        'mean'),
            mean_lcoe      =('lcoe_$/mwh',         'mean'),
            mean_annual_cost=('annual_cost_$/kw/yr','mean'),
        )
        .round(2)
    ).reset_index()
    
    summary.to_csv(HERE / f'output/bnef_summary_{VERSION}.csv', index=False)
    print(summary.to_string())

    # Battery component cost table (Pack, Rack, BOS+EMS, EPC, PCS+Overhead by year)
    print("\nGenerating battery component cost table ...")
    generate_battery_cost_csv(
        inflation_path=inflation_path,
        battery_input_path=battery_input_path,
        battery_output_path=battery_output_path,
    )

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile country-level BNEF renewable cost curves + global benchmark.")
    parser.add_argument('--version', default=VERSION, help='Version label used in default output filename')
    parser.add_argument('--years', default=",".join(str(y) for y in YEARS), help='Comma-separated years (e.g. 2025,2030)')
    parser.add_argument('--out', default=None, help='Output CSV path (overrides default)')
    args = parser.parse_args()

    VERSION = args.version
    YEARS = [int(x.strip()) for x in args.years.split(",") if x.strip()]
    unified_output = args.out or str(HERE / f'output/bnef_solar_pv_costs_{VERSION}.csv')

    main()