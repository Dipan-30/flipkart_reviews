"""Multi-model comparison schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScoreBucket(BaseModel):
    range: str
    count: int


class ModelStats(BaseModel):
    """Dataset level statistics for one model."""

    model_config = {"protected_namespaces": ()}

    model_name: str
    available: bool = True
    analyzed_reviews: int = 0
    failed_reviews: int = 0
    unavailable_reviews: int = 0
    average_score: float = 0.0
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    positive_pct: float = 0.0
    neutral_pct: float = 0.0
    negative_pct: float = 0.0
    avg_processing_time_ms: int = 0
    score_distribution: list[ScoreBucket] = Field(default_factory=list)
    error_types: dict[str, int] = Field(default_factory=dict)
    #: Mean agreement of this model with each of the other models (%)
    agreement_with_others_pct: Optional[float] = None
    # Enhanced metrics (Phase 2)
    avg_latency_ms: Optional[int] = None
    success_rate_pct: Optional[float] = None
    macro_f1: Optional[float] = None


class PairwiseAgreement(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_a: str
    model_b: str
    compared_reviews: int
    agreed_reviews: int
    agreement_pct: float


class AgreementSummary(BaseModel):
    total_reviews: int = 0
    high: int = 0
    moderate: int = 0
    low: int = 0
    single_model: int = 0
    unavailable: int = 0
    high_pct: float = 0.0
    moderate_pct: float = 0.0
    low_pct: float = 0.0
    agreement_index: float = 0.0


class ReviewScoreComparison(BaseModel):
    """Per-review score comparison used by the review-level comparison chart."""

    model_config = {"protected_namespaces": ()}

    review_id: str
    review_excerpt: str
    product_name: Optional[str] = None
    model_scores: dict[str, float] = Field(default_factory=dict)
    model_sentiments: dict[str, str] = Field(default_factory=dict)
    ensemble_score: Optional[float] = None
    ensemble_sentiment: Optional[str] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    score_range: Optional[float] = None
    agreement_level: str = "unavailable"
    agreement_ratio: float = 0.0
    models_failed: list[str] = Field(default_factory=list)


class SentimentSplit(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    positive_pct: float = 0.0
    neutral_pct: float = 0.0
    negative_pct: float = 0.0


class ModelComparisonResponse(BaseModel):
    """GET /api/datasets/{dataset_id}/model-comparison"""

    model_config = {"protected_namespaces": ()}

    dataset_id: str
    dataset_name: Optional[str] = None
    models_configured: list[str] = Field(default_factory=list)
    models_reporting: list[str] = Field(default_factory=list)
    models_missing: list[str] = Field(default_factory=list)
    multi_model: bool = False
    legacy_single_model: bool = False

    total_reviews: int = 0
    analyzed_reviews: int = 0

    ensemble_score: Optional[float] = None
    ensemble_sentiment: Optional[str] = None
    ensemble_split: SentimentSplit = Field(default_factory=SentimentSplit)
    ensemble_score_distribution: list[ScoreBucket] = Field(default_factory=list)

    model_stats: list[ModelStats] = Field(default_factory=list)
    pairwise_agreement: list[PairwiseAgreement] = Field(default_factory=list)
    agreement_summary: AgreementSummary = Field(default_factory=AgreementSummary)
    review_comparisons: list[ReviewScoreComparison] = Field(default_factory=list)
    review_comparisons_limit: int = 0

    generated_at: datetime


class ModelResultDetail(BaseModel):
    """One model's result for one review, including failure information."""

    model_config = {"protected_namespaces": ()}

    model_name: str
    status: str
    sentiment: Optional[str] = None
    ai_sentiment_score: Optional[float] = None
    reason: Optional[str] = None
    aspects: list[dict] = Field(default_factory=list)
    positive_points: list[str] = Field(default_factory=list)
    negative_points: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None
    attempts: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class ReviewModelAnalysisResponse(BaseModel):
    """GET /api/reviews/{review_id}/model-analysis"""

    model_config = {"protected_namespaces": ()}

    review_id: str
    dataset_id: str
    review: str
    product_name: Optional[str] = None
    processing_status: str

    model_results: list[ModelResultDetail] = Field(default_factory=list)
    models_configured: list[str] = Field(default_factory=list)
    models_missing: list[str] = Field(default_factory=list)

    ensemble_score: Optional[float] = None
    ensemble_sentiment: Optional[str] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    score_range: Optional[float] = None
    average_score: Optional[float] = None
    agreement_level: str = "unavailable"
    agreement_ratio: float = 0.0
    agreement_label: str = "Unavailable"
    success_count: int = 0
    failure_count: int = 0
    legacy_single_model: bool = False
