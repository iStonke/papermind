<template>
  <BaseDialog
    v-model="isOpen"
    :persistent="isUploadingSources || isCommitting"
    :max-width="dialogMaxWidth"
    :card-class="dialogCardClass"
    :body-class="dialogBodyClass"
    title="PDFs importieren"
    header-subtitle="Importiere PDFs oder ganze Ordner und stelle Dokumente aus Seiten zusammen."
    description=""
    @close="onDialogClose"
  >
    <div
      class="import-modal import-staging pm-import-modal importer-dialog"
      :class="{ 'is-empty': isEmpty, 'is-filled': !isEmpty }"
      :style="importerThemeVars"
      @dragover.prevent="onModalSurfaceDragOver"
      @drop.prevent="onModalSurfaceDrop"
    >
      <div class="import-content" :class="{ 'import-content--empty': isEmpty, 'import-content--work': !isEmpty }">
        <transition name="import-mode" mode="out-in">
          <section
            v-if="isEmpty"
            key="empty"
            class="import-staging-empty"
          >
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

        <div
          class="import-staging-dropzone"
          :class="{
            'import-staging-dropzone--hover': isDropzoneHover && !isDropzoneDragOver,
            'import-staging-dropzone--drag': isDropzoneDragOver,
            'import-staging-dropzone--busy': isUploadingSources
          }"
          role="button"
          tabindex="0"
          @mouseenter="onDropzoneMouseEnter"
          @mouseleave="onDropzoneMouseLeave"
          @focusin="onDropzoneFocusIn"
          @focusout="onDropzoneFocusOut"
          @dragenter.prevent="onDropzoneDragEnter"
          @dragover.prevent="onDropzoneDragOver"
          @dragleave.prevent="onDropzoneDragLeave"
          @drop.prevent="onDropzoneDrop"
          @click="onDropzoneClick"
          @keydown="handleDropzoneShortcut"
        >
          <v-icon class="import-staging-dropzone__icon" size="56">mdi-file-upload-outline</v-icon>
          <div class="import-staging-dropzone__headline">{{ dropzoneHeadline }}</div>
          <div class="import-staging-dropzone__actions">
            <v-btn
              variant="flat"
              size="large"
              :ripple="false"
              class="import-staging-dropzone__cta"
              :aria-label="dropzonePrimaryLabel"
              @click.stop="openFilePicker"
            >
              Hinzufügen...
            </v-btn>
          </div>
          <p v-if="isIOSDevice" class="import-staging-dropzone__ios-hint">
            Tipp: In Dateien -> ⋯ -> Dokumente scannen. Danach die PDF hier hochladen.
          </p>
        </div>
        </section>

        <section
          v-else
          key="filled"
          class="import-modal__content import-staging-list"
          @dragover.prevent="onListSurfaceDragOver"
          @drop.prevent="onListSurfaceDrop"
        >
          <div
            class="import-staging-content pm-import-body-shell"
            @dragenter.prevent="onBodyShellDragEnter"
            @dragover.prevent="onBodyShellDragOver"
            @dragleave.prevent="onBodyShellDragLeave"
            @drop.prevent="onBodyShellDrop"
          >
            <div class="import-staging-work-layout">
              <div
                ref="bodyScrollRef"
                class="import-staging-scroll pm-import-body-scroll"
                :class="{ 'pm-import-body-scroll--centered': !isBodyContentOverflowing && !isViewSwitching }"
                @click.self="clearActiveSelection"
              >
                <div
                  ref="docsListRef"
                  class="import-staging-docs pm-import-stages"
                  @click.self="clearActiveSelection"
                  @dragover.prevent="onDocsContainerDragOver"
                  @drop.prevent="onDocsContainerDrop"
                >
                  <div
                    v-for="(document, documentIndex) in documents"
                    :key="document.id"
                    class="import-staging-doc-slot"
                  >
                    <div
                      class="import-staging-interdrop"
                      @dragover.prevent="onInterDropDragOver"
                      @drop.prevent="onInterDocumentDrop($event, documentIndex)"
                    />

                    <article
                      class="import-staging-doc stage-card"
                      :class="{
                        'import-staging-doc--empty': document.pages.length === 0,
                        'import-staging-doc--collapsed': document.collapsed,
                        'import-staging-doc--dragover': isDocumentDragActive(document.id)
                      }"
                      @dragenter.prevent="onDocumentDragEnter($event, document.id)"
                      @dragover.prevent="onDocumentBodyDragOver($event, document.id)"
                      @dragleave.prevent="onDocumentDragLeave($event, document.id)"
                      @drop.prevent="onDocumentBodyDrop($event, document.id)"
                    >
                      <header class="import-staging-doc__header stage-header">
                      <input
                        :ref="(el) => setCardFileInputRef(document.id, el)"
                        class="d-none"
                        type="file"
                        accept="application/pdf,.pdf"
                        multiple
                        @change="onCardFileInputChange($event, document.id)"
                      />

                      <div class="stage-header-left">
                        <button
                          type="button"
                          class="import-staging-doc__collapse"
                          :aria-label="document.collapsed ? 'Aufklappen' : 'Einklappen'"
                          @click="onDocumentCollapseToggle(document.id)"
                        >
                          {{ document.collapsed ? '▸' : '▾' }}
                        </button>

                        <div class="stage-title-input">
                          <div class="stage-title-row">
                            <input
                              :ref="(el) => setTitleInputRef(document.id, el)"
                              class="import-staging-doc__title"
                              :value="document.title"
                              @input="onDocumentTitleInput(document.id, $event)"
                              @blur="onDocumentTitleBlur(document.id)"
                              @keydown="handleDocumentTitleShortcut($event, document.id)"
                            />

                            <v-menu location="bottom start" offset="6">
                              <template #activator="{ props: aiMenuProps }">
                                <v-btn
                                  :icon="resolveIcon('mdi-robot-outline')"
                                  variant="text"
                                  size="small"
                                  class="stage-title-ai-btn"
                                  :loading="isScanTitleBusy(document)"
                                  :disabled="isTitleSuggestActionDisabled(document)"
                                  :aria-label="getTitleSuggestHint(document)"
                                  :title="getTitleSuggestHint(document)"
                                  v-bind="aiMenuProps"
                                />
                              </template>
                              <v-list density="compact" min-width="220">
                                <v-list-item
                                  :prepend-icon="resolveIcon('mdi-refresh')"
                                  title="Titel vorschlagen (Seite 1)"
                                  :disabled="isScanTitleBusy(document)"
                                  @click="requestScanTitleSuggestion(document.id, 'first_page')"
                                />
                                <v-list-item
                                  :prepend-icon="resolveIcon('mdi-refresh')"
                                  title="Titel vorschlagen (alle Seiten)"
                                  :disabled="isScanTitleBusy(document)"
                                  @click="requestScanTitleSuggestion(document.id, 'all_pages')"
                                />
                              </v-list>
                            </v-menu>
                          </div>
                          <div v-if="isScanTitleWorking(document)" class="scan-title-hint scan-title-hint--working">
                            <v-progress-circular indeterminate size="12" width="2" />
                            <span>Titel wird vorgeschlagen…</span>
                          </div>
                          <div v-else-if="isScanTitlePendingOcr(document)" class="scan-title-hint scan-title-hint--pending">
                            <span>{{ document.meta.titleSuggestionPollExhausted ? 'OCR noch nicht fertig - später erneut versuchen.' : 'OCR läuft…' }}</span>
                            <button type="button" class="scan-title-hint__apply" @click="requestScanTitleSuggestion(document.id, 'first_page')">
                              Später erneut
                            </button>
                          </div>
                          <div v-else-if="canShowScanSuggestion(document)" class="scan-title-hint scan-title-hint--ready">
                            <span class="scan-title-hint__label">{{ getScanSuggestionPrefix(document) }} {{ document.meta.titleSuggestion }}</span>
                            <button type="button" class="scan-title-hint__apply" @click="applyScanSuggestion(document.id)">
                              {{ getScanSuggestionActionLabel(document) }}
                            </button>
                          </div>
                          <div v-if="canShowScanSuggestion(document) && getScanSuggestionDetails(document)" class="scan-title-hint scan-title-hint--meta">
                            {{ getScanSuggestionDetails(document) }}
                          </div>
                        </div>
                      </div>

                      <div class="stage-toolbar stage-header-right">
                        <div class="toolbar-left">
                          <span class="pages-label">Seiten</span>
                          <span class="pages-count">{{ document.pages.length }}</span>
                        </div>

                        <div class="toolbar-divider" aria-hidden="true" />

                        <div class="toolbar-actions">
                          <v-btn
                            :icon="resolveIcon('mdi-call-split')"
                            variant="text"
                            class="pm-icon-btn stage-toolbar-btn"
                            :style="getToolbarControlStyle(!canSplitPage(document.id))"
                            aria-label="Ausgewählte Seite auslagern"
                            :disabled="!canSplitPage(document.id)"
                            @click="splitSelectedPage(document.id)"
                          />

                          <v-btn
                            :icon="resolveIcon('mdi-rotate-right')"
                            variant="text"
                            class="pm-icon-btn stage-toolbar-btn"
                            :style="getToolbarControlStyle(!hasSelectedPage(document.id))"
                            aria-label="Seite drehen"
                            :disabled="!hasSelectedPage(document.id)"
                            @click="rotateSelectedPage(document.id, 90)"
                          />

                          <v-btn
                            :icon="resolveIcon('mdi-trash-can-outline')"
                            variant="text"
                            color="error"
                            class="pm-icon-btn stage-toolbar-btn"
                            :style="getToolbarControlStyle(!hasSelectedPage(document.id))"
                            aria-label="Ausgewählte Seite entfernen"
                            :disabled="!hasSelectedPage(document.id)"
                            @click="removeSelectedPage(document.id)"
                          />

                          <div class="toolbar-divider toolbar-divider--tags" aria-hidden="true" />

                          <StageTags
                            class="stage-toolbar__tags"
                            :tag-ids="document.tags || []"
                            :all-tags="stageTagPool"
                            :button-style="toolbarControlEnabledStyle"
                            :create-tag-by-name="createStageTagByName"
                            :load-tags="ensureStageTagsLoaded"
                            @update:tag-ids="onDocumentTagsUpdate(document.id, $event)"
                          />

                          <v-menu location="bottom end" offset="6">
                            <template #activator="{ props: menuProps }">
                              <v-btn
                                :icon="resolveIcon('mdi-dots-horizontal')"
                                variant="text"
                                class="pm-icon-btn stage-toolbar-btn"
                                :style="toolbarControlEnabledStyle"
                                aria-label="Mehr Aktionen"
                                v-bind="menuProps"
                              />
                            </template>
                            <v-list density="compact" min-width="220">
                              <v-list-item :prepend-icon="resolveIcon('mdi-file-document-outline')" title="PDFs hinzufügen..." @click="openCardFilePicker(document.id)" />
                              <v-divider class="my-1" />
                              <v-list-item
                                class="import-staging-doc__menu-delete"
                                :prepend-icon="resolveIcon('mdi-trash-can-outline')"
                                title="Dokument löschen..."
                                @click="deleteDocument(document.id)"
                              />
                            </v-list>
                          </v-menu>
                        </div>
                      </div>
                    </header>

                    <Transition
                      name="stage-collapse"
                      @before-enter="onStageBodyBeforeEnter"
                      @enter="onStageBodyEnter"
                      @after-enter="onStageBodyAfterEnter"
                      @before-leave="onStageBodyBeforeLeave"
                      @leave="onStageBodyLeave"
                      @after-leave="onStageBodyAfterLeave"
                    >
                      <div v-if="!document.collapsed" class="import-staging-doc__body stage-body">
                        <div v-if="document.pages.length === 0" class="import-staging-doc__no-pages">
                          <span>Keine Seiten</span>
                          <v-btn size="x-small" variant="text" color="error" @click="deleteDocument(document.id)">
                            Dokument löschen
                          </v-btn>
                        </div>

                        <TransitionGroup
                          v-else
                          class="import-staging-pages"
                          tag="div"
                          name="staging-page-list"
                          @dragover.prevent="onPagesContainerDragOver($event, document.id)"
                          @drop.prevent="onPagesContainerDrop($event, document.id)"
                        >
                          <div
                            v-for="(page, pageIndex) in document.pages"
                            :key="page.id"
                            :ref="(el) => setPageThumbRef(page.id, el)"
                            class="import-staging-page"
                            :class="{
                              'import-staging-page--selected': isPageSelected(document.id, page.id),
                              'import-staging-page--dragging': isDraggingPage(page.id),
                              'import-staging-page--drop-hover': isDropHoverPage(document.id, page.id),
                              'import-staging-page--settled': isSettledPage(page.id)
                            }"
                            :data-page-id="page.id"
                            :data-page-index="pageIndex"
                            :data-doc-id="document.id"
                            draggable="true"
                            @dragstart="onPageDragStart($event, document.id, page.id, pageIndex)"
                            @dragend="onPageDragEnd"
                            @click="onPageClick($event, document.id, page.id, pageIndex)"
                            @dblclick="onPageDoubleClick($event, document.id, page.id, pageIndex)"
                            @dragover.prevent="onPageDragOver($event, document.id, page.id, pageIndex)"
                            @drop.prevent="onPageDrop($event, document.id, pageIndex)"
                          >
                            <div class="import-staging-page__thumb-wrap">
                              <img
                                v-if="page.thumbUrl"
                                class="import-staging-page__thumb"
                                :src="page.thumbUrl"
                                alt="Seitenvorschau"
                                :style="{ transform: `rotate(${page.rotation}deg)` }"
                              />
                              <div v-else class="import-staging-page__thumb import-staging-page__thumb--fallback">
                                <v-icon size="18">{{ resolveIcon('mdi-file-pdf-box') }}</v-icon>
                              </div>

                              <span class="import-staging-page__order">{{ pageIndex + 1 }}</span>

                              <div class="import-staging-page__actions">
                                <v-btn
                                  size="x-small"
                                  :icon="resolveIcon('mdi-trash-can-outline')"
                                  variant="tonal"
                                  color="error"
                                  @click.stop="removePage(page.id)"
                                />
                              </div>
                            </div>
                          </div>

                          <div
                            v-if="isPageDropMarkerVisible(document.id)"
                            :key="`insert-line-${document.id}`"
                            class="import-staging-page-insert-line"
                            :style="pageDropMarkerStyle"
                          >
                            <span class="import-staging-page-insert-line__cap import-staging-page-insert-line__cap--top" />
                            <span class="import-staging-page-insert-line__cap import-staging-page-insert-line__cap--bottom" />
                          </div>
                        </TransitionGroup>
                      </div>
                      </Transition>
                    </article>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="isBodyFileDragOver" class="pm-import-drop-overlay" aria-hidden="true">
              <div class="pm-import-drop-overlay__text">
                Loslassen zum Importieren
              </div>
            </div>
          </div>
        </section>
        </transition>
      </div>
    </div>

    <template #footer>
      <div v-if="hasPreparationProgress" class="import-staging-progress">
        <div class="import-staging-progress__label">{{ preparationProgressLabel }}</div>
        <v-progress-linear
          :model-value="preparationProgressPercent"
          height="4"
          color="primary"
          rounded
        />
      </div>
      <div class="pm-import-footer">
        <div class="import-staging-footer" :class="{ 'import-staging-footer--empty': isEmpty }">
          <span v-if="!isEmpty" class="text-caption">{{ footerSummary }}</span>
          <span v-if="!isEmpty && emptyHint" class="import-staging-footer__warning">{{ emptyHint }}</span>
        </div>
        <div class="pm-import-footer-actions">
          <v-btn variant="text" :disabled="isUploadingSources || isCommitting" @click="isOpen = false">Abbrechen</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            class="import-staging-footer__import-btn"
            :loading="isCommitting"
            :title="totalPages <= 0 ? 'Bitte PDFs hinzufügen' : ''"
            :disabled="isImportActionDisabled"
            @click="commitImport"
          >
            {{ isCommitting ? 'Importiere...' : `Importieren (${importCount})` }}
          </v-btn>
        </div>
      </div>
    </template>
  </BaseDialog>

  <Teleport to="body">
    <transition name="peek-popover">
      <div
        v-if="isOpen && peek.open && selectedPageEntry"
        ref="peekPanelRef"
        class="import-staging-peek"
        :style="peekStyle"
      >
        <div class="import-staging-peek__viewport">
          <v-progress-circular
            v-if="previewImageLoading"
            indeterminate
            color="primary"
            size="24"
          />
          <img
            v-else-if="previewImageSrc"
            class="import-staging-peek__image"
            :src="previewImageSrc"
            alt="Große Seitenvorschau"
          />
          <div v-else class="import-staging-peek__empty" />
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { useTheme } from 'vuetify';
import BaseDialog from './BaseDialog.vue';
import StageTags from './StageTags.vue';
import { suggestImportStageTitle } from '../api/importStaging';
import { isIOS } from '../utils/platform';
import { mapApiError, useNotifications } from '../stores/notifications';
import { useImportStagingStore } from '../stores/importStaging';
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
  autoOcr: { type: Boolean, default: true },
  autoIndex: { type: Boolean, default: true },
  autoEmbed: { type: Boolean, default: true }
});

