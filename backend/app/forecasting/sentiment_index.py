"""
Aggregate AI sentiment scores → daily sentiment index per product.

The sentiment index is the mean AI score (1-5) for all completed reviews
of a given product on each date. It is stored in the `daily_sentiment`
collection and used as an exogenous regressor in SARIMAX.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def build_daily_sentiment_index(
    db: AsyncIOMotorDatabase,
    dataset_id: str,
    product_name: Optional[str] = None,
) -> list[dict]:
    """
    Read analysis_results for a dataset, group by (review_date, product_name),
    compute mean AI score per day.

    Returns a list of dicts:
        {date: str (YYYY-MM-DD), product_name: str, avg_score: float, review_count: int}

    Also upserts the results into the `daily_sentiment` collection.
    """
    # Pull reviews that have a date field
    query: dict = {"dataset_id": dataset_id, "review_date": {"$exists": True, "$ne": None}}
    if product_name:
        query["product_name"] = product_name

    cursor = db.analysis_results.find(
        {"dataset_id": dataset_id, "status": "completed"},
        {"review_id": 1, "ai_sentiment_score": 1, "product_name": 1},
    )
    result_docs = await cursor.to_list(length=None)

    # Map review_id -> analysis score
    score_map = {
        doc["review_id"]: doc.get("ai_sentiment_score")
        for doc in result_docs
        if doc.get("ai_sentiment_score") is not None
    }

    # Pull reviews (with dates)
    rev_query: dict = {"dataset_id": dataset_id, "review_date": {"$exists": True, "$ne": None}}
    if product_name:
        rev_query["product_name"] = product_name

    rev_cursor = db.reviews.find(
        rev_query,
        {"_id": 1, "review_date": 1, "product_name": 1},
    )
    reviews = await rev_cursor.to_list(length=None)

    if not reviews:
        logger.warning(
            f"No reviews with review_date found for dataset {dataset_id}. "
            "Sentiment index will be empty. "
            "Tip: add a 'review_date' column to your reviews CSV."
        )
        return []

    # Aggregate
    buckets: dict[tuple, list[float]] = defaultdict(list)
    for rev in reviews:
        rid = str(rev["_id"])
        score = score_map.get(rid)
        if score is None:
            continue
        pname = rev.get("product_name", "Unknown")
        rdate = rev.get("review_date")
        if rdate is None:
            continue
        # Normalize date to YYYY-MM-DD string
        if isinstance(rdate, datetime):
            date_str = rdate.strftime("%Y-%m-%d")
        elif isinstance(rdate, date):
            date_str = rdate.isoformat()
        else:
            date_str = str(rdate)[:10]
        buckets[(date_str, pname)].append(float(score))

    records = []
    for (date_str, pname), scores in buckets.items():
        avg_score = round(sum(scores) / len(scores), 4)
        record = {
            "dataset_id": dataset_id,
            "date": date_str,
            "product_name": pname,
            "avg_score": avg_score,
            "review_count": len(scores),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)
        # Upsert
        await db.daily_sentiment.update_one(
            {"dataset_id": dataset_id, "date": date_str, "product_name": pname},
            {"$set": record},
            upsert=True,
        )

    logger.info(
        f"Built {len(records)} daily sentiment records for dataset {dataset_id}"
        + (f", product '{product_name}'" if product_name else "")
    )
    return records


async def get_daily_sentiment(
    db: AsyncIOMotorDatabase,
    dataset_id: str,
    product_name: str,
) -> list[dict]:
    """Return stored daily sentiment records sorted by date."""
    cursor = db.daily_sentiment.find(
        {"dataset_id": dataset_id, "product_name": product_name},
        {"_id": 0},
        sort=[("date", 1)],
    )
    return await cursor.to_list(length=None)
