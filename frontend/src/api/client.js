/**
 * api/client.js – Axios instance pre-configured for the IntelliPM backend.
 *
 * VITE_API_BASE_URL is set in frontend/.env and injected by Vite at build time.
 * All API calls in the project should import `apiClient` from this file so
 * the base URL and any future interceptors (e.g., JWT headers) are centralised.
 */
import axios from 'axios';
import { getToken, clearToken } from './session';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor ────────────────────────────────────────────────────
// Attach this tab's JWT on every request (see api/session.js: each tab has its own login).
apiClient.interceptors.request.use(
  (config) => {
    const token = getToken();
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
  (error) => {
    // 401 on a normal request = the saved login expired or is invalid: sign out and go to /login.
    // (Not for /auth/login and /auth/register themselves: a wrong password is also a 401.)
    const url = error.config?.url || '';
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/register');
    if (error.response?.status === 401 && !isAuthCall && getToken()) {
      clearToken();
      if (!window.location.pathname.startsWith('/login')) window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

export default apiClient;
