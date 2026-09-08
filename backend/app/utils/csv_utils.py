"""
CSV validation and processing utilities.
"""
import io
import logging
import re
import chardet
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

# Accepted column name variants for the required Review field
REVIEW_COLUMN_VARIANTS = ["review", "Review", "review_text", "Review_Text", "reviews", "Reviews", "text", "Text"]

# Optional columns and their normalized names
OPTIONAL_COLUMN_MAP = {
    "product_name": ["product_name", "Product_Name", "product", "Product", "name", "Name", "item", "Item"],
    "product_price": ["product_price", "Product_Price", "price", "Price", "cost", "Cost", "mrp", "MRP"],
    "summary": ["summary", "Summary", "title", "Title", "review_title", "Review_Title"],
    "date": ["date", "Date", "review_date", "Review_Date", "created_at", "timestamp"],
    "ground_truth_sentiment": ["sentiment", "Sentiment", "ground_truth", "label", "Label"],
}


def detect_encoding(file_bytes: bytes) -> str:
    """Detect file encoding using chardet."""
    result = chardet.detect(file_bytes)
    return result.get("encoding") or "utf-8"


def find_review_column(df: pd.DataFrame) -> Optional[str]:
    """Find the review column in a dataframe."""
    for variant in REVIEW_COLUMN_VARIANTS:
        if variant in df.columns:
            return variant
    # Case-insensitive fallback
    lower_cols = {c.lower(): c for c in df.columns}
    for variant in REVIEW_COLUMN_VARIANTS:
        if variant.lower() in lower_cols:
            return lower_cols[variant.lower()]
    return None


def find_optional_column(df: pd.DataFrame, field: str) -> Optional[str]:
    """Find an optional column in a dataframe."""
    variants = OPTIONAL_COLUMN_MAP.get(field, [])
    for variant in variants:
        if variant in df.columns:
            return variant
    # Case-insensitive fallback
    lower_cols = {c.lower(): c for c in df.columns}
    for variant in variants:
        if variant.lower() in lower_cols:
            return lower_cols[variant.lower()]
    return None


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in review text."""
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()


def validate_and_parse_csv(
    file_bytes: bytes,
    filename: str,
    max_size_bytes: int,
) -> tuple[pd.DataFrame, dict]:
    """
    Validate and parse a CSV file.
    Returns (dataframe, column_mapping) or raises ValueError.
    """
    # Size check
    if len(file_bytes) > max_size_bytes:
        raise ValueError(
            f"File too large. Maximum allowed: {max_size_bytes // (1024*1024)} MB"
        )

    # Extension check
    if not filename.lower().endswith(".csv"):
        raise ValueError("Only CSV files are accepted.")

    # Encoding detection
    encoding = detect_encoding(file_bytes)
    logger.info(f"Detected encoding: {encoding}")

    # Parse CSV
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, dtype=str)
    except Exception:
        # Try UTF-8 as fallback
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8", dtype=str)
        except Exception as e:
            raise ValueError(f"Could not parse CSV file: {str(e)}")

    if df.empty:
        raise ValueError("The CSV file is empty.")

    if len(df.columns) == 0:
        raise ValueError("CSV has no columns.")

    # Find review column
    review_col = find_review_column(df)
    if review_col is None:
        raise ValueError(
            f"Required 'Review' column not found. "
            f"Available columns: {list(df.columns)}. "
            f"Accepted names: {REVIEW_COLUMN_VARIANTS}"
        )

    # Build column mapping
    column_mapping = {"review": review_col}
    for field in OPTIONAL_COLUMN_MAP:
        col = find_optional_column(df, field)
        if col:
            column_mapping[field] = col

    # Rename to normalized names
    rename_map = {v: k for k, v in column_mapping.items()}
    df = df.rename(columns=rename_map)

    # Drop completely empty reviews
    original_count = len(df)
    df = df.dropna(subset=["review"])
    df = df[df["review"].str.strip().str.len() > 0]
    dropped = original_count - len(df)
    if dropped > 0:
        logger.info(f"Dropped {dropped} empty reviews.")

    if len(df) == 0:
        raise ValueError("No valid reviews found after filtering empty rows.")

    # Remove exact duplicate reviews
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["review"])
    deduped = before_dedup - len(df)
    if deduped > 0:
        logger.info(f"Removed {deduped} duplicate reviews.")

    # Normalize whitespace in review text
    df["review"] = df["review"].apply(normalize_whitespace)

    # Reset index
    df = df.reset_index(drop=True)

    logger.info(
        f"CSV parsed: {len(df)} valid reviews, columns: {list(df.columns)}"
    )
    return df, column_mapping
