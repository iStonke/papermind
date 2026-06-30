<template>
  <v-dialog :model-value="modelValue" max-width="520" @update:model-value="$emit('update:modelValue', $event)">
    <v-card class="link-dialog">
      <div class="link-dialog__head">
        <v-icon size="20" class="link-dialog__head-icon">mdi-link-variant</v-icon>
        <span class="link-dialog__title">Mit Dokument verknüpfen</span>
        <button class="link-dialog__close" aria-label="Schließen" @click="close">
          <v-icon size="20">mdi-close</v-icon>
        </button>
      </div>

      <div v-if="quote" class="link-dialog__quote">„{{ quote }}"</div>

      <v-text-field
        ref="searchField"
        v-model="query"
        placeholder="Dokument suchen…"
        variant="outlined"
        density="comfortable"
        hide-details
        clearable
        autofocus
        prepend-inner-icon="mdi-magnify"
        class="link-dialog__search"
        @update:model-value="onQueryChange"
      />

      <div class="link-dialog__results">
        <div v-if="isLoading" class="link-dialog__hint">Suche läuft…</div>
        <div v-else-if="!results.length" class="link-dialog__hint">Keine Treffer.</div>
        <button
          v-for="doc in results"
          :key="doc.id"
          class="link-dialog__item"
          @click="choose(doc)"
        >
          <v-icon size="18" class="link-dialog__item-icon">mdi-file-document-outline</v-icon>
          <span class="link-dialog__item-text">
            <span class="link-dialog__item-title">{{ titleOf(doc) }}</span>
            <span v-if="doc.correspondent_name" class="link-dialog__item-sub">{{ doc.correspondent_name }}</span>
          </span>
        </button>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch } from 'vue';

import { listDocuments } from '../api/documents.js';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  currentDocumentId: { type: String, default: '' },
  quote: { type: String, default: '' },
});

const emit = defineEmits(['update:modelValue', 'select']);

const query = ref('');
const results = ref([]);
const isLoading = ref(false);
let searchSeq = 0;
let debounceTimer = 0;

function titleOf(doc) {
  const raw = doc.display_name || doc.original_filename || 'Dokument';
  return raw.replace(/\.pdf$/i, '');
}

async function runSearch() {
  const seq = ++searchSeq;
  isLoading.value = true;
  try {
    const params = new URLSearchParams({ limit: '20' });
    const term = query.value?.trim();
    if (term) params.set('q', term);
    const payload = await listDocuments(params.toString());
    if (seq !== searchSeq) return; // veraltete Antwort verwerfen
    results.value = (payload?.items ?? []).filter((d) => d.id !== props.currentDocumentId);
  } catch (error) {
    if (seq === searchSeq) results.value = [];
    console.error('Dokumentsuche fehlgeschlagen:', error);
  } finally {
    if (seq === searchSeq) isLoading.value = false;
  }
}

function onQueryChange() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(runSearch, 250);
}

function choose(doc) {
  emit('select', { id: doc.id, title: titleOf(doc) });
  close();
}

function close() {
  emit('update:modelValue', false);
}

// Beim Öffnen: Suchfeld zurücksetzen und letzte Dokumente laden.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    query.value = '';
    results.value = [];
    runSearch();
  },
);
</script>

<style scoped>
.link-dialog {
  padding: 16px;
  border-radius: 14px;
}
.link-dialog__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.link-dialog__head-icon {
  color: rgb(var(--v-theme-primary));
}
.link-dialog__title {
  flex: 1 1 auto;
  font-size: 1rem;
  font-weight: 500;
}
.link-dialog__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: rgb(var(--v-theme-on-surface) / 0.6);
  cursor: pointer;
}
.link-dialog__close:hover {
  background: rgb(var(--v-theme-on-surface) / 0.08);
}
.link-dialog__quote {
  margin-bottom: 12px;
  padding: 8px 10px;
  border-left: 3px solid rgb(var(--v-theme-primary) / 0.5);
  border-radius: 0 6px 6px 0;
  background: rgb(var(--v-theme-on-surface) / 0.04);
  font-size: 0.82rem;
  color: rgb(var(--v-theme-on-surface) / 0.75);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.link-dialog__search {
  margin-bottom: 8px;
}
.link-dialog__results {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.link-dialog__hint {
  padding: 14px 4px;
  font-size: 0.85rem;
  color: rgb(var(--v-theme-on-surface) / 0.5);
  text-align: center;
}
.link-dialog__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 120ms ease;
}
.link-dialog__item:hover {
  background: rgb(var(--v-theme-primary) / 0.1);
}
.link-dialog__item-icon {
  flex: 0 0 auto;
  color: rgb(var(--v-theme-on-surface) / 0.5);
}
.link-dialog__item-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.link-dialog__item-title {
  font-size: 0.88rem;
  color: rgb(var(--v-theme-on-surface));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.link-dialog__item-sub {
  font-size: 0.74rem;
  color: rgb(var(--v-theme-on-surface) / 0.55);
}
</style>
