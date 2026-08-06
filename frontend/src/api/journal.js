import { apiClient } from './client';

export const getJournalTags = () => apiClient.get('/api/journal/tags').then((r) => r.data);

export const listJournalEntries = (params = {}) =>
  apiClient.get('/api/journal/entries', { params }).then((r) => r.data);

export const getJournalEntry = (entryId) =>
  apiClient.get(`/api/journal/entries/${entryId}`).then((r) => r.data);

export const createJournalEntry = (payload) =>
  apiClient.post('/api/journal/entries', payload).then((r) => r.data);

export const updateJournalEntry = (entryId, payload) =>
  apiClient.put(`/api/journal/entries/${entryId}`, payload).then((r) => r.data);

export const deleteJournalEntry = (entryId) =>
  apiClient.delete(`/api/journal/entries/${entryId}`).then((r) => r.data);

export const analyzeJournalEntry = (entryId, regenerate = false) =>
  apiClient.post(`/api/journal/entries/${entryId}/analyze`, null, { params: { regenerate } }).then((r) => r.data);

export const getJournalInsights = () => apiClient.get('/api/journal/insights').then((r) => r.data);

/**
 * Check the news thesis behind an entry: did the cited headline actually move the price,
 * and what else was published that day that went unmentioned?
 */
export const reviewEntryNews = (entryId) =>
  apiClient.post(`/api/journal/entries/${entryId}/news-review`).then((r) => r.data);
