"""
Ensemble / model-agreement mathematics.

Pure functions only — no database, no HTTP, no Pydantic — so the logic can be
unit tested in isolation and reused by the worker, the comparison service and
the recommendation service.

Terminology
-----------
model result      one model's analysis of one review
consensus         the merged, backward-compatible single result stored in
                  `analysis_results` (what the existing UI/analytics read)
ensemble score    mean of the successful model scores for one review
agreement         how much the models agree on the sentiment LABEL
"""
from collections import Counter, OrderedDict
from typing import Iterable, Optional

# --------------------------------------------------------------------- #
# Sentiment thresholds
# --------------------------------------------------------------------- #
# A 0.0-5.0 AI sentiment score is mapped to a label with these cut-offs.
# They match the few-shot examples used in the prompt
# (0.5 -> negative, 2.7 -> neutral, 4.8 -> positive).
POSITIVE_SCORE_THRESHOLD = 3.5
NEGATIVE_SCORE_THRESHOLD = 2.0

SENTIMENTS = ("positive", "neutral", "negative")

# Agreement levels
AGREEMENT_HIGH = "high"
AGREEMENT_MODERATE = "moderate"
AGREEMENT_LOW = "low"
AGREEMENT_SINGLE = "single_model"
AGREEMENT_NONE = "unavailable"

SCORE_BUCKETS = ("0-1", "1-2", "2-3", "3-4", "4-5")

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_UNAVAILABLE = "unavailable"


def score_to_sentiment(score: Optional[float]) -> Optional[str]:
    """Map a 0-5 sentiment score to a label using the documented thresholds."""
    if score is None:
        return None
    if score >= POSITIVE_SCORE_THRESHOLD:
        return "positive"
    if score < NEGATIVE_SCORE_THRESHOLD:
        return "negative"
    return "neutral"


def normalize_sentiment(value: Optional[str]) -> Optional[str]:
    """Normalize a free-form sentiment label, or None when unrecognised."""
    if not value:
        return None
    v = str(value).strip().lower()
    if v in SENTIMENTS:
        return v
    if v in ("pos", "good", "1"):
        return "positive"
    if v in ("neg", "bad", "-1"):
        return "negative"
    if v in ("neu", "mixed", "0"):
        return "neutral"
    return None


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(float(value), digits)


# --------------------------------------------------------------------- #
# Agreement
# --------------------------------------------------------------------- #
def compute_agreement(sentiments: Iterable[Optional[str]]) -> dict:
    """
    Agreement metric for the sentiment labels produced by several models.

        all models identical              -> high      (ratio 1.0)
        a strict majority exists          -> moderate  (e.g. 2 of 3)
        no majority / even split          -> low       (e.g. 1/1/1 or 1/1)
        exactly one usable result         -> single_model
        no usable result                  -> unavailable

    `ratio` is the share of models backing the most common label and is used
    as the numeric agreement index elsewhere.
    """
    labels = [s for s in (normalize_sentiment(x) for x in sentiments) if s]
    n = len(labels)
    if n == 0:
        return {
            "level": AGREEMENT_NONE,
            "ratio": 0.0,
            "majority_sentiment": None,
            "model_count": 0,
            "distribution": {},
        }
    counts = Counter(labels)
    top_label, top_count = counts.most_common(1)[0]
    ratio = round(top_count / n, 4)
    if n == 1:
        level = AGREEMENT_SINGLE
    elif top_count == n:
        level = AGREEMENT_HIGH
    elif top_count > n / 2:
        level = AGREEMENT_MODERATE
    else:
        level = AGREEMENT_LOW
    return {
        "level": level,
        "ratio": ratio,
        # A majority label only exists when more than half the models back it.
        "majority_sentiment": top_label if top_count > n / 2 or n == 1 else None,
        "model_count": n,
        "distribution": dict(counts),
    }


def agreement_label(level: str) -> str:
    """Human readable agreement level."""
    return {
        AGREEMENT_HIGH: "High",
        AGREEMENT_MODERATE: "Moderate",
        AGREEMENT_LOW: "Low",
        AGREEMENT_SINGLE: "Single model",
        AGREEMENT_NONE: "Unavailable",
    }.get(level, "Unknown")


