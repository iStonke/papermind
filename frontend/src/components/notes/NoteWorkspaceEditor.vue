<!--
  Eingebetteter Notizen-Editor für die rechte Workspace-Spalte. Titel und Body
  werden beim Wechsel geladen und anschließend verzögert gespeichert. Kleine
  UI-Metadaten zum verknüpften Dokument liegen in den Attributen des
  ProseMirror-Wurzeldokuments und werden zusammen mit body_json persistiert.
-->
<template>
  <section
    class="note-workspace-editor"
    :aria-busy="loading || switching ? 'true' : undefined"
    @keydown.capture="handleWorkspaceKeydown"
  >
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
        :readonly="switching || status === 'conflict'"
        @keydown.enter.prevent="focusEditorBody"
      />

      <div class="note-workspace-editor__actions">
        <v-btn
          class="note-workspace-editor__navigation-toggle"
          :class="['pm-header-icon-btn', 'pm-header-icon-btn--quiet']"
          :variant="findBarOpen ? 'tonal' : 'text'"
          icon
          aria-label="Suchen und ersetzen"
          title="Suchen und ersetzen (⌘/Strg+F)"
          :aria-pressed="findBarOpen"
          :disabled="!hasLoadedContent"
          @click="toggleFindBar"
        >
          <v-icon size="20">mdi-magnify</v-icon>
        </v-btn>

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

        <v-menu location="bottom end" :offset="8" transition="fade-transition">
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

          <v-list
            class="note-workspace-editor__more-menu"
            density="compact"
            min-width="228"
            role="menu"
            aria-label="Notizaktionen"
          >
            <div class="note-workspace-editor__more-label">Aktionen</div>
            <v-list-item
              class="note-workspace-editor__more-item"
              title="Als Vorlage speichern"
              :disabled="savingTemplate"
              :ripple="false"
              role="menuitem"
              @click="saveCurrentNoteAsTemplate"
            >
              <template #prepend>
                <span class="note-workspace-editor__more-icon" aria-hidden="true">
                  <v-icon size="17">mdi-file-document-plus-outline</v-icon>
                </span>
              </template>
            </v-list-item>
            <v-list-item
              class="note-workspace-editor__more-item"
              title="Versionsverlauf"
              :ripple="false"
              role="menuitem"
              @click="openVersionHistory"
            >
              <template #prepend>
                <span class="note-workspace-editor__more-icon" aria-hidden="true">
                  <v-icon size="17">mdi-history</v-icon>
                </span>
              </template>
            </v-list-item>
            <v-list-item
              class="note-workspace-editor__more-item"
              title="Tastenkürzel"
              :ripple="false"
              role="menuitem"
              @click="openNoteShortcuts"
            >
              <template #prepend>
                <span class="note-workspace-editor__more-icon" aria-hidden="true">
                  <v-icon size="17">mdi-keyboard-outline</v-icon>
                </span>
              </template>
              <template #append>
                <span class="note-workspace-editor__more-hint">{{ shortcutsHint }}</span>
              </template>
            </v-list-item>

            <div class="note-workspace-editor__more-group-label">Exportieren</div>
            <v-list-item
              class="note-workspace-editor__more-item"
              title="Markdown"
              :ripple="false"
              role="menuitem"
              @click="exportNoteAsMarkdown"
            >
              <template #prepend>
                <span class="note-workspace-editor__more-icon" aria-hidden="true">
                  <v-icon size="17">mdi-file-document-outline</v-icon>
                </span>
              </template>
            </v-list-item>
            <v-list-item
              class="note-workspace-editor__more-item"
              title="PDF"
              :disabled="exportingPdf"
              :ripple="false"
              role="menuitem"
              @click="exportNoteAsPdf"
            >
              <template #prepend>
                <span class="note-workspace-editor__more-icon" aria-hidden="true">
                  <v-icon size="17">mdi-file-pdf-box</v-icon>
                </span>
              </template>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>
    </header>

    <div v-if="hasLoadedContent" class="note-workspace-editor__meta">
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
        <NoteNotebookChip
          :note-id="noteId"
          :notebook-id="noteNotebookId"
          :disabled="!hasLoadedContent || loading || switching || loadedNoteId !== noteId"
        />
      </div>

      <div
        v-if="syncIssueVisible"
        class="note-workspace-editor__sync"
        :class="`is-${status}`"
        role="status"
        aria-live="polite"
      >
        <v-icon size="14">{{ syncStatusIcon }}</v-icon>
        <span class="note-workspace-editor__sync-label">{{ syncStatusLabel }}</span>
        <template v-if="status === 'conflict'">
          <button type="button" @click="useLocalConflictDraft">Entwurf verwenden</button>
          <button type="button" @click="keepServerVersion">Serverstand</button>
        </template>
        <button v-else-if="status === 'error'" type="button" @click="retrySave">Erneut versuchen</button>
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

    <div v-else class="note-workspace-editor__main">
      <div
        ref="scrollContainerRef"
        class="note-workspace-editor__scroll"
        @scroll.passive="rememberScrollPosition()"
      >
        <NoteEditor
          ref="noteEditorRef"
          class="note-workspace-editor__body"
          :class="{ 'is-fullscreen': !listVisible }"
          v-model="body"
          workspace
          :note-id="loadedNoteId"
          :document-items="slashDocuments"
          :link-targets="linkTargets"
          :block-templates="notesStore.blockTemplates"
          :writing-width="notesWritingWidth"
          :paragraph-spacing="notesParagraphSpacing"
          :font-family="notesFontFamily"
          :spellcheck-enabled="notesSpellcheckEnabled"
          :readonly="status === 'conflict'"
          :ai-available="aiAvailable"
          :ai-prompt-suggestions="aiPromptSuggestions"
          @word-count="updateWordCount"
          @change="scheduleSave"
          @history-checkpoint="markHistoryCheckpoint"
          @note-search-state="applyNoteSearchState"
          @save-block-template="onSaveBlockTemplate"
          @image-upload-error="onImageUploadError"
        />

        <section
          v-if="backlinks.length"
          class="note-workspace-editor__backlinks"
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

      <!-- Schwebende Suchen-&-Ersetzen-Leiste (oben rechts, ueberlagert den
           Editor). Nutzt dieselbe noteSearch-Engine wie zuvor die Seitenleiste;
           die rechte Navigator-Leiste (Gliederung + Suche) ist entfallen. -->
      <Transition name="note-find">
        <div
          v-if="findBarOpen"
          class="note-workspace-editor__find"
          role="search"
          aria-label="In dieser Notiz suchen und ersetzen"
        >
          <div class="note-workspace-editor__find-row">
            <button
              type="button"
              class="note-workspace-editor__find-expand"
              :class="{ 'is-open': replaceExpanded }"
              :aria-expanded="replaceExpanded"
              aria-label="Ersetzen ein- oder ausklappen"
              title="Ersetzen ein-/ausklappen"
              @click="toggleReplaceRow"
            ><v-icon size="16">{{ replaceExpanded ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon></button>
            <label class="note-workspace-editor__find-field">
              <v-icon size="15" aria-hidden="true">mdi-magnify</v-icon>
              <input
                ref="noteSearchInputRef"
                v-model="noteSearchQuery"
                type="text"
                autocomplete="off"
                spellcheck="false"
                placeholder="Suchen"
                aria-label="Suchbegriff in dieser Notiz"
                @keydown.enter.prevent="moveNoteSearch($event.shiftKey ? -1 : 1)"
                @keydown.esc.prevent="closeFindBar"
              />
            </label>
            <span class="note-workspace-editor__find-count" aria-live="polite">{{ findCountLabel }}</span>
            <button
              type="button"
              class="note-workspace-editor__find-nav"
              aria-label="Vorheriger Treffer"
              title="Vorheriger Treffer (Shift+Enter)"
              :disabled="!noteSearchCount"
              @click="moveNoteSearch(-1)"
            ><v-icon size="18">mdi-chevron-up</v-icon></button>
            <button
              type="button"
              class="note-workspace-editor__find-nav"
              aria-label="Naechster Treffer"
              title="Naechster Treffer (Enter)"
              :disabled="!noteSearchCount"
              @click="moveNoteSearch(1)"
            ><v-icon size="18">mdi-chevron-down</v-icon></button>
            <span class="note-workspace-editor__find-sep" aria-hidden="true"></span>
            <button
              type="button"
              class="note-workspace-editor__find-nav"
              aria-label="Suche schliessen"
              title="Schliessen (Esc)"
              @click="closeFindBar"
            ><v-icon size="18">mdi-close</v-icon></button>
          </div>
          <div v-if="replaceExpanded" class="note-workspace-editor__find-row note-workspace-editor__find-row--replace">
            <label class="note-workspace-editor__find-field">
              <input
                ref="replaceInputRef"
                v-model="replaceValue"
                type="text"
                autocomplete="off"
                spellcheck="false"
                placeholder="Ersetzen durch"
                aria-label="Ersatztext"
                @keydown.enter.prevent="doReplaceActive"
                @keydown.esc.prevent="closeFindBar"
              />
            </label>
            <button
              type="button"
              class="note-workspace-editor__find-replace"
              :disabled="!noteSearchCount"
              @click="doReplaceActive"
            >Ersetzen</button>
            <button
              type="button"
              class="note-workspace-editor__find-replace is-primary"
              :disabled="!noteSearchCount"
              @click="doReplaceAll"
            >Alle</button>
          </div>
        </div>
      </Transition>
    </div>

    <NoteVersionHistoryDialog
      v-if="loadedNoteId"
      v-model="historyOpen"
      :note-id="loadedNoteId"
      :current-revision="serverRevision"
      :restoring="historyRestoring"
      @restore="restoreHistoryRevision"
    />

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
import { downloadNotePdf } from '../../utils/notePdfDownload.js';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, toRaw, watch } from 'vue';
import { documentThumbnailUrl, listDocuments } from '../../api/documents.js';
import { authedUrl, getBaseUrl } from '../../api/client.js';
import { getAICredentialStatus } from '../../api/aiCredentials.js';
import { useSettingsStore } from '../../stores/settings.js';
import { useUiStore } from '../../stores/ui.js';
import { isNoteEmpty, useNotesStore } from '../../stores/notes.js';
import { checkpointNoteRevision, getNoteBacklinks } from '../../api/notes.js';
import { useCorrespondentStore } from '../../stores/correspondents.js';
import { useDossierStore } from '../../stores/dossiers.js';
import { useTagStore } from '../../stores/tags.js';
import { notifyError, useNotifications } from '../../stores/notifications.js';
import { NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT } from '../../constants/promptDefaults.js';
import {
  createNoteDraftVersion,
  deleteNoteDraft,
  getNoteDraft,
  latestKnownNoteRevision,
  noteDraftMatchesServer,
  putNoteDraft,
} from '../../utils/noteDraftStorage.js';
import {
  noteExportFilename,
  noteToMarkdown,
  noteToPrintableHtml,
} from '../../utils/noteExport.js';
import { nextWrappedIndex } from '../../utils/noteNavigation.js';
import BaseDialog from '../BaseDialog.vue';
import PmActionIcon from '../PmActionIcon.vue';
import NoteEditor from './NoteEditor.vue';
import NoteTagBar from './NoteTagBar.vue';
import NoteNotebookChip from './NoteNotebookChip.vue';
import NoteVersionHistoryDialog from './NoteVersionHistoryDialog.vue';

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
const historyOpen = ref(false);
const historyRestoring = ref(false);
const correspondentStore = useCorrespondentStore();
const dossierStore = useDossierStore();
const tagStore = useTagStore();
// Tags der geladenen Notiz (gemeinsames PaperMind-Vokabular).
const noteTagIds = ref([]);
const noteNotebookId = ref(null);
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

// Kürzel-Hinweis im ⋮-Menü: plattformgerecht (⌘ auf Mac, sonst Strg).
const shortcutsHint = (typeof navigator !== 'undefined'
  && /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent || ''))
  ? '⌘ /'
  : 'Strg /';
