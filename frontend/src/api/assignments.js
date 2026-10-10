/**
 * api/assignments.js – Assignment optimizer and workload API helpers.
 */
import apiClient from './client';

export const recommendAssignments = (projectId, force = false) =>
  apiClient
    .post(`/projects/${projectId}/assignments/recommend`, { force })
    .then((r) => r.data.data);

export const applyAssignments = (projectId, assignments) =>
  apiClient
    .post(`/projects/${projectId}/assignments/apply`, { assignments })
    .then((r) => r.data.data);

export const getWorkload = (projectId) =>
  apiClient
    .get(`/projects/${projectId}/analytics/workload`)
    .then((r) => r.data.data);

// Skills open tasks need that nobody has, with who should learn each one
export const getSkillGaps = (projectId) =>
  apiClient
    .get(`/projects/${projectId}/assignments/skill-gaps`)
    .then((r) => r.data.data);
