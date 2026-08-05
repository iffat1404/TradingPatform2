import { apiClient } from './client';

export const register = (payload) => apiClient.post('/api/auth/register', payload).then((r) => r.data);

export const login = (payload) => apiClient.post('/api/auth/login', payload).then((r) => r.data);

export const getMe = () => apiClient.get('/api/auth/me').then((r) => r.data);
