<template>
  <BaseDialog
    v-model="isOpen"
    :persistent="isUploadingSources || isCommitting"
    :max-width="MODAL_WORK_WIDTH_SPLIT"
    :card-class="['isd-card']"
    title="Importieren"
    header-subtitle="Gescannte Seiten als neues Dokument"
    @close="onDialogClose"
  >
    <div class="isd-body">
      <!-- Hidden file input required by openFilePicker() -->
      <input
        v-if="isIOSDevice"
        ref="fileInput"
        class="d-none"
        type="file"
        accept="application/pdf"
        multiple
        @change="onFileInputChange"
      />
      <input
        v-else
        ref="fileInput"
        class="d-none"
        type="file"
        accept="application/pdf"
        multiple
        webkitdirectory
        directory
        @change="onFileInputChange"
      />

      <!-- Left column: page grid + bottom toolbar -->
      <div class="isd-left">

        <!-- Ladefortschritt -->
        <v-progress-linear
          v-if="isUploadingSources"
          :model-value="hasPreparationProgress ? preparationProgressPercent : undefined"
          :indeterminate="!hasPreparationProgress"
          color="primary"
          height="3"
          class="isd-progress"
        />

        <div
          class="isd-grid-scroll"
          :style="{ ...gridScrollStyle, paddingBottom: isEmpty ? '40px' : '82px' }"
          @dragenter.prevent="onMiniatureDragEnter"
          @dragover.prevent="onMiniatureDragOver"
          @dragleave="onMiniatureDragLeave"
          @drop.prevent="onMiniatureDrop"
        >

          <!-- Dropzone (empty state) -->
          <div
            v-if="isEmpty"
            class="isd-dropzone"
            :class="{ 'isd-dropzone--over': isDropzoneDragOver }"
            role="button"
            tabindex="0"
            @click="onDropzoneClick"
            @dragenter.prevent="onDropzoneDragEnter"
            @dragover.prevent="onDropzoneDragOver"
            @dragleave="onDropzoneDragLeave"
            @drop.prevent="onDropzoneDrop"
            @mouseenter="onDropzoneMouseEnter"
            @mouseleave="onDropzoneMouseLeave"
          >
            <div class="isd-dropzone__icon">
              <v-icon size="52" class="isd-dropzone__icon-svg">mdi-tray-arrow-down</v-icon>
            </div>
            <div class="isd-dropzone__text">
              <p class="isd-dropzone__title">
                PDF-Dateien auswählen<br>oder hierher ziehen
              </p>
              <p class="isd-dropzone__subtitle">
                Mehrere Dateien gleichzeitig möglich
              </p>
            </div>
            <div class="isd-dropzone__types">
              <span class="isd-dropzone__chip">
                <v-icon size="12" class="isd-dropzone__chip-icon">mdi-file-pdf-box</v-icon>
                PDF
              </span>
            </div>
          </div>

          <!-- Page grid -->
          <div
            v-else
            class="isd-page-grid import-staging-pages"
            @dragover.prevent="onPagesContainerDragOver($event, documents[0]?.id)"
            @drop.prevent="onPagesContainerDrop($event, documents[0]?.id)"
          >
            <div
              v-for="{ doc, page, globalIndex, pageIndexInDoc } in allPagesFlat"
              :key="page.id"
              :ref="el => setPageThumbRef(page.id, el)"
              class="isd-page-card import-staging-page"
              :data-page-id="page.id"
              :data-page-index="pageIndexInDoc"
              :draggable="true"
              :class="{
                'isd-page-card--selected': isPageSelected(doc.id, page.id),
                'isd-page-card--multi': isPageMultiSelected(page.id),
                'isd-page-card--dragging': isDraggingPage(page.id),
                'isd-page-card--drop-before':
                  pageDragState.active && pageDragState.overDocId === doc.id &&
                  pageDragState.dropIndex === pageIndexInDoc && !isDraggingPage(page.id),
                'isd-page-card--drop-after':
                  pageDragState.active && pageDragState.overDocId === doc.id &&
                  pageDragState.dropIndex === pageIndexInDoc + 1 && !isDraggingPage(page.id)
              }"
              @click="onPageGridClick($event, doc, page, globalIndex)"
              @dblclick="onPageDoubleClick($event, doc.id, page.id, globalIndex)"
              @dragstart="onPageDragStart($event, doc.id, page.id, pageIndexInDoc)"
              @dragend="onPageDragEnd()"
              @dragover.prevent="onPageDragOver($event, doc.id, page.id, pageIndexInDoc)"
              @drop.prevent="onPageDrop($event, doc.id, pageIndexInDoc)"
            >
              <div class="isd-page-thumb-wrap">
                <div class="isd-page-thumb-inner">
                  <img
                    v-if="page.thumbUrl"
                    :src="page.thumbUrl"
                    class="isd-page-thumb import-staging-page__thumb"
                    :style="{ transform: page.rotation ? `rotate(${page.rotation}deg)` : undefined }"
                    draggable="false"
                    alt=""
                  />
                  <v-icon v-else size="32" class="isd-page-thumb-placeholder-icon">mdi-file-document-outline</v-icon>
                </div>
                <!-- Select-Mode Checkbox-Indikator -->
                <div
                  v-if="isSelectMode"
                  class="isd-page-select-indicator"
                  :class="{ 'isd-page-select-indicator--checked': isPageMultiSelected(page.id) }"
                >
                  <v-icon v-if="isPageMultiSelected(page.id)" size="14">mdi-check</v-icon>
                </div>
              </div>
              <div class="isd-page-num">{{ globalIndex + 1 }}</div>
            </div>

            <!-- Add-files placeholder card -->
            <div
              class="isd-add-page-card"
              :class="{
                'isd-add-page-card--disabled': isUploadingSources || isCommitting,
                'isd-add-page-card--drag-over': isAddPageDragOver
              }"
              role="button"
              tabindex="0"
              title="Dateien hierher ziehen oder klicken zum Hinzufügen"
              @click="openFilePicker"
              @keydown.enter.prevent="openFilePicker"
              @keydown.space.prevent="openFilePicker"
            >
              <div class="isd-add-page-thumb-wrap">
                <div class="isd-add-page-inner">
                  <v-icon size="28">mdi-plus</v-icon>
                </div>
              </div>
              <div class="isd-page-num" aria-hidden="true">&nbsp;</div>
            </div>
          </div>

        </div>
        <div v-show="!isEmpty" class="isd-toolbar">

          <!-- Linke Gruppe: Modus-Toggle + Seitenaktionen -->
          <div class="isd-toolbar-left">
            <v-btn
              icon
              size="x-small"
              :variant="isSelectMode ? 'flat' : 'text'"
              :color="isSelectMode ? 'primary' : undefined"
              :title="isSelectMode ? 'Auswahl beenden' : 'Seiten auswählen'"
              class="isd-toolbar-select-btn"
              :class="{ 'isd-toolbar-select-btn--active': isSelectMode }"
              @click="toggleSelectMode"
            >
              <v-icon size="20">mdi-checkbox-multiple-outline</v-icon>
            </v-btn>

            <div class="isd-toolbar-divider" />

            <div class="isd-rotate-group">
              <v-btn
                icon
                size="x-small"
                variant="text"
                title="Nach links drehen"
                :disabled="!hasAnySelectedPage"
                @click="rotateAnySelectedPage(-90)"
              >
                <v-icon size="20">mdi-rotate-left</v-icon>
              </v-btn>
              <v-btn
                icon
                size="x-small"
                variant="text"
                title="Nach rechts drehen"
                :disabled="!hasAnySelectedPage"
                @click="rotateAnySelectedPage(90)"
              >
                <v-icon size="20">mdi-rotate-right</v-icon>
              </v-btn>
            </div>

            <v-btn
              icon
              size="x-small"
              variant="text"
              color="error"
              title="Ausgewählte Seiten löschen"
              :disabled="!isDeleteEnabled"
              @click="deleteSelectedPages"
            >
              <v-icon size="20">mdi-trash-can-outline</v-icon>
            </v-btn>
          </div>

          <!-- Flexibler Abstand -->
          <div class="isd-toolbar-spacer" />

          <!-- Rechte Gruppe: Zoom + Seitenanzahl -->
          <div class="isd-toolbar-right">
            <div class="isd-zoom-group">
              <span class="isd-zoom-label">klein</span>
              <input
                type="range"
                class="isd-zoom-slider"
                min="0"
                max="3"
                step="1"
                :value="gridZoomIndex"
                @input="onGridZoomChange"
              />
              <span class="isd-zoom-label">groß</span>
            </div>
            <span class="isd-page-count">{{ totalPages }} {{ totalPages === 1 ? 'Seite' : 'Seiten' }}</span>
          </div>

        </div>
      </div>

      <!-- Right column: document properties -->
      <div class="isd-props" :class="{ 'isd-props--disabled': isEmpty }">

       <div class="isd-props-scroll">

        <!-- Document name -->
        <div class="isd-field">
          <div class="isd-field-label">
            Dokumentname
            <v-tooltip text="Wie lautet der Name des Dokuments? Wird für Suche und Anzeige verwendet." location="top" max-width="220">
              <template #activator="{ props: tip }"><v-icon class="isd-field-info" v-bind="tip" size="14">mdi-information-outline</v-icon></template>
            </v-tooltip>
          </div>
          <div class="isd-field-row">
            <v-text-field
              :model-value="primaryDocTitle"
              placeholder="z. B. Rechnung Stadtwerke März 2024"
              density="compact"
              variant="outlined"
              hide-details
              @update:model-value="onPrimaryDocTitleInput({ target: { value: $event } })"
              @blur="onPrimaryDocTitleBlur"
            />
            <v-btn
              icon
              size="small"
              variant="text"
              color="primary"
              :loading="isPrimaryDocTitleBusy"
              :disabled="isPrimaryDocTitleBusy || !primaryDocument || primaryDocument.pages.length === 0"
              title="Titel mit KI vorschlagen"
              @click="primaryDocument && requestScanTitleSuggestion(primaryDocument.id, 'first_page')"
            >
              <v-icon size="18">mdi-creation</v-icon>
            </v-btn>
          </div>
          <button
            v-if="primaryDocSuggestionText"
            type="button"
            class="isd-ai-chip"
            @click="primaryDocument && applyScanSuggestion(primaryDocument.id)"
          >
            <v-icon size="13">{{ resolveIcon('mdi-robot-outline') }}</v-icon>
            <span class="isd-ai-chip__text">{{ primaryDocSuggestionText }}</span>
            <span class="isd-ai-chip__action">übernehmen</span>
          </button>
        </div>

        <!-- Document date -->
        <div class="isd-field">
          <div class="isd-field-label">
            Dokumentdatum
            <v-tooltip text="Wann wurde das Dokument ausgestellt? (Nicht das Importdatum)" location="top" max-width="220">
              <template #activator="{ props: tip }"><v-icon class="isd-field-info" v-bind="tip" size="14">mdi-information-outline</v-icon></template>
            </v-tooltip>
            <span v-if="docDateAiFilled" class="isd-ai-filled-badge">KI</span>
          </div>
          <div class="isd-field-row">
            <v-text-field
              v-model="docDate"
              placeholder="Datum eingeben…"
              density="compact"
              variant="outlined"
              hide-details
              inputmode="numeric"
              :maxlength="10"
              @input="docDateTouched = true; docDateAiFilled = false"
            />
            <v-btn
              icon
              size="small"
              variant="text"
              color="primary"
              title="Datum aus Dokument erkennen"
            >
              <v-icon size="18">mdi-creation</v-icon>
            </v-btn>
          </div>
        </div>

        <!-- Category -->
        <div class="isd-field">
          <div class="isd-field-label">
            Kategorie
            <v-tooltip text="Grobe Einordnung: Was ist das Dokument? Ein Dokument gehört zu genau einer Kategorie." location="top" max-width="220">
              <template #activator="{ props: tip }"><v-icon class="isd-field-info" v-bind="tip" size="14">mdi-information-outline</v-icon></template>
            </v-tooltip>
            <span v-if="docCategoryAiFilled" class="isd-ai-filled-badge">KI</span>
          </div>
          <v-select
            v-model="docCategory"
            :items="DOC_CATEGORIES"
            placeholder="Kategorie wählen…"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="docCategoryTouched = true; docCategoryAiFilled = false"
          />
        </div>

        <!-- Tags -->
        <div class="isd-field">
          <div class="isd-field-label">
            Tags
            <v-tooltip text="Freie Schlagwörter für Kontext, Projekt oder Personen. Mehrere Tags möglich." location="top" max-width="220">
              <template #activator="{ props: tip }"><v-icon class="isd-field-info" v-bind="tip" size="14">mdi-information-outline</v-icon></template>
            </v-tooltip>
            <span v-if="docTagsAiFilled" class="isd-ai-filled-badge">KI</span>
          </div>
          <v-combobox
            :model-value="primaryDocTagNames"
            v-model:search="tagInlineValue"
            :items="allTagNamesForPool"
            multiple
            chips
            closable-chips
            hide-selected
            :clearable="false"
            density="compact"
            variant="outlined"
            hide-details
            placeholder="Tag hinzufügen…"
            :loading="isCreatingTags"
            :menu-props="{
              maxHeight: 220,
              offset: 4,
              closeOnContentClick: false,
              attach: 'body',
              zIndex: 6000
            }"
            @update:model-value="onTagNamesChange"
            @focus="ensureStageTagsLoaded()"
          />
        </div>

        <!-- Note -->
        <div class="isd-field">
          <div class="isd-field-label">
            Notiz
            <v-tooltip text="Interne Notiz zum Dokument – nur für dich sichtbar." location="top" max-width="220">
              <template #activator="{ props: tip }"><v-icon class="isd-field-info" v-bind="tip" size="14">mdi-information-outline</v-icon></template>
            </v-tooltip>
          </div>
          <v-textarea
            v-model="docNote"
            placeholder="Interne Notiz zum Dokument…"
            density="compact"
            variant="outlined"
            hide-details
            rows="3"
            no-resize
          />
        </div>

       </div>

        <!-- KI-Analyse-Status (gespiegelte Toolbar, unten) -->
        <div
          v-if="!isEmpty"
          class="isd-props-status"
          :class="`isd-props-status--${aiAnalysis.kind}`"
        >
          <template v-if="aiAnalysis.kind === 'busy'">
            <v-progress-circular indeterminate size="15" width="2" color="primary" />
            <span class="isd-props-status__text">KI analysiert Dokument…</span>
          </template>
          <template v-else-if="aiAnalysis.kind === 'success'">
            <v-icon size="16" color="success">mdi-check-circle-outline</v-icon>
            <span
              class="isd-props-status__text"
              :title="`Automatisch erkannt: ${aiAnalysis.fields.join(', ')}`"
            >Automatisch erkannt: {{ aiAnalysis.fields.join(', ') }}</span>
          </template>
          <template v-else-if="aiAnalysis.kind === 'partial'">
            <v-icon size="16" color="success">mdi-check-circle-outline</v-icon>
            <span class="isd-props-status__text">Analyse abgeschlossen – keine Felder ergänzt</span>
          </template>
          <template v-else-if="aiAnalysis.kind === 'failed'">
            <v-icon size="16" class="isd-props-status__warn-icon">mdi-alert-circle-outline</v-icon>
            <span class="isd-props-status__text">Keine automatische Erkennung</span>
            <button
              type="button"
              class="isd-props-status__retry"
              :disabled="!primaryDocument || primaryDocument.pages.length === 0"
              @click="primaryDocument && requestScanTitleSuggestion(primaryDocument.id, 'first_page')"
            >
              Erneut versuchen
            </button>
          </template>
          <template v-else>
            <v-icon size="16" class="isd-props-status__idle-icon">mdi-creation</v-icon>
            <span class="isd-props-status__text">Felder werden automatisch erkannt</span>
          </template>
        </div>

      </div>
    </div>

    <template #footer>
      <div class="isd-footer">
        <div class="isd-footer-start">
          <v-btn
            variant="text"
            :disabled="isUploadingSources || isCommitting"
            @click="isOpen = false"
          >
            Abbrechen
          </v-btn>
        </div>
        <div class="isd-footer-end">
          <span v-if="isCommitting || hasPreparationProgress" class="isd-footer-status">
            {{ preparationProgressLabel || 'Verarbeitung läuft…' }}
          </span>
          <v-btn
            v-if="hasMultiSelection"
            variant="tonal"
            color="primary"
            :disabled="isCommitting"
            @click="commitSelectionImport"
          >
            Auswahl importieren ({{ multiSelectionCount }})
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="isImportActionDisabled"
            @click="commitImport"
          >
            {{ isCommitting ? 'Verarbeitung läuft…' : `Importieren (${importCount})` }}
          </v-btn>
        </div>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { useTheme } from 'vuetify';
import BaseDialog from './BaseDialog.vue';
import StageTags from './StageTags.vue';
import { discardImportInboxSourcePages } from '../api/importInbox';
import { suggestImportStageTitle } from '../api/importStaging';
import { isIOS } from '../utils/platform';
import { mapApiError, useNotifications } from '../stores/notifications';
import { useImportStagingStore } from '../stores/importStaging';
import { useSettingsStore } from '../stores/settings';
import {
  SHORTCUT_ACTIONS,
  handleShortcut,
  isEditableShortcutTarget,
  useShortcutScope
} from '../keyboard/shortcuts';

GlobalWorkerOptions.workerSrc = pdfWorkerSrc;

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  apiBaseUrl: { type: String, default: '' },
  autoEmbed: { type: Boolean, default: true }
});

