/**
 * api/report.js – Project report (M16). Rule-based, no LLM.
 */
import apiClient from './client';

export const getReport = (projectId) =>
  apiClient.get(`/projects/${projectId}/report`).then((r) => r.data.data);
