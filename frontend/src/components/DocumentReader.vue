<template>
  <Teleport to="body">
    <Transition name="reader" appear @after-leave="$emit('close')">
    <div
      v-if="!leaving"
      class="doc-reader"
      role="dialog"
      aria-modal="true"
      :aria-label="`Lesemodus: ${title || 'Dokument'}`"
    >
      <!-- Kopfleiste -->
      <header class="doc-reader__bar">
        <div class="doc-reader__bar-left">
          <button class="doc-reader__icon-btn" aria-label="Lesemodus schließen" title="Schließen (Esc)" @click="requestClose">
            <v-icon size="20">mdi-arrow-collapse</v-icon>
          </button>
          <div class="doc-reader__title-wrap">
            <div class="doc-reader__title" :title="title">{{ title || 'Dokument' }}</div>
            <span v-if="pageTotal" class="doc-reader__page-chip">{{ currentPage }} / {{ pageTotal }}</span>
          </div>
        </div>
        <div class="doc-reader__bar-actions">
          <div class="doc-reader__view-toggle" role="group" aria-label="Ansicht">
            <button
              class="doc-reader__icon-btn"
              :class="{ 'doc-reader__icon-btn--active': showThumbs }"
              :aria-pressed="showThumbs"
              aria-label="Miniaturen umschalten"
              title="Miniaturen"
              @click="showThumbs = !showThumbs"
            >
              <v-icon size="20">mdi-view-grid-outline</v-icon>
            </button>
            <button
              class="doc-reader__icon-btn"
              :class="{ 'doc-reader__icon-btn--active': showNotes }"
              :aria-pressed="showNotes"
              aria-label="Notizen umschalten"
              title="Notizen"
              @click="showNotes = !showNotes"
            >
              <v-icon size="20">mdi-comment-text-outline</v-icon>
              <span v-if="annotations.length" class="doc-reader__badge">{{ annotations.length }}</span>
            </button>
          </div>
        </div>
      </header>

      <div class="doc-reader__body">
        <!-- Miniatur-Leiste -->
        <aside v-show="showThumbs" ref="railEl" class="doc-reader__rail" aria-label="Seitenminiaturen">
          <button
            v-for="page in pageTotal"
            :key="page"
            :ref="el => setThumbRef(el, page)"
            class="doc-reader__thumb"
            :class="{ 'doc-reader__thumb--active': page === currentPage }"
            :data-page="page"
            :aria-label="`Zu Seite ${page} springen`"
            :aria-current="page === currentPage ? 'true' : undefined"
            @click="goToPage(page)"
          >
            <canvas :ref="el => setCanvasRef(el, page)" class="doc-reader__thumb-canvas" />
            <span class="doc-reader__thumb-num">{{ page }}</span>
          </button>
        </aside>

        <!-- Hauptansicht: dieselbe PdfPreview, voller Platz -->
        <main class="doc-reader__main">
          <PdfPreview
            ref="previewRef"
            :src="src"
            :target-page="targetPage"
            :annotatable="true"
            :annotations="annotations"
            @loaded="onPreviewLoaded"
            @create-annotation="$emit('create-annotation', $event)"
            @request-link="$emit('request-link', $event)"
          />
        </main>

        <!-- Notizen-Leiste -->
        <aside v-show="showNotes" class="doc-reader__notes" aria-label="Notizen und Markierungen">
          <div class="doc-reader__notes-head">
            <span>Notizen</span>
            <span class="doc-reader__notes-count">{{ annotations.length }}</span>
          </div>

          <div v-if="!annotations.length" class="doc-reader__notes-empty">
            Keine Notizen
          </div>

          <TransitionGroup v-else tag="ul" name="note" class="doc-reader__notes-list">
            <li
              v-for="annot in sortedAnnotations"
              :key="annot.id"
              class="doc-reader__note"
              :style="{ '--note-color': annot.color || '#FAC775' }"
            >
              <button class="doc-reader__note-jump" :aria-label="`Zu Seite ${annot.page} springen`" @click="goToPage(annot.page)">
                <span class="doc-reader__note-main">
                  <span class="doc-reader__note-dot" aria-hidden="true" />
                  <span class="doc-reader__note-quote">{{ annot.quote || '(ohne Text)' }}</span>
                </span>
                <span class="doc-reader__note-page">S. {{ annot.page }}</span>
              </button>

              <button
                v-if="annot.kind === 'link'"
                class="doc-reader__note-link"
                :aria-label="`Verknüpftes Dokument öffnen: ${annot.target_document_title || ''}`"
                @click="$emit('open-link', annot)"
              >
                <v-icon size="14">mdi-link-variant</v-icon>
                <span class="doc-reader__note-link-title">{{ annot.target_document_title || 'Verknüpftes Dokument' }}</span>
                <v-icon size="14" class="doc-reader__note-link-go">mdi-chevron-right</v-icon>
              </button>

              <div v-if="editingId === annot.id" class="doc-reader__note-edit">
                <textarea
                  ref="editFieldEl"
                  v-model="editingText"
                  class="doc-reader__note-input"
                  rows="2"
                  placeholder="Kommentar…"
                  @keydown.enter.exact.prevent="commitEdit(annot)"
                  @keydown.esc.prevent="cancelEdit"
                />
                <div class="doc-reader__note-edit-actions">
                  <button class="doc-reader__note-btn" @click="commitEdit(annot)">Speichern</button>
                  <button class="doc-reader__note-btn doc-reader__note-btn--ghost" @click="cancelEdit">Abbrechen</button>
                </div>
              </div>
              <button
                v-else
                class="doc-reader__note-comment"
                :class="{ 'doc-reader__note-comment--empty': !annot.comment }"
                @click="startEdit(annot)"
              >
                {{ annot.comment || 'Kommentar hinzufügen…' }}
              </button>

              <button class="doc-reader__note-delete" aria-label="Markierung löschen" title="Löschen" @click="$emit('delete-annotation', annot.id)">
                <v-icon size="16">mdi-trash-can-outline</v-icon>
              </button>
            </li>
          </TransitionGroup>
        </aside>
      </div>
    </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

