import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { datasetService } from '../services/datasets';
import { Dataset } from '../types/dataset';
import { Database, Upload, ArrowRight, Activity, CheckCircle, Clock, TrendingUp } from 'lucide-react';
import { formatPercent } from '../utils/formatters';

export default function DashboardPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    datasetService.list().then(res => {
      setDatasets(res.datasets);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const totalReviews = datasets.reduce((acc, d) => acc + d.total_reviews, 0);
  const processedReviews = datasets.reduce((acc, d) => acc + (d.processed_reviews || 0), 0);
  
  if (loading) {
    return <div className="p-8 text-center"><div className="animate-pulse flex flex-col items-center"><div className="h-32 w-full bg-slate-200 rounded-xl mb-4"></div></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <Link to="/upload" className="flex items-center bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition">
          <Upload size={18} className="mr-2" />
          Upload New Dataset
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center text-slate-500 mb-2">
            <Database size={20} className="mr-2" />
            <h3 className="font-medium">Total Datasets</h3>
          </div>
          <p className="text-3xl font-bold text-slate-900">{datasets.length}</p>
        </div>
        
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center text-slate-500 mb-2">
            <Activity size={20} className="mr-2" />
            <h3 className="font-medium">Total Reviews</h3>
          </div>
          <p className="text-3xl font-bold text-slate-900">{totalReviews.toLocaleString()}</p>
        </div>
        
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center text-slate-500 mb-2">
            <CheckCircle size={20} className="mr-2 text-primary-500" />
            <h3 className="font-medium">AI Analyzed</h3>
          </div>
          <p className="text-3xl font-bold text-slate-900">{processedReviews.toLocaleString()}</p>
          <p className="text-sm text-slate-500 mt-1">{totalReviews > 0 ? formatPercent((processedReviews/totalReviews)*100) : '0%'} completion</p>
        </div>
      </div>

      {/* Sales Forecasting Quick-Access Card */}
      <Link to="/forecasting" className="block bg-gradient-to-r from-primary-50 to-blue-50 border border-primary-200 rounded-xl p-6 hover:shadow-md transition">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary-100 rounded-xl">
              <TrendingUp size={24} className="text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900">Sales Forecasting</h3>
              <p className="text-sm text-slate-600 mt-0.5">
                Train SARIMA &amp; SARIMAX models. Use LLM sentiment as an exogenous signal.
              </p>
            </div>
          </div>
          <ArrowRight size={20} className="text-primary-600 shrink-0" />
        </div>
      </Link>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mt-8">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="font-semibold text-lg text-slate-900">Recent Datasets</h2>
        </div>
        {datasets.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <p>No datasets uploaded yet.</p>
            <Link to="/upload" className="text-primary-600 font-medium hover:underline mt-2 inline-block">Upload your first dataset</Link>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {datasets.slice(0, 5).map(dataset => (
              <li key={dataset.id}>
                <Link to={`/datasets/${dataset.id}`} className="block hover:bg-slate-50 transition px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">{dataset.filename}</h4>
                      <p className="text-xs text-slate-500 mt-1 flex items-center">
                        <Clock size={12} className="mr-1" />
                        {new Date(dataset.created_at).toLocaleDateString()} &middot; {dataset.total_reviews} reviews
                      </p>
                    </div>
                    <div className="flex items-center">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium mr-4
                        ${dataset.status === 'completed' ? 'bg-green-100 text-green-800' : 
                          dataset.status === 'analyzing' ? 'bg-blue-100 text-blue-800' :
                          dataset.status === 'stopped' || dataset.status === 'cancelled' ? 'bg-amber-100 text-amber-800' :
                          dataset.status === 'uploaded' ? 'bg-slate-100 text-slate-800' :
                          'bg-red-100 text-red-800'}`}>
                        {dataset.status}
                      </span>
                      <ArrowRight size={16} className="text-slate-400" />
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
