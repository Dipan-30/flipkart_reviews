"""
Ollama LLM Service implementation.

Calls Ollama's local HTTP API. A single reusable class serves ALL configured
models — the model name is passed to the constructor:

    OllamaLLMService()                      # primary model from settings
    OllamaLLMService(model="qwen2.5:7b")    # any other Ollama model

Model instances are cached in a small registry (see get_llm_service /
get_model_services) so the same httpx settings and logging apply everywhere.
"""
import logging
import time
from typing import Optional

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.llm.base import LLMService
from app.llm.errors import (
    LLMConnectionError,
    LLMHTTPError,
    LLMInvalidOutputError,
    LLMTimeoutError,
)
from app.prompts.sentiment_prompt import build_analysis_prompt, build_correction_prompt
from app.schemas.llm import LLMAnalysisResult
from app.utils.json_utils import safe_extract_json

logger = logging.getLogger(__name__)


class OllamaLLMService(LLMService):
    """
    LLM service implementation using Ollama's local HTTP API.

    The default model comes from OLLAMA_MODEL, but any model name can be
    injected, which is how the multi-model orchestration layer runs several
    models through one implementation.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        force_json: Optional[bool] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.primary_model
        self.timeout = timeout or settings.ollama_timeout
        self.force_json = settings.ollama_force_json if force_json is None else force_json
        logger.info(f"OllamaLLMService initialized | model={self.model} | url={self.base_url}")

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #
    async def analyze_review(
        self,
        review: str,
        product_name: Optional[str] = None,
        product_price: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> LLMAnalysisResult:
        """
        Analyze a review using Ollama.
        Validates output with Pydantic.
        Retries once with correction prompt on invalid JSON.
        """
        result, _meta = await self.analyze_review_with_meta(
            review=review,
            product_name=product_name,
            product_price=product_price,
            summary=summary,
        )
        return result

    async def analyze_review_with_meta(
        self,
        review: str,
        product_name: Optional[str] = None,
        product_price: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> tuple[LLMAnalysisResult, dict]:
        """
        Same as analyze_review() but also returns metadata
        (model name, attempts made, elapsed milliseconds).
        """
        prompt = build_analysis_prompt(review, product_name, product_price, summary)
        start_time = time.time()

        # First attempt
        raw_response = await self._call_ollama(prompt)
        result = self._parse_and_validate(raw_response)

        if result is not None:
            elapsed = round((time.time() - start_time) * 1000)
            logger.info(
                f"[{self.model}] Review analyzed in {elapsed}ms | "
                f"sentiment={result.sentiment} | score={result.ai_sentiment_score}"
            )
            return result, {"model": self.model, "attempts": 1, "elapsed_ms": elapsed}

        # Retry with correction prompt
        logger.warning(f"[{self.model}] First attempt failed validation, retrying with correction prompt...")
        correction_prompt = build_correction_prompt(review, product_name, product_price, summary)
        raw_response2 = await self._call_ollama(correction_prompt)
        result2 = self._parse_and_validate(raw_response2)

        if result2 is not None:
            elapsed = round((time.time() - start_time) * 1000)
            logger.info(f"[{self.model}] Retry succeeded in {elapsed}ms | sentiment={result2.sentiment}")
            return result2, {"model": self.model, "attempts": 2, "elapsed_ms": elapsed}

        # Both attempts failed
        elapsed = round((time.time() - start_time) * 1000)
        snippet = raw_response2[:200] if raw_response2 else "empty"
        logger.error(f"[{self.model}] Both LLM attempts failed after {elapsed}ms. Raw response: {snippet}")
        raise LLMInvalidOutputError(
            f"LLM returned invalid JSON after 2 attempts. Last response: {snippet}",
            model=self.model,
        )

    def _parse_and_validate(self, raw: Optional[str]) -> Optional[LLMAnalysisResult]:
        """Extract JSON and validate with Pydantic. Returns None on failure."""
        if not raw:
            return None
        data = safe_extract_json(raw)
        if data is None:
            logger.warning(f"[{self.model}] JSON extraction failed.")
            return None
        try:
            return LLMAnalysisResult.model_validate(data)
        except ValidationError as e:
            logger.warning(f"[{self.model}] Pydantic validation failed: {e}")
            return None

    async def _call_ollama(self, prompt: str, force_json: Optional[bool] = None) -> Optional[str]:
        """Make HTTP call to Ollama generate endpoint."""
        url = f"{self.base_url}/api/generate"
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.1,   # Low temperature for consistent structured output
                "top_p": 0.9,
                "num_predict": 300,   # Capped output token limit for faster inference
            },
        }
        want_json = self.force_json if force_json is None else force_json
        if want_json:
            # Ollama constrains sampling to valid JSON. Greatly reduces parse
            # failures, especially for models other than gemma3.
            payload["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.TimeoutException:
            logger.error(f"[{self.model}] Ollama request timed out after {self.timeout}s")
            raise LLMTimeoutError(
                f"Ollama request for model '{self.model}' timed out after {self.timeout} seconds.",
                model=self.model,
            )
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama service.")
            raise LLMConnectionError(
                "Local Ollama service is not running. Please start Ollama and try again.",
                model=self.model,
            )
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.text[:200]
            except Exception:
                pass
            logger.error(f"[{self.model}] Ollama HTTP error: {e.response.status_code} {detail}")
            raise LLMHTTPError(
                f"Ollama API error for model '{self.model}': {e.response.status_code}. {detail}".strip(),
                model=self.model,
            )

    # ------------------------------------------------------------------ #
    # Free-form generation
    # ------------------------------------------------------------------ #
    async def generate(self, prompt: str, force_json: bool = False) -> str:
        """
        Plain text completion.

        Used only for optional natural-language phrasing (e.g. the
        recommendation narrative). It never influences any score or label.
        """
        response = await self._call_ollama(prompt, force_json=force_json)
        return (response or "").strip()

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #
    async def check_availability(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List installed Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def check_model_available(self, model_name: str) -> bool:
        """Check if a specific model is installed in Ollama."""
        models = await self.list_models()
        return is_model_installed(model_name, models)


def is_model_installed(model_name: str, installed: list[str]) -> bool:
    """
    Decide whether `model_name` is present in the list returned by
    Ollama's /api/tags.

    Matching rules (pure function, unit tested):
      - exact match                    gemma3:4b   == gemma3:4b
      - implicit :latest tag           gemma3      ~= gemma3:latest
      - untagged config name           gemma3      ~= gemma3:4b
    A configured tag is never matched against a different tag, so
    'gemma3:4b' does NOT report available when only 'gemma3:12b' is installed.
    """
    if not model_name:
        return False
    wanted = model_name.strip()
    if not wanted:
        return False
    for installed_name in installed:
        name = (installed_name or "").strip()
        if not name:
            continue
        if name == wanted:
            return True
        if ":" not in wanted:
            # Untagged config: accept any tag of the same family.
            if name == f"{wanted}:latest" or name.split(":")[0] == wanted:
                return True
    return False


# --------------------------------------------------------------------- #
# Service registry
# --------------------------------------------------------------------- #
_services: dict[str, OllamaLLMService] = {}


def get_llm_service(model: Optional[str] = None) -> LLMService:
    """
    Dependency injection for LLM service.

    Called without arguments it returns the primary model service, which keeps
    every existing call site working exactly as before.
    """
    settings = get_settings()
    key = model or settings.primary_model
    if key not in _services:
        _services[key] = OllamaLLMService(model=key)
    return _services[key]


def get_model_services() -> list[OllamaLLMService]:
    """Return one service instance per configured model, in configured order."""
    settings = get_settings()
    return [get_llm_service(m) for m in settings.llm_models]  # type: ignore[misc]


def reset_service_registry() -> None:
    """Drop cached service instances (used by tests)."""
    _services.clear()
