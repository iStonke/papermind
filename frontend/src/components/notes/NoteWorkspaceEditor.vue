<!--
  Eingebetteter Notizen-Editor für die rechte Workspace-Spalte. Titel und Body
  werden beim Wechsel geladen und anschließend verzögert gespeichert. Kleine
  UI-Metadaten zum verknüpften Dokument liegen in den Attributen des
  ProseMirror-Wurzeldokuments und werden zusammen mit body_json persistiert.
-->
<template>
  <section class="note-workspace-editor" :aria-busy="loading || switching ? 'true' : undefined">
    <header class="note-workspace-editor__bar">
      <input
        ref="titleInputRef"
        v-model="title"
        class="note-workspace-editor__title"
        type="text"
        placeholder="Titel der Notiz"
        aria-label="Titel der Notiz"
        :spellcheck="notesSpellcheckEnabled"
        :disabled="!hasLoadedContent && (loading || loadError)"
        :readonly="switching"
        @keydown.enter.prevent="focusEditorBody"
      />

      <div class="note-workspace-editor__actions">
        <v-menu location="bottom end">
          <template #activator="{ props: moreMenuProps }">
            <v-btn
              v-bind="moreMenuProps"
              class="note-workspace-editor__more-btn"
              :class="['pm-header-icon-btn', 'pm-header-icon-btn--quiet']"
              variant="text"
              icon
              aria-label="Weitere Aktionen"
              title="Weitere Aktionen"
              :disabled="!hasLoadedContent"
            >
              <v-icon size="20">mdi-dots-vertical</v-icon>
            </v-btn>
          </template>

          <v-list class="note-workspace-editor__more-menu" density="compact" min-width="228">
            <v-list-item
              prepend-icon="mdi-file-document-plus-outline"
              title="Als Vorlage speichern"
              :disabled="savingTemplate"
              @click="saveCurrentNoteAsTemplate"
            />
            <v-divider class="note-workspace-editor__more-divider" />
            <v-list-subheader class="note-workspace-editor__more-subheader">Exportieren</v-list-subheader>
            <v-list-item
              prepend-icon="mdi-file-document-outline"
              title="Markdown"
              @click="exportNoteAsMarkdown"
            />
            <v-list-item
              prepend-icon="mdi-file-pdf-box"
              title="PDF"
              @click="exportNoteAsPdf"
            />
          </v-list>
        </v-menu>

        <span class="note-workspace-editor__view-divider" aria-hidden="true" />

        <v-btn
          class="note-workspace-editor__list-toggle"
          :class="['pm-header-icon-btn', 'pm-header-icon-btn--quiet']"
          :variant="listVisible ? 'text' : 'tonal'"
          icon
          :aria-label="listVisible ? 'Editor im Vollbild anzeigen' : 'Vollbildansicht verlassen'"
          :title="listVisible ? 'Editor im Vollbild anzeigen' : 'Vollbildansicht verlassen'"
          :aria-pressed="listVisible ? 'false' : 'true'"
          @click="emit('toggle-list')"
        >
          <PmActionIcon :name="listVisible ? 'fullscreen' : 'fullscreen-exit'" />
        </v-btn>
      </div>
    </header>

    <div v-if="hasLoadedContent" class="note-workspace-editor__meta" :class="{ 'is-centered': !listVisible }">
      <div class="note-workspace-editor__meta-main">
        <div class="note-workspace-editor__meta-tags">
          <NoteTagBar
            compact
            :tag-ids="noteTagIds"
            :all-tags="noteAllTags"
            :create-tag-by-name="tagStore.ensureTagIdByName"
            :load-tags="tagStore.fetchTags"
            @update:tag-ids="applyNoteTagIds"
          />
        </div>

        <span class="note-workspace-editor__meta-sep" aria-hidden="true" />

        <v-menu
          v-if="linkedDocument"
          v-model="documentDetailsOpen"
          location="bottom start"
          :close-on-content-click="true"
        >
          <template #activator="{ props: docMenuProps }">
            <button
              v-bind="docMenuProps"
              type="button"
              class="note-workspace-editor__doc-chip"
              :title="linkedDocumentDisplayTitle"
            >
              <v-icon size="14">mdi-file-document-outline</v-icon>
              <span class="note-workspace-editor__doc-chip-label">{{ linkedDocumentDisplayTitle }}</span>
              <v-icon size="13">mdi-chevron-down</v-icon>
            </button>
          </template>

          <v-card class="note-workspace-editor__document-popover" min-width="300" max-width="360">
            <div class="note-workspace-editor__document-popover-summary">
              <img :src="documentThumbnailUrl(linkedDocument.id)" alt="" loading="lazy" />
              <span>
                <strong>{{ linkedDocumentDisplayTitle }}</strong>
                <small>{{ linkedDocumentMeta }}</small>
              </span>
            </div>
            <v-divider />
            <v-list density="compact">
              <v-list-item prepend-icon="mdi-open-in-new" title="Dokument öffnen" @click="openLinkedDocument" />
              <v-list-item prepend-icon="mdi-swap-horizontal" title="Dokument wechseln" @click="openDocumentPicker" />
              <v-list-item prepend-icon="mdi-link-off" title="Verknüpfung lösen" @click="unlinkDocument" />
            </v-list>
          </v-card>
        </v-menu>

        <button
          v-else
          type="button"
          class="note-workspace-editor__doc-chip note-workspace-editor__doc-chip--empty"
          title="Dokument zuordnen"
          @click="openDocumentPicker"
        >
          <v-icon size="14">mdi-link-variant-plus</v-icon>
          <span>Dokument</span>
        </button>
      </div>

      <span class="note-workspace-editor__word-count">
        {{ wordCount }} {{ wordCount === 1 ? 'Wort' : 'Wörter' }}
      </span>
    </div>

    <div v-if="loading && !hasLoadedContent" class="note-workspace-editor__state" aria-live="polite">
      <v-progress-circular indeterminate color="primary" size="28" width="2" />
      <span>Notiz wird geladen …</span>
    </div>

    <div v-else-if="loadError && !hasLoadedContent" class="note-workspace-editor__state note-workspace-editor__state--error" role="alert">
      <v-icon size="28">mdi-alert-circle-outline</v-icon>
      <strong>Die Notiz konnte nicht geladen werden.</strong>
      <button type="button" @click="loadNote">Erneut versuchen</button>
    </div>

    <div
      v-else
      ref="scrollContainerRef"
      class="note-workspace-editor__scroll"
      @scroll.passive="rememberScrollPosition()"
    >
      <NoteEditor
        ref="noteEditorRef"
        class="note-workspace-editor__body"
        :class="{ 'is-centered': !listVisible }"
        v-model="body"
        workspace
        :document-items="slashDocuments"
        :link-targets="linkTargets"
        :writing-width="notesWritingWidth"
        :paragraph-spacing="notesParagraphSpacing"
        :font-family="notesFontFamily"
        :spellcheck-enabled="notesSpellcheckEnabled"
        :ai-available="aiAvailable"
        :ai-prompt-suggestions="aiPromptSuggestions"
        @word-count="updateWordCount"
        @change="scheduleSave"
      />

      <section
        v-if="backlinks.length"
        class="note-workspace-editor__backlinks"
        :class="{ 'is-centered': !listVisible }"
        aria-label="Rückverweise"
      >
        <div class="note-workspace-editor__backlinks-heading">
          <v-icon size="15">mdi-link-variant</v-icon>
          <span>Rückverweise</span>
          <span class="note-workspace-editor__backlinks-count">{{ backlinks.length }}</span>
        </div>
        <ul class="note-workspace-editor__backlinks-list">
          <li v-for="bl in backlinks" :key="bl.id">
            <button type="button" class="note-workspace-editor__backlink" @click="openBacklink(bl.id)">
              <span class="note-workspace-editor__backlink-title" :class="{ 'is-untitled': !bl.title?.trim() }">
                {{ bl.title?.trim() || 'Ohne Titel' }}
              </span>
              <span v-if="bl.preview?.trim()" class="note-workspace-editor__backlink-snippet">{{ bl.preview }}</span>
            </button>
          </li>
        </ul>
      </section>
    </div>

    <BaseDialog
      v-model="templateTitleDialogOpen"
      title="Vorlage benennen"
      description="Diese Notiz hat noch keinen Titel. Vergib einen Titel für die neue Vorlage."
      primary-text="Vorlage speichern"
      secondary-text="Abbrechen"
      :primary-disabled="!templateTitleInput.trim()"
      :loading="savingTemplate"
      :persistent="savingTemplate"
      max-width="460"
      @primary="confirmTemplateTitle"
      @close="closeTemplateTitleDialog"
    >
      <v-text-field
        v-model="templateTitleInput"
        label="Titel der Vorlage"
        prepend-inner-icon="mdi-file-document-plus-outline"
        maxlength="500"
        density="comfortable"
        variant="outlined"
        hide-details
        autocomplete="off"
        @keydown.enter.prevent="confirmTemplateTitle"
      />
    </BaseDialog>

    <BaseDialog
      v-model="documentPickerOpen"
      title="Dokument zuordnen"
      description="Wähle ein vorhandenes Dokument aus der PaperMind-Bibliothek."
      primary-text="Zuordnen"
      :primary-disabled="!documentPickerSelection"
      :loading="documentPickerLoading"
      :persistent="documentPickerLoading"
      max-width="780"
      scrollable
      @primary="assignPickedDocument"
      @close="closeDocumentPicker"
    >
      <v-text-field
        v-model="documentPickerSearch"
        prepend-inner-icon="mdi-magnify"
        placeholder="Dokumente suchen"
        variant="outlined"
        density="comfortable"
        clearable
        hide-details
        @update:model-value="scheduleDocumentPickerSearch"
      />

      <v-progress-linear
        v-if="documentPickerLoading"
        class="note-workspace-editor__picker-progress"
        indeterminate
        color="primary"
      />

      <div class="note-workspace-editor__picker-list" role="listbox" aria-label="Dokumente aus der Bibliothek">
        <button
          v-for="document in documentPickerDocuments"
          :key="document.id"
          type="button"
          class="note-workspace-editor__picker-row"
          :class="{ 'is-selected': documentPickerSelection?.id === document.id }"
          role="option"
          :aria-selected="documentPickerSelection?.id === document.id"
          @click="selectPickerDocument(document)"
        >
          <img :src="documentThumbnailUrl(document.id)" alt="" loading="lazy" />
          <span>
            <strong>{{ documentDisplayLabel(document) }}</strong>
            <small>{{ documentPickerMeta(document) }}</small>
          </span>
          <v-icon size="20">
            {{ documentPickerSelection?.id === document.id ? 'mdi-check-circle' : 'mdi-circle-outline' }}
          </v-icon>
        </button>

        <div v-if="documentPickerError" class="note-workspace-editor__picker-empty" role="alert">
          {{ documentPickerError }}
        </div>
        <div
          v-else-if="!documentPickerLoading && !documentPickerDocuments.length"
          class="note-workspace-editor__picker-empty"
        >Keine Dokumente gefunden.</div>
      </div>
    </BaseDialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { documentThumbnailUrl, listDocuments } from '../../api/documents.js';