# --------------------------------------------------------------------- #
# Merging model results into a consensus
# --------------------------------------------------------------------- #
def merge_aspects(results: list[dict]) -> list[dict]:
    """
    Merge the `aspects` lists of several model results.

    Aspects are grouped by (lower-cased) name; the score becomes the mean
    across models and the sentiment the majority label (falling back to the
    score threshold when models disagree evenly).
    """
    grouped: "OrderedDict[str, dict]" = OrderedDict()
    for res in results:
        for aspect in res.get("aspects") or []:
            name = str(aspect.get("name", "")).strip().lower()
            if not name:
                continue
            entry = grouped.setdefault(name, {"scores": [], "sentiments": []})
            try:
                entry["scores"].append(float(aspect.get("score", 0.0)))
            except (TypeError, ValueError):
                continue
            sentiment = normalize_sentiment(aspect.get("sentiment"))
            if sentiment:
                entry["sentiments"].append(sentiment)

    merged: list[dict] = []
    for name, entry in grouped.items():
        if not entry["scores"]:
            continue
        avg = sum(entry["scores"]) / len(entry["scores"])
        counts = Counter(entry["sentiments"])
        if counts:
            top_label, top_count = counts.most_common(1)[0]
            total = sum(counts.values())
            sentiment = top_label if top_count > total / 2 else (score_to_sentiment(avg) or "neutral")
        else:
            sentiment = score_to_sentiment(avg) or "neutral"
        merged.append(
            {
                "name": name,
                "sentiment": sentiment,
                "score": round(max(0.0, min(5.0, avg)), 2),
                "model_mentions": len(entry["scores"]),
            }
        )
    merged.sort(key=lambda a: (-a["model_mentions"], a["name"]))
    return merged[:20]


def merge_text_list(results: list[dict], field: str, limit: int) -> list[str]:
    """Union of a list-of-strings field across models, de-duplicated, order kept."""
    seen: set[str] = set()
    out: list[str] = []
    for res in results:
        for item in res.get(field) or []:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
            if len(out) >= limit:
                return out
    return out


def summarize_model_results(
    model_results: list[dict],
    primary_model: Optional[str] = None,
) -> dict:
    """
    Turn the per-model results of ONE review into comparison metrics plus a
    consensus payload.

    `model_results` items are plain dicts with at least:
        model_name, status, sentiment, ai_sentiment_score
    and optionally reason/aspects/positive_points/negative_points/keywords/
    processing_time_ms/error_message/error_type.

    The returned dict never raises when every model failed — callers decide
    what to do with `success_count == 0`.
    """
    succeeded = [r for r in model_results if r.get("status") == STATUS_COMPLETED]
    failed = [r for r in model_results if r.get("status") != STATUS_COMPLETED]

    scores: "OrderedDict[str, float]" = OrderedDict()
    sentiments: "OrderedDict[str, str]" = OrderedDict()
    times: "OrderedDict[str, Optional[int]]" = OrderedDict()
    for res in succeeded:
        name = res.get("model_name") or "unknown"
        raw_score = res.get("ai_sentiment_score")
        if raw_score is None:
            continue
        scores[name] = round(float(raw_score), 2)
        sentiments[name] = normalize_sentiment(res.get("sentiment")) or (
            score_to_sentiment(float(raw_score)) or "neutral"
        )
        times[name] = res.get("processing_time_ms")

    agreement = compute_agreement(sentiments.values())
    score_values = list(scores.values())
    ensemble_score = _round(sum(score_values) / len(score_values)) if score_values else None
    score_min = _round(min(score_values)) if score_values else None
    score_max = _round(max(score_values)) if score_values else None
    score_range = _round(score_max - score_min) if score_values else None

    # Ensemble sentiment: majority vote when a majority exists, otherwise the
    # label implied by the averaged score.
    ensemble_sentiment = agreement["majority_sentiment"] or score_to_sentiment(ensemble_score)

    consensus: Optional[dict] = None
    if succeeded:
        # Reference model supplies the human readable `reason`: the primary
        # (legacy) model when it succeeded, otherwise the first success.
        reference = next(
            (r for r in succeeded if r.get("model_name") == primary_model),
            succeeded[0],
        )
        consensus = {
            "sentiment": ensemble_sentiment,
            "ai_sentiment_score": ensemble_score,
            "reason": reference.get("reason"),
            "reference_model": reference.get("model_name"),
            "aspects": merge_aspects(succeeded),
            "positive_points": merge_text_list(succeeded, "positive_points", 10),
            "negative_points": merge_text_list(succeeded, "negative_points", 10),
            "keywords": merge_text_list(succeeded, "keywords", 20),
        }

    return {
        "model_scores": dict(scores),
        "model_sentiments": dict(sentiments),
        "model_processing_times": {k: v for k, v in times.items()},
        "ensemble_score": ensemble_score,
        "ensemble_sentiment": ensemble_sentiment,
        "score_min": score_min,
        "score_max": score_max,
        "score_range": score_range,
        "agreement_level": agreement["level"],
        "agreement_ratio": agreement["ratio"],
        "agreement_distribution": agreement["distribution"],
        "majority_sentiment": agreement["majority_sentiment"],
        "models_total": len(model_results),
        "models_used": list(scores.keys()),
        "models_failed": [r.get("model_name") for r in failed],
        "success_count": len(succeeded),
        "failure_count": len(failed),
        "consensus": consensus,
    }


# --------------------------------------------------------------------- #
# Dataset level statistics
# --------------------------------------------------------------------- #
def score_distribution(scores: Iterable[float]) -> list[dict]:
    """Bucket scores into the same 0-1 … 4-5 ranges the analytics page uses."""
    buckets = {key: 0 for key in SCORE_BUCKETS}
    for raw in scores:
        if raw is None:
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        if score < 1:
            buckets["0-1"] += 1
        elif score < 2:
            buckets["1-2"] += 1
        elif score < 3:
            buckets["2-3"] += 1
        elif score < 4:
            buckets["3-4"] += 1
        else:
            buckets["4-5"] += 1
    return [{"range": key, "count": buckets[key]} for key in SCORE_BUCKETS]


