import { apiClient } from './client';

/**
 * Headlines up to the current simulated moment. The backend refuses to return anything
 * published later than "now" in the simulation, so this can't leak future news.
 */
export const listNews = (params = {}) =>
  apiClient.get('/api/news/', { params }).then((r) => r.data);

export const getNewsArticle = (articleId) =>
  apiClient.get(`/api/news/${articleId}`).then((r) => r.data);
