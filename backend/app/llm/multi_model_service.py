"""
Multi-model orchestration.

Sends the SAME review text to every configured Ollama model through the single
reusable OllamaLLMService, isolates per-model failures, and derives the
ensemble/agreement metrics via app.services.ensemble.

Design notes
------------
* One reusable service per model (no per-model subclasses).
* Model calls run under a semaphore (OLLAMA_MODEL_CONCURRENCY) so we never
  flood Ollama or force several large models to be resident at once.
* A model that times out, returns invalid JSON, or is not installed produces a
  `failed` / `unavailable` ModelAnalysisResult instead of raising — the review
  still succeeds as long as at least one model worked.
* Availability is checked once (cached) instead of per review, and a model that
  turns out to be missing mid-run is remembered so later reviews skip it fast.
"""
import asyncio
import logging
import time
from typing import Optional, Sequence

from app.config import get_settings
from app.llm.base import LLMService
from app.llm.errors import LLMHTTPError, classify_error
from app.llm.ollama_service import get_model_services, is_model_installed
from app.schemas.llm import ModelAnalysisResult, MultiModelAnalysis
from app.services import ensemble as ens

logger = logging.getLogger(__name__)


def _is_missing_model_error(exc: BaseException) -> bool:
    """Ollama answers 404 with 'model ... not found, try pulling it first'."""
    if not isinstance(exc, LLMHTTPError):
        return False
    text = str(exc).lower()
    return "404" in text or "not found" in text


