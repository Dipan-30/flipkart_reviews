import api from './api';
import type { AnalyticsResponse } from '../types/analytics';

export const analyticsService = {
  async get(datasetId: string): Promise<AnalyticsResponse> {
    const response = await api.get(`/datasets/${datasetId}/analytics`);
    return response.data;
  }
};
