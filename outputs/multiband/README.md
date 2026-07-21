# Multi-band HP + IHB optimization outputs

## Solar + storage cases (current default)

No converter CAPEX (HP / heat battery converts electricity → heat). No VoLL on unserved.
Hard 90% availability floor; land-limited sites maximize served heat then cost-minimize.

| Folder | Land buffer | Heat case |
|--------|-------------|-----------|
| `land_5km_ss/` | 5 km | base |
| `land_15km_ss/` | 15 km | base |
| `land_5km_ss_heat_low/` / `_heat_high/` | 5 km | low / high |
| `land_15km_ss_heat_low/` / `_heat_high/` | 15 km | low / high |

Heat bounds (sector multipliers) live on `outputs/eu_ihb_site_assessment_2024.csv`:
`replaceable_heat_mwh_th_low` / `_high`. Fleet totals: **388 / 522 / 697 TWh/y** (low / base / high).

Summary table: [`heat_case_summary.txt`](heat_case_summary.txt).
Plots: [`analysis/heat_case_sensitivity.png`](analysis/heat_case_sensitivity.png), [`analysis/heat_case_mechanism.png`](analysis/heat_case_mechanism.png).

```bash
python heat_demand/facilities/heat_sensitivity_bounds.py
python run_multiband_potential.py --scenario land_5km_ss --heat-case low
python run_multiband_potential.py --scenario land_5km_ss --heat-case high
python run_multiband_potential.py --scenario land_15km_ss --heat-case low \
  --land-csv land_availability/outputs/land_availability_by_facility_15km.csv
python run_multiband_potential.py --scenario land_15km_ss --heat-case high \
  --land-csv land_availability/outputs/land_availability_by_facility_15km.csv
```

## Earlier runs (with converter CAPEX + VoLL)

| Folder | Notes |
|--------|-------|
| `land_5km/` | Prior base with converter costs |
| `land_15km/` | Prior 15 km with converter costs |
