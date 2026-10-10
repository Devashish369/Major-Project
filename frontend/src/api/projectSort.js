/**
 * api/projectSort.js – order the dashboard's project cards.
 *
 * One field + a direction.  Each field has a natural direction ("first" order); `reverse` flips it.
 *   date      newest → oldest
 *   risk      highest → lowest   (lower health score = riskier; same bands as the card badge)
 *   priority  high → low
 *   status    pending → in progress → completed
 *   progress  highest → lowest
 * Projects without a value (e.g. no health score yet because there are no tasks) always go last,
 * in either direction.  Ties: project title A→Z.
 */
export const SORT_FIELDS = [
  { value: 'date', label: 'Date', first: 'Newest', last: 'Oldest' },
  { value: 'risk', label: 'Risk', first: 'Highest', last: 'Lowest' },
  { value: 'priority', label: 'Priority', first: 'High', last: 'Low' },
  { value: 'status', label: 'Status', first: 'Pending', last: 'Completed' },
  { value: 'progress', label: 'Progress', first: 'Highest', last: 'Lowest' },
];

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const STATUS_RANK = { pending: 0, in_progress: 1, completed: 2 };

// Smaller key = earlier in the natural direction; null = no value (always last).
const KEY = {
  date: (p) => (p.created_at ? -new Date(p.created_at).getTime() : null),
  risk: (p) => p.health_score ?? null,
  priority: (p) => PRIORITY_RANK[p.priority] ?? null,
  status: (p) => STATUS_RANK[p.status] ?? null,
  progress: (p) => (p.done_ratio == null ? null : -p.done_ratio),
};

/** Returns a NEW sorted array (the cached list is never mutated). */
export function sortProjects(projects, field = 'date', reverse = false) {
  const key = KEY[field] || KEY.date;
  return [...projects].sort((a, b) => {
    const ka = key(a), kb = key(b);
    if (ka == null || kb == null || Number.isNaN(ka) || Number.isNaN(kb)) {
      const missA = ka == null || Number.isNaN(ka), missB = kb == null || Number.isNaN(kb);
      if (missA !== missB) return missA ? 1 : -1;                // missing values last
    } else if (ka !== kb) {
      return reverse ? kb - ka : ka - kb;
    }
    return (a.title || '').localeCompare(b.title || '') || a.id - b.id;
  });
}

/** Read a saved choice; older saved values (e.g. "progress_desc") are mapped to the new form. */
export function parseSort(saved) {
  const legacy = { default: ['date', false], pending: ['status', false], progress_desc: ['progress', false],
                   progress_asc: ['progress', true] };
  if (legacy[saved]) return { field: legacy[saved][0], reverse: legacy[saved][1] };
  const [field, dir] = String(saved || '').split(':');
  return SORT_FIELDS.some((f) => f.value === field) ? { field, reverse: dir === 'rev' } : { field: 'date', reverse: false };
}

export const serializeSort = ({ field, reverse }) => `${field}:${reverse ? 'rev' : 'fwd'}`;
