import { apiGet } from './client.js';

/** GET /api/sidebar/counts */
export const getSidebarCounts = () =>
  apiGet('/api/sidebar/counts');
