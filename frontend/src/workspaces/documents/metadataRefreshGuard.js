function hasText(value) {
  return String(value || '').trim().length > 0;
}

/**
 * Entscheidet, ob ein stiller Server-Refresh den sichtbaren Drawer-Entwurf
 * unangetastet lassen muss. Berücksichtigt neben Textfeldern auch teleportierte
 * Menüs, noch laufende Vokabular-Saves und eine lediglich eingetippte Tag-Suche.
 */
export function shouldPreserveMetadataDraft({
  documentId,
  draftDocumentId,
  editorHasFocus = false,
  metadataDirty = false,
  tagSelectionDirty = false,
  tagQuery = '',
  tagSearch = '',
  categoryDirty = false,
  correspondentDirty = false,
  hasPendingMutation = false,
} = {}) {
  if (!documentId || draftDocumentId !== documentId) return false;
  return Boolean(
    editorHasFocus
    || metadataDirty
    || tagSelectionDirty
    || hasText(tagQuery)
    || hasText(tagSearch)
    || categoryDirty
    || correspondentDirty
    || hasPendingMutation
  );
}

export function tagQueryIsEmpty(tagQuery, tagSearch) {
  return !hasText(tagQuery) && !hasText(tagSearch);
}
