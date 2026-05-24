<template>
  <!-- Tag erstellen -->
  <BaseDialog
    v-model="isCreateOpen"
    max-width="420"
    title="Tag erstellen"
    description="Neuen Tag für die Dokumentorganisation anlegen."
    primary-text="Erstellen"
    secondary-text="Abbrechen"
    :loading="isTagMutationRunning"
    @primary="submitCreate"
    @close="closeCreate"
  >
    <v-text-field
      v-model="createName"
      label="Name"
      density="comfortable"
      variant="outlined"
      hide-details
      @keydown.enter.prevent="submitCreate"
    />
  </BaseDialog>

  <!-- Tag umbenennen -->
  <BaseDialog
    v-model="isRenameOpen"
    max-width="420"
    title="Tag umbenennen"
    description="Bestehenden Tag-Namen aktualisieren."
    primary-text="Speichern"
    secondary-text="Abbrechen"
    :loading="isTagMutationRunning"
    @primary="submitRename"
    @close="closeRename"
  >
    <v-text-field
      v-model="renameName"
      label="Neuer Name"
      density="comfortable"
      variant="outlined"
      hide-details
      @keydown.enter.prevent="submitRename"
    />
  </BaseDialog>

  <!-- Tag zusammenführen -->
  <BaseDialog
    v-model="isMergeOpen"
    max-width="460"
    title="Tag zusammenführen"
    description="Verknüpfungen vom Quell-Tag auf einen Ziel-Tag verschieben."
    primary-text="Zusammenführen"
    secondary-text="Abbrechen"
    :loading="isTagMutationRunning"
    :primary-disabled="!mergeTargetTagId"
    @primary="submitMerge"
    @close="closeMerge"
  >
    <div class="text-body-2 mb-3">
      Alle Verknüpfungen von
      <strong>{{ mergeSourceTag?.name }}</strong>
      werden auf den Ziel-Tag übertragen. Der Quell-Tag wird gelöscht.
    </div>
    <v-autocomplete
      v-model="mergeTargetTagId"
      :items="mergeTargetCandidates"
      item-title="name"
      item-value="id"
      :return-object="false"
      label="Ziel-Tag"
      density="comfortable"
      variant="outlined"
      hide-details
    />
  </BaseDialog>

  <!-- Tag löschen -->
  <BaseDialog
    v-model="isDeleteOpen"
    max-width="420"
    variant="destructive"
    title="Tag löschen"
    description="Tag und seine Verknüpfungen entfernen."
    primary-text="Tag löschen"
    secondary-text="Abbrechen"
    :loading="isTagMutationRunning"
    @primary="submitDelete"
    @close="closeDelete"
  >
    <p class="dialog-delete-copy">
      Tag <strong>„{{ deleteTarget?.name }}"</strong> wird gelöscht.
    </p>
  </BaseDialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import BaseDialog from './BaseDialog.vue';
import { useTagStore } from '../stores/tags';
import { notifyError, logDevError, useNotifications } from '../stores/notifications';

// ── Store ────────────────────────────────────────────────────────────────────

const tagStore = useTagStore();
const { tags, isTagMutationRunning } = storeToRefs(tagStore);
const { notify } = useNotifications();

// ── Emits ────────────────────────────────────────────────────────────────────

const emit = defineEmits(['tag-mutated']);

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

function normalizeTagInput(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

const sortedTagsByName = computed(() =>
  [...tags.value].sort((a, b) => a.name.localeCompare(b.name, 'de-DE', { sensitivity: 'base' }))
);

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
  const normalized = normalizeTagInput(createName.value);
  if (!normalized) {
    notify({ type: 'warning', message: 'Tag-Name darf nicht leer sein.' });
    return;
  }

  isTagMutationRunning.value = true;
  try {
    const result = await tagStore.createTagByName(normalized);
    if (!result.ok) {
      if (result.reason === 'exists') {
        notify({ type: 'warning', message: `Tag "${result.name}" existiert bereits.` });
      }
      return;
    }
    notify({ type: 'success', title: 'Tag', message: `Tag "${result.name}" erstellt.` });
    emit('tag-mutated', { action: 'created' });
    closeCreate();
  } catch (error) {
    notifyError(error, 'Tag konnte nicht erstellt werden.');
  } finally {
    isTagMutationRunning.value = false;
  }
}

// ── Rename ───────────────────────────────────────────────────────────────────

const isRenameOpen = ref(false);
const renameName = ref('');
const renameTarget = ref(null);

function openRename(tag) {
  renameTarget.value = tag;
  renameName.value = tag?.name || '';
  isRenameOpen.value = true;
}

function closeRename() {
  isRenameOpen.value = false;
  renameName.value = '';
  renameTarget.value = null;
}

async function submitRename() {
  if (!renameTarget.value) return;
  const newName = normalizeTagInput(renameName.value);
  if (!newName) {
    notify({ type: 'warning', message: 'Tag-Name darf nicht leer sein.' });
    return;
  }
  try {
    await tagStore.renameTag(renameTarget.value.id, newName);
    emit('tag-mutated', { action: 'renamed' });
    closeRename();
  } catch (error) {
    logDevError(error, 'store-notified');
  }
}

// ── Merge ────────────────────────────────────────────────────────────────────

const isMergeOpen = ref(false);
const mergeSourceTag = ref(null);
const mergeTargetTagId = ref(null);

const mergeTargetCandidates = computed(() => {
  if (!mergeSourceTag.value) return sortedTagsByName.value;
  return sortedTagsByName.value.filter((tag) => tag.id !== mergeSourceTag.value.id);
});

function openMerge(tag) {
  mergeSourceTag.value = tag;
  mergeTargetTagId.value = null;
  isMergeOpen.value = true;
}

function closeMerge() {
  isMergeOpen.value = false;
  mergeSourceTag.value = null;
  mergeTargetTagId.value = null;
}

async function submitMerge() {
  if (!mergeSourceTag.value || !mergeTargetTagId.value) return;
  const sourceId = mergeSourceTag.value.id;
  const targetId = mergeTargetTagId.value;
  try {
    await tagStore.mergeTag(sourceId, targetId);
    emit('tag-mutated', { action: 'merged', sourceId, targetId });
    closeMerge();
  } catch (error) {
    logDevError(error, 'store-notified');
  }
}

// ── Delete ───────────────────────────────────────────────────────────────────

const isDeleteOpen = ref(false);
const deleteTarget = ref(null);

function openDelete(tag) {
  deleteTarget.value = tag;
  isDeleteOpen.value = true;
}

function closeDelete() {
  isDeleteOpen.value = false;
  deleteTarget.value = null;
}

async function submitDelete() {
  if (!deleteTarget.value) return;
  const tagId = deleteTarget.value.id;
  try {
    await tagStore.deleteTag(tagId);
    emit('tag-mutated', { action: 'deleted', tagId });
    closeDelete();
  } catch (error) {
    logDevError(error, 'store-notified');
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

defineExpose({ openCreate, openRename, openMerge, openDelete });
</script>
