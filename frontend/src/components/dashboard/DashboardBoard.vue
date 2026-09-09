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
    <div
      ref="boardScrollEl"
      class="dash-board__scroll"
      :class="{ 'is-drop-target': paletteDragging }"
    >
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
        <div
          v-if="dropPreview"
          class="dash-board__drop-preview"
          :style="dropPreviewStyle"
          aria-hidden="true"
        >
          <v-icon size="22">mdi-plus</v-icon>
          <span>{{ widgets[draggingWidgetKey]?.label }}</span>
        </div>
      </div>
    </div>

    <!-- Die Auswahl ist ein eigener Schritt: Der Dialog verschwindet vor dem
         Verschieben/Skalieren und kann im Bearbeitungsmodus erneut geöffnet werden. -->
    <BaseDialog
      v-model="managerOpen"
      title="Dashboard anpassen"
      header-subtitle="Klicke zum Ein- oder Ausblenden – oder ziehe eine Kachel direkt ins Dashboard."
      icon="mdi-view-dashboard-edit-outline"
      :show-footer="true"
      :show-secondary="false"
      max-width="720"
      :scrim="!paletteDragging"
      :content-class="['dash-widget-picker-overlay', { 'is-dragging': paletteDragging }]"
      :card-class="['dash-widget-picker', { 'is-dragging': paletteDragging }]"
    >
      <ul class="dash-widget-picker__grid">
        <li v-for="key in allWidgetKeys" :key="key" class="dash-widget-picker__item">
          <label
            class="dash-widget-picker__tile"
            :class="{ 'is-selected': placedIds.has(key) }"
            @pointerdown="onPalettePointerDown(key, $event)"
            @click.capture="onPaletteTileClick"
          >
            <input
              type="checkbox"
              class="dash-widget-picker__check"
              :checked="placedIds.has(key)"
              @change="toggleWidget(key, $event.target.checked)"
            />
            <span class="dash-widget-picker__icon">
              <v-icon size="24">{{ widgets[key].icon }}</v-icon>
            </span>
            <span class="dash-widget-picker__copy">
              <strong class="dash-widget-picker__name">{{ widgets[key].label }}</strong>
              <span class="dash-widget-picker__description">{{ widgets[key].description }}</span>
            </span>
            <span class="dash-widget-picker__state" aria-hidden="true">
              <v-icon size="16">{{ placedIds.has(key) ? 'mdi-check' : 'mdi-plus' }}</v-icon>
            </span>
          </label>
        </li>
      </ul>
      <template #footer>
        <v-btn variant="text" class="dash-widget-picker__reset" prepend-icon="mdi-restore" @click="resetLayout">
          Standard wiederherstellen
        </v-btn>
        <v-spacer />
        <v-btn color="primary" variant="tonal" class="dash-widget-picker__continue" @click="managerOpen = false">
          Layout bearbeiten
        </v-btn>
      </template>
    </BaseDialog>

    <Teleport to="body">
      <div
        v-if="paletteDragging && draggingWidgetKey"
        class="dash-widget-drag-ghost"
        :style="dragGhostStyle"
        aria-hidden="true"
      >
        <span class="dash-widget-drag-ghost__icon">
          <v-icon size="20">{{ widgets[draggingWidgetKey].icon }}</v-icon>
        </span>
        <span>{{ widgets[draggingWidgetKey].label }}</span>
      </div>
    </Teleport>
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
import BaseDialog from '../BaseDialog.vue';

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
const boardScrollEl = ref(null);
const managerOpen = ref(false);
const paletteDragging = ref(false);
const draggingWidgetKey = ref('');
const dropPreview = ref(null);
const dragPointer = ref({ x: 0, y: 0 });
let pointerCandidate = null;
let suppressTileClick = false;
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
    managerOpen.value = val;
    await nextTick();
    applyEditable(val);
  }
);

function openManager() {
  if (props.editing) managerOpen.value = true;
}

defineExpose({ openManager });

