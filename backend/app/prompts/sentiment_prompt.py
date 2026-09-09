"""
Few-shot prompt template for sentiment analysis.
Uses structured JSON output format with a compact example.
"""

SYSTEM_INSTRUCTION = """Analyze the product review. Return ONLY valid JSON (no markdown).

Fields:
- sentiment: "positive" | "neutral" | "negative"
- ai_sentiment_score: float 0.0 (very negative) to 5.0 (very positive)
- reason: brief explanation
- aspects: [{"name": str, "sentiment": str, "score": float}]
- positive_points: brief pros
- negative_points: brief cons
- keywords: 3-5 topic words"""

FEW_SHOT_EXAMPLES = """Example:
Review: "Great camera quality and smooth performance. Battery life is okay."
JSON:
{"sentiment":"positive","ai_sentiment_score":4.2,"reason":"Strong camera and performance; battery average.","aspects":[{"name":"camera","sentiment":"positive","score":4.8},{"name":"battery","sentiment":"neutral","score":3.0}],"positive_points":["Great camera","Smooth performance"],"negative_points":[],"keywords":["camera","performance","battery"]}"""

CORRECTION_PROMPT_SUFFIX = "\nReturn ONLY valid raw JSON starting with { and ending with }."


def build_analysis_prompt(
    review: str,
    product_name: str | None = None,
    product_price: str | None = None,
    summary: str | None = None,
) -> str:
    """Build prompt for review sentiment analysis.

    Only review text and optional product name are sent to the LLM.
    Price, summary, and ground-truth labels are intentionally omitted.
    """
    context = f"Product: {product_name}\n" if product_name else ""

    return f"""{SYSTEM_INSTRUCTION}

{FEW_SHOT_EXAMPLES}

Review:
{context}{review}

JSON:"""


def build_correction_prompt(
    review: str,
    product_name: str | None = None,
    product_price: str | None = None,
    summary: str | None = None,
) -> str:
    """Build correction prompt when first attempt failed."""
    return build_analysis_prompt(review, product_name, product_price, summary) + CORRECTION_PROMPT_SUFFIX
