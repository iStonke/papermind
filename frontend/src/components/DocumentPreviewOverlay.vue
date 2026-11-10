<!--
  DocumentPreviewOverlay — große Vorschau eines Dokuments als Overlay nur über
  dem rechten Bereich (nächster `.corr-profile`), weitgehend rahmenlos: eine
  milchige Fläche, darauf das Dokument wie ein Blatt mit Stapel darunter.

  Beim Öffnen wird das Blatt von rechts in den sichtbaren Bereich „geworfen“;
  beim Blättern zwischen Dokumenten (←/→) wechselt es ohne Animation. Blättern im PDF
  wie in der Dokumentvorschau; ←/→ wechseln zwischen den Dokumenten der Liste,
  Esc oder ein Klick daneben schließt. Öffnet nichts im Dokumentbereich.
-->
<template>
  <span ref="anchorEl" class="doc-overlay__anchor" hidden />
  <Teleport :to="containerEl || 'body'" :disabled="!containerEl">
    <Transition name="doc-overlay">
      <div
        v-if="current"
        ref="layerEl"
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
        <!-- Der Wurf startet sofort beim Klick; bis die erste Seite gerendert ist,
             fliegt eine weiße Platzhalterseite mit, danach blendet das PDF ein. -->
        <div
          :key="current.document_id"
          class="doc-overlay__stage"
          :class="{ 'is-throwing': throwIn, 'is-ready': pageReady }"
          @click.self="close"
        >
          <div class="doc-overlay__placeholder">
            <div class="doc-overlay__placeholder-box">
              <div class="doc-overlay__sheet">
                <!-- Ladeanimation im PaperMind-Stil: Blatt-Symbol, dessen Zeilen sich
                     schreiben, darunter pulsierende Punkte. -->
                <div v-if="!pageReady" class="doc-overlay__loader" role="status" aria-label="Dokument wird geladen">
                  <span class="doc-overlay__halo" aria-hidden="true" />
                  <svg class="doc-overlay__mark" viewBox="0 0 64 64" aria-hidden="true">
                    <path class="doc-overlay__mark-page" d="M17 8h22l11 11v37H17z" />
                    <path class="doc-overlay__mark-fold" d="M39 8v11h11" />
                    <line class="doc-overlay__mark-line" x1="24" y1="30" x2="43" y2="30" />
                    <line class="doc-overlay__mark-line" x1="24" y1="38" x2="43" y2="38" />
                    <line class="doc-overlay__mark-line" x1="24" y1="46" x2="35" y2="46" />
                  </svg>
                  <span class="doc-overlay__dots" aria-hidden="true"><i /><i /><i /></span>
                </div>
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
  /** Bereich, den das Overlay überdeckt (nächster Vorfahr mit diesem Selektor). */
  container: { type: String, default: '.corr-profile' },
});
const emit = defineEmits(['update:modelValue', 'closed']);