def compute_model_stats(model_name: str, rows: list[dict]) -> dict:
    """
    Per-model dataset statistics.

    `rows` are that model's result documents for one dataset (or one product):
    {status, sentiment, ai_sentiment_score, processing_time_ms, error_type}
    """
    completed = [r for r in rows if r.get("status") == STATUS_COMPLETED]
    failed = [r for r in rows if r.get("status") == STATUS_FAILED]
    unavailable = [r for r in rows if r.get("status") == STATUS_UNAVAILABLE]

    scores = [
        float(r["ai_sentiment_score"])
        for r in completed
        if r.get("ai_sentiment_score") is not None
    ]
    counter = Counter(
        normalize_sentiment(r.get("sentiment")) or "neutral" for r in completed
    )
    total = len(completed)
    times = [
        int(r["processing_time_ms"])
        for r in completed
        if r.get("processing_time_ms") is not None
    ]
    error_types = Counter(
        r.get("error_type") or "error" for r in rows if r.get("status") == STATUS_FAILED
    )

    def pct(count: int) -> float:
        return round(count / total * 100, 1) if total else 0.0

    return {
        "model_name": model_name,
        "analyzed_reviews": total,
        "failed_reviews": len(failed),
        "unavailable_reviews": len(unavailable),
        "average_score": _round(sum(scores) / len(scores)) if scores else 0.0,
        "positive_count": counter.get("positive", 0),
        "neutral_count": counter.get("neutral", 0),
        "negative_count": counter.get("negative", 0),
        "positive_pct": pct(counter.get("positive", 0)),
        "neutral_pct": pct(counter.get("neutral", 0)),
        "negative_pct": pct(counter.get("negative", 0)),
        "avg_processing_time_ms": round(sum(times) / len(times)) if times else 0,
        "score_distribution": score_distribution(scores),
        "error_types": dict(error_types),
    }


def pairwise_agreement(
    per_review_sentiments: dict[str, dict[str, str]],
    models: list[str],
) -> list[dict]:
    """
    Agreement between every pair of models.

    `per_review_sentiments` maps review_id -> {model_name: sentiment} and only
    reviews where BOTH models of a pair produced a label are compared.
    """
    out: list[dict] = []
    for i, model_a in enumerate(models):
        for model_b in models[i + 1 :]:
            compared = 0
            agreed = 0
            for sentiment_by_model in per_review_sentiments.values():
                a = normalize_sentiment(sentiment_by_model.get(model_a))
                b = normalize_sentiment(sentiment_by_model.get(model_b))
                if a and b:
                    compared += 1
                    if a == b:
                        agreed += 1
            out.append(
                {
                    "model_a": model_a,
                    "model_b": model_b,
                    "compared_reviews": compared,
                    "agreed_reviews": agreed,
                    "agreement_pct": round(agreed / compared * 100, 1) if compared else 0.0,
                }
            )
    return out


def agreement_summary(review_comparisons: list[dict]) -> dict:
    """
    Aggregate per-review agreement into dataset level numbers.

    `review_comparisons` items need `agreement_level` and `agreement_ratio`.
    """
    levels = Counter(
        c.get("agreement_level") or AGREEMENT_NONE for c in review_comparisons
    )
    ratios = [
        float(c.get("agreement_ratio") or 0.0)
        for c in review_comparisons
        if c.get("agreement_level") not in (AGREEMENT_NONE, None)
    ]
    total = sum(levels.values())

    def pct(count: int) -> float:
        return round(count / total * 100, 1) if total else 0.0

    return {
        "total_reviews": total,
        "high": levels.get(AGREEMENT_HIGH, 0),
        "moderate": levels.get(AGREEMENT_MODERATE, 0),
        "low": levels.get(AGREEMENT_LOW, 0),
        "single_model": levels.get(AGREEMENT_SINGLE, 0),
        "unavailable": levels.get(AGREEMENT_NONE, 0),
        "high_pct": pct(levels.get(AGREEMENT_HIGH, 0)),
        "moderate_pct": pct(levels.get(AGREEMENT_MODERATE, 0)),
        "low_pct": pct(levels.get(AGREEMENT_LOW, 0)),
        # Numeric index in 0..1 used by the recommendation service.
        "agreement_index": round(sum(ratios) / len(ratios), 4) if ratios else 0.0,
    }


def dataset_ensemble_score(review_comparisons: list[dict]) -> Optional[float]:
    """Mean of the per-review ensemble scores (the primary AI indicator)."""
    scores = [
        float(c["ensemble_score"])
        for c in review_comparisons
        if c.get("ensemble_score") is not None
    ]
    return _round(sum(scores) / len(scores)) if scores else None
