<!--
  NotesWorkspace — Notizen-Arbeitsfläche im Stil der übrigen Listenbereiche.
  Die kompakte mittlere Spalte enthält Kopfzeile, Filterleiste und Notizkarten;
  rechts bleibt der Platz für den späteren Inline-Editor reserviert.
-->
<template>
  <section
    class="notes-ws"
    :class="{ 'is-list-collapsed': isListPanelCollapsed }"
  >
    <aside
      class="notes-ws__list-panel"
      aria-label="Notizenliste"
      :aria-hidden="panelInert ? 'true' : undefined"
      :inert="panelInert"
    >
      <header class="notes-ws__header">
        <div class="notes-ws__title">
          <div class="notes-ws__heading">
            <span>Notizen</span>
          </div>
          <div class="notes-ws__count">{{ resultCountLabel }}</div>
        </div>

        <!-- Sammlungs-Chip: horizontal in der Titelleiste zentriert (absolut,
             wie die Verwaltungs-Suchleiste), unabhängig von Titel-/Button-Breite. -->
        <v-menu location="bottom center" :offset="6">
          <template #activator="{ props: pillProps }">
            <button
              type="button"
              class="notes-ws__collection-pill notes-ws__collection-pill--centered"
              v-bind="pillProps"
              :title="`Sammlung: ${activeCollectionName}`"
              aria-label="Sammlung wechseln"
            >
              <span class="notes-ws__collection-dot" :style="collectionDotStyle(activeCollection)"></span>
              <span class="notes-ws__collection-name">{{ activeCollectionName }}</span>
              <v-icon size="15">mdi-chevron-down</v-icon>
            </button>
          </template>
          <v-list density="compact" min-width="220" class="notes-ws__collection-menu">
            <v-list-subheader>Sammlung</v-list-subheader>
            <v-list-item
              v-for="c in collections"
              :key="c.id"
              :title="c.name"
              :active="c.id === activeCollectionId"
              @click="switchCollection(c.id)"
            >
              <template #prepend><span class="notes-ws__collection-dot" :style="collectionDotStyle(c)"></span></template>
              <template #append><span class="notes-ws__collection-count">{{ c.note_count }}</span></template>
            </v-list-item>
          </v-list>
        </v-menu>

        <div class="notes-ws__header-actions">
          <v-btn
            class="notes-ws__manage-toggle pm-header-icon-btn"
            color="primary"
            variant="tonal"
            icon
            aria-pressed="false"
            aria-label="Notizen verwalten"
            title="Notizen verwalten"
            @click="toggleManageMode"
          >
            <v-icon size="20">mdi-view-grid-outline</v-icon>
          </v-btn>
        </div>
      </header>

      <div class="notes-ws__list-shell">
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
        v-if="!loadError"
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

    <section
      class="notes-ws__editor-slot"
      aria-label="Notizbereich"
      :aria-hidden="isManageMode ? 'true' : undefined"
      :inert="isManageMode"
    >
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

    <Transition name="notes-ws-manage" appear>
      <aside
        v-if="isManageMode"
        class="notes-ws__manage-panel"
        aria-label="Notizen verwalten"
      >
        <header class="notes-ws__header">
          <div class="notes-ws__title">
            <div class="notes-ws__heading">
              <v-menu location="bottom start" :offset="6" transition="fade-transition">
                <template #activator="{ props: viewMenuProps }">
                  <button
                    v-bind="viewMenuProps"
                    type="button"
                    class="notes-ws__manage-view-trigger"
                    aria-label="Ansicht wechseln"
                  >
                    <span>{{ manageFacet === 'templates' ? 'Vorlagen' : 'Notizen' }}</span>
                    <v-icon class="notes-ws__manage-view-chevron" size="15" aria-hidden="true">mdi-chevron-down</v-icon>
                  </button>
                </template>

                <div class="notes-ws__manage-view-menu" role="menu" aria-label="Ansicht auswählen">
                  <button
                    type="button"
                    role="menuitemradio"
                    :aria-checked="manageFacet === 'notes' ? 'true' : 'false'"
                    :class="{ 'is-active': manageFacet === 'notes' }"
                    @click="manageFacet = 'notes'"
                  >
                    <v-icon size="18">mdi-note-outline</v-icon>
                    <span>Notizen</span>
                    <v-icon v-if="manageFacet === 'notes'" class="notes-ws__manage-view-check" size="16">mdi-check</v-icon>
                  </button>
                  <button
                    type="button"
                    role="menuitemradio"
                    :aria-checked="manageFacet === 'templates' ? 'true' : 'false'"
                    :class="{ 'is-active': manageFacet === 'templates' }"
                    @click="manageFacet = 'templates'"
                  >
                    <v-icon size="18">mdi-file-document-multiple-outline</v-icon>
                    <span>Vorlagen</span>
                    <v-icon v-if="manageFacet === 'templates'" class="notes-ws__manage-view-check" size="16">mdi-check</v-icon>
                  </button>
                </div>
              </v-menu>
            </div>
            <div class="notes-ws__count">{{ manageCountLabel }}</div>
          </div>

          <div
            class="notes-ws__manage-search"
            :class="{ 'is-open': manageSearchExpanded || normalizedManageSearchQuery }"
            role="search"
            @click="focusManageSearch"
          >
            <v-icon size="18" aria-hidden="true">mdi-magnify</v-icon>
            <input
              ref="manageSearchInputRef"
              v-model="manageSearchQuery"
              type="search"
              autocomplete="off"
              spellcheck="false"
              aria-label="Notizen und Notizbücher durchsuchen"
              placeholder="Notizen durchsuchen …"
              @focus="manageSearchExpanded = true"
              @blur="manageSearchExpanded = Boolean(normalizedManageSearchQuery)"
              @keydown="handleManageSearchKeydown"
            />
            <button
              v-if="manageSearchQuery"
              type="button"
              class="notes-ws__manage-search-clear"
              aria-label="Suche leeren"
              title="Suche leeren"
              @click.stop="clearManageSearch"
            >
              <v-icon size="15">mdi-close</v-icon>
            </button>
          </div>

          <div class="notes-ws__header-actions notes-ws__manage-header-actions">
            <v-btn
              class="notes-ws__manage-toggle pm-header-icon-btn"
              color="primary"
              variant="tonal"
              icon
              aria-pressed="true"
              aria-label="Verwaltung schließen"
              title="Verwaltung schließen"
              @click="toggleManageMode"
            >
              <v-icon size="20">mdi-close</v-icon>
            </v-btn>
          </div>
        </header>

        <NotesManageGrid
          ref="manageGridRef"
          class="notes-ws__manage"
          :facet="manageFacet"
          :search-query="searchQuery"
          :search-scope="searchScope"
          :global-search-query="normalizedManageSearchQuery"
          :global-search-notes="manageSearchNotes"
          :global-search-notebooks="matchingManageNotebooks"
          :global-search-loading="manageSearchLoading"
          @open-note="openNoteFromManage"
          @open-search-note="openManageNoteResult"
          @select-search-notebook="openManageNotebookResult"
          @changed="onManageChanged"
          @create-note="createNoteFromManage"
        />
      </aside>
    </Transition>

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
import { useNoteListPreferences } from '../components/notes/composables/useNoteListPreferences.js';
import { isNoteEmpty, useNotesStore } from '../stores/notes.js';
import { useSettingsStore } from '../stores/settings.js';
import { notifyNoteDeleted } from '../utils/noteDeletionFeedback.js';
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
const NOTES_MANAGE_FACET_STORAGE_KEY = 'pm-notes-manage-facet-v1';

