import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { reviewService } from '../services/reviews';
import { ReviewListResponse } from '../types/review';
import { Search, Filter, ChevronLeft, ChevronRight, X, ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { getSentimentColor, getScoreColor } from '../utils/sentimentColors';
import { formatScore } from '../utils/formatters';
import { getAgreementColor, getAgreementLabel } from '../utils/multiModel';
import ReviewModelComparison from '../components/ReviewModelComparison';

export default function ReviewsPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ReviewListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sentiment, setSentiment] = useState('');
  const [status, setStatus] = useState('');

  // Expanded per-review model comparison
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  // Debounced search
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1); // Reset page on new search
    }, 500);
    return () => clearTimeout(handler);
  }, [search]);

  useEffect(() => {
    if (!id) return;
    
    setLoading(true);
    setExpandedId(null);
    reviewService.list(id, {
      page,
      page_size: 15,
      search: debouncedSearch || undefined,
      sentiment: sentiment || undefined,
      status: status || undefined
    }).then(res => {
      setData(res);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, [id, page, debouncedSearch, sentiment, status]);

  const clearFilters = () => {
    setSearch('');
    setSentiment('');
    setStatus('');
    setPage(1);
  };

  const hasFilters = search || sentiment || status;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reviews</h1>
          <p className="text-slate-500 mt-1">Browse and filter analyzed reviews.</p>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4">
        <div className="flex-1 relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search size={18} className="text-slate-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg focus:ring-primary focus:border-primary sm:text-sm"
            placeholder="Search in review text or product name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex gap-4">
          <select
            className="block w-40 pl-3 pr-10 py-2 border border-slate-300 rounded-lg focus:ring-primary focus:border-primary sm:text-sm bg-white"
            value={sentiment}
            onChange={(e) => { setSentiment(e.target.value); setPage(1); }}
          >
            <option value="">All Sentiments</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="negative">Negative</option>
          </select>
          
          <select
            className="block w-40 pl-3 pr-10 py-2 border border-slate-300 rounded-lg focus:ring-primary focus:border-primary sm:text-sm bg-white"
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          >
            <option value="">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center px-3 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
              title="Clear filters"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        {loading ? (
          <div className="p-12 text-center text-slate-500">Loading reviews...</div>
        ) : !data || data.reviews.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Filter size={48} className="mx-auto text-slate-300 mb-4" />
            <p className="text-lg font-medium text-slate-900">No reviews found</p>
            <p className="mt-1">Try adjusting your filters.</p>
            {hasFilters && (
              <button onClick={clearFilters} className="mt-4 text-primary-600 font-medium hover:underline">
                Clear all filters
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider w-1/3">Review & Product</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">AI Sentiment (Ensemble)</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Models</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Keywords</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {data.reviews.map((review) => {
                    const modelScores = review.model_scores ?? {};
                    const modelNames = Object.keys(modelScores);
                    const isExpanded = expandedId === review.id;
                    return (
                    <React.Fragment key={review.id}>
                    <tr className="hover:bg-slate-50">
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium text-slate-900 mb-1 line-clamp-1">{review.product_name || 'Unknown Product'}</div>
                        <div className="text-sm text-slate-500 line-clamp-3" title={review.review}>
                          "{review.review}"
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {review.processing_status === 'completed' ? (
                          <div className="flex flex-col space-y-2">
                            <div className="flex items-center space-x-2">
                              <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase ${getSentimentColor(review.sentiment)}`}>
                                {review.sentiment}
                              </span>
                              <span className={`font-bold text-sm ${getScoreColor(review.ai_sentiment_score)}`}>
                                {formatScore(review.ai_sentiment_score)}/5
                              </span>
                            </div>
                            <div className="text-xs text-slate-500 line-clamp-2" title={review.reason}>
                              {review.reason}
                            </div>
                          </div>
                        ) : (
                          <span className="text-sm text-slate-400 italic">Not analyzed</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {modelNames.length > 0 ? (
                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-1">
                              {modelNames.map((model) => (
                                <span
                                  key={model}
                                  className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-mono"
                                  title={`${model}: ${review.model_sentiments?.[model] ?? ''}`}
                                >
                                  {model}
                                  <span className="ml-1.5 font-sans font-semibold">{formatScore(modelScores[model])}</span>
                                </span>
                              ))}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-0.5 rounded-md text-[10px] font-medium border ${getAgreementColor(review.agreement_level)}`}>
                                {getAgreementLabel(review.agreement_level)} agreement
                              </span>
                              {review.models_failed && review.models_failed.length > 0 && (
                                <span className="text-[10px] text-red-600">
                                  {review.models_failed.join(', ')} unavailable
                                </span>
                              )}
                            </div>
                            <button
                              onClick={() => setExpandedId(isExpanded ? null : review.id)}
                              className="inline-flex items-center text-xs font-medium text-primary-600 hover:text-primary-700"
                            >
                              <Layers size={13} className="mr-1" />
                              {isExpanded ? 'Hide comparison' : 'Compare models'}
                              {isExpanded ? <ChevronUp size={13} className="ml-1" /> : <ChevronDown size={13} className="ml-1" />}
                            </button>
                          </div>
                        ) : review.processing_status === 'completed' ? (
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : review.id)}
                            className="inline-flex items-center text-xs font-medium text-primary-600 hover:text-primary-700"
                          >
                            <Layers size={13} className="mr-1" />
                            {isExpanded ? 'Hide comparison' : 'Compare models'}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400 italic">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1">
                          {review.keywords?.slice(0, 3).map((kw, i) => (
                            <span key={i} className="inline-block px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs">
                              {kw}
                            </span>
                          ))}
                          {review.keywords && review.keywords.length > 3 && (
                            <span className="inline-block px-2 py-0.5 rounded text-slate-400 text-xs">+{review.keywords.length - 3}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                          ${review.processing_status === 'completed' ? 'bg-green-100 text-green-800' :
                            review.processing_status === 'pending' ? 'bg-slate-100 text-slate-800' :
                            review.processing_status === 'processing' ? 'bg-blue-100 text-blue-800' :
                            'bg-red-100 text-red-800'}`}>
                          {review.processing_status}
                        </span>
                        {review.error_message && (
                          <p className="text-[10px] text-slate-400 mt-1 max-w-[12rem] line-clamp-2" title={review.error_message}>
                            {review.error_message}
                          </p>
                        )}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-slate-50">
                        <td colSpan={5} className="px-6 py-4">
                          <ReviewModelComparison reviewId={review.id} />
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            
            {/* Pagination */}
            <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex items-center justify-between sm:px-6 mt-auto">
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-slate-700">
                    Showing <span className="font-medium">{((page - 1) * data.page_size) + 1}</span> to <span className="font-medium">{Math.min(page * data.page_size, data.total)}</span> of <span className="font-medium">{data.total}</span> results
                  </p>
                </div>
                <div>
                  <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-slate-300 bg-white text-sm font-medium text-slate-500 hover:bg-slate-50 disabled:opacity-50"
                    >
                      <span className="sr-only">Previous</span>
                      <ChevronLeft size={16} />
                    </button>
                    <div className="px-4 py-2 border border-slate-300 bg-white text-sm font-medium text-slate-700">
                      Page {page} of {data.total_pages}
                    </div>
                    <button
                      onClick={() => setPage(p => Math.min(data.total_pages, p + 1))}
                      disabled={page === data.total_pages}
                      className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-slate-300 bg-white text-sm font-medium text-slate-500 hover:bg-slate-50 disabled:opacity-50"
                    >
                      <span className="sr-only">Next</span>
                      <ChevronRight size={16} />
                    </button>
                  </nav>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
