"""
Abstract base class for LLM services.
All LLM providers must implement this interface.
"""
import time
from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.llm import LLMAnalysisResult


class LLMService(ABC):
    """Abstract interface for LLM analysis services."""

    #: Name of the model this service instance talks to.
    model: str = "unknown"

    @abstractmethod
    async def analyze_review(
        self,
        review: str,
        product_name: Optional[str] = None,
        product_price: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> LLMAnalysisResult:
        """
        Analyze a review and return structured sentiment analysis.
        Never sends Rate or existing Sentiment labels to the model.
        """
        ...

    async def analyze_review_with_meta(
        self,
        review: str,
        product_name: Optional[str] = None,
        product_price: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> tuple[LLMAnalysisResult, dict]:
        """
        Analyze a review and additionally return metadata
        ({"model", "attempts", "elapsed_ms"}).

        Providers may override this with a cheaper implementation; the default
        simply wraps analyze_review() so every LLMService supports it.
        """
        start = time.time()
        result = await self.analyze_review(review, product_name, product_price, summary)
        return result, {
            "model": getattr(self, "model", "unknown"),
            "attempts": 1,
            "elapsed_ms": round((time.time() - start) * 1000),
        }

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the LLM service is available."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List available models."""
        ...

    @abstractmethod
    async def check_model_available(self, model_name: str) -> bool:
        """Check if a specific model is installed."""
        ...
