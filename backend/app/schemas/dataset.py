"""Dataset schemas."""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class DatasetResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    total_reviews: int
    processed_reviews: int
    successful_reviews: int
    failed_reviews: int
    status: Literal["uploaded", "analyzing", "completed", "failed", "paused", "stopped", "cancelled"]
    has_ground_truth: bool
    original_columns: list[str]
    created_at: datetime
    completed_at: Optional[datetime] = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetResponse]
    total: int


class UploadResponse(BaseModel):
    dataset_id: str
    filename: str
    total_reviews: int
    columns_detected: dict[str, str]
    message: str


class AnalysisJobStartResponse(BaseModel):
    job_id: str
    dataset_id: str
    message: str
