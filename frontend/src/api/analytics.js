import { apiClient } from './client';

export const getIndicators = (ticker) => apiClient.get(`/api/analytics/${ticker}/indicators`).then((r) => r.data);

export const getAlerts = (ticker) => apiClient.get(`/api/analytics/${ticker}/alerts`).then((r) => r.data);

export const getSentimentDivergence = (ticker, date) =>
  apiClient.get(`/api/analytics/${ticker}/sentiment-divergence`, { params: { date } }).then((r) => r.data);
