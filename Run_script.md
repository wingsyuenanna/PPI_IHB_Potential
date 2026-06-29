# Analysis pipeline

Each stage writes its own output. A final merge step will combine everything once solar radiation is ready.

## Output layout


| Stage                      | Script                                               | Output                                                        |
| -------------------------- | ---------------------------------------------------- | ------------------------------------------------------------- |
| 1. Facilities              | `heat_demand/facilities/export_facilities_2024.py`   | `heat_demand/facilities/facilities_2024_eu.csv`               |
| 1b. Heat demand            | Excel workbook (formulas)                            | `heat_demand/pulp_paper_heat_demand_corrected.xlsx`           |
| 2. Fossil share (optional) | `heat_demand/fossil_share/calculate_fossil_share.py` | `heat_demand/fossil_share/fossil_share_lookup.csv`            |
| 3. Land availability       | `land_availability/` scripts                         | `land_availability/outputs/land_availability_by_facility.csv` |
| 4. Solar radiation         | PVGIS (TODO)                                         | `solar_radiation/outputs/solar_radiation_by_facility.csv`     |
| 5. Final merge             | TODO                                                 | `outputs/facilities_analysis.csv`                             |


---

## 1. Export Climate TRACE production → workbook

```bash
python3 heat_demand/facilities/export_facilities_2024.py
```

- Exports EU facilities to `heat_demand/facilities/facilities_2024_eu.csv`
- Writes `annual_output_t` into `heat_demand/pulp_paper_heat_demand_corrected.xlsx`

Heat demand, fossil share, and replaceable heat are calculated by **Excel formulas** in that workbook.

## 2. (Optional) Export fossil-share lookup

```bash
python3 heat_demand/fossil_share/calculate_fossil_share.py
```

## 3. Land availability (Google Earth Engine)

Use `**land_availability/gee_facility_calculate_available_area.py**` for production runs.  
Use `**GEE_facility_calculate_available_area.ipynb**` only to explore maps or test buffers.

**Buffer:** default **5 km** — appropriate for colocated solar (on-site / immediately adjacent land).  
15 km is too far for a colocated network in most cases (extra land may not be owned, permitted, or economical to connect). Run 15 km only as a sensitivity case.

```bash
# 3a. Refresh facility points (after step 1)
python3 land_availability/prepare_gee_upload.py

# Upload Input/facilities_2024_eu_gee_upload.csv in GEE Console as an asset.

# 3b. Start GEE batch export (requires ee auth; project defaults to eu-re-potential)
python3 land_availability/gee_facility_calculate_available_area.py \
  --project eu-re-potential \
  --asset projects/eu-re-potential/assets/facilities_2024_eu_gee_upload \
  --buffer-m 5000

# Download CSV from Google Drive → Input/LandCover_Area_Categorized_5km.csv

# 3c. Process into standalone land output
python3 land_availability/merge_land_availability.py \
  --land-export Input/LandCover_Area_Categorized_5km.csv
```

- Output: `land_availability/outputs/land_availability_by_facility.csv`
- `available_land_km2` = `bare_sparse_km2` + `cropland_km2` (built-up excluded)
- DEM: SRTM where available; Copernicus GLO-30 above 60°N (Finland / northern Sweden)

## 4. Solar radiation (TODO)

Pull PVGIS data per facility lat/lon → `solar_radiation/outputs/solar_radiation_by_facility.csv`

## 5. Final merge (TODO)

Join facilities + heat demand (from workbook export) + land + solar into `outputs/facilities_analysis.csv`