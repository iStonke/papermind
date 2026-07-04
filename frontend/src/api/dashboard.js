import { apiGet } from './client.js';

/** GET /api/dashboard/overview */
export const getDashboardOverview = () =>
  apiGet('/api/dashboard/overview');
