# Multi-LLM Sentiment Comparison and Product Recommendation

This document describes the multi-model upgrade to the Flipkart AI Review Intelligence System:
what was added, how to configure and run it, how the numbers are calculated, and what the
known limitations are. The original single-model (Ollama + Gemma 3 4B) behaviour is preserved
throughout — a dataset analysed before the upgrade still opens, and a deployment configured
with a single model still works.

## What changed, in one paragraph

Every review is now sent, unchanged, to each configured Ollama model. Each model produces the
same structured JSON the project always used, validated by the same Pydantic schema, and each
result is stored as its own document instead of overwriting the previous one. On top of the
per-model results the backend computes an ensemble score (the mean of the model scores), a
model-agreement metric, dataset- and product-level statistics, per-model evaluation metrics
against the existing ground truth, and a deterministic, explainable product recommendation.
The frontend gained a Multi-Model Comparison page, a recommendation card on the dataset and
product pages, a per-review model comparison table, per-model evaluation columns, and per-model
availability in the Ollama status panel.

## Models

Three models are configured by default, all served by the existing Ollama installation:
`gemma3:4b` (the original primary model, kept as the reference/consensus model), `qwen2.5:7b`
and `llama3.1:8b`. They were chosen because they are different model families from three
different labs — Google, Alibaba and Meta — so their disagreements are meaningful rather than
being three checkpoints of the same base model, and because all three fit the ~4B/8B class the
brief asked for.

Install them yourself (the application never downloads a model):

```bash
ollama pull gemma3:4b
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
ollama list          # all three must appear here
```

On a machine with limited RAM, replace the two larger models with smaller ones and restart the
backend; nothing in the code depends on these particular names:

```
OLLAMA_MODELS=gemma3:4b,qwen2.5:3b,phi4-mini
```

## Configuration

All settings live in `backend/.env` (see `.env.example` at the repository root, which contains
no secrets). Model names are never hard-coded in the application.

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint. |
| `OLLAMA_MODEL` | `gemma3:4b` | Primary/reference model, kept for backward compatibility. |
| `OLLAMA_MODELS` | `gemma3:4b,qwen2.5:7b,llama3.1:8b` | Comma-separated list analysed per review. Falls back to `OLLAMA_MODEL` when empty. |
| `OLLAMA_CONCURRENCY` | `1` | How many reviews are processed at once. |
| `OLLAMA_MODEL_CONCURRENCY` | `1` | How many models run at once *within* one review. |
| `OLLAMA_TIMEOUT` | `120` | Per-request timeout in seconds. |
| `OLLAMA_FORCE_JSON` | `true` | Sends Ollama's `format: "json"` constraint, which greatly reduces parse failures on non-Gemma models. Set to `false` to disable. |
| `RECOMMENDATION_LLM_NARRATIVE` | `false` | When true, an LLM may rephrase the recommendation *text*. The recommendation itself is always computed from numbers. |

Total simultaneous Ollama requests is `OLLAMA_CONCURRENCY × OLLAMA_MODEL_CONCURRENCY`, so the
defaults keep exactly one request in flight — safest on a laptop GPU. Raise them only if you
have the memory: three 4-8B models resident at once is roughly 12-16 GB.

## Running it

```bash
# 1. MongoDB and Ollama running, models pulled (see above)

# 2. backend  (PowerShell: run these one per line, && is not a separator)
cd backend
pip install -r requirements.txt
python ../scripts/migrate_multi_model.py --dry-run     # only if you have pre-upgrade data
python ../scripts/migrate_multi_model.py               # backfill + create indexes
python -m uvicorn app.main:app --reload                # http://localhost:8000

# 3. frontend
cd frontend
npm install
npm run dev                                            # http://localhost:5173
```

Then register or log in, upload a CSV, press Analyze, and watch the progress page: it reports
per-model counters while the job runs. When it finishes, the dataset page shows the ensemble
score and the recommendation, the Multi-Model Comparison page shows the model-by-model
breakdown, and the Reviews page shows the per-review model table.

Use `data/sample_flipkart_reviews.csv` for a quick smoke test, or
`data/demo_multi_model_reviews.csv` for a full demonstration — the latter has 18 labelled
reviews across 3 products with 6 reviews each, which clears the 5-review floor so every product
receives a real recommendation tier rather than "Insufficient Data".