const emit = defineEmits(['update:modelValue', 'committed', 'discarded-sources']);

const { notify } = useNotifications();
const stagingStore = useImportStagingStore();
const theme = useTheme();
const { documents, documentCount, totalPages, emptyDocuments, commitDocuments } = storeToRefs(stagingStore);

const KNOWN_ICONS = new Set([
  'mdi-file-document-outline',
  'mdi-folder-outline',
  'mdi-plus',
  'mdi-robot-outline',
  'mdi-call-split',
  'mdi-rotate-right',
  'mdi-dots-horizontal',
  'mdi-trash-can-outline',
  'mdi-file-pdf-box',
  'mdi-refresh'
]);

const isDropzoneDragOver = ref(false);
const isDropzoneHover = ref(false);
const dropDragDepth = ref(0);
const documentDragDepth = ref({});
const isBodyFileDragOver = ref(false);
const bodyFileDragDepth = ref(0);
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
  return status === 'working' || status === 'pending_ocr';
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

function canShowScanSuggestion(documentEntry) {
  const suggestion = String(documentEntry?.meta?.titleSuggestion || '').trim();
  const status = String(documentEntry?.meta?.titleSuggestionStatus || '');
  if (!suggestion || status !== 'ready') {
    return false;
  }
  return isDefaultScanTitle(documentEntry?.title);
}

