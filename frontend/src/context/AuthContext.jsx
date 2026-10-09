/**
 * context/AuthContext.jsx – Global auth state for IntelliPM.
 *
 * Responsibilities:
 *   - Store the current user and JWT token in React state + localStorage.
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

// ── Context ───────────────────────────────────────────────────────────────────
const AuthContext = createContext(null);

const TOKEN_KEY = 'intellipm_token';   // localStorage key

// ── Provider ──────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const qc = useQueryClient();
  const [user, setUser] = useState(null);
  // true while validating a stored token; nothing to validate when there is none
  const [loading, setLoading] = useState(() => !!localStorage.getItem(TOKEN_KEY));

  /**
   * On mount: if a token exists in localStorage, call /auth/me to validate it
   * and restore the user session. This is what keeps the user logged in after
   * a page refresh without re-entering credentials.
   */
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    // Token exists: validate with the server
    getMe()
      .then((userData) => setUser(userData))
      .catch(() => {
        // Token invalid or expired — clear it silently
        localStorage.removeItem(TOKEN_KEY);
      })
      .finally(() => setLoading(false));
  }, []);

  /**
   * Another tab of this browser logged in/out (the token is shared through localStorage).
   * This tab would otherwise keep showing the old account while sending the new account's
   * token, so reload it: it re-validates the token and starts with an empty cache.
   */
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === TOKEN_KEY || e.key === null) window.location.reload();
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  /**
   * Store token and user in state + localStorage.
   * The query cache is emptied first: its keys (['projects'], ['tasks', 5] ...) do not contain
   * the user, so without this the NEXT person to log in, in the same tab, would be shown the
   * previous person's projects until the cache expired.
   */
  function _saveSession(token, userData) {
    qc.clear();
    localStorage.setItem(TOKEN_KEY, token);
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
    localStorage.removeItem(TOKEN_KEY);
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