import { getAICredentialStatus } from '../../api/aiCredentials.js';
import { useSettingsStore } from '../../stores/settings.js';
import { useUiStore } from '../../stores/ui.js';
import { isNoteEmpty, useNotesStore } from '../../stores/notes.js';
import { getNoteBacklinks } from '../../api/notes.js';
import { useCorrespondentStore } from '../../stores/correspondents.js';
import { useDossierStore } from '../../stores/dossiers.js';
import { useTagStore } from '../../stores/tags.js';
import { notifyError, useNotifications } from '../../stores/notifications.js';
import { NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT } from '../../constants/promptDefaults.js';
import {
  noteExportFilename,
  notePrintTitle,
  noteToMarkdown,
  noteToPrintableHtml,
} from '../../utils/noteExport.js';
import BaseDialog from '../BaseDialog.vue';
import PmActionIcon from '../PmActionIcon.vue';
import NoteEditor from './NoteEditor.vue';
import NoteTagBar from './NoteTagBar.vue';

const EMPTY_DOC = { type: 'doc', content: [{ type: 'paragraph' }] };

const props = defineProps({
  noteId: { type: String, required: true },
  listVisible: { type: Boolean, default: true },
});

const emit = defineEmits(['toggle-list']);

const notesStore = useNotesStore();
const { notify } = useNotifications();
const settingsStore = useSettingsStore();
const uiStore = useUiStore();
const savingTemplate = ref(false);
const templateTitleDialogOpen = ref(false);
const templateTitleInput = ref('');
const correspondentStore = useCorrespondentStore();
const dossierStore = useDossierStore();
const tagStore = useTagStore();
// Tags der geladenen Notiz (gemeinsames PaperMind-Vokabular).
const noteTagIds = ref([]);
const noteTagSeed = ref([]);
const noteAllTags = computed(() => {
  const map = new Map();
  for (const t of tagStore.tags || []) {
    const id = String(t?.id || '').trim();
    if (id) map.set(id, { id, name: String(t?.name || '').trim() });
  }
  for (const t of noteTagSeed.value || []) {
    const id = String(t?.id || '').trim();
    if (id && !map.has(id)) map.set(id, { id, name: String(t?.name || '').trim() });
  }
  return [...map.values()];
});
const noteEditorRef = ref(null);
const scrollContainerRef = ref(null);
const titleInputRef = ref(null);
const title = ref('');
const body = ref(EMPTY_DOC);
const wordCount = ref(0);
const status = ref('idle');
const loading = ref(true);
const switching = ref(false);
const hasLoadedContent = ref(false);
const loadedNoteId = ref(null);
const loadError = ref(false);
const documentDetailsOpen = ref(false);
const documentPickerOpen = ref(false);
const documentPickerLoading = ref(false);
const documentPickerSearch = ref('');
const documentPickerDocuments = ref([]);
const documentPickerSelection = ref(null);
const documentPickerError = ref('');
const aiCredentialStatus = ref({
  openai: { configured: false },
  anthropic: { configured: false },
});
// Allgemeine Dokumentliste für den /beleg- und [[-Picker im Editor (M4).
const slashDocuments = ref([]);
// Verweis-Ziele für /verweis und [[…]]: Dokumente + Korrespondenten + Dossiers.
const linkTargets = computed(() => ([
  ...slashDocuments.value,
  ...(correspondentStore.correspondents || []).map((c) => ({
    id: c.id,
    label: c.name,
    type: 'correspondent',
    hint: c.kind === 'person' ? 'Person' : 'Organisation',
  })),
  ...(dossierStore.dossiers || []).map((d) => ({
    id: d.id,
    label: d.title,
    type: 'dossier',
    hint: d.reference || 'Dossier',
  })),
  ...notesStore.notes
    .filter((n) => n.id !== props.noteId)
    .map((n) => ({ id: n.id, label: n.title?.trim() || 'Ohne Titel', type: 'note', hint: 'Notiz' })),
]));

