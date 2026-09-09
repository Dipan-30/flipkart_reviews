"""
Multi-model comparison service.

Reads the per-model documents written by the analysis worker
(`model_analysis_results`) and aggregates them into dataset level comparison
metrics. Datasets analysed before the multi-model upgrade have no per-model
documents; for those we fall back to the legacy `analysis_results` collection
and report a single model, so old data still renders instead of erroring.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.config import get_settings
from app.database.connection import get_db
from app.services import ensemble as ens

logger = logging.getLogger(__name__)

# Fields needed for comparison maths — the bulky text fields are left out.
_LIGHT_PROJECTION = {
    "review_id": 1,
    "model_name": 1,
    "status": 1,
    "sentiment": 1,
    "ai_sentiment_score": 1,
    "processing_time_ms": 1,
    "error_type": 1,
    "product_name": 1,
}


async def load_model_rows(dataset_id: str) -> tuple[list[dict], bool]:
    """
    Return (rows, legacy) where rows are per-model result documents.

    `legacy` is True when the rows were synthesized from the pre-upgrade
    `analysis_results` collection.
    """
    db = get_db()
    cursor = db.model_analysis_results.find({"dataset_id": dataset_id}, _LIGHT_PROJECTION)
    rows = await cursor.to_list(length=None)
    if rows:
        return rows, False

    # ---- legacy fallback: one analysis_results doc == one model result ----
    cursor = db.analysis_results.find(
        {"dataset_id": dataset_id},
        {
            "review_id": 1,
            "model_name": 1,
            "status": 1,
            "sentiment": 1,
            "ai_sentiment_score": 1,
            "processing_time_ms": 1,
            "product_name": 1,
            "error_message": 1,
        },
    )
    legacy_docs = await cursor.to_list(length=None)
    settings = get_settings()
    synthesized = [
        {
            "review_id": doc.get("review_id"),
            "model_name": doc.get("model_name") or settings.primary_model,
            "status": doc.get("status") or "completed",
            "sentiment": doc.get("sentiment"),
            "ai_sentiment_score": doc.get("ai_sentiment_score"),
            "processing_time_ms": doc.get("processing_time_ms"),
            "product_name": doc.get("product_name"),
            "error_type": "error" if doc.get("status") == "failed" else None,
        }
        for doc in legacy_docs
    ]
    return synthesized, bool(synthesized)


def build_review_comparisons(rows: list[dict], primary_model: str) -> dict[str, dict]:
    """review_id -> comparison metrics (ensemble score, agreement, per-model scores)."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        review_id = row.get("review_id")
        if not review_id:
            continue
        grouped.setdefault(review_id, []).append(row)

    comparisons: dict[str, dict] = {}
    for review_id, model_rows in grouped.items():
        summary = ens.summarize_model_results(model_rows, primary_model=primary_model)
        summary.pop("consensus", None)
        comparisons[review_id] = summary
    return comparisons


