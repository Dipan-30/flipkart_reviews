"""
Few-shot prompt template for sentiment analysis.
Uses structured JSON output format with 3 examples.
"""

SYSTEM_INSTRUCTION = """You are an expert e-commerce product review sentiment analysis system.

Your task is to analyze a product review and return ONLY a valid JSON object.

Rules:
- Return ONLY the JSON object. No markdown. No explanations. No text outside the JSON.
- The "sentiment" field must be exactly one of: "positive", "neutral", or "negative"
- The "ai_sentiment_score" is YOUR assessment of how positive/negative the review is, from 0.0 (very negative) to 5.0 (very positive). This is NOT the customer's star rating.
- Only include aspects that are clearly mentioned or strongly implied in the review.
- "positive_points" and "negative_points" should be concise bullet-style strings.
- "keywords" should be the most important 3-6 topic words from the review.

Required JSON structure:
{
  "sentiment": "positive|neutral|negative",
  "ai_sentiment_score": 0.0-5.0,
  "reason": "brief explanation of the sentiment",
  "aspects": [
    {"name": "aspect_name", "sentiment": "positive|neutral|negative", "score": 0.0-5.0}
  ],
  "positive_points": ["point 1", "point 2"],
  "negative_points": ["point 1", "point 2"],
  "keywords": ["keyword1", "keyword2", "keyword3"]
}"""


FEW_SHOT_EXAMPLES = """
--- EXAMPLES ---

EXAMPLE 1 (Positive Review):
Review: "The camera on this phone is absolutely phenomenal. Portrait mode produces stunning bokeh and low-light photography is impressive. Performance is buttery smooth with no lag whatsoever. Battery easily lasts a full day of heavy use. Best purchase I've made this year!"

Expected JSON:
{
  "sentiment": "positive",
  "ai_sentiment_score": 4.8,
  "reason": "The reviewer is highly satisfied with the camera, performance, and battery life. Very enthusiastic and positive language throughout.",
  "aspects": [
    {"name": "camera", "sentiment": "positive", "score": 5.0},
    {"name": "performance", "sentiment": "positive", "score": 4.9},
    {"name": "battery", "sentiment": "positive", "score": 4.5}
  ],
  "positive_points": ["Excellent camera with great portrait mode", "Smooth performance with no lag", "Long battery life lasting a full day"],
  "negative_points": [],
  "keywords": ["camera", "performance", "battery", "portrait", "low-light"]
}

EXAMPLE 2 (Negative Review):
Review: "Complete waste of money. The product stopped working after just 10 days. Build quality is terrible, feels flimsy and cheap. Customer service was unhelpful and refused to process my return. The display also has a dead pixel. Absolutely disgusted with this purchase."

Expected JSON:
{
  "sentiment": "negative",
  "ai_sentiment_score": 0.5,
  "reason": "The reviewer is extremely dissatisfied with product quality, durability, display, and customer service. Strong negative language used throughout.",
  "aspects": [
    {"name": "build quality", "sentiment": "negative", "score": 0.5},
    {"name": "display", "sentiment": "negative", "score": 0.8},
    {"name": "customer service", "sentiment": "negative", "score": 0.3}
  ],
  "positive_points": [],
  "negative_points": ["Product failed after only 10 days", "Poor build quality, feels cheap", "Unhelpful customer service", "Dead pixel on display"],
  "keywords": ["build quality", "customer service", "display", "durability", "return"]
}

EXAMPLE 3 (Mixed/Neutral Review):
Review: "The phone has a decent camera for daylight shots but really struggles in low light conditions. Battery life is mediocre at best, barely lasting a day. However the display is very bright and vivid which I appreciate. Performance is acceptable for basic tasks but gaming causes noticeable heating. Price seems reasonable for what you get."

Expected JSON:
{
  "sentiment": "neutral",
  "ai_sentiment_score": 2.7,
  "reason": "The review has both positives and negatives. Good display and acceptable price, but camera, battery, and heating are concerns. Overall balanced experience.",
  "aspects": [
    {"name": "camera", "sentiment": "neutral", "score": 2.5},
    {"name": "battery", "sentiment": "negative", "score": 1.8},
    {"name": "display", "sentiment": "positive", "score": 4.2},
    {"name": "performance", "sentiment": "neutral", "score": 2.8},
    {"name": "heating", "sentiment": "negative", "score": 1.5},
    {"name": "price/value", "sentiment": "positive", "score": 3.5}
  ],
  "positive_points": ["Vivid and bright display", "Reasonable price for the features"],
  "negative_points": ["Poor low-light camera performance", "Mediocre battery life", "Heating during gaming"],
  "keywords": ["camera", "battery", "display", "heating", "performance", "price"]
}

--- END EXAMPLES ---"""


CORRECTION_PROMPT_SUFFIX = """

IMPORTANT: Your previous response was not valid JSON. 
You MUST return ONLY the JSON object and nothing else.
Do not add any text before or after the JSON.
Do not use markdown code blocks.
Start your response with { and end with }"""


def build_analysis_prompt(
    review: str,
    product_name: str | None = None,
    product_price: str | None = None,
    summary: str | None = None,
) -> str:
    """Build the complete prompt for review analysis."""
    context_parts = []
    if product_name:
        context_parts.append(f"Product: {product_name}")
    if product_price:
        context_parts.append(f"Price: {product_price}")
    if summary:
        context_parts.append(f"Review Title/Summary: {summary}")

    context = "\n".join(context_parts)
    if context:
        context = f"\nContext:\n{context}\n"

    return f"""{SYSTEM_INSTRUCTION}

{FEW_SHOT_EXAMPLES}

--- NOW ANALYZE THIS REVIEW ---
{context}
Review: {review}

Return ONLY the JSON object:"""


def build_correction_prompt(
    review: str,
    product_name: str | None = None,
    product_price: str | None = None,
    summary: str | None = None,
) -> str:
    """Build a correction prompt when the first attempt failed."""
    base = build_analysis_prompt(review, product_name, product_price, summary)
    return base + CORRECTION_PROMPT_SUFFIX