function openNoteShortcuts() {
  noteEditorRef.value?.openShortcuts?.();
}
const titleInputRef = ref(null);
const noteSearchInputRef = ref(null);
const replaceInputRef = ref(null);
const title = ref('');
const body = ref(EMPTY_DOC);
const wordCount = ref(0);
const findBarOpen = ref(false);
const replaceExpanded = ref(false);
const replaceValue = ref('');
const noteSearchQuery = ref('');
const noteSearchCount = ref(0);
const noteSearchActiveIndex = ref(-1);
const hasNoteSearchQuery = computed(() => Boolean(noteSearchQuery.value.trim()));
const findCountLabel = computed(() => (
  hasNoteSearchQuery.value
    ? `${noteSearchCount.value ? noteSearchActiveIndex.value + 1 : 0}/${noteSearchCount.value}`
    : ''
));
const status = ref('idle');
const serverRevision = ref(1);
const currentDraftVersion = ref(null);
const hasUnsyncedChanges = ref(false);
const localDraftSaved = ref(false);
const conflictingDraft = ref(null);
const conflictServerNote = ref(null);
const lastSaveError = ref(null);
const isOnline = ref(navigatorOnline());
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
let currentSnapshot = null;
let scrollPositionSaveTimer = null;
let documentPickerSearchTimer = null;
let documentPickerRevision = 0;
let loadRevision = 0;
let discardPendingSave = false;
let pendingEditorFocusRequest = null;
const savePipelines = new Map();

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
const syncIssueVisible = computed(() => ['error', 'conflict', 'local'].includes(status.value));
const syncStatusIcon = computed(() => ({
  conflict: 'mdi-alert-outline',
  error: isOnline.value ? 'mdi-cloud-sync-outline' : 'mdi-cloud-outline',
  local: 'mdi-content-save-outline',
}[status.value] || 'mdi-cloud-outline'));
const syncStatusLabel = computed(() => {
  if (status.value === 'conflict') return 'Lokaler Entwurf und Serverstand unterscheiden sich';
  if (status.value === 'local') return 'Lokaler Entwurf wiederhergestellt';
  if (status.value === 'error') {
    if (!isOnline.value) return localDraftSaved.value ? 'Offline · lokal gesichert' : 'Offline · nicht gesichert';
    return localDraftSaved.value ? 'Nicht synchronisiert · lokal gesichert' : 'Nicht synchronisiert';
  }
  return '';
});
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

