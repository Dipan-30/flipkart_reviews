"""
Evaluation service — compares AI predictions against ground truth labels.
Uses scikit-learn metrics. Never leaks ground truth to the LLM.

The existing single-model evaluation is preserved: the top level
accuracy/precision/recall/f1_score keys now describe the ENSEMBLE prediction
(which is what `analysis_results` stores after the multi-model upgrade, and is
identical to the single model result when only one model is configured).
`model_metrics` adds the same four metrics for every individual model so the
models can be compared against the SAME ground truth.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from bson import ObjectId

from app.database.connection import get_db

logger = logging.getLogger(__name__)

SENTIMENT_LABELS = ["negative", "neutral", "positive"]


def _metrics(y_true: list[str], y_pred: list[str]) -> dict:
    """Accuracy / weighted precision / recall / F1 / macro F1 + confusion matrix (percentages)."""
    labels_present = sorted(set(y_true + y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=labels_present)
    report = classification_report(
        y_true, y_pred, labels=labels_present, output_dict=True, zero_division=0
    )
    return {
        "accuracy": round(accuracy_score(y_true, y_pred) * 100, 2),
        "precision": round(
            precision_score(y_true, y_pred, average="weighted", zero_division=0) * 100, 2
        ),
        "recall": round(
            recall_score(y_true, y_pred, average="weighted", zero_division=0) * 100, 2
        ),
        "f1_score": round(f1_score(y_true, y_pred, average="weighted", zero_division=0) * 100, 2),
        "macro_f1": round(f1_score(y_true, y_pred, average="macro", zero_division=0) * 100, 2),
        "confusion_matrix": {"labels": labels_present, "matrix": cm.tolist()},
        "per_class_metrics": {
            label: {
                "precision": round(report[label]["precision"] * 100, 2),
                "recall": round(report[label]["recall"] * 100, 2),
                "f1_score": round(report[label]["f1-score"] * 100, 2),
                "support": int(report[label]["support"]),
            }
            for label in labels_present
            if label in report
        },
    }


async def run_evaluation(dataset_id: str, user_id: str) -> dict:
    """
    Compare AI-predicted sentiments against ground truth.
    Returns ensemble metrics plus one metric set per model.
    """
    db = get_db()

    # Get reviews with ground truth
    rev_cursor = db.reviews.find(
        {"dataset_id": dataset_id, "ground_truth_sentiment": {"$exists": True, "$ne": None}}
    )
    reviews = await rev_cursor.to_list(length=None)

    if not reviews:
        return {"error": "No reviews with ground truth labels found in this dataset."}

    review_ids = [str(r["_id"]) for r in reviews]
    ground_truth = {}
    for review in reviews:
        normalized = _normalize_sentiment(review.get("ground_truth_sentiment", ""))
        if normalized:
            ground_truth[str(review["_id"])] = normalized

    # ---- ensemble predictions (existing behaviour) ----
    res_cursor = db.analysis_results.find(
        {"review_id": {"$in": review_ids}, "status": "completed"}
    )
    results = await res_cursor.to_list(length=None)

    y_true: list[str] = []
    y_pred: list[str] = []
    matched = 0
    for result in results:
        gt = ground_truth.get(result.get("review_id"))
        pred = _normalize_sentiment(result.get("sentiment") or "")
        if gt and pred:
            y_true.append(gt)
            y_pred.append(pred)
            matched += 1
    skipped = len(reviews) - matched

    if not y_true:
        return {"error": "No matching AI predictions found. Please run analysis first."}

    logger.info(f"Evaluation: {matched} matched, {skipped} skipped")

    ensemble_metrics = _metrics(y_true, y_pred)

    # ---- per-model predictions + latency + success rate ----
    model_cursor = db.model_analysis_results.find(
        {"review_id": {"$in": review_ids}},
        {"review_id": 1, "model_name": 1, "sentiment": 1, "status": 1, "processing_time_ms": 1},
    )
    model_docs = await model_cursor.to_list(length=None)

    per_model: dict[str, dict] = defaultdict(lambda: {
        "true": [], "pred": [], "latencies": [], "total": 0, "success": 0
    })
    for doc in model_docs:
        model_name = doc.get("model_name") or "unknown"
        bucket = per_model[model_name]
        bucket["total"] += 1
        status = doc.get("status", "")
        if status == "completed":
            bucket["success"] += 1
            lat = doc.get("processing_time_ms")
            if lat is not None:
                bucket["latencies"].append(lat)
        gt = ground_truth.get(doc.get("review_id"))
        pred = _normalize_sentiment(doc.get("sentiment") or "")
        if gt and pred and status == "completed":
            bucket["true"].append(gt)
            bucket["pred"].append(pred)

    model_metrics = []
    for model_name, data in per_model.items():
        if not data["true"]:
            continue
        metrics = _metrics(data["true"], data["pred"])
        metrics["model_name"] = model_name
        metrics["matched_reviews"] = len(data["true"])
        total = data["total"]
        success = data["success"]
        lats = data["latencies"]
        metrics["avg_latency_ms"] = round(sum(lats) / len(lats)) if lats else 0
        metrics["success_rate_pct"] = round((success / total) * 100, 2) if total > 0 else 0.0
        model_metrics.append(metrics)
    model_metrics.sort(key=lambda m: -m["macro_f1"])

    best_model = model_metrics[0]["model_name"] if model_metrics else None

    eval_result = {
        "dataset_id": dataset_id,
        "total_with_ground_truth": len(reviews),
        "matched_reviews": matched,
        "skipped_reviews": skipped,
        # Ensemble = existing top-level keys (unchanged names)
        "accuracy": ensemble_metrics["accuracy"],
        "precision": ensemble_metrics["precision"],
        "recall": ensemble_metrics["recall"],
        "f1_score": ensemble_metrics["f1_score"],
        "confusion_matrix": ensemble_metrics["confusion_matrix"],
        "per_class_metrics": ensemble_metrics["per_class_metrics"],
        # New: explicit ensemble block + per-model comparison
        "ensemble_metrics": {
            **{k: v for k, v in ensemble_metrics.items()},
            "model_name": "Ensemble",
            "matched_reviews": matched,
        },
        "model_metrics": model_metrics,
        "models_evaluated": [m["model_name"] for m in model_metrics],
        "best_model": best_model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save to reports collection
    await db.reports.update_one(
        {"dataset_id": dataset_id, "type": "evaluation"},
        {"$set": {**eval_result, "user_id": user_id, "type": "evaluation"}},
        upsert=True,
    )

    return eval_result


async def get_evaluation_result(dataset_id: str) -> dict | None:
    """Get the most recent evaluation result for a dataset."""
    db = get_db()
    return await db.reports.find_one(
        {"dataset_id": dataset_id, "type": "evaluation"},
        sort=[("created_at", -1)],
    )


def _normalize_sentiment(s: str) -> str | None:
    """Normalize sentiment label to one of: positive, neutral, negative."""
    if not s:
        return None
    s = s.strip().lower()
    if s in ("positive", "pos", "1", "good"):
        return "positive"
    if s in ("negative", "neg", "-1", "bad"):
        return "negative"
    if s in ("neutral", "neu", "0", "mixed"):
        return "neutral"
    return s if s in SENTIMENT_LABELS else None
