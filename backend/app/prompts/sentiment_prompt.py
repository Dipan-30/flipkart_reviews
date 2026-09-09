"""
Few-shot prompt template for sentiment analysis.
Uses structured JSON output format with 3 examples.
"""

SYSTEM_INSTRUCTION = """Analyze the product review and return ONLY a valid JSON object.

Rules:
- Return ONLY JSON. No markdown formatting.
- "sentiment": "positive", "neutral", or "negative"
- "ai_sentiment_score": float from 0.0 (very negative) to 5.0 (very positive)
- "reason": brief explanation
- "aspects": [{"name": str, "sentiment": str, "score": float}]
- "positive_points": list of brief pros
- "negative_points": list of brief cons
- "keywords": 3-5 key topic words

Required JSON format:
{
  "sentiment": "positive|neutral|negative",
  "ai_sentiment_score": 4.5,
  "reason": "brief reason",
  "aspects": [{"name": "camera", "sentiment": "positive", "score": 4.8}],
  "positive_points": ["Great camera"],
  "negative_points": [],
  "keywords": ["camera", "display"]
}"""

FEW_SHOT_EXAMPLES = """EXAMPLE:
Review: "Great camera quality and smooth performance. Battery life is okay."
JSON:
{
  "sentiment": "positive",
  "ai_sentiment_score": 4.2,
  "reason": "Very good camera and performance, acceptable battery.",
  "aspects": [{"name": "camera", "sentiment": "positive", "score": 4.8}, {"name": "battery", "sentiment": "neutral", "score": 3.0}],
  "positive_points": ["Great camera quality", "Smooth performance"],
  "negative_points": [],
  "keywords": ["camera", "performance", "battery"]
}"""

CORRECTION_PROMPT_SUFFIX = """

IMPORTANT: Return ONLY valid raw JSON starting with { and ending with }."""


def build_analysis_prompt(
    review: str,
    product_name: str | None = None,
    product_price: str | None = None,
    summary: str | None = None,
) -> str:
    """Build prompt for review sentiment analysis."""
    context_parts = []
    if product_name:
        context_parts.append(f"Product: {product_name}")
    if product_price:
        context_parts.append(f"Price: {product_price}")
    if summary:
        context_parts.append(f"Summary: {summary}")

    context = ("\n".join(context_parts) + "\n") if context_parts else ""

    return f"""{SYSTEM_INSTRUCTION}

{FEW_SHOT_EXAMPLES}

Review to analyze:
{context}Review: {review}

JSON:"""


def build_correction_prompt(
    review: str,
    product_name: str | None = None,
    product_price: str | None = None,
    summary: str | None = None,
) -> str:
    """Build correction prompt when first attempt failed."""
    base = build_analysis_prompt(review, product_name, product_price, summary)
    return base + CORRECTION_PROMPT_SUFFIX
