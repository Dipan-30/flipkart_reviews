import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { comparisonService } from '../services/comparison';
import { ReviewModelAnalysisResponse } from '../types/comparison';
import { formatScore } from '../utils/formatters';
import { formatMs, getAgreementColor, getAgreementLabel, getModelColor } from '../utils/multiModel';
import { getSentimentColor, getScoreColor } from '../utils/sentimentColors';

interface Props {
  reviewId: string;
}

/**
 * Per-review model comparison table, lazily loaded when a review row is
 * expanded on the Reviews page.
 */
export default function ReviewModelComparison({ reviewId }: Props) {
  const [data, setData] = useState<ReviewModelAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    comparisonService
      .getReviewModelAnalysis(reviewId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError('');
        }
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Could not load per-model analysis.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reviewId]);

  if (loading) {
    return (
      <div className="flex items-center text-sm text-slate-500 py-2">
        <Loader2 size={16} className="animate-spin mr-2" /> Loading per-model analysis...
      </div>
    );
  }

  if (error || !data) {
    return <p className="text-sm text-red-600 py-2">{error}</p>;
  }

  const models = data.model_results.map((r) => r.model_name);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h4 className="text-sm font-semibold text-slate-900">Model comparison</h4>
        <span className={`px-2 py-0.5 rounded-md text-xs font-medium border ${getAgreementColor(data.agreement_level)}`}>
          Agreement: {getAgreementLabel(data.agreement_level)}
        </span>
        <span className="text-xs text-slate-500">
          Ensemble: <span className="font-semibold text-slate-800">{formatScore(data.ensemble_score)}/5</span>
          {data.ensemble_sentiment ? ` (${data.ensemble_sentiment})` : ''}
        </span>
        {data.score_range !== null && data.score_range !== undefined && (
          <span className="text-xs text-slate-500">
            Range: {formatScore(data.score_min)}–{formatScore(data.score_max)} (spread {formatScore(data.score_range)})
          </span>
        )}
      </div>

      {data.legacy_single_model && (
        <p className="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
          Analysed before the multi-model upgrade — only the original model result exists. Re-run the
          analysis to compare all configured models.
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 bg-white">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Model</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Sentiment</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Score</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Time</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider w-1/3">Reasoning</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.model_results.map((result) => (
              <tr key={result.model_name} className={result.status === 'completed' ? '' : 'bg-red-50/50'}>
                <td className="px-4 py-3 whitespace-nowrap text-sm font-mono text-slate-800">
                  <span className="inline-flex items-center">
                    <span
                      className="h-2 w-2 rounded-full mr-2"
                      style={{ backgroundColor: getModelColor(models, result.model_name) }}
                    />
                    {result.model_name}
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  {result.status === 'completed' ? (
                    <span className={`px-2 py-0.5 rounded-md text-xs font-bold uppercase border ${getSentimentColor(result.sentiment ?? undefined)}`}>
                      {result.sentiment}
                    </span>
                  ) : (
                    <span className="inline-flex items-center text-xs font-medium text-red-700">
                      <AlertTriangle size={13} className="mr-1" />
                      {result.status === 'unavailable'
                        ? `${result.model_name} unavailable`
                        : `Failed (${result.error_type ?? 'error'})`}
                    </span>
                  )}
                </td>
                <td className={`px-4 py-3 whitespace-nowrap text-sm text-right font-semibold ${getScoreColor(result.ai_sentiment_score ?? undefined)}`}>
                  {result.status === 'completed' ? `${formatScore(result.ai_sentiment_score)}/5` : '—'}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-slate-500">
                  {formatMs(result.processing_time_ms)}
                </td>
                <td className="px-4 py-3 text-sm text-slate-600">
                  <span className="line-clamp-3">
                    {result.status === 'completed'
                      ? result.reason
                      : result.error_message || 'No result produced by this model.'}
                  </span>
                </td>
              </tr>
            ))}
            {data.model_results.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-4 text-sm text-slate-500 text-center">
                  No model has analysed this review yet.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot className="bg-slate-50">
            <tr>
              <td className="px-4 py-2 text-xs font-semibold text-slate-700 uppercase tracking-wider">Ensemble</td>
              <td className="px-4 py-2">
                <span className={`px-2 py-0.5 rounded-md text-xs font-bold uppercase border ${getSentimentColor(data.ensemble_sentiment ?? undefined)}`}>
                  {data.ensemble_sentiment ?? '—'}
                </span>
              </td>
              <td className="px-4 py-2 text-sm text-right font-bold text-slate-900">
                {formatScore(data.ensemble_score)}/5
              </td>
              <td className="px-4 py-2" />
              <td className="px-4 py-2 text-xs text-slate-500">
                {data.success_count} model(s) succeeded
                {data.failure_count > 0 ? `, ${data.failure_count} failed` : ''}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {data.models_missing.length > 0 && (
        <p className="text-xs text-amber-700">
          No result from: {data.models_missing.join(', ')} —{' '}
          <code className="font-mono bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
            ollama pull {data.models_missing[0]}
          </code>{' '}
          then re-run the analysis.
        </p>
      )}
    </div>
  );
}
