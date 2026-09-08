# Sales Forecasting with Sentiment Index Integration

## Overview

The Sales Forecasting module provides time-series modeling capabilities to predict product sales over flexible forecast horizons (e.g., 7, 14, 30, or 60 days). It incorporates LLM-derived sentiment scores as exogenous regressors (SARIMAX) to evaluate whether product sentiment improves forecasting accuracy compared to standard univariate time-series baselines (SARIMA).

---

## Technical Methodology

### 1. Data Ingestion & Preprocessing
- **Source Data**: Uploaded sales CSV file containing at least `date`, `product_name`, and `units_sold` (with optional `revenue` and `price`).
- **Validation**: Strict column validation, multi-format date parsing (`YYYY-MM-DD`, `DD-MM-YYYY`, `MM/DD/YYYY`, etc.), chronological sorting, and numeric coercing.
- **Aggregation**: Daily grouping by `(date, product_name)` summing `units_sold` and `revenue`.

### 2. Daily Sentiment Index Aggregation
- **Source**: Completed LLM sentiment analysis results stored in MongoDB (`analysis_results` & `reviews`).
- **Calculation**: For each `(review_date, product_name)` pair, the average AI sentiment score (1.0 to 5.0) across analyzed reviews is computed.
- **Persistence**: Results are stored in the `daily_sentiment` MongoDB collection.

### 3. Dataset Joining & Alignment
- **Left Join**: Sales daily records are joined with daily sentiment index on `date`.
- **Missing Value Handling**: Missing sentiment scores on dates without reviews are imputed using the product's historical mean sentiment score.

### 4. Time-Series Modeling

#### Univariate Baseline (SARIMA)
- **Model**: `SARIMAX(p, d, q) x (P, D, Q, s)` operating solely on `units_sold`.
- **Default Order**: `(1, 1, 1)` with `(0, 0, 0, 0)` seasonal components.

#### Exogenous Sentiment Model (SARIMAX)
- **Model**: `SARIMAX(p, d, q) x (P, D, Q, s)` with `sentiment_score` passed as `exog`.
- **Future Exogenous Strategy**: For out-of-sample forecasting, future sentiment values default to the mean historical sentiment score unless future sentiment signals are supplied.

### 5. Evaluation Metrics

- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|$$

- **Root Mean Squared Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (y_i - \hat{y}_i)^2}$$

- **Mean Absolute Percentage Error (MAPE)**:
  $$\text{MAPE} = \frac{100}{n} \sum_{i=1}^{n} \left| \frac{y_i - \hat{y}_i}{y_i} \right|$$
  *(Note: Zero actual values $y_i = 0$ are safely excluded to prevent division by zero errors.)*

---

## API Summary

- `POST /api/forecasting/upload-sales` — Upload and validate a sales CSV file.
- `GET /api/forecasting/sales-datasets` — List uploaded sales dataset metadata.
- `GET /api/forecasting/products` — Products present in both reviews and sales datasets.
- `POST /api/forecasting/build-sentiment-index` — Aggregate LLM scores into a daily sentiment index.
- `POST /api/forecasting/build-dataset` — Join daily sales data with sentiment index.
- `POST /api/forecasting/train` — Train SARIMA and SARIMAX models, return test & train metrics.
- `POST /api/forecasting/forecast` — Generate future predictions for specified horizon.
- `GET /api/forecasting/runs` — List historical experiment runs.
- `GET /api/forecasting/runs/{run_id}` — Get single experiment run details.
