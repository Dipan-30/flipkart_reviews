export interface JobModelCounters {
  success?: number;
  failed?: number;
  unavailable?: number;
}

export interface JobStatusResponse {
  job_id: string;
  dataset_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  total: number;
  processed: number;
  successful: number;
  failed: number;
  progress_percent: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  // Multi-model progress (optional)
  models?: string[];
  models_unavailable?: string[];
  model_stats?: Record<string, JobModelCounters>;
}
