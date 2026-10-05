/**
 * api/tasks.js – Task and dependency API helpers.
 */
import apiClient from './client';

export const listTasks = (projectId) =>
  apiClient.get(`/projects/${projectId}/tasks`).then((r) => r.data.data);

export const createTask = (projectId, data) =>
  apiClient.post(`/projects/${projectId}/tasks`, data).then((r) => r.data.data);

export const getTask = (taskId) =>
  apiClient.get(`/tasks/${taskId}`).then((r) => r.data.data);

export const updateTask = (taskId, data) =>
  apiClient.patch(`/tasks/${taskId}`, data).then((r) => r.data.data);

export const deleteTask = (taskId) =>
  apiClient.delete(`/tasks/${taskId}`).then((r) => r.data);

export const addDependency = (taskId, dependsOnId) =>
  apiClient.post(`/tasks/${taskId}/dependencies`, { depends_on_id: dependsOnId }).then((r) => r.data.data);

export const removeDependency = (taskId, depId) =>
  apiClient.delete(`/tasks/${taskId}/dependencies/${depId}`).then((r) => r.data);

export const listActivity = (projectId) =>
  apiClient.get(`/projects/${projectId}/activity`).then((r) => r.data.data);
