import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { datasetService } from '../services/datasets';
import { UploadCloud, FileType, CheckCircle2, AlertCircle } from 'lucide-react';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (selectedFile: File) => {
    setError('');
    setSuccess('');
    if (!selectedFile.name.endsWith('.csv')) {
      setError('Please upload a valid CSV file.');
      setFile(null);
      return;
    }
    // Limit to 20MB
    if (selectedFile.size > 20 * 1024 * 1024) {
      setError('File is too large. Maximum size is 20MB.');
      setFile(null);
      return;
    }
    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError('');

    try {
      const res = await datasetService.upload(file);
      setSuccess(`Successfully uploaded ${res.total_reviews} reviews!`);
      setTimeout(() => {
        navigate(`/datasets/${res.dataset_id}`);
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please check the CSV format.');
      setFile(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Upload Dataset</h1>
        <p className="text-slate-500 mt-2">Upload your Flipkart reviews CSV file for AI analysis.</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
        <div 
          className={`
            border-2 border-dashed rounded-xl p-10 text-center transition-colors
            ${dragActive ? 'border-primary-500 bg-primary-50' : 'border-slate-300 hover:border-slate-400'}
            ${file ? 'bg-slate-50 border-solid border-slate-300' : ''}
          `}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !file && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            onChange={handleChange}
            className="hidden"
          />

          {!file ? (
            <div className="cursor-pointer flex flex-col items-center">
              <div className="h-16 w-16 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center mb-4">
                <UploadCloud size={32} />
              </div>
              <h3 className="text-lg font-medium text-slate-900 mb-1">Click or drag file to upload</h3>
              <p className="text-sm text-slate-500">CSV format only, max 20MB.</p>
              <p className="text-xs text-slate-400 mt-4 max-w-sm">
                Required columns: 'Review' (or 'review_text').<br/>
                Optional: 'product_name', 'product_price', 'Summary'.
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <FileType size={48} className="text-blue-500 mb-4" />
              <h3 className="text-lg font-medium text-slate-900">{file.name}</h3>
              <p className="text-sm text-slate-500 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              
              <div className="flex space-x-4 mt-6">
                <button 
                  onClick={() => setFile(null)}
                  disabled={loading}
                  className="px-4 py-2 border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button 
                  onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                  disabled={loading}
                  className="px-6 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition flex items-center disabled:opacity-70"
                >
                  {loading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Uploading...
                    </>
                  ) : 'Upload File'}
                </button>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-6 p-4 bg-red-50 text-red-700 rounded-md flex items-start">
            <AlertCircle className="shrink-0 mr-3 mt-0.5" size={18} />
            <p className="text-sm font-medium">{error}</p>
          </div>
        )}

        {success && (
          <div className="mt-6 p-4 bg-green-50 text-green-700 rounded-md flex items-center justify-center">
            <CheckCircle2 className="mr-2" size={20} />
            <p className="font-medium">{success}</p>
          </div>
        )}
      </div>
    </div>
  );
}