const notesStore = useNotesStore();
const settingsStore = useSettingsStore();
const activeNoteId = ref(null);
const isListCollapsed = ref(resolveInitialListCollapsed());
const isManageMode = ref(false);
const manageFacet = ref(loadManageFacet());
const isCompactLayout = ref(false);
const { sortMode, dateRange, notebookFilter } = useNoteListPreferences(
  () => settingsStore.settingsDraft.ui.notes_sort_order,
);
// Notizbuch-Filter der kompakten Liste: '' = alle, 'none' = ohne Notizbuch,
// sonst die Notizbuch-ID. Rein clientseitig über note.notebook_id.
// Sammlungen (oberste Ebene): Spiegel-Pille im Header, geteilter aktiver Zustand
// mit dem Verwaltungsraster (persistiert im Store).
const collections = computed(() => notesStore.collections);
const activeCollectionId = computed(() => notesStore.activeCollectionId);
const activeCollection = computed(
  () => collections.value.find((c) => c.id === activeCollectionId.value) || null,
);
const activeCollectionName = computed(() => activeCollection.value?.name || 'Sammlung');
function collectionDotStyle(c) {
  return { '--pm-coll-dot': c?.color || 'var(--pm-accent, #006b75)' };
}
async function switchCollection(id) {
  if (!id || id === activeCollectionId.value) return;
  notebookFilter.value = ''; // Notizbuch-Filter gehört zur alten Sammlung.
  try {
    await notesStore.setActiveCollection(id);
  } catch { /* Ladefehler werden über die Notizen-Ladeanzeige sichtbar. */ }
}
const manageGridRef = ref(null);
const manageSearchInputRef = ref(null);
const manageSearchQuery = ref('');
const manageSearchExpanded = ref(false);
const manageSearchNotes = ref([]);
const manageSearchLoading = ref(false);
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
let manageSearchTimer = null;
let manageSearchRevision = 0;
let compactLayoutQuery = null;
let noteSelectionRevision = 0;

