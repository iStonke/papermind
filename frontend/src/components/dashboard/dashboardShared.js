/*
 * Gemeinsame Bausteine der Dashboard-Widgets (Phase 1: Widgetisierung).
 *
 * - Formatierung (Zahlen, Datum) und die Diagramm-Farbpalette werden von
 *   mehreren Widgets genutzt und liegen daher hier zentral.
 * - Aktionen (Import öffnen, Dokument öffnen, Jahr wählen …) reicht der Host
 *   DashboardView.vue per provide/inject an die Widgets durch. So bleiben die
 *   Widgets datseitig eigenständig (sie lesen den Store selbst) und melden
 *   Interaktionen über einen einzigen, klar benannten Kanal zurück – ohne dass
 *   jedes Widget seine Events einzeln durch den Host schleifen muss.
 */
import { inject } from 'vue';

export const DASHBOARD_ACTIONS = Symbol('pm-dashboard-actions');

const NOOP = () => {};

const FALLBACK_ACTIONS = {
  openImport: NOOP,
  openAi: NOOP,
  openDocument: NOOP,
  attentionSelect: NOOP,
  showAllRecent: NOOP,
  searchTerm: NOOP,
  yearSelect: NOOP,
  openNote: NOOP,
};

/** Host-Aktionen im Widget beziehen (Fallback = No-ops, falls ohne Host gerendert). */
export function useDashboardActions() {
  return inject(DASHBOARD_ACTIONS, FALLBACK_ACTIONS);
}

// ── Formatierung ────────────────────────────────────────────────────────────
const intFormatter = new Intl.NumberFormat('de-DE');

export const formatInt = (n) => intFormatter.format(Number(n || 0));

export function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ── Diagramm-Farbpalette ──────────────────────────────────────────────────────
export const chartPalette = [
  '#5bb7c8',
  '#7aa2e3',
  '#a78bda',
  '#e8a45d',
  '#75b798',
  '#e27d7d',
  '#94a3b8',
  '#d48ac8',
];

/** Farbpalette für Ranglisten, Suchbalken und Donut-Segmente. */
export function rampColor(index, total) {
  if (total <= 1) return chartPalette[0];
  return chartPalette[index % chartPalette.length];
}
