<!--
  CollectionMemberTiles — Mitglieder einer Sammlung als Kacheln. Jede Kachel
  zeigt einen Stapel der neuesten Deckblätter, Anzahl und Zeitraum. Ein Klick öffnet direkt unter der Kachelzeile ein Panel mit
  den Dokumenten des Mitglieds (die Kacheln bleiben an ihrem Platz, das Panel
  wächst in der Höhe auf); ein Klick auf ein Dokument öffnet eine große
  Vorschau als Overlay.

  Daten: utils/correspondentProfileStats.js → collectionMemberSummaries().
-->
<template>
  <ul
    ref="gridEl"
    class="cmt-grid"
    :aria-label="`Mitglieder von ${collectionName}`"
    @keydown.esc="onEscape"
  >
    <template v-for="(entry, index) in entries" :key="entry.key">
      <li v-if="entry.add" class="cmt cmt--add">
        <slot name="add" />
      </li>
      <li
        v-else
        class="cmt"
        :class="{ 'is-active': openKey === entry.key, 'is-empty': !entry.count, 'cmt--direct': entry.direct }"
        :style="{ '--cmt-tone': entry.tone }"
        :data-key="entry.key"
      >
        <!-- Ohne Dokumente gibt es nichts aufzuklappen: keine Schaltfläche. -->
        <component
          :is="entry.count ? 'button' : 'div'"
          v-bind="entry.count ? {
            type: 'button',
            'aria-expanded': openKey === entry.key,
            'aria-controls': openKey === entry.key ? panelId : undefined,
            'aria-label': `${entry.name}: ${countLabel(entry.count)} ${openKey === entry.key ? 'zuklappen' : 'aufklappen'}`,
          } : {}"
          class="cmt__face"
          @click="entry.count && toggle(entry.key)"
        >
          <span class="cmt__stack" aria-hidden="true">
            <span
              v-for="(sheet, sheetIndex) in sheetsOf(entry)"
              :key="sheetIndex"
              class="cmt__sheet"
              :class="`cmt__sheet--${sheetIndex}`"
            >
              <!-- Platzhalter liegt hinter dem Deckblatt; sichtbar ohne Seiten oder wenn das Bild fehlt. -->
              <v-icon size="26" class="cmt__sheet-icon">mdi-file-document-outline</v-icon>
              <img v-if="sheet" :src="thumbnail(sheet)" alt="" loading="lazy" decoding="async" @error="$event.target.hidden = true">
            </span>
          </span>
          <span class="cmt__name">
            <v-icon size="15" class="cmt__kind" aria-hidden="true">{{ entry.icon }}</v-icon>
            <span class="cmt__name-text" :title="entry.name">{{ entry.name }}</span>
          </span>
          <span class="cmt__meta">{{ metaLabel(entry) }}</span>
        </component>
        <button
          v-if="!entry.direct"
          type="button"
          class="cmt__remove"
          :disabled="disabled"
          :aria-label="`Zuordnung von ${entry.name} lösen`"
          :title="`Zuordnung von ${entry.name} lösen`"
          @click="emit('remove', entry.id)"
        ><v-icon size="14" aria-hidden="true">mdi-close</v-icon></button>
      </li>

      <!-- Panel unter der Zeile der geöffneten Kachel. -->
      <Transition :css="false" @enter="onPanelEnter" @leave="animatePanelLeave">
        <li
          v-if="openTile && panelAfter === index"
          :id="panelId"
          :key="`panel-${index}`"
          class="cmt-panel"
          role="region"
          :aria-label="`Dokumente von ${openTile.name}`"
        >
          <div :key="openTile.key" class="cmt-panel__body" :style="{ '--cmt-tone': openTile.tone }">
            <div class="cmt__head">
              <span class="cmt__dot" aria-hidden="true" />
              <div class="cmt__head-copy">
                <h3 class="cmt__title">{{ openTile.name }}</h3>
                <span class="cmt__meta">{{ metaLabel(openTile) }}</span>
              </div>
              <button
                v-if="!openTile.direct"
                type="button"
                class="cmt__link"
                @click="emit('open-profile', openTile.id)"
              >
                Profil öffnen
                <v-icon size="14" aria-hidden="true">mdi-arrow-right</v-icon>
              </button>
              <button
                type="button"
                class="cmt__icon-btn"
                :aria-label="`${openTile.name} zuklappen`"
                title="Zuklappen"
                @click="close({ focus: true })"
              ><v-icon size="18" aria-hidden="true">mdi-chevron-up</v-icon></button>
            </div>

            <CorrespondentDocumentGrid
              class="cmt-panel__docs"
              size="compact"
              :documents="docs.items"
              :total="docs.total"
              :loading="docs.loading && !docs.items.length"
              :loading-more="docs.loading && docs.items.length > 0"
              :failed="docs.failed && !docs.items.length"
              :load-more-failed="docs.failed && docs.items.length > 0"
              :skeleton-count="skeletonCount"
              :label="`Dokumente von ${openTile.name}`"
              @retry="loadDocs(openTile)"
              @load-more="loadDocs(openTile, true)"
            />
          </div>
        </li>
      </Transition>
    </template>
  </ul>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import CorrespondentDocumentGrid from './CorrespondentDocumentGrid.vue';
