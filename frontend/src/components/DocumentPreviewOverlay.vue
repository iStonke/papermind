<!--
  DocumentPreviewOverlay — große Vorschau eines Dokuments als Overlay nur über
  dem rechten Bereich (nächster `.corr-profile`), weitgehend rahmenlos: eine
  milchige Fläche mit einer scrollbaren PDF-Vorschau.

  Beim Öffnen wächst das Blatt aus dem angeklickten Vorschaubild.
  ←/→ wechseln ohne Animation zwischen den Dokumenten der Liste,
  Esc oder ein Klick daneben schließt. Öffnet nichts im Dokumentbereich.
-->
<template>
  <span ref="anchorEl" class="doc-overlay__anchor" hidden />
  <Teleport :to="containerEl || 'body'" :disabled="!containerEl">
    <Transition name="doc-overlay">
      <div
        v-if="current"
        class="doc-overlay"
        :class="{ 'doc-overlay--detached': !containerEl, 'is-static': staticMotion }"
        role="region"
        :aria-label="`Vorschau: ${titleOf(current)}`"
        tabindex="-1"
        @keydown="onKeydown"
        @click.self="close"
      >
        <header class="doc-overlay__bar">
          <div class="doc-overlay__caption">
            <h2 class="doc-overlay__title" :title="titleOf(current)">{{ titleOf(current) }}</h2>
            <p class="doc-overlay__meta">
              <span v-if="current.document_type">{{ current.document_type }}</span>
              <span v-if="pageLabel">{{ pageLabel }}</span>
              <span v-if="dateLabel">{{ dateLabel }}</span>
              <span v-if="items.length > 1" class="doc-overlay__position">{{ index + 1 }} / {{ items.length }}</span>
            </p>
          </div>
          <div class="doc-overlay__nav">
            <button
              v-if="items.length > 1"
              type="button"
              class="doc-overlay__btn"
              :disabled="index <= 0"
              aria-label="Vorheriges Dokument"
              title="Vorheriges Dokument (←)"
              @click="step(-1)"
            ><v-icon size="20" aria-hidden="true">mdi-chevron-left</v-icon></button>
            <button
              v-if="items.length > 1"
              type="button"
              class="doc-overlay__btn"
              :disabled="index >= items.length - 1"
              aria-label="Nächstes Dokument"
              title="Nächstes Dokument (→)"
              @click="step(1)"
            ><v-icon size="20" aria-hidden="true">mdi-chevron-right</v-icon></button>
            <button
              ref="closeRef"
              type="button"
              class="doc-overlay__btn"
              aria-label="Vorschau schließen"
              title="Schließen (Esc)"
              @click="close"
            ><v-icon size="20" aria-hidden="true">mdi-close</v-icon></button>
          </div>
        </header>
        <div
          :key="current.document_id"
          class="doc-overlay__stage"
          :class="{ 'is-opening': opening, 'is-ready': pageReady && !opening }"
          :aria-busy="!pageReady"
          @click.self="close"
        >
          <div class="doc-overlay__placeholder">
            <div class="doc-overlay__placeholder-box">
              <div
                ref="sheetEl"
                class="doc-overlay__sheet"
                :style="opening?.style"
                @animationend.self="opening = null"
              >
                <img v-if="opening?.image" class="doc-overlay__thumbnail" :src="opening.image" alt="">
              </div>
            </div>
          </div>
          <PdfPreview
            ref="previewRef"
            class="doc-overlay__pdf"
            :src="documentFileUrl(current.document_id, 'searchable')"
            fit-page
            @first-page="pageReady = true"
            @failed="pageReady = true"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue';
import { documentFileUrl } from '../api/documents.js';
import { formatDocumentDateInputFromIso } from '../utils/dates.js';
import { motionOff } from '../utils/expandPanel.js';

const PdfPreview = defineAsyncComponent(() => import('./PdfPreview.vue'));

