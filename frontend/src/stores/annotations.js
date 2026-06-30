/**
 * useAnnotationStore
 *
 * Hält die Markierungen/Notizen/Verknüpfungen des AKTUELL geöffneten Dokuments.
 * Bewusst single-document: beim Dokumentwechsel wird neu geladen (race-sicher
 * über documentId-Abgleich). Markierungen sind ein Overlay – das Original-PDF
 * bleibt unangetastet.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

import {
  createAnnotation as apiCreate,
  deleteAnnotation as apiDelete,
  listAnnotations as apiList,
  updateAnnotation as apiUpdate,
} from '../api/annotations.js';
import { mapApiError, useNotifications } from './notifications.js';

export const useAnnotationStore = defineStore('annotations', () => {
  const { notify } = useNotifications();

  const annotations = ref([]);
  const documentId = ref(null);
  const isLoading = ref(false);

  /** Lädt die Markierungen für ein Dokument (leert vorher; race-sicher). */
  async function load(docId) {
    documentId.value = docId || null;
    annotations.value = [];
    if (!docId) return;
    isLoading.value = true;
    try {
      const payload = await apiList(docId);
      if (documentId.value !== docId) return; // Dokument zwischenzeitlich gewechselt
      annotations.value = payload?.items ?? [];
    } catch (error) {
      console.error('Annotationen konnten nicht geladen werden:', error);
    } finally {
      if (documentId.value === docId) isLoading.value = false;
    }
  }

  /** Legt eine Markierung an und hängt sie an die lokale Liste. */
  async function create(docId, payload) {
    try {
      const created = await apiCreate(docId, payload);
      if (documentId.value === docId) {
        annotations.value = [...annotations.value, created];
      }
      return created;
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Markierung konnte nicht gespeichert werden.') });
      return null;
    }
  }

  /** Aktualisiert Farbe/Kommentar/Verknüpfung einer Markierung. */
  async function update(id, patch) {
    try {
      const updated = await apiUpdate(id, patch);
      annotations.value = annotations.value.map((a) => (a.id === id ? updated : a));
      return updated;
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Markierung konnte nicht aktualisiert werden.') });
      return null;
    }
  }

  /** Entfernt eine Markierung (optimistisch, mit Rollback bei Fehler). */
  async function remove(id) {
    const previous = annotations.value;
    annotations.value = annotations.value.filter((a) => a.id !== id);
    try {
      await apiDelete(id);
    } catch (error) {
      annotations.value = previous;
      notify({ type: 'error', message: mapApiError(error, 'Markierung konnte nicht gelöscht werden.') });
    }
  }

  return { annotations, documentId, isLoading, load, create, update, remove };
});
