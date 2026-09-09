import api from './api';
import type { DatasetListResponse, Dataset, UploadResponse, AnalysisJobStartResponse } from '../types/dataset';

export const datasetService = {
  async upload(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/datasets/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async list(): Promise<DatasetListResponse> {
    const response = await api.get('/datasets');
    return response.data;
  },

  async get(id: string): Promise<Dataset> {
    const response = await api.get(`/datasets/${id}`);
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/datasets/${id}`);
  },

  async analyze(id: string): Promise<AnalysisJobStartResponse> {
    const response = await api.post(`/datasets/${id}/analyze`);
    return response.data;
  },

  async stop(id: string): Promise<void> {
    await api.post(`/datasets/${id}/stop`);
  }
};
