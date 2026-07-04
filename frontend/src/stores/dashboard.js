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
    attention: { unread: 0, untagged: 0, retention_due: 0, to_review: 0 },
    recent: [],
  };
}

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref(createEmptyOverview());
  const isLoading = ref(false);
  const hasLoadedOnce = ref(false);
  const error = ref(null);

  /** GET /api/dashboard/overview */
  async function fetchOverview() {
    isLoading.value = true;
    error.value = null;
    try {
      const payload = await getDashboardOverview();
      overview.value = { ...createEmptyOverview(), ...payload };
      hasLoadedOnce.value = true;
    } catch (err) {
      error.value = err;
      console.warn('Dashboard-Daten konnten nicht geladen werden:', err);
    } finally {
      isLoading.value = false;
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
