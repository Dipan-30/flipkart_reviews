"""Evaluation router."""
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.services.evaluation_service import get_evaluation_result, run_evaluation

router = APIRouter(tags=["evaluation"])


@router.post("/datasets/{dataset_id}/evaluate")
async def trigger_evaluation(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    dataset = await db.datasets.find_one(
        {"_id": ObjectId(dataset_id), "user_id": current_user["user_id"]}
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    if not dataset.get("has_ground_truth"):
        raise HTTPException(
            status_code=400,
            detail="This dataset does not have ground truth labels. Upload a CSV with a 'Sentiment' column.",
        )

    result = await run_evaluation(dataset_id, current_user["user_id"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/datasets/{dataset_id}/evaluate")
async def get_evaluation(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    dataset = await db.datasets.find_one(
        {"_id": ObjectId(dataset_id), "user_id": current_user["user_id"]}
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    result = await get_evaluation_result(dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="No evaluation results found. Run evaluation first.")

    result["_id"] = str(result["_id"])
    return result