watch(() => props.noteId, (noteId) => {
  if (pendingEditorFocusRequest?.noteId !== noteId) pendingEditorFocusRequest = null;
  resetNoteNavigationForNote();
  loadNote(noteId);
}, { immediate: true });

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

watch(noteSearchQuery, (query) => {
  if (!findBarOpen.value) return;
  runNoteSearch(query, 0);
});

function handleWorkspaceKeydown(event) {
  if (
    event.key?.toLocaleLowerCase() !== 'f'
    || (!event.metaKey && !event.ctrlKey)
    || event.altKey
    || !hasLoadedContent.value
  ) return;
  event.preventDefault();
  event.stopPropagation();
  openFindBar();
}

function openFindBar({ replace = false } = {}) {
  findBarOpen.value = true;
  if (replace) replaceExpanded.value = true;
  nextTick(() => {
    if (noteSearchQuery.value.trim()) {
      runNoteSearch(noteSearchQuery.value, Math.max(0, noteSearchActiveIndex.value));
    }
    noteSearchInputRef.value?.focus();
    noteSearchInputRef.value?.select();
  });
}

function closeFindBar() {
  findBarOpen.value = false;
  replaceExpanded.value = false;
  noteSearchCount.value = 0;
  noteSearchActiveIndex.value = -1;
  noteEditorRef.value?.clearNoteSearch?.();
}

function toggleFindBar() {
  if (findBarOpen.value) closeFindBar();
  else openFindBar();
}

function toggleReplaceRow() {
  replaceExpanded.value = !replaceExpanded.value;
  if (replaceExpanded.value) nextTick(() => replaceInputRef.value?.focus());
}

function doReplaceActive() {
  if (!noteSearchCount.value) return;
  const result = noteEditorRef.value?.replaceActiveNoteSearch?.(replaceValue.value);
  if (result) {
    noteSearchCount.value = result.count;
    noteSearchActiveIndex.value = result.activeIndex;
  }
}

function doReplaceAll() {
  if (!noteSearchCount.value) return;
  const result = noteEditorRef.value?.replaceAllNoteSearch?.(replaceValue.value);
  if (result) {
    noteSearchCount.value = result.count;
    noteSearchActiveIndex.value = result.activeIndex;
  }
}

function resetNoteNavigationForNote() {
  findBarOpen.value = false;
  replaceExpanded.value = false;
  noteSearchQuery.value = '';
  replaceValue.value = '';
  noteSearchCount.value = 0;
  noteSearchActiveIndex.value = -1;
  noteEditorRef.value?.clearNoteSearch?.();
}

function runNoteSearch(query, activeIndex = 0) {
  const result = noteEditorRef.value?.searchInNote?.(query, activeIndex);
  if (!result) {
    noteSearchCount.value = 0;
    noteSearchActiveIndex.value = -1;
    return;
  }
  noteSearchCount.value = result.count;
  noteSearchActiveIndex.value = result.activeIndex;
}

function applyNoteSearchState(state) {
  if (String(state?.query || '') !== noteSearchQuery.value.trim()) return;
  noteSearchCount.value = Math.max(0, Number(state?.count) || 0);
  noteSearchActiveIndex.value = noteSearchCount.value
    ? Math.max(0, Number(state?.activeIndex) || 0)
    : -1;
}

