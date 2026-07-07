/**
 * useTagStore
 *
 * Verwaltet die Tag-Liste und alle Tag-CRUD-Operationen.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  createTag as apiCreateTag,
  deleteTag as apiDeleteTag,
  listTags,
  mergeTag as apiMergeTag,
  renameTag as apiRenameTag,
} from '../api/tags.js';
import { mapApiError, useNotifications } from './notifications.js';

const VOCAB_NAME_MIN_LENGTH = 2;
const VOCAB_NAME_MAX_LENGTH = 30;

export const useTagStore = defineStore('tags', () => {
  const { notify } = useNotifications();

  // ── State ──────────────────────────────────────────────────────────────
  const tags               = ref([]);
  const isTagMutationRunning = ref(false);

  // ── Helpers ────────────────────────────────────────────────────────────
  function normalizeTagName(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function validateTagName(name) {
    if (name.length < VOCAB_NAME_MIN_LENGTH) {
      return `Tag muss mindestens ${VOCAB_NAME_MIN_LENGTH} Zeichen enthalten.`;
    }
    if (name.length > VOCAB_NAME_MAX_LENGTH) {
      return `Tag darf maximal ${VOCAB_NAME_MAX_LENGTH} Zeichen enthalten.`;
    }
    return '';
  }

  const findByName = (name) => {
    const normalized = normalizeTagName(name).toLocaleLowerCase('de-DE');
    if (!normalized) return null;
    return tags.value.find((t) => normalizeTagName(t?.name).toLocaleLowerCase('de-DE') === normalized) ?? null;
  };

  function upsertTagLocally(tag) {
    const tagId = String(tag?.id || '').trim();
    const tagName = normalizeTagName(tag?.name);
    if (!tagId || !tagName) return;
    const tagKey = tagName.toLocaleLowerCase('de-DE');
    const existingIndex = tags.value.findIndex((entry) => {
      if (entry?.id === tagId) return true;
      return normalizeTagName(entry?.name).toLocaleLowerCase('de-DE') === tagKey;
    });
    const nextTag = { usage_count: 0, ...tag, id: tagId, name: tagName };
    if (existingIndex >= 0) {
      tags.value.splice(existingIndex, 1, { ...tags.value[existingIndex], ...nextTag });
      return;
    }
    tags.value.push(nextTag);
  }

  // ── Actions ────────────────────────────────────────────────────────────

  /** Lädt alle Tags (inkl. Zähler). */
  async function fetchTags() {
    try {
      const payload = await listTags(true);
      tags.value = payload?.items ?? [];
    } catch (error) {
      console.error('Tags konnten nicht geladen werden:', error);
    }
  }

  /**
   * Erstellt einen Tag falls nicht vorhanden.
   * @returns {{ ok: boolean, reason: string, name: string, id?: string }}
   */
  async function createTagByName(rawName) {
    const name = normalizeTagName(rawName);
    if (!name) return { ok: false, reason: 'empty', name: '' };
    const validationMessage = validateTagName(name);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      return { ok: false, reason: 'invalid', name };
    }
    const existing = findByName(name);
    if (existing) return { ok: false, reason: 'exists', name: existing.name, id: existing.id };

    try {
      const created = await apiCreateTag(name);
      upsertTagLocally(created);
      return { ok: true, reason: 'created', name: created?.name || name, id: created?.id };
    } catch (error) {
      await fetchTags();
      const recovered = findByName(name);
      if (recovered) {
        return { ok: false, reason: 'exists', name: recovered.name, id: recovered.id };
      }
      throw error;
    }
  }

  /**
   * Stellt sicher, dass ein Tag mit diesem Namen existiert,
   * und gibt seine ID zurück.
   */
  async function ensureTagIdByName(rawName) {
    const name = normalizeTagName(rawName);
    if (!name) return '';
    const validationMessage = validateTagName(name);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      return '';
    }
    const existing = findByName(name);
    if (existing) return existing.id;

    const result = await createTagByName(name);
    return result.id ?? findByName(name)?.id ?? '';
  }

  /** PATCH /api/tags/{id} */
  async function renameTag(id, newName) {
    const normalizedName = normalizeTagName(newName);
    const validationMessage = validateTagName(normalizedName);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      throw new Error(validationMessage);
    }
    isTagMutationRunning.value = true;
    try {
      await apiRenameTag(id, normalizedName);
      await fetchTags();
      notify({ type: 'success', title: 'Tag', message: `Tag umbenannt.` });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Tag konnte nicht umbenannt werden.') });
      throw error;
    } finally {
      isTagMutationRunning.value = false;
    }
  }

  /** POST /api/tags/{sourceId}/merge */
  async function mergeTag(sourceId, targetId) {
    isTagMutationRunning.value = true;
    try {
      await apiMergeTag(sourceId, targetId);
      await fetchTags();
      notify({ type: 'success', title: 'Tag', message: 'Tag zusammengeführt.' });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Tag konnte nicht zusammengeführt werden.') });
      throw error;
    } finally {
      isTagMutationRunning.value = false;
    }
  }

  /** DELETE /api/tags/{id} */
  async function deleteTag(id) {
    isTagMutationRunning.value = true;
    try {
      await apiDeleteTag(id);
      tags.value = tags.value.filter((t) => t.id !== id);
      notify({ type: 'success', title: 'Tag', message: 'Tag gelöscht.' });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Tag konnte nicht gelöscht werden.') });
      throw error;
    } finally {
      isTagMutationRunning.value = false;
    }
  }

  return {
    // State
    tags,
    isTagMutationRunning,
    // Helpers
    findByName,
    // Actions
    fetchTags,
    createTagByName,
    ensureTagIdByName,
    renameTag,
    mergeTag,
    deleteTag,
  };
});
