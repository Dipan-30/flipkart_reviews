"""
Flipkart AI Review Intelligence System — FastAPI Application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.connection import close_db, connect_db, get_db
from app.database.indexes import create_indexes
from app.routers import (
    analytics,
    auth,
    comparison,
    datasets,
    evaluation,
    health,
    jobs,
    ollama,
    reviews,
)
from app.routers import forecasting as forecasting_router
from app.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("=== Flipkart AI Review Intelligence System Starting ===")
    settings = get_settings()
    logger.info(f"Ollama URL: {settings.ollama_base_url}")
    logger.info(
        f"Configured LLM models ({len(settings.llm_models)}): {', '.join(settings.llm_models)}"
    )
    logger.info(f"Primary (reference) model: {settings.primary_model}")
    logger.info(
        f"Concurrency: {settings.ollama_concurrency} review(s) x "
        f"{settings.ollama_model_concurrency} model(s) | timeout={settings.ollama_timeout}s"
    )

    # Connect to MongoDB and create indexes
    await connect_db()
    db = get_db()
    await create_indexes(db)

    yield

    # Shutdown
    await close_db()
    logger.info("=== Application Shutdown ===")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Flipkart AI Review Intelligence System",
        description="AI-powered product review analysis using local Ollama LLM",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(datasets.router, prefix=api_prefix)
    app.include_router(jobs.router, prefix=api_prefix)
    app.include_router(reviews.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)
    app.include_router(comparison.router, prefix=api_prefix)
    app.include_router(evaluation.router, prefix=api_prefix)
    app.include_router(ollama.router, prefix=api_prefix)
    app.include_router(forecasting_router.router, prefix=api_prefix)

    return app


app = create_app()
