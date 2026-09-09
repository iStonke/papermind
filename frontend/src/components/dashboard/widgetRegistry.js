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
import QuickNoteWidget from './QuickNoteWidget.vue';
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
    description: 'Dokumentbestand und Entwicklung auf einen Blick',
    icon: 'mdi-numeric',
    component: markRaw(StatsWidget),
    defaultSize: { w: 12, h: 2 },
    minW: 6,
    minH: 2,
  },
  quickNote: {
    key: 'quickNote',
    label: 'Schnelle Notiz',
    description: 'Gedanken direkt auf der Übersicht festhalten',
    icon: 'mdi-note-plus-outline',
    component: markRaw(QuickNoteWidget),
    defaultSize: { w: 4, h: 3 },
    minW: 3,
    minH: 3,
  },
  documentsPerYear: {
    key: 'documentsPerYear',
    label: 'Dokumente pro Jahr',
    description: 'Jahresverlauf und kumulierte Entwicklung',
    icon: 'mdi-chart-timeline-variant',
    component: markRaw(DocumentsPerYearWidget),
    defaultSize: { w: 7, h: 5 },
    minW: 4,
    minH: 4,
  },
  topCorrespondents: {
    key: 'topCorrespondents',
    label: 'Top-Korrespondenten',
    description: 'Deine wichtigsten Absender und Kontakte',
    icon: 'mdi-account-group-outline',
    component: markRaw(TopCorrespondentsWidget),
    defaultSize: { w: 5, h: 5 },
    minW: 3,
    minH: 3,
  },
  recentImports: {
    key: 'recentImports',
    label: 'Zuletzt importiert',
    description: 'Die neuesten Dokumente in deiner Bibliothek',
    icon: 'mdi-tray-arrow-down',
    component: markRaw(RecentImportsWidget),
    defaultSize: { w: 7, h: 5 },
    minW: 4,
    minH: 3,
  },
  openTasks: {
    key: 'openTasks',
    label: 'Offene Aufgaben',
    description: 'Aufgaben aus deinen Notizen im Überblick',
    icon: 'mdi-checkbox-marked-circle-outline',
    component: markRaw(OpenTasksWidget),
    defaultSize: { w: 5, h: 4 },
    minW: 3,
    minH: 3,
  },
  topSearches: {
    key: 'topSearches',
    label: 'Häufig gesucht',
    description: 'Deine meistverwendeten Suchbegriffe',
    icon: 'mdi-magnify',
    component: markRaw(TopSearchesWidget),
    defaultSize: { w: 4, h: 4 },
    minW: 3,
    minH: 3,
  },
  distribution: {
    key: 'distribution',
    label: 'Verteilung',
    description: 'Dokumenttypen und ihre Anteile',
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
  { id: 'quickNote', x: 8, y: 7, w: 4, h: 3 },
  { id: 'openTasks', x: 8, y: 10, w: 4, h: 5 },
  { id: 'distribution', x: 0, y: 11, w: 4, h: 5 },
  { id: 'topSearches', x: 4, y: 11, w: 4, h: 4 },
];
