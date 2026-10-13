const storagePrefix = grouping => grouping === 'document_types'
  ? 'pm.documents.document-types.expanded.v1:' : 'pm.documents.correspondents.expanded.v1:';
const validGroupKey = (key, grouping) => typeof key === 'string'
  && (key === 'unassigned' || (grouping === 'document_types'
    ? key.startsWith('type:') && key.length > 5 && key.length <= 1000
    : /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(key)));

export function loadGroupExpansion(ownerId, storage, grouping = 'correspondents') {
  if (!ownerId) return new Set();
  try {
    const saved = JSON.parse((storage ?? globalThis.localStorage).getItem(`${storagePrefix(grouping)}${ownerId}`));
    return new Set(Array.isArray(saved) ? saved.filter(key => validGroupKey(key, grouping)) : []);
  } catch {
    return new Set();
  }
}

export function saveGroupExpansion(ownerId, expanded, storage, grouping = 'correspondents') {
  if (!ownerId) return;
  try {
    (storage ?? globalThis.localStorage).setItem(
      `${storagePrefix(grouping)}${ownerId}`, JSON.stringify([...expanded].filter(key => validGroupKey(key, grouping))),
    );
  } catch { /* The open groups still remain available for this view. */ }
}
