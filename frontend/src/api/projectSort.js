/**
 * api/projectSort.js – order the dashboard's project cards.
 *
 * Risk uses the same bands as the card badge (health ≥ 75 low, 50–74 medium, < 50 high);
 * within a band the lower health score (riskier) comes first. Ties: project title A→Z.
 */
export const SORT_OPTIONS = [
  { value: 'default', label: 'Newest first' },
  { value: 'risk', label: 'Risk (highest first)' },
  { value: 'priority', label: 'Priority (high → low)' },
  { value: 'pending', label: 'Pending first' },
  { value: 'progress_desc', label: 'Progress (highest)' },
  { value: 'progress_asc', label: 'Progress (lowest)' },
];

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const STATUS_RANK = { pending: 0, in_progress: 1, completed: 2 };

// Projects without a health score (no tasks yet) are treated as least risky and go last.
const health = (p) => (p.health_score == null ? Infinity : p.health_score);
const progress = (p) => p.done_ratio ?? 0;
const byTitle = (a, b) => (a.title || '').localeCompare(b.title || '');
const byNewest = (a, b) => new Date(b.created_at) - new Date(a.created_at) || b.id - a.id;

const COMPARATORS = {
  default: byNewest,
  risk: (a, b) => health(a) - health(b) || byTitle(a, b),
  priority: (a, b) => (PRIORITY_RANK[a.priority] ?? 3) - (PRIORITY_RANK[b.priority] ?? 3) || health(a) - health(b) || byTitle(a, b),
  pending: (a, b) => (STATUS_RANK[a.status] ?? 3) - (STATUS_RANK[b.status] ?? 3) || progress(a) - progress(b) || byTitle(a, b),
  progress_desc: (a, b) => progress(b) - progress(a) || byTitle(a, b),
  progress_asc: (a, b) => progress(a) - progress(b) || byTitle(a, b),
};

/** Returns a NEW sorted array (the cached list is never mutated). */
export function sortProjects(projects, mode) {
  const cmp = COMPARATORS[mode] || COMPARATORS.default;
  return [...projects].sort((a, b) => {
    const r = cmp(a, b);
    return Number.isNaN(r) ? 0 : r;
  });
}
