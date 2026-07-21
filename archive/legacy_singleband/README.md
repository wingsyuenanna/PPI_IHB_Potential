# Legacy single-band package

Moved here when the project standardized on multi-band HP + IHB
(`run_multiband_potential.py`).

| File | Former role |
|------|-------------|
| `run_ihb_potential.py` | Single flat-load solar + TES (or Li-ion) fleet runner |
| `run_hp_ihb_lcoh_screen.py` | Annual energy-matching LCOH screen (non-LP) |
| `solvers/optimize_flatblock_highs_heat_battery.py` | Single-band TES LP |
| `solvers/optimize_flatblock_highs_unserved_v2.py` | Li-ion / generic unserved LP |
| `utils/maps/map_sites_lcoh.py` | Map of single-band `summary.csv` |
| `docs/Run_script.md` | Old pulp-only pipeline instructions |
| `docs/flatblock_optimization_README.md` | Pre-multiband flatblock docs (S3/US batch) |
| `docs/scenario_comparison_2025_2030.md` | Notes on 2025 vs 2030 single-band runs |
| `fossil_share/calculate_fossil_share.py` | Excel-based fossil share (replaced by `compute_fossil_share.py`) |
| `notebooks/ihb_steam_scope_results_analysis.ipynb` | Analysis of archived single-band summary |
| `outputs/hp_ihb_lcoh_by_facility.csv` | Screen output from `run_hp_ihb_lcoh_screen.py` |

Hourly result dumps: `../flatblock_singleband_outputs_2025_2030.tar.gz`.
