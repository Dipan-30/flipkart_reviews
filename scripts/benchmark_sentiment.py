#!/usr/bin/env python3
"""Benchmark LLM sentiment analysis on N reviews (default 10)."""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
import time

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.llm.ollama_service import OllamaLLMService, close_all_services, reset_service_registry


def load_reviews(csv_path: str, limit: int) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows


async def run_benchmark(limit: int, csv_path: str) -> dict:
    reset_service_registry()
    service = OllamaLLMService()
    reviews = load_reviews(csv_path, limit)

    latencies: list[int] = []
    successes = 0
    failures = 0
    retries = 0

    start = time.time()
    for i, row in enumerate(reviews, 1):
        review_text = row.get("Review") or row.get("review") or ""
        product_name = row.get("product_name")
        t0 = time.time()
        try:
            result, meta = await service.analyze_review_with_meta(
                review=review_text,
                product_name=product_name,
            )
            elapsed = meta.get("elapsed_ms") or round((time.time() - t0) * 1000)
            latencies.append(elapsed)
            attempts = meta.get("attempts", 1)
            if attempts > 1:
                retries += attempts - 1
            successes += 1
            print(
                f"  [{i}/{limit}] OK sentiment={result.sentiment} "
                f"score={result.ai_sentiment_score} latency={elapsed}ms attempts={attempts}"
            )
        except Exception as exc:
            failures += 1
            print(f"  [{i}/{limit}] FAIL {exc}")

    total_ms = round((time.time() - start) * 1000)
    await close_all_services()

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    total_min = total_ms / 60000
    rpm = (successes / total_min) if total_min > 0 else 0

    return {
        "total_reviews": limit,
        "llm_calls": successes + failures,
        "successful": successes,
        "failed": failures,
        "retries": retries,
        "avg_llm_latency_ms": round(avg_latency, 1),
        "total_time_ms": total_ms,
        "reviews_per_minute": round(rpm, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--csv",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "demo_multi_model_reviews.csv",
        ),
    )
    args = parser.parse_args()

    stats = asyncio.run(run_benchmark(args.limit, args.csv))
    print("\n--- Benchmark Results ---")
    for k, v in stats.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
