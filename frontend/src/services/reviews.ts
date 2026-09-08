import api from './api';
import type { ReviewListResponse, Review } from '../types/review';

export const reviewService = {
  async list(
    datasetId: string, 
    params?: { 
      page?: number; 
      page_size?: number; 
      sentiment?: string; 
      search?: string;
      product?: string;
      min_score?: number;
      max_score?: number;
      status?: string;
    }
  ): Promise<ReviewListResponse> {
    const response = await api.get(`/datasets/${datasetId}/reviews`, { params });
    return response.data;
  },

  async get(reviewId: string): Promise<Review> {
    const response = await api.get(`/reviews/${reviewId}`);
    return response.data;
  }
};
