/**
 * useCorrespondentStore
 *
 * Verwaltet die Liste der kanonischen Korrespondenten (Absender/Aussteller)
 * sowie das Anlegen neuer Korrespondenten und das Hinzufügen von Aliasen.
 * Speist u. a. das Korrespondenten-Feld im Import-Dialog (AP10 Schritt 6).
 */
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  addCorrespondentAlias as apiAddAlias,
  createCorrespondent as apiCreateCorrespondent,
  deleteCorrespondent as apiDeleteCorrespondent,
  deleteCorrespondentAlias as apiDeleteAlias,
  listCorrespondents,
  unlinkCorrespondentDocuments as apiUnlinkCorrespondentDocuments,
  updateCorrespondent as apiUpdateCorrespondent,
} from '../api/correspondents.js';
import { mapApiError, useNotifications } from './notifications.js';

const NAME_MIN_LENGTH = 2;
const NAME_MAX_LENGTH = 120;
const AUTO_RETRY_AFTER_MS = 5000;

export const useCorrespondentStore = defineStore('correspondents', () => {
  const { notify } = useNotifications();

  const correspondents = ref([]);
  const isLoaded = ref(false);
  const isMutationRunning = ref(false);
  // Verhindert Mehrfach-/Dauerabrufe (z. B. wenn der Endpoint nicht erreichbar
  // ist) und damit eine Konsolen-Fehlerflut.
  let inFlight = null;
  let loadAttempted = false;
  let lastLoadFailedAt = 0;

  /**
   * Für v-autocomplete: { title, value }. Sammlungen stehen geschlossen am
   * Anfang (jeweils A–Z), danach die übrigen Korrespondenten A–Z.
   */
  const correspondentOptions = computed(() =>
    correspondents.value
      .map((c) => ({
        title: c.kind === 'collection' ? `${c.name} · Sammlung` : c.name,
        value: c.id,
        name: c.name,
        kind: c.kind,
        short_name: c.short_name,
        props: {
          prependIcon: c.kind === 'collection' ? 'mdi-shape-outline' : undefined,
        },
      }))
      .sort((a, b) => {
        const aCollection = a.kind === 'collection';
        const bCollection = b.kind === 'collection';
        if (aCollection !== bCollection) return aCollection ? -1 : 1;
        return a.name.localeCompare(b.name, 'de-DE');
      })
  );

  function normalizeName(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  const findById = (id) => correspondents.value.find((c) => c.id === id) ?? null;

  const findByName = (name) => {
    const normalized = normalizeName(name).toLocaleLowerCase('de-DE');
    if (!normalized) return null;
    return (
      correspondents.value.find(
        (c) => normalizeName(c?.name).toLocaleLowerCase('de-DE') === normalized
      ) ?? null
    );
  };

  async function fetchCorrespondents() {
    if (inFlight) return inFlight;
    inFlight = (async () => {
      try {
        const payload = await listCorrespondents(true);
        correspondents.value = payload?.items ?? [];
        isLoaded.value = true;
        lastLoadFailedAt = 0;
      } catch (error) {
        // Nur warnen (nicht error-spammen): typischerweise ist das Backend
        // noch nicht neugestartet, sodass /api/correspondents fehlt.
        lastLoadFailedAt = Date.now();
        console.warn('Korrespondenten konnten nicht geladen werden:', error?.message || error);
      } finally {
        loadAttempted = true;
        inFlight = null;
      }
    })();
    return inFlight;
  }

  async function ensureLoaded() {
    if (isLoaded.value) return;
    // Nach einem fehlgeschlagenen automatischen Versuch kurz pausieren, danach
    // erneut probieren. So heilt sich ein Backend-Neustart ohne Seiten-Reload.
    if (loadAttempted && Date.now() - lastLoadFailedAt < AUTO_RETRY_AFTER_MS) return;
    await fetchCorrespondents();
  }

  /** POST /api/correspondents – legt an oder liefert vorhandenen (idempotent). */
  async function createCorrespondentByName(rawName, { kind = null } = {}) {
    const name = normalizeName(rawName);
    if (name.length < NAME_MIN_LENGTH) {
      notify({ type: 'warning', message: `Korrespondent muss mindestens ${NAME_MIN_LENGTH} Zeichen enthalten.` });
      return { ok: false, reason: 'invalid', name };
    }
    if (name.length > NAME_MAX_LENGTH) {
      notify({ type: 'warning', message: `Korrespondent darf maximal ${NAME_MAX_LENGTH} Zeichen enthalten.` });
      return { ok: false, reason: 'invalid', name };
    }
    isMutationRunning.value = true;
    try {
      const created = await apiCreateCorrespondent(kind ? { name, kind } : { name });
      await fetchCorrespondents();
      notify({ type: 'success', title: 'Korrespondent', message: 'Korrespondent angelegt.' });
      return { ok: true, id: created?.id, name: created?.name || name };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Korrespondent konnte nicht angelegt werden.') });
      throw error;
    } finally {
      isMutationRunning.value = false;
    }
  }

  /** POST /api/correspondents/{id}/aliases */
  async function addAlias(correspondentId, rawAlias) {
    const alias = normalizeName(rawAlias);
    const isRecognitionName = findById(correspondentId)?.kind === 'collection';
    const term = isRecognitionName ? 'Erkennungsname' : 'Alias';
    if (!alias) {
      notify({ type: 'warning', message: `${term} darf nicht leer sein.` });
      return { ok: false };
    }
    isMutationRunning.value = true;
    try {
      const updated = await apiAddAlias(correspondentId, alias);
      await fetchCorrespondents();
      notify({ type: 'success', title: 'Korrespondent', message: `${term} „${alias}" hinzugefügt.` });
      return { ok: true, correspondent: updated };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, `${term} konnte nicht hinzugefügt werden.`) });
      throw error;
    } finally {
      isMutationRunning.value = false;
    }
  }

  async function updateCorrespondent(correspondentId, payload, { silent = false } = {}) {
    isMutationRunning.value = true;
    try {
      const updated = await apiUpdateCorrespondent(correspondentId, payload);
      await fetchCorrespondents();
      // Beim Auto-Speichern keine Erfolgsmeldung (sonst Toast-Flut pro Tastendruck).
      if (!silent) notify({ type: 'success', title: 'Korrespondent', message: 'Korrespondent aktualisiert.' });
      return { ok: true, correspondent: updated };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Korrespondent konnte nicht aktualisiert werden.') });
      throw error;
    } finally {
      isMutationRunning.value = false;
    }
  }

  async function deleteCorrespondent(correspondentId) {
    isMutationRunning.value = true;
    try {
      await apiDeleteCorrespondent(correspondentId);
      await fetchCorrespondents();
      notify({ type: 'success', title: 'Korrespondent', message: 'Korrespondent gelöscht.' });
      return { ok: true };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Korrespondent konnte nicht gelöscht werden.') });
      throw error;
    } finally {
      isMutationRunning.value = false;
    }
  }

  async function unlinkDocuments(correspondentId) {
    isMutationRunning.value = true;
    try {
      const result = await apiUnlinkCorrespondentDocuments(correspondentId);
      await fetchCorrespondents();
      const count = Number(result?.count || 0);
      notify({
        type: 'success',
        title: 'Korrespondent',
        message: count === 1
          ? '1 Dokumentzuordnung wurde gelöst.'
          : `${count} Dokumentzuordnungen wurden gelöst.`,
      });
      return { ok: true, count };
    } catch (error) {
      notify({
        type: 'error',
        message: mapApiError(error, 'Dokumentzuordnungen konnten nicht gelöst werden.'),
      });
      throw error;
    } finally {
      isMutationRunning.value = false;
    }
  }

  async function deleteAlias(correspondentId, aliasId) {
    const isRecognitionName = findById(correspondentId)?.kind === 'collection';
    const term = isRecognitionName ? 'Erkennungsname' : 'Alias';
    isMutationRunning.value = true;
    try {
      const updated = await apiDeleteAlias(correspondentId, aliasId);
      await fetchCorrespondents();
      notify({ type: 'success', title: 'Korrespondent', message: `${term} entfernt.` });
      return { ok: true, correspondent: updated };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, `${term} konnte nicht entfernt werden.`) });
      throw error;
    } finally {
      isMutationRunning.value = false;
    }
  }

  return {
    correspondents,
    isLoaded,
    isMutationRunning,
    correspondentOptions,
    findById,
    findByName,
    fetchCorrespondents,
    ensureLoaded,
    createCorrespondentByName,
    updateCorrespondent,
    deleteCorrespondent,
    unlinkDocuments,
    addAlias,
    deleteAlias,
  };
});