async def get_model_comparison(
    dataset_id: str,
    dataset: Optional[dict] = None,
    review_limit: int = 30,
) -> dict:
    """Dataset level multi-model comparison payload."""
    db = get_db()
    settings = get_settings()
    configured = list(settings.llm_models)

    rows, legacy = await load_model_rows(dataset_id)
    comparisons = build_review_comparisons(rows, settings.primary_model)

    # Models present in the stored data (may include models no longer configured).
    observed: list[str] = []
    for row in rows:
        name = row.get("model_name")
        if name and name not in observed:
            observed.append(name)
    ordered_models = configured + [m for m in observed if m not in configured]

    # --- per model statistics ---
    rows_by_model: dict[str, list[dict]] = {name: [] for name in ordered_models}
    for row in rows:
        rows_by_model.setdefault(row.get("model_name") or "unknown", []).append(row)

    per_review_sentiments = {
        review_id: comparison["model_sentiments"]
        for review_id, comparison in comparisons.items()
    }
    pairwise = ens.pairwise_agreement(per_review_sentiments, ordered_models)

    model_stats = []
    for name in ordered_models:
        stats = ens.compute_model_stats(name, rows_by_model.get(name, []))
        related = [p for p in pairwise if name in (p["model_a"], p["model_b"]) and p["compared_reviews"]]
        stats["agreement_with_others_pct"] = (
            round(sum(p["agreement_pct"] for p in related) / len(related), 1) if related else None
        )
        stats["available"] = stats["analyzed_reviews"] > 0
        model_stats.append(stats)

    # --- ensemble level numbers ---
    comparison_list = list(comparisons.values())
    ensemble_scores = [
        c["ensemble_score"] for c in comparison_list if c.get("ensemble_score") is not None
    ]
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for comparison in comparison_list:
        sentiment = comparison.get("ensemble_sentiment")
        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1
    analyzed = len(ensemble_scores)

    def pct(count: int) -> float:
        return round(count / analyzed * 100, 1) if analyzed else 0.0

    dataset_score = ens.dataset_ensemble_score(comparison_list)

    # --- review level sample for the comparison chart ---
    sample_ids = _sorted_review_ids(list(comparisons.keys()))[:review_limit]
    review_docs = await _fetch_reviews(db, sample_ids)
    review_comparisons = []
    for review_id in sample_ids:
        comparison = comparisons[review_id]
        review = review_docs.get(review_id, {})
        text = (review.get("review") or "").strip()
        review_comparisons.append(
            {
                "review_id": review_id,
                "review_excerpt": (text[:160] + "…") if len(text) > 160 else text,
                "product_name": review.get("product_name"),
                "model_scores": comparison["model_scores"],
                "model_sentiments": comparison["model_sentiments"],
                "ensemble_score": comparison["ensemble_score"],
                "ensemble_sentiment": comparison["ensemble_sentiment"],
                "score_min": comparison["score_min"],
                "score_max": comparison["score_max"],
                "score_range": comparison["score_range"],
                "agreement_level": comparison["agreement_level"],
                "agreement_ratio": comparison["agreement_ratio"],
                "models_failed": [m for m in comparison["models_failed"] if m],
            }
        )

    if dataset is None:
        dataset = await _get_dataset(db, dataset_id)

    reporting = [s["model_name"] for s in model_stats if s["analyzed_reviews"] > 0]
    missing = [m for m in configured if m not in reporting]

    return {
        "dataset_id": dataset_id,
        "dataset_name": (dataset or {}).get("name"),
        "models_configured": configured,
        "models_reporting": reporting,
        "models_missing": missing,
        "multi_model": len(reporting) > 1,
        "legacy_single_model": legacy,
        "total_reviews": (dataset or {}).get("total_reviews", len(comparisons)),
        "analyzed_reviews": analyzed,
        "ensemble_score": dataset_score,
        "ensemble_sentiment": ens.score_to_sentiment(dataset_score),
        "ensemble_split": {
            "positive": sentiment_counts["positive"],
            "neutral": sentiment_counts["neutral"],
            "negative": sentiment_counts["negative"],
            "positive_pct": pct(sentiment_counts["positive"]),
            "neutral_pct": pct(sentiment_counts["neutral"]),
            "negative_pct": pct(sentiment_counts["negative"]),
        },
        "ensemble_score_distribution": ens.score_distribution(ensemble_scores),
        "model_stats": model_stats,
        "pairwise_agreement": pairwise,
        "agreement_summary": ens.agreement_summary(comparison_list),
        "review_comparisons": review_comparisons,
        "review_comparisons_limit": review_limit,
        "generated_at": datetime.now(timezone.utc),
    }