import { documentThumbnailUrl, listDocuments } from '../api/documents.js';
import { collectionTone } from '../utils/correspondentProfileStats.js';
import { correspondentKindIcon } from '../utils/correspondentHierarchy.js';
import {
  animatePanelEnter,
  animatePanelLeave,
  observeColumns,
  revealPanel,
  rowEnd,
  tweenHeight,
} from '../utils/expandPanel.js';

const DIRECT_KEY = '__direct';
const ADD_KEY = '__add';
const DOC_PAGE_SIZE = 12;

const props = defineProps({
  collectionId: { type: String, required: true },
  collectionName: { type: String, default: '' },
  /** collectionMemberSummaries() → { rows, direct } */
  summaries: { type: Object, required: true },
  disabled: Boolean,
});
const emit = defineEmits(['open-profile', 'remove', 'open-change']);

const panelId = `cmt-panel-${Math.random().toString(36).slice(2, 8)}`;

const tiles = computed(() => {
  const list = (props.summaries?.rows || []).map((row, index) => ({
    ...row,
    key: row.id,
    direct: false,
    icon: correspondentKindIcon(row.kind) || 'mdi-domain',
    tone: collectionTone(index),
  }));
  const direct = props.summaries?.direct;
  if (direct?.count) {
    list.unshift({
      ...direct,
      id: props.collectionId,
      key: DIRECT_KEY,
      name: 'Direkt zugeordnet',
      direct: true,
      icon: 'mdi-shape-outline',
      tone: 'color-mix(in srgb, var(--pm-muted) 55%, var(--pm-app-surface))',
    });
  }
  return list;
});
const entries = computed(() => [...tiles.value, { key: ADD_KEY, add: true }]);

const openKey = ref(null);
const docs = reactive({ items: [], total: 0, loading: false, failed: false });
let loadSeq = 0;

const openTile = computed(() => tiles.value.find((t) => t.key === openKey.value) || null);
const skeletonCount = computed(() => Math.min(Math.max(openTile.value?.count || 1, 1), DOC_PAGE_SIZE));

// Spaltenzahl des Rasters → Panel landet hinter dem letzten Element der Zeile.
const gridEl = ref(null);
const memberCols = ref(1);
let stopObserving = null;
watch(gridEl, (el) => {
  stopObserving?.();
  stopObserving = el ? observeColumns(el, (count) => { memberCols.value = count; }) : null;
}, { flush: 'post' });
onBeforeUnmount(() => stopObserving?.());

const panelAfter = computed(() => rowEnd(
  entries.value.findIndex((e) => e.key === openKey.value),
  memberCols.value,
  entries.value.length,
));

function livePanel() {
  return gridEl.value?.querySelector(':scope > .cmt-panel:not(.is-leaving)') || null;
}
function reveal() {
  revealPanel(gridEl.value?.querySelector(':scope > .cmt.is-active'), livePanel());
}
function onPanelEnter(el, done) {
  animatePanelEnter(el, done, reveal);
}
function tileFace(key) {
  return gridEl.value?.querySelector(`:scope > .cmt[data-key="${CSS.escape(key)}"] .cmt__face`) || null;
}

async function open(key) {
  const tile = tiles.value.find((t) => t.key === key);
  if (!tile?.count) return;
  const index = entries.value.findIndex((e) => e.key === key);
  const sameRow = openKey.value && rowEnd(index, memberCols.value, entries.value.length) === panelAfter.value;
  const apply = () => {
    openKey.value = key;
    loadDocs(tile);
  };
  emit('open-change', tile.id);
  if (sameRow) {
    await tweenHeight(livePanel(), apply);
    reveal();
  } else {
    apply();
  }
}

async function close({ focus = false } = {}) {
  const key = openKey.value;
  if (!key) return;
  const hadFocus = livePanel()?.contains(document.activeElement);
  openKey.value = null;
  loadSeq += 1;
  emit('open-change', null);
  if (focus || hadFocus) {
    await nextTick();
    tileFace(key)?.focus?.({ preventScroll: true });
  }
}

function toggle(key) {
  if (openKey.value === key) close();
  else open(key);
}

/** Von außen (Anteilsband): Mitglied aufklappen bzw. zuklappen. */
function toggleMember(id) {
  toggle(id === props.collectionId ? DIRECT_KEY : id);
}

