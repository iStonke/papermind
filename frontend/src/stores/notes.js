import { defineStore } from 'pinia';
import { ref } from 'vue';

import * as api from '../api/notes.js';

// Client-seitige Vorschau-Ableitung – spiegelt derive_body_text im Backend
// (Textknoten + sichtbare Attribute der PaperMind-Nodes), damit der Listentext
// sofort stimmt, ohne die volle Liste neu zu laden.
const NODE_TEXT_ATTRS = {
  documentChip: ['title'],
  wikiLink: ['label'],
  ocrQuote: ['text'],
  aiBlock: ['text'],
};

function pmText(node) {
  if (!node || typeof node !== 'object') return '';
  const parts = [];
  if (node.text) parts.push(String(node.text));
  const attrs = node.attrs || {};
  for (const key of NODE_TEXT_ATTRS[node.type] || []) {
    if (attrs[key]) parts.push(String(attrs[key]));
  }
  for (const child of node.content || []) {
    const t = pmText(child);
    if (t) parts.push(t);
  }
  return parts.join(' ');
}

export function notePreview(bodyJson) {
  return pmText(bodyJson).replace(/\s+/g, ' ').trim().slice(0, 200);
}

export function isNoteEmpty(note) {
  const title = String(note?.title || '').trim();
  const bodyText = note?.body_json !== undefined
    ? notePreview(note.body_json)
    : String(note?.preview || '').trim();
  return !title && !bodyText;
}

