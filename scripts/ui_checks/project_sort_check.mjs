// Unit check for frontend/src/api/projectSort.js:  node scripts/ui_checks/project_sort_check.mjs
import assert from 'node:assert/strict';
import { sortProjects, SORT_FIELDS, parseSort, serializeSort } from '../../frontend/src/api/projectSort.js';

const P = [
  { id: 1, title: 'Alpha', priority: 'low', status: 'completed', done_ratio: 1.0, health_score: 99, created_at: '2026-10-01T00:00:00Z' },
  { id: 2, title: 'Bravo', priority: 'high', status: 'in_progress', done_ratio: 0.25, health_score: 41, created_at: '2026-10-03T00:00:00Z' },
  { id: 3, title: 'Charlie', priority: 'medium', status: 'pending', done_ratio: 0, health_score: null, created_at: '2026-10-02T00:00:00Z' },
  { id: 4, title: 'Delta', priority: 'high', status: 'in_progress', done_ratio: 0.39, health_score: 63, created_at: '2026-10-04T00:00:00Z' },
  { id: 5, title: 'Echo', priority: 'medium', status: 'pending', done_ratio: 0, health_score: 80, created_at: '2026-10-05T00:00:00Z' },
];
const ids = (field, rev = false) => sortProjects(P, field, rev).map((p) => p.id);

assert.deepEqual(ids('date'), [5, 4, 2, 3, 1]);              // newest
assert.deepEqual(ids('date', true), [1, 3, 2, 4, 5]);        // oldest
assert.deepEqual(ids('risk'), [2, 4, 5, 1, 3]);              // highest risk; no score last
assert.deepEqual(ids('risk', true), [1, 5, 4, 2, 3]);        // lowest risk; no score still last
assert.deepEqual(ids('priority'), [2, 4, 3, 5, 1]);          // high, medium, low (A→Z in a tie)
assert.deepEqual(ids('priority', true), [1, 3, 5, 2, 4]);
assert.deepEqual(ids('status'), [3, 5, 2, 4, 1]);            // pending, in progress, completed
assert.deepEqual(ids('status', true), [1, 2, 4, 3, 5]);
assert.deepEqual(ids('progress'), [1, 4, 2, 3, 5]);          // 100 %, 39 %, 25 %, 0 %, 0 %
assert.deepEqual(ids('progress', true), [3, 5, 2, 4, 1]);
assert.deepEqual(ids('nonsense'), ids('date'));
const copy = [...P]; sortProjects(P, 'risk'); assert.deepEqual(P, copy);   // input not mutated

assert.deepEqual(SORT_FIELDS.map((f) => f.label), ['Date', 'Risk', 'Priority', 'Status', 'Progress']);
assert.deepEqual(parseSort(serializeSort({ field: 'risk', reverse: true })), { field: 'risk', reverse: true });
assert.deepEqual(parseSort('progress_asc'), { field: 'progress', reverse: true });     // old saved value
assert.deepEqual(parseSort(null), { field: 'date', reverse: false });
assert.deepEqual(parseSort('garbage:rev'), { field: 'date', reverse: false });
console.log('projectSort.js: all checks passed');
