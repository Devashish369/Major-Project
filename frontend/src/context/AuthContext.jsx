/**
 * context/AuthContext.jsx – Global auth state for IntelliPM.
 *
 * Responsibilities:
 *   - Store the current user in React state and the JWT in this tab's sessionStorage (per-tab login).
 *   - Expose login(), register(), logout(), and updateProfile() actions.
 *   - On mount, validate the stored token by calling GET /auth/me so the
 *     user stays logged in after a page refresh (M1 done-when test).
 *
 * Usage:
 *   const { user, login, logout, loading } = useAuth();
 */

import { createContext, useContext, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { loginUser, registerUser, getMe, updateMe } from '../api/auth';
import { getToken, setToken, clearToken } from '../api/session';

// ── Context ───────────────────────────────────────────────────────────────────
const AuthContext = createContext(null);

// ── Provider ──────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const qc = useQueryClient();
  const [user, setUser] = useState(null);
  // true while validating a stored token; nothing to validate when there is none
  const [loading, setLoading] = useState(() => !!getToken());

  /**
   * On mount: if this tab has a saved token, call /auth/me to validate it
   * and restore the user session. This is what keeps the user logged in after
   * a page refresh without re-entering credentials.
   */
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    // Token exists: validate with the server
    getMe()
      .then((userData) => setUser(userData))
      .catch(() => {
        // Token invalid or expired — clear it silently
        clearToken();
      })
      .finally(() => setLoading(false));
  }, []);

  /**
   * Store the token (this tab only) and the user in state.
   * The query cache is emptied first: its keys (['projects'], ['tasks', 5] ...) do not contain
   * the user, so without this the NEXT person to log in, in the same tab, would be shown the
   * previous person's projects until the cache expired.
   */
  function _saveSession(token, userData) {
    qc.clear();
    setToken(token);
    setUser(userData);
  }

  /** POST /auth/login */
  async function login(email, password) {
    const data = await loginUser({ email, password });
    _saveSession(data.access_token, data.user);
    return data.user;
  }

  /** POST /auth/register */
  async function register(email, username, full_name, password) {
    const data = await registerUser({ email, username, full_name, password });
    _saveSession(data.access_token, data.user);
    return data.user;
  }

  /** Clear session and redirect handled by ProtectedRoute. */
  function logout() {
    clearToken();
    qc.clear();            // never leave one account's data in memory for the next login
    setUser(null);
  }

  /** PATCH /auth/me – update name/skills, refresh local state. */
  async function updateProfile(updates) {
    const updated = await updateMe(updates);
    setUser(updated);
    return updated;
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Custom hook – throws if used outside AuthProvider. */
// eslint-disable-next-line react/only-export-components -- the hook deliberately lives next to its provider
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
