import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { evaluationService, EvaluationResult, MetricSet } from '../services/evaluation';
import { ArrowLeft, RefreshCw, AlertCircle, CheckCircle, Trophy } from 'lucide-react';
import { formatPercent } from '../utils/formatters';

export default function EvaluationPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<EvaluationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('Ensemble');

  const fetchEval = async () => {
    if (!id) return;
    try {
      const res = await evaluationService.get(id);
      setData(res);
      setError('');
    } catch (err: any) {
      if (err.response?.status !== 404) {
        setError('Failed to load evaluation.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEval();
  }, [id]);

  const handleRunEvaluation = async () => {
    if (!id) return;
    setRunning(true);
    setError('');
    try {
      const res = await evaluationService.run(id);
      setData(res);
      setSelectedModel('Ensemble');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to run evaluation.');
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading evaluation...</div>;

  // The backend already returns percentages (e.g. 91.25 === 91.25%).
  const ensembleMetrics: MetricSet | null = data
    ? data.ensemble_metrics ?? {
        model_name: 'Ensemble',
        matched_reviews: data.matched_reviews,
        accuracy: data.accuracy,
        precision: data.precision,
        recall: data.recall,
        f1_score: data.f1_score,
        confusion_matrix: data.confusion_matrix,
        per_class_metrics: data.per_class_metrics,
      }
    : null;

  const modelMetrics = data?.model_metrics ?? [];
  const allMetricSets: MetricSet[] = ensembleMetrics ? [ensembleMetrics, ...modelMetrics] : [];
  const active = allMetricSets.find((m) => m.model_name === selectedModel) ?? ensembleMetrics;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <Link to={`/datasets/${id}`} className="p-2 text-slate-500 hover:text-slate-800 bg-white rounded-lg border border-slate-200">
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">AI Evaluation Metrics</h1>
            <p className="text-slate-500">Compare every local LLM against the same ground truth.</p>
          </div>
        </div>
        <button
          onClick={handleRunEvaluation}
          disabled={running}
          className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
        >
          <RefreshCw size={18} className={`mr-2 ${running ? 'animate-spin' : ''}`} />
          {running ? 'Running...' : data ? 'Re-run Evaluation' : 'Run Evaluation'}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-md flex items-start border border-red-200">
          <AlertCircle className="shrink-0 mr-3 mt-0.5" size={18} />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      {!data && !error && (
        <div className="bg-white p-12 rounded-xl border border-slate-200 shadow-sm text-center">
          <CheckCircle size={48} className="mx-auto text-slate-300 mb-4" />
          <h3 className="text-lg font-medium text-slate-900">Ready to Evaluate</h3>
          <p className="mt-2 text-slate-500 max-w-md mx-auto">
            This dataset has ground truth labels. Click the button above to run standard ML metrics
            (Accuracy, F1, Precision, Recall) for the ensemble and for each individual model.
          </p>
        </div>
      )}

      {data && ensembleMetrics && (
        <>
          {/* Ensemble headline metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
              <h3 className="text-sm font-medium text-slate-500 mb-1">Accuracy</h3>
              <p className="text-3xl font-bold text-slate-900">{formatPercent(ensembleMetrics.accuracy)}</p>
            </div>
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
              <h3 className="text-sm font-medium text-slate-500 mb-1">Weighted F1 Score</h3>
              <p className="text-3xl font-bold text-slate-900">{formatPercent(ensembleMetrics.f1_score)}</p>
            </div>
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
              <h3 className="text-sm font-medium text-slate-500 mb-1">Precision</h3>
              <p className="text-3xl font-bold text-slate-900">{formatPercent(ensembleMetrics.precision)}</p>
            </div>
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
              <h3 className="text-sm font-medium text-slate-500 mb-1">Recall</h3>
              <p className="text-3xl font-bold text-slate-900">{formatPercent(ensembleMetrics.recall)}</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 text-center -mt-2">
            Headline figures describe the ensemble prediction (the average of all model scores).
          </p>

          {/* Per-model comparison */}
          {modelMetrics.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">Model Comparison vs Ground Truth</h3>
                {data.best_model && (
                  <span className="inline-flex items-center text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full">
                    <Trophy size={13} className="mr-1.5" /> Best F1: {data.best_model}
                  </span>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Model</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Accuracy</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Precision</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Recall</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">F1 (W)</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Macro F1</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Latency (ms)</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Success %</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Reviews</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-slate-200">
                    {allMetricSets.map((metrics) => {
                      const isEnsemble = metrics.model_name === 'Ensemble';
                      const isActive = metrics.model_name === selectedModel;
                      return (
                        <tr
                          key={metrics.model_name}
                          onClick={() => setSelectedModel(metrics.model_name)}
                          className={`cursor-pointer ${isActive ? 'bg-primary-50' : 'hover:bg-slate-50'}`}
                        >
                          <td className={`px-6 py-4 whitespace-nowrap text-sm ${isEnsemble ? 'font-semibold text-slate-900' : 'font-mono text-slate-800'}`}>
                            {metrics.model_name}
                            {data.best_model === metrics.model_name && (
                              <Trophy size={13} className="inline ml-2 text-amber-500" />
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-right">{formatPercent(metrics.accuracy)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-right">{formatPercent(metrics.precision)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-right">{formatPercent(metrics.recall)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-900 text-right">{formatPercent(metrics.f1_score)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-indigo-700 font-semibold text-right">{metrics.macro_f1 != null ? formatPercent(metrics.macro_f1) : '—'}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{metrics.avg_latency_ms != null ? `${metrics.avg_latency_ms} ms` : '—'}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{metrics.success_rate_pct != null ? `${metrics.success_rate_pct}%` : '—'}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{metrics.matched_reviews}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500">
                Select a row to see its per-class metrics and confusion matrix below.
              </div>
            </div>
          )}

          {/* Per-class metrics + confusion matrix for the selected model */}
          {active && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200">
                  <h3 className="font-semibold text-slate-900">
                    Per-Class Metrics <span className="text-sm font-normal text-slate-500">— {active.model_name}</span>
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                      <tr>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Class</th>
                        <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Precision</th>
                        <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Recall</th>
                        <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">F1 Score</th>
                        <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Support</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-slate-200">
                      {Object.entries(active.per_class_metrics).map(([label, metrics]) => (
                        <tr key={label}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900 capitalize">{label}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{formatPercent(metrics.precision)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{formatPercent(metrics.recall)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{formatPercent(metrics.f1_score)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-right">{metrics.support}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200">
                  <h3 className="font-semibold text-slate-900">
                    Confusion Matrix <span className="text-sm font-normal text-slate-500">— {active.model_name}</span>
                  </h3>
                </div>
                <div className="p-6 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-500">Actual \ Predicted</th>
                        {active.confusion_matrix.labels.map((label) => (
                          <th key={label} className="px-3 py-2 text-center text-xs font-medium text-slate-500 capitalize">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {active.confusion_matrix.matrix.map((row, rowIdx) => (
                        <tr key={rowIdx}>
                          <td className="px-3 py-2 text-xs font-medium text-slate-700 capitalize">
                            {active.confusion_matrix.labels[rowIdx]}
                          </td>
                          {row.map((value, colIdx) => (
                            <td
                              key={colIdx}
                              className={`px-3 py-2 text-center font-medium rounded ${
                                rowIdx === colIdx ? 'bg-green-50 text-green-800' : value > 0 ? 'bg-red-50 text-red-700' : 'text-slate-400'
                              }`}
                            >
                              {value}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          <p className="text-sm text-slate-500 text-center mt-4">
            Evaluated {data.matched_reviews} out of {data.total_with_ground_truth} reviews with ground
            truth labels. Last run: {new Date(data.created_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}
