"""
Dataset service — handles CSV ingestion and storage.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from app.database.connection import get_db

logger = logging.getLogger(__name__)


async def create_dataset_from_csv(
    user_id: str,
    filename: str,
    df,  # pandas DataFrame
    column_mapping: dict,
) -> str:
    """
    Store reviews from a parsed DataFrame into MongoDB.
    Returns the new dataset_id.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    has_ground_truth = "ground_truth_sentiment" in column_mapping

    # Create dataset document
    dataset_doc = {
        "user_id": user_id,
        "filename": filename,
        "original_columns": list(df.columns),
        "column_mapping": column_mapping,
        "total_reviews": len(df),
        "processed_reviews": 0,
        "successful_reviews": 0,
        "failed_reviews": 0,
        "status": "uploaded",
        "has_ground_truth": has_ground_truth,
        "created_at": now,
        "completed_at": None,
    }

    result = await db.datasets.insert_one(dataset_doc)
    dataset_id = str(result.inserted_id)
    logger.info(f"Dataset created: {dataset_id} | {len(df)} reviews | file={filename}")

    # Build review documents
    review_docs = []
    for _, row in df.iterrows():
        doc = {
            "dataset_id": dataset_id,
            "user_id": user_id,
            "review": row.get("review", ""),
            "processing_status": "pending",
            "attempt_count": 0,
            "error_message": None,
            "created_at": now,
        }
        # Optional fields
        for field in ["product_name", "product_price", "summary"]:
            val = row.get(field)
            if val and isinstance(val, str) and val.strip():
                doc[field] = val.strip()
            else:
                doc[field] = None

        # Ground truth stored separately, never sent to LLM
        if has_ground_truth:
            gt = row.get("ground_truth_sentiment")
            if gt and isinstance(gt, str) and gt.strip():
                doc["ground_truth_sentiment"] = gt.strip().lower()

        review_docs.append(doc)

    if review_docs:
        await db.reviews.insert_many(review_docs)
        logger.info(f"Inserted {len(review_docs)} review documents for dataset {dataset_id}")

    return dataset_id


async def get_dataset(dataset_id: str, user_id: str) -> Optional[dict]:
    """Get a dataset by ID, verifying ownership."""
    db = get_db()
    try:
        doc = await db.datasets.find_one(
            {"_id": ObjectId(dataset_id), "user_id": user_id}
        )
        return doc
    except Exception:
        return None


async def list_datasets(user_id: str) -> list[dict]:
    """List all datasets for a user."""
    db = get_db()
    cursor = db.datasets.find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    return await cursor.to_list(length=100)


async def delete_dataset(dataset_id: str, user_id: str) -> bool:
    """Delete dataset and all associated data."""
    db = get_db()
    try:
        # Verify ownership
        dataset = await db.datasets.find_one(
            {"_id": ObjectId(dataset_id), "user_id": user_id}
        )
        if not dataset:
            return False

        # Delete in order
        await db.analysis_results.delete_many({"dataset_id": dataset_id})
        await db.model_analysis_results.delete_many({"dataset_id": dataset_id})
        await db.reviews.delete_many({"dataset_id": dataset_id})
        await db.analysis_jobs.delete_many({"dataset_id": dataset_id})
        await db.reports.delete_many({"dataset_id": dataset_id})
        await db.datasets.delete_one({"_id": ObjectId(dataset_id)})

        logger.info(f"Dataset {dataset_id} deleted.")
        return True
    except Exception as e:
        logger.error(f"Error deleting dataset {dataset_id}: {e}")
        return False


async def create_analysis_job(dataset_id: str, user_id: str, total: int) -> str:
    """Create a new analysis job and return its ID."""
    db = get_db()
    now = datetime.now(timezone.utc)
    job_doc = {
        "dataset_id": dataset_id,
        "user_id": user_id,
        "status": "pending",
        "total": total,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "created_at": now,
    }
    result = await db.analysis_jobs.insert_one(job_doc)
    job_id = str(result.inserted_id)

    # Update dataset status
    await db.datasets.update_one(
        {"_id": ObjectId(dataset_id)},
        {"$set": {"status": "analyzing"}},
    )
    logger.info(f"Analysis job created: {job_id} | dataset={dataset_id}")
    return job_id
