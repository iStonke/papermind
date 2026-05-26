import { apiFetch } from './client.js';

export async function getImportInbox({ limit = 50 } = {}) {
  const search = new URLSearchParams();
  search.set('limit', String(Math.max(1, Math.min(Number(limit) || 50, 200))));
  return apiFetch(`/api/import/inbox?${search}`);
}

export async function claimImportInboxItems(itemIds = []) {
  return apiFetch('/api/import/inbox/claim', {
    method: 'POST',
    body: JSON.stringify({
      item_ids: Array.from(itemIds || []).map((id) => String(id || '').trim()).filter(Boolean)
    })
  });
}

export async function discardImportInboxItems(itemIds = []) {
  return apiFetch('/api/import/inbox/discard', {
    method: 'POST',
    body: JSON.stringify({
      item_ids: Array.from(itemIds || []).map((id) => String(id || '').trim()).filter(Boolean)
    })
  });
}

export async function discardImportInboxSourcePages(sourceFileId, pageIndices = []) {
  const normalizedSourceFileId = String(sourceFileId || '').trim();
  return apiFetch(`/api/import/inbox/source/${encodeURIComponent(normalizedSourceFileId)}/pages/discard`, {
    method: 'POST',
    body: JSON.stringify({
      page_indices: Array.from(pageIndices || [])
        .map((index) => Number(index))
        .filter((index) => Number.isInteger(index) && index >= 0)
    })
  });
}
