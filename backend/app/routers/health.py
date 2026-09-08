"""Health check router."""
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Flipkart AI Review Intelligence System",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
