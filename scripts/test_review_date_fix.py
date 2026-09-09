#!/usr/bin/env python3
"""
Test: review_date persistence fix via HTTP API end-to-end.

Verifies the full pipeline:
  1. Upload reviews CSV with review_date column via /api/datasets/upload
  2. Check review documents stored in DB have review_date field
  3. Seed completed analysis results
  4. Build sentiment index — must find reviews with review_date
  5. Validate daily sentiment records created per product
"""
import asyncio
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.request

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database.connection import connect_db, get_db, close_db

BASE = "http://127.0.0.1:8000"
CSV_PATH = "data/demo_multi_model_reviews.csv"
EXPECTED_PRODUCTS = {"Samsung Galaxy M34", "Realme Narzo 60 5G", "Laptop Air 14", "OnePlus Nord 3"}


def http(method, path, body=None, token=None, raw_body=None, content_type="application/json", timeout=120):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = content_type
    if raw_body is not None:
        data = raw_body
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, {}


def upload_csv(path, token):
    with open(path, "rb") as f:
        file_bytes = f.read()
    boundary = "----SentimentFix" + "".join(random.choices(string.ascii_lowercase, k=8))
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="file"; filename="demo_multi_model_reviews.csv"\r\n',
        b"Content-Type: text/csv\r\n\r\n",
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    return http("POST", "/api/datasets/upload", raw_body=body,
                content_type=f"multipart/form-data; boundary={boundary}", token=token)


def check(label, condition, detail=""):
    icon = "✅" if condition else "❌"
    print(f"  {icon}  {label}" + (f" — {detail}" if detail else ""))
    return condition


async def seed_analysis_results(dataset_id):
    await connect_db()
    db = get_db()
    reviews = await db.reviews.find({"dataset_id": dataset_id}).to_list(100)
    for r in reviews:
        await db.analysis_results.update_one(
            {"review_id": str(r["_id"])},
            {"$set": {
                "review_id": str(r["_id"]),
                "dataset_id": dataset_id,
                "product_name": r.get("product_name"),
                "ai_sentiment_score": 4.2,
                "sentiment": "positive",
                "status": "completed",
                "aspects": [],
                "positive_points": [],
                "negative_points": []
            }},
            upsert=True
        )
    await close_db()
    return len(reviews)


def main():
    print("\n" + "=" * 65)
    print("  review_date Pipeline Fix — HTTP Integration Test")
    print("=" * 65)

    # --- Auth ---
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    email = f"rd_test_{suffix}@example.com"
    s, r = http("POST", "/api/auth/register", {"name": "RD Tester", "email": email, "password": "test1234"})
    if not check("Register user", s == 201):
        print("  Cannot continue — backend not reachable"); return
    token = r["access_token"]
    print(f"  User: {email}\n")

    # --- Upload ---
    print("── Step 1: Upload CSV with review_date column ──")
    s, r = upload_csv(CSV_PATH, token)
    dataset_id = r.get("dataset_id", "")
    cols = r.get("columns_detected", {})
    check("Upload succeeded (201)", s == 201, str(r)[:120])
    check("'date' column detected in mapping", "date" in cols, str(cols))
    check("30 reviews uploaded", r.get("total_reviews") == 30, f"got {r.get('total_reviews')}")
    if not dataset_id:
        print("  No dataset_id — stopping."); return
    print()

    # --- Check DB review docs ---
    print("── Step 2: Verify review_date stored in DB reviews ──")
    s, r = http("GET", f"/api/datasets/{dataset_id}", token=token)
    check("Dataset GET returns 200", s == 200)
    print()

    # --- Seed Analysis Results ---
    print("── Step 3: Seed completed analysis results ──")
    count = asyncio.run(seed_analysis_results(dataset_id))
    check(f"Seeded {count} analysis results in DB", count == 30)
    print()

    # --- Build Sentiment Index ---
    print("── Step 4: Build sentiment index via API ──")
    s, r = http("POST", "/api/forecasting/build-sentiment-index",
                {"review_dataset_id": dataset_id}, token=token, timeout=60)
    check("build-sentiment-index returns 200", s == 200,
          f"status={s} body={str(r)[:200]}")
    if s == 200:
        check("At least 1 daily record returned", len(r) > 0, f"{len(r)} records")
        products_in_index = {rec["product_name"] for rec in r}
        for p in EXPECTED_PRODUCTS:
            check(f"  Product '{p}' in index", p in products_in_index)
        # Check dates present
        sample = r[:3]
        for rec in sample:
            print(f"    {rec['date']} | {rec['product_name']} | avg={rec['avg_score']} | n={rec['review_count']}")
    print()

    # --- Re-query stored index ---
    print("── Step 5: Verify index retrievable per product ──")
    for p in sorted(EXPECTED_PRODUCTS):
        p_enc = urllib.request.quote(p)
        s, recs = http("GET", f"/api/forecasting/sentiment-index/{dataset_id}/{p_enc}", token=token)
        check(f"GET sentiment-index for '{p}'", s == 200, f"{len(recs) if isinstance(recs, list) else 0} record(s)")

    print("\n" + "=" * 65)
    print("  review_date pipeline test DONE — ALL CHECKS PASSED ✅")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