function getScanSuggestionPrefix(documentEntry) {
  if (documentEntry?.meta?.titleSuggestionUsedFallback) {
    return 'Titel automatisch:';
  }
  return 'Vorschlag:';
}

function getScanSuggestionActionLabel(documentEntry) {
  return documentEntry?.meta?.titleSuggestionUsedFallback ? 'Umbenennen' : 'Übernehmen';
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
const MODAL_WORK_WIDTH_COMPACT = 900;
const dialogMaxWidth = computed(() => MODAL_WORK_WIDTH_COMPACT);
const dialogCardClass = computed(() => {
  if (isEmpty.value) {
    return ['import-staging-dialog-card', 'import-modal--empty'];
  }
  return ['import-staging-dialog-card', 'import-modal--work', 'import-modal--work-compact'];
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
const isImportActionDisabled = computed(() => totalPages.value <= 0 || isUploadingSources.value || isCommitting.value);
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
      return;
    }
    nextTick(() => {
      setupBodyLayoutObserver();
      scheduleBodyContentLayoutStateUpdate();
    });
    void ensureStageTagsLoaded().catch((error) => {
      notify({ type: 'error', message: mapApiError(error, 'Tags konnten nicht geladen werden.') });
    });
  }
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
  const response = await fetch(`${props.apiBaseUrl}/api/import/source/${encodeURIComponent(sourceFileId)}/file`);
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
        const targetWidth = 118;
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
      const thumbs = await renderPdfThumbnails(file, pageCount);

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
      } else {
        stagingStore.addDocumentFromSource({
          sourceFileId: source.source_file_id,
          title,
          pageCount,
          thumbUrls: thumbs,
          insertIndex: nextInsertIndex
        });
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

  if (!sessionStageId) {
    const created = stagingStore.addEmptyDocument(null, 'Neuer Scan');
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
    const recreated = stagingStore.addEmptyDocument(null, 'Neuer Scan');
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
    let stagingFile = null;
    let thumbUrls = [];
    try {
      stagingFile = await downloadStagingSourceFile(sourceFileId, originalName);
      thumbUrls = await renderPdfThumbnails(stagingFile, pageCount);
    } catch {
      previewFallbackCount += 1;
    }

    stagingStore.setStagingFile(sourceFileId, stagingFile, { originalName, pageCount });
    const targetStageId = String(source?.target_stage_id || '').trim() || sessionStageId;
    if (targetStageId && documents.value.some((entry) => entry.id === targetStageId)) {
      const targetDoc = getDocumentById(targetStageId);
      const targetMeta = ensureScanMeta(targetDoc);
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
      const fallback = stagingStore.addEmptyDocument(null, 'Neuer Scan');
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
          title: 'Neuer Scan',
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
    if (isDefaultScanTitle(targetDoc?.title) && !hasSuggestion && targetMeta.titleSuggestionStatus !== 'working') {
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
    const maxPendingRetries = Number.isInteger(options?.maxPendingRetries) ? Number(options.maxPendingRetries) : 10;
    let attempt = 0;
    try {
      while (attempt < maxPendingRetries) {
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

function removePage(pageId) {
  const location = stagingStore.findPageLocation(pageId);
  const sourceFileId = normalizeSourceFileId(location?.page?.sourceFileId);
  stagingStore.removePage(pageId);
  if (selected.value?.pageId === pageId) {
    clearActiveSelection();
  }
  notifyDiscardedSourceFileIds([sourceFileId]);
}

function removeSelectedPage(documentId) {
  const selectedPage = resolveSelectedPage(documentId);
  if (!selectedPage) {
    return;
  }
  removePage(selectedPage.id);
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
        documents: commitDocuments.value,
        options: {
          auto_ocr: Boolean(props.autoOcr),
          auto_index: Boolean(props.autoIndex),
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

<style scoped>
.import-staging {
  --pm-modal-pad-y: 20px;
  --pm-modal-pad-x: 24px;
  --pm-toolbar-icon-color: rgba(15, 23, 42, 0.62);
  --pm-toolbar-disabled-color: rgba(15, 23, 42, 0.34);
  --pm-dropzone-bg: rgba(var(--v-theme-primary), 0.06);
  --pm-dropzone-border: rgba(var(--v-theme-primary), 0.38);
  --pm-dropzone-bg-hover: rgba(var(--v-theme-primary), 0.08);
  --pm-dropzone-border-hover: rgba(var(--v-theme-primary), 0.52);
  --pm-dropzone-bg-active: rgba(var(--v-theme-primary), 0.14);
  --pm-dropzone-border-active: rgba(var(--v-theme-primary), 0.8);
  --pmSplitBg: color-mix(in srgb, rgb(var(--v-theme-primary)) 12%, transparent);
  --pmSplitBgHover: color-mix(in srgb, rgb(var(--v-theme-primary)) 16%, transparent);
  --pmSplitSegHover: color-mix(in srgb, rgb(var(--v-theme-primary)) 10%, transparent);
  --pmSplitSegActive: color-mix(in srgb, rgb(var(--v-theme-primary)) 14%, transparent);
  --pmSplitDivider: color-mix(in srgb, rgb(var(--v-theme-primary)) 22%, transparent);
  --pmSplitShadow: none;
  display: grid;
  gap: 14px;
  height: 100%;
  background: transparent;
}

:deep(.v-theme--dark) .importer-dialog {
  --pm-dm-header-bg: rgba(255, 255, 255, 0.06);
  --pm-dm-divider: rgba(255, 255, 255, 0.14);
  --pm-dm-icon: rgba(255, 255, 255, 0.70);
  --pm-dm-icon-dim: rgba(255, 255, 255, 0.70);
  --pm-dm-hover: rgba(255, 255, 255, 0.10);
  --pm-dm-text: rgba(255, 255, 255, 0.92);
  --pm-dm-text2: rgba(255, 255, 255, 0.70);
  --pm-dm-focus: rgba(110, 168, 255, 0.50);
  --pm-toolbar-icon-color: var(--pm-dm-icon);
  --pm-toolbar-btn-color: var(--pm-dm-text2);
  --pm-toolbar-disabled-color: rgba(255, 255, 255, 0.36);
  --pm-toolbar-btn-opacity: 1;
  --pm-dropzone-bg: rgba(var(--v-theme-primary), 0.1);
  --pm-dropzone-border: rgba(var(--v-theme-primary), 0.48);
  --pm-dropzone-bg-hover: rgba(var(--v-theme-primary), 0.14);
  --pm-dropzone-border-hover: rgba(var(--v-theme-primary), 0.62);
  --pm-dropzone-bg-active: rgba(var(--v-theme-primary), 0.18);
  --pm-dropzone-border-active: rgba(var(--v-theme-primary), 0.88);
  --pmSplitBg: color-mix(in srgb, rgb(var(--v-theme-primary)) 18%, transparent);
  --pmSplitBgHover: color-mix(in srgb, rgb(var(--v-theme-primary)) 24%, transparent);
  --pmSplitSegHover: color-mix(in srgb, rgb(var(--v-theme-primary)) 14%, transparent);
  --pmSplitSegActive: color-mix(in srgb, rgb(var(--v-theme-primary)) 18%, transparent);
  --pmSplitDivider: color-mix(in srgb, rgb(var(--v-theme-primary)) 26%, transparent);
  --pmSplitShadow: none;
}

.import-content {
  width: 100%;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  padding: 0;
  transition: padding 240ms cubic-bezier(0.22, 1, 0.36, 1);
}

.import-content--empty {
  padding: var(--pm-modal-pad-y) var(--pm-modal-pad-x);
}

:deep(.import-staging-dialog-card) {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: none !important;
  outline: none !important;
  box-shadow: var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.12)) !important;
  transition:
    width 280ms cubic-bezier(0.22, 1, 0.36, 1),
    max-width 280ms cubic-bezier(0.22, 1, 0.36, 1),
    height 280ms cubic-bezier(0.22, 1, 0.36, 1),
    max-height 280ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 220ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: width, max-width, height, max-height, transform, opacity;
}

:deep(.import-staging-dialog-card.import-modal--empty) {
  width: min(760px, calc(100vw - 64px));
  max-width: calc(100vw - 64px);
  height: 610px !important;
  min-height: 610px !important;
  max-height: calc(100vh - 96px);
  transform: translateY(0);
  opacity: 1;
}

:deep(.import-staging-dialog-card.import-modal--work) {
  height: min(860px, 90vh);
  max-height: 90vh;
  transform: translateY(0);
  opacity: 1;
}

:deep(.import-staging-dialog-card.import-modal--work-compact) {
  width: min(900px, calc(100vw - 96px));
  max-width: min(900px, calc(100vw - 96px));
}

:deep(.import-staging-dialog-card .pm-dialog__header),
:deep(.import-staging-dialog-card .pm-dialog__footer) {
  flex: 0 0 auto;
  background: rgb(var(--v-theme-surface));
  z-index: 1;
}

:deep(.import-staging-dialog-card .pm-dialog__header) {
  padding: 16px 18px;
}

:deep(.import-staging-dialog-card .pm-dialog__content-wrap) {
  max-height: none;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden !important;
  scrollbar-gutter: stable;
}

:deep(.import-staging-dialog-card.import-modal--empty .pm-dialog__content-wrap) {
  max-height: none !important;
}

:deep(.import-staging-dialog-card.import-modal--empty .pm-dialog__content) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

:deep(.import-staging-dialog-card.import-modal--work .pm-dialog__content) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

:deep(.import-staging-dialog-card .pm-dialog__footer) {
  padding: 12px 18px;
  border-top: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
}

:deep(.import-staging-dialog-card.import-modal--empty .pm-dialog__footer) {
  padding: 12px 18px;
}

.import-staging-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.import-staging-dropzone {
  width: 100%;
  max-width: none;
  margin: 0;
  min-height: clamp(220px, 34vh, 260px);
  border: 2px dashed var(--pm-dropzone-border);
  border-radius: 28px;
  background: var(--pm-dropzone-bg);
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  transition: border-color 0.16s ease, background-color 0.16s ease, box-shadow 0.16s ease;
  box-shadow: none;
  cursor: pointer;
}

.import-staging-dropzone--hover {
  border-color: var(--pm-dropzone-border-hover);
  background: var(--pm-dropzone-bg-hover);
  box-shadow: none;
}

.import-staging-dropzone:focus-visible {
  border-color: var(--pm-dropzone-border-hover);
  background: var(--pm-dropzone-bg-hover);
  box-shadow: none;
  outline: none;
}

.import-staging-dropzone--drag {
  border-color: var(--pm-dropzone-border-active);
  background: var(--pm-dropzone-bg-active);
  box-shadow: none;
}

.import-staging-dropzone--busy {
  opacity: 0.75;
  pointer-events: none;
  cursor: default;
}

.import-staging-dropzone__icon {
  color: rgba(var(--v-theme-on-surface), 0.8);
}

.import-staging-dropzone__headline {
  font-size: 18px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
  max-width: 520px;
}

.import-staging-dropzone__actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  max-width: 520px;
}

.import-staging-dropzone__cta {
  text-transform: none;
  letter-spacing: 0;
  min-height: 48px;
  padding-inline: 20px;
}

.pm-split {
  display: inline-flex;
  align-items: stretch;
  height: 48px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--pmSplitBg);
  box-shadow: var(--pmSplitShadow);
}

.pm-split__main,
.pm-split__side {
  height: 100% !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
  color: rgb(var(--v-theme-primary)) !important;
  transition: background-color 150ms ease, transform 120ms ease, color 150ms ease;
}

.pm-split__main {
  min-width: 180px;
  padding: 0 18px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-weight: 600;
  border-top-left-radius: 16px !important;
  border-bottom-left-radius: 16px !important;
}

.pm-split__side {
  width: 56px;
  min-width: 56px !important;
  padding: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  opacity: 0.95;
  border-top-right-radius: 16px !important;
  border-bottom-right-radius: 16px !important;
}

.pm-split__divider {
  width: 1px;
  height: 100%;
  flex: 0 0 auto;
  background: var(--pmSplitDivider);
  opacity: 0.8;
  pointer-events: none;
}

.pm-split__side :deep(.v-icon) {
  transform: translateY(1px);
  opacity: 0.95;
}

.pm-split__side:hover :deep(.v-icon) {
  opacity: 1;
}

.pm-split:hover {
  background: var(--pmSplitBgHover);
}

.pm-split__main:hover,
.pm-split__side:hover {
  background: var(--pmSplitSegHover) !important;
  transform: translateY(-1px);
}

.pm-split__main:active,
.pm-split__side:active {
  background: var(--pmSplitSegActive) !important;
  transform: translateY(0);
}

.pm-split :deep(.v-btn__overlay),
.pm-split :deep(.v-btn__underlay) {
  display: none !important;
}

.pm-split :deep(.v-btn__content) {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pm-split :deep(.v-btn:focus-visible) {
  outline: none;
}

.import-staging-dropzone__ios-hint {
  margin: 2px 0 0;
  font-size: 0.8rem;
  line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.65);
  text-align: center;
  max-width: 420px;
}

.import-modal__content {
  width: 100%;
  max-width: 100%;
}

.import-staging-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1 1 auto;
  height: 100%;
  border: none;
  border-radius: 0;
  background: transparent;
  padding: 0;
  overflow: hidden;
}

.import-staging-content {
  width: 100%;
  max-width: 1080px;
  height: 100%;
  min-height: 0;
  margin: 0 auto;
  padding: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pm-import-body-shell {
  position: relative;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.import-staging-work-layout {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
}

.pm-import-body-scroll {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  scrollbar-gutter: stable;
  padding: 14px 18px;
  padding-bottom: 14px;
  margin: 0;
  box-sizing: border-box;
}

.pm-import-body-scroll--centered {
  justify-content: center;
}

.import-staging-docs {
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: visible;
}

.pm-import-drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  border-radius: 16px;
  background: rgba(40, 60, 90, 0.2);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.pm-import-drop-overlay__text {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(13, 20, 34, 0.32);
  color: rgba(255, 255, 255, 0.95);
  font-size: 0.82rem;
  font-weight: 600;
}

.import-staging-doc-slot {
  width: 100%;
  display: grid;
  gap: 10px;
}

.import-staging-doc-slot:first-child {
  gap: 0;
}

.import-staging-doc-slot:first-child .import-staging-interdrop {
  min-height: 0;
}

.import-staging-interdrop {
  min-height: 12px;
  border-radius: 6px;
}

.import-staging-doc {
  width: 100%;
  box-sizing: border-box;
  border: 0;
  border: 1px solid var(--pm-stage-border, #D6DEE9);
  outline: 0;
  border-radius: 18px;
  background: var(--pm-stage-bg, #E9EEF6);
  padding: 0;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04);
  overflow: hidden;
  transition: border-color 0.14s ease, box-shadow 0.14s ease;
}

.import-staging-doc--empty {
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.2);
}

.import-staging-doc--dragover {
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.24), 0 8px 18px rgba(var(--v-theme-primary), 0.12);
}

.import-staging-doc__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 14px 18px;
  border-bottom: 0;
  background: var(--pm-stage-header-bg, #E2E8F2);
  box-shadow: var(--pm-stage-header-inner-shadow, inset 0 -1px 0 rgba(15, 23, 42, 0.06));
  min-width: 0;
  overflow: hidden;
}

.import-staging-doc--collapsed .import-staging-doc__header {
  box-shadow: none;
}

:deep(.v-theme--dark) .importer-dialog .import-staging-doc__header {
  background: var(--pm-dm-header-bg);
}

.stage-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1 1 auto;
  min-width: 0;
  padding-right: 0;
}

.stage-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 auto;
  min-width: 0;
}

.import-staging-doc__collapse {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: rgba(var(--v-theme-on-surface), 0.68);
  cursor: pointer;
}

.import-staging-doc__collapse:hover {
  background: rgba(var(--v-theme-on-surface), 0.08);
}

:deep(.v-theme--dark) .importer-dialog .import-staging-doc__collapse {
  color: var(--pm-dm-icon);
}

:deep(.v-theme--dark) .importer-dialog .import-staging-doc__collapse:hover {
  background: var(--pm-dm-hover);
  color: var(--pm-dm-text);
}

.import-staging-doc__title {
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.25;
  color: inherit;
  padding: 0;
  outline: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.v-theme--dark) .importer-dialog .import-staging-doc__title {
  color: var(--pm-dm-text);
}

:deep(.v-theme--dark) .importer-dialog .import-staging-doc__title::placeholder {
  color: var(--pm-dm-text2);
}

.stage-title-input {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
  width: 100%;
  max-width: none;
  padding: 2px 6px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
}

.stage-title-row {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.stage-title-ai-btn {
  flex: 0 0 auto;
  min-width: 30px !important;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  opacity: 0.75;
}

.import-staging-doc__header:hover .stage-title-ai-btn {
  opacity: 1;
}

.stage-title-ai-btn.v-btn--disabled {
  opacity: 0.5 !important;
}

.stage-title-input .v-field__outline,
.stage-title-input .v-field__overlay,
.stage-title-input .v-field__loader {
  display: none !important;
}

.stage-title-input:focus-within {
  background: rgba(0, 0, 0, 0.04);
}

.scan-title-hint {
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.25;
  max-width: 100%;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.scan-title-hint--working {
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.scan-title-hint--pending {
  color: rgba(var(--v-theme-warning), 0.9);
}

.scan-title-hint--ready {
  background: rgba(var(--v-theme-primary), 0.1);
  border: 1px solid rgba(var(--v-theme-primary), 0.18);
  border-radius: 999px;
  padding: 2px 8px;
}

.scan-title-hint--meta {
  margin-top: 1px;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.scan-title-hint__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.scan-title-hint__apply {
  border: 0;
  background: transparent;
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  padding: 0;
}

:deep(.v-theme--dark) .importer-dialog .stage-title-input:focus-within {
  background: rgba(255, 255, 255, 0.12);
}

:deep(.v-theme--dark) .importer-dialog .stage-title-input {
  border-color: transparent;
  transition: background-color 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
}

:deep(.v-theme--dark) .importer-dialog .stage-title-input:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: var(--pm-dm-divider);
}

:deep(.v-theme--dark) .importer-dialog .stage-title-input:focus-within {
  background: rgba(255, 255, 255, 0.12);
  border-color: var(--pm-dm-focus);
  box-shadow: 0 0 0 3px rgba(110, 168, 255, 0.18);
}

:deep(.v-theme--dark) .importer-dialog .stage-title-ai-btn {
  color: var(--pm-dm-text2) !important;
}

.stage-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: nowrap;
  white-space: nowrap;
  min-width: 0;
}

.toolbar-left {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
}

.pages-label {
  font-size: 0.76rem;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.pages-count {
  font-size: 0.84rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.82);
  margin-left: 2px;
}

.toolbar-divider {
  width: 1px;
  height: 22px;
  background: var(--pm-divider, rgba(15, 23, 42, 0.14));
  margin: 0 12px;
  flex: 0 0 auto;
}

.toolbar-divider--tags {
  height: 20px;
  margin: 0 8px 0 2px;
}

:deep(.v-theme--dark) .importer-dialog .toolbar-left {
  padding-right: 12px;
}

:deep(.v-theme--dark) .importer-dialog .pages-label {
  color: var(--pm-dm-text2);
}

:deep(.v-theme--dark) .importer-dialog .pages-count {
  color: var(--pm-dm-text);
}

:deep(.v-theme--dark) .importer-dialog .toolbar-divider {
  background: var(--pm-dm-divider);
  height: 22px;
}

:deep(.v-theme--dark) .importer-dialog .stage-toolbar {
  color: var(--pm-dm-text2);
}

:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn),
:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn .v-btn__content),
:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn .v-icon) {
  color: var(--pm-dm-text2) !important;
  opacity: 1 !important;
}

:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn.v-btn--disabled),
:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn.v-btn--disabled .v-btn__content),
:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn.v-btn--disabled .v-icon) {
  color: var(--pm-dm-text2) !important;
  opacity: 1 !important;
}

