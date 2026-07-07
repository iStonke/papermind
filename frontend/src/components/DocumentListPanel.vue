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
      <div class="document-list-content">
        <Transition name="pm-list-state">
          <div
            v-if="showDocumentListLoadingState"
            key="loading"
            class="document-list document-list-state document-list--skeleton"
          >
            <v-skeleton-loader
              v-for="n in 6"
              :key="`skel-${n}`"
              type="list-item-avatar-two-line"
              class="document-row-skeleton"
            />
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
            <div
              v-for="document in renderedDocuments"
              :key="document.id"
              class="document-row pm-doc-item"
              :class="{
                'document-row--active': !isSelectionMode && document.id === selectedDocumentId,
                'document-row--selected': isSelectionMode && selectionIds.has(document.id),
                'document-row--selection-mode': isSelectionMode
              }"
              role="button"
              tabindex="0"
              @click="onRowClick($event, document.id)"
              @keydown="handleDocumentRowShortcut($event, document.id)"
            >
              <div class="document-row__thumb" :class="{ 'document-row__thumb--selectable': isSelectionMode }">
                <img
                  v-if="!hasThumbnailError(document.id)"
                  :src="thumbnailUrl(document)"
                  alt="thumbnail"
                  loading="lazy"
                  @load="onThumbnailLoad(document.id)"
                  @error="onThumbnailError(document.id)"
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
                  <span v-if="document.is_unread" class="document-row__unread-dot" aria-hidden="true" />
                  <span class="document-row__kicker-type">{{ displayDocumentType(document) }}</span>
                  <template v-if="displayCorrespondent(document)">
                    <span class="document-row__kicker-dot" aria-hidden="true">·</span>
                    <span class="document-row__kicker-corr">{{ displayCorrespondent(document) }}</span>
                  </template>
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
                  <v-btn
                    v-if="!isTrashView"
                    :icon="document.is_favorite ? 'mdi-star' : 'mdi-star-outline'"
                    variant="text"
                    size="small"
                    density="comfortable"
                    :ripple="false"
                    :class="['document-row__fav-btn', { 'document-row__fav-btn--active': document.is_favorite }]"
                    :aria-label="document.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'"
                    @click.stop="emit('toggle-favorite', document)"
                  />

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
            <div
              v-if="virtualBottomPad > 0"
              class="document-list__virtual-pad"
              :style="{ height: `${virtualBottomPad}px` }"
              aria-hidden="true"
            />
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
  bottomSpacerHeight:         { type: Number,  default: 0 },
  hasMoreDocuments:           { type: Boolean, default: false },
  isLoadingMoreDocuments:     { type: Boolean, default: false },
  loadedDocumentCount:        { type: Number,  default: 0 },
});