const emit = defineEmits(['update:modelValue', 'committed', 'discarded-sources']);

const { notify } = useNotifications();
const stagingStore = useImportStagingStore();
const settingsStore = useSettingsStore();
const theme = useTheme();
const { documents, documentCount, totalPages, emptyDocuments, commitDocuments } = storeToRefs(stagingStore);

const KNOWN_ICONS = new Set([
  'mdi-file-document-outline',
  'mdi-folder-outline',
  'mdi-plus',
  'mdi-robot-outline',
  'mdi-call-split',
  'mdi-rotate-left',
  'mdi-rotate-right',
  'mdi-dots-horizontal',
  'mdi-trash-can-outline',
  'mdi-file-pdf-box',
  'mdi-refresh',
  'mdi-check'
]);

const isDropzoneDragOver = ref(false);
const isDropzoneHover = ref(false);
const dropDragDepth = ref(0);
const documentDragDepth = ref({});
const isBodyFileDragOver = ref(false);
const bodyFileDragDepth = ref(0);
const isAddPageDragOver = ref(false);
const addPageDragDepth = ref(0);
const selected = ref(null);
const peek = ref({ open: false, x: 0, y: 0 });
const isUploadingSources = ref(false);
const isCommitting = ref(false);
const preparationProgress = ref({ done: 0, total: 0 });
const remoteSourceStageBySession = new Map();
const titleSuggestJobByStage = new Map();
const previewImageSrc = ref('');
const previewImageLoading = ref(false);
const stageTagPool = ref([]);
const fileInput = ref(null);
const peekPanelRef = ref(null);
const peekAnchorEl = ref(null);
const bodyScrollRef = ref(null);
const docsListRef = ref(null);
const titleInputRefs = new Map();
const cardFileInputRefs = new Map();
const pageThumbRefs = new Map();
let peekRepositionRaf = 0;
const pageDragState = ref({
  active: false,
  pageId: '',
  sourceDocId: '',
  sourceIndex: -1,
  overDocId: '',
  dropIndex: -1,
  hoverPageId: ''
});
const pageDropMarker = ref({
  docId: '',
  index: -1,
  left: 0,
  top: 0,
  height: 0
});
const settledPageId = ref('');
const isBodyContentOverflowing = ref(false);
let settlePageTimer = 0;
let autoScrollRaf = 0;
let bodyLayoutRaf = 0;
let bodyLayoutObserver = null;
let closeResetTimer = 0;
let viewSwitchTimer = 0;
const autoScrollState = {
  container: null,
  dx: 0,
  dy: 0
};
const isViewSwitching = ref(false);

const DOC_CATEGORIES = ['Rechnungen', 'Verträge', 'Briefe', 'Belege', 'Steuern', 'Versicherung', 'Bank'];
const docDate = ref('');
const docCategory = ref(null);
const docNote = ref('');
const docTitleTouched = ref(false);
const docDateTouched = ref(false);
const docCategoryTouched = ref(false);
const docTagsTouched = ref(false);
const docTitleAiFilled = ref(false);
const docDateAiFilled = ref(false);
const docCategoryAiFilled = ref(false);
const docTagsAiFilled = ref(false);

const docOcrLang = computed(() => settingsStore.settings.documents.ocr_doc_lang ?? 'de');
const docDateIso = computed(() => germanDateToIso(docDate.value));
const isDocDateValid = computed(() => isValidGermanDate(docDate.value));
const tagInputRef = ref(null);
const tagSearchInput = ref('');
const tagDropdownOpen = ref(false);
const tagInlineValue = ref('');
const isCreatingTags = ref(false);
const gridZoomIndex = ref(1);

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

const isIOSDevice = computed(() => isIOS());
const isEmpty = computed(() => documentCount.value === 0 && totalPages.value === 0);
const dropzoneHeadline = computed(() => (isIOSDevice.value ? 'PDFs hier ablegen' : 'PDFs oder Ordner hier ablegen'));
const dropzonePrimaryLabel = computed(() => (isIOSDevice.value ? 'PDF auswählen' : 'PDFs oder Ordner auswählen'));

function getDocumentById(documentId) {
  return documents.value.find((entry) => entry.id === documentId) || null;
}

function ensureScanMeta(documentEntry) {
  if (!documentEntry) {
    return null;
  }
  if (!documentEntry.meta || typeof documentEntry.meta !== 'object') {
    documentEntry.meta = {};
  }
  if (!Array.isArray(documentEntry.meta.scanSourceFileIds)) {
    documentEntry.meta.scanSourceFileIds = [];
  }
  if (!documentEntry.meta.titleSuggestionStatus) {
    documentEntry.meta.titleSuggestionStatus = 'idle';
  }
  if (typeof documentEntry.meta.titleSuggestion !== 'string') {
    documentEntry.meta.titleSuggestion = '';
  }
  if (typeof documentEntry.meta.titleSuggestionUsedFallback !== 'boolean') {
    documentEntry.meta.titleSuggestionUsedFallback = false;
  }
  if (typeof documentEntry.meta.titleSuggestionPollExhausted !== 'boolean') {
    documentEntry.meta.titleSuggestionPollExhausted = false;
  }
  if (!documentEntry.meta.titleSuggestionMeta || typeof documentEntry.meta.titleSuggestionMeta !== 'object') {
    documentEntry.meta.titleSuggestionMeta = null;
  }
  return documentEntry.meta;
}

function isDefaultScanTitle(title) {
  return String(title || '').trim() === 'Neuer Scan';
}

function isScanStage(documentEntry) {
  const meta = ensureScanMeta(documentEntry);
  if (!meta) {
    return false;
  }
  return Boolean(meta.isScanSession || meta.scanSourceFileIds.length > 0 || isDefaultScanTitle(documentEntry?.title));
}

function isScanTitleWorking(documentEntry) {
  return String(documentEntry?.meta?.titleSuggestionStatus || '') === 'working';
}

function isScanTitlePendingOcr(documentEntry) {
  return String(documentEntry?.meta?.titleSuggestionStatus || '') === 'pending_ocr';
}

function isScanTitleBusy(documentEntry) {
  const status = String(documentEntry?.meta?.titleSuggestionStatus || '');
  if (status === 'working') return true;
  if (status === 'pending_ocr') return !Boolean(documentEntry?.meta?.titleSuggestionPollExhausted);
  return false;
}

function canOpenTitleSuggestActions(documentEntry) {
  return Boolean(documentEntry && Number(documentEntry?.pages?.length || 0) > 0);
}

function isTitleSuggestActionDisabled(documentEntry) {
  if (isScanTitleBusy(documentEntry)) {
    return true;
  }
  return !canOpenTitleSuggestActions(documentEntry);
}

function getTitleSuggestHint(documentEntry) {
  if (isScanTitleBusy(documentEntry)) {
    return 'Bitte warten…';
  }
  if (Number(documentEntry?.pages?.length || 0) <= 0) {
    return 'Erst Seiten hinzufügen';
  }
  return 'Titel mit KI vorschlagen';
}

function hasReadyScanSuggestion(documentEntry) {
  const suggestion = String(documentEntry?.meta?.titleSuggestion || '').trim();
  const status = String(documentEntry?.meta?.titleSuggestionStatus || '');
  return Boolean(suggestion && status === 'ready');
}

function canShowScanSuggestion(documentEntry) {
  if (!hasReadyScanSuggestion(documentEntry)) {
    return false;
  }
  const suggestion = String(documentEntry?.meta?.titleSuggestion || '').trim();
  const currentTitle = String(documentEntry?.title || '').trim();
  return suggestion !== currentTitle;
}

function getScanSuggestionPrefix(documentEntry) {
  if (documentEntry?.meta?.titleSuggestionUsedFallback) {
    return 'Titel automatisch';
  }
  return 'KI-Vorschlag';
}

function getScanSuggestionActionLabel(documentEntry) {
  return documentEntry?.meta?.titleSuggestionUsedFallback ? 'Bearbeiten' : 'Übernehmen';
}

function getScanSuggestionDetails(documentEntry) {
  const meta = documentEntry?.meta?.titleSuggestionMeta;
  if (!meta || typeof meta !== 'object') {
    return '';
  }
  const details = [];
  const issuer = String(meta.issuer || '').trim();
  const subject = String(meta.subject || '').trim();
  const amount = Number(meta.amount);
  const currency = String(meta.currency || '').trim();
  if (issuer) {
    details.push(`Firma: ${issuer}`);
  }
  if (subject) {
    details.push(`Betreff: ${subject}`);
  }
  if (Number.isFinite(amount) && amount > 0) {
    const formatted = amount.toFixed(2).replace('.', ',');
    details.push(`Betrag: ${formatted}${currency === 'EUR' ? '€' : currency || ''}`);
  }
  return details.join(' · ');
}

function getStageTitleMetaText(documentEntry) {
  if (isScanTitleWorking(documentEntry)) {
    return 'Titel wird vorgeschlagen…';
  }
  if (isScanTitlePendingOcr(documentEntry)) {
    return documentEntry?.meta?.titleSuggestionPollExhausted
      ? 'OCR noch nicht fertig - später erneut versuchen.'
      : 'OCR läuft…';
  }
  if (hasReadyScanSuggestion(documentEntry)) {
    const suggestion = String(documentEntry?.meta?.titleSuggestion || '').trim();
    const details = getScanSuggestionDetails(documentEntry);
    const parts = [];
    if (canShowScanSuggestion(documentEntry)) {
      parts.push(`${getScanSuggestionPrefix(documentEntry)}: ${suggestion}`);
    } else {
      parts.push('Automatisch erkannt');
    }
    if (details) {
      parts.push(details);
    }
    return parts.join(' · ');
  }
  return '';
}

function getStageTitleMetaClass(documentEntry) {
  if (isScanTitleWorking(documentEntry)) {
    return 'scan-title-hint--working';
  }
  if (isScanTitlePendingOcr(documentEntry)) {
    return 'scan-title-hint--pending';
  }
  return 'scan-title-hint--ready';
}
const selectedDocumentEntry = computed(
  () => documents.value.find((entry) => entry.id === selected.value?.stageId) || null
);
const selectedPageEntry = computed(() => {
  const documentEntry = selectedDocumentEntry.value;
  if (!documentEntry) {
    return null;
  }
  return documentEntry.pages.find((page) => page.id === selected.value?.pageId) || null;
});
const hasSelectedPreview = computed(() => Boolean(selectedPageEntry.value));
const MODAL_WORK_WIDTH_COMPACT = 860;
const MODAL_WORK_WIDTH_SPLIT = 1180;
const dialogMaxWidth = computed(() => isEmpty.value ? MODAL_WORK_WIDTH_COMPACT : MODAL_WORK_WIDTH_SPLIT);
const dialogCardClass = computed(() => {
  if (isEmpty.value) {
    return ['import-staging-dialog-card', 'import-modal--empty'];
  }
  return ['import-staging-dialog-card', 'import-modal--work', 'import-modal--work-split'];
});
const dialogBodyClass = computed(() => [
  'import-staging-dialog-body',
  isEmpty.value ? 'import-staging-dialog-body--empty' : 'import-staging-dialog-body--work'
]);
const peekStyle = computed(() => ({
  left: `${Math.round(peek.value.x)}px`,
  top: `${Math.round(peek.value.y)}px`
}));
const pageDropMarkerStyle = computed(() => ({
  left: `${Math.round(pageDropMarker.value.left)}px`,
  top: `${Math.round(pageDropMarker.value.top)}px`,
  height: `${Math.round(pageDropMarker.value.height)}px`
}));
const importCount = computed(() => totalPages.value);
const footerSummary = computed(() => `${documentCount.value} Dokumente • ${totalPages.value} Seiten`);
const emptyHint = computed(() => (emptyDocuments.value.length > 0 ? 'Leere Dokumente werden nicht importiert.' : ''));
const primaryDocument = computed(() => documents.value[0] || null);
const primaryDocTitle = computed(() => primaryDocument.value?.title || '');
const isPrimaryDocTitleBusy = computed(() => primaryDocument.value ? isScanTitleBusy(primaryDocument.value) : false);
const primaryDocSuggestionText = computed(() => {
  if (!primaryDocument.value) return '';
  return canShowScanSuggestion(primaryDocument.value) ? String(primaryDocument.value.meta?.titleSuggestion || '').trim() : '';
});
const primaryDocTags = computed(() => {
  if (!primaryDocument.value) return [];
  return (primaryDocument.value.tags || [])
    .map(id => stageTagPool.value.find(t => t.id === id) || { id, name: id });
});
const tagDropdownResults = computed(() => {
  const q = tagSearchInput.value.trim().toLowerCase();
  const selectedIds = new Set(primaryDocument.value?.tags || []);
  const pool = stageTagPool.value.filter(t => !selectedIds.has(t.id));
  if (!q) return pool.slice(0, 8);
  return pool.filter(t => t.name.toLowerCase().includes(q)).slice(0, 8);
});
const primaryDocTagNames = computed(() => primaryDocTags.value.map(t => t.name));
const allTagNamesForPool = computed(() => stageTagPool.value.map(t => t.name));
const hasAnySelectedPage = computed(() => Boolean(selected.value?.pageId));
const gridScrollStyle = computed(() => ({
  '--pm-grid-min': ['100px', '140px', '185px', '240px'][gridZoomIndex.value] || '140px'
}));
const isImportActionDisabled = computed(() => totalPages.value <= 0 || !primaryDocTitle.value.trim() || !isDocDateValid.value || isUploadingSources.value || isCommitting.value);

/* ── Multi-Selektion ── */
const multiSelectedPageIds = ref(new Set());
const hasMultiSelection = computed(() => multiSelectedPageIds.value.size > 0);
const multiSelectionCount = computed(() => multiSelectedPageIds.value.size);
const isSelectMode = ref(false);
const isDeleteEnabled = computed(() => hasMultiSelection.value || hasAnySelectedPage.value);

function isPageMultiSelected(pageId) {
  return multiSelectedPageIds.value.has(pageId);
}

function clearMultiSelection() {
  if (multiSelectedPageIds.value.size > 0) {
    multiSelectedPageIds.value = new Set();
  }
}

const allPagesSelected = computed(() => {
  const flat = allPagesFlat.value;
  return flat.length > 0 && flat.every(({ page }) => multiSelectedPageIds.value.has(page.id));
});

function toggleSelectAll() {
  if (allPagesSelected.value) {
    clearMultiSelection();
  } else {
    multiSelectedPageIds.value = new Set(allPagesFlat.value.map(({ page }) => page.id));
  }
}

function toggleSelectMode() {
  isSelectMode.value = !isSelectMode.value;
  if (!isSelectMode.value) {
    clearMultiSelection();
  }
}

async function deleteSelectedPages() {
  if (hasMultiSelection.value) {
    const toDelete = [...multiSelectedPageIds.value];
    clearMultiSelection();
    for (const pageId of toDelete) {
      await removePage(pageId);
    }
    if (isSelectMode.value && totalPages.value === 0) {
      isSelectMode.value = false;
    }
  } else if (selected.value?.pageId) {
    await removeSelectedPage(selected.value.stageId);
  }
}

function onPageGridClick(event, doc, page, globalIndex) {
  if (isSelectMode.value) {
    const next = new Set(multiSelectedPageIds.value);
    if (next.has(page.id)) {
      next.delete(page.id);
    } else {
      next.add(page.id);
    }
    multiSelectedPageIds.value = next;
    return;
  }
  if (event.metaKey || event.ctrlKey) {
    const next = new Set(multiSelectedPageIds.value);
    if (next.size === 0 && selected.value?.pageId) {
      // Bestehende Einzelselektion beim ersten CMD+Click mit übernehmen
      if (selected.value.pageId === page.id) {
        // CMD+Click auf die bereits aktive Seite → komplett deselektieren
        clearActiveSelection();
        return;
      }
      next.add(selected.value.pageId);
    }
    if (next.has(page.id)) {
      next.delete(page.id);
      // Einzelselektion auf dieselbe Seite ebenfalls aufheben
      if (selected.value?.pageId === page.id) {
        selected.value = null;
      }
    } else {
      next.add(page.id);
      selectPage(doc.id, page.id, globalIndex);
    }
    multiSelectedPageIds.value = next;
  } else if (event.shiftKey) {
    const flat = allPagesFlat.value;
    const anchorIndex = selected.value?.pageId
      ? flat.findIndex(({ page: p }) => p.id === selected.value.pageId)
      : 0;
    const start = Math.min(anchorIndex < 0 ? 0 : anchorIndex, globalIndex);
    const end = Math.max(anchorIndex < 0 ? 0 : anchorIndex, globalIndex);
    const next = new Set(multiSelectedPageIds.value);
    for (let i = start; i <= end; i++) {
      if (flat[i]) next.add(flat[i].page.id);
    }
    multiSelectedPageIds.value = next;
  } else {
    clearMultiSelection();
    onPageClick(event, doc.id, page.id, globalIndex);
  }
}

async function commitSelectionImport() {
  if (!hasMultiSelection.value || isCommitting.value) return;
  const selectedIds = multiSelectedPageIds.value;
  const toRemove = allPagesFlat.value
    .filter(({ page }) => !selectedIds.has(page.id))
    .map(({ page }) => page.id);
  for (const pageId of toRemove) {
    await removePage(pageId);
  }
  clearMultiSelection();
  await commitImport();
}

