<template>
  <div ref="listShell" class="document-list-shell docs-column" @scroll.passive="handleListScroll">
    <div v-if="activeStatusFilterLabel && !isImportsView" class="active-filter-row">
      <v-chip size="small" variant="outlined">
        Status: {{ activeStatusFilterLabel }}
      </v-chip>
    </div>

    <ListActionToolbar
      v-if="!isTrashView && !isImportsView"
      :actions="toolbarActions"
      :filter-toggles="toolbarFilterToggles"
      :selection-mode="isSelectionMode"
      :selection-count="selectionIds.size"
      :selection-disabled="selectionDisabled"
      @action-select="handleToolbarAction"
      @filter-toggle="handleToolbarFilterToggle"
      @toggle-selection="emit('toggle-selection-mode')"
      @select-all="emit('select-all')"
    />

    <div
      class="document-list-body docs-list-dropzone"
      :class="{ 'document-list-body--dragover': isListDragOver }"
      @dragenter="onListDragEnter"
      @dragover="onListDragOver"
      @dragleave="onListDragLeave"
      @drop="onListDrop"
    >
      <!--
        Landezone der Import-Fluganimation: hervorgehobene Skelett-Zeile am
        Listenkopf, in die die fliegende Dokumentkarte einrastet. Liegt als
        Overlay über der (virtualisierten) Liste, ohne deren Modell zu berühren.
      -->
      <div
        v-if="importLandingActive"
        ref="importLandingRowRef"
        class="document-row document-row--import-landing"
        :class="{
          'document-row--import-landing-resolving': importLandingResolving,
          'document-row--import-landing--snippets': showSnippets,
          'document-row--import-landing--revealed': importLandingRevealed
        }"
        aria-hidden="true"
      >
        <div class="document-row__thumb document-row--import-landing__thumb">
          <span class="document-row--import-landing__pulse" />
        </div>
        <div class="document-row__content">
          <div class="document-row--import-landing__line document-row--import-landing__line--kicker" />
          <div class="document-row--import-landing__line document-row--import-landing__line--title" />
          <div class="document-row--import-landing__line document-row--import-landing__line--meta" />
        </div>
      </div>

      <div class="document-list-content">
        <!-- Papierkorb: Dokumente als eigene Gruppe mit Anzahl (analog Notizen).
             Bewusst AUSSERHALB des virtualisierten .document-list, damit dessen
             offsetTop (= listContentOffsetTop) den Kopf mitzählt und die
             Zeilen-Virtualisierung korrekt bleibt. -->
        <div
          v-if="isTrashView && documents.length"
          class="trash-notes__heading trash-docs-heading"
        >
          <v-icon size="16">mdi-file-document-outline</v-icon>
          <span>Dokumente</span>
          <span>{{ documents.length }}</span>
        </div>

        <Transition name="pm-list-state" mode="out-in">
          <div
            v-if="showDocumentListLoadingState"
            key="loading"
            class="document-list document-list-state document-list--skeleton"
          >
            <!--
              Skelett-Zeilen erst nach kurzer Verzögerung zeigen. Der Loading-
              Zweig ist sofort aktiv (verdeckt alten Inhalt), bleibt aber in den
              ersten Millisekunden leer. Löst der Fetch schnell auf – etwa bei
              einem leeren Bereich – erscheint das Skelett nie und es geht ruhig
              direkt zum Platzhalter, statt kurz aufzublitzen.
            -->
            <Transition name="pm-skeleton-fade">
              <div v-if="skeletonRowsVisible" class="document-list__skeleton-rows">
                <v-skeleton-loader
                  v-for="n in 6"
                  :key="`skel-${n}`"
                  type="list-item-avatar-two-line"
                  class="document-row-skeleton"
                />
              </div>
            </Transition>
          </div>

          <div
            v-else-if="showDocumentListEmptyState"
            key="empty"
            class="document-list-state document-list-empty-state-wrap"
          >
            <PmEmptyState
              :icon="documentListEmptyState.icon"
              :title="documentListEmptyState.title"
              :subtitle="documentListEmptyState.subtitle"
              size="md"
            />
          </div>

          <div
            v-else
            key="documents"
            ref="documentListRef"
            class="document-list document-list-state"
            :class="{
              'document-list--with-bottom-spacer': effectiveBottomSpacerHeight > 0,
              'document-list--with-snippets': showSnippets
            }"
          >
            <div
              v-if="virtualTopPad > 0"
              class="document-list__virtual-pad"
              :style="{ height: `${virtualTopPad}px` }"
              aria-hidden="true"
            />
            <!--
              Bewusst KEIN <TransitionGroup>: Bei einer virtualisierten Liste
              wandern beim Scrollen ständig Zeilen ins Fenster hinein und wieder
              hinaus. <TransitionGroup> misst dabei über getBoundingClientRect()
              in jedem Render die Position JEDER gerenderten Zeile (FLIP) und
              erzwingt zusätzliche Reflows – bei bis zu MAX_ROW_OVERSCAN Zeilen
              im DOM ist das der Hauptgrund für ruckelndes Scrollen und verzögert
              erscheinende Einträge. Eine schlichte Liste patcht die keyed Zeilen
              ohne Layout-Messung und scrollt dadurch flüssig.
            -->
            <div class="document-list__rows">
              <div
                v-for="document in renderedDocuments"
                :key="document.id"
                class="document-row pm-doc-item"
                :data-document-id="document.id"
                :class="{
                  'document-row--active': !isSelectionMode && document.id === selectedDocumentId,
                  'document-row--selected': isSelectionMode && selectionIds.has(document.id),
                  'document-row--selection-mode': isSelectionMode,
                  'document-row--unread': document.is_unread,
                  'document-row--arrival-marker-pending': document.id === importArrivalMarkerPendingDocId,
                  'document-row--just-arrived': document.id === justArrivedDocId
                }"
                role="button"
                tabindex="0"
                @click="onRowClick($event, document.id)"
                @keydown="handleDocumentRowShortcut($event, document.id)"
              >
              <div
                class="document-row__thumb"
                :class="{
                  'document-row__thumb--selectable': isSelectionMode,
                  'document-row__thumb--error': hasThumbnailError(document.id),
                  'document-row__thumb--loaded': hasThumbnailLoaded(document.id),
                  'document-row__thumb--awaiting-import': document.id === importLandingThumbDocId
                }"
              >
                <img
                  v-if="!hasThumbnailError(document.id)"
                  :src="thumbnailUrl(document)"
                  alt="thumbnail"
                  loading="lazy"
                  decoding="async"
                  @load="onThumbnailLoad(document.id, $event)"
                  @error="onThumbnailError(document.id, $event)"
                />
                <div v-else class="document-row__thumb-fallback">
                  <v-icon size="22">mdi-file-pdf-box</v-icon>
                </div>
                <!-- Checkbox-Overlay auf dem Thumbnail -->
                <Transition name="checkbox-pop">
                  <div
                    v-if="isSelectionMode"
                    class="document-row__checkbox-overlay"
                    :class="{ 'document-row__checkbox-overlay--checked': selectionIds.has(document.id) }"
                    aria-hidden="true"
                  >
                    <v-icon v-if="selectionIds.has(document.id)" size="14">mdi-check</v-icon>
                  </div>
                </Transition>
              </div>

              <div class="document-row__content">
                <div class="document-row__kicker">
                  <span v-if="displayDocumentType(document)" class="document-row__kicker-type">{{ displayDocumentType(document) }}</span>
                  <span
                    v-if="displayDocumentType(document) && displayCorrespondent(document)"
                    class="document-row__kicker-dot"
                    aria-hidden="true"
                  >·</span>
                  <span v-if="displayCorrespondent(document)" class="document-row__kicker-corr">{{ displayCorrespondent(document) }}</span>
                </div>
                <div class="document-row__title">
                  <div class="document-row__name">{{ formatDocumentTitle(document) }}</div>
                </div>
                <div
                  v-if="Array.isArray(document.tags) && document.tags.length > 0"
                  class="document-row__tags"
                >
                  <span
                    v-for="tag in document.tags.slice(0, 3)"
                    :key="`doc-${document.id}-tag-${tag.id}`"
                    class="document-row__tag-chip"
                  >
                    {{ tag.name }}
                  </span>
                  <span
                    v-if="document.tags.length > 3"
                    key="more"
                    class="document-row__tag-chip document-row__tag-chip--more"
                  >
                    +{{ document.tags.length - 3 }}
                  </span>
                </div>
                <div
                  v-if="showSnippets && document.snippet"
                  class="document-row__snippet"
                  v-html="formatSnippet(document.snippet)"
                />
              </div>

              <div class="document-row__aside">
                <div class="document-row__actions">
                  <!-- Favoriten-Stern (nur außerhalb des Papierkorbs) -->
                  <span
                    v-if="!isTrashView"
                    class="document-row__fav-wrap"
                    :class="{ 'document-row__fav-wrap--pop': animatingFavoriteId === document.id }"
                  >
                    <v-btn
                      :icon="document.is_favorite ? 'mdi-star' : 'mdi-star-outline'"
                      variant="text"
                      size="small"
                      density="comfortable"
                      :ripple="false"
                      :class="['document-row__fav-btn', { 'document-row__fav-btn--active': document.is_favorite }]"
                      :aria-label="document.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'"
                      @click.stop="onToggleFavorite(document)"
                    />
                  </span>

                  <!-- Drei-Punkte-Menü -->
                  <v-menu location="bottom end">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        icon="mdi-dots-vertical"
                        size="small"
                        density="comfortable"
                        variant="text"
                        :ripple="false"
                        class="document-row__menu-btn"
                        aria-label="Aktionen"
                        @click.stop
                      />
                    </template>

                    <!-- Normales Menü -->
                    <v-list v-if="!isTrashView" density="compact">
                      <v-list-item @click="emit('download', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-download-outline</v-icon>
                        </template>
                        <v-list-item-title>Herunterladen</v-list-item-title>
                      </v-list-item>
                      <v-list-item @click="emit('rename', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-pencil-outline</v-icon>
                        </template>
                        <v-list-item-title>Umbenennen</v-list-item-title>
                      </v-list-item>
                      <v-list-item @click="emit('manage-tags', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-tag-multiple-outline</v-icon>
                        </template>
                        <v-list-item-title>Tags verwalten</v-list-item-title>
                      </v-list-item>
                      <v-list-item v-if="!document.is_unread" @click="emit('mark-unread', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-circle-outline</v-icon>
                        </template>
                        <v-list-item-title>Ungelesen markieren</v-list-item-title>
                      </v-list-item>
                      <v-list-item class="menu-item--danger" @click="emit('delete', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-trash-can-outline</v-icon>
                        </template>
                        <v-list-item-title>In Papierkorb</v-list-item-title>
                      </v-list-item>
                    </v-list>

                    <!-- Papierkorb-Menü -->
                    <v-list v-else density="compact">
                      <v-list-item @click="emit('restore', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-restore</v-icon>
                        </template>
                        <v-list-item-title>Wiederherstellen</v-list-item-title>
                      </v-list-item>
                      <v-list-item class="menu-item--danger" @click="emit('delete-permanent', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-delete-forever-outline</v-icon>
                        </template>
                        <v-list-item-title>Endgültig löschen…</v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-menu>
                </div>
                <div class="document-row__date">{{ displayListDate(document) }}</div>
              </div>
              </div>
            </div>
            <div
              v-if="virtualBottomPad > 0"
              class="document-list__virtual-pad"
              :style="{ height: `${virtualBottomPad}px` }"
              aria-hidden="true"
            />

            <section
              v-if="isTrashView && trashNotes.length"
              class="trash-notes"
              :class="{ 'trash-notes--only': documents.length === 0 }"
              aria-label="Gelöschte Notizen"
            >
              <div class="trash-notes__heading">
                <v-icon size="16">mdi-note-outline</v-icon>
                <span>Notizen</span>
                <span>{{ trashNotes.length }}</span>
              </div>

              <div ref="trashNoteListRef" class="document-list__rows trash-notes__rows">
                <div
                  v-for="note in trashNotes"
                  :key="`trash-note-${note.id}`"
                  class="document-row pm-trash-note"
                  :class="{ 'is-active': note.id === selectedTrashNoteId }"
                  :data-trash-note-id="note.id"
                  role="button"
                  tabindex="0"
                  :aria-current="note.id === selectedTrashNoteId ? 'true' : undefined"
                  @click="emit('select-note', note)"
                  @keydown.enter="emit('select-note', note)"
                >
                  <div class="document-row__thumb pm-trash-note__thumb" aria-hidden="true">
                    <v-icon size="24">mdi-note-outline</v-icon>
                  </div>

                  <div class="document-row__content">
                    <div class="document-row__kicker">
                      <span class="document-row__kicker-type">Notiz</span>
                    </div>
                    <div class="document-row__title">
                      <div class="document-row__name" :class="{ 'pm-trash-note__title--empty': !note.title?.trim() }">
                        {{ note.title?.trim() || 'Ohne Titel' }}
                      </div>
                    </div>
                    <div v-if="note.preview" class="document-row__snippet pm-trash-note__snippet">
                      {{ note.preview }}
                    </div>
                  </div>

                  <div class="document-row__aside">
                    <div class="document-row__actions" @click.stop>
                      <v-menu location="bottom end">
                        <template #activator="{ props: menuProps }">
                          <v-btn
                            v-bind="menuProps"
                            icon="mdi-dots-vertical"
                            size="small"
                            density="comfortable"
                            variant="text"
                            :ripple="false"
                            class="document-row__menu-btn"
                            aria-label="Aktionen"
                          />
                        </template>
                        <v-list density="compact">
                          <v-list-item @click="emit('restore-note', note)">
                            <template #prepend>
                              <v-icon size="16">mdi-restore</v-icon>
                            </template>
                            <v-list-item-title>Wiederherstellen</v-list-item-title>
                          </v-list-item>
                          <v-list-item class="menu-item--danger" @click="emit('delete-note-permanent', note)">
                            <template #prepend>
                              <v-icon size="16">mdi-delete-forever-outline</v-icon>
                            </template>
                            <v-list-item-title>Endgültig löschen…</v-list-item-title>
                          </v-list-item>
                        </v-list>
                      </v-menu>
                    </div>
                    <div class="document-row__date">{{ formatDate(note.deleted_at || note.updated_at) }}</div>
                  </div>
                </div>
              </div>
            </section>

            <div
              v-if="effectiveBottomSpacerHeight > 0"
              class="document-list__bottom-spacer"
              :style="{ height: `${effectiveBottomSpacerHeight}px` }"
              aria-hidden="true"
            />
            <div
              v-if="hasMoreDocuments"
              class="document-list__load-more"
              aria-live="polite"
            >
              <div v-if="isLoadingMoreDocuments" class="document-list__loading-more">
                <v-progress-circular
                  indeterminate
                  size="18"
                  width="2"
                  aria-hidden="true"
                />
                <span>Weitere Dokumente werden geladen</span>
              </div>
              <v-btn
                v-else
                size="x-small"
                variant="text"
                color="primary"
                append-icon="mdi-chevron-down"
                class="document-list__load-more-button"
                @click="emit('load-more')"
              >
                Weitere laden
              </v-btn>
            </div>
          </div>
        </Transition>
      </div>

      <div v-if="isListDragOver" class="document-list-drop-overlay" aria-hidden="true">
        <div class="document-list-drop-overlay__inner">
          <v-icon size="20">mdi-file-upload-outline</v-icon>
          <span>PDFs hier ablegen, um zu importieren</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount } from 'vue';