export const useNotesStore = defineStore('notes', () => {
  // Listeneinträge: { id, title, preview, created_at, updated_at }
  const notes = ref([]);
  const loaded = ref(false);
  // Vorlagen (M6): eigene, benutzereigene Notiz-Gerüste. Getrennt von `notes`,
  // damit sie nicht im normalen Notizzähler/der Liste auftauchen.
  const templates = ref([]);
  const templatesLoaded = ref(false);
  // Signal: eine bestimmte Notiz im NotesWorkspace öffnen (z. B. aus dem
  // Dokument-Detailbereich „Notizen"). NotesWorkspace konsumiert es beim Mount/Watch.
  const pendingOpenId = ref(null);
  const pendingOpenCursorPosition = ref(null);
  let loadingPromise = null;
  const noteDetails = new Map();
  const detailRequests = new Map();

  function cacheDetail(note) {
    if (note?.id) noteDetails.set(note.id, note);
    return note;
  }

  function sortInPlace() {
    notes.value.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
  }

  async function fetchNotes() {
    const res = await api.listNotes();
    notes.value = res.items || [];
    loaded.value = true;
  }

  /** Servergestützte Volltextsuche, ohne die kanonische Notizenliste zu
   *  ersetzen. So bleiben Zähler, Autosave und das Leeren der Suche stabil. */
  async function searchNotes(query, { scope = 'all' } = {}) {
    const res = await api.listNotes({ q: query, searchScope: scope });
    return res.items || [];
  }

  function ensureLoaded() {
    if (loaded.value) return Promise.resolve();
    if (!loadingPromise) loadingPromise = fetchNotes().finally(() => { loadingPromise = null; });
    return loadingPromise;
  }

  /** Legt eine Notiz an (optional vorbelegt, z. B. mit verknüpftem Dokument)
   *  und gibt das volle Objekt (inkl. body_json) zurück. */
  async function create(initial = {}) {
    const note = cacheDetail(await api.createNote(initial));
    notes.value.unshift({
      id: note.id,
      title: note.title,
      preview: notePreview(note.body_json),
      created_at: note.created_at,
      updated_at: note.updated_at,
    });
    return note;
  }

  // --- Vorlagen (M6) ---------------------------------------------------------
  async function fetchTemplates() {
    const res = await api.listNoteTemplates();
    templates.value = res.items || [];
    templatesLoaded.value = true;
  }

  function ensureTemplatesLoaded() {
    if (templatesLoaded.value) return Promise.resolve();
    return fetchTemplates();
  }

  /** Legt aus einer Vorlage eine neue, reguläre Notiz an und gibt sie zurück. */
  async function createFromTemplate(templateId) {
    const note = cacheDetail(await api.createNoteFromTemplate(templateId));
    notes.value.unshift({
      id: note.id,
      title: note.title,
      preview: notePreview(note.body_json),
      created_at: note.created_at,
      updated_at: note.updated_at,
    });
    return note;
  }

  /** Speichert eine bestehende Notiz als (neue) Vorlage. */
  async function saveAsTemplate(id, { title = '' } = {}) {
    const template = await api.saveNoteAsTemplate(id, { title });
    templates.value.unshift({
      id: template.id,
      title: template.title,
      preview: notePreview(template.body_json),
      created_at: template.created_at,
      updated_at: template.updated_at,
    });
    return template;
  }

  function requestOpen(id, { cursorPosition = null } = {}) {
    pendingOpenId.value = id || null;
    pendingOpenCursorPosition.value = ['start', 'end'].includes(cursorPosition)
      ? cursorPosition
      : null;
  }
  function consumeOpen() {
    const id = pendingOpenId.value;
    pendingOpenId.value = null;
    pendingOpenCursorPosition.value = null;
    return id;
  }

  /** Volles Detail (mit body_json) zum Öffnen im Editor. */
  function peek(id) {
    return noteDetails.get(id) || null;
  }

  function get(id, { refresh = false } = {}) {
    if (!refresh && noteDetails.has(id)) return Promise.resolve(noteDetails.get(id));
    if (!refresh && detailRequests.has(id)) return detailRequests.get(id);

    const request = api.getNote(id)
      .then(cacheDetail)
      .finally(() => {
        if (detailRequests.get(id) === request) detailRequests.delete(id);
      });
    detailRequests.set(id, request);
    return request;
  }

  /** Teilaktualisierung (Autosave). Aktualisiert den Listeneintrag lokal. */
  async function update(id, patch) {
    // Das Detail sofort aktualisieren: Wechselt man während des Requests weg
    // und direkt zurück, darf nicht kurz die ältere Serverfassung erscheinen.
    const previousDetail = noteDetails.get(id) || null;
    // base_revision ist ausschließlich eine Schreibvorbedingung und darf nicht
    // als scheinbares Notizfeld in den Detail-Cache gelangen.
    const optimisticPatch = { ...patch };
    delete optimisticPatch.base_revision;
    delete optimisticPatch.history_reason;
    const optimisticDetail = previousDetail ? { ...previousDetail, ...optimisticPatch } : null;
    if (optimisticDetail) cacheDetail(optimisticDetail);

    let updated;
    try {
      updated = cacheDetail(await api.patchNote(id, patch));
    } catch (error) {
      if (optimisticDetail && noteDetails.get(id) === optimisticDetail) {
        if (previousDetail) noteDetails.set(id, previousDetail);
        else noteDetails.delete(id);
      }
      throw error;
    }
    const item = notes.value.find((n) => n.id === id);
    if (item) {
      item.title = updated.title;
      item.updated_at = updated.updated_at;
      if (patch.body_json !== undefined) item.preview = notePreview(updated.body_json);
    }
    sortInPlace();
    return updated;
  }

  /** Stellt einen historischen Stand wieder her und ersetzt alle lokalen
   *  Detail-/Listencaches durch die vom Server bestätigte neue Revision. */
  async function restoreRevision(id, revisionId, baseRevision) {
    const restored = cacheDetail(await api.restoreNoteRevision(id, revisionId, baseRevision));
    const item = notes.value.find((note) => note.id === id);
    if (item) {
      item.title = restored.title;
      item.preview = notePreview(restored.body_json);
      item.updated_at = restored.updated_at;
    }
    sortInPlace();
    return restored;
  }

  /** Setzt die Tags einer Notiz und aktualisiert Detail-Cache + Listeneintrag. */
  async function setTags(id, { tagIds = [], tags = [] } = {}) {
    const updated = cacheDetail(await api.setNoteTags(id, { tagIds, tags }));
    const item = notes.value.find((n) => n.id === id);
    if (item) item.tags = updated.tags || [];
    return updated;
  }

  async function trash(id) {
    return api.trashNote(id);
  }

  async function deletePermanently(id) {
    const result = await api.deleteNote(id);
    noteDetails.delete(id);
    detailRequests.delete(id);
    return result;
  }

  function removeFromList(id) {
    notes.value = notes.value.filter((n) => n.id !== id);
    noteDetails.delete(id);
    detailRequests.delete(id);
  }

  async function remove(id) {
    await trash(id);
    removeFromList(id);
  }

  /**
   * Sammelaktion der Verwaltungsfläche. Der Aufrufer entscheidet, welche
   * Listen danach neu geladen werden – hier bleibt nur die Detail-Cache-Pflege.
   */
  async function bulk(action, ids) {
    const result = await api.bulkNotes({ action, ids });
    if (action === 'delete') {
      for (const id of ids) {
        noteDetails.delete(id);
        detailRequests.delete(id);
      }
    }
    return result?.affected ?? 0;
  }

  return {
    notes,
    loaded,
    templates,
    templatesLoaded,
    pendingOpenId,
    pendingOpenCursorPosition,
    fetchNotes,
    searchNotes,
    ensureLoaded,
    fetchTemplates,
    ensureTemplatesLoaded,
    createFromTemplate,
    saveAsTemplate,
    create,
    peek,
    get,
    update,
    restoreRevision,
    setTags,
    trash,
    deletePermanently,
    removeFromList,
    remove,
    bulk,
    requestOpen,
    consumeOpen,
  };
});
