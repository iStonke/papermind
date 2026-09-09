<template>
  <article class="dash-card dash-quick-note">
    <header class="dash-quick-note__head">
      <div>
        <h2 class="dash-card__title">Schnelle Notiz</h2>
        <p class="dash-quick-note__hint">Erste Zeile wird zum Titel</p>
      </div>
      <button
        v-if="savedNote"
        type="button"
        class="dash-quick-note__open"
        title="Gespeicherte Notiz öffnen"
        @click="openSavedNote"
      >
        <v-icon size="15">mdi-check-circle-outline</v-icon>
        Öffnen
      </button>
    </header>

    <textarea
      v-model="draft"
      class="dash-quick-note__input"
      placeholder="Gedanken festhalten …"
      aria-label="Text der schnellen Notiz"
      :disabled="saving"
      @keydown.meta.enter.prevent="saveNote"
      @keydown.ctrl.enter.prevent="saveNote"
    />

    <p v-if="errorMessage" class="dash-quick-note__error" role="alert">{{ errorMessage }}</p>

    <footer class="dash-quick-note__footer">
      <label class="dash-quick-note__target" title="Ziel für die neue Notiz">
        <v-icon size="15">mdi-notebook-outline</v-icon>
        <select
          v-model="selectedTarget"
          aria-label="Sammlung oder Notizbuch auswählen"
          :disabled="targetsLoading || saving"
        >
          <option v-if="!targetGroups.length" value="">Ohne Zuordnung</option>
          <optgroup v-for="group in targetGroups" :key="group.id" :label="group.name">
            <option :value="collectionTargetValue(group.id)">{{ group.name }} · ohne Notizbuch</option>
            <option
              v-for="notebook in group.notebooks"
              :key="notebook.id"
              :value="notebookTargetValue(notebook.id)"
            >
              ↳ {{ notebook.name }}
            </option>
          </optgroup>
        </select>
        <v-icon size="14" class="dash-quick-note__target-chevron">mdi-chevron-down</v-icon>
      </label>

      <button
        type="button"
        class="dash-quick-note__save"
        :disabled="!canSave"
        :aria-busy="saving"
        @click="saveNote"
      >
        <v-icon size="16">{{ saving ? 'mdi-progress-clock' : 'mdi-content-save-outline' }}</v-icon>
        <span>{{ saving ? 'Speichert …' : 'Speichern' }}</span>
      </button>
    </footer>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { listNotebooks } from '../../api/notes.js';
import { useAuthStore } from '../../stores/auth.js';
import { useNotesStore } from '../../stores/notes.js';
import { mapApiError } from '../../stores/notifications.js';
import { buildQuickNotePayload } from '../../utils/quickNote.js';
import './dashboard.css';

const DRAFT_STORAGE_PREFIX = 'pm-dashboard-quick-note-draft-v1';
const TARGET_STORAGE_PREFIX = 'pm-dashboard-quick-note-target-v2';
const DRAFT_WRITE_DELAY_MS = 180;

const auth = useAuthStore();
const notesStore = useNotesStore();
const { activeCollectionId, collections } = storeToRefs(notesStore);

const draft = ref('');
const selectedTarget = ref('');
const allNotebooks = ref([]);
const saving = ref(false);
const targetsLoading = ref(true);
const savedNote = ref(null);
const errorMessage = ref('');
let draftWriteTimer = null;
let storageReady = false;

const userStorageScope = computed(() => String(auth.user?.id || auth.username || 'local'));
const draftStorageKey = computed(() => `${DRAFT_STORAGE_PREFIX}:${userStorageScope.value}`);
const targetStorageKey = computed(() => `${TARGET_STORAGE_PREFIX}:${userStorageScope.value}`);
const targetGroups = computed(() => collections.value.map((collection) => ({
  ...collection,
  notebooks: allNotebooks.value.filter((notebook) => notebook.collection_id === collection.id),
})));
const canSave = computed(() => Boolean(buildQuickNotePayload(draft.value)) && !saving.value);

const collectionTargetValue = (id) => `collection:${id}`;
const notebookTargetValue = (id) => `notebook:${id}`;

function readStorage(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}

function writeDraftNow() {
  if (!storageReady) return;
  try {
    const text = draft.value;
    if (!text) {
      window.localStorage.removeItem(draftStorageKey.value);
      return;
    }
    window.localStorage.setItem(draftStorageKey.value, JSON.stringify({
      text,
      target: selectedTarget.value || null,
    }));
  } catch {
    // Der lokale Entwurf ist eine Komfortfunktion; Speichern bleibt verfügbar.
  }
}

function scheduleDraftWrite() {
  if (!storageReady) return;
  if (draftWriteTimer !== null) window.clearTimeout(draftWriteTimer);
  draftWriteTimer = window.setTimeout(() => {
    draftWriteTimer = null;
    writeDraftNow();
  }, DRAFT_WRITE_DELAY_MS);
}

function persistTarget() {
  if (!storageReady) return;
  try {
    if (selectedTarget.value) {
      window.localStorage.setItem(targetStorageKey.value, selectedTarget.value);
    } else {
      window.localStorage.removeItem(targetStorageKey.value);
    }
  } catch {
    // Die Zielvorgabe ist optional.
  }
}

function restoreDraftText() {
  const raw = readStorage(draftStorageKey.value);
  if (!raw) return null;
  try {
    const saved = JSON.parse(raw);
    draft.value = typeof saved?.text === 'string' ? saved.text : '';
    return saved;
  } catch {
    return null;
  }
}

