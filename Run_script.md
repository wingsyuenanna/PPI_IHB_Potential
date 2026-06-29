# Heat demand pipeline

## 1. Export Climate TRACE production → workbook

```bash
python3 heat_demand/facilities/export_facilities_2024.py
```

This:
- Exports EU facilities to `heat_demand/facilities/facilities_2024_eu.csv`
- Writes `annual_output_t` into `heat_demand/pulp_paper_heat_demand_corrected.xlsx` (Facilities sheet)

Heat demand, fossil share, and replaceable heat are calculated by **Excel formulas** in that workbook.

## 2. (Optional) Export fossil-share lookup for reference

```bash
python3 heat_demand/fossil_share/calculate_fossil_share.py
```

Exports the `Fossil_Shares` lookup table from the workbook to CSV.  
To refresh fossil shares, update columns D–E in the workbook's `Fossil_Shares` sheet from Eurostat, then re-open the workbook.
