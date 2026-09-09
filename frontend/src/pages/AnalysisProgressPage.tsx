import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { jobService } from '../services/jobs';
import { JobStatusResponse } from '../types/job';
import { Loader2, CheckCircle2, AlertTriangle, ArrowRight, Square } from 'lucide-react';
import { formatPercent } from '../utils/formatters';

export default function AnalysisProgressPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState('');
  const [stopping, setStopping] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;

    let intervalId: ReturnType<typeof setInterval>;

    const fetchStatus = async () => {
      try {
        const data = await jobService.getStatus(id);
        setJob(data);

        // Stop polling if completed, failed, or stopped
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped' || data.status === 'cancelled') {
          clearInterval(intervalId);
        }
      } catch (err) {
        setError('Failed to fetch job status.');
        clearInterval(intervalId);
      }
    };

    fetchStatus();
    // Poll every 3 seconds
    intervalId = setInterval(fetchStatus, 3000);

    return () => clearInterval(intervalId);
  }, [id]);

  const handleStopAnalysis = async () => {
    if (!id || stopping) return;
    setStopping(true);
    try {
      const updated = await jobService.stop(id);
      setJob(updated);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to stop analysis.');
    } finally {
      setStopping(false);
    }
  };

  if (error) return <div className="p-8 text-center text-red-500">{error}</div>;
  if (!job) return <div className="p-8 text-center text-slate-500">Loading job status...</div>;

  const isRunning = job.status === 'running' || job.status === 'pending';
  const isCompleted = job.status === 'completed';
  const isStopped = job.status === 'stopped' || job.status === 'cancelled';

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Analysis Progress</h1>
          <p className="text-slate-500 mt-1">Local LLM is analyzing your reviews in the background.</p>
        </div>
        {isRunning && (
          <button
            onClick={handleStopAnalysis}
            disabled={stopping}
            className="flex items-center px-4 py-2 bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 transition text-sm font-semibold disabled:opacity-50 shadow-sm"
          >
            <Square size={16} className="mr-2 fill-current" />
            {stopping ? 'Stopping...' : 'Stop Analysis'}
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-slate-700">
            {job.status === 'completed' ? 'Analysis Complete' :
             job.status === 'running' ? 'Analyzing...' :
             job.status === 'pending' ? 'Starting...' :
             isStopped ? 'Analysis Stopped' : 'Failed'}
          </span>
          <span className="text-sm font-medium text-slate-900">{formatPercent(job.progress_percent)}</span>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-100 rounded-full h-4 mb-6 overflow-hidden">
          <div
            className={`h-4 rounded-full transition-all duration-500 ${
              isCompleted ? 'bg-green-500' : isStopped ? 'bg-amber-500' : job.status === 'failed' ? 'bg-red-500' : 'bg-primary-500'
            }`}
            style={{ width: `${job.progress_percent}%` }}
          ></div>
        </div>

        <div className="grid grid-cols-3 gap-4 text-center mb-8 border-y border-slate-100 py-6">
          <div>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">Total</p>
            <p className="text-2xl font-semibold text-slate-900">{job.total}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">Processed</p>
            <p className="text-2xl font-semibold text-primary-600">{job.processed}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">Failed</p>
            <p className="text-2xl font-semibold text-red-600">{job.failed}</p>
          </div>
        </div>

        {isRunning && (
          <div className="flex flex-col md:flex-row items-center justify-between text-primary-600 bg-primary-50 p-4 rounded-lg gap-4">
            <div className="flex items-center">
              <Loader2 className="animate-spin mr-3 shrink-0" size={24} />
              <span className="font-medium text-sm">
                {job.models && job.models.length > 1
                  ? `Each review is being analysed by ${job.models.length} models.`
                  : 'Processing reviews with the local LLM. You can leave this page or stop anytime.'}
              </span>
            </div>
            <button
              onClick={handleStopAnalysis}
              disabled={stopping}
              className="px-3 py-1.5 bg-red-600 text-white rounded-md hover:bg-red-700 transition text-xs font-semibold shrink-0 disabled:opacity-50"
            >
              {stopping ? 'Stopping...' : 'Stop Analysis'}
            </button>
          </div>
        )}

        {/* Per-model progress */}
        {job.models && job.models.length > 0 && (
          <div className="mt-6 border-t border-slate-100 pt-6">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Models</h3>
            <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
              {job.models.map((model) => {
                const counters = job.model_stats?.[model];
                const unavailable = job.models_unavailable?.includes(model);
                return (
                  <div key={model} className="px-4 py-3 flex items-center justify-between bg-white text-sm">
                    <span className="font-mono text-slate-800 truncate">{model}</span>
                    {unavailable ? (
                      <span className="inline-flex items-center text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full whitespace-nowrap">
                        <AlertTriangle size={12} className="mr-1" /> Not installed — skipped
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500 whitespace-nowrap">
                        <span className="text-green-600 font-medium">{counters?.success ?? 0}</span> ok
                        {(counters?.failed ?? 0) > 0 && (
                          <>
                            {' · '}
                            <span className="text-red-600 font-medium">{counters?.failed}</span> failed
                          </>
                        )}
                        {(counters?.unavailable ?? 0) > 0 && (
                          <>
                            {' · '}
                            <span className="text-amber-600 font-medium">{counters?.unavailable}</span> unavailable
                          </>
                        )}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-slate-500 mt-2">
              A review counts as analysed when at least one model succeeds, so a single failing model
              never fails the dataset.
            </p>
          </div>
        )}

        {isCompleted && (
          <div className="flex flex-col items-center justify-center space-y-4 mt-6">
            <div className="flex items-center justify-center text-green-600 bg-green-50 p-4 rounded-lg w-full">
              <CheckCircle2 className="mr-3" size={24} />
              <span className="font-medium">Analysis finished successfully!</span>
            </div>

            <Link
              to={`/datasets/${job.dataset_id}/products`}
              className="flex items-center px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition w-full justify-center font-medium"
            >
              View Analytics &amp; AI Recommendation <ArrowRight className="ml-2" size={18} />
            </Link>

            <Link
              to={`/datasets/${job.dataset_id}/model-comparison`}
              className="flex items-center px-6 py-3 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition w-full justify-center font-medium"
            >
              Compare Models <ArrowRight className="ml-2" size={18} />
            </Link>
          </div>
        )}

        {isStopped && (
          <div className="flex flex-col items-center justify-center space-y-4 mt-6">
            <div className="flex items-start text-amber-800 bg-amber-50 border border-amber-200 p-4 rounded-lg w-full">
              <AlertTriangle className="mr-3 shrink-0 mt-0.5 text-amber-600" size={20} />
              <div>
                <span className="font-semibold block text-base">Analysis Stopped</span>
                <span className="text-sm mt-1 block">
                  Analysis was stopped by user. {job.processed} of {job.total} reviews have been analyzed. You can resume anytime from the dataset page.
                </span>
              </div>
            </div>

            <Link
              to={`/datasets/${job.dataset_id}`}
              className="flex items-center px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition w-full justify-center font-medium"
            >
              Return to Dataset to Resume <ArrowRight className="ml-2" size={18} />
            </Link>
          </div>
        )}

        {job.status === 'failed' && (
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="flex items-start text-red-700 bg-red-50 p-4 rounded-lg w-full">
              <AlertTriangle className="mr-3 shrink-0 mt-0.5" size={20} />
              <div>
                <span className="font-medium block">Analysis failed or was interrupted.</span>
                <span className="text-sm mt-1 block">{job.error_message || 'Unknown error occurred.'}</span>
              </div>
            </div>

            <Link
              to={`/datasets/${job.dataset_id}`}
              className="mt-4 flex items-center px-6 py-3 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition w-full justify-center font-medium"
            >
              Return to Dataset
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
