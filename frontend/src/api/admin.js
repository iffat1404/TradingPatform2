import { apiClient } from './client';

// KYC review
export const getKycQueue = (statusFilter = 'PENDING_REVIEW') =>
  apiClient.get('/api/admin/kyc', { params: { status_filter: statusFilter } }).then((r) => r.data);

export const getKycSubmission = (submissionId) =>
  apiClient.get(`/api/admin/kyc/${submissionId}`).then((r) => r.data);

export const approveKyc = (submissionId, reviewerId) =>
  apiClient.post(`/api/admin/kyc/${submissionId}/approve`, { reviewer_id: reviewerId }).then((r) => r.data);

export const rejectKyc = (submissionId, rejectionReason, reviewerId) =>
  apiClient
    .post(`/api/admin/kyc/${submissionId}/reject`, { rejection_reason: rejectionReason, reviewer_id: reviewerId })
    .then((r) => r.data);

// Accounts
export const getAccounts = () => apiClient.get('/api/admin/accounts').then((r) => r.data);

// Logs & compliance
export const getAuditLogs = (params = {}) => apiClient.get('/api/admin/audit-logs', { params }).then((r) => r.data);

export const getTradeLogs = (params = {}) => apiClient.get('/api/admin/trade-logs', { params }).then((r) => r.data);

export const getComplianceFlags = () => apiClient.get('/api/admin/flags').then((r) => r.data);

// Feed / MarketClock session control
export const resetFeed = () => apiClient.post('/api/admin/feed/reset').then((r) => r.data);

export const getFeedStatus = () => apiClient.get('/api/admin/feed/status').then((r) => r.data);

export const setSessionTime = (date, time) =>
  apiClient.post('/api/admin/session/time', { date, time }).then((r) => r.data);

export const resetSession = () => apiClient.post('/api/admin/session/reset').then((r) => r.data);

export const setSessionSpeed = (multiplier) =>
  apiClient.post('/api/admin/session/speed', { multiplier }).then((r) => r.data);

export const getSessionStatus = () => apiClient.get('/api/admin/session/status').then((r) => r.data);
