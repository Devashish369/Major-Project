/**
 * api/errors.js – turn ANY API / network error into a plain string that is safe to render.
 *
 * Why this exists: a 422 validation error carries its `detail` as a LIST of objects.
 * Putting that list into the page as text makes React throw ("Objects are not valid as a
 * React child") and the whole screen goes blank.  Every place that shows an error must go
 * through this function.
 *
 * Order: the readable `message` of the standard envelope -> a string/list `detail` -> fallback.
 */
const asText = (v) => {
  if (typeof v === 'string') return v.trim();
  if (Array.isArray(v)) {
    return v.map((x) => (typeof x === 'string' ? x : x?.msg || '')).filter(Boolean).join('; ');
  }
  return '';
};

export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  if (!err) return fallback;
  if (!err.response) {
    // No reply at all: server asleep (free hosting), offline, or blocked by CORS
    return err.request
      ? 'Cannot reach the server. If it was idle, wait about a minute for it to wake up and try again.'
      : asText(err.message) || fallback;
  }
  const data = err.response.data;
  return asText(data?.message) || asText(data?.detail) || fallback;
}
