import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { datasetService } from '../services/datasets';
import { Dataset } from '../types/dataset';
import { Upload, Trash2, BarChart2 } from 'lucide-react';
import { formatDate } from '../utils/formatters';

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDatasets = async () => {
    try {
      const res = await datasetService.list();
      setDatasets(res.datasets);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this dataset? This will delete all associated reviews and analysis results.')) {
      try {
        await datasetService.delete(id);
        setDatasets(datasets.filter(d => d.id !== id));
      } catch (e) {
        alert('Failed to delete dataset');
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Datasets</h1>
        <Link to="/upload" className="flex items-center bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition">
          <Upload size={18} className="mr-2" />
          Upload New Dataset
        </Link>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-500">Loading datasets...</div>
        ) : datasets.length === 0 ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center">
            <Database size={48} className="text-slate-300 mb-4" />
            <h3 className="text-lg font-medium text-slate-900">No datasets found</h3>
            <p className="mt-1">Upload a CSV file to get started with analysis.</p>
            <Link to="/upload" className="mt-4 text-primary-600 font-medium hover:underline">Upload CSV</Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">File Name</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Reviews</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date Uploaded</th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {datasets.map((dataset) => (
                  <tr key={dataset.id} className="hover:bg-slate-50 transition">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <Link to={`/datasets/${dataset.id}`} className="text-sm font-medium text-primary-600 hover:text-primary-900">
                          {dataset.filename}
                        </Link>
                        {dataset.has_ground_truth && (
                          <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800" title="Contains ground truth sentiment labels">
                            Labeled
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                        ${dataset.status === 'completed' ? 'bg-green-100 text-green-800' : 
                          dataset.status === 'analyzing' ? 'bg-blue-100 text-blue-800 animate-pulse' :
                          dataset.status === 'stopped' || dataset.status === 'cancelled' ? 'bg-amber-100 text-amber-800' :
                          dataset.status === 'uploaded' ? 'bg-slate-100 text-slate-800' :
                          'bg-red-100 text-red-800'}`}>
                        {dataset.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                      {dataset.processed_reviews} / {dataset.total_reviews}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                      {formatDate(dataset.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end space-x-3">
                        <Link to={`/datasets/${dataset.id}`} className="text-slate-400 hover:text-primary-600 transition" title="View details">
                          <BarChart2 size={18} />
                        </Link>
                        <button onClick={() => handleDelete(dataset.id)} className="text-slate-400 hover:text-red-600 transition" title="Delete dataset">
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// Need Database icon fallback inside DatasetsPage since we used it
import { Database } from 'lucide-react';
