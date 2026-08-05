import { apiClient } from './client';

export const getPortfolioSummaryAi = () => apiClient.post('/api/genai/portfolio-summary').then((r) => r.data);

export const explainTicker = (ticker) => apiClient.post(`/api/genai/explain/${ticker}`).then((r) => r.data);

export const extractId = (text) => apiClient.post('/api/genai/extract-id', { text }).then((r) => r.data);

export const parseOrder = (text) => apiClient.post('/api/genai/parse-order', { text }).then((r) => r.data);

export const explainRejection = (orderId, rejectionReason) =>
  apiClient
    .post('/api/genai/explain-rejection', { order_id: orderId, rejection_reason: rejectionReason })
    .then((r) => r.data);
