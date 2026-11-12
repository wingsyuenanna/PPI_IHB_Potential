> **Update 2026-11-05: real 2025 USD basis.** All costs are now in constant (real) 2025 USD. HP (2021) and IHB (2023) source costs are CPI-inflated to 2025 only (x1.1882 and x1.0566) and are held flat in the 2030 and 2035 columns, with no further inflation. BNEF 2030 PV and Li-ion costs are taken as real 2025 USD (BNEF's dollar year is not stated in the dataset; the storage survey is real 2025 USD). The CRF uses IRENA's real WACC directly (`REAL_BASIS = True` in `Input/bnef/compile_bnef_costs.py`), not the nominal rate. The nominal-2030 tables below are superseded and kept for reference. Previous files: nominal CRF and 2030-inflated HP/IHB costs.

# Cost-year inflation (USD) — HP and IHB

Solar PV and Li-ion already enter as **BNEF project-year dollars** (e.g. 2030
CAPEX when `--project-start 2030`). Industrial heat-pump and IHB CAPEX/FOM are
published in earlier-year dollars and are inflated to the project-start year
before annualization with the country BNEF CRF.

## Method

**Index:** US CPI-U, all items, annual average (BLS / FRED).

| Year | CPI-U | Role |
|------|------:|------|
| 2021 | 270.970 | HP source year (Rissman 2022 / Agora basis) |
| 2023 | 304.703 | IHB source year (Rissman & Gimon, Energy Innovation) |
| 2025 | 321.962 | Latest full annual average used |
| 2030 | 355.472 | = 2025 × (1.02)⁵ |
| 2035 | 392.470 | = 2030 × (1.02)⁵ |

Forward years use **2%/yr** from 2025 (long-run inflation assumption; 2030 CPI
not yet observed). This is general CPI inflation, **not** a technology learning
curve (costs rise with the price level; they are not assumed to get cheaper).

| Bridge | Factor |
|--------|-------:|
| 2021 → 2030 | **1.3119** (+31.2%) |
| 2023 → 2030 | **1.1666** (+16.7%) |

## Source levels → 2030 USD (in `input_heat_battery_cost.csv`)

| Item | Source $ | 2030 $ |
|------|--------:|-------:|
| HP CAPEX &lt;100 °C | 700 /kW_th (2021) | **918.30** |
| HP CAPEX 100–200 °C | 870 /kW_th (2021) | **1141.31** |
| HP FOM &lt;100 °C | 12 /kW_th-yr (2021) | **15.74** |
| HP FOM 100–200 °C | 18 /kW_th-yr (2021) | **23.61** |
| IHB input | 100 /kW (2023) | **116.66** |
| IHB delivery | 300 /kW (2023) | **349.99** |
| IHB storage | 5 /kWh (2023) | **5.83** |

Annualization at project start remains: `CAPEX × CRF_country(year) + FOM`.
