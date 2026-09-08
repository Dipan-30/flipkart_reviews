import api from './api';
import type { JobStatusResponse } from '../types/job';

export const jobService = {
  async getStatus(jobId: string): Promise<JobStatusResponse> {
    const response = await api.get(`/jobs/${jobId}`);
    return response.data;
  },

  async retry(jobId: string): Promise<JobStatusResponse> {
    const response = await api.post(`/jobs/${jobId}/retry`);
    return response.data;
  }
};
