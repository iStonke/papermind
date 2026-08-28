<!--
  NotesWorkspace — Notizen-Arbeitsfläche im Stil der übrigen Listenbereiche.
  Die kompakte mittlere Spalte enthält Kopfzeile, Filterleiste und Notizkarten;
  rechts bleibt der Platz für den späteren Inline-Editor reserviert.
-->
<template>
  <section class="notes-ws" :class="{ 'is-list-collapsed': isListPanelCollapsed && !isManageMode, 'is-manage': isManageMode }">
    <aside
      class="notes-ws__list-panel"
      aria-label="Notizenliste"
      :aria-hidden="panelInert ? 'true' : undefined"
      :inert="panelInert"
    >
      <header class="notes-ws__header">
        <div class="notes-ws__title">
          <div class="notes-ws__heading">Notizen</div>
          <div class="notes-ws__count">{{ headerCountLabel }}</div>
        </div>

        <div
          v-if="isManageMode"
          class="notes-ws__manage-switch"
          :class="{ 'is-templates': manageFacet === 'templates' }"
          role="tablist"
          aria-label="Notizen oder Vorlagen anzeigen"
        >
          <span class="notes-ws__manage-switch-indicator" aria-hidden="true" />
          <button
            type="button"
            role="tab"
            class="notes-ws__manage-switch-option"
            :class="{ 'is-active': manageFacet === 'notes' }"
            :aria-selected="manageFacet === 'notes' ? 'true' : 'false'"
            @click="manageFacet = 'notes'"
          >
            <span>Notizen</span>
          </button>
          <button
            type="button"
            role="tab"
            class="notes-ws__manage-switch-option"
            :class="{ 'is-active': manageFacet === 'templates' }"
            :aria-selected="manageFacet === 'templates' ? 'true' : 'false'"
            @click="manageFacet = 'templates'"
          >
            <span>Vorlagen</span>
          </button>
        </div>

        <div class="notes-ws__header-actions">
          <v-btn
            class="notes-ws__manage-toggle pm-header-icon-btn"
            color="primary"
            variant="tonal"
            icon
            :aria-pressed="String(isManageMode)"
            :aria-label="isManageMode ? 'Verwaltung schließen' : 'Notizen verwalten'"
            :title="isManageMode ? 'Verwaltung schließen' : 'Notizen verwalten'"
            @click="toggleManageMode"
          >
            <v-icon size="20">{{ isManageMode ? 'mdi-view-agenda-outline' : 'mdi-view-grid-outline' }}</v-icon>
          </v-btn>
        </div>
      </header>

      <NotesManageGrid
        v-if="isManageMode"
        class="notes-ws__manage"
        :facet="manageFacet"
        :search-query="searchQuery"
        :search-scope="searchScope"
        @open-note="openNoteFromManage"
        @changed="onManageChanged"
      />

      <div v-else class="notes-ws__list-shell">
        <ListActionToolbar
          :actions="toolbarActions"
          :show-selection="false"
          @action-select="handleToolbarAction"
        />

        <div class="notes-ws__list-scroll" :aria-busy="isSearchingNotes ? 'true' : undefined">
          <div v-if="isLoading" class="notes-ws__state" aria-live="polite">
            <v-progress-circular indeterminate color="primary" size="24" width="2" />
            <span>Notizen werden geladen …</span>
          </div>

          <div
            v-else-if="loadError"
            class="notes-ws__empty-state-wrap notes-ws__empty-state-wrap--error"
            role="alert"
          >
            <PmEmptyState
              icon="mdi-alert-circle-outline"
              :title="loadError"
              subtitle="Prüfe deine Verbindung und versuche es erneut."
              size="md"
              :animated="false"
            >
              <button type="button" class="notes-ws__retry" @click="loadNotes">
                <v-icon size="16">mdi-refresh</v-icon>
                <span>Erneut versuchen</span>
              </button>
            </PmEmptyState>
          </div>

          <div v-else-if="!visibleNotes.length" class="notes-ws__empty-state-wrap">
            <PmEmptyState
              icon="mdi-note-outline"
              :title="emptyTitle"
              :subtitle="emptyCopy"
              size="md"
            />
          </div>

          <div v-else class="notes-ws__groups">
            <section
              v-for="group in groupedNotes"
              :key="group.key"
              class="notes-ws__group"
              :aria-labelledby="`notes-ws-group-${group.key}`"
            >
              <h2 :id="`notes-ws-group-${group.key}`" class="notes-ws__group-heading">
                <span>{{ group.label }}</span>
              </h2>

              <ul class="notes-ws__list">
                <li
                  v-for="note in group.notes"
                  :key="note.id"
                  class="notes-ws__item"
                  :data-note-id="note.id"
                  :class="{
                    'is-active': note.id === activeNoteId,
                    'is-new': note.id === newlyCreatedNoteId,
                    'is-removing': note.id === removingNoteId,
                  }"
                  @animationend.self="finishNewNoteAnimation(note.id)"
                >
                  <button
                    type="button"
                    class="notes-ws__item-select"
                    :aria-current="note.id === activeNoteId ? 'true' : undefined"
                    @pointerenter="prefetchNote(note.id)"
                    @focus="prefetchNote(note.id)"
                    @click="selectNote(note.id)"
                  >
                    <span class="notes-ws__item-head">
                      <span class="notes-ws__item-title" :class="{ 'is-untitled': !note.title?.trim() }">
                        <span
                          v-for="(part, partIndex) in searchHighlightParts(note.title?.trim() || 'Ohne Titel')"
                          :key="`title-${partIndex}`"
                          class="notes-ws__search-part"
                          :class="{ 'is-match': part.match }"
                        >
                          {{ part.text }}
                        </span>
                      </span>
                      <span class="notes-ws__item-date">{{ formatDate(note.updated_at) }}</span>
                    </span>
                    <span class="notes-ws__item-snippet">
                      <span
                        v-for="(part, partIndex) in searchHighlightParts(snippet(note))"
                        :key="`snippet-${partIndex}`"
                        class="notes-ws__search-part"
                        :class="{ 'is-match': part.match }"
                      >
                        {{ part.text }}
                      </span>
                    </span>
                  </button>

                  <button
                    type="button"
                    class="notes-ws__item-delete"
                    :aria-label="noteDeleteAriaLabel(note)"
                    :title="isNoteEmpty(note) ? 'Entfernen' : 'In Papierkorb'"
                    @click="openDeleteNoteDialog(note)"
                  >
                    <v-icon size="16">mdi-trash-can-outline</v-icon>
                  </button>
                </li>
              </ul>
            </section>
          </div>

        </div>
      </div>

      <!-- Primäraktion als schwebender Button unten rechts (entlastet die Kopfzeile). -->
      <div
        v-if="!isManageMode && !loadError"
        class="notes-ws__fab"
        :class="{ 'has-templates': notesStore.templates.length > 0 }"
      >
        <v-btn
          class="notes-ws__fab-main"
          color="primary"
          :loading="creating"
          @click="createNote"
        >
          <v-icon size="20" class="mr-1">mdi-square-edit-outline</v-icon>
          Neue Notiz
        </v-btn>
        <v-menu
          v-if="notesStore.templates.length"
          location="top end"
          :offset="10"
          transition="scale-transition"
        >
          <template #activator="{ props }">
            <v-btn
              class="notes-ws__fab-caret"
              color="primary"
              aria-label="Aus Vorlage anlegen"
              :disabled="creating"
              v-bind="props"
            >
              <v-icon size="18">mdi-chevron-up</v-icon>
            </v-btn>
          </template>
          <div class="notes-ws__template-pop">
            <div class="notes-ws__template-pop-title">Aus Vorlage</div>
            <button
              v-for="template in notesStore.templates"
              :key="template.id"
              type="button"
              class="notes-ws__template-pop-item"
              @click="createNoteFromTemplate(template.id)"
            >
              <v-icon size="16">mdi-file-document-outline</v-icon>
              <span>{{ template.title?.trim() || 'Unbenannte Vorlage' }}</span>
            </button>
          </div>
        </v-menu>
      </div>
    </aside>

    <section class="notes-ws__editor-slot" aria-label="Notizbereich">
      <NoteWorkspaceEditor
        v-if="activeNote"
        ref="editorPanelRef"
        :note-id="activeNote.id"
        :list-visible="!isListPanelCollapsed"
        @toggle-list="toggleNotesList"
      />

      <v-btn
        v-if="!activeNote && isListPanelCollapsed"
        class="notes-ws__list-reveal"
        icon="mdi-arrow-collapse"
        size="small"
        variant="tonal"
        aria-label="Vollbildansicht verlassen und Notizenliste einblenden"
        title="Vollbildansicht verlassen"
        @click="toggleNotesList"
      />

      <NotesEditorIllustration
        v-if="!activeNote"
      />
    </section>

    <DestructiveDialog
      v-model="isDeleteNoteDialogOpen"
      title="Notiz löschen"
      header-subtitle="Möchtest du diese Notiz in den Papierkorb verschieben?"
      primary-text="In Papierkorb"
      secondary-text="Zurück"
      icon="mdi-trash-can-outline"
      :max-width="480"
      :loading="isDeletingNote"
      :persistent="isDeletingNote"
      @primary="confirmDeleteNote"
      @close="closeDeleteNoteDialog"
    >
      <p class="notes-ws__delete-dialog-name">„{{ noteTitle(deleteNoteTarget) }}“</p>
    </DestructiveDialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import DestructiveDialog from '../components/DestructiveDialog.vue';
