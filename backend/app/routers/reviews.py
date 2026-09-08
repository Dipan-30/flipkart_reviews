"""Reviews router — paginated list, single review, per-model analysis."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.schemas.comparison import ReviewModelAnalysisResponse
from app.schemas.review import ReviewListResponse, ReviewResponse
from app.services import comparison_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reviews"])


def _build_review_response(review: dict, result: Optional[dict]) -> ReviewResponse:
    base = ReviewResponse(
        id=str(review["_id"]),
        dataset_id=review["dataset_id"],
        product_name=review.get("product_name"),
        product_price=review.get("product_price"),
        review=review.get("review", ""),
        summary=review.get("summary"),
        processing_status=review.get("processing_status", "pending"),
        attempt_count=review.get("attempt_count", 0),
        error_message=review.get("error_message"),
        created_at=review["created_at"],
    )
    if result and result.get("status") == "completed":
        base.sentiment = result.get("sentiment")
        base.ai_sentiment_score = result.get("ai_sentiment_score")
        base.reason = result.get("reason")
        base.aspects = result.get("aspects", [])
        base.positive_points = result.get("positive_points", [])
        base.negative_points = result.get("negative_points", [])
        base.keywords = result.get("keywords", [])
        base.model_name = result.get("model_name")
        base.processing_time_ms = result.get("processing_time_ms")

        # Multi-model comparison data (written by the analysis worker).
        # Absent for datasets analysed before the multi-model upgrade.
        model_scores = result.get("model_scores")
        if model_scores:
            base.model_scores = model_scores
            base.model_sentiments = result.get("model_sentiments") or {}
            base.ensemble_score = result.get("ensemble_score")
            base.ensemble_sentiment = result.get("ensemble_sentiment")
            base.score_min = result.get("score_min")
            base.score_max = result.get("score_max")
            base.score_range = result.get("score_range")
            base.agreement_level = result.get("agreement_level")
            base.agreement_ratio = result.get("agreement_ratio")
            base.models_used = result.get("models_used") or []
            base.models_failed = result.get("models_failed") or []
            base.models_total = result.get("models_total")
    elif result and result.get("status") == "failed":
        base.models_failed = result.get("models_failed") or []
        base.models_total = result.get("models_total")
    return base


@router.get("/datasets/{dataset_id}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sentiment: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    db = get_db()

    # Verify dataset ownership
    dataset = await db.datasets.find_one(
        {"_id": ObjectId(dataset_id), "user_id": current_user["user_id"]}
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    # Build review query
    query: dict = {"dataset_id": dataset_id}
    if search:
        query["review"] = {"$regex": search, "$options": "i"}
    if product:
        query["product_name"] = {"$regex": product, "$options": "i"}
    if status_filter:
        query["processing_status"] = status_filter

    total = await db.reviews.count_documents(query)
    skip = (page - 1) * page_size
    cursor = db.reviews.find(query, skip=skip, limit=page_size, sort=[("_id", 1)])
    reviews = await cursor.to_list(length=page_size)

    # Fetch analysis results
    review_ids = [str(r["_id"]) for r in reviews]
    res_cursor = db.analysis_results.find({"review_id": {"$in": review_ids}})
    results = await res_cursor.to_list(length=len(review_ids))
    result_map = {r["review_id"]: r for r in results}

    # Apply score and sentiment filters (post-fetch, from result data)
    response_reviews = []
    for review in reviews:
        rid = str(review["_id"])
        result = result_map.get(rid)
        if sentiment and result and result.get("sentiment") != sentiment:
            continue
        if min_score is not None and result and result.get("ai_sentiment_score", -1) < min_score:
            continue
        if max_score is not None and result and result.get("ai_sentiment_score", 6) > max_score:
            continue
        response_reviews.append(_build_review_response(review, result))

    total_pages = max(1, (total + page_size - 1) // page_size)
    return ReviewListResponse(
        reviews=response_reviews,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    review = await _get_owned_review(db, review_id, current_user["user_id"])
    result = await db.analysis_results.find_one({"review_id": review_id})
    return _build_review_response(review, result)


@router.get("/reviews/{review_id}/model-analysis", response_model=ReviewModelAnalysisResponse)
async def get_review_model_analysis(
    review_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Every model's own analysis of one review, plus the ensemble score and the
    agreement level. Ownership is verified through the parent dataset.
    """
    db = get_db()
    review = await _get_owned_review(db, review_id, current_user["user_id"])
    payload = await comparison_service.get_review_model_analysis(review_id, review)
    return ReviewModelAnalysisResponse(**payload)


async def _get_owned_review(db, review_id: str, user_id: str) -> dict:
    """Fetch a review and verify the caller owns its dataset."""
    try:
        review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID.")

    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    try:
        dataset = await db.datasets.find_one(
            {"_id": ObjectId(review["dataset_id"]), "user_id": user_id}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dataset reference.")
    if not dataset:
        raise HTTPException(status_code=403, detail="Access denied.")
    return review
