import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { analyticsService } from '../services/analytics';
import { AnalyticsResponse } from '../types/analytics';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { ArrowLeft, ChevronDown, ChevronUp, Layers, TrendingUp, TrendingDown } from 'lucide-react';
import { formatScore } from '../utils/formatters';

const COLORS = {
  positive: '#10b981', // emerald-500
  neutral: '#f59e0b',  // amber-500
  negative: '#ef4444'  // red-500
};

export default function ProductAnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [expandedProduct, setExpandedProduct] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    analyticsService.get(id).then(res => {
      setData(res);
      setLoading(false);
    }).catch(err => {
      setError('Analytics not available. Has the dataset finished processing?');
      setLoading(false);
    });
  }, [id]);

  if (loading) return <div className="p-8 text-center text-slate-500">Loading analytics...</div>;
  if (error || !data) return <div className="p-8 text-center text-red-500">{error}</div>;

  const sentimentData = [
    { name: 'Positive', value: data.sentiment_counts.positive, color: COLORS.positive },
    { name: 'Neutral', value: data.sentiment_counts.neutral, color: COLORS.neutral },
    { name: 'Negative', value: data.sentiment_counts.negative, color: COLORS.negative },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div className="flex items-center space-x-4">
          <Link to={`/datasets/${id}`} className="p-2 text-slate-500 hover:text-slate-800 bg-white rounded-lg border border-slate-200">
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Dataset Analytics</h1>
            <p className="text-slate-500">AI-generated insights from {data.completed_reviews} reviews.</p>
          </div>
        </div>
        <Link
          to={`/datasets/${id}/model-comparison`}
          className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
        >
          <Layers size={18} className="mr-2" />
          Multi-Model Comparison
        </Link>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Average Sentiment Score</h3>
          <p className="text-3xl font-bold text-primary-600">{formatScore(data.average_ai_score)}<span className="text-lg text-slate-400">/5</span></p>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Positive Reviews</h3>
          <p className="text-3xl font-bold text-green-600">{data.sentiment_percentages.positive.toFixed(1)}%</p>
          <p className="text-xs text-slate-400 mt-1">{data.sentiment_counts.positive} count</p>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Neutral Reviews</h3>
          <p className="text-3xl font-bold text-yellow-500">{data.sentiment_percentages.neutral.toFixed(1)}%</p>
          <p className="text-xs text-slate-400 mt-1">{data.sentiment_counts.neutral} count</p>
        </div>
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Negative Reviews</h3>
          <p className="text-3xl font-bold text-red-500">{data.sentiment_percentages.negative.toFixed(1)}%</p>
          <p className="text-xs text-slate-400 mt-1">{data.sentiment_counts.negative} count</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment Distribution Pie Chart */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-semibold text-slate-900 mb-4">Sentiment Overview</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={sentimentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {sentimentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <RechartsTooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Score Distribution Bar Chart */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-semibold text-slate-900 mb-4">Score Distribution</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.score_distribution} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="range" tick={{fontSize: 12}} tickLine={false} axisLine={false} />
                <YAxis tick={{fontSize: 12}} tickLine={false} axisLine={false} />
                <RechartsTooltip cursor={{fill: '#f1f5f9'}} />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Keywords */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-slate-200">
            <h3 className="font-semibold text-slate-900 flex items-center"><TrendingUp className="mr-2 text-green-500" size={18} /> Top Positive Keywords</h3>
          </div>
          <div className="p-6 flex-1 flex flex-wrap gap-2 content-start">
            {data.top_positive_keywords.length > 0 ? data.top_positive_keywords.map((kw, idx) => (
              <div key={idx} className="bg-green-50 border border-green-100 text-green-700 px-3 py-1.5 rounded-lg text-sm flex items-center">
                {kw.keyword} <span className="ml-2 bg-green-200 text-green-800 text-xs py-0.5 px-1.5 rounded-md">{kw.count}</span>
              </div>
            )) : <p className="text-sm text-slate-500 w-full text-center">No keywords detected.</p>}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-slate-200">
            <h3 className="font-semibold text-slate-900 flex items-center"><TrendingDown className="mr-2 text-red-500" size={18} /> Top Negative Keywords</h3>
          </div>
          <div className="p-6 flex-1 flex flex-wrap gap-2 content-start">
            {data.top_negative_keywords.length > 0 ? data.top_negative_keywords.map((kw, idx) => (
              <div key={idx} className="bg-red-50 border border-red-100 text-red-700 px-3 py-1.5 rounded-lg text-sm flex items-center">
                {kw.keyword} <span className="ml-2 bg-red-200 text-red-800 text-xs py-0.5 px-1.5 rounded-md">{kw.count}</span>
              </div>
            )) : <p className="text-sm text-slate-500 w-full text-center">No keywords detected.</p>}
          </div>
        </div>
      </div>

      {/* Product Table */}
      {data.products.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200">
            <h3 className="font-semibold text-slate-900">Product Analysis</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Product Name</th>
                  <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Total Reviews</th>
                  <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Avg Score</th>
                  <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Sentiment Breakdown</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {data.products.map((product, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                      {product.product_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 text-center">
                      {product.total_reviews}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-900 text-center">
                      {formatScore(product.avg_score)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap w-1/4">
                      <div className="flex h-2 w-full rounded-full overflow-hidden">
                        <div style={{ width: `${product.positive_pct}%` }} className="bg-green-500" title={`Positive: ${product.positive_pct.toFixed(1)}%`}></div>
                        <div style={{ width: `${product.neutral_pct}%` }} className="bg-yellow-400" title={`Neutral: ${product.neutral_pct.toFixed(1)}%`}></div>
                        <div style={{ width: `${product.negative_pct}%` }} className="bg-red-500" title={`Negative: ${product.negative_pct.toFixed(1)}%`}></div>
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                        <span>{product.positive_pct.toFixed(0)}%</span>
                        <span>{product.neutral_pct.toFixed(0)}%</span>
                        <span>{product.negative_pct.toFixed(0)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
