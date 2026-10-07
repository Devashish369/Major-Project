/**
 * api/sprints.js – read-only sprint list (sprints are created by applying an AI plan).
 */
import apiClient from './client';

export const listSprints = (projectId) =>
  apiClient.get(`/projects/${projectId}/sprints`).then((r) => r.data.data);