const NOTE_REMOVAL_DURATION_MS = 210;
const NOTE_SEARCH_DEBOUNCE_MS = 220;
const MANAGE_SEARCH_DEBOUNCE_MS = 180;

const isListPanelCollapsed = computed(() => isListCollapsed.value && !isCompactLayout.value);
const panelInert = computed(() => isListPanelCollapsed.value || isManageMode.value);
const normalizedSearchQuery = computed(() => String(props.searchQuery || '').trim().slice(0, 256));
const normalizedSearchScope = computed(() => (
  ['all', 'title', 'body'].includes(props.searchScope) ? props.searchScope : 'all'
));
const activeSearchKey = computed(() => (
  normalizedSearchQuery.value
    ? `${normalizedSearchScope.value}:${normalizedSearchQuery.value.toLocaleLowerCase('de-DE')}`
    : ''
));
const normalizedManageSearchQuery = computed(() => (
  String(manageSearchQuery.value || '').trim().slice(0, 256)
));
const manageSearchTerms = computed(() => (
  normalizedManageSearchQuery.value.toLocaleLowerCase('de-DE').split(/\s+/).filter(Boolean)
));
const matchingManageNotebooks = computed(() => {
  if (!manageSearchTerms.value.length) return [];
  return notesStore.notebooks.filter((notebook) => {
    const name = String(notebook.name || '').toLocaleLowerCase('de-DE');
    return manageSearchTerms.value.every((term) => name.includes(term));
  });
});
const searchSourceNotes = computed(() => {
  if (!activeSearchKey.value) return notesStore.notes;
  if (resolvedSearchKey.value === activeSearchKey.value) return searchedNotes.value;
  // Während des kurzen Debounce-Fensters bleibt die bestehende Liste stabil.
  // Das verhindert, dass der Editor beim Tippen vorübergehend abgewählt wird.
  return notesStore.notes;
});

function matchesNotebookFilter(note) {
  if (!notebookFilter.value) return true;
  if (notebookFilter.value === 'none') return !note.notebook_id;
  return note.notebook_id === notebookFilter.value;
}

