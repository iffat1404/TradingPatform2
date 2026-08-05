import { apiClient } from './client';

export const getPortfolioSummary = () => apiClient.get('/api/portfolio/').then((r) => r.data);

export const getPortfolioPnl = () => apiClient.get('/api/portfolio/pnl').then((r) => r.data);

export const getPortfolioExposure = () => apiClient.get('/api/portfolio/exposure').then((r) => r.data);

export const getPositions = () => apiClient.get('/api/portfolio/positions').then((r) => r.data);

export const getTickerLots = (ticker) => apiClient.get(`/api/portfolio/${ticker}/lots`).then((r) => r.data);