const anchorEl = ref(null);
const containerEl = ref(null);
const layerEl = ref(null);
const previewRef = ref(null);
const closeRef = ref(null);
// Geworfen wird nur beim Öffnen; beim Blättern wechselt das Dokument ohne Animation.
const throwIn = ref(true);
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
  throwIn.value = false;
  pageReady.value = false;
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
watch(() => props.modelValue, async (id, previous) => {
  if (!id) return;
  if (previous) return;
  pageReady.value = false;
  throwIn.value = true;
  staticMotion.value = motionOff();
  await nextTick();
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
  background: color-mix(in srgb, var(--pm-app-surface) 82%, transparent);
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

/* Luft rundum, damit das Blatt wie auf einem Tisch liegt und der Stapel
   darunter sichtbar bleibt. Abgeschnitten wird erst am Rand des Bereichs. */
.doc-overlay__stage { position: relative; flex: 1; min-height: 0; padding: 4px clamp(24px, 6%, 56px) 30px; }
.doc-overlay__pdf { display: block; width: 100%; height: 100%; }
.doc-overlay__stage :deep(.pdf-preview),
.doc-overlay__stage :deep(.pdf-preview__viewer) { overflow: visible; background: transparent !important; }
.doc-overlay__stage :deep(.pdf-preview__pages) { padding: 6px 18px 18px 4px; }

/* Das Blatt mit zwei Bögen darunter – ein kleiner Stapel. */
.doc-overlay .doc-overlay__stage :deep(.pdf-preview .pdf-preview__page) {
  overflow: visible;
  box-shadow:
    0 18px 40px rgb(0 0 0 / 0.22),
    0 2px 6px rgb(0 0 0 / 0.14),
    7px 6px 0 -1px #f3f3f1,
    7px 6px 0 0 rgb(0 0 0 / 0.1),
    14px 11px 0 -1px #e9e9e6,
    14px 11px 0 0 rgb(0 0 0 / 0.09);
}

/* „Reinwerfen“ mit dezentem Bounce: der Stapel fliegt sofort beim Klick schräg
   herein, schießt leicht über die Mitte hinaus und pendelt kurz aus. */
.doc-overlay__stage.is-throwing {
  --dir: 1;
  animation: doc-throw 820ms both;
  transform-origin: 50% 90%;
}
@keyframes doc-throw {
  0% {
    transform: translate(calc(var(--dir) * 110%), -6%) rotate(calc(var(--dir) * 12deg)) scale(1.03);
    animation-timing-function: cubic-bezier(0.15, 0.75, 0.3, 1);
  }
  45% {
    transform: translate(calc(var(--dir) * -2.2%), 0.4%) rotate(calc(var(--dir) * -1.8deg));
    animation-timing-function: cubic-bezier(0.4, 0, 0.5, 1);
  }
  68% {
    transform: translate(calc(var(--dir) * 0.8%), 0) rotate(calc(var(--dir) * 0.6deg));
    animation-timing-function: cubic-bezier(0.4, 0, 0.5, 1);
  }
  86% {
    transform: translate(calc(var(--dir) * -0.25%), 0) rotate(calc(var(--dir) * -0.2deg));
  }
  100% { transform: none; }
}

/* Weiße Platzhalterseite (mit demselben Stapel), bis das PDF da ist. */
.doc-overlay__placeholder {
  position: absolute;
  inset: 4px clamp(24px, 6%, 56px) 30px;
  display: flex;
  justify-content: center;
  padding: 6px 18px 18px 4px;
  pointer-events: none;
  transition: opacity 220ms ease;
}
/* Platzhalter so groß wie eine eingepasste A4-Seite (Breite oder Höhe begrenzt). */
.doc-overlay__placeholder-box { flex: 1; display: flex; justify-content: center; min-width: 0; container-type: size; }
.doc-overlay__sheet {
  width: min(100cqw, calc(100cqh / 1.414));
  height: min(100cqh, calc(100cqw * 1.414));
  border-radius: 3px;
  background: #fff;
  box-shadow:
    0 18px 40px rgb(0 0 0 / 0.22),
    0 2px 6px rgb(0 0 0 / 0.14),
    7px 6px 0 -1px #f3f3f1,
    7px 6px 0 0 rgb(0 0 0 / 0.1),
    14px 11px 0 -1px #e9e9e6,
    14px 11px 0 0 rgb(0 0 0 / 0.09);
}
.doc-overlay__stage.is-ready .doc-overlay__placeholder { opacity: 0; }

/* Ladeanimation auf der weißen Seite (Papier ist immer hell → feste Farben). */
.doc-overlay__sheet { position: relative; container-type: size; }
.doc-overlay__loader {
  --loader-accent: #0b7a83;
  --loader-line: #cfe3e6;
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(10px, 3cqh, 18px);
  animation: loader-in 360ms ease 180ms both;
}
@keyframes loader-in { from { opacity: 0; transform: translateY(6px); } }
.doc-overlay__halo {
  position: absolute;
  top: 50%;
  left: 50%;
  width: clamp(150px, 46cqw, 260px);
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--loader-accent) 14%, transparent), transparent 68%);
  transform: translate(-50%, -62%);
  animation: loader-halo 2.4s ease-in-out infinite;
}
@keyframes loader-halo {
  0%, 100% { opacity: 0.55; transform: translate(-50%, -62%) scale(0.92); }
  50% { opacity: 1; transform: translate(-50%, -62%) scale(1.06); }
}
.doc-overlay__mark {
  position: relative;
  width: clamp(72px, 24cqw, 132px);
  height: auto;
  overflow: visible;
  animation: loader-float 2.4s ease-in-out infinite;
}
@keyframes loader-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
.doc-overlay__mark-page { fill: #f6fbfb; stroke: var(--loader-accent); stroke-width: 2.6; stroke-linejoin: round; }
.doc-overlay__mark-fold { fill: #ddeef0; stroke: var(--loader-accent); stroke-width: 2.6; stroke-linejoin: round; }
/* Zeilen „schreiben“ sich nacheinander, halten kurz und setzen neu an. */
.doc-overlay__mark-line {
  stroke: var(--loader-accent);
  stroke-width: 3.6;
  stroke-linecap: round;
  stroke-dasharray: 20;
  stroke-dashoffset: 20;
  animation: loader-write 2.4s cubic-bezier(0.45, 0, 0.25, 1) infinite;
}
.doc-overlay__mark-line:nth-of-type(2) { animation-delay: 0.22s; }
.doc-overlay__mark-line:nth-of-type(3) { animation-delay: 0.44s; }
@keyframes loader-write {
  0% { stroke-dashoffset: 20; opacity: 1; }
  35%, 72% { stroke-dashoffset: 0; opacity: 1; }
  90%, 100% { stroke-dashoffset: 0; opacity: 0; }
}
.doc-overlay__dots { position: relative; display: flex; gap: 7px; }
.doc-overlay__dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--loader-accent);
  opacity: 0.35;
  animation: loader-dot 1.4s ease-in-out infinite;
}
.doc-overlay__dots i:nth-child(2) { animation-delay: 0.18s; }
.doc-overlay__dots i:nth-child(3) { animation-delay: 0.36s; }
@keyframes loader-dot { 0%, 100% { opacity: 0.3; transform: scale(0.85); } 40% { opacity: 1; transform: scale(1.1); } }