const allPagesFlat = computed(() => {
  let index = 0;
  const result = [];
  for (const doc of documents.value) {
    let pageIndexInDoc = 0;
    for (const page of doc.pages || []) {
      result.push({ doc, page, globalIndex: index++, pageIndexInDoc: pageIndexInDoc++ });
    }
  }
  return result;
});
const hasPreparationProgress = computed(() => isUploadingSources.value && preparationProgress.value.total > 0);
const preparationProgressPercent = computed(() => {
  const total = Math.max(0, Number(preparationProgress.value.total || 0));
  const done = Math.max(0, Number(preparationProgress.value.done || 0));
  if (total <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((done / total) * 100));
});
const preparationProgressLabel = computed(() => {
  const total = Math.max(0, Number(preparationProgress.value.total || 0));
  const done = Math.max(0, Number(preparationProgress.value.done || 0));
  if (total <= 0) {
    return '';
  }
  return `Vorbereiten: ${Math.min(done, total)}/${total}`;
});
const previewImageCache = new Map();
let previewRenderNonce = 0;
const importerThemeVars = computed(() => {
  if (theme.global.current.value.dark) {
    return {
      '--pm-toolbar-btn-color': 'rgba(255, 255, 255, 0.72)',
      '--pm-toolbar-btn-opacity': '1',
      '--pm-toolbar-icon-color': 'rgba(255, 255, 255, 0.72)',
      '--pm-dm-text2': 'rgba(255, 255, 255, 0.72)'
    };
  }
  return {
    '--pm-toolbar-btn-color': 'rgba(15, 23, 42, 0.62)',
    '--pm-toolbar-btn-opacity': '1',
    '--pm-toolbar-icon-color': 'rgba(15, 23, 42, 0.62)'
  };
});
const toolbarControlEnabledStyle = Object.freeze({
  color: 'rgba(var(--v-theme-on-surface), 0.72)',
  '--v-btn-color': 'rgba(var(--v-theme-on-surface), 0.72)',
  opacity: '1'
});
const toolbarControlDisabledStyle = Object.freeze({
  color: 'rgba(var(--v-theme-on-surface), 0.34)',
  '--v-btn-color': 'rgba(var(--v-theme-on-surface), 0.34)',
  opacity: '0.5'
});


function getToolbarControlStyle(disabled) {
  return disabled ? toolbarControlDisabledStyle : toolbarControlEnabledStyle;
}

/* ── Dokumentweiter KI-Analyse-Status (für die Status-Zeile rechts unten) ──
 * Spiegelt den titleSuggestionStatus des primären Dokuments auf vier UI-Zustände:
 *   busy     – Analyse läuft
 *   success  – fertig, mindestens ein Feld automatisch befüllt
 *   partial  – fertig, aber keine Felder ergänzt
 *   failed   – Analyse fehlgeschlagen/abgebrochen (Retry anbieten)
 *   idle     – noch keine Analyse
 */
const aiAnalysis = computed(() => {
  const doc = primaryDocument.value;
  if (!doc || Number(doc.pages?.length || 0) === 0) {
    return { kind: 'idle', fields: [] };
  }
  const status = String(doc.meta?.titleSuggestionStatus || '');
  const exhausted = Boolean(doc.meta?.titleSuggestionPollExhausted);

  // Wurde mindestens ein Feld per KI befüllt, gilt die Erkennung als ERFOLGREICH –
  // unabhängig davon, ob ein späterer optionaler Schritt den Status auf 'error'
  // gesetzt hat. Sonst zeigt die UI fälschlich "Keine automatische Erkennung",
  // obwohl z. B. der Titel korrekt erkannt und eingetragen wurde.
  const fields = [];
  if (docTitleAiFilled.value) fields.push('Name');
  if (docDateAiFilled.value) fields.push('Datum');
  if (docCategoryAiFilled.value) fields.push('Kategorie');
  if (docTagsAiFilled.value) fields.push('Tags');
  if (fields.length > 0) {
    return { kind: 'success', fields };
  }

  if (status === 'working' || (status === 'pending_ocr' && !exhausted)) {
    return { kind: 'busy', fields: [] };
  }
  if (status === 'error' || (status === 'pending_ocr' && exhausted)) {
    return { kind: 'failed', fields: [] };
  }
  if (status === 'ready' || status === 'applied') {
    return { kind: 'partial', fields: [] };
  }
  return { kind: 'idle', fields: [] };
});

