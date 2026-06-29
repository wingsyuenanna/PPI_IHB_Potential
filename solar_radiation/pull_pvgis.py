"""Pull hourly PVGIS solar profiles for EU pulp & paper facilities."""

from __future__ import annotations

import argparse
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from timezonefinder import TimezoneFinder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACILITIES = PROJECT_ROOT / "heat_demand" / "facilities" / "facilities_2024_eu.csv"
DEFAULT_HOURLY_DIR = PROJECT_ROOT / "solar_radiation" / "outputs" / "hourly_profiles"
DEFAULT_SUMMARY = (
    PROJECT_ROOT / "solar_radiation" / "outputs" / "solar_radiation_by_facility.csv"
)
DEFAULT_LOG_DIR = PROJECT_ROOT / "solar_radiation" / "logs"

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/seriescalc"
RAD_DATABASE = "PVGIS-ERA5"


def get_optimal_azimuth(lat: float) -> int:
    return 180 if lat < 0 else 0


def build_timezone_cache(sites_df: pd.DataFrame, lat_col: str, lon_col: str) -> dict[tuple[float, float], str | None]:
    tf = TimezoneFinder()
    sites_df = sites_df.copy()
    sites_df["lat_rounded"] = sites_df[lat_col].round(2)
    sites_df["lon_rounded"] = sites_df[lon_col].round(2)
    cache: dict[tuple[float, float], str | None] = {}
    for _, row in sites_df[["lat_rounded", "lon_rounded"]].drop_duplicates().iterrows():
        cache[(row["lat_rounded"], row["lon_rounded"])] = tf.timezone_at(
            lat=row["lat_rounded"], lng=row["lon_rounded"]
        )
    return cache


def parse_pvgis_csv(response_text: str) -> tuple[pd.DataFrame, list[str]]:
    lines = response_text.splitlines()
    header_line = next((i for i, line in enumerate(lines) if line.startswith("time,")), None)
    if header_line is None:
        raise ValueError("No CSV header found in PVGIS response")
    header_lines = lines[:header_line]
    df = pd.read_csv(StringIO("\n".join(lines[header_line:])))
    return df, header_lines


def process_hourly_profile(
    df: pd.DataFrame,
    *,
    source_id: int,
    source_name: str,
    start_year: int,
    end_year: int,
    local_tz: str | None,
) -> pd.DataFrame:
    if "time" not in df.columns or "P" not in df.columns:
        raise ValueError(f"Missing required PVGIS columns. Available: {df.columns.tolist()}")

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], format="%Y%m%d:%H%M", errors="coerce")
    df = df.dropna(subset=["time"]).set_index("time").tz_localize("UTC")

    if local_tz:
        df = df.tz_convert(local_tz)
        df.index = df.index.tz_localize(None)

    df.index = df.index.floor("h")
    if df.index.duplicated().any():
        df = df[~df.index.duplicated(keep="first")]

    df = df[df.index.year == start_year]
    df["P_kWperkWp"] = pd.to_numeric(df["P"], errors="coerce") / 1000.0

    full_range = pd.date_range(
        start=f"{start_year}-01-01 00:00:00",
        end=f"{end_year}-12-31 23:00:00",
        freq="h",
    )
    df = df.reindex(full_range).fillna(0)
    df.index.name = "timestamp"

    out = df.reset_index().rename(columns={"index": "timestamp"})
    out["source_id"] = source_id
    out["source_name"] = source_name
    out["year"] = out["timestamp"].dt.year
    return out[["source_id", "source_name", "year", "timestamp", "P_kWperkWp"]]