// `items` = Renderliste der Zellen. Nur bei Add/Remove verändert; Position/Größe
// besitzt nach der Initialisierung gridstack. shallowRef, weil die Item-Objekte
// nach dem Rendern nicht reaktiv weitergepflegt werden.
const items = shallowRef(buildInitialItems());

const placedIds = computed(() => new Set(items.value.map((i) => i.id)));
// Alle bekannten Widgets in Standardreihenfolge – Grundlage der Auswahlliste.
const allWidgetKeys = DEFAULT_WIDGET_ORDER;

const dropPreviewStyle = computed(() => {
  if (!dropPreview.value) return undefined;
  const { x, y, w, h } = dropPreview.value;
  return {
    left: `calc(${(x / GRID_COLUMN) * 100}% + 7px)`,
    top: `${y * CELL_HEIGHT + 7}px`,
    width: `calc(${(w / GRID_COLUMN) * 100}% - 14px)`,
    height: `${h * CELL_HEIGHT - 14}px`,
  };
});

const dragGhostStyle = computed(() => ({
  left: `${dragPointer.value.x + 14}px`,
  top: `${dragPointer.value.y + 14}px`,
}));

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

async function addWidget(key, position = null) {
  if (!widgets[key] || placedIds.value.has(key)) return;
  const def = widgets[key];
  const item = {
    id: key,
    w: def.defaultSize.w,
    h: def.defaultSize.h,
    ...(position || {}),
  };
  items.value = [...items.value, item];
  await nextTick();
  const el = gridEl.value?.querySelector(`.grid-stack-item[gs-id="${key}"]`);
  if (el && grid) {
    grid.makeWidget(el);
    schedulePersist();
  }
}

function getDropPosition(point, key) {
  const rect = gridEl.value?.getBoundingClientRect();
  const def = widgets[key];
  if (!rect || !def || rect.width <= 0) return null;
  const w = Math.min(def.defaultSize.w, GRID_COLUMN);
  const h = def.defaultSize.h;
  const columnWidth = rect.width / GRID_COLUMN;
  const pointerColumn = (point.clientX - rect.left) / columnWidth;
  const x = Math.max(0, Math.min(GRID_COLUMN - w, Math.round(pointerColumn - w / 2)));
  const pointerRow = (point.clientY - rect.top) / CELL_HEIGHT;
  const y = Math.max(0, Math.round(pointerRow - h / 2));
  return { x, y, w, h };
}

function onPalettePointerDown(key, event) {
  if (event.button !== 0) return;
  pointerCandidate = {
    key,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
  };
  dragPointer.value = { x: event.clientX, y: event.clientY };
  window.addEventListener('pointermove', onPalettePointerMove, { passive: false });
  window.addEventListener('pointerup', onPalettePointerUp);
  window.addEventListener('pointercancel', onPalettePointerCancel);
}

function clearPaletteDrag() {
  paletteDragging.value = false;
  draggingWidgetKey.value = '';
  dropPreview.value = null;
  pointerCandidate = null;
  document.body.classList.remove('dash-widget-is-dragging');
  window.removeEventListener('pointermove', onPalettePointerMove);
  window.removeEventListener('pointerup', onPalettePointerUp);
  window.removeEventListener('pointercancel', onPalettePointerCancel);
}

function pointerIsOverBoard(point) {
  const rect = boardScrollEl.value?.getBoundingClientRect();
  return Boolean(
    rect
    && point.clientX >= rect.left
    && point.clientX <= rect.right
    && point.clientY >= rect.top
    && point.clientY <= rect.bottom
  );
}

