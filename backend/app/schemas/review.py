"""Review schemas."""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
from app.schemas.llm import AspectSentiment


class ReviewResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    id: str
    dataset_id: str
    product_name: Optional[str] = None
    product_price: Optional[str] = None
    review: str
    summary: Optional[str] = None
    processing_status: Literal["pending", "processing", "completed", "failed"]
    attempt_count: int
    error_message: Optional[str] = None
    created_at: datetime

    # Analysis result fields (populated when completed)
    sentiment: Optional[str] = None
    ai_sentiment_score: Optional[float] = None
    reason: Optional[str] = None
    aspects: Optional[list[AspectSentiment]] = None
    positive_points: Optional[list[str]] = None
    negative_points: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    model_name: Optional[str] = None
    processing_time_ms: Optional[int] = None

    # Multi-model comparison (populated when several models analyzed the review).
    # All optional, so existing clients that ignore them keep working.
    model_scores: Optional[dict[str, float]] = None
    model_sentiments: Optional[dict[str, str]] = None
    ensemble_score: Optional[float] = None
    ensemble_sentiment: Optional[str] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    score_range: Optional[float] = None
    agreement_level: Optional[str] = None
    agreement_ratio: Optional[float] = None
    models_used: Optional[list[str]] = None
    models_failed: Optional[list[str]] = None
    models_total: Optional[int] = None


class ReviewListResponse(BaseModel):
    reviews: list[ReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class JobStatusResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    job_id: str
    dataset_id: str
    status: Literal["pending", "running", "completed", "failed", "paused", "stopped", "cancelled"]
    total: int
    processed: int
    successful: int
    failed: int
    progress_percent: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    # Multi-model progress (optional — absent for jobs created before the upgrade)
    models: Optional[list[str]] = None
    models_unavailable: Optional[list[str]] = None
    #: {model_name: {"success": n, "failed": n, "unavailable": n}}
    model_stats: Optional[dict[str, dict[str, int]]] = None
