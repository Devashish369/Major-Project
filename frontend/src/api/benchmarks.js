/**
 * api/benchmarks.js – Frontend API helper for the Benchmarks page (M8).
 */
import api from './axios';

/**
 * GET /ml/effort-benchmark
 * Returns { effort, risk, label, risk_data_note }
 */
export const getBenchmarks = async () => {
  const r = await api.get('/ml/effort-benchmark');
  return r.data.data;
};
