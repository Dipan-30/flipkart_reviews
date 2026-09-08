#!/usr/bin/env python3
"""
Mock Ollama server — a TEST DOUBLE for the real Ollama daemon.

Purpose
-------
Lets you exercise the whole multi-model pipeline (upload -> analyze -> compare ->
recommend -> evaluate) on a machine that cannot run three real LLMs, and lets you
deliberately reproduce the failure modes required by the spec: a model that is
not installed, a model that times out, a model that returns unparsable output.

IMPORTANT
---------
The scores this server returns come from a crude keyword heuristic, NOT from a
language model. They are only useful for verifying plumbing. Never point a real
demo, screenshot or report at this server — run real models instead:

    ollama pull gemma3:4b && ollama pull qwen2.5:7b && ollama pull llama3.1:8b

Usage
-----
    # installed: gemma3:4b, qwen2.5:7b   ->   llama3.1:8b answers 404
    python scripts/mock_ollama.py --port 11435 --models gemma3:4b,qwen2.5:7b

    # all three installed, one of them always times out
    python scripts/mock_ollama.py --port 11435 \
        --models gemma3:4b,qwen2.5:7b,llama3.1:8b --timeout-models llama3.1:8b

Then start the backend against it:

    OLLAMA_BASE_URL=http://localhost:11435 uvicorn app.main:app --reload

Implements only what app/llm/ollama_service.py calls: GET /api/tags and
POST /api/generate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

POSITIVE_WORDS = {
    "amazing", "awesome", "best", "brilliant", "clear", "crisp", "excellent",
    "exceptional", "fantastic", "good", "great", "happy", "impressive", "love",
    "loved", "nice", "perfect", "phenomenal", "premium", "recommend", "reliable",
    "satisfied", "smooth", "solid", "stunning", "superb", "vivid", "worth",
}
NEGATIVE_WORDS = {
    "awful", "bad", "broke", "broken", "cheap", "defective", "disappointed",
    "disappointing", "disgusted", "drains", "faulty", "flimsy", "heating",
    "heats", "horrible", "lags", "overpriced", "poor", "refund", "return",
    "regret", "slow", "terrible", "unhelpful", "useless", "waste", "worst",
}
ASPECT_WORDS = {
    "camera": ("camera", "photo", "photos", "photography", "lens"),
    "battery": ("battery", "charge", "charging", "backup"),
    "display": ("display", "screen", "brightness"),
    "performance": ("performance", "lag", "lags", "gaming", "speed", "smooth"),
    "build quality": ("build", "quality", "flimsy", "sturdy", "plastic"),
    "sound quality": ("sound", "audio", "bass", "speaker", "speakers"),
    "price": ("price", "priced", "value", "money", "overpriced"),
}
REVIEW_MARKER = "--- NOW ANALYZE THIS REVIEW ---"


def extract_review(prompt: str) -> str:
    """Pull the review out of the backend's prompt template."""
    tail = prompt.rsplit(REVIEW_MARKER, 1)[-1]
    match = re.search(r"Review:\s*(.+?)\s*Return ONLY the JSON object", tail, re.S)
    if match:
        return match.group(1).strip()
    return tail.strip()


def model_offset(model: str) -> float:
    """Small, stable per-model bias so the three models do not agree exactly."""
    total = sum(ord(c) for c in model)
    return round(((total % 7) - 3) * 0.1, 2)          # -0.3 .. +0.3


def heuristic_analysis(review: str, model: str) -> dict:
    words = re.findall(r"[a-z']+", review.lower())
    positives = [w for w in words if w in POSITIVE_WORDS]
    negatives = [w for w in words if w in NEGATIVE_WORDS]
    hits = len(positives) + len(negatives)

    if hits == 0:
        score = 3.0
    else:
        score = 1.0 + 4.0 * (len(positives) / hits)
    score = max(0.0, min(5.0, round(score + model_offset(model), 2)))
    sentiment = "positive" if score >= 3.5 else "neutral" if score >= 2.0 else "negative"

    aspects = []
    for name, triggers in ASPECT_WORDS.items():
        if not any(t in words for t in triggers):
            continue
        window = " ".join(words)
        near_negative = any(n in window for n in NEGATIVE_WORDS) and name in ("battery", "performance")
        aspect_score = max(0.0, min(5.0, round(score - 0.6 if near_negative else score + 0.2, 2)))
        aspects.append({
            "name": name,
            "sentiment": "positive" if aspect_score >= 3.5 else "neutral" if aspect_score >= 2.0 else "negative",
            "score": aspect_score,
        })

    return {
        "sentiment": sentiment,
        "ai_sentiment_score": score,
        "reason": f"[mock:{model}] {len(positives)} positive and {len(negatives)} negative cues detected.",
        "aspects": aspects[:5],
        "positive_points": sorted(set(positives))[:4],
        "negative_points": sorted(set(negatives))[:4],
        "keywords": [a["name"] for a in aspects][:6] or sorted(set(words))[:4],
    }


