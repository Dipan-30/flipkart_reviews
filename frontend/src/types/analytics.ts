export interface SentimentCount {
  positive: number;
  neutral: number;
  negative: number;
}

export interface SentimentPercentage {
  positive: number;
  neutral: number;
  negative: number;
}

export interface ScoreDistributionBucket {
  range: string;
  count: number;
}

export interface AspectAnalytics {
  name: string;
  count: number;
  avg_score: number;
  sentiment: string;
}

export interface KeywordItem {
  keyword: string;
  count: number;
  sentiment: string;
}

export interface ProductSentiment {
  product_name: string;
  total_reviews: number;
  avg_score: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
}

export interface AnalyticsResponse {
  dataset_id: string;
  total_reviews: number;
  completed_reviews: number;
  sentiment_counts: SentimentCount;
  sentiment_percentages: SentimentPercentage;
  average_ai_score: number;
  score_distribution: ScoreDistributionBucket[];
  top_aspects: AspectAnalytics[];
  top_positive_keywords: KeywordItem[];
  top_negative_keywords: KeywordItem[];
  products: ProductSentiment[];
}
