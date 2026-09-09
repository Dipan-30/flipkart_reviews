import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { datasetService } from '../services/datasets';
import { Dataset } from '../types/dataset';
import { Database, Play, FileText, CheckCircle2, Clock, AlertCircle, BarChart2, Layers, Square } from 'lucide-react';
import { formatPercent } from '../utils/formatters';


export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (id) {
      datasetService.get(id).then(res => {
        setDataset(res);
        setLoading(false);
      }).catch(err => {
        setError('Failed to load dataset details.');
        setLoading(false);
      });
    }
  }, [id]);

  const handleStartAnalysis = async () => {
    if (!id) return;
    setStarting(true);
    try {
      const res = await datasetService.analyze(id);
      navigate(`/jobs/${res.job_id}`);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to start analysis.');
      setStarting(false);
    }
  };

  const handleStopAnalysis = async () => {
    if (!id || stopping) return;
    setStopping(true);
    try {
      await datasetService.stop(id);
      setDataset(prev => prev ? { ...prev, status: 'stopped' } : null);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to stop analysis.');
    } finally {
      setStopping(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading dataset...</div>;
  if (!dataset) return <div className="p-8 text-center text-red-500">{error}</div>;

  const isCompleted = dataset.status === 'completed';
  const isAnalyzing = dataset.status === 'analyzing';
  const isStopped = dataset.status === 'stopped' || dataset.status === 'cancelled';
  const canAnalyze = dataset.status === 'uploaded' || isStopped || (dataset.failed_reviews > 0 && !isAnalyzing);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{dataset.filename}</h1>
          <p className="text-slate-500 mt-1 flex items-center">
            <Clock size={14} className="mr-1" /> Uploaded {new Date(dataset.created_at).toLocaleString()}
          </p>
        </div>
        
        <div className="flex flex-wrap gap-3">
          {canAnalyze && (
            <button
              onClick={handleStartAnalysis}
              disabled={starting}
              className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
            >
              <Play size={18} className="mr-2" />
              {starting ? 'Starting...' : dataset.status === 'uploaded' ? 'Start AI Analysis' : isStopped ? 'Resume AI Analysis' : 'Retry Failed Reviews'}
            </button>
          )}

          {isAnalyzing && (
            <button
              onClick={handleStopAnalysis}
              disabled={stopping}
              className="flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
            >
              <Square size={18} className="mr-2 fill-current" />
              {stopping ? 'Stopping...' : 'Stop Analysis'}
            </button>
          )}
          
          {isCompleted && (
            <Link
              to={`/datasets/${dataset.id}/products`}
              className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              <BarChart2 size={18} className="mr-2" />
              View Analytics
            </Link>
          )}

          {isCompleted && (
            <Link
              to={`/datasets/${dataset.id}/model-comparison`}
              className="flex items-center px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition"
            >
              <Layers size={18} className="mr-2" />
              Multi-Model Comparison
            </Link>
          )}

          <Link
            to={`/datasets/${dataset.id}/reviews`}
            className="flex items-center px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition"
          >
            <FileText size={18} className="mr-2" />
            View Reviews
          </Link>

          {dataset.has_ground_truth && isCompleted && (
            <Link
              to={`/datasets/${dataset.id}/evaluate`}
              className="flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition"
            >
              <CheckCircle2 size={18} className="mr-2" />
              Evaluate AI
            </Link>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-md flex items-start border border-red-200">
          <AlertCircle className="shrink-0 mr-3 mt-0.5" size={18} />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col items-center justify-center text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Status</h3>
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium
            ${dataset.status === 'completed' ? 'bg-green-100 text-green-800' : 
              dataset.status === 'analyzing' ? 'bg-blue-100 text-blue-800 animate-pulse' :
              dataset.status === 'stopped' || dataset.status === 'cancelled' ? 'bg-amber-100 text-amber-800' :
              dataset.status === 'uploaded' ? 'bg-slate-100 text-slate-800' :
              'bg-red-100 text-red-800'}`}>
            {dataset.status.toUpperCase()}
          </span>
        </div>
        
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Total Reviews</h3>
          <p className="text-3xl font-bold text-slate-900">{dataset.total_reviews}</p>
        </div>
        
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Successfully Analyzed</h3>
          <p className="text-3xl font-bold text-green-600">{dataset.successful_reviews}</p>
          <p className="text-xs text-slate-400 mt-1">{formatPercent((dataset.successful_reviews/dataset.total_reviews)*100)}</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center">
          <h3 className="text-sm font-medium text-slate-500 mb-1">Failed to Analyze</h3>
          <p className="text-3xl font-bold text-red-600">{dataset.failed_reviews}</p>
          <p className="text-xs text-slate-400 mt-1">{formatPercent((dataset.failed_reviews/dataset.total_reviews)*100)}</p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
          <Database size={20} className="mr-2 text-slate-500" />
          Detected Columns
        </h3>
        <div className="flex flex-wrap gap-2">
          {dataset.original_columns.map(col => (
            <span key={col} className="px-3 py-1 text-sm rounded-md border bg-slate-50 text-slate-600 border-slate-200">
              {col}
            </span>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-4">
          {dataset.original_columns.length} columns detected in the uploaded CSV file.
        </p>
      </div>
    </div>
  );
}
