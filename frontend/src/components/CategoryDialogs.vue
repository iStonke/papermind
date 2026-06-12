<template>
  <!-- Dokumenttyp erstellen -->
  <BaseDialog
    v-model="isCreateOpen"
    max-width="420"
    title="Dokumenttyp erstellen"
    header-subtitle="Neuen Dokumenttyp für die Organisation anlegen."
    primary-text="Erstellen"
    secondary-text="Abbrechen"
    :loading="isCategoryMutationRunning"
    @primary="submitCreate"
    @close="closeCreate"
  >
    <v-text-field
      v-model="createName"
      label="Name"
      :maxlength="VOCAB_NAME_MAX_LENGTH"
      density="comfortable"
      variant="outlined"
      hide-details
      @keydown="handleCreateShortcut"
    />
  </BaseDialog>

  <!-- Dokumenttyp umbenennen -->
  <BaseDialog
    v-model="isRenameOpen"
    max-width="420"
    title="Dokumenttyp umbenennen"
    description="Bestehenden Dokumenttyp-Namen aktualisieren."
    primary-text="Speichern"
    secondary-text="Abbrechen"
    :loading="isCategoryMutationRunning"
    @primary="submitRename"
    @close="closeRename"
  >
    <v-text-field
      v-model="renameName"
      label="Neuer Name"
      :maxlength="VOCAB_NAME_MAX_LENGTH"
      density="comfortable"
      variant="outlined"
      hide-details
      @keydown="handleRenameShortcut"
    />
  </BaseDialog>

  <!-- Dokumenttyp löschen -->
  <BaseDialog
    v-model="isDeleteOpen"
    max-width="420"
    variant="destructive"
    title="Dokumenttyp löschen"
    description="Auswahloption entfernen."
    primary-text="Dokumenttyp löschen"
    secondary-text="Abbrechen"
    :loading="isCategoryMutationRunning"
    @primary="submitDelete"
    @close="closeDelete"
  >
    <p class="dialog-delete-copy">
      Dokumenttyp <strong>„{{ deleteTarget?.name }}"</strong> wird als Auswahloption entfernt.
      Bereits zugewiesene Dokumente behalten ihren Dokumenttyp.
    </p>
  </BaseDialog>
</template>

<script setup>
import { ref } from 'vue';
import { storeToRefs } from 'pinia';
import BaseDialog from './BaseDialog.vue';
import { useCategoryStore } from '../stores/categories';
import { logDevError, useNotifications } from '../stores/notifications';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts';

const VOCAB_NAME_MAX_LENGTH = 30;

// ── Store ────────────────────────────────────────────────────────────────────

const categoryStore = useCategoryStore();
const { isCategoryMutationRunning } = storeToRefs(categoryStore);
const { notify } = useNotifications();

// ── Emits ────────────────────────────────────────────────────────────────────

const emit = defineEmits(['category-mutated']);

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

function normalizeCategoryInput(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

// ── Create ───────────────────────────────────────────────────────────────────

const isCreateOpen = ref(false);
const createName = ref('');

function openCreate() {
  createName.value = '';
  isCreateOpen.value = true;
}

function closeCreate() {
  isCreateOpen.value = false;
  createName.value = '';
}

async function submitCreate() {
  const normalized = normalizeCategoryInput(createName.value);
  if (!normalized) {
    notify({ type: 'warning', message: 'Dokumenttyp-Name darf nicht leer sein.' });
    return;
  }
  try {
    const result = await categoryStore.createCategoryByName(normalized);
    if (!result.ok) {
      return;
    }
    emit('category-mutated', { action: 'created', name: result.name });
    closeCreate();
  } catch (error) {
    logDevError(error, 'store-notified');
  }
}

function handleCreateShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, submitCreate, { ignoreEditable: false });
}

// ── Rename ───────────────────────────────────────────────────────────────────

const isRenameOpen = ref(false);
const renameName = ref('');
const renameTarget = ref(null);

function openRename(category) {
  renameTarget.value = category;
  renameName.value = category?.name || '';
  isRenameOpen.value = true;
}

function closeRename() {
  isRenameOpen.value = false;
  renameName.value = '';
  renameTarget.value = null;
}

async function submitRename() {
  if (!renameTarget.value) return;
  const newName = normalizeCategoryInput(renameName.value);
  if (!newName) {
    notify({ type: 'warning', message: 'Dokumenttyp-Name darf nicht leer sein.' });
    return;
  }
  if (newName === normalizeCategoryInput(renameTarget.value.name)) {
    closeRename();
    return;
  }
  try {
    await categoryStore.renameCategory(renameTarget.value.id, newName);
    emit('category-mutated', { action: 'renamed', id: renameTarget.value.id, name: newName });
    closeRename();
  } catch (error) {
    logDevError(error, 'store-notified');
  }
}

function handleRenameShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, submitRename, { ignoreEditable: false });
}

// ── Delete ───────────────────────────────────────────────────────────────────

const isDeleteOpen = ref(false);
const deleteTarget = ref(null);

function openDelete(category) {
  deleteTarget.value = category;
  isDeleteOpen.value = true;
}

function closeDelete() {
  isDeleteOpen.value = false;
  deleteTarget.value = null;
}

async function submitDelete() {
  if (!deleteTarget.value) return;
  const categoryId = deleteTarget.value.id;
  try {
    await categoryStore.deleteCategory(categoryId);
    emit('category-mutated', { action: 'deleted', id: categoryId });
    closeDelete();
  } catch (error) {
    logDevError(error, 'store-notified');
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

defineExpose({ openCreate, openRename, openDelete });
</script>
