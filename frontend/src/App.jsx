/**
 * App.jsx – Root component and router for IntelliPM.
 *
 * M1 adds:
 *   - AuthProvider wrapping the whole app
 *   - /login  → LoginPage      (public)
 *   - /register → RegisterPage (public)
 *   - /dashboard → DashboardPage (PROTECTED)
 *   - / redirects to /dashboard (ProtectedRoute handles unauthenticated → /login)
 *
 * Future modules add more routes inside the ProtectedRoute wrapper.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

import HealthPage from './pages/HealthPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProjectPage from './pages/ProjectPage';
import BenchmarksPage from './pages/BenchmarksPage';
import ErrorBoundary from './components/ErrorBoundary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* AuthProvider must wrap everything that needs auth state */}
        <AuthProvider>
          <Routes>
            {/* ── Public routes ───────────────────────────── */}
            <Route path="/login"    element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/health"   element={<HealthPage />} />

            {/* ── Protected routes ────────────────────────── */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/projects/:id"
              element={
                <ProtectedRoute>
                  <ProjectPage />
                </ProtectedRoute>
              }
            />

            {/* M8: Benchmarks page (NASA93 + risk model metrics) */}
            <Route
              path="/benchmarks"
              element={
                <ProtectedRoute>
                  <div className="min-h-screen bg-slate-900 p-6">
                    <BenchmarksPage />
                  </div>
                </ProtectedRoute>
              }
            />

            {/* M2+: Project, Board, Team, Analytics pages go here */}

            {/* ── Default redirect ─────────────────────────── */}
            {/* / → /dashboard; ProtectedRoute will send unauthenticated to /login */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />

            {/* 404 fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
