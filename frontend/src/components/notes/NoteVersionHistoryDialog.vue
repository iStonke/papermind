<template>
  <BaseDialog
    :model-value="modelValue"
    title="Versionsverlauf"
    :header-subtitle="historySubtitle"
    description="Autosaves werden gebündelt. Bewusste Wechsel, Exporte und KI-Übernahmen markieren eigene Wiederherstellungspunkte."
    icon="mdi-history"
    primary-text="Diesen Stand wiederherstellen"
    secondary-text="Schließen"
    :primary-disabled="!selectedRevision || selectedIsCurrent || loading || Boolean(error)"
    :loading="restoring"
    :persistent="restoring"
    :guard-close="restoring"
    max-width="920"
    scrollable
    body-class="note-version-history__dialog-body"
    @update:model-value="emit('update:modelValue', $event)"
    @primary="restoreSelected"
  >
    <div v-if="loading" class="note-version-history__state" aria-live="polite">
      <v-progress-circular indeterminate size="25" width="2" color="primary" />
      <span>Versionen werden geladen …</span>
    </div>

    <div v-else-if="error" class="note-version-history__state is-error" role="alert">
      <v-icon size="22">mdi-alert-circle-outline</v-icon>
      <span>{{ error }}</span>
      <button type="button" @click="loadHistory">Erneut versuchen</button>
    </div>

    <div v-else-if="!revisions.length" class="note-version-history__state">
      <v-icon size="24">mdi-history</v-icon>
      <span>Noch keine früheren Stände vorhanden.</span>
    </div>

    <div v-else class="note-version-history">
      <div class="note-version-history__list" role="list" aria-label="Gespeicherte Versionen">
        <button
          v-for="revision in revisions"
          :key="revision.id"
          type="button"
          class="note-version-history__item"
          :class="{ 'is-selected': revision.id === selectedRevisionId }"
          :aria-current="revision.id === selectedRevisionId ? 'true' : undefined"
          @click="selectRevision(revision.id)"
        >
          <span class="note-version-history__item-icon" aria-hidden="true">
            <v-icon size="16">{{ reasonIcon(revision.reason) }}</v-icon>
          </span>
          <span class="note-version-history__item-main">
            <strong>{{ formatTimestamp(revision.updated_at) }}</strong>
            <small>{{ reasonLabel(revision.reason) }}</small>
            <span>{{ revision.preview || revision.title || 'Leere Notiz' }}</span>
          </span>
          <span v-if="revision.note_revision === currentRevision" class="note-version-history__current">
            Aktuell
          </span>
        </button>
      </div>

      <section class="note-version-history__preview" aria-live="polite">
        <div v-if="detailLoading" class="note-version-history__preview-loading">
          <v-progress-circular indeterminate size="22" width="2" color="primary" />
        </div>
        <template v-else-if="selectedRevision">
          <header>
            <span>{{ formatTimestamp(selectedRevision.updated_at) }}</span>
            <strong>{{ selectedRevision.title?.trim() || 'Ohne Titel' }}</strong>
          </header>
          <pre>{{ selectedPreview }}</pre>
        </template>
      </section>
    </div>
  </BaseDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

import { getNoteRevision, listNoteRevisions } from '../../api/notes.js';
import BaseDialog from '../BaseDialog.vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  noteId: { type: String, required: true },
  currentRevision: { type: Number, default: 1 },
  restoring: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'restore']);

const revisions = ref([]);
const total = ref(0);
const loading = ref(false);
const detailLoading = ref(false);
const error = ref('');
const selectedRevisionId = ref(null);
const selectedRevision = ref(null);
let loadSequence = 0;
let detailSequence = 0;

const selectedIsCurrent = computed(
  () => Number(selectedRevision.value?.note_revision) === Number(props.currentRevision),
);
const selectedPreview = computed(() => {
  const text = String(selectedRevision.value?.body_text || '').trim();
  return text || 'Dieser Stand enthält noch keinen Text.';
});
const historySubtitle = computed(() => {
  if (loading.value) return 'Wird geladen …';
  if (!total.value) return 'Noch keine Stände';
  if (total.value > revisions.value.length) {
    return `${revisions.value.length} von ${total.value} Ständen`;
  }
  return `${total.value} ${total.value === 1 ? 'Stand' : 'Stände'}`;
});

function reasonLabel(reason) {
  return {
    created: 'Erstellt',
    autosave: 'Bearbeitung',
    navigation: 'Beim Notizwechsel',
    export: 'Vor Export',
    ai: 'KI-Übernahme',
    before_restore: 'Vor Wiederherstellung',
    restore: 'Wiederhergestellt',
    manual: 'Manueller Stand',
  }[reason] || 'Bearbeitung';
}

