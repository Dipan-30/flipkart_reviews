export interface Dataset {
  id: string;
  user_id: string;
  filename: string;
  total_reviews: number;
  processed_reviews: number;
  successful_reviews: number;
  failed_reviews: number;
  status: 'uploaded' | 'analyzing' | 'completed' | 'failed' | 'paused';
  has_ground_truth: boolean;
  original_columns: string[];
  created_at: string;
  completed_at?: string;
}

export interface DatasetListResponse {
  datasets: Dataset[];
  total: number;
}

export interface UploadResponse {
  dataset_id: string;
  filename: string;
  total_reviews: number;
  columns_detected: Record<string, string>;
  message: string;
}

export interface AnalysisJobStartResponse {
  job_id: string;
  dataset_id: string;
  message: string;
}