const SORT_OPTIONS = [
  { value: 'newest',      label: 'Neueste zuerst' },
  { value: 'oldest',      label: 'Älteste zuerst' },
  { value: 'name_asc',    label: 'Name A–Z' },
  { value: 'unread',      label: 'Ungelesen zuerst' },
  { value: 'favorites',   label: 'Favoriten zuerst' },
];

const DATE_RANGE_OPTIONS = [
  { value: '',               label: 'Alle Zeiträume' },
  { value: 'this_year',      label: 'Dieses Jahr' },
  { value: 'last_year',      label: 'Letztes Jahr' },
  { value: 'last_30_days',   label: 'Letzte 30 Tage' },
  { value: 'last_12_months', label: 'Letzte 12 Monate' },
];
const YEAR_RANGE_RE = /^year:(\d{4})$/;
const UNTIL_RANGE_RE = /^until:(\d{4})$/;
import { storeToRefs } from 'pinia';
import { useDocumentStore } from '../stores/documents.js';
import { useSettingsStore } from '../stores/settings.js';
import { useAuthStore } from '../stores/auth.js';
import { authedUrl, getBaseUrl } from '../api/client.js';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts.js';
import { thumbnailRetryDelay } from '../utils/thumbnailRecovery.js';
import ListActionToolbar from './ListActionToolbar.vue';
import PmEmptyState from './PmEmptyState.vue';

// ── Props & Emits ──────────────────────────────────────────────────────────
const props = defineProps({
  listDropNotice:             { type: String,  default: '' },
  activeStatusFilterLabel:    { type: String,  default: '' },
  isImportsView:              { type: Boolean, default: false },
  isTrashView:                { type: Boolean, default: false },
  showDocumentListLoadingState: { type: Boolean, default: false },
  showDocumentListEmptyState:   { type: Boolean, default: false },
  documentListEmptyState:       { type: Object,  default: () => ({ icon: '', title: '', subtitle: '' }) },
  showSnippets:               { type: Boolean, default: false },
  isSelectionMode:            { type: Boolean, default: false },
  selectionDisabled:          { type: Boolean, default: false },
  selectionIds:               { type: Set,     default: () => new Set() },
  currentSort:                { type: String,  default: 'newest' },
  currentDateRange:           { type: String,  default: '' },
  showTagFilterToggle:        { type: Boolean, default: false },
  tagFilterDrawerOpen:        { type: Boolean, default: false },
  showDocumentTypeFilterToggle: { type: Boolean, default: false },
  documentTypeFilterDrawerOpen: { type: Boolean, default: false },
  bottomSpacerHeight:         { type: Number,  default: 0 },
  hasMoreDocuments:           { type: Boolean, default: false },
  isLoadingMoreDocuments:     { type: Boolean, default: false },
  loadedDocumentCount:        { type: Number,  default: 0 },
  trashNotes:                 { type: Array,   default: () => [] },
  selectedTrashNoteId:        { type: String,  default: null },
});

