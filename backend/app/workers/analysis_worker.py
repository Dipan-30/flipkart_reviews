"""
Background analysis worker.

Processes reviews with configurable concurrency (OLLAMA_CONCURRENCY reviews in
parallel, OLLAMA_MODEL_CONCURRENCY models in parallel per review) and supports
resumable processing — only pending/failed reviews are picked up.

Multi-model behaviour
---------------------
Every configured model receives the SAME review text. Each model's result is
stored individually in `model_analysis_results`, and the merged/ensemble result
is stored in `analysis_results` (the collection the existing analytics,
evaluation and reviews endpoints already read), which keeps the whole existing
API working while reflecting the ensemble.

A review is marked `completed` when AT LEAST ONE model succeeded; the failed
models are recorded with their error type so the UI can show
"model X unavailable" without failing the dataset.
"""
import asyncio
import logging
from datetime import datetime, timezone

from bson import ObjectId

from app.config import get_settings
from app.database.connection import get_db
from app.llm.multi_model_service import MultiModelAnalysisService
from app.schemas.llm import MultiModelAnalysis

logger = logging.getLogger(__name__)


async def run_analysis_job(job_id: str, dataset_id: str, user_id: str) -> None:
    """
    Main background analysis task.
    Fetches pending/failed reviews and processes them through every configured model.
    Resumes gracefully if interrupted.
    """
    settings = get_settings()
    db = get_db()
    # Fresh orchestrator per job so the availability cache reflects the models
    # installed right now.
    multi = MultiModelAnalysisService()
    semaphore = asyncio.Semaphore(max(1, settings.ollama_concurrency))

    logger.info(
        f"[Job {job_id}] Starting analysis | dataset={dataset_id} | "
        f"models={', '.join(multi.models) or 'none'}"
    )

    try:
        availability = await multi.refresh_availability(force=True)
        missing = [name for name, ok in availability["models"].items() if not ok]
        if missing:
            logger.warning(
                f"[Job {job_id}] Unavailable model(s): {', '.join(missing)} — "
                "these will be recorded as unavailable, the job continues."
            )
        if availability["models"] and all(not ok for ok in availability["models"].values()):
            # Nothing can possibly succeed — fail loudly instead of silently
            # writing an all-failed dataset.
            message = (
                availability.get("error")
                or f"None of the configured models are installed in Ollama: {', '.join(missing)}"
            )
            raise RuntimeError(message)

        await db.analysis_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "running",
                    "started_at": datetime.now(timezone.utc),
                    "models": multi.models,
                    "models_unavailable": missing,
                }
            },
        )

        # Reset any stuck "processing" reviews from a previous crash
        await db.reviews.update_many(
            {"dataset_id": dataset_id, "processing_status": "processing"},
            {"$set": {"processing_status": "pending"}},
        )

        # Get all pending or failed reviews
        cursor = db.reviews.find(
            {"dataset_id": dataset_id, "processing_status": {"$in": ["pending", "failed"]}},
            sort=[("_id", 1)],
        )
        reviews = await cursor.to_list(length=None)

        logger.info(f"[Job {job_id}] Found {len(reviews)} reviews to process.")

        if not reviews:
            logger.info(f"[Job {job_id}] No pending reviews. Marking complete.")
            await _mark_job_complete(db, job_id, dataset_id)
            return

        tasks = [
            _process_single_review(db, multi, semaphore, job_id, dataset_id, user_id, review)
            for review in reviews
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        await _mark_job_complete(db, job_id, dataset_id)
        logger.info(f"[Job {job_id}] Analysis complete.")

    except Exception as e:
        logger.error(f"[Job {job_id}] Fatal error: {e}", exc_info=True)
        await db.analysis_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc),
                    "error_message": str(e),
                }
            },
        )


