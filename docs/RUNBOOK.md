# Runbook — running the Multi-LLM Flipkart Review Intelligence System

Everything below is written for **Windows PowerShell** from the project root
`C:\Users\asus\OneDrive\Desktop\Flipkart_reviews`.

Two things to remember about PowerShell: `&&` is **not** a command separator (run
the lines one at a time), and `uvicorn`/`pytest` may not be on your PATH, so this
guide always uses `python -m <tool>`.

---

## Part 0 — One-time prerequisites

### 0.1 MongoDB must be running

```powershell
Get-Service MongoDB
```

If `Status` is not `Running`:

```powershell
Start-Service MongoDB
```

### 0.2 Ollama must be running

On Windows, Ollama normally runs in the background after install. Confirm with:

```powershell
ollama list
```

If that errors, start Ollama from the Start menu (or run `ollama serve` in its own
terminal and leave it open).

### 0.3 Pull the three models

The application never downloads a model for you — this is deliberate.

```powershell
ollama pull gemma3:4b
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
ollama list
```

All three names must appear in `ollama list`. Combined they are roughly 12 GB on
disk. If your machine can't hold the two larger ones, see *Part 9.4* for how to
swap in smaller models — nothing in the code depends on these particular names.

### 0.4 Python dependencies

```powershell
cd backend
python -m pip install -r requirements.txt
```

