import { apiPost } from './client.js';

/**
 * POST /api/ai/ask
 * @param {{ session_id: string, question: string, top_k: number }} payload
 */
export const askQuestion = (payload) =>
  apiPost('/api/ai/ask', payload);
