/**
 * App.jsx – Root component for IntelliPM.
 *
 * M0: Sets up:
 *   - QueryClientProvider from @tanstack/react-query (global data-fetching cache)
 *   - BrowserRouter + Routes from react-router-dom
 *   - A single route: "/" → HealthPage (M0 done-when test)
 *
 * In later modules (M1+), protected routes and more pages are added here.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HealthPage from './pages/HealthPage';

// Create a single QueryClient that caches all server state.
// staleTime: 60s before a query is considered stale and re-fetched.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* M0: Health check page */}
          <Route path="/" element={<HealthPage />} />

          {/* M1+: Login, Register, Dashboard, Project pages will be added here */}
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
