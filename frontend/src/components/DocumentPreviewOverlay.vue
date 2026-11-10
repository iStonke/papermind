<!--
  DocumentPreviewOverlay — große Vorschau eines Dokuments als Overlay über der
  aktuellen Seite (z. B. aus den Karten von „Ohne Korrespondent“ / „Genauer
  zuordnen“). Blättern im PDF wie in der Dokumentvorschau; ←/→ wechseln
  zwischen den Dokumenten der Liste, Esc schließt. Öffnet nichts im
  Dokumentbereich.
-->
<template>
  <v-dialog
    :model-value="Boolean(current)"
    attach=".papermind-app"
    :max-width="1100"
    width="calc(100vw - 48px)"
    scrim="rgba(8, 12, 14, 0.62)"
    content-class="doc-overlay__content"
    @update:model-value="(open) => { if (!open) close(); }"
  >
    <section
      v-if="current"
      class="doc-overlay"
      role="region"
      :aria-label="`Vorschau: ${titleOf(current)}`"
      @keydown="onKeydown"
    >
      <header class="doc-overlay__head">
        <div class="doc-overlay__heading">
          <h2 class="doc-overlay__title" :title="titleOf(current)">{{ titleOf(current) }}</h2>
          <p class="doc-overlay__meta">
            <span v-if="current.document_type">{{ current.document_type }}</span>
            <span v-if="pageLabel">{{ pageLabel }}</span>
            <span v-if="dateLabel">{{ dateLabel }}</span>
            <span v-if="items.length > 1" class="doc-overlay__position">{{ index + 1 }} / {{ items.length }}</span>
          </p>
        </div>
        <div class="doc-overlay__nav">
          <v-btn
            v-if="items.length > 1"
            class="pm-header-icon-btn doc-overlay__btn"
            variant="outlined"
            icon="mdi-chevron-left"
            :disabled="index <= 0"
            aria-label="Vorheriges Dokument"
            title="Vorheriges Dokument (←)"
            @click="step(-1)"
          />
          <v-btn
            v-if="items.length > 1"
            class="pm-header-icon-btn doc-overlay__btn"
            variant="outlined"
            icon="mdi-chevron-right"
            :disabled="index >= items.length - 1"
            aria-label="Nächstes Dokument"
            title="Nächstes Dokument (→)"
            @click="step(1)"
          />
          <v-btn
            ref="closeRef"
            class="pm-header-icon-btn doc-overlay__btn"
            variant="outlined"
            icon="mdi-close"
            aria-label="Vorschau schließen"
            title="Schließen (Esc)"
            @click="close"
          />
        </div>
      </header>
      <div class="doc-overlay__viewer">
        <PdfPreview
          ref="previewRef"
          :key="current.document_id"
          class="doc-overlay__pdf"
          :src="documentFileUrl(current.document_id, 'searchable')"
          fit-page
        />
      </div>
    </section>
  </v-dialog>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, ref, watch } from 'vue';
import { documentFileUrl } from '../api/documents.js';
import { formatDocumentDateInputFromIso } from '../utils/dates.js';

const PdfPreview = defineAsyncComponent(() => import('./PdfPreview.vue'));

const props = defineProps({
  /** Geöffnetes Dokument (null = zu). */
  modelValue: { type: String, default: null },
  /** Dokumente, zwischen denen ←/→ wechseln ({ document_id, title, … }). */
  items: { type: Array, default: () => [] },
});
const emit = defineEmits(['update:modelValue', 'closed']);

const previewRef = ref(null);
const closeRef = ref(null);
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
  emit('update:modelValue', null);
  emit('closed', id);
}

function step(delta) {
  const next = props.items[index.value + delta];
  if (next) emit('update:modelValue', next.document_id);
}

function onKeydown(event) {
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
  if (!id || previous) return;
  await nextTick();
  closeRef.value?.$el?.focus?.({ preventScroll: true });
});
</script>

<style scoped>
.doc-overlay {
  display: flex;
  flex-direction: column;
  height: min(92vh, 1100px);
  overflow: hidden;
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
  background: var(--pm-app-surface);
  box-shadow: var(--pm-shadow);
}
.doc-overlay__head {
  flex: none;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--pm-divider);
}
.doc-overlay__heading { flex: 1; min-width: 0; }
.doc-overlay__title {
  margin: 0;
  overflow: hidden;
  color: var(--pm-text);
  font-size: 1.02rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-overlay__meta { display: flex; flex-wrap: wrap; gap: 2px 0; margin: 2px 0 0; color: var(--pm-muted); font-size: 0.8rem; }
.doc-overlay__meta span + span::before { content: '·'; margin: 0 8px; color: color-mix(in srgb, var(--pm-muted) 70%, transparent); }
.doc-overlay__position { font-variant-numeric: tabular-nums; }
.doc-overlay__nav { display: flex; flex: none; align-items: center; gap: 8px; }
.doc-overlay__btn.v-btn { border-color: var(--pm-divider); color: var(--pm-muted); }
.doc-overlay__viewer { flex: 1; min-height: 0; }
.doc-overlay__pdf { display: block; width: 100%; height: 100%; }
</style>
