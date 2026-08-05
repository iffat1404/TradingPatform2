import { apiClient } from './client';

export const submitKyc = (idType, file) => {
  const form = new FormData();
  form.append('id_type', idType);
  form.append('id_document', file);
  return apiClient.post('/api/kyc/submit', form).then((r) => r.data);
};

export const getKycStatus = () => apiClient.get('/api/kyc/status').then((r) => r.data);
