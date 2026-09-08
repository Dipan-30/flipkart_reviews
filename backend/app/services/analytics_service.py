"""
Analytics service — computes statistics from stored analysis results.
Uses Python/Pandas only. Does NOT call the LLM.
"""
import logging
from collections import Counter, defaultdict
from typing import Optional

from app.database.connection import get_db
from app.schemas.analytics import (
    AnalyticsResponse,
    AspectAnalytics,
    KeywordItem,
    ProductSentiment,
    ScoreDistributionBucket,
    SentimentCount,
    SentimentPercentage,
)

logger = logging.getLogger(__name__)


async def compute_analytics(dataset_id: str) -> AnalyticsResponse:
    """Compute all analytics for a dataset from stored results."""
    db = get_db()

    # Fetch all completed analysis results for this dataset
    cursor = db.analysis_results.find(
        {"dataset_id": dataset_id, "status": "completed"}
    )
    results = await cursor.to_list(length=None)

    # Fetch reviews for product info
    rev_cursor = db.reviews.find({"dataset_id": dataset_id})
    reviews = await rev_cursor.to_list(length=None)
    review_map = {str(r["_id"]): r for r in reviews}

    total_reviews = len(reviews)
    completed = len(results)

    if completed == 0:
        return _empty_analytics(dataset_id, total_reviews)

    # Sentiment counts
    sentiment_counter = Counter(r["sentiment"] for r in results)
    pos = sentiment_counter.get("positive", 0)
    neu = sentiment_counter.get("neutral", 0)
    neg = sentiment_counter.get("negative", 0)

    # Average score
    scores = [r["ai_sentiment_score"] for r in results if "ai_sentiment_score" in r]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Score distribution buckets
    buckets = {"0-1": 0, "1-2": 0, "2-3": 0, "3-4": 0, "4-5": 0}
    for s in scores:
        if s < 1:
            buckets["0-1"] += 1
        elif s < 2:
            buckets["1-2"] += 1
        elif s < 3:
            buckets["2-3"] += 1
        elif s < 4:
            buckets["3-4"] += 1
        else:
            buckets["4-5"] += 1
    score_distribution = [ScoreDistributionBucket(range=k, count=v) for k, v in buckets.items()]

    # Aspect analytics
    aspect_data = defaultdict(lambda: {"scores": [], "sentiments": []})
    for r in results:
        for a in r.get("aspects", []):
            name = a.get("name", "").strip().lower()
            if name:
                aspect_data[name]["scores"].append(a.get("score", 0))
                aspect_data[name]["sentiments"].append(a.get("sentiment", "neutral"))

    top_aspects = []
    for name, data in sorted(aspect_data.items(), key=lambda x: len(x[1]["scores"]), reverse=True)[:15]:
        s_counter = Counter(data["sentiments"])
        dominant = s_counter.most_common(1)[0][0]
        avg = round(sum(data["scores"]) / len(data["scores"]), 2)
        top_aspects.append(AspectAnalytics(name=name, count=len(data["scores"]), avg_score=avg, sentiment=dominant))

    # Keywords by sentiment
    pos_keywords: Counter = Counter()
    neg_keywords: Counter = Counter()
    for r in results:
        keywords = r.get("keywords", [])
        if r["sentiment"] == "positive":
            pos_keywords.update(keywords)
        elif r["sentiment"] == "negative":
            neg_keywords.update(keywords)

    top_positive_keywords = [
        KeywordItem(keyword=k, count=c, sentiment="positive")
        for k, c in pos_keywords.most_common(10)
    ]
    top_negative_keywords = [
        KeywordItem(keyword=k, count=c, sentiment="negative")
        for k, c in neg_keywords.most_common(10)
    ]

    # Product-level analytics
    product_data = defaultdict(lambda: {"results": [], "prices": []})
    for r in results:
        rev = review_map.get(r["review_id"], {})
        p_name = rev.get("product_name") or "Unknown Product"
        product_data[p_name]["results"].append(r)
        price = rev.get("product_price")
        if price:
            product_data[p_name]["prices"].append(price)

    products = []
    for p_name, data in product_data.items():
        p_results = data["results"]
        p_counter = Counter(rr["sentiment"] for rr in p_results)
        p_pos = p_counter.get("positive", 0)
        p_neu = p_counter.get("neutral", 0)
        p_neg = p_counter.get("negative", 0)
        p_total = len(p_results)
        p_scores = [rr["ai_sentiment_score"] for rr in p_results if "ai_sentiment_score" in rr]
        p_avg = round(sum(p_scores) / len(p_scores), 2) if p_scores else 0.0
        products.append(ProductSentiment(
            product_name=p_name,
            total_reviews=p_total,
            avg_score=p_avg,
            positive_count=p_pos,
            neutral_count=p_neu,
            negative_count=p_neg,
            positive_pct=round(p_pos / p_total * 100, 1) if p_total else 0,
            neutral_pct=round(p_neu / p_total * 100, 1) if p_total else 0,
            negative_pct=round(p_neg / p_total * 100, 1) if p_total else 0,
        ))

    return AnalyticsResponse(
        dataset_id=dataset_id,
        total_reviews=total_reviews,
        completed_reviews=completed,
        sentiment_counts=SentimentCount(positive=pos, neutral=neu, negative=neg),
        sentiment_percentages=SentimentPercentage(
            positive=round(pos / completed * 100, 1) if completed else 0,
            neutral=round(neu / completed * 100, 1) if completed else 0,
            negative=round(neg / completed * 100, 1) if completed else 0,
        ),
        average_ai_score=avg_score,
        score_distribution=score_distribution,
        top_aspects=top_aspects,
        top_positive_keywords=top_positive_keywords,
        top_negative_keywords=top_negative_keywords,
        products=products,
    )


def _empty_analytics(dataset_id: str, total_reviews: int) -> AnalyticsResponse:
    return AnalyticsResponse(
        dataset_id=dataset_id,
        total_reviews=total_reviews,
        completed_reviews=0,
        sentiment_counts=SentimentCount(positive=0, neutral=0, negative=0),
        sentiment_percentages=SentimentPercentage(positive=0, neutral=0, negative=0),
        average_ai_score=0.0,
        score_distribution=[],
        top_aspects=[],
        top_positive_keywords=[],
        top_negative_keywords=[],
        products=[],
    )