function reasonIcon(reason) {
  return {
    created: 'mdi-file-document-plus-outline',
    export: 'mdi-tray-arrow-down',
    ai: 'mdi-auto-fix',
    before_restore: 'mdi-backup-restore',
    restore: 'mdi-restore',
  }[reason] || 'mdi-content-save-outline';
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unbekannter Zeitpunkt';
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

async function loadHistory() {
  if (!props.noteId) return;
  const sequence = ++loadSequence;
  loading.value = true;
  error.value = '';
  selectedRevision.value = null;
  try {
    const response = await listNoteRevisions(props.noteId, { limit: 50 });
    if (sequence !== loadSequence) return;
    revisions.value = response?.items || [];
    total.value = Number(response?.total) || revisions.value.length;
    const current = revisions.value.find(
      (revision) => Number(revision.note_revision) === Number(props.currentRevision),
    );
    const initial = current || revisions.value[0] || null;
    selectedRevisionId.value = initial?.id || null;
    if (initial) await loadRevisionDetail(initial.id);
  } catch (loadError) {
    if (sequence !== loadSequence) return;
    revisions.value = [];
    total.value = 0;
    error.value = loadError?.message || 'Der Versionsverlauf konnte nicht geladen werden.';
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}

async function loadRevisionDetail(revisionId) {
  if (!revisionId || !props.noteId) return;
  const sequence = ++detailSequence;
  detailLoading.value = true;
  try {
    const detail = await getNoteRevision(props.noteId, revisionId);
    if (sequence === detailSequence) selectedRevision.value = detail;
  } catch (loadError) {
    if (sequence === detailSequence) {
      error.value = loadError?.message || 'Der ausgewählte Stand konnte nicht geladen werden.';
    }
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}

function selectRevision(revisionId) {
  if (!revisionId || revisionId === selectedRevisionId.value) return;
  selectedRevisionId.value = revisionId;
  selectedRevision.value = null;
  void loadRevisionDetail(revisionId);
}

function restoreSelected() {
  if (!selectedRevision.value || selectedIsCurrent.value || props.restoring) return;
  emit('restore', selectedRevision.value);
}

watch(
  () => [props.modelValue, props.noteId],
  ([open]) => {
    if (open) void loadHistory();
    else {
      loadSequence += 1;
      detailSequence += 1;
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.note-version-history {
  display: grid;
  min-height: 390px;
  grid-template-columns: minmax(250px, 0.78fr) minmax(320px, 1.22fr);
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.11);
  border-radius: 14px;
  background: rgba(var(--v-theme-on-surface), 0.018);
}

.note-version-history__list {
  max-height: 470px;
  overflow-y: auto;
  padding: 7px;
  border-right: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}

.note-version-history__item {
  display: flex;
  width: 100%;
  min-height: 76px;
  align-items: flex-start;
  gap: 9px;
  padding: 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.note-version-history__item:hover,
.note-version-history__item:focus-visible {
  background: rgba(var(--v-theme-on-surface), 0.055);
  outline: none;
}

.note-version-history__item.is-selected {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 11%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--pm-accent, #006b75) 22%, transparent);
}

.note-version-history__item-icon {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.055);
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.note-version-history__item-main {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 1px;
}

.note-version-history__item-main strong {
  font-size: 0.8rem;
  font-weight: 680;
}

.note-version-history__item-main small {
  color: var(--pm-accent-strong, #00555f);
  font-size: 0.69rem;
  font-weight: 650;
}

.note-version-history__item-main > span {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 0.72rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-version-history__current {
  flex: none;
  padding: 2px 5px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
  color: var(--pm-accent-strong, #00555f);
  font-size: 0.62rem;
  font-weight: 700;
}

.note-version-history__preview {
  min-width: 0;
  padding: 22px 24px;
  background: rgba(var(--v-theme-surface), 0.68);
}

.note-version-history__preview header {
  display: grid;
  gap: 5px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}

.note-version-history__preview header span {
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 0.72rem;
}

.note-version-history__preview header strong {
  font-family: var(--pm-font-display, inherit);
  font-size: 1.12rem;
}

.note-version-history__preview pre {
  max-height: 350px;
  margin: 0;
  overflow: auto;
  padding: 18px 0;
  color: rgba(var(--v-theme-on-surface), 0.76);
  font: 400 0.88rem/1.65 var(--pm-font-body, inherit);
  white-space: pre-wrap;
  word-break: break-word;
}

.note-version-history__preview-loading,
.note-version-history__state {
  display: flex;
  min-height: 300px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.note-version-history__state.is-error {
  color: rgb(var(--v-theme-error));
}

.note-version-history__state button {
  border: 0;
  background: transparent;
  color: currentColor;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  text-decoration: underline;
}

@media (max-width: 760px) {
  .note-version-history {
    grid-template-columns: 1fr;
  }
  .note-version-history__list {
    max-height: 230px;
    border-right: 0;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  }
  .note-version-history__preview {
    min-height: 260px;
  }
}
</style>
