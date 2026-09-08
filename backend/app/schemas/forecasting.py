"""Pydantic schemas for the Sales Forecasting API."""
from typing import Optional
from pydantic import BaseModel, Field


class ForecastMetrics(BaseModel):
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    n_test_samples: int = 0


class ModelForecastResult(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str
    order: list[int]
    seasonal_order: list[int]
    train_metrics: ForecastMetrics
    test_metrics: ForecastMetrics
    test_predictions: list[float] = Field(default_factory=list)
    forecast: list[float] = Field(default_factory=list)
    fitted_values: list[float] = Field(default_factory=list)


class SalesDatasetMeta(BaseModel):
    sales_dataset_id: str
    filename: str
    user_id: str
    total_rows: int
    products: list[str] = Field(default_factory=list)
    date_range_start: str
    date_range_end: str
    created_at: str


class SentimentBuildRequest(BaseModel):
    review_dataset_id: str
    product_name: Optional[str] = None


class JoinDatasetRequest(BaseModel):
    sales_dataset_id: str
    review_dataset_id: str
    product_name: str


class TrainRequest(BaseModel):
    sales_dataset_id: str
    review_dataset_id: str
    product_name: str
    order: list[int] = Field(default=[1, 1, 1])
    seasonal_order: list[int] = Field(default=[0, 0, 0, 0])
    forecast_horizon: int = Field(default=30, ge=1, le=365)
    test_fraction: float = Field(default=0.2, ge=0.05, le=0.5)


class ForecastRunSummary(BaseModel):
    run_id: str
    product_name: str
    created_at: str
    has_sentiment: bool = False
    n_train: int = 0
    n_test: int = 0
    sarima_test_metrics: Optional[ForecastMetrics] = None
    sarimax_test_metrics: Optional[ForecastMetrics] = None


class ForecastRunDetail(BaseModel):
    run_id: str
    sales_dataset_id: str
    review_dataset_id: str
    product_name: str
    order: list[int]
    seasonal_order: list[int]
    forecast_horizon: int
    test_fraction: float
    n_train: int
    n_test: int
    has_sentiment: bool
    sarima: Optional[ModelForecastResult] = None
    sarimax: Optional[ModelForecastResult] = None
    actual_dates: list[str] = Field(default_factory=list)
    actual_values: list[float] = Field(default_factory=list)
    train_dates: list[str] = Field(default_factory=list)
    test_dates: list[str] = Field(default_factory=list)
    test_actual_values: list[float] = Field(default_factory=list)
    future_dates: list[str] = Field(default_factory=list)
    created_at: str


class DailySentimentRecord(BaseModel):
    date: str
    product_name: str
    avg_score: float
    review_count: int
