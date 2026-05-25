<template>
  <div class="document-list-shell docs-column">
    <div v-if="activeStatusFilterLabel && !isImportsView" class="active-filter-row">
      <v-chip size="small" variant="outlined">
        Status: {{ activeStatusFilterLabel }}
      </v-chip>
    </div>

    <!-- Toolbar -->
    <div v-if="!isTrashView && !isImportsView" class="doclist-toolbar">
      <!-- Linke Seite: im Auswahlmodus → Alle auswählen + Zähler; sonst → Sort + Status -->
      <div class="doclist-toolbar__left">
        <template v-if="isSelectionMode">
          <button type="button" class="doclist-toolbar__action-btn" @click="emit('select-all')">
            Alle auswählen
          </button>
          <span v-if="selectionIds.size > 0" class="doclist-toolbar__count">
            {{ selectionIds.size }} ausgewählt
          </span>
        </template>
        <template v-else>
          <!-- Sortierung -->
          <v-menu location="bottom start" offset="4">
            <template #activator="{ props: menuProps }">
              <button type="button" class="doclist-toolbar__action-btn doclist-toolbar__action-btn--icon" v-bind="menuProps">
                <v-icon size="14">mdi-sort</v-icon>
                {{ sortLabel }}
              </button>
            </template>
            <v-list density="compact" min-width="190">
              <v-list-item
                v-for="opt in SORT_OPTIONS"
                :key="opt.value"
                :class="{ 'v-list-item--active': currentSort === opt.value }"
                @click="emit('change-sort', opt.value)"
              >
                <v-list-item-title>{{ opt.label }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>

          <!-- Statusfilter -->
          <v-menu location="bottom start" offset="4">
            <template #activator="{ props: menuProps }">
              <button
                type="button"
                class="doclist-toolbar__action-btn doclist-toolbar__action-btn--icon"
                :class="{ 'doclist-toolbar__action-btn--active': currentStatus }"
                v-bind="menuProps"
              >
                <v-icon size="14">mdi-filter-variant</v-icon>
                {{ statusLabel }}
              </button>
            </template>
            <v-list density="compact" min-width="170">
              <v-list-item
                v-for="opt in STATUS_OPTIONS"
                :key="opt.value"
                :class="{ 'v-list-item--active': currentStatus === opt.value }"
                @click="emit('change-status', opt.value)"
              >
                <v-list-item-title>{{ opt.label }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
        </template>
      </div>

      <!-- Rechte Seite: Auswählen / Abbrechen -->
      <button
        type="button"
        class="doclist-toolbar__select-btn"
        :class="{ 'doclist-toolbar__select-btn--cancel': isSelectionMode }"
        @click="emit('toggle-selection-mode')"
      >
        {{ isSelectionMode ? 'Abbrechen' : 'Auswählen' }}
      </button>
    </div>

    <div
      class="document-list-body docs-list-dropzone"
      :class="{ 'document-list-body--dragover': isListDragOver }"
      @dragenter="onListDragEnter"
      @dragover="onListDragOver"
      @dragleave="onListDragLeave"
      @drop="onListDrop"
    >
      <div class="document-list-content">
        <div v-if="isLoadingDocuments && documents.length === 0" class="document-list document-list--skeleton">
          <v-skeleton-loader
            v-for="n in 6"
            :key="`skel-${n}`"
            type="list-item-avatar-two-line"
            class="document-row-skeleton"
          />
        </div>

        <div v-else-if="showDocumentListEmptyState" class="document-list-empty-state-wrap">
          <PmEmptyState
            :icon="documentListEmptyState.icon"
            :title="documentListEmptyState.title"
            :subtitle="documentListEmptyState.subtitle"
            size="md"
          />
        </div>

        <TransitionGroup v-else tag="div" name="pm-list-item" class="document-list">
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
                :src="thumbnailUrl(document.id)"
                alt="thumbnail"
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
                  variant="text"
                  size="small"
                  density="comfortable"
                  :class="['document-row__fav-btn', { 'document-row__fav-btn--active': document.is_favorite }]"
                  :aria-label="document.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'"
                  @click.stop="emit('toggle-favorite', document)"
                >
                  <v-icon size="20">{{ document.is_favorite ? 'mdi-star' : 'mdi-star-outline' }}</v-icon>
                </v-btn>

                <!-- Drei-Punkte-Menü -->
                <v-menu location="bottom end">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon="mdi-dots-vertical"
                      size="small"
                      density="comfortable"
                      variant="text"
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
        </TransitionGroup>
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
import { ref, computed } from 'vue';

const SORT_OPTIONS = [
  { value: 'newest',      label: 'Neueste zuerst' },
  { value: 'oldest',      label: 'Älteste zuerst' },
  { value: 'name_asc',    label: 'Name A–Z' },
  { value: 'name_desc',   label: 'Name Z–A' },
  { value: 'last_opened', label: 'Zuletzt geöffnet' },
];

const STATUS_OPTIONS = [
  { value: '',           label: 'Alle Status' },
  { value: 'ready',      label: 'Bereit' },
  { value: 'processing', label: 'Verarbeitung' },
  { value: 'imported',   label: 'Importiert' },
  { value: 'failed',     label: 'Fehler' },
];
import { storeToRefs } from 'pinia';
import { useDocumentStore } from '../stores/documents.js';
import { useSettingsStore } from '../stores/settings.js';
import { getBaseUrl } from '../api/client.js';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts.js';
import PmEmptyState from './PmEmptyState.vue';

// ── Props & Emits ──────────────────────────────────────────────────────────
const props = defineProps({
  listDropNotice:             { type: String,  default: '' },
  activeStatusFilterLabel:    { type: String,  default: '' },
  isImportsView:              { type: Boolean, default: false },
  isTrashView:                { type: Boolean, default: false },
  showDocumentListEmptyState: { type: Boolean, default: false },
  documentListEmptyState:     { type: Object,  default: () => ({ icon: '', title: '', subtitle: '' }) },
  showSnippets:               { type: Boolean, default: false },
  isSelectionMode:            { type: Boolean, default: false },
  selectionIds:               { type: Set,     default: () => new Set() },
  currentSort:                { type: String,  default: 'newest' },
  currentStatus:              { type: String,  default: '' },
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
  'change-status',
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const docStore      = useDocumentStore();
const settingsStore = useSettingsStore();

const { documents, selectedDocumentId, isLoadingDocuments } = storeToRefs(docStore);
const showPdfSuffixComputed = computed(() => settingsStore.settingsDraft?.ui?.showFilenameSuffix ?? false);

const sortLabel   = computed(() => SORT_OPTIONS.find(o => o.value === props.currentSort)?.label ?? 'Sortierung');
const statusLabel = computed(() => STATUS_OPTIONS.find(o => o.value === props.currentStatus)?.label ?? 'Status');

// ── Refs ───────────────────────────────────────────────────────────────────
const thumbnailErrorMap = ref({});
const isListDragOver    = ref(false);
const listDropDragDepth = ref(0);

// ── Thumbnail helpers ──────────────────────────────────────────────────────
function thumbnailUrl(documentId) {
  return `${getBaseUrl()}/api/documents/${documentId}/thumbnail`;
}

function hasThumbnailError(documentId) {
  return Boolean(thumbnailErrorMap.value[documentId]);
}

function onThumbnailError(documentId) {
  thumbnailErrorMap.value = { ...thumbnailErrorMap.value, [documentId]: true };
}

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
  const normalized = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    const [year, month, day] = normalized.split('-').map(Number);
    return new Intl.DateTimeFormat('de-DE').format(new Date(year, month - 1, day));
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return '-';
  return new Intl.DateTimeFormat('de-DE').format(parsed);
}

function displayListDate(document) {
  if (document.document_date) {
    return `Dokumentdatum: ${formatDate(document.document_date)}`;
  }
  return 'Dokumentdatum: —';
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
/* ── Toolbar ──────────────────────────────────────────────────────────── */
.doclist-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 12px;
  border-bottom: 1px solid var(--pm-divider);
  min-height: 36px;
}

.doclist-toolbar__left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

/* Gemeinsame Basis für alle Toolbar-Buttons */
.doclist-toolbar__action-btn,
.doclist-toolbar__select-btn {
  background: none;
  border: none;
  padding: 3px 7px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: background 0.12s;
}

.doclist-toolbar__action-btn {
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.doclist-toolbar__action-btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.85);
}

.doclist-toolbar__action-btn--active {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.doclist-toolbar__select-btn {
  color: rgb(var(--v-theme-primary));
  flex-shrink: 0;
}

.doclist-toolbar__select-btn:hover {
  background: rgba(var(--v-theme-primary), 0.08);
}

.doclist-toolbar__select-btn--cancel {
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.doclist-toolbar__select-btn--cancel:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.doclist-toolbar__count {
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
  padding-left: 4px;
}

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
</style>