const props = defineProps({
  /** Geöffnetes Dokument (null = zu). */
  modelValue: { type: String, default: null },
  /** Dokumente, zwischen denen ←/→ wechseln ({ document_id, title, … }). */
  items: { type: Array, default: () => [] },
  /** Thumbnail des Auslösers für die Öffnungsanimation. */
  thumbnail: { type: Object, default: null },
  /** Bereich, den das Overlay überdeckt (nächster Vorfahr mit diesem Selektor). */
  container: { type: String, default: '.corr-profile' },
});
const emit = defineEmits(['update:modelValue', 'closed']);

const anchorEl = ref(null);
const containerEl = ref(null);
const sheetEl = ref(null);
const previewRef = ref(null);
const closeRef = ref(null);
const opening = ref(null);
const pageReady = ref(false);
const staticMotion = ref(false);

onMounted(() => {
  containerEl.value = anchorEl.value?.closest?.(props.container) || null;
});

const current = computed(() => props.items.find(item => item.document_id === props.modelValue) || null);
const index = computed(() => props.items.findIndex(item => item.document_id === props.modelValue));
const pageLabel = computed(() => {
  const count = previewRef.value?.pageCount;
  if (!count) return '';
  return count === 1 ? '1 Seite' : `${count} Seiten`;
});
const dateLabel = computed(() => formatDocumentDateInputFromIso(current.value?.document_date));

function titleOf(item) {
  return item?.title || item?.original_filename || 'Ohne Titel';
}

function close() {
  const id = props.modelValue;
  if (!id) return;
  emit('update:modelValue', null);
  emit('closed', id);
}

function step(delta) {
  const next = props.items[index.value + delta];
  if (!next) return;
  emit('update:modelValue', next.document_id);
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    close();
    return;
  }
  // In Eingabefeldern (z. B. PDF-Suche) bleiben die Pfeiltasten beim Feld.
  if (event.target?.closest?.('input, textarea, [contenteditable="true"]')) return;
  if (event.key === 'ArrowLeft') { event.preventDefault(); step(-1); }
  else if (event.key === 'ArrowRight') { event.preventDefault(); step(1); }
}

// Verschwindet das Dokument aus der Liste (z. B. zugeordnet), schließt die Vorschau.
watch(() => props.items, () => {
  if (props.modelValue && !current.value) close();
});
watch(() => props.modelValue, async (id, previous, onCleanup) => {
  opening.value = null;
  pageReady.value = false;
  if (!id || previous) return;
  staticMotion.value = motionOff();
  const image = props.thumbnail?.querySelector('img');
  const loadedImage = image?.complete && image.naturalWidth && !image.hidden ? image : null;
  const source = staticMotion.value ? null : (loadedImage || props.thumbnail)?.getBoundingClientRect();
  let cancelled = false;
  onCleanup(() => { cancelled = true; });
  await nextTick();
  if (cancelled) return;
  const target = sheetEl.value?.getBoundingClientRect();
  if (source?.width && source.height && target?.width && target.height) {
    opening.value = {
      image: loadedImage?.currentSrc || loadedImage?.src,
      style: {
        '--open-x': `${source.left - target.left}px`,
        '--open-y': `${source.top - target.top}px`,
        '--open-scale-x': source.width / target.width,
        '--open-scale-y': source.height / target.height,
      },
    };
  }
  closeRef.value?.focus?.({ preventScroll: true });
});
</script>

<style scoped>
/* Milchige Fläche nur über dem rechten Bereich; kein Rahmen, keine Karte. */
.doc-overlay {
  position: absolute;
  inset: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: color-mix(in srgb, var(--pm-app-surface) 70%, transparent);
  -webkit-backdrop-filter: blur(12px) saturate(120%);
  backdrop-filter: blur(12px) saturate(120%);
  outline: none;
  /* PdfPreview ohne eigene Bühne: das Blatt liegt direkt auf der Fläche. */
  --pm-viewer-surface: transparent;
  --pm-pdf-stage-bg: transparent;
}
.doc-overlay--detached { position: fixed; }

