/**
 * pages/HealthPage.jsx – M0 done-when test page.
 *
 * Calls GET /api/v1/health and displays the response.
 * Uses @tanstack/react-query for data fetching so loading/error states
 * are handled cleanly. This pattern is reused throughout the project.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle, XCircle, Loader2, Server } from 'lucide-react';
import apiClient from '../api/client';

/** Fetch the health endpoint; returns the full axios response */
async function fetchHealth() {
  const res = await apiClient.get('/health');
  return res.data; // { success: true, data: { status: "ok" }, message: "OK" }
}

export default function HealthPage() {
  const [today] = useState(() => new Date().toLocaleDateString());   // computed once, not on every render
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],         // cache key
    queryFn: fetchHealth,
    retry: 1,                     // retry once on failure
    refetchInterval: 30_000,      // auto-refresh every 30 s to show it's live
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800 p-8 shadow-2xl">

        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="rounded-xl bg-indigo-600 p-3">
            <Server className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100">IntelliPM</h1>
            <p className="text-sm text-slate-400">Backend Health Check</p>
          </div>
        </div>

        {/* Status card */}
        <div className="rounded-xl border border-slate-700 bg-slate-900 p-6">

          {isLoading && (
            <div className="flex items-center gap-3 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
              <span className="text-sm font-medium">Connecting to backend…</span>
            </div>
          )}

          {isError && (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <XCircle className="h-6 w-6 text-red-400 flex-shrink-0" />
                <span className="font-semibold text-red-400">Backend unreachable</span>
              </div>
              <p className="text-xs text-slate-500 pl-9 font-mono break-all">
                {error?.message || 'Unknown error'}
              </p>
              <p className="text-xs text-slate-500 pl-9">
                Make sure the FastAPI server is running on{' '}
                <code className="text-indigo-400">
                  {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'}
                </code>
              </p>
            </div>
          )}

          {data && !isLoading && !isError && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="h-6 w-6 text-emerald-400 flex-shrink-0" />
                <span className="font-semibold text-emerald-400">Backend is healthy</span>
              </div>

              {/* Raw response envelope */}
              <pre className="mt-4 rounded-lg bg-slate-800 border border-slate-700 p-4 text-xs text-slate-300 overflow-auto">
                {JSON.stringify(data, null, 2)}
              </pre>

              <p className="text-xs text-slate-500">
                Auto-refreshes every 30 s · Endpoint:{' '}
                <code className="text-indigo-400">GET /api/v1/health</code>
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-slate-600">
          IntelliPM · system status · {today}
        </p>
      </div>
    </div>
  );
}
