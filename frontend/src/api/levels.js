import { apiClient } from './client';

/**
 * Target/stop breaches on open positions. The backend re-checks on request, so this both
 * evaluates and returns. Advisory only — nothing is ever traded automatically.
 */
export const getLevelAlerts = () => apiClient.get('/api/levels/alerts').then((r) => r.data);

export const acknowledgeLevelAlert = (alertId) =>
  apiClient.post(`/api/levels/alerts/${alertId}/acknowledge`).then((r) => r.data);