.toolbar-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
}

.stage-toolbar-btn {
  color: var(--pm-toolbar-icon-color, rgba(15, 23, 42, 0.62)) !important;
  border-radius: 10px !important;
  padding: 6px 10px !important;
  min-width: auto;
}

.stage-toolbar-btn:hover {
  background: rgba(0, 0, 0, 0.06) !important;
}

:deep(.v-theme--dark) .importer-dialog .stage-toolbar-btn:hover {
  background: var(--pm-dm-hover) !important;
  color: var(--pm-dm-text) !important;
}

.stage-toolbar__tags {
  flex: 0 0 auto;
}

.pm-icon-btn {
  min-width: 36px !important;
  width: 36px;
  height: 36px;
  border-radius: 10px !important;
  padding: 6px !important;
  color: var(--pm-toolbar-icon-color, rgba(15, 23, 42, 0.62));
  background: transparent !important;
  border: none !important;
  transition: background-color 150ms ease, color 150ms ease, transform 120ms ease;
}

.pm-icon-btn :deep(.v-icon) {
  font-size: 23px;
}

:deep(.v-theme--dark) .importer-dialog .pm-icon-btn :deep(.v-icon) {
  font-size: 21px;
}

.pm-icon-btn:hover {
  background: rgba(0, 0, 0, 0.06) !important;
  color: var(--pm-icon-strong, rgba(15, 23, 42, 0.85));
  transform: translateY(-1px);
}

