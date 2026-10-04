/**
 * api/client.js – Axios instance pre-configured for the IntelliPM backend.
 *
 * VITE_API_BASE_URL is set in frontend/.env and injected by Vite at build time.
 * All API calls in the project should import `apiClient` from this file so
 * the base URL and any future interceptors (e.g., JWT headers) are centralised.
 */
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor ────────────────────────────────────────────────────
// M1 will add: attach Authorization: Bearer <token> here.
apiClient.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error),
);

// ── Response interceptor ───────────────────────────────────────────────────
// Unwrap the response envelope so callers get `response.data.data` directly.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
);

export default apiClient;