def summarize_profile(
    hourly_df: pd.DataFrame,
    *,
    source_id: int,
    source_name: str,
    iso3_country: str | None,
    lat: float,
    lon: float,
    start_year: int,
    tilt_deg: float,
    azimuth_deg: int,
) -> dict:
    annual_yield = float(hourly_df["P_kWperkWp"].sum())
    hours = len(hourly_df)
    return {
        "source_id": source_id,
        "source_name": source_name,
        "iso3_country": iso3_country,
        "lat": lat,
        "lon": lon,
        "year": start_year,
        "annual_yield_kwh_per_kwp": annual_yield,
        "capacity_factor": annual_yield / hours if hours else 0.0,
        "pvgis_raddatabase": RAD_DATABASE,
        "tilt_deg": tilt_deg,
        "azimuth_deg": azimuth_deg,
        "system_loss_pct": 0.0,
    }


def fetch_site(
    row: pd.Series,
    *,
    start_year: int,
    end_year: int,
    lat_col: str,
    lon_col: str,
    hourly_dir: Path,
    overwrite: bool,
    timezone_cache: dict[tuple[float, float], str | None],
    write_lock: threading.Lock,
    iso3_country: str | None = None,
) -> dict:
    source_id = int(row["source_id"])
    source_name = row["source_name"]
    lat = float(row[lat_col])
    lon = float(row[lon_col])
    lat_rounded = round(lat, 2)
    lon_rounded = round(lon, 2)
    tilt_deg = abs(lat)
    azimuth_deg = get_optimal_azimuth(lat)

    output_file = hourly_dir / f"{source_id}_{start_year}.parquet"
    if output_file.exists() and not overwrite:
        hourly_df = pd.read_parquet(output_file)
        summary = summarize_profile(
            hourly_df,
            source_id=source_id,
            source_name=source_name,
            iso3_country=iso3_country,
            lat=lat,
            lon=lon,
            start_year=start_year,
            tilt_deg=tilt_deg,
            azimuth_deg=azimuth_deg,
        )
        return {"success": True, "source_id": source_id, "source_name": source_name, "summary": summary, "cached": True}

    params = {
        lat_col: lat,
        lon_col: lon,
        "raddatabase": RAD_DATABASE,
        "pvcalculation": 1,
        "peakpower": 1,
        "loss": 0,
        "angle": tilt_deg,
        "aspect": azimuth_deg,
        "startyear": start_year,
        "endyear": end_year,
        "outputformat": "csv",
    }

    try:
        response = requests.get(PVGIS_URL, params=params, timeout=60)
        response.raise_for_status()
        raw_df, _ = parse_pvgis_csv(response.text)
        hourly_df = process_hourly_profile(
            raw_df,
            source_id=source_id,
            source_name=source_name,
            start_year=start_year,
            end_year=end_year,
            local_tz=timezone_cache.get((lat_rounded, lon_rounded)),
        )
        summary = summarize_profile(
            hourly_df,
            source_id=source_id,
            source_name=source_name,
            iso3_country=iso3_country,
            lat=lat,
            lon=lon,
            start_year=start_year,
            tilt_deg=tilt_deg,
            azimuth_deg=azimuth_deg,
        )

        with write_lock:
            hourly_dir.mkdir(parents=True, exist_ok=True)
            hourly_df.to_parquet(output_file, engine="pyarrow", compression="zstd", index=False)

        return {"success": True, "source_id": source_id, "source_name": source_name, "summary": summary, "cached": False}
    except Exception as exc:
        return {
            "success": False,
            "source_id": source_id,
            "source_name": source_name,
            "error": str(exc),
        }


def load_sites(path: Path, lat_col: str, lon_col: str, overwrite: bool, hourly_dir: Path, start_year: int) -> pd.DataFrame:
    sites = pd.read_csv(path)
    keep_cols = ["source_id", "source_name", lat_col, lon_col]
    if "iso3_country" in sites.columns:
        keep_cols.append("iso3_country")
    sites = sites[keep_cols].drop_duplicates(subset="source_id")
    sites = sites.dropna(subset=[lat_col, lon_col])

    if not overwrite:
        existing_ids = {
            int(path.stem.split("_", 1)[0])
            for path in hourly_dir.glob(f"*_{start_year}.parquet")
        }
        sites = sites[~sites["source_id"].isin(existing_ids)]
    return sites


