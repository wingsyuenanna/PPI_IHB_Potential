# Land availability

Eligible land for ground-mounted solar within 5 km and 15 km of each facility, computed in Google Earth Engine (project `eu-re-potential`). Eligible land is bare/sparse, cropland, grassland and shrubland (ESA WorldCover 2021) with slope at most 5° and outside WDPA protected areas (pinned release `WCMC/WDPA/202607`, 100 m buffer). German Landscape Protection Areas count as eligible (manuscript Supplementary Note 9).

## Scripts

| Script | Does |
|---|---|
| `prepare_gee_upload.py` | Writes facility points for upload as a GEE table asset. `--with-heat` keeps the 2,192 facilities with replaceable heat and adds the `heat_mwh` weight. |
| `gee_facility_calculate_available_area.py` | Starts the GEE export of land-cover area per facility. `--allocate-by heat_mwh` shares overlapping buffers in proportion to heat. `--to-asset` exports to an EE asset instead of Drive. |
| `merge_land_availability.py` | Turns a GEE export into a land-availability CSV with `available_land_km2`. |
| `check_land_allocation.py` | Checks allocated against independent land: allocated never larger, isolated facilities equal. |

## Outputs (`outputs/`)

| File | Used by |
|---|---|
| `land_availability_allocated_5km.csv` | Main case. Default of `run_multiband_potential.py` and `build_sites_input.py`. |
| `land_availability_allocated_15km.csv` | `run_multiband_potential.py --land-km 15` |
| `land_availability_by_facility_{5,15}km.csv` | Independent buffers (single-facility comparison), all 2,415 facilities |

Raw GEE exports are in `Input/`: `LandCover_Area_Allocated_{5,15}km.csv` (assets `facilities_2024_eu_gee_upload_heat`) and `LandCover_Area_Categorized_{5,15}km_all_sectors.csv` (asset `facilities_2024_eu_gee_upload_v1`). All four were exported on 2026-11-14 with the settings above.

## Rebuild

```bash
P=projects/eu-re-potential/assets
python land_availability/gee_facility_calculate_available_area.py --asset $P/facilities_2024_eu_gee_upload_heat --allocate-by heat_mwh --buffer-m 5000
python land_availability/gee_facility_calculate_available_area.py --asset $P/facilities_2024_eu_gee_upload_v1 --buffer-m 5000
# same with --buffer-m 15000, download the CSVs into Input/, then for each:
python land_availability/merge_land_availability.py --land-export Input/LandCover_Area_Allocated_5km.csv --output land_availability/outputs/land_availability_allocated_5km.csv
python land_availability/merge_land_availability.py --land-export Input/LandCover_Area_Categorized_5km_all_sectors.csv --output land_availability/outputs/land_availability_by_facility_5km.csv
python land_availability/check_land_allocation.py --radius-km 5 --allocated land_availability/outputs/land_availability_allocated_5km.csv --independent land_availability/outputs/land_availability_by_facility_5km.csv
```

Redo the allocated exports whenever replaceable heat changes, because the weights come from `heat_demand/facilities/facilities_2024_eu_replaceable.csv`.
