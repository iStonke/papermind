import { apiGet, apiPost } from './client.js';

function queryString(values = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

export const getWikiOverview = () => apiGet('/api/wiki/overview');
export const listWikiPages = (options = {}) => apiGet(`/api/wiki/pages${queryString(options)}`);
export const getWikiPage = (
  pageId,
  { includeHistory = false, claimLimit = 100, claimOffset = 0 } = {},
) => apiGet(`/api/wiki/pages/${pageId}${queryString({
  include_history: includeHistory || undefined,
  claim_limit: claimLimit,
  claim_offset: claimOffset || undefined,
})}`);
export const listWikiRevisions = (pageId) => apiGet(`/api/wiki/pages/${pageId}/revisions`);
export const listWikiProposals = ({ status = 'pending', limit = 100, offset = 0 } = {}) =>
  apiGet(`/api/wiki/proposals${queryString({ status, limit, offset: offset || undefined })}`);
export const reviewWikiProposal = (proposalId, body) =>
  apiPost(`/api/wiki/proposals/${proposalId}/review`, body);
export const correctWikiClaim = (claimId, body) => apiPost(`/api/wiki/claims/${claimId}/correct`, body);
export const retractWikiClaim = (claimId, body) => apiPost(`/api/wiki/claims/${claimId}/retract`, body);
export const captureChatAnswer = (body) => apiPost('/api/wiki/capture-answer', body);
export const lintWiki = ({ fix = true } = {}) => apiPost(`/api/wiki/lint${queryString({ fix })}`, {});
export const backfillWiki = ({ batchSize = 1, documentLimit } = {}) =>
  apiPost(`/api/wiki/backfill${queryString({
    batch_size: batchSize,
    document_limit: documentLimit,
  })}`, {});
export const getWikiBackfillStatus = () => apiGet('/api/wiki/backfill/status');
export const controlWikiBackfill = (runId, action) =>
  apiPost(`/api/wiki/backfill/${runId}/control`, { action });
export const refreshDocumentWiki = (documentId) => apiPost(`/api/wiki/documents/${documentId}/refresh`, {});
