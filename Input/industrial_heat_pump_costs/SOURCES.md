# Gas boiler heat-cost benchmark — sources for Zotero

## Published fossil gas-boiler LCOH (cite for a numeric comparator)

**Reform Institute (2025).** *Clean industrial heat: Electrification scenarios for selected sectors.*  
https://ireform.eu/en/our-projects/clean-industrial-heat-electrification-scenarios-for-selected-sectors-reform-institute-report/

Reproduced in **Agora Industry & Agora Energiewende (2025)**, *The business case for electrifying industrial heat*, **Annex 3 (Poland)**:

| | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|
| **Table 18 — Fossil gas boiler LCOH** (EUR/MWh_th) | **86.3** | 90.9 | 95.7 | 100.3 | 104.7 |
| Table 17 — Fossil gas boiler operating cost (EUR/MWh_th) | 85.1 | 89.7 | 94.5 | 99.1 | 103.5 |

**Cite Table 18** for LCOH (≈ **€86/MWh_th in 2030**). The chart with 85.1 is Table 17 (operating cost only).

Suggested Zotero item: **Report**. Creator: Reform Institute. Year: 2025.

## Agora main report — price scenarios (Germany), not an EU LCOH range

**Agora Industry & Agora Energiewende (2025).** *The business case for electrifying industrial heat.*  
PDF: https://www.agora-industry.org/fileadmin/Projekte/2023/2023-36_IND_Electrification_low_heat/A-IND_396_The_business_case_for_electrifying_industrial_heat_WEB.pdf

- **Table 2** — gas €50 / €40 / €25 per MWh and CO₂ €210 / €145 / €80 per t; 2024 Eurostat-based **gas+CO₂** parameter **€80.6/MWh** (not full boiler LCOH).
- **Fig. 10** — Fraunhofer ISI technology LCOH bars under those price cases.

Do **not** cite Agora for a standalone EU gas-boiler LCOH of €43–100/MWh_th.

## Country-level values used in this repo’s site comparison (primary Results numbers)

File: `eu_heat_pump_costs_by_country.csv` → column `gas_heat_cost_eur_mwh`.

Construction (see `eu_heat_pump_cost_assumptions.csv`):

- Industrial **gas price** by country (`gas_price_eur_mwh`)
- Divided by **boiler efficiency 0.85** (US DOE / industrial steam-boiler convention)
- Plus **EUA carbon** at **73.43 EUR/tCO₂** (2025, ICAP)

Resulting site benchmark: about **€61–122/MWh_th** (~**$66–132/MWh** at EURUSD 1.08);
fleet heat-weighted mean ≈ **$84/MWh** — close to Reform Institute **≈ €86/MWh_th (2030, Table 18)**.

Pipeline: `outputs/multiband/add_gas_benchmark.py`.

**Gas price series (rebuilt 2026-11-05):** Eurostat `nrg_pc_203` (gas prices for non-household consumers),
consumption band **I4 (100,000-999,999 GJ/yr)**, tax level **X_VAT** (excluding VAT and other recoverable taxes
and levies; no EU ETS cost is included), **mean of 2025-S1 and 2025-S2**, unit EUR/kWh x 1000 -> EUR/MWh (gross
calorific value). Extract: `eurostat_nrg_pc_203_I4_XVAT_2025.csv`. Cyprus, Luxembourg and Malta have no I4 value
and use the EU-27 I4 mean (EUR 51.4/MWh); the `gas_price_source` column marks them. The earlier series was
2025-S2 only (EU-27 I4 S2 = 48.3; S1 = 54.5). UK (GBR) is proxied to Ireland in `add_gas_benchmark.py`.

`gas_heat_cost_eur_mwh = (gas_price + 73.43 x 0.202) / 0.94` (EUA 73.43 EUR/tCO2, 2025, ICAP; natural-gas
boiler efficiency 0.94 from Saad et al. 2026 SI Table S3, changed from 0.85 on 2026-11-11).
Result: EUR 59-114/MWh_th by country, heat-weighted mean about EUR 72. The EU-27 benchmark used in plots is
computed the same way from the EU27_2020 I4 price (EUR 51.4/MWh) in `outputs/multiband/analysis/gas_benchmark.py`:
about EUR 70.5/MWh_th. (The poster's EUR 93 used a hard-coded 63.25 EUR/MWh gas price, EUA 79 and 0.85; no
longer used.)
The sector file `eu_heat_pump_costs_by_sector.csv` has its own sector-averaged gas prices that were NOT rebuilt;
only its `gas_heat_cost_eur_mwh` was recomputed with EUA 73.43. No code reads it.

## Related technical references (optional)

- Danish Energy Agency technology catalogue (gas boiler CAPEX/O&M).
- US DOE steam-system guidance — **0.85** boiler efficiency (superseded by 0.94, Saad et al. 2026).

## Grid electricity reference (plots)

Eurostat `nrg_pc_205` (electricity prices for non-household consumers), EU27_2020, X_VAT, EUR/kWh x 1000,
2025-S1 and 2025-S2, all consumption bands, downloaded 2026-11-11 from the Eurostat dissemination API →
`eurostat_nrg_pc_205_XVAT_2025_EU27.csv`. The band used is set in `eu_heat_pump_cost_assumptions.csv`
("Grid electricity band (nrg_pc_205)"), currently ID (2,000-19,999 MWh/yr): mean EUR 161.8/MWh, which
reproduces the earlier hard-coded EUR 162. Reference heat cost = price / 0.95 IHB round-trip efficiency
= EUR 170.3/MWh_th (`outputs/multiband/analysis/gas_benchmark.py`). Note the gas benchmark uses gas band I4
(27.8-278 GWh/yr), which corresponds to electricity bands IE-IG (EUR 136 / 123 / 111 per MWh), not ID.
