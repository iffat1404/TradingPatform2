import { apiClient } from './client';

export const getPortfolioReport = () => apiClient.get('/api/reports/portfolio').then((r) => r.data);

export const exportPortfolioCsv = () =>
  apiClient
    .get('/api/reports/portfolio/export', { params: { format: 'csv' }, responseType: 'blob' })
    .then((r) => r.data);