/* ── Datum-Hilfsfunktionen ── */
function todayDateStr() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()}`;
}

function isValidGermanDate(str) {
  if (!/^\d{2}\.\d{2}\.\d{4}$/.test(str)) return false;
  const [dd, mm, yyyy] = str.split('.').map(Number);
  const d = new Date(yyyy, mm - 1, dd);
  return d.getFullYear() === yyyy && d.getMonth() === mm - 1 && d.getDate() === dd;
}

function germanDateToIso(str) {
  if (!str || !isValidGermanDate(str)) return null;
  const [dd, mm, yyyy] = str.split('.');
  return `${yyyy}-${mm}-${dd}`;
}

function isoToGermanDate(iso) {
  if (!iso) return '';
  const [yyyy, mm, dd] = iso.split('-');
  return `${dd}.${mm}.${yyyy}`;
}

function normalizeTagName(rawName) {
  return String(rawName || '').replace(/\s+/g, ' ').trim();
}

function findStageTagIdByName(name) {
  const normalized = normalizeTagName(name).toLocaleLowerCase('de-DE');
  if (!normalized) {
    return '';
  }
  return (
    stageTagPool.value.find((entry) => normalizeTagName(entry?.name).toLocaleLowerCase('de-DE') === normalized)?.id ||
    ''
  );
}

async function fetchStageTags() {
  const response = await fetch(`${props.apiBaseUrl}/api/tags?include_count=true`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  const payload = await response.json();
  const items = Array.isArray(payload?.items) ? payload.items : [];
  stageTagPool.value = items
    .map((entry) => ({
      id: String(entry?.id || '').trim(),
      name: normalizeTagName(entry?.name || '')
    }))
    .filter((entry) => entry.id && entry.name);
}

async function ensureStageTagsLoaded(options = {}) {
  const force = Boolean(options?.force);
  if (!force && stageTagPool.value.length > 0) {
    return;
  }
  await fetchStageTags();
}

async function createStageTagByName(rawName) {
  const normalizedName = normalizeTagName(rawName);
  if (!normalizedName) {
    return '';
  }
  const existingId = findStageTagIdByName(normalizedName);
  if (existingId) {
    return existingId;
  }

  const response = await fetch(`${props.apiBaseUrl}/api/tags`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ name: normalizedName })
  });

  if (!response.ok) {
    if (response.status === 409) {
      await fetchStageTags();
      return findStageTagIdByName(normalizedName);
    }
    throw new Error(await parseResponseError(response));
  }

  const created = await response.json();
  const createdId = String(created?.id || '').trim();
  const createdTagName = normalizeTagName(created?.name || normalizedName);
  if (!createdId || !createdTagName) {
    await fetchStageTags();
    return findStageTagIdByName(normalizedName);
  }

  stageTagPool.value = [...stageTagPool.value, { id: createdId, name: createdTagName }];
  stageTagPool.value.sort((left, right) => left.name.localeCompare(right.name, 'de-DE'));
  return createdId;
}

function onDocumentTagsUpdate(documentId, tagIds) {
  stagingStore.setDocumentTags(documentId, tagIds);
}

function attachPeekGlobalListeners() {
  if (typeof window === 'undefined') {
    return;
  }
  window.addEventListener('pointerdown', onGlobalPointerDown, true);
  window.addEventListener('resize', onGlobalViewportChange);
  window.addEventListener('scroll', onGlobalViewportChange, true);
}

function detachPeekGlobalListeners() {
  if (typeof window === 'undefined') {
    return;
  }
  window.removeEventListener('pointerdown', onGlobalPointerDown, true);
  window.removeEventListener('resize', onGlobalViewportChange);
  window.removeEventListener('scroll', onGlobalViewportChange, true);
}

watch(
  () => props.modelValue,
  (open) => {
    if (open && typeof window !== 'undefined' && closeResetTimer) {
      window.clearTimeout(closeResetTimer);
      closeResetTimer = 0;
    }
    if (!open && typeof window !== 'undefined' && viewSwitchTimer) {
      window.clearTimeout(viewSwitchTimer);
      viewSwitchTimer = 0;
      isViewSwitching.value = false;
    }
    if (open) {
      return;
    }
    isDropzoneDragOver.value = false;
    dropDragDepth.value = 0;
    isBodyFileDragOver.value = false;
    bodyFileDragDepth.value = 0;
    isAddPageDragOver.value = false;
    addPageDragDepth.value = 0;
    documentDragDepth.value = {};
    selected.value = null;
    peek.value = { open: false, x: 0, y: 0 };
    peekAnchorEl.value = null;
    resetPageDragState();
    clearSettledPage();
    stopAutoScroll();
    remoteSourceStageBySession.clear();
    titleSuggestJobByStage.clear();
    previewImageSrc.value = '';
    previewImageLoading.value = false;
    previewImageCache.clear();
    pageThumbRefs.clear();
    if (typeof window === 'undefined') {
      stagingStore.reset();
      return;
    }
    if (closeResetTimer) {
      window.clearTimeout(closeResetTimer);
    }
    closeResetTimer = window.setTimeout(() => {
      closeResetTimer = 0;
      if (!props.modelValue) {
        stagingStore.reset();
      }
    }, 280);
  }
);

watch(
  isEmpty,
  () => {
    if (typeof window === 'undefined') {
      return;
    }
    isViewSwitching.value = true;
    if (viewSwitchTimer) {
      window.clearTimeout(viewSwitchTimer);
    }
    viewSwitchTimer = window.setTimeout(() => {
      viewSwitchTimer = 0;
      isViewSwitching.value = false;
      scheduleBodyContentLayoutStateUpdate();
    }, 320);
  },
  { flush: 'post' }
);

function updateBodyContentLayoutState() {
  if (typeof window === 'undefined') {
    isBodyContentOverflowing.value = false;
    return;
  }
  const scrollEl = bodyScrollRef.value;
  const docsEl = docsListRef.value;
  if (!(scrollEl instanceof HTMLElement) || !(docsEl instanceof HTMLElement)) {
    isBodyContentOverflowing.value = false;
    return;
  }
  const computedStyle = window.getComputedStyle(scrollEl);
  const paddingTop = Number.parseFloat(computedStyle.paddingTop || '0') || 0;
  const paddingBottom = Number.parseFloat(computedStyle.paddingBottom || '0') || 0;
  const availableHeight = Math.max(0, scrollEl.clientHeight - paddingTop - paddingBottom);
  const contentHeight = docsEl.offsetHeight;
  isBodyContentOverflowing.value = contentHeight > availableHeight + 1;
}

function scheduleBodyContentLayoutStateUpdate() {
  if (typeof window === 'undefined') {
    return;
  }
  if (bodyLayoutRaf) {
    return;
  }
  bodyLayoutRaf = window.requestAnimationFrame(() => {
    bodyLayoutRaf = 0;
    updateBodyContentLayoutState();
  });
}

function setupBodyLayoutObserver() {
  if (typeof window === 'undefined' || typeof ResizeObserver === 'undefined') {
    return;
  }
  if (!bodyLayoutObserver) {
    bodyLayoutObserver = new ResizeObserver(() => {
      scheduleBodyContentLayoutStateUpdate();
    });
  }
  if (bodyScrollRef.value instanceof HTMLElement) {
    bodyLayoutObserver.observe(bodyScrollRef.value);
  }
  if (docsListRef.value instanceof HTMLElement) {
    bodyLayoutObserver.observe(docsListRef.value);
  }
}

function teardownBodyLayoutObserver() {
  if (bodyLayoutObserver) {
    bodyLayoutObserver.disconnect();
  }
}

watch(
  documents,
  () => {
    nextTick(() => {
      scheduleBodyContentLayoutStateUpdate();
    });
  },
  { deep: true }
);


watch(
  isOpen,
  (open) => {
    if (!open) {
      teardownBodyLayoutObserver();
      stageTagPool.value = [];
      docDate.value = '';
      docCategory.value = null;
      docNote.value = '';
      tagInlineValue.value = '';
      isSelectMode.value = false;
      multiSelectedPageIds.value = new Set();
      docTitleTouched.value = false;
      docDateTouched.value = false;
      docCategoryTouched.value = false;
      docTagsTouched.value = false;
      docTitleAiFilled.value = false;
      docDateAiFilled.value = false;
      docCategoryAiFilled.value = false;
      docTagsAiFilled.value = false;
      return;
    }
    nextTick(() => {
      setupBodyLayoutObserver();
      scheduleBodyContentLayoutStateUpdate();
      // Selbstheilung beim (Wieder-)Öffnen des Dialogs.
      //
      // Beim Schließen wird titleSuggestJobByStage geleert (siehe Zeile ~1207),
      // während stagingStore.reset() um 280 ms verzögert ist. Öffnet der Nutzer den
      // Dialog schnell wieder (oder nach einem HMR-Update), bleiben Dokumente erhalten,
      // deren persistierter meta-Status noch 'working'/'pending_ocr'/'error' ist –
      // ohne zugehörigen Job. Solche Dokumente NICHT als fehlgeschlagen anzeigen
      // ("Keine automatische Erkennung"), sondern die Analyse erneut anstoßen, damit
      // die KI-Erkennung beim nächsten Import zuverlässig läuft. Bereits fertige
      // Dokumente ('ready'/'applied') bleiben unangetastet, der Dedup-Guard in
      // requestScanTitleSuggestion verhindert Doppelläufe.
      for (const doc of documents.value) {
        const status = String(doc.meta?.titleSuggestionStatus || '');
        const isTerminalGood = status === 'ready' || status === 'applied';
        const hasPages = Number(doc.pages?.length || 0) > 0;
        if (!isTerminalGood && hasPages && !titleSuggestJobByStage.has(doc.id)) {
          const recoverMeta = ensureScanMeta(doc);
          if (recoverMeta) {
            recoverMeta.titleSuggestionStatus = 'idle';
            recoverMeta.titleSuggestionPollExhausted = false;
          }
          void requestScanTitleSuggestion(doc.id, 'first_page', { silent: true, maxPendingRetries: 20 });
        }
      }
    });
    void ensureStageTagsLoaded().catch((error) => {
      notify({ type: 'error', message: mapApiError(error, 'Tags konnten nicht geladen werden.') });
    });
  },
  { immediate: true }
);

watch(
  documents,
  () => {
    if (!selected.value) {
      return;
    }
    const documentEntry = documents.value.find((entry) => entry.id === selected.value?.stageId);
    if (!documentEntry || documentEntry.collapsed) {
      clearActiveSelection();
      return;
    }
    const pageIndex = documentEntry.pages.findIndex((page) => page.id === selected.value?.pageId);
    if (pageIndex < 0) {
      clearActiveSelection();
      return;
    }
    if (selected.value.pageIndex !== pageIndex) {
      selected.value = {
        ...selected.value,
        pageIndex
      };
    }
    if (peek.value.open) {
      schedulePeekReposition();
    }
  },
  { deep: true }
);

const selectedPreviewRenderKey = computed(() => {
  const pageEntry = selectedPageEntry.value;
  if (!pageEntry) {
    return '';
  }
  return [
    pageEntry.id,
    pageEntry.sourceFileId,
    Number(pageEntry.pageIndex || 0),
    Number(pageEntry.rotation || 0)
  ].join(':');
});

watch(
  selectedPreviewRenderKey,
  async (renderKey) => {
    previewRenderNonce += 1;
    const nonce = previewRenderNonce;
    const pageEntry = selectedPageEntry.value;

    if (!renderKey || !pageEntry) {
      previewImageSrc.value = '';
      previewImageLoading.value = false;
      return;
    }

    const cacheKey = `${pageEntry.sourceFileId}:${pageEntry.pageIndex}:r${Number(pageEntry.rotation || 0)}:lg`;
    const cached = previewImageCache.get(cacheKey);
    if (cached) {
      previewImageSrc.value = cached;
      previewImageLoading.value = false;
      return;
    }

    previewImageSrc.value = pageEntry.thumbUrl || '';
    previewImageLoading.value = true;

    const rendered = await renderLargePreview(pageEntry, 1400, Number(pageEntry.rotation || 0));
    if (nonce !== previewRenderNonce) {
      return;
    }
    if (rendered) {
      previewImageCache.set(cacheKey, rendered);
      previewImageSrc.value = rendered;
    }
    previewImageLoading.value = false;
  }
);

watch(
  isOpen,
  (open) => {
    if (open) {
      return;
    }
    detachPeekGlobalListeners();
    stopAutoScroll();
    resetPageDragState();
    clearSettledPage();
    if (peekRepositionRaf) {
      window.cancelAnimationFrame(peekRepositionRaf);
      peekRepositionRaf = 0;
    }
  },
  { immediate: true }
);

watch(
  () => peek.value.open,
  (open) => {
    if (typeof window === 'undefined') {
      return;
    }
    if (open && isOpen.value) {
      attachPeekGlobalListeners();
      nextTick(() => schedulePeekReposition());
      return;
    }
    detachPeekGlobalListeners();
  }
);

function onDialogClose() {
  if (isUploadingSources.value || isCommitting.value) {
    return;
  }
  isOpen.value = false;
}

function resolveIcon(name) {
  if (!name) {
    return null;
  }
  return KNOWN_ICONS.has(name) ? name : null;
}

function stripPdfSuffix(filename) {
  return String(filename || '').replace(/\.pdf$/i, '').trim();
}

function getRemoteSourceTitle(source, fallback = 'Neuer Scan') {
  const title = stripPdfSuffix(source?.original_name || '');
  return title || fallback;
}

function normalizeRelativePath(pathValue) {
  return String(pathValue || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .trim();
}

function isPdfCandidate(file) {
  const filename = String(file?.name || '').toLowerCase();
  if (filename.endsWith('.pdf')) {
    return true;
  }
  return String(file?.type || '').toLowerCase() === 'application/pdf';
}

function buildDedupKey(file, relativePath = '') {
  const name = String(file?.name || '').trim();
  const size = Number(file?.size || 0);
  const lastModified = Number(file?.lastModified || 0);
  return `${name}|${size}|${lastModified}|${relativePath}`;
}

function hasFileDragPayload(event) {
  const types = Array.from(event?.dataTransfer?.types || []);
  return types.includes('Files');
}

async function parseResponseError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

async function uploadSources(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const response = await fetch(`${props.apiBaseUrl}/api/import/source`, {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  const payload = await response.json();
  if (!Array.isArray(payload?.items)) {
    throw new Error('Ungültige Antwort vom Import-Server.');
  }
  return payload.items;
}

function ensurePdfFilename(filename) {
  const normalized = String(filename || '').trim() || 'Scan Upload.pdf';
  return /\.pdf$/i.test(normalized) ? normalized : `${normalized}.pdf`;
}

async function downloadStagingSourceFile(sourceFileId, originalName = '') {
  const response = await fetch(`${props.apiBaseUrl}/api/import/source/${encodeURIComponent(sourceFileId)}/file`, {
    cache: 'no-store'
  });
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  const blob = await response.blob();
  return new File([blob], ensurePdfFilename(originalName), {
    type: 'application/pdf',
    lastModified: Date.now()
  });
}

async function renderPdfThumbnails(file, pageCount) {
  if (!(file instanceof File) || pageCount <= 0) {
    return [];
  }

  const bytes = await file.arrayBuffer();
  const loadingTask = getDocument({ data: bytes });
  const pdf = await loadingTask.promise;
  const thumbs = [];
  const total = Math.min(Number(pageCount) || 0, pdf.numPages || 0);

  try {
    for (let pageNumber = 1; pageNumber <= total; pageNumber += 1) {
      try {
        const page = await pdf.getPage(pageNumber);
        const baseViewport = page.getViewport({ scale: 1 });
        const targetWidth = 480; // 2× max grid size (240 px) → scharf auf Retina
        const scale = targetWidth / Math.max(1, baseViewport.width);
        const viewport = page.getViewport({ scale });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d', { alpha: false });

        if (!context) {
          thumbs.push('');
          continue;
        }

        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);

        await page.render({ canvasContext: context, viewport }).promise;
        thumbs.push(canvas.toDataURL('image/webp', 0.82));
      } catch {
        thumbs.push('');
      }
    }
  } finally {
    try {
      await pdf.cleanup();
    } catch {
      // ignore cleanup failures
    }
    try {
      await pdf.destroy();
    } catch {
      // ignore cleanup failures
    }
  }

  return thumbs;
}

async function renderLargePreview(pageEntry, targetLongEdge = 1400, rotation = 0) {
  const file = stagingStore.stagingFiles.get(pageEntry?.sourceFileId);
  if (!(file instanceof File)) {
    return '';
  }

  const bytes = await file.arrayBuffer();
  const loadingTask = getDocument({ data: bytes });
  const pdf = await loadingTask.promise;

  try {
    const pageNumber = Number(pageEntry?.pageIndex || 0) + 1;
    const page = await pdf.getPage(pageNumber);
    const normalizedRotation = ((Number(rotation || 0) % 360) + 360) % 360;
    const baseViewport = page.getViewport({ scale: 1, rotation: normalizedRotation });
    const scale = Math.max(0.5, targetLongEdge / Math.max(1, baseViewport.width, baseViewport.height));
    const viewport = page.getViewport({ scale, rotation: normalizedRotation });
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) {
      return '';
    }
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    await page.render({ canvasContext: context, viewport }).promise;
    return canvas.toDataURL('image/webp', 0.9);
  } catch {
    return '';
  } finally {
    try {
      await pdf.cleanup();
    } catch {
      // ignore cleanup failures
    }
    try {
      await pdf.destroy();
    } catch {
      // ignore cleanup failures
    }
  }
}

function resolveSingleDocTitle(accepted, uploaded) {
  if (uploaded.length === 1) {
    return stripPdfSuffix(uploaded[0]?.original_name || accepted[0]?.file?.name || 'Neues Dokument');
  }
  return 'Neues Dokument';
}

function ensureExistingDocTitle(documentId) {
  return documents.value.find((entry) => entry.id === documentId)?.title || 'Neues Dokument';
}

function appendSourceToDocumentSafe(documentId, payload) {
  if (typeof stagingStore.appendSourceToDocument === 'function') {
    stagingStore.appendSourceToDocument(documentId, payload);
    return;
  }

  const target = documents.value.find((entry) => entry.id === documentId);
  if (!target) {
    stagingStore.addDocumentFromSource({
      sourceFileId: payload.sourceFileId,
      title: 'Neues Dokument',
      pageCount: payload.pageCount,
      thumbUrls: payload.thumbUrls || []
    });
    return;
  }

  // HMR/back-compat fallback: create temporary source document and move its pages.
  const tempDoc = stagingStore.addDocumentFromSource({
    sourceFileId: payload.sourceFileId,
    title: target.title || 'Neues Dokument',
    pageCount: payload.pageCount,
    thumbUrls: payload.thumbUrls || []
  });
  if (!tempDoc?.id || tempDoc.id === documentId) {
    return;
  }

  const tempPages = Array.isArray(tempDoc.pages) ? [...tempDoc.pages] : [];
  for (const page of tempPages) {
    stagingStore.movePage(page.id, documentId, null);
  }
  stagingStore.deleteDocument(tempDoc.id);
  target.sourceType = 'manual';
}

async function addFilesToStaging(candidates, options = {}) {
  const dedupe = new Set();
  const accepted = [];
  let skippedNonPdf = 0;
  let skippedDuplicates = 0;

  for (const entry of candidates) {
    const file = entry.file;
    const relativePath = normalizeRelativePath(entry.relativePath);
    const dedupKey = buildDedupKey(file, relativePath);
    if (dedupe.has(dedupKey)) {
      skippedDuplicates += 1;
      continue;
    }
    dedupe.add(dedupKey);

    if (!isPdfCandidate(file)) {
      skippedNonPdf += 1;
      continue;
    }

    accepted.push(entry);
  }

  if (skippedNonPdf > 0 || skippedDuplicates > 0) {
    const parts = [];
    if (skippedNonPdf > 0) {
      if (isIOSDevice.value) {
        parts.push(`${skippedNonPdf} Datei${skippedNonPdf === 1 ? '' : 'en'} übersprungen (nur PDFs). Scanne über Dateien -> Dokumente scannen.`);
      } else {
        parts.push(`${skippedNonPdf} Datei${skippedNonPdf === 1 ? '' : 'en'} übersprungen (nur PDF).`);
      }
    }
    if (skippedDuplicates > 0) {
      parts.push(`${skippedDuplicates} Datei${skippedDuplicates === 1 ? '' : 'en'} bereits vorhanden.`);
    }
    notify({ type: 'warning', message: parts.join(' ') });
  }

  if (accepted.length <= 0) {
    return;
  }

  isUploadingSources.value = true;
  preparationProgress.value = { done: 0, total: accepted.length };
  const touchedDocumentIds = new Set();
  try {
    const uploaded = await uploadSources(accepted.map((entry) => entry.file));
    if (uploaded.length !== accepted.length) {
      throw new Error('Upload-Antwort ist unvollständig.');
    }

    let targetDocumentId = options.targetDocumentId || null;
    let nextInsertIndex = Number.isInteger(options.insertIndex) ? Math.max(0, Number(options.insertIndex)) : null;

    if (!targetDocumentId && options.createSingleDocument) {
      const created = stagingStore.addEmptyDocument(options.insertIndex, resolveSingleDocTitle(accepted, uploaded));
      targetDocumentId = created?.id || null;
    }

    if (targetDocumentId && !documents.value.some((entry) => entry.id === targetDocumentId)) {
      const fallback = stagingStore.addEmptyDocument(options.insertIndex, ensureExistingDocTitle(targetDocumentId));
      targetDocumentId = fallback?.id || null;
    }

    for (let index = 0; index < uploaded.length; index += 1) {
      const source = uploaded[index];
      const file = accepted[index].file;
      const pageCount = Number(source?.page_count || 0);
      const title = stripPdfSuffix(source?.original_name || file?.name || 'Neues Dokument');
      let thumbs = [];
      try {
        thumbs = await renderPdfThumbnails(file, pageCount);
      } catch {
        // Thumbnails are optional; a failed render must not abort the entire batch.
      }

      stagingStore.setStagingFile(source.source_file_id, file, {
        originalName: source?.original_name || file?.name || '',
        pageCount
      });

      if (targetDocumentId) {
        appendSourceToDocumentSafe(targetDocumentId, {
          sourceFileId: source.source_file_id,
          pageCount,
          thumbUrls: thumbs
        });
        touchedDocumentIds.add(targetDocumentId);
      } else {
        const newDoc = stagingStore.addDocumentFromSource({
          sourceFileId: source.source_file_id,
          title,
          pageCount,
          thumbUrls: thumbs,
          insertIndex: nextInsertIndex
        });
        if (newDoc?.id) {
          touchedDocumentIds.add(newDoc.id);
        }
        if (nextInsertIndex != null) {
          nextInsertIndex += 1;
        }
      }
      preparationProgress.value = {
        ...preparationProgress.value,
        done: index + 1
      };
    }

  } finally {
    isUploadingSources.value = false;
    // Always start OCR jobs for any docs whose pages were queued for analysis.
    // Runs in finally so a mid-batch exception (e.g. thumbnail render failure)
    // never leaves pages stuck in 'analyzing' with no job running.
    for (const docId of touchedDocumentIds) {
      const docEntry = getDocumentById(docId);
      const docMeta = ensureScanMeta(docEntry);
      if (!docEntry || !docMeta || isScanTitleBusy(docEntry)) continue;
      if (Number(docEntry.pages?.length || 0) === 0) continue;
      // Trigger the per-document KI analysis unless it already completed for this doc.
      const alreadyAnalyzed = ['ready', 'applied'].includes(String(docMeta.titleSuggestionStatus || ''));
      if (!alreadyAnalyzed) {
        void requestScanTitleSuggestion(docId, 'first_page', { silent: true, maxPendingRetries: 20 });
      }
    }
    preparationProgress.value = { done: 0, total: 0 };
  }
}

async function addRemoteSources(payload = []) {
  const items = Array.isArray(payload) ? payload : Array.isArray(payload?.sources) ? payload.sources : [];
  const preferredTargetStageId = String(payload?.targetStageId || '').trim() || null;
  const sessionId = String(payload?.sessionId || '').trim() || '__scan_default__';
  if (items.length === 0) {
    return;
  }

  let addedCount = 0;
  let previewFallbackCount = 0;
  let sessionStageId = preferredTargetStageId || remoteSourceStageBySession.get(sessionId) || null;
  const isSessionManagedScanStage = !preferredTargetStageId;
  const initialScanTitle = items.map((item) => getRemoteSourceTitle(item, '')).find(Boolean) || 'Neuer Scan';

  if (!sessionStageId) {
    const created = stagingStore.addEmptyDocument(null, initialScanTitle);
    sessionStageId = created?.id || null;
    if (sessionStageId) {
      remoteSourceStageBySession.set(sessionId, sessionStageId);
      const createdDoc = getDocumentById(sessionStageId);
      const createdMeta = ensureScanMeta(createdDoc);
      if (createdMeta) {
        createdMeta.isScanSession = true;
      }
    }
  } else if (!documents.value.some((entry) => entry.id === sessionStageId)) {
    const recreated = stagingStore.addEmptyDocument(null, initialScanTitle);
    sessionStageId = recreated?.id || null;
    if (sessionStageId) {
      remoteSourceStageBySession.set(sessionId, sessionStageId);
      const recreatedDoc = getDocumentById(sessionStageId);
      const recreatedMeta = ensureScanMeta(recreatedDoc);
      if (recreatedMeta) {
        recreatedMeta.isScanSession = true;
      }
    }
  } else {
    remoteSourceStageBySession.set(sessionId, sessionStageId);
    const existingDoc = getDocumentById(sessionStageId);
    const existingMeta = ensureScanMeta(existingDoc);
    if (existingMeta) {
      existingMeta.isScanSession = isSessionManagedScanStage || isDefaultScanTitle(existingDoc?.title);
    }
  }

  const touchedStageIds = new Set();

  for (const source of items) {
    const sourceFileId = String(source?.source_file_id || '').trim();
    const pageCount = Number(source?.page_count || 0);
    if (!sourceFileId || pageCount <= 0) {
      continue;
    }
    if (stagingStore.sourceMetaById?.has?.(sourceFileId)) {
      continue;
    }

    const originalName = String(source?.original_name || '').trim() || 'Scan Upload.pdf';
    const sourceTitle = getRemoteSourceTitle(source);
    let stagingFile = null;
    let thumbUrls = [];
    try {
      stagingFile = await downloadStagingSourceFile(sourceFileId, originalName);
      thumbUrls = await renderPdfThumbnails(stagingFile, pageCount);
    } catch {
      previewFallbackCount += 1;
    }

    stagingStore.setStagingFile(sourceFileId, stagingFile, { originalName, pageCount, isImportInbox: true });
    const targetStageId = String(source?.target_stage_id || '').trim() || sessionStageId;
    if (targetStageId && documents.value.some((entry) => entry.id === targetStageId)) {
      const targetDoc = getDocumentById(targetStageId);
      const targetMeta = ensureScanMeta(targetDoc);
      if (isDefaultScanTitle(targetDoc?.title) && sourceTitle) {
        stagingStore.renameDocument(targetStageId, sourceTitle);
      }
      if (targetMeta) {
        targetMeta.isScanSession = targetMeta.isScanSession || isSessionManagedScanStage || isDefaultScanTitle(targetDoc?.title);
        if (!targetMeta.scanSourceFileIds.includes(sourceFileId)) {
          targetMeta.scanSourceFileIds.push(sourceFileId);
        }
      }
      appendSourceToDocumentSafe(targetStageId, {
        sourceFileId,
        pageCount,
        thumbUrls
      });
      touchedStageIds.add(targetStageId);
    } else {
      const fallback = stagingStore.addEmptyDocument(null, sourceTitle);
      const fallbackStageId = fallback?.id || null;
      if (fallbackStageId) {
        remoteSourceStageBySession.set(sessionId, fallbackStageId);
        const fallbackDoc = getDocumentById(fallbackStageId);
        const fallbackMeta = ensureScanMeta(fallbackDoc);
        if (fallbackMeta) {
          fallbackMeta.isScanSession = true;
          if (!fallbackMeta.scanSourceFileIds.includes(sourceFileId)) {
            fallbackMeta.scanSourceFileIds.push(sourceFileId);
          }
        }
        appendSourceToDocumentSafe(fallbackStageId, {
          sourceFileId,
          pageCount,
          thumbUrls
        });
        touchedStageIds.add(fallbackStageId);
      } else {
        stagingStore.addDocumentFromSource({
          sourceFileId,
          title: sourceTitle,
          pageCount,
          thumbUrls
        });
      }
    }
    addedCount += 1;
  }

  for (const stageId of touchedStageIds) {
    const targetDoc = getDocumentById(stageId);
    const targetMeta = ensureScanMeta(targetDoc);
    if (!targetDoc || !targetMeta) {
      continue;
    }
    const hasSuggestion = Boolean(String(targetMeta.titleSuggestion || '').trim());
    if (targetMeta.isScanSession && !hasSuggestion && !isScanTitleBusy(targetDoc)) {
      void requestScanTitleSuggestion(stageId, 'first_page', { silent: true });
    }
  }

  if (addedCount > 0) {
    notify({
      type: 'success',
      message: `${addedCount} iPhone-Upload${addedCount === 1 ? '' : 's'} hinzugefügt.`
    });
  }
  if (previewFallbackCount > 0) {
    notify({
      type: 'warning',
      message: `Bei ${previewFallbackCount} iPhone-Upload${previewFallbackCount === 1 ? '' : 's'} fehlen Vorschaubilder.`
    });
  }
}

function collectScanSourceFileIds(stageId) {
  const documentEntry = getDocumentById(stageId);
  if (!documentEntry) {
    return [];
  }
  const fromPages = Array.isArray(documentEntry.pages)
    ? documentEntry.pages.map((page) => String(page?.sourceFileId || '').trim()).filter(Boolean)
    : [];
  const fromMeta = Array.isArray(documentEntry?.meta?.scanSourceFileIds)
    ? documentEntry.meta.scanSourceFileIds.map((entry) => String(entry || '').trim()).filter(Boolean)
    : [];
  return Array.from(new Set([...fromMeta, ...fromPages]));
}

async function requestScanTitleSuggestion(stageId, pageScope = 'first_page', options = {}) {
  const normalizedStageId = String(stageId || '').trim();
  if (!normalizedStageId) {
    return;
  }
  const documentEntry = getDocumentById(normalizedStageId);
  if (!documentEntry) {
    return;
  }
  const meta = ensureScanMeta(documentEntry);
  if (!meta) {
    return;
  }

  const normalizedScope = String(pageScope || '').trim().toLowerCase() === 'all_pages' ? 'all_pages' : 'first_page';
  if (titleSuggestJobByStage.has(normalizedStageId)) {
    return titleSuggestJobByStage.get(normalizedStageId);
  }

  const sourceFileIds = collectScanSourceFileIds(normalizedStageId);
  if (sourceFileIds.length === 0) {
    return;
  }

  meta.titleSuggestionStatus = 'working';
  meta.titleSuggestionPollExhausted = false;
  meta.titleSuggestionUsedFallback = false;
  meta.titleSuggestionMeta = null;
  const job = (async () => {
    const maxPendingRetries = options?.maxPendingRetries != null ? options.maxPendingRetries : 10;
    let attempt = 0;
    try {
      while (attempt < maxPendingRetries) {
        // WICHTIG: Hier KEINE Abfrage auf isOpen/modelValue, die den Job abbricht.
        // Das war die Hauptursache für "Keine automatische Erkennung": Wird der Dialog
        // mit einem neuen Scan geöffnet, läuft dieser Analyse-Job, während
        // props.modelValue noch false ist (der Dialog öffnet gerade erst). Ein
        // Abbruch mit status='error' VOR dem Request markierte dann fälschlich einen
        // Fehlschlag – obwohl die Erkennung nie versucht wurde. Die Analyse läuft jetzt
        // unabhängig vom Offen-Zustand; das Ergebnis landet im meta und wird beim
        // Anzeigen genutzt. Der Request ist durch AbortController (90 s) begrenzt, ein
        // "Ghost-working" kann es also nicht geben.
        const payload = await suggestImportStageTitle(props.apiBaseUrl, normalizedStageId, {
          sourceFileIds,
          pageScope: normalizedScope
        });
        const status = String(payload?.status || 'ready').trim().toLowerCase();
        if (status === 'pending_ocr') {
          meta.titleSuggestionStatus = 'pending_ocr';
          attempt += 1;
          if (attempt >= maxPendingRetries) {
            meta.titleSuggestionPollExhausted = true;
            if (!options?.silent) {
              notify({ type: 'warning', message: 'OCR noch nicht fertig - bitte später erneut versuchen.' });
            }
            return;
          }
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
          continue;
        }

        const suggestion = String(payload?.suggestion || '').trim();
        if (suggestion) {
          meta.titleSuggestion = suggestion;
        }
        meta.titleSuggestionUsedFallback = Boolean(payload?.usedFallback);
        meta.titleSuggestionMeta = payload?.meta && typeof payload.meta === 'object' ? payload.meta : null;
        meta.titleSuggestionStatus = 'ready';

        // Auto-Fill aller vier Felder (Name, Datum, Kategorie, Tags) aus KI-Meta.
        // Immer aktiv im Import-Dialog – der Nutzer prüft vor dem Import und kann
        // jedes Feld überschreiben (überschriebene Felder werden respektiert).
        //
        // Best-effort: Der Vorschlag steht ab hier bereits (Status 'ready'). Ein
        // Fehler beim Anreichern (z. B. /api/tags nicht erreichbar oder
        // primaryDocument wechselt während eines await) darf die erfolgreiche
        // Erkennung NICHT in den 'error'-Status kippen – sonst zeigt die UI
        // fälschlich "Keine automatische Erkennung" trotz 200-Antwort.
        try {
        if (normalizedStageId === primaryDocument.value?.id) {
          // Dokumentname: nur bei belastbarem Vorschlag (kein Fallback) automatisch
          // übernehmen und nur, wenn der Nutzer den Titel nicht selbst angefasst hat.
          if (suggestion && !meta.titleSuggestionUsedFallback && !docTitleTouched.value) {
            stagingStore.renameDocument(normalizedStageId, suggestion);
            meta.titleSuggestionStatus = 'applied';
            docTitleAiFilled.value = true;
          }

          const aiMeta = payload?.meta;
          if (aiMeta && typeof aiMeta === 'object') {
            // Datum
            const isoDate = String(aiMeta.date || '').trim();
            if (/^\d{4}-\d{2}-\d{2}$/.test(isoDate) && !docDateTouched.value) {
              const formatted = isoToGermanDate(isoDate);
              if (formatted && isValidGermanDate(formatted)) {
                docDate.value = formatted;
                docDateAiFilled.value = true;
              }
            }
            // Kategorie
            const aiCategory = String(aiMeta.category || '').trim();
            if (aiCategory && !docCategoryTouched.value) {
              docCategory.value = aiCategory;
              docCategoryAiFilled.value = true;
            }
            // Tags: vorhandene bevorzugen, sonst sinnvolle neu anlegen.
            // findStageTagIdByName matcht normalisiert (Groß-/Kleinschreibung,
            // Leerzeichen) gegen den Bestand; das Backend rastet KI-Tags zusätzlich
            // auf die exakte Schreibweise vorhandener Tags ein. Nur wenn wirklich
            // kein passendes Tag existiert, wird eines neu erstellt.
            const aiTags = Array.isArray(aiMeta.tags) ? aiMeta.tags : [];
            if (aiTags.length > 0 && !docTagsTouched.value && primaryDocument.value) {
              await ensureStageTagsLoaded();
              const targetDocId = primaryDocument.value.id;
              const toAdd = [];
              for (const rawName of aiTags) {
                const name = normalizeTagName(String(rawName || ''));
                if (!name) continue;
                let id = findStageTagIdByName(name);
                if (!id) {
                  try {
                    id = await createStageTagByName(name);
                  } catch (tagErr) {
                    console.warn('[ImportStaging] Tag konnte nicht angelegt werden:', name, tagErr);
                    continue;
                  }
                }
                if (id && !toAdd.includes(id)) {
                  toAdd.push(id);
                }
              }
              // Aktuellen Tag-Stand frisch lesen (das Dokument könnte sich während
              // der await-Aufrufe geändert haben) und nur fehlende Tags ergänzen.
              const freshDoc = getDocumentById(targetDocId);
              if (freshDoc && toAdd.length > 0) {
                const current = new Set(freshDoc.tags || []);
                const merged = [...current];
                for (const id of toAdd) {
                  if (!current.has(id)) merged.push(id);
                }
                if (merged.length > current.size) {
                  onDocumentTagsUpdate(targetDocId, merged);
                  docTagsAiFilled.value = true;
                }
              }
            }
          }
        }
        } catch (enrichError) {
          // Anreicherung ist optional – der Vorschlag steht bereits (Status 'ready'/'applied').
          console.warn('[ImportStaging] KI-Felder konnten nicht angewendet werden:', enrichError);
        }

        if (!options?.silent) {
          notify({ type: 'success', message: 'Titelvorschlag aktualisiert.' });
        }
        return;
      }
    } catch (error) {
      meta.titleSuggestionStatus = 'error';
      if (!options?.silent) {
        notify({ type: 'error', message: mapApiError(error, 'Titelvorschlag konnte nicht erstellt werden.') });
      }
    } finally {
      titleSuggestJobByStage.delete(normalizedStageId);
    }
  })();
  titleSuggestJobByStage.set(normalizedStageId, job);

  // Safety net: the request itself is bounded by SUGGEST_TITLE_TIMEOUT_MS (90 s) via
  // AbortController; on timeout the fetch rejects and the catch sets a terminal state.
  // This timer is only a last resort and must fire AFTER that timeout — never before —
  // otherwise a slow-but-successful OCR run (Tesseract auf großen Scans) wird fälschlich
  // als Fehler markiert ("Keine automatische Erkennung").
  const safetyTimer = window.setTimeout(() => {
    if (meta.titleSuggestionStatus === 'working' || meta.titleSuggestionStatus === 'pending_ocr') {
      meta.titleSuggestionStatus = 'error';
    }
  }, 95_000);
  job.finally(() => window.clearTimeout(safetyTimer));

  return job;
}

function applyScanSuggestion(stageId) {
  const documentEntry = getDocumentById(stageId);
  const suggestion = String(documentEntry?.meta?.titleSuggestion || '').trim();
  if (!documentEntry || !suggestion) {
    return;
  }
  if (documentEntry?.meta?.titleSuggestionUsedFallback) {
    stagingStore.setDocumentTitleDraft(stageId, suggestion);
    nextTick(() => {
      focusDocumentTitle(stageId);
    });
    return;
  }
  stagingStore.renameDocument(stageId, suggestion);
  const meta = ensureScanMeta(documentEntry);
  if (meta) {
    meta.titleSuggestionStatus = 'applied';
  }
}

function openFilePicker() {
  fileInput.value?.click();
}

function setCardFileInputRef(documentId, element) {
  if (!element) {
    cardFileInputRefs.delete(documentId);
    return;
  }
  cardFileInputRefs.set(documentId, element);
}

function openCardFilePicker(documentId) {
  cardFileInputRefs.get(documentId)?.click?.();
}

function fileListToCandidates(files, source = 'file') {
  return Array.from(files || []).map((file) => ({
    file,
    relativePath:
      source === 'folder' || source === 'auto'
        ? normalizeRelativePath(file?.webkitRelativePath)
        : ''
  }));
}

async function onFileInputChange(event) {
  const candidates = fileListToCandidates(event.target?.files, 'auto');
  event.target.value = '';
  if (candidates.length <= 0) {
    return;
  }

  try {
    await addFilesToStaging(candidates);
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Import-Quellen konnten nicht hochgeladen werden.') });
  }
}

async function onCardFileInputChange(event, documentId) {
  const candidates = fileListToCandidates(event.target?.files, 'file');
  event.target.value = '';
  if (candidates.length <= 0) {
    return;
  }

  try {
    await addFilesToStaging(candidates, {
      targetDocumentId: documentId,
      showSelectionSummary: false
    });
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
  }
}

function onDropzoneDragEnter(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  dropDragDepth.value += 1;
  isDropzoneDragOver.value = true;
}

function onDropzoneDragOver(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.dataTransfer.dropEffect = 'copy';
  isDropzoneDragOver.value = true;
}

function onDropzoneDragLeave(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  dropDragDepth.value = Math.max(0, dropDragDepth.value - 1);
  if (dropDragDepth.value === 0) {
    isDropzoneDragOver.value = false;
  }
}

function onDropzoneMouseEnter() {
  isDropzoneHover.value = true;
}

function onDropzoneMouseLeave() {
  isDropzoneHover.value = false;
}

function onDropzoneFocusIn() {
  isDropzoneHover.value = true;
}

function onDropzoneFocusOut(event) {
  const currentTarget = event?.currentTarget;
  const nextTarget = event?.relatedTarget;
  if (currentTarget instanceof HTMLElement && nextTarget instanceof Node && currentTarget.contains(nextTarget)) {
    return;
  }
  isDropzoneHover.value = false;
}

function onDropzoneClick(event) {
  if (isUploadingSources.value || isCommitting.value) {
    return;
  }
  const target = event?.target;
  if (target instanceof HTMLElement && target.closest('button, a, input, label')) {
    return;
  }
  openFilePicker();
}

function onDropzoneKeyboardActivate() {
  if (isUploadingSources.value || isCommitting.value) {
    return;
  }
  openFilePicker();
}

function readFileEntry(entry, prefix = '') {
  return new Promise((resolve) => {
    entry.file((file) => {
      resolve([
        {
          file,
          relativePath: normalizeRelativePath(`${prefix}${file.name}`)
        }
      ]);
    });
  });
}

function readDirectoryEntries(directoryReader) {
  return new Promise((resolve, reject) => {
    const entries = [];

    function readNextBatch() {
      directoryReader.readEntries(
        (batch) => {
          if (!batch.length) {
            resolve(entries);
            return;
          }
          entries.push(...batch);
          readNextBatch();
        },
        (error) => reject(error)
      );
    }

    readNextBatch();
  });
}

async function readDroppedEntry(entry, prefix = '') {
  if (entry.isFile) {
    return readFileEntry(entry, prefix);
  }
  if (!entry.isDirectory) {
    return [];
  }

  const children = await readDirectoryEntries(entry.createReader());
  const results = [];
  for (const child of children) {
    const childResults = await readDroppedEntry(child, `${prefix}${entry.name}/`);
    results.push(...childResults);
  }
  return results;
}

async function collectDropCandidates(dataTransfer) {
  const items = Array.from(dataTransfer?.items || []);
  if (items.length > 0 && typeof items[0]?.webkitGetAsEntry === 'function') {
    const collected = [];
    for (const item of items) {
      const entry = item.webkitGetAsEntry?.();
      if (!entry) {
        continue;
      }
      const results = await readDroppedEntry(entry, '');
      collected.push(...results);
    }
    if (collected.length > 0) {
      return collected;
    }
  }

  return Array.from(dataTransfer?.files || []).map((file) => ({ file, relativePath: '' }));
}

async function addNewDocumentsFromTransfer(dataTransfer, options = {}) {
  const candidates = await collectDropCandidates(dataTransfer);
  await addFilesToStaging(candidates, {
    insertIndex: options.insertIndex,
    showSelectionSummary: false
  });
}

async function onDropzoneDrop(event) {
  event.stopPropagation();
  isDropzoneDragOver.value = false;
  dropDragDepth.value = 0;

  try {
    const candidates = await collectDropCandidates(event.dataTransfer);
    await addFilesToStaging(candidates);
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Import-Quellen konnten nicht hochgeladen werden.') });
  }
}

// Der gesamte Miniatur-Bereich (.isd-grid-scroll – inklusive der leeren Fläche
// unter den Seiten) ist die Drop-Zone für neue PDF-Dokumente/Seiten von außen.
// Der Add-Page-Platzhalter dient nur als optischer Indikator: Sobald eine Datei
// über dem Bereich schwebt, "leuchtet" er via isAddPageDragOver auf. Der
// Tiefen-Zähler verhindert Flackern beim Überqueren von Kind-Elementen.
// (Das Verschieben vorhandener Seiten ist kein Datei-Payload und löst kein
// Highlight aus; im Leerzustand übernimmt die eigene .isd-dropzone.)
function onMiniatureDragEnter(event) {
  if (isEmpty.value || !hasFileDragPayload(event)) {
    return;
  }
  addPageDragDepth.value += 1;
  isAddPageDragOver.value = true;
}

function onMiniatureDragOver(event) {
  if (isEmpty.value || !hasFileDragPayload(event)) {
    return;
  }
  event.dataTransfer.dropEffect = 'copy';
  isAddPageDragOver.value = true;
}

function onMiniatureDragLeave(event) {
  if (isEmpty.value || !hasFileDragPayload(event)) {
    return;
  }
  addPageDragDepth.value = Math.max(0, addPageDragDepth.value - 1);
  if (addPageDragDepth.value === 0) {
    isAddPageDragOver.value = false;
  }
}

async function onMiniatureDrop(event) {
  if (isEmpty.value || !hasFileDragPayload(event)) {
    return;
  }
  isAddPageDragOver.value = false;
  addPageDragDepth.value = 0;
  if (isUploadingSources.value || isCommitting.value) {
    return;
  }

  try {
    const candidates = await collectDropCandidates(event.dataTransfer);
    await addFilesToStaging(candidates, {
      targetDocumentId: documents.value[0]?.id,
      showSelectionSummary: false
    });
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
  }
}

function setTitleInputRef(documentId, element) {
  if (!element) {
    titleInputRefs.delete(documentId);
    return;
  }
  titleInputRefs.set(documentId, element);
}

function focusDocumentTitle(documentId) {
  const target = titleInputRefs.get(documentId);
  target?.focus?.();
  target?.select?.();
}

function onDocumentTitleInput(documentId, event) {
  stagingStore.setDocumentTitleDraft(documentId, event.target?.value || '');
}

function onDocumentTitleBlur(documentId) {
  const documentEntry = documents.value.find((entry) => entry.id === documentId);
  stagingStore.renameDocument(documentId, documentEntry?.title || 'Neues Dokument');
}

function onDocumentTitleEnter(event, documentId) {
  const input = event.target;
  input?.blur?.();
  onDocumentTitleBlur(documentId);
}

function handleDocumentTitleShortcut(event, documentId) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, () => onDocumentTitleEnter(event, documentId), {
    ignoreEditable: false
  });
}

function handleDropzoneShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.ACTIVATE, onDropzoneKeyboardActivate, { ignoreEditable: false });
}

function addEmptyDocument() {
  const created = stagingStore.addEmptyDocument();
  if (!created) {
    return;
  }
  nextTick(() => {
    focusDocumentTitle(created.id);
  });
}

function onPrimaryDocTitleInput(event) {
  if (!primaryDocument.value) return;
  docTitleTouched.value = true;
  docTitleAiFilled.value = false;
  stagingStore.setDocumentTitleDraft(primaryDocument.value.id, event.target?.value || '');
}

function onPrimaryDocTitleBlur() {
  if (!primaryDocument.value) return;
  const title = (primaryDocument.value?.title || '').trim();
  if (title) {
    stagingStore.renameDocument(primaryDocument.value.id, title);
  }
}

function rotateAnySelectedPage(delta) {
  if (!selected.value?.stageId) return;
  rotateSelectedPage(selected.value.stageId, delta);
}

function onGridZoomChange(event) {
  gridZoomIndex.value = Number(event.target?.value ?? 1);
}

function addPrimaryDocTagById(tagId) {
  if (!primaryDocument.value) return;
  const current = primaryDocument.value.tags || [];
  if (!current.includes(tagId)) {
    onDocumentTagsUpdate(primaryDocument.value.id, [...current, tagId]);
  }
}
function removePrimaryDocTag(tagId) {
  if (!primaryDocument.value) return;
  onDocumentTagsUpdate(primaryDocument.value.id, (primaryDocument.value.tags || []).filter(id => id !== tagId));
}
function onTagInputBackspace() {
  if (tagSearchInput.value === '' && primaryDocument.value?.tags?.length > 0) {
    const tags = primaryDocument.value.tags;
    removePrimaryDocTag(tags[tags.length - 1]);
  }
}
function focusTagInput() { tagInputRef.value?.focus(); }

async function onTagNamesChange(newNames) {
  if (!primaryDocument.value) return;
  docTagsTouched.value = true;
  docTagsAiFilled.value = false;
  isCreatingTags.value = true;
  try {
    const ids = [];
    for (const name of newNames) {
      if (!name || typeof name !== 'string') continue;
      const id = findStageTagIdByName(name) || await createStageTagByName(name);
      if (id) ids.push(id);
    }
    stagingStore.setDocumentTags(primaryDocument.value.id, ids);
  } finally {
    isCreatingTags.value = false;
  }
}

// Auto-Masking DD.MM.YYYY beim Tippen
watch(docDate, (newVal, oldVal) => {
  if (newVal.length <= (oldVal?.length ?? 0)) return; // Löschen: nicht eingreifen
  const digits = newVal.replace(/\D/g, '').slice(0, 8);
  let formatted = digits;
  if (digits.length > 2) formatted = digits.slice(0, 2) + '.' + digits.slice(2);
  if (digits.length > 4) formatted = digits.slice(0, 2) + '.' + digits.slice(2, 4) + '.' + digits.slice(4);
  if (formatted !== newVal) docDate.value = formatted;
}, { flush: 'sync' });

// Datum auf heute setzen sobald das erste Dokument erscheint
watch(isEmpty, (empty) => {
  if (!empty && !docDate.value) {
    docDate.value = todayDateStr();
  }
});


function normalizeSourceFileId(sourceFileId) {
  return String(sourceFileId || '').trim();
}

function collectDocumentSourceFileIds(documentId) {
  const documentEntry = documents.value.find((entry) => entry.id === documentId);
  if (!documentEntry) {
    return [];
  }
  const ids = new Set();
  for (const page of documentEntry.pages || []) {
    const sourceFileId = normalizeSourceFileId(page?.sourceFileId);
    if (sourceFileId) {
      ids.add(sourceFileId);
    }
  }
  if (Array.isArray(documentEntry.meta?.scanSourceFileIds)) {
    for (const sourceFileId of documentEntry.meta.scanSourceFileIds) {
      const normalized = normalizeSourceFileId(sourceFileId);
      if (normalized) {
        ids.add(normalized);
      }
    }
  }
  return Array.from(ids);
}

function notifyDiscardedSourceFileIds(sourceFileIds = []) {
  const candidates = Array.from(new Set((sourceFileIds || []).map(normalizeSourceFileId).filter(Boolean)));
  if (candidates.length === 0) {
    return;
  }
  const usedSourceIds = stagingStore.collectUsedSourceFileIds();
  const discarded = candidates.filter((sourceFileId) => !usedSourceIds.has(sourceFileId));
  if (discarded.length > 0) {
    emit('discarded-sources', { sourceFileIds: discarded });
  }
}

function countPagesForSourceFile(sourceFileId) {
  const normalized = normalizeSourceFileId(sourceFileId);
  if (!normalized) {
    return 0;
  }
  return documents.value.reduce(
    (sum, documentEntry) =>
      sum + (documentEntry.pages || []).filter((page) => normalizeSourceFileId(page?.sourceFileId) === normalized).length,
    0
  );
}

function isImportInboxSourceFile(sourceFileId) {
  const normalized = normalizeSourceFileId(sourceFileId);
  return Boolean(normalized && stagingStore.sourceMetaById?.get?.(normalized)?.isImportInbox);
}

function clearPreviewCacheForSource(sourceFileId) {
  const normalized = normalizeSourceFileId(sourceFileId);
  if (!normalized) {
    return;
  }
  for (const cacheKey of Array.from(previewImageCache.keys())) {
    if (String(cacheKey).startsWith(`${normalized}:`)) {
      previewImageCache.delete(cacheKey);
    }
  }
}

async function refreshImportInboxSourceFile(sourceFileId, pageCount) {
  const normalized = normalizeSourceFileId(sourceFileId);
  const sourceMeta = stagingStore.sourceMetaById?.get?.(normalized);
  if (!normalized || !sourceMeta) {
    return;
  }
  try {
    const refreshedFile = await downloadStagingSourceFile(normalized, sourceMeta.originalName || '');
    const thumbUrls = await renderPdfThumbnails(refreshedFile, Number(pageCount || sourceMeta.pageCount || 0));
    stagingStore.setStagingFile(normalized, refreshedFile, {
      originalName: sourceMeta.originalName || refreshedFile.name,
      pageCount: Number(pageCount || sourceMeta.pageCount || 0),
      isImportInbox: true
    });
    stagingStore.updateSourceThumbnails(normalized, thumbUrls);
    clearPreviewCacheForSource(normalized);
  } catch {
    // The existing thumbnails are still usable; the backend source is already updated.
  }
}

async function removePage(pageId) {
  const location = stagingStore.findPageLocation(pageId);
  const sourceFileId = normalizeSourceFileId(location?.page?.sourceFileId);
  const sourcePageIndex = Number(location?.page?.pageIndex || 0);
  const shouldPersistSourcePageRemoval =
    sourceFileId && isImportInboxSourceFile(sourceFileId) && countPagesForSourceFile(sourceFileId) > 0;

  let discardPageResult = null;
  if (shouldPersistSourcePageRemoval) {
    try {
      discardPageResult = await discardImportInboxSourcePages(sourceFileId, [sourcePageIndex]);
    } catch (error) {
      notify({ type: 'warning', message: mapApiError(error, 'Gelöschte SMB-Seite konnte nicht endgültig gelöscht werden.') });
      return;
    }
  }

  stagingStore.removePage(pageId);
  if (shouldPersistSourcePageRemoval) {
    stagingStore.remapSourcePagesAfterRemoval(sourceFileId, [sourcePageIndex], discardPageResult?.page_count);
    await refreshImportInboxSourceFile(sourceFileId, discardPageResult?.page_count);
  }
  if (selected.value?.pageId === pageId) {
    clearActiveSelection();
  }
  notifyDiscardedSourceFileIds([sourceFileId]);
}

async function removeSelectedPage(documentId) {
  const selectedPage = resolveSelectedPage(documentId);
  if (!selectedPage) {
    return;
  }
  await removePage(selectedPage.id);
}

function deleteDocument(documentId) {
  const sourceFileIds = collectDocumentSourceFileIds(documentId);
  stagingStore.deleteDocument(documentId);
  if (selected.value?.stageId === documentId) {
    clearActiveSelection();
  }
  notifyDiscardedSourceFileIds(sourceFileIds);
}

function setPageThumbRef(pageId, element) {
  if (!element) {
    pageThumbRefs.delete(pageId);
    return;
  }
  pageThumbRefs.set(pageId, element);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getSelectedAnchorEl() {
  const pageId = String(selected.value?.pageId || '').trim();
  if (!pageId) {
    return null;
  }
  const element = pageThumbRefs.get(pageId);
  return element instanceof HTMLElement ? element : null;
}

function updatePeekPosition(anchorElement) {
  if (!peek.value.open || typeof window === 'undefined') {
    return;
  }
  const anchor = anchorElement instanceof HTMLElement ? anchorElement : getSelectedAnchorEl();
  if (!anchor) {
    return;
  }
  peekAnchorEl.value = anchor;

  const viewportPadding = 12;
  const rect = anchor.getBoundingClientRect();
  const panelRect = peekPanelRef.value?.getBoundingClientRect?.();
  const maxPanelWidth = Math.max(320, window.innerWidth - viewportPadding * 2);
  const panelWidth = Math.min(panelRect?.width || 520, maxPanelWidth);
  const maxPanelHeight = Math.max(260, window.innerHeight - viewportPadding * 2);
  const panelHeight = Math.min(panelRect?.height || Math.round(window.innerHeight * 0.7), maxPanelHeight);
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const preferredRightX = rect.right + 12;
  const preferredLeftX = rect.left - panelWidth - 12;

  let x = preferredRightX;
  if (preferredRightX + panelWidth > viewportWidth - viewportPadding) {
    if (preferredLeftX >= viewportPadding) {
      x = preferredLeftX;
    } else {
      x = clamp(rect.left + rect.width / 2 - panelWidth / 2, viewportPadding, viewportWidth - panelWidth - viewportPadding);
    }
  }

  const y = clamp(rect.top + rect.height / 2 - panelHeight / 2, viewportPadding, viewportHeight - panelHeight - viewportPadding);
  peek.value = {
    ...peek.value,
    x,
    y
  };
}

function schedulePeekReposition(anchorElement) {
  if (!peek.value.open || typeof window === 'undefined') {
    return;
  }
  if (peekRepositionRaf) {
    return;
  }
  peekRepositionRaf = window.requestAnimationFrame(() => {
    peekRepositionRaf = 0;
    updatePeekPosition(anchorElement);
  });
}

function openPeek(anchorElement) {
  peek.value = {
    ...peek.value,
    open: true
  };
  nextTick(() => {
    updatePeekPosition(anchorElement);
  });
}

function closePeek() {
  peek.value = {
    ...peek.value,
    open: false
  };
}

function clearActiveSelection() {
  selected.value = null;
  clearMultiSelection();
  closePeek();
  peekAnchorEl.value = null;
}

function selectPage(documentId, pageId, pageIndex, options = {}) {
  const normalizedDocId = String(documentId || '').trim();
  const normalizedPageId = String(pageId || '').trim();
  if (!normalizedDocId || !normalizedPageId) {
    return false;
  }
  selected.value = {
    stageId: normalizedDocId,
    pageId: normalizedPageId,
    pageIndex: Number.isInteger(pageIndex) ? pageIndex : Math.max(0, Number(pageIndex) || 0)
  };
  if (options.anchorEl instanceof HTMLElement) {
    peekAnchorEl.value = options.anchorEl;
  }
  return true;
}

function onPageClick(event, documentId, pageId, pageIndex) {
  const anchorEl = event?.currentTarget instanceof HTMLElement ? event.currentTarget : getSelectedAnchorEl();
  selectPage(documentId, pageId, pageIndex, { anchorEl });
  closePeek();
}

function onPageDoubleClick(event, documentId, pageId, pageIndex) {
  const anchorEl = event?.currentTarget instanceof HTMLElement ? event.currentTarget : getSelectedAnchorEl();
  const didSelect = selectPage(documentId, pageId, pageIndex, { anchorEl });
  if (!didSelect) {
    return;
  }
  openPeek(anchorEl);
}

function resolveSelectedPage(documentId) {
  if (selected.value?.stageId !== documentId) {
    return null;
  }
  const documentEntry = documents.value.find((entry) => entry.id === documentId);
  if (!documentEntry) {
    return null;
  }
  return documentEntry.pages.find((page) => page.id === selected.value?.pageId) || null;
}

function hasSelectedPage(documentId) {
  return Boolean(resolveSelectedPage(documentId));
}

function resolveSplitTargetPage(documentId) {
  const documentEntry = documents.value.find((entry) => entry.id === documentId);
  if (!documentEntry || documentEntry.pages.length <= 1) {
    return null;
  }
  const selectedPage = resolveSelectedPage(documentId);
  if (selectedPage) {
    return selectedPage;
  }
  return null;
}

function canSplitPage(documentId) {
  return Boolean(resolveSplitTargetPage(documentId));
}

function isPageSelected(documentId, pageId) {
  return (
    selected.value?.stageId === String(documentId || '').trim() &&
    selected.value?.pageId === String(pageId || '').trim()
  );
}

function isDraggingPage(pageId) {
  return pageDragState.value.active && pageDragState.value.pageId === String(pageId || '');
}

function isDropHoverPage(documentId, pageId) {
  return (
    pageDragState.value.active &&
    pageDragState.value.overDocId === String(documentId || '') &&
    pageDragState.value.hoverPageId === String(pageId || '')
  );
}

function isPageDropMarkerVisible(documentId) {
  return (
    pageDragState.value.active &&
    pageDropMarker.value.docId === String(documentId || '') &&
    pageDropMarker.value.index >= 0
  );
}

function isSettledPage(pageId) {
  return settledPageId.value === String(pageId || '');
}

function rotateSelectedPage(documentId, delta) {
  const selectedPage = resolveSelectedPage(documentId);
  if (!selectedPage) {
    return;
  }
  stagingStore.rotatePage(selectedPage.id, Number(delta) < 0 ? 'left' : 'right');
}

async function splitSelectedPage(documentId) {
  const targetPage = resolveSplitTargetPage(documentId);
  if (!targetPage) {
    return;
  }

  const created = stagingStore.splitPageToNewDocument(targetPage.id);
  const createdPage = created?.pages?.[0] || null;
  if (!created || !createdPage) {
    return;
  }

  await nextTick();
  const anchorEl = pageThumbRefs.get(createdPage.id) || null;
  selectPage(created.id, createdPage.id, 0, { anchorEl });
  closePeek();
}

function onDocumentCollapseToggle(documentId) {
  const documentEntry = documents.value.find((entry) => entry.id === documentId);
  const willCollapse = Boolean(documentEntry && !documentEntry.collapsed);
  stagingStore.toggleDocumentCollapsed(documentId);
  if (willCollapse && selected.value?.stageId === documentId) {
    clearActiveSelection();
  }
}

function onStageBodyBeforeEnter(element) {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.style.height = '0px';
  element.style.opacity = '0';
  element.style.overflow = 'hidden';
}

function onStageBodyEnter(element, done) {
  if (!(element instanceof HTMLElement)) {
    done();
    return;
  }
  const targetHeight = element.scrollHeight;
  const onTransitionEnd = (event) => {
    if (event.target !== element || event.propertyName !== 'height') {
      return;
    }
    element.removeEventListener('transitionend', onTransitionEnd);
    done();
  };
  element.addEventListener('transitionend', onTransitionEnd);
  requestAnimationFrame(() => {
    element.style.height = `${targetHeight}px`;
    element.style.opacity = '1';
  });
}

function onStageBodyAfterEnter(element) {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.style.height = 'auto';
  element.style.opacity = '1';
  element.style.overflow = '';
  scheduleBodyContentLayoutStateUpdate();
}

function onStageBodyBeforeLeave(element) {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.style.height = `${element.scrollHeight}px`;
  element.style.opacity = '1';
  element.style.overflow = 'hidden';
}

function onStageBodyLeave(element, done) {
  if (!(element instanceof HTMLElement)) {
    done();
    return;
  }
  const onTransitionEnd = (event) => {
    if (event.target !== element || event.propertyName !== 'height') {
      return;
    }
    element.removeEventListener('transitionend', onTransitionEnd);
    done();
  };
  element.addEventListener('transitionend', onTransitionEnd);
  requestAnimationFrame(() => {
    element.style.height = '0px';
    element.style.opacity = '0';
  });
}

function onStageBodyAfterLeave(element) {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.style.height = '';
  element.style.opacity = '';
  element.style.overflow = '';
  scheduleBodyContentLayoutStateUpdate();
}

function shiftSelection(step) {
  const documentEntry = selectedDocumentEntry.value;
  const pageEntry = selectedPageEntry.value;
  if (!documentEntry || !pageEntry) {
    return;
  }
  const currentIndex = documentEntry.pages.findIndex((page) => page.id === pageEntry.id);
  if (currentIndex < 0) {
    return;
  }
  const nextIndex = Math.max(0, Math.min(documentEntry.pages.length - 1, currentIndex + step));
  if (nextIndex === currentIndex) {
    return;
  }
  const nextPage = documentEntry.pages[nextIndex];
  if (!nextPage) {
    return;
  }
  selectPage(documentEntry.id, nextPage.id, nextIndex, { anchorEl: pageThumbRefs.get(nextPage.id) || null });
}

function onGlobalPointerDown(event) {
  if (!peek.value.open) {
    return;
  }
  const target = event.target;
  if (!(target instanceof Node)) {
    return;
  }
  const panel = peekPanelRef.value;
  const anchor = getSelectedAnchorEl();
  if (panel?.contains(target) || anchor?.contains(target)) {
    return;
  }
  closePeek();
}

function onGlobalViewportChange() {
  schedulePeekReposition();
}

function onGlobalKeydown(event) {
  if (!isOpen.value) {
    return;
  }
  if (isEditableShortcutTarget(event.target) && !handleShortcut(event, SHORTCUT_ACTIONS.CANCEL, null, {
    prevent: false,
    ignoreEditable: false
  })) {
    return;
  }
  if (handleShortcut(event, SHORTCUT_ACTIONS.CANCEL, null, { prevent: false, ignoreEditable: false })) {
    if (peek.value.open) {
      closePeek();
      event.preventDefault();
    }
    return;
  }
  if (!isImportActionDisabled.value && handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, commitImport, {
    ignoreEditable: false
  })) {
    return;
  }
  if (!hasSelectedPreview.value) {
    return;
  }
  if (handleShortcut(event, SHORTCUT_ACTIONS.MOVE_NEXT, () => shiftSelection(1), { ignoreEditable: false })) {
    return;
  }
  handleShortcut(event, SHORTCUT_ACTIONS.MOVE_PREVIOUS, () => shiftSelection(-1), { ignoreEditable: false });
}

useShortcutScope(onGlobalKeydown, { enabled: isOpen });

const DRAG_MIME = 'application/x-papermind-staging';

function writeDragPayload(event, payload) {
  if (!event.dataTransfer) {
    return;
  }
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData(DRAG_MIME, JSON.stringify(payload));
  event.dataTransfer.setData('text/plain', JSON.stringify(payload));
}

function readDragPayload(event) {
  const raw = event.dataTransfer?.getData(DRAG_MIME) || event.dataTransfer?.getData('text/plain');
  if (!raw) {
    return null;
  }
  try {
    const payload = JSON.parse(raw);
    if (!payload || typeof payload !== 'object') {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function onDocumentDragStart(event, documentId) {
  writeDragPayload(event, { type: 'document', documentId });
}

function clearSettledPage() {
  if (settlePageTimer) {
    clearTimeout(settlePageTimer);
    settlePageTimer = 0;
  }
  settledPageId.value = '';
}

function markSettledPage(pageId) {
  clearSettledPage();
  settledPageId.value = String(pageId || '');
  settlePageTimer = window.setTimeout(() => {
    settledPageId.value = '';
    settlePageTimer = 0;
  }, 180);
}

function resetPageDragState() {
  pageDragState.value = {
    active: false,
    pageId: '',
    sourceDocId: '',
    sourceIndex: -1,
    overDocId: '',
    dropIndex: -1,
    hoverPageId: ''
  };
  pageDropMarker.value = {
    docId: '',
    index: -1,
    left: 0,
    top: 0,
    height: 0
  };
}

function clearPageDropMarker() {
  pageDropMarker.value = {
    docId: '',
    index: -1,
    left: 0,
    top: 0,
    height: 0
  };
  pageDragState.value = {
    ...pageDragState.value,
    overDocId: '',
    dropIndex: -1,
    hoverPageId: ''
  };
}

function runAutoScroll() {
  if (!autoScrollState.container) {
    autoScrollRaf = 0;
    return;
  }
  autoScrollState.container.scrollBy(autoScrollState.dx, autoScrollState.dy);
  if (autoScrollState.dx === 0 && autoScrollState.dy === 0) {
    autoScrollRaf = 0;
    return;
  }
  autoScrollRaf = window.requestAnimationFrame(runAutoScroll);
}

function stopAutoScroll() {
  if (typeof window !== 'undefined' && autoScrollRaf) {
    window.cancelAnimationFrame(autoScrollRaf);
  }
  autoScrollRaf = 0;
  autoScrollState.container = null;
  autoScrollState.dx = 0;
  autoScrollState.dy = 0;
}

function updateAutoScroll(container, clientX, clientY) {
  if (!(container instanceof HTMLElement) || typeof window === 'undefined') {
    stopAutoScroll();
    return;
  }
  const threshold = 44;
  const maxSpeed = 16;
  const rect = container.getBoundingClientRect();
  const horizontalLeft = rect.left + threshold - clientX;
  const horizontalRight = clientX - (rect.right - threshold);
  const verticalTop = rect.top + threshold - clientY;
  const verticalBottom = clientY - (rect.bottom - threshold);
  const dx =
    horizontalLeft > 0
      ? -Math.ceil((Math.min(threshold, horizontalLeft) / threshold) * maxSpeed)
      : horizontalRight > 0
      ? Math.ceil((Math.min(threshold, horizontalRight) / threshold) * maxSpeed)
      : 0;
  const dy =
    verticalTop > 0
      ? -Math.ceil((Math.min(threshold, verticalTop) / threshold) * maxSpeed)
      : verticalBottom > 0
      ? Math.ceil((Math.min(threshold, verticalBottom) / threshold) * maxSpeed)
      : 0;

  autoScrollState.container = container;
  autoScrollState.dx = dx;
  autoScrollState.dy = dy;

  if (!autoScrollRaf && (dx !== 0 || dy !== 0)) {
    autoScrollRaf = window.requestAnimationFrame(runAutoScroll);
  }
  if (dx === 0 && dy === 0) {
    stopAutoScroll();
  }
}

function resolveAutoScrollContainer(startElement) {
  const pagesContainer = startElement?.closest?.('.import-staging-pages');
  if (
    pagesContainer instanceof HTMLElement &&
    (pagesContainer.scrollWidth > pagesContainer.clientWidth + 1 ||
      pagesContainer.scrollHeight > pagesContainer.clientHeight + 1)
  ) {
    return pagesContainer;
  }
  const docsContainer = startElement?.closest?.('.import-staging-scroll');
  if (docsContainer instanceof HTMLElement) {
    return docsContainer;
  }
  return null;
}

function createDragGhost(pageElement, pageOrder) {
  if (!(pageElement instanceof HTMLElement) || typeof document === 'undefined') {
    return null;
  }
  const rect = pageElement.getBoundingClientRect();
  const thumbElement = pageElement.querySelector('.import-staging-page__thumb');
  const ghost = document.createElement('div');
  ghost.style.position = 'fixed';
  ghost.style.left = '-10000px';
  ghost.style.top = '-10000px';
  ghost.style.width = `${Math.round(rect.width)}px`;
  ghost.style.height = `${Math.round(rect.height)}px`;
  ghost.style.borderRadius = '12px';
  ghost.style.overflow = 'hidden';
  ghost.style.background = 'rgba(40, 44, 55, 0.95)';
  ghost.style.border = '1px solid rgba(255,255,255,0.10)';
  ghost.style.boxShadow = '0 8px 24px rgba(15,23,42,0.18), 0 2px 6px rgba(15,23,42,0.10)';
  ghost.style.pointerEvents = 'none';
  ghost.style.display = 'flex';
  ghost.style.alignItems = 'center';
  ghost.style.justifyContent = 'center';
  ghost.style.padding = '6px';

  if (thumbElement instanceof HTMLImageElement && thumbElement.src) {
    const image = document.createElement('img');
    image.src = thumbElement.src;
    image.style.width = '100%';
    image.style.height = '100%';
    image.style.objectFit = 'contain';
    image.style.transform = thumbElement.style.transform || 'none';
    ghost.append(image);
  }

  const badge = document.createElement('span');
  badge.textContent = String(pageOrder);
  badge.style.position = 'absolute';
  badge.style.left = '8px';
  badge.style.bottom = '8px';
  badge.style.minWidth = '20px';
  badge.style.height = '20px';
  badge.style.borderRadius = '999px';
  badge.style.background = 'rgba(10,14,24,0.85)';
  badge.style.color = 'rgba(255,255,255,0.96)';
  badge.style.fontSize = '12px';
  badge.style.fontWeight = '600';
  badge.style.lineHeight = '20px';
  badge.style.textAlign = 'center';
  badge.style.padding = '0 6px';
  ghost.append(badge);

  document.body.append(ghost);
  return ghost;
}

function updatePageDropTarget(targetDocId, targetPageId, targetIndex, lineRect, containerRect) {
  pageDragState.value = {
    ...pageDragState.value,
    overDocId: String(targetDocId || ''),
    dropIndex: Math.max(0, Number(targetIndex) || 0),
    hoverPageId: String(targetPageId || '')
  };

  pageDropMarker.value = {
    docId: String(targetDocId || ''),
    index: Math.max(0, Number(targetIndex) || 0),
    left: Math.max(0, (lineRect?.left || 0) - (containerRect?.left || 0)),
    top: Math.max(0, (lineRect?.top || 0) - (containerRect?.top || 0) + 6),
    height: Math.max(14, Number(lineRect?.height || 0) - 12)
  };
}

function onPageDragStart(event, documentId, pageId, pageIndex) {
  writeDragPayload(event, { type: 'page', documentId, pageId });
  pageDragState.value = {
    active: true,
    pageId: String(pageId || ''),
    sourceDocId: String(documentId || ''),
    sourceIndex: Number.isInteger(pageIndex) ? pageIndex : Math.max(0, Number(pageIndex) || 0),
    overDocId: String(documentId || ''),
    dropIndex: Number.isInteger(pageIndex) ? pageIndex : Math.max(0, Number(pageIndex) || 0),
    hoverPageId: String(pageId || '')
  };

  if (!event.dataTransfer) {
    return;
  }
  event.dataTransfer.effectAllowed = 'move';
  const pageElement = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  if (!pageElement) {
    return;
  }
  const ghost = createDragGhost(pageElement, (Number(pageIndex) || 0) + 1);
  if (!ghost) {
    return;
  }
  event.dataTransfer.setDragImage(ghost, Math.round(pageElement.clientWidth * 0.42), Math.round(pageElement.clientHeight * 0.38));
  window.setTimeout(() => {
    ghost.remove();
  }, 0);
}

function onPageDragEnd() {
  stopAutoScroll();
  resetPageDragState();
}

function setDocumentDragDepth(documentId, nextDepth) {
  const nextValue = Math.max(0, Number(nextDepth || 0));
  documentDragDepth.value = {
    ...documentDragDepth.value,
    [documentId]: nextValue
  };
}

function clearDocumentDragDepth(documentId) {
  if (!(documentId in documentDragDepth.value)) {
    return;
  }
  const nextState = { ...documentDragDepth.value };
  delete nextState[documentId];
  documentDragDepth.value = nextState;
}

function isDocumentDragActive(documentId) {
  return Number(documentDragDepth.value[documentId] || 0) > 0;
}

function onInterDropDragOver(event) {
  event.dataTransfer.dropEffect = hasFileDragPayload(event) ? 'copy' : 'move';
  if (!hasFileDragPayload(event) && pageDragState.value.active) {
    clearPageDropMarker();
  }
}

function onDocsContainerDragOver(event) {
  if (hasFileDragPayload(event)) {
    event.dataTransfer.dropEffect = 'copy';
    return;
  }
  event.dataTransfer.dropEffect = 'move';
  if (pageDragState.value.active) {
    clearPageDropMarker();
  }
}

async function onDocsContainerDrop(event) {
  if (hasFileDragPayload(event)) {
    return;
  }
  await onInterDocumentDrop(event, documents.value.length);
}

function onDocumentDragEnter(event, documentId) {
  if (!event.dataTransfer) {
    return;
  }
  event.stopPropagation();
  setDocumentDragDepth(documentId, Number(documentDragDepth.value[documentId] || 0) + 1);
}

function onDocumentBodyDragOver(event, documentId) {
  event.stopPropagation();
  event.dataTransfer.dropEffect = hasFileDragPayload(event) ? 'copy' : 'move';
  if (!hasFileDragPayload(event)) {
    updateAutoScroll(resolveAutoScrollContainer(event.currentTarget), event.clientX, event.clientY);
  }
  if (!isDocumentDragActive(documentId)) {
    setDocumentDragDepth(documentId, 1);
  }
}

function onDocumentDragLeave(event, documentId) {
  if (!event.dataTransfer) {
    return;
  }
  event.stopPropagation();
  const nextDepth = Number(documentDragDepth.value[documentId] || 0) - 1;
  if (nextDepth <= 0) {
    clearDocumentDragDepth(documentId);
    if (pageDragState.value.active && pageDropMarker.value.docId === documentId) {
      clearPageDropMarker();
    }
    return;
  }
  setDocumentDragDepth(documentId, nextDepth);
}

async function onInterDocumentDrop(event, targetIndex) {
  event.stopPropagation();
  stopAutoScroll();

  if (hasFileDragPayload(event)) {
    try {
      const targetDocumentId =
        documents.value[targetIndex]?.id ||
        documents.value[Math.max(0, targetIndex - 1)]?.id ||
        null;
      if (!targetDocumentId) {
        await addNewDocumentsFromTransfer(event.dataTransfer, { insertIndex: targetIndex });
        return;
      }
      const candidates = await collectDropCandidates(event.dataTransfer);
      await addFilesToStaging(candidates, {
        targetDocumentId,
        showSelectionSummary: false
      });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
    }
    return;
  }

  const payload = readDragPayload(event);
  if (!payload) {
    const draggedPageId = resolveDraggedPageId(event);
    if (draggedPageId) {
      stagingStore.movePageToNewDocument(draggedPageId, targetIndex, 'Neues Dokument');
      markSettledPage(draggedPageId);
      resetPageDragState();
    }
    return;
  }

  if (payload.type === 'document' && payload.documentId) {
    stagingStore.moveDocument(payload.documentId, targetIndex);
    resetPageDragState();
    return;
  }

  if (payload.type === 'page' && payload.pageId) {
    stagingStore.movePageToNewDocument(payload.pageId, targetIndex, 'Neues Dokument');
    markSettledPage(payload.pageId);
    resetPageDragState();
  }
}

async function onDocumentBodyDrop(event, targetDocId) {
  event.stopPropagation();
  stopAutoScroll();
  clearDocumentDragDepth(targetDocId);

  if (hasFileDragPayload(event)) {
    try {
      const candidates = await collectDropCandidates(event.dataTransfer);
      await addFilesToStaging(candidates, {
        targetDocumentId: targetDocId,
        showSelectionSummary: false
      });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
    }
    return;
  }

  const payload = readDragPayload(event);
  const draggedPageId =
    payload?.type === 'page' && payload?.pageId
      ? String(payload.pageId)
      : resolveDraggedPageId(event);
  if (!draggedPageId) {
    return;
  }

  stagingStore.movePage(draggedPageId, targetDocId, null);
  markSettledPage(draggedPageId);
  resetPageDragState();
}

function readPagePayload(event) {
  const payload = readDragPayload(event);
  if (!payload || payload.type !== 'page' || !payload.pageId) {
    return null;
  }
  return payload;
}

function resolveDraggedPageId(event) {
  const payload = readPagePayload(event);
  if (payload?.pageId) {
    return String(payload.pageId);
  }
  if (pageDragState.value.active && pageDragState.value.pageId) {
    return String(pageDragState.value.pageId);
  }
  return '';
}

function findNearestPageElement(containerEl, clientX, clientY) {
  if (!(containerEl instanceof HTMLElement)) {
    return null;
  }
  const candidates = Array.from(containerEl.querySelectorAll('.import-staging-page'));
  if (candidates.length === 0) {
    return null;
  }
  let best = null;
  for (const element of candidates) {
    const rect = element.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const distance = Math.hypot(clientX - centerX, (clientY - centerY) * 1.18);
    if (!best || distance < best.distance) {
      best = { element, rect, distance };
    }
  }
  return best;
}

function updatePageDropTargetFromElement(event, targetDocId, targetPageId, targetPageIndex, targetEl) {
  if (!(targetEl instanceof HTMLElement)) {
    return;
  }
  const itemRect = targetEl.getBoundingClientRect();
  const containerEl = targetEl.closest('.import-staging-pages');
  const containerRect = containerEl?.getBoundingClientRect?.();
  if (!containerRect) {
    return;
  }
  const before = event.clientX < itemRect.left + itemRect.width / 2;
  const insertionIndex = before ? targetPageIndex : targetPageIndex + 1;
  const lineRect = {
    left: before ? itemRect.left : itemRect.right,
    top: itemRect.top,
    height: itemRect.height
  };
  updatePageDropTarget(targetDocId, targetPageId, insertionIndex, lineRect, containerRect);
}

function updatePageDropTargetFromContainer(event, targetDocId) {
  const containerEl = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  if (!containerEl) {
    return;
  }
  const nearest = findNearestPageElement(containerEl, event.clientX, event.clientY);
  if (!nearest) {
    return;
  }
  const nearestIndex = Number(nearest.element.dataset.pageIndex || 0);
  const nearestPageId = String(nearest.element.dataset.pageId || '');
  updatePageDropTargetFromElement(event, targetDocId, nearestPageId, nearestIndex, nearest.element);
}

function getResolvedDropIndex(targetDocId, fallbackIndex) {
  if (
    pageDragState.value.active &&
    pageDragState.value.overDocId === String(targetDocId || '') &&
    pageDragState.value.dropIndex >= 0
  ) {
    return pageDragState.value.dropIndex;
  }
  return fallbackIndex;
}

function onPageDragOver(event, targetDocId, targetPageId, targetPageIndex) {
  event.stopPropagation();
  const isFileDrop = hasFileDragPayload(event);
  event.dataTransfer.dropEffect = isFileDrop ? 'copy' : 'move';
  updateAutoScroll(resolveAutoScrollContainer(event.currentTarget), event.clientX, event.clientY);
  if (isFileDrop) {
    isAddPageDragOver.value = true;
    return;
  }
  const draggedPageId = resolveDraggedPageId(event);
  if (!draggedPageId) {
    return;
  }
  updatePageDropTargetFromElement(event, targetDocId, targetPageId, targetPageIndex, event.currentTarget);
}

async function onPageDrop(event, targetDocId, targetPageIndex) {
  event.stopPropagation();
  stopAutoScroll();
  clearDocumentDragDepth(targetDocId);
  isAddPageDragOver.value = false;
  addPageDragDepth.value = 0;

  if (hasFileDragPayload(event)) {
    try {
      const candidates = await collectDropCandidates(event.dataTransfer);
      await addFilesToStaging(candidates, {
        targetDocumentId: targetDocId,
        showSelectionSummary: false
      });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
    }
    return;
  }

  const draggedPageId = resolveDraggedPageId(event);
  if (!draggedPageId) {
    return;
  }

  const insertionIndex = getResolvedDropIndex(targetDocId, targetPageIndex);
  stagingStore.movePage(draggedPageId, targetDocId, insertionIndex);
  markSettledPage(draggedPageId);
  resetPageDragState();
}

function onPagesContainerDragOver(event, targetDocId) {
  event.stopPropagation();
  const isFileDrop = hasFileDragPayload(event);
  event.dataTransfer.dropEffect = isFileDrop ? 'copy' : 'move';
  updateAutoScroll(resolveAutoScrollContainer(event.currentTarget), event.clientX, event.clientY);
  if (isFileDrop) {
    isAddPageDragOver.value = true;
    return;
  }
  const draggedPageId = resolveDraggedPageId(event);
  if (!draggedPageId) {
    return;
  }
  updatePageDropTargetFromContainer(event, targetDocId);
}

async function onPagesContainerDrop(event, targetDocId) {
  event.stopPropagation();
  stopAutoScroll();
  clearDocumentDragDepth(targetDocId);
  isAddPageDragOver.value = false;
  addPageDragDepth.value = 0;

  if (hasFileDragPayload(event)) {
    try {
      const candidates = await collectDropCandidates(event.dataTransfer);
      await addFilesToStaging(candidates, {
        targetDocumentId: targetDocId,
        showSelectionSummary: false
      });
    } catch (error) {
      notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
    }
    return;
  }

  const draggedPageId = resolveDraggedPageId(event);
  if (!draggedPageId) {
    return;
  }
  const targetDoc = documents.value.find((entry) => entry.id === targetDocId);
  const fallbackIndex = targetDoc?.pages?.length ?? 0;
  const insertionIndex = getResolvedDropIndex(targetDocId, fallbackIndex);
  stagingStore.movePage(draggedPageId, targetDocId, insertionIndex);
  markSettledPage(draggedPageId);
  resetPageDragState();
}

function onBodyShellDragEnter(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.stopPropagation();
  bodyFileDragDepth.value += 1;
  isBodyFileDragOver.value = true;
}

function onBodyShellDragOver(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.stopPropagation();
  event.dataTransfer.dropEffect = 'copy';
  isBodyFileDragOver.value = true;
}

function onBodyShellDragLeave(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.stopPropagation();
  bodyFileDragDepth.value = Math.max(0, bodyFileDragDepth.value - 1);
  if (bodyFileDragDepth.value === 0) {
    isBodyFileDragOver.value = false;
  }
}

async function onBodyShellDrop(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.stopPropagation();
  isBodyFileDragOver.value = false;
  bodyFileDragDepth.value = 0;
  try {
    await addNewDocumentsFromTransfer(event.dataTransfer, { insertIndex: documents.value.length });
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
  }
}

function onListSurfaceDragOver(event) {
  event.dataTransfer.dropEffect = hasFileDragPayload(event) ? 'copy' : 'move';
}

async function onListSurfaceDrop(event) {
  event.stopPropagation();
  isBodyFileDragOver.value = false;
  bodyFileDragDepth.value = 0;
  if (!hasFileDragPayload(event)) {
    return;
  }

  try {
    await addNewDocumentsFromTransfer(event.dataTransfer, { insertIndex: documents.value.length });
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
  }
}

function onModalSurfaceDragOver(event) {
  event.dataTransfer.dropEffect = hasFileDragPayload(event) ? 'copy' : 'move';
}

async function onModalSurfaceDrop(event) {
  isBodyFileDragOver.value = false;
  bodyFileDragDepth.value = 0;
  if (!hasFileDragPayload(event)) {
    return;
  }
  try {
    await addNewDocumentsFromTransfer(event.dataTransfer, { insertIndex: documents.value.length });
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'PDFs konnten nicht hinzugefügt werden.') });
  }
}

async function commitImport() {
  if (isImportActionDisabled.value) {
    return;
  }

  isCommitting.value = true;
  try {
    const response = await fetch(`${props.apiBaseUrl}/api/import/commit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        documents: commitDocuments.value.map((doc, idx) =>
          idx === 0
            ? { ...doc, category: docCategory.value || null, note: docNote.value.trim() || null, date: docDateIso.value || null }
            : doc
        ),
        options: {
          auto_ocr: Boolean(settingsStore.settings.documents.auto_ocr),
          auto_index: Boolean(settingsStore.settings.documents.auto_tagging && settingsStore.settings.documents.auto_ocr),
          auto_embed: Boolean(props.autoEmbed)
        }
      })
    });

    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const payload = await response.json();
    const createdCount = Array.isArray(payload?.created) ? payload.created.length : 0;
    const errorCount = Array.isArray(payload?.errors) ? payload.errors.length : 0;

    if (createdCount > 0) {
      emit('committed', payload);
    }

    if (createdCount > 0 && errorCount === 0) {
      notify({
        type: 'success',
        message: `Import gestartet (${createdCount} Dokumente). OCR läuft im Hintergrund.`
      });
      isOpen.value = false;
      return;
    }

    if (createdCount > 0 && errorCount > 0) {
      notify({
        type: 'warning',
        message: `Teilweise importiert: ${createdCount} erfolgreich, ${errorCount} fehlgeschlagen.`
      });
      return;
    }

    if (errorCount > 0) {
      const firstMessage = String(payload.errors[0]?.message || 'Import fehlgeschlagen.');
      notify({ type: 'error', message: firstMessage });
      return;
    }

    notify({ type: 'warning', message: 'Keine Dokumente importiert.' });
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Import fehlgeschlagen.') });
  } finally {
    isCommitting.value = false;
  }
}