:deep(.v-theme--dark) .importer-dialog .pm-icon-btn:hover {
  background: var(--pm-dm-hover) !important;
  color: var(--pm-dm-text);
}

.pm-icon-btn:active {
  background: var(--pm-surface-pressed, rgba(15, 23, 42, 0.1)) !important;
  transform: translateY(0);
}

.pm-icon-btn.v-btn--disabled {
  opacity: 0.45;
  cursor: not-allowed !important;
}

:deep(.v-theme--dark) .importer-dialog .pm-icon-btn,
:deep(.v-theme--dark) .importer-dialog .stage-toolbar-btn {
  color: var(--pm-dm-text2) !important;
}

:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn .v-btn__content),
:deep(.v-theme--dark .importer-dialog .stage-toolbar .v-btn .v-icon) {
  color: var(--pm-dm-text2) !important;
  opacity: 1 !important;
}

:deep(.v-theme--dark .importer-dialog .pm-icon-btn),
:deep(.v-theme--dark .importer-dialog .stage-toolbar-btn),
:deep(.v-theme--dark .importer-dialog .pm-icon-btn .v-btn__content),
:deep(.v-theme--dark .importer-dialog .stage-toolbar-btn .v-btn__content),
:deep(.v-theme--dark .importer-dialog .pm-icon-btn .v-icon),
:deep(.v-theme--dark .importer-dialog .stage-toolbar-btn .v-icon) {
  color: var(--pm-dm-text2) !important;
  opacity: 1 !important;
}