const emit = defineEmits([
  'select-document',
  'download',
  'rename',
  'manage-tags',
  'mark-unread',
  'delete',
  'restore',
  'delete-permanent',
  'select-note',
  'restore-note',
  'delete-note-permanent',
  'toggle-favorite',
  'files-dropped',
  'toggle-selection-mode',
  'toggle-document-selection',
  'select-all',
  'change-sort',
  'change-date-range',
  'toggle-tag-filter-drawer',
  'toggle-document-type-filter-drawer',
  'load-more',
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const docStore      = useDocumentStore();
const settingsStore = useSettingsStore();
const authStore     = useAuthStore();

const { documents, selectedDocumentId } = storeToRefs(docStore);
const listShell = ref(null);
const documentListRef = ref(null);
const trashNoteListRef = ref(null);

// ── Import-Fluganimation: Landezone ─────────────────────────────────────────
const importLandingActive = ref(false);
const importLandingResolving = ref(false);
// Skelett-Fallback bleibt während des Flugs UNSICHTBAR (nur Messung) und wird
// erst bei der Landung eingeblendet – so liegt nie ein breites Skelett unter der
// noch großen Flugkarte (das zerstörte die Illusion).
const importLandingRevealed = ref(false);
const importLandingRowRef = ref(null);
// Das Ziel-Thumbnail ist ab dem ersten Rendern der neuen Zeile weiß. Erst die
// landende Karte „liefert" das echte Vorschaubild ab. Die ID wird deshalb schon
// vor dem Nachladen der Liste gesetzt, damit das korrekte Bild nie kurz aufblitzt.
const importLandingThumbDocId = ref('');
let pendingLandingThumbDocId = '';
let importLandingRevealRequested = false;
// Der Ungelesen-Balken gehört zum abgeschlossenen Ankunftszustand. Während
// Flug und Aufleuchten bleibt er verborgen und wird erst nach dem letzten Puls
// freigegeben.
const importArrivalMarkerPendingDocId = ref('');
let importArrivalMarkerTimer = 0;
const IMPORT_ARRIVAL_MARKER_DELAY_MS = 1600;
const IMPORT_ARRIVAL_MARKER_REDUCED_DELAY_MS = 600;
// Frisch importierte Zeile kurz hervorheben, sobald die echten Daten stehen.
const justArrivedDocId = ref('');
let justArrivedTimer = 0;

// Löschanimationen laufen nur auf den konkret betroffenen DOM-Zeilen. So bleibt
// das Scrollen der virtualisierten Liste frei von permanenten FLIP-Messungen.
const DOCUMENT_REMOVAL_DURATION_MS = 210;
const TRASH_EMPTY_STAGGER_MS = 12;
const TRASH_EMPTY_MAX_STAGGER_MS = 120;
const documentRemovalWaiters = new Map();

function documentListMotionDisabled() {
  if (typeof window === 'undefined') return true;
  if (document.querySelector('.pm-no-animations')) return true;
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false;
}

function waitForDocumentRemoval(additionalDelayMs = 0) {
  return new Promise((resolve) => {
    let timer = 0;
    const finish = () => {
      documentRemovalWaiters.delete(timer);
      resolve();
    };
    timer = window.setTimeout(
      finish,
      DOCUMENT_REMOVAL_DURATION_MS + Math.max(0, Number(additionalDelayMs) || 0)
    );
    documentRemovalWaiters.set(timer, finish);
  });
}

async function animateDocumentRemoval(documentIds = []) {
  const ids = new Set(
    (Array.isArray(documentIds) ? documentIds : [documentIds])
      .map((id) => String(id || '').trim())
      .filter(Boolean)
  );
  if (ids.size === 0 || documentListMotionDisabled()) return;

  const rows = Array.from(documentListRef.value?.querySelectorAll(
    '.document-list__rows .document-row[data-document-id]'
  ) || []).filter((row) => ids.has(String(row.dataset.documentId || '')));
  if (rows.length === 0) return;

  rows.forEach((row) => {
    row.setAttribute('aria-hidden', 'true');
    row.classList.add('document-row--removing');
  });
  await waitForDocumentRemoval();
}

async function animateTrashNoteRemoval(noteIds = []) {
  const ids = new Set(
    (Array.isArray(noteIds) ? noteIds : [noteIds])
      .map((id) => String(id || '').trim())
      .filter(Boolean)
  );
  if (ids.size === 0 || documentListMotionDisabled()) return;

  const rows = Array.from(trashNoteListRef.value?.querySelectorAll(
    '.pm-trash-note[data-trash-note-id]'
  ) || []).filter((row) => ids.has(String(row.dataset.trashNoteId || '')));
  if (rows.length === 0) return;

  rows.forEach((row) => {
    row.setAttribute('aria-hidden', 'true');
    row.classList.add('document-row--removing');
  });
  await waitForDocumentRemoval();
}

async function animateTrashEmpty() {
  if (documentListMotionDisabled()) return;

  // Die Dokumentliste ist virtualisiert: Animiert werden deshalb bewusst alle
  // aktuell gerenderten Dokument- und Notizzeilen in ihrer sichtbaren Reihenfolge.
  const rows = Array.from(documentListRef.value?.querySelectorAll(
    '.document-row[data-document-id], .pm-trash-note[data-trash-note-id]'
  ) || []);
  if (rows.length === 0) return;

  let lastDelayMs = 0;
  rows.forEach((row, index) => {
    const delayMs = Math.min(index * TRASH_EMPTY_STAGGER_MS, TRASH_EMPTY_MAX_STAGGER_MS);
    lastDelayMs = Math.max(lastDelayMs, delayMs);
    row.style.setProperty('--pm-removal-delay', `${delayMs}ms`);
    row.setAttribute('aria-hidden', 'true');
    row.classList.add('document-row--removing');
  });
  await waitForDocumentRemoval(lastDelayMs);
}

function importArrivalMarkerDelay() {
  if (typeof window === 'undefined') return 0;
  if (document.querySelector('.pm-no-animations')) return 0;
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    ? IMPORT_ARRIVAL_MARKER_REDUCED_DELAY_MS
    : IMPORT_ARRIVAL_MARKER_DELAY_MS;
}

// Bereitet die Zielzeile vor, bevor fetchDocuments() sie rendert. So bekommt das
// neue Item unmittelbar den weißen Platzhalter statt zunächst das echte Bild.
function prepareImportLanding(documentId = '') {
  const id = String(documentId || '').trim();
  if (importArrivalMarkerTimer) {
    window.clearTimeout(importArrivalMarkerTimer);
    importArrivalMarkerTimer = 0;
  }
  importLandingRevealRequested = false;
  importArrivalMarkerPendingDocId.value = id;
  pendingLandingThumbDocId = id;
  importLandingThumbDocId.value = id;
}

function importLandingVisualMetrics(element) {
  if (!(element instanceof HTMLElement) || typeof window === 'undefined') return {};
  const numberValue = (value, fallback = 0) => {
    const parsed = Number.parseFloat(String(value || ''));
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const frameStyle = window.getComputedStyle(element);
  const image = element.querySelector('img');
  const imageStyle = image ? window.getComputedStyle(image) : null;
  return {
    borderRadius: numberValue(frameStyle.borderTopLeftRadius, 6),
    borderWidth: numberValue(frameStyle.borderTopWidth, 1),
    borderColor: frameStyle.borderTopColor || 'transparent',
    backgroundColor: frameStyle.backgroundColor || '#fff',
    boxShadow: frameStyle.boxShadow || 'none',
    imageFit: imageStyle?.objectFit || 'cover',
    imagePosition: imageStyle?.objectPosition || 'top center'
  };
}

// Liefert das Flugziel: bevorzugt das THUMBNAIL der konkret importierten Zeile
// (die durch das parallele Nachladen meist schon steht) → nahtloser Hero-Übergang,
// die Karte legt sich passgenau auf das echte Vorschaubild. Nur wenn noch keine
// Zeile da ist, dient ein (zunächst unsichtbares) Skelett als Landeplatz.
async function beginImportLanding(documentId = '') {
  importLandingResolving.value = false;

  const landingId = String(documentId || pendingLandingThumbDocId || '').trim();
  const rows = Array.from(documentListRef.value?.querySelectorAll(
    '.document-list__rows .document-row[data-document-id]'
  ) || []);
  const realRow = landingId
    ? rows.find((row) => String(row.dataset.documentId || '') === landingId)
    : rows[0];
  const realThumb = realRow?.querySelector('.document-row__thumb');
  if (realThumb) {
    const r = realThumb.getBoundingClientRect();
    if (r.width >= 4 && r.height >= 4) {
      importLandingActive.value = false; // kein Skelett nötig
      pendingLandingThumbDocId = landingId || String(realRow.dataset.documentId || '');
      importLandingThumbDocId.value = pendingLandingThumbDocId;
      return {
        left: r.left,
        top: r.top,
        width: r.width,
        height: r.height,
        onRealRow: true,
        ...importLandingVisualMetrics(realThumb)
      };
    }
  }

  // Fallback: Skelett rendern, aber unsichtbar halten (nur zum Messen/Landen).
  importLandingActive.value = true;
  importLandingRevealed.value = false;
  await nextTick();
  const el = importLandingRowRef.value;
  if (!el) {
    importLandingActive.value = false;
    return null;
  }
  const thumbEl = el.querySelector('.document-row--import-landing__thumb');
  const rect = (thumbEl || el).getBoundingClientRect();
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    onRealRow: false,
    ...importLandingVisualMetrics(thumbEl || el)
  };
}

// Wird im Moment der Landung aufgerufen: blendet das Fallback-Skelett ein
// (falls verwendet), damit es genau dann erscheint, wenn die Karte klein in der
// Thumbnail-Spalte ankommt – nie vorher.
// Endanflug: Sicherheitsnetz für ältere/alternative Aufrufer. Im regulären
// Ablauf ist die Maske bereits durch prepareImportLanding() aktiv.
function maskLandingThumb() {
  if (pendingLandingThumbDocId) {
    importLandingThumbDocId.value = pendingLandingThumbDocId;
  }
}

function completeImportLandingThumbReveal(documentId = '') {
  const id = String(documentId || '').trim();
  const targetId = String(importLandingThumbDocId.value || pendingLandingThumbDocId || '').trim();
  if (id && targetId && id !== targetId) return;
  importLandingThumbDocId.value = '';
  pendingLandingThumbDocId = '';
  importLandingRevealRequested = false;
}

function revealImportLanding() {
  // Die Landung allein reicht nicht: Das Listenbild wird erst aufgedeckt, wenn
  // es vollständig geladen/dekodiert ist. Bis dahin bleibt das Blatt weiß und
  // der dunkle Standard-Shimmer kann nicht kurz sichtbar werden.
  importLandingRevealRequested = true;
  const id = String(importLandingThumbDocId.value || pendingLandingThumbDocId || '').trim();
  if (!id || hasThumbnailLoaded(id) || hasThumbnailError(id)) {
    completeImportLandingThumbReveal(id);
  }
  if (importLandingActive.value) {
    importLandingRevealed.value = true;
  }
}

// Löst die Landung auf: das Skelett (falls sichtbar) verblasst, die echte (erste)
// Zeile leuchtet kurz auf. `documentId` markiert die anzuhebende Zeile.
function resolveImportLanding(documentId = '') {
  // Sicherheitsnetz für einen ausgebliebenen Landed-Callback. Die Maske wird
  // dabei weiterhin erst gelöst, sobald das Listen-Thumbnail bereit ist.
  revealImportLanding();
  const id = String(documentId || '').trim();
  if (id) {
    importArrivalMarkerPendingDocId.value = id;
    justArrivedDocId.value = id;
    if (justArrivedTimer) window.clearTimeout(justArrivedTimer);
    justArrivedTimer = window.setTimeout(() => {
      justArrivedDocId.value = '';
      justArrivedTimer = 0;
    }, 1900);

    if (importArrivalMarkerTimer) window.clearTimeout(importArrivalMarkerTimer);
    // Ab dem nächsten Render-Takt laufen Zeilenpuls und Verzögerung gemeinsam.
    // So erscheint der Balken auch bei einem längeren Anflug niemals vorzeitig.
    nextTick(() => {
      if (importArrivalMarkerPendingDocId.value !== id) return;
      const delay = importArrivalMarkerDelay();
      if (delay <= 0) {
        importArrivalMarkerPendingDocId.value = '';
        return;
      }
      importArrivalMarkerTimer = window.setTimeout(() => {
        if (importArrivalMarkerPendingDocId.value === id) {
          importArrivalMarkerPendingDocId.value = '';
        }
        importArrivalMarkerTimer = 0;
      }, delay);
    });
  }
  if (importLandingActive.value) {
    importLandingResolving.value = true;
    // Skelett nach kurzer Übergabe entfernen.
    window.setTimeout(() => {
      importLandingActive.value = false;
      importLandingResolving.value = false;
      importLandingRevealed.value = false;
    }, 260);
  }
}

function cancelImportLanding() {
  importLandingActive.value = false;
  importLandingResolving.value = false;
  importLandingRevealed.value = false;
  importLandingThumbDocId.value = '';
  importLandingRevealRequested = false;
  importArrivalMarkerPendingDocId.value = '';
  pendingLandingThumbDocId = '';
  if (importArrivalMarkerTimer) {
    window.clearTimeout(importArrivalMarkerTimer);
    importArrivalMarkerTimer = 0;
  }
}
const showPdfSuffixComputed = computed(() => settingsStore.settingsDraft?.ui?.showFilenameSuffix ?? false);
const DOCUMENT_LIST_BOTTOM_SPACER = 16;
const effectiveBottomSpacerHeight = computed(() =>
  DOCUMENT_LIST_BOTTOM_SPACER + Math.max(0, Number(props.bottomSpacerHeight || 0))
);

// ── Virtualisierung (Windowing) ─────────────────────────────────────────────
// Die Liste bleibt ab der ersten Seite im gleichen Windowing-Modus. Dadurch
// entsteht beim ersten Nachladen kein Wechsel von "volle DOM-Liste" zu
// "virtualisiertes Fenster". Die Zeilen haben feste Layout-Metriken; Spacer
// müssen während des Scrollens nicht nachgemessen und korrigiert werden.
const VIRTUAL_ROW_HEIGHT = 112;
const VIRTUAL_ROW_HEIGHT_WITH_SNIPPET = 152;
const VIRTUAL_ROW_GAP = 10;
// Bei schnellen Trackpad-/Mausrad-Sprüngen muss ein ganzer Sichtbereich
// bereits im DOM liegen, bevor das nächste rAF die Fenstergrenzen nachzieht.
// Der etwas grössere Puffer verhindert kurzzeitig leere Listenzeilen, bleibt
// mit rund 50–70 Zeilen aber deutlich unter einer unvirtualisierten Liste.
const ROW_OVERSCAN = 24;
// Geschwindigkeitsabhängiger Overscan: Bei schnellem Fling scrollt der
// Compositor dem rAF-getakteten Fenster-Update voraus → kurzzeitig leere
// Zeilen. Dann puffern wir zusätzliche Zeilen IN Scroll-Richtung (dort
// entstehen die Lücken), gedeckelt, und fallen nach dem Anhalten auf die
// Basis zurück, damit langsames/ruhendes Scrollen ein schlankes DOM behält.
const MAX_ROW_OVERSCAN = 140;
const VELOCITY_OVERSCAN_FACTOR = 3;
const OVERSCAN_SETTLE_MS = 180;
const VIRTUAL_WINDOW_SAFETY_ROWS = 8;
// Die Folgeseite wird deutlich vor dem sichtbaren Listenende angefordert. So
// erreicht ein schneller Fling in der Regel nie den Ladeindikator.
const LOAD_MORE_AHEAD_ROWS = 18;
const LOAD_MORE_AHEAD_VIEWPORTS = 2;

const listScrollTop = ref(0);
const listViewport = ref(0);
const listContentOffsetTop = ref(0);
// Richtungsabhängiger Puffer (Zeilen) ober-/unterhalb des Sichtbereichs.
const startOverscan = ref(ROW_OVERSCAN);
const endOverscan = ref(ROW_OVERSCAN);
let overscanResetTimer = null;
let virtualWindowFrame = 0;
let pendingVirtualWindowElement = null;
// Getrennt vom zuletzt *gerenderten* Scrollstand (`listScrollTop`): Der Wert
// wird schon im Scroll-Handler fortgeschrieben und dient ausschließlich dazu,
// die Richtung aufeinanderfolgender Browser-Events zu erkennen.
let lastHandledListScrollTop = 0;
let listResizeObserver = null;
let thumbnailRecoveryDisposed = false;
let deletionVirtualWindowTimer = null;
const deletionVirtualWindow = ref(null);

const isVirtualized = computed(() => documents.value.length > 0);
const virtualRowHeight = computed(() =>
  props.showSnippets ? VIRTUAL_ROW_HEIGHT_WITH_SNIPPET : VIRTUAL_ROW_HEIGHT
);
const virtualRowStep = computed(() => virtualRowHeight.value + VIRTUAL_ROW_GAP);
const rowRelativeScrollTop = computed(() =>
  Math.max(0, listScrollTop.value - listContentOffsetTop.value)
);

const calculatedVirtualStartIndex = computed(() => {
  if (!isVirtualized.value) return 0;
  return Math.max(0, Math.floor(rowRelativeScrollTop.value / virtualRowStep.value) - startOverscan.value);
});

const requestedVirtualEndIndex = computed(() => {
  const visibleEnd = Math.ceil((rowRelativeScrollTop.value + (listViewport.value || 0)) / virtualRowStep.value);
  return Math.max(calculatedVirtualStartIndex.value + 1, visibleEnd + endOverscan.value);
});

const calculatedVirtualEndIndex = computed(() => {
  if (!isVirtualized.value) return documents.value.length;
  return Math.min(documents.value.length, requestedVirtualEndIndex.value);
});

// Beim Löschen einer sichtbaren Zeile bleibt das virtuelle Fenster für einen
// Frame der Ausblendung konstant. Ohne diese kurze Sperre würde gleichzeitig
// am Ende des Fensters ein neuer Eintrag nachrücken und den FLIP-Übergang
// sichtbar stottern lassen.
const virtualStartIndex = computed(() =>
  deletionVirtualWindow.value?.start ?? calculatedVirtualStartIndex.value
);
const virtualEndIndex = computed(() =>
  deletionVirtualWindow.value?.end ?? calculatedVirtualEndIndex.value
);

const renderedDocuments = computed(() => {
  if (!isVirtualized.value) return documents.value;
  return documents.value.slice(virtualStartIndex.value, virtualEndIndex.value);
});

const virtualTopPad = computed(() =>
  isVirtualized.value ? virtualStartIndex.value * virtualRowStep.value : 0
);

const virtualBottomPad = computed(() => {
  if (!isVirtualized.value) return 0;
  return Math.max(0, (documents.value.length - virtualEndIndex.value) * virtualRowStep.value);
});

watch(
  () => documents.value.map((document) => document.id),
  (nextIds, previousIds = []) => {
    const isSingleRemoval = previousIds.length === nextIds.length + 1;
    if (!isSingleRemoval) return;

    const nextIdSet = new Set(nextIds);
    const removedIndex = previousIds.findIndex((id) => !nextIdSet.has(id));
    const start = calculatedVirtualStartIndex.value;
    const visibleEndBeforeRemoval = Math.min(previousIds.length, requestedVirtualEndIndex.value);
    const wasVisible = removedIndex >= start && removedIndex < visibleEndBeforeRemoval;
    if (!wasVisible) return;

    deletionVirtualWindow.value = {
      start,
      end: Math.max(start, visibleEndBeforeRemoval - 1),
    };
    if (deletionVirtualWindowTimer) window.clearTimeout(deletionVirtualWindowTimer);
    deletionVirtualWindowTimer = window.setTimeout(() => {
      deletionVirtualWindow.value = null;
      deletionVirtualWindowTimer = null;
    }, 260);
  },
  { flush: 'sync' }
);

function updateVirtualWindow(element = listShell.value) {
  if (!element) return;
  const nextScrollTop = element.scrollTop;
  // listScrollTop ist der Stand, für den Vue das letzte virtuelle Fenster
  // berechnet hat. Gegen diesen Wert muss die Distanz gemessen werden. Der
  // Scroll-Handler kennt zwar schon die neueste Position, darf sie aber nicht
  // vorab als Messbasis setzen – sonst wäre die Geschwindigkeit immer 0.
  applyScrollVelocityOverscan(nextScrollTop - listScrollTop.value);
  listScrollTop.value = nextScrollTop;
  lastHandledListScrollTop = nextScrollTop;
  listViewport.value = element.clientHeight;
  listContentOffsetTop.value = documentListRef.value?.offsetTop || 0;
}

// Puffert bei schnellem Scrollen zusätzliche Zeilen in Scroll-Richtung, damit
// dem Compositor beim Fling nie leere Zeilen vorauseilen. `delta` ist die
// (rAF-getaktete) Scroll-Distanz seit dem letzten Update in Pixeln.
function applyScrollVelocityOverscan(delta) {
  if (!delta) return;
  const rowsPerFrame = Math.abs(delta) / virtualRowStep.value;
  const dynamic = Math.min(
    MAX_ROW_OVERSCAN,
    ROW_OVERSCAN + Math.ceil(rowsPerFrame * VELOCITY_OVERSCAN_FACTOR)
  );
  if (delta > 0) {
    endOverscan.value = dynamic;       // nach unten → Puffer unterhalb
    startOverscan.value = ROW_OVERSCAN;
  } else {
    startOverscan.value = dynamic;     // nach oben → Puffer oberhalb
    endOverscan.value = ROW_OVERSCAN;
  }
  if (overscanResetTimer) window.clearTimeout(overscanResetTimer);
  overscanResetTimer = window.setTimeout(() => {
    overscanResetTimer = null;
    // Nach dem Anhalten wieder auf die Basis – schlankes DOM bei Ruhe/langsam.
    startOverscan.value = ROW_OVERSCAN;
    endOverscan.value = ROW_OVERSCAN;
  }, OVERSCAN_SETTLE_MS);
}

function scheduleVirtualWindowUpdate(element = listShell.value) {
  if (!element) return;
  pendingVirtualWindowElement = element;
  if (virtualWindowFrame) return;
  virtualWindowFrame = requestAnimationFrame(() => {
    virtualWindowFrame = 0;
    updateVirtualWindow(pendingVirtualWindowElement || listShell.value);
    pendingVirtualWindowElement = null;
  });
}

function requestMoreIfNearEnd(element = listShell.value) {
  if (!element || !props.hasMoreDocuments || props.isLoadingMoreDocuments) return;
  const remaining = element.scrollHeight - element.scrollTop - element.clientHeight;
  const loadAheadDistance = Math.max(
    LOAD_MORE_AHEAD_ROWS * virtualRowStep.value,
    element.clientHeight * LOAD_MORE_AHEAD_VIEWPORTS
  );
  if (remaining <= loadAheadDistance) {
    emit('load-more');
  }
}

function handleListScroll(event) {
  const element = event.currentTarget;
  const nextScrollTop = element.scrollTop;
  const scrollingDown = nextScrollTop >= lastHandledListScrollTop;
  lastHandledListScrollTop = nextScrollTop;

  const relativeScrollTop = Math.max(0, nextScrollTop - listContentOffsetTop.value);
  const firstVisibleRow = Math.floor(relativeScrollTop / virtualRowStep.value);
  const lastVisibleRow = Math.ceil(
    (relativeScrollTop + (listViewport.value || element.clientHeight)) / virtualRowStep.value
  );
  const isApproachingWindowEdge = scrollingDown
    ? lastVisibleRow >= virtualEndIndex.value - VIRTUAL_WINDOW_SAFETY_ROWS
    : firstVisibleRow <= virtualStartIndex.value + VIRTUAL_WINDOW_SAFETY_ROWS;

  if (isApproachingWindowEdge) {
    // Keine rAF-Latenz, wenn das aktuelle Sichtfenster den gerenderten Puffer
    // fast eingeholt hat. So bleibt bei schnellen Sprüngen stets eine Zeile
    // unter dem Viewport vorhanden.
    updateVirtualWindow(element);
  } else {
    scheduleVirtualWindowUpdate(element);
  }
  requestMoreIfNearEnd(element);
}

// Liste neu vermessen, wenn sich der Bestand ändert (Fenster + Zeilenhöhe).
watch(
  () => documents.value.length,
  () => {
    void nextTick(() => {
      updateVirtualWindow();
    });
  }
);

watch(
  () => [props.showSnippets, props.isImportsView, props.activeStatusFilterLabel],
  () => {
    void nextTick(() => updateVirtualWindow());
  }
);

onMounted(() => {
  thumbnailRecoveryDisposed = false;
  updateVirtualWindow();
  if (typeof ResizeObserver !== 'undefined' && listShell.value) {
    listResizeObserver = new ResizeObserver(() => updateVirtualWindow());
    listResizeObserver.observe(listShell.value);
  }
  window.addEventListener('online', recoverErroredThumbnails);
  document.addEventListener('visibilitychange', handleThumbnailVisibilityChange);
});

defineExpose({
  animateDocumentRemoval,
  animateTrashNoteRemoval,
  animateTrashEmpty,
  prepareImportLanding,
  beginImportLanding,
  maskLandingThumb,
  revealImportLanding,
  resolveImportLanding,
  cancelImportLanding
});

onBeforeUnmount(() => {
  thumbnailRecoveryDisposed = true;
  for (const [timer, finish] of documentRemovalWaiters) {
    window.clearTimeout(timer);
    finish();
  }
  if (virtualWindowFrame) cancelAnimationFrame(virtualWindowFrame);
  if (deletionVirtualWindowTimer) window.clearTimeout(deletionVirtualWindowTimer);
  if (overscanResetTimer) window.clearTimeout(overscanResetTimer);
  if (favoriteAnimTimer) window.clearTimeout(favoriteAnimTimer);
  if (skeletonRevealTimer) window.clearTimeout(skeletonRevealTimer);
  if (justArrivedTimer) window.clearTimeout(justArrivedTimer);
  if (importArrivalMarkerTimer) window.clearTimeout(importArrivalMarkerTimer);
  if (listResizeObserver) {
    listResizeObserver.disconnect();
    listResizeObserver = null;
  }
  window.removeEventListener('online', recoverErroredThumbnails);
  document.removeEventListener('visibilitychange', handleThumbnailVisibilityChange);
  for (const timer of thumbnailRetryTimerByDocumentId.values()) {
    window.clearTimeout(timer);
  }
  thumbnailRetryTimerByDocumentId.clear();
  thumbnailRetryAttemptByDocumentId.clear();
  thumbnailUrlCache.clear();
});

watch(
  () => [props.hasMoreDocuments, props.isLoadingMoreDocuments, props.loadedDocumentCount],
  () => {
    void nextTick(() => requestMoreIfNearEnd());
  },
  { flush: 'post' }
);

const sortLabel      = computed(() => SORT_OPTIONS.find(o => o.value === props.currentSort)?.label ?? 'Sortierung');
const dateRangeLabel = computed(() => {
  const yearMatch = YEAR_RANGE_RE.exec(props.currentDateRange || '');
  if (yearMatch) return yearMatch[1];
  const untilMatch = UNTIL_RANGE_RE.exec(props.currentDateRange || '');
  if (untilMatch) return `bis ${untilMatch[1]}`;
  return DATE_RANGE_OPTIONS.find(o => o.value === props.currentDateRange)?.label ?? 'Zeitraum';
});
const toolbarActions = computed(() => [
  {
    key: 'sort',
    icon: 'mdi-sort',
    label: sortLabel.value,
    value: props.currentSort,
    options: SORT_OPTIONS,
    minWidth: 190
  },
  {
    key: 'dateRange',
    icon: 'mdi-calendar-range',
    label: dateRangeLabel.value,
    value: props.currentDateRange,
    active: Boolean(props.currentDateRange),
    options: DATE_RANGE_OPTIONS,
    minWidth: 180
  }
]);
const toolbarFilterToggles = computed(() => {
  const toggles = [];
  if (props.showDocumentTypeFilterToggle) {
    toggles.push({
      key: 'documentTypeFilter',
      icon: 'mdi-file-document-outline',
      label: 'Typen',
      ariaLabel: props.documentTypeFilterDrawerOpen
        ? 'Dokumenttyp-Filter ausblenden'
        : 'Dokumenttyp-Filter einblenden',
      active: props.documentTypeFilterDrawerOpen
    });
  }
  if (props.showTagFilterToggle) {
    toggles.push({
      key: 'tagFilter',
      icon: 'mdi-tag-multiple-outline',
      label: 'Tags',
      ariaLabel: props.tagFilterDrawerOpen ? 'Tag-Filter ausblenden' : 'Tag-Filter einblenden',
      active: props.tagFilterDrawerOpen
    });
  }
  return toggles;
});

// ── Refs ───────────────────────────────────────────────────────────────────
const thumbnailErrorMap = ref({});
const thumbnailLoadedMap = ref({});
const isListDragOver    = ref(false);
const listDropDragDepth = ref(0);
const thumbnailVersionByDocumentId = ref({});
const thumbnailSignatureByDocumentId = ref({});
const thumbnailRetryAttemptByDocumentId = new Map();
const thumbnailRetryTimerByDocumentId = new Map();

// Treibt den Thumbnail-State-Watch unten: erkennt, wenn sich für ein Dokument
// updated_at/status/ocr_status ändert (z. B. nach OCR), um Fehler-/Versionsstate
// zurückzusetzen. Single-Pass ohne Zwischen-Array, um Allokationen bei großen
// Listen gering zu halten; die String-Gleichheit als Änderungssignal bleibt.
const documentThumbnailSignature = computed(() => {
  let signature = '';
  for (const document of documents.value) {
    signature += thumbnailStateKey(document);
    signature += '|';
  }
  return signature;
});

function handleToolbarAction({ action, value }) {
  if (action === 'sort') {
    emit('change-sort', value);
    return;
  }
  if (action === 'dateRange') {
    emit('change-date-range', value);
  }
}

function handleToolbarFilterToggle(action) {
  if (action === 'documentTypeFilter') {
    emit('toggle-document-type-filter-drawer');
    return;
  }
  if (action === 'tagFilter') {
    emit('toggle-tag-filter-drawer');
  }
}

// ── Thumbnail helpers ──────────────────────────────────────────────────────
function appendUrlParam(url, key, value) {
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
}

function thumbnailStateKey(document) {
  return [
    document?.id || '',
    document?.updated_at || '',
    document?.status || '',
    document?.ocr_status || '',
  ].join(':');
}

// Gebaute Thumbnail-URLs je Dokument zwischenspeichern. Die URL hängt bewusst
// NUR an Inhalts-Signatur (updated_at) + Fehler-Retry-Version, NICHT an der
// rotierenden fileTokenVersion. Sonst bekämen bei jeder Token-Erneuerung (~4,5
// min) alle sichtbaren Thumbnails eine neue URL und luden gleichzeitig neu
// ("Blitz durch die Liste"). Ein bereits geladenes Bild bleibt im Browser-Cache
// gültig; ein abgelaufenes Token trifft nur noch NICHT geladene Bilder, deren
// Fehler-Retry dann ein frisches Token einbaut.
const thumbnailUrlCache = new Map();

function thumbnailUrl(document) {
  const documentId = document?.id;
  if (!documentId) return '';
  const sig = [
    document?.updated_at || '',
    thumbnailVersionByDocumentId.value[documentId] || 0,
  ].join(':');
  const cached = thumbnailUrlCache.get(documentId);
  if (cached && cached.sig === sig) {
    return cached.url;
  }
  const base = authedUrl(`${getBaseUrl()}/api/documents/${documentId}/thumbnail`);
  const url = appendUrlParam(base, 'thumb_v', sig);
  thumbnailUrlCache.set(documentId, { sig, url });
  return url;
}

// Nur Thumbnails, die aktuell im Fehlerzustand sind, mit frischem Token erneut
// versuchen (z. B. nachdem das Token nach dem Login angekommen ist). Bereits
// geladene Bilder bleiben unangetastet → kein periodisches Neuladen.
function retryErroredThumbnails() {
  const erroredIds = Object.keys(thumbnailErrorMap.value);
  if (erroredIds.length === 0) return;
  const nextVersions = { ...thumbnailVersionByDocumentId.value };
  const nextLoaded = { ...thumbnailLoadedMap.value };
  for (const documentId of erroredIds) {
    clearThumbnailRetryTimer(documentId);
    nextVersions[documentId] = Number(nextVersions[documentId] || 0) + 1;
    thumbnailUrlCache.delete(documentId);
    delete nextLoaded[documentId];
  }
  thumbnailErrorMap.value = {};
  thumbnailLoadedMap.value = nextLoaded;
  thumbnailVersionByDocumentId.value = nextVersions;
}

function clearThumbnailRetryTimer(documentId) {
  const timer = thumbnailRetryTimerByDocumentId.get(documentId);
  if (timer !== undefined) {
    window.clearTimeout(timer);
    thumbnailRetryTimerByDocumentId.delete(documentId);
  }
}

function retryThumbnail(documentId) {
  if (!thumbnailSignatureByDocumentId.value[documentId]) return;
  clearThumbnailRetryTimer(documentId);
  const nextErrors = { ...thumbnailErrorMap.value };
  delete nextErrors[documentId];
  thumbnailErrorMap.value = nextErrors;
  const nextLoaded = { ...thumbnailLoadedMap.value };
  delete nextLoaded[documentId];
  thumbnailLoadedMap.value = nextLoaded;
  thumbnailVersionByDocumentId.value = {
    ...thumbnailVersionByDocumentId.value,
    [documentId]: Number(thumbnailVersionByDocumentId.value[documentId] || 0) + 1,
  };
  thumbnailUrlCache.delete(documentId);
}

async function runThumbnailRetry(documentId) {
  thumbnailRetryTimerByDocumentId.delete(documentId);
  if (thumbnailRecoveryDisposed || !thumbnailErrorMap.value[documentId]) return;
  await authStore.refreshFileToken();
  if (thumbnailRecoveryDisposed || !thumbnailErrorMap.value[documentId]) return;
  retryThumbnail(documentId);
}

async function recoverErroredThumbnails() {
  if (Object.keys(thumbnailErrorMap.value).length === 0) return;
  await authStore.refreshFileToken();
  if (thumbnailRecoveryDisposed) return;
  retryErroredThumbnails();
}

function handleThumbnailVisibilityChange() {
  if (document.visibilityState === 'visible') {
    void recoverErroredThumbnails();
  }
}

function hasThumbnailError(documentId) {
  return Boolean(thumbnailErrorMap.value[documentId]);
}

function hasThumbnailLoaded(documentId) {
  return Boolean(thumbnailLoadedMap.value[documentId]);
}

function onThumbnailError(documentId, event) {
  const nextLoaded = { ...thumbnailLoadedMap.value };
  delete nextLoaded[documentId];
  thumbnailLoadedMap.value = nextLoaded;
  thumbnailErrorMap.value = { ...thumbnailErrorMap.value, [documentId]: true };
  if (importLandingRevealRequested && String(importLandingThumbDocId.value) === String(documentId)) {
    completeImportLandingThumbReveal(documentId);
  }
  if (thumbnailRetryTimerByDocumentId.has(documentId)) return;

  const attempt = thumbnailRetryAttemptByDocumentId.get(documentId) || 0;
  const delay = thumbnailRetryDelay(attempt, documentId);
  if (delay === null) return;

  thumbnailRetryAttemptByDocumentId.set(documentId, attempt + 1);
  thumbnailRetryTimerByDocumentId.set(
    documentId,
    window.setTimeout(() => { void runThumbnailRetry(documentId); }, delay),
  );
}

async function onThumbnailLoad(documentId, event) {
  const image = event?.currentTarget;
  const loadedSrc = String(image?.currentSrc || image?.src || '');
  try {
    await image?.decode?.();
  } catch {
    // Das load-Event bestätigt bereits ein nutzbares Bild; decode() kann z. B.
    // beim schnellen Unmounten einer virtualisierten Zeile abgewiesen werden.
  }
  if (image && loadedSrc && String(image.currentSrc || image.src || '') !== loadedSrc) return;
  thumbnailLoadedMap.value = { ...thumbnailLoadedMap.value, [documentId]: true };
  clearThumbnailRetryTimer(documentId);
  thumbnailRetryAttemptByDocumentId.delete(documentId);
  if (thumbnailErrorMap.value[documentId]) {
    const next = { ...thumbnailErrorMap.value };
    delete next[documentId];
    thumbnailErrorMap.value = next;
  }
  if (importLandingRevealRequested && String(importLandingThumbDocId.value) === String(documentId)) {
    completeImportLandingThumbReveal(documentId);
  }
}

watch(documentThumbnailSignature, () => {
  const nextSignatures = {};
  const nextErrors = {};
  const nextLoaded = {};
  const nextVersions = {};

  for (const document of documents.value) {
    if (!document?.id) continue;
    const signature = thumbnailStateKey(document);
    nextSignatures[document.id] = signature;
    nextVersions[document.id] = thumbnailVersionByDocumentId.value[document.id] || 0;
    if (
      thumbnailLoadedMap.value[document.id]
      && thumbnailSignatureByDocumentId.value[document.id] === signature
    ) {
      nextLoaded[document.id] = true;
    }

    if (
      thumbnailErrorMap.value[document.id]
      && thumbnailSignatureByDocumentId.value[document.id] === signature
    ) {
      nextErrors[document.id] = true;
    } else if (thumbnailSignatureByDocumentId.value[document.id] !== signature) {
      clearThumbnailRetryTimer(document.id);
      thumbnailRetryAttemptByDocumentId.delete(document.id);
      thumbnailUrlCache.delete(document.id);
    }
  }

  for (const documentId of Object.keys(thumbnailSignatureByDocumentId.value)) {
    if (nextSignatures[documentId]) continue;
    clearThumbnailRetryTimer(documentId);
    thumbnailRetryAttemptByDocumentId.delete(documentId);
    thumbnailUrlCache.delete(documentId);
  }

  thumbnailSignatureByDocumentId.value = nextSignatures;
  thumbnailErrorMap.value = nextErrors;
  thumbnailLoadedMap.value = nextLoaded;
  thumbnailVersionByDocumentId.value = nextVersions;
});

watch(
  () => authStore.fileTokenVersion,
  () => {
    retryErroredThumbnails();
  }
);

function handleDocumentRowShortcut(event, documentId) {
  handleShortcut(event, SHORTCUT_ACTIONS.ACTIVATE, () => emit('select-document', documentId), {
    ignoreEditable: false
  });
}

// Skelett-Zeilen erst nach kurzer Verzögerung einblenden, damit schnelle
// (z. B. leere) Ladevorgänge kein kurz aufblitzendes Skelett zeigen, bevor der
// Platzhalter erscheint. Der Loading-Zweig selbst bleibt sofort aktiv.
// Bewusst großzügig: Auf langsameren Backends (Pi) sollen leere Bereiche gar
// nicht erst das Skelett zeigen, bevor der Platzhalter kommt. Bekannte leere
// Bereiche werden ohnehin sofort über die Sidebar-Counts abgefangen
// (knownEmptyTarget); dieser Wert ist die Absicherung für nicht abgedeckte
// Ansichten (z. B. „Zuletzt hinzugefügt") und die Phase, bevor die Counts da
// sind. Das Skelett erscheint dadurch nur bei wirklich langen Ladezeiten.
const SKELETON_REVEAL_DELAY_MS = 800;
const skeletonRowsVisible = ref(false);
let skeletonRevealTimer = null;

watch(
  () => props.showDocumentListLoadingState,
  (loading) => {
    if (loading) {
      if (skeletonRevealTimer || skeletonRowsVisible.value) return;
      skeletonRevealTimer = window.setTimeout(() => {
        skeletonRevealTimer = null;
        skeletonRowsVisible.value = true;
      }, SKELETON_REVEAL_DELAY_MS);
    } else {
      if (skeletonRevealTimer) {
        window.clearTimeout(skeletonRevealTimer);
        skeletonRevealTimer = null;
      }
      skeletonRowsVisible.value = false;
    }
  }
);

// Favoriten-Toggle. Die Pop-Animation wird bewusst hier – beim Klick – ausgelöst
// (nicht per Klasse am is_favorite-Zustand), damit sie NUR bei der aktiven
// Aktion läuft und nicht, wenn eine bereits favorisierte Zeile ins
// virtualisierte Fenster scrollt. Nur beim Setzen, nicht beim Entfernen.
const animatingFavoriteId = ref(null);
let favoriteAnimTimer = null;

function onToggleFavorite(document) {
  if (!document?.is_favorite) {
    animatingFavoriteId.value = document.id;
    if (favoriteAnimTimer) window.clearTimeout(favoriteAnimTimer);
    favoriteAnimTimer = window.setTimeout(() => {
      animatingFavoriteId.value = null;
      favoriteAnimTimer = null;
    }, 480);
  }
  emit('toggle-favorite', document);
}

function onRowClick(event, documentId) {
  if (event.metaKey || event.ctrlKey) {
    // Cmd/Ctrl+Klick: Auswahlmodus aktivieren falls nötig, dann Dokument (de)selektieren
    if (!props.isSelectionMode) {
      emit('toggle-selection-mode');
    }
    emit('toggle-document-selection', documentId);
    return;
  }
  if (props.isSelectionMode) {
    emit('toggle-document-selection', documentId);
  } else {
    emit('select-document', documentId);
  }
}

// ── Formatting helpers ─────────────────────────────────────────────────────
function getDocumentTitle(document) {
  if (!document || typeof document !== 'object') return '';
  const displayName = String(document.display_name || '').trim();
  if (displayName) return displayName;
  return String(document.original_filename || '').trim();
}

function formatDocumentFilename(filename) {
  const value = String(filename || '').trim();
  if (!value) return '';
  if (showPdfSuffixComputed.value) return value;
  // Nur eine echte Dateiendung entfernen (Buchstabe + bis zu 7 alphanum.
  // Zeichen). Frühere Variante [^./\\]+ erfasste auch Leerzeichen und kappte
  // Titel wie "Antrag a. Rückerstattung_300768" zu "Antrag a".
  return value.replace(/\.[A-Za-z][A-Za-z0-9]{0,7}$/, '');
}

function formatDocumentTitle(document) {
  return formatDocumentFilename(getDocumentTitle(document));
}

function formatDate(value) {
  if (!value) return '-';
  const formatter = new Intl.DateTimeFormat('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
  const normalized = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    const [year, month, day] = normalized.split('-').map(Number);
    return formatter.format(new Date(year, month - 1, day));
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return '-';
  return formatter.format(parsed);
}

function displayListDate(document) {
  if (document.document_date) {
    return formatDate(document.document_date);
  }
  return '—';
}

function displayDocumentType(document) {
  return String(document?.document_type || document?.category || '').trim();
}

function displayCorrespondent(document) {
  const correspondent = document?.correspondent;
  return String(
    document?.correspondent_name ||
    document?.correspondent_short_name ||
    correspondent?.short_name ||
    correspondent?.name ||
    correspondent?.title ||
    ''
  ).trim();
}

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatSnippet(value) {
  const snippet = String(value || '').replace(/\s+/g, ' ').trim();
  const escaped = escapeHtml(snippet);
  return escaped
    .replace(/&lt;mark&gt;/g, '<mark>')
    .replace(/&lt;\/mark&gt;/g, '</mark>');
}

// ── Drag & Drop ────────────────────────────────────────────────────────────
function hasFileDragPayload(event) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
}

function onListDragEnter(event) {
  if (!hasFileDragPayload(event)) return;
  event.preventDefault();
  event.stopPropagation();
  listDropDragDepth.value += 1;
  isListDragOver.value = true;
}

function onListDragOver(event) {
  if (!hasFileDragPayload(event)) return;
  event.preventDefault();
  event.stopPropagation();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
  if (!isListDragOver.value) isListDragOver.value = true;
}

function onListDragLeave(event) {
  if (!hasFileDragPayload(event)) return;
  event.preventDefault();
  event.stopPropagation();
  listDropDragDepth.value = Math.max(0, listDropDragDepth.value - 1);
  if (listDropDragDepth.value === 0) isListDragOver.value = false;
}

function onListDrop(event) {
  if (!hasFileDragPayload(event)) return;
  event.preventDefault();
  event.stopPropagation();
  isListDragOver.value = false;
  listDropDragDepth.value = 0;
  const files = Array.from(event.dataTransfer?.files || []);
  if (files.length > 0) emit('files-dropped', files);
}
</script>

<style scoped>
/* ── Thumbnail im Auswahlmodus ────────────────────────────────────────── */
.document-row__thumb {
  position: relative;
}

.document-row__thumb::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: linear-gradient(
    100deg,
    var(--pm-thumb-bg, rgba(15, 23, 42, 0.08)) 22%,
    color-mix(in srgb, var(--pm-thumb-line, rgba(255, 255, 255, 0.52)) 72%, transparent) 42%,
    var(--pm-thumb-bg, rgba(15, 23, 42, 0.08)) 62%
  );
  background-size: 220% 100%;
  animation: document-thumbnail-shimmer 1.35s ease-in-out infinite;
}

.document-row__thumb--error::before {
  display: none;
}

.document-row__thumb--loaded::before {
  animation: none;
  opacity: 0;
}

.document-row__thumb img,
.document-row__thumb-fallback {
  position: relative;
  z-index: 1;
}

/* Wartet auf die landende Karte: leeres weißes Dokumentblatt statt Vorschau.
   Die Karte „liefert" das echte Bild erst bei der Landung (Klasse wird entfernt,
   Bild erscheint sofort → nahtloser Übergang). */
.document-row__thumb--awaiting-import {
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
}
.document-row__thumb--awaiting-import::before {
  display: none;
}
.document-row__thumb--awaiting-import img,
.document-row__thumb--awaiting-import .document-row__thumb-fallback {
  opacity: 0;
}

@keyframes document-thumbnail-shimmer {
  from { background-position: 100% 0; }
  to { background-position: -120% 0; }
}

/* ── Import-Fluganimation: Landezeile am Listenkopf ─────────────────────── */
.document-row--import-landing {
  --document-row-height: 112px;
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  z-index: 3;
  height: var(--document-row-height);
  min-height: var(--document-row-height);
  pointer-events: none;
  cursor: default;
  border-color: color-mix(in srgb, var(--pm-accent, #14b8a6) 42%, transparent);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--pm-accent, #14b8a6) 30%, transparent),
    0 14px 30px rgba(15, 23, 42, 0.16);
  background: var(--pm-app-surface-raised);
  /* Während des Flugs unsichtbar (nur Messung); erst bei der Landung einblenden. */
  opacity: 0;
  transform: translateY(6px) scale(0.985);
  transition:
    opacity 220ms var(--pm-easing-decel, cubic-bezier(0, 0, 0.2, 1)),
    transform 220ms var(--pm-easing-decel, cubic-bezier(0, 0, 0.2, 1));
}

.document-row--import-landing--revealed {
  opacity: 1;
  transform: none;
}

.document-row--import-landing--snippets {
  --document-row-height: 152px;
}

.document-row--import-landing__thumb {
  overflow: hidden;
  background: var(--pm-thumb-bg, rgba(15, 23, 42, 0.08));
  border-radius: 8px;
}

.document-row--import-landing__pulse {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    var(--pm-thumb-bg, rgba(15, 23, 42, 0.08)) 22%,
    color-mix(in srgb, var(--pm-accent, #14b8a6) 22%, transparent) 46%,
    var(--pm-thumb-bg, rgba(15, 23, 42, 0.08)) 68%
  );
  background-size: 220% 100%;
  animation: document-thumbnail-shimmer 1.1s ease-in-out infinite;
}

.document-row--import-landing__line {
  border-radius: 6px;
  background: linear-gradient(
    100deg,
    rgba(148, 163, 184, 0.22) 22%,
    rgba(148, 163, 184, 0.42) 46%,
    rgba(148, 163, 184, 0.22) 68%
  );
  background-size: 220% 100%;
  animation: document-thumbnail-shimmer 1.1s ease-in-out infinite;
}

.document-row--import-landing__line--kicker {
  width: 34%;
  height: 10px;
  margin-top: 4px;
}

.document-row--import-landing__line--title {
  width: 72%;
  height: 15px;
  margin-top: 12px;
}

.document-row--import-landing__line--meta {
  width: 52%;
  height: 10px;
  margin-top: 14px;
}

/* Übergabe an die echte Zeile: Landeskelett verblasst leicht angehoben. */
.document-row--import-landing-resolving {
  opacity: 0;
  transform: translateY(-4px) scale(0.99);
  transition:
    opacity 240ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 1, 1)),
    transform 240ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 1, 1));
}