let loadingContent = false;
let saveTimer = null;
let scrollPositionSaveTimer = null;
let documentPickerSearchTimer = null;
let documentPickerRevision = 0;
let loadRevision = 0;
let saveRevision = 0;
let discardPendingSave = false;

const NOTE_SCROLL_POSITIONS_STORAGE_KEY = 'pm-note-scroll-positions-v1';
const NOTE_SCROLL_POSITIONS_LIMIT = 100;
const noteScrollPositions = loadStoredScrollPositions();

const noteAttributes = computed(() => body.value?.attrs || {});
const linkedDocument = computed(() => noteAttributes.value.linkedDocument || null);
const showFilenameSuffix = computed(() => settingsStore.settingsDraft?.ui?.showFilenameSuffix ?? false);
const notesWritingWidth = computed(() => {
  const value = settingsStore.settingsDraft?.ui?.notes_writing_width;
  return ['compact', 'comfortable', 'wide'].includes(value) ? value : 'comfortable';
});
const notesParagraphSpacing = computed(() => {
  const value = settingsStore.settingsDraft?.ui?.notes_paragraph_spacing;
  return ['compact', 'comfortable', 'spacious'].includes(value) ? value : 'comfortable';
});
const notesFontFamily = computed(() => {
  const value = settingsStore.settingsDraft?.ui?.notes_font_family;
  return ['sans', 'serif', 'mono'].includes(value) ? value : 'sans';
});
const notesSpellcheckEnabled = computed(
  () => settingsStore.settingsDraft?.ui?.notes_spellcheck_enabled !== false
);
const aiAvailable = computed(() => {
  const config = settingsStore.settingsDraft?.text_generation;
  if (!config?.enabled) return false;
  const provider = config.provider;
  const modelKey = {
    ollama: 'ollama_model',
    openai: 'openai_model',
    anthropic: 'anthropic_model',
  }[provider];
  if (!modelKey || !String(config[modelKey] || '').trim()) return false;
  if (provider === 'ollama') return settingsStore.settingsDraft?.ollama?.enabled === true;
  return aiCredentialStatus.value?.[provider]?.configured === true;
});
const aiPromptSuggestions = computed(() => {
  const configured = settingsStore.settingsDraft?.text_generation?.prompt_suggestions;
  const source = Array.isArray(configured)
    ? configured
    : NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT;
  return source
    .filter((suggestion) => typeof suggestion === 'string')
    .map((suggestion) => suggestion.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .slice(0, 6);
});
const linkedDocumentDisplayTitle = computed(() =>
  formatDocumentFilename(linkedDocument.value?.title || 'Dokument')
);
const linkedDocumentMeta = computed(() => {
  const document = linkedDocument.value;
  if (!document) return '';
  return [
    'PDF',
    document.pageCount ? `${document.pageCount} ${document.pageCount === 1 ? 'Seite' : 'Seiten'}` : '',
    document.correspondent || '',
    document.documentDate ? formatYear(document.documentDate) : '',
  ].filter(Boolean).join(' · ');
});

watch(() => props.noteId, (noteId) => loadNote(noteId), { immediate: true });

// Rückverweise: Notizen, die auf DIESE Notiz verweisen ([[Notiz]]).
const backlinks = ref([]);
let backlinksRequestId = 0;
async function loadBacklinks(noteId = props.noteId) {
  const rev = ++backlinksRequestId;
  if (!noteId) { backlinks.value = []; return; }
  try {
    const res = await getNoteBacklinks(noteId);
    if (rev === backlinksRequestId) backlinks.value = res.items || [];
  } catch {
    if (rev === backlinksRequestId) backlinks.value = [];
  }
}
watch(() => props.noteId, (noteId) => loadBacklinks(noteId), { immediate: true });

function openBacklink(noteId) {
  if (noteId) notesStore.requestOpen(noteId);
}
watch(title, () => scheduleSave());

async function loadNote(noteId = props.noteId) {
  const revision = ++loadRevision;
  if (loadedNoteId.value && loadedNoteId.value !== noteId) {
    rememberScrollPosition(loadedNoteId.value);
    flushSave();
  }
  discardPendingSave = false;
  loadError.value = false;
  const cachedNote = notesStore.peek(noteId);
  if (cachedNote) {
    applyLoadedNote(cachedNote, noteId);
    loading.value = false;
    switching.value = false;
    return;
  }

  loading.value = !hasLoadedContent.value;
  switching.value = hasLoadedContent.value;
  try {
    const note = await notesStore.get(noteId);
    if (revision !== loadRevision) return;
    applyLoadedNote(note, noteId);
  } catch {
    if (revision !== loadRevision) return;
    loadError.value = true;
    status.value = 'error';
  } finally {
    if (revision === loadRevision) {
      loading.value = false;
      switching.value = false;
    }
  }
}

function applyLoadedNote(note, noteId) {
  loadingContent = true;
  title.value = note?.title || '';
  body.value = normalizeBody(note?.body_json);
  noteTagSeed.value = Array.isArray(note?.tags) ? note.tags : [];
  noteTagIds.value = noteTagSeed.value.map((t) => t.id);
  loadedNoteId.value = noteId;
  hasLoadedContent.value = true;
  status.value = 'saved';
  nextTick(() => {
    loadingContent = false;
    if (loadedNoteId.value === noteId) restoreScrollPosition(noteId);
  });
}

async function applyNoteTagIds(ids) {
  const noteId = loadedNoteId.value;
  if (!noteId) return;
  const previous = noteTagIds.value;
  noteTagIds.value = ids; // optimistisch
  try {
    const updated = await notesStore.setTags(noteId, { tagIds: ids });
    if (loadedNoteId.value === noteId) {
      noteTagSeed.value = updated.tags || [];
      noteTagIds.value = (updated.tags || []).map((t) => t.id);
    }
  } catch (error) {
    if (loadedNoteId.value === noteId) noteTagIds.value = previous;
    notifyError(error, 'Tags konnten nicht gespeichert werden.');
  }
}

function loadStoredScrollPositions() {
  if (typeof window === 'undefined') return new Map();
  try {
    const stored = JSON.parse(window.localStorage.getItem(NOTE_SCROLL_POSITIONS_STORAGE_KEY) || '{}');
    return new Map(
      Object.entries(stored)
        .filter(([, entry]) => Number.isFinite(entry?.top) && entry.top >= 0)
        .map(([id, entry]) => [id, {
          top: Math.round(entry.top),
          touchedAt: Number.isFinite(entry.touchedAt) ? entry.touchedAt : 0,
        }]),
    );
  } catch {
    return new Map();
  }
}

function rememberScrollPosition(noteId = loadedNoteId.value) {
  const scrollElement = scrollContainerRef.value;
  if (!noteId || !scrollElement) return;
  noteScrollPositions.set(noteId, {
    top: Math.max(0, Math.round(scrollElement.scrollTop)),
    touchedAt: Date.now(),
  });
  if (scrollPositionSaveTimer) window.clearTimeout(scrollPositionSaveTimer);
  scrollPositionSaveTimer = window.setTimeout(persistScrollPositions, 180);
}

function persistScrollPositions() {
  if (scrollPositionSaveTimer) window.clearTimeout(scrollPositionSaveTimer);
  scrollPositionSaveTimer = null;
  const entries = [...noteScrollPositions.entries()]
    .sort(([, a], [, b]) => b.touchedAt - a.touchedAt);
  for (const [id] of entries.slice(NOTE_SCROLL_POSITIONS_LIMIT)) noteScrollPositions.delete(id);
  try {
    window.localStorage.setItem(
      NOTE_SCROLL_POSITIONS_STORAGE_KEY,
      JSON.stringify(Object.fromEntries(entries.slice(0, NOTE_SCROLL_POSITIONS_LIMIT))),
    );
  } catch {
    // Die aktuelle Sitzung funktioniert auch ohne verfügbaren Local Storage.
  }
}

function restoreScrollPosition(noteId) {
  const top = noteScrollPositions.get(noteId)?.top || 0;
  noteEditorRef.value?.restoreWorkspaceScroll?.(top);
}

function normalizeBody(value) {
  if (!value || value.type !== 'doc') return structuredClone(EMPTY_DOC);
  return value;
}

function clearSaveTimer() {
  if (!saveTimer) return;
  window.clearTimeout(saveTimer);
  saveTimer = null;
}

function scheduleSave() {
  if (loadingContent || switching.value || loading.value || loadError.value || discardPendingSave) return;
  status.value = 'saving';
  clearSaveTimer();
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    void persist();
  }, 650);
}

