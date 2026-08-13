import { apiGet, apiPost } from './client.js';

const CHAT_HISTORY_TIMEOUT_MS = 6000;
const CHAT_HISTORY_MESSAGE_LIMIT = 60;

/**
 * POST /api/ai/ask
 * @param {{ session_id: string, question: string, top_k: number }} payload
 */
export const askQuestion = (payload) =>
  apiPost('/api/ai/ask', payload);

export const listChatSessions = ({ limit = 30 } = {}) =>
  apiGet(`/api/ai/sessions?limit=${encodeURIComponent(limit)}`, { timeoutMs: CHAT_HISTORY_TIMEOUT_MS });

export const getLatestChatSession = ({ messageLimit = CHAT_HISTORY_MESSAGE_LIMIT } = {}) =>
  apiGet(`/api/ai/sessions/latest?message_limit=${encodeURIComponent(messageLimit)}`, { timeoutMs: CHAT_HISTORY_TIMEOUT_MS });

export const getChatSession = (sessionId, { messageLimit = CHAT_HISTORY_MESSAGE_LIMIT } = {}) =>
  apiGet(`/api/ai/sessions/${encodeURIComponent(sessionId)}?message_limit=${encodeURIComponent(messageLimit)}`, { timeoutMs: CHAT_HISTORY_TIMEOUT_MS });

export const archiveChatSession = (sessionId) =>
  apiPost(`/api/ai/sessions/${encodeURIComponent(sessionId)}/archive`, {}, { timeoutMs: CHAT_HISTORY_TIMEOUT_MS });
