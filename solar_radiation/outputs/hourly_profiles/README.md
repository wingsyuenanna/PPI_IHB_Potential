# Hourly PVGIS profiles (on S3)

2023 hourly PVGIS parquet profiles, one per facility (`<source_id>_2023.parquet`), read by `run_multiband_potential.py`. The parquet files are not in git. They live at

    s3://annaiecc/facility_IHB_potential/solar_hourly_profiles/source_id=<id>/year=2023/<id>_2023.parquet

Download them into this folder from the repo root with `python pull_s3_data.py` (needs AWS credentials, `aws configure`). Aggregated capacity factors stay in git in `solar_radiation/outputs/solar_radiation_by_facility.csv`.

The three `*.pre_1km_fix.parquet` files kept locally are superseded versions and are not on S3.
