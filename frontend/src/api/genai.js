import { apiClient } from './client';

export const getPortfolioSummaryAi = () => apiClient.post('/api/genai/portfolio-summary').then((r) => r.data);

// Note: this endpoint is a GET on the backend, unlike the other genai routes.
export const explainTicker = (ticker) => apiClient.get(`/api/genai/explain/${ticker}`).then((r) => r.data);

// KYC document extraction. Takes an uploaded document path, NOT free text — the old
// {text} signature never matched this endpoint and always returned nulls.
export const extractIdDocument = (filePath, contentType) =>
  apiClient
    .post('/api/genai/extract-id', { file_path: filePath, content_type: contentType })
    .then((r) => r.data);

export const parseOrder = (text) => apiClient.post('/api/genai/parse-order', { text }).then((r) => r.data);

// The server reads the real reason off the order's audit trail, so no reason is passed.
export const explainRejection = (orderId) =>
  apiClient.post('/api/genai/explain-rejection', { order_id: orderId }).then((r) => r.data);
