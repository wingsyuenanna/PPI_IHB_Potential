# Multi-band HP + IHB optimization outputs

## Configuration (current code)

- **&lt;200 °C:** heat pump + shared **Li-ion** (BNEF utility-scale 4h battery; implied $/kWh = CAPEX/4)
- **≥200 °C:** **IHB** with Energy Innovation CAPEX — $100/kW-in, $300/kW-out, $5/kWh, RTE 95% (annualized at **country BNEF CRF**, same as solar/Li-ion)
- **HP / IHB dollars:** source-year CAPEX/FOM are **CPI-inflated to project-start USD** (HP 2021→2030 ×1.31; IHB 2023→2030 ×1.17) — see [`flatblock_optimization/inputs/COST_YEAR_INFLATION.md`](../../flatblock_optimization/inputs/COST_YEAR_INFLATION.md). Solar/Li-ion are already BNEF 2030 $.
- **HP equipment** (2030 USD): **~$918 / $1141 per kW_th** (&lt;100 / 100–200 °C) + FOM **~$16 / $24 per kW_th-yr**. Annualized with country BNEF CRF.
- Shared on-site solar; hard 90% availability; land cap 50 MWdc/km²

## Li-ion HP + Energy Innovation IHB (2030)

New formulation folders (compare to thermal-store predecessors):

| Folder | Land | Notes |
|--------|------|-------|
| `land_5km_ss_2030_liion/` | 5 km | HP←Li-ion (BNEF); IHB←EI CAPEX; country BNEF CRF |
| `land_15km_ss_2030_liion/` | 15 km | same |

Comparison + daily dispatch plots: [`analysis/compare_liion_vs_thermal_2030.txt`](analysis/compare_liion_vs_thermal_2030.txt), [`analysis/dispatch_daily_food_*.png`](analysis/), [`analysis/dispatch_daily_cement_*.png`](analysis/).

```bash
python run_multiband_potential.py --scenario land_5km_ss_2030_liion --project-start 2030
python outputs/multiband/analysis/compare_liion_vs_thermal.py
```

## Primary Results (2030 costs) — prior thermal-store formulation

No VoLL on unserved. Hard 90% availability floor; land-limited sites maximize served heat then cost-minimize. **Primary cost year: 2030** (BNEF 2030 PV + Li-ion; IHB Energy Innovation costs). Heat inventory remains the 2024 Climate TRACE–based estimate.

| Folder | Land buffer | Heat case | Cost year |
|--------|-------------|-----------|-----------|
| `land_5km_ss_2030/` | 5 km | base | 2030 |
| `land_15km_ss_2030/` | 15 km | base | 2030 |
| `land_5km_ss_2030_heat_low/` / `_heat_high/` | 5 km | low / high | 2030 |
| `land_15km_ss_2030_heat_low/` / `_heat_high/` | 15 km | low / high | 2030 |

2025 cost counterparts (sensitivity): `land_5km_ss/`, `land_15km_ss/`, and matching `_heat_*` folders.

Heat bounds (sector multipliers) live on `outputs/eu_ihb_site_assessment_2024.csv`:
`replaceable_heat_mwh_th_low` / `_high`. Fleet totals: **388 / 522 / 697 TWh/y** (low / base / high).

Comparison: [`analysis/compare_2025_vs_2030.txt`](analysis/compare_2025_vs_2030.txt).
Map: [`map_lcoh_5km_15km_ss.html`](map_lcoh_5km_15km_ss.html) — 2030 Li-ion HP + IHB; shows **max serve → then min LCOH** (black outline = met 90% floor; red = land-capped max-serve). Defaults to `land_*_ss_2030_liion/`.

```bash
python run_multiband_potential.py --scenario land_5km_ss_2030_liion --project-start 2030
python run_multiband_potential.py --scenario land_15km_ss_2030_liion --project-start 2030 \
  --land-csv land_availability/outputs/land_availability_by_facility_15km.csv
python outputs/multiband/map_multiband_lcoh.py
# optional heat cases / gas benchmark on thermal-store folders still work via --five/--fifteen
```

## Earlier runs (with converter CAPEX + VoLL)

| Folder | Notes |
|--------|-------|
| `land_5km/` | Prior base with converter costs |
| `land_15km/` | Prior 15 km with converter costs |
