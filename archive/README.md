# Archive

Parked material superseded by the multi-band solar + storage workflow
(`run_multiband_potential.py` → `outputs/multiband/land_*_ss*`), plus bulky
inputs moved out of the active workspace to reduce Cursor indexing lag.

## 2026-08-06 cleanup (`2026-08-06_cleanup/`)

| Archive | Contents | Unpack when |
|---------|----------|-------------|
| `analysis_clutter.tar.gz` | ~4.4k per-site LCOH CSVs, dispatch examples, `ht_fail_*` plots, superseded single-buffer country scatters | Inspecting old site-level curves |
| `solar_hourly_profiles.tar.gz` | PVGIS hourly parquets | Re-running site optimization (`run_multiband_potential.py`) |
| `jrc_idees.tar.gz` | JRC-IDEES raw + extracted UED | Rebuilding heat-demand inputs |
| `hotmaps_load_profiles.tar.gz` | Hotmaps yearlong load profiles | Regenerating representative-day heat shapes |
| `older_multiband_scenarios.tar.gz` | All `land_*` except `land_{5,15}km_ss_2030_liion` | Comparing against thermal-store / 2025 / heat cases |

```bash
# Example restore (from repo root)
tar -xzf archive/2026-08-06_cleanup/solar_hourly_profiles.tar.gz -C .
```

Kept active after cleanup:
- `outputs/multiband/land_5km_ss_2030_liion/` and `land_15km_ss_2030_liion/`
- `solar_radiation/outputs/solar_radiation_by_facility.csv` (aggregated CF)
- Analysis scripts + recent figures under `outputs/multiband/analysis/`

See `2026-08-06_cleanup/MANIFEST.txt` for the full move log.

**Git note:** `jrc_idees.tar.gz` (~779 MB) and `solar_hourly_profiles.tar.gz` (~215 MB) are kept local-only (listed in `.gitignore`) because they exceed GitHub’s 100 MB limit. Smaller tarballs and the path deletions are committed.

## Earlier archive contents

| Path | What |
|------|------|
| `flatblock_singleband_outputs_2025_2030.tar.gz` | Full `flatblock_optimization/output{,_2030}/` hourly dumps + logs |
| `legacy_singleband/` | Single-band runners, solvers, docs |
| `merge_eu_pulp_paper_ihb_sites.py` | Pre–multi-sector site merge |
| `pulp_paper_heat_demand_corrected.xlsx` | Excel heat workbook (replaced by `heat_demand/facilities/`) |
| `nrg_d_indq_n__custom_21951118_spreadsheet.xlsx` | Older Eurostat extract |
| `benchmark.md` | Old notes |
