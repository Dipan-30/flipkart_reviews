import api from './api';

export interface ClassMetrics {
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
}

export interface ConfusionMatrix {
  labels: string[];
  matrix: number[][];
}

/**
 * All metric values are percentages already multiplied by 100 by the backend
 * (e.g. 91.25 means 91.25%).
 */
export interface MetricSet {
  model_name: string;
  matched_reviews: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  macro_f1?: number;
  avg_latency_ms?: number;
  success_rate_pct?: number;
  confusion_matrix: ConfusionMatrix;
  per_class_metrics: Record<string, ClassMetrics>;
}

export interface EvaluationResult {
  _id: string;
  dataset_id: string;
  total_with_ground_truth: number;
  matched_reviews: number;
  skipped_reviews: number;
  // Ensemble metrics (existing top-level keys, unchanged)
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  confusion_matrix: ConfusionMatrix;
  per_class_metrics: Record<string, ClassMetrics>;
  // Multi-model additions
  ensemble_metrics?: MetricSet;
  model_metrics?: MetricSet[];
  models_evaluated?: string[];
  best_model?: string | null;
  created_at: string;
}

export const evaluationService = {
  async run(datasetId: string): Promise<EvaluationResult> {
    const response = await api.post(`/datasets/${datasetId}/evaluate`);
    return response.data;
  },

  async get(datasetId: string): Promise<EvaluationResult> {
    const response = await api.get(`/datasets/${datasetId}/evaluate`);
    return response.data;
  }
};
