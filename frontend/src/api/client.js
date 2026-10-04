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
// Attach the JWT from localStorage on every request.
// The token is stored by AuthContext after login/register.
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('intellipm_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response interceptor ───────────────────────────────────────────────────
// Unwrap the response envelope so callers get `response.data.data` directly.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
);

export default apiClient;
