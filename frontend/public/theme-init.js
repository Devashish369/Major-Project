// Applies the saved theme BEFORE React renders, so the page never flashes the wrong colours.
// A separate file (not an inline script) because the site's Content-Security-Policy allows
// only scripts from the site itself.  Keep in sync with src/context/ThemeContext.jsx.
(function () {
  var mode = 'system';
  try { mode = localStorage.getItem('intellipm_theme') || 'system'; } catch { /* private mode */ }
  var dark = mode === 'dark' || (mode !== 'light' && window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
})();
