/**
 * Shared presentation helpers for the multi-model UI.
 * Colours follow the palette already used by the existing charts.
 */

export const MODEL_COLORS = ['#3b82f6', '#8b5cf6', '#f97316', '#0ea5e9', '#14b8a6'];

export const ENSEMBLE_COLOR = '#1e293b';

/** Stable colour per model, based on its position in the configured list. */
export const getModelColor = (models: string[], name: string) => {
  const index = models.indexOf(name);
  return MODEL_COLORS[(index < 0 ? 0 : index) % MODEL_COLORS.length];
};

const AGREEMENT_LABELS: Record<string, string> = {
  high: 'High',
  moderate: 'Moderate',
  low: 'Low',
  single_model: 'Single model',
  unavailable: 'Unavailable',
};

export const getAgreementLabel = (level: string | undefined) =>
  AGREEMENT_LABELS[level ?? ''] ?? 'Unavailable';

export const getAgreementColor = (level: string | undefined) => {
  switch (level) {
    case 'high':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'moderate':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'low':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'single_model':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    default:
      return 'bg-slate-100 text-slate-600 border-slate-200';
  }
};

/** Card/badge styling per recommendation tier. */
export const getRecommendationStyle = (recommendation: string | undefined) => {
  switch (recommendation) {
    case 'Highly Recommended':
      return {
        badge: 'bg-green-100 text-green-800 border-green-200',
        card: 'bg-green-50 border-green-200',
        text: 'text-green-700',
        bar: 'bg-green-500',
      };
    case 'Recommended':
      return {
        badge: 'bg-emerald-100 text-emerald-800 border-emerald-200',
        card: 'bg-emerald-50 border-emerald-200',
        text: 'text-emerald-700',
        bar: 'bg-emerald-500',
      };
    case 'Consider Carefully':
      return {
        badge: 'bg-amber-100 text-amber-800 border-amber-200',
        card: 'bg-amber-50 border-amber-200',
        text: 'text-amber-700',
        bar: 'bg-amber-500',
      };
    case 'Not Recommended':
      return {
        badge: 'bg-red-100 text-red-800 border-red-200',
        card: 'bg-red-50 border-red-200',
        text: 'text-red-700',
        bar: 'bg-red-500',
      };
    default:
      return {
        badge: 'bg-slate-100 text-slate-700 border-slate-200',
        card: 'bg-slate-50 border-slate-200',
        text: 'text-slate-700',
        bar: 'bg-slate-400',
      };
  }
};

export const getConfidenceColor = (confidence: string | undefined) => {
  switch (confidence) {
    case 'High':
      return 'bg-green-100 text-green-800';
    case 'Medium':
      return 'bg-yellow-100 text-yellow-800';
    case 'Low':
      return 'bg-slate-100 text-slate-700';
    default:
      return 'bg-slate-100 text-slate-700';
  }
};

/** "gemma3:4b" -> "gemma3:4b" but shortened for tight chart axes. */
export const shortModelName = (name: string, max = 14) =>
  name.length <= max ? name : `${name.slice(0, max - 1)}…`;

export const formatMs = (ms: number | null | undefined) => {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
};