function updateWordCount(value) {
  wordCount.value = Number.isFinite(value) ? value : 0;
}

async function persist() {
  if (loadingContent || discardPendingSave || !loadedNoteId.value) return;
  const noteId = loadedNoteId.value;
  const savedTitle = title.value;
  const savedBody = body.value;
  const revision = ++saveRevision;
  status.value = 'saving';
  try {
    await notesStore.update(noteId, {
      title: savedTitle,
      body_json: savedBody,
    });
    if (noteId === loadedNoteId.value && revision === saveRevision) {
      status.value = 'saved';
    }
  } catch {
    if (noteId === loadedNoteId.value && revision === saveRevision) status.value = 'error';
  }
}

async function saveCurrentNoteAsTemplate() {
  const currentTitle = String(title.value || '').trim();
  if (!currentTitle) {
    templateTitleInput.value = '';
    templateTitleDialogOpen.value = true;
    return;
  }
  await persistCurrentNoteAsTemplate(currentTitle);
}

async function confirmTemplateTitle() {
  const requestedTitle = String(templateTitleInput.value || '').trim();
  if (!requestedTitle || savingTemplate.value) return;
  await persistCurrentNoteAsTemplate(requestedTitle);
}

function closeTemplateTitleDialog() {
  if (savingTemplate.value) return;
  templateTitleInput.value = '';
}

