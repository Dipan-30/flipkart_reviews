"""
Re-open an already-analysed dataset so it can be analysed again by ALL the
currently configured models.

Why this exists
---------------
`POST /api/datasets/{id}/analyze` only picks up reviews whose
`processing_status` is `pending` or `failed` (that is what makes analysis
resumable). A dataset that was fully analysed before the multi-model upgrade
therefore has every review marked `completed`, so it can never be re-run and
its reviews keep showing "Single model" agreement.

This script flips those reviews back to `pending` and resets the dataset's
counters, which makes the existing "Start AI Analysis" button appear again and
lets the normal, unmodified analysis flow re-run every configured model.

What it touches (nothing is deleted by default)
-----------------------------------------------
* `reviews`  : processing_status -> "pending", error_message cleared,
               models_succeeded / models_failed removed.
* `datasets` : status -> "uploaded", processed/successful/failed counters -> 0,
               completed_at -> None.

Analysis documents are intentionally LEFT IN PLACE: the worker upserts on
`(review_id, model_name)` for `model_analysis_results` and on `review_id` for
`analysis_results`, so a re-run overwrites each model's own result and never
duplicates it. Use `--purge-results` only if you also changed OLLAMA_MODELS and
want results from models you no longer use to disappear from the comparison.

Usage (from the backend/ directory)
-----------------------------------
    python ../scripts/reset_dataset_analysis.py --list
    python ../scripts/reset_dataset_analysis.py --dataset-id <id> --dry-run
    python ../scripts/reset_dataset_analysis.py --dataset-id <id>
    python ../scripts/reset_dataset_analysis.py --all --dry-run

Then press "Start AI Analysis" in the UI (or POST to the analyze endpoint).
"""
import argparse
import asyncio
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from bson import ObjectId  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database.connection import close_db, connect_db, get_db  # noqa: E402


async def list_datasets(db) -> None:
    """Print every dataset with the models that actually produced results."""
    cursor = db.datasets.find({}, sort=[("created_at", -1)])
    datasets = await cursor.to_list(length=200)
    if not datasets:
        print("  (no datasets found)")
        return

    print(f"  {'dataset_id':26} {'status':11} {'reviews':>7}  models with stored results")
    print("  " + "-" * 78)
    for doc in datasets:
        dataset_id = str(doc["_id"])
        models = await db.model_analysis_results.distinct(
            "model_name", {"dataset_id": dataset_id}
        )
        print(
            f"  {dataset_id:26} {str(doc.get('status')):11} "
            f"{doc.get('total_reviews', 0):>7}  "
            f"{', '.join(sorted(models)) or '(none)'}"
        )


async def reset_dataset(db, dataset_id: str, dry_run: bool, purge: bool) -> dict:
    """Flip one dataset's reviews back to pending. Returns a stats dict."""
    try:
        oid = ObjectId(dataset_id)
    except Exception:
        raise SystemExit(f"'{dataset_id}' is not a valid dataset id.")

    dataset = await db.datasets.find_one({"_id": oid})
    if not dataset:
        raise SystemExit(f"Dataset {dataset_id} not found.")

    total = await db.reviews.count_documents({"dataset_id": dataset_id})
    completed = await db.reviews.count_documents(
        {"dataset_id": dataset_id, "processing_status": {"$nin": ["pending"]}}
    )
    existing_models = await db.model_analysis_results.distinct(
        "model_name", {"dataset_id": dataset_id}
    )

    stats = {
        "dataset_id": dataset_id,
        "filename": dataset.get("filename"),
        "reviews_total": total,
        "reviews_reset": completed,
        "models_with_results": sorted(existing_models),
        "results_purged": 0,
    }

    if dry_run:
        return stats

    if purge:
        deleted_model = await db.model_analysis_results.delete_many(
            {"dataset_id": dataset_id}
        )
        deleted_consensus = await db.analysis_results.delete_many(
            {"dataset_id": dataset_id}
        )
        stats["results_purged"] = (
            deleted_model.deleted_count + deleted_consensus.deleted_count
        )

    await db.reviews.update_many(
        {"dataset_id": dataset_id},
        {
            "$set": {"processing_status": "pending", "error_message": None},
            "$unset": {"models_succeeded": "", "models_failed": ""},
        },
    )
    await db.datasets.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "uploaded",
                "processed_reviews": 0,
                "successful_reviews": 0,
                "failed_reviews": 0,
                "completed_at": None,
            }
        },
    )
    return stats


async def run(args) -> None:
    settings = get_settings()
    await connect_db()
    db = get_db()
    try:
        if args.list:
            print("\n=== Datasets ===")
            await list_datasets(db)
            print(f"\nCurrently configured models: {', '.join(settings.llm_models)}")
            return

        if args.all:
            cursor = db.datasets.find({}, {"_id": 1})
            ids = [str(doc["_id"]) for doc in await cursor.to_list(length=500)]
        else:
            ids = [args.dataset_id]

        header = "=== Reset for re-analysis " + ("(dry run) " if args.dry_run else "") + "==="
        print("\n" + header)
        for dataset_id in ids:
            stats = await reset_dataset(db, dataset_id, args.dry_run, args.purge_results)
            print(f"\n  dataset            {stats['dataset_id']}  ({stats['filename']})")
            print(f"  reviews total      {stats['reviews_total']}")
            print(f"  reviews reset      {stats['reviews_reset']}")
            print(f"  existing results   {', '.join(stats['models_with_results']) or '(none)'}")
            if args.purge_results:
                print(f"  results purged     {stats['results_purged']}")

        print(f"\n  models to be used  {', '.join(settings.llm_models)}")
        if args.dry_run:
            print("\nNothing was written. Re-run without --dry-run to apply.")
        else:
            print(
                "\nDone. Open the dataset in the UI and press 'Start AI Analysis' — "
                "every configured model will now score every review."
            )
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-open an analysed dataset so all configured models can re-run."
    )
    parser.add_argument("--dataset-id", help="dataset to reset")
    parser.add_argument("--all", action="store_true", help="reset every dataset")
    parser.add_argument("--list", action="store_true", help="list datasets and exit")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument(
        "--purge-results",
        action="store_true",
        help="also DELETE stored analysis results for this dataset "
        "(only needed if you removed a model from OLLAMA_MODELS)",
    )
    args = parser.parse_args()

    if not args.list and not args.all and not args.dataset_id:
        parser.error("give --dataset-id <id>, or --all, or --list")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
