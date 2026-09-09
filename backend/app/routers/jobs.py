"""Jobs router — status and retry."""
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.schemas.review import JobStatusResponse
from app.workers.analysis_worker import run_analysis_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _format_job(doc: dict) -> JobStatusResponse:
    total = doc.get("total", 1) or 1
    processed = doc.get("processed", 0)
    models = doc.get("models") or []
    raw_stats = doc.get("model_stats") or {}
    model_stats = {}
    for name in models:
        key = (name or "unknown").replace(".", "_").replace("$", "_")
        if key in raw_stats:
            model_stats[name] = raw_stats[key]
    for key, value in raw_stats.items():
        if key not in {(n or "").replace(".", "_").replace("$", "_") for n in models}:
            model_stats.setdefault(key, value)

    return JobStatusResponse(
        job_id=str(doc["_id"]),
        dataset_id=doc["dataset_id"],
        status=doc.get("status", "pending"),
        total=doc.get("total", 0),
        processed=processed,
        successful=doc.get("successful", 0),
        failed=doc.get("failed", 0),
        progress_percent=round(processed / total * 100, 1),
        started_at=doc.get("started_at"),
        completed_at=doc.get("completed_at"),
        error_message=doc.get("error_message"),
        models=models or None,
        models_unavailable=doc.get("models_unavailable") or None,
        model_stats=model_stats or None,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    try:
        doc = await db.analysis_jobs.find_one(
            {"_id": ObjectId(job_id), "user_id": current_user["user_id"]}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID.")

    if not doc:
        raise HTTPException(status_code=404, detail="Job not found.")

    return _format_job(doc)


@router.post("/{job_id}/stop", response_model=JobStatusResponse)
@router.post("/{job_id}/cancel", response_model=JobStatusResponse)
async def stop_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Stop an in-progress AI analysis job."""
    db = get_db()
    try:
        job = await db.analysis_jobs.find_one(
            {"_id": ObjectId(job_id), "user_id": current_user["user_id"]}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID.")

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    dataset_id = job["dataset_id"]
    now = datetime.now(timezone.utc)

    # Mark job as stopped
    await db.analysis_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"status": "stopped", "completed_at": now, "error_message": "Analysis stopped by user."}},
    )

    # Mark dataset as stopped
    await db.datasets.update_one(
        {"_id": ObjectId(dataset_id)},
        {"$set": {"status": "stopped"}},
    )

    # Revert processing reviews back to pending
    await db.reviews.update_many(
        {"dataset_id": dataset_id, "processing_status": "processing"},
        {"$set": {"processing_status": "pending"}},
    )

    logger.info(f"Analysis job {job_id} stopped by user.")
    updated = await db.analysis_jobs.find_one({"_id": ObjectId(job_id)})
    return _format_job(updated)


@router.post("/{job_id}/retry", response_model=JobStatusResponse)
async def retry_failed_reviews(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    try:
        job = await db.analysis_jobs.find_one(
            {"_id": ObjectId(job_id), "user_id": current_user["user_id"]}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID.")

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    dataset_id = job["dataset_id"]

    # Count failed reviews
    failed_count = await db.reviews.count_documents(
        {"dataset_id": dataset_id, "processing_status": "failed"}
    )
    if failed_count == 0:
        raise HTTPException(status_code=400, detail="No failed reviews to retry.")

    # Reset failed reviews to pending
    await db.reviews.update_many(
        {"dataset_id": dataset_id, "processing_status": "failed"},
        {"$set": {"processing_status": "pending", "error_message": None}},
    )

    # Update job for retry
    await db.analysis_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": "pending",
                "failed": 0,
                "completed_at": None,
                "error_message": None,
            },
            "$inc": {"total": 0},
        },
    )

    await db.datasets.update_one(
        {"_id": ObjectId(dataset_id)},
        {"$set": {"status": "analyzing"}},
    )

    # Relaunch background task
    asyncio.create_task(run_analysis_job(job_id, dataset_id, current_user["user_id"]))
    logger.info(f"Retrying {failed_count} failed reviews for job {job_id}")

    updated = await db.analysis_jobs.find_one({"_id": ObjectId(job_id)})
    return _format_job(updated)