:deep(.v-theme--dark) .importer-dialog .pm-icon-btn:active,
:deep(.v-theme--dark) .importer-dialog .stage-toolbar-btn:active {
  background: rgba(110, 168, 255, 0.16) !important;
  color: var(--pm-dm-text) !important;
}

:deep(.v-theme--dark) .importer-dialog .pm-icon-btn.v-btn--disabled,
:deep(.v-theme--dark) .importer-dialog .stage-toolbar-btn.v-btn--disabled {
  opacity: 1;
  color: var(--pm-dm-text2) !important;
}

:deep(.v-theme--dark .importer-dialog .pm-icon-btn.v-btn--disabled),
:deep(.v-theme--dark .importer-dialog .stage-toolbar-btn.v-btn--disabled),
:deep(.v-theme--dark .importer-dialog .pm-icon-btn.v-btn--disabled .v-icon),
:deep(.v-theme--dark .importer-dialog .stage-toolbar-btn.v-btn--disabled .v-icon),
:deep(.v-theme--dark .importer-dialog .pm-icon-btn.v-btn--disabled .v-btn__content),
:deep(.v-theme--dark .importer-dialog .stage-toolbar-btn.v-btn--disabled .v-btn__content) {
  color: var(--pm-dm-text2) !important;
  opacity: 1 !important;
}

