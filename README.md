# Flipkart AI Review Intelligence & Sales Forecasting System

An end-to-end intelligence platform for e-commerce review analysis, multi-model LLM benchmarking, and sales forecasting integrated with AI sentiment signals.

---

## Key Features

1. **Multi-Model LLM Sentiment Analysis**:
   - Compare predictions across multiple local Ollama models (e.g., `gemma3:4b`, `qwen2.5:7b`, `llama3.1:8b`).
   - Extract granular aspect-based sentiment, scores (1-5), and key customer pain points.
   - Deterministic ensemble aggregation with agreement indexing.

2. **Model Evaluation & Benchmarking**:
   - Comprehensive model comparison reporting metrics: Accuracy, Precision, Recall, Weighted F1, **Macro F1**, **Average Latency**, and **Success Rate**.
   - Review-level comparison side-by-side matrices.

3. **Sales Forecasting Module**:
   - Time-series sales prediction over flexible horizons (7, 14, 30, 60 days).
   - **SARIMA Baseline**: Classical univariate seasonal auto-regressive model.
   - **SARIMAX Exogenous Model**: Uses daily aggregated AI sentiment index as an exogenous regressor to improve sales predictions.
   - Comprehensive metric reporting: **MAE**, **RMSE**, and **MAPE** (with zero-safe division).
   - Interactive chart visualization with actual vs predicted lines and sentiment-sales overlay.

---

## System Architecture

- **Backend**: FastAPI, Motor (async MongoDB driver), Pydantic v2, Statsmodels, Pandas, NumPy, Ollama REST client.
- **Frontend**: React, Vite, TypeScript, Tailwind CSS, Lucide Icons, Recharts.
- **Database**: MongoDB (collections: `users`, `datasets`, `reviews`, `analysis_results`, `model_analysis_results`, `sales_datasets`, `sales_records`, `daily_sentiment`, `forecasting_runs`, `forecast_results`).

---

## Quickstart Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- MongoDB instance running locally or via URI
- Ollama installed (optional, for local LLM inference)

### 1. Backend Setup

```bash
cd backend

# Create & activate virtual environment (optional)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (.env)
cp ../.env.example .env

# Run FastAPI development server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The application will be available at `http://localhost:5173`.

---

## Verification & API Documentation

- **Interactive API Documentation (Swagger UI)**: `http://127.0.0.1:8000/docs`
- **End-to-End Automated Acceptance Verification**:
  ```bash
  python3 scripts/e2e_check.py
  ```

---

## Sample Datasets

Sample CSV files are located in `data/`:
- `data/sample_flipkart_reviews.csv` — E-commerce product reviews for sentiment analysis.
- `data/demo_multi_model_reviews.csv` — Review dataset configured for multi-model LLM benchmarking.
- `data/flipkart_sales_forecasting_sample.csv` — Daily sales time-series data for baseline SARIMA forecasting.
- `data/flipkart_sales_forecasting_combined_sample.csv` — Combined daily sales and review sentiment data for SARIMAX exogenous forecasting.

---

## System Documentation

- **System Runbook & User Guide**: [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
- **Multi-Model LLM Sentiment Engine**: [`docs/MULTI_MODEL.md`](docs/MULTI_MODEL.md)
- **SARIMA / SARIMAX Sales Forecasting**: [`docs/FORECASTING.md`](docs/FORECASTING.md)

