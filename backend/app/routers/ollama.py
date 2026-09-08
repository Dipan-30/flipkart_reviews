"""Ollama status and model endpoints."""
import logging

from fastapi import APIRouter

from app.config import get_settings
from app.llm.multi_model_service import get_multi_model_service
from app.llm.ollama_service import get_llm_service, is_model_installed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ollama", tags=["ollama"])


@router.get("/status")
async def ollama_status():
    """
    Ollama connectivity plus the availability of EVERY configured model.

    Response shape (the first three keys are unchanged so existing clients
    keep working; `models` is the new per-model detail):

        {
          "available": true,                 # Ollama reachable
          "model": "gemma3:4b",              # primary model (legacy field)
          "model_available": true,           # primary model installed
          "base_url": "...",
          "models": [
            {"name": "gemma3:4b", "available": true,  "primary": true,  "pull_command": null},
            {"name": "qwen2.5:7b", "available": false, "primary": false,
             "pull_command": "ollama pull qwen2.5:7b"}
          ],
          "models_available": 1,
          "models_configured": 2,
          "installed_models": [...],
          "error": null
        }

    Models are never downloaded automatically — the install command is only
    reported so the user can run it themselves.
    """
    settings = get_settings()
    llm = get_llm_service()
    configured = list(settings.llm_models)
    primary = settings.primary_model

    available = await llm.check_availability()
    if not available:
        return {
            "available": False,
            "model": primary,
            "model_available": False,
            "base_url": settings.ollama_base_url,
            "models": [
                {
                    "name": name,
                    "available": False,
                    "primary": name == primary,
                    "pull_command": f"ollama pull {name}",
                }
                for name in configured
            ],
            "models_available": 0,
            "models_configured": len(configured),
            "installed_models": [],
            "error": "Local Ollama service is not running. Please start Ollama and try again.",
        }

    installed = await llm.list_models()
    models = [
        {
            "name": name,
            "available": is_model_installed(name, installed),
            "primary": name == primary,
        }
        for name in configured
    ]
    for model in models:
        model["pull_command"] = None if model["available"] else f"ollama pull {model['name']}"

    missing = [m["name"] for m in models if not m["available"]]
    primary_available = next((m["available"] for m in models if m["primary"]), False)

    if missing:
        error = "Model(s) not installed: " + ", ".join(missing) + ". Run: " + "; ".join(
            f"ollama pull {name}" for name in missing
        )
    else:
        error = None

    # Keep the shared orchestrator's availability cache in sync with what the
    # settings page just reported.
    try:
        await get_multi_model_service().refresh_availability(force=True)
    except Exception as exc:
        logger.debug(f"Could not refresh multi-model availability cache: {exc}")

    return {
        "available": True,
        "model": primary,
        "model_available": primary_available,
        "base_url": settings.ollama_base_url,
        "models": models,
        "models_available": len(models) - len(missing),
        "models_configured": len(configured),
        "installed_models": installed,
        "concurrency": {
            "reviews": settings.ollama_concurrency,
            "models_per_review": settings.ollama_model_concurrency,
            "timeout_seconds": settings.ollama_timeout,
        },
        "error": error,
    }


@router.get("/models")
async def list_models():
    """List all installed Ollama models."""
    llm = get_llm_service()
    models = await llm.list_models()
    settings = get_settings()
    return {
        "models": models,
        "configured": list(settings.llm_models),
        "primary": settings.primary_model,
    }
