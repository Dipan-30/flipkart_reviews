import api from './api';

export interface OllamaModelStatus {
  name: string;
  available: boolean;
  primary: boolean;
  pull_command: string | null;
}

export interface OllamaConcurrency {
  reviews: number;
  models_per_review: number;
  timeout_seconds: number;
}

export interface OllamaStatus {
  available: boolean;
  /** Primary (reference) model — legacy field, kept for backward compatibility. */
  model: string;
  model_available: boolean;
  base_url?: string;
  error: string | null;

  // Multi-model fields
  models?: OllamaModelStatus[];
  models_available?: number;
  models_configured?: number;
  installed_models?: string[];
  concurrency?: OllamaConcurrency;
}

export const ollamaService = {
  async getStatus(): Promise<OllamaStatus> {
    const response = await api.get('/ollama/status');
    return response.data;
  },

  async getModels(): Promise<{ models: string[]; configured?: string[]; primary?: string }> {
    const response = await api.get('/ollama/models');
    return response.data;
  }
};
