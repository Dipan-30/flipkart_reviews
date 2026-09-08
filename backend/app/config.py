"""
Application configuration using pydantic-settings.
All values are loaded from environment variables / .env file.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017/flipkart_reviews"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    # Primary / legacy single-model setting. Kept for backward compatibility:
    # if OLLAMA_MODELS is empty the application runs with this model only.
    ollama_model: str = "gemma3:4b"
    # Comma separated list of models used for multi-model analysis,
    # e.g. "gemma3:4b,qwen2.5:7b,llama3.1:8b"
    ollama_models: str = ""
    # How many reviews are analyzed in parallel.
    ollama_concurrency: int = 1
    # How many models are queried in parallel for the SAME review.
    # Keep at 1 on machines with limited RAM/VRAM (Ollama then serves the
    # models one after another instead of loading all of them at once).
    ollama_model_concurrency: int = 1
    ollama_timeout: int = 120
    # Ask Ollama for strict JSON output (format="json"). Improves parsing
    # reliability across different models. Set to false to reproduce the
    # original prompt-only behaviour.
    ollama_force_json: bool = True

    # File upload
    max_file_size_mb: int = 20

    # CORS
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", os.path.join(os.path.dirname(__file__), "..", ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def llm_models(self) -> list[str]:
        """
        Ordered list of models used for analysis.

        Falls back to the single OLLAMA_MODEL value when OLLAMA_MODELS is not
        configured, so the application stays usable with only one model.
        Duplicates are removed while preserving the configured order.
        """
        raw = [m.strip() for m in (self.ollama_models or "").split(",")]
        models = [m for m in raw if m]
        if not models:
            models = [self.ollama_model.strip()] if self.ollama_model.strip() else []
        deduped: list[str] = []
        for m in models:
            if m not in deduped:
                deduped.append(m)
        return deduped

    @property
    def primary_model(self) -> str:
        """
        The reference model used for backward-compatible single-model fields.
        OLLAMA_MODEL wins when it is part of the configured list.
        """
        models = self.llm_models
        if self.ollama_model in models:
            return self.ollama_model
        return models[0] if models else self.ollama_model

    @property
    def is_multi_model(self) -> bool:
        return len(self.llm_models) > 1


@lru_cache()
def get_settings() -> Settings:
    return Settings()
