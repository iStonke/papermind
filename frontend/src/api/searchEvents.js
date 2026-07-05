import { apiPost } from './client.js';

/**
 * POST /api/search-events — protokolliert einen abgeschickten Suchbegriff.
 * Fehler werden bewusst verschluckt: Logging darf die Suche nie stören.
 */
export function logSearchEvent(term) {
  const normalized = String(term || '').trim();
  if (!normalized) return;
  void apiPost('/api/search-events', { term: normalized }).catch(() => {});
}
