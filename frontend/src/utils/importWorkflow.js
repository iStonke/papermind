import { parseDocumentDateInput } from './dates.js';

const EMPTY = /^(?:ohne betreff|kein betreff|unbekannt|unknown|null|none|n\/a|nicht erkannt|unbenannt|untitled|sonstiges|neues dokument|dokument|scan(?:\s*[-–]\s*\d[\d. -]*)?)$/iu;
export function meaningfulSuggestion(value) {
  const text = String(value || '').replace(/\s+/gu, ' ').trim();
  return text && !EMPTY.test(text) && !/^ohne betreff(?:$|[\s:–-])/iu.test(text) ? text : '';
}
export function canOfferTitle(document) {
  const suggestion = meaningfulSuggestion(document?.meta?.titleSuggestion);
  const current = String(document?.title || '').replace(/\s+/gu, ' ').trim();
  return Boolean(suggestion && suggestion.toLocaleLowerCase('de-DE') !== current.toLocaleLowerCase('de-DE')
    && !document?.meta?.titleSuggestionUsedFallback && document?.meta?.dismissedTitle !== suggestion);
}
export function sourcePages(document, sourceMeta = new Map()) {
  return (document?.pages || []).map(page => ({
    source_file_id: page.sourceFileId, page_index: page.pageIndex, rotation: page.rotation || 0,
    color_mode: page.colorMode || 'auto', source_revision: sourceMeta.get(page.sourceFileId)?.sourceRevision || null,
  }));
}
export function documentRevision(document, sourceMeta) {
  return hashRevision(sourcePages(document, sourceMeta));
}
// Analysis always reads the prepared source, independently of display colour.
export function analysisRevision(document, sourceMeta) {
  return hashRevision(sourcePages(document, sourceMeta).map(({ color_mode, ...page }) => page));
}
export function pageDisplayRevision(page, sourceMeta) {
  return hashRevision([page.id, sourcePages({ pages: [page] }, sourceMeta)[0], page.thumbUrl || '']);
}
function hashRevision(value) {
  const serialized = JSON.stringify(value);
  let first = 2166136261;
  let second = 5381;
  for (const character of serialized) {
    first = Math.imul(first ^ character.charCodeAt(0), 16777619);
    second = Math.imul(second, 33) ^ character.charCodeAt(0);
  }
  return `r2:${serialized.length}:${first >>> 0}:${second >>> 0}`;
}
export function defaultImportForm() {
  return { date: '', category: null, note: '', correspondentId: null, retention: null,
    touched: {}, aiFilled: {}, revisions: {}, proposals: {}, previousValues: {}, dismissed: {} };
}
export function ensureImportForm(document) {
  if (!document) return defaultImportForm();
  document.meta ||= {};
  const form = document.meta.form ||= defaultImportForm();
  for (const name of ['touched', 'aiFilled', 'revisions', 'proposals', 'previousValues', 'dismissed']) form[name] ||= {};
  return form;
}
export function validateImportDocument(document, { requireComplete = true } = {}) {
  const form = ensureImportForm(document);
  const errors = {};
  const title = String(document.title || '').trim();
  const date = String(form.date || '').trim();
  if (!title && requireComplete) errors.title = 'Bitte einen Dokumentnamen eingeben.';
  else if (title && document.title.length > 200) errors.title = 'Der Dokumentname darf höchstens 200 Zeichen enthalten.';
  if (!date && requireComplete) errors.date = 'Bitte ein Dokumentdatum eingeben.';
  else if (date && !parseDocumentDateInput(form.date).ok) errors.date = 'Bitte ein gültiges Datum eingeben, z. B. 15.10.2026.';
  if (requireComplete && !String(form.category || '').trim()) errors.category = 'Bitte einen Dokumenttyp wählen.';
  const correspondent = typeof form.correspondentId === 'object' && form.correspondentId
    ? form.correspondentId.value || form.correspondentId.id || form.correspondentId.name || form.correspondentId.title : form.correspondentId;
  if (requireComplete && !String(correspondent || '').trim()) errors.correspondent = 'Bitte einen Korrespondenten wählen.';
  const hasTag = [...(document.tags || []), ...(document.meta?.pendingTagNames || [])].some(tag => String(tag || '').trim());
  if (requireComplete && !hasTag) errors.tags = 'Bitte mindestens einen Tag hinzufügen.';
  if (String(form.note || '').length > 10000) errors.note = 'Die Notiz darf höchstens 10.000 Zeichen enthalten.';
  if (requireComplete && !document.pages?.length) errors.pages = 'Bitte mindestens eine Seite hinzufügen.';
  return errors;
}
export function applyFieldProposal(document, field, value, expectedRevision, read, write, origin = 'KI') {
  const form = ensureImportForm(document);
  const current = read();
  if (JSON.stringify(value) === JSON.stringify(current)) {
    if (!form.touched[field] && form.aiFilled[field] && origin === 'KI') form.aiFilled[field] = origin;
    delete form.proposals[field];
    return false;
  }
  if (JSON.stringify(value) === JSON.stringify(form.dismissed[field])) return false;
  const words = text => String(text || '').toLocaleLowerCase('de-DE').match(/[\p{L}\p{N}]{3,}/gu) || [];
  const clearerTitle = field === 'title' && origin === 'KI' && form.aiFilled[field] === 'Regeln'
    && words(current).length > 0 && String(value).length > String(current).length && words(current).every(word => words(value).includes(word));
  const expandedTags = field === 'tags' && Array.isArray(value) && Array.isArray(current) && current.every(tag => value.includes(tag));
  const replacesAutomaticValue = form.aiFilled[field] && current != null && current !== ''
    && !clearerTitle && !expandedTags;
  if ((form.revisions[field] || 0) !== expectedRevision || form.touched[field] || replacesAutomaticValue) {
    if (value != null && value !== '') form.proposals[field] = { value, origin };
    return false;
  }
  if (!(field in form.previousValues)) form.previousValues[field] = current;
  write(value);
  form.aiFilled[field] = origin;
  delete form.proposals[field];
  return true;
}
export function commitSubset(documents, selectedPageIds = null) {
  return documents.map(document => ({ document, pages: document.pages.filter(page => !selectedPageIds || selectedPageIds.has(page.id)) }))
    .filter(entry => entry.pages.length > 0);
}
