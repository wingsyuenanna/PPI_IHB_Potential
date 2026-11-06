# BNEF cost compilation (source for ../bnef_country_costs.csv)

Rebuilds `Input/bnef_country_costs.csv` (verified 2026-11-05: all 1,964 rows and 17 columns match).

    python Input/bnef/compile_bnef_costs.py      # writes Input/bnef/output/bnef_solar_pv_costs_v5.csv (= bnef_country_costs.csv)

Copy the v5 output to `Input/bnef_country_costs.csv` to replace the file the model reads. Paths in the script are relative to this folder.

| File in `input/` | What it is |
|---|---|
| `BNEF_raw_data_2024.xlsx` | BNEF cost dataset by country (Capex, Fixed O&M, Variable O&M, LCOE; Low/Mid/High; script uses Mid). No dollar-year note in the file. |
| `IRENA_cost_of_cap.json` | IRENA real WACC by country and technology (Solar PV used for all technologies) |
| `weoapr2025all.csv` | IMF WEO April 2025; CPI inflation (2025–2030 average) turns the real WACC into nominal |
| `wb_income_groups.json` | World Bank income group and region, used for peer-mean imputation |
| `COUNTRY2ISO.json` | BNEF region name to ISO3 |
| `battery_2024_cost.csv` | Battery component table (only feeds the side output `battery_2025_cost.csv`, not used by the model) |

Key settings in the script: CRF lifetime 25 years; years 2025 and 2030; missing countries use the mean of same-region-and-income peers, then income group, then global mean.

**Not in git:** `input/BNEF_raw_data_2024.xlsx` is licensed BNEF data and is git-ignored (it stays on disk locally). Obtain it from BNEF before running the script on a fresh clone.