async function openWithFiles(files) {
  const candidates = Array.from(files || []).map((file) => ({ file, relativePath: '' }));
  if (candidates.length <= 0) {
    return;
  }

  try {
    await addFilesToStaging(candidates);
    isOpen.value = true;
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Import-Quellen konnten nicht hochgeladen werden.') });
  }
}

async function openWithRemoteSources(payload = {}) {
  isOpen.value = true;
  await nextTick();
  await addRemoteSources(payload);
}

function openDialog() {
  isOpen.value = true;
}

defineExpose({
  openDialog,
  openWithFiles,
  openWithRemoteSources
});

onBeforeUnmount(() => {
  if (typeof window !== 'undefined' && closeResetTimer) {
    window.clearTimeout(closeResetTimer);
    closeResetTimer = 0;
  }
  if (typeof window !== 'undefined' && viewSwitchTimer) {
    window.clearTimeout(viewSwitchTimer);
    viewSwitchTimer = 0;
  }
  teardownBodyLayoutObserver();
  if (typeof window !== 'undefined' && bodyLayoutRaf) {
    window.cancelAnimationFrame(bodyLayoutRaf);
    bodyLayoutRaf = 0;
  }
  clearSettledPage();
  stopAutoScroll();
  resetPageDragState();
  if (typeof window !== 'undefined') {
    detachPeekGlobalListeners();
    if (peekRepositionRaf) {
      window.cancelAnimationFrame(peekRepositionRaf);
      peekRepositionRaf = 0;
    }
  }
  pageThumbRefs.clear();
  previewImageCache.clear();
  stagingStore.reset();
});
</script>

