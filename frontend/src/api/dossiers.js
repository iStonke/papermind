import { apiDelete, apiFetch, apiGet, apiPatch, apiPost, apiPut, authedUrl, getBaseUrl } from './client.js';

export const listDossiers = ({ includeArchived = false, q = '' } = {}) => {
  const params = new URLSearchParams();
  if (includeArchived) params.set('include_archived', 'true');
  if (q) params.set('q', q);
  const suffix = params.toString();
  return apiGet(`/api/dossiers${suffix ? `?${suffix}` : ''}`);
};

export const createDossier = (body) => apiPost('/api/dossiers', body);
export const getDossier = (id) => apiGet(`/api/dossiers/${id}`);
export const getDossierBoard = (id) => apiGet(`/api/dossiers/${id}/board`);
export const patchDossier = (id, body) => apiPatch(`/api/dossiers/${id}`, body);
export const deleteDossier = (id) => apiDelete(`/api/dossiers/${id}`);
export const duplicateDossier = (id) => apiPost(`/api/dossiers/${id}/duplicate`, {});

export const createDossierGroup = (dossierId, body) =>
  apiPost(`/api/dossiers/${dossierId}/groups`, body);
export const patchDossierGroup = (dossierId, groupId, body) =>
  apiPatch(`/api/dossiers/${dossierId}/groups/${groupId}`, body);
export const reorderDossierGroups = (dossierId, groupIds) =>
  apiPut(`/api/dossiers/${dossierId}/groups/order`, { group_ids: groupIds });
export const deleteDossierGroup = (dossierId, groupId) =>
  apiDelete(`/api/dossiers/${dossierId}/groups/${groupId}`);

export const addDossierDocuments = (dossierId, documentIds, groupId = null) =>
  apiPost(`/api/dossiers/${dossierId}/documents`, {
    document_ids: documentIds,
    group_id: groupId,
  });

export const createDossierItem = (dossierId, body) =>
  apiPost(`/api/dossiers/${dossierId}/items`, body);
export const uploadDossierImage = (dossierId, file) => {
  const body = new FormData();
  body.append('file', file);
  return apiFetch(`/api/dossiers/${dossierId}/images`, { method: 'POST', body });
};
export const dossierImageUrl = (dossierId, itemId) =>
  authedUrl(`${getBaseUrl()}/api/dossiers/${dossierId}/items/${itemId}/image`);
export const patchDossierItem = (dossierId, itemId, body) =>
  apiPatch(`/api/dossiers/${dossierId}/items/${itemId}`, body);
export const reorderDossierItems = (dossierId, placements) =>
  apiPut(`/api/dossiers/${dossierId}/items/order`, { placements });
export const deleteDossierItems = (dossierId, itemIds) =>
  apiPost(`/api/dossiers/${dossierId}/items/batch-delete`, { item_ids: itemIds });
export const restoreDossierItems = (dossierId, items) =>
  apiPost(`/api/dossiers/${dossierId}/items/batch-restore`, { items });
export const deleteDossierItem = (dossierId, itemId) =>
  apiDelete(`/api/dossiers/${dossierId}/items/${itemId}`);
