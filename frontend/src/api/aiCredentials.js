import { apiDelete, apiGet, apiPut } from './client.js';

export const getAICredentialStatus = () => apiGet('/api/settings/ai-credentials');
export const saveAICredential = (provider, apiKey) =>
  apiPut('/api/settings/ai-credentials', { provider, api_key: apiKey });
export const deleteAICredential = (provider) =>
  apiDelete(`/api/settings/ai-credentials/${encodeURIComponent(provider)}`);
