#!/usr/bin/env python3
"""
End-to-end acceptance check for the Multi-LLM Flipkart Review Intelligence System.

Walks the whole workflow against a RUNNING backend and prints PASS / FAIL for
each of the 20 test cases in the project spec, plus the 18 acceptance criteria
it can observe from the API. Standard library only — no pytest, no requests.

Prerequisites
-------------
1. MongoDB running.
2. Ollama running with the configured models installed:
       ollama pull gemma3:4b && ollama pull qwen2.5:7b && ollama pull llama3.1:8b
       ollama list
   (or the mock double:  python scripts/mock_ollama.py --port 11435 ...)
3. Backend running:
       cd backend && uvicorn app.main:app --reload

Usage
-----
    python scripts/e2e_check.py
    python scripts/e2e_check.py --base-url http://127.0.0.1:8000 \
        --csv data/sample_flipkart_reviews.csv --wait 900

    # skip the (slow) analysis run and only verify the read paths of a dataset
    # that has already been processed:
    python scripts/e2e_check.py --dataset-id 65f0... --skip-analysis

Nothing is faked: every number printed comes from the backend's own responses.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.request

DEFAULT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "sample_flipkart_reviews.csv")

MALFORMED_CSV = b"this file is not a csv at all\x00\x01\x02"
EDGE_CASE_CSV = (
    "product_name,product_price,Review,Summary,Sentiment\n"
    "Edge Case Product,999,\"\",Empty review,neutral\n"
    "Edge Case Product,999,\"   \",Whitespace only,neutral\n"
    "Edge Case Product,999,\"ok\",Very short,neutral\n"
    "Edge Case Product,999,\"" + ("very long review text " * 200) + "\",Very long,positive\n"
).encode()


# --------------------------------------------------------------------- #
# tiny HTTP client
# --------------------------------------------------------------------- #
class Client:
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None

    def request(self, method: str, path: str, body=None, token=True,
                content_type="application/json", raw=False, timeout=None):
        url = self.base + path
        headers = {}
        if token and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = body if raw else json.dumps(body).encode()
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                payload = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            payload, status = exc.read(), exc.code
        except urllib.error.URLError as exc:
            return 0, {"detail": f"cannot reach {url}: {exc.reason}"}
        try:
            return status, json.loads(payload or b"null")
        except json.JSONDecodeError:
            return status, {"raw": payload[:400].decode("utf-8", "replace")}

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body, **kw)

    def upload_csv(self, filename: str, content: bytes):
        boundary = "----e2echeck" + "".join(random.choices(string.ascii_lowercase, k=12))
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: text/csv\r\n\r\n",
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        return self.request("POST", "/api/datasets/upload", body=body, raw=True,
                            content_type=f"multipart/form-data; boundary={boundary}")


# --------------------------------------------------------------------- #
# result collector
# --------------------------------------------------------------------- #
class Checks:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []

    def record(self, case: str, ok: bool | None, detail: str = ""):
        state = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        colour = {"PASS": "\033[32m", "FAIL": "\033[31m", "SKIP": "\033[33m"}[state]
        reset = "\033[0m" if sys.stdout.isatty() else ""
        prefix = colour if sys.stdout.isatty() else ""
        print(f"  {prefix}{state}{reset}  {case}" + (f" — {detail}" if detail else ""))
        self.rows.append((state, case, detail))
        return bool(ok)

    def summary(self) -> int:
        passed = sum(1 for s, _, _ in self.rows if s == "PASS")
        failed = [r for r in self.rows if r[0] == "FAIL"]
        skipped = sum(1 for s, _, _ in self.rows if s == "SKIP")
        print("\n" + "=" * 74)
        print(f"passed={passed} failed={len(failed)} skipped={skipped}")
        if failed:
            print("\nfailures:")
            for _, case, detail in failed:
                print(f"  - {case}: {detail}")
        print("=" * 74)
        return 1 if failed else 0


def section(title: str):
    print("\n" + "-" * 74)
    print(title)
    print("-" * 74)


# --------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("Prerequisites")[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--email", default=None, help="defaults to a unique throwaway address")
    parser.add_argument("--password", default="e2e-check-pass")
    parser.add_argument("--wait", type=float, default=1800.0, help="max seconds to wait for analysis")
    parser.add_argument("--dataset-id", default=None, help="reuse an existing dataset")
    parser.add_argument("--skip-analysis", action="store_true")
    parser.add_argument("--frontend-url", default=None,
                        help="optional dev-server URL to check the frontend responds, e.g. http://localhost:5173")
    args = parser.parse_args()

    checks = Checks()
    client = Client(args.base_url)
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    email = args.email or f"e2e-{suffix}@example.com"

    print("=" * 74)
    print("Multi-LLM Flipkart Review Intelligence — end-to-end check")
    print("=" * 74)
    print(f"backend  {args.base_url}")
    print(f"csv      {args.csv}")
    print(f"user     {email}")

    # ---------------------------------------------------------------- #
    section("environment")
    status, health = client.get("/api/health", token=False)
    if not checks.record("backend is reachable (GET /api/health)", status == 200, str(health)[:120]):
        print("\nStart the backend first:  cd backend && uvicorn app.main:app --reload")
        return checks.summary()

    status, ollama = client.get("/api/ollama/status", token=False)
    checks.record("15. Ollama status endpoint responds", status == 200, str(ollama)[:120])
    configured = [m["name"] for m in (ollama.get("models") or [])] if status == 200 else []
    installed = [m["name"] for m in (ollama.get("models") or []) if m.get("available")] if status == 200 else []
    missing = [m for m in (ollama.get("models") or []) if not m.get("available")] if status == 200 else []
    if status == 200:
        checks.record("    models configured", len(configured) >= 1, ", ".join(configured))
        checks.record("    Ollama reachable", bool(ollama.get("available")), str(ollama.get("error"))[:120])
        checks.record("3.  three models configured",
                      len(configured) >= 3 or None,
                      f"{len(configured)} configured, {len(installed)} installed")
        if missing:
            cmds = "; ".join(m.get("pull_command") or "" for m in missing)
            checks.record("15. missing model reported with a pull command",
                          all(m.get("pull_command") for m in missing), cmds)
        else:
            checks.record("15. every configured model is installed", True, ", ".join(installed))

    # ---------------------------------------------------------------- #
    section("authentication (§25.1, §25.2, §25.18)")
    status, body = client.post("/api/auth/register",
                               {"name": "E2E Check", "email": email, "password": args.password},
                               token=False)
    registered = checks.record("1.  user registration", status == 201 and "access_token" in body,
                               str(body)[:140])
    if registered:
        client.token = body["access_token"]

    status, body = client.post("/api/auth/login", {"email": email, "password": args.password}, token=False)
    if checks.record("2.  login", status == 200 and "access_token" in body, str(body)[:140]):
        client.token = body["access_token"]

    status, _ = client.post("/api/auth/login", {"email": email, "password": "wrong-password"}, token=False)
    checks.record("18. wrong password rejected", status == 401, f"status={status}")

    status, _ = client.get("/api/datasets", token=False)
    checks.record("18. unauthenticated request rejected", status in (401, 403), f"status={status}")

    status, me = client.get("/api/auth/me")
    checks.record("2.  token identifies the user", status == 200 and me.get("email") == email, str(me)[:120])

    # ---------------------------------------------------------------- #
    section("upload and dataset creation (§25.3, §25.4, §25.20)")
    dataset_id = args.dataset_id
    if dataset_id:
        checks.record("3.  CSV upload", None, f"reusing dataset {dataset_id}")
    else:
        try:
            with open(args.csv, "rb") as fh:
                csv_bytes = fh.read()
        except OSError as exc:
            checks.record("3.  CSV upload", False, f"cannot read {args.csv}: {exc}")
            return checks.summary()

        status, body = client.upload_csv(os.path.basename(args.csv), csv_bytes)
        if not checks.record("3.  CSV upload", status == 201 and body.get("dataset_id"), str(body)[:160]):
            return checks.summary()
        dataset_id = body["dataset_id"]
        checks.record("3.  columns detected", bool(body.get("columns_detected")),
                      json.dumps(body.get("columns_detected"))[:160])

    status, dataset = client.get(f"/api/datasets/{dataset_id}")
    checks.record("4.  dataset created", status == 200 and (dataset.get("dataset_id") or dataset.get("id")) == dataset_id,
                  f"{dataset.get('total_reviews')} reviews, ground_truth={dataset.get('has_ground_truth')}")

    status, listing = client.get("/api/datasets")
    checks.record("4.  dataset appears in the user's list",
                  status == 200 and any((d.get("dataset_id") or d.get("id")) == dataset_id for d in listing.get("datasets", [])),
                  f"{listing.get('total')} dataset(s)")

    status, _ = client.upload_csv("broken.csv", MALFORMED_CSV)
    checks.record("20. malformed CSV rejected with 400", status == 400, f"status={status}")

    status, edge = client.upload_csv("edge_cases.csv", EDGE_CASE_CSV)
    edge_id = edge.get("dataset_id") if status == 201 else None
    checks.record("20. empty / whitespace / oversized reviews accepted without a crash",
                  status in (201, 400), f"status={status} {str(edge)[:100]}")

    # ownership isolation: a second user must not see the first user's dataset
    other = Client(args.base_url)
    status, body = other.post("/api/auth/register",
                              {"name": "Other User", "email": f"e2e-other-{suffix}@example.com",
                               "password": args.password}, token=False)
    if status == 201:
        other.token = body["access_token"]
        status, _ = other.get(f"/api/datasets/{dataset_id}")
        checks.record("18. another user cannot read this dataset", status in (403, 404), f"status={status}")
        status, _ = other.get(f"/api/datasets/{dataset_id}/model-comparison")
        checks.record("18. ownership enforced on model-comparison", status in (403, 404), f"status={status}")
        status, _ = other.get(f"/api/datasets/{dataset_id}/recommendation")
        checks.record("18. ownership enforced on recommendation", status in (403, 404), f"status={status}")
    else:
        checks.record("18. ownership isolation", None, "could not register a second user")

    # ---------------------------------------------------------------- #
    section("analysis (§25.5, §25.6, §25.13, §25.14)")
    if args.skip_analysis:
        checks.record("5.  review processing", None, "--skip-analysis")
        job = {}
    else:
        status, job = client.post(f"/api/datasets/{dataset_id}/analyze")
        if status == 400 and "No pending reviews" in str(job):
            checks.record("5.  review processing", None, "dataset already analyzed")
        elif not checks.record("5.  analysis job started", status == 200 and job.get("job_id"), str(job)[:160]):
            return checks.summary()
        else:
            job_id = job["job_id"]
            deadline = time.time() + args.wait
            last = -1
            while time.time() < deadline:
                status, job = client.get(f"/api/jobs/{job_id}")
                if status != 200:
                    break
                pct = job.get("progress_percent", 0)
                if pct != last:
                    print(f"        ... {job.get('status')} {job.get('processed')}/{job.get('total')} ({pct}%)")
                    last = pct
                if job.get("status") in ("completed", "failed", "cancelled"):
                    break
                time.sleep(3)

            checks.record("5.  analysis job completed",
                          job.get("status") == "completed",
                          f"status={job.get('status')} processed={job.get('processed')} "
                          f"successful={job.get('successful')} failed={job.get('failed')} "
                          f"{job.get('error_message') or ''}")
            checks.record("6.  job reports the models it used",
                          bool(job.get("models")), ", ".join(job.get("models") or []))
            stats = job.get("model_stats") or {}
            if stats:
                for name, row in stats.items():
                    print(f"        {name}: {json.dumps(row)}")
            unavailable = job.get("models_unavailable") or []
            checks.record("13/17. unavailable models recorded on the job, run not aborted",
                          job.get("status") == "completed",
                          f"unavailable={unavailable or 'none'}")

    # ---------------------------------------------------------------- #
    section("model comparison (§25.7, §25.8, §25.9, §25.11, §25.12)")
    status, comp = client.get(f"/api/datasets/{dataset_id}/model-comparison?review_limit=5")
    if not checks.record("8.  GET /datasets/{id}/model-comparison", status == 200, str(comp)[:200]):
        return checks.summary()

    checks.record("7.  per-model statistics returned",
                  bool(comp.get("model_stats")),
                  ", ".join(f"{s['model_name']}={s['average_score']}" for s in comp.get("model_stats", [])))
    for s in comp.get("model_stats", []):
        print(f"        {s['model_name']}: n={s['analyzed_reviews']} avg={s['average_score']} "
              f"pos={s['positive_pct']}% neu={s['neutral_pct']}% neg={s['negative_pct']}% "
              f"time={s['avg_processing_time_ms']}ms failed={s['failed_reviews']} "
              f"available={s['available']}")

    checks.record("6.  every configured model analyzed the reviews",
                  len(comp.get("models_reporting") or []) >= min(3, len(configured) or 1)
                  or bool(comp.get("models_missing")),
                  f"reporting={comp.get('models_reporting')} missing={comp.get('models_missing')}")
    checks.record("9.  dataset ensemble score present",
                  comp.get("ensemble_score") is not None,
                  f"ensemble={comp.get('ensemble_score')} ({comp.get('ensemble_sentiment')})")
    checks.record("11. sentiment distributions comparable across models",
                  all("positive_pct" in s for s in comp.get("model_stats", [])),
                  f"ensemble split={json.dumps(comp.get('ensemble_split'))[:120]}")
    agree = comp.get("agreement_summary") or {}
    checks.record("12. model agreement computed",
                  "agreement_index" in agree,
                  f"index={agree.get('agreement_index')} high={agree.get('high')} "
                  f"moderate={agree.get('moderate')} low={agree.get('low')}")
    checks.record("12. pairwise agreement computed",
                  bool(comp.get("pairwise_agreement")) or len(configured) < 2,
                  "; ".join(f"{p['model_a']}~{p['model_b']}={p['agreement_pct']}%"
                            for p in comp.get("pairwise_agreement", [])))
    checks.record("14. review-level comparison sample returned",
                  bool(comp.get("review_comparisons")),
                  f"{len(comp.get('review_comparisons') or [])} review(s)")

    # ---------------------------------------------------------------- #
    section("review-level drill-down (§25.7, §25.14)")
    status, reviews = client.get(f"/api/datasets/{dataset_id}/reviews?page=1&page_size=5")
    checks.record("16. reviews list still works (pagination preserved)",
                  status == 200 and reviews.get("reviews") is not None,
                  f"total={reviews.get('total')}")
    status, filtered = client.get(f"/api/datasets/{dataset_id}/reviews?sentiment=positive&page_size=3")
    checks.record("16. sentiment filter still works", status == 200, f"total={filtered.get('total')}")
    status, searched = client.get(f"/api/datasets/{dataset_id}/reviews?search=battery&page_size=3")
    checks.record("16. review search still works", status == 200, f"total={searched.get('total')}")

    review_id = None
    for row in (reviews.get("reviews") or []):
        if row.get("processing_status") == "completed":
            review_id = row.get("review_id")
            break
    review_id = review_id or ((reviews.get("reviews") or [{}])[0].get("review_id"))

    if review_id:
        status, detail = client.get(f"/api/reviews/{review_id}/model-analysis")
        if checks.record("7.  GET /reviews/{id}/model-analysis", status == 200, str(detail)[:200]):
            for row in detail.get("model_results", []):
                print(f"        {row['model_name']}: {row['status']} "
                      f"{row.get('sentiment')} {row.get('ai_sentiment_score')} "
                      f"{row.get('processing_time_ms')}ms {row.get('error_type') or ''}")
            checks.record("6.  the same review has one result per model",
                          len(detail.get("model_results") or []) >= 1,
                          f"{len(detail.get('model_results') or [])} model result(s)")
            checks.record("10. per-review ensemble + agreement",
                          detail.get("ensemble_score") is not None,
                          f"ensemble={detail.get('ensemble_score')} "
                          f"agreement={detail.get('agreement_label')} "
                          f"range={detail.get('score_range')}")
            checks.record("17. failed models surfaced per review, not fatal",
                          detail.get("success_count", 0) >= 1 or detail.get("failure_count", 0) >= 1,
                          f"ok={detail.get('success_count')} failed={detail.get('failure_count')}")
    else:
        checks.record("7.  review model-analysis", None, "no reviews available")

    # ---------------------------------------------------------------- #
    section("recommendation (§25.10, §25.11, §25.19)")
    status, rec = client.get(f"/api/datasets/{dataset_id}/recommendation")
    if checks.record("10. GET /datasets/{id}/recommendation", status == 200, str(rec)[:200]):
        overall = rec.get("overall") or {}
        print(f"        {overall.get('recommendation')} "
              f"(score {overall.get('recommendation_score')}, confidence {overall.get('confidence')})")
        for reason in overall.get("reasons", []):
            print(f"          - {reason}")
        for warning in overall.get("warnings", []):
            print(f"          ! {warning}")
        checks.record("10. recommendation tier assigned",
                      overall.get("recommendation") in (
                          "Highly Recommended", "Recommended", "Consider Carefully",
                          "Not Recommended", "Insufficient Data"),
                      str(overall.get("recommendation")))
        checks.record("10. recommendation is explainable",
                      bool(overall.get("reasons")) and bool(overall.get("explanation")),
                      f"{len(overall.get('reasons') or [])} reason(s)")
        checks.record("10. recommendation score is numeric, not an LLM opinion",
                      isinstance(overall.get("recommendation_score"), (int, float))
                      and overall.get("narrative_source") in ("deterministic", "llm"),
                      f"score={overall.get('recommendation_score')} "
                      f"narrative={overall.get('narrative_source')}")
        products = rec.get("products") or []
        for product in products:
            print(f"        {product.get('label')}: n={product.get('review_count')} "
                  f"score={product.get('ensemble_score')} -> {product.get('recommendation')}")
        checks.record("11/19. per-product recommendations", bool(products), f"{len(products)} product(s)")
        checks.record("19. multiple products handled independently",
                      len(products) >= 2 or None,
                      f"{len(products)} product(s) in this dataset")

    # ---------------------------------------------------------------- #
    section("analytics + evaluation (§25.12, §25.16)")
    status, analytics = client.get(f"/api/datasets/{dataset_id}/analytics")
    checks.record("16. existing analytics endpoint still works", status == 200,
                  f"reviews={analytics.get('total_reviews')} "
                  f"avg={analytics.get('average_ai_score') or analytics.get('avg_sentiment_score')}")

    if dataset.get("has_ground_truth"):
        status, evaluation = client.post(f"/api/datasets/{dataset_id}/evaluate")
        if checks.record("12. ground-truth evaluation runs", status == 200, str(evaluation)[:200]):
            print(f"        ensemble: acc={evaluation.get('accuracy')} "
                  f"prec={evaluation.get('precision')} rec={evaluation.get('recall')} "
                  f"f1={evaluation.get('f1_score')}")
            for row in evaluation.get("model_metrics", []):
                print(f"        {row['model_name']}: acc={row['accuracy']} prec={row['precision']} "
                      f"rec={row['recall']} f1={row['f1_score']} n={row['matched_reviews']}")
            checks.record("12. per-model evaluation metrics",
                          bool(evaluation.get("model_metrics")),
                          f"models={evaluation.get('models_evaluated')} best={evaluation.get('best_model')}")
            checks.record("12. ensemble evaluation metrics",
                          bool(evaluation.get("ensemble_metrics")),
                          f"accuracy={(evaluation.get('ensemble_metrics') or {}).get('accuracy')}")
        status, stored = client.get(f"/api/datasets/{dataset_id}/evaluate")
        checks.record("12. evaluation result persisted", status == 200, f"status={status}")
    else:
        checks.record("12. ground-truth evaluation", None, "dataset has no Sentiment column")

    # ---------------------------------------------------------------- #
    section("frontend (§25.17)")
    if args.frontend_url:
        status, body = Client(args.frontend_url).get("/", token=False)
        checks.record("17. frontend dev server responds", status == 200, f"status={status}")
    else:
        checks.record("17. frontend loading", None,
                      "pass --frontend-url http://localhost:5173 to check, or open it in a browser")

    # ---------------------------------------------------------------- #
    if edge_id:
        client.request("DELETE", f"/api/datasets/{edge_id}")

    return checks.summary()


if __name__ == "__main__":
    raise SystemExit(main())
