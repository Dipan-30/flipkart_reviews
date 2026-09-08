import api from './api';
import {
  DailySentimentRecord,
  ForecastRunDetail,
  ForecastRunSummary,
  SalesDatasetMeta,
  TrainRequest,
} from '../types/forecasting';

export const forecastingService = {
  async uploadSales(file: File): Promise<SalesDatasetMeta> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post('/forecasting/upload-sales', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  async listSalesDatasets(): Promise<SalesDatasetMeta[]> {
    const res = await api.get('/forecasting/sales-datasets');
    return res.data;
  },

  async getProductsWithBothData(): Promise<{ product_name: string }[]> {
    const res = await api.get('/forecasting/products');
    return res.data;
  },

  async buildSentimentIndex(
    reviewDatasetId: string,
    productName?: string
  ): Promise<DailySentimentRecord[]> {
    const res = await api.post('/forecasting/build-sentiment-index', {
      review_dataset_id: reviewDatasetId,
      product_name: productName,
    });
    return res.data;
  },

  async getSentimentIndex(
    reviewDatasetId: string,
    productName: string
  ): Promise<DailySentimentRecord[]> {
    const res = await api.get(
      `/forecasting/sentiment-index/${reviewDatasetId}/${encodeURIComponent(productName)}`
    );
    return res.data;
  },

  async train(body: TrainRequest): Promise<ForecastRunDetail> {
    const res = await api.post('/forecasting/train', body);
    return res.data;
  },

  async listRuns(): Promise<ForecastRunSummary[]> {
    const res = await api.get('/forecasting/runs');
    return res.data;
  },

  async getRun(runId: string): Promise<ForecastRunDetail> {
    const res = await api.get(`/forecasting/runs/${runId}`);
    return res.data;
  },
};
