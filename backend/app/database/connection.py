"""
MongoDB connection management using Motor async driver.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    """Initialize MongoDB connection."""
    global _client
    settings = get_settings()
    logger.info("Connecting to MongoDB...")
    _client = AsyncIOMotorClient(settings.mongo_uri)
    # Verify connection
    await _client.admin.command("ping")
    logger.info("MongoDB connected successfully.")


async def close_db() -> None:
    """Close MongoDB connection."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """Return the database instance."""
    if _client is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    settings = get_settings()
    # Extract db name from URI or default
    db_name = settings.mongo_uri.rsplit("/", 1)[-1].split("?")[0] or "flipkart_reviews"
    return _client[db_name]
