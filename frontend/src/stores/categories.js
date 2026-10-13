/**
 * useCategoryStore
 *
 * Verwaltet die Liste der zur Verfügung stehenden Dokumenttypen
 * sowie alle CRUD-Operationen. Wird in den Einstellungen gepflegt und
 * speist u. a. das Dokumenttyp-Dropdown im Import-Dialog.
 */
import { defineSessionStore as defineStore } from './sessionStores.js';
import { computed, ref } from 'vue';
import {
  createCategory as apiCreateCategory,
  deleteCategory as apiDeleteCategory,
  listCategories,
  renameCategory as apiRenameCategory,
  updateCategory as apiUpdateCategory,
} from '../api/categories.js';
import { mapApiError, useNotifications } from './notifications.js';
import { reconcileRecordReload } from '../utils/recordReload.js';

const VOCAB_NAME_MIN_LENGTH = 2;
const VOCAB_NAME_MAX_LENGTH = 30;
const categoryNameCollator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });

export const useCategoryStore = defineStore('categories', () => {
  const { notify } = useNotifications();

  // ── State ──────────────────────────────────────────────────────────────
  const categories = ref([]);
  const isLoaded = ref(false);
  const isLoading = ref(false);
  const pendingMutations = ref(0);
  const isCategoryMutationRunning = computed(() => pendingMutations.value > 0);
  let listVersion = 0;
  const recordVersions = new Map();

  // ── Getters ──────────────────────────────────────────────────────────────
  const sortedCategories = computed(() => [...categories.value].sort((left, right) => (
    categoryNameCollator.compare(
      normalizeCategoryName(left?.name),
      normalizeCategoryName(right?.name)
    )
  )));

  /** Reine Namensliste (alphabetisch), z. B. als v-select :items. */
  const categoryNames = computed(() => sortedCategories.value
    .filter((c) => c?.is_active !== false)
    .map((c) => c.name));

  // ── Helpers ────────────────────────────────────────────────────────────
  function normalizeCategoryName(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function validateCategoryName(name) {
    if (name.length < VOCAB_NAME_MIN_LENGTH) {
      return `Dokumenttyp muss mindestens ${VOCAB_NAME_MIN_LENGTH} Zeichen enthalten.`;
    }
    if (name.length > VOCAB_NAME_MAX_LENGTH) {
      return `Dokumenttyp darf maximal ${VOCAB_NAME_MAX_LENGTH} Zeichen enthalten.`;
    }
    return '';
  }

  const findByName = (name) => {
    const normalized = normalizeCategoryName(name).toLocaleLowerCase('de-DE');
    if (!normalized) return null;
    return categories.value.find(
      (c) => normalizeCategoryName(c?.name).toLocaleLowerCase('de-DE') === normalized
    ) ?? null;
  };

  const findById = (id) => categories.value.find((c) => String(c?.id) === String(id)) ?? null;

  function applyRecord(updated) {
    if (!updated?.id) return;
    listVersion += 1;
    recordVersions.set(updated.id, listVersion);
    const previous = findById(updated.id);
    const next = { ...previous, ...updated, usage_count: updated.usage_count ?? previous?.usage_count ?? 0 };
    categories.value = previous
      ? categories.value.map(item => item.id === updated.id ? next : item)
      : [...categories.value, next];
  }

  // ── Actions ────────────────────────────────────────────────────────────

  /** Lädt alle Dokumenttypen (inkl. Zähler). */
  async function fetchCategories() {
    isLoading.value = true;
    const requestedVersion = listVersion;
    try {
      const payload = await listCategories(true);
      categories.value = reconcileRecordReload(categories.value, payload?.items ?? [], recordVersions, requestedVersion);
      isLoaded.value = true;
    } catch (error) {
      console.error('Dokumenttypen konnten nicht geladen werden:', error);
    } finally {
      isLoading.value = false;
    }
  }

  /** Lädt einmalig, falls noch nicht geschehen. */
  async function ensureLoaded() {
    if (isLoaded.value) return;
    await fetchCategories();
  }

  /** POST /api/document-types */
  async function createCategoryByName(rawName) {
    const name = normalizeCategoryName(rawName);
    if (!name) return { ok: false, reason: 'empty', name: '' };
    const validationMessage = validateCategoryName(name);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      return { ok: false, reason: 'invalid', name };
    }
    const existing = findByName(name);
    if (existing) {
      notify({ type: 'warning', title: 'Dokumenttyp', message: `"${existing.name}" existiert bereits.` });
      return { ok: false, reason: 'exists', name: existing.name, id: existing.id };
    }

    pendingMutations.value += 1;
    try {
      const created = await apiCreateCategory(name);
      applyRecord(created);
      notify({ type: 'success', title: 'Dokumenttyp', message: 'Dokumenttyp hinzugefügt.' });
      return { ok: true, reason: 'created', name: created?.name || name, id: created?.id };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Dokumenttyp konnte nicht hinzugefügt werden.') });
      throw error;
    } finally {
      pendingMutations.value = Math.max(0, pendingMutations.value - 1);
    }
  }

  /** PATCH /api/document-types/{id} */
  async function renameCategory(id, newName) {
    const name = normalizeCategoryName(newName);
    const validationMessage = validateCategoryName(name);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      throw new Error(validationMessage);
    }
    const existing = findByName(name);
    if (existing && String(existing.id) !== String(id)) {
      const message = `"${existing.name}" existiert bereits.`;
      notify({ type: 'warning', title: 'Dokumenttyp', message });
      throw new Error(message);
    }
    pendingMutations.value += 1;
    try {
      const updated = await apiRenameCategory(id, name);
      applyRecord(updated);
      notify({ type: 'success', title: 'Dokumenttyp', message: 'Dokumenttyp umbenannt.' });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Dokumenttyp konnte nicht umbenannt werden.') });
      throw error;
    } finally {
      pendingMutations.value = Math.max(0, pendingMutations.value - 1);
    }
  }

  /** PATCH /api/document-types/{id} */
  async function updateCategory(id, payload = {}, { silent = false } = {}) {
    const nextPayload = { ...payload };
    if ('name' in nextPayload) {
      nextPayload.name = normalizeCategoryName(nextPayload.name);
      const validationMessage = validateCategoryName(nextPayload.name);
      if (validationMessage) {
        notify({ type: 'warning', message: validationMessage });
        throw new Error(validationMessage);
      }
      const existing = findByName(nextPayload.name);
      if (existing && String(existing.id) !== String(id)) {
        const message = `"${existing.name}" existiert bereits.`;
        notify({ type: 'warning', title: 'Dokumenttyp', message });
        throw new Error(message);
      }
    }
    if ('naming_template' in nextPayload) {
      const template = String(nextPayload.naming_template || '').trim();
      nextPayload.naming_template = template || null;
    }

    pendingMutations.value += 1;
    try {
      const updated = await apiUpdateCategory(id, nextPayload);
      applyRecord(updated);
      // Beim Auto-Speichern keine Erfolgsmeldung (sonst Toast-Flut pro Tastendruck).
      if (!silent) notify({ type: 'success', title: 'Dokumenttyp', message: 'Dokumenttyp aktualisiert.' });
      return { ok: true, category: updated };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Dokumenttyp konnte nicht aktualisiert werden.') });
      throw error;
    } finally {
      pendingMutations.value = Math.max(0, pendingMutations.value - 1);
    }
  }

  /** DELETE /api/document-types/{id} */
  async function deleteCategory(id) {
    pendingMutations.value += 1;
    try {
      await apiDeleteCategory(id);
      listVersion += 1;
      recordVersions.set(id, listVersion);
      categories.value = categories.value.filter((c) => c.id !== id);
      notify({ type: 'success', title: 'Dokumenttyp', message: 'Dokumenttyp gelöscht.' });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Dokumenttyp konnte nicht gelöscht werden.') });
      throw error;
    } finally {
      pendingMutations.value = Math.max(0, pendingMutations.value - 1);
    }
  }

  return {
    // State
    categories,
    isLoaded,
    isLoading,
    isCategoryMutationRunning,
    // Getters
    sortedCategories,
    categoryNames,
    // Helpers
    findByName,
    findById,
    // Actions
    fetchCategories,
    ensureLoaded,
    createCategoryByName,
    updateCategory,
    renameCategory,
    deleteCategory,
  };
});
