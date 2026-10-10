/**
 * api/auth.js – Auth API functions for IntelliPM.
 *
 * All calls go through apiClient which reads VITE_API_BASE_URL from .env.
 * The interceptor in client.js will attach the Bearer token in M1's update.
 */
import apiClient from './client';

/** Register a new account. Returns { access_token, token_type, user }. */
export const registerUser = (data) =>
  apiClient.post('/auth/register', data).then((r) => r.data.data);

/** Login. Returns { access_token, token_type, user }. */
export const loginUser = (data) =>
  apiClient.post('/auth/login', data).then((r) => r.data.data);

/** GET /auth/me – requires Authorization header (set in client interceptor). */
export const getMe = () =>
  apiClient.get('/auth/me').then((r) => r.data.data);

/** PATCH /auth/me – partial update of full_name / skills. */
export const updateMe = (data) =>
  apiClient.patch('/auth/me', data).then((r) => r.data.data);

/** POST /auth/change-password – returns a fresh token for this tab; all other sessions end. */
export const changePassword = (current_password, new_password) =>
  apiClient.post('/auth/change-password', { current_password, new_password }).then((r) => r.data.data);

/** POST /auth/logout-all – revoke every token of this account. */
export const logoutAll = () => apiClient.post('/auth/logout-all').then((r) => r.data);

/** GET /auth/security-events – recent sign-ins and security changes of the current user. */
export const getSecurityEvents = () => apiClient.get('/auth/security-events').then((r) => r.data.data);
