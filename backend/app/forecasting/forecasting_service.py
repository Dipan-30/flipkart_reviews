"""
Orchestrates the full forecasting pipeline:
  upload → sentiment index → join → train → forecast
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
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


from bson import ObjectId


def sanitize_for_mongo(obj):
    """
    Recursively convert NumPy/Pandas scalar types, ndarrays, and ObjectIds to native Python primitives
    (bool, int, float, list, str) so that BSON encoding in Motor/PyMongo and JSON encoding in FastAPI never fails.
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: sanitize_for_mongo(v) for k, v in obj.items() if k != "_id"}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_mongo(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return [sanitize_for_mongo(item) for item in obj.tolist()]
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        val = float(obj)
        return None if (np.isnan(val) or np.isinf(val)) else val
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


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

    await db.sales_datasets.insert_one(sanitize_for_mongo({**metadata}))

    # Store individual records
    records = daily.to_dict(orient="records")
    for rec in records:
        rec["sales_dataset_id"] = dataset_id
        rec["user_id"] = user_id
        rec["date"] = rec["date"].strftime("%Y-%m-%d") if hasattr(rec["date"], "strftime") else str(rec["date"])[:10]
        await db.sales_records.insert_one(sanitize_for_mongo(rec))

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
    """Return products that appear in both the user's reviews and their sales data."""
    # Products in this user's sales records only
    sales_products = set(await db.sales_records.distinct("product_name", {"user_id": user_id}))

    # Products with completed analysis scoped to this user's datasets
    user_dataset_ids = await db.datasets.distinct("_id", {"user_id": user_id})
    user_dataset_id_strs = [str(d) for d in user_dataset_ids]

    review_products = set(await db.analysis_results.distinct(
        "product_name",
        {"dataset_id": {"$in": user_dataset_id_strs}, "status": "completed"},
    )) if user_dataset_id_strs else set()

    overlap = sales_products & review_products
    return [{"product_name": p} for p in sorted(overlap)]


async def build_joined_dataset(
    db: AsyncIOMotorDatabase,
    sales_dataset_id: str,
    review_dataset_id: str,
    product_name: str,
) -> pd.DataFrame | None:
    """
    Join daily sales records with LAG-1 daily sentiment on (date, product_name).

    Lag-1: sentiment(t-1) is used to predict sales(t).
    This prevents same-day leakage.

    Returns a DataFrame (date-indexed) or None if insufficient data.
    NaN sentinel in 'lagged_sentiment' means no sentiment for that day;
    imputation happens in run_training AFTER train/test split.
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

    # Load daily sentiment
    sentiment_records = await get_daily_sentiment(db, review_dataset_id, product_name)

    if not sentiment_records:
        logger.warning(f"No daily sentiment records found for '{product_name}'. Using SARIMA only.")
        return sales_df.sort_values("date").set_index("date")

    sentiment_df = pd.DataFrame(sentiment_records)
    sentiment_df["date"] = pd.to_datetime(sentiment_df["date"])
    sentiment_df = sentiment_df.rename(columns={"avg_score": "lagged_sentiment"})
    sentiment_df = sentiment_df.sort_values("date")

    # Lag-1: shift sentiment forward by 1 day so sentiment(date D) → sales(date D+1)
    sentiment_df["date"] = sentiment_df["date"] + pd.Timedelta(days=1)

    merged = sales_df.merge(
        sentiment_df[["date", "lagged_sentiment"]], on="date", how="left"
    )
    return merged.sort_values("date").set_index("date")


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

    Methodology:
    - Lag-1 sentiment: sentiment(t-1) → sales(t); eliminates same-day leakage.
    - Train-only imputation: missing lagged_sentiment filled with TRAINING-set mean only.
    - SARIMAX future exog: training-mean repeated for forecast horizon (future sentiment unknown).
    - Seasonality auto-disabled when training set is too small for the requested period.
    - Both SARIMA and SARIMAX evaluated on the same chronological test window.
    - Metrics: MAE, RMSE, MAPE on out-of-sample test set only.

    Minimum: 10 rows. Recommended: 60+ days for weekly seasonality.
    """
    df = await build_joined_dataset(db, sales_dataset_id, review_dataset_id, product_name)
    if df is None or len(df) < 10:
        raise ValueError(
            f"Insufficient data for product '{product_name}'. "
            f"Need at least 10 rows, got {len(df) if df is not None else 0}. "
            f"Recommended: 60+ days for meaningful seasonal analysis."
        )

    units = df["units_sold"]
    has_sentiment = bool("lagged_sentiment" in df.columns and bool(df["lagged_sentiment"].notna().any()))

    train_units, test_units = train_test_split_chronological(units, test_fraction)

    # Auto-disable seasonality when training data is too small for the period
    s = seasonal_order[3] if len(seasonal_order) == 4 else 0
    effective_seasonal_order = tuple(seasonal_order)
    if s > 0 and len(train_units) <= 2 * s:
        logger.warning(
            f"Disabling seasonality (s={s}): training set has only {len(train_units)} points "
            f"(need > {2 * s}). Setting seasonal_order=(0,0,0,0)."
        )
        effective_seasonal_order = (0, 0, 0, 0)

    sarima_result = fit_sarima(
        train_units, test_units,
        order=tuple(order), seasonal_order=effective_seasonal_order,
        forecast_horizon=forecast_horizon,
    )

    sarimax_result = None
    if has_sentiment:
        sentiment = df["lagged_sentiment"]
        train_sent, test_sent = train_test_split_chronological(sentiment, test_fraction)

        # Impute with TRAINING mean only — never use test-set information
        train_mean = float(train_sent.mean()) if train_sent.notna().any() else 3.0
        train_sent = train_sent.fillna(train_mean)
        test_sent = test_sent.fillna(train_mean)

        # Future exog: repeat training mean (future real-world sentiment is unknown)
        future_exog_vals = pd.Series(
            np.full(forecast_horizon, train_mean),
            dtype=float,
        )

        try:
            sarimax_result = fit_sarimax(
                train_units, test_units,
                exog_train=train_sent, exog_test=test_sent,
                future_exog=future_exog_vals,
                order=tuple(order), seasonal_order=effective_seasonal_order,
                forecast_horizon=forecast_horizon,
            )
        except Exception as exc:
            logger.warning(f"SARIMAX failed, falling back to SARIMA only: {exc}")

    # Determine best model based on out-of-sample test MAE
    best_model = "SARIMA"
    if (
        sarimax_result
        and sarimax_result.get("test_metrics")
        and sarima_result.get("test_metrics")
    ):
        sx_mae = sarimax_result["test_metrics"].get("mae")
        s_mae = sarima_result["test_metrics"].get("mae")
        if sx_mae is not None and s_mae is not None and sx_mae < s_mae:
            best_model = "SARIMAX"

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
        "seasonal_order": list(effective_seasonal_order),
        "forecast_horizon": forecast_horizon,
        "test_fraction": test_fraction,
        "best_model": best_model,
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

    sanitized_doc = sanitize_for_mongo({k: v for k, v in run_doc.items() if k != "_id"})
    await db.forecasting_runs.insert_one(sanitized_doc)
    sanitized_doc.pop("_id", None)
    logger.info(f"Forecasting run {run_id} saved for product '{product_name}' (best model: {best_model})")
    return sanitized_doc


async def get_runs(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    cursor = db.forecasting_runs.find(
        {"user_id": user_id},
        {
            "_id": 0,
            "run_id": 1,
            "product_name": 1,
            "created_at": 1,
            "has_sentiment": 1,
            "best_model": 1,
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
