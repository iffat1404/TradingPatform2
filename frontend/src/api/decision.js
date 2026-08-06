import { apiClient } from './client';

/**
 * Score a hypothetical trade without executing it.
 * `explain` is opt-in so the live ticket panel doesn't call the model on every keystroke.
 */
export const previewDecision = (payload, { explain = false } = {}) =>
  apiClient.post('/api/decision/preview', payload, { params: { explain } }).then((r) => r.data);

export const getDecisionForOrder = (orderId) =>
  apiClient.get(`/api/decision/order/${orderId}`).then((r) => r.data);

export const getDecisionHistory = (limit = 50) =>
  apiClient.get('/api/decision/history', { params: { limit } }).then((r) => r.data);

export const updateOrderLevels = (orderId, levels) =>
  apiClient.patch(`/api/orders/${orderId}/levels`, levels).then((r) => r.data);