<style>
/*
 * Unscoped — v-dialog teleportiert seinen Inhalt zu <body>, daher sind
 * :deep()-Selektoren wirkungslos. Namespace .isd-card.pm-dialog ist
 * eindeutig genug, um andere Dialoge nicht zu beeinflussen.
 */

.isd-card.pm-dialog {
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
  height: min(820px, 90vh) !important;
  min-height: min(820px, 90vh) !important;
  max-height: min(820px, 90vh) !important;
}

.isd-card.pm-dialog .pm-dialog__header {
  flex: 0 0 auto;
}

.isd-card.pm-dialog .pm-dialog__content-wrap {
  flex: 1 1 auto !important;
  min-height: 0 !important;
  max-height: none !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
}

.isd-card.pm-dialog .pm-dialog__content {
  padding: 0 !important;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.isd-card.pm-dialog .pm-dialog__footer {
  flex: 0 0 auto;
  padding: 12px 18px !important;
  justify-content: space-between !important;
}
</style>

<style scoped>
/* ── Body split layout ── */
.isd-body {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  /* Gemeinsame, feste Höhe für Toolbar (links) und Statusleiste (rechts), damit
   * ihre border-top-Linien exakt fluchten. Bei box-sizing:border-box ist die
   * linke Toolbar tatsächlich 49px hoch: 32px Icon-Button (x-small + default
   * density) + 2×8px Padding + 1px border-top. Die rechte Leiste übernimmt
   * exakt denselben Wert. */
  --isd-bar-height: 49px;
}

.isd-progress {
  flex: 0 0 auto;
}

.isd-left {
  flex: 0 0 65%;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  border-right: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
}

.isd-grid-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 40px;
}


