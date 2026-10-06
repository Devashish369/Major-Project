/**
 * api/decisions.js – Decision log and "Ask" helpers (M12).
 */
import apiClient from './client';

export const listDecisions = (projectId) =>
  apiClient.get(`/projects/${projectId}/decisions`).then((r) => r.data.data);

export const createDecision = (projectId, data) =>
  apiClient.post(`/projects/${projectId}/decisions`, data).then((r) => r.data.data);

export const deleteDecision = (decisionId) =>
  apiClient.delete(`/decisions/${decisionId}`).then((r) => r.data);

/** Returns { answer, sources: [{type, id}] }. Errors carry a readable response.data.detail. */
export const askProject = (projectId, question) =>
  apiClient.post(`/projects/${projectId}/ask`, { question }).then((r) => r.data.data);
