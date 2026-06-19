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
            class="document-list document-list-state"
            :class="{ 'document-list--with-bottom-spacer': bottomSpacerHeight > 0 }"
          >
            <div
              v-for="document in documents"
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
                <div class="document-row__title">
                  <span v-if="document.is_unread" class="document-row__unread-dot" aria-hidden="true" />
                  <div class="document-row__name">{{ formatDocumentTitle(document) }}</div>
                </div>
                <div class="document-row__meta-line">
                  <div class="document-row__meta">{{ displayDocumentType(document) }}</div>
                </div>
                <div class="document-row__meta-line">
                  <div class="document-row__meta">{{ displayListDate(document) }}</div>
                </div>
                <TransitionGroup
                  v-if="Array.isArray(document.tags) && document.tags.length > 0"
                  tag="div"
                  name="pm-chip"
                  class="document-row__tags"
                >
                  <v-chip
                    v-for="tag in document.tags.slice(0, 3)"
                    :key="`doc-${document.id}-tag-${tag.id}`"
                    size="x-small"
                    variant="tonal"
                    class="document-row__tag-chip"
                  >
                    {{ tag.name }}
                  </v-chip>
                  <v-chip
                    v-if="document.tags.length > 3"
                    key="more"
                    size="x-small"
                    variant="outlined"
                    class="document-row__tag-chip document-row__tag-chip--more"
                  >
                    +{{ document.tags.length - 3 }}
                  </v-chip>
                </TransitionGroup>
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
                      <v-list-item @click.stop="emit('download', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-download-outline</v-icon>
                        </template>
                        <v-list-item-title>Herunterladen</v-list-item-title>
                      </v-list-item>
                      <v-list-item @click.stop="emit('rename', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-pencil-outline</v-icon>
                        </template>
                        <v-list-item-title>Umbenennen</v-list-item-title>
                      </v-list-item>
                      <v-list-item @click.stop="emit('manage-tags', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-tag-multiple-outline</v-icon>
                        </template>
                        <v-list-item-title>Tags verwalten</v-list-item-title>
                      </v-list-item>
                      <v-list-item class="menu-item--danger" @click.stop="emit('delete', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-trash-can-outline</v-icon>
                        </template>
                        <v-list-item-title>In Papierkorb</v-list-item-title>
                      </v-list-item>
                    </v-list>

                    <!-- Papierkorb-Menü -->
                    <v-list v-else density="compact">
                      <v-list-item @click.stop="emit('restore', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-restore</v-icon>
                        </template>
                        <v-list-item-title>Wiederherstellen</v-list-item-title>
                      </v-list-item>
                      <v-list-item class="menu-item--danger" @click.stop="emit('delete-permanent', document)">
                        <template #prepend>
                          <v-icon size="16">mdi-delete-forever-outline</v-icon>
                        </template>
                        <v-list-item-title>Endgültig löschen…</v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-menu>
                </div>
              </div>
            </div>
            <div
              v-if="bottomSpacerHeight > 0"
              class="document-list__bottom-spacer"
              :style="{ height: `${bottomSpacerHeight}px` }"
              aria-hidden="true"
            />
            <div
              v-if="totalDocumentCount > 0"
              class="document-list__pagination"
              :class="{ 'document-list__pagination--complete': !hasMoreDocuments }"
              aria-live="polite"
            >
              <div class="document-list__pagination-status">
                <div class="document-list__pagination-label">
                  <v-progress-circular
                    v-if="isLoadingMoreDocuments"
                    indeterminate
                    size="16"
                    width="2"
                    aria-hidden="true"
                  />
                  <v-icon
                    v-else-if="!hasMoreDocuments"
                    size="16"
                    color="success"
                    aria-hidden="true"
                  >
                    mdi-check-circle-outline
                  </v-icon>
                  <span>{{ paginationStatusLabel }}</span>
                </div>
                <span v-if="hasMoreDocuments" class="document-list__pagination-count">
                  {{ paginationLabel }}
                </span>
              </div>
              <v-progress-linear
                :model-value="paginationProgress"
                :indeterminate="isLoadingMoreDocuments"
                height="3"
                rounded
                color="primary"
                class="document-list__pagination-progress"
              />
              <v-btn
                v-if="hasMoreDocuments"
                block
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-chevron-down"
                :loading="isLoadingMoreDocuments"
                :disabled="isLoadingMoreDocuments"
                class="document-list__pagination-button"
                @click="emit('load-more')"
              >
                {{ loadMoreLabel }}
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
import { ref, computed, nextTick, watch } from 'vue';

const SORT_OPTIONS = [
  { value: 'newest',      label: 'Neueste zuerst' },
  { value: 'oldest',      label: 'Älteste zuerst' },
  { value: 'name_asc',    label: 'Name A–Z' },
  { value: 'favorites',   label: 'Favoriten zuerst' },
];