function moveNoteSearch(direction) {
  if (!noteSearchQuery.value.trim() || !noteSearchCount.value) return;
  const nextIndex = nextWrappedIndex(
    noteSearchActiveIndex.value,
    noteSearchCount.value,
    direction,
  );
  const result = noteEditorRef.value?.selectNoteSearchResult?.(nextIndex);
  if (result) {
    noteSearchCount.value = result.count;
    noteSearchActiveIndex.value = result.activeIndex;
  }
}

async function loadNote(noteId = props.noteId) {
  const revision = ++loadRevision;
  if (loadedNoteId.value && loadedNoteId.value !== noteId) {
    const previousNoteId = loadedNoteId.value;
    rememberScrollPosition(previousNoteId);
    void finalizeHistory(previousNoteId, 'navigation');
  }
  discardPendingSave = false;
  loadError.value = false;
  const cachedNote = notesStore.peek(noteId);
  if (cachedNote) {
    await applyLoadedNote(cachedNote, noteId);
    if (revision !== loadRevision) return;
    loading.value = false;
    switching.value = false;
    return;
  }

  loading.value = !hasLoadedContent.value;
  switching.value = hasLoadedContent.value;
  try {
    const note = await notesStore.get(noteId);
    if (revision !== loadRevision) return;
    await applyLoadedNote(note, noteId);
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

async function applyLoadedNote(note, noteId) {
  const loadedRevision = Math.max(1, Number(note?.revision) || 1);
  let localDraft = null;
  try {
    localDraft = await getNoteDraft(noteId);
  } catch {
    // Der Serverstand bleibt auch ohne verfügbare IndexedDB vollständig nutzbar.
  }
  if (noteId !== props.noteId) return;

  const pendingPipeline = savePipelines.get(noteId);
  if (localDraft && noteDraftMatchesServer(localDraft, note) && !pendingPipeline?.running) {
    void deleteNoteDraft(noteId, localDraft.clientVersion).catch(() => {});
    localDraft = null;
  }

  const canRestoreDraft = localDraft
    && Number(localDraft.baseRevision) === loadedRevision;
  const hasDraftConflict = localDraft && !canRestoreDraft;
  loadingContent = true;
  title.value = canRestoreDraft ? String(localDraft.title || '') : (note?.title || '');
  body.value = normalizeBody(canRestoreDraft ? localDraft.bodyJson : note?.body_json);
  noteTagSeed.value = Array.isArray(note?.tags) ? note.tags : [];
  noteTagIds.value = noteTagSeed.value.map((t) => t.id);
  noteNotebookId.value = note?.notebook_id ?? null;
  loadedNoteId.value = noteId;
  serverRevision.value = loadedRevision;
  currentDraftVersion.value = canRestoreDraft ? localDraft.clientVersion : null;
  currentSnapshot = canRestoreDraft ? localDraft : null;
  hasUnsyncedChanges.value = Boolean(canRestoreDraft);
  localDraftSaved.value = Boolean(localDraft);
  conflictingDraft.value = hasDraftConflict ? localDraft : null;
  conflictServerNote.value = hasDraftConflict ? note : null;
  lastSaveError.value = null;
  hasLoadedContent.value = true;
  status.value = hasDraftConflict ? 'conflict' : (canRestoreDraft ? 'local' : 'saved');
  nextTick(() => {
    loadingContent = false;
    if (loadedNoteId.value !== noteId) return;
    restoreScrollPosition(noteId);
    if (canRestoreDraft) scheduleRecoveredDraftSave();
    // NoteEditor übernimmt den neuen modelValue-Inhalt in einem eigenen
    // Watcher und verwirft dabei absichtlich die alte DOM-Auswahl. Erst im
    // darauffolgenden Tick darf eine angeforderte Schreibmarke gesetzt werden.
    void nextTick(() => flushPendingEditorFocus(noteId));
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

function navigatorOnline() {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

function cloneBodyForSave(value) {
  const normalized = normalizeBody(value);
  // body.value ist ein reaktives Vue-Objekt. `toRaw` entpackt den Proxy VOR der
  // Serialisierung: sonst löst JSON.stringify pro Anschlag das Deep-Proxying des
  // gesamten Dokumentbaums aus (jede verschachtelte Node wird beim Zugriff in
  // einen reaktiven Proxy gehüllt) – teuer bei langen Notizen. Auf dem rohen
  // POJO ist es eine reine Plain-Traversierung. Der JSON-Roundtrip bleibt, weil
  // er eine klonbare, reaktivitätsfreie Momentaufnahme liefert (structuredClone
  // würde an übrig gebliebenen Proxys scheitern).
  return JSON.parse(JSON.stringify(toRaw(normalized)));
}

function createCurrentSnapshot({ clientVersion = createNoteDraftVersion() } = {}) {
  const noteId = loadedNoteId.value;
  if (!noteId) return null;
  return {
    noteId,
    title: title.value,
    bodyJson: cloneBodyForSave(body.value),
    baseRevision: serverRevision.value,
    clientVersion,
    savedAt: Date.now(),
    historyReason: 'autosave',
  };
}

function persistLocalSnapshot(snapshot) {
  snapshot.localWritePromise = putNoteDraft(snapshot)
    .then(() => {
      if (loadedNoteId.value === snapshot.noteId && currentDraftVersion.value === snapshot.clientVersion) {
        localDraftSaved.value = true;
      }
      return true;
    })
    .catch(() => {
      if (loadedNoteId.value === snapshot.noteId && currentDraftVersion.value === snapshot.clientVersion) {
        localDraftSaved.value = false;
      }
      return false;
    });
  return snapshot.localWritePromise;
}

function stageLocalDraft() {
  const snapshot = createCurrentSnapshot();
  if (!snapshot) return null;
  currentSnapshot = snapshot;
  currentDraftVersion.value = snapshot.clientVersion;
  hasUnsyncedChanges.value = true;
  localDraftSaved.value = false;
  conflictingDraft.value = null;
  conflictServerNote.value = null;
  lastSaveError.value = null;
  persistLocalSnapshot(snapshot);
  return snapshot;
}

function scheduleSave() {
  if (
    loadingContent
    || switching.value
    || loading.value
    || loadError.value
    || discardPendingSave
    || status.value === 'conflict'
  ) return;
  stageLocalDraft();
  status.value = 'saving';
  clearSaveTimer();
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    void persist();
  }, 650);
}

function scheduleRecoveredDraftSave() {
  if (!currentSnapshot || discardPendingSave) return;
  currentSnapshot.localWritePromise = Promise.resolve(true);
  clearSaveTimer();
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    void persist();
  }, 450);
}

function updateWordCount(value) {
  wordCount.value = Number.isFinite(value) ? value : 0;
}

function pipelineFor(snapshot) {
  let pipeline = savePipelines.get(snapshot.noteId);
  if (!pipeline) {
    const activeRevision = snapshot.noteId === loadedNoteId.value
      ? serverRevision.value
      : snapshot.baseRevision;
    pipeline = {
      noteId: snapshot.noteId,
      // Ein Snapshot kann während des vorherigen Requests entstanden sein und
      // deshalb noch dessen alte Basisrevision tragen. Für eine neue Pipeline
      // gilt immer der jüngste bereits bestätigte Stand dieses Editors.
      serverRevision: latestKnownNoteRevision(snapshot.baseRevision, activeRevision),
      latest: null,
      currentVersion: null,
      running: false,
      promise: Promise.resolve(),
    };
    savePipelines.set(snapshot.noteId, pipeline);
  }
  return pipeline;
}

function enqueueSnapshot(snapshot) {
  if (!snapshot) return Promise.resolve();
  const pipeline = pipelineFor(snapshot);
  if (
    pipeline.currentVersion === snapshot.clientVersion
    || pipeline.latest?.clientVersion === snapshot.clientVersion
  ) return pipeline.promise;
  pipeline.latest = snapshot;
  if (pipeline.running) return pipeline.promise;
  pipeline.running = true;
  pipeline.promise = drainSavePipeline(pipeline).finally(() => {
    pipeline.running = false;
    savePipelines.delete(pipeline.noteId);
  });
  return pipeline.promise;
}

async function drainSavePipeline(pipeline) {
  while (pipeline.latest) {
    const snapshot = pipeline.latest;
    pipeline.latest = null;
    pipeline.currentVersion = snapshot.clientVersion;
    await (snapshot.localWritePromise || Promise.resolve());
    try {
      const updated = await notesStore.update(snapshot.noteId, {
        title: snapshot.title,
        body_json: snapshot.bodyJson,
        base_revision: pipeline.serverRevision,
        history_reason: snapshot.historyReason || 'autosave',
      });
      pipeline.serverRevision = Math.max(
        pipeline.serverRevision + 1,
        Number(updated?.revision) || 1,
      );
      await deleteNoteDraft(snapshot.noteId, snapshot.clientVersion).catch(() => false);

      if (snapshot.noteId === loadedNoteId.value) {
        serverRevision.value = pipeline.serverRevision;
        const pendingSnapshot = currentSnapshot;
        if (
          pendingSnapshot?.noteId === snapshot.noteId
          && pendingSnapshot.clientVersion !== snapshot.clientVersion
          && Number(pendingSnapshot.baseRevision) < pipeline.serverRevision
        ) {
          // Der neuere lokale Entwurf baut logisch auf dem soeben bestätigten
          // Save auf. Revision auch in IndexedDB nachziehen, damit ein Reload
          // in diesem kurzen Zwischenfenster keinen falschen Konflikt meldet.
          pendingSnapshot.baseRevision = pipeline.serverRevision;
          persistLocalSnapshot(pendingSnapshot);
        }
        if (currentDraftVersion.value === snapshot.clientVersion) {
          currentSnapshot = null;
          currentDraftVersion.value = null;
          hasUnsyncedChanges.value = false;
          localDraftSaved.value = false;
          lastSaveError.value = null;
          status.value = 'saved';
        }
      }
    } catch (error) {
      pipeline.latest = null;
      if (snapshot.noteId === loadedNoteId.value) {
        lastSaveError.value = error;
        hasUnsyncedChanges.value = true;
        if (error?.status === 409) {
          serverRevision.value = Math.max(
            1,
            Number(error?.details?.current_revision) || pipeline.serverRevision,
          );
          conflictingDraft.value = snapshot;
          try {
            conflictServerNote.value = await notesStore.get(snapshot.noteId, { refresh: true });
            serverRevision.value = Math.max(
              serverRevision.value,
              Number(conflictServerNote.value?.revision) || 1,
            );
            // Die vorige PATCH-Antwort kann auf dem Rückweg verloren gegangen
            // sein. Stimmt der Serverinhalt bereits exakt mit dem Entwurf
            // überein, ist das kein echter Konflikt.
            if (noteDraftMatchesServer(snapshot, conflictServerNote.value)) {
              await deleteNoteDraft(snapshot.noteId, snapshot.clientVersion).catch(() => false);
              currentSnapshot = null;
              currentDraftVersion.value = null;
              hasUnsyncedChanges.value = false;
              localDraftSaved.value = false;
              conflictingDraft.value = null;
              conflictServerNote.value = null;
              lastSaveError.value = null;
              status.value = 'saved';
              break;
            }
          } catch {
            conflictServerNote.value = null;
          }
          status.value = 'conflict';
        } else {
          status.value = 'error';
        }
      }
      break;
    } finally {
      pipeline.currentVersion = null;
    }
  }
}

function persist() {
  if (loadingContent || discardPendingSave || !loadedNoteId.value) return Promise.resolve();
  const snapshot = currentSnapshot || stageLocalDraft();
  if (!snapshot) return Promise.resolve();
  status.value = 'saving';
  return enqueueSnapshot(snapshot);
}

function retrySave() {
  if (!hasUnsyncedChanges.value || status.value === 'conflict') return;
  clearSaveTimer();
  void persist();
}

async function useLocalConflictDraft() {
  const draft = conflictingDraft.value;
  if (!draft || !loadedNoteId.value) return;
  loadingContent = true;
  title.value = String(draft.title || '');
  body.value = normalizeBody(draft.bodyJson);
  await nextTick();
  loadingContent = false;
  conflictingDraft.value = null;
  conflictServerNote.value = null;
  const snapshot = stageLocalDraft();
  status.value = 'local';
  if (snapshot) {
    clearSaveTimer();
    saveTimer = window.setTimeout(() => {
      saveTimer = null;
      void persist();
    }, 120);
  }
}

async function keepServerVersion() {
  const noteId = loadedNoteId.value;
  if (!noteId) return;
  let serverNote = conflictServerNote.value;
  if (!serverNote) {
    try {
      serverNote = await notesStore.get(noteId, { refresh: true });
    } catch (error) {
      lastSaveError.value = error;
      status.value = 'error';
      return;
    }
  }
  loadingContent = true;
  title.value = serverNote.title || '';
  body.value = normalizeBody(serverNote.body_json);
  serverRevision.value = Math.max(1, Number(serverNote.revision) || 1);
  await nextTick();
  loadingContent = false;
  const draftVersion = conflictingDraft.value?.clientVersion || currentDraftVersion.value;
  await deleteNoteDraft(noteId, draftVersion).catch(() => false);
  currentSnapshot = null;
  currentDraftVersion.value = null;
  hasUnsyncedChanges.value = false;
  localDraftSaved.value = false;
  conflictingDraft.value = null;
  conflictServerNote.value = null;
  lastSaveError.value = null;
  status.value = 'saved';
}

function markHistoryCheckpoint(reason = 'manual') {
  if (!['ai', 'manual'].includes(reason) || status.value === 'conflict') return;
  const snapshot = currentSnapshot || stageLocalDraft();
  if (!snapshot) return;
  snapshot.historyReason = reason;
  clearSaveTimer();
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    void persist();
  }, 80);
}