import PdfPreview from './PdfPreview.vue';

const props = defineProps({
  src:         { type: String, default: '' },
  targetPage:  { type: Number, default: null },
  annotations: { type: Array, default: () => [] },
  title:       { type: String, default: '' },
});

const emit = defineEmits(['close', 'create-annotation', 'delete-annotation', 'update-annotation', 'request-link', 'open-link']);

const previewRef = ref(null);
const railEl = ref(null);
const editFieldEl = ref(null);

const showThumbs = ref(true);
const showNotes = ref(true);
const pageTotal = ref(0);
const leaving = ref(false); // steuert die Leave-Transition vor dem Schließen

const editingId = ref(null);
const editingText = ref('');

// Aktuelle Seite aus der (exposeten) PdfPreview – reaktiv für Rail-Hervorhebung.
const currentPage = computed(() => previewRef.value?.currentPage || 1);

const sortedAnnotations = computed(() =>
  [...props.annotations].sort((a, b) => (a.page - b.page) || (a.created_at < b.created_at ? -1 : 1)),
);

// ── Miniaturen ────────────────────────────────────────────────────────────────
const thumbEls = new Map();   // page → button-Element
const canvasEls = new Map();  // page → canvas-Element
const renderedThumbs = new Set();
let thumbObserver = null;

function setThumbRef(el, page) {
  if (el) thumbEls.set(page, el);
  else thumbEls.delete(page);
}
function setCanvasRef(el, page) {
  if (el) canvasEls.set(page, el);
  else canvasEls.delete(page);
}

function setupThumbObserver() {
  thumbObserver?.disconnect();
  if (!railEl.value) return;
  thumbObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const page = Number(entry.target.dataset.page);
        renderThumb(page);
      }
    },
    { root: railEl.value, rootMargin: '300px 0px', threshold: 0 },
  );
  for (const el of thumbEls.values()) thumbObserver.observe(el);
}

