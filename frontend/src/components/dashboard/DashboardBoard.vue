<!--
  DashboardBoard — konfigurierbares Übersicht-Board (Phase 2).

  Rendert die Widgets aus der Registry in einem gridstack-Raster. gridstack ist
  eine imperative Bibliothek; die Kopplung an Vue folgt daher einem bewussten
  Vertrag, um DOM-Konflikte zu vermeiden:

    - Vue rendert die Item-Hülle (v-for) EINMALIG aus `items`; danach besitzt
      gridstack Position/Größe (per Inline-Style). Wir schreiben Koordinaten NICHT
      reaktiv nach `items` zurück, sondern lesen sie bei Bedarf via grid.save().
    - Reaktiv bleibt nur der INHALT jeder Zelle (die Widget-Komponente + der
      Entfernen-Knopf) innerhalb von .grid-stack-item-content.
    - Hinzufügen/Entfernen läuft über gridstack (makeWidget/removeWidget) plus
      synchrones Nachziehen von `items`.

  Persistenz vorerst in localStorage (Phase 2b: Server-Setting ui.dashboard_layout).
-->
<template>
  <div class="dash-board" :class="{ 'is-editing': editing }">
    <div class="dash-board__scroll">
      <div ref="gridEl" class="grid-stack" :key="gridKey">
        <div
          v-for="item in items"
          :key="item.id"
          class="grid-stack-item"
          :gs-id="item.id"
          :gs-x="item.x"
          :gs-y="item.y"
          :gs-w="item.w"
          :gs-h="item.h"
          :gs-min-w="widgets[item.id]?.minW"
          :gs-min-h="widgets[item.id]?.minH"
        >
          <div class="grid-stack-item-content">
            <!-- Griff IMMER im DOM (nur per CSS ein-/ausgeblendet): gridstack bindet
                 das Drag-Handle beim Init/makeWidget; ein erst reaktiv erzeugter
                 Handle würde sonst nicht als ziehbar erkannt. -->
            <div class="dash-board__grip" title="Zum Verschieben ziehen" aria-label="Widget verschieben">
              <v-icon size="15">mdi-drag</v-icon>
            </div>
            <div class="dash-board__widget">
              <component :is="widgets[item.id].component" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Verwaltungsfenster: öffnet mit „Anpassen". Schwebend (nicht modal), damit
         das Board gleichzeitig umsortiert werden kann. Hier werden Widgets an-/
         abgewählt und das Layout zurückgesetzt. -->
    <div v-if="editing" class="dash-board__manager" role="dialog" aria-label="Widgets verwalten">
      <div class="dash-board__manager-head">
        <span class="dash-board__manager-title">Widgets verwalten</span>
        <button
          type="button"
          class="dash-board__manager-close"
          title="Fertig"
          @click="emit('update:editing', false)"
        >
          <v-icon size="18">mdi-close</v-icon>
        </button>
      </div>
      <p class="dash-board__manager-hint">Wähle die Widgets und ordne sie per Ziehen an.</p>
      <ul class="dash-board__manager-list">
        <li v-for="key in allWidgetKeys" :key="key" class="dash-board__manager-item">
          <label class="dash-board__manager-label">
            <input
              type="checkbox"
              class="dash-board__manager-check"
              :checked="placedIds.has(key)"
              @change="toggleWidget(key, $event.target.checked)"
            />
            <v-icon size="16" class="dash-board__manager-icon">{{ widgets[key].icon }}</v-icon>
            <span class="dash-board__manager-name">{{ widgets[key].label }}</span>
          </label>
        </li>
      </ul>
      <button type="button" class="dash-board__manager-reset" @click="resetLayout">
        <v-icon size="15">mdi-restore</v-icon>
        Auf Standard zurücksetzen
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import { GridStack } from 'gridstack';
import 'gridstack/dist/gridstack.min.css';
import { DASHBOARD_WIDGETS, DEFAULT_LAYOUT, DEFAULT_WIDGET_ORDER } from './widgetRegistry.js';
import { useSettingsStore } from '../../stores/settings.js';
import { getBaseUrl } from '../../api/client.js';
import { buildDashboardLayoutPatch } from '../../utils/settingsApi.js';

