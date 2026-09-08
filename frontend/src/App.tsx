import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AuthLayout from './layouts/AuthLayout';
import AppLayout from './layouts/AppLayout';

// Auth Pages
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

// App Pages
import DashboardPage from './pages/DashboardPage';
import DatasetsPage from './pages/DatasetsPage';
import UploadPage from './pages/UploadPage';
import DatasetDetailPage from './pages/DatasetDetailPage';
import AnalysisProgressPage from './pages/AnalysisProgressPage';
import ReviewsPage from './pages/ReviewsPage';
import ProductAnalysisPage from './pages/ProductAnalysisPage';
import ModelComparisonPage from './pages/ModelComparisonPage';
import EvaluationPage from './pages/EvaluationPage';
import SettingsPage from './pages/SettingsPage';
import SalesForecastingPage from './pages/SalesForecastingPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/datasets/:id" element={<DatasetDetailPage />} />
          <Route path="/jobs/:id" element={<AnalysisProgressPage />} />
          <Route path="/datasets/:id/reviews" element={<ReviewsPage />} />
          <Route path="/datasets/:id/products" element={<ProductAnalysisPage />} />
          <Route path="/datasets/:id/model-comparison" element={<ModelComparisonPage />} />
          <Route path="/datasets/:id/evaluate" element={<EvaluationPage />} />
          <Route path="/forecasting" element={<SalesForecastingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
