/**
 * api/analytics.js – Analytics endpoints used by the Analytics tab (M9).
 */
import apiClient from './client';

const get = (projectId, name) =>
  apiClient.get(`/projects/${projectId}/analytics/${name}`).then((r) => r.data.data);

export const getHealth = (projectId) => get(projectId, 'health');
export const getForecast = (projectId) => get(projectId, 'forecast');
export const getBurndown = (projectId) => get(projectId, 'burndown');
