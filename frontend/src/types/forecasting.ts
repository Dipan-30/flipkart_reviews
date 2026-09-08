export interface ForecastMetrics {
  mae: number | null;
  rmse: number | null;
  mape: number | null;
  n_test_samples: number;
}

export interface ModelForecastResult {
  model_name: string;
  order: number[];
  seasonal_order: number[];
  train_metrics: ForecastMetrics;
  test_metrics: ForecastMetrics;
  test_predictions: number[];
  forecast: number[];
  fitted_values: number[];
}

export interface SalesDatasetMeta {
  sales_dataset_id: string;
  filename: string;
  user_id: string;
  total_rows: number;
  products: string[];
  date_range_start: string;
  date_range_end: string;
  created_at: string;
}

export interface DailySentimentRecord {
  date: string;
  product_name: string;
  avg_score: number;
  review_count: number;
}

export interface ForecastRunSummary {
  run_id: string;
  product_name: string;
  created_at: string;
  has_sentiment: boolean;
  n_train: number;
  n_test: number;
  sarima_test_metrics?: ForecastMetrics;
  sarimax_test_metrics?: ForecastMetrics;
}

export interface ForecastRunDetail {
  run_id: string;
  sales_dataset_id: string;
  review_dataset_id: string;
  product_name: string;
  order: number[];
  seasonal_order: number[];
  forecast_horizon: number;
  test_fraction: number;
  n_train: number;
  n_test: number;
  has_sentiment: boolean;
  sarima?: ModelForecastResult;
  sarimax?: ModelForecastResult;
  actual_dates: string[];
  actual_values: number[];
  train_dates: string[];
  test_dates: string[];
  test_actual_values: number[];
  future_dates: string[];
  created_at: string;
}

export interface TrainRequest {
  sales_dataset_id: string;
  review_dataset_id: string;
  product_name: string;
  order?: number[];
  seasonal_order?: number[];
  forecast_horizon?: number;
  test_fraction?: number;
}
