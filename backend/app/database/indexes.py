"""
Create MongoDB indexes for performance.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create all required indexes on startup."""
    logger.info("Creating MongoDB indexes...")

    # users
    await db.users.create_index([("email", ASCENDING)], unique=True)

    # datasets
    await db.datasets.create_index([("user_id", ASCENDING)])
    await db.datasets.create_index([("created_at", DESCENDING)])

    # reviews
    await db.reviews.create_index([("dataset_id", ASCENDING)])
    await db.reviews.create_index([("processing_status", ASCENDING)])
    await db.reviews.create_index([("dataset_id", ASCENDING), ("processing_status", ASCENDING)])

    # analysis_results (consensus / ensemble document, one per review)
    await db.analysis_results.create_index([("review_id", ASCENDING)], unique=True)
    await db.analysis_results.create_index([("dataset_id", ASCENDING)])
    await db.analysis_results.create_index([("sentiment", ASCENDING)])
    await db.analysis_results.create_index([("dataset_id", ASCENDING), ("status", ASCENDING)])
    await db.analysis_results.create_index([("dataset_id", ASCENDING), ("agreement_level", ASCENDING)])

    # model_analysis_results (one document per review + model)
    await db.model_analysis_results.create_index(
        [("review_id", ASCENDING), ("model_name", ASCENDING)], unique=True
    )
    await db.model_analysis_results.create_index([("dataset_id", ASCENDING)])
    await db.model_analysis_results.create_index(
        [("dataset_id", ASCENDING), ("model_name", ASCENDING), ("status", ASCENDING)]
    )
    await db.model_analysis_results.create_index(
        [("dataset_id", ASCENDING), ("product_name", ASCENDING), ("model_name", ASCENDING)]
    )
    await db.model_analysis_results.create_index([("user_id", ASCENDING)])

    # analysis_jobs
    await db.analysis_jobs.create_index([("dataset_id", ASCENDING)])
    await db.analysis_jobs.create_index([("user_id", ASCENDING)])

    # reports (evaluation + recommendation snapshots)
    await db.reports.create_index([("dataset_id", ASCENDING), ("type", ASCENDING)])

    # ---- Forecasting collections ----
    # sales_datasets
    await db.sales_datasets.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    # sales_records
    await db.sales_records.create_index(
        [("sales_dataset_id", ASCENDING), ("product_name", ASCENDING), ("date", ASCENDING)]
    )

    # daily_sentiment
    await db.daily_sentiment.create_index(
        [("dataset_id", ASCENDING), ("product_name", ASCENDING), ("date", ASCENDING)], unique=True
    )

    # forecasting_runs
    await db.forecasting_runs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.forecasting_runs.create_index([("run_id", ASCENDING)], unique=True)

    # forecast_results
    await db.forecast_results.create_index([("run_id", ASCENDING)])

    logger.info("MongoDB indexes created.")
