"""
LLM error types.

They subclass the builtin exceptions that the previous single-model
implementation raised (TimeoutError / ConnectionError / ValueError /
RuntimeError) so existing error handling keeps working, while adding a
machine-readable `error_type` used by the multi-model layer and the UI.
"""
from typing import Optional


class LLMError(Exception):
    """Base class for all LLM failures. Carries the model name and a type tag."""

    error_type: str = "error"

    def __init__(self, message: str, model: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.model = model


class LLMTimeoutError(LLMError, TimeoutError):
    error_type = "timeout"


class LLMConnectionError(LLMError, ConnectionError):
    error_type = "connection_error"


class LLMModelUnavailableError(LLMError, RuntimeError):
    error_type = "model_unavailable"


class LLMHTTPError(LLMError, RuntimeError):
    error_type = "http_error"


class LLMInvalidOutputError(LLMError, ValueError):
    error_type = "invalid_output"


def classify_error(exc: BaseException) -> str:
    """Map an exception to a stable error_type string."""
    if isinstance(exc, LLMError):
        return exc.error_type
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "connection_error"
    if isinstance(exc, ValueError):
        return "invalid_output"
    return "error"
