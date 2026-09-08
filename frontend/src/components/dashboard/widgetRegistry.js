/*
 * Registry der Dashboard-Widgets.
 *
 * Einzige Stelle, die Widget-Key → {Komponente, Label, Icon, Standardgröße}
 * verbindet. Phase 1 nutzt daraus vorerst nur die Komponenten (der Host rendert
 * sie noch im festen Raster); Phase 2 (konfigurierbares Board) speist daraus die
 * Widget-Palette und das Default-Layout. Die Größen (Rasterfelder w×h, min) sind
 * daher vorläufig und werden mit dem Board-Umbau final kalibriert.
 */
import { markRaw } from 'vue';
import StatsWidget from './StatsWidget.vue';
import DocumentsPerYearWidget from './DocumentsPerYearWidget.vue';
import TopCorrespondentsWidget from './TopCorrespondentsWidget.vue';
import RecentImportsWidget from './RecentImportsWidget.vue';
import OpenTasksWidget from './OpenTasksWidget.vue';
import TopSearchesWidget from './TopSearchesWidget.vue';
import DistributionWidget from './DistributionWidget.vue';

/** Reihenfolge = späteres Default-Layout (12-Spalten-Raster gedacht). */
export const DASHBOARD_WIDGETS = {
  stats: {
    key: 'stats',
    label: 'Kennzahlen',
    icon: 'mdi-numeric',
    component: markRaw(StatsWidget),
    defaultSize: { w: 12, h: 2 },
    minW: 6,
    minH: 2,
  },
  documentsPerYear: {
    key: 'documentsPerYear',
    label: 'Dokumente pro Jahr',
    icon: 'mdi-chart-timeline-variant',
    component: markRaw(DocumentsPerYearWidget),
    defaultSize: { w: 7, h: 5 },
    minW: 4,
    minH: 4,
  },
  topCorrespondents: {
    key: 'topCorrespondents',
    label: 'Top-Korrespondenten',
    icon: 'mdi-account-group-outline',
    component: markRaw(TopCorrespondentsWidget),
    defaultSize: { w: 5, h: 5 },
    minW: 3,
    minH: 3,
  },
  recentImports: {
    key: 'recentImports',
    label: 'Zuletzt importiert',
    icon: 'mdi-tray-arrow-down',
    component: markRaw(RecentImportsWidget),
    defaultSize: { w: 7, h: 5 },
    minW: 4,
    minH: 3,
  },
  openTasks: {
    key: 'openTasks',
    label: 'Offene Aufgaben',
    icon: 'mdi-checkbox-marked-circle-outline',
    component: markRaw(OpenTasksWidget),
    defaultSize: { w: 5, h: 4 },
    minW: 3,
    minH: 3,
  },
  topSearches: {
    key: 'topSearches',
    label: 'Häufig gesucht',
    icon: 'mdi-magnify',
    component: markRaw(TopSearchesWidget),
    defaultSize: { w: 4, h: 4 },
    minW: 3,
    minH: 3,
  },
  distribution: {
    key: 'distribution',
    label: 'Verteilung',
    icon: 'mdi-chart-donut',
    component: markRaw(DistributionWidget),
    defaultSize: { w: 5, h: 5 },
    minW: 3,
    minH: 3,
  },
};

/** Standardreihenfolge der Widgets (Keys). */
export const DEFAULT_WIDGET_ORDER = Object.keys(DASHBOARD_WIDGETS);

/**
 * Explizites Default-Layout (12-Spalten-Raster). Bewusst gesetzt statt Auto-Flow,
 * damit das Board frisch/zurückgesetzt eine durchdachte Anordnung zeigt:
 * Kennzahlen-Band oben, darunter Diagramm + Rangliste, dann Belege + Aufgaben,
 * unten Verteilung + Suchbegriffe.
 */
export const DEFAULT_LAYOUT = [
  { id: 'stats', x: 0, y: 0, w: 12, h: 2 },
  { id: 'documentsPerYear', x: 0, y: 2, w: 8, h: 5 },
  { id: 'topCorrespondents', x: 8, y: 2, w: 4, h: 5 },
  { id: 'recentImports', x: 0, y: 7, w: 8, h: 4 },
  { id: 'openTasks', x: 8, y: 7, w: 4, h: 4 },
  { id: 'distribution', x: 0, y: 11, w: 4, h: 5 },
  { id: 'topSearches', x: 4, y: 11, w: 8, h: 4 },
];
