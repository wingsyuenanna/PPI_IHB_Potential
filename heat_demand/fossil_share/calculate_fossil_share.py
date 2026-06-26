"""Calculate country-level fossil share from Eurostat simplified energy balances."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

FOSSIL_FUEL_COLUMNS = [
    "Solid fossil fuels",
    "Oil shale and oil sands",
    "Natural gas",
    "Oil and petroleum products (excluding biofuel portion)",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    PROJECT_ROOT / "Input" / "nrg_bal_s__custom_21950796_spreadsheet.xlsx"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "heat_demand" / "fossil_share" / "fossil_share_by_country.csv"


def find_tj_sheet(path: Path) -> str:
    """Return the sheet name whose unit of measure is Terajoule (TJ)."""
    workbook = pd.ExcelFile(path)
    for sheet_name in workbook.sheet_names:
        preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=12)
        if preview.astype(str).apply(lambda s: s.str.contains("Terajoule", case=False, na=False)).any().any():
            return sheet_name
    raise ValueError(f"No Terajoule (TJ) sheet found in {path}")


def _to_numeric(value) -> float | None:
    if pd.isna(value) or value == ":":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_tj_data(path: Path, sheet_name: str | None = None) -> pd.DataFrame:
    """Load the Eurostat TJ export and return country-level energy balances."""
    sheet_name = sheet_name or find_tj_sheet(path)
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)

    header_row_idx = raw.index[raw.iloc[:, 0] == "SIEC (Labels)"][0]
    headers = {
        str(label).strip(): col_idx
        for col_idx, label in enumerate(raw.iloc[header_row_idx])
        if pd.notna(label) and str(label).strip()
    }

    if "Total" not in headers:
        raise ValueError("Expected a 'Total' column in the Eurostat TJ sheet.")

    missing = [col for col in FOSSIL_FUEL_COLUMNS if col not in headers]
    if missing:
        raise ValueError(f"Missing expected fossil fuel columns: {missing}")

    records: list[dict] = []
    for _, row in raw.iloc[header_row_idx + 2 :].iterrows():
        country = row.iloc[0]
        if pd.isna(country):
            continue

        country = str(country).strip()
        if not country or country.startswith("Special value"):
            break

        total = _to_numeric(row.iloc[headers["Total"]])
        if total is None or total <= 0:
            continue

        record: dict = {"country": country, "total_tj": total}
        fossil_total = 0.0
        for fuel in FOSSIL_FUEL_COLUMNS:
            value = _to_numeric(row.iloc[headers[fuel]]) or 0.0
            column_name = fuel.lower().replace(" ", "_").replace("(", "").replace(")", "")
            column_name = column_name.replace("__", "_").replace(",", "")
            record[f"{column_name}_tj"] = value
            fossil_total += value

        record["fossil_total_tj"] = fossil_total
        record["fossil_share"] = fossil_total / total
        records.append(record)

    return pd.DataFrame(records)


def calculate_fossil_share(path: Path, sheet_name: str | None = None) -> pd.DataFrame:
    """Calculate fossil share (fossil fuels / total) for each country."""
    result = load_tj_data(path, sheet_name=sheet_name)
    return result.sort_values("country").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate country-level fossil share for pulp and paper industry "
            "energy use from Eurostat simplified energy balances (TJ sheet)."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to the Eurostat Excel export.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the fossil share CSV.",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Optional sheet name override (default: auto-detect Terajoule sheet).",
    )
    args = parser.parse_args()

    result = calculate_fossil_share(args.input, sheet_name=args.sheet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    print(f"Wrote {len(result)} countries to {args.output}")
    print(result[["country", "total_tj", "fossil_total_tj", "fossil_share"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