import ListActionToolbar from '../components/ListActionToolbar.vue';
import PmEmptyState from '../components/PmEmptyState.vue';
import NoteWorkspaceEditor from '../components/notes/NoteWorkspaceEditor.vue';
import NotesEditorIllustration from '../components/notes/NotesEditorIllustration.vue';
import NotesManageGrid from '../components/notes/NotesManageGrid.vue';
import { isNoteEmpty, useNotesStore } from '../stores/notes.js';
import { useSettingsStore } from '../stores/settings.js';
import { groupNotesByCreationDay } from '../utils/noteDateGroups.js';

const props = defineProps({
  /** Suchtext aus der globalen PaperMind-Seitenleiste. */
  searchQuery: { type: String, default: '' },
  /** Im Notizenbereich: all | title | body. */
  searchScope: { type: String, default: 'all' },
});

const emit = defineEmits(['trash-changed']);

const NOTE_SORT_OPTIONS = [
  { value: 'updated', label: 'Zuletzt bearbeitet' },
  { value: 'created', label: 'Erstellungsdatum' },
  { value: 'title', label: 'Titel (A–Z)' },
];

const NOTE_DATE_RANGE_OPTIONS = [
  { value: '', label: 'Alle Zeiträume' },
  { value: 'today', label: 'Heute' },
  { value: 'last_7_days', label: 'Letzte 7 Tage' },
  { value: 'last_30_days', label: 'Letzte 30 Tage' },
];

const notesStore = useNotesStore();
const settingsStore = useSettingsStore();
const activeNoteId = ref(null);
const isListCollapsed = ref(resolveInitialListCollapsed());
const isManageMode = ref(false);
const manageFacet = ref('notes');
const isCompactLayout = ref(false);
const sortMode = ref(normalizeSortMode(settingsStore.settingsDraft.ui.notes_sort_order));
const dateRange = ref('');
const isLoading = ref(false);
const creating = ref(false);
const loadError = ref('');
const editorPanelRef = ref(null);
const newlyCreatedNoteId = ref(null);
const removingNoteId = ref(null);
const isDeleteNoteDialogOpen = ref(false);
const isDeletingNote = ref(false);
const deleteNoteTarget = ref(null);
const searchedNotes = ref([]);
const resolvedSearchKey = ref('');
const isSearchingNotes = ref(false);

