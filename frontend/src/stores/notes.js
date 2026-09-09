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
  image: ['caption', 'alt', 'title'],
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
  // Favorisierte Notizen für den globalen Favoriten-Bereich (eigener Abschnitt).
  const favoriteNotes = ref([]);
  const favoritesLoaded = ref(false);
  // Vorlagen (M6): eigene, benutzereigene Notiz-Gerüste. Getrennt von `notes`,
  // damit sie nicht im normalen Notizzähler/der Liste auftauchen.
  const templates = ref([]);
  const templatesLoaded = ref(false);
  // Bausteine: benutzereigene Feldblock-Vorlagen (templateBox). Eigenständiges
  // Konzept neben den Ganz-Notiz-Vorlagen.
  const blockTemplates = ref([]);
  const blockTemplatesLoaded = ref(false);
  // Sammlungen (oberste Ebene, harte Partition): { id, name, color, position, note_count }.
  // Genau eine ist aktiv; sie scopt Notizen + Notizbücher. Die aktive Sammlung
  // wird pro Browser persistiert, damit man im letzten „Raum" landet.
  const collections = ref([]);
  const collectionsLoaded = ref(false);
  const ACTIVE_COLLECTION_KEY = 'pm-notes-active-collection-v1';
  function loadActiveCollection() {
    try { return window.localStorage.getItem(ACTIVE_COLLECTION_KEY) || null; } catch { return null; }
  }
  function persistActiveCollection(id) {
    try {
      if (id) window.localStorage.setItem(ACTIVE_COLLECTION_KEY, id);
      else window.localStorage.removeItem(ACTIVE_COLLECTION_KEY);
    } catch { /* Storage ist optional. */ }
  }
  const activeCollectionId = ref(loadActiveCollection());
  // Notizbücher (flache Ablageebene): { id, name, color, position, note_count }.
  const notebooks = ref([]);
  const notebooksLoaded = ref(false);
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
    // Auf die aktive Sammlung gescopt (harte Partition). Ist noch keine gesetzt,
    // liefert der Server ungescopt – ``ensureLoaded`` lädt darum Sammlungen zuerst.
    const res = await api.listNotes({ collectionId: activeCollectionId.value });
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
    // Sammlungen zuerst: sie setzen die aktive Sammlung, nach der Notizen scopen.
    if (!loadingPromise) {
      loadingPromise = ensureCollectionsLoaded()
        .then(fetchNotes)
        .finally(() => { loadingPromise = null; });
    }
    return loadingPromise;
  }

  // --- Sammlungen (oberste Ebene, harte Partition) ---------------------------
  async function fetchCollections() {
    const res = await api.listCollections();
    collections.value = res.items || [];
    // Aktive Sammlung validieren: gespeicherte behalten, sonst die erste nehmen.
    const ids = new Set(collections.value.map((c) => c.id));
    if (!activeCollectionId.value || !ids.has(activeCollectionId.value)) {
      activeCollectionId.value = collections.value[0]?.id || null;
    }
    persistActiveCollection(activeCollectionId.value);
    collectionsLoaded.value = true;
    return collections.value;
  }

  function ensureCollectionsLoaded() {
    if (collectionsLoaded.value) return Promise.resolve(collections.value);
    return fetchCollections();
  }

  /** Wechselt die aktive Sammlung und lädt Notizen + Notizbücher neu (Space-Wechsel). */
  async function setActiveCollection(id) {
    if (!id || id === activeCollectionId.value) return;
    if (!collections.value.some((c) => c.id === id)) return;
    activeCollectionId.value = id;
    persistActiveCollection(id);
    await Promise.all([fetchNotes(), fetchNotebooks()]);
  }

  async function createCollection(payload = {}) {
    const c = await api.createCollection(payload);
    collections.value.push(c);
    return c;
  }

  async function updateCollection(id, payload = {}) {
    const c = await api.updateCollection(id, payload);
    const idx = collections.value.findIndex((x) => x.id === id);
    if (idx !== -1) collections.value.splice(idx, 1, c);
    return c;
  }

  /** Löscht eine Sammlung; nicht-leere hängen ihre Inhalte nach ``reassignTo`` um. */
  async function deleteCollection(id, { reassignTo = null } = {}) {
    await api.deleteCollection(id, { reassignTo });
    const wasActive = activeCollectionId.value === id;
    collections.value = collections.value.filter((c) => c.id !== id);
    if (wasActive) {
      activeCollectionId.value = collections.value[0]?.id || null;
      persistActiveCollection(activeCollectionId.value);
    }
    await fetchCollections();
    if (wasActive || reassignTo === activeCollectionId.value) {
      await Promise.all([fetchNotes(), fetchNotebooks()]);
    }
  }

  /** Reihenfolge der Sammlungen (optimistisch, dann serverbestätigt). */
  async function reorderCollections(ids) {
    const byId = new Map(collections.value.map((c) => [c.id, c]));
    const next = ids.map((id) => byId.get(id)).filter(Boolean);
    for (const c of collections.value) if (!ids.includes(c.id)) next.push(c);
    collections.value = next;
    const res = await api.reorderCollections(ids);
    collections.value = res.items || collections.value;
    return collections.value;
  }

  /** Verschiebt Notizen in eine andere Sammlung (koppelt ihr Notizbuch ab). */
  async function moveToCollection(ids, collectionId) {
    const result = await api.moveNotesToCollection({ ids, collectionId });
    if (collectionId !== activeCollectionId.value) {
      // Verschobene Notizen verlassen die aktive (gescopte) Liste.
      const idSet = new Set(ids);
      notes.value = notes.value.filter((n) => !idSet.has(n.id));
      for (const id of ids) {
        const detail = noteDetails.get(id);
        if (detail) { detail.collection_id = collectionId; detail.notebook_id = null; }
      }
    }
    // Zähler der Sammlungen und Notizbücher (abgekoppelt) auffrischen.
    fetchCollections().catch(() => {});
    fetchNotebooks().catch(() => {});
    return result?.affected ?? 0;
  }

  /** Legt eine Notiz an (optional vorbelegt, z. B. mit verknüpftem Dokument)
   *  und gibt das volle Objekt (inkl. body_json) zurück. */
  async function create(initial = {}) {
    // Neue echte Notiz landet in der aktiven Sammlung, sofern nicht anders
    // vorbelegt (ein gewähltes Notizbuch bestimmt die Sammlung serverseitig).
    const payload = { ...initial };
    if (!payload.is_template && !payload.notebook_id && payload.collection_id == null && activeCollectionId.value) {
      payload.collection_id = activeCollectionId.value;
    }
    const note = cacheDetail(await api.createNote(payload));
    // Eine Dashboard-Schnellnotiz kann gezielt in einer anderen Sammlung
    // entstehen. Eine bereits geladene, sammlungsbezogene Liste darf sie dann
    // nicht vorübergehend im falschen Bereich anzeigen.
    if (!loaded.value || note.collection_id === activeCollectionId.value) {
      notes.value.unshift({
        id: note.id,
        title: note.title,
        preview: notePreview(note.body_json),
        notebook_id: note.notebook_id ?? null,
        collection_id: note.collection_id ?? null,
        is_favorite: note.is_favorite ?? false,
        created_at: note.created_at,
        updated_at: note.updated_at,
      });
    }
    if (note.notebook_id) bumpNotebookCount(note.notebook_id, 1);
    if (note.collection_id) bumpCollectionCount(note.collection_id, 1);
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
      notebook_id: note.notebook_id ?? null,
      collection_id: note.collection_id ?? null,
      is_favorite: note.is_favorite ?? false,
      created_at: note.created_at,
      updated_at: note.updated_at,
    });
    if (note.notebook_id) bumpNotebookCount(note.notebook_id, 1);
    if (note.collection_id) bumpCollectionCount(note.collection_id, 1);
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

  // --- Bausteine (Feldblock-Vorlagen) ----------------------------------------
  async function fetchBlockTemplates() {
    const res = await api.listBlockTemplates();
    blockTemplates.value = res.items || [];
    blockTemplatesLoaded.value = true;
    return blockTemplates.value;
  }

  function ensureBlockTemplatesLoaded() {
    if (blockTemplatesLoaded.value) return Promise.resolve(blockTemplates.value);
    return fetchBlockTemplates();
  }

  async function createBlockTemplate(payload = {}) {
    const tpl = await api.createBlockTemplate(payload);
    blockTemplates.value.unshift(tpl);
    return tpl;
  }

  async function updateBlockTemplate(id, payload = {}) {
    const tpl = await api.updateBlockTemplate(id, payload);
    const idx = blockTemplates.value.findIndex((t) => t.id === id);
    if (idx !== -1) blockTemplates.value.splice(idx, 1, tpl);
    return tpl;
  }

  async function deleteBlockTemplate(id) {
    await api.deleteBlockTemplate(id);
    blockTemplates.value = blockTemplates.value.filter((t) => t.id !== id);
  }

  // --- Notizbücher (flache Ablageebene) --------------------------------------
  function bumpNotebookCount(notebookId, delta) {
    if (!notebookId) return;
    const nb = notebooks.value.find((n) => n.id === notebookId);
    if (nb) nb.note_count = Math.max(0, (nb.note_count || 0) + delta);
  }

  // Sammlungs-Zähler lokal pflegen (analog Notizbuch), damit er ohne Neuladen
  // sofort stimmt – Anlegen/Papierkorb/Wiederherstellen ändern ihn.
  function bumpCollectionCount(collectionId, delta) {
    if (!collectionId) return;
    const c = collections.value.find((x) => x.id === collectionId);
    if (c) c.note_count = Math.max(0, (c.note_count || 0) + delta);
  }

  async function fetchNotebooks() {
    // Notizbücher der aktiven Sammlung (harte Partition).
    const res = await api.listNotebooks(activeCollectionId.value);
    notebooks.value = res.items || [];
    notebooksLoaded.value = true;
    return notebooks.value;
  }

  function ensureNotebooksLoaded() {
    if (notebooksLoaded.value) return Promise.resolve(notebooks.value);
    return ensureCollectionsLoaded().then(fetchNotebooks);
  }

  async function createNotebook(payload = {}) {
    const nb = await api.createNotebook(payload);
    notebooks.value.push(nb);
    return nb;
  }

  async function updateNotebook(id, payload = {}) {
    const nb = await api.updateNotebook(id, payload);
    const idx = notebooks.value.findIndex((n) => n.id === id);
    if (idx !== -1) notebooks.value.splice(idx, 1, nb);
    return nb;
  }

  /** Setzt die Reihenfolge der Notizbücher (optimistisch, dann serverbestätigt). */
  async function reorderNotebooks(ids) {
    const byId = new Map(notebooks.value.map((n) => [n.id, n]));
    const next = ids.map((id) => byId.get(id)).filter(Boolean);
    for (const n of notebooks.value) if (!ids.includes(n.id)) next.push(n);
    notebooks.value = next;
    const res = await api.reorderNotebooks(ids);
    notebooks.value = res.items || notebooks.value;
    return notebooks.value;
  }

  async function deleteNotebook(id) {
    await api.deleteNotebook(id);
    notebooks.value = notebooks.value.filter((n) => n.id !== id);
    // Enthaltene Notizen rutschen serverseitig nach „Ohne Notizbuch"; lokale
    // Listeneinträge nachziehen, damit Filter/Zähler sofort stimmen.
    for (const item of notes.value) {
      if (item.notebook_id === id) item.notebook_id = null;
    }
  }

  /** Verschiebt Notizen in ein Notizbuch (notebookId=null → heraus). */
  async function moveToNotebook(ids, notebookId = null) {
    const result = await api.moveNotesToNotebook({ ids, notebookId });
    const idSet = new Set(ids);
    for (const item of notes.value) {
      if (!idSet.has(item.id)) continue;
      const prev = item.notebook_id ?? null;
      if (prev === notebookId) continue;
      bumpNotebookCount(prev, -1);
      bumpNotebookCount(notebookId, 1);
      item.notebook_id = notebookId;
      const detail = noteDetails.get(item.id);
      if (detail) detail.notebook_id = notebookId;
    }
    return result?.affected ?? 0;
  }

  /** Lädt die favorisierten Notizen für den globalen Favoriten-Bereich. */
  async function fetchFavorites() {
    const res = await api.listNotes({ favoritesOnly: true });
    favoriteNotes.value = res.items || [];
    favoritesLoaded.value = true;
    return favoriteNotes.value;
  }

  function syncFavoriteList(item, favorite) {
    if (!item) return;
    const idx = favoriteNotes.value.findIndex((n) => n.id === item.id);
    if (favorite && idx === -1) favoriteNotes.value.unshift({ ...item, is_favorite: true });
    else if (!favorite && idx !== -1) favoriteNotes.value.splice(idx, 1);
  }

  /** Favorisiert eine Notiz oder hebt es auf (Metadaten, kein Revisions-Bump). */
  async function setFavorite(id, favorite) {
    const item = notes.value.find((n) => n.id === id)
      || favoriteNotes.value.find((n) => n.id === id);
    const detail = noteDetails.get(id);
    // Optimistisch umschalten – Stern/Sortierung sollen ohne Verzögerung reagieren.
    if (item) item.is_favorite = favorite;
    if (detail) detail.is_favorite = favorite;
    syncFavoriteList(item || (detail && { id, title: detail.title, preview: notePreview(detail.body_json) }), favorite);
    try {
      const updated = await api.patchNote(id, { is_favorite: favorite });
      if (item) item.is_favorite = updated.is_favorite;
      cacheDetail(updated);
      return updated;
    } catch (error) {
      if (item) item.is_favorite = !favorite;
      if (detail) detail.is_favorite = !favorite;
      syncFavoriteList(item, !favorite);
      throw error;
    }
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
    // Sammlung der Notiz vor dem Verschieben ermitteln (Zähler pflegen).
    const collectionId = notes.value.find((n) => n.id === id)?.collection_id
      ?? noteDetails.get(id)?.collection_id ?? null;
    const result = await api.trashNote(id);
    if (collectionId) bumpCollectionCount(collectionId, -1);
    return result;
  }

  async function restore(id) {
    const note = cacheDetail(await api.restoreNote(id));
    const item = { ...note, preview: notePreview(note.body_json) };
    const index = notes.value.findIndex((entry) => entry.id === note.id);
    if (index >= 0) notes.value.splice(index, 1, item);
    else notes.value.push(item);
    if (note.collection_id) bumpCollectionCount(note.collection_id, 1);
    sortInPlace();
    return note;
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
    // Papierkorb/Wiederherstellen ändern die Sammlungs-Zähler; serverseitig
    // resynchronisieren (Vorlagen-Ableitung lässt Originale in ihrer Sammlung).
    if (action === 'trash' || action === 'restore') {
      fetchCollections().catch(() => {});
    }
    return result?.affected ?? 0;
  }

  return {
    notes,
    loaded,
    templates,
    templatesLoaded,
    favoriteNotes,
    favoritesLoaded,
    fetchFavorites,
    pendingOpenId,
    pendingOpenCursorPosition,
    fetchNotes,
    searchNotes,
    ensureLoaded,
    fetchTemplates,
    ensureTemplatesLoaded,
    createFromTemplate,
    saveAsTemplate,
    blockTemplates,
    blockTemplatesLoaded,
    fetchBlockTemplates,
    ensureBlockTemplatesLoaded,
    createBlockTemplate,
    updateBlockTemplate,
    deleteBlockTemplate,
    collections,
    collectionsLoaded,
    activeCollectionId,
    fetchCollections,
    ensureCollectionsLoaded,
    setActiveCollection,
    createCollection,
    updateCollection,
    deleteCollection,
    reorderCollections,
    moveToCollection,
    notebooks,
    notebooksLoaded,
    fetchNotebooks,
    ensureNotebooksLoaded,
    createNotebook,
    updateNotebook,
    deleteNotebook,
    reorderNotebooks,
    moveToNotebook,
    setFavorite,
    create,
    peek,
    get,
    update,
    restoreRevision,
    setTags,
    trash,
    deletePermanently,
    restore,
    removeFromList,
    remove,
    bulk,
    requestOpen,
    consumeOpen,
  };
});
