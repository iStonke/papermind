/**
 * useCategoryStore
 *
 * Verwaltet die Liste der zur Verfügung stehenden Dokument-Kategorien
 * sowie alle CRUD-Operationen. Wird in den Einstellungen gepflegt und
 * speist u. a. das Kategorie-Dropdown im Import-Dialog.
 */
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  createCategory as apiCreateCategory,
  deleteCategory as apiDeleteCategory,
  listCategories,
  renameCategory as apiRenameCategory,
} from '../api/categories.js';
import { mapApiError, useNotifications } from './notifications.js';

const VOCAB_NAME_MIN_LENGTH = 2;
const VOCAB_NAME_MAX_LENGTH = 30;

export const useCategoryStore = defineStore('categories', () => {
  const { notify } = useNotifications();

  // ── State ──────────────────────────────────────────────────────────────
  const categories = ref([]);
  const isLoaded = ref(false);
  const isCategoryMutationRunning = ref(false);

  // ── Getters ──────────────────────────────────────────────────────────────
  /** Reine Namensliste (alphabetisch), z. B. als v-select :items. */
  const categoryNames = computed(() => categories.value.map((c) => c.name));

  // ── Helpers ────────────────────────────────────────────────────────────
  function normalizeCategoryName(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function validateCategoryName(name) {
    if (name.length < VOCAB_NAME_MIN_LENGTH) {
      return `Kategorie muss mindestens ${VOCAB_NAME_MIN_LENGTH} Zeichen enthalten.`;
    }
    if (name.length > VOCAB_NAME_MAX_LENGTH) {
      return `Kategorie darf maximal ${VOCAB_NAME_MAX_LENGTH} Zeichen enthalten.`;
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

  // ── Actions ────────────────────────────────────────────────────────────

  /** Lädt alle Kategorien (inkl. Zähler). */
  async function fetchCategories() {
    try {
      const payload = await listCategories(true);
      categories.value = payload?.items ?? [];
      isLoaded.value = true;
    } catch (error) {
      console.error('Kategorien konnten nicht geladen werden:', error);
    }
  }

  /** Lädt einmalig, falls noch nicht geschehen. */
  async function ensureLoaded() {
    if (isLoaded.value) return;
    await fetchCategories();
  }

  /** POST /api/categories */
  async function createCategoryByName(rawName) {
    const name = normalizeCategoryName(rawName);
    if (!name) return { ok: false, reason: 'empty', name: '' };
    const validationMessage = validateCategoryName(name);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      return { ok: false, reason: 'invalid', name };
    }
    const existing = findByName(name);
    if (existing) return { ok: false, reason: 'exists', name: existing.name, id: existing.id };

    isCategoryMutationRunning.value = true;
    try {
      const created = await apiCreateCategory(name);
      await fetchCategories();
      notify({ type: 'success', title: 'Kategorie', message: 'Kategorie hinzugefügt.' });
      return { ok: true, reason: 'created', name: created?.name || name, id: created?.id };
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Kategorie konnte nicht hinzugefügt werden.') });
      throw error;
    } finally {
      isCategoryMutationRunning.value = false;
    }
  }

  /** PATCH /api/categories/{id} */
  async function renameCategory(id, newName) {
    const name = normalizeCategoryName(newName);
    const validationMessage = validateCategoryName(name);
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      throw new Error(validationMessage);
    }
    isCategoryMutationRunning.value = true;
    try {
      await apiRenameCategory(id, name);
      await fetchCategories();
      notify({ type: 'success', title: 'Kategorie', message: 'Kategorie umbenannt.' });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Kategorie konnte nicht umbenannt werden.') });
      throw error;
    } finally {
      isCategoryMutationRunning.value = false;
    }
  }

  /** DELETE /api/categories/{id} */
  async function deleteCategory(id) {
    isCategoryMutationRunning.value = true;
    try {
      await apiDeleteCategory(id);
      categories.value = categories.value.filter((c) => c.id !== id);
      notify({ type: 'success', title: 'Kategorie', message: 'Kategorie gelöscht.' });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Kategorie konnte nicht gelöscht werden.') });
      throw error;
    } finally {
      isCategoryMutationRunning.value = false;
    }
  }

  return {
    // State
    categories,
    isLoaded,
    isCategoryMutationRunning,
    // Getters
    categoryNames,
    // Helpers
    findByName,
    // Actions
    fetchCategories,
    ensureLoaded,
    createCategoryByName,
    renameCategory,
    deleteCategory,
  };
});