function onPalettePointerMove(event) {
  if (!pointerCandidate || event.pointerId !== pointerCandidate.pointerId) return;
  const distance = Math.hypot(
    event.clientX - pointerCandidate.startX,
    event.clientY - pointerCandidate.startY,
  );
  if (!paletteDragging.value && distance < 6) return;

  if (!paletteDragging.value) {
    draggingWidgetKey.value = pointerCandidate.key;
    paletteDragging.value = true;
    suppressTileClick = true;
    document.body.classList.add('dash-widget-is-dragging');
  }

  event.preventDefault();
  dragPointer.value = { x: event.clientX, y: event.clientY };
  dropPreview.value = pointerIsOverBoard(event)
    ? getDropPosition(event, pointerCandidate.key)
    : null;

  const scrollEl = boardScrollEl.value;
  if (scrollEl && dropPreview.value) {
    const rect = scrollEl.getBoundingClientRect();
    if (event.clientY < rect.top + 40) scrollEl.scrollTop -= 18;
    else if (event.clientY > rect.bottom - 40) scrollEl.scrollTop += 18;
  }
}

async function placeDraggedWidget(key, position) {
  if (placedIds.value.has(key)) {
    const el = gridEl.value?.querySelector(`.grid-stack-item[gs-id="${key}"]`);
    if (el && grid) {
      grid.update(el, { x: position.x, y: position.y });
      schedulePersist();
    }
    return;
  }
  await addWidget(key, position);
}

function onPalettePointerUp(event) {
  if (!pointerCandidate || event.pointerId !== pointerCandidate.pointerId) return;
  const key = pointerCandidate.key;
  const position = paletteDragging.value && pointerIsOverBoard(event)
    ? getDropPosition(event, key)
    : null;
  const didDrag = paletteDragging.value;
  clearPaletteDrag();

  if (didDrag) {
    // Der nach pointerup erzeugte Label-Klick darf das Widget nicht wieder ausblenden.
    window.setTimeout(() => { suppressTileClick = false; }, 0);
  }
  if (position) {
    managerOpen.value = false;
    void placeDraggedWidget(key, position);
  }
}

function onPalettePointerCancel() {
  const didDrag = paletteDragging.value;
  clearPaletteDrag();
  if (didDrag) window.setTimeout(() => { suppressTileClick = false; }, 0);
}

function onPaletteTileClick(event) {
  if (!suppressTileClick) return;
  event.preventDefault();
  event.stopPropagation();
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
  clearPaletteDrag();
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
  /* Bis an die Fensterkante ausdehnen (über den horizontalen Seitenabstand des
     Elternteils hinaus), damit die Scrollbar rechts NEBEN dem ausgerichteten
     Inhalt schwebt statt über den Kacheln. */
  margin-right: calc(-1 * var(--dash-pad-x, 30px));
}

.dash-board__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  /* Kacheln enden exakt beim Seitenabstand (bündig zum Kopf); die restliche
     Breite bis zur Fensterkante ist die Scrollbar-Rinne. Minus 7px, weil die
     gridstack-Karten ihrerseits um den Margin (7px) eingerückt sind. */
  padding-right: calc(var(--dash-pad-x, 30px) - 7px);
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
  position: relative;
  margin: -7px 0 0 -7px;
}

.dash-board__drop-preview {
  position: absolute;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  pointer-events: none;
  border: 2px dashed color-mix(in srgb, var(--pm-accent) 68%, transparent);
  border-radius: 16px;
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 12%, transparent);
  font-size: 13px;
  font-weight: 650;
  animation: dash-drop-preview-in 140ms ease-out both;
}
@keyframes dash-drop-preview-in {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
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
  user-select: none;
}
.dash-board.is-editing .dash-board__grip:active { cursor: grabbing; }

/* Im Bearbeiten-Modus die Karten leicht „anfassbar“ rahmen. */
.dash-board.is-editing :deep(.grid-stack-item-content) {
  outline: 1px dashed color-mix(in srgb, var(--pm-accent) 30%, transparent);
  outline-offset: -1px;
  border-radius: 16px;
}

