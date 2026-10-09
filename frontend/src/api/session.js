/**
 * api/session.js – where this browser TAB keeps its login token.
 *
 * sessionStorage is private to one tab (localStorage is shared by every tab of the browser),
 * so each tab can be signed in as a different person at the same time.  A page refresh keeps
 * the login; closing the tab ends it.  "Duplicate tab" starts as the same user and is then
 * independent.  Wrapped in try/catch because some privacy modes block storage entirely.
 */
const KEY = 'intellipm_token';

export const getToken = () => {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
};
export const setToken = (token) => {
  try { sessionStorage.setItem(KEY, token); } catch { /* storage blocked: login lasts until reload */ }
};
export const clearToken = () => {
  try { sessionStorage.removeItem(KEY); } catch { /* nothing to clear */ }
};