/* Frisch angekommene echte Zeile kräftig aufleuchten lassen. */
.document-row--just-arrived {
  animation: document-row-arrive 1600ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

/* Das gelandete Thumbnail ist bereits der ruhige Endzustand. Es liegt deshalb
   über dem Zeilen-Schimmer und darf während der Ankunft keinen eigenen
   Lade-Shimmer mehr starten. So gibt es nach der Übergabe kein zweites Blinken. */
.document-row--just-arrived .document-row__thumb {
  z-index: 5;
}

.document-row--just-arrived .document-row__thumb::before {
  animation: none;
  opacity: 0;
}

/* Über die Zeile wandernder Lichtstreifen – durch overflow:hidden der Zeile
   beschnitten, contain:layout macht die Zeile zum Bezugsrahmen für absolute. */
.document-row--just-arrived::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 4;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(
    100deg,
    transparent 34%,
    color-mix(in srgb, var(--pm-accent, #14b8a6) 40%, transparent) 44%,
    color-mix(in srgb, var(--pm-accent, #14b8a6) 92%, white) 50%,
    color-mix(in srgb, var(--pm-accent, #14b8a6) 40%, transparent) 56%,
    transparent 66%
  );
  background-size: 220% 100%;
  /* Grundzustand unsichtbar: nach Ablauf der Animation (kein fill-mode) fällt
     das ::after hierauf zurück – sonst bliebe die helle Bande als Fleck stehen,
     bis die Klasse entfernt wird (störendes Aufblitzen rechts). */
  opacity: 0;
  animation: document-row-arrive-sweep 1100ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)) forwards;
}

@keyframes document-row-arrive {
  0% {
    box-shadow:
      0 0 0 2.5px color-mix(in srgb, var(--pm-accent, #14b8a6) 78%, transparent),
      0 0 22px 2px color-mix(in srgb, var(--pm-accent, #14b8a6) 45%, transparent),
      0 16px 34px rgba(15, 23, 42, 0.22);
    background: color-mix(in srgb, var(--pm-accent, #14b8a6) 20%, var(--pm-app-surface-raised));
  }
  35% {
    box-shadow:
      0 0 0 1.5px color-mix(in srgb, var(--pm-accent, #14b8a6) 42%, transparent),
      0 0 12px 1px color-mix(in srgb, var(--pm-accent, #14b8a6) 22%, transparent),
      0 10px 22px rgba(15, 23, 42, 0.14);
    background: color-mix(in srgb, var(--pm-accent, #14b8a6) 9%, var(--pm-app-surface-raised));
  }
  /* zweiter, kleinerer Puls = „Schimmern“ statt einmaligem Aufblitzen */
  58% {
    box-shadow:
      0 0 0 2px color-mix(in srgb, var(--pm-accent, #14b8a6) 60%, transparent),
      0 0 16px 1.5px color-mix(in srgb, var(--pm-accent, #14b8a6) 34%, transparent),
      0 12px 26px rgba(15, 23, 42, 0.16);
    background: color-mix(in srgb, var(--pm-accent, #14b8a6) 14%, var(--pm-app-surface-raised));
  }
  100% {
    box-shadow: none;
    background: var(--pm-app-surface-raised);
  }
}

@keyframes document-row-arrive-sweep {
  0% {
    background-position: 130% 0;
    opacity: 0;
  }
  12% {
    opacity: 1;
  }
  88% {
    opacity: 1;
  }
  100% {
    background-position: -60% 0;
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .document-row--import-landing__pulse,
  .document-row--import-landing__line {
    animation: none;
  }
  .document-row--just-arrived {
    animation-duration: 600ms;
  }
  .document-row--just-arrived::after {
    animation: none;
    display: none;
  }
}

:global(.pm-no-animations) .document-row__thumb::before {
  animation: none;
}

@media (prefers-reduced-motion: reduce) {
  .document-row__thumb::before {
    animation: none;
  }
}

.document-row__thumb--selectable img,
.document-row__thumb--selectable .document-row__thumb-fallback {
  opacity: 0.55;
  transition: opacity var(--pm-duration-normal) var(--pm-easing);
}

/* ── Checkbox-Overlay ─────────────────────────────────────────────────── */
.document-row__checkbox-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1.5px solid rgba(var(--v-theme-on-surface), 0.35);
  background: rgba(var(--v-theme-surface), 0.55);
  transition: background var(--pm-duration-fast), border-color var(--pm-duration-fast);
}

.document-row__checkbox-overlay--checked {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: #fff;
}

/* Vue Transition */
.checkbox-pop-enter-active,
.checkbox-pop-leave-active {
  transition: opacity var(--pm-duration-fast) var(--pm-easing), transform var(--pm-duration-fast) var(--pm-easing);
}

.checkbox-pop-enter-from,
.checkbox-pop-leave-to {
  opacity: 0;
  transform: scale(0.6);
}

/* ── Skeleton ─────────────────────────────────────────────────────────── */
.document-list--skeleton {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.document-list__skeleton-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.document-row-skeleton {
  border-radius: 12px;
  overflow: hidden;
}

/* Sanftes Einblenden der (verzögerten) Skelett-Zeilen bei längeren Ladezeiten. */
.pm-skeleton-fade-enter-active {
  transition: opacity var(--pm-duration-normal, 220ms) var(--pm-easing, ease);
}
.pm-skeleton-fade-enter-from {
  opacity: 0;
}
:global(.pm-no-animations) .pm-skeleton-fade-enter-active {
  transition-duration: 0ms;
}
@media (prefers-reduced-motion: reduce) {
  .pm-skeleton-fade-enter-active {
    transition-duration: 0ms;
  }
}

/* Nur tatsächlich gelöschte Zeilen werden animiert. Sie verblassen und klappen
   gleichzeitig zusammen; danach kann Vue sie ohne sichtbaren Sprung aus der
   virtualisierten Liste entfernen. */
.document-list__rows {
  position: relative;
}

.document-row--removing {
  pointer-events: none;
  height: 0;
  min-height: 0;
  margin-top: 0 !important;
  padding-top: 0;
  padding-bottom: 0;
  border-top-width: 0;
  border-bottom-width: 0;
  opacity: 0;
  transform: translateY(-4px) scale(0.99);
  will-change: height, opacity, transform;
  transition:
    height 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    min-height 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    margin-top 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    padding-top 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    padding-bottom 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    border-top-width 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    border-bottom-width 210ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) var(--pm-removal-delay, 0ms),
    opacity 160ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 1, 1)) var(--pm-removal-delay, 0ms),
    transform 180ms var(--pm-easing-accel, cubic-bezier(0.4, 0, 1, 1)) var(--pm-removal-delay, 0ms);
}

.trash-notes {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--pm-divider, rgba(127, 127, 127, 0.2));
}

/* Dokument-Gruppenkopf im Papierkorb (erste Gruppe, daher ohne Trennlinie).
   Horizontal-Einzug (16px) exakt auf den Notizen-Kopf ausgerichtet: dieser sitzt
   im virtualisierten .document-list (Container-Einzug 12px) + eigenem 4px-Margin;
   der Dokument-Kopf ist direktes Kind von .document-list-content, deshalb hier
   die Summe (16px) direkt als Margin. */
.trash-notes__heading.trash-docs-heading {
  margin: 12px 16px 9px;
}

.trash-notes--only {
  margin-top: 0;
  padding-top: 0;
  border-top: 0;
}

.trash-notes__heading {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 4px 9px;
  color: var(--pm-muted, #748084);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.trash-notes__heading > span:last-child {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.pm-trash-note {
  cursor: pointer;
}

.pm-trash-note.is-active {
  background: var(--pm-row-active, rgba(0, 107, 117, 0.08));
  box-shadow: inset 2px 0 0 var(--pm-accent, #006b75);
}

.pm-trash-note:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--pm-accent, #006b75) 55%, transparent);
  outline-offset: -2px;
}

.pm-trash-note__thumb {
  display: grid;
  place-items: center;
  border: 1px solid var(--pm-divider, rgba(127, 127, 127, 0.2));
  border-radius: 9px;
  background: var(--pm-viewer-surface, rgba(127, 127, 127, 0.08));
  color: var(--pm-muted, #748084);
}

.pm-trash-note__thumb::before {
  display: none;
}

.pm-trash-note__title--empty {
  color: var(--pm-muted, #748084);
  font-style: italic;
}

.pm-trash-note__snippet {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

:global(.pm-no-animations) .document-row--removing {
  transition-duration: 0ms;
}

@media (prefers-reduced-motion: reduce) {
  .document-row--removing {
    transition-duration: 0ms;
  }
}

/* ── Selektierter Zustand ─────────────────────────────────────────────── */
.document-row--selected {
  background: rgba(var(--v-theme-primary), 0.07);
}

.document-row--selected:hover {
  background: rgba(var(--v-theme-primary), 0.07);
}

.document-row__tag-chip {
  min-width: 0;
  max-width: min(150px, 42%);
}

.document-row__tag-chip :deep(.v-chip__content) {
  display: block;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-list__bottom-spacer {
  flex: 0 0 auto;
  pointer-events: none;
}

/* Platzhalter für virtualisierte (nicht gerenderte) Zeilen ober-/unterhalb des
   sichtbaren Fensters – hält die Scrollhöhe konstant. */
.document-list__virtual-pad {
  flex: 0 0 auto;
  width: 100%;
  pointer-events: none;
}

.document-list__load-more {
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 8px 12px 12px;
}

.document-list__loading-more {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 0.75rem;
}

.document-list__load-more-button {
  opacity: 0.72;
}

.document-list--with-bottom-spacer {
  flex: 0 0 auto;
}
</style>
