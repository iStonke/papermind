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
  // IDs von Entwürfen, die radiert wurden, während ihr create() noch unterwegs
  // war (siehe create()/remove() unten) — verhindert, dass sie nach der
  // Server-Antwort ungewollt wieder auftauchen.
  const pendingRemovals = new Set();

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

  /**
   * Legt eine Markierung an — optimistisch: erscheint SOFORT lokal (mit
   * temporärer ID), noch bevor die Server-Antwort da ist. Ohne das gab es
   * ein Zeitfenster (Netzwerk-Laufzeit) direkt nach dem Zeichnen, in dem die
   * Zeichnung nirgends existierte (Entwurf schon zerstört, echte Markierung
   * noch nicht gerendert) — ein Klick mit dem Radierer in genau diesem
   * Moment traf dadurch ins Leere.
   */
  async function create(docId, payload) {
    const tempId = `temp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const isCurrentDoc = documentId.value === docId;
    if (isCurrentDoc) {
      annotations.value = [...annotations.value, { ...payload, id: tempId }];
    }
    try {
      const created = await apiCreate(docId, payload);
      if (pendingRemovals.has(tempId)) {
        // Wurde radiert, während die Anfrage noch lief — Server-Eintrag
        // gleich wieder löschen, damit er nicht doch noch auftaucht.
        pendingRemovals.delete(tempId);
        apiDelete(created.id).catch(() => {});
        return created;
      }
      if (documentId.value === docId) {
        annotations.value = annotations.value.map((a) => (a.id === tempId ? created : a));
      }
      return created;
    } catch (error) {
      if (documentId.value === docId) {
        annotations.value = annotations.value.filter((a) => a.id !== tempId);
      }
      pendingRemovals.delete(tempId);
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
    if (String(id).startsWith('temp-')) {
      // Entwurf, dessen create() noch unterwegs ist: lokal sofort entfernen;
      // create() räumt den Server-Eintrag nach, sobald die Antwort da ist.
      pendingRemovals.add(id);
      annotations.value = annotations.value.filter((a) => a.id !== id);
      return;
    }
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
