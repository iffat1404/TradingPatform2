import { apiClient } from './client';

export const createOrder = (payload) => apiClient.post('/api/orders/', payload).then((r) => r.data);

export const listOrders = (params = {}) => apiClient.get('/api/orders/', { params }).then((r) => r.data);

export const getOrder = (orderId) => apiClient.get(`/api/orders/${orderId}`).then((r) => r.data);

export const cancelOrder = (orderId) => apiClient.delete(`/api/orders/${orderId}`).then((r) => r.data);

export const getOrderEvents = (orderId) => apiClient.get(`/api/orders/${orderId}/events`).then((r) => r.data);