async def get_review_model_analysis(review_id: str, review: dict) -> dict:
    """Full per-model detail for one review (used by the reviews page drill-down)."""
    db = get_db()
    settings = get_settings()
    configured = list(settings.llm_models)

    cursor = db.model_analysis_results.find({"review_id": review_id})
    docs = await cursor.to_list(length=None)
    legacy = False

    if not docs:
        # Legacy single-model data: present the stored analysis as one model.
        legacy_doc = await db.analysis_results.find_one({"review_id": review_id})
        if legacy_doc:
            legacy = True
            docs = [
                {
                    "model_name": legacy_doc.get("model_name") or settings.primary_model,
                    "status": legacy_doc.get("status") or "completed",
                    "sentiment": legacy_doc.get("sentiment"),
                    "ai_sentiment_score": legacy_doc.get("ai_sentiment_score"),
                    "reason": legacy_doc.get("reason"),
                    "aspects": legacy_doc.get("aspects") or [],
                    "positive_points": legacy_doc.get("positive_points") or [],
                    "negative_points": legacy_doc.get("negative_points") or [],
                    "keywords": legacy_doc.get("keywords") or [],
                    "processing_time_ms": legacy_doc.get("processing_time_ms"),
                    "error_message": legacy_doc.get("error_message"),
                    "error_type": "error" if legacy_doc.get("status") == "failed" else None,
                }
            ]

    # Keep configured order first, then any extra models found in the data.
    order = {name: i for i, name in enumerate(configured)}
    docs.sort(key=lambda d: order.get(d.get("model_name"), len(order)))

    summary = ens.summarize_model_results(docs, primary_model=settings.primary_model)
    reporting = [d.get("model_name") for d in docs if d.get("status") == "completed"]
    model_results = [
        {
            "model_name": doc.get("model_name") or "unknown",
            "status": doc.get("status") or "failed",
            "sentiment": doc.get("sentiment"),
            "ai_sentiment_score": doc.get("ai_sentiment_score"),
            "reason": doc.get("reason"),
            "aspects": doc.get("aspects") or [],
            "positive_points": doc.get("positive_points") or [],
            "negative_points": doc.get("negative_points") or [],
            "keywords": doc.get("keywords") or [],
            "processing_time_ms": doc.get("processing_time_ms"),
            "attempts": doc.get("attempts"),
            "error_type": doc.get("error_type"),
            "error_message": doc.get("error_message"),
        }
        for doc in docs
    ]

    return {
        "review_id": review_id,
        "dataset_id": review.get("dataset_id"),
        "review": review.get("review", ""),
        "product_name": review.get("product_name"),
        "processing_status": review.get("processing_status", "pending"),
        "model_results": model_results,
        "models_configured": configured,
        "models_missing": [m for m in configured if m not in [d.get("model_name") for d in docs]],
        "ensemble_score": summary["ensemble_score"],
        "ensemble_sentiment": summary["ensemble_sentiment"],
        "score_min": summary["score_min"],
        "score_max": summary["score_max"],
        "score_range": summary["score_range"],
        "average_score": summary["ensemble_score"],
        "agreement_level": summary["agreement_level"],
        "agreement_ratio": summary["agreement_ratio"],
        "agreement_label": ens.agreement_label(summary["agreement_level"]),
        "success_count": summary["success_count"],
        "failure_count": summary["failure_count"],
        "legacy_single_model": legacy,
    }


async def load_review_comparison_map(review_ids: list[str]) -> dict[str, dict]:
    """
    Lightweight per-review comparison metrics for a page of reviews.

    Used by the reviews list endpoint so the UI can render the model comparison
    table without one request per review.
    """
    if not review_ids:
        return {}
    db = get_db()
    settings = get_settings()
    cursor = db.model_analysis_results.find(
        {"review_id": {"$in": review_ids}}, _LIGHT_PROJECTION
    )
    rows = await cursor.to_list(length=None)
    if not rows:
        return {}
    return build_review_comparisons(rows, settings.primary_model)


# --------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------- #
def _sorted_review_ids(review_ids: list[str]) -> list[str]:
    """Stable ordering (ObjectIds are time-ordered, so this is insertion order)."""
    return sorted(review_ids)


async def _fetch_reviews(db, review_ids: list[str]) -> dict[str, dict]:
    object_ids = []
    for review_id in review_ids:
        try:
            object_ids.append(ObjectId(review_id))
        except (InvalidId, TypeError):
            continue
    if not object_ids:
        return {}
    cursor = db.reviews.find(
        {"_id": {"$in": object_ids}}, {"review": 1, "product_name": 1}
    )
    docs = await cursor.to_list(length=None)
    return {str(doc["_id"]): doc for doc in docs}


async def _get_dataset(db, dataset_id: str) -> Optional[dict]:
    try:
        return await db.datasets.find_one({"_id": ObjectId(dataset_id)})
    except (InvalidId, TypeError):
        return None
