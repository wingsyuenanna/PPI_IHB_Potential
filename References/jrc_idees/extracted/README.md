# JRC-IDEES extracts (on S3)

Per-country useful-energy-demand CSVs for 2021 and 2023, read by `heat_demand/facilities/merge_production.py` and `heat_demand/analysis_outputs/build_validation_tables.py`. The CSVs are not in git. They live at `s3://annaiecc/facility_IHB_potential/jrc_idees_extracted/<year>/`.

Download them from the repo root with `python pull_s3_data.py --jrc`.
