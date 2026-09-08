"""Analytics schemas."""
from typing import Optional
from pydantic import BaseModel


class SentimentCount(BaseModel):
    positive: int
    neutral: int
    negative: int


class SentimentPercentage(BaseModel):
    positive: float
    neutral: float
    negative: float


class ScoreDistributionBucket(BaseModel):
    range: str
    count: int


class AspectAnalytics(BaseModel):
    name: str
    count: int
    avg_score: float
    sentiment: str  # overall dominant sentiment


class KeywordItem(BaseModel):
    keyword: str
    count: int
    sentiment: str


class ProductSentiment(BaseModel):
    product_name: str
    total_reviews: int
    avg_score: float
    positive_count: int
    neutral_count: int
    negative_count: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float


class AnalyticsResponse(BaseModel):
    dataset_id: str
    total_reviews: int
    completed_reviews: int
    sentiment_counts: SentimentCount
    sentiment_percentages: SentimentPercentage
    average_ai_score: float
    score_distribution: list[ScoreDistributionBucket]
    top_aspects: list[AspectAnalytics]
    top_positive_keywords: list[KeywordItem]
    top_negative_keywords: list[KeywordItem]
    products: list[ProductSentiment]