async function persistCurrentNoteAsTemplate(templateTitle) {
  const noteId = loadedNoteId.value;
  if (!noteId || savingTemplate.value) return;
  savingTemplate.value = true;
  try {
    // Ausstehende Änderungen zuerst persistieren, damit die Vorlage den
    // aktuellen Stand kopiert (save_as_template liest den Serverzustand).
    clearSaveTimer();
    await persist();
    const template = await notesStore.saveAsTemplate(noteId, { title: templateTitle });
    const savedTitle = template.title?.trim() || templateTitle;
    templateTitleDialogOpen.value = false;
    templateTitleInput.value = '';
    notify({
      type: 'success',
      title: 'Vorlage gespeichert',
      message: `„${savedTitle}" wurde zu deinen Vorlagen hinzugefügt.`,
      critical: true,
    });
  } catch (error) {
    notifyError(error, 'Vorlage konnte nicht gespeichert werden.');
  } finally {
    savingTemplate.value = false;
  }
}

function patchBodyAttributes(patch) {
  body.value = {
    ...normalizeBody(body.value),
    attrs: { ...noteAttributes.value, ...patch },
  };
  scheduleSave();
}

async function openDocumentPicker() {
  documentDetailsOpen.value = false;
  documentPickerSearch.value = '';
  documentPickerSelection.value = null;
  documentPickerOpen.value = true;
  await loadDocumentPickerDocuments();
}

function closeDocumentPicker() {
  if (documentPickerSearchTimer) window.clearTimeout(documentPickerSearchTimer);
  documentPickerSearchTimer = null;
  documentPickerSelection.value = null;
}

async function loadDocumentPickerDocuments() {
  const revision = ++documentPickerRevision;
  documentPickerLoading.value = true;
  documentPickerError.value = '';
  try {
    const params = new URLSearchParams({
      limit: '100',
      offset: '0',
      include_total: 'false',
      sort: 'created_at',
      order: 'desc',
    });
    const query = documentPickerSearch.value.trim();
    if (query) params.set('q', query);
    const payload = await listDocuments(params.toString());
    if (revision !== documentPickerRevision) return;
    documentPickerDocuments.value = (payload?.items || []).filter((document) => !document.is_deleted);
  } catch {
    if (revision !== documentPickerRevision) return;
    documentPickerDocuments.value = [];
    documentPickerError.value = 'Die Dokumente konnten nicht geladen werden.';
  } finally {
    if (revision === documentPickerRevision) documentPickerLoading.value = false;
  }
}

// Reale Dokumente für den Editor-Slash-Picker (/beleg, /verweis, [[).
async function loadSlashDocuments() {
  try {
    const params = new URLSearchParams({
      limit: '100', offset: '0', include_total: 'false', sort: 'created_at', order: 'desc',
    });
    const payload = await listDocuments(params.toString());
    slashDocuments.value = (payload?.items || [])
      .filter((document) => !document.is_deleted)
      .map((document) => ({
        id: document.id,
        label: documentDisplayLabel(document),
        type: 'document',
        hint: documentPickerMeta(document),
      }));
  } catch {
    slashDocuments.value = [];
  }
}
onMounted(() => {
  loadSlashDocuments();
  loadAICredentialStatus();
  window.addEventListener('papermind:ai-configuration-changed', loadAICredentialStatus);
  correspondentStore.ensureLoaded?.();
  dossierStore.fetchList?.();
});