async function renderThumb(page) {
  if (renderedThumbs.has(page)) return;
  const canvas = canvasEls.get(page);
  const api = previewRef.value;
  if (!canvas || !api?.renderThumbnail) return;
  renderedThumbs.add(page);
  await api.renderThumbnail(page, canvas);
  canvas.style.opacity = '1'; // sanftes Einblenden nach dem Rendern
}

async function onPreviewLoaded() {
  pageTotal.value = previewRef.value?.pageCount || 0;
  renderedThumbs.clear();
  await nextTick();
  setupThumbObserver();
}

function goToPage(page) {
  previewRef.value?.goToPage(page);
  // Aktive Miniatur in den sichtbaren Bereich rollen.
  nextTick(() => thumbEls.get(page)?.scrollIntoView({ block: 'nearest' }));
}

// ── Notiz-Kommentar bearbeiten ──────────────────────────────────────────────
function startEdit(annot) {
  editingId.value = annot.id;
  editingText.value = annot.comment || '';
  nextTick(() => {
    const field = Array.isArray(editFieldEl.value) ? editFieldEl.value[0] : editFieldEl.value;
    field?.focus();
  });
}
function cancelEdit() {
  editingId.value = null;
  editingText.value = '';
}
function commitEdit(annot) {
  const next = editingText.value.trim();
  if (next !== (annot.comment || '')) {
    emit('update-annotation', annot.id, { comment: next || null });
  }
  cancelEdit();
}

function requestClose() {
  // Löst die Leave-Transition aus; @after-leave emittiert dann 'close'.
  if (!leaving.value) leaving.value = true;
}

function onKeydown(event) {
  if (event.key === 'Escape' && editingId.value === null) {
    requestClose();
  }
}

onMounted(() => {
  document.documentElement.style.overflow = 'hidden';
  window.addEventListener('keydown', onKeydown);
});
onBeforeUnmount(() => {
  thumbObserver?.disconnect();
  document.documentElement.style.overflow = '';
  window.removeEventListener('keydown', onKeydown);
});
</script>

<style scoped>
/* Sanfter Ein-/Ausblend-Übergang beim Screenwechsel in/aus dem Lesemodus. */
.reader-enter-active,
.reader-leave-active {
  transition: opacity 200ms ease, transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.reader-enter-from,
.reader-leave-to {
  opacity: 0;
  transform: scale(0.985) translateY(10px);
}
@media (prefers-reduced-motion: reduce) {
  .reader-enter-active,
  .reader-leave-active,
  .note-enter-active,
  .note-leave-active,
  .note-move,
  .doc-reader__thumb-canvas {
    transition: none;
  }
}

.doc-reader {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  --reader-panel-bg: rgb(12 18 30);
  --reader-panel-bg-soft: rgb(15 22 36);
  --reader-divider: rgb(255 255 255 / 0.08);
  --reader-muted: rgb(226 232 240 / 0.62);
  --reader-text: rgb(241 245 249);
  background: rgb(8 13 23);
  color: var(--reader-text);
}

.doc-reader__bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 54px;
  padding: 8px 18px;
  border-bottom: 1px solid var(--reader-divider);
  background: rgb(10 16 27 / 0.96);
}

.doc-reader__bar-left {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.doc-reader__title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.doc-reader__title {
  min-width: 0;
  font-size: 0.95rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--reader-text);
}

.doc-reader__page-chip {
  flex: 0 0 auto;
  padding: 2px 8px;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 999px;
  color: var(--reader-muted);
  background: rgb(255 255 255 / 0.04);
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
}

.doc-reader__bar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.doc-reader__view-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 3px;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 10px;
  background: rgb(255 255 255 / 0.04);
}

.doc-reader__icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: rgb(226 232 240 / 0.78);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
}
.doc-reader__icon-btn:hover {
  background: rgb(255 255 255 / 0.08);
  color: var(--reader-text);
}
.doc-reader__icon-btn--active {
  background: rgb(var(--v-theme-primary) / 0.18);
  border-color: rgb(var(--v-theme-primary) / 0.38);
  color: rgb(120 231 255);
}
.doc-reader__badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  font-size: 0.65rem;
  line-height: 16px;
  text-align: center;
}

