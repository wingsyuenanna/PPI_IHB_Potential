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
- Plus **EUA carbon** at **79 EUR/tCO₂**

Resulting site benchmark: about **€61–122/MWh_th** (~**$66–132/MWh** at EURUSD 1.08);
fleet heat-weighted mean ≈ **$84/MWh** — close to Reform Institute **≈ €86/MWh_th (2030, Table 18)**.

Pipeline: `outputs/multiband/add_gas_benchmark.py`.

**Gas price series:** compiled screening series in the CSV. For a primary statistical citation,
use Eurostat **nrg_pc_203** (gas prices for non-household consumers) for the matching year.

## Related technical references (optional)

- Danish Energy Agency technology catalogue (gas boiler CAPEX/O&M).
- US DOE steam-system guidance — **0.85** boiler efficiency assumption.