async function finalizeHistory(noteId, reason) {
  if (!noteId) return;
  try {
    await flushSave();
    await checkpointNoteRevision(noteId, reason);
  } catch {
    // Verlaufspunkte sind Best Effort. Ein nicht synchronisierter Inhalt bleibt
    // weiterhin durch den lokalen Entwurf und die Autosave-Fehleranzeige sicher.
  }
}

async function openVersionHistory() {
  const noteId = loadedNoteId.value;
  if (!noteId || historyOpen.value) return;
  await finalizeHistory(noteId, 'manual');
  if (loadedNoteId.value === noteId) historyOpen.value = true;
}

async function restoreHistoryRevision(revision) {
  const noteId = loadedNoteId.value;
  if (!noteId || !revision?.id || historyRestoring.value) return;
  historyRestoring.value = true;
  try {
    await flushSave();
    if (status.value === 'error' || status.value === 'conflict') {
      throw lastSaveError.value || new Error('Die Notiz ist noch nicht synchronisiert.');
    }
    const restored = await notesStore.restoreRevision(noteId, revision.id, serverRevision.value);
    await deleteNoteDraft(noteId).catch(() => false);
    await applyLoadedNote(restored, noteId);
    historyOpen.value = false;
    notify({
      type: 'success',
      title: 'Stand wiederhergestellt',
      message: `Version vom ${new Intl.DateTimeFormat('de-DE', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(revision.updated_at))} ist wieder aktiv.`,
      critical: true,
    });
  } catch (error) {
    if (error?.status === 409) {
      serverRevision.value = Math.max(
        serverRevision.value,
        Number(error?.details?.current_revision) || 1,
      );
    }
    notifyError(error, 'Der ausgewählte Stand konnte nicht wiederhergestellt werden.');
  } finally {
    historyRestoring.value = false;
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
    if (status.value === 'error' || status.value === 'conflict') {
      throw lastSaveError.value || new Error('Die Notiz ist noch nicht synchronisiert.');
    }
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

// Aktuelle Box aus dem Editor als wiederverwendbaren Baustein speichern.
async function onSaveBlockTemplate({ title = '', color = 'teal', fields = [] } = {}) {
  const suggested = (title || '').trim() || 'Neuer Schnellblock';
  const name = (window.prompt('Name des Schnellblocks:', suggested) || '').trim();
  if (!name) return;
  try {
    await notesStore.createBlockTemplate({ name, title, color, fields });
    notify({
      type: 'success',
      title: 'Schnellblock gespeichert',
      message: `„${name}" steht jetzt im /-Menü und in der Vorlagenmappe bereit.`,
      critical: true,
    });
  } catch (error) {
    notifyError(error, 'Schnellblock konnte nicht gespeichert werden.');
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
  window.addEventListener('online', onNetworkOnline);
  window.addEventListener('offline', onNetworkOffline);
  window.addEventListener('beforeunload', onBeforePageUnload);
  correspondentStore.ensureLoaded?.();
  dossierStore.fetchList?.();
  notesStore.ensureBlockTemplatesLoaded?.();
});

function onNetworkOnline() {
  isOnline.value = true;
  if (status.value === 'error' && hasUnsyncedChanges.value) retrySave();
}

function onNetworkOffline() {
  isOnline.value = false;
  if (hasUnsyncedChanges.value && status.value !== 'conflict') status.value = 'error';
}

function onBeforePageUnload(event) {
  // Eine Serverbestätigung ODER die bestätigte IndexedDB-Kopie genügt. Nur
  // wenn beides fehlt, warnt der Browser vor möglichem Datenverlust.
  if (!hasUnsyncedChanges.value || localDraftSaved.value) return;
  event.preventDefault();
  event.returnValue = '';
}

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

function flushPendingEditorFocus(noteId = loadedNoteId.value) {
  const request = pendingEditorFocusRequest;
  if (
    !request
    || request.noteId !== noteId
    || request.noteId !== props.noteId
    || loadingContent
  ) return false;
  const focused = noteEditorRef.value?.focusBody?.(request.position) === true;
  if (focused) pendingEditorFocusRequest = null;
  return focused;
}

async function focusEditorBody(position = 'start') {
  const normalizedPosition = position === 'end' ? 'end' : 'start';
  // Beim Anlegen ist NoteWorkspaceEditor oft schon sichtbar, während sein
  // asynchron geladener NoteEditor den neuen Inhalt noch nicht übernommen hat.
  // Die Anfrage bleibt deshalb an genau diese Notiz gebunden und wird nach dem
  // Laden erneut ausgeführt.
  pendingEditorFocusRequest = {
    noteId: props.noteId,
    position: normalizedPosition,
  };
  await nextTick();
  return flushPendingEditorFocus(props.noteId);
}

function focusTitle() {
  titleInputRef.value?.focus();
}

function onImageUploadError(message) {
  notify({
    type: 'error',
    message: String(message || 'Bild konnte nicht eingefügt werden.'),
  });
}

function exportNoteAsMarkdown() {
  void finalizeHistory(loadedNoteId.value, 'export');
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

const exportingPdf = ref(false);

async function exportNoteAsPdf() {
  if (exportingPdf.value) return;
  exportingPdf.value = true;
  void finalizeHistory(loadedNoteId.value, 'export');
  try {
    const html = noteToPrintableHtml({
      title: title.value,
      body: body.value,
      fontFamily: notesFontFamily.value,
      paragraphSpacing: notesParagraphSpacing.value,
      imageUrl: (src) => {
        const raw = String(src || '').trim();
        if (!raw) return '';
        if (!/^\/api\/notes\/[0-9a-f-]+\/images\/[0-9a-f-]+\/file$/i.test(raw)) return raw;
        const apiBase = String(getBaseUrl() || '').replace(/\/$/, '');
        const candidate = `${apiBase}${raw}`;
        const absolute = new URL(candidate, window.location.origin).href;
        return authedUrl(absolute);
      },
    });
    await downloadNotePdf(html, title.value);
  } catch (error) {
    notifyError(error, 'PDF konnte nicht heruntergeladen werden.');
  } finally {
    exportingPdf.value = false;
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

async function discardPendingDraft() {
  discardPendingSave = true;
  clearSaveTimer();
  const noteId = loadedNoteId.value;
  const draftVersion = currentDraftVersion.value || conflictingDraft.value?.clientVersion;
  await (currentSnapshot?.localWritePromise || Promise.resolve());
  if (noteId) await deleteNoteDraft(noteId, draftVersion).catch(() => false);
  currentSnapshot = null;
  currentDraftVersion.value = null;
  hasUnsyncedChanges.value = false;
  localDraftSaved.value = false;
  conflictingDraft.value = null;
  conflictServerNote.value = null;
}

function isEmpty() {
  if (loading.value || loadError.value) return null;
  return isNoteEmpty({ title: title.value, body_json: body.value });
}

function flushSave() {
  clearSaveTimer();
  if (status.value === 'conflict') return Promise.resolve();
  if (hasUnsyncedChanges.value && !discardPendingSave) return persist();
  const activePipeline = loadedNoteId.value ? savePipelines.get(loadedNoteId.value) : null;
  if (activePipeline?.running) return activePipeline.promise;
  return Promise.resolve();
}

defineExpose({ cancelPendingSave, discardPendingDraft, resumePendingSave, flushSave, focusEditorBody, focusTitle, isEmpty });

onBeforeUnmount(() => {
  rememberScrollPosition();
  persistScrollPositions();
  if (documentPickerSearchTimer) window.clearTimeout(documentPickerSearchTimer);
  window.removeEventListener('papermind:ai-configuration-changed', loadAICredentialStatus);
  window.removeEventListener('online', onNetworkOnline);
  window.removeEventListener('offline', onNetworkOffline);
  window.removeEventListener('beforeunload', onBeforePageUnload);
  void finalizeHistory(loadedNoteId.value, 'navigation');
});
</script>

<style scoped>
.note-workspace-editor {
  --pm-note-editor-header-bg: rgba(var(--v-theme-surface), 0.68);
  position: relative;
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

/* Das Aktionsmenü verwendet dieselbe kompakte Karten-, Zeilen- und
   Icon-Sprache wie der Darstellungsumschalter in „Alle Dokumente“. */
.note-workspace-editor__more-menu {
  overflow: hidden;
  padding: 6px;
  border: 1px solid color-mix(in srgb, var(--pm-divider) 86%, transparent);
  border-radius: 14px;
  background: var(--pm-app-surface-raised);
  box-shadow: var(--pm-shadow);
  color: var(--pm-text);
  opacity: 1 !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.note-workspace-editor__more-label,
.note-workspace-editor__more-group-label {
  padding: 4px 9px 6px;
  color: var(--pm-muted);
  font-size: 0.66rem;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.note-workspace-editor__more-group-label {
  margin-top: 5px;
  padding-top: 9px;
  border-top: 1px solid color-mix(in srgb, var(--pm-divider) 72%, transparent);
}

.note-workspace-editor__more-item {
  min-height: 38px;
  margin: 1px 0;
  padding-inline: 7px 8px !important;
  border-radius: 9px;
  color: color-mix(in srgb, var(--pm-text) 84%, var(--pm-muted));
  transition: none;
}

.note-workspace-editor__more-item :deep(.v-list-item__overlay) {
  transition: none !important;
}

.note-workspace-editor__more-item :deep(.v-list-item__prepend > .v-list-item__spacer) {
  width: 8px;
}

.note-workspace-editor__more-icon {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-divider) 34%, transparent);
  color: var(--pm-muted);
  transition: none;
}

.note-workspace-editor__more-hint {
  font: 500 0.72rem/1.4 'IBM Plex Mono', ui-monospace, monospace;
  color: var(--pm-muted);
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.note-workspace-editor__more-item:hover,
.note-workspace-editor__more-item:focus-visible {
  background: color-mix(in srgb, var(--pm-accent) 6%, transparent);
  color: var(--pm-text);
}

.note-workspace-editor__more-item:hover .note-workspace-editor__more-icon,
.note-workspace-editor__more-item:focus-visible .note-workspace-editor__more-icon {
  color: var(--pm-accent-strong, var(--pm-accent));
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

.note-workspace-editor__sync {
  display: inline-flex;
  min-width: 0;
  max-width: min(520px, 48vw);
  flex: none;
  align-items: center;
  gap: 5px;
  padding: 2px 7px;
  border: 1px solid color-mix(in srgb, var(--pm-warning, #b45309) 34%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-warning, #b45309) 8%, transparent);
  color: var(--pm-warning, #9a5b05);
  font-size: 0.7rem;
  line-height: 1.35;
  white-space: nowrap;
}

.note-workspace-editor__sync.is-error {
  border-color: color-mix(in srgb, var(--pm-danger, #c2453b) 34%, transparent);
  background: color-mix(in srgb, var(--pm-danger, #c2453b) 8%, transparent);
  color: var(--pm-danger, #a7372f);
}

.note-workspace-editor__sync.is-local {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 30%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 7%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.note-workspace-editor__sync-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.note-workspace-editor__sync button {
  flex: none;
  padding: 0 3px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: currentColor;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.note-workspace-editor__sync button:hover,
.note-workspace-editor__sync button:focus-visible {
  background: color-mix(in srgb, currentColor 10%, transparent);
  outline: none;
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
.note-workspace-editor__sync,
.note-workspace-editor__word-count {
  position: relative;
  top: -4px;
}

@media (max-width: 860px) {
  .note-workspace-editor__sync {
    max-width: 42vw;
  }
  .note-workspace-editor__sync.is-conflict {
    border-radius: 8px;
  }
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

/* Der 20-px-Glyph sitzt im 36-px-Button jeweils 8 px eingerückt. Der negative
   Außenabstand richtet die sichtbare Kante des rechten Menübuttons an der
   Wortanzahl aus. */
.note-workspace-editor__more-btn {
  margin-right: -8px;
}

.note-workspace-editor__main {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
}

.note-workspace-editor__scroll {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

/* Schwebende Suchen-&-Ersetzen-Leiste – ueberlagert oben rechts den Editor,
   unterhalb der Formatierungsleiste. Ersetzt die fruehere rechte Navigator-
   Seitenleiste (Gliederung + Suche). */
.note-workspace-editor__find {
  position: absolute;
  top: 60px;
  right: clamp(12px, 4vw, 40px);
  z-index: 15;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: min(360px, calc(100% - 24px));
  padding: 6px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px;
  background: var(--pm-app-surface-raised, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.14);
  transform-origin: top right;
}
.note-find-enter-active {
  will-change: opacity, transform;
  transition:
    opacity 160ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    transform 180ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1));
}
.note-find-leave-active {
  pointer-events: none;
  will-change: opacity, transform;
  transition:
    opacity 120ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    transform 140ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}
.note-find-enter-from,
.note-find-leave-to {
  opacity: 0;
  transform: translateY(-5px) scale(0.985);
}
.note-workspace-editor__find-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.note-workspace-editor__find-row--replace { padding-left: 28px; }
.note-workspace-editor__find-expand {
  flex: none;
  display: grid;
  place-items: center;
  width: 22px;
  height: 28px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
}
.note-workspace-editor__find-expand:hover {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 45%, transparent);
}
.note-workspace-editor__find-field {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 7px;
  background: var(--pm-content-surface, #fff);
  color: var(--pm-muted, #535e62);
}
.note-workspace-editor__find-field:focus-within {
  border-color: var(--pm-accent, #006b75);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
}
.note-workspace-editor__find-field input {
  flex: 1 1 auto;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.86rem;
}
.note-workspace-editor__find-count {
  flex: none;
  min-width: 34px;
  text-align: center;
  color: var(--pm-muted, #535e62);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
}
.note-workspace-editor__find-nav {
  flex: none;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
}
.note-workspace-editor__find-nav:hover:not(:disabled) {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 45%, transparent);
  color: var(--pm-text, #0e181b);
}
.note-workspace-editor__find-nav:disabled { opacity: 0.4; cursor: default; }
.note-workspace-editor__find-sep {
  flex: none;
  width: 1px;
  height: 18px;
  background: var(--pm-divider, #d8dfe1);
}
.note-workspace-editor__find-replace {
  flex: none;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 6px;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
}
.note-workspace-editor__find-replace:hover:not(:disabled) {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 40%, transparent);
}
.note-workspace-editor__find-replace:disabled { opacity: 0.45; cursor: default; }
.note-workspace-editor__find-replace.is-primary {
  border-color: transparent;
  background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff);
}
.note-workspace-editor__find-replace.is-primary:hover:not(:disabled) { filter: brightness(1.07); }

@media (max-width: 760px) {
  .note-workspace-editor__find { right: 12px; left: 12px; width: auto; }
}

:global(.pm-no-animations .note-find-enter-active),
:global(.pm-no-animations .note-find-leave-active) {
  transition: none;
}

@media (prefers-reduced-motion: reduce) {
  .note-find-enter-active,
  .note-find-leave-active {
    transition: none;
  }
}

/* Rückverweise: Notizen, die auf diese Notiz verweisen */
.note-workspace-editor__backlinks {
  padding: 14px clamp(20px, 5vw, 56px) 48px;
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