let newNoteAnimationTimer = null;
let noteRemovalTimer = null;
let noteSearchTimer = null;
let noteSearchRevision = 0;
let compactLayoutQuery = null;
let noteSelectionRevision = 0;

const NOTE_REMOVAL_DURATION_MS = 210;
const NOTE_SEARCH_DEBOUNCE_MS = 220;

const isListPanelCollapsed = computed(() => isListCollapsed.value && !isCompactLayout.value);
// Im Verwaltungsmodus füllt das Panel die volle Breite und bleibt bedienbar.
const panelInert = computed(() => isListPanelCollapsed.value && !isManageMode.value);
const normalizedSearchQuery = computed(() => String(props.searchQuery || '').trim().slice(0, 256));
const normalizedSearchScope = computed(() => (
  ['all', 'title', 'body'].includes(props.searchScope) ? props.searchScope : 'all'
));
const activeSearchKey = computed(() => (
  normalizedSearchQuery.value
    ? `${normalizedSearchScope.value}:${normalizedSearchQuery.value.toLocaleLowerCase('de-DE')}`
    : ''
));
const searchSourceNotes = computed(() => {
  if (!activeSearchKey.value) return notesStore.notes;
  if (resolvedSearchKey.value === activeSearchKey.value) return searchedNotes.value;
  // Während des kurzen Debounce-Fensters bleibt die bestehende Liste stabil.
  // Das verhindert, dass der Editor beim Tippen vorübergehend abgewählt wird.
  return notesStore.notes;
});

const visibleNotes = computed(() => {
  const notes = searchSourceNotes.value
    .filter((note) => isWithinDateRange(note.updated_at, dateRange.value))
    .slice();

  if (sortMode.value === 'created') {
    return notes.sort((a, b) => timestamp(b.created_at || b.updated_at) - timestamp(a.created_at || a.updated_at));
  }
  if (sortMode.value === 'title') {
    return notes.sort((a, b) => noteTitle(a).localeCompare(noteTitle(b), 'de', { sensitivity: 'base' }));
  }
  return notes.sort((a, b) => timestamp(b.updated_at) - timestamp(a.updated_at));
});

const activeNote = computed(() =>
  visibleNotes.value.find((note) => note.id === activeNoteId.value) || null
);

const groupedNotes = computed(() => groupNotesByCreationDay(visibleNotes.value));

const resultCountLabel = computed(() => {
  const total = notesStore.notes.length;
  if (isSearchingNotes.value && resolvedSearchKey.value !== activeSearchKey.value) return 'Suche …';
  if ((activeSearchKey.value || dateRange.value) && visibleNotes.value.length !== total) {
    return `${visibleNotes.value.length} von ${total} Notizen`;
  }
  return total === 1 ? '1 Notiz' : `${total} Notizen`;
});

const headerCountLabel = computed(() => {
  if (isManageMode.value && manageFacet.value === 'templates') {
    const total = notesStore.templates.length;
    return total === 1 ? '1 Vorlage' : `${total} Vorlagen`;
  }
  return resultCountLabel.value;
});

const sortLabel = computed(() =>
  NOTE_SORT_OPTIONS.find((option) => option.value === sortMode.value)?.label || 'Sortierung'
);

const dateRangeLabel = computed(() =>
  NOTE_DATE_RANGE_OPTIONS.find((option) => option.value === dateRange.value)?.label || 'Zeitraum'
);

const toolbarActions = computed(() => [
  {
    key: 'sort',
    icon: 'mdi-sort',
    label: sortLabel.value,
    value: sortMode.value,
    options: NOTE_SORT_OPTIONS,
    minWidth: 190,
  },
  {
    key: 'dateRange',
    icon: 'mdi-calendar-range',
    label: dateRangeLabel.value,
    value: dateRange.value,
    active: Boolean(dateRange.value),
    options: NOTE_DATE_RANGE_OPTIONS,
    minWidth: 180,
  },
]);

const emptyTitle = computed(() => {
  if (activeSearchKey.value) return 'Keine passenden Notizen';
  return notesStore.notes.length ? 'Keine Notizen in diesem Zeitraum' : 'Noch keine Notizen';
});

const emptyCopy = computed(() => {
  if (activeSearchKey.value) return 'Passe den Suchbegriff an oder leere die globale Suche.';
  return notesStore.notes.length
    ? 'Wähle oben einen anderen Zeitraum aus.'
    : 'Halte Gedanken und Fundstellen an einem Ort fest.';
});

watch(
  visibleNotes,
  (notes) => {
    if (!notes.some((note) => note.id === activeNoteId.value)) {
      const nextId = notes[0]?.id || null;
      if (nextId) void selectNote(nextId);
      else activeNoteId.value = null;
    }
  },
  { immediate: true },
);

watch(
  () => settingsStore.settingsDraft.ui.notes_default_view,
  (mode) => {
    isListCollapsed.value = resolveListCollapsed(mode);
  },
);

watch(
  () => settingsStore.settingsDraft.ui.notes_sort_order,
  (sortOrder) => {
    sortMode.value = normalizeSortMode(sortOrder);
  },
);

watch(activeSearchKey, () => scheduleNoteSearch(), { immediate: true });

// Nach Autosave, Anlegen oder Löschen die aktive Suche neu bewerten. Der
// Signatur-Watch beobachtet bewusst nur die schlanken Listendaten.
watch(
  () => notesStore.notes.map((note) => (
    `${note.id}:${note.updated_at || ''}:${note.title || ''}:${note.preview || ''}`
  )).join('|'),
  () => {
    if (activeSearchKey.value) scheduleNoteSearch(80);
  },
);

onMounted(() => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    compactLayoutQuery = window.matchMedia('(max-width: 700px)');
    updateCompactLayout(compactLayoutQuery);
    compactLayoutQuery.addEventListener?.('change', updateCompactLayout);
  }
  loadNotes();
});

