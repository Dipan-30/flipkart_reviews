export interface AspectSentiment {
  name: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  score: number;
}

export interface Review {
  id: string;
  dataset_id: string;
  product_name?: string;
  product_price?: string;
  review: string;
  summary?: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  attempt_count: number;
  error_message?: string;
  created_at: string;
  
  sentiment?: 'positive' | 'neutral' | 'negative';
  ai_sentiment_score?: number;
  reason?: string;
  aspects?: AspectSentiment[];
  positive_points?: string[];
  negative_points?: string[];
  keywords?: string[];
  model_name?: string;
  processing_time_ms?: number;

  // Multi-model fields. Present once the review has been analysed by the
  // multi-model pipeline; absent for datasets analysed before the upgrade.
  model_scores?: Record<string, number>;
  model_sentiments?: Record<string, string>;
  ensemble_score?: number;
  ensemble_sentiment?: 'positive' | 'neutral' | 'negative' | string;
  score_min?: number;
  score_max?: number;
  score_range?: number;
  agreement_level?: 'high' | 'moderate' | 'low' | 'single_model' | 'unavailable' | string;
  agreement_ratio?: number;
  models_used?: string[];
  models_failed?: string[];
  models_total?: number;
}

export interface ReviewListResponse {
  reviews: Review[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
