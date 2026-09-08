"""Dataset management router."""
import asyncio
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database.connection import get_db
from app.schemas.dataset import (
    AnalysisJobStartResponse,
    DatasetListResponse,
    DatasetResponse,
    UploadResponse,
)
from app.services.dataset_service import (
    create_analysis_job,
    create_dataset_from_csv,
    delete_dataset,
    get_dataset,
    list_datasets,
)
from app.utils.csv_utils import validate_and_parse_csv
from app.workers.analysis_worker import run_analysis_job
from bson import ObjectId

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])


def _format_dataset(doc: dict) -> DatasetResponse:
    return DatasetResponse(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        filename=doc["filename"],
        total_reviews=doc["total_reviews"],
        processed_reviews=doc.get("processed_reviews", 0),
        successful_reviews=doc.get("successful_reviews", 0),
        failed_reviews=doc.get("failed_reviews", 0),
        status=doc.get("status", "uploaded"),
        has_ground_truth=doc.get("has_ground_truth", False),
        original_columns=doc.get("original_columns", []),
        created_at=doc["created_at"],
        completed_at=doc.get("completed_at"),
    )


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    settings = get_settings()
    file_bytes = await file.read()

    try:
        df, column_mapping = validate_and_parse_csv(
            file_bytes=file_bytes,
            filename=file.filename or "upload.csv",
            max_size_bytes=settings.max_file_size_bytes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_id = await create_dataset_from_csv(
        user_id=current_user["user_id"],
        filename=file.filename or "upload.csv",
        df=df,
        column_mapping=column_mapping,
    )

    return UploadResponse(
        dataset_id=dataset_id,
        filename=file.filename or "upload.csv",
        total_reviews=len(df),
        columns_detected=column_mapping,
        message=f"Successfully uploaded {len(df)} reviews.",
    )


@router.get("", response_model=DatasetListResponse)
async def list_user_datasets(current_user: dict = Depends(get_current_user)):
    docs = await list_datasets(current_user["user_id"])
    return DatasetListResponse(
        datasets=[_format_dataset(d) for d in docs],
        total=len(docs),
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset_detail(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    doc = await get_dataset(dataset_id, current_user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return _format_dataset(doc)


@router.delete("/{dataset_id}")
async def delete_dataset_endpoint(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    success = await delete_dataset(dataset_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {"message": "Dataset deleted successfully."}


@router.post("/{dataset_id}/analyze", response_model=AnalysisJobStartResponse)
async def start_analysis(
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    doc = await get_dataset(dataset_id, current_user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    # Check if there's already a running job
    existing_job = await db.analysis_jobs.find_one(
        {"dataset_id": dataset_id, "status": "running"}
    )
    if existing_job:
        raise HTTPException(status_code=409, detail="Analysis is already running for this dataset.")

    # Count pending/failed reviews
    pending_count = await db.reviews.count_documents(
        {"dataset_id": dataset_id, "processing_status": {"$in": ["pending", "failed"]}}
    )
    if pending_count == 0:
        raise HTTPException(status_code=400, detail="No pending reviews to analyze.")

    job_id = await create_analysis_job(dataset_id, current_user["user_id"], pending_count)

    # Launch background task (non-blocking)
    asyncio.create_task(run_analysis_job(job_id, dataset_id, current_user["user_id"]))

    logger.info(f"Analysis started | job={job_id} | dataset={dataset_id} | reviews={pending_count}")
    return AnalysisJobStartResponse(
        job_id=job_id,
        dataset_id=dataset_id,
        message=f"Analysis started for {pending_count} reviews.",
    )
