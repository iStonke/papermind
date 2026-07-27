import { parseDocumentDateInput } from './dates.js';

export function normalizeDocumentDisplayName(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

/**
 * Erstellt einen minimalen PATCH für die frei editierbaren Dokumentmetadaten.
 * Ein ungültiges Datum wird bewusst nicht übertragen, damit Änderungen an
 * Dokumentname oder Notizen trotzdem gespeichert werden können.
 */
export function buildDocumentMetadataPatch({
  detail,
  currentNameDraft,
  draftName,
  draftDate,
  draftNotes
}) {
  const parsedDocumentDate = parseDocumentDateInput(draftDate);
  const patchBody = {};
  const normalizedName = normalizeDocumentDisplayName(draftName);
  const normalizedCurrentName = normalizeDocumentDisplayName(currentNameDraft);
  const currentDate = detail?.document_date || null;
  const currentNotes = detail?.notes || '';

  if (normalizedName !== normalizedCurrentName) {
    patchBody.display_name = normalizedName || null;
  }
  if (parsedDocumentDate.ok && parsedDocumentDate.iso !== currentDate) {
    patchBody.document_date = parsedDocumentDate.iso;
  }
  if (String(draftNotes || '') !== currentNotes) {
    patchBody.notes = draftNotes || null;
  }

  return {
    patchBody,
    parsedDocumentDate,
    dateChanged: Object.prototype.hasOwnProperty.call(patchBody, 'document_date'),
    hasChanges: Object.keys(patchBody).length > 0
  };
}
