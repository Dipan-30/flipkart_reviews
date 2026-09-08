"""Analytics router."""
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.schemas.analytics import AnalyticsResponse
from app.services.analytics_service import compute_analytics

router = APIRouter(tags=["analytics"])


@router.get("/datasets/{dataset_id}/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    dataset = await db.datasets.find_one(
        {"_id": ObjectId(dataset_id), "user_id": current_user["user_id"]}
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    return await compute_analytics(dataset_id)