async function loadDocs(tile, more = false) {
  const seq = ++loadSeq;
  if (!more) {
    docs.items = [];
    docs.total = tile.count;
  }
  docs.loading = true;
  docs.failed = false;
  const params = new URLSearchParams({
    correspondent_id: tile.id,
    sort: 'correspondent_date',
    order: 'desc',
    limit: String(DOC_PAGE_SIZE),
    offset: String(more ? docs.items.length : 0),
  });
  if (!tile.direct) params.set('correspondent_members', 'true');
  try {
    const result = await listDocuments(params.toString());
    if (seq !== loadSeq) return;
    await tweenHeight(livePanel(), () => {
      const known = new Set(docs.items.map((d) => d.id));
      const items = (result.items || []).filter((d) => !known.has(d.id));
      docs.items = [...docs.items, ...items];
      docs.total = Number(result.total ?? docs.items.length);
      if (!items.length) docs.total = docs.items.length;
      docs.loading = false;
    });
  } catch {
    if (seq === loadSeq) {
      await tweenHeight(livePanel(), () => {
        docs.failed = true;
        docs.loading = false;
      });
    }
  } finally {
    if (seq === loadSeq) docs.loading = false;
  }
}

function onEscape(event) {
  if (!openKey.value) return;
  close({ focus: true });
  event.stopPropagation();
}

watch(() => props.collectionId, () => {
  openKey.value = null;
  loadSeq += 1;
});
// Verschwindet das geöffnete Mitglied (z. B. Zuordnung gelöst), Panel schließen.
watch(tiles, (list) => {
  if (openKey.value && !list.some((t) => t.key === openKey.value)) {
    openKey.value = null;
    emit('open-change', null);
  }
});

function sheetsOf(tile) {
  const ids = tile.coverIds || [];
  const count = Math.min(3, Math.max(1, tile.count || 0));
  return Array.from({ length: count }, (_, i) => ids[count - 1 - i] || null);
}

function thumbnail(id) {
  return documentThumbnailUrl(id);
}

function countLabel(n) {
  if (!n) return 'Keine Dokumente';
  return `${n} ${n === 1 ? 'Dokument' : 'Dokumente'}`;
}

function metaLabel(tile) {
  const a = tile.first?.getFullYear?.();
  const b = tile.last?.getFullYear?.();
  const span = a && b ? (a === b ? String(a) : `${a}–${b}`) : '';
  return [countLabel(tile.count), span].filter(Boolean).join(' · ');
}

defineExpose({ toggleMember, openKey });
</script>

<style scoped>
/*
  Zeilenabstand über margin-bottom statt row-gap: so kann ein Panel beim
  Auf-/Zuklappen seinen Abstand mitanimieren (row-gap würde springen).
*/
.cmt-grid {
  --cmt-gap: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 196px), 1fr));
  column-gap: var(--cmt-gap);
  row-gap: 0;
  margin: 0 0 calc(-1 * var(--cmt-gap));
  padding: 0;
  list-style: none;
  /* Neutrales, leicht abgesenktes Panel: die Dokumentkarten liegen erhöht darauf.
     Akzentfarbe nur für den Zustand „ausgewählt“. */
  --cmt-panel-bg: color-mix(in srgb, var(--pm-text) 3.5%, var(--pm-app-surface));
  --cmt-panel-border: var(--pm-list-divider);
  --cmt-active: var(--pm-accent);
}
.cmt {
  position: relative;
  min-width: 0;
  /* Platz für Deckblätter, Abstände und zwei Textzeilen. */
  block-size: calc(140px + 2.34rem);
  margin-bottom: var(--cmt-gap);
  border: 1px solid var(--pm-list-divider);
  border-radius: 12px;
  background: var(--pm-app-surface);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
.cmt:hover { border-color: color-mix(in srgb, var(--pm-text) 22%, transparent); }
.cmt.is-active {
  z-index: 2;
  border-color: var(--cmt-active);
  background: color-mix(in srgb, var(--cmt-active) 5%, var(--pm-app-surface));
  box-shadow: 0 0 0 1px var(--cmt-active);
}
/* Zeiger von der aktiven Kachel ins Panel darunter. */
.cmt.is-active::after {
  content: '';
  position: absolute;
  bottom: calc(-1 * var(--cmt-gap) - 8px);
  left: 50%;
  width: 14px;
  height: 14px;
  margin-left: -7px;
  border-top: 1px solid var(--cmt-panel-border);
  border-left: 1px solid var(--cmt-panel-border);
  background: var(--cmt-panel-bg);
  transform: rotate(45deg);
  animation: cmt-notch 220ms ease 140ms both;
}
@keyframes cmt-notch { from { opacity: 0; transform: translateY(6px) rotate(45deg); } }
.cmt--add { display: flex; border: 0; background: transparent; }
.cmt--add:hover { border: 0; }
.cmt--add > :deep(*) { flex: 1; }
.cmt--add :deep(.corr-placeholder) { width: 100%; min-height: 64px; height: 100%; justify-content: center; border-radius: 12px; }

.cmt__face {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  height: 100%;
  padding: 14px 14px 12px;
  border: 0;
  border-radius: inherit;
  background: transparent;
  color: var(--pm-text);
  font: inherit;
  text-align: start;
  cursor: pointer;
}
.cmt__face:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -2px; }
.cmt.is-empty .cmt__face { cursor: default; }