A step-by-step operator guide, including model checks, dataset requirements, what to look at on
each page and a troubleshooting table, is in [`RUNBOOK.md`](RUNBOOK.md).

A virtual environment is optional — the commands above use whatever Python `pip install` targeted.
If you do want one, `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1` (PowerShell needs
the `.\` prefix and the `.ps1` script, and may need
`Set-ExecutionPolicy -Scope Process RemoteSigned` once). `python -m uvicorn` is used instead of
plain `uvicorn` because pip installs console scripts into
`%APPDATA%\Python\Python3xx\Scripts`, which is often not on PATH.

The migration script is optional, idempotent and non-destructive: it creates the new indexes
and, for datasets analysed before the upgrade, backfills one per-model document from each
legacy result so those datasets render in the new UI. Run it with `--dry-run` first to see what
it would touch. Nothing is deleted or overwritten.

Backfilled datasets still only hold one model's result, so they display single-model agreement.
Because analysis is resumable — only `pending`/`failed` reviews are picked up — a fully analysed
dataset cannot be re-run from the UI. `scripts/reset_dataset_analysis.py --dataset-id <id>`
re-opens one by flipping its reviews back to `pending` and zeroing the dataset counters, after
which the normal Start AI Analysis flow runs every configured model. It supports `--list` and
`--dry-run`, and deletes nothing unless you pass `--purge-results`.

## Data model

Two collections carry the analysis now.

`model_analysis_results` holds one document per review *per model*: `review_id`, `dataset_id`,
`user_id`, `product_name`, `model_name`, `status` (`completed` / `failed` / `unavailable`),
`sentiment`, `ai_sentiment_score`, `reason`, `aspects`, `positive_points`, `negative_points`,
`keywords`, `processing_time_ms`, `attempts`, `error_type`, `error_message`. A unique index on
`(review_id, model_name)` makes re-analysis idempotent, and compound indexes on
`(dataset_id, model_name, status)` and `(dataset_id, product_name, model_name)` serve the
comparison and per-product queries.

`analysis_results` keeps its original one-document-per-review shape and its original field
names, so every existing query, chart and export keeps working. It is now the *consensus*
document: alongside the legacy fields it stores `ensemble_score`, `ensemble_sentiment`,
`model_scores`, `model_sentiments`, `score_min`, `score_max`, `score_range`,
`agreement_level`, `agreement_ratio`, `models_used`, `models_failed` and `reference_model`.
Its `sentiment` and `ai_sentiment_score` now carry the ensemble values, which is what makes the
pre-existing analytics, filters and evaluation automatically reflect all three models.

`reports` gained a `type: "recommendation"` snapshot next to the existing evaluation snapshot.
`analysis_jobs` gained `models`, `models_unavailable` and per-model counters.

## How the numbers are calculated

**Per review.** `ensemble_score` is the arithmetic mean of the scores of the models that
succeeded, rounded to two decimals; `score_min`, `score_max` and `score_range` come from the
same set. Agreement is a majority vote over the model labels: all models agreeing is `high`
(ratio 1.0), a strict majority is `moderate`, no majority — including an even split — is `low`.
One configured model is reported as `single_model` rather than pretending to be agreement, and
a review where every model failed is `unavailable`. The ensemble label is the majority label
when one exists, otherwise it is derived from the ensemble score (≥ 3.5 positive, ≥ 2.0
neutral, below that negative). A failed model lowers nothing: it is simply excluded from the
mean and listed in `models_failed`.

**Per dataset and per model.** Each model gets its own review count, average score,
positive/neutral/negative percentages, average processing time, five-bucket score
distribution, failure counts by error type, and an agreement-with-others percentage computed
pairwise over the reviews both models actually scored. The dataset ensemble score is the mean
of the per-review ensemble scores, and the dataset agreement index is the mean of the
per-review agreement ratios.

**Recommendation.** A deterministic weighted score in the 0-100 range:

```
score = 100 × (0.55 × ensemble/5  +  0.25 × positive_share
             + 0.10 × (1 − negative_share)  +  0.10 × agreement_index)
```

mapped to tiers at 82 (Highly Recommended), 65 (Recommended) and 48 (Consider Carefully),
below which it is Not Recommended. Four guardrails may then *lower* — never raise — the tier:
fewer than 5 analysed reviews becomes Insufficient Data; a negative share of 35% or more, or an
ensemble score below 3.0, caps at Consider Carefully; an agreement index below 0.5 caps at
Recommended. Every applied cap is returned in `applied_caps` and shown in the UI, so a
suppressed tier is always explained. Confidence is a separate figure,
`0.45 × evidence + 0.35 × agreement + 0.20 × model_coverage`, reported as High at 0.72 and
Medium at 0.50, where evidence is a step function of the review count and coverage is the share
of the possible model runs that actually produced a score. Strengths and concerns come from
aspects mentioned in at least two reviews. All thresholds are named constants at the top of
`backend/app/services/recommendation.py`.

An LLM never decides the tier, the score or the confidence. When
`RECOMMENDATION_LLM_NARRATIVE=true`, a model may rewrite the explanation *sentence* from those
already-computed numbers, and if that call fails the deterministic text is kept — the response
field `narrative_source` tells you which text you are looking at.

**Evaluation.** When the uploaded CSV has a `Sentiment` column, accuracy, precision, recall and
F1 are computed for each model and for the ensemble against the same ground truth, using the
existing scikit-learn code path. The original top-level metric fields still hold the ensemble
numbers, so the existing evaluation page and any stored reports remain valid.

## Failure handling

A model that is not installed is reported as `unavailable` with the exact
`ollama pull <model>` command needed to fix it, and it is remembered for the rest of the run so
the pipeline stops re-asking. A model that times out, returns unparsable output or errors is
recorded per review with its `error_type`, and the review still completes on the remaining
models. The UI shows the affected model as unavailable or failed instead of hiding it, and the
recommendation warns when a model failed on more than 10% of reviews. A review is only marked
failed when *every* model failed.

## Tests

Four suites run without MongoDB, Ollama or a network. With the backend venv active:

```bash
cd backend
pytest tests                                   # or: python tests/test_ensemble.py
```

`tests/test_ensemble.py` (23 tests) covers the score/label thresholds, agreement levels,
per-review summaries, merging and the dataset statistics. `tests/test_recommendation_scoring.py`
(21 tests) pins the weighted formula, the tier boundaries, each guardrail, the confidence bands
and the explainability payload. `tests/test_multi_model_service.py` (16 tests) drives the
orchestrator with fake models to prove the same review text reaches every model, that
concurrency limits hold, and that timeouts, invalid output and missing models are isolated.
`tests/test_service_integration.py` (18 tests) runs the comparison and recommendation services
against an in-memory MongoDB stand-in, including the legacy single-model fallback and
per-product recommendations. `tests/test_ollama_single.py` is the project's original manual
smoke script and still needs a live Ollama.

Two harness scripts support acceptance testing:

```bash
# stand in for Ollama; here llama3.1:8b is "not installed" so it 404s
python scripts/mock_ollama.py --port 11435 --models gemma3:4b,qwen2.5:7b
#   ... then run the backend with OLLAMA_BASE_URL=http://localhost:11435

# walk the whole workflow against a running backend and print PASS/FAIL per spec case
python scripts/e2e_check.py --frontend-url http://localhost:5173
```

`mock_ollama.py` is explicitly a test double: its scores come from a keyword heuristic, not
from a language model, and it exists to reproduce failure modes (`--timeout-models`,
`--error-models`, `--bad-json-models`) and to let the pipeline be exercised on hardware that
cannot host three real models. Never use it for a demo or a report.

## Limitations

Processing time scales with the number of models: three models at the default concurrency of
one means roughly three times the single-model runtime, so a few thousand reviews is an
overnight job on a laptop. Agreement is computed over the three coarse sentiment labels, so two
models can "agree" while differing by more than a point of score — the score range is reported
alongside precisely so that case is visible. Aspect merging matches aspect names literally after
lower-casing, so "battery" and "battery life" are counted separately. The per-product
recommendation groups on the CSV's `product_name` string, so inconsistent product naming in the
source data produces separate products. The recommendation thresholds are calibrated by hand
against Flipkart-style review distributions rather than learned, and should be revisited if you
apply the system to a very different corpus.