class MultiModelAnalysisService:
    """Runs every configured model over one review and combines the results."""

    def __init__(
        self,
        services: Optional[Sequence[LLMService]] = None,
        model_concurrency: Optional[int] = None,
        primary_model: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.services: list[LLMService] = list(
            services if services is not None else get_model_services()
        )
        self.model_concurrency = max(1, model_concurrency or settings.ollama_model_concurrency)
        self.primary_model = primary_model or settings.primary_model
        self._semaphore = asyncio.Semaphore(self.model_concurrency)
        # model name -> installed?  (None = not checked yet)
        self._availability: dict[str, bool] = {}
        self._ollama_available: Optional[bool] = None

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #
    @property
    def models(self) -> list[str]:
        return [getattr(s, "model", "unknown") for s in self.services]

    async def refresh_availability(self, force: bool = False) -> dict:
        """
        Ask Ollama once which models are installed.

        Returns {"ollama_available", "installed", "models": {name: bool}, "error"}.
        Never raises: a dead Ollama simply reports everything unavailable.
        """
        if self._availability and not force:
            return {
                "ollama_available": bool(self._ollama_available),
                "installed": [],
                "models": dict(self._availability),
                "error": None,
            }
        if not self.services:
            self._ollama_available = False
            return {"ollama_available": False, "installed": [], "models": {}, "error": "No models configured"}

        probe = self.services[0]
        error: Optional[str] = None
        installed: list[str] = []
        try:
            ollama_up = await probe.check_availability()
            if ollama_up:
                installed = await probe.list_models()
            else:
                error = "Ollama is not reachable"
        except Exception as exc:  # defensive: status must never break a job
            ollama_up = False
            error = str(exc)

        self._ollama_available = ollama_up
        self._availability = {
            name: (is_model_installed(name, installed) if ollama_up else False)
            for name in self.models
        }
        missing = [name for name, ok in self._availability.items() if not ok]
        if missing:
            logger.warning(f"Configured models not installed in Ollama: {', '.join(missing)}")
        return {
            "ollama_available": ollama_up,
            "installed": installed,
            "models": dict(self._availability),
            "error": error,
        }

    def mark_unavailable(self, model_name: str) -> None:
        """Remember that a model is missing so later reviews skip it quickly."""
        if self._availability.get(model_name) is not False:
            logger.warning(f"Marking model '{model_name}' as unavailable for the rest of this run.")
        self._availability[model_name] = False

    def _known_unavailable(self, model_name: str) -> bool:
        return self._availability.get(model_name) is False

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #
    async def analyze_review(
        self,
        review: str,
        product_name: Optional[str] = None,
        product_price: Optional[str] = None,
        summary: Optional[str] = None,
        skip_unavailable: bool = True,
        review_id: Optional[str] = None,
        db: Optional[object] = None,
    ) -> MultiModelAnalysis:
        """
        Send the identical review to every configured model.

        The review text is never modified between models, which is what makes
        the score comparison meaningful.
        """
        if not self.services:
            return MultiModelAnalysis()

        tasks = [
            self._analyze_with_model(
                service=service,
                review=review,
                product_name=product_name,
                product_price=product_price,
                summary=summary,
                skip_unavailable=skip_unavailable,
                review_id=review_id,
                db=db,
            )
            for service in self.services
        ]
        model_results: list[ModelAnalysisResult] = await asyncio.gather(*tasks)
        return self.combine(model_results)

    def combine(self, model_results: list[ModelAnalysisResult]) -> MultiModelAnalysis:
        """Derive ensemble + agreement metrics from the per-model results."""
        payload = [r.model_dump() for r in model_results]
        summary = ens.summarize_model_results(payload, primary_model=self.primary_model)
        return MultiModelAnalysis(
            model_results=model_results,
            ensemble_score=summary["ensemble_score"],
            ensemble_sentiment=summary["ensemble_sentiment"],
            score_min=summary["score_min"],
            score_max=summary["score_max"],
            score_range=summary["score_range"],
            agreement_level=summary["agreement_level"],
            agreement_ratio=summary["agreement_ratio"],
            majority_sentiment=summary["majority_sentiment"],
            model_scores=summary["model_scores"],
            model_sentiments=summary["model_sentiments"],
            models_used=summary["models_used"],
            models_failed=[m for m in summary["models_failed"] if m],
            models_total=summary["models_total"],
            success_count=summary["success_count"],
            failure_count=summary["failure_count"],
            consensus=summary["consensus"],
        )

    async def _analyze_with_model(
        self,
        service: LLMService,
        review: str,
        product_name: Optional[str],
        product_price: Optional[str],
        summary: Optional[str],
        skip_unavailable: bool,
        review_id: Optional[str] = None,
        db: Optional[object] = None,
    ) -> ModelAnalysisResult:
        """Analyze with one model, converting any failure into a result row."""
        model_name = getattr(service, "model", "unknown")

        if skip_unavailable and self._known_unavailable(model_name):
            return ModelAnalysisResult.from_failure(
                model_name=model_name,
                error_type="model_unavailable",
                error_message=f"Model '{model_name}' is not installed in Ollama. Run: ollama pull {model_name}",
                status="unavailable",
            )

        # Check if already successfully analyzed for (review_id, model_name)
        if db is not None and review_id:
            try:
                existing = await db.model_analysis_results.find_one(
                    {"review_id": review_id, "model_name": model_name, "status": "completed"}
                )
                if existing:
                    logger.info(f"[{model_name}] Reusing cached result for review {review_id}")
                    from app.schemas.llm import AspectSentiment, LLMAnalysisResult
                    aspects = [AspectSentiment(**a) if isinstance(a, dict) else a for a in existing.get("aspects", [])]
                    res = LLMAnalysisResult(
                        sentiment=existing.get("sentiment", "neutral"),
                        ai_sentiment_score=existing.get("ai_sentiment_score", 3.0),
                        reason=existing.get("reason", ""),
                        aspects=aspects,
                        positive_points=existing.get("positive_points", []),
                        negative_points=existing.get("negative_points", []),
                        keywords=existing.get("keywords", []),
                    )
                    return ModelAnalysisResult.from_success(
                        model_name=model_name,
                        result=res,
                        processing_time_ms=existing.get("processing_time_ms", 0),
                        attempts=existing.get("attempts", 1),
                    )
            except Exception as exc:
                logger.warning(f"[{model_name}] Cache lookup failed for review {review_id}: {exc}")

        started = time.time()
        async with self._semaphore:
            try:
                result, meta = await service.analyze_review_with_meta(
                    review=review,
                    product_name=product_name,
                    product_price=product_price,
                    summary=summary,
                )
                return ModelAnalysisResult.from_success(
                    model_name=model_name,
                    result=result,
                    processing_time_ms=meta.get("elapsed_ms"),
                    attempts=meta.get("attempts"),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                elapsed = round((time.time() - started) * 1000)
                if _is_missing_model_error(exc):
                    self.mark_unavailable(model_name)
                    return ModelAnalysisResult.from_failure(
                        model_name=model_name,
                        error_type="model_unavailable",
                        error_message=(
                            f"Model '{model_name}' is not installed in Ollama. "
                            f"Run: ollama pull {model_name}"
                        ),
                        status="unavailable",
                        processing_time_ms=elapsed,
                    )
                error_type = classify_error(exc)
                logger.error(f"[{model_name}] analysis failed ({error_type}): {exc}")
                return ModelAnalysisResult.from_failure(
                    model_name=model_name,
                    error_type=error_type,
                    error_message=str(exc),
                    processing_time_ms=elapsed,
                )


# --------------------------------------------------------------------- #
# Accessor
# --------------------------------------------------------------------- #
_multi_service: Optional[MultiModelAnalysisService] = None


def get_multi_model_service() -> MultiModelAnalysisService:
    """Shared instance (keeps the availability cache warm across requests)."""
    global _multi_service
    if _multi_service is None:
        _multi_service = MultiModelAnalysisService()
    return _multi_service


def reset_multi_model_service() -> None:
    """Drop the shared instance (used by tests / config reloads)."""
    global _multi_service
    _multi_service = None
