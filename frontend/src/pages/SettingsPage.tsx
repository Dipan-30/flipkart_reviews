import React, { useEffect, useState } from 'react';
import { ollamaService, OllamaStatus } from '../services/ollama';
import { Server, CheckCircle2, AlertCircle, RefreshCw, Cpu } from 'lucide-react';

export default function SettingsPage() {
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await ollamaService.getStatus();
      setStatus(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  // Fall back to the legacy single-model shape if the backend is older.
  const models =
    status?.models ??
    (status
      ? [
          {
            name: status.model,
            available: status.model_available,
            primary: true,
            pull_command: status.model_available ? null : `ollama pull ${status.model}`,
          },
        ]
      : []);
  const missing = models.filter((m) => !m.available);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <h3 className="font-semibold text-slate-900 flex items-center">
            <Server className="mr-2 text-slate-500" size={18} />
            Local LLM Configuration (Ollama)
          </h3>
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="text-sm text-primary-600 font-medium hover:text-primary-700 flex items-center"
          >
            <RefreshCw size={14} className={`mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">Ollama Daemon Status</p>
              <p className="text-sm text-slate-500 mt-1">Is the local Ollama process reachable?</p>
            </div>
            <div>
              {loading ? (
                <div className="h-6 w-20 bg-slate-200 rounded animate-pulse"></div>
              ) : status?.available ? (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <CheckCircle2 size={14} className="mr-1" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                  <AlertCircle size={14} className="mr-1" /> Disconnected
                </span>
              )}
            </div>
          </div>

          {/* Per-model availability */}
          <div className="border-t border-slate-100 pt-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-sm font-medium text-slate-900">Configured Models</p>
                <p className="text-sm text-slate-500 mt-1">
                  Every model listed in <code className="font-mono text-xs">OLLAMA_MODELS</code> analyses each review independently.
                </p>
              </div>
              {!loading && status && (
                <span className="text-xs text-slate-500 whitespace-nowrap">
                  {status.models_available ?? (status.model_available ? 1 : 0)} of{' '}
                  {status.models_configured ?? models.length} available
                </span>
              )}
            </div>

            {loading ? (
              <div className="space-y-2">
                <div className="h-12 bg-slate-100 rounded-lg animate-pulse" />
                <div className="h-12 bg-slate-100 rounded-lg animate-pulse" />
              </div>
            ) : (
              <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
                {models.map((model) => (
                  <div key={model.name} className="px-4 py-3 flex items-center justify-between bg-white">
                    <div className="min-w-0">
                      <p className="text-sm font-mono font-medium text-slate-800 truncate">
                        {model.name}
                        {model.primary && (
                          <span className="ml-2 font-sans text-[10px] uppercase tracking-wider bg-primary-50 text-primary-700 px-1.5 py-0.5 rounded">
                            primary
                          </span>
                        )}
                      </p>
                      {model.pull_command && (
                        <p className="text-xs text-slate-500 mt-1">
                          Install with{' '}
                          <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">{model.pull_command}</code>
                        </p>
                      )}
                    </div>
                    {model.available ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 whitespace-nowrap">
                        <CheckCircle2 size={14} className="mr-1" /> Available
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 whitespace-nowrap">
                        <AlertCircle size={14} className="mr-1" /> Not Installed
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Concurrency */}
          {status?.concurrency && (
            <div className="border-t border-slate-100 pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-900 flex items-center">
                    <Cpu size={16} className="mr-2 text-slate-400" /> Processing Limits
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    Controls how many Ollama requests run at once. Raise carefully — every model
                    loaded at the same time uses additional RAM/VRAM.
                  </p>
                </div>
                <div className="text-right text-sm text-slate-700 space-y-1 whitespace-nowrap">
                  <p>
                    <span className="text-slate-500">Reviews in parallel:</span>{' '}
                    <span className="font-medium">{status.concurrency.reviews}</span>
                  </p>
                  <p>
                    <span className="text-slate-500">Models per review:</span>{' '}
                    <span className="font-medium">{status.concurrency.models_per_review}</span>
                  </p>
                  <p>
                    <span className="text-slate-500">Timeout:</span>{' '}
                    <span className="font-medium">{status.concurrency.timeout_seconds}s</span>
                  </p>
                </div>
              </div>
            </div>
          )}

          {status?.base_url && (
            <div className="border-t border-slate-100 pt-6 flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-slate-900">Ollama Base URL</p>
                <p className="text-sm text-slate-500 mt-1">Where the backend looks for Ollama.</p>
              </div>
              <span className="font-mono text-sm font-medium bg-slate-100 text-slate-800 px-3 py-1.5 rounded-md">
                {status.base_url}
              </span>
            </div>
          )}

          {!loading && (!status?.available || missing.length > 0) && (
            <div className="bg-amber-50 p-4 rounded-lg border border-amber-200 mt-4">
              <h4 className="text-amber-800 font-medium flex items-center mb-2">
                <AlertCircle size={16} className="mr-2" /> Action Required
              </h4>
              {!status?.available ? (
                <p className="text-sm text-amber-700 ml-6">
                  Ensure the Ollama application is running on your machine and the backend can reach it.
                </p>
              ) : (
                <div className="text-sm text-amber-700 ml-6 space-y-2">
                  <p>
                    {missing.length === 1 ? 'This model is' : 'These models are'} configured but not
                    installed. Run the command{missing.length === 1 ? '' : 's'} below in your terminal —
                    the app never downloads models for you:
                  </p>
                  <pre className="bg-white border border-amber-200 rounded-md p-3 font-mono text-xs text-slate-800 overflow-x-auto">
{missing.map((m) => m.pull_command ?? `ollama pull ${m.name}`).join('\n')}
                  </pre>
                  <p>
                    Analysis still runs with the remaining models — a missing model is reported as
                    unavailable rather than failing the dataset.
                  </p>
                </div>
              )}
            </div>
          )}

          {!loading && status?.installed_models && status.installed_models.length > 0 && (
            <details className="border-t border-slate-100 pt-6">
              <summary className="text-sm font-medium text-slate-900 cursor-pointer">
                Installed models in Ollama ({status.installed_models.length})
              </summary>
              <div className="flex flex-wrap gap-2 mt-3">
                {status.installed_models.map((name) => (
                  <span key={name} className="font-mono text-xs bg-slate-100 text-slate-700 px-2 py-1 rounded">
                    {name}
                  </span>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
