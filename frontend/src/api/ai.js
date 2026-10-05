/**
 * api/ai.js – AI planner API helpers.
 */
import apiClient from './client';

export const generatePlan = (description, teamSize, durationWeeks) =>
  apiClient.post('/ai/generate-plan', {
    description,
    team_size: teamSize,
    duration_weeks: durationWeeks,
  }).then((r) => ({ plan: r.data.data, source: r.data.source }));

export const applyPlan = (projectId, plan, source) =>
  apiClient.post(`/projects/${projectId}/apply-plan`, { plan, source })
    .then((r) => r.data.data);