async def _process_single_review(
    db,
    multi: MultiModelAnalysisService,
    semaphore: asyncio.Semaphore,
    job_id: str,
    dataset_id: str,
    user_id: str,
    review: dict,
) -> None:
    """Run every model on one review and persist per-model + consensus results."""
    review_id = str(review["_id"])
    now = datetime.now(timezone.utc)

    async with semaphore:
        # Check if job was cancelled / stopped
        job_doc = await db.analysis_jobs.find_one({"_id": ObjectId(job_id)}, {"status": 1})
        if job_doc and job_doc.get("status") in ["stopped", "cancelled"]:
            await db.reviews.update_one(
                {"_id": review["_id"]},
                {"$set": {"processing_status": "pending"}}
            )
            return

        try:
            await db.reviews.update_one(
                {"_id": review["_id"]},
                {"$set": {"processing_status": "processing"}, "$inc": {"attempt_count": 1}},
            )

            # Identical review text for every model (never sends Rate/Sentiment).
            analysis: MultiModelAnalysis = await multi.analyze_review(
                review=review.get("review", ""),
                product_name=review.get("product_name"),
                product_price=review.get("product_price"),
                summary=review.get("summary"),
            )

            await _store_model_results(db, dataset_id, user_id, review, analysis, now)

            if analysis.success_count == 0:
                # Every model failed -> the review itself failed.
                error_msg = _first_error(analysis) or "All configured models failed."
                await _record_review_failure(
                    db, job_id, dataset_id, review, review_id, analysis, error_msg, now
                )
                return

            await _store_consensus(db, dataset_id, review_id, review, analysis, now)

            partial = analysis.failure_count > 0
            await db.reviews.update_one(
                {"_id": review["_id"]},
                {
                    "$set": {
                        "processing_status": "completed",
                        "error_message": _partial_message(analysis) if partial else None,
                        "models_succeeded": analysis.models_used,
                        "models_failed": analysis.models_failed,
                    }
                },
            )

            await db.analysis_jobs.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$inc": {
                        "processed": 1,
                        "successful": 1,
                        "partial_reviews": 1 if partial else 0,
                        **_model_counter_increments(analysis),
                    }
                },
            )
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$inc": {"processed_reviews": 1, "successful_reviews": 1}},
            )

            scores = ", ".join(f"{m}={s}" for m, s in analysis.model_scores.items())
            logger.info(
                f"[Job {job_id}] ✓ Review {review_id} | ensemble={analysis.ensemble_score} "
                f"({analysis.ensemble_sentiment}) | agreement={analysis.agreement_level} | {scores}"
                + (f" | failed: {', '.join(analysis.models_failed)}" if partial else "")
            )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            error_msg = str(e)[:500]
            logger.error(f"[Job {job_id}] ✗ Review {review_id} failed: {error_msg}", exc_info=True)
            await _record_review_failure(
                db, job_id, dataset_id, review, review_id, None, error_msg, now
            )


# --------------------------------------------------------------------- #
# Persistence helpers
# --------------------------------------------------------------------- #
async def _store_model_results(
    db,
    dataset_id: str,
    user_id: str,
    review: dict,
    analysis: MultiModelAnalysis,
    now: datetime,
) -> None:
    """Upsert one document per (review, model) — no result is ever overwritten by another model."""
    review_id = str(review["_id"])
    for result in analysis.model_results:
        doc = {
            "review_id": review_id,
            "dataset_id": dataset_id,
            "user_id": user_id,
            "product_name": review.get("product_name"),
            "model_name": result.model_name,
            "status": result.status,
            "sentiment": result.sentiment,
            "ai_sentiment_score": result.ai_sentiment_score,
            "reason": result.reason,
            "aspects": [a.model_dump() for a in result.aspects],
            "positive_points": result.positive_points,
            "negative_points": result.negative_points,
            "keywords": result.keywords,
            "processing_time_ms": result.processing_time_ms,
            "attempts": result.attempts,
            "error_type": result.error_type,
            "error_message": result.error_message,
            "updated_at": now,
        }
        await db.model_analysis_results.update_one(
            {"review_id": review_id, "model_name": result.model_name},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )


