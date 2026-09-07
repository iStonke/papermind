<template>
  <v-menu v-model="open" location="bottom start" :max-height="320" :close-on-content-click="true">
    <template #activator="{ props: menuProps }">
      <button
        v-bind="menuProps"
        type="button"
        class="note-notebook-chip"
        :class="{ 'is-empty': !currentId }"
        :title="label"
        :aria-label="currentId ? `Notizbuch: ${label}. Zuordnung ändern` : label"
        :disabled="disabled || saving"
      >
        <v-icon size="14" :style="currentNotebook ? { color: currentCollectionColor || 'var(--pm-accent, #006b75)' } : undefined">mdi-notebook-outline</v-icon>
        <span>{{ label }}</span>
        <v-icon size="13">mdi-chevron-down</v-icon>
      </button>
    </template>
    <v-list class="pm-menu note-notebook-menu" density="compact" min-width="240" aria-label="Notizbuch auswählen">
      <v-list-subheader>Notizbuch zuordnen</v-list-subheader>
      <v-list-item title="Ohne Notizbuch" :active="!currentId" :disabled="saving" @click="assign(null)">
        <template #prepend><v-icon size="18">mdi-inbox-outline</v-icon></template>
        <template #append><v-icon v-if="!currentId" size="16">mdi-check</v-icon></template>
      </v-list-item>
      <v-list-item
        v-for="notebook in store.notebooks"
        :key="notebook.id"
        :title="notebook.name"
        :active="currentId === notebook.id"
        :disabled="saving"
        @click="assign(notebook.id)"
      >
        <template #prepend><v-icon size="18" :style="{ color: noteCollectionColor(notebook, store.collections) || 'var(--pm-accent, #006b75)' }">mdi-notebook-outline</v-icon></template>
        <template #append><v-icon v-if="currentId === notebook.id" size="16">mdi-check</v-icon></template>
      </v-list-item>
      <v-list-item v-if="loadError" title="Notizbücher erneut laden" subtitle="Laden fehlgeschlagen" @click="loadNotebooks" />
      <v-list-item v-else-if="!store.notebooksLoaded" title="Notizbücher werden geladen …" disabled />
      <v-list-item v-else-if="!store.notebooks.length" title="Noch keine Notizbücher angelegt" disabled />
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useNotesStore } from '../../stores/notes.js';
import { noteCollectionColor } from '../../utils/noteCollectionColor.js';
import { notifyError } from '../../stores/notifications.js';

const props = defineProps({
  noteId: { type: String, required: true },
  notebookId: { type: String, default: null },
  disabled: { type: Boolean, default: false },
});
const store = useNotesStore();
const open = ref(false);
const saving = ref(false);
const loadError = ref(false);
const fallbackId = ref(props.notebookId);
const currentId = computed(() => {
  const note = store.notes.find(note => note.id === props.noteId);
  return note ? note.notebook_id ?? null : fallbackId.value;
});
const currentNotebook = computed(() => store.notebooks.find(book => book.id === currentId.value));
const currentCollectionColor = computed(() => noteCollectionColor(currentNotebook.value, store.collections));
const label = computed(() => currentId.value
  ? currentNotebook.value?.name || 'Notizbuch'
  : 'Notizbuch zuordnen');
watch(() => [props.noteId, props.notebookId], () => { open.value = false; fallbackId.value = props.notebookId; });
watch(open, value => { if (value) void loadNotebooks(); });
onMounted(loadNotebooks);

async function loadNotebooks() {
  loadError.value = false;
  try {
    await store.ensureCollectionsLoaded();
    await store.ensureNotebooksLoaded();
  }
  catch { loadError.value = true; }
}

async function assign(notebookId) {
  if (props.disabled || saving.value || notebookId === currentId.value) return;
  const noteId = props.noteId;
  saving.value = true;
  try {
    await store.moveToNotebook([noteId], notebookId);
    if (props.noteId === noteId) fallbackId.value = notebookId;
  } catch (error) {
    notifyError(error, 'Das Notizbuch konnte nicht zugeordnet werden.');
  } finally { saving.value = false; }
}
</script>

<style scoped>
.note-notebook-menu :deep(.v-list-item:not(.v-list-item--disabled):hover),
.note-notebook-menu :deep(.v-list-item:not(.v-list-item--disabled):focus-visible) {
  background: var(--pm-row-hover, rgba(var(--v-theme-on-surface), 0.1));
}
.note-notebook-menu :deep(.v-list-item--active) {
  background: var(--pm-selected, rgba(var(--v-theme-primary), 0.16));
}
.note-notebook-menu :deep(.v-list-item--active:not(.v-list-item--disabled):hover),
.note-notebook-menu :deep(.v-list-item--active:not(.v-list-item--disabled):focus-visible) {
  background: color-mix(in srgb, var(--pm-selected, rgb(var(--v-theme-primary))) 85%, var(--pm-text, rgb(var(--v-theme-on-surface))));
}
.note-notebook-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 70px;
  max-width: 220px;
  flex: 0 1 auto;
  padding: 3px 9px 3px 8px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
}
.note-notebook-chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-notebook-chip .v-icon { flex: none; color: var(--pm-muted, #64748b); }
.note-notebook-chip:hover:not(:disabled) { background: var(--pm-row-hover); }
.note-notebook-chip:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.note-notebook-chip:disabled { cursor: default; }
</style>
