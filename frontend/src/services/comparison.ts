import api from './api';
import type {
  ModelComparisonResponse,
  ReviewModelAnalysisResponse,
} from '../types/comparison';

export const comparisonService = {
  /** Dataset-level multi-model comparison (per-model stats, agreement, ensemble). */
  async getModelComparison(
    datasetId: string,
    params?: { review_limit?: number }
  ): Promise<ModelComparisonResponse> {
    const response = await api.get(`/datasets/${datasetId}/model-comparison`, { params });
    return response.data;
  },

  /** Every model's own analysis of a single review. */
  async getReviewModelAnalysis(reviewId: string): Promise<ReviewModelAnalysisResponse> {
    const response = await api.get(`/reviews/${reviewId}/model-analysis`);
    return response.data;
  },
};