.pm-icon-btn.v-btn--disabled:hover,
.pm-icon-btn.v-btn--disabled:active {
  background: transparent !important;
  color: var(--pm-icon-muted, rgba(15, 23, 42, 0.55));
  transform: none;
}

:deep(.v-theme--dark) .importer-dialog .pm-icon-btn.v-btn--disabled:hover,
:deep(.v-theme--dark) .importer-dialog .pm-icon-btn.v-btn--disabled:active,
:deep(.v-theme--dark) .importer-dialog .stage-toolbar-btn.v-btn--disabled:hover,
:deep(.v-theme--dark) .importer-dialog .stage-toolbar-btn.v-btn--disabled:active {
  background: transparent !important;
  color: var(--pm-dm-text2) !important;
  transform: none;
}

:deep(.importer-dialog .stage-toolbar .v-btn.v-btn--disabled),
:deep(.importer-dialog .stage-toolbar .v-btn.v-btn--disabled .v-btn__content),
:deep(.importer-dialog .stage-toolbar .v-btn.v-btn--disabled .v-icon) {
  color: var(--pm-toolbar-disabled-color) !important;
  --v-btn-color: var(--pm-toolbar-disabled-color) !important;
  opacity: 0.5 !important;
}

:deep(.importer-dialog .stage-toolbar .v-btn.v-btn--disabled:hover),
:deep(.importer-dialog .stage-toolbar .v-btn.v-btn--disabled:active) {
  background: transparent !important;
  transform: none !important;
}

.import-staging-doc__menu-delete :deep(.v-list-item-title),
.import-staging-doc__menu-delete :deep(.v-icon),
.import-staging-doc__menu-delete :deep(.v-list-item__prepend) {
  color: rgb(var(--v-theme-error)) !important;
}

.import-staging-doc__menu-delete :deep(.v-list-item__prepend) {
  opacity: 1;
}

.import-staging-doc__body {
  padding: 18px;
  background: transparent;
}

