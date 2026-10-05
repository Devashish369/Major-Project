/**
 * api/estimator.js – Story-point estimator API helper (spec §8.6).
 */
import apiClient from './client';

/**
 * Estimate story points and hours for a task.
 *
 * @param {string} title       - Task title (required)
 * @param {string} description - Task description (optional)
 * @returns {{ story_points: number, hours: number, model: string }}
 */
export const estimateTask = (title, description = '') =>
  apiClient
    .post('/ai/estimate', { title, description: description || undefined })
    .then((r) => r.data.data);