function legacyDraftTarget(savedDraft) {
  if (savedDraft?.target) return savedDraft.target;
  if (savedDraft?.notebookId) return notebookTargetValue(savedDraft.notebookId);
  if (savedDraft?.collectionId) return collectionTargetValue(savedDraft.collectionId);
  return '';
}

function validTarget(value) {
  const target = String(value || '');
  const [kind, id] = target.split(':', 2);
  if (kind === 'collection' && collections.value.some((collection) => collection.id === id)) return target;
  if (kind === 'notebook' && allNotebooks.value.some((notebook) => notebook.id === id)) return target;
  return '';
}

function defaultTarget() {
  const collectionId = activeCollectionId.value || collections.value[0]?.id;
  return collectionId ? collectionTargetValue(collectionId) : '';
}

function applyTargetToPayload(payload) {
  const [kind, id] = selectedTarget.value.split(':', 2);
  if (!id) return;
  if (kind === 'notebook') payload.notebook_id = id;
  else if (kind === 'collection') payload.collection_id = id;
}

async function loadTargets(savedDraft) {
  targetsLoading.value = true;
  try {
    await notesStore.ensureCollectionsLoaded();
    const response = await listNotebooks();
    allNotebooks.value = response?.items || [];
    selectedTarget.value = validTarget(
      legacyDraftTarget(savedDraft) || readStorage(targetStorageKey.value)
    ) || defaultTarget();
  } catch {
    errorMessage.value = 'Notizbücher konnten nicht geladen werden.';
  } finally {
    targetsLoading.value = false;
  }
}

function openSavedNote() {
  if (!savedNote.value?.id) return;
  window.dispatchEvent(new CustomEvent('pm-note:navigate', {
    detail: { type: 'note', id: savedNote.value.id },
  }));
}

async function saveNote() {
  const payload = buildQuickNotePayload(draft.value);
  if (!payload || saving.value) return;

  saving.value = true;
  errorMessage.value = '';
  try {
    applyTargetToPayload(payload);
    savedNote.value = await notesStore.create(payload);
    draft.value = '';
    if (draftWriteTimer !== null) {
      window.clearTimeout(draftWriteTimer);
      draftWriteTimer = null;
    }
    writeDraftNow();
  } catch (error) {
    errorMessage.value = mapApiError(error, 'Die Notiz konnte nicht gespeichert werden.');
  } finally {
    saving.value = false;
  }
}

watch(draft, () => {
  if (draft.value.trim()) savedNote.value = null;
  errorMessage.value = '';
  scheduleDraftWrite();
});
watch(selectedTarget, () => {
  persistTarget();
  scheduleDraftWrite();
});

onMounted(async () => {
  const savedDraft = restoreDraftText();
  await loadTargets(savedDraft);
  storageReady = true;
});

onBeforeUnmount(() => {
  if (draftWriteTimer !== null) window.clearTimeout(draftWriteTimer);
  writeDraftNow();
});
</script>

<style scoped>
.dash-quick-note {
  container-type: inline-size;
  height: 100%;
  min-height: 0;
  padding: 15px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.dash-quick-note__head,
.dash-quick-note__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.dash-quick-note__hint {
  margin: 2px 0 0;
  color: var(--pm-muted);
  font-size: 11.5px;
  line-height: 1.2;
}

.dash-quick-note__open {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 7px;
  border: 0;
  border-radius: 7px;
  background: color-mix(in srgb, var(--pm-success) 11%, transparent);
  color: var(--pm-success);
  font-size: 11.5px;
  font-weight: 650;
  cursor: pointer;
}

.dash-quick-note__input {
  flex: 1 1 auto;
  width: 100%;
  min-height: 62px;
  resize: none;
  padding: 10px 11px;
  border: 1px solid var(--pm-divider);
  border-radius: 10px;
  outline: none;
  background: color-mix(in srgb, var(--pm-v-card, var(--pm-app-surface-raised)) 96%, var(--pm-text) 4%);
  color: var(--pm-text);
  font: inherit;
  font-size: 13px;
  line-height: 1.45;
  transition: border-color var(--pm-duration-fast) var(--pm-easing), box-shadow var(--pm-duration-fast) var(--pm-easing);
}

.dash-quick-note__input::placeholder { color: color-mix(in srgb, var(--pm-muted) 78%, transparent); }
.dash-quick-note__input:focus {
  border-color: color-mix(in srgb, var(--pm-accent) 58%, var(--pm-divider));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent) 10%, transparent);
}

.dash-quick-note__error {
  margin: -4px 0 0;
  color: var(--pm-error);
  font-size: 11.5px;
  line-height: 1.25;
}

.dash-quick-note__target {
  position: relative;
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--pm-muted);
}

.dash-quick-note__target select {
  min-width: 0;
  width: 100%;
  height: 30px;
  padding: 0 24px 0 0;
  appearance: none;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  cursor: pointer;
}

.dash-quick-note__target-chevron {
  position: absolute;
  right: 2px;
  pointer-events: none;
}

.dash-quick-note__save {
  flex: none;
  height: 31px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid color-mix(in srgb, var(--pm-accent) 35%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-accent) 13%, transparent);
  color: var(--pm-accent);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.dash-quick-note__save:hover:not(:disabled) {
  background: color-mix(in srgb, var(--pm-accent) 20%, transparent);
}

.dash-quick-note__save:disabled {
  opacity: 0.45;
  cursor: default;
}

@container (max-width: 290px) {
  .dash-quick-note__save span { display: none; }
  .dash-quick-note__save { width: 32px; padding: 0; justify-content: center; }
}

@media (prefers-reduced-motion: reduce) {
  .dash-quick-note__input { transition: none; }
}
</style>
