import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import {
  Upload,
  TrendingUp,
  Brain,
  Play,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  Database,
  BarChart2,
  Clock,
} from 'lucide-react';
import { forecastingService } from '../services/forecasting';
import { datasetService } from '../services/datasets';
import {
  SalesDatasetMeta,
  ForecastRunDetail,
  ForecastRunSummary,
  ForecastMetrics,
} from '../types/forecasting';
import { Dataset } from '../types/dataset';

/* ── helpers ── */
const fmt = (v: number | null | undefined, dp = 2): string =>
  v == null ? '—' : v.toFixed(dp);

function MetricBadge({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3 text-center border border-slate-200">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-lg font-bold text-slate-900">{fmt(value)}</p>
    </div>
  );
}

function MetricsRow({ metrics, label }: { metrics?: ForecastMetrics; label: string }) {
  if (!metrics) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">{label}</p>
      <div className="grid grid-cols-3 gap-2">
        <MetricBadge label="MAE" value={metrics.mae} />
        <MetricBadge label="RMSE" value={metrics.rmse} />
        <MetricBadge label="MAPE (%)" value={metrics.mape} />
      </div>
    </div>
  );
}

/* ── Steps ── */
const STEPS = ['Upload Sales', 'Configure', 'Build Index', 'Train & Forecast', 'Results'];

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((s, i) => (
        <React.Fragment key={s}>
          <div className={`flex items-center gap-2 ${i <= current ? 'opacity-100' : 'opacity-40'}`}>
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                ${i < current ? 'bg-primary-600 text-white' : i === current ? 'bg-primary-100 text-primary-700 border-2 border-primary-600' : 'bg-slate-200 text-slate-500'}`}
            >
              {i < current ? <CheckCircle size={14} /> : i + 1}
            </div>
            <span className={`text-xs font-medium hidden sm:inline ${i === current ? 'text-primary-700' : 'text-slate-500'}`}>{s}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`flex-1 h-0.5 ${i < current ? 'bg-primary-400' : 'bg-slate-200'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

/* ── Main Page ── */
export default function SalesForecastingPage() {
  const [step, setStep] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // Step 0 – Upload
  const [salesDatasets, setSalesDatasets] = useState<SalesDatasetMeta[]>([]);
  const [selectedSalesDataset, setSelectedSalesDataset] = useState<SalesDatasetMeta | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // Step 1 – Configure
  const [reviewDatasets, setReviewDatasets] = useState<Dataset[]>([]);
  const [selectedReviewDatasetId, setSelectedReviewDatasetId] = useState('');
  const [selectedProduct, setSelectedProduct] = useState('');
  const [forecastHorizon, setForecastHorizon] = useState(7);
  const [testFraction, setTestFraction] = useState(0.20);

  // Step 2 – Build sentiment index
  const [sentimentBuilt, setSentimentBuilt] = useState(false);
  const [sentimentCount, setSentimentCount] = useState(0);

  // Step 3 – Training
  const [trainingRun, setTrainingRun] = useState<ForecastRunDetail | null>(null);

  // Past runs
  const [pastRuns, setPastRuns] = useState<ForecastRunSummary[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [selectedPastRun, setSelectedPastRun] = useState<ForecastRunDetail | null>(null);

  // Load initial data
  useEffect(() => {
    Promise.all([
      forecastingService.listSalesDatasets(),
      datasetService.list(),
      forecastingService.listRuns(),
    ]).then(([sales, ds, runs]) => {
      setSalesDatasets(sales);
      setReviewDatasets(ds.datasets.filter((d: Dataset) => d.status === 'completed'));
      setPastRuns(runs);
      setLoadingRuns(false);
    }).catch(() => setLoadingRuns(false));
  }, []);

  const handleUpload = useCallback(async () => {
    if (!uploadFile) return;
    setBusy(true);
    setError('');
    try {
      const meta = await forecastingService.uploadSales(uploadFile);
      setSalesDatasets(prev => [meta, ...prev]);
      setSelectedSalesDataset(meta);
      setStep(1);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Upload failed.');
    } finally {
      setBusy(false);
    }
  }, [uploadFile]);

  const handleBuildSentiment = useCallback(async () => {
    if (!selectedReviewDatasetId) return;
    setBusy(true);
    setError('');
    try {
      const records = await forecastingService.buildSentimentIndex(
        selectedReviewDatasetId,
        selectedProduct || undefined,
      );
      setSentimentBuilt(true);
      setSentimentCount(records.length);
      setStep(3);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Building sentiment index failed.');
    } finally {
      setBusy(false);
    }
  }, [selectedReviewDatasetId, selectedProduct]);

  const handleTrain = useCallback(async () => {
    if (!selectedSalesDataset || !selectedProduct) return;
    setBusy(true);
    setError('');
    try {
      const run = await forecastingService.train({
        sales_dataset_id: selectedSalesDataset.sales_dataset_id,
        review_dataset_id: selectedReviewDatasetId || 'none',
        product_name: selectedProduct,
        forecast_horizon: forecastHorizon,
        test_fraction: testFraction,
      });
      setTrainingRun(run);
      forecastingService.listRuns().then(setPastRuns);
      setStep(4);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Training failed.');
    } finally {
      setBusy(false);
    }
  }, [selectedSalesDataset, selectedReviewDatasetId, selectedProduct, forecastHorizon, testFraction]);

  const viewPastRun = useCallback(async (runId: string) => {
    setBusy(true);
    try {
      const detail = await forecastingService.getRun(runId);
      setSelectedPastRun(detail);
      setTrainingRun(detail);
      setStep(4);
    } catch (e: any) {
      setError('Could not load run.');
    } finally {
      setBusy(false);
    }
  }, []);

  /* ── Chart data builder ── */
  const buildChartData = (run: ForecastRunDetail) => {
    const points: Record<string, string | number | null | undefined>[] = [];

    run.actual_dates.forEach((d, i) => {
      points.push({ date: d, actual: run.actual_values[i] });
    });

    // overlay test predictions on the chart
    run.test_dates.forEach((d, i) => {
      const existing = points.find(p => p.date === d);
      if (existing) {
        existing.sarima_test = run.sarima?.test_predictions?.[i] ?? null;
        existing.sarimax_test = run.sarimax?.test_predictions?.[i] ?? null;
      }
    });

    // future forecast
    run.future_dates.forEach((d, i) => {
      points.push({
        date: d,
        sarima_forecast: run.sarima?.forecast?.[i] ?? null,
        sarimax_forecast: run.sarimax?.forecast?.[i] ?? null,
      });
    });

    return points;
  };

  const activeRun = trainingRun;
  const chartData = activeRun ? buildChartData(activeRun) : [];
  const splitDate = activeRun?.test_dates?.[0];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <TrendingUp className="text-primary-600" size={26} />
            Sales Forecasting
          </h1>
          <p className="text-slate-500 mt-1">
            SARIMA &amp; SARIMAX models powered by LLM sentiment signals
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          <AlertCircle size={18} className="shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Step Indicator */}
      <StepIndicator current={step} />

      {/* ── Step 0: Upload / Select Sales Dataset ── */}
      {step === 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2">
              <Upload size={18} className="text-primary-600" /> Upload New Sales CSV
            </h2>
            <p className="text-sm text-slate-500">
              Required columns: <code className="bg-slate-100 px-1 rounded">date</code>,{' '}
              <code className="bg-slate-100 px-1 rounded">product_name</code>,{' '}
              <code className="bg-slate-100 px-1 rounded">units_sold</code>
            </p>
            <label className="block">
              <div className="border-2 border-dashed border-slate-200 rounded-lg p-6 text-center hover:border-primary-400 transition cursor-pointer">
                <Upload size={24} className="mx-auto text-slate-400 mb-2" />
                <span className="text-sm text-slate-600">
                  {uploadFile ? uploadFile.name : 'Click or drag to upload CSV'}
                </span>
              </div>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={e => setUploadFile(e.target.files?.[0] || null)}
              />
            </label>
            <button
              onClick={handleUpload}
              disabled={!uploadFile || busy}
              className="w-full py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 font-medium"
            >
              {busy ? 'Uploading...' : 'Upload & Continue'}
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2">
              <Database size={18} className="text-primary-600" /> Select Existing Dataset
            </h2>
            {salesDatasets.length === 0 ? (
              <p className="text-sm text-slate-500">No sales datasets uploaded yet.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {salesDatasets.map(ds => (
                  <button
                    key={ds.sales_dataset_id}
                    onClick={() => { setSelectedSalesDataset(ds); setStep(1); }}
                    className="w-full text-left p-3 rounded-lg border border-slate-200 hover:border-primary-400 hover:bg-primary-50 transition"
                  >
                    <p className="text-sm font-medium text-slate-900">{ds.filename}</p>
                    <p className="text-xs text-slate-500">
                      {ds.total_rows} rows · {ds.products.length} products ·{' '}
                      {ds.date_range_start} → {ds.date_range_end}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Step 1: Configure ── */}
      {step === 1 && selectedSalesDataset && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <BarChart2 size={18} className="text-primary-600" /> Configure Forecast
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Review Dataset (AI Analysis Source)
              </label>
              <select
                value={selectedReviewDatasetId}
                onChange={e => setSelectedReviewDatasetId(e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              >
                <option value="none">None (SARIMA Baseline Only)</option>
                {reviewDatasets.map(d => (
                  <option key={d.id} value={d.id}>{d.filename}</option>
                ))}
              </select>
              {reviewDatasets.length === 0 && (
                <p className="text-xs text-amber-600 mt-1">
                  No completed review datasets found. Using SARIMA baseline mode.
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Product Name</label>
              <select
                value={selectedProduct}
                onChange={e => setSelectedProduct(e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              >
                <option value="">— Select product —</option>
                {selectedSalesDataset.products.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Forecast Horizon (days): {forecastHorizon}
              </label>
              <input
                type="range" min={7} max={90} step={1}
                value={forecastHorizon}
                onChange={e => setForecastHorizon(Number(e.target.value))}
                className="w-full accent-primary-600"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Test Set Size: {Math.round(testFraction * 100)}%
              </label>
              <input
                type="range" min={0.20} max={0.30} step={0.05}
                value={testFraction}
                onChange={e => setTestFraction(Number(e.target.value))}
                className="w-full accent-primary-600"
              />
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep(0)} className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50">
              Back
            </button>
            <button
              onClick={() => setStep(selectedReviewDatasetId && selectedReviewDatasetId !== 'none' ? 2 : 3)}
              disabled={!selectedProduct}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 font-medium"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Build Sentiment Index ── */}
      {step === 2 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Brain size={18} className="text-primary-600" /> Build Sentiment Index
          </h2>
          <p className="text-sm text-slate-600">
            Aggregate LLM sentiment scores from the selected review dataset into a daily index per
            product. This becomes the exogenous variable for SARIMAX.
          </p>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            <strong>Note:</strong> Your reviews CSV must include a{' '}
            <code className="bg-amber-100 px-1 rounded">review_date</code> column for this step to
            produce results. If it's missing, SARIMA will still train without sentiment data.
          </div>
          <div className="flex gap-3">
            <button onClick={() => setStep(1)} className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50">
              Back
            </button>
            <button
              onClick={handleBuildSentiment}
              disabled={busy}
              className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 font-medium"
            >
              <Brain size={16} className="mr-2" />
              {busy ? 'Building...' : 'Build Sentiment Index'}
            </button>
            <button
              onClick={() => setStep(3)}
              className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
            >
              Skip (SARIMA only)
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Train ── */}
      {step === 3 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Play size={18} className="text-primary-600" /> Train Models
          </h2>

          {sentimentBuilt && (
            <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
              <CheckCircle size={16} />
              Sentiment index built: {sentimentCount} daily records ready for SARIMAX.
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <p className="text-xs text-slate-500 mb-1">Sales Dataset</p>
              <p className="font-medium text-slate-900">{selectedSalesDataset?.filename}</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <p className="text-xs text-slate-500 mb-1">Product</p>
              <p className="font-medium text-slate-900">{selectedProduct || 'All'}</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <p className="text-xs text-slate-500 mb-1">Forecast Horizon</p>
              <p className="font-medium text-slate-900">{forecastHorizon} days</p>
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep(selectedReviewDatasetId && selectedReviewDatasetId !== 'none' ? 2 : 1)} className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50">
              Back
            </button>
            <button
              onClick={handleTrain}
              disabled={busy || !selectedSalesDataset || !selectedProduct}
              className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 font-medium"
            >
              <Play size={16} className="mr-2" />
              {busy ? 'Training (may take a moment)...' : 'Train Model'}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 4: Results ── */}
      {step === 4 && activeRun && (
        <div className="space-y-6">
          {/* Summary row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Product</p>
              <p className="text-sm font-semibold text-slate-900 truncate">{activeRun.product_name}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Training Points</p>
              <p className="text-2xl font-bold text-slate-900">{activeRun.n_train}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Test Points</p>
              <p className="text-2xl font-bold text-slate-900">{activeRun.n_test}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Forecast Horizon</p>
              <p className="text-2xl font-bold text-slate-900">{activeRun.forecast_horizon}d</p>
            </div>
          </div>

          {/* Chart */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="font-semibold text-slate-900 mb-4">
              Units Sold — Actual vs Predicted vs Forecast
            </h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                  <RechartsTooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    formatter={(v: any) => (v != null ? Number(v).toFixed(1) : '—')}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {splitDate && (
                    <ReferenceLine x={splitDate} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'Test Start', fontSize: 10, fill: '#f59e0b' }} />
                  )}
                  <Line type="monotone" dataKey="actual" stroke="#64748b" strokeWidth={1.5} dot={false} name="Actual" />
                  <Line type="monotone" dataKey="sarima_test" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="SARIMA (test)" strokeDasharray="4 2" />
                  {activeRun.sarimax && (
                    <Line type="monotone" dataKey="sarimax_test" stroke="#8b5cf6" strokeWidth={1.5} dot={false} name="SARIMAX (test)" strokeDasharray="4 2" />
                  )}
                  <Line type="monotone" dataKey="sarima_forecast" stroke="#3b82f6" strokeWidth={2} dot={false} name="SARIMA Forecast" />
                  {activeRun.sarimax && (
                    <Line type="monotone" dataKey="sarimax_forecast" stroke="#8b5cf6" strokeWidth={2} dot={false} name="SARIMAX Forecast" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Model Comparison Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900">Model Comparison — Test Set Metrics</h3>
                <p className="text-xs text-slate-500 mt-0.5">Lower is better for all metrics.</p>
              </div>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                Selected Best Model: {activeRun.best_model || 'SARIMA'}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {['Model', 'MAE', 'RMSE', 'MAPE (%)'].map(h => (
                      <th key={h} className={`px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider ${h === 'Model' ? 'text-left' : 'text-right'}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {activeRun.sarima && (
                    <tr>
                      <td className="px-6 py-4 text-sm font-mono font-medium text-slate-900">SARIMA</td>
                      <td className="px-6 py-4 text-sm text-slate-700 text-right">{fmt(activeRun.sarima.test_metrics.mae)}</td>
                      <td className="px-6 py-4 text-sm text-slate-700 text-right">{fmt(activeRun.sarima.test_metrics.rmse)}</td>
                      <td className="px-6 py-4 text-sm text-slate-700 text-right">{fmt(activeRun.sarima.test_metrics.mape)}</td>
                    </tr>
                  )}
                  {activeRun.sarimax && (
                    <tr className="bg-purple-50/40">
                      <td className="px-6 py-4 text-sm font-mono font-medium text-purple-900">SARIMAX + Sentiment</td>
                      <td className="px-6 py-4 text-sm text-slate-700 text-right">{fmt(activeRun.sarimax.test_metrics.mae)}</td>
                      <td className="px-6 py-4 text-sm text-slate-700 text-right">{fmt(activeRun.sarimax.test_metrics.rmse)}</td>
                      <td className="px-6 py-4 text-sm text-slate-700 text-right">{fmt(activeRun.sarimax.test_metrics.mape)}</td>
                    </tr>
                  )}
                  {!activeRun.sarimax && (
                    <tr>
                      <td colSpan={4} className="px-6 py-3 text-xs text-slate-400 italic">
                        SARIMAX not trained — no daily sentiment index available for this product.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <button
            onClick={() => { setStep(0); setTrainingRun(null); setSelectedPastRun(null); }}
            className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
          >
            Start New Forecast
          </button>
        </div>
      )}

      {/* ── Past Runs ── */}
      {pastRuns.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200">
            <h3 className="font-semibold text-slate-900 flex items-center gap-2">
              <Clock size={16} className="text-slate-400" /> Past Forecasting Runs
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {['Product', 'Train', 'Test', 'SARIMA RMSE', 'SARIMAX RMSE', 'Sentiment', 'Date', ''].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {pastRuns.map(run => (
                  <tr key={run.run_id} className="hover:bg-slate-50 cursor-pointer" onClick={() => viewPastRun(run.run_id)}>
                    <td className="px-4 py-3 text-sm font-medium text-slate-900">{run.product_name}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{run.n_train}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{run.n_test}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{fmt(run.sarima_test_metrics?.rmse)}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{fmt(run.sarimax_test_metrics?.rmse)}</td>
                    <td className="px-4 py-3">
                      {run.has_sentiment
                        ? <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">Yes</span>
                        : <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">No</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{new Date(run.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-xs text-primary-600 hover:underline font-medium">View</td>
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
