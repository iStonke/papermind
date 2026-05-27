/**
 * useDocumentStore
 *
 * Verwaltet die Dokumentenliste, das ausgewählte Dokument und
 * alle direkten CRUD-Operationen gegen die API.
 *
 * Komplexe Orchestrierung (selectDocument, saveMetadata) bleibt
 * vorerst in App.vue, da sie viele UI-Refs referenziert.
 * Die Store-Refs sind als computed-Proxies in App.vue nutzbar.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  deleteDocument as apiDeleteDocument,
  getDocument,
  listDocuments,
  listSmartFolderDocuments,
  markDocumentViewed,
  patchDocument as apiPatchDocument,
  queueOcr,
  runAutoTags,
  setDocumentTags,
} from '../api/documents.js';
import { mapApiError, useNotifications } from './notifications.js';

export const useDocumentStore = defineStore('documents', () => {
  const { notify } = useNotifications();

  // ── State ──────────────────────────────────────────────────────────────
  const documents            = ref([]);
  const selectedDocumentId   = ref(null);
  const selectedDocumentDetail = ref(null);
  const isLoadingDocuments   = ref(false);

  // ── Helpers ────────────────────────────────────────────────────────────
  function patchDocumentInList(updatedDoc) {
    const idx = documents.value.findIndex((d) => d.id === updatedDoc.id);
    if (idx >= 0) {
      documents.value.splice(idx, 1, { ...documents.value[idx], ...updatedDoc });
    }
  }

  // ── API Actions ────────────────────────────────────────────────────────

  /**
   * Lädt die Dokumentenliste.
   * @param {string} queryString - fertig gebauter Query-String
   * @param {string|null} [smartFolderId] - wenn gesetzt, Ordner-Endpoint
   */
  async function fetchDocuments(queryString, smartFolderId = null) {
    isLoadingDocuments.value = true;
    try {
      const payload = smartFolderId
        ? await listSmartFolderDocuments(smartFolderId, queryString)
        : await listDocuments(queryString);
      documents.value = payload?.items ?? [];
    } catch (error) {
      const message = mapApiError(error, 'Dokumente konnten nicht geladen werden.');
      notify({ type: 'error', message });
    } finally {
      isLoadingDocuments.value = false;
    }
  }

  /** Lädt Detaildaten eines einzelnen Dokuments. */
  async function fetchDocumentDetail(documentId) {
    if (!documentId) {
      selectedDocumentDetail.value = null;
      return null;
    }
    const detail = await getDocument(documentId);
    selectedDocumentDetail.value = detail;
    return detail;
  }

  /** Markiert ein Dokument als gelesen (optimistisch). */
  async function markViewed(documentId) {
    const listDoc   = documents.value.find((d) => d.id === documentId);
    const detailDoc = selectedDocumentDetail.value?.id === documentId ? selectedDocumentDetail.value : null;
    const wasUnread = Boolean(listDoc?.is_unread ?? detailDoc?.is_unread);
    if (!wasUnread) return;

    // Optimistisch in Liste + Detail aktualisieren
    if (listDoc)   patchDocumentInList({ id: documentId, is_unread: false });
    if (detailDoc) selectedDocumentDetail.value = { ...detailDoc, is_unread: false };

    try {
      await markDocumentViewed(documentId);
    } catch {
      // Rollback
      if (listDoc)   patchDocumentInList({ id: documentId, is_unread: true });
      if (detailDoc) selectedDocumentDetail.value = { ...detailDoc, is_unread: true };
    }
  }

  /** PATCH /api/documents/{id} */
  async function patchDocument(id, body) {
    const updated = await apiPatchDocument(id, body);
    if (updated?.id) {
      patchDocumentInList(updated);
      if (selectedDocumentDetail.value?.id === updated.id) {
        selectedDocumentDetail.value = updated;
      }
    }
    return updated;
  }

  /** DELETE /api/documents/{id} */
  async function deleteDocument(id) {
    await apiDeleteDocument(id);
    documents.value = documents.value.filter((d) => d.id !== id);
    if (selectedDocumentId.value === id) {
      selectedDocumentId.value   = null;
      selectedDocumentDetail.value = null;
    }
  }

  /** POST /api/documents/{id}/tags */
  async function syncTags(documentId, tagIds) {
    const detail = await setDocumentTags(documentId, tagIds);
    if (detail?.id) {
      if (selectedDocumentId.value === detail.id) {
        selectedDocumentDetail.value = detail;
      }
      patchDocumentInList(detail);
    }
    return detail;
  }

  /** POST /api/documents/{id}/auto-tags */
  async function triggerAutoTags(documentId) {
    return runAutoTags(documentId);
  }

  /** POST /api/documents/{id}/ocr */
  async function triggerOcr(documentId) {
    return queueOcr(documentId);
  }

  return {
    // State
    documents,
    selectedDocumentId,
    selectedDocumentDetail,
    isLoadingDocuments,
    // Helpers
    patchDocumentInList,
    // Actions
    fetchDocuments,
    fetchDocumentDetail,
    markViewed,
    patchDocument,
    deleteDocument,
    syncTags,
    triggerAutoTags,
    triggerOcr,
  };
});
