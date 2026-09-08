"""
Backfill script: make datasets analysed BEFORE the multi-model upgrade work
with the new multi-model collections.

What it does (idempotent, non-destructive):

1. For every `analysis_results` document that has no matching
   `model_analysis_results` document, it creates ONE per-model document from
   the legacy fields (the model that actually produced that result).
2. It adds the new ensemble fields to the legacy `analysis_results` document
   (ensemble_score = the stored ai_sentiment_score, single-model agreement),
   without touching the existing fields.

Nothing is deleted or overwritten: documents that already carry ensemble data
are skipped, so the script can be run as many times as you like.

Usage (from the backend/ directory, with the venv active):

    python ../scripts/migrate_multi_model.py            # apply
    python ../scripts/migrate_multi_model.py --dry-run  # report only
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import get_settings  # noqa: E402
from app.database.connection import close_db, connect_db, get_db  # noqa: E402
from app.database.indexes import create_indexes  # noqa: E402


async def migrate(dry_run: bool = False) -> dict:
    settings = get_settings()
    await connect_db()
    db = get_db()

    if not dry_run:
        await create_indexes(db)

    stats = {
        "analysis_results_seen": 0,
        "model_docs_created": 0,
        "consensus_docs_updated": 0,
        "already_migrated": 0,
        "skipped_no_model_data": 0,
    }
    now = datetime.now(timezone.utc)

    cursor = db.analysis_results.find({})
    async for doc in cursor:
        stats["analysis_results_seen"] += 1
        review_id = doc.get("review_id")
        if not review_id:
            stats["skipped_no_model_data"] += 1
            continue

        existing = await db.model_analysis_results.count_documents({"review_id": review_id})
        has_ensemble = doc.get("models_total") is not None

        if existing and has_ensemble:
            stats["already_migrated"] += 1
            continue

        model_name = doc.get("model_name") or settings.primary_model
        status = doc.get("status") or "completed"
        score = doc.get("ai_sentiment_score")
        sentiment = doc.get("sentiment")

        # ---- 1. per-model document ----
        if not existing:
            model_doc = {
                "review_id": review_id,
                "dataset_id": doc.get("dataset_id"),
                "user_id": doc.get("user_id"),
                "product_name": doc.get("product_name"),
                "model_name": model_name,
                "status": status,
                "sentiment": sentiment,
                "ai_sentiment_score": score,
                "reason": doc.get("reason"),
                "aspects": doc.get("aspects") or [],
                "positive_points": doc.get("positive_points") or [],
                "negative_points": doc.get("negative_points") or [],
                "keywords": doc.get("keywords") or [],
                "processing_time_ms": doc.get("processing_time_ms"),
                "attempts": None,
                "error_type": "error" if status == "failed" else None,
                "error_message": doc.get("error_message"),
                "migrated_from_legacy": True,
                "created_at": doc.get("created_at") or now,
                "updated_at": now,
            }
            if not dry_run:
                await db.model_analysis_results.update_one(
                    {"review_id": review_id, "model_name": model_name},
                    {"$set": model_doc},
                    upsert=True,
                )
            stats["model_docs_created"] += 1

        # ---- 2. ensemble fields on the consensus document ----
        if not has_ensemble:
            completed = status == "completed" and score is not None
            update = {
                "ensemble_score": score if completed else None,
                "ensemble_sentiment": sentiment if completed else None,
                "model_scores": {model_name: score} if completed else {},
                "model_sentiments": {model_name: sentiment} if completed and sentiment else {},
                "score_min": score if completed else None,
                "score_max": score if completed else None,
                "score_range": 0.0 if completed else None,
                "agreement_level": "single_model" if completed else "unavailable",
                "agreement_ratio": 1.0 if completed else 0.0,
                "majority_sentiment": sentiment if completed else None,
                "models_used": [model_name] if completed else [],
                "models_failed": [] if completed else [model_name],
                "models_total": 1,
                "models_succeeded_count": 1 if completed else 0,
                "models_failed_count": 0 if completed else 1,
                "migrated_from_legacy": True,
                "updated_at": now,
            }
            if not dry_run:
                await db.analysis_results.update_one({"_id": doc["_id"]}, {"$set": update})
            stats["consensus_docs_updated"] += 1

    await close_db()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill multi-model analysis data.")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    stats = asyncio.run(migrate(dry_run=args.dry_run))

    print("\n=== Multi-model migration " + ("(dry run) " if args.dry_run else "") + "===")
    for key, value in stats.items():
        print(f"  {key:26} {value}")
    if args.dry_run:
        print("\nNothing was written. Re-run without --dry-run to apply.")
    else:
        print("\nDone. Existing data was preserved; only new fields were added.")


if __name__ == "__main__":
    main()