def pull_pvgis_profiles(
    *,
    facilities_path: Path,
    hourly_dir: Path,
    summary_path: Path,
    start_year: int = 2023,
    end_year: int = 2023,
    lat_col: str = "lat",
    lon_col: str = "lon",
    max_workers: int = 8,
    overwrite: bool = False,
) -> pd.DataFrame:
    log_dir = DEFAULT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"pvgis_pull_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        force=True,
    )
    logger = logging.getLogger(__name__)
    logger.info("Loading facilities from %s", facilities_path)

    if overwrite and hourly_dir.exists():
        for path in hourly_dir.glob(f"*_{start_year}.parquet"):
            path.unlink()
        if summary_path.exists():
            summary_path.unlink()

    sites_df = load_sites(facilities_path, lat_col, lon_col, overwrite, hourly_dir, start_year)
    logger.info("Sites to process: %s", len(sites_df))
    timezone_cache = build_timezone_cache(sites_df, lat_col, lon_col)

    write_lock = threading.Lock()
    summaries: list[dict] = []
    errors: list[dict] = []
    start_time = datetime.now()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                fetch_site,
                row,
                start_year=start_year,
                end_year=end_year,
                lat_col=lat_col,
                lon_col=lon_col,
                hourly_dir=hourly_dir,
                overwrite=overwrite,
                timezone_cache=timezone_cache,
                write_lock=write_lock,
                iso3_country=row.get("iso3_country"),
            ): row["source_id"]
            for _, row in sites_df.iterrows()
        }

        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if result["success"]:
                summaries.append(result["summary"])
                status = "cached" if result.get("cached") else "fetched"
                logger.info("[%s/%s] OK %s (%s)", completed, total, result["source_id"], status)
            else:
                errors.append(result)
                logger.error("[%s/%s] FAIL %s: %s", completed, total, result["source_id"], result["error"])

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if summary_path.exists() and not overwrite:
        existing = pd.read_csv(summary_path)
        new_summary = pd.DataFrame(summaries)
        combined = pd.concat([existing, new_summary], ignore_index=True)
        combined = combined.drop_duplicates(subset=["source_id", "year"], keep="last")
    else:
        combined = pd.DataFrame(summaries)

    if not combined.empty:
        combined = combined.sort_values(["iso3_country", "source_name"], na_position="last")
        combined.to_csv(summary_path, index=False)

    duration = datetime.now() - start_time
    logger.info("Done in %s. Summary rows: %s. Errors: %s", duration, len(combined), len(errors))
    logger.info("Hourly profiles: %s", hourly_dir)
    logger.info("Summary CSV: %s", summary_path)
    logger.info("Log file: %s", log_file)

    if errors:
        error_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        pd.DataFrame(errors).to_csv(error_file, index=False)
        logger.warning("Wrote error log to %s", error_file)

    return combined


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull PVGIS hourly solar profiles for facility coordinates."
    )
    parser.add_argument("--facilities", type=Path, default=DEFAULT_FACILITIES)
    parser.add_argument("--hourly-dir", type=Path, default=DEFAULT_HOURLY_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.facilities.exists():
        raise FileNotFoundError(f"Facilities file not found: {args.facilities}")
    if args.end_year != args.start_year:
        raise ValueError("Only single-year pulls are supported for now.")

    result = pull_pvgis_profiles(
        facilities_path=args.facilities,
        hourly_dir=args.hourly_dir,
        summary_path=args.output,
        start_year=args.start_year,
        end_year=args.end_year,
        max_workers=args.max_workers,
        overwrite=args.overwrite,
    )

    print(f"Wrote {len(result)} summary rows to {args.output}")
    preview_cols = [
        c
        for c in [
            "source_name",
            "iso3_country",
            "annual_yield_kwh_per_kwp",
            "capacity_factor",
        ]
        if c in result.columns
    ]
    if not result.empty:
        print(result[preview_cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
