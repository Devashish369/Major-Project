/**
 * api/projects.js – Project + Member API helpers.
 */
import apiClient from './client';

// ── Projects ──────────────────────────────────────────────────────────────────

export const listProjects = () =>
  apiClient.get('/projects').then((r) => r.data.data);

export const createProject = (data) =>
  apiClient.post('/projects', data).then((r) => r.data.data);

export const getProject = (id) =>
  apiClient.get(`/projects/${id}`).then((r) => r.data.data);

export const updateProject = (id, data) =>
  apiClient.patch(`/projects/${id}`, data).then((r) => r.data.data);

export const deleteProject = (id) =>
  apiClient.delete(`/projects/${id}`).then((r) => r.data);

// ── Members ───────────────────────────────────────────────────────────────────

export const listMembers = (projectId) =>
  apiClient.get(`/projects/${projectId}/members`).then((r) => r.data.data);

export const addMember = (projectId, data) =>
  apiClient.post(`/projects/${projectId}/members`, data).then((r) => r.data.data);

export const updateMember = (projectId, userId, data) =>
  apiClient.patch(`/projects/${projectId}/members/${userId}`, data).then((r) => r.data.data);

export const removeMember = (projectId, userId) =>
  apiClient.delete(`/projects/${projectId}/members/${userId}`).then((r) => r.data);
