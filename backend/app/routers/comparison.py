"""
Multi-model comparison and product recommendation router.

Both endpoints reuse the project's existing authentication dependency and the
same dataset ownership check as the other dataset routes, so a user can never
read another user's dataset.
"""
import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.schemas.comparison import ModelComparisonResponse
from app.services import comparison_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["comparison"])


async def _get_owned_dataset(dataset_id: str, user_id: str) -> dict:
    db = get_db()
    try:
        dataset = await db.datasets.find_one(
            {"_id": ObjectId(dataset_id), "user_id": user_id}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dataset ID.")
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


@router.get("/datasets/{dataset_id}/model-comparison", response_model=ModelComparisonResponse)
async def get_model_comparison(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
    review_limit: int = Query(30, ge=1, le=200, description="Reviews in the per-review chart"),
):
    """Per-model statistics, agreement metrics and ensemble numbers for a dataset."""
    dataset = await _get_owned_dataset(dataset_id, current_user["user_id"])
    payload = await comparison_service.get_model_comparison(
        dataset_id, dataset=dataset, review_limit=review_limit
    )
    return ModelComparisonResponse(**payload)