onBeforeUnmount(() => {
  if (newNoteAnimationTimer) window.clearTimeout(newNoteAnimationTimer);
  if (noteRemovalTimer) window.clearTimeout(noteRemovalTimer);
  if (noteSearchTimer) window.clearTimeout(noteSearchTimer);
  noteSearchRevision += 1;
  compactLayoutQuery?.removeEventListener?.('change', updateCompactLayout);
});

function localNoteSearch(notes, query, scope) {
  const terms = String(query || '').toLocaleLowerCase('de-DE').split(/\s+/).filter(Boolean);
  return notes.filter((note) => {
    const title = String(note.title || '').toLocaleLowerCase('de-DE');
    const body = String(note.preview || '').toLocaleLowerCase('de-DE');
    const haystack = scope === 'title' ? title : scope === 'body' ? body : `${title} ${body}`;
    return terms.every((term) => haystack.includes(term));
  });
}

function searchHighlightParts(value) {
  const text = String(value || '');
  const terms = [...new Set(
    normalizedSearchQuery.value.split(/\s+/).map((term) => term.trim()).filter(Boolean),
  )].sort((a, b) => b.length - a.length);
  if (!terms.length) return [{ text, match: false }];
  const escapedTerms = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(${escapedTerms.join('|')})`, 'giu');
  const normalizedTerms = new Set(terms.map((term) => term.toLocaleLowerCase('de-DE')));
  return text.split(pattern).filter(Boolean).map((part) => ({
    text: part,
    match: normalizedTerms.has(part.toLocaleLowerCase('de-DE')),
  }));
}

function scheduleNoteSearch(delay = NOTE_SEARCH_DEBOUNCE_MS) {
  const query = normalizedSearchQuery.value;
  const scope = normalizedSearchScope.value;
  const key = activeSearchKey.value;
  const revision = ++noteSearchRevision;
  if (noteSearchTimer) window.clearTimeout(noteSearchTimer);
  noteSearchTimer = null;

  if (!query) {
    searchedNotes.value = [];
    resolvedSearchKey.value = '';
    isSearchingNotes.value = false;
    return;
  }

  isSearchingNotes.value = true;
  noteSearchTimer = window.setTimeout(async () => {
    noteSearchTimer = null;
    try {
      const results = await notesStore.searchNotes(query, { scope });
      if (revision !== noteSearchRevision || key !== activeSearchKey.value) return;
      searchedNotes.value = results;
    } catch {
      if (revision !== noteSearchRevision || key !== activeSearchKey.value) return;
      // Bei einem vorübergehenden Backendfehler bleibt zumindest die Suche in
      // den bereits geladenen Titeln und Vorschautexten verfügbar.
      searchedNotes.value = localNoteSearch(notesStore.notes, query, scope);
    } finally {
      if (revision === noteSearchRevision && key === activeSearchKey.value) {
        resolvedSearchKey.value = key;
        isSearchingNotes.value = false;
      }
    }
  }, delay);
}

async function loadNotes() {
  isLoading.value = true;
  loadError.value = '';
  try {
    await notesStore.ensureLoaded();
    await applyPendingOpen();
  } catch {
    loadError.value = 'Die Notizen konnten nicht geladen werden.';
  } finally {
    isLoading.value = false;
  }
  // Vorlagen still im Hintergrund laden (füttern das „Neue Notiz"-Menü).
  notesStore.ensureTemplatesLoaded().catch(() => {});
}

// Von außen angeforderte Notiz öffnen (z. B. aus dem Dokument-Detailbereich).
// Zeitraumfilter zurücksetzen, damit die Ziel-Notiz garantiert sichtbar ist.
async function applyPendingOpen() {
  const id = notesStore.pendingOpenId;
  const cursorPosition = notesStore.pendingOpenCursorPosition;
  if (!id) return;
  await notesStore.ensureLoaded();
  if (!notesStore.notes.some((note) => note.id === id)) {
    // Neu/verknüpft, aber noch nicht in der Liste: frisch laden.
    await notesStore.fetchNotes();
  }
  if (notesStore.notes.some((note) => note.id === id)) {
    dateRange.value = '';
    if (await selectNote(id) && notesStore.pendingOpenId === id) {
      notesStore.consumeOpen();
      await focusRequestedEditorBody(cursorPosition);
    }
  }
}

watch(
  () => notesStore.pendingOpenId,
  (id) => { if (id) applyPendingOpen(); },
  { immediate: true },
);

function handleToolbarAction({ action, value }) {
  if (action === 'sort') sortMode.value = value;
  if (action === 'dateRange') dateRange.value = value;
}

function prefetchNote(noteId) {
  if (!noteId || noteId === activeNoteId.value) return;
  void notesStore.get(noteId).catch(() => {});
}

async function selectNote(noteId) {
  if (!noteId) return false;
  if (noteId === activeNoteId.value) return true;
  const revision = ++noteSelectionRevision;
  try {
    // Erst das Detail laden und danach umschalten. Die bisherige Editoransicht
    // bleibt dadurch stabil, falls ein nicht vorgepufferter Abruf kurz dauert.
    await notesStore.get(noteId);
  } catch {
    return false;
  }
  if (revision !== noteSelectionRevision) return false;
  activeNoteId.value = noteId;
  return true;
}

function loadNotesListCollapsed() {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem('pm-notes-list-collapsed') === 'true';
  } catch {
    return false;
  }
}

function resolveListCollapsed(mode) {
  if (mode === 'list') return false;
  if (mode === 'focus') return true;
  return loadNotesListCollapsed();
}

function resolveInitialListCollapsed() {
  return resolveListCollapsed(settingsStore.settingsDraft.ui.notes_default_view);
}

function normalizeSortMode(value) {
  return NOTE_SORT_OPTIONS.some((option) => option.value === value) ? value : 'updated';
}

function toggleNotesList() {
  isListCollapsed.value = !isListCollapsed.value;
  try {
    window.localStorage.setItem('pm-notes-list-collapsed', String(isListCollapsed.value));
  } catch {
    // Die Arbeitsfläche bleibt auch ohne verfügbaren Local Storage bedienbar.
  }
}

function toggleManageMode() {
  isManageMode.value = !isManageMode.value;
}

// Aus der Verwaltungsfläche eine Notiz im Editor öffnen: Modus verlassen und
// die Notiz aktivieren (nach dem Bulk-Refresh liegt sie sicher in der Liste).
async function openNoteFromManage(noteId, { cursorPosition = null } = {}) {
  isManageMode.value = false;
  await notesStore.ensureLoaded();
  if (!notesStore.notes.some((note) => note.id === noteId)) await notesStore.fetchNotes();
  dateRange.value = '';
  if (await selectNote(noteId)) await focusRequestedEditorBody(cursorPosition);
}

// Kartenaktion hat Papierkorb/Vorlagen/Notizen verändert → Umgebung informieren.
function onManageChanged() {
  emit('trash-changed');
}

function updateCompactLayout(event) {
  isCompactLayout.value = Boolean(event?.matches);
}

// Frisch angelegte Notiz auswählen, die Anlege-Animation auslösen und den
// Cursor erst nach dem Rendern direkt in die Schreibfläche setzen.
async function revealNewNote(note, cursorPosition = 'start') {
  activeNoteId.value = note.id;
  newlyCreatedNoteId.value = note.id;
  if (newNoteAnimationTimer) window.clearTimeout(newNoteAnimationTimer);
  // Fallback, falls Animationen deaktiviert sind und deshalb kein
  // animationend-Ereignis ausgelöst wird.
  newNoteAnimationTimer = window.setTimeout(() => finishNewNoteAnimation(note.id), 700);
  await focusRequestedEditorBody(cursorPosition);
}

async function focusRequestedEditorBody(cursorPosition) {
  if (!['start', 'end'].includes(cursorPosition)) return;
  await nextTick();
  await editorPanelRef.value?.focusEditorBody?.(cursorPosition);
}

async function createNote() {
  if (creating.value) return;
  creating.value = true;
  loadError.value = '';
  try {
    await revealNewNote(await notesStore.create());
  } catch {
    loadError.value = 'Die Notiz konnte nicht angelegt werden.';
  } finally {
    creating.value = false;
  }
}

async function createNoteFromTemplate(templateId) {
  if (!templateId || creating.value) return;
  creating.value = true;
  loadError.value = '';
  try {
    await revealNewNote(await notesStore.createFromTemplate(templateId), 'end');
  } catch {
    loadError.value = 'Die Notiz konnte aus der Vorlage nicht angelegt werden.';
  } finally {
    creating.value = false;
  }
}

function finishNewNoteAnimation(noteId) {
  if (newlyCreatedNoteId.value !== noteId) return;
  newlyCreatedNoteId.value = null;
  if (newNoteAnimationTimer) window.clearTimeout(newNoteAnimationTimer);
  newNoteAnimationTimer = null;
}

function openDeleteNoteDialog(note) {
  if (!note?.id || isDeletingNote.value) return;
  if (noteIsEmptyForDeletion(note)) {
    void discardEmptyNote(note);
    return;
  }
  deleteNoteTarget.value = note;
  isDeleteNoteDialogOpen.value = true;
}

function noteIsEmptyForDeletion(note) {
  if (note?.id === activeNoteId.value) {
    const editorEmpty = editorPanelRef.value?.isEmpty?.();
    if (typeof editorEmpty === 'boolean') return editorEmpty;
  }
  return isNoteEmpty(note);
}

function noteDeleteAriaLabel(note) {
  return isNoteEmpty(note)
    ? 'Leere Notiz entfernen'
    : `${note?.title?.trim() || 'Notiz'} in den Papierkorb verschieben`;
}

async function discardEmptyNote(note) {
  if (!note?.id || isDeletingNote.value) return;
  const isActive = note.id === activeNoteId.value;
  isDeletingNote.value = true;
  try {
    if (isActive) editorPanelRef.value?.cancelPendingSave?.();
    await notesStore.deletePermanently(note.id);
    if (isActive) await editorPanelRef.value?.discardPendingDraft?.();
    await animateNoteRemoval(note.id);
    notesStore.removeFromList(note.id);
    emit('trash-changed');
  } catch {
    if (isActive) editorPanelRef.value?.resumePendingSave?.();
    loadError.value = 'Die leere Notiz konnte nicht entfernt werden.';
  } finally {
    isDeletingNote.value = false;
  }
}

function closeDeleteNoteDialog() {
  if (isDeletingNote.value) return;
  isDeleteNoteDialogOpen.value = false;
  deleteNoteTarget.value = null;
}

async function confirmDeleteNote() {
  const note = deleteNoteTarget.value;
  if (!note?.id || isDeletingNote.value) return;

  const isActive = note.id === activeNoteId.value;
  isDeletingNote.value = true;
  try {
    if (isActive) editorPanelRef.value?.cancelPendingSave?.();
    await notesStore.trash(note.id);
    if (isActive) await editorPanelRef.value?.discardPendingDraft?.();
    isDeleteNoteDialogOpen.value = false;
    deleteNoteTarget.value = null;
    await animateNoteRemoval(note.id);
    notesStore.removeFromList(note.id);
    emit('trash-changed');
  } catch {
    if (isActive) editorPanelRef.value?.resumePendingSave?.();
    loadError.value = 'Die Notiz konnte nicht in den Papierkorb verschoben werden.';
  } finally {
    isDeletingNote.value = false;
  }
}

function noteListMotionDisabled() {
  if (typeof window === 'undefined') return true;
  if (document.querySelector('.pm-no-animations')) return true;
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false;
}

async function animateNoteRemoval(noteId) {
  if (noteListMotionDisabled()) return Promise.resolve();
  removingNoteId.value = noteId;
  await nextTick();
  return new Promise((resolve) => {
    noteRemovalTimer = window.setTimeout(() => {
      removingNoteId.value = null;
      noteRemovalTimer = null;
      resolve();
    }, NOTE_REMOVAL_DURATION_MS);
  });
}

function noteTitle(note) {
  return note?.title?.trim() || 'Ohne Titel';
}

function timestamp(value) {
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function isWithinDateRange(value, range) {
  if (!range) return true;
  const noteDate = new Date(value);
  if (Number.isNaN(noteDate.getTime())) return false;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const cutoff = new Date(today);
  if (range === 'today') return noteDate >= today;
  if (range === 'last_7_days') cutoff.setDate(cutoff.getDate() - 6);
  if (range === 'last_30_days') cutoff.setDate(cutoff.getDate() - 29);
  return noteDate >= cutoff;
}

function snippet(note) {
  return note.preview?.trim().replace(/\s+/g, ' ') || 'Leer';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const time = date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });

  if (date.toDateString() === now.toDateString()) return `heute ${time}`;
  if (date.toDateString() === yesterday.toDateString()) return `gestern ${time}`;

  return date.toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'short',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  });
}
</script>

<style scoped>
.notes-ws {
  --notes-list-width: clamp(300px, 31vw, 380px);
  --notes-header-height: 54px;
  --notes-meta-row-height: 36px;

  display: flex;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: var(--pm-viewer-surface, #eef2f4);
}

.notes-ws__list-panel,
.notes-ws__editor-slot {
  min-width: 0;
  min-height: 0;
}

.notes-ws__list-panel {
  position: relative;
  display: flex;
  width: var(--notes-list-width);
  flex: 0 0 var(--notes-list-width);
  flex-direction: column;
  background: var(--pm-content-surface, #fff);
  border-right: 1px solid var(--pm-divider, #d8dfe1);
  opacity: 1;
  transform: translateX(0);
  visibility: visible;
  will-change: margin-left, opacity, transform, flex-basis;
  transition:
    margin-left 260ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    opacity 180ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    transform 260ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    width 300ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    flex-basis 300ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    visibility 0ms linear;
}

.notes-ws.is-list-collapsed .notes-ws__list-panel {
  margin-left: calc(-1 * var(--notes-list-width));
  opacity: 0;
  pointer-events: none;
  transform: translateX(-18px);
  visibility: hidden;
  transition-delay: 0ms, 0ms, 0ms, 0ms, 0ms, 260ms;
}

/* Verwaltungsmodus: Liste entfaltet sich auf volle Breite, Editor klappt weg. */
.notes-ws.is-manage {
  --notes-list-width: 100%;
}

.notes-ws.is-manage .notes-ws__list-panel {
  border-right: 0;
}

.notes-ws.is-manage .notes-ws__editor-slot {
  flex: 0 0 0;
  width: 0;
  min-width: 0;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transition:
    flex-basis 300ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 0.2, 1)),
    width 300ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 0.2, 1)),
    opacity 160ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.notes-ws__header {
  position: relative;
  flex: none;
  display: flex;
  box-sizing: border-box;
  height: var(--notes-header-height);
  min-height: var(--notes-header-height);
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  background: rgba(var(--v-theme-surface), 0.68);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
}

.notes-ws__title {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 1px;
}

.notes-ws__heading {
  min-width: 0;
  overflow: hidden;
  color: var(--pm-text);
  font-size: 0.98rem;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.notes-ws__count {
  min-width: 0;
  overflow: hidden;
  color: var(--pm-muted);
  font-size: 0.74rem;
  font-weight: 500;
  line-height: 1.2;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.notes-ws__header-actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
}

.notes-ws__manage-switch {
  position: absolute;
  top: 50%;
  left: 50%;
  display: grid;
  width: min(250px, 38vw);
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 3px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 80%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--pm-viewer-surface, #eef2f4) 78%, transparent);
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
  transform: translate(-50%, -50%);
}

.notes-ws__manage-switch-indicator {
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 3px;
  width: calc((100% - 6px) / 2);
  border-radius: 9px;
  background: var(--pm-app-surface-raised, #fff);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.14), 0 1px 1px rgba(15, 23, 42, 0.06);
  transition: transform 180ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1));
}

.notes-ws__manage-switch.is-templates .notes-ws__manage-switch-indicator {
  transform: translateX(100%);
}

.notes-ws__manage-switch-option {
  position: relative;
  z-index: 1;
  display: inline-flex;
  min-width: 0;
  min-height: 30px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 5px 11px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
  font: inherit;
  font-size: 0.81rem;
  font-weight: 560;
  transition: color 140ms ease;
}

.notes-ws__manage-switch-option:hover,
.notes-ws__manage-switch-option.is-active {
  color: var(--pm-text);
}

.notes-ws__manage-switch-option.is-active {
  font-weight: 650;
}

.notes-ws__manage-switch-option:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--pm-accent, #006b75) 58%, transparent);
  outline-offset: -2px;
}

.notes-ws__header .v-btn {
  border-radius: 10px;
  text-transform: none;
  letter-spacing: 0;
}

/* Split-Button „Neue Notiz" + Vorlagen-Menü. */
/* Schwebende Primäraktion („Neue Notiz") unten rechts über der Liste. */
.notes-ws__fab {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 16px;
  z-index: 5;
  display: flex;
  align-items: stretch;
  gap: 1px;
  border-radius: 999px;
  box-shadow: 0 6px 20px -6px rgba(0, 0, 0, 0.32), 0 2px 6px -2px rgba(0, 0, 0, 0.18);
  transition: box-shadow 180ms var(--pm-easing, cubic-bezier(0.2, 0, 0, 1));
}
.notes-ws__fab .v-btn {
  text-transform: none;
  letter-spacing: 0;
  transition:
    background-color 180ms var(--pm-easing, cubic-bezier(0.2, 0, 0, 1)),
    box-shadow 180ms var(--pm-easing, cubic-bezier(0.2, 0, 0, 1));
}
.notes-ws__fab .v-btn:hover:not(.v-btn--disabled) {
  background-color: color-mix(
    in srgb,
    rgb(var(--v-theme-primary)) 91%,
    rgb(var(--v-theme-on-primary)) 9%
  ) !important;
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, rgb(var(--v-theme-on-primary)) 28%, transparent),
    inset 0 0 0 1px color-mix(in srgb, rgb(var(--v-theme-on-primary)) 14%, transparent);
}
.notes-ws__fab:has(.v-btn:hover:not(.v-btn--disabled)) {
  box-shadow:
    0 10px 28px -10px color-mix(in srgb, rgb(var(--v-theme-primary)) 56%, transparent),
    0 4px 10px -5px rgba(0, 0, 0, 0.3),
    0 0 0 3px color-mix(in srgb, rgb(var(--v-theme-primary)) 13%, transparent);
}
.notes-ws__fab-main.v-btn {
  height: 44px;
  padding-inline: 20px 18px;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: 999px;
}
.notes-ws__fab.has-templates .notes-ws__fab-main.v-btn {
  border-radius: 999px 0 0 999px;
}
.notes-ws__fab-caret.v-btn {
  height: 44px;
  min-width: 38px;
  padding-inline: 0;
  border-radius: 0 999px 999px 0;
  border-left: 1px solid color-mix(in srgb, var(--pm-app-surface, #fff) 22%, transparent);
}
/* „Aus Vorlage"-Popover am FAB. Teleportiert aus .papermind-app → nur
   --v-theme-*-Variablen greifen zuverlässig (kein --pm-*). */
.notes-ws__template-pop {
  min-width: 240px;
  max-width: 288px;
  padding: 6px;
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  box-shadow: 0 12px 32px -10px rgba(0, 0, 0, 0.4), 0 4px 12px -4px rgba(0, 0, 0, 0.22);
}
.notes-ws__template-pop-title {
  padding: 8px 12px 6px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 0.67rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.notes-ws__template-pop-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: rgb(var(--v-theme-on-surface));
  font: inherit;
  font-size: 0.9rem;
  text-align: left;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.notes-ws__template-pop-item .v-icon { color: rgba(var(--v-theme-on-surface), 0.5); transition: color 120ms ease; }
.notes-ws__template-pop-item:hover {
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}
.notes-ws__template-pop-item:hover .v-icon { color: rgb(var(--v-theme-primary)); }
@media (prefers-reduced-motion: reduce) {
  .notes-ws__template-pop-item { transition: none; }
}

.list-header-btn.v-btn {
  transition: background-color var(--pm-duration-fast, 140ms) var(--pm-easing, ease);
}

.list-header-btn.v-btn:hover:not(.v-btn--disabled) {
  background-color: color-mix(in srgb, currentColor 14%, var(--pm-app-surface-raised)) !important;
}

.list-header-btn.v-btn:focus-visible:not(.v-btn--disabled) {
  outline: 2px solid currentColor;
  outline-offset: 2px;
}

:global(.pm-no-animations) .list-header-btn.v-btn {
  transition-duration: 0ms;
}

.notes-ws__list-shell {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  flex-direction: column;
}

.notes-ws__list-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.notes-ws__groups {
  margin: 0;
  /* Unten Platz lassen, damit der schwebende FAB die letzte Notiz nicht verdeckt. */
  padding: 0 10px 76px;
}

.notes-ws__group + .notes-ws__group {
  margin-top: 14px;
}

.notes-ws__group-heading {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  min-height: 30px;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 9px 8px 6px;
  background: var(--pm-content-surface, rgb(var(--v-theme-surface)));
  color: var(--pm-muted);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.075em;
  line-height: 1.2;
  text-transform: uppercase;
}

.notes-ws__group-heading::after {
  content: '';
  flex: 1 1 auto;
  height: 1px;
  margin-left: 3px;
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 70%, transparent);
}

.notes-ws__list {
  display: block;
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-anchor: none;
}

.notes-ws__item {
  position: relative;
  box-sizing: border-box;
  height: 112px;
  min-height: 112px;
  overflow: hidden;
  border: 1px solid var(--pm-document-row-border, rgba(15, 23, 42, 0.06));
  border-radius: 14px;
  background: var(--pm-document-row-bg, var(--pm-app-surface-raised, #fff));
  box-shadow: var(--pm-document-row-shadow, 0 2px 8px rgba(15, 23, 42, 0.08));
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    border-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.notes-ws__item + .notes-ws__item {
  margin-top: 10px;
}

.notes-ws__item:hover {
  border-color: var(--pm-document-row-hover-border, color-mix(in srgb, var(--pm-accent) 16%, transparent));
  background: var(--pm-row-hover);
}

.notes-ws__item.is-active {
  border-color: var(--pm-document-row-active-border, color-mix(in srgb, var(--pm-accent) 30%, transparent));
  background: var(--pm-document-row-active-bg, var(--pm-row-active));
}

.notes-ws__item.is-active:hover {
  border-color: var(--pm-document-row-active-hover-border, color-mix(in srgb, var(--pm-accent) 38%, transparent));
  background: var(--pm-document-row-active-bg, var(--pm-row-active));
}

.notes-ws__item.is-new {
  transform-origin: 50% 0;
  animation: notes-ws-note-created var(--pm-duration-slow, 340ms) var(--pm-easing-decel, cubic-bezier(0, 0, 0.2, 1)) both;
}

/* Identischer Ausblend-/Zusammenklapp-Ablauf wie bei Dokumentzeilen. */
.notes-ws__item.is-removing {
  pointer-events: none;
  height: 0;
  min-height: 0;
  margin-top: 0 !important;
  border-top-width: 0;
  border-bottom-width: 0;
  opacity: 0;
  transform: translateY(-4px) scale(0.99);
  animation: none;
  will-change: height, opacity, transform;
  transition:
    height 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    min-height 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    margin-top 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    border-top-width 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    border-bottom-width 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)),
    opacity 160ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 1, 1)),
    transform 180ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 1, 1));
}

@keyframes notes-ws-note-created {
  0% {
    min-height: 0;
    max-height: 0;
    opacity: 0;
    transform: translateY(-10px) scale(0.975);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--pm-accent) 0%, transparent);
  }
  68% {
    min-height: 112px;
    max-height: 140px;
    opacity: 1;
    transform: translateY(1px) scale(1.006);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent) 14%, transparent);
  }
  100% {
    min-height: 112px;
    max-height: 140px;
    opacity: 1;
    transform: none;
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--pm-accent) 0%, transparent);
  }
}

.notes-ws__item-select {
  display: flex;
  width: 100%;
  min-height: 110px;
  flex-direction: column;
  gap: 9px;
  padding: 15px 42px 15px 17px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.notes-ws__item-head {
  display: flex;
  min-width: 0;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.notes-ws__item-title {
  min-width: 0;
  overflow: hidden;
  color: var(--pm-text);
  font-size: 0.94rem;
  font-weight: 650;
  line-height: 1.3;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.notes-ws__item-title.is-untitled {
  color: var(--pm-muted);
  font-style: italic;
  font-weight: 560;
}

.notes-ws__item-date {
  flex: none;
  color: var(--pm-muted);
  font-size: 0.73rem;
  white-space: nowrap;
}

.notes-ws__item-snippet {
  display: -webkit-box;
  overflow: hidden;
  color: var(--pm-muted);
  font-size: 0.82rem;
  line-height: 1.46;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.notes-ws__search-part.is-match {
  border-radius: 3px;
  background: color-mix(in srgb, var(--pm-accent) 22%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--pm-accent) 8%, transparent);
  color: inherit;
  padding: 0 0.08em;
}

.notes-ws__item-delete {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
}

.notes-ws__item:hover .notes-ws__item-delete,
.notes-ws__item-delete:focus-visible {
  opacity: 1;
}

.notes-ws__item-delete:hover {
  background: color-mix(in srgb, var(--pm-danger, #d95757) 12%, transparent);
  color: var(--pm-danger, #d95757);
}

.notes-ws__state {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 28px;
  color: var(--pm-muted);
  font-size: 0.84rem;
  text-align: center;
}

.notes-ws__retry {
  display: inline-flex;
  height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 13px;
  border: 1px solid color-mix(in srgb, var(--pm-accent) 24%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent) 7%, transparent);
  color: var(--pm-accent-strong, var(--pm-accent));
  cursor: pointer;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}

.notes-ws__retry:hover,
.notes-ws__retry:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent) 42%, transparent);
  background: color-mix(in srgb, var(--pm-accent) 12%, transparent);
}

.notes-ws__retry:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--pm-accent) 42%, transparent);
  outline-offset: 2px;
}

.notes-ws__delete-dialog-name {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.86);
  font-size: 0.98rem;
  font-weight: 650;
  line-height: 1.45;
}

.notes-ws__empty-state-wrap {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 260px;
  align-items: center;
  justify-content: center;
}

.notes-ws__empty-state-wrap--error :deep(.pm-empty-state__halo) {
  border-color: color-mix(in srgb, var(--pm-danger, #c84c4c) 28%, transparent);
  background: color-mix(in srgb, var(--pm-danger, #c84c4c) 7%, transparent);
}

.notes-ws__empty-state-wrap--error :deep(.pm-empty-state__halo::after) {
  border-color: color-mix(in srgb, var(--pm-danger, #c84c4c) 48%, transparent);
}

.notes-ws__empty-state-wrap--error :deep(.pm-empty-state__icon) {
  color: var(--pm-danger, #c84c4c);
  opacity: 0.46;
}

.notes-ws__editor-slot {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  background: var(--pm-viewer-surface, #eef2f4);
}

.notes-ws__list-reveal.v-btn {
  position: absolute;
  z-index: 3;
  top: 12px;
  left: 12px;
  border-radius: 9px;
}

@media (max-width: 920px) {
  .notes-ws {
    --notes-list-width: clamp(280px, 42%, 380px);
  }
}

@media (max-width: 700px) {
  .notes-ws {
    display: block;
  }

  .notes-ws__editor-slot {
    display: none;
  }

  .notes-ws__list-panel,
  .notes-ws.is-list-collapsed .notes-ws__list-panel {
    width: 100%;
    height: 100%;
    margin-left: 0;
    border-right: 0;
    opacity: 1;
    pointer-events: auto;
    transform: none;
    visibility: visible;
  }
}

@media (hover: none) {
  .notes-ws__item-delete {
    opacity: 0.72;
  }
}

@media (prefers-reduced-motion: reduce) {
  .notes-ws__fab,
  .notes-ws__fab .v-btn,
  .list-header-btn.v-btn,
  .notes-ws__manage-switch-indicator,
  .notes-ws__list-panel,
  .notes-ws__item.is-new,
  .notes-ws__item.is-removing {
    transition-duration: 0ms;
  }

  .notes-ws__item.is-new {
    animation: none;
  }
}

:global(.pm-no-animations) .notes-ws__fab,
:global(.pm-no-animations) .notes-ws__fab .v-btn {
  transition-duration: 0ms;
}

:global(.pm-no-animations) .notes-ws__item.is-new {
  animation: none;
}

:global(.pm-no-animations) .notes-ws__item.is-removing {
  transition-duration: 0ms;
}

:global(.pm-no-animations) .notes-ws__list-panel {
  transition-duration: 0ms;
}

:global(.pm-no-animations) .notes-ws__manage-switch-indicator {
  transition-duration: 0ms;
}
</style>
