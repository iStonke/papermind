/**
 * useDashboardStore
 *
 * Lädt die aggregierten Übersichts-Kennzahlen (read-only) für die
 * Dashboard-Startseite. Bewusst schlank: eine Payload, ein Ladezustand.
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getDashboardOverview } from '../api/dashboard.js';

function createEmptyOverview() {
  return {
    stats: {
      documents_total: 0,
      this_month: 0,
      correspondents: 0,
      tags: 0,
      document_types: 0,
      storage_bytes: 0,
      storage_limit_bytes: null,
      total_trend_pct: null,
      correspondents_new: 0,
      untagged_pct: 0,
    },
    documents_per_month: [],
    documents_per_month_total: 0,
    documents_per_year: [],
    top_correspondents: [],
    tag_distribution: [],
    tag_count_total: 0,
    type_distribution: [],
    type_count_total: 0,
    storage_series: [],
    top_searches: [],
    attention: { unread: 0, untagged: 0, retention_due: 0, to_review: 0, unclassified: 0, ocr_issues: 0, without_document_type: 0 },
    recent: [],
    open_tasks: [],
    open_tasks_total: 0,
  };
}

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref(createEmptyOverview());
  const isLoading = ref(false);
  const hasLoadedOnce = ref(false);
  const error = ref(null);
  let requestRevision = 0;

  /** GET /api/dashboard/overview */
  async function fetchOverview() {
    const revision = ++requestRevision;
    isLoading.value = true;
    error.value = null;
    try {
      const payload = await getDashboardOverview();
      // Ein nach einem Notiz-Autosave gestarteter Abruf ist neuer als der
      // initiale Mount-Abruf und darf nicht von dessen späterer Antwort ersetzt
      // werden.
      if (revision !== requestRevision) return;
      overview.value = { ...createEmptyOverview(), ...payload };
      hasLoadedOnce.value = true;
    } catch (err) {
      if (revision !== requestRevision) return;
      error.value = err;
      console.warn('Dashboard-Daten konnten nicht geladen werden:', err);
    } finally {
      if (revision === requestRevision) isLoading.value = false;
    }
  }

  return {
    overview,
    isLoading,
    hasLoadedOnce,
    error,
    fetchOverview,
  };
});