async def _store_consensus(
    db,
    dataset_id: str,
    review_id: str,
    review: dict,
    analysis: MultiModelAnalysis,
    now: datetime,
) -> None:
    """
    Write the merged ensemble result into `analysis_results`.

    Same shape as before (sentiment / ai_sentiment_score / reason / aspects /
    positive_points / negative_points / keywords / model_name /
    processing_time_ms / status), plus the new ensemble fields, so every
    existing endpoint keeps working unchanged.
    """
    consensus = analysis.consensus or {}
    times = [
        r.processing_time_ms
        for r in analysis.model_results
        if r.status == "completed" and r.processing_time_ms is not None
    ]
    doc = {
        "review_id": review_id,
        "dataset_id": dataset_id,
        "product_name": review.get("product_name"),
        "sentiment": consensus.get("sentiment"),
        "ai_sentiment_score": consensus.get("ai_sentiment_score"),
        "reason": consensus.get("reason"),
        "aspects": consensus.get("aspects", []),
        "positive_points": consensus.get("positive_points", []),
        "negative_points": consensus.get("negative_points", []),
        "keywords": consensus.get("keywords", []),
        # Legacy field: which model's reasoning text is shown.
        "model_name": consensus.get("reference_model"),
        "processing_time_ms": max(times) if times else None,
        "status": "completed",
        "error_message": _partial_message(analysis) if analysis.failure_count else None,
        # --- multi-model fields ---
        "is_ensemble": True,
        "ensemble_score": analysis.ensemble_score,
        "ensemble_sentiment": analysis.ensemble_sentiment,
        "model_scores": analysis.model_scores,
        "model_sentiments": analysis.model_sentiments,
        "score_min": analysis.score_min,
        "score_max": analysis.score_max,
        "score_range": analysis.score_range,
        "agreement_level": analysis.agreement_level,
        "agreement_ratio": analysis.agreement_ratio,
        "majority_sentiment": analysis.majority_sentiment,
        "models_used": analysis.models_used,
        "models_failed": analysis.models_failed,
        "models_total": analysis.models_total,
        "models_succeeded_count": analysis.success_count,
        "models_failed_count": analysis.failure_count,
        "total_processing_time_ms": sum(times) if times else None,
        "updated_at": now,
    }
    await db.analysis_results.update_one(
        {"review_id": review_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


async def _record_review_failure(
    db,
    job_id: str,
    dataset_id: str,
    review: dict,
    review_id: str,
    analysis: MultiModelAnalysis | None,
    error_msg: str,
    now: datetime,
) -> None:
    """Mark a review failed (every model failed, or an unexpected error)."""
    doc = {
        "review_id": review_id,
        "dataset_id": dataset_id,
        "product_name": review.get("product_name"),
        "status": "failed",
        "error_message": error_msg,
        "updated_at": now,
    }
    if analysis is not None:
        doc.update(
            {
                "models_failed": analysis.models_failed,
                "models_total": analysis.models_total,
                "models_succeeded_count": 0,
                "models_failed_count": analysis.failure_count,
                "model_scores": {},
                "agreement_level": "unavailable",
            }
        )
    await db.analysis_results.update_one(
        {"review_id": review_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    await db.reviews.update_one(
        {"_id": review["_id"]},
        {
            "$set": {
                "processing_status": "failed",
                "error_message": error_msg,
                "models_succeeded": [],
                "models_failed": analysis.models_failed if analysis else [],
            }
        },
    )
    increments = {"processed": 1, "failed": 1}
    if analysis is not None:
        increments.update(_model_counter_increments(analysis))
    await db.analysis_jobs.update_one({"_id": ObjectId(job_id)}, {"$inc": increments})
    await db.datasets.update_one(
        {"_id": ObjectId(dataset_id)},
        {"$inc": {"processed_reviews": 1, "failed_reviews": 1}},
    )


def _model_counter_increments(analysis: MultiModelAnalysis) -> dict:
    """
    Per-model success/failure counters on the job document.

    Dots are not allowed in `$inc` keys of a nested path unless we escape the
    model name — model names contain ':' (fine) but may contain '.' (e.g.
    'llama3.1:8b'), so the key is sanitized.
    """
    increments: dict[str, int] = {}
    for result in analysis.model_results:
        key = _safe_key(result.model_name)
        bucket = "success" if result.status == "completed" else (
            "unavailable" if result.status == "unavailable" else "failed"
        )
        increments[f"model_stats.{key}.{bucket}"] = 1
    return increments


def _safe_key(model_name: str) -> str:
    """MongoDB field names cannot contain '.' or start with '$'."""
    return (model_name or "unknown").replace(".", "_").replace("$", "_")


def _partial_message(analysis: MultiModelAnalysis) -> str | None:
    if not analysis.models_failed:
        return None
    details = []
    for result in analysis.model_results:
        if result.status != "completed":
            details.append(f"{result.model_name}: {result.error_type or 'failed'}")
    return "Partial analysis — " + "; ".join(details)


def _first_error(analysis: MultiModelAnalysis) -> str | None:
    for result in analysis.model_results:
        if result.error_message:
            return f"{result.model_name}: {result.error_message}"
    return None


async def _mark_job_complete(db, job_id: str, dataset_id: str) -> None:
    """Mark job and dataset as completed."""
    job = await db.analysis_jobs.find_one({"_id": ObjectId(job_id)}, {"status": 1})
    if job and job.get("status") in ["stopped", "cancelled"]:
        logger.info(f"[Job {job_id}] Was stopped by user. Skipping completion status update.")
        return

    now = datetime.now(timezone.utc)
    await db.analysis_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"status": "completed", "completed_at": now}},
    )
    await db.datasets.update_one(
        {"_id": ObjectId(dataset_id)},
        {"$set": {"status": "completed", "completed_at": now}},
    )