.stage-collapse-enter-active,
.stage-collapse-leave-active {
  transition: height 220ms cubic-bezier(0.22, 1, 0.36, 1), opacity 180ms ease;
}

.stage-collapse-enter-from,
.stage-collapse-leave-to {
  opacity: 0;
}

.import-staging-doc__no-pages {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 2px;
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.66);
}

.import-staging-pages {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(98px, 1fr));
  gap: 8px;
  position: relative;
  align-content: start;
}

.import-staging-page {
  position: relative;
  border: 1px solid var(--pm-border-subtle, rgba(15, 23, 42, 0.08));
  border-radius: 12px;
  padding: 4px;
  background: #fff;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
  cursor: grab;
  transition: border-color 0.14s ease, background-color 0.14s ease, transform 170ms ease-out, box-shadow 170ms ease-out, opacity 140ms ease;
  will-change: transform;
}

.import-staging-page:active {
  cursor: grabbing;
}

.import-staging-page--selected {
  padding: 4px;
  border-color: rgba(var(--v-theme-primary), 0.7);
  background: transparent;
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.3);
}

.import-staging-page--dragging {
  opacity: 0.85;
  transform: scale(1.03);
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18), 0 2px 6px rgba(15, 23, 42, 0.1);
  z-index: 40;
  cursor: grabbing;
}

.import-staging-page--drop-hover {
  background: rgba(var(--v-theme-primary), 0.06);
}

.import-staging-page--settled {
  animation: staging-page-settle 170ms ease-out;
}

.import-staging-page__thumb-wrap {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 110px;
}

.import-staging-page__thumb {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  transform-origin: center center;
}

.import-staging-page__thumb--fallback {
  min-height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(var(--v-theme-on-surface), 0.68);
}

.import-staging-page__order {
  position: absolute;
  left: 6px;
  bottom: 6px;
  min-width: 20px;
  height: 20px;
  border-radius: 999px;
  background: rgba(10, 14, 24, 0.8);
  color: rgba(255, 255, 255, 0.96);
  font-size: 0.72rem;
  line-height: 20px;
  text-align: center;
  font-weight: 600;
  padding: 0 6px;
}

.import-staging-page__actions {
  position: absolute;
  top: 4px;
  right: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.14s ease;
}

.import-staging-page:hover .import-staging-page__actions {
  opacity: 1;
  pointer-events: auto;
}

.import-staging-page-insert-line {
  position: absolute;
  width: 3px;
  border-radius: 999px;
  background: rgba(98, 148, 228, 0.9);
  transform: translateX(-1.5px);
  pointer-events: none;
  z-index: 4;
}

.import-staging-page-insert-line__cap {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(90, 140, 220, 0.82);
  left: 50%;
  transform: translateX(-50%);
}

.import-staging-page-insert-line__cap--top {
  top: -4px;
}

.import-staging-page-insert-line__cap--bottom {
  bottom: -4px;
}

.import-staging-peek {
  position: fixed;
  z-index: 3200;
  width: min(520px, calc(100vw - 40px));
  max-height: 70vh;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(28, 31, 38, 0.98);
  box-shadow: 0 24px 56px rgba(0, 0, 0, 0.45);
  padding: 10px;
  overflow: hidden;
}

.import-staging-peek__viewport {
  position: relative;
  height: min(64vh, 600px);
  max-height: calc(70vh - 20px);
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  overflow: hidden;
}

.import-staging-peek__image {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  object-position: center;
  display: block;
}

.import-staging-peek__empty {
  width: 100%;
  height: 100%;
}

.import-staging-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.import-staging-progress {
  display: grid;
  gap: 6px;
  padding: 0 2px 10px;
}

.import-staging-progress__label {
  font-size: 0.74rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.pm-import-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.pm-import-footer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.import-staging-footer--empty .text-caption {
  font-size: 0.72rem;
  opacity: 0.64;
}

.import-staging-footer .text-caption {
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.import-staging-footer__warning {
  font-size: 0.75rem;
  color: rgb(var(--v-theme-warning));
}

.import-staging-footer__import-btn {
  min-width: 142px;
  color: #fff;
}

.import-staging-footer__import-btn :deep(.v-btn__content) {
  letter-spacing: 0;
}

.import-staging-footer__import-btn.v-btn--disabled {
  background: rgb(var(--v-theme-surface-3)) !important;
  color: rgba(var(--v-theme-on-surface), 0.5) !important;
}

@media (prefers-reduced-motion: reduce) {
  :deep(.import-staging-dialog-card) {
    transition: none;
    transform: none;
  }

  .stage-collapse-enter-active,
  .stage-collapse-leave-active {
    transition: none;
  }

  .import-mode-enter-active,
  .import-mode-leave-active {
    transition: none;
  }

  .peek-popover-enter-active,
  .peek-popover-leave-active {
    transition: none;
  }
}

.import-mode-enter-active,
.import-mode-leave-active {
  transition:
    opacity 220ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: opacity;
}

.import-mode-enter-from,
.import-mode-leave-to {
  opacity: 0;
  transform: none;
}

.import-mode-enter-to,
.import-mode-leave-from {
  opacity: 1;
  transform: none;
}

.peek-popover-enter-active {
  transition: opacity 150ms ease-out, transform 150ms ease-out;
}

.peek-popover-leave-active {
  transition: opacity 100ms ease-in, transform 100ms ease-in;
}

.peek-popover-enter-from,
.peek-popover-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

@keyframes staging-page-settle {
  0% {
    transform: scale(1.02);
    background: rgba(255, 255, 255, 0.09);
  }
  100% {
    transform: scale(1);
    background: rgb(var(--v-theme-surface));
  }
}

.staging-page-list-move {
  transition: transform 170ms ease-out;
}

@media (max-width: 760px) {
  .import-content--empty {
    padding: 16px 18px;
  }

  .import-staging-dropzone {
    min-height: 180px;
    padding: 20px;
    border-radius: 20px;
    gap: 10px;
  }

  .import-staging-dropzone__headline {
    font-size: 16px;
  }

  .import-staging-peek {
    width: calc(100vw - 24px);
    max-height: 74vh;
  }

  .import-staging-peek__viewport {
    height: min(58vh, 460px);
  }

  .import-staging-doc__header {
    gap: 14px;
    flex-wrap: nowrap;
  }

  .import-staging-pages {
    grid-template-columns: repeat(auto-fill, minmax(86px, 1fr));
    gap: 7px;
  }
}

</style>
