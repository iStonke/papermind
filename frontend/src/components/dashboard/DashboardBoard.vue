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
    <div class="dash-board__bar">
      <button type="button" class="dash-board__btn" :class="{ 'is-active': editing }" @click="toggleEdit">
        <v-icon size="15">{{ editing ? 'mdi-check' : 'mdi-view-dashboard-edit-outline' }}</v-icon>
        {{ editing ? 'Fertig' : 'Anpassen' }}
      </button>

      <template v-if="editing">
        <div class="dash-board__spacer" />
        <div v-if="addableWidgets.length" class="dash-board__add">
          <span class="dash-board__add-label">Hinzufügen:</span>
          <button
            v-for="w in addableWidgets"
            :key="w.key"
            type="button"
            class="dash-board__chip"
            @click="addWidget(w.key)"
          >
            <v-icon size="14">{{ w.icon }}</v-icon>
            {{ w.label }}
          </button>
        </div>
        <button type="button" class="dash-board__btn dash-board__btn--ghost" @click="resetLayout">
          <v-icon size="15">mdi-restore</v-icon>
          Zurücksetzen
        </button>
      </template>
    </div>

    <div class="dash-board__scroll">
      <div ref="gridEl" class="grid-stack">
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
            <div class="dash-board__grip" title="Zum Verschieben ziehen">
              <v-icon size="16">mdi-drag</v-icon>
              <span class="dash-board__grip-label">{{ widgets[item.id]?.label }}</span>
              <button
                type="button"
                class="dash-board__remove"
                title="Widget entfernen"
                @pointerdown.stop
                @click.stop="removeWidget(item.id)"
              >
                <v-icon size="16">mdi-close</v-icon>
              </button>
            </div>
            <div class="dash-board__widget">
              <component :is="widgets[item.id].component" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import { GridStack } from 'gridstack';
import 'gridstack/dist/gridstack.min.css';
import { DASHBOARD_WIDGETS, DEFAULT_LAYOUT, DEFAULT_WIDGET_ORDER } from './widgetRegistry.js';

const STORAGE_KEY = 'pm.dashboard.layout.v1';
const GRID_COLUMN = 12;
const CELL_HEIGHT = 74;

const widgets = DASHBOARD_WIDGETS;
const gridEl = ref(null);
const editing = ref(false);
let grid = null;

// `items` = Renderliste der Zellen. Nur bei Add/Remove verändert; Position/Größe
// besitzt nach der Initialisierung gridstack. shallowRef, weil die Item-Objekte
// nach dem Rendern nicht reaktiv weitergepflegt werden.
const items = shallowRef(buildInitialItems());

const placedIds = computed(() => new Set(items.value.map((i) => i.id)));
const addableWidgets = computed(() =>
  DEFAULT_WIDGET_ORDER.filter((key) => !placedIds.value.has(key)).map((key) => widgets[key])
);

function defaultItems() {
  // Explizites Default-Layout (durchdachte Anordnung) statt Auto-Flow.
  return DEFAULT_LAYOUT.map((it) => ({ ...it }));
}

function buildInitialItems() {
  const saved = loadLayout();
  if (!saved?.length) return defaultItems();
  // Nur bekannte Widgets übernehmen; unbekannte (z. B. entfernte) ignorieren.
  const known = saved.filter((it) => it.id && widgets[it.id]);
  return known.length ? known.map((it) => ({ ...it })) : defaultItems();
}

function loadLayout() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function persist() {
  if (!grid) return;
  try {
    const nodes = grid.save(false); // [{id,x,y,w,h}, …]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nodes));
  } catch { /* Speicher nicht verfügbar – Layout bleibt nur zur Laufzeit */ }
}

async function toggleEdit() {
  editing.value = !editing.value;
  // Erst rendern lassen: der Drag-Handle (.dash-board__grip) entsteht reaktiv
  // mit dem Bearbeiten-Modus. Würde setStatic(false) davor laufen, fände
  // gridstack den Handle nicht und ließe die Karten nicht ziehen.
  await nextTick();
  if (!grid) return;
  grid.setStatic(!editing.value);
  grid.enableMove(editing.value);
  grid.enableResize(editing.value);
}

