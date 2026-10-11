/**
 * context/ThemeContext.jsx – light / dark / follow-the-system theme.
 *
 * The choice is saved per browser ('intellipm_theme'); public/theme-init.js applies it before
 * the first paint.  The theme is a `data-theme` attribute on <html>; index.css swaps the colour
 * variables for light mode, so components keep their normal Tailwind classes.
 */
import { createContext, useContext, useEffect, useState } from 'react';

const KEY = 'intellipm_theme';
const ThemeContext = createContext({ mode: 'system', theme: 'dark', setMode: () => {} });

const systemPrefersDark = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches;

function readMode() {
  try {
    const m = localStorage.getItem(KEY);
    return m === 'light' || m === 'dark' ? m : 'system';
  } catch {
    return 'system';
  }
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readMode);
  const [systemDark, setSystemDark] = useState(systemPrefersDark);
  const theme = mode === 'system' ? (systemDark ? 'dark' : 'light') : mode;

  // Follow the operating system while the mode is "Auto"
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return undefined;
    const onChange = (e) => setSystemDark(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Another tab changed the theme: follow it (a theme is a per-browser preference, unlike logins)
  useEffect(() => {
    const onStorage = (e) => { if (e.key === KEY) setModeState(readMode()); };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  function setMode(next) {
    // brief colour fade while the theme changes (index.css .theme-switching; off for reduced motion)
    const root = document.documentElement;
    root.classList.add('theme-switching');
    window.setTimeout(() => root.classList.remove('theme-switching'), 220);
    setModeState(next);
    try {
      if (next === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch { /* private mode: the choice lasts until the tab closes */ }
  }

  return <ThemeContext.Provider value={{ mode, theme, setMode }}>{children}</ThemeContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(ThemeContext);
