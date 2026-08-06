import { apiClient } from './client';

export const getLatestPrice = (ticker) => apiClient.get(`/api/prices/${ticker}/latest`).then((r) => r.data);

export const getPlatformQuotes = (ticker, volatilityMultiplier = 1.0) =>
  apiClient.get(`/api/prices/${ticker}/quotes`, { params: { volatility_multiplier: volatilityMultiplier } }).then((r) => r.data);

export const getIntraday = (ticker, interval = '5m') =>
  apiClient.get(`/api/prices/${ticker}/intraday`, { params: { interval } }).then((r) => r.data);

export const getDaily = (ticker) => apiClient.get(`/api/prices/${ticker}/daily`).then((r) => r.data);

export const getMarketCurrent = () => apiClient.get('/api/prices/market/current').then((r) => r.data);

export const TICKERS = ['AAPL', 'GOOG', 'IBM', 'MSFT', 'TSLA', 'UL', 'WMT'];
