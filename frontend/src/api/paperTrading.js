import { apiClient } from './client';

export const createStrategy = (payload) =>
  apiClient.post('/api/paper-trading/strategies', payload).then((r) => r.data);

export const listStrategies = () => apiClient.get('/api/paper-trading/strategies').then((r) => r.data);

export const listBacktestRuns = () => apiClient.get('/api/paper-trading/backtest').then((r) => r.data);

export const runBacktest = (strategyId, payload) =>
  apiClient.post(`/api/paper-trading/backtest/${strategyId}/run`, payload).then((r) => r.data);

export const getBacktestResults = (runId) =>
  apiClient.get(`/api/paper-trading/backtest/${runId}/results`).then((r) => r.data);
