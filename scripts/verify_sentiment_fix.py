import asyncio
import os
import sys

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database.connection import connect_db, get_db, close_db
from app.services.dataset_service import create_dataset_from_csv
from app.utils.csv_utils import validate_and_parse_csv
from app.forecasting.sentiment_index import build_daily_sentiment_index
from bson import ObjectId

async def test_sentiment_pipeline():
    await connect_db()
    db = get_db()
    
    # 1. Parse dummy CSV using csv_utils
    sample_csv = """product_name,product_price,Review,review_date,Summary
Samsung Galaxy M34,16999,Great phone,2024-01-01,Great
Samsung Galaxy M34,16999,Poor camera,2024-01-01,Poor
Realme Narzo 60,14999,Awesome battery,2024-01-02,Awesome
"""
    content = sample_csv.encode("utf-8")
    df, col_map = validate_and_parse_csv(content, "test.csv", 50 * 1024 * 1024)
    print("Detected column mapping:", col_map)
    
    dataset_id = await create_dataset_from_csv(
        user_id="test_user_123",
        filename="test.csv",
        df=df,
        column_mapping=col_map,
    )
    print(f"Created Dataset ID: {dataset_id}")
    
    # 2. Verify MongoDB reviews documents have review_date field
    reviews = await db.reviews.find({"dataset_id": dataset_id}).to_list(10)
    print(f"Stored {len(reviews)} reviews.")
    for r in reviews:
        print("Review Doc keys:", list(r.keys()), "| review_date:", r.get("review_date"))
        assert r.get("review_date") is not None, f"review_date missing on review doc! doc={r}"
    
    # 3. Simulate analysis results in analysis_results collection
    for r in reviews:
        await db.analysis_results.insert_one({
            "review_id": str(r["_id"]),
            "dataset_id": dataset_id,
            "product_name": r.get("product_name"),
            "ai_sentiment_score": 4.5 if "Great" in r["review"] or "Awesome" in r["review"] else 1.5,
            "sentiment": "positive" if "Great" in r["review"] or "Awesome" in r["review"] else "negative",
            "status": "completed",
            "aspects": [],
            "positive_points": [],
            "negative_points": [],
            "created_at": "2024-01-01T00:00:00"
        })
    
    # 4. Call build_daily_sentiment_index
    res = await build_daily_sentiment_index(db, dataset_id)
    print(f"\nbuild_daily_sentiment_index returned {len(res)} daily records:")
    for item in res:
        print("  ", item)
    
    # 5. Verify stored sentiment_index documents in DB
    idx_docs = await db.daily_sentiment.find({"dataset_id": dataset_id}).to_list(10)
    print(f"DB daily_sentiment collection contains {len(idx_docs)} documents.")
    assert len(idx_docs) == len(res), "Stored daily_sentiment count does not match result!"
    
    # Clean up test data
    await db.datasets.delete_one({"_id": ObjectId(dataset_id)})
    await db.reviews.delete_many({"dataset_id": dataset_id})
    await db.analysis_results.delete_many({"dataset_id": dataset_id})
    await db.daily_sentiment.delete_many({"dataset_id": dataset_id})
    await close_db()
    print("\nCleanup complete. TEST PASSED SUCCESSFULLY! ✅")

if __name__ == "__main__":
    asyncio.run(test_sentiment_pipeline())
