import React from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function AuthLayout() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900">Flipkart AI Review Intelligence</h1>
          <p className="text-slate-500 mt-2">Local LLM Sentiment Analysis Engine</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
