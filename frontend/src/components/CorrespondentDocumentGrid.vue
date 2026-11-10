<!--
  CorrespondentDocumentGrid — Dokumente eines Korrespondenten als Kachelraster.
  Ein Klick auf eine Kachel öffnet direkt unter ihrer Zeile die Vorschau
  (Vorschaubild oder „Seiten blättern“ mit PdfPreview); die Kacheln bleiben
  stehen, das Panel wächst in der Höhe auf. Nichts führt in den Dokumentbereich.

  Genutzt im Profil von Organisation/Person und in den aufgeklappten
  Mitglieder-Kacheln einer Sammlung (CollectionMemberTiles). Das Laden der
  Dokumente bleibt beim Aufrufer; hier wird nur dargestellt.
-->
<template>
  <div ref="rootEl" class="cdg" :class="[`cdg--${size}`, `cdg--${layout}`]">
    <p v-if="failed && !documents.length" class="cdg__state" role="alert">
      Dokumente konnten nicht geladen werden.
      <button type="button" class="cdg__link" @click="emit('retry')">Erneut versuchen</button>
    </p>
    <p v-else-if="!loading && !documents.length" class="cdg__state">{{ emptyText }}</p>

    <ul
      v-if="documents.length || loading"
      ref="gridEl"
      class="cdg__grid"
      :class="{ 'cdg__grid--peek': layout === 'row' && documents.length > 3 }"
      :aria-label="label"
      :aria-busy="loading || loadingMore || undefined"
      :tabindex="layout === 'row' && documents.length > 1 ? 0 : undefined"
      @keydown.esc="onEscape"
      @scroll.passive="loadMoreNearEnd"
    >
      <template v-if="loading && !documents.length">
        <li v-for="n in skeletonCount" :key="`sk-${n}`" class="cdg-doc cdg-doc--skeleton" aria-hidden="true">
          <span class="cdg-doc__face">
            <span class="cdg-doc__page" />
            <span class="cdg-doc__title"><span class="cdg-sk" /></span>
            <span class="cdg-doc__date"><span class="cdg-sk cdg-sk--short" /></span>
          </span>
        </li>
      </template>
      <template v-for="(doc, index) in documents" :key="doc.id">
        <li
          class="cdg-doc"
          :class="{ 'is-active': openDocId === doc.id }"
          :style="{ '--i': index % 12 }"
          :data-doc="doc.id"
        >
          <button
            type="button"
            class="cdg-doc__face"
            :aria-expanded="openDocId === doc.id"
            :aria-controls="openDocId === doc.id ? panelId : undefined"
            :aria-label="`${titleOf(doc)} ${openDocId === doc.id ? 'verkleinern' : 'vergrößern'}`"
            @click="toggleDoc(doc.id)"
          >
            <span class="cdg-doc__page" aria-hidden="true">
              <v-icon :size="size === 'regular' ? 28 : 24">mdi-file-document-outline</v-icon>
              <img :key="doc.updated_at" :src="thumbnail(doc)" alt="" loading="lazy" decoding="async" @error="$event.target.hidden = true">
            </span>
            <span class="cdg-doc__title" :title="titleOf(doc)">{{ titleOf(doc) }}</span>
            <span v-if="showType && doc.document_type" class="cdg-doc__type">{{ doc.document_type }}</span>
            <span class="cdg-doc__date">{{ formatDate(doc.document_date || doc.created_at) }}</span>
          </button>
        </li>

        <Transition :css="false" @enter="onPanelEnter" @leave="animatePanelLeave">
          <li
            v-if="layout === 'grid' && openDoc && panelAfter === index"
            :id="panelId"
            :key="`panel-${index}`"
            class="cdg-panel"
            role="region"
            :aria-label="titleOf(openDoc)"
          >
            <CorrespondentDocumentDetail
              :key="openDoc.id"
              :doc="openDoc"
              :title="titleOf(openDoc)"
              :date="formatDate(openDoc.document_date || openDoc.created_at)"
              :thumbnail="thumbnail(openDoc)"
              :browsing="browsing"
              :owner-name="ownerName"
              @toggle-browsing="toggleBrowsing"
              @close="closeDoc({ focus: true })"
            />
          </li>
        </Transition>
      </template>
    </ul>

    <!-- Zeile: Vorschau unter der ganzen Reihe (die Reihe scrollt waagerecht). -->
    <Transition :css="false" @enter="onPanelEnter" @leave="animatePanelLeave">
      <div
        v-if="layout === 'row' && openDoc"
        :id="panelId"
        class="cdg-panel cdg-panel--row"
        role="region"
        :aria-label="titleOf(openDoc)"
        @keydown.esc="onEscape"
      >
        <CorrespondentDocumentDetail
          :key="openDoc.id"
          :doc="openDoc"
          :title="titleOf(openDoc)"
          :date="formatDate(openDoc.document_date || openDoc.created_at)"
          :thumbnail="thumbnail(openDoc)"
          :browsing="browsing"
          :owner-name="ownerName"
          @toggle-browsing="toggleBrowsing"
          @close="closeDoc({ focus: true })"
        />
      </div>
    </Transition>

    <div v-if="layout === 'grid' && documents.length && documents.length < total && !loadMoreFailed" class="cdg__more">
      <button type="button" class="cdg__btn" :disabled="loadingMore" @click="emit('load-more')">
        {{ loadingMore ? 'Lädt …' : `Weitere ${total - documents.length} laden` }}
      </button>
    </div>
    <p v-if="loadMoreFailed" class="cdg__state cdg__state--center" role="status">
      Weitere Dokumente konnten nicht geladen werden.
      <button type="button" class="cdg__link" :disabled="loadingMore" @click="emit('load-more')">Erneut versuchen</button>
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import CorrespondentDocumentDetail from './CorrespondentDocumentDetail.vue';
import { documentThumbnailUrl } from '../api/documents.js';
import {
  animatePanelEnter,
  animatePanelLeave,
  observeColumns,
  revealPanel,
  rowEnd,
  tweenHeight,
} from '../utils/expandPanel.js';