class MockOllamaHandler(BaseHTTPRequestHandler):
    server_version = "MockOllama/1.0"
    config: argparse.Namespace                      # set on the server class

    # ---------------------------------------------------------------- #
    def log_message(self, fmt, *args):
        if self.config.verbose:
            sys.stderr.write("mock-ollama: " + fmt % args + "\n")

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------------------------------------------------------------- #
    def do_GET(self):                                # noqa: N802
        if self.path.rstrip("/") in ("/api/tags", "/api/ps"):
            self._send_json(200, {
                "models": [
                    {"name": name, "model": name, "size": 0, "digest": "mock"}
                    for name in self.config.models
                ]
            })
            return
        if self.path.rstrip("/") == "":
            self._send_text(200, "Ollama is running (mock)")
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):                               # noqa: N802
        if self.path.rstrip("/") != "/api/generate":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid request body"})
            return

        model = payload.get("model") or ""
        prompt = payload.get("prompt") or ""

        # 1. model not installed -> exactly what real Ollama answers
        if model not in self.config.models:
            self._send_text(
                404, f"model '{model}' not found, try pulling it first"
            )
            return

        # 2. deliberate timeout (client gives up first)
        if model in self.config.timeout_models:
            time.sleep(self.config.timeout_seconds)
            self._send_json(200, {"model": model, "response": "{}", "done": True})
            return

        # 3. deliberate server error
        if model in self.config.error_models:
            self._send_text(500, "mock server error")
            return

        if self.config.delay:
            time.sleep(self.config.delay)

        # 4. deliberate unparsable output
        if model in self.config.bad_json_models:
            self._send_json(200, {
                "model": model,
                "response": "Sure! Here is my analysis: the review seems fine.",
                "done": True,
            })
            return

        analysis = heuristic_analysis(extract_review(prompt), model)
        self._send_json(200, {
            "model": model,
            "response": json.dumps(analysis),
            "done": True,
            "eval_count": 128,
        })


def _split(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("Usage")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--models", default="gemma3:4b,qwen2.5:7b,llama3.1:8b",
                        help="comma separated list of INSTALLED models; anything else returns 404")
    parser.add_argument("--timeout-models", default="", help="models that never answer in time")
    parser.add_argument("--error-models", default="", help="models that answer HTTP 500")
    parser.add_argument("--bad-json-models", default="", help="models that answer unparsable text")
    parser.add_argument("--timeout-seconds", type=float, default=180.0,
                        help="how long --timeout-models stall (must exceed OLLAMA_TIMEOUT)")
    parser.add_argument("--delay", type=float, default=0.0, help="artificial latency per request")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    args.models = _split(args.models)
    args.timeout_models = set(_split(args.timeout_models))
    args.error_models = set(_split(args.error_models))
    args.bad_json_models = set(_split(args.bad_json_models))

    MockOllamaHandler.config = args
    server = ThreadingHTTPServer((args.host, args.port), MockOllamaHandler)

    print("=" * 72)
    print("MOCK OLLAMA — TEST DOUBLE. Scores come from a keyword heuristic,")
    print("not from a language model. Use real models for anything that matters.")
    print("=" * 72)
    print(f"listening on   http://{args.host}:{args.port}")
    print(f"installed      {', '.join(args.models) or '(none)'}")
    if args.timeout_models:
        print(f"will time out  {', '.join(sorted(args.timeout_models))}")
    if args.error_models:
        print(f"will 500       {', '.join(sorted(args.error_models))}")
    if args.bad_json_models:
        print(f"bad JSON       {', '.join(sorted(args.bad_json_models))}")
    print("point the backend at it with OLLAMA_BASE_URL=http://"
          f"{args.host}:{args.port}\nCtrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
