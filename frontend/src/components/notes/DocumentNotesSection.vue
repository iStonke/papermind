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
        <span class="doc-notes__heading-icon" aria-hidden="true">
          <v-icon size="17">mdi-note-multiple-outline</v-icon>
        </span>
        <span>Verknüpfte Notizen</span>
        <span class="doc-notes__count">{{ notes.length }}</span>
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
        Notiz hinzufügen
      </v-btn>
    </header>

    <div v-if="loading" class="doc-notes__state">
      <v-progress-circular indeterminate color="primary" size="18" width="2" />
    </div>

    <div v-else-if="!notes.length" class="doc-notes__empty">
      <span class="doc-notes__empty-icon" aria-hidden="true">
        <v-icon size="22">mdi-note-plus-outline</v-icon>
      </span>
      <strong>Noch keine verknüpften Notizen</strong>
      <span>Erstelle eine Notiz direkt zu diesem Dokument.</span>
    </div>

    <ul v-else class="doc-notes__list">
      <li v-for="note in notes" :key="note.id">
        <button type="button" class="doc-notes__item" @click="emit('open-note', note.id)">
          <span class="doc-notes__item-icon" aria-hidden="true">
            <v-icon size="17">mdi-note-text-outline</v-icon>
          </span>
          <span class="doc-notes__item-copy">
            <span class="doc-notes__item-title" :class="{ 'is-untitled': !note.title?.trim() }">
              {{ note.title?.trim() || 'Ohne Titel' }}
            </span>
            <span v-if="note.preview?.trim()" class="doc-notes__item-snippet">{{ note.preview }}</span>
          </span>
          <span class="doc-notes__item-end">
            <span class="doc-notes__item-date">{{ formatDate(note.updated_at) }}</span>
            <v-icon size="16">mdi-chevron-right</v-icon>
          </span>
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
  gap: 12px;
  margin-top: 16px;
  padding: 14px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 14px;
  background: color-mix(in srgb, var(--pm-chip-bg, #eef2f4) 62%, transparent);
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
  gap: 8px;
  min-width: 0;
  color: var(--pm-text, #0e181b);
  font-size: 0.88rem;
  font-weight: 650;
}

.doc-notes__heading-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent, #006b75);
}

.doc-notes__count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 100px;
  background: color-mix(in srgb, var(--pm-muted, #535e62) 12%, transparent);
  color: var(--pm-muted, #535e62);
  font-size: 0.68rem;
  line-height: 20px;
  text-align: center;
}

.doc-notes__new.v-btn {
  text-transform: none;
  letter-spacing: 0;
  min-height: 30px;
  padding-inline: 9px;
  font-weight: 600;
}

.doc-notes__state {
  display: flex;
  justify-content: center;
  padding: 10px 0;
}

.doc-notes__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 12px 16px;
  color: var(--pm-muted, #748084);
  text-align: center;
  font-size: 0.76rem;
}

.doc-notes__empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin-bottom: 3px;
  border-radius: 11px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
  color: color-mix(in srgb, var(--pm-accent, #006b75) 78%, var(--pm-muted, #748084));
}

.doc-notes__empty strong {
  color: var(--pm-text, #0e181b);
  font-size: 0.84rem;
  font-weight: 600;
}

.doc-notes__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.doc-notes__item {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px;
  background: var(--pm-app-surface-raised, #fff);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: border-color 120ms ease, background 120ms ease, transform 120ms ease;
}

.doc-notes__item:hover {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.04));
  transform: translateY(-1px);
}

.doc-notes__item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
  color: var(--pm-accent, #006b75);
}

.doc-notes__item-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
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
  white-space: nowrap;
}

.doc-notes__item-end {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--pm-muted, #535e62);
}

@media (prefers-reduced-motion: reduce) {
  .doc-notes__item { transition: none; }
  .doc-notes__item:hover { transform: none; }
}
</style>