.cmt__stack { position: relative; display: block; height: 96px; margin-bottom: 8px; }
.cmt__sheet {
  position: absolute;
  top: 4px;
  left: 50%;
  width: 62px;
  height: 84px;
  margin-left: -31px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--pm-text) 16%, transparent);
  border-radius: 3px;
  background: #fff;
  transition: transform 360ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.cmt__sheet { display: grid; place-items: center; }
.cmt__sheet img { position: absolute; inset: 0; width: 100%; height: 100%; background: #fff; object-fit: cover; object-position: top; }
.cmt__sheet-icon { color: color-mix(in srgb, #000 22%, #fff); }
/* Ein einzelnes Deckblatt steht gerade und fächert nicht auf. */
.cmt__sheet--0:not(:only-child) { transform: rotate(-5deg); }
.cmt__sheet--2 { transform: rotate(5deg); }
.cmt__sheet:last-child { box-shadow: 0 1px 3px color-mix(in srgb, #000 18%, transparent); }
.cmt:hover .cmt__sheet--0:not(:only-child), .cmt__face:focus-visible .cmt__sheet--0:not(:only-child) { transform: translateX(-34px) rotate(-10deg); }
.cmt:hover .cmt__sheet--2, .cmt__face:focus-visible .cmt__sheet--2 { transform: translateX(34px) rotate(10deg); }
.cmt:hover .cmt__sheet--1:not(:last-child) { transform: translateY(-3px); }

/* Feste Zeilen: Name (1), Umfang (1) – jede Kachel gleich gegliedert. */
.cmt__name { display: flex; align-items: center; gap: 6px; min-width: 0; font-size: 0.9rem; font-weight: 650; line-height: 1.3; }
.cmt__kind { flex: none; margin-top: 1px; color: var(--cmt-tone); }
.cmt--direct .cmt__kind { color: var(--pm-muted); }
.cmt__name-text { min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.cmt__meta { overflow: hidden; color: var(--pm-muted); font-size: 0.78rem; white-space: nowrap; text-overflow: ellipsis; }

.cmt__remove {
  position: absolute;
  top: 8px;
  right: 8px;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted);
  opacity: 0;
  cursor: pointer;
  transition: opacity 120ms ease;
}
.cmt:hover .cmt__remove, .cmt__remove:focus-visible { opacity: 1; }
.cmt__remove:hover:not(:disabled) { background: var(--pm-list-hover); color: var(--pm-text); }
.cmt__remove:focus-visible { outline: 2px solid var(--pm-accent); }
@media (hover: none) { .cmt__remove { opacity: 1; } }

/* Panel unter der Kachelzeile. */
.cmt-panel {
  grid-column: 1 / -1;
  min-width: 0;
  margin-bottom: var(--cmt-gap);
  border: 1px solid var(--cmt-panel-border);
  border-radius: 12px;
  background: var(--cmt-panel-bg);
}
.cmt-panel__body { padding: 12px 14px 14px; animation: cmt-in 260ms ease both; }
@keyframes cmt-in { from { opacity: 0; } }
.cmt__head { display: flex; align-items: center; gap: 10px; }
.cmt__dot { flex: none; width: 10px; height: 10px; border-radius: 3px; background: var(--cmt-tone); }
.cmt__head-copy { flex: 1; min-width: 0; }
.cmt__title { margin: 0; color: var(--pm-text); font-size: 0.95rem; font-weight: 650; overflow-wrap: anywhere; }
.cmt__link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-accent-text);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}
.cmt__link:hover { background: var(--pm-list-hover); }
.cmt__icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--pm-list-divider);
  border-radius: 8px;
  background: var(--pm-app-surface);
  color: var(--pm-text);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.cmt__icon-btn { width: 32px; height: 32px; }
.cmt__icon-btn:hover { background: var(--pm-list-hover); }
.cmt__icon-btn:focus-visible, .cmt__link:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }

.cmt-panel__docs { margin-top: 12px; }

@media (prefers-reduced-motion: reduce) {
  .cmt-panel__body, .cmt__sheet, .cmt.is-active::after {
    animation: none !important;
    transition: none !important;
  }
}
:global(.pm-no-animations) .cmt-panel__body,
:global(.pm-no-animations) .cmt__sheet,
:global(.pm-no-animations) .cmt.is-active::after { animation: none !important; transition: none !important; }
</style>
