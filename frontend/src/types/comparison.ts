// Mirrors backend/app/schemas/comparison.py

export type AgreementLevel = 'high' | 'moderate' | 'low' | 'single_model' | 'unavailable';

export interface ScoreBucket {
  range: string;
  count: number;
}

export interface ModelStats {
  model_name: string;
  available: boolean;
  analyzed_reviews: number;
  failed_reviews: number;
  unavailable_reviews: number;
  average_score: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
  avg_processing_time_ms: number;
  score_distribution: ScoreBucket[];
  error_types: Record<string, number>;
  agreement_with_others_pct?: number | null;
}

export interface PairwiseAgreement {
  model_a: string;
  model_b: string;
  compared_reviews: number;
  agreed_reviews: number;
  agreement_pct: number;
}

export interface AgreementSummary {
  total_reviews: number;
  high: number;
  moderate: number;
  low: number;
  single_model: number;
  unavailable: number;
  high_pct: number;
  moderate_pct: number;
  low_pct: number;
  agreement_index: number;
}

export interface ReviewScoreComparison {
  review_id: string;
  review_excerpt: string;
  product_name?: string | null;
  model_scores: Record<string, number>;
  model_sentiments: Record<string, string>;
  ensemble_score?: number | null;
  ensemble_sentiment?: string | null;
  score_min?: number | null;
  score_max?: number | null;
  score_range?: number | null;
  agreement_level: AgreementLevel | string;
  agreement_ratio: number;
  models_failed: string[];
}

export interface SentimentSplit {
  positive: number;
  neutral: number;
  negative: number;
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
}

export interface ModelComparisonResponse {
  dataset_id: string;
  dataset_name?: string | null;
  models_configured: string[];
  models_reporting: string[];
  models_missing: string[];
  multi_model: boolean;
  legacy_single_model: boolean;

  total_reviews: number;
  analyzed_reviews: number;

  ensemble_score?: number | null;
  ensemble_sentiment?: string | null;
  ensemble_split: SentimentSplit;
  ensemble_score_distribution: ScoreBucket[];

  model_stats: ModelStats[];
  pairwise_agreement: PairwiseAgreement[];
  agreement_summary: AgreementSummary;
  review_comparisons: ReviewScoreComparison[];
  review_comparisons_limit: number;

  generated_at: string;
}

export interface ModelResultDetail {
  model_name: string;
  status: 'completed' | 'failed' | 'unavailable' | string;
  sentiment?: string | null;
  ai_sentiment_score?: number | null;
  reason?: string | null;
  aspects: { name?: string; sentiment?: string; score?: number }[];
  positive_points: string[];
  negative_points: string[];
  keywords: string[];
  processing_time_ms?: number | null;
  attempts?: number | null;
  error_type?: string | null;
  error_message?: string | null;
}

export interface ReviewModelAnalysisResponse {
  review_id: string;
  dataset_id: string;
  review: string;
  product_name?: string | null;
  processing_status: string;

  model_results: ModelResultDetail[];
  models_configured: string[];
  models_missing: string[];

  ensemble_score?: number | null;
  ensemble_sentiment?: string | null;
  score_min?: number | null;
  score_max?: number | null;
  score_range?: number | null;
  average_score?: number | null;
  agreement_level: AgreementLevel | string;
  agreement_ratio: number;
  agreement_label: string;
  success_count: number;
  failure_count: number;
  legacy_single_model: boolean;
}