/* Eigene Ladeanzeige der Vorschau ausblenden – der Platzhalter übernimmt. */
.doc-overlay__stage :deep(.pdf-preview__state--loading) { visibility: hidden; }

.doc-overlay-enter-active, .doc-overlay-leave-active { transition: opacity 200ms ease; }
.doc-overlay-enter-from, .doc-overlay-leave-to { opacity: 0; }

@media (prefers-reduced-motion: reduce) {
  .doc-overlay__stage.is-throwing { animation: none; }
  .doc-overlay__loader, .doc-overlay__halo, .doc-overlay__mark, .doc-overlay__dots i { animation: none; }
  .doc-overlay__mark-line { animation: none; stroke-dashoffset: 0; }
  .doc-overlay-enter-active, .doc-overlay-leave-active { transition: none; }
}
.doc-overlay.is-static .doc-overlay__stage.is-throwing { animation: none; }
.doc-overlay.is-static .doc-overlay__loader,
.doc-overlay.is-static .doc-overlay__halo,
.doc-overlay.is-static .doc-overlay__mark,
.doc-overlay.is-static .doc-overlay__dots i { animation: none; }
.doc-overlay.is-static .doc-overlay__mark-line { animation: none; stroke-dashoffset: 0; }
.doc-overlay.is-static.doc-overlay-enter-active,
.doc-overlay.is-static.doc-overlay-leave-active { transition: none; }
</style>
