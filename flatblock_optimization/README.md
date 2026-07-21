# Flatblock optimization (active)

Current fleet path: repo-root `run_multiband_potential.py`, which calls

`solvers/optimize_flatblock_multiband_heatpump.py`

with country costs from `Input/bnef_country_costs.csv` and thermal storage
assumptions from `inputs/input_heat_battery_cost.csv`.

Site table is built by `inputs/build_sites_input.py` →
`outputs/eu_ihb_site_assessment_2024.csv`.

Legacy single-band runners, Li-ion/TES solvers, and old batch docs live in
`../archive/legacy_singleband/`. Archived 2025/2030 hourly outputs are in
`../archive/flatblock_singleband_outputs_2025_2030.tar.gz`.