const props = defineProps({
  // Der Anpassen-Modus wird vom Host (DashboardView-Kopfzeile) gesteuert.
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['update:editing']);

const GRID_COLUMN = 12;
const CELL_HEIGHT = 74;
const PERSIST_DEBOUNCE_MS = 600;

const settingsStore = useSettingsStore();
const widgets = DASHBOARD_WIDGETS;
const gridEl = ref(null);
// Wird beim Reset erhöht, um den Grid-Teilbaum frisch neu zu rendern (siehe resetLayout).
const gridKey = ref(0);
let grid = null;
// Unterdrückt das Speichern während programmatischer Umbauten (Reset), damit die
// dabei ausgelösten gridstack-Events nicht das gewünschte Ergebnis überschreiben.
let suppressPersist = false;
let persistTimer = null;

// Ziehen/Skalieren an den Anpassen-Modus koppeln. nextTick, damit die reaktiv
// ein-/ausgeblendeten Griffe (Drag-Handles) im DOM stehen, bevor gridstack sie
// aktiviert (siehe Handle-Hinweis unten).
function applyEditable(val) {
  if (!grid) return;
  grid.setStatic(!val);
  grid.enableMove(val);
  grid.enableResize(val);
}
watch(
  () => props.editing,
  async (val) => {
    await nextTick();
    applyEditable(val);
  }
);

// `items` = Renderliste der Zellen. Nur bei Add/Remove verändert; Position/Größe
// besitzt nach der Initialisierung gridstack. shallowRef, weil die Item-Objekte
// nach dem Rendern nicht reaktiv weitergepflegt werden.
const items = shallowRef(buildInitialItems());

const placedIds = computed(() => new Set(items.value.map((i) => i.id)));
// Alle bekannten Widgets in Standardreihenfolge – Grundlage der Auswahlliste.
const allWidgetKeys = DEFAULT_WIDGET_ORDER;

function toggleWidget(key, on) {
  if (on) addWidget(key);
  else removeWidget(key);
}

function defaultItems() {
  // Explizites Default-Layout (durchdachte Anordnung) statt Auto-Flow.
  return DEFAULT_LAYOUT.map((it) => ({ ...it }));
}

function buildInitialItems() {
  // Server-Layout (pro Benutzer) hat Vorrang; unbekannte/entfernte Widgets werden
  // ignoriert. Leeres Layout ⇒ durchdachtes Standard-Layout.
  const saved = Array.isArray(settingsStore.settings?.ui?.dashboard_layout)
    ? settingsStore.settings.ui.dashboard_layout
    : [];
  const known = saved.filter((it) => it?.id && widgets[it.id]);
  return known.length ? known.map((it) => ({ ...it })) : defaultItems();
}

// ── Persistenz (Server-Setting ui.dashboard_layout, debounced) ────────────────
function collectNodes() {
  // grid.save(false) liefert u. a. id/x/y/w/h (+ min-Attribute); nur die Lage merken.
  return grid ? grid.save(false).map((n) => ({ id: n.id, x: n.x, y: n.y, w: n.w, h: n.h })) : [];
}

function writeLayout(nodes) {
  return settingsStore
    .patchSettings(getBaseUrl(), buildDashboardLayoutPatch(nodes))
    .catch((err) => {
      console.warn('Dashboard-Layout konnte nicht gespeichert werden:', err);
    });
}

function schedulePersist() {
  if (!grid || suppressPersist) return;
  if (persistTimer) clearTimeout(persistTimer);
  persistTimer = setTimeout(() => {
    persistTimer = null;
    if (grid) writeLayout(collectNodes());
  }, PERSIST_DEBOUNCE_MS);
}

async function addWidget(key) {
  if (!widgets[key] || placedIds.value.has(key)) return;
  const def = widgets[key];
  items.value = [...items.value, { id: key, w: def.defaultSize.w, h: def.defaultSize.h }];
  await nextTick();
  const el = gridEl.value?.querySelector(`.grid-stack-item[gs-id="${key}"]`);
  if (el && grid) {
    grid.makeWidget(el);
    schedulePersist();
  }
}

function removeWidget(key) {
  const el = gridEl.value?.querySelector(`.grid-stack-item[gs-id="${key}"]`);
  if (el && grid) grid.removeWidget(el, false); // DOM behält Vue, gridstack vergisst
  items.value = items.value.filter((i) => i.id !== key);
  schedulePersist();
}

function resetLayout() {
  // Programmatische Events während des Umbaus nicht speichern.
  suppressPersist = true;
  // Altes Grid verwerfen und den Teilbaum per key-Wechsel FRISCH rendern: so
  // entstehen saubere DOM-Elemente ohne gridstack-Rückstände (Inline-Styles,
  // verstellte gs-*-Attribute). Danach adoptiert initGrid die Standard-Items
  // zuverlässig über deren gs-*-Attribute.
  destroyGrid();
  items.value = defaultItems();
  gridKey.value += 1;
  nextTick(() => {
    initGrid();
    suppressPersist = false;
    if (persistTimer) { clearTimeout(persistTimer); persistTimer = null; }
    // Leeres Layout auf dem Server = „nutze Standard".
    writeLayout([]);
  });
}

function initGrid() {
  grid = GridStack.init(
    {
      column: GRID_COLUMN,
      cellHeight: CELL_HEIGHT,
      margin: 7,
      float: false,
      staticGrid: true, // Ansichtsmodus: kein Ziehen/Skalieren bis „Anpassen“.
      handle: '.dash-board__grip',
      animate: true,
    },
    gridEl.value
  );
  grid.on('change', schedulePersist);
  grid.on('added', schedulePersist);
  grid.on('removed', schedulePersist);
  // Falls im Anpassen-Modus (Mount während editing, oder Reset), Zustand anwenden.
  if (props.editing) applyEditable(true);
}

function destroyGrid() {
  if (!grid) return;
  grid.off('change');
  grid.off('added');
  grid.off('removed');
  grid.destroy(false); // DOM behalten (Vue besitzt es)
  grid = null;
}

onMounted(initGrid);

onBeforeUnmount(() => {
  // Ausstehende Speicherung vor dem Zerstören noch abschließen.
  if (persistTimer) {
    clearTimeout(persistTimer);
    persistTimer = null;
    if (grid) writeLayout(collectNodes());
  }
  destroyGrid();
});
</script>

<style scoped>
.dash-board {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1 1 auto;
}

.dash-board__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  /* Rinne für die (auf macOS überlagernde) Scrollbar reservieren, damit sie
     nicht über der rechten Kachelkante schwebt. scrollbar-gutter deckt klassische
     Scrollbars ab, das padding die Overlay-Variante. */
  scrollbar-gutter: stable;
  padding-right: 12px;
}

