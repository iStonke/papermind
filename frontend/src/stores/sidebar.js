/**
 * useSidebarStore
 *
 * Verwaltet Sidebar-Counts, gespeicherte Suchen (Smart Folders)
 * und die Sichtbarkeit der Sidebar-Sektionen.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getSidebarCounts } from '../api/sidebar.js';
import {
  createSmartFolder,
  deleteSmartFolder,
  getSmartFolder,
  listSmartFolders,
  updateSmartFolder,
} from '../api/smartFolders.js';
import { mapApiError, useNotifications } from './notifications.js';
import { createEmptyCounts, normalizeCounts } from '../utils/sidebarCounts.js';

const SECTION_VISIBILITY_KEY = 'pm.sidebar.section_visibility.v1';
const SECTION_DEFAULTS = Object.freeze({ library: true, folders: true, tags: true });

function sanitizeSectionVisibility(raw) {
  if (!raw || typeof raw !== 'object') return { ...SECTION_DEFAULTS };
  return {
    library: raw.library !== false,
    folders: raw.folders !== false,
    tags:    raw.tags    !== false,
  };
}

export const useSidebarStore = defineStore('sidebar', () => {
  const { notify } = useNotifications();

  // ── State ──────────────────────────────────────────────────────────────
  const sidebarCounts          = ref(createEmptyCounts());
  const isLoadingSidebarCounts = ref(false);
  const savedSearches          = ref([]);
  const isLoadingSavedSearches = ref(false);
  const sectionVisibility      = ref(loadSectionVisibility());

  let countsRefreshTimer = null;

  // ── Helpers ────────────────────────────────────────────────────────────

  function loadSectionVisibility() {
    try {
      return sanitizeSectionVisibility(JSON.parse(localStorage.getItem(SECTION_VISIBILITY_KEY)));
    } catch {
      return { ...SECTION_DEFAULTS };
    }
  }

  function persistSectionVisibility() {
    try { localStorage.setItem(SECTION_VISIBILITY_KEY, JSON.stringify(sectionVisibility.value)); }
    catch { /* ignore */ }
  }

  // ── Counts ─────────────────────────────────────────────────────────────

  /** GET /api/sidebar/counts */
  async function fetchCounts() {
    isLoadingSidebarCounts.value = true;
    try {
      const payload = await getSidebarCounts();
      sidebarCounts.value = normalizeCounts(payload);
    } catch (error) {
      console.warn('Sidebar-Counts konnten nicht geladen werden:', error);
    } finally {
      isLoadingSidebarCounts.value = false;
    }
  }

  /** Verzögerter Refresh der Counts (nach Mutations). */
  function scheduleCounts(delay = 240) {
    if (countsRefreshTimer) window.clearTimeout(countsRefreshTimer);
    countsRefreshTimer = window.setTimeout(() => {
      countsRefreshTimer = null;
      void fetchCounts();
    }, delay);
  }

  const tagCount          = (tagId, fallback = 0) =>
    Number(sidebarCounts.value.tags?.[tagId] ?? fallback);

  const savedSearchCount  = (id) =>
    Number(sidebarCounts.value.saved_searches?.[id] ?? 0);

  // ── Smart Folders / Saved Searches ─────────────────────────────────────

  async function fetchSavedSearches() {
    isLoadingSavedSearches.value = true;
    try {
      const payload = await listSmartFolders();
      savedSearches.value = Array.isArray(payload?.items) ? payload.items : [];
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'Ordner konnten nicht geladen werden.') });
    } finally {
      isLoadingSavedSearches.value = false;
    }
  }

  async function fetchSavedSearchDetail(id) {
    return getSmartFolder(id);
  }

  async function saveSavedSearch(id, body) {
    const result = id
      ? await updateSmartFolder(id, body)
      : await createSmartFolder(body);
    await fetchSavedSearches();
    scheduleCounts();
    return result;
  }

  async function removeSavedSearch(id) {
    await deleteSmartFolder(id);
    savedSearches.value = savedSearches.value.filter((s) => s.id !== id);
    scheduleCounts();
  }

  // ── Section visibility ─────────────────────────────────────────────────

  function isSectionVisible(key) {
    return sectionVisibility.value[key] !== false;
  }

  function toggleSection(key) {
    sectionVisibility.value = { ...sectionVisibility.value, [key]: !sectionVisibility.value[key] };
    persistSectionVisibility();
  }

  return {
    // State
    sidebarCounts,
    isLoadingSidebarCounts,
    savedSearches,
    isLoadingSavedSearches,
    sectionVisibility,
    // Counts
    fetchCounts,
    scheduleCounts,
    tagCount,
    savedSearchCount,
    // Smart Folders
    fetchSavedSearches,
    fetchSavedSearchDetail,
    saveSavedSearch,
    removeSavedSearch,
    // Section visibility
    isSectionVisible,
    toggleSection,
  };
});
