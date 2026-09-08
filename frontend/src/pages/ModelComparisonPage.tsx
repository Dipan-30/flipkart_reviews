import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertCircle, AlertTriangle, ArrowLeft, Layers, RefreshCw } from 'lucide-react';
import { comparisonService } from '../services/comparison';
import { ModelComparisonResponse } from '../types/comparison';
import { formatPercent, formatScore } from '../utils/formatters';
import {
  ENSEMBLE_COLOR,
  formatMs,
  getAgreementColor,
  getAgreementLabel,
  getModelColor,
  shortModelName,
} from '../utils/multiModel';
import { getSentimentColor } from '../utils/sentimentColors';

const SENTIMENT_COLORS = {
  positive: '#10b981',
  neutral: '#f59e0b',
  negative: '#ef4444',
};

const AGREEMENT_COLORS: Record<string, string> = {
  High: '#10b981',
  Moderate: '#f59e0b',
  Low: '#ef4444',
  'Single model': '#3b82f6',
  Unavailable: '#cbd5e1',
};

export default function ModelComparisonPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ModelComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await comparisonService.getModelComparison(id, { review_limit: 30 });
      setData(res);
      setError('');
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          'Model comparison is not available. Has the dataset finished processing?'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  if (loading) return <div className="p-8 text-center text-slate-500">Loading model comparison...</div>;
  if (error || !data) return <div className="p-8 text-center text-red-500">{error}</div>;

  const reportingModels = data.models_reporting;
  const stats = data.model_stats;

  // Chart 1 — average sentiment score by model (ensemble appended for reference)
  const avgScoreData = [
    ...stats.map((s) => ({
      name: shortModelName(s.model_name),
      model: s.model_name,
      score: s.average_score,
      fill: getModelColor(reportingModels, s.model_name),
    })),
    ...(data.ensemble_score !== null && data.ensemble_score !== undefined
      ? [
          {
            name: 'Ensemble',
            model: 'Ensemble',
            score: data.ensemble_score,
            fill: ENSEMBLE_COLOR,
          },
        ]
      : []),
  ];

  // Chart 2 — sentiment percentage split by model
  const sentimentSplitData = stats.map((s) => ({
    name: shortModelName(s.model_name),
    Positive: s.positive_pct,
    Neutral: s.neutral_pct,
    Negative: s.negative_pct,
  }));

  // Chart 3 — score distribution by model (grouped bars per bucket)
  const buckets = stats[0]?.score_distribution.map((b) => b.range) ?? [];
  const distributionData = buckets.map((range) => {
    const row: Record<string, string | number> = { range };
    stats.forEach((s) => {
      row[s.model_name] = s.score_distribution.find((b) => b.range === range)?.count ?? 0;
    });
    return row;
  });

  // Chart 4 — agreement distribution
  const agreement = data.agreement_summary;
  const agreementData = [
    { name: 'High', value: agreement.high },
    { name: 'Moderate', value: agreement.moderate },
    { name: 'Low', value: agreement.low },
    { name: 'Single model', value: agreement.single_model },
    { name: 'Unavailable', value: agreement.unavailable },
  ].filter((entry) => entry.value > 0);

  // Chart 5 — review-level score comparison
  const reviewSeries = data.review_comparisons.map((rc, index) => {
    const row: Record<string, string | number | null> = {
      label: `#${index + 1}`,
      excerpt: rc.review_excerpt,
      Ensemble: rc.ensemble_score ?? null,
    };
    reportingModels.forEach((model) => {
      row[model] = rc.model_scores[model] ?? null;
    });
    return row;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <Link
            to={`/datasets/${id}`}
            className="p-2 text-slate-500 hover:text-slate-800 bg-white rounded-lg border border-slate-200"
          >
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Multi-Model AI Analysis</h1>
            <p className="text-slate-500">
              {data.analyzed_reviews} of {data.total_reviews} reviews analysed by{' '}
              {reportingModels.length || 'no'} model{reportingModels.length === 1 ? '' : 's'}.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            to={`/datasets/${id}/products`}
            className="flex items-center px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition"
          >
            Analytics &amp; Recommendation
          </Link>
          <button
            onClick={load}
            className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
          >
            <RefreshCw size={18} className="mr-2" /> Refresh
          </button>
        </div>
      </div>

      {data.models_missing.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start">
          <AlertTriangle className="text-amber-600 shrink-0 mr-3 mt-0.5" size={18} />
          <div className="text-sm text-amber-800">
            <p className="font-medium">
              {data.models_missing.join(', ')} produced no results for this dataset.
            </p>
            <p className="mt-1">
              The model may not be installed or may have been added after this dataset was
              processed. Install it with{' '}
              <code className="font-mono bg-amber-100 px-1.5 py-0.5 rounded">
                ollama pull {data.models_missing[0]}
              </code>{' '}
              and re-run the analysis to include it.
            </p>
          </div>
        </div>
      )}

      {data.legacy_single_model && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start">
          <AlertCircle className="text-blue-600 shrink-0 mr-3 mt-0.5" size={18} />
          <p className="text-sm text-blue-800">
            This dataset was analysed before the multi-model upgrade, so only the original
            single-model results are shown. Re-run the analysis to compare all configured models.
          </p>
        </div>
      )}

      {/* Summary cards: one per model + ensemble */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.model_name} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-slate-500 font-mono truncate" title={s.model_name}>
                {s.model_name}
              </h3>
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: getModelColor(reportingModels, s.model_name) }}
              />
            </div>
            <p className="text-3xl font-bold text-slate-900">
              {formatScore(s.average_score)}
              <span className="text-lg text-slate-400">/5</span>
            </p>
            <div className="mt-3 flex h-1.5 w-full rounded-full overflow-hidden">
              <div style={{ width: `${s.positive_pct}%` }} className="bg-green-500" />
              <div style={{ width: `${s.neutral_pct}%` }} className="bg-yellow-400" />
              <div style={{ width: `${s.negative_pct}%` }} className="bg-red-500" />
            </div>
            <p className="text-xs text-slate-500 mt-2">
              {s.analyzed_reviews} analysed · {formatMs(s.avg_processing_time_ms)} avg
            </p>
            {(s.failed_reviews > 0 || s.unavailable_reviews > 0) && (
              <p className="text-xs text-red-600 mt-1">
                {s.unavailable_reviews > 0
                  ? `${s.model_name} unavailable for ${s.unavailable_reviews} review(s)`
                  : `${s.failed_reviews} failed`}
              </p>
            )}
          </div>
        ))}

        <div className="bg-slate-900 p-5 rounded-xl border border-slate-900 shadow-sm text-white">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Overall Ensemble Score</h3>
          <p className="text-3xl font-bold">
            {formatScore(data.ensemble_score)}
            <span className="text-lg text-slate-400">/5</span>
          </p>
          <p className="text-xs text-slate-300 mt-3 capitalize">
            {data.ensemble_sentiment ?? 'n/a'} · agreement index{' '}
            {formatPercent(agreement.agreement_index * 100)}
          </p>
          <p className="text-xs text-slate-400 mt-1">Average of every model score per review</p>
        </div>
      </div>

      {stats.length === 0 ? (
        <div className="bg-white p-12 rounded-xl border border-slate-200 shadow-sm text-center">
          <Layers size={48} className="mx-auto text-slate-300 mb-4" />
          <h3 className="text-lg font-medium text-slate-900">No model results yet</h3>
          <p className="mt-2 text-slate-500">Run the AI analysis for this dataset first.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Average score by model */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-900 mb-4">Average Sentiment Score by Model</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={avgScoreData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 5]} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                    <RechartsTooltip
                      cursor={{ fill: '#f1f5f9' }}
                      formatter={(value: any) => [`${formatScore(Number(value))}/5`, 'Avg score']}
                    />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                      {avgScoreData.map((entry) => (
                        <Cell key={entry.model} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Sentiment split by model */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-900 mb-4">Sentiment Distribution by Model</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sentimentSplitData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis unit="%" domain={[0, 100]} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                    <RechartsTooltip
                      cursor={{ fill: '#f1f5f9' }}
                      formatter={(value: any) => formatPercent(Number(value))}
                    />
                    <Legend />
                    <Bar dataKey="Positive" stackId="s" fill={SENTIMENT_COLORS.positive} />
                    <Bar dataKey="Neutral" stackId="s" fill={SENTIMENT_COLORS.neutral} />
                    <Bar dataKey="Negative" stackId="s" fill={SENTIMENT_COLORS.negative} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Score distribution by model */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-900 mb-4">Score Distribution by Model</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={distributionData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="range" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                    <RechartsTooltip cursor={{ fill: '#f1f5f9' }} />
                    <Legend />
                    {stats.map((s) => (
                      <Bar
                        key={s.model_name}
                        dataKey={s.model_name}
                        fill={getModelColor(reportingModels, s.model_name)}
                        radius={[4, 4, 0, 0]}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Model agreement */}
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-semibold text-slate-900 mb-4">Model Agreement</h3>
              <div className="h-64">
                {agreementData.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center pt-16">No agreement data yet.</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={agreementData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {agreementData.map((entry) => (
                          <Cell key={entry.name} fill={AGREEMENT_COLORS[entry.name] ?? '#94a3b8'} />
                        ))}
                      </Pie>
                      <RechartsTooltip formatter={(value: any) => [`${Number(value)} reviews`, 'Reviews']} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-500 border-t border-slate-100 pt-4">
                <div>
                  <p className="text-lg font-semibold text-green-600">{formatPercent(agreement.high_pct)}</p>
                  High
                </div>
                <div>
                  <p className="text-lg font-semibold text-yellow-500">{formatPercent(agreement.moderate_pct)}</p>
                  Moderate
                </div>
                <div>
                  <p className="text-lg font-semibold text-red-500">{formatPercent(agreement.low_pct)}</p>
                  Low
                </div>
              </div>
            </div>
          </div>

          {/* Review-level score comparison */}
          {reviewSeries.length > 0 && (
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="font-semibold text-slate-900">Review-Level Score Comparison</h3>
                <p className="text-xs text-slate-500">
                  First {reviewSeries.length} analysed review{reviewSeries.length === 1 ? '' : 's'}
                </p>
              </div>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={reviewSeries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 5]} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                    <RechartsTooltip
                      formatter={(value: any, name: any) => [formatScore(Number(value)), String(name)]}
                      labelFormatter={(label: any, payload: any) =>
                        payload?.[0]?.payload?.excerpt
                          ? `${label} — "${payload[0].payload.excerpt}"`
                          : String(label ?? '')
                      }
                    />
                    <Legend />
                    {reportingModels.map((model) => (
                      <Line
                        key={model}
                        type="monotone"
                        dataKey={model}
                        stroke={getModelColor(reportingModels, model)}
                        strokeWidth={2}
                        dot={{ r: 2 }}
                        connectNulls
                      />
                    ))}
                    <Line
                      type="monotone"
                      dataKey="Ensemble"
                      stroke={ENSEMBLE_COLOR}
                      strokeWidth={2}
                      strokeDasharray="5 4"
                      dot={false}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Per-model statistics table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <h3 className="font-semibold text-slate-900">Per-Model Statistics</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Model</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Reviews</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Avg Score</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Pos / Neu / Neg</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Avg Time</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Agrees With Others</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Failures</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {stats.map((s) => (
                    <tr key={s.model_name} className="hover:bg-slate-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900 font-mono">
                        <span className="inline-flex items-center">
                          <span
                            className="h-2.5 w-2.5 rounded-full mr-2"
                            style={{ backgroundColor: getModelColor(reportingModels, s.model_name) }}
                          />
                          {s.model_name}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-center">{s.analyzed_reviews}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-900 text-center">{formatScore(s.average_score)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-center">
                        {formatPercent(s.positive_pct)} / {formatPercent(s.neutral_pct)} / {formatPercent(s.negative_pct)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-center">{formatMs(s.avg_processing_time_ms)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-center">
                        {s.agreement_with_others_pct === null || s.agreement_with_others_pct === undefined
                          ? '—'
                          : formatPercent(s.agreement_with_others_pct)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                        {s.failed_reviews === 0 && s.unavailable_reviews === 0 ? (
                          <span className="text-slate-400">None</span>
                        ) : (
                          <span className="text-red-600" title={Object.entries(s.error_types).map(([k, v]) => `${k}: ${v}`).join(', ')}>
                            {s.failed_reviews + s.unavailable_reviews}
                            {s.unavailable_reviews > 0 ? ' (unavailable)' : ''}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pairwise agreement */}
          {data.pairwise_agreement.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200">
                <h3 className="font-semibold text-slate-900">Pairwise Sentiment Agreement</h3>
              </div>
              <div className="divide-y divide-slate-100">
                {data.pairwise_agreement.map((pair) => (
                  <div key={`${pair.model_a}-${pair.model_b}`} className="px-6 py-4 flex items-center gap-4">
                    <div className="w-full md:w-1/3 text-sm font-mono text-slate-700">
                      {pair.model_a} <span className="text-slate-400">vs</span> {pair.model_b}
                    </div>
                    <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className="bg-primary-500 h-2" style={{ width: `${pair.agreement_pct}%` }} />
                    </div>
                    <div className="text-sm font-semibold text-slate-900 w-20 text-right">
                      {formatPercent(pair.agreement_pct)}
                    </div>
                    <div className="hidden md:block text-xs text-slate-400 w-28 text-right">
                      {pair.agreed_reviews}/{pair.compared_reviews} reviews
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Review-level table */}
          {data.review_comparisons.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200">
                <h3 className="font-semibold text-slate-900">Review-Level Model Comparison</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider w-1/3">Review</th>
                      {reportingModels.map((model) => (
                        <th key={model} className="px-4 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider font-mono">
                          {shortModelName(model)}
                        </th>
                      ))}
                      <th className="px-4 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Ensemble</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Range</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Agreement</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-slate-200">
                    {data.review_comparisons.map((rc) => (
                      <tr key={rc.review_id} className="hover:bg-slate-50">
                        <td className="px-6 py-4 text-sm text-slate-600">
                          <span className="line-clamp-2">"{rc.review_excerpt}"</span>
                          {rc.product_name && (
                            <span className="block text-xs text-slate-400 mt-1 line-clamp-1">{rc.product_name}</span>
                          )}
                        </td>
                        {reportingModels.map((model) => {
                          const score = rc.model_scores[model];
                          const sentiment = rc.model_sentiments[model];
                          return (
                            <td key={model} className="px-4 py-4 text-center whitespace-nowrap">
                              {score === undefined ? (
                                <span className="text-xs text-red-500">
                                  {rc.models_failed.includes(model) ? 'unavailable' : '—'}
                                </span>
                              ) : (
                                <div className="flex flex-col items-center">
                                  <span className="text-sm font-semibold text-slate-900">{formatScore(score)}</span>
                                  <span className={`mt-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${getSentimentColor(sentiment)}`}>
                                    {sentiment}
                                  </span>
                                </div>
                              )}
                            </td>
                          );
                        })}
                        <td className="px-4 py-4 text-center whitespace-nowrap">
                          <span className="text-sm font-bold text-slate-900">{formatScore(rc.ensemble_score)}</span>
                          <span className="block text-[10px] text-slate-400 uppercase mt-1">{rc.ensemble_sentiment}</span>
                        </td>
                        <td className="px-4 py-4 text-center whitespace-nowrap text-sm text-slate-500">
                          {rc.score_range === null || rc.score_range === undefined ? '—' : formatScore(rc.score_range)}
                        </td>
                        <td className="px-4 py-4 text-center whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded-md text-xs font-medium border ${getAgreementColor(rc.agreement_level)}`}>
                            {getAgreementLabel(rc.agreement_level)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500">
                Showing up to {data.review_comparisons_limit} reviews. Use the Reviews page to inspect
                any individual review's per-model analysis.
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