const props = defineProps({
  documents: { type: Array, required: true },
  /** Gesamtzahl (für „Weitere N laden“). */
  total: { type: Number, default: 0 },
  loading: Boolean,
  loadingMore: Boolean,
  failed: Boolean,
  loadMoreFailed: Boolean,
  skeletonCount: { type: Number, default: 6 },
  /** Name des Korrespondenten der Seite; „Von“ erscheint nur bei Abweichung. */
  ownerName: { type: String, default: '' },
  label: { type: String, default: 'Dokumente' },
  emptyText: { type: String, default: 'Keine Dokumente.' },
  showType: Boolean,
  /** compact = in Sammlungs-Panels, regular = eigenständig im Profil. */
  size: { type: String, default: 'regular', validator: (v) => ['compact', 'regular'].includes(v) },
  /** grid = mehrzeiliges Raster, row = eine waagerecht scrollende Reihe (lädt am Ende nach). */
  layout: { type: String, default: 'grid', validator: (v) => ['grid', 'row'].includes(v) },
});
const emit = defineEmits(['load-more', 'retry']);

const panelId = `cdg-panel-${Math.random().toString(36).slice(2, 8)}`;
const gridEl = ref(null);
const cols = ref(1);
const openDocId = ref(null);
const browsing = ref(false);

const openDoc = computed(() => props.documents.find((d) => d.id === openDocId.value) || null);
const panelAfter = computed(() => rowEnd(
  props.documents.findIndex((d) => d.id === openDocId.value),
  cols.value,
  props.documents.length,
));

let stopObserving = null;
watch(gridEl, (el) => {
  stopObserving?.();
  stopObserving = el ? observeColumns(el, (count) => { cols.value = count; }) : null;
}, { flush: 'post' });
onBeforeUnmount(() => stopObserving?.());

// Verschwindet das geöffnete Dokument aus der Liste, Vorschau schließen.
watch(() => props.documents, (list) => {
  if (openDocId.value && !list.some((d) => d.id === openDocId.value)) {
    openDocId.value = null;
    browsing.value = false;
  }
});

const rootEl = ref(null);
function livePanel() {
  return rootEl.value?.querySelector('.cdg-panel:not(.is-leaving)') || null;
}
function reveal() {
  revealPanel(gridEl.value?.querySelector(':scope > .cdg-doc.is-active'), livePanel());
}