const DATE_RANGE_OPTIONS = [
  { value: '',               label: 'Alle Zeiträume' },
  { value: 'this_year',      label: 'Dieses Jahr' },
  { value: 'last_year',      label: 'Letztes Jahr' },
  { value: 'last_30_days',   label: 'Letzte 30 Tage' },
  { value: 'last_12_months', label: 'Letzte 12 Monate' },
];
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
  totalDocumentCount:         { type: Number,  default: 0 },
  loadMoreBatchSize:           { type: Number,  default: 100 },
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
const showPdfSuffixComputed = computed(() => settingsStore.settingsDraft?.ui?.showFilenameSuffix ?? false);
const paginationLabel = computed(() => {
  const loaded = Math.min(props.loadedDocumentCount, props.totalDocumentCount);
  return `${loaded} von ${props.totalDocumentCount} Dokumenten`;
});
const remainingDocumentCount = computed(() =>
  Math.max(0, props.totalDocumentCount - props.loadedDocumentCount)
);
const nextLoadCount = computed(() =>
  Math.min(props.loadMoreBatchSize, remainingDocumentCount.value)
);
const paginationProgress = computed(() => {
  if (props.totalDocumentCount <= 0) return 0;
  return Math.min(100, (props.loadedDocumentCount / props.totalDocumentCount) * 100);
});
const paginationStatusLabel = computed(() => {
  if (props.isLoadingMoreDocuments) return 'Weitere Dokumente werden geladen …';
  if (!props.hasMoreDocuments) return `Alle ${props.totalDocumentCount} Dokumente geladen`;
  return 'Weitere Dokumente verfügbar';
});
const loadMoreLabel = computed(() =>
  `${nextLoadCount.value} weitere laden`
);

function requestMoreIfNearEnd(element = listShell.value) {
  if (!element || !props.hasMoreDocuments || props.isLoadingMoreDocuments) return;
  const remaining = element.scrollHeight - element.scrollTop - element.clientHeight;
  if (remaining <= 480) {
    emit('load-more');
  }
}

function handleListScroll(event) {
  requestMoreIfNearEnd(event.currentTarget);
}

watch(
  () => [props.hasMoreDocuments, props.isLoadingMoreDocuments, props.loadedDocumentCount],
  () => {
    void nextTick(() => requestMoreIfNearEnd());
  },
  { flush: 'post' }
);

const sortLabel      = computed(() => SORT_OPTIONS.find(o => o.value === props.currentSort)?.label ?? 'Sortierung');
const dateRangeLabel = computed(() => DATE_RANGE_OPTIONS.find(o => o.value === props.currentDateRange)?.label ?? 'Zeitraum');
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

const documentThumbnailSignature = computed(() => (
  documents.value
    .map((document) => thumbnailStateKey(document))
    .join('|')
));

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

function thumbnailUrl(document) {
  const documentId = document?.id;
  const versionParts = [
    authStore.fileTokenVersion || 0,
    document?.updated_at || '',
    thumbnailVersionByDocumentId.value[documentId] || 0,
  ];
  const url = authedUrl(`${getBaseUrl()}/api/documents/${documentId}/thumbnail`);
  return appendUrlParam(url, 'thumb_v', versionParts.join(':'));
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

function retryVisibleThumbnails() {
  const nextErrors = {};
  const nextVersions = { ...thumbnailVersionByDocumentId.value };
  for (const document of documents.value) {
    if (!document?.id) continue;
    nextVersions[document.id] = (Number(nextVersions[document.id] || 0) + 1);
  }
  thumbnailErrorMap.value = nextErrors;
  thumbnailVersionByDocumentId.value = nextVersions;
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
    retryVisibleThumbnails();
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
  return value.replace(/\.[^./\\]+$/, '');
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
    return `Dokumentdatum: ${formatDate(document.document_date)}`;
  }
  return 'Dokumentdatum: —';
}

function displayDocumentType(document) {
  const documentType = String(document?.document_type || document?.category || '').trim();
  return `Dokumenttyp: ${documentType || '—'}`;
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

.document-row__meta-line {
  display: flex;
  width: 100%;
}

.document-list__bottom-spacer {
  flex: 0 0 auto;
  pointer-events: none;
}

.document-list__pagination {
  position: sticky;
  bottom: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 4px;
  padding: 12px 14px 14px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  background: rgba(var(--v-theme-surface), 0.97);
  box-shadow: 0 -5px 14px rgba(var(--v-theme-on-surface), 0.06);
  backdrop-filter: blur(8px);
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.78rem;
}

.document-list__pagination--complete {
  padding-block: 11px;
  box-shadow: none;
}

.document-list__pagination-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  gap: 12px;
}

.document-list__pagination-label {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
  color: rgba(var(--v-theme-on-surface), 0.76);
  font-weight: 500;
}

.document-list__pagination-label span,
.document-list__pagination-count {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-list__pagination-count {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
}

.document-list__pagination-progress {
  flex: 0 0 auto;
}

.document-list__pagination-button {
  min-height: 34px;
}

.document-list--with-bottom-spacer {
  flex: 0 0 auto;
}
</style>