async function loadAICredentialStatus() {
  try {
    aiCredentialStatus.value = await getAICredentialStatus();
  } catch {
    aiCredentialStatus.value = {
      openai: { configured: false },
      anthropic: { configured: false },
    };
  }
}

function scheduleDocumentPickerSearch() {
  if (documentPickerSearchTimer) window.clearTimeout(documentPickerSearchTimer);
  documentPickerSearchTimer = window.setTimeout(() => {
    documentPickerSearchTimer = null;
    void loadDocumentPickerDocuments();
  }, 280);
}

function selectPickerDocument(document) {
  documentPickerSelection.value = document;
}

function assignPickedDocument() {
  if (!documentPickerSelection.value) return;
  assignDocument(documentPickerSelection.value);
  documentPickerOpen.value = false;
  closeDocumentPicker();
}

function assignDocument(document) {
  patchBodyAttributes({
    linkedDocument: {
      id: document.id,
      title: documentLabel(document),
      pageCount: document.page_count || null,
      correspondent: document.correspondent_name || '',
      documentDate: document.document_date || '',
    },
  });
}

function unlinkDocument() {
  documentDetailsOpen.value = false;
  patchBodyAttributes({ linkedDocument: null });
}

function openLinkedDocument() {
  if (!linkedDocument.value?.id) return;
  documentDetailsOpen.value = false;
  uiStore.requestWorkspace('openDocumentReader', linkedDocument.value.id);
}

async function focusEditorBody(position) {
  // Beim Anlegen kann der Editor im selben Render-Zyklus noch seinen neuen
  // Inhalt übernehmen. Ein weiterer Tick verhindert, dass der Fokus dabei
  // wieder verloren geht.
  await nextTick();
  noteEditorRef.value?.focusBody?.(position);
}

function focusTitle() {
  titleInputRef.value?.focus();
}

function exportNoteAsMarkdown() {
  try {
    const markdown = noteToMarkdown({ title: title.value, body: body.value });
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = noteExportFilename(title.value);
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
  } catch (error) {
    notifyError(error, 'Notiz konnte nicht exportiert werden.');
  }
}

function exportNoteAsPdf() {
  let printWindow = null;
  try {
    const html = noteToPrintableHtml({
      title: title.value,
      body: body.value,
      fontFamily: notesFontFamily.value,
      paragraphSpacing: notesParagraphSpacing.value,
    });
    printWindow = window.open('', '_blank', 'width=900,height=720');
    if (!printWindow) throw new Error('Popup für PDF-Export wurde blockiert.');
    printWindow.opener = null;
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.document.title = notePrintTitle(title.value);
    printWindow.addEventListener('load', () => {
      printWindow.setTimeout(() => {
        printWindow.focus();
        printWindow.print();
      }, 80);
    }, { once: true });
    printWindow.addEventListener('afterprint', () => printWindow.close(), { once: true });
  } catch (error) {
    printWindow?.close();
    notifyError(error, 'PDF-Export konnte nicht geöffnet werden.');
  }
}

function documentLabel(document) {
  return document.display_name || document.original_filename || 'Dokument';
}

function documentDisplayLabel(document) {
  return formatDocumentFilename(documentLabel(document));
}

function formatDocumentFilename(filename) {
  const value = String(filename || '').trim();
  if (!value || showFilenameSuffix.value) return value;
  return value.replace(/\.[A-Za-z][A-Za-z0-9]{0,7}$/, '');
}

function documentPickerMeta(document) {
  return [
    document.document_type || 'Dokument',
    formatDocumentDate(document.document_date),
  ].filter(Boolean).join(' · ');
}

function formatDocumentDate(value) {
  if (!value) return 'Ohne Datum';
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return 'Ohne Datum';
  return new Intl.DateTimeFormat('de-DE').format(date);
}

function formatYear(value) {
  const year = new Date(value).getFullYear();
  return Number.isFinite(year) ? String(year) : '';
}

function cancelPendingSave() {
  discardPendingSave = true;
  clearSaveTimer();
}

function resumePendingSave() {
  if (!discardPendingSave) return;
  discardPendingSave = false;
  scheduleSave();
}

function isEmpty() {
  if (loading.value || loadError.value) return null;
  return isNoteEmpty({ title: title.value, body_json: body.value });
}

function flushSave() {
  const pending = Boolean(saveTimer);
  clearSaveTimer();
  if (pending && !discardPendingSave) return persist();
  return Promise.resolve();
}

defineExpose({ cancelPendingSave, resumePendingSave, flushSave, focusEditorBody, focusTitle, isEmpty });

onBeforeUnmount(() => {
  rememberScrollPosition();
  persistScrollPositions();
  if (documentPickerSearchTimer) window.clearTimeout(documentPickerSearchTimer);
  window.removeEventListener('papermind:ai-configuration-changed', loadAICredentialStatus);
  flushSave();
});
</script>

