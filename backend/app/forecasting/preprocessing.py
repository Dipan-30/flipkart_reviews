"""
CSV validation, date parsing and chronological sorting for sales data.
"""
import io
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"date", "product_name", "units_sold"}
OPTIONAL_COLUMNS = {"revenue", "price"}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
]


def validate_and_parse_csv(content: bytes, filename: str = "upload.csv") -> pd.DataFrame:
    """
    Parse a sales CSV, validate required columns, parse dates, sort chronologically.

    Returns a clean DataFrame with columns:
        date (datetime64), product_name (str), units_sold (float),
        revenue (float, optional), price (float, optional)

    Raises ValueError with a descriptive message on validation failure.
    """
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(f"Cannot parse CSV: {exc}") from exc

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}. "
            f"Required: {sorted(REQUIRED_COLUMNS)}"
        )

    # Parse date column
    df["date"] = _parse_dates(df["date"])

    # Coerce numeric columns
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce")
    if df["units_sold"].isna().all():
        raise ValueError("Column 'units_sold' contains no valid numeric data.")

    for col in OPTIONAL_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows without a parseable date
    before = len(df)
    df = df.dropna(subset=["date", "units_sold"])
    dropped = before - len(df)
    if dropped:
        logger.warning(f"Dropped {dropped} rows with invalid date/units_sold from {filename}")

    if df.empty:
        raise ValueError("No valid rows remain after cleaning.")

    df = df.sort_values("date").reset_index(drop=True)
    df["product_name"] = df["product_name"].astype(str).str.strip()
    return df


def _parse_dates(series: pd.Series) -> pd.Series:
    """Try multiple date formats; return NaT for unparseable entries."""
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().sum() > 0:
        return parsed
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        if parsed.notna().sum() > 0:
            return parsed
    return parsed


def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by (date, product_name) and sum units_sold + revenue (if present).
    Returns a DataFrame indexed by date with product_name as a column.
    """
    agg: dict = {"units_sold": "sum"}
    if "revenue" in df.columns:
        agg["revenue"] = "sum"
    grouped = df.groupby(["date", "product_name"], as_index=False).agg(agg)
    return grouped.sort_values(["product_name", "date"]).reset_index(drop=True)


def train_test_split_chronological(
    series: pd.Series, test_fraction: float = 0.2
) -> tuple[pd.Series, pd.Series]:
    """Split a time series chronologically (no shuffling)."""
    n = len(series)
    split = max(1, int(n * (1 - test_fraction)))
    return series.iloc[:split], series.iloc[split:]
