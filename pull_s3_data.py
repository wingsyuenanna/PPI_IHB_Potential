"""Download the large inputs kept on S3 (not in git) into their local paths.

    python pull_s3_data.py                 # solar hourly profiles (needed by run_multiband_potential.py)
    python pull_s3_data.py --jrc           # also JRC-IDEES extracts (needed by heat_demand/facilities/merge_production.py)

Bucket layout under s3://annaiecc/facility_IHB_potential/:
    solar_hourly_profiles/source_id=<id>/year=2023/<id>_2023.parquet  -> solar_radiation/outputs/hourly_profiles/<id>_2023.parquet
    jrc_idees_extracted/<year>/...                                    -> References/jrc_idees/extracted/<year>/...
    archive/...                                                       old results, not downloaded here

Needs AWS credentials with read access to the bucket (aws configure). Files already present
with the same size are skipped.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent
BUCKET = "annaiecc"
PREFIX = "facility_IHB_potential"


def pull(s3, prefix: str, dest_for) -> None:
    n_new = n_skip = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            dest = dest_for(obj["Key"])
            if dest.exists() and dest.stat().st_size == obj["Size"]:
                n_skip += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(BUCKET, obj["Key"], str(dest))
            n_new += 1
    print(f"s3://{BUCKET}/{prefix}: {n_new} downloaded, {n_skip} already present")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jrc", action="store_true", help="Also download JRC-IDEES extracts")
    args = ap.parse_args()
    s3 = boto3.client("s3")

    solar_dir = ROOT / "solar_radiation" / "outputs" / "hourly_profiles"
    pull(s3, f"{PREFIX}/solar_hourly_profiles/", lambda k: solar_dir / k.rsplit("/", 1)[1])

    if args.jrc:
        jrc_prefix = f"{PREFIX}/jrc_idees_extracted/"
        jrc_dir = ROOT / "References" / "jrc_idees" / "extracted"
        pull(s3, jrc_prefix, lambda k: jrc_dir / k[len(jrc_prefix):])


if __name__ == "__main__":
    main()