.dash-widget-picker__grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.dash-widget-picker__item {
  min-width: 0;
}
.dash-widget-picker__tile {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 104px;
  height: 100%;
  padding: 16px;
  border: 1px solid color-mix(in srgb, var(--pm-divider) 85%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--pm-v-card, var(--pm-app-surface-raised)) 96%, var(--pm-text) 4%);
  cursor: grab;
  color: var(--pm-text);
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}
.dash-widget-picker__tile:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--pm-accent) 34%, var(--pm-divider));
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.07);
}
.dash-widget-picker__tile:active { cursor: grabbing; }
.dash-widget-picker__tile.is-selected {
  border-color: color-mix(in srgb, var(--pm-accent) 52%, var(--pm-divider));
  background: color-mix(in srgb, var(--pm-accent) 7%, var(--pm-v-card, var(--pm-app-surface-raised)));
}
.dash-widget-picker__tile:focus-within {
  outline: 2px solid color-mix(in srgb, var(--pm-accent) 58%, transparent);
  outline-offset: 2px;
}
.dash-widget-picker__check {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
}
.dash-widget-picker__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex: none;
  border-radius: 11px;
  color: var(--pm-muted);
  background: rgba(var(--v-theme-on-surface), 0.055);
}
.dash-widget-picker__tile.is-selected .dash-widget-picker__icon {
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 13%, transparent);
}
.dash-widget-picker__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding-right: 22px;
}
.dash-widget-picker__name {
  font-size: 14px;
  font-weight: 650;
  line-height: 1.25;
}
.dash-widget-picker__description {
  color: var(--pm-muted);
  font-size: 12px;
  line-height: 1.4;
}
.dash-widget-picker__state {
  position: absolute;
  top: 13px;
  right: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 23px;
  height: 23px;
  border: 1px solid var(--pm-divider);
  border-radius: 50%;
  color: var(--pm-muted);
  background: var(--pm-v-card, var(--pm-app-surface-raised));
}
.dash-widget-picker__tile.is-selected .dash-widget-picker__state {
  color: white;
  border-color: var(--pm-accent);
  background: var(--pm-accent);
}
.dash-widget-picker__reset,
.dash-widget-picker__continue {
  text-transform: none;
  letter-spacing: 0;
  font-weight: 650;
}
@media (max-width: 620px) {
  .dash-widget-picker__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (prefers-reduced-motion: reduce) {
  .dash-widget-picker__tile { transition: none; }
  .dash-widget-picker__tile:hover { transform: none; }
  .dash-board__drop-preview { animation: none; }
}
</style>

<!-- Der Dialog wird zu <body> teleportiert. Diese beiden Klassen müssen daher
     global sein; alle Namen bleiben dashboard-spezifisch. -->
<style>
.dash-widget-picker-overlay {
  transition: transform 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.dash-widget-picker-overlay.is-dragging {
  transform: translateY(calc(50vh - 104px)) scale(0.92);
  pointer-events: none;
}

.pm-dialog.dash-widget-picker {
  max-height: 680px;
  overflow: hidden;
  transition: max-height 280ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 180ms ease;
}

.pm-dialog.dash-widget-picker.is-dragging {
  position: relative;
  max-height: 76px;
  min-height: 76px;
  opacity: 0.96;
}

.pm-dialog.dash-widget-picker.is-dragging > * {
  opacity: 0;
}

.pm-dialog.dash-widget-picker.is-dragging::after {
  content: 'Im Dashboard ablegen';
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--v-theme-primary));
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.dash-widget-drag-ghost {
  position: fixed;
  z-index: 10000;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  max-width: 260px;
  padding: 10px 13px 10px 10px;
  border: 1px solid color-mix(in srgb, rgb(var(--v-theme-primary)) 48%, transparent);
  border-radius: 12px;
  color: rgb(var(--v-theme-on-surface));
  background: rgb(var(--v-theme-surface-2, var(--v-theme-surface)));
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
  font-size: 13px;
  font-weight: 650;
  pointer-events: none;
}

.dash-widget-drag-ghost__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  color: rgb(var(--v-theme-primary));
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 13%, transparent);
}

body.dash-widget-is-dragging,
body.dash-widget-is-dragging * {
  cursor: grabbing !important;
  user-select: none !important;
}

@media (prefers-reduced-motion: reduce) {
  .dash-widget-picker-overlay,
  .pm-dialog.dash-widget-picker {
    transition: none;
  }
}
</style>
