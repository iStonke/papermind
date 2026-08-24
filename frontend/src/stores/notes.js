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
  // Signal: eine bestimmte Notiz im NotesWorkspace öffnen (z. B. aus dem
  // Dokument-Detailbereich „Notizen"). NotesWorkspace konsumiert es beim Mount/Watch.
  const pendingOpenId = ref(null);
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

  function requestOpen(id) { pendingOpenId.value = id || null; }
  function consumeOpen() {
    const id = pendingOpenId.value;
    pendingOpenId.value = null;
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
    const optimisticDetail = previousDetail ? { ...previousDetail, ...patch } : null;
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

  return {
    notes,
    loaded,
    pendingOpenId,
    fetchNotes,
    searchNotes,
    ensureLoaded,
    create,
    peek,
    get,
    update,
    trash,
    deletePermanently,
    removeFromList,
    remove,
    requestOpen,
    consumeOpen,
  };
});