<style scoped>
.note-workspace-editor {
  --pm-note-editor-header-bg: rgba(var(--v-theme-surface), 0.68);
  display: flex;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  background: var(--pm-content-surface, #fff);
}

.note-workspace-editor__bar {
  display: flex;
  box-sizing: border-box;
  height: var(--notes-header-height, 54px);
  min-height: var(--notes-header-height, 54px);
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 7px 16px 7px 7px;
  /* Keine eigene Linie mehr – Titel + Tags bilden EINEN Kopfblock; die einzige
     Trennlinie sitzt unter den Tags (Metazeile) und fluchtet mit dem unteren
     Trenner der linken Filterleiste. */
  background: var(--pm-note-editor-header-bg);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.note-workspace-editor__title {
  min-width: 0;
  flex: 1 1 auto;
  border: 0;
  border-radius: 8px;
  outline: none;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 1.125rem;
  font-weight: 680;
  line-height: 1.25;
  padding: 8px 9px;
  transition: background-color 120ms ease, box-shadow 120ms ease;
}

.note-workspace-editor__title::placeholder {
  color: var(--pm-muted, #535e62);
  opacity: 0.78;
}

.note-workspace-editor__title:hover:not(:disabled) {
  background: color-mix(in srgb, var(--pm-text, #0e181b) 4%, transparent);
}

.note-workspace-editor__title:focus {
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 74%, transparent);
  box-shadow: inset 0 0 0 1px var(--pm-divider, #d8dfe1);
}

.note-workspace-editor__title:disabled {
  opacity: 0.64;
}

.note-workspace-editor__actions {
  display: flex;
  min-width: 0;
  flex: 0 0 auto;
  align-self: center;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.note-workspace-editor__word-count {
  flex: none;
  align-self: center;
  margin-left: auto;
  padding-left: 8px;
  color: var(--pm-muted, #535e62);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* Metadaten-Zeile unter dem Titel: Tags und Dokument links, Wortanzahl rechts.
   Ihre untere Trennlinie fluchtet mit der linken Filterleiste. */
.note-workspace-editor__meta {
  --pm-note-placeholder-chip-border: color-mix(in srgb, var(--pm-muted, #64748b) 55%, transparent);
  --pm-note-placeholder-chip-color: rgba(var(--v-theme-on-surface), 0.6);
  --pm-note-placeholder-chip-font-size: 12.5px;
  --pm-note-placeholder-chip-font-weight: 400;
  --pm-note-placeholder-chip-letter-spacing: 0.012em;
  flex: none;
  display: flex;
  box-sizing: border-box;
  height: var(--notes-meta-row-height, 36px);
  min-height: var(--notes-meta-row-height, 36px);
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  padding: 0 16px;
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
  background: var(--pm-note-editor-header-bg);
}
.note-workspace-editor__meta-main {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}
.note-workspace-editor__meta-main,
.note-workspace-editor__word-count {
  position: relative;
  top: -4px;
}
.note-workspace-editor__meta.is-centered {
  width: 100%;
  max-width: 820px;
  margin-inline: auto;
}
.note-workspace-editor__meta-tags {
  min-width: 0;
  flex: 0 1 auto;
  overflow: hidden;
  /* Keine „Pop"-Animation der Tag-Chips beim Öffnen einer Notiz (nur im
     Editor; TagInlineEditor ist geteilt). Dauer 0 = sofort sichtbar. */
  --pm-tag-chip-enter-duration: 0ms;
  --pm-tag-chip-leave-duration: 0ms;
}
.note-workspace-editor__meta-tags :deep(.pm-tags-input) {
  --pm-detail-chip-add-border: var(--pm-note-placeholder-chip-border);
  width: auto;
  min-width: 0;
  flex-wrap: nowrap;
  gap: 0;
  overflow: hidden;
}
.note-workspace-editor__meta-tags :deep(.pm-tags-input__chips) {
  display: flex;
  min-width: 0;
  flex: 0 1 auto;
  flex-wrap: nowrap;
  gap: 7px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}
.note-workspace-editor__meta-tags :deep(.pm-tags-input__chips:not(:empty)) {
  margin-right: 7px;
}
.note-workspace-editor__meta-tags :deep(.pm-tags-input__add-label) {
  color: var(--pm-note-placeholder-chip-color);
  font-family: inherit;
  font-size: var(--pm-note-placeholder-chip-font-size);
  font-weight: var(--pm-note-placeholder-chip-font-weight);
  letter-spacing: var(--pm-note-placeholder-chip-letter-spacing);
  line-height: normal;
}
.note-workspace-editor__meta-tags :deep(.pm-tags-input__chips::-webkit-scrollbar) {
  display: none;
}
.note-workspace-editor__meta-tags :deep(.pm-tags-input__chip-wrap),
.note-workspace-editor__meta-tags :deep(.pm-tags-input__field) {
  flex: none;
}
/* Beim Notizwechsel soll die Tag-Leiste NICHT aufblitzen: jegliche Transition/
   Animation innerhalb der Leiste abschalten (Chip-Enter/Leave/Move, Feld-Breite,
   gestrichelter Rahmen …). Nur im Editor – das teleportierte Dropdown-Menü und
   die Dokumentenschublade behalten ihre Animationen. */
.note-workspace-editor__meta-tags :deep(*) {
  animation: none !important;
  transition: none !important;
}
/* Ausscheidende Chips sofort aus dem Layout nehmen – sonst verbreitern sie beim
   Wechsel für einen Frame die Leiste (das sichtbare „Aufblitzen"). */
.note-workspace-editor__meta-tags :deep(.metadata-tag-chip-leave-active) {
  display: none !important;
}
.note-workspace-editor__meta-sep {
  width: 1px;
  height: 18px;
  flex: none;
  background: var(--pm-divider, #d8dfe1);
  margin: 0 2px;
}

/* Verknüpftes Dokument als ruhiger Chip (Popover: öffnen/wechseln/lösen). */
.note-workspace-editor__doc-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 260px;
  padding: 3px 9px 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  background: transparent;
  color: var(--pm-text, #0e181b);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.note-workspace-editor__doc-chip:hover {
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.05));
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
}
.note-workspace-editor__doc-chip > .v-icon:first-child { color: var(--pm-muted, #64748b); flex: none; }
.note-workspace-editor__doc-chip-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.note-workspace-editor__doc-chip--empty {
  box-sizing: border-box;
  height: 26px;
  border: 1px dashed var(--pm-note-placeholder-chip-border);
  border-radius: 15px;
  color: var(--pm-note-placeholder-chip-color);
  font-family: inherit;
  font-size: var(--pm-note-placeholder-chip-font-size);
  font-weight: var(--pm-note-placeholder-chip-font-weight);
  letter-spacing: var(--pm-note-placeholder-chip-letter-spacing);
  line-height: normal;
}
.note-workspace-editor__doc-chip--empty:hover {
  border-color: var(--pm-note-placeholder-chip-border);
  color: var(--pm-accent-strong, #00555f);
}

@media (prefers-reduced-motion: reduce) {
  .note-workspace-editor__doc-chip { transition: none; }
}

.note-workspace-editor__view-divider {
  width: 1px;
  height: 20px;
  flex: none;
  margin: 0 4px 0 6px;
  background: var(--pm-divider, #d8dfe1);
}

/* Der 20-px-Glyph sitzt im 36-px-Button jeweils 8 px eingerückt. Der negative
   Außenabstand richtet seine sichtbare rechte Kante an der Wortanzahl aus. */
.note-workspace-editor__list-toggle {
  margin-right: -8px;
}

.note-workspace-editor__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

/* Rückverweise: Notizen, die auf diese Notiz verweisen */
.note-workspace-editor__backlinks {
  padding: 14px clamp(20px, 5vw, 56px) 48px;
}
.note-workspace-editor__backlinks.is-centered {
  max-width: 820px;
  margin-inline: auto;
}
.note-workspace-editor__backlinks-heading {
  display: flex;
  align-items: center;
  gap: 7px;
  padding-top: 14px;
  border-top: 1px solid var(--pm-divider, #d8dfe1);
  color: var(--pm-muted, #748084);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.note-workspace-editor__backlinks-count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 100px;
  background: var(--pm-viewer-surface, #eef2f4);
  color: var(--pm-muted, #535e62);
  font-size: 0.7rem;
  text-align: center;
}
.note-workspace-editor__backlinks-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}
.note-workspace-editor__backlink {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px;
  background: var(--pm-app-surface, #fff);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: border-color 120ms ease, background 120ms ease;
}
.note-workspace-editor__backlink:hover {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.04));
}
.note-workspace-editor__backlink-title {
  color: var(--pm-text, #0e181b);
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.note-workspace-editor__backlink-title.is-untitled { color: var(--pm-muted); font-style: italic; font-weight: 500; }
.note-workspace-editor__backlink-snippet {
  color: var(--pm-muted, #535e62);
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (prefers-reduced-motion: reduce) {
  .note-workspace-editor__backlink { transition: none; }
}

.note-workspace-editor__body.is-centered :deep(.pm-content) {
  box-sizing: border-box;
  width: 100%;
  margin-inline: auto;
}

.note-workspace-editor__document-popover {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  border-radius: 12px;
  color: rgb(var(--v-theme-on-surface));
}

.note-workspace-editor__document-popover-summary {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  align-items: center;
  gap: 11px;
  padding: 12px 14px;
}

.note-workspace-editor__document-popover-summary img {
  box-sizing: border-box;
  width: 38px;
  height: 48px;
  object-fit: cover;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.note-workspace-editor__document-popover-summary span {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.note-workspace-editor__document-popover-summary strong,
.note-workspace-editor__document-popover-summary small {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.note-workspace-editor__document-popover-summary strong {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.84rem;
}

.note-workspace-editor__document-popover-summary small {
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.72rem;
}

.note-workspace-editor__picker-progress {
  margin-top: 12px;
}

.note-workspace-editor__picker-list {
  max-height: 420px;
  margin-top: 14px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 11px;
  background: rgba(var(--v-theme-on-surface), 0.018);
}

.note-workspace-editor__picker-row {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 24px;
  width: 100%;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  background: transparent;
  color: rgb(var(--v-theme-on-surface));
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.note-workspace-editor__picker-row:last-of-type {
  border-bottom: 0;
}

.note-workspace-editor__picker-row:hover {
  background: rgba(var(--v-theme-on-surface), 0.055);
}

.note-workspace-editor__picker-row.is-selected {
  background: rgba(var(--v-theme-primary), 0.12);
}

.note-workspace-editor__picker-row:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}

.note-workspace-editor__picker-row img {
  box-sizing: border-box;
  width: 38px;
  height: 48px;
  object-fit: cover;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.18);
  border-radius: 3px;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.note-workspace-editor__picker-row span {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.note-workspace-editor__picker-row strong {
  overflow: hidden;
  font-size: 0.8rem;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.note-workspace-editor__picker-row small {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.7rem;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.note-workspace-editor__picker-row > .v-icon {
  color: rgba(var(--v-theme-on-surface), 0.46);
}

.note-workspace-editor__picker-row.is-selected > .v-icon {
  color: rgb(var(--v-theme-primary));
}

.note-workspace-editor__picker-empty {
  padding: 30px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.82rem;
  text-align: center;
}

.note-workspace-editor__picker-empty[role="alert"] {
  color: rgb(var(--v-theme-error));
}

.note-workspace-editor__state {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  color: var(--pm-muted, #535e62);
  font-size: 0.84rem;
  text-align: center;
}

.note-workspace-editor__state--error {
  color: var(--pm-danger, #c84c4c);
}

.note-workspace-editor__state--error button {
  border: 0;
  background: transparent;
  color: var(--pm-accent, #006b75);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}

@media (max-width: 1080px) {
  .note-workspace-editor__bar {
    gap: 8px;
    padding-left: 7px;
  }

}
</style>
