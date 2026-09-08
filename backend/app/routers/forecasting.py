"""
Forecasting REST API router.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth.dependencies import get_current_user
from app.database.connection import get_db
from app.forecasting import forecasting_service as svc
from app.forecasting.sentiment_index import build_daily_sentiment_index, get_daily_sentiment
from app.schemas.forecasting import (
    DailySentimentRecord,
    ForecastRunDetail,
    ForecastRunSummary,
    JoinDatasetRequest,
    SalesDatasetMeta,
    SentimentBuildRequest,
    TrainRequest,
    ForecastMetrics,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecasting", tags=["forecasting"])


@router.post("/upload-sales", response_model=SalesDatasetMeta, status_code=status.HTTP_201_CREATED)
async def upload_sales(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a sales CSV file. Required columns: date, product_name, units_sold."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    db = get_db()
    try:
        meta = await svc.upload_sales_dataset(
            db, content, file.filename, str(current_user["_id"])
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return meta


@router.get("/sales-datasets", response_model=list[SalesDatasetMeta])
async def list_sales_datasets(current_user: dict = Depends(get_current_user)):
    """List all uploaded sales datasets for the current user."""
    db = get_db()
    return await svc.get_sales_datasets(db, str(current_user["_id"]))


@router.get("/products")
async def get_products(current_user: dict = Depends(get_current_user)):
    """Return products that appear in both reviews and sales data."""
    db = get_db()
    return await svc.get_products_with_both_data(db, str(current_user["_id"]))


@router.post("/build-sentiment-index", response_model=list[DailySentimentRecord])
async def build_sentiment_index(
    body: SentimentBuildRequest,
    current_user: dict = Depends(get_current_user),
):
    """Aggregate LLM sentiment scores into a daily index per product."""
    db = get_db()
    records = await build_daily_sentiment_index(
        db, body.review_dataset_id, body.product_name
    )
    if not records:
        raise HTTPException(
            status_code=404,
            detail=(
                "No reviews with 'review_date' found for this dataset. "
                "Make sure your reviews CSV includes a 'review_date' column and "
                "analysis has completed."
            ),
        )
    return records


@router.get("/sentiment-index/{review_dataset_id}/{product_name}", response_model=list[DailySentimentRecord])
async def get_sentiment_index(
    review_dataset_id: str,
    product_name: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve stored daily sentiment records for a product."""
    db = get_db()
    records = await get_daily_sentiment(db, review_dataset_id, product_name)
    if not records:
        raise HTTPException(status_code=404, detail="No sentiment index found. Run build-sentiment-index first.")
    return records


@router.post("/train", status_code=status.HTTP_201_CREATED)
async def train_models(
    body: TrainRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Train SARIMA and SARIMAX models for a product.
    Returns full run detail including metrics and forecasts.
    """
    db = get_db()
    try:
        run = await svc.run_training(
            db=db,
            sales_dataset_id=body.sales_dataset_id,
            review_dataset_id=body.review_dataset_id,
            product_name=body.product_name,
            user_id=str(current_user["_id"]),
            order=tuple(body.order),
            seasonal_order=tuple(body.seasonal_order),
            forecast_horizon=body.forecast_horizon,
            test_fraction=body.test_fraction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(f"Training failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Training failed: {exc}") from exc

    return run


@router.get("/runs", response_model=list[ForecastRunSummary])
async def list_runs(current_user: dict = Depends(get_current_user)):
    """List all forecasting runs for the current user."""
    db = get_db()
    docs = await svc.get_runs(db, str(current_user["_id"]))
    result = []
    for doc in docs:
        sarima_metrics = None
        if doc.get("sarima") and doc["sarima"].get("test_metrics"):
            sarima_metrics = ForecastMetrics(**doc["sarima"]["test_metrics"])
        sarimax_metrics = None
        if doc.get("sarimax") and doc["sarimax"].get("test_metrics"):
            sarimax_metrics = ForecastMetrics(**doc["sarimax"]["test_metrics"])
        result.append(ForecastRunSummary(
            run_id=doc["run_id"],
            product_name=doc["product_name"],
            created_at=doc["created_at"],
            has_sentiment=doc.get("has_sentiment", False),
            n_train=doc.get("n_train", 0),
            n_test=doc.get("n_test", 0),
            sarima_test_metrics=sarima_metrics,
            sarimax_test_metrics=sarimax_metrics,
        ))
    return result


@router.get("/runs/{run_id}")
async def get_run(run_id: str, current_user: dict = Depends(get_current_user)):
    """Get details of a single forecasting run."""
    db = get_db()
    run = await svc.get_run(db, run_id, str(current_user["_id"]))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
