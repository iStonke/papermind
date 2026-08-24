<!--
  DocumentNotesSection — zeigt im Dokument-Detailbereich die Notizen, die mit
  diesem Dokument verknüpft sind (body_json.attrs.linkedDocument.id), plus einen
  Knopf, um eine neue, bereits verknüpfte Notiz anzulegen. Öffnen/Anlegen laufen
  über Events an DocumentsWorkspace, das in den Notizbereich wechselt.
-->
<template>
  <section class="doc-notes" aria-label="Notizen zu diesem Dokument">
    <header class="doc-notes__header">
      <div class="doc-notes__heading">
        <v-icon size="16">mdi-note-outline</v-icon>
        <span>Verknüpfte Notizen</span>
        <span v-if="notes.length" class="doc-notes__count">{{ notes.length }}</span>
      </div>
      <v-btn
        class="doc-notes__new"
        size="small"
        variant="text"
        color="primary"
        :loading="creating"
        @click="emit('new-note')"
      >
        <v-icon size="16" class="mr-1">mdi-plus</v-icon>
        Neue Notiz
      </v-btn>
    </header>

    <div v-if="loading" class="doc-notes__state">
      <v-progress-circular indeterminate color="primary" size="18" width="2" />
    </div>

    <div v-else-if="!notes.length" class="doc-notes__empty">
      Noch keine Notizen zu diesem Dokument.
    </div>

    <ul v-else class="doc-notes__list">
      <li v-for="note in notes" :key="note.id">
        <button type="button" class="doc-notes__item" @click="emit('open-note', note.id)">
          <span class="doc-notes__item-title" :class="{ 'is-untitled': !note.title?.trim() }">
            {{ note.title?.trim() || 'Ohne Titel' }}
          </span>
          <span v-if="note.preview?.trim()" class="doc-notes__item-snippet">{{ note.preview }}</span>
          <span class="doc-notes__item-date">{{ formatDate(note.updated_at) }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue';
import { listNotes } from '../../api/notes.js';

const props = defineProps({
  documentId: { type: String, default: null },
  creating: { type: Boolean, default: false },
  // Erhöht sich, wenn der Aufrufer die Liste neu laden möchte (z. B. nach Anlegen).
  reloadKey: { type: Number, default: 0 },
});

const emit = defineEmits(['open-note', 'new-note']);

const notes = ref([]);
const loading = ref(false);
let requestId = 0;

async function load() {
  if (!props.documentId) { notes.value = []; return; }
  const rev = ++requestId;
  loading.value = true;
  try {
    const res = await listNotes({ documentId: props.documentId });
    if (rev !== requestId) return;
    notes.value = res.items || [];
  } catch {
    if (rev !== requestId) return;
    notes.value = [];
  } finally {
    if (rev === requestId) loading.value = false;
  }
}

watch(() => props.documentId, load, { immediate: true });
watch(() => props.reloadKey, load);

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return `heute ${date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}`;
  }
  return date.toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'short',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  });
}
</script>

<style scoped>
.doc-notes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-notes__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.doc-notes__heading {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--pm-muted, #748084);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.doc-notes__count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 100px;
  background: var(--pm-viewer-surface, #eef2f4);
  color: var(--pm-muted, #535e62);
  font-size: 0.7rem;
  text-align: center;
}

.doc-notes__new.v-btn {
  text-transform: none;
  letter-spacing: 0;
}

.doc-notes__state {
  display: flex;
  justify-content: center;
  padding: 10px 0;
}

.doc-notes__empty {
  padding: 4px 2px 8px;
  color: var(--pm-muted, #748084);
  font-size: 0.82rem;
}

.doc-notes__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.doc-notes__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px;
  background: var(--pm-app-surface, #fff);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: border-color 120ms ease, background 120ms ease;
}

.doc-notes__item:hover {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.04));
}

.doc-notes__item-title {
  color: var(--pm-text, #0e181b);
  font-size: 0.88rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc-notes__item-title.is-untitled { color: var(--pm-muted); font-style: italic; font-weight: 500; }

.doc-notes__item-snippet {
  color: var(--pm-muted, #535e62);
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-notes__item-date {
  color: var(--pm-muted, #535e62);
  font-size: 0.7rem;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
}

@media (prefers-reduced-motion: reduce) {
  .doc-notes__item { transition: none; }
}
</style>
