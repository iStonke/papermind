<template>
  <div class="document-list-shell docs-column">
    <div v-if="activeStatusFilterLabel && !isImportsView" class="active-filter-row">
      <v-chip size="small" variant="outlined">
        Status: {{ activeStatusFilterLabel }}
      </v-chip>
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
        <div v-if="showDocumentListEmptyState" class="document-list-empty-state-wrap">
          <PmEmptyState
            :icon="documentListEmptyState.icon"
            :title="documentListEmptyState.title"
            :subtitle="documentListEmptyState.subtitle"
            size="md"
          />
        </div>

        <div v-else class="document-list">
          <div
            v-for="document in documents"
            :key="document.id"
            class="document-row pm-doc-item"
            :class="{ 'document-row--active': document.id === selectedDocumentId }"
            role="button"
            tabindex="0"
            @click="emit('select-document', document.id)"
            @keydown.enter.prevent="emit('select-document', document.id)"
            @keydown.space.prevent="emit('select-document', document.id)"
          >
            <div class="document-row__thumb">
              <img
                v-if="!hasThumbnailError(document.id)"
                :src="thumbnailUrl(document.id)"
                alt="thumbnail"
                @error="onThumbnailError(document.id)"
              />
              <div v-else class="document-row__thumb-fallback">
                <v-icon size="22">mdi-file-pdf-box</v-icon>
              </div>
            </div>

            <div class="document-row__content">
              <div class="document-row__title">
                <span v-if="document.is_unread" class="document-row__unread-dot" aria-hidden="true" />
                <div class="document-row__name">{{ formatDocumentTitle(document) }}</div>
              </div>
              <div class="document-row__meta-line">
                <div class="document-row__meta">{{ displayListDate(document) }}</div>
              </div>
              <div v-if="Array.isArray(document.tags) && document.tags.length > 0" class="document-row__tags">
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
                  size="x-small"
                  variant="outlined"
                  class="document-row__tag-chip document-row__tag-chip--more"
                >
                  +{{ document.tags.length - 3 }}
                </v-chip>
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
        </div>
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
import { storeToRefs } from 'pinia';
import { useDocumentStore } from '../stores/documents.js';
import { useSettingsStore } from '../stores/settings.js';
import { getBaseUrl } from '../api/client.js';
import PmEmptyState from './PmEmptyState.vue';

// ── Props & Emits ──────────────────────────────────────────────────────────
const props = defineProps({
  listDropNotice:          { type: String,  default: '' },
  activeStatusFilterLabel: { type: String,  default: '' },
  isImportsView:           { type: Boolean, default: false },
  isTrashView:             { type: Boolean, default: false },
  showDocumentListEmptyState: { type: Boolean, default: false },
  documentListEmptyState:  { type: Object,  default: () => ({ icon: '', title: '', subtitle: '' }) },
  showSnippets:            { type: Boolean, default: false },
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
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const docStore      = useDocumentStore();
const settingsStore = useSettingsStore();

const { documents, selectedDocumentId, isLoadingDocuments } = storeToRefs(docStore);
const showPdfSuffixComputed = computed(() => settingsStore.settingsDraft?.ui?.showFilenameSuffix ?? false);

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
