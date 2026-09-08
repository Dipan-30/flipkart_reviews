"""
Pydantic schemas for LLM response validation.
All LLM JSON output is validated through these models.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class AspectSentiment(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(..., ge=0.0, le=5.0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return v.strip().lower()


class LLMAnalysisResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    ai_sentiment_score: float = Field(..., ge=0.0, le=5.0)
    reason: str = Field(..., min_length=1, max_length=1000)
    aspects: list[AspectSentiment] = Field(default_factory=list)
    positive_points: list[str] = Field(default_factory=list)
    negative_points: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("ai_sentiment_score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return round(max(0.0, min(5.0, v)), 2)

    @field_validator("aspects")
    @classmethod
    def limit_aspects(cls, v: list) -> list:
        return v[:20]  # max 20 aspects

    @field_validator("keywords")
    @classmethod
    def limit_keywords(cls, v: list) -> list:
        return [str(k).strip() for k in v[:20] if str(k).strip()]

    @field_validator("positive_points", "negative_points")
    @classmethod
    def limit_points(cls, v: list) -> list:
        return [str(p).strip() for p in v[:10] if str(p).strip()]


class ModelAnalysisResult(BaseModel):
    """
    One model's attempt at analysing one review.

    On success the LLM fields are populated (validated by LLMAnalysisResult
    first); on failure they stay None and the error fields explain why. This is
    what lets a single model fail without failing the whole review.
    """

    model_config = {"protected_namespaces": ()}

    model_name: str
    status: Literal["completed", "failed", "unavailable"] = "completed"

    sentiment: Optional[Literal["positive", "neutral", "negative"]] = None
    ai_sentiment_score: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    reason: Optional[str] = None
    aspects: list[AspectSentiment] = Field(default_factory=list)
    positive_points: list[str] = Field(default_factory=list)
    negative_points: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    processing_time_ms: Optional[int] = None
    attempts: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_success(
        cls,
        model_name: str,
        result: LLMAnalysisResult,
        processing_time_ms: Optional[int] = None,
        attempts: Optional[int] = None,
    ) -> "ModelAnalysisResult":
        return cls(
            model_name=model_name,
            status="completed",
            processing_time_ms=processing_time_ms,
            attempts=attempts,
            **result.model_dump(),
        )

    @classmethod
    def from_failure(
        cls,
        model_name: str,
        error_type: str,
        error_message: str,
        status: Literal["failed", "unavailable"] = "failed",
        processing_time_ms: Optional[int] = None,
    ) -> "ModelAnalysisResult":
        return cls(
            model_name=model_name,
            status=status,
            error_type=error_type,
            error_message=error_message[:500],
            processing_time_ms=processing_time_ms,
        )

    @property
    def succeeded(self) -> bool:
        return self.status == "completed" and self.ai_sentiment_score is not None


class MultiModelAnalysis(BaseModel):
    """All model results for one review plus the derived ensemble metrics."""

    model_config = {"protected_namespaces": ()}

    model_results: list[ModelAnalysisResult] = Field(default_factory=list)

    ensemble_score: Optional[float] = None
    ensemble_sentiment: Optional[Literal["positive", "neutral", "negative"]] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    score_range: Optional[float] = None
    agreement_level: str = "unavailable"
    agreement_ratio: float = 0.0
    majority_sentiment: Optional[str] = None
    model_scores: dict[str, float] = Field(default_factory=dict)
    model_sentiments: dict[str, str] = Field(default_factory=dict)
    models_used: list[str] = Field(default_factory=list)
    models_failed: list[str] = Field(default_factory=list)
    models_total: int = 0
    success_count: int = 0
    failure_count: int = 0

    #: Merged result written to `analysis_results` for backward compatibility.
    consensus: Optional[dict] = None

    @property
    def any_success(self) -> bool:
        return self.success_count > 0