const visibleNotes = computed(() => {
  const notes = searchSourceNotes.value
    .filter((note) => isWithinDateRange(note.updated_at, dateRange.value))
    .filter(matchesNotebookFilter)
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
  if ((activeSearchKey.value || dateRange.value || notebookFilter.value) && visibleNotes.value.length !== total) {
    return `${visibleNotes.value.length} von ${total} Notizen`;
  }
  return total === 1 ? '1 Notiz' : `${total} Notizen`;
});

const manageCountLabel = computed(() => {
  if (manageFacet.value === 'templates') {
    // Der Vorlagen-Bereich umfasst Schnellblöcke UND Startnotizen.
    const total = notesStore.blockTemplates.length + notesStore.templates.length;
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

// Notizbuch-Dropdown: Alle · je Notizbuch · Ohne Notizbuch.
const notebookFilterOptions = computed(() => [
  { value: '', label: 'Alle Notizbücher' },
  ...notesStore.notebooks.map((nb) => ({ value: nb.id, label: nb.name })),
  { value: 'none', label: 'Ohne Notizbuch' },
]);

const notebookFilterLabel = computed(() =>
  notebookFilterOptions.value.find((option) => option.value === notebookFilter.value)?.label
    || 'Notizbuch'
);

const toolbarActions = computed(() => {
  const actions = [
    {
      key: 'sort',
      icon: 'mdi-sort',
      label: sortLabel.value,
      value: sortMode.value,
      options: NOTE_SORT_OPTIONS,
      minWidth: 190,
    },
  ];
  // Notizbuch-Filter nur anbieten, wenn es überhaupt Notizbücher gibt.
  if (notesStore.notebooks.length) {
    actions.push({
      key: 'notebook',
      icon: 'mdi-notebook-outline',
      label: notebookFilterLabel.value,
      value: notebookFilter.value,
      active: Boolean(notebookFilter.value),
      // Im Standard („Alle Notizbücher") nur das Icon zeigen – spart Platz in der
      // schmalen Liste; aktiv zeigt es das gewählte Notizbuch.
      iconOnly: !notebookFilter.value,
      options: notebookFilterOptions.value,
      minWidth: 200,
    });
  }
  actions.push({
    key: 'dateRange',
    icon: 'mdi-calendar-range',
    label: dateRangeLabel.value,
    value: dateRange.value,
    active: Boolean(dateRange.value),
    iconOnly: !dateRange.value,
    options: NOTE_DATE_RANGE_OPTIONS,
    minWidth: 180,
  });
  return actions;
});

const emptyTitle = computed(() => {
  if (activeSearchKey.value) return 'Keine passenden Notizen';
  if (!notesStore.notes.length) return 'Noch keine Notizen';
  if (notebookFilter.value === 'none') return 'Keine Notizen ohne Notizbuch';
  if (notebookFilter.value) return 'Dieses Notizbuch ist leer';
  return 'Keine Notizen in diesem Zeitraum';
});

const emptyCopy = computed(() => {
  if (activeSearchKey.value) return 'Passe den Suchbegriff an oder leere die globale Suche.';
  if (!notesStore.notes.length) return 'Halte Gedanken und Fundstellen an einem Ort fest.';
  if (notebookFilter.value) return 'Verschiebe Notizen hierher oder wähle ein anderes Notizbuch.';
  return 'Wähle oben einen anderen Zeitraum aus.';
});

// Wurde das gefilterte Notizbuch (z. B. im Verwaltungsraster) gelöscht, fällt der
// Filter auf „Alle" zurück, statt eine dauerhaft leere Liste zu zeigen.
watch(
  () => [notesStore.notebooks, notesStore.notebooksLoaded],
  ([list]) => {
    if (
      notesStore.notebooksLoaded
      && notebookFilter.value
      && notebookFilter.value !== 'none'
      && !list.some((nb) => nb.id === notebookFilter.value)
    ) {
      notebookFilter.value = '';
    }
  },
  { deep: true, immediate: true },
);

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

watch(activeSearchKey, () => scheduleNoteSearch(), { immediate: true });
watch(normalizedManageSearchQuery, scheduleManageSearch);

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
  // Sammlungen früh laden, damit die Spiegel-Pille sofort befüllt ist.
  notesStore.ensureCollectionsLoaded().catch(() => {});
  loadNotes();
});

onBeforeUnmount(() => {
  if (newNoteAnimationTimer) window.clearTimeout(newNoteAnimationTimer);
  if (noteRemovalTimer) window.clearTimeout(noteRemovalTimer);
  if (noteSearchTimer) window.clearTimeout(noteSearchTimer);
  if (manageSearchTimer) window.clearTimeout(manageSearchTimer);
  noteSearchRevision += 1;
  manageSearchRevision += 1;
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

function highlightParts(value, query) {
  const text = String(value || '');
  const terms = [...new Set(
    String(query || '').split(/\s+/).map((term) => term.trim()).filter(Boolean),
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

function searchHighlightParts(value) {
  return highlightParts(value, normalizedSearchQuery.value);
}

function notebookNameForSearchResult(note) {
  if (!note?.notebook_id) return '';
  return notesStore.notebooks.find((notebook) => notebook.id === note.notebook_id)?.name || '';
}

function localManageNoteSearch(query) {
  const terms = String(query || '').toLocaleLowerCase('de-DE').split(/\s+/).filter(Boolean);
  return notesStore.notes.filter((note) => {
    const tags = (note.tags || []).map((tag) => tag.name || '').join(' ');
    const notebook = notebookNameForSearchResult(note);
    const haystack = `${note.title || ''} ${note.preview || ''} ${tags} ${notebook}`.toLocaleLowerCase('de-DE');
    return terms.every((term) => haystack.includes(term));
  });
}

function scheduleManageSearch() {
  const query = normalizedManageSearchQuery.value;
  const revision = ++manageSearchRevision;
  if (manageSearchTimer) window.clearTimeout(manageSearchTimer);
  manageSearchTimer = null;
  if (!query) {
    manageSearchNotes.value = [];
    manageSearchLoading.value = false;
    return;
  }

  manageSearchNotes.value = localManageNoteSearch(query);
  manageSearchLoading.value = true;
  manageSearchTimer = window.setTimeout(async () => {
    manageSearchTimer = null;
    try {
      const remoteResults = await notesStore.searchNotes(query, { scope: 'all' });
      if (revision !== manageSearchRevision || query !== normalizedManageSearchQuery.value) return;
      const merged = new Map(remoteResults.map((note) => [note.id, note]));
      for (const note of localManageNoteSearch(query)) merged.set(note.id, note);
      manageSearchNotes.value = [...merged.values()];
    } catch {
      if (revision !== manageSearchRevision || query !== normalizedManageSearchQuery.value) return;
      manageSearchNotes.value = localManageNoteSearch(query);
    } finally {
      if (revision === manageSearchRevision && query === normalizedManageSearchQuery.value) {
        manageSearchLoading.value = false;
      }
    }
  }, MANAGE_SEARCH_DEBOUNCE_MS);
}

function focusManageSearch() {
  manageSearchExpanded.value = true;
  nextTick(() => manageSearchInputRef.value?.focus());
}

function clearManageSearch() {
  manageSearchQuery.value = '';
  manageSearchNotes.value = [];
  focusManageSearch();
}

function openManageNotebookResult(notebook) {
  manageSearchQuery.value = '';
  nextTick(() => manageGridRef.value?.selectNotebook?.(notebook.id));
}

async function openManageNoteResult(note) {
  manageSearchQuery.value = '';
  await openNoteFromManage(note.id);
}

function handleManageSearchKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    manageSearchQuery.value = '';
    manageSearchExpanded.value = false;
    manageSearchInputRef.value?.blur();
  }
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
  // Notizbücher still im Hintergrund laden (speisen den Notizbuch-Filter).
  notesStore.ensureNotebooksLoaded().catch(() => {});
}

// Von außen angeforderte Notiz öffnen (z. B. aus dem Dokument-Detailbereich).
// Zeitraumfilter zurücksetzen, damit die Ziel-Notiz garantiert sichtbar ist.
async function applyPendingOpen() {
  const id = notesStore.pendingOpenId;
  const cursorPosition = notesStore.pendingOpenCursorPosition;
  if (!id) return;
  await notesStore.ensureLoaded();
  if (!notesStore.notes.some((note) => note.id === id)) {
    // Nicht in der aktiven Sammlung sichtbar? Detail laden, ggf. in die
    // Sammlung der Notiz wechseln (Space-Wechsel), dann frisch laden.
    try {
      const detail = await notesStore.get(id);
      if (detail?.collection_id && detail.collection_id !== notesStore.activeCollectionId) {
        await notesStore.setActiveCollection(detail.collection_id);
      }
    } catch { /* Fällt unten auf einen erneuten Listenabruf zurück. */ }
    if (!notesStore.notes.some((note) => note.id === id)) {
      // Neu/verknüpft, aber noch nicht in der Liste: frisch laden.
      await notesStore.fetchNotes();
    }
  }
  if (notesStore.notes.some((note) => note.id === id)) {
    dateRange.value = '';
    notebookFilter.value = '';
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
  if (action === 'notebook') notebookFilter.value = value;
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
  if (!isManageMode.value) {
    manageSearchQuery.value = '';
    manageSearchExpanded.value = false;
  }
}

function normalizeManageFacet(value) {
  return value === 'templates' ? 'templates' : 'notes';
}

function loadManageFacet() {
  if (typeof window === 'undefined') return 'notes';
  try {
    return normalizeManageFacet(window.localStorage.getItem(NOTES_MANAGE_FACET_STORAGE_KEY));
  } catch {
    return 'notes';
  }
}

function persistManageFacet(value) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NOTES_MANAGE_FACET_STORAGE_KEY, normalizeManageFacet(value));
  } catch {
    // Die Verwaltung bleibt auch ohne verfügbaren Local Storage bedienbar.
  }
}

watch(manageFacet, persistManageFacet);

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

// Ist gerade ein bestimmtes Notizbuch gefiltert, entsteht die neue Notiz direkt
// darin – so bleibt sie in der gefilterten Liste sichtbar und landet dort, wo der
// Nutzer gerade arbeitet. „Ohne Notizbuch"/„Alle" erzeugen wie gehabt ohne Buch.
function newNoteInitial() {
  return notebookFilter.value && notebookFilter.value !== 'none'
    ? { notebook_id: notebookFilter.value }
    : {};
}

async function createNote() {
  if (creating.value) return;
  creating.value = true;
  loadError.value = '';
  try {
    await revealNewNote(await notesStore.create(newNoteInitial()));
  } catch {
    loadError.value = 'Die Notiz konnte nicht angelegt werden.';
  } finally {
    creating.value = false;
  }
}

// Anlegen aus der Verwaltungsfläche: neue Notiz erzeugen, Panel schließen, öffnen.
async function createNoteFromManage() {
  if (creating.value) return;
  creating.value = true;
  loadError.value = '';
  try {
    const note = await notesStore.create(newNoteInitial());
    isManageMode.value = false;
    await revealNewNote(note);
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
    // Vorlagen-Notizen entstehen ohne Notizbuch; damit die neue Notiz sichtbar
    // bleibt, den Notizbuch-Filter dafür lösen.
    notebookFilter.value = '';
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
    await notesStore.trash(note.id);
    if (isActive) await editorPanelRef.value?.discardPendingDraft?.();
    await animateNoteRemoval(note.id);
    notesStore.removeFromList(note.id);
    emit('trash-changed');
    notifyNoteDeleted(note, { restore: notesStore.restore, onRestored: () => emit('trash-changed') });
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
    notifyNoteDeleted(note, { restore: notesStore.restore, onRestored: () => emit('trash-changed') });
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

  position: relative;
  display: flex;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: var(--pm-viewer-surface, #eef2f4);
}

.notes-ws__list-panel,
.notes-ws__editor-slot,
.notes-ws__manage-panel {
  min-width: 0;
  min-height: 0;
}

.notes-ws__list-panel {
  position: relative;
  display: flex;
  width: var(--notes-list-width);
  flex: 0 0 var(--notes-list-width);
  flex-direction: column;
  overflow: hidden;
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

.notes-ws__manage-panel {
  position: absolute;
  /* Über der Formatierungsleiste und den schwebenden Editor-Menüs (bis z-index 80). */
  z-index: 100;
  inset: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-left: 0;
  background: var(--pm-content-surface, #fff);
  opacity: 1;
  transform: translateX(0);
}

/* Identische Schubladenbewegung wie beim Dokument-Lesemodus. */
.notes-ws-manage-enter-active {
  transition: transform 460ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.notes-ws-manage-leave-active {
  transition: transform 620ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.notes-ws-manage-enter-from,
.notes-ws-manage-leave-to {
  transform: translateY(100%);
}

.notes-ws-manage-enter-to,
.notes-ws-manage-leave-from {
  transform: translateY(0);
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
  display: flex;
  align-items: baseline;
  gap: 0.32em;
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

/* --- Sammlungs-Spiegel-Pille (oberster Space-Wechsel) -------------------- */
.notes-ws__collection-pill {
  display: inline-flex;
  align-items: center;
  align-self: center;
  gap: 7px;
  max-width: 168px;
  padding: 5px 9px;
  border: 1px solid color-mix(in srgb, var(--pm-text, #0f172a) 9%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-text, #0f172a) 4%, transparent);
  color: var(--pm-muted);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease;
}
.notes-ws__collection-pill:hover,
.notes-ws__collection-pill:focus-visible {
  background: color-mix(in srgb, var(--pm-text, #0f172a) 8%, transparent);
  border-color: color-mix(in srgb, var(--pm-text, #0f172a) 16%, transparent);
  color: var(--pm-text);
}
/* Horizontal in der Titelleiste zentriert (unabhängig von Titel-/Button-Breite). */
.notes-ws__collection-pill--centered {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
}
.notes-ws__collection-dot {
  flex: 0 0 auto;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--pm-coll-dot, var(--pm-accent, #006b75));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #000 14%, transparent);
}
.notes-ws__collection-name {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.notes-ws__collection-count {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--pm-muted);
}
/* Im Dropdown sitzt der Farbpunkt sonst direkt am Sammlungsnamen. */
.notes-ws__collection-menu .notes-ws__collection-dot {
  margin-inline-end: 10px;
}

.notes-ws__header-actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
}

.notes-ws__manage-header-actions {
  position: relative;
  z-index: 3;
  margin-inline-start: auto;
}

.notes-ws__manage-search {
  position: absolute;
  z-index: 4;
  top: 50%;
  left: 50%;
  display: flex;
  box-sizing: border-box;
  width: clamp(300px, 34vw, 520px);
  height: 38px;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 0 9px 0 11px;
  border: 1px solid color-mix(in srgb, var(--pm-muted) 38%, var(--pm-divider, #d8dfe1));
  border-radius: 11px;
  background: color-mix(in srgb, var(--pm-app-surface-raised, #fff) 96%, var(--pm-viewer-surface, #eef2f4));
  color: var(--pm-muted);
  cursor: text;
  box-shadow: none;
  transform: translate(-50%, -50%);
  transition: border-color 140ms ease, background-color 140ms ease;
}

.notes-ws__manage-search:hover,
.notes-ws__manage-search:focus-within {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 38%, var(--pm-divider, #d8dfe1));
  background: var(--pm-app-surface-raised, #fff);
}

.notes-ws__manage-search:focus-within {
  border-color: var(--pm-accent, #006b75);
}

.notes-ws__manage-search > .v-icon {
  flex: none;
  color: color-mix(in srgb, var(--pm-accent, #006b75) 78%, var(--pm-muted));
}

.notes-ws__manage-search input {
  width: 0;
  min-width: 0;
  flex: 1 1 auto;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.82rem;
}

.notes-ws__manage-search input::placeholder {
  color: var(--pm-muted);
  opacity: 0.92;
}

.notes-ws__manage-search input::-webkit-search-cancel-button {
  display: none;
}

.notes-ws__manage-search-clear {
  display: grid;
  width: 24px;
  height: 24px;
  flex: none;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}

.notes-ws__manage-search-clear:hover,
.notes-ws__manage-search-clear:focus-visible {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 56%, transparent);
  color: var(--pm-text);
  outline: none;
}

.notes-ws__manage-view-trigger {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  margin: -4px 0 -4px -6px;
  padding: 4px 6px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  transition: background-color 140ms ease, color 140ms ease;
}

.notes-ws__manage-view-trigger:hover,
.notes-ws__manage-view-trigger:focus-visible,
.notes-ws__manage-view-trigger[aria-expanded="true"] {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 48%, transparent);
  outline: none;
}

.notes-ws__manage-view-chevron {
  color: var(--pm-muted);
  transition: transform 160ms ease;
}

.notes-ws__manage-view-trigger[aria-expanded="true"] .notes-ws__manage-view-chevron {
  transform: rotate(180deg);
}

.notes-ws__manage-view-menu {
  width: 190px;
  padding: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  box-shadow: 0 12px 32px -14px rgba(0, 0, 0, 0.38), 0 4px 12px -8px rgba(0, 0, 0, 0.24);
}

.notes-ws__manage-view-menu button {
  display: grid;
  width: 100%;
  min-height: 38px;
  grid-template-columns: 22px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--pm-text);
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
  text-align: left;
}

.notes-ws__manage-view-menu button:hover,
.notes-ws__manage-view-menu button:focus-visible {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 50%, transparent);
  outline: none;
}

.notes-ws__manage-view-menu button.is-active {
  color: var(--pm-accent, #006b75);
  font-weight: 650;
}

.notes-ws__manage-view-check {
  grid-column: 3;
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
  padding: 15px 17px;
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
  margin-right: 25px;
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

  .notes-ws__manage-search {
    left: auto;
    right: 60px;
    width: 38px;
    justify-content: center;
    padding-inline: 0;
    transform: translateY(-50%);
  }

  .notes-ws__manage-search input,
  .notes-ws__manage-search-clear {
    display: none;
  }

  .notes-ws__manage-search.is-open {
    right: 60px;
    width: min(300px, calc(100vw - 116px));
    justify-content: flex-start;
    padding: 0 9px 0 11px;
  }

  .notes-ws__manage-search.is-open input,
  .notes-ws__manage-search.is-open .notes-ws__manage-search-clear {
    display: block;
  }

  .notes-ws__header > .notes-ws__title {
    max-width: 150px;
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
  .notes-ws__manage-view-chevron,
  .notes-ws__manage-search,
  .notes-ws__list-panel,
  .notes-ws-manage-enter-active,
  .notes-ws-manage-leave-active,
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

:global(.pm-no-animations .notes-ws__list-panel) {
  transition-duration: 0ms;
}

:global(.pm-no-animations .notes-ws-manage-enter-active),
:global(.pm-no-animations .notes-ws-manage-leave-active) {
  transition-duration: 0ms;
}

:global(.pm-no-animations) .notes-ws__manage-view-chevron {
  transition-duration: 0ms;
}
</style>