.doc-reader__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  background: rgb(8 13 23);
}

/* ── Miniatur-Leiste ─────────────────────────────────────────────────────── */
.doc-reader__rail {
  flex: 0 0 auto;
  width: 138px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px 8px 18px;
  border-right: 1px solid var(--reader-divider);
  background: var(--reader-panel-bg);
}

.doc-reader__thumb {
  position: relative;
  display: block;
  padding: 4px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  line-height: 0;
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
}
.doc-reader__thumb:hover {
  background: rgb(255 255 255 / 0.05);
  border-color: rgb(255 255 255 / 0.08);
}
.doc-reader__thumb--active {
  background: rgb(var(--v-theme-primary) / 0.12);
  border-color: rgb(var(--v-theme-primary) / 0.72);
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-primary));
}
.doc-reader__thumb-canvas {
  display: block;
  width: 104px;
  min-height: 136px;
  border-radius: 4px;
  background: #fff;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.22);
  opacity: 0;
  transition: opacity 220ms ease;
}
.doc-reader__thumb-num {
  position: absolute;
  bottom: 8px;
  right: 8px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgb(15 23 42 / 0.72);
  color: #fff;
  font-size: 0.7rem;
  line-height: 18px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

/* ── Hauptansicht ─────────────────────────────────────────────────────────── */
.doc-reader__main {
  flex: 1 1 auto;
  min-width: 0;
  position: relative;
  background:
    linear-gradient(90deg, rgb(8 13 23) 0, rgb(12 18 30) 16%, rgb(12 18 30) 84%, rgb(8 13 23) 100%);
}

.doc-reader__main :deep(.pdf-preview) {
  background: transparent;
}

.doc-reader__main :deep(.pdf-preview__viewer) {
  background: transparent;
}

.doc-reader__main :deep(.pdf-preview__toolbar) {
  top: 12px;
  left: 50%;
  right: auto;
  transform: translateX(-50%);
  width: auto;
  min-width: 330px;
  min-height: 34px;
  justify-content: center;
  gap: 10px;
  padding: 4px 8px;
  border: 1px solid rgb(255 255 255 / 0.1);
  border-radius: 999px;
  background: rgb(15 23 42 / 0.72);
  box-shadow: 0 8px 22px rgb(0 0 0 / 0.24);
}

.doc-reader__main :deep(.pdf-preview__left-controls),
.doc-reader__main :deep(.pdf-preview__zoom-controls) {
  position: static;
}

.doc-reader__main :deep(.pdf-preview__page-info) {
  color: rgb(var(--v-theme-on-surface) / 0.85);
}

.doc-reader__main :deep(.pdf-preview__pages) {
  padding: 0 24px 32px;
  gap: 22px;
}

.doc-reader__main :deep(.pdf-preview__page) {
  border-radius: 4px;
}

.doc-reader__main :deep(.pdf-preview__page:has(.pdf-preview__page-inner:not(:empty))) {
  box-shadow: 0 14px 34px rgb(0 0 0 / 0.3);
}

/* ── Notizen-Leiste ───────────────────────────────────────────────────────── */
.doc-reader__notes {
  flex: 0 0 auto;
  width: 310px;
  overflow-y: auto;
  border-left: 1px solid var(--reader-divider);
  background: var(--reader-panel-bg);
  display: flex;
  flex-direction: column;
}
.doc-reader__notes-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 18px 18px 12px;
  font-size: 0.9rem;
  font-weight: 650;
  color: var(--reader-text);
}
.doc-reader__notes-count {
  min-width: 24px;
  height: 22px;
  padding: 0 8px;
  border-radius: 11px;
  background: rgb(255 255 255 / 0.07);
  color: var(--reader-muted);
  font-size: 0.72rem;
  line-height: 22px;
  text-align: center;
}
.doc-reader__notes-empty {
  margin: 4px 18px;
  padding: 14px 12px;
  border: 1px dashed rgb(255 255 255 / 0.12);
  border-radius: 8px;
  font-size: 0.82rem;
  color: var(--reader-muted);
  line-height: 1.5;
}
.doc-reader__notes-list {
  list-style: none;
  margin: 0;
  padding: 4px 12px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Notizen: ein-/ausblenden + sanftes Nachrücken beim Umsortieren/Löschen. */
.note-enter-active,
.note-leave-active {
  transition: opacity 220ms ease, transform 220ms ease;
}
.note-enter-from,
.note-leave-to {
  opacity: 0;
  transform: translateX(14px);
}
.note-leave-active {
  position: absolute;
  left: 10px;
  right: 10px;
}
.note-move {
  transition: transform 240ms ease;
}
.doc-reader__note {
  position: relative;
  padding: 10px 38px 10px 12px;
  border: 1px solid rgb(255 255 255 / 0.08);
  border-left: 3px solid var(--note-color);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.035);
  transition: background 120ms ease, border-color 120ms ease;
}
.doc-reader__note:hover {
  background: rgb(255 255 255 / 0.055);
  border-color: rgb(255 255 255 / 0.12);
}
.doc-reader__note-jump {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.doc-reader__note-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.doc-reader__note-dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--note-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--note-color) 24%, transparent);
}
.doc-reader__note-quote {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.82rem;
  color: rgb(241 245 249 / 0.9);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.doc-reader__note-page {
  flex: 0 0 auto;
  padding: 2px 7px;
  border: 1px solid rgb(255 255 255 / 0.08);
  border-radius: 999px;
  background: rgb(255 255 255 / 0.04);
  font-size: 0.7rem;
  color: var(--reader-muted);
  font-variant-numeric: tabular-nums;
}
.doc-reader__note-link {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  margin-top: 6px;
  padding: 5px 8px;
  border: 1px solid rgb(24 95 165 / 0.3);
  border-radius: 7px;
  background: rgb(24 95 165 / 0.08);
  color: rgb(24 95 165 / 0.95);
  cursor: pointer;
  transition: background 120ms ease;
}
.doc-reader__note-link:hover {
  background: rgb(24 95 165 / 0.16);
}
.doc-reader__note-link-title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc-reader__note-link-go {
  flex: 0 0 auto;
  opacity: 0.7;
}
.doc-reader__note-comment {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 0.78rem;
  color: rgb(226 232 240 / 0.68);
  line-height: 1.4;
  cursor: text;
}
.doc-reader__note-comment--empty {
  color: rgb(226 232 240 / 0.38);
  font-style: italic;
}
.doc-reader__note-input {
  width: 100%;
  margin-top: 6px;
  padding: 6px 8px;
  border: 1px solid rgb(255 255 255 / 0.16);
  border-radius: 6px;
  background: rgb(8 13 23);
  color: var(--reader-text);
  font: inherit;
  font-size: 0.8rem;
  resize: vertical;
}
.doc-reader__note-edit-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.doc-reader__note-btn {
  padding: 3px 10px;
  border: 1px solid rgb(var(--v-theme-primary) / 0.5);
  border-radius: 6px;
  background: rgb(var(--v-theme-primary) / 0.12);
  color: rgb(var(--v-theme-primary));
  font-size: 0.75rem;
  cursor: pointer;
}
.doc-reader__note-btn--ghost {
  border-color: rgb(var(--v-theme-on-surface) / 0.16);
  background: transparent;
  color: rgb(var(--v-theme-on-surface) / 0.6);
}
.doc-reader__note-delete {
  position: absolute;
  top: 7px;
  right: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgb(226 232 240 / 0.42);
  cursor: pointer;
  opacity: 0;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
}
.doc-reader__note:hover .doc-reader__note-delete,
.doc-reader__note-delete:focus-visible {
  opacity: 1;
}
.doc-reader__note-delete:hover {
  background: rgb(var(--v-theme-error) / 0.12);
  color: rgb(var(--v-theme-error));
}
</style>
