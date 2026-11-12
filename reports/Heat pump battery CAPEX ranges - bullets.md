# Heat pump and heat battery costs: Rissman vs DEA vs model

| Asset | Metric | Rissman 2022 | DEA 2026 | Model (current) |
|---|---|---|---|---|
| **HP <100 °C** | CAPEX | $700/kW_th, 2021 USD, equipment only, 80–100 °C unit. *Rissman Table 3, PDF p. 17* | €950/kW_th, 2025 €, installed, hot water to 60 °C, 40 K lift. *DEA datasheet, sheet 1.1* | **$918.30/kW_th** (2030 USD) = $700 × 1.3119 CPI. *COST_YEAR_INFLATION.md* |
| | O&M | $2/MWh_th non-energy opex (staffing, maintenance). *Rissman Table 3, p. 17* | Fixed €2,127/MW-yr + variable €3.07/MWh_th. *DEA datasheet, sheet 1.1* | **FOM $15.74/kW_th-yr** = $12 × 1.3119. No VOM. |
| | COP | 3.7. *Rissman Table 3, p. 17* | 5.28 annual average at 40 K lift; 3.95 at 60 K. *DEA datasheet, sheet 1.1* | **3.7** (Rissman; changed from 2.7 on 2026-10-26). |
| **HP 100–200 °C** | CAPEX | $870/kW_th, 2021 USD, equipment only, 100–180 °C unit. *Rissman Table 3, p. 17* | €1,550/kW_th hot water to 150 °C. *DEA Table 2, p. 48.* €1,750/kW_th if steam. *DEA Table 4, p. 53* | **$1,141.31/kW_th** (2030 USD) = $870 × 1.3119. *COST_YEAR_INFLATION.md* |
| | O&M | $3/MWh_th non-energy opex. *Rissman Table 3, p. 17* | Fixed €2,494/MW-yr + variable €3.60/MWh_th. *DEA datasheet, sheet 2.b* (labeled "from last update in 2019") | **FOM $23.61/kW_th-yr** = $18 × 1.3119. No VOM. |
| | COP | 2.2. *Rissman Table 3, p. 17* | 2.70 annual average at 65 K lift; 2.40 at 80 K; 2.05 at 100 K; steam −0.15 points. *DEA datasheet, sheet 2.b* | **2.2** (Rissman; changed from 1.8 on 2026-10-26). |
| **Heat battery (IHB), ≥200 °C** | CAPEX | $100/kW input, $300/kW delivery, $5/kWh storage, 2023 USD. *Energy Innovation 2023 (Rissman and Gimon), PDF p. 17* | **None.** DEA has no thermal storage or heat battery prices (only direct-electric element 0.060 M€/MW, sheet 7.3). | **$116.66/kW input, $349.99/kW delivery, $5.83/kWh** (2030 USD) = 2023 values × 1.1666 CPI. *COST_YEAR_INFLATION.md* |
| | O&M | None in the cost buildup | None | **0** |
| | Efficiency | 95% round trip. *Energy Innovation 2023, PDF p. 25* | None | **95%** |

## Cost by band (DEA without installation)

| Band | Rissman (2022; IHB 2023) | DEA (2026), equipment only | Model now (2030 USD) |
|---|---|---|---|
| **<100 °C** CAPEX | $700/kW_th (2021 USD, 80–100 °C unit, equipment only) | €380/kW_th (2025 €) = 40% × €950 installed (hot water to 60 °C, 40 K lift) | $918.30/kW_th |
| <100 °C O&M | $2/MWh_th | €2.13/kW_th-yr fixed + €3.07/MWh_th variable | $15.74/kW_th-yr FOM, no VOM |
| **100–200 °C** CAPEX | $870/kW_th (2021 USD, 100–180 °C unit, equipment only) | €620/kW_th = 40% × €1,550 installed (hot water to 150 °C); €700/kW_th for steam = 40% × €1,750 | $1,141.31/kW_th |
| 100–200 °C O&M | $3/MWh_th | €2.49/kW_th-yr fixed + €3.60/MWh_th variable | $23.61/kW_th-yr FOM, no VOM |
| **>200 °C** IHB | $100/kW input + $300/kW delivery + $5/kWh storage (2023 USD) | Not provided | $116.66/kW in, $349.99/kW out, $5.83/kWh |

**How DEA equipment-only was calculated:** DEA's datasheet splits investment into 40% equipment and 60% installation, so equipment = 0.4 × the nominal (installed) figure. O&M is not split, so it is shown as published. Costs are in 2025 euros, not converted to USD or CPI-adjusted. At an assumed 1.1 USD/EUR the equipment-only values are about $418 and $682/kW_th (steam $770), against Rissman's $700 and $870 in 2021 USD (about $832 and $1,034 in 2025 USD).

## Checks on the model figures

- **HP CAPEX and FOM** come from Rissman. The FOM is Rissman's $2 and $3/MWh_th × 6,000 h/yr = $12 and $18/kW-yr. This is my inference from matching numbers; the repo does not document it.
- **HP CAPEX basis differs.** Rissman is equipment only. DEA includes installation (40% equipment, 60% installation per the datasheet). In 2025 USD (Rissman × 1.188 CPI; DEA at an assumed 1.1 USD/EUR), Rissman is $832 and $1,034/kW, between DEA equipment ($418 and $682) and DEA installed ($1,045 and $1,705).
- **COP** 2.7 and 1.8 match neither source. 2.7 equals DEA's annual average for HTHPs to 150 °C (65 K lift, sheet 2.b); 1.8 has no match.
- **Heat battery storage** $5.83/kWh is consistent with McMillan et al. 2025 (firebrick, $4.55/kWh_th, PDF p. 3). Higher published figures exist (IEA Annex 30: 15–40 €/kWh, PDF p. 14).
- **No VOM** in the model. DEA's variable O&M (€3.07–3.60/MWh_th) is not included; it includes some auxiliary electricity, which the off-grid solar would already cover.

## Notes

- Page numbers are PDF-viewer pages. For Rissman and Energy Innovation the printed number is one lower; DEA's is the same.
- Currencies and years are not converted except the CPI step the model already applies (2021→2030 ×1.3119 for HP, 2023→2030 ×1.1666 for IHB, from `input_heat_battery_cost.csv`).
- Full citations: Rissman, *Decarbonizing Low-Temperature Industrial Heat in the U.S.*, Energy Innovation, Oct 2022. DEA and Energinet, *Technology Data for Industrial Process Heat*, Jan 2026 revision (catalogue PDF https://ens.dk/media/7757/download, datasheet https://ens.dk/media/7758/download). Rissman and Gimon, *Industrial Thermal Batteries*, Energy Innovation, July 2023.