/* ── Dropzone ── */
@keyframes isd-bounce {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(5px); }
}

.isd-dropzone {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 32px;
  text-align: center;
  border: 2px dashed rgb(var(--v-theme-primary));
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
  box-sizing: border-box;
  /* 1 — Schraffur */
  background-image:
    repeating-linear-gradient(
      -45deg,
      rgba(var(--v-theme-primary), 0.025) 0px,
      rgba(var(--v-theme-primary), 0.025) 1px,
      transparent 1px,
      transparent 10px
    );
  background-color: rgba(var(--v-theme-primary), 0.03);
}

.isd-dropzone--over {
  background-color: rgba(var(--v-theme-primary), 0.08);
}

/* 2 — Icon-Animation */
.isd-dropzone__icon {
  color: rgb(var(--v-theme-primary));
  margin-bottom: 18px;
}

.isd-dropzone__icon-svg {
  animation: isd-bounce 2.2s ease-in-out infinite;
}

.isd-dropzone__text {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 4 — Titel stärker */
.isd-dropzone__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
  color: rgb(var(--v-theme-on-surface));
}

.isd-dropzone__subtitle {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.isd-dropzone__types {
  display: flex;
  gap: 6px;
  margin-top: 22px;
}

/* 6 — Chip mit Icon */
.isd-dropzone__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 3px 10px 3px 7px;
  border-radius: 20px;
  border: 1px solid rgba(var(--v-theme-primary), 0.35);
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.06);
}