async function addWidget(key) {
  if (!widgets[key] || placedIds.value.has(key)) return;
  const def = widgets[key];
  items.value = [...items.value, { id: key, w: def.defaultSize.w, h: def.defaultSize.h }];
  await nextTick();
  const el = gridEl.value?.querySelector(`.grid-stack-item[gs-id="${key}"]`);
  if (el && grid) {
    grid.makeWidget(el);
    persist();
  }
}

function removeWidget(key) {
  const el = gridEl.value?.querySelector(`.grid-stack-item[gs-id="${key}"]`);
  if (el && grid) grid.removeWidget(el, false); // DOM behält Vue, gridstack vergisst
  items.value = items.value.filter((i) => i.id !== key);
  persist();
}

function resetLayout() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* egal */ }
  // Neu aufbauen: gridstack leeren, Vue-Liste ersetzen, neu adoptieren.
  grid?.removeAll(false);
  items.value = defaultItems();
  nextTick(() => {
    if (!grid) return;
    grid.batchUpdate();
    for (const el of gridEl.value?.querySelectorAll('.grid-stack-item') || []) {
      grid.makeWidget(el);
    }
    grid.batchUpdate(false);
    persist();
  });
}

onMounted(() => {
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
  grid.on('change', persist);
  grid.on('added', persist);
  grid.on('removed', persist);
});

onBeforeUnmount(() => {
  grid?.off('change');
  grid?.off('added');
  grid?.off('removed');
  grid?.destroy(false);
  grid = null;
});
</script>

<style scoped>
.dash-board {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1 1 auto;
}

.dash-board__bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  flex: none;
}

.dash-board__spacer { flex: 1 1 auto; }

.dash-board__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  font-size: 12.5px;
  font-weight: 600;
  border-radius: 8px;
  border: 1px solid var(--pm-divider);
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
  transition: background var(--pm-duration-fast, 140ms) var(--pm-easing, ease), color var(--pm-duration-fast, 140ms) var(--pm-easing, ease), border-color var(--pm-duration-fast, 140ms) var(--pm-easing, ease);
}
.dash-board__btn:hover {
  color: var(--pm-text);
  border-color: color-mix(in srgb, var(--pm-text) 22%, transparent);
}
.dash-board__btn.is-active {
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 13%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 32%, transparent);
}
.dash-board__btn--ghost { font-weight: 500; }

.dash-board__add {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.dash-board__add-label {
  font-size: 12px;
  color: var(--pm-muted);
}
.dash-board__chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 100px;
  border: 1px dashed color-mix(in srgb, var(--pm-accent) 40%, var(--pm-divider));
  background: transparent;
  color: var(--pm-text);
  cursor: pointer;
}
.dash-board__chip:hover {
  border-style: solid;
  background: color-mix(in srgb, var(--pm-accent) 8%, transparent);
}

.dash-board__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

/* gridstack-Zellinhalt trägt das jeweilige Widget randlos und füllend. */
.dash-board :deep(.grid-stack-item-content) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  inset: 0;
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

/* Verschiebe-Griff + Entfernen: immer im DOM, aber nur im Bearbeiten-Modus
   sichtbar (siehe Kommentar im Template). */
.dash-board__grip { display: none; }
.dash-board.is-editing .dash-board__grip {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 6px 0 4px;
  flex: none;
  color: var(--pm-muted);
  cursor: grab;
  border-bottom: 1px dashed var(--pm-divider);
  background: color-mix(in srgb, var(--pm-accent) 5%, transparent);
}
.dash-board__grip:active { cursor: grabbing; }
.dash-board__grip-label {
  font-size: 11.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 auto;
}
.dash-board__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}
.dash-board__remove:hover {
  color: var(--pm-danger, #c2453b);
  background: color-mix(in srgb, var(--pm-danger, #c2453b) 12%, transparent);
}

/* Im Bearbeiten-Modus die Karten leicht „anfassbar“ rahmen. */
.dash-board.is-editing :deep(.grid-stack-item-content) {
  outline: 1px dashed color-mix(in srgb, var(--pm-accent) 30%, transparent);
  outline-offset: -1px;
  border-radius: 16px;
}
</style>