/* gridstack-Zellinhalt trägt das jeweilige Widget füllend. WICHTIG: kein
   inset:0 – gridstack setzt top/right/bottom/left = --gs-item-margin-* und
   erzeugt daraus die Abstände zwischen den Karten. */
.dash-board :deep(.grid-stack-item-content) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Rasterinhalt bündig zum Seitenkopf: gridstack rückt die Karten um den Margin
   (7px) ein; der negative Rand zieht die linke (und obere) Außenkante an die
   Kopfzeile heran. RECHTS bewusst 0 – ein negativer rechter Rand schöbe die
   Karten in die Scrollbar-Rinne, sodass die Scrollbar hinter den Kacheln läge. */
.dash-board :deep(.grid-stack) {
  margin: -7px 0 0 -7px;
}

.dash-board__widget {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
/* Widget-Wurzel füllt die Zelle. */
.dash-board__widget > :deep(*) {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
}

/* Verschiebe-Griff: nur im Bearbeiten-Modus sichtbar. Als kleine, ÜBERLAGERNDE
   Drag-Pille oben-mittig – so nimmt sie keine Höhe weg (keine abgeschnittenen
   Kacheln), dupliziert keinen Titel und sitzt über dem meist leeren Zentrum
   (verdeckt weder Titel links noch „Alle anzeigen" rechts). */
.dash-board__grip { display: none; }
.dash-board.is-editing .dash-board__grip {
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  height: 18px;
  padding: 0 10px;
  border-radius: 100px;
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 15%, var(--pm-v-card, var(--pm-app-surface-raised)));
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.14);
  cursor: grab;
}
.dash-board.is-editing .dash-board__grip:active { cursor: grabbing; }

/* Im Bearbeiten-Modus die Karten leicht „anfassbar“ rahmen. */
.dash-board.is-editing :deep(.grid-stack-item-content) {
  outline: 1px dashed color-mix(in srgb, var(--pm-accent) 30%, transparent);
  outline-offset: -1px;
  border-radius: 16px;
}

/* Rechts Platz für das Verwaltungsfenster reservieren, damit keine Kachel (und
   damit kein Resize-Anfasser) darunter liegt. Die %-basierten gridstack-Items
   stauchen sich automatisch mit der schmaleren Fläche. */
.dash-board.is-editing .dash-board__scroll {
  padding-right: 280px; /* ≈ Fensterbreite (264) + rechter Versatz (24) minus dem
                           bereits vorhandenen Seiten-Innenabstand */
}

/* ── Verwaltungsfenster (schwebend, nicht modal) ──────────────────────────── */
.dash-board__manager {
  position: fixed;
  top: 84px;
  right: 24px;
  z-index: 40;
  width: 264px;
  max-height: calc(100vh - 108px);
  display: flex;
  flex-direction: column;
  background: var(--pm-v-card, var(--pm-app-surface-raised));
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
  padding: 14px 14px 12px;
  animation: dash-manager-in 0.18s ease-out both;
}
@keyframes dash-manager-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .dash-board__manager { animation: none; }
}
.dash-board__manager-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.dash-board__manager-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--pm-text);
}
.dash-board__manager-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}
.dash-board__manager-close:hover {
  color: var(--pm-text);
  background: rgba(var(--v-theme-on-surface), 0.06);
}
.dash-board__manager-hint {
  margin: 4px 0 10px;
  font-size: 11.5px;
  color: var(--pm-muted);
  line-height: 1.35;
}
.dash-board__manager-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1 1 auto;
  min-height: 0;
}
.dash-board__manager-label {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 6px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--pm-text);
}
.dash-board__manager-label:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}
.dash-board__manager-check {
  width: 16px;
  height: 16px;
  accent-color: var(--pm-accent);
  cursor: pointer;
  flex: none;
}
.dash-board__manager-icon {
  color: var(--pm-muted) !important;
  flex: none;
}
.dash-board__manager-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dash-board__manager-reset {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 34px;
  border: 1px solid var(--pm-divider);
  border-radius: 9px;
  background: transparent;
  color: var(--pm-muted);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  flex: none;
  transition: color 140ms ease, border-color 140ms ease;
}
.dash-board__manager-reset:hover {
  color: var(--pm-text);
  border-color: color-mix(in srgb, var(--pm-text) 22%, transparent);
}
</style>
