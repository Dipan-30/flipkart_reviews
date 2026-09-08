"""
Safe JSON extraction utilities for parsing LLM output.
"""
import json
import re
import logging

logger = logging.getLogger(__name__)


def _as_dict(parsed) -> dict | None:
    """Only object payloads are usable; some models wrap the result in a list."""
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                return item
    return None


def safe_extract_json(text: str) -> dict | None:
    """
    Try multiple strategies to extract JSON from LLM output text.
    Returns parsed dict or None if extraction fails.
    """
    if not text or not text.strip():
        return None

    # Strategy 0: Drop reasoning blocks emitted by "thinking" models
    # (<think>...</think>) before looking for JSON.
    if "<think>" in text.lower():
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Strategy 1: Direct parse (LLM returned clean JSON)
    try:
        result = _as_dict(json.loads(text.strip()))
        if result is not None:
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown code fences (```json ... ```)
    stripped = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    stripped = stripped.replace("```", "").strip()
    try:
        result = _as_dict(json.loads(stripped))
        if result is not None:
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 3: Extract first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            result = _as_dict(json.loads(match.group()))
            if result is not None:
                return result
        except json.JSONDecodeError:
            pass

    # Strategy 4: Find JSON starting from first '{'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = _as_dict(json.loads(text[start : end + 1]))
            if result is not None:
                return result
        except json.JSONDecodeError:
            pass

    logger.warning("All JSON extraction strategies failed.")
    return None