.doc-overlay__bar {
  position: relative;
  z-index: 2;
  flex: none;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 18px 6px 22px;
}
.doc-overlay__caption { flex: 1; min-width: 0; }
.doc-overlay__title {
  margin: 0;
  overflow: hidden;
  color: var(--pm-text);
  font-size: 0.98rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-overlay__meta { display: flex; flex-wrap: wrap; margin: 2px 0 0; color: var(--pm-muted); font-size: 0.78rem; }
.doc-overlay__meta span + span::before { content: '·'; margin: 0 8px; color: color-mix(in srgb, var(--pm-muted) 70%, transparent); }
.doc-overlay__position { font-variant-numeric: tabular-nums; }
.doc-overlay__nav { display: flex; flex: none; gap: 6px; }
.doc-overlay__btn {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: color-mix(in srgb, var(--pm-text) 7%, transparent);
  color: var(--pm-text);
  cursor: pointer;
  transition: background-color 140ms ease, opacity 140ms ease;
}
.doc-overlay__btn:hover:not(:disabled) { background: color-mix(in srgb, var(--pm-text) 14%, transparent); }
.doc-overlay__btn:disabled { opacity: 0.35; cursor: default; }
.doc-overlay__btn:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }

.doc-overlay__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  padding: 4px clamp(24px, 6%, 56px) 12px;
}
.doc-overlay__stage :deep(.pdf-preview__pages) {
  align-items: safe center;
  overscroll-behavior: contain;
}
.doc-overlay__stage.is-opening .doc-overlay__pdf { visibility: hidden; }
.doc-overlay__stage.is-opening .doc-overlay__sheet {
  transform-origin: top left;
  animation: doc-grow 320ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
@keyframes doc-grow {
  from {
    transform: translate(var(--open-x), var(--open-y)) scale(var(--open-scale-x), var(--open-scale-y));
  }
  to { transform: none; }
}

.doc-overlay__thumbnail {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  animation: doc-thumbnail-fade 320ms ease both;
}
@keyframes doc-thumbnail-fade {
  0%, 40% { opacity: 1; }
  100% { opacity: 0; }
}

.doc-overlay__placeholder {
  position: absolute;
  inset: 4px clamp(24px, 6%, 56px) 12px;
  display: flex;
  justify-content: center;
  padding: 0 20px 16px;
  pointer-events: none;
  transition: opacity 220ms ease;
}
/* Platzhalter so groß wie eine eingepasste A4-Seite (Breite oder Höhe begrenzt). */
.doc-overlay__placeholder-box { flex: 1; display: flex; justify-content: center; min-width: 0; container-type: size; }
.doc-overlay__sheet {
  position: relative;
  width: min(100cqw, calc(100cqh / 1.414));
  height: min(100cqh, calc(100cqw * 1.414));
  border-radius: 3px;
  background: #fff;
  box-shadow: 0 10px 28px rgb(0 0 0 / 0.12), 0 1px 3px rgb(0 0 0 / 0.1);
}
.doc-overlay__stage.is-ready .doc-overlay__placeholder { opacity: 0; }

/* Eigene Ladeanzeige der Vorschau ausblenden – der Platzhalter übernimmt. */
.doc-overlay__stage :deep(.pdf-preview__state--loading) { visibility: hidden; }

.doc-overlay-enter-active, .doc-overlay-leave-active { transition: opacity 200ms ease; }
.doc-overlay-enter-from, .doc-overlay-leave-to { opacity: 0; }

@media (prefers-reduced-motion: reduce) {
  .doc-overlay-enter-active, .doc-overlay-leave-active { transition: none; }
}
.doc-overlay.is-static.doc-overlay-enter-active,
.doc-overlay.is-static.doc-overlay-leave-active { transition: none; }
</style>
