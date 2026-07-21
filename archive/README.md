# Archive

Parked material superseded by the multi-band solar + storage workflow
(`run_multiband_potential.py` → `outputs/multiband/land_*_ss*`).

## Contents

| Path | What |
|------|------|
| `flatblock_singleband_outputs_2025_2030.tar.gz` | Full `flatblock_optimization/output{,_2030}/` hourly dumps + logs (~23 MB compressed; ~100 MB uncompressed) from `run_ihb_potential.py` |
| `legacy_singleband/` | Single-band runners, solvers, docs, HP/IHB annual screen, related notebook/output |
| `merge_eu_pulp_paper_ihb_sites.py` | Pre–multi-sector site merge (pulp & paper only) |
| `pulp_paper_heat_demand_corrected.xlsx` | Excel heat workbook (replaced by `heat_demand/facilities/`) |
| `nrg_d_indq_n__custom_21951118_spreadsheet.xlsx` | Older Eurostat extract |
| `benchmark.md` | Old notes |

## Restore single-band outputs

```bash
tar -xzf archive/flatblock_singleband_outputs_2025_2030.tar.gz
```

## Re-run legacy single-band optimizer

Scripts under `legacy_singleband/` expect repo-root paths and the archived solvers.
Prefer restoring solvers next to `flatblock_optimization/solvers/` or adjusting imports before running.
