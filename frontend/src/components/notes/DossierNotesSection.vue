<!--
  DossierNotesSection — zeigt im Leuchttisch-Inspektor die first-class-Notizen,
  die auf dieses Dossier verweisen (note_link target_type='dossier', gespeist aus
  wikiLink-Knoten im Notiztext), plus einen Knopf für eine neue, bereits auf das
  Dossier verweisende Notiz. Öffnen/Anlegen laufen über Events an
  DossierWorkspace, das in den Notizbereich wechselt.
-->
<template>
  <section class="dsr-notes" aria-label="Notizen zu diesem Leuchttisch">
    <header class="dsr-notes__header">
      <div class="dsr-notes__heading">
        <v-icon size="16">mdi-note-outline</v-icon>
        <span>Notizen</span>
        <span v-if="notes.length" class="dsr-notes__count">{{ notes.length }}</span>
      </div>
      <v-btn
        class="dsr-notes__new"
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

    <div v-if="loading" class="dsr-notes__state">
      <v-progress-circular indeterminate color="primary" size="18" width="2" />
    </div>

    <div v-else-if="!notes.length" class="dsr-notes__empty">
      Noch keine Notizen zu diesem Leuchttisch.
    </div>

    <ul v-else class="dsr-notes__list">
      <li v-for="note in notes" :key="note.id">
        <button type="button" class="dsr-notes__item" @click="emit('open-note', note.id)">
          <span class="dsr-notes__item-title" :class="{ 'is-untitled': !note.title?.trim() }">
            {{ note.title?.trim() || 'Ohne Titel' }}
          </span>
          <span v-if="note.preview?.trim()" class="dsr-notes__item-snippet">{{ note.preview }}</span>
          <span class="dsr-notes__item-date">{{ formatDate(note.updated_at) }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue';
import { listNotes } from '../../api/notes.js';

const props = defineProps({
  dossierId: { type: String, default: null },
  creating: { type: Boolean, default: false },
  // Erhöht sich, wenn der Aufrufer die Liste neu laden möchte (z. B. nach Anlegen).
  reloadKey: { type: Number, default: 0 },
});

const emit = defineEmits(['open-note', 'new-note']);

const notes = ref([]);
const loading = ref(false);
let requestId = 0;

async function load() {
  if (!props.dossierId) { notes.value = []; return; }
  const rev = ++requestId;
  loading.value = true;
  try {
    const res = await listNotes({ dossierId: props.dossierId });
    if (rev !== requestId) return;
    notes.value = res.items || [];
  } catch {
    if (rev !== requestId) return;
    notes.value = [];
  } finally {
    if (rev === requestId) loading.value = false;
  }
}

watch(() => props.dossierId, load, { immediate: true });
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
.dsr-notes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dsr-notes__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.dsr-notes__heading {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--pm-muted, #748084);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.dsr-notes__count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 100px;
  background: var(--pm-viewer-surface, #eef2f4);
  color: var(--pm-muted, #535e62);
  font-size: 0.7rem;
  text-align: center;
}

.dsr-notes__new.v-btn {
  text-transform: none;
  letter-spacing: 0;
}

.dsr-notes__state {
  display: flex;
  justify-content: center;
  padding: 10px 0;
}

.dsr-notes__empty {
  padding: 4px 2px 8px;
  color: var(--pm-muted, #748084);
  font-size: 0.82rem;
}

.dsr-notes__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.dsr-notes__item {
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

.dsr-notes__item:hover {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.04));
}

.dsr-notes__item-title {
  color: var(--pm-text, #0e181b);
  font-size: 0.88rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dsr-notes__item-title.is-untitled { color: var(--pm-muted); font-style: italic; font-weight: 500; }

.dsr-notes__item-snippet {
  color: var(--pm-muted, #535e62);
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dsr-notes__item-date {
  color: var(--pm-muted, #535e62);
  font-size: 0.7rem;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
}

@media (prefers-reduced-motion: reduce) {
  .dsr-notes__item { transition: none; }
}
</style>