/** Zeile: kurz vor dem Ende der Reihe die nächste Seite anfordern. */
function loadMoreNearEnd({ currentTarget: list }) {
  if (props.layout !== 'row' || props.loadingMore || props.loadMoreFailed) return;
  if (props.documents.length >= props.total) return;
  if (list.scrollWidth - list.clientWidth - list.scrollLeft <= list.clientWidth / 2) emit('load-more');
}
function onPanelEnter(el, done) {
  animatePanelEnter(el, done, reveal);
}
function docFace(id) {
  return gridEl.value?.querySelector(`.cdg-doc[data-doc="${CSS.escape(id)}"] .cdg-doc__face`) || null;
}

async function openDocument(id) {
  const index = props.documents.findIndex((d) => d.id === id);
  const sameRow = openDocId.value
    && (props.layout === 'row' || rowEnd(index, cols.value, props.documents.length) === panelAfter.value);
  const apply = () => {
    openDocId.value = id;
    browsing.value = false;
  };
  if (sameRow) {
    await tweenHeight(livePanel(), apply);
    reveal();
  } else {
    apply();
  }
}

function closeDoc({ focus = false } = {}) {
  const id = openDocId.value;
  if (!id) return;
  const hadFocus = livePanel()?.contains(document.activeElement);
  openDocId.value = null;
  browsing.value = false;
  if (focus || hadFocus) docFace(id)?.focus?.({ preventScroll: true });
}

function toggleDoc(id) {
  if (openDocId.value === id) closeDoc();
  else openDocument(id);
}

async function toggleBrowsing() {
  await tweenHeight(livePanel(), () => { browsing.value = !browsing.value; });
  reveal();
}

function onEscape(event) {
  if (!openDocId.value) return;
  closeDoc({ focus: true });
  event.stopPropagation();
}

function thumbnail(doc) {
  const base = documentThumbnailUrl(doc.id);
  return doc.updated_at ? `${base}${base.includes('?') ? '&' : '?'}thumb_v=${encodeURIComponent(doc.updated_at)}` : base;
}

function titleOf(doc) {
  return String(doc.display_name || doc.original_filename || '').trim() || 'Ohne Titel';
}

function formatDate(iso) {
  if (!iso) return '–';
  const d = new Date(String(iso).length <= 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? '–' : d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

defineExpose({ closeDoc, openDocId });
</script>

<style scoped>
.cdg {
  --cdg-gap: 10px;
  --cdg-min: 150px;
  --cdg-page: 150px;
  --cdg-active: var(--pm-accent);
  --cdg-card-bg: var(--pm-app-surface-raised, var(--pm-app-surface));
  --cdg-detail-bg: var(--cdg-card-bg);
  --cdg-detail-border: var(--pm-list-divider);
  container-type: inline-size;
}
.cdg--regular { --cdg-gap: 12px; --cdg-min: 220px; --cdg-page: 210px; }

.cdg__state { margin: 12px 0 0; color: var(--pm-muted); font-size: 0.84rem; }
.cdg__state:first-child { margin-top: 0; }
.cdg__state--center { text-align: center; }
.cdg__link {
  padding: 2px 4px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-accent-text);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.cdg__link:hover { background: var(--pm-list-hover); }
.cdg__link:focus-visible, .cdg__btn:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }
.cdg__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--pm-list-divider);
  border-radius: 8px;
  background: transparent;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.cdg__btn:hover:not(:disabled) { background: var(--pm-list-hover); }
.cdg__btn:disabled { cursor: default; opacity: 0.6; }
.cdg__more { display: flex; justify-content: center; margin-top: 12px; }

/* Zeilenabstand über margin-bottom, damit das Panel ihn mitanimieren kann. */
.cdg__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, var(--cdg-min)), 1fr));
  column-gap: var(--cdg-gap);
  row-gap: 0;
  margin: 0 0 calc(-1 * var(--cdg-gap));
  padding: 0;
  list-style: none;
}
.cdg-doc {
  position: relative;
  min-width: 0;
  margin-bottom: var(--cdg-gap);
  animation: cdg-in-up 280ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
  animation-delay: calc(var(--i, 0) * 25ms);
}
@keyframes cdg-in-up { from { opacity: 0; transform: translateY(4px); } }
.cdg-doc.is-active { z-index: 2; }
/* Zeiger von der aktiven Kachel in die Vorschau darunter. */
.cdg-doc.is-active::after {
  content: '';
  position: absolute;
  bottom: calc(-1 * var(--cdg-gap) - 8px);
  left: 50%;
  width: 14px;
  height: 14px;
  margin-left: -7px;
  border-top: 1px solid var(--cdg-detail-border);
  border-left: 1px solid var(--cdg-detail-border);
  background: var(--cdg-detail-bg);
  transform: rotate(45deg);
  animation: cdg-notch 220ms ease 140ms both;
}
@keyframes cdg-notch { from { opacity: 0; transform: translateY(6px) rotate(45deg); } }
.cdg-doc--skeleton { animation: cdg-pulse 1.1s ease-in-out infinite alternate; }
@keyframes cdg-pulse { from { opacity: 1; } to { opacity: 0.55; } }

