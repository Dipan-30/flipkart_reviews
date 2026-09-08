"""
Orchestrates the full forecasting pipeline:
  upload → sentiment index → join → train → forecast
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.forecasting.preprocessing import (
    aggregate_daily,
    train_test_split_chronological,
    validate_and_parse_csv,
)
from app.forecasting.sentiment_index import get_daily_sentiment
from app.forecasting.models import fit_sarima, fit_sarimax

logger = logging.getLogger(__name__)


async def upload_sales_dataset(
    db: AsyncIOMotorDatabase,
    content: bytes,
    filename: str,
    user_id: str,
) -> dict:
    """Parse, validate, store a sales CSV and return metadata."""
    df = validate_and_parse_csv(content, filename)
    daily = aggregate_daily(df)

    dataset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    metadata = {
        "sales_dataset_id": dataset_id,
        "filename": filename,
        "user_id": user_id,
        "total_rows": len(daily),
        "products": sorted(daily["product_name"].unique().tolist()),
        "date_range_start": daily["date"].min().strftime("%Y-%m-%d"),
        "date_range_end": daily["date"].max().strftime("%Y-%m-%d"),
        "created_at": now,
    }

    await db.sales_datasets.insert_one({**metadata})

    # Store individual records
    records = daily.to_dict(orient="records")
    for rec in records:
        rec["sales_dataset_id"] = dataset_id
        rec["user_id"] = user_id
        rec["date"] = rec["date"].strftime("%Y-%m-%d") if hasattr(rec["date"], "strftime") else str(rec["date"])[:10]
        await db.sales_records.insert_one(rec)

    return metadata


async def get_sales_datasets(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    cursor = db.sales_datasets.find(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return await cursor.to_list(length=None)


async def get_products_with_both_data(
    db: AsyncIOMotorDatabase, user_id: str
) -> list[dict]:
    """Return products that appear in both reviews (analysis_results) and sales_records."""
    # Products in sales
    sales_products_cursor = db.sales_records.distinct("product_name", {"user_id": user_id})
    # distinct returns a list directly for motor
    sales_products = set(await db.sales_records.distinct("product_name", {"user_id": user_id}))

    # Products with completed analysis
    review_products = set(await db.analysis_results.distinct(
        "product_name", {"status": "completed"}
    ))

    overlap = sales_products & review_products
    return [{"product_name": p} for p in sorted(overlap)]


async def build_joined_dataset(
    db: AsyncIOMotorDatabase,
    sales_dataset_id: str,
    review_dataset_id: str,
    product_name: str,
) -> pd.DataFrame | None:
    """
    Join daily sales records with daily sentiment index on (date, product_name).
    Returns a DataFrame or None if insufficient data.
    """
    # Load sales records
    cursor = db.sales_records.find(
        {"sales_dataset_id": sales_dataset_id, "product_name": product_name},
        {"_id": 0, "date": 1, "units_sold": 1},
        sort=[("date", 1)],
    )
    sales_docs = await cursor.to_list(length=None)

    if not sales_docs:
        return None

    sales_df = pd.DataFrame(sales_docs)
    sales_df["date"] = pd.to_datetime(sales_df["date"])

    # Load sentiment
    sentiment_records = await get_daily_sentiment(db, review_dataset_id, product_name)

    if not sentiment_records:
        logger.warning(f"No daily sentiment records found for {product_name}. Using SARIMA only.")
        sales_df = sales_df.sort_values("date").set_index("date")
        return sales_df

    sentiment_df = pd.DataFrame(sentiment_records)
    sentiment_df["date"] = pd.to_datetime(sentiment_df["date"])
    sentiment_df = sentiment_df.rename(columns={"avg_score": "sentiment_score"})

    merged = sales_df.merge(
        sentiment_df[["date", "sentiment_score"]], on="date", how="left"
    )
    merged["sentiment_score"] = merged["sentiment_score"].fillna(merged["sentiment_score"].mean())
    merged = merged.sort_values("date").set_index("date")
    return merged


async def run_training(
    db: AsyncIOMotorDatabase,
    sales_dataset_id: str,
    review_dataset_id: str,
    product_name: str,
    user_id: str,
    order: tuple = (1, 1, 1),
    seasonal_order: tuple = (0, 0, 0, 0),
    forecast_horizon: int = 30,
    test_fraction: float = 0.2,
) -> dict:
    """
    Train SARIMA + SARIMAX and store results in forecasting_runs.
    Returns the run document.
    """
    df = await build_joined_dataset(db, sales_dataset_id, review_dataset_id, product_name)
    if df is None or len(df) < 10:
        raise ValueError(
            f"Insufficient data for product '{product_name}'. "
            f"Need at least 10 rows, got {len(df) if df is not None else 0}."
        )

    units = df["units_sold"]
    has_sentiment = "sentiment_score" in df.columns

    train_units, test_units = train_test_split_chronological(units, test_fraction)

    sarima_result = fit_sarima(
        train_units, test_units,
        order=tuple(order), seasonal_order=tuple(seasonal_order),
        forecast_horizon=forecast_horizon,
    )

    sarimax_result = None
    if has_sentiment:
        sentiment = df["sentiment_score"]
        train_sent, test_sent = train_test_split_chronological(sentiment, test_fraction)
        try:
            sarimax_result = fit_sarimax(
                train_units, test_units,
                exog_train=train_sent, exog_test=test_sent,
                order=tuple(order), seasonal_order=tuple(seasonal_order),
                forecast_horizon=forecast_horizon,
            )
        except Exception as exc:
            logger.warning(f"SARIMAX failed, falling back to SARIMA only: {exc}")

    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build date indices for the forecast period
    last_date = df.index[-1]
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1), periods=forecast_horizon, freq="D"
    )
    test_dates = [d.strftime("%Y-%m-%d") for d in test_units.index]
    actual_dates = [d.strftime("%Y-%m-%d") for d in df.index]
    train_dates = [d.strftime("%Y-%m-%d") for d in train_units.index]

    run_doc = {
        "run_id": run_id,
        "sales_dataset_id": sales_dataset_id,
        "review_dataset_id": review_dataset_id,
        "product_name": product_name,
        "user_id": user_id,
        "order": list(order),
        "seasonal_order": list(seasonal_order),
        "forecast_horizon": forecast_horizon,
        "test_fraction": test_fraction,
        "n_train": len(train_units),
        "n_test": len(test_units),
        "sarima": sarima_result,
        "sarimax": sarimax_result,
        "actual_dates": actual_dates,
        "actual_values": units.values.tolist(),
        "train_dates": train_dates,
        "test_dates": test_dates,
        "test_actual_values": test_units.values.tolist(),
        "future_dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "has_sentiment": has_sentiment,
        "created_at": now,
    }

    await db.forecasting_runs.insert_one({k: v for k, v in run_doc.items() if k != "_id"})
    logger.info(f"Forecasting run {run_id} saved for product '{product_name}'")
    return run_doc


async def get_runs(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    cursor = db.forecasting_runs.find(
        {"user_id": user_id},
        {
            "_id": 0,
            "run_id": 1,
            "product_name": 1,
            "created_at": 1,
            "has_sentiment": 1,
            "sarima.test_metrics": 1,
            "sarimax.test_metrics": 1,
            "n_train": 1,
            "n_test": 1,
        },
        sort=[("created_at", -1)],
    )
    return await cursor.to_list(length=None)


async def get_run(db: AsyncIOMotorDatabase, run_id: str, user_id: str) -> dict | None:
    return await db.forecasting_runs.find_one(
        {"run_id": run_id, "user_id": user_id},
        {"_id": 0},
    )