const emit = defineEmits([
  'select-document',
  'download',
  'rename',
  'manage-tags',
  'delete',
  'restore',
  'delete-permanent',
  'toggle-favorite',
  'files-dropped',
  'toggle-selection-mode',
  'toggle-document-selection',
  'select-all',
  'change-sort',
  'change-date-range',
  'toggle-tag-filter-drawer',
  'load-more',
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const docStore      = useDocumentStore();
const settingsStore = useSettingsStore();
const authStore     = useAuthStore();

const { documents, selectedDocumentId } = storeToRefs(docStore);
const listShell = ref(null);
const documentListRef = ref(null);
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
const ROW_OVERSCAN = 12;

const listScrollTop = ref(0);
const listViewport = ref(0);
const listContentOffsetTop = ref(0);
let virtualWindowFrame = 0;
let pendingVirtualWindowElement = null;
let listResizeObserver = null;

const isVirtualized = computed(() => documents.value.length > 0);
const virtualRowHeight = computed(() =>
  props.showSnippets ? VIRTUAL_ROW_HEIGHT_WITH_SNIPPET : VIRTUAL_ROW_HEIGHT
);
const virtualRowStep = computed(() => virtualRowHeight.value + VIRTUAL_ROW_GAP);
const rowRelativeScrollTop = computed(() =>
  Math.max(0, listScrollTop.value - listContentOffsetTop.value)
);

const virtualStartIndex = computed(() => {
  if (!isVirtualized.value) return 0;
  return Math.max(0, Math.floor(rowRelativeScrollTop.value / virtualRowStep.value) - ROW_OVERSCAN);
});

const virtualEndIndex = computed(() => {
  if (!isVirtualized.value) return documents.value.length;
  const visibleEnd = Math.ceil((rowRelativeScrollTop.value + (listViewport.value || 0)) / virtualRowStep.value);
  return Math.min(
    documents.value.length,
    Math.max(virtualStartIndex.value + 1, visibleEnd + ROW_OVERSCAN)
  );
});

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

function updateVirtualWindow(element = listShell.value) {
  if (!element) return;
  listScrollTop.value = element.scrollTop;
  listViewport.value = element.clientHeight;
  listContentOffsetTop.value = documentListRef.value?.offsetTop || 0;
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
  if (remaining <= 480) {
    emit('load-more');
  }
}

function handleListScroll(event) {
  const element = event.currentTarget;
  scheduleVirtualWindowUpdate(element);
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
  updateVirtualWindow();
  if (typeof ResizeObserver !== 'undefined' && listShell.value) {
    listResizeObserver = new ResizeObserver(() => updateVirtualWindow());
    listResizeObserver.observe(listShell.value);
  }
});

onBeforeUnmount(() => {
  if (virtualWindowFrame) cancelAnimationFrame(virtualWindowFrame);
  if (listResizeObserver) {
    listResizeObserver.disconnect();
    listResizeObserver = null;
  }
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
  if (!props.showTagFilterToggle) {
    return [];
  }
  return [
    {
      key: 'tagFilter',
      icon: 'mdi-tag-multiple-outline',
      label: 'Tags',
      ariaLabel: props.tagFilterDrawerOpen ? 'Tag-Filter ausblenden' : 'Tag-Filter einblenden',
      active: props.tagFilterDrawerOpen
    }
  ];
});

// ── Refs ───────────────────────────────────────────────────────────────────
const thumbnailErrorMap = ref({});
const isListDragOver    = ref(false);
const listDropDragDepth = ref(0);
const thumbnailVersionByDocumentId = ref({});
const thumbnailSignatureByDocumentId = ref({});

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
  for (const documentId of erroredIds) {
    nextVersions[documentId] = Number(nextVersions[documentId] || 0) + 1;
  }
  thumbnailErrorMap.value = {};
  thumbnailVersionByDocumentId.value = nextVersions;
}

function hasThumbnailError(documentId) {
  return Boolean(thumbnailErrorMap.value[documentId]);
}

function onThumbnailError(documentId) {
  thumbnailErrorMap.value = { ...thumbnailErrorMap.value, [documentId]: true };
}

function onThumbnailLoad(documentId) {
  if (!thumbnailErrorMap.value[documentId]) return;
  const next = { ...thumbnailErrorMap.value };
  delete next[documentId];
  thumbnailErrorMap.value = next;
}

watch(documentThumbnailSignature, () => {
  const nextSignatures = {};
  const nextErrors = {};
  const nextVersions = {};

  for (const document of documents.value) {
    if (!document?.id) continue;
    const signature = thumbnailStateKey(document);
    nextSignatures[document.id] = signature;
    nextVersions[document.id] = thumbnailVersionByDocumentId.value[document.id] || 0;

    if (
      thumbnailErrorMap.value[document.id]
      && thumbnailSignatureByDocumentId.value[document.id] === signature
    ) {
      nextErrors[document.id] = true;
    }
  }

  thumbnailSignatureByDocumentId.value = nextSignatures;
  thumbnailErrorMap.value = nextErrors;
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
  const documentType = String(document?.document_type || document?.category || '').trim();
  return documentType || '—';
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

.document-row__thumb--selectable img,
.document-row__thumb--selectable .document-row__thumb-fallback {
  opacity: 0.55;
  transition: opacity 0.18s ease;
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
  transition: background 0.12s, border-color 0.12s;
}

.document-row__checkbox-overlay--checked {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: #fff;
}

/* Vue Transition */
.checkbox-pop-enter-active,
.checkbox-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
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

.document-row-skeleton {
  border-radius: 12px;
  overflow: hidden;
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