A virtual environment is optional. If you want one:
`python -m venv .venv` then `.\.venv\Scripts\Activate.ps1` (PowerShell needs the
`.\` prefix and the `.ps1` file, and may need
`Set-ExecutionPolicy -Scope Process RemoteSigned` once).

### 0.5 Confirm the configuration

Open `backend\.env` and check these keys exist:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_MODELS=gemma3:4b,qwen2.5:7b,llama3.1:8b
OLLAMA_CONCURRENCY=1
OLLAMA_MODEL_CONCURRENCY=1
OLLAMA_TIMEOUT=120
OLLAMA_FORCE_JSON=true
```

`MONGO_URI` and `JWT_SECRET` should already be there from before — leave them
alone. `.env.example` in the project root documents every key with no secrets in
it.

### 0.6 One-time database migration (only if you have pre-upgrade data)

You have already run this successfully, so **skip it**. For reference:

```powershell
cd backend
python ..\scripts\migrate_multi_model.py --dry-run
python ..\scripts\migrate_multi_model.py
```

It is idempotent and non-destructive: it creates the new indexes and backfills
one per-model document from each old single-model result. Nothing is deleted.

---

## Part 1 — Start the application (two terminals)

### Terminal 1 — backend

```powershell
cd C:\Users\asus\OneDrive\Desktop\Flipkart_reviews\backend
python -m uvicorn app.main:app --reload
```

Wait for this block, which confirms the multi-model config was picked up:

```
Configured LLM models (3): gemma3:4b, qwen2.5:7b, llama3.1:8b
Primary (reference) model: gemma3:4b
Concurrency: 1 review(s) x 1 model(s) | timeout=120s
MongoDB connected successfully.
Application startup complete.
```

Leave this terminal open — the per-review analysis log appears here and is the
best progress indicator.

### Terminal 2 — frontend

```powershell
cd C:\Users\asus\OneDrive\Desktop\Flipkart_reviews\frontend
npm install        # first run only
npm run dev
```

Open the URL it prints, normally <http://localhost:5173>, and log in.

---

## Part 2 — Confirm all three models BEFORE you analyse

Go to **Settings** in the left sidebar. You should see:

- Ollama: **Connected**
- `gemma3:4b` — **Available**
- `qwen2.5:7b` — **Available**
- `llama3.1:8b` — **Available**

Any model showing **Not Installed** comes with the exact `ollama pull …` command
next to it. Run it, then reload the page. You *can* analyse with a model missing
— it will be recorded as unavailable per review and the others still run — but
for a first full pass you want all three green.

Equivalent API check if you prefer the terminal:

```powershell
Invoke-RestMethod http://localhost:8000/api/ollama/status | ConvertTo-Json -Depth 5
```

---

## Part 3 — Which dataset to upload

### 3.1 Recommended: the demo CSV built for this feature

```
data\demo_multi_model_reviews.csv
```

**18 reviews, 3 products, 6 reviews each, with ground-truth `Sentiment` labels.**

Use this one for your first full run. It is sized deliberately:

- 6 reviews per product clears the recommendation service's `MIN_REVIEWS = 5`
  floor, so each product gets a real tier instead of "Insufficient Data".
- The three products have deliberately different review profiles (one strongly
  positive, one mixed with heating/camera complaints, one mostly negative), so
  the per-product recommendations should land in visibly different tiers.
- Several reviews are genuinely ambiguous — e.g. *"The camera is excellent but
  the battery drains faster than I expected"* — which is where the three models
  tend to disagree. That disagreement is the whole point of the comparison view.
- Ground-truth labels (8 positive, 3 neutral, 7 negative) mean the **Evaluate AI**
  page can score every model against the same labels.
- 18 reviews × 3 models = **54 model calls**, which is a realistic but not
  overnight first run.

The sentiment labels in this file are my labels for review text written as
sample input. Every score, aspect and recommendation you see in the UI is
produced by the actual models at run time — nothing is pre-filled.

### 3.2 The original sample (quick smoke test only)

```
data\sample_flipkart_reviews.csv
```

12 reviews spread across **7** products, so most products have only 1–2 reviews.
The dataset-level recommendation works, but nearly every *product* will correctly
report **Insufficient Data** because it is under the 5-review floor. Fine for
checking the pipeline runs; not a good demo of product-level recommendations.

### 3.3 Your own Flipkart CSV

Only one column is required. Accepted names for it (case-insensitive):
`Review`, `review`, `review_text`, `reviews`, `text`.

Optional columns, any of these spellings:

| Purpose | Accepted column names |
| --- | --- |
| Product grouping | `product_name`, `product`, `name`, `item` |
| Price | `product_price`, `price`, `cost`, `mrp` |
| Short title | `summary`, `title`, `review_title` |
| Date | `date`, `review_date`, `created_at`, `timestamp` |
| Ground truth for evaluation | `Sentiment`, `sentiment`, `ground_truth`, `label` |

Practical guidance:

- Include `product_name` — without it there is nothing to group per-product
  recommendations by.
- Give every product you care about **at least 5 reviews**, ideally 15+ (below 15
  the recommendation adds a "thin evidence" warning, which is correct behaviour).
- Include `Sentiment` if you want per-model accuracy/precision/recall/F1. Values
  should be `positive` / `neutral` / `negative`.
- Ground truth is stored separately and **never** sent to the models, so it can't
  leak into their predictions.
- Start small. Multiply your review count by 3 to get the number of model calls.
- The uploader drops empty reviews and exact duplicate review text, so the count
  shown after upload may be lower than your row count.

---

## Part 4 — Upload and analyse

1. Left sidebar → **Datasets** → **Upload New Dataset** (or go straight to `/upload`).
2. Choose `data\demo_multi_model_reviews.csv` and upload. You land on the dataset
   detail page; the **Detected Columns** panel should list
   `product_name, product_price, Review, Summary, Sentiment`, status **UPLOADED**,
   Total Reviews **18**.
3. Press **Start AI Analysis**. You are redirected to the progress page, which
   shows a live success/failure counter *per model* and warns you that three
   models take longer than one. You can navigate away and come back.
4. Watch Terminal 1. One line per finished review, for example:

   ```
   ✓ Review 68ac… | ensemble=4.13 (positive) | agreement=high | gemma3:4b=4.2, qwen2.5:7b=4.0, llama3.1:8b=4.2
   ```

   That single line is your proof the same review went to all three models and
   all three results were kept. Time the first two or three lines to estimate the
   whole run — at the default concurrency of 1×1 the models run strictly one call
   at a time, so total time ≈ 54 × (seconds per call) on your hardware.
5. If a model times out you'll see the review still succeed with a
   `| failed: llama3.1:8b` suffix. That is the intended behaviour, not an error.
6. Wait for status **COMPLETED** on the dataset page.

---

## Part 5 — What to look at, page by page

From the dataset detail page, four buttons appear once analysis completes.

### 5.1 Multi-Model Comparison → **"Multi-Model AI Analysis"**

The core of the feature. In order down the page:

- A summary card per model with its average score, plus a dark **Overall
  Ensemble Score** card.
- **Average Sentiment Score by Model** — the headline comparison chart.
- **Sentiment Distribution by Model** — positive/neutral/negative % per model.
- **Score Distribution by Model** — five score buckets per model.
- **Model Agreement** — how many reviews had high / moderate / low agreement.
- **Review-Level Score Comparison** — the three models plus the ensemble line
  across individual reviews; the spread between lines is model disagreement.
- **Per-Model Statistics** — reviews analysed, average score, sentiment split,
  average processing time, failures by error type, agreement with the others.
- **Pairwise Sentiment Agreement** — each model pair's agreement, computed only
  over reviews both models actually scored.
- **Review-Level Model Comparison** — a table of review, each model's score,
  ensemble and agreement label.

### 5.2 View Analytics → the Product Analysis page

Top of the page is the **AI Product Recommendation** card for the whole dataset:
tier, confidence, ensemble score out of 5, the "why" bullets (positive %,
negative %, agreement, top strengths, top concerns), any warnings, and any
guardrail that capped the tier. Below it, the same card per product — this is
where the three products should differ.

### 5.3 View Reviews

Per review, press **Compare models** to expand a per-model table (model,
sentiment, score) with the ensemble score and agreement level underneath. A model
that failed on that review shows as unavailable/failed rather than being hidden.
Sentiment filter, product filter, search and pagination all still work.

### 5.4 Evaluate AI (only shown when the CSV had ground truth)

Accuracy, precision, recall and F1 **per model** plus the ensemble, all against
the same labels. The original single-model evaluation view is unchanged; the
per-model columns are additions.

---

## Part 6 — Re-running a dataset you already analysed

Your existing dataset `6a86cc63…` was analysed before the upgrade. Analysis is
resumable by design, so `Start AI Analysis` only picks up reviews that are
`pending` or `failed` — a fully analysed dataset has none, so the button is
hidden and its reviews will keep showing "Single model" agreement.

To re-open it for all three models:

```powershell
cd backend
python ..\scripts\reset_dataset_analysis.py --list
python ..\scripts\reset_dataset_analysis.py --dataset-id 6a86cc639d1f19f3afd15173 --dry-run
python ..\scripts\reset_dataset_analysis.py --dataset-id 6a86cc639d1f19f3afd15173
```

It flips the reviews back to `pending` and resets the dataset counters, nothing
more. Reload the dataset page, press **Start AI Analysis**, and all three models
will score all 18 reviews. Stored results are left in place because the worker
upserts on `(review_id, model_name)`, so each model overwrites only its own row.
Add `--purge-results` only if you removed a model from `OLLAMA_MODELS` and want
its old rows gone from the comparison.

Uploading the CSV again as a fresh dataset is also perfectly fine and leaves the
old one untouched.

---

## Part 7 — Proving the failure handling (optional but convincing)

### 7.1 A missing model

Add a model you have not pulled to `OLLAMA_MODELS`, e.g.
`OLLAMA_MODELS=gemma3:4b,qwen2.5:7b,llama3.1:8b,mistral:7b`, and restart the
backend. Settings shows `mistral:7b` as **Not Installed** with its pull command;
analysis still runs on the other three and the comparison page lists it as
missing. Remove it again afterwards.

### 7.2 Timeouts and bad output, without touching real models

```powershell
# Terminal 3 — a fake Ollama where llama3.1:8b is absent and qwen times out
python scripts\mock_ollama.py --port 11435 --models gemma3:4b,qwen2.5:7b --timeout-models qwen2.5:7b
```

Point `OLLAMA_BASE_URL=http://localhost:11435` in `backend\.env`, restart the
backend, and analyse a small dataset. You get one success, one timeout and one
unavailable per review — the review still completes.

**Set `OLLAMA_BASE_URL` back to `http://localhost:11434` afterwards.** The mock's
scores come from a keyword heuristic, not a language model, so never use its
output in a demo or report.

---

## Part 8 — Automated end-to-end check

With the backend and frontend both running:

```powershell
python scripts\e2e_check.py --frontend-url http://localhost:5173
```

It registers a throwaway user, logs in, uploads a CSV, runs analysis, polls the
job, then exercises model comparison, review-level model analysis,
recommendation, analytics, evaluation, ownership isolation (a second user must
not see the first user's dataset), malformed CSV rejection and unauthenticated
access, printing PASS/FAIL/SKIP per case. Add `--skip-analysis` for a fast
API-only sweep.

Offline unit suites, no MongoDB or Ollama needed:

```powershell
cd backend
python -m pytest tests
```

78 tests across `test_ensemble.py`, `test_recommendation_scoring.py`,
`test_multi_model_service.py` and `test_service_integration.py`.

---

## Part 9 — Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `uvicorn : The term 'uvicorn' is not recognized` | pip put console scripts in `%APPDATA%\Python\Python313\Scripts`, not on PATH. Use `python -m uvicorn app.main:app --reload`. |
| `.venv\Scripts\activate : The module '.venv' could not be loaded` | No venv exists, and PowerShell needs `.\.venv\Scripts\Activate.ps1`. A venv is optional — just skip the line. |
| `ServerSelectionTimeoutError` on startup | MongoDB isn't running → `Start-Service MongoDB`. |
| Every model reports unavailable | Ollama isn't running, or `OLLAMA_BASE_URL` still points at the mock on port 11435. |
| Job fails immediately with "None of the configured models are installed" | Correct behaviour — nothing could have succeeded. Pull at least one configured model. |
| One model always times out | It's too large for your RAM/VRAM. Raise `OLLAMA_TIMEOUT`, or swap it for a smaller model (9.4). |
| Analysis feels extremely slow | Three models at 1×1 is deliberately conservative. See 9.3. |
| Product cards all say "Insufficient Data" | Fewer than 5 reviews per product. Use `demo_multi_model_reviews.csv` or add reviews. |
| Reviews show "Single model" agreement | That dataset was analysed before the upgrade → Part 6. |
| **Evaluate AI** button missing | The CSV had no ground-truth `Sentiment` column. |
| `Field "model_coverage" … protected namespace` warning | Fixed; restart the backend to clear it. |

### 9.3 Speed vs. resources

`OLLAMA_CONCURRENCY` (reviews at once) × `OLLAMA_MODEL_CONCURRENCY` (models at
once within a review) is the total number of simultaneous Ollama requests. The
default 1×1 keeps exactly one call in flight, which is safest on a laptop GPU.
Raising either multiplies memory use — three 4–8B models resident at once is
roughly 12–16 GB. Change one step at a time and watch Task Manager.

### 9.4 Using smaller models

Any Ollama model works. Edit `OLLAMA_MODELS`, pull the replacements, restart:

```
OLLAMA_MODELS=gemma3:4b,qwen2.5:3b,phi4-mini
```

Keep `OLLAMA_MODEL` pointing at a model that is actually in the list — it is the
reference model whose reasoning text appears in the legacy single-result views.
The system also runs correctly with a single model configured.

---

## Part 10 — The five-minute version

```powershell
# prerequisites
Start-Service MongoDB
ollama list                        # gemma3:4b, qwen2.5:7b, llama3.1:8b present

# terminal 1
cd C:\Users\asus\OneDrive\Desktop\Flipkart_reviews\backend
python -m uvicorn app.main:app --reload

# terminal 2
cd C:\Users\asus\OneDrive\Desktop\Flipkart_reviews\frontend
npm run dev
```

Then in the browser: log in → **Settings** (all three models Available) →
**Upload** `data\demo_multi_model_reviews.csv` → **Start AI Analysis** → wait for
COMPLETED → **Multi-Model Comparison**, then **View Analytics** for the
recommendations, **View Reviews** → *Compare models* for per-review detail, and
**Evaluate AI** for per-model metrics.

The maths behind every number on those pages is documented in
[`docs/MULTI_MODEL.md`](MULTI_MODEL.md).