.cdg-doc__face {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  height: 100%;
  padding: 8px;
  border: 1px solid var(--pm-list-divider);
  border-radius: 10px;
  background: var(--cdg-card-bg);
  color: var(--pm-text);
  font: inherit;
  text-align: start;
  cursor: pointer;
  transition: border-color 140ms ease, transform 160ms ease, box-shadow 160ms ease;
}
.cdg-doc__face:hover { border-color: color-mix(in srgb, var(--pm-text) 24%, transparent); transform: translateY(-2px); }
.cdg-doc.is-active .cdg-doc__face {
  border-color: var(--cdg-active);
  background: color-mix(in srgb, var(--cdg-active) 5%, var(--cdg-card-bg));
  box-shadow: 0 0 0 1px var(--cdg-active);
  transform: none;
}
.cdg-doc__face:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -2px; }
.cdg-doc--skeleton .cdg-doc__face { cursor: default; }
.cdg-doc__page {
  position: relative;
  display: grid;
  place-items: center;
  align-self: stretch;
  height: var(--cdg-page);
  margin-bottom: 6px;
  border-radius: 6px;
  color: color-mix(in srgb, var(--pm-muted) 70%, transparent);
}
/* Kein Kasten hinter dem Vorschaubild: das Blatt selbst liegt mit Kante und Schatten auf der Karte. */
.cdg-doc__page img {
  position: absolute;
  inset: 0;
  max-width: 100%;
  max-height: 100%;
  margin: auto;
  border: 1px solid color-mix(in srgb, var(--pm-text) 10%, transparent);
  border-radius: 2px;
  background: #fff;
  box-shadow: 0 1px 3px color-mix(in srgb, #000 14%, transparent);
}
.cdg-doc--skeleton .cdg-doc__page { background: var(--pm-list-hover); }
.cdg-doc__title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  align-self: stretch;
  min-height: 2.6em;
  overflow: hidden;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.cdg--regular .cdg-doc__title { font-size: 0.84rem; }
.cdg-doc__type {
  max-width: 100%;
  margin: 2px 0;
  padding: 1px 8px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent) 12%, transparent);
  color: var(--pm-accent-text);
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.cdg-doc__date { margin-top: auto; color: var(--pm-muted); font-size: 0.74rem; }
.cdg-sk { display: inline-block; width: 85%; height: 0.8em; border-radius: 4px; background: var(--pm-list-hover); vertical-align: middle; }
.cdg-sk--short { width: 55%; }

.cdg-panel {
  grid-column: 1 / -1;
  min-width: 0;
  margin-bottom: var(--cdg-gap);
}
/* Zeile (Organisation/Person): eine waagerecht scrollende Reihe, drei Karten
   sichtbar; ab vier lugt die nächste an. Die Vorschau öffnet unter der Reihe. */
.cdg--row { --cdg-page: 168px; }
.cdg--row .cdg__grid {
  --cdg-peek: 0px;
  grid-template-columns: none;
  grid-auto-flow: column;
  grid-auto-columns: min(100%, max(166px, calc((100% - 2 * var(--cdg-gap) - var(--cdg-peek)) / 3)));
  margin: 0;
  padding: 3px 0 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--pm-outline) transparent;
}
.cdg--row .cdg__grid--peek { --cdg-peek: 30px; }
.cdg--row .cdg__grid:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.cdg--row .cdg-doc { margin-bottom: 0; }
.cdg--row .cdg-doc.is-active::after { display: none; }
.cdg-panel--row { margin-top: 4px; }

@media (prefers-reduced-motion: reduce) {
  .cdg-doc, .cdg-doc.is-active::after { animation: none !important; }
  .cdg-doc__face { transition: none; }
}
:global(.pm-no-animations) .cdg-doc,
:global(.pm-no-animations) .cdg-doc.is-active::after { animation: none !important; }
:global(.pm-no-animations) .cdg-doc__face { transition: none; }
</style>