.isd-dropzone__chip-icon {
  opacity: 0.8;
}

/* ── Page grid ── */
.isd-page-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--pm-grid-min, 164px), 1fr));
  gap: 16px;
  margin-bottom: 10px;
}

/* ── Page card ── */
.isd-page-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: grab;
  border-radius: 5px;
  padding: 0;
  transition: background 0.12s, opacity 0.15s;
}

.isd-page-card:hover .isd-page-thumb-wrap {
  border-color: rgba(var(--v-theme-on-surface), 0.2);
}

.isd-page-card--dragging {
  opacity: 0.35;
  cursor: grabbing;
}

.isd-page-card--drop-before .isd-page-thumb-wrap {
  border-left: 3px solid rgb(var(--v-theme-primary));
}

.isd-page-card--drop-after .isd-page-thumb-wrap {
  border-right: 3px solid rgb(var(--v-theme-primary));
}

.isd-page-card--multi .isd-page-thumb-wrap {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 0;
  border-color: transparent;
}

.isd-page-card--multi::after {
  content: '';
  position: absolute;
  top: 6px;
  left: 6px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='white' d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
  background-size: 12px;
  background-repeat: no-repeat;
  background-position: center;
  pointer-events: none;
}

.isd-page-card--selected .isd-page-thumb-wrap {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 0;
  border-color: transparent;
}

/* ── Thumbnail ── */
.isd-page-thumb-wrap {
  position: relative;
  width: 100%;
  padding-top: 133%; /* 3:4 portrait ratio */
  background: rgba(var(--v-theme-on-surface), 0.05);
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  transition: border-color 0.12s;
}

.isd-page-thumb-inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.isd-page-select-indicator {
  position: absolute;
  top: 5px;
  left: 5px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.9);
  background: rgba(0, 0, 0, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: background 0.12s, border-color 0.12s;
}

.isd-page-select-indicator--checked {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: #fff;
}


.isd-page-thumb {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.isd-page-thumb-placeholder-icon {
  opacity: 0.3;
}

/* ── Page number badge ── */
.isd-page-num {
  font-size: 11px;
  font-weight: 500;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* ── Add-files placeholder card ── */
.isd-add-page-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  border-radius: 5px;
  padding: 0;
}

.isd-add-page-card--disabled {
  opacity: 0.35;
  pointer-events: none;
}

.isd-add-page-thumb-wrap {
  position: relative;
  width: 100%;
  padding-top: 133%;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-radius: 4px;
  border: 2px dashed rgba(var(--v-theme-on-surface), 0.18);
  transition: border-color 0.15s, background 0.15s;
}

.isd-add-page-card:hover .isd-add-page-thumb-wrap {
  border-color: rgba(var(--v-theme-primary), 0.55);
  background: rgba(var(--v-theme-primary), 0.05);
}

.isd-add-page-inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(var(--v-theme-on-surface), 0.25);
  transition: color 0.15s, transform 0.15s;
}

.isd-add-page-card:hover .isd-add-page-inner {
  color: rgb(var(--v-theme-primary));
}

/* Drag-over: der gestrichelte Platzhalter "leuchtet auf" */
.isd-add-page-card--drag-over .isd-add-page-thumb-wrap {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
  box-shadow: 0 0 0 3px rgba(var(--v-theme-primary), 0.18);
}

.isd-add-page-card--drag-over .isd-add-page-inner {
  color: rgb(var(--v-theme-primary));
  transform: scale(1.08);
}

.isd-toolbar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 0;
  padding: 8px 12px;
  border-top: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  box-sizing: border-box;
  height: var(--isd-bar-height, 49px);
  background: rgba(var(--v-theme-surface), 0.82);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.isd-toolbar-left {
  display: flex;
  align-items: center;
  gap: 4px;
}

.isd-toolbar-spacer {
  flex: 1;
}

.isd-toolbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.isd-toolbar-divider {
  width: 1px;
  height: 18px;
  background: rgba(var(--v-theme-on-surface), 0.14);
  margin: 0 10px;
  flex-shrink: 0;
}

.isd-toolbar-btn {
  text-transform: none;
  letter-spacing: normal;
  font-size: 13px;
}

.isd-toolbar-select-btn--active {
  box-shadow: 0 0 0 3px rgba(var(--v-theme-primary), 0.22);
}

.isd-rotate-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.isd-zoom-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.isd-zoom-label {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  white-space: nowrap;
}

.isd-zoom-slider {
  width: 120px;
  cursor: pointer;
  accent-color: rgb(var(--v-theme-primary));
}

.isd-page-count {
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* Spiegelt exakt die Struktur der linken Spalte (.isd-left): position:relative
 * als Anker, scrollender Inhalt, und die Statusleiste absolut am unteren Rand –
 * identische Technik wie .isd-toolbar, damit beide Leisten pixelgenau fluchten. */
.isd-props {
  flex: 0 0 35%;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.isd-props-scroll {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 18px 20px 64px; /* unten Platz für die absolute Statusleiste */
}

/* KI-Analyse-Status: absolut am unteren Rand – exakt wie .isd-toolbar
 * (position:absolute; bottom:0; padding:8px 12px; gemeinsame --isd-bar-height; border-top:1px). */
.isd-props-status {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  box-sizing: border-box;
  height: var(--isd-bar-height, 49px);
  overflow: hidden;
  border-top: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  background: rgba(var(--v-theme-surface), 0.82);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.isd-props-status__text {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 12.5px;
  line-height: 1.3;
  color: rgba(var(--v-theme-on-surface), 0.72);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.isd-props-status--failed .isd-props-status__text {
  color: rgba(var(--v-theme-on-surface), 0.78);
}

.isd-props-status__warn-icon {
  color: rgb(var(--v-theme-warning)) !important;
}

.isd-props-status__idle-icon {
  color: rgba(var(--v-theme-on-surface), 0.4) !important;
}

.isd-props-status__retry {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-primary));
  padding: 3px 8px;
  border-radius: 6px;
  transition: background 0.15s;
}

.isd-props-status__retry:hover:not(:disabled) {
  background: rgba(var(--v-theme-primary), 0.1);
}

.isd-props-status__retry:disabled {
  opacity: 0.4;
  cursor: default;
}

.isd-props--disabled {
  pointer-events: none;
  opacity: 0.4;
}

/* ── Fields ── */
.isd-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.isd-field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.isd-field-info {
  color: rgba(var(--v-theme-on-surface), 0.35) !important;
  cursor: default;
  flex-shrink: 0;
  transition: color 0.15s;
}

.isd-field-info:hover {
  color: rgba(var(--v-theme-on-surface), 0.65) !important;
}

.isd-ai-filled-badge {
  display: inline-flex;
  align-items: center;
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.05em;
}


.isd-field-row {
  display: flex;
  gap: 4px;
  align-items: center;
}


.isd-ai-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  align-self: flex-start;
  padding: 3px 9px;
  background: transparent;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.28);
  border-radius: 20px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  font-size: 11px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.isd-ai-chip:hover {
  border-color: rgba(var(--v-theme-on-surface), 0.5);
  color: rgba(var(--v-theme-on-surface), 0.75);
}
.isd-ai-chip__action { font-weight: 600; }


/* ── Divider & Toggles ── */
.isd-divider {
  height: 1px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  margin: 2px 0;
}

.isd-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.isd-toggle-lbl {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.isd-toggle-lbl span { font-size: 13px; font-weight: 400; }
.isd-toggle-lbl small { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.54); }

.isd-toggle {
  flex: 0 0 auto;
  position: relative;
  width: 38px;
  height: 21px;
  border-radius: 11px;
  border: none;
  background: rgba(var(--v-theme-on-surface), 0.2);
  cursor: pointer;
  transition: background 0.2s;
  appearance: none;
}
.isd-toggle::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
.isd-toggle--on { background: rgb(var(--v-theme-primary)); }
.isd-toggle--on::after { transform: translateX(17px); }
.isd-toggle--dis { opacity: 0.38; cursor: not-allowed; }

/* ── Footer ── */
.isd-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.isd-footer-end {
  display: flex;
  align-items: center;
  gap: 10px;
}

.isd-footer-status {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.54);
}
</style>
