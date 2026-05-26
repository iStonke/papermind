<template>
  <v-app
    class="papermind-app"
    :class="{ 'pm-no-animations': !settingsStore.animationsEnabled }"
    :data-color-variant="appColorVariant"
  >
    <v-app-bar class="app-topbar" flat height="64">
      <div class="appbar-layout">
        <div class="appbar-left app-title">
          <button type="button" class="app-title__brand app-title__brand-button" @click="openLibraryView">
            PaperMind
          </button>
        </div>

        <div class="appbar-center">
          <v-text-field
            ref="appBarSearchRef"
            v-model="searchText"
            class="appbar-search__field"
            prepend-inner-icon="mdi-magnify"
            clearable
            clear-icon="mdi-close"
            :placeholder="searchPlaceholder"
            density="compact"
            variant="outlined"
            :messages="searchHintMessages"
            hide-details="auto"
            @update:model-value="onAppBarSearchInput"
            @keydown="handleSearchShortcut"
            @click:clear="clearSearchFromInput"
          />
        </div>

        <div class="appbar-right appbar-actions">
          <v-menu v-if="pendingImportInboxCount > 0" location="bottom end" offset="8">
            <template #activator="{ props: importMenuProps }">
              <v-badge
                model-value
                :content="pendingImportInboxBadgeLabel"
                color="error"
                offset-x="3"
                offset-y="3"
              >
                <v-btn class="topbar-btn topbar-btn--import" variant="text" v-bind="importMenuProps">
                  <v-icon size="18" class="mr-1">mdi-tray-arrow-up</v-icon>
                  Importieren
                </v-btn>
              </v-badge>
            </template>
            <v-list density="compact" min-width="240">
              <v-list-item
                class="import-inbox-menu-item"
                prepend-icon="mdi-inbox-arrow-down-outline"
                :title="pendingImportInboxMenuTitle"
                @click="openImportInboxScans"
              />
              <v-divider />
              <v-list-item
                prepend-icon="mdi-file-upload-outline"
                title="PDF hochladen..."
                @click="openImportPdfPicker"
              />
            </v-list>
          </v-menu>
          <v-btn
            v-else
            class="topbar-btn topbar-btn--import"
            variant="text"
            @click="openImportPdfPicker"
          >
            <v-icon size="18" class="mr-1">mdi-tray-arrow-up</v-icon>
            Importieren
          </v-btn>

          <v-btn
            class="topbar-btn topbar-btn--import"
            :class="{ 'topbar-btn--active': isAiDialogOpen }"
            variant="text"
            @click="openAiView"
          >
            <v-icon size="18" class="mr-1">mdi-robot</v-icon>
            KI
          </v-btn>

          <v-btn
            class="topbar-btn topbar-btn--icon"
            variant="text"
            aria-label="Einstellungen"
            @click="openSettingsDialog"
          >
            <v-icon size="20">mdi-cog-outline</v-icon>
          </v-btn>
        </div>
      </div>
    </v-app-bar>

    <v-main class="app-main">
      <SettingsDialog
        v-model="isSettingsDialogOpen"
        @reload-imports="onSettingsReloadImports"
        @open-shortcuts="openShortcutsFromSettings"
      />
      <ShortcutsHelpDialog v-model="isShortcutsHelpDialogOpen" />
      <BatchTagDialog
        v-model="isBatchTagDialogOpen"
        :tags="tags"
        :count="selectionIds.size"
        :loading="isBatchTagSaving"
        @confirm="executeBatchTag"
      />

      <ImportStagingDialog
        ref="importStagingDialogRef"
        v-model="isUploadDialogOpen"
        :api-base-url="apiBaseUrl"
        :auto-ocr="settingsDraft.documents.auto_ocr"
        :auto-index="true"
        :auto-embed="true"
        @committed="onImportCommitted"
      />
      <input
        ref="importPdfInputRef"
        class="d-none"
        type="file"
        accept="application/pdf"
        multiple
        @change="onImportPdfInputChange"
      />

      <TagDialogs ref="tagDialogsRef" @tag-mutated="onTagMutated" />

      <DeleteDocumentDialog
        v-model="isDeleteDocumentDialogOpen"
        :document-name="formatDocumentTitle(deleteDocumentTarget)"
        @close="closeDeleteDocumentDialog"
        :loading="isDeletingDocument"
        @confirm="confirmDeleteDocumentFromDialog"
      />

      <RenameDocumentDialog ref="renameDocumentDialogRef" :api-base-url="apiBaseUrl" @saved="onDocumentRenamed" />

      <SmartFolderEditor
        v-model="isSmartFolderEditorOpen"
        :loading="isSavingSavedSearch"
        :mode="smartFolderEditorMode"
        :folder="smartFolderEditorTarget"
        :tags="tags"
        :api-base-url="apiBaseUrl"
        @save="handleSmartFolderSave"
        @close="closeSmartFolderEditor"
      />

      <AiDialog
        v-model="isAiDialogOpen"
        :api-base-url="apiBaseUrl"
        @open-citation="openCitation"
      />

      <div class="workspace">
        <AppSidebar
          :active-view="activeView"
          :active-saved-search-id="activeSavedSearchId"
          :active-tag-id="activeTagId"
          :is-tag-view="isTagView"
          @select-view="selectView"
          @open-saved-search="openSavedSearch"
          @create-folder="openCreateSavedSearchDialog"
          @edit-folder="openEditSavedSearchDialog"
          @delete-folder="deleteSavedSearch"
          @open-tags-view="openTagsView"
          @apply-tag-filter="applyTagFilterFromSidebar"
        />

        <section class="panel panel-middle">
          <Transition name="pm-panel">
            <div v-if="isTagView" key="tags" class="panel-middle__view tags-view">
              <div class="list-toolbar tags-view-toolbar">
                <div class="list-toolbar__main">
                  <v-text-field
                    ref="tagSearchField"
                    v-model="tagSearchText"
                    class="list-toolbar__search tags-view-search"
                    density="comfortable"
                    variant="outlined"
                    hide-details
                    prepend-inner-icon="mdi-magnify"
                    placeholder="Tags suchen oder erstellen…"
                    @keydown="handleTagToolbarShortcut"
                  >
                    <template #append-inner>
                      <div class="tags-view-search__actions">
                        <v-btn
                          v-if="hasTagToolbarQuery"
                          icon="mdi-close"
                          size="x-small"
                          variant="text"
                          class="tags-view-search__action-btn"
                          aria-label="Tag-Suche leeren"
                          @click.stop="clearTagToolbarQuery"
                        />
                        <v-btn
                          v-if="canCreateTagFromToolbar"
                          icon="mdi-plus"
                          size="x-small"
                          variant="text"
                          class="tags-view-search__action-btn tags-view-search__action-btn--create"
                          aria-label="Tag erstellen"
                          :loading="isTagMutationRunning"
                          @click.stop="createTagFromToolbar"
                        />
                      </div>
                    </template>
                  </v-text-field>
                </div>
                <div v-if="showTagToolbarCreateHint" class="tags-view-toolbar__hint">Enter ↵ zum Erstellen</div>
              </div>

              <div class="tags-view-cloud-wrap">
                <div class="tags-view-section-title">Tag-Wolke</div>
                <div v-if="filteredTags.length > 0" class="tag-cloud">
                  <button
                    v-for="tag in filteredTags"
                    :key="`cloud-${tag.id}`"
                    type="button"
                    class="tag-cloud-item"
                    :style="tagCloudItemStyle(tag)"
                    @click="openTagDocuments(tag.id)"
                  >
                    <span>{{ tag.name }}</span>
                    <small>{{ tag.usage_count ?? 0 }}</small>
                  </button>
                </div>
                <div v-else class="panel-empty">Keine Tags gefunden.</div>
              </div>

              <div class="tags-view-list-wrap">
                <div class="tags-view-section-title">Tag-Liste</div>
                <div v-if="filteredTags.length > 0" class="tag-table">
                  <div v-for="tag in filteredTags" :key="`row-${tag.id}`" class="tag-row">
                    <button type="button" class="tag-row__name" @click="openTagDocuments(tag.id)">
                      {{ tag.name }}
                    </button>
                    <span class="tag-row__count">{{ tag.usage_count ?? 0 }}</span>
                    <v-menu location="bottom end">
                      <template #activator="{ props }">
                        <v-btn icon="mdi-dots-vertical" size="small" variant="text" v-bind="props" />
                      </template>
                      <v-list density="compact">
                        <v-list-item @click.stop="tagDialogsRef?.openRename(tag)">
                          <template #prepend>
                            <v-icon size="16">mdi-pencil-outline</v-icon>
                          </template>
                          <v-list-item-title>Umbenennen</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click.stop="tagDialogsRef?.openMerge(tag)">
                          <template #prepend>
                            <v-icon size="16">mdi-source-merge</v-icon>
                          </template>
                          <v-list-item-title>Zusammenführen</v-list-item-title>
                        </v-list-item>
                        <v-list-item class="menu-item--danger" @click.stop="tagDialogsRef?.openDelete(tag)">
                          <template #prepend>
                            <v-icon size="16">mdi-trash-can-outline</v-icon>
                          </template>
                          <v-list-item-title>Löschen…</v-list-item-title>
                        </v-list-item>
                      </v-list>
                    </v-menu>
                  </div>
                </div>
                <div v-else class="panel-empty">Keine Tags verfügbar.</div>
              </div>
            </div>

            <DocumentListPanel
              v-else
              key="documents"
              class="panel-middle__view"
              :list-drop-notice="listDropNotice"
              :active-status-filter-label="activeStatusFilterLabel"
              :is-imports-view="isImportsView"
              :is-trash-view="isTrashView"
              :show-document-list-empty-state="showDocumentListEmptyState"
              :document-list-empty-state="documentListEmptyState"
              :show-snippets="showSnippets"
              :is-selection-mode="isSelectionMode"
              :selection-disabled="isAllDocumentsSelectionDisabled"
              :selection-ids="selectionIds"
              :current-sort="currentSort"
              :current-status="documentListQuery.status || ''"
              @select-document="selectDocument"
              @download="downloadDocumentFromList"
              @rename="(doc) => renameDocumentDialogRef?.open(doc)"
              @manage-tags="openTagManagerFromList"
              @delete="openDeleteDocumentDialog"
              @restore="restoreDocumentFromTrash"
              @delete-permanent="openPermanentDeleteDialog"
              @toggle-favorite="toggleDocumentFavorite"
              @files-dropped="onDroppedFiles"
              @toggle-selection-mode="toggleSelectionMode"
              @toggle-document-selection="toggleDocumentSelection"
              @select-all="selectAllDocuments"
              @change-sort="applySort"
              @change-status="applyStatusFilter"
            />
          </Transition>
          <BatchActionsBar
            v-if="isSelectionMode"
            :count="selectionIds.size"
            @tag="openBatchTagDialog"
            @delete="confirmBatchDelete"
          />
        </section>

        <section class="panel panel-right">
          <DocumentPreviewLayout
            class="panel-right__preview"
            :show-drawer="!isTagView && Boolean(selectedDocumentDetail)"
            :is-open="isDetailsDrawerOpen"
            :collapsed-height="DETAILS_DRAWER_COLLAPSED_HEIGHT"
          >
            <template #viewer>
              <PmEmptyState
                v-if="isTagView"
                icon="mdi-tag-multiple-outline"
                title="Tag-Ansicht aktiv"
                subtitle="Wähle einen Tag, um die Dokumentliste zu filtern."
                size="lg"
              />
              <div
                v-else-if="selectedDocumentId"
                class="preview-frame-wrap"
              >
                <PdfPreview
                  :key="previewRenderKey"
                  class="preview-frame"
                  :src="documentFileUrl(selectedDocumentId)"
                  :target-page="previewTargetPage"
                  :highlight-text="previewHighlightText"
                  @failed="onPreviewFrameError(selectedDocumentId)"
                  @loaded="onPreviewFrameLoad(selectedDocumentId)"
                />
              </div>
              <PmEmptyState
                v-else
                icon="mdi-file-document-outline"
                title="Kein Dokument ausgewählt"
                subtitle="Wähle ein Dokument aus der Liste, um die Vorschau zu öffnen."
                size="lg"
              />
            </template>

            <template #drawer-header>
              <div
                class="details-drawer__header"
                :class="isDetailsDrawerOpen ? 'details-drawer__header--expanded' : 'details-drawer__header--collapsed'"
                @click="handleDetailsDrawerHeaderClick"
              >
                <div class="details-drawer__inner">
                  <div class="details-command-bar">
                    <div class="details-command-bar__left">
                      <div class="details-drawer__title-row">
                        <div class="details-drawer__title-wrap">
                          <div v-if="selectedDocumentDetail" class="details-drawer__subtitle">
                            {{ formatDocumentTitle(selectedDocumentDetail) }}
                          </div>
                          <div v-if="headerMetaParts.length" class="details-drawer__meta-line">
                            <template v-for="(part, index) in headerMetaParts" :key="`meta-${index}`">
                              <span class="details-drawer__meta-part">{{ part }}</span>
                              <span
                                v-if="index < headerMetaParts.length - 1"
                                class="details-drawer__meta-dot"
                                aria-hidden="true"
                              />
                            </template>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="details-command-bar__right" @click.stop>
                      <v-chip
                        v-if="showGreenOcrChip"
                        size="x-small"
                        variant="tonal"
                        color="success"
                        class="details-ocr-chip"
                      >
                        OCR
                      </v-chip>
                      <v-btn
                        v-else-if="showHeaderOcrActionButton"
                        size="x-small"
                        density="comfortable"
                        variant="tonal"
                        color="primary"
                        class="details-ocr-action-btn"
                        :loading="isQueueingHeaderOcr"
                        :disabled="isQueueingHeaderOcr || hasActiveOcrJob || !selectedDocumentDetail"
                        @click="queueOcrFromHeader"
                      >
                        OCR durchführen
                      </v-btn>

                      <v-btn
                        :icon="detailsDrawerChevronIcon"
                        size="small"
                        density="comfortable"
                        variant="text"
                        class="details-chevron-btn"
                        :class="{ 'details-chevron-btn--expanded': isDetailsDrawerChevronExpanded }"
                        aria-label="Details ein- oder ausklappen"
                        :disabled="isDrawerAlwaysExpanded"
                        @click="toggleDetailsDrawer"
                      />
                    </div>
                  </div>

                  <v-progress-linear
                    v-if="showHeaderProgress"
                    :model-value="headerProgressValue"
                    color="primary"
                    height="3"
                    rounded
                    class="details-header-progress"
                  />
                </div>
              </div>
            </template>

            <template #drawer-body>
              <div v-if="selectedDocumentDetail" class="details-drawer__body">
                <div class="details-drawer__inner pm-drawer-body">
                  <div class="pm-drawer-section">
                    <div class="pm-label">Dokumentdatum</div>
                    <v-text-field
                      v-model="metadataDocDate"
                      class="pm-date-field"
                      density="compact"
                      variant="outlined"
                      placeholder="TT.MM.JJJJ"
                      inputmode="numeric"
                      maxlength="10"
                      hide-details
                      :error="metadataDocDateHasError"
                      @blur="handleDocumentDateBlur"
                      @keydown="handleDocumentDateShortcut"
                    />
                  </div>

                  <div class="pm-drawer-section">
                    <div class="pm-label">Tags</div>
                    <div class="details-tags-row">
                      <v-combobox
                        ref="metadataTagsCombobox"
                        v-model="metadataTagNames"
                        v-model:search="metadataTagSearch"
                        :items="allTagNames"
                        multiple
                        chips
                        closable-chips
                        hide-selected
                        :clearable="false"
                        density="compact"
                        variant="outlined"
                        hide-details="auto"
                        class="details-tags-combobox"
                        placeholder="Tag hinzufügen…"
                        :loading="isSavingTags || isRunningManualAutoTagging"
                        :disabled="isRunningManualAutoTagging"
                        :menu-props="{
                          maxHeight: 180,
                          offset: 10,
                          closeOnContentClick: false,
                          attach: 'body',
                          zIndex: 6000,
                          contentClass: 'pm-menu pm-menu--tags'
                        }"
                        @update:model-value="onMetadataTagNamesChange"
                        @keydown="handleMetadataTagShortcut"
                      />
                      <v-btn
                        size="x-small"
                        density="comfortable"
                        variant="text"
                        class="details-tags-ai-btn"
                        :loading="isRunningManualAutoTagging"
                        :disabled="isRunningManualAutoTagging || isSavingTags || !selectedDocumentDetail"
                        aria-label="Tags per KI analysieren"
                        @click="runManualAutoTagging"
                      >
                        <v-icon size="15">mdi-robot-outline</v-icon>
                      </v-btn>
                    </div>
                  </div>

                  <div class="pm-drawer-section">
                    <div class="pm-label">Notizen</div>
                    <v-textarea
                      v-model="metadataNotes"
                      :rows="1"
                      :max-rows="5"
                      auto-grow
                      density="compact"
                      variant="outlined"
                      placeholder="Notiz hinzufügen…"
                      hide-details
                      class="pm-notes-field"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="panel-empty details-drawer__empty">
                Dokument auswählen, um Metadaten zu bearbeiten.
              </div>
            </template>
          </DocumentPreviewLayout>
        </section>
      </div>

      <NotificationStack />
    </v-main>
  </v-app>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useTheme } from 'vuetify';
import BaseDialog from './components/BaseDialog.vue';
import PmEmptyState from './components/PmEmptyState.vue';
import DeleteDocumentDialog from './components/DeleteDocumentDialog.vue';
import DocumentPreviewLayout from './components/DocumentPreviewLayout.vue';
import ImportStagingDialog from './components/ImportStagingDialog.vue';
import NotificationStack from './components/NotificationStack.vue';
import AppSidebar from './components/AppSidebar.vue';
import DocumentListPanel from './components/DocumentListPanel.vue';
import BatchActionsBar from './components/BatchActionsBar.vue';
import BatchTagDialog from './components/BatchTagDialog.vue';
import SmartFolderEditor from './components/SmartFolderEditor.vue';
import TagDialogs from './components/TagDialogs.vue';
import RenameDocumentDialog from './components/RenameDocumentDialog.vue';
import AiDialog from './components/AiDialog.vue';
import SettingsDialog from './components/SettingsDialog.vue';
import ShortcutsHelpDialog from './components/ShortcutsHelpDialog.vue';
import { mapApiError, notifyError, logDevError, useNotifications } from './stores/notifications';
import { useSettingsStore } from './stores/settings';
import { useDocumentStore } from './stores/documents';
import { useTagStore } from './stores/tags';
import { useSidebarStore } from './stores/sidebar';
import {
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildDrawerAlwaysExpandedPatch,
  buildDrawerRememberStatePatch,
  buildRecentImportWindowPatch,
  buildShowFilenameSuffixPatch,
  buildSortOrderPatch,
  buildThemeModePatch
} from './utils/settingsApi';
import { formatDateTime, formatDocumentDateInputFromIso, parseDocumentDateInput } from './utils/dates';
import { useOcrPolling } from './composables/useOcrPolling';
import { useGlobalKeyboard } from './composables/useGlobalKeyboard';
import { useSearch } from './composables/useSearch';
import { SHORTCUT_ACTIONS, handleShortcut } from './keyboard/shortcuts';
import { getBaseUrl } from './api/client.js';
import { claimImportInboxItems, getImportInbox } from './api/importInbox.js';
import { applyPaperMindVuetifyColors, resolvePaperMindColorVariant } from './theme/tokens';

const PdfPreview = defineAsyncComponent(() => import('./components/PdfPreview.vue'));

const apiBaseUrl = getBaseUrl();

const SETTINGS_SORT_TO_QUERY = {
  newest: { sort: 'created_at', order: 'desc' },
  oldest: { sort: 'created_at', order: 'asc' },
  document_date_desc: { sort: 'document_date', order: 'desc' },
  document_date_asc: { sort: 'document_date', order: 'asc' },
  name_asc: { sort: 'name', order: 'asc' },
  name_desc: { sort: 'name', order: 'desc' },
  last_opened: { sort: 'updated_at', order: 'desc' },
  favorites: { sort: 'favorite', order: 'desc' }
};

const TAG_REPLACE_DEBOUNCE_MS = 300;
const METADATA_AUTOSAVE_DEBOUNCE_MS = 450;
const PREVIEW_RETRY_BASE_DELAY_MS = 600;
const PREVIEW_RETRY_MAX_DELAY_MS = 4500;
const PREVIEW_RETRY_MAX_ATTEMPTS = 5;
const IMPORTS_RECENT_LIMIT = 100;

const DETAILS_DRAWER_COLLAPSED_HEIGHT = 72;
const LAST_SELECTED_DOC_KEY = 'pm.lastSelectedDocumentId';

function readStoredLastSelectedDocId() {
  try { return window.localStorage.getItem(LAST_SELECTED_DOC_KEY) || null; } catch { return null; }
}

function persistLastSelectedDocId(id) {
  try {
    if (id) window.localStorage.setItem(LAST_SELECTED_DOC_KEY, String(id));
    else     window.localStorage.removeItem(LAST_SELECTED_DOC_KEY);
  } catch { /* ignore */ }
}

let isRestoringLastSelectedDocument = false;

const theme = useTheme();
const { notify } = useNotifications();
const settingsStore = useSettingsStore();
const appSettings = computed(() => settingsStore.settings);
const settingsDraft = settingsStore.settingsDraft;
const appColorVariant = computed(() => resolvePaperMindColorVariant(settingsDraft.ui.color_variant));
const showPdfSuffix = computed(() => settingsStore.settingsDraft.ui.showFilenameSuffix);

// ── Domain Stores ────────────────────────────────────────────────────────
const docStore     = useDocumentStore();
const tagStore     = useTagStore();
const sidebarStore = useSidebarStore();

const { documents, selectedDocumentId, selectedDocumentDetail, isLoadingDocuments } = storeToRefs(docStore);
const { tags, isTagMutationRunning } = storeToRefs(tagStore);

// Letztes Dokument persistent speichern
watch(selectedDocumentId, (id) => {
  if (isRestoringLastSelectedDocument) {
    return;
  }
  persistLastSelectedDocId(id);
});
const { sidebarCounts, isLoadingSidebarCounts, savedSearches, isLoadingSavedSearches } = storeToRefs(sidebarStore);

const isAiDialogOpen = ref(false);
const activeView = ref('all');
const activeSavedSearchId = ref(null);
const activeSavedSearchQuery = ref(null);
const documentListQuery = reactive({
  q: null,
  tagId: null,
  untagged: null,
  status: null,
  dateFrom: null,
  dateTo: null,
  sort: 'created_at',
  order: 'desc',
  limit: 100,
  offset: 0
});
const activeTagId = computed({
  get: () => documentListQuery.tagId,
  set: (value) => {
    documentListQuery.tagId = value || null;
  }
});
const tagSearchText = ref('');

const tagSearchField = ref(null);
const isSavingSavedSearch = ref(false);
const isSmartFolderEditorOpen = ref(false);
const smartFolderEditorMode = ref('create');
const smartFolderEditorTarget = ref(null);

const tagDialogsRef = ref(null);

const previewTargetPage    = ref(null);
const previewHighlightText = ref('');



const importStagingDialogRef = ref(null);
const importPdfInputRef = ref(null);
const isSettingsDialogOpen = ref(false);
const isShortcutsHelpDialogOpen = ref(false);
const importInboxItems = ref([]);
const isImportInboxLoading = ref(false);
const importInboxSuppressedItemIds = ref(new Set());
const activeImportInboxItemIds = ref(new Set());
const isClaimingImportInbox = ref(false);

// ── Batch-Auswahl ──────────────────────────────────────────────────────────
const isSelectionMode = ref(false);
const selectionIds    = ref(new Set());

function toggleSelectionMode() {
  if (!isSelectionMode.value && isAllDocumentsSelectionDisabled.value) {
    return;
  }
  isSelectionMode.value = !isSelectionMode.value;
  if (!isSelectionMode.value) selectionIds.value = new Set();
}

function exitSelectionMode() {
  isSelectionMode.value = false;
  selectionIds.value = new Set();
}

function toggleDocumentSelection(id) {
  const next = new Set(selectionIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selectionIds.value = next;
}

// ── Toolbar-Aktionen ───────────────────────────────────────────────────────
function isFavoriteSortQuery(sort = documentListQuery.sort, order = documentListQuery.order) {
  return (sort === 'favorite' || sort === 'is_favorite') && order === 'desc';
}

const currentSort = computed(() => {
  if (isFavoriteSortQuery()) {
    return 'favorites';
  }
  const entry = Object.entries(SETTINGS_SORT_TO_QUERY).find(
    ([, v]) => v.sort === documentListQuery.sort && v.order === documentListQuery.order
  );
  return entry ? entry[0] : 'newest';
});

function applySort(sortKey) {
  const mapping = SETTINGS_SORT_TO_QUERY[sortKey];
  if (!mapping) return;
  documentListQuery.sort  = mapping.sort;
  documentListQuery.order = mapping.order;
  void fetchDocuments(selectedDocumentId.value);
}

function applyStatusFilter(status) {
  documentListQuery.status = status || null;
  void fetchDocuments(null, { autoSelectFirst: false });
}

function selectAllDocuments() {
  selectionIds.value = new Set(docStore.documents.map((d) => d.id));
}

// ── Batch Tag-Dialog ───────────────────────────────────────────────────────
const isBatchTagDialogOpen  = ref(false);
const isBatchTagSaving      = ref(false);

function openBatchTagDialog() {
  if (selectionIds.value.size === 0) return;
  isBatchTagDialogOpen.value = true;
}

async function executeBatchTag(tagIdsToAdd) {
  if (!tagIdsToAdd?.length || selectionIds.value.size === 0) return;
  isBatchTagSaving.value = true;
  const ids = Array.from(selectionIds.value);
  try {
    // Alle Dokumente sequenziell taggen; bestehende Tags erhalten (union)
    for (const docId of ids) {
      const doc = docStore.documents.find((d) => d.id === docId);
      const existingTagIds = (doc?.tags || []).map((t) => t.id);
      const mergedTagIds = Array.from(new Set([...existingTagIds, ...tagIdsToAdd]));
      await fetch(`${apiBaseUrl}/api/documents/${docId}/tags`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag_ids: mergedTagIds }),
      });
    }
    notify({ type: 'success', title: 'Tags', message: `${ids.length} ${ids.length === 1 ? 'Dokument' : 'Dokumente'} getaggt.` });
    isBatchTagDialogOpen.value = false;
    exitSelectionMode();
    await fetchDocuments(selectedDocumentId.value);
    await fetchTags();
  } catch (error) {
    notifyError(error, 'Tags konnten nicht gespeichert werden.');
  } finally {
    isBatchTagSaving.value = false;
  }
}

// ── Batch Löschen ──────────────────────────────────────────────────────────
const isBatchDeleting = ref(false);

async function confirmBatchDelete() {
  if (selectionIds.value.size === 0) return;
  const ids = Array.from(selectionIds.value);
  const count = ids.length;
  const confirmed = window.confirm(
    `${count} ${count === 1 ? 'Dokument' : 'Dokumente'} in den Papierkorb verschieben?`
  );
  if (!confirmed) return;
  isBatchDeleting.value = true;
  try {
    for (const docId of ids) {
      await fetch(`${apiBaseUrl}/api/documents/${docId}/trash`, { method: 'POST' });
    }
    notify({ type: 'success', title: 'Papierkorb', message: `${count} ${count === 1 ? 'Dokument' : 'Dokumente'} verschoben.` });
    exitSelectionMode();
    if (ids.includes(selectedDocumentId.value)) {
      selectedDocumentId.value = null;
      selectedDocumentDetail.value = null;
      isDetailsDrawerOpen.value = false;
    }
    await fetchDocuments(selectedDocumentId.value);
    scheduleSidebarCountsRefresh();
    await fetchTags();
  } catch (error) {
    notifyError(error, 'Dokumente konnten nicht in den Papierkorb verschoben werden.');
  } finally {
    isBatchDeleting.value = false;
  }
}

const isUploadDialogOpen = ref(false);
const listDropNotice = ref('');
const previewReloadNonce = ref(0);

const isDetailsDrawerOpen = computed({
  get: () => settingsStore.drawerExpanded,
  set: (value) => {
    settingsStore.setDrawerExpanded(value);
  }
});
const isDrawerAlwaysExpanded = computed(() => appSettings.value.ui.drawerAlwaysExpanded);
const isDetailsDrawerChevronExpanded = computed(() => isDrawerAlwaysExpanded.value || isDetailsDrawerOpen.value);
const detailsDrawerChevronIcon = computed(() =>
  isDetailsDrawerChevronExpanded.value ? 'mdi-chevron-down' : 'mdi-chevron-up'
);
const metadataTagsCombobox = ref(null);

const metadataDocDate = ref('');
const metadataDocDateHasError = ref(false);
const metadataNotes = ref('');
const metadataTagIds = ref([]);
const metadataTagNames = ref([]);
const metadataTagSearch = ref('');
const isSavingMetadata = ref(false);
const isSavingTags = ref(false);
const isRunningManualAutoTagging = ref(false);
const isQueueingHeaderOcr = ref(false);
const metadataSuccessMessage = ref('');
const metadataErrorMessage = ref('');
const metadataTagErrorMessage = ref('');
const isDeleteDocumentDialogOpen = ref(false);
const deleteDocumentTarget = ref(null);
const isDeletingDocument = ref(false);
const permanentDeleteMode = ref(false); // true → endgültig löschen, false → in Papierkorb
const renameDocumentDialogRef = ref(null);

const latestOcrJob = computed(() => {
  if (!selectedDocumentDetail.value?.jobs?.length) {
    return null;
  }
  const jobs = selectedDocumentDetail.value.jobs
    .filter((job) => job.type === 'OCR')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  return jobs[0] || null;
});

const hasActiveOcrJob = computed(() => {
  const statusValue = latestOcrJob.value?.status;
  return statusValue === 'queued' || statusValue === 'running';
});

const ocrStatusValue = computed(() => {
  if (selectedDocumentDetail.value?.ocr_status) {
    return selectedDocumentDetail.value.ocr_status;
  }
  if (latestOcrJob.value?.status === 'running') {
    return 'running';
  }
  if (latestOcrJob.value?.status === 'queued') {
    return 'queued';
  }
  if (latestOcrJob.value?.status === 'done') {
    return 'done';
  }
  if (latestOcrJob.value?.status === 'failed') {
    return 'failed';
  }
  return 'not_started';
});

const headerProgressValue = computed(() => latestOcrJob.value?.progress ?? 0);
const showHeaderProgress = computed(() => selectedDocumentDetail.value?.status === 'processing');
const headerPageCountLabel = computed(() => {
  const raw = Number(selectedDocumentDetail.value?.page_count);
  if (!Number.isFinite(raw) || raw <= 0) {
    return '';
  }
  const pages = Math.round(raw);
  return pages === 1 ? '1 Seite' : `${pages} Seiten`;
});
const headerCreatedDateLabel = computed(() => {
  const raw = selectedDocumentDetail.value?.created_at;
  if (!raw) {
    return '';
  }
  const formattedDateTime = formatDateTime(raw);
  return formattedDateTime === '-' ? '' : formattedDateTime;
});
const headerMetaParts = computed(() => {
  const parts = [];
  if (headerPageCountLabel.value) {
    parts.push(headerPageCountLabel.value);
  }
  if (headerCreatedDateLabel.value) {
    parts.push(headerCreatedDateLabel.value);
  }
  return parts;
});
const hasCompletedOcr = computed(() => {
  const detail = selectedDocumentDetail.value;
  if (!detail) {
    return false;
  }
  if (detail.ocr_status === 'done' || detail.text_source === 'ocr') {
    return true;
  }
  if (hasOcrFile(detail)) {
    return true;
  }
  return Boolean(detail.jobs?.some((job) => job.type === 'OCR' && job.status === 'done'));
});
const showGreenOcrChip = computed(() => {
  const detail = selectedDocumentDetail.value;
  if (!detail) {
    return false;
  }
  const isTextBased = detail.text_source === 'embedded';
  return isTextBased || hasCompletedOcr.value;
});
const showHeaderOcrActionButton = computed(() => {
  return Boolean(selectedDocumentDetail.value) && !showGreenOcrChip.value;
});
const isTagView       = computed(() => activeView.value === 'tags');
const isImportsView   = computed(() => activeView.value === 'imports');
const isUntaggedView  = computed(() => activeView.value === 'untagged');
const isFavoritesView = computed(() => activeView.value === 'favorites');
const isTrashView     = computed(() => activeView.value === 'trash');
const isAllDocumentsSelectionDisabled = computed(() => {
  return activeView.value === 'all' &&
    !isLoadingSidebarCounts.value &&
    Number(sidebarCounts.value.all_documents || 0) <= 0;
});
const tagNameCollator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });
const sortedTagsByName = computed(() => {
  return [...tags.value].sort((left, right) => {
    const leftName = normalizeTagInput(left?.name || '');
    const rightName = normalizeTagInput(right?.name || '');
    return tagNameCollator.compare(leftName, rightName);
  });
});
const allTagNames = computed(() => sortedTagsByName.value.map((tag) => tag.name));
const filteredTags = computed(() => {
  const query = tagSearchText.value.trim().toLocaleLowerCase('de-DE');
  if (!query) {
    return sortedTagsByName.value;
  }
  return sortedTagsByName.value.filter((tag) => tag.name.toLocaleLowerCase('de-DE').includes(query));
});
const normalizedTagToolbarQuery = computed(() => normalizeTagInput(tagSearchText.value));
const hasTagToolbarQuery = computed(() => normalizedTagToolbarQuery.value.length > 0);
const canCreateTagFromToolbar = computed(() => hasTagToolbarQuery.value && !findTagByName(normalizedTagToolbarQuery.value));
const showTagToolbarCreateHint = computed(
  () => canCreateTagFromToolbar.value && filteredTags.value.length === 0
);
const maxTagUsageCount = computed(() => {
  if (!sortedTagsByName.value.length) {
    return 1;
  }
  return Math.max(...sortedTagsByName.value.map((tag) => Number(tag.usage_count || 0)), 1);
});
const activeTagFilterName = computed(() => {
  if (!documentListQuery.tagId) {
    return '';
  }
  return tags.value.find((tag) => tag.id === documentListQuery.tagId)?.name || '';
});
const activeStatusFilterLabel = computed(() => {
  switch (documentListQuery.status) {
    case 'imported':
      return 'Importiert';
    case 'processing':
      return 'Verarbeitung';
    case 'ready':
      return 'Bereit';
    case 'failed':
      return 'Fehler';
    default:
      return '';
  }
});
const activeSavedSearch = computed(() => {
  if (!activeSavedSearchId.value) {
    return null;
  }
  return savedSearches.value.find((item) => item.id === activeSavedSearchId.value) || null;
});
const activeSavedSearchName = computed(() => activeSavedSearch.value?.name || '');

const previewRenderKey = computed(() => {
  if (!selectedDocumentId.value) {
    return `empty:${previewReloadNonce.value}`;
  }
  return `${selectedDocumentId.value}:${previewReloadNonce.value}`;
});
const hasActiveListFilter = computed(() => {
  return Boolean(
    activeSavedSearchId.value ||
      (documentListQuery.q || '').trim() ||
      documentListQuery.tagId ||
      documentListQuery.untagged ||
      documentListQuery.status ||
      documentListQuery.dateFrom ||
      documentListQuery.dateTo
  );
});
const showDocumentListEmptyState = computed(() => !isLoadingDocuments.value && documents.value.length === 0);
const recentImportWindowLabel = computed(() => {
  const parsedHours = Number(appSettings.value?.documents?.recent_import_window_hours || 24);
  const hours = Number.isFinite(parsedHours) && parsedHours > 0 ? Math.round(parsedHours) : 24;
  return hours === 1 ? '1 Stunde' : `${hours} Stunden`;
});
const documentListEmptyState = computed(() => {
  if (isUntaggedView.value) {
    return {
      icon: 'mdi-tag-off-outline',
      title: 'Keine ungetaggten Dokumente',
      subtitle: 'Alle Dokumente haben bereits Tags.'
    };
  }
  if (isImportsView.value) {
    return {
      icon: 'mdi-tray-arrow-down',
      title: 'Keine zuletzt hinzugefügten Dokumente',
      subtitle: `Keine Importe in den letzten ${recentImportWindowLabel.value}.`
    };
  }
  if (isFavoritesView.value) {
    return {
      icon: 'mdi-star-outline',
      title: 'Noch keine Favoriten',
      subtitle: 'Klicke den Stern neben einem Dokument, um es als Favorit zu markieren.'
    };
  }
  if (isTrashView.value) {
    return {
      icon: 'mdi-trash-can-outline',
      title: 'Papierkorb ist leer',
      subtitle: 'Gelöschte Dokumente erscheinen hier.'
    };
  }
  if (hasActiveListFilter.value) {
    return {
      icon: 'mdi-magnify',
      title: 'Keine Treffer',
      subtitle: 'Passe deine Suche oder Filter an.'
    };
  }
  return {
    icon: 'mdi-file-document-outline',
    title: 'Noch keine Dokumente vorhanden',
    subtitle: 'Importiere dein erstes PDF, um loszulegen.'
  };
});
const documentListSavedQueryKey = computed(() =>
  JSON.stringify({
    q: documentListQuery.q,
    tagId: documentListQuery.tagId,
    untagged: documentListQuery.untagged,
    status: documentListQuery.status,
    dateFrom: documentListQuery.dateFrom,
    dateTo: documentListQuery.dateTo,
    sort: documentListQuery.sort,
    order: documentListQuery.order,
    limit: documentListQuery.limit,
    offset: documentListQuery.offset
  })
);
const documentListQueryReloadKey = computed(() =>
  JSON.stringify({
    q: documentListQuery.q,
    tagId: documentListQuery.tagId,
    untagged: documentListQuery.untagged,
    status: documentListQuery.status,
    dateFrom: documentListQuery.dateFrom,
    dateTo: documentListQuery.dateTo,
    sort: documentListQuery.sort,
    order: documentListQuery.order,
    limit: documentListQuery.limit,
    offset: documentListQuery.offset,
    recentImports: isImportsView.value,
    favoritesOnly: isFavoritesView.value,
    inTrash: isTrashView.value
  })
);
const isMetadataDirty = computed(() => {
  if (!selectedDocumentDetail.value) {
    return false;
  }

  const detailDate = selectedDocumentDetail.value.document_date || '';
  const detailNotes = selectedDocumentDetail.value.notes || '';
  const parsedDocumentDate = parseDocumentDateInput(metadataDocDate.value);
  const draftDate = parsedDocumentDate.ok
    ? parsedDocumentDate.iso || ''
    : `invalid:${String(metadataDocDate.value || '').trim()}`;

  if (draftDate !== detailDate) {
    return true;
  }
  return (metadataNotes.value || '') !== detailNotes;
});

let mediaQuery = null;
let tagReplaceDebounceTimer = null;
let metadataAutosaveDebounceTimer = null;
let previewRetryTimer = null;
let listDropNoticeTimer = null;
let importInboxPollTimer = null;
// sidebarCountsRefreshTimer → jetzt in useSidebarStore verwaltet
let shouldSkipTagAutosave = false;
let shouldSkipMetadataAutosave = false;
let shouldRunMetadataAutosaveAfterSave = false;
let isApplyingSavedSearchQuery = false;
let shouldSkipTagNameSync = false;
const previewRetryAttemptsByDocument = ref({});

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyColorVariant(variant) {
  applyPaperMindVuetifyColors(theme, variant);
}

function applyThemeFromSettings() {
  theme.global.name.value = resolveThemeName(appSettings.value.ui.theme_mode);
  applyColorVariant(appSettings.value.ui.color_variant || 'slate');
}

watch(
  () => settingsStore.settingsDraft.ui.color_variant,
  (variant) => {
    applyColorVariant(variant || 'slate');
  }
);

// ── Sidebar-Counts ────────────────────────────────────────────────────────

async function fetchSidebarCounts() {
  await sidebarStore.fetchCounts();
}

function scheduleSidebarCountsRefresh() {
  sidebarStore.scheduleCounts();
}

const pendingImportInboxCount = computed(() => importInboxItems.value.length);
const pendingImportInboxBadgeLabel = computed(() => {
  const count = pendingImportInboxCount.value;
  return count > 99 ? '99+' : String(count);
});
const pendingImportInboxMenuTitle = computed(() => {
  const count = pendingImportInboxCount.value;
  return count === 1 ? 'Neuen Scan anzeigen' : `Neue Scans anzeigen (${count})`;
});

function normalizeImportInboxItems(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items
    .map((item) => ({
      id: String(item?.id || '').trim(),
      source_file_id: String(item?.source_file_id || '').trim(),
      original_name: String(item?.original_name || '').trim() || 'Scan Upload.pdf',
      page_count: Number(item?.page_count || 0),
      client_name: String(item?.client_name || '').trim(),
      created_at: String(item?.created_at || '')
    }))
    .filter(
      (item) =>
        item.id &&
        item.source_file_id &&
        item.page_count > 0 &&
        !importInboxSuppressedItemIds.value.has(item.id)
    );
}

async function refreshImportInbox({ silent = true } = {}) {
  if (isImportInboxLoading.value) {
    return;
  }
  isImportInboxLoading.value = true;
  try {
    const payload = await getImportInbox({ limit: 50 });
    importInboxItems.value = normalizeImportInboxItems(payload);
  } catch (error) {
    if (!silent) {
      notify({ type: 'error', message: mapApiError(error, 'Neue Scans konnten nicht geladen werden.') });
    }
  } finally {
    isImportInboxLoading.value = false;
  }
}

function startImportInboxPolling() {
  if (importInboxPollTimer) {
    window.clearInterval(importInboxPollTimer);
  }
  void refreshImportInbox({ silent: true });
  importInboxPollTimer = window.setInterval(() => {
    void refreshImportInbox({ silent: true });
  }, 7000);
}

async function openImportInboxScans() {
  await refreshImportInbox({ silent: false });
  const items = importInboxItems.value.slice();
  if (items.length === 0) {
    notify({ type: 'info', message: 'Keine neuen Scans verfügbar.' });
    return;
  }

  const dialogRef = importStagingDialogRef.value;
  if (!dialogRef || typeof dialogRef.openWithRemoteSources !== 'function') {
    isUploadDialogOpen.value = true;
    return;
  }

  try {
    await dialogRef.openWithRemoteSources({
      sources: items,
      sessionId: 'import-inbox'
    });
    const itemIds = items.map((item) => item.id).filter(Boolean);
    if (itemIds.length > 0) {
      const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
      const nextActive = new Set(activeImportInboxItemIds.value);
      for (const itemId of itemIds) {
        nextSuppressed.add(itemId);
        nextActive.add(itemId);
      }
      importInboxSuppressedItemIds.value = nextSuppressed;
      activeImportInboxItemIds.value = nextActive;
      importInboxItems.value = importInboxItems.value.filter((item) => !nextSuppressed.has(item.id));
    }
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Neue Scans konnten nicht übernommen werden.') });
  }
}

async function claimActiveImportInboxItems() {
  const itemIds = Array.from(activeImportInboxItemIds.value);
  if (itemIds.length === 0) {
    return;
  }
  isClaimingImportInbox.value = true;
  try {
    await claimImportInboxItems(itemIds);
    activeImportInboxItemIds.value = new Set();
    const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
    for (const itemId of itemIds) {
      nextSuppressed.delete(itemId);
    }
    importInboxSuppressedItemIds.value = nextSuppressed;
    await refreshImportInbox({ silent: true });
  } catch (error) {
    notify({ type: 'warning', message: mapApiError(error, 'Import-Inbox konnte nicht aktualisiert werden.') });
  } finally {
    isClaimingImportInbox.value = false;
  }
}

watch(isUploadDialogOpen, (open) => {
  if (open || isClaimingImportInbox.value || activeImportInboxItemIds.value.size === 0) {
    return;
  }
  const itemIds = Array.from(activeImportInboxItemIds.value);
  activeImportInboxItemIds.value = new Set();
  const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
  for (const itemId of itemIds) {
    nextSuppressed.delete(itemId);
  }
  importInboxSuppressedItemIds.value = nextSuppressed;
  void refreshImportInbox({ silent: true });
});

// ── Navigation ────────────────────────────────────────────────────────────

function openAiView() {
  isAiDialogOpen.value = true;
}

function openLibraryView() {
  leaveActiveSavedSearch();
  selectView('all');
}

// ── Tag-Hilfsfunktionen ───────────────────────────────────────────────────

async function createTagByName(rawName) {
  const result = await tagStore.createTagByName(normalizeTagInput(rawName));
  if (result.ok) {
    await fetchTags();
    scheduleSidebarCountsRefresh();
  }
  return result;
}

async function ensureTagIdByName(typedName) {
  isSavingTags.value = true;
  try {
    const id = await tagStore.ensureTagIdByName(normalizeTagInput(typedName));
    if (id) { await fetchTags(); scheduleSidebarCountsRefresh(); }
    return id;
  } catch (error) {
    metadataTagErrorMessage.value = notifyError(error, 'Tag konnte nicht erstellt werden.');
    return '';
  } finally {
    isSavingTags.value = false;
  }
}

async function syncMetadataTagsFromNames(nextNames) {
  if (!selectedDocumentDetail.value) return;
  const normalizedNames = normalizeTagNames(nextNames);
  metadataTagErrorMessage.value = '';

  const resolvedTagIds = [];
  for (const name of normalizedNames) {
    let tagId = findTagByName(name)?.id || '';
    if (!tagId) tagId = await ensureTagIdByName(name);
    if (!tagId) continue;
    resolvedTagIds.push(tagId);
  }

  const canonicalIds = normalizeTagIds(resolvedTagIds);
  const canonicalNames = canonicalIds.map((id) => tags.value.find((t) => t.id === id)?.name || id);
  const sanitizedNames = normalizeTagNames(canonicalNames);

  shouldSkipTagNameSync = true;
  metadataTagNames.value = sanitizedNames;
  window.setTimeout(() => { shouldSkipTagNameSync = false; }, 0);
  metadataTagIds.value = canonicalIds;
}

async function createTagFromToolbar() {
  if (!canCreateTagFromToolbar.value || isTagMutationRunning.value) return;
  isTagMutationRunning.value = true;
  try {
    const result = await createTagByName(tagSearchText.value);
    if (!result.ok) return;
    notify({ type: 'success', title: 'Tag', message: `Tag "${result.name}" erstellt.` });
    clearTagToolbarQuery();
    await nextTick();
    tagSearchField.value?.focus?.();
  } catch (error) {
    notifyError(error, 'Tag konnte nicht erstellt werden.');
  } finally {
    isTagMutationRunning.value = false;
  }
}

// ── Tag-Toolbar & Metadaten-Combobox Handler ──────────────────────────────

function clearTagToolbarQuery() {
  tagSearchText.value = '';
}

function onTagToolbarEnter() {
  if (!canCreateTagFromToolbar.value || isTagMutationRunning.value) return;
  void createTagFromToolbar();
}

function handleSearchShortcut(event) {
  if (handleShortcut(event, SHORTCUT_ACTIONS.SEARCH_SUBMIT, triggerSearchNow, { ignoreEditable: false })) {
    return;
  }
  handleShortcut(event, SHORTCUT_ACTIONS.SEARCH_CANCEL, handleSearchEscape, { ignoreEditable: false });
}

function handleTagToolbarShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, onTagToolbarEnter, { ignoreEditable: false });
}

async function onMetadataTagNamesChange(nextValues) {
  if (shouldSkipTagNameSync || !selectedDocumentDetail.value) return;
  await syncMetadataTagsFromNames(nextValues);
}

async function handleMetadataTagEnter() {
  if (!selectedDocumentDetail.value) return;
  const normalizedNames = normalizeTagNames([...metadataTagNames.value, metadataTagSearch.value]);
  if (!normalizedNames.length) return;
  await syncMetadataTagsFromNames(normalizedNames);
  metadataTagSearch.value = '';
}

function handleMetadataTagShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, handleMetadataTagEnter, {
    ignoreEditable: false,
    stop: true
  });
}

function resolveDefaultSortQuery() {
  const fromSettings = SETTINGS_SORT_TO_QUERY[appSettings.value.documents.sort_order];
  if (fromSettings) {
    return fromSettings;
  }
  return SETTINGS_SORT_TO_QUERY.newest;
}

function applyDefaultSortToQuery(options = {}) {
  const resolved = resolveDefaultSortQuery();
  patchDocumentListQuery(
    {
      sort: resolved.sort,
      order: resolved.order
    },
    options
  );
}

function syncUiFromSettings(options = {}) {
  applyThemeFromSettings();
  if (options.applyDefaultSort !== false && !activeSavedSearchId.value && !isImportsView.value) {
    applyDefaultSortToQuery({ resetOffset: false });
  }
}

async function fetchAppSettings(options = {}) {
  try {
    await settingsStore.fetchSettings(apiBaseUrl, options);
    syncUiFromSettings(options);
  } catch (error) {
    if (options.silent !== true) {
      notifyError(error, 'Einstellungen konnten nicht geladen werden.');
    } else {
      logDevError(error, 'fetchAppSettings');
    }
  }
}


async function openSettingsDialog() {
  isSettingsDialogOpen.value = true;
  await fetchAppSettings();
}

function openShortcutsHelpDialog() {
  isShortcutsHelpDialogOpen.value = true;
}

async function openShortcutsFromSettings() {
  isSettingsDialogOpen.value = false;
  await nextTick();
  openShortcutsHelpDialog();
}

function handleSystemThemeChange() {
  if (appSettings.value.ui.theme_mode === 'system') {
    applyThemeFromSettings();
  }
}

function formatDocumentFilename(filename) {
  const value = String(filename || '').trim();
  if (!value) {
    return '';
  }
  if (showPdfSuffix.value) {
    return value;
  }
  return value.replace(/\.[^./\\]+$/, '');
}

function stripPdfSuffix(filename) {
  return String(filename || '').trim().replace(/\.pdf$/i, '');
}

function getDocumentTitle(document) {
  if (!document || typeof document !== 'object') {
    return '';
  }
  const displayName = String(document.display_name || '').trim();
  if (displayName) {
    return displayName;
  }
  return String(document.original_filename || '').trim();
}

function formatDocumentTitle(document) {
  return formatDocumentFilename(getDocumentTitle(document));
}


async function openCitation(citation) {
  const documentId = citation?.doc_id;
  if (!documentId) {
    return;
  }

  if (!closeDetailsDrawerWithGuard()) {
    return;
  }
  isAiDialogOpen.value = false;

  leaveActiveSavedSearch();
  activeView.value = 'all';
  searchText.value = '';
  patchDocumentListQuery({
    q: null,
    tagId: null,
    untagged: null,
    status: null,
    dateFrom: null,
    dateTo: null,
    ...resolveDefaultSortQuery(),
    limit: 100,
    offset: 0
  });

  const primaryPage =
    Number(citation?.page_from) > 0
      ? Number(citation.page_from)
      : Number(citation?.page_to) > 0
        ? Number(citation.page_to)
        : null;
  previewTargetPage.value    = primaryPage;
  previewHighlightText.value = String(citation?.snippet || '').trim();

  try {
    await fetchDocuments(null, { autoSelectFirst: false });
    await selectDocument(documentId, { preserveTargetPage: true });
  } catch (error) {
    notifyError(error, 'Quelle konnte nicht geöffnet werden.', { title: 'KI' });
  }
}

function documentDateIsFromOcr(document) {
  return String(document?.document_date_source || '').toLowerCase() === 'ocr';
}

function tagCloudItemStyle(tag) {
  const usage = Number(tag?.usage_count || 0);
  const ratio = Math.min(1, usage / maxTagUsageCount.value);
  const fontSizeRem = 0.82 + ratio * 0.46;
  const opacity = 0.66 + ratio * 0.34;
  const fontWeight = Math.round(520 + ratio * 120);
  const borderOpacity = 0.18 + ratio * 0.28;
  const backgroundOpacity = 0.05 + ratio * 0.11;
  return {
    fontSize: `${fontSizeRem.toFixed(3)}rem`,
    opacity: opacity.toFixed(2),
    fontWeight: String(fontWeight),
    borderColor: `rgba(var(--v-theme-primary), ${borderOpacity.toFixed(2)})`,
    backgroundColor: `rgba(var(--v-theme-primary), ${backgroundOpacity.toFixed(2)})`
  };
}

function hasOcrFile(document) {
  return Boolean(document?.files?.some((file) => file.role === 'ocr'));
}

function resolvePreviewRole(documentId) {
  if (selectedDocumentDetail.value?.id === documentId && hasOcrFile(selectedDocumentDetail.value)) {
    return 'ocr';
  }
  return 'original';
}

function documentFileUrl(documentId) {
  const selectedRole = resolvePreviewRole(documentId);
  return `${apiBaseUrl}/api/documents/${documentId}/file?role=${selectedRole}`;
}

function setDocumentUnreadState(documentId, unreadValue) {
  const listDocument = documents.value.find((item) => item.id === documentId);
  if (listDocument) {
    listDocument.is_unread = unreadValue;
  }

  if (selectedDocumentDetail.value?.id === documentId) {
    selectedDocumentDetail.value = {
      ...selectedDocumentDetail.value,
      is_unread: unreadValue
    };
  }
}

const markDocumentViewedOptimistic = (documentId) => docStore.markViewed(documentId);

function extractTagId(value) {
  if (!value) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'object' && 'id' in value) {
    return String(value.id || '');
  }
  return '';
}

function normalizeTagIds(tagIds) {
  const normalized = [];
  const seen = new Set();
  for (const value of tagIds || []) {
    const tagId = extractTagId(value);
    if (!tagId || seen.has(tagId)) {
      continue;
    }
    seen.add(tagId);
    normalized.push(tagId);
  }
  return normalized;
}

function normalizeQueryValue(value) {
  if (value === undefined) {
    return undefined;
  }
  if (value === null || value === '') {
    return null;
  }
  return value;
}

function patchDocumentListQuery(patch, options = {}) {
  const resetOffset = options.resetOffset !== false;
  let hasChanged = false;

  for (const [key, value] of Object.entries(patch || {})) {
    const nextValue = normalizeQueryValue(value);
    if (nextValue === undefined) {
      continue;
    }
    if (documentListQuery[key] !== nextValue) {
      documentListQuery[key] = nextValue;
      hasChanged = true;
    }
  }

  if (resetOffset && documentListQuery.offset !== 0) {
    documentListQuery.offset = 0;
    hasChanged = true;
  }

  return hasChanged;
}

function sortedTagIds(tagIds) {
  return [...normalizeTagIds(tagIds)].sort();
}

function isSameTagSelection(left, right) {
  const normalizedLeft = sortedTagIds(left);
  const normalizedRight = sortedTagIds(right);
  if (normalizedLeft.length !== normalizedRight.length) {
    return false;
  }
  return normalizedLeft.every((value, index) => value === normalizedRight[index]);
}

function sanitizeSelectedTagIds(tagValues) {
  const knownIds = new Set(tags.value.map((tag) => tag.id));
  return normalizeTagIds(tagValues).filter((tagId) => knownIds.has(tagId));
}

function applyMetadataFromDetail(detail) {
  shouldSkipTagAutosave = true;
  shouldSkipMetadataAutosave = true;
  metadataDocDate.value = formatDocumentDateInputFromIso(detail?.document_date);
  metadataDocDateHasError.value = false;
  metadataNotes.value = detail?.notes || '';
  const nextTagIds = normalizeTagIds((detail?.tags || []).map((tag) => tag.id));
  metadataTagIds.value = nextTagIds;
  metadataTagNames.value = (detail?.tags || []).map((tag) => normalizeTagInput(tag.name)).filter(Boolean);
  metadataTagSearch.value = '';
  metadataTagErrorMessage.value = '';
  window.setTimeout(() => {
    shouldSkipTagAutosave = false;
    shouldSkipMetadataAutosave = false;
  }, 0);
}

function syncTagSelectionLocal(tagIds) {
  shouldSkipTagAutosave = true;
  const sanitizedIds = sanitizeSelectedTagIds(tagIds);
  const names = sanitizedIds.map((tagId) => {
    const fromList = tags.value.find((tag) => tag.id === tagId)?.name;
    if (fromList) {
      return fromList;
    }
    const fromDetail = selectedDocumentDetail.value?.tags?.find((tag) => tag.id === tagId)?.name;
    return fromDetail || '';
  }).filter(Boolean);
  metadataTagIds.value = sanitizedIds;
  metadataTagNames.value = names;
  window.setTimeout(() => {
    shouldSkipTagAutosave = false;
  }, 0);
}

async function replaceDocumentTags(tagIds) {
  if (!selectedDocumentDetail.value) {
    return;
  }

  const documentId = selectedDocumentDetail.value.id;
  const nextTagIds = sanitizeSelectedTagIds(tagIds);
  const previousTagIds = normalizeTagIds((selectedDocumentDetail.value.tags || []).map((tag) => tag.id));

  if (isSameTagSelection(nextTagIds, previousTagIds)) {
    syncTagSelectionLocal(nextTagIds);
    return;
  }

  metadataTagErrorMessage.value = '';
  isSavingTags.value = true;

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag_ids: nextTagIds })
    });

    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    let detail = null;
    try {
      detail = await response.json();
    } catch (error) {
      logDevError(error, 'json-parse');
      detail = null;
    }
    if (detail?.id) {
      selectedDocumentDetail.value = detail;
      applyMetadataFromDetail(detail);
    } else {
      await fetchDocumentDetail(documentId);
    }
    await fetchTags();
    scheduleSidebarCountsRefresh();
    notify({ type: 'success', title: 'Tags', message: 'Tags gespeichert.', timeoutMs: 2500 });
  } catch (error) {
    metadataTagErrorMessage.value = notifyError(error, 'Tags konnten nicht gespeichert werden.');
    syncTagSelectionLocal(previousTagIds);
  } finally {
    isSavingTags.value = false;
  }
}

async function runManualAutoTagging() {
  if (!selectedDocumentDetail.value || isRunningManualAutoTagging.value) {
    return;
  }

  const documentId = selectedDocumentDetail.value.id;
  const previousTagIds = normalizeTagIds((selectedDocumentDetail.value.tags || []).map((tag) => tag.id));
  isRunningManualAutoTagging.value = true;
  metadataTagErrorMessage.value = '';

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/auto-tags`, {
      method: 'POST'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    let detail = null;
    try {
      detail = await response.json();
    } catch (error) {
      logDevError(error, 'json-parse');
      detail = null;
    }

    if (detail?.id) {
      selectedDocumentDetail.value = detail;
      documents.value = documents.value.map((document) => (
        document.id === detail.id ? { ...document, ...detail } : document
      ));
      applyMetadataFromDetail(detail);
    } else {
      await fetchDocumentDetail(documentId);
    }

    await fetchTags();
    scheduleSidebarCountsRefresh();
    const currentTagIds = normalizeTagIds((selectedDocumentDetail.value?.tags || []).map((tag) => tag.id));
    if (isSameTagSelection(previousTagIds, currentTagIds)) {
      notify({ type: 'warning', title: 'Tags', message: 'Keine neuen Informationen für Tags gefunden.' });
    } else {
      notify({ type: 'success', title: 'Tags', message: 'KI-Tagging abgeschlossen.' });
    }
  } catch (error) {
    metadataTagErrorMessage.value = notifyError(error, 'KI-Tagging konnte nicht ausgeführt werden.');
  } finally {
    isRunningManualAutoTagging.value = false;
  }
}

async function queueOcrFromHeader() {
  if (!selectedDocumentDetail.value || isQueueingHeaderOcr.value) {
    return;
  }

  const documentId = selectedDocumentDetail.value.id;
  isQueueingHeaderOcr.value = true;

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/ocr`, {
      method: 'POST'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    let detail = null;
    try {
      detail = await response.json();
    } catch (error) {
      logDevError(error, 'json-parse');
      detail = null;
    }

    if (detail?.id) {
      if (selectedDocumentDetail.value?.id === detail.id) {
        selectedDocumentDetail.value = {
          ...selectedDocumentDetail.value,
          status: detail.status,
          ocr_status: detail.ocr_status,
          jobs: detail.jobs,
          files: detail.files,
          text_source: detail.text_source,
          updated_at: detail.updated_at
        };
      } else {
        selectedDocumentDetail.value = detail;
      }

      documents.value = documents.value.map((document) => (
        document.id === detail.id
          ? {
              ...document,
              status: detail.status,
              ocr_status: detail.ocr_status,
              text_source: detail.text_source,
              updated_at: detail.updated_at
            }
          : document
      ));
    }

    scheduleSidebarCountsRefresh();
    notify({ type: 'success', title: 'OCR', message: 'OCR-Analyse wurde gestartet.' });
  } catch (error) {
    notifyError(error, 'OCR konnte nicht gestartet werden.');
  } finally {
    isQueueingHeaderOcr.value = false;
  }
}

function scheduleReplaceDocumentTags(tagIds) {
  if (tagReplaceDebounceTimer) {
    window.clearTimeout(tagReplaceDebounceTimer);
  }
  tagReplaceDebounceTimer = window.setTimeout(() => {
    void replaceDocumentTags(tagIds);
  }, TAG_REPLACE_DEBOUNCE_MS);
}

function scheduleMetadataAutosave() {
  if (metadataAutosaveDebounceTimer) {
    window.clearTimeout(metadataAutosaveDebounceTimer);
  }
  metadataAutosaveDebounceTimer = window.setTimeout(() => {
    if (!selectedDocumentDetail.value || !isMetadataDirty.value) {
      return;
    }
    if (isSavingMetadata.value) {
      shouldRunMetadataAutosaveAfterSave = true;
      return;
    }
    void saveMetadata({ skipDocumentReload: true, silentSuccess: true });
  }, METADATA_AUTOSAVE_DEBOUNCE_MS);
}

async function commitDocumentDateValue() {
  const parsedDocumentDate = parseDocumentDateInput(metadataDocDate.value);
  if (!parsedDocumentDate.ok) {
    metadataDocDateHasError.value = true;
    return;
  }

  metadataDocDateHasError.value = false;
  metadataDocDate.value = parsedDocumentDate.display;
  if (!selectedDocumentDetail.value || !isMetadataDirty.value) {
    return;
  }
  await saveMetadata({ skipDocumentReload: true, silentSuccess: true });
}

function handleDocumentDateBlur() {
  void commitDocumentDateValue();
}

function handleDocumentDateEnter() {
  void commitDocumentDateValue();
}

function handleDocumentDateShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, handleDocumentDateEnter, { ignoreEditable: false });
}

function resetDetailsSectionState() {
  // reserved for future section-level UI state resets
}

function canDiscardMetadataChanges() {
  if (isSavingMetadata.value) {
    return true;
  }
  if (!isMetadataDirty.value) {
    return true;
  }
  return window.confirm('Ungespeicherte Änderungen verwerfen?');
}

function closeDetailsDrawerWithGuard() {
  if (isDrawerAlwaysExpanded.value) {
    return true;
  }
  if (!isDetailsDrawerOpen.value) {
    return true;
  }
  if (!canDiscardMetadataChanges()) {
    return false;
  }
  isDetailsDrawerOpen.value = false;
  resetDetailsSectionState();
  metadataSuccessMessage.value = '';
  metadataErrorMessage.value = '';
  metadataTagErrorMessage.value = '';
  if (selectedDocumentDetail.value && !isSavingMetadata.value) {
    applyMetadataFromDetail(selectedDocumentDetail.value);
  }
  return true;
}

function toggleDetailsDrawer() {
  if (isDrawerAlwaysExpanded.value) {
    settingsStore.setDrawerExpanded(true, { force: true, persist: false });
    return;
  }
  if (isDetailsDrawerOpen.value) {
    closeDetailsDrawerWithGuard();
    return;
  }
  if (!selectedDocumentDetail.value) {
    return;
  }
  resetDetailsSectionState();
  metadataSuccessMessage.value = '';
  metadataErrorMessage.value = '';
  metadataTagErrorMessage.value = '';
  void fetchTags();
  isDetailsDrawerOpen.value = true;
}

function handleDetailsDrawerHeaderClick() {
  toggleDetailsDrawer();
}

function focusMetadataTagsInput() {
  const field = metadataTagsCombobox.value;
  const rootElement = field?.$el || field;
  const inputElement = rootElement?.querySelector?.('input');
  if (!inputElement || typeof inputElement.focus !== 'function') {
    return Promise.resolve();
  }
  return nextTick().then(() => {
    inputElement.focus();
    window.setTimeout(() => {
      void nextTick().then(() => {
        const retryRoot = field?.$el || field;
        const retryInput = retryRoot?.querySelector?.('input');
        retryInput?.focus?.();
      });
    }, 220);
  });
}

function handleGlobalKeydown(event) {
  if (handleShortcut(event, SHORTCUT_ACTIONS.HELP, openShortcutsHelpDialog)) {
    return;
  }
  if (
    handleShortcut(event, SHORTCUT_ACTIONS.TRASH, () => {
      if (selectedDocumentDetail.value && !isTrashView.value) {
        openDeleteDocumentDialog(selectedDocumentDetail.value);
      }
    })
  ) {
    return;
  }
  if (!handleShortcut(event, SHORTCUT_ACTIONS.CANCEL, null, { prevent: false, ignoreEditable: false })) {
    return;
  }
  if (isDetailsDrawerOpen.value) {
    event.preventDefault();
    closeDetailsDrawerWithGuard();
    return;
  }
  if (!selectedDocumentId.value) {
    return;
  }
  if (!canDiscardMetadataChanges()) {
    return;
  }
  event.preventDefault();
  selectedDocumentId.value = null;
  selectedDocumentDetail.value = null;
  isDetailsDrawerOpen.value = false;
  previewTargetPage.value    = null;
  previewHighlightText.value = '';
  resetDetailsSectionState();
  metadataSuccessMessage.value = '';
  metadataErrorMessage.value = '';
  metadataTagErrorMessage.value = '';
}

function buildDocumentListQuery() {
  const params = new URLSearchParams();
  params.set('limit', String(documentListQuery.limit));
  params.set('offset', String(documentListQuery.offset));
  params.set('sort', isFavoriteSortQuery() ? 'created_at' : documentListQuery.sort);
  params.set('order', isFavoriteSortQuery() ? 'desc' : documentListQuery.order);

  if (documentListQuery.q) {
    params.set('q', documentListQuery.q);
  }

  if (documentListQuery.status) {
    params.set('status', documentListQuery.status);
  }

  if (documentListQuery.dateFrom) {
    params.set('date_from', documentListQuery.dateFrom);
  }

  if (documentListQuery.dateTo) {
    params.set('date_to', documentListQuery.dateTo);
  }

  if (documentListQuery.untagged) {
    params.set('untagged', 'true');
  } else if (documentListQuery.tagId) {
    params.set('tag_id', documentListQuery.tagId);
  }

  if (isImportsView.value) {
    params.set('recent_imports', 'true');
  }

  if (isTrashView.value) {
    params.set('in_trash', 'true');
  }

  if (isFavoritesView.value) {
    params.set('favorites_only', 'true');
  }

  return params.toString();
}

function mapDocumentSortToSmartFolderSort() {
  if (isFavoriteSortQuery()) {
    return 'created_desc';
  }
  if (documentListQuery.sort === 'name' && documentListQuery.order === 'asc') {
    return 'title_asc';
  }
  if (
    (documentListQuery.sort === 'doc_date' || documentListQuery.sort === 'document_date') &&
    documentListQuery.order === 'desc'
  ) {
    return 'doc_date_desc';
  }
  if (
    (documentListQuery.sort === 'doc_date' || documentListQuery.sort === 'document_date') &&
    documentListQuery.order === 'asc'
  ) {
    return 'doc_date_asc';
  }
  return 'created_desc';
}

function buildSmartFolderDocumentsQuery() {
  const params = new URLSearchParams();
  params.set('limit', String(documentListQuery.limit));
  params.set('offset', String(documentListQuery.offset));
  params.set('sort', mapDocumentSortToSmartFolderSort());
  return params.toString();
}

function sortDocumentsForCurrentView(items) {
  const normalizedItems = Array.isArray(items) ? [...items] : [];
  if (!isFavoriteSortQuery()) {
    return normalizedItems;
  }
  return normalizedItems
    .map((document, index) => ({ document, index }))
    .sort((left, right) => {
      const favoriteDelta = Number(Boolean(right.document?.is_favorite)) - Number(Boolean(left.document?.is_favorite));
      if (favoriteDelta !== 0) {
        return favoriteDelta;
      }
      const rightUpdated = Date.parse(String(right.document?.updated_at || right.document?.created_at || '')) || 0;
      const leftUpdated = Date.parse(String(left.document?.updated_at || left.document?.created_at || '')) || 0;
      if (rightUpdated !== leftUpdated) {
        return rightUpdated - leftUpdated;
      }
      return left.index - right.index;
    })
    .map((entry) => entry.document);
}

async function parseResponseError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch (error) {
    logDevError(error, 'parseResponseError');
    return `Request failed (${response.status})`;
  }
}

async function parseJsonResponse(response) {
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (!contentType.includes('application/json')) {
    throw new Error('Keine gültige Antwort vom Server.');
  }
  return response.json();
}

function clearPreviewRetryTimer() {
  if (!previewRetryTimer) {
    return;
  }
  window.clearTimeout(previewRetryTimer);
  previewRetryTimer = null;
}

function nextPreviewRetryDelay(attempt) {
  const exponentialDelay = PREVIEW_RETRY_BASE_DELAY_MS * 2 ** Math.max(0, attempt - 1);
  return Math.min(exponentialDelay, PREVIEW_RETRY_MAX_DELAY_MS);
}

function resetPreviewRetryState(documentId) {
  const normalizedId = String(documentId || '').trim();
  if (!normalizedId) {
    return;
  }
  if (!previewRetryAttemptsByDocument.value[normalizedId]) {
    return;
  }
  const nextState = { ...previewRetryAttemptsByDocument.value };
  delete nextState[normalizedId];
  previewRetryAttemptsByDocument.value = nextState;
}

function schedulePreviewRetry(documentId) {
  const normalizedId = String(documentId || '').trim();
  if (!normalizedId) {
    return false;
  }
  const currentAttempts = Number(previewRetryAttemptsByDocument.value[normalizedId] || 0);
  const nextAttempts = currentAttempts + 1;
  previewRetryAttemptsByDocument.value = {
    ...previewRetryAttemptsByDocument.value,
    [normalizedId]: nextAttempts
  };
  if (nextAttempts > PREVIEW_RETRY_MAX_ATTEMPTS) {
    return false;
  }
  clearPreviewRetryTimer();
  const retryDelay = nextPreviewRetryDelay(nextAttempts);
  previewRetryTimer = window.setTimeout(() => {
    previewRetryTimer = null;
    if (String(selectedDocumentId.value || '').trim() !== normalizedId) {
      return;
    }
    previewReloadNonce.value += 1;
  }, retryDelay);
  return true;
}

function onPreviewFrameError(documentId) {
  if (!documentId) {
    return;
  }
  schedulePreviewRetry(documentId);
}

function onPreviewFrameLoad(documentId) {
  if (!documentId) {
    return;
  }
  clearPreviewRetryTimer();
  resetPreviewRetryState(documentId);
  if (previewTargetPage.value) {
    window.setTimeout(() => {
      previewTargetPage.value = null;
    }, 250);
  }
}

function leaveActiveSavedSearch() {
  activeSavedSearchId.value = null;
  activeSavedSearchQuery.value = null;
}

function onActiveSavedSearchChipClose() {
  const hadActiveSavedSearch = Boolean(activeSavedSearchId.value);
  leaveActiveSavedSearch();
  if (!hadActiveSavedSearch) {
    return;
  }
  activeView.value = 'all';
  searchText.value = '';
  const defaultSort = resolveDefaultSortQuery();
  patchDocumentListQuery(
    {
      q: null,
      tagId: null,
      untagged: null,
      status: null,
      dateFrom: null,
      dateTo: null,
      sort: defaultSort.sort,
      order: defaultSort.order,
      limit: 100,
      offset: 0
    },
    { resetOffset: false }
  );
  syncSearchStateToQuery({ resetOffset: false });
  void fetchDocuments(selectedDocumentId.value);
}

async function fetchSavedSearches() {
  await sidebarStore.fetchSavedSearches();
  // Falls aktiver Ordner nicht mehr existiert: zurückfallen
  if (activeSavedSearchId.value && !savedSearches.value.some((s) => s.id === activeSavedSearchId.value)) {
    leaveActiveSavedSearch();
    void fetchDocuments(selectedDocumentId.value);
  }
}

const fetchSavedSearchDetail = (id) => sidebarStore.fetchSavedSearchDetail(id);

function openCreateSavedSearchDialog() {
  smartFolderEditorMode.value = 'create';
  smartFolderEditorTarget.value = null;
  isSmartFolderEditorOpen.value = true;
}

async function openEditSavedSearchDialog(savedSearch) {
  if (!savedSearch?.id) {
    return;
  }
  try {
    const detail = await fetchSavedSearchDetail(savedSearch.id);
    smartFolderEditorMode.value = 'edit';
    smartFolderEditorTarget.value = detail;
    isSmartFolderEditorOpen.value = true;
  } catch (error) {
    notifyError(error, 'Ordner konnte nicht geladen werden.');
  }
}

function closeSmartFolderEditor() {
  isSmartFolderEditorOpen.value = false;
  smartFolderEditorTarget.value = null;
  smartFolderEditorMode.value = 'create';
}

async function handleSmartFolderSave(payload) {
  if (!payload || typeof payload !== 'object') {
    return;
  }
  const normalizedName = normalizeTagInput(payload.name);
  if (!normalizedName) {
    return;
  }

  isSavingSavedSearch.value = true;
  try {
    const isEdit = smartFolderEditorMode.value === 'edit' && Boolean(smartFolderEditorTarget.value?.id);
    const endpoint = isEdit
      ? `${apiBaseUrl}/api/smart-folders/${smartFolderEditorTarget.value.id}`
      : `${apiBaseUrl}/api/smart-folders`;
    const method = isEdit ? 'PUT' : 'POST';
    const response = await fetch(endpoint, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: normalizedName,
        query_json: payload.query_json
      })
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const savedFolder = await response.json();
    isApplyingSavedSearchQuery = true;
    activeView.value = 'all';
    activeSavedSearchId.value = savedFolder.id;
    activeSavedSearchQuery.value = savedFolder.query_json || null;
    searchText.value = '';
    const defaultSort = resolveDefaultSortQuery();
    patchDocumentListQuery(
      {
        q: null,
        tagId: null,
        untagged: null,
        status: null,
        dateFrom: null,
        dateTo: null,
        sort: defaultSort.sort,
        order: defaultSort.order,
        limit: 100,
        offset: 0
      },
      { resetOffset: false }
    );
    syncSearchStateToQuery({ resetOffset: false });
    window.setTimeout(() => {
      isApplyingSavedSearchQuery = false;
    }, 0);
    await fetchSavedSearches();
    scheduleSidebarCountsRefresh();
    closeSmartFolderEditor();
    await fetchDocuments(selectedDocumentId.value);
    notify({
      type: 'success',
      message: isEdit ? 'Ordner gespeichert.' : 'Ordner erstellt.'
    });
  } catch (error) {
    notifyError(error, 'Ordner konnte nicht gespeichert werden.');
    isApplyingSavedSearchQuery = false;
  } finally {
    isSavingSavedSearch.value = false;
  }
}

async function deleteSavedSearch(savedSearch) {
  const confirmed = window.confirm(`Ordner "${savedSearch.name}" wirklich löschen?`);
  if (!confirmed) {
    return;
  }

  isSavingSavedSearch.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/smart-folders/${savedSearch.id}`, {
      method: 'DELETE'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const deletedActiveFolder = activeSavedSearchId.value === savedSearch.id;
    if (activeSavedSearchId.value === savedSearch.id) {
      leaveActiveSavedSearch();
    }
    await fetchSavedSearches();
    scheduleSidebarCountsRefresh();
    if (deletedActiveFolder) {
      await fetchDocuments(selectedDocumentId.value);
    }
  } catch (error) {
    notifyError(error, 'Ordner konnte nicht gelöscht werden.');
  } finally {
    isSavingSavedSearch.value = false;
  }
}

async function openSavedSearch(savedSearchId) {
  if (!closeDetailsDrawerWithGuard()) {
    return;
  }

  try {
    const detail = await fetchSavedSearchDetail(savedSearchId);

    isApplyingSavedSearchQuery = true;
    activeView.value = 'all';
    activeSavedSearchId.value = detail.id;
    activeSavedSearchQuery.value = detail.query_json || null;
    searchText.value = '';

    const defaultSort = resolveDefaultSortQuery();
    patchDocumentListQuery({
      q: null,
      tagId: null,
      untagged: null,
      status: null,
      dateFrom: null,
      dateTo: null,
      sort: defaultSort.sort,
      order: defaultSort.order,
      limit: 100,
      offset: 0
    });
    syncSearchStateToQuery({ resetOffset: false });

    window.setTimeout(() => {
      isApplyingSavedSearchQuery = false;
    }, 0);
    await fetchDocuments(selectedDocumentId.value);
  } catch (error) {
    notifyError(error, 'Ordner konnte nicht geöffnet werden.');
    isApplyingSavedSearchQuery = false;
  }
}

async function fetchTags() {
  await tagStore.fetchTags();
  ensureActiveTagFilterIsValid();
}

async function fetchDocumentDetail(documentId) {
  if (!documentId) {
    selectedDocumentDetail.value = null;
    return;
  }

  const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  const detail = await parseJsonResponse(response);
  selectedDocumentDetail.value = detail;
  const ocrDone =
    detail?.ocr_status === 'done' ||
    detail?.jobs?.some((job) => job.type === 'OCR' && job.status === 'done');
  if (ocrDone && !hasOcrFile(detail)) {
    console.warn('OCR status indicates completion but ocr file is missing; falling back to original preview.', {
      documentId
    });
  }
  applyMetadataFromDetail(detail);
}

async function fetchDocuments(preferredDocumentId = null, options = {}) {
  const autoSelectFirst = options.autoSelectFirst === true;
  const allowPreferredOutsideList = options.allowPreferredOutsideList === true;
  isLoadingDocuments.value = true;

  try {
    const query = activeSavedSearchId.value ? buildSmartFolderDocumentsQuery() : buildDocumentListQuery();
    const endpoint = activeSavedSearchId.value
      ? `${apiBaseUrl}/api/smart-folders/${activeSavedSearchId.value}/documents?${query}`
      : `${apiBaseUrl}/api/documents?${query}`;
    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const payload = await parseJsonResponse(response);
    documents.value = sortDocumentsForCurrentView(payload.items || []);

    if (documents.value.length === 0) {
      if (!canDiscardMetadataChanges()) {
        return;
      }
      isDetailsDrawerOpen.value = false;
      selectedDocumentId.value = null;
      selectedDocumentDetail.value = null;
      return;
    }

    let resolvedSelectionId = selectedDocumentId.value;
    const preferredExists = preferredDocumentId && documents.value.some((doc) => doc.id === preferredDocumentId);
    if (preferredExists) {
      resolvedSelectionId = preferredDocumentId;
    } else {
      const hasSelection = documents.value.some((doc) => doc.id === resolvedSelectionId);
      if (!hasSelection) {
        if (!canDiscardMetadataChanges()) {
          return;
        }
        resolvedSelectionId = allowPreferredOutsideList && preferredDocumentId
          ? preferredDocumentId
          : autoSelectFirst
            ? documents.value[0].id
            : null;
      }
    }

    selectedDocumentId.value = resolvedSelectionId;
    if (!resolvedSelectionId) {
      selectedDocumentDetail.value = null;
      return;
    }

    try {
      await fetchDocumentDetail(resolvedSelectionId);
      void markDocumentViewedOptimistic(resolvedSelectionId);
    } catch (error) {
      if (!allowPreferredOutsideList || resolvedSelectionId !== preferredDocumentId) {
        throw error;
      }
      persistLastSelectedDocId(null);
      selectedDocumentId.value = autoSelectFirst ? documents.value[0]?.id || null : null;
      selectedDocumentDetail.value = null;
      if (selectedDocumentId.value) {
        await fetchDocumentDetail(selectedDocumentId.value);
        void markDocumentViewedOptimistic(selectedDocumentId.value);
      }
    }
  } catch (error) {
    notifyError(error, 'Dokumente konnten nicht geladen werden.');
  } finally {
    isLoadingDocuments.value = false;
  }
}

async function selectDocument(documentId, options = {}) {
  if (documentId === selectedDocumentId.value) {
    return;
  }
  const preserveTargetPage = options.preserveTargetPage === true;
  if (!canDiscardMetadataChanges()) {
    return;
  }
  if (!preserveTargetPage) {
    previewTargetPage.value    = null;
    // Suchbegriff aus der globalen Suche als Highlight übernehmen
    previewHighlightText.value = parsedSearch.value.q || '';
  }
  selectedDocumentId.value = documentId;
  metadataSuccessMessage.value = '';
  metadataErrorMessage.value = '';
  metadataTagErrorMessage.value = '';
  try {
    await fetchDocumentDetail(documentId);
    void markDocumentViewedOptimistic(documentId);
    await fetchTags();
  } catch (error) {
    metadataErrorMessage.value = notifyError(error, 'Dokumentdetails konnten nicht geladen werden.');
  }
}

async function openTagManagerFromList(document) {
  if (!document?.id) {
    return;
  }

  if (document.id !== selectedDocumentId.value) {
    await selectDocument(document.id);
    if (selectedDocumentId.value !== document.id) {
      return;
    }
  } else if (!selectedDocumentDetail.value) {
    try {
      await fetchDocumentDetail(document.id);
    } catch (error) {
      metadataErrorMessage.value = notifyError(error, 'Dokumentdetails konnten nicht geladen werden.');
      return;
    }
  }

  if (!isDetailsDrawerOpen.value) {
    resetDetailsSectionState();
    metadataSuccessMessage.value = '';
    metadataErrorMessage.value = '';
    metadataTagErrorMessage.value = '';
    isDetailsDrawerOpen.value = true;
  }

  await fetchTags();
  await focusMetadataTagsInput();
}

function openDeleteDocumentDialog(document) {
  if (!document?.id) {
    return;
  }
  deleteDocumentTarget.value = {
    id: document.id,
    original_filename: document.original_filename,
    display_name: document.display_name || null
  };
  isDeleteDocumentDialogOpen.value = true;
}

function closeDeleteDocumentDialog() {
  if (isDeletingDocument.value) {
    return;
  }
  isDeleteDocumentDialogOpen.value = false;
  deleteDocumentTarget.value = null;
  permanentDeleteMode.value = false;
}

function onDocumentRenamed(updated) {
  documents.value = documents.value.map((document) =>
    document.id === updated.id ? { ...document, ...updated } : document
  );
  if (selectedDocumentId.value === updated.id) {
    selectedDocumentDetail.value = updated;
    applyMetadataFromDetail(updated);
  }
}

async function confirmDeleteDocumentFromDialog() {
  if (isDeletingDocument.value || !deleteDocumentTarget.value?.id) {
    return;
  }

  isDeletingDocument.value = true;

  const targetDocumentId = deleteDocumentTarget.value.id;
  const isDeletedSelection = selectedDocumentId.value === targetDocumentId;
  const preferredDocumentId = isDeletedSelection ? null : selectedDocumentId.value;
  const isPermanent = permanentDeleteMode.value;

  try {
    const url = isPermanent
      ? `${apiBaseUrl}/api/documents/${targetDocumentId}`
      : `${apiBaseUrl}/api/documents/${targetDocumentId}/trash`;
    const method = isPermanent ? 'DELETE' : 'POST';

    const response = await fetch(url, { method });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    isDeleteDocumentDialogOpen.value = false;
    deleteDocumentTarget.value = null;
    permanentDeleteMode.value = false;

    if (isDeletedSelection) {
      isDetailsDrawerOpen.value = false;
      selectedDocumentId.value = null;
      selectedDocumentDetail.value = null;
    }

    await fetchTags();
    await fetchDocuments(preferredDocumentId, {
      autoSelectFirst: !isDeletedSelection
    });
    scheduleSidebarCountsRefresh();
    notify({
      type: 'success',
      title: 'Dokument',
      message: isPermanent ? 'Dokument endgültig gelöscht.' : 'Dokument in den Papierkorb verschoben.'
    });
  } catch (error) {
    notifyError(error, isPermanent ? 'Dokument konnte nicht gelöscht werden.' : 'Dokument konnte nicht in den Papierkorb verschoben werden.');
  } finally {
    isDeletingDocument.value = false;
  }
}

/** Öffnet Bestätigungsdialog für endgültiges Löschen (aus dem Papierkorb). */
function openPermanentDeleteDialog(document) {
  if (!document?.id) return;
  permanentDeleteMode.value = true;
  deleteDocumentTarget.value = {
    id: document.id,
    original_filename: document.original_filename,
    display_name: document.display_name || null
  };
  isDeleteDocumentDialogOpen.value = true;
}

/** Dokument direkt aus dem Papierkorb wiederherstellen (kein Dialog). */
async function restoreDocumentFromTrash(document) {
  if (!document?.id) return;
  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${document.id}/restore`, { method: 'POST' });
    if (!response.ok) throw new Error(await parseResponseError(response));
    await fetchDocuments(selectedDocumentId.value === document.id ? null : selectedDocumentId.value, {
      autoSelectFirst: selectedDocumentId.value === document.id
    });
    scheduleSidebarCountsRefresh();
    notify({ type: 'success', title: 'Dokument', message: 'Dokument wiederhergestellt.' });
  } catch (error) {
    notifyError(error, 'Wiederherstellen fehlgeschlagen.');
  }
}

/** Favoriten-Status eines Dokuments umschalten. */
async function toggleDocumentFavorite(document) {
  if (!document?.id) return;
  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${document.id}/favorite`, { method: 'POST' });
    if (!response.ok) throw new Error(await parseResponseError(response));
    const updated = await response.json();
    if (isFavoritesView.value && updated.is_favorite === false) {
      documents.value = documents.value.filter((doc) => doc.id !== updated.id);
      if (selectedDocumentId.value === updated.id) {
        const nextDocument = documents.value[0] || null;
        selectedDocumentId.value = nextDocument?.id || null;
        selectedDocumentDetail.value = null;
        if (nextDocument?.id) {
          await fetchDocumentDetail(nextDocument.id);
          void markDocumentViewedOptimistic(nextDocument.id);
        } else {
          isDetailsDrawerOpen.value = false;
        }
      }
    } else {
      documents.value = documents.value.map((doc) =>
        doc.id === updated.id ? { ...doc, is_favorite: updated.is_favorite } : doc
      );
    }
    if (selectedDocumentDetail.value?.id === updated.id) {
      selectedDocumentDetail.value = { ...selectedDocumentDetail.value, is_favorite: updated.is_favorite };
    }
    if (isFavoriteSortQuery() && !isFavoritesView.value) {
      await fetchDocuments(selectedDocumentId.value);
    }
    scheduleSidebarCountsRefresh();
  } catch (error) {
    notifyError(error, 'Favoriten-Status konnte nicht geändert werden.');
  }
}

function selectView(viewKey) {
  if (viewKey === 'tags' && !closeDetailsDrawerWithGuard()) {
    return;
  }
  if (viewKey !== 'tags') {
    clearTagFeedbackMessages();
  }

  if (viewKey === 'all') {
    const defaultSort = resolveDefaultSortQuery();
    const hadActiveSavedSearch = Boolean(activeSavedSearchId.value);
    activeView.value = 'all';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      untagged: null,
      status: null,
      sort: defaultSort.sort,
      order: defaultSort.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    if (hadActiveSavedSearch) {
      void fetchDocuments(selectedDocumentId.value);
    }
    return;
  }

  if (viewKey === 'imports') {
    activeView.value = 'imports';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      untagged: null,
      status: null,
      sort: 'created_at',
      order: 'desc',
      limit: IMPORTS_RECENT_LIMIT
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'untagged') {
    const defaultSort = resolveDefaultSortQuery();
    activeView.value = 'untagged';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      untagged: true,
      status: null,
      sort: defaultSort.sort,
      order: defaultSort.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'favorites') {
    const defaultSort = resolveDefaultSortQuery();
    activeView.value = 'favorites';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      untagged: null,
      status: null,
      sort: defaultSort.sort,
      order: defaultSort.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'trash') {
    activeView.value = 'trash';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      untagged: null,
      status: null,
      sort: 'created_at',
      order: 'desc'
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'tags') {
    leaveActiveSavedSearch();
  }
  activeView.value = viewKey;
}

function clearTagFeedbackMessages() {
  // no-op: legacy local tag error banner removed in favor of global notifications
}

function openTagsView() {
  selectView('tags');
}

function selectTagFilter(tagId) {
  patchDocumentListQuery({
    tagId,
    untagged: null,
    status: null
  });
}

function clearTagFilter() {
  leaveActiveSavedSearch();
  patchDocumentListQuery({
    tagId: null
  });
  syncSearchStateToQuery({ resetOffset: false });
}

function tagUsageCount(tagId, fallback = 0) {
  return sidebarStore.tagCount(tagId, fallback);
}

function ensureActiveTagFilterIsValid() {
  const currentTagId = String(documentListQuery.tagId || '').trim();
  if (!currentTagId) {
    return;
  }

  const hasActiveTag = tags.value.some((tag) => (
    String(tag.id || '').trim() === currentTagId &&
    tagUsageCount(tag.id, tag.usage_count ?? 0) > 0
  ));
  if (hasActiveTag) {
    return;
  }

  if (activeView.value === 'tags') {
    activeView.value = 'all';
  }
  clearTagFilter();
}

function applyTagFilterFromSidebar(tagId) {
  activeView.value = 'all';
  leaveActiveSavedSearch();
  searchText.value = '';
  patchDocumentListQuery({
    q: null,
    tagId,
    untagged: null,
    status: null,
    dateFrom: null,
    dateTo: null
  });
  syncSearchStateToQuery({ resetOffset: false });
}

function openTagDocuments(tagId) {
  clearTagFeedbackMessages();
  activeView.value = 'all';
  leaveActiveSavedSearch();
  searchText.value = '';
  patchDocumentListQuery({
    q: null,
    tagId,
    untagged: null,
    status: null,
    dateFrom: null,
    dateTo: null
  });
  syncSearchStateToQuery({ resetOffset: false });
}

function normalizeTagInput(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function normalizeTagNames(values) {
  const normalized = [];
  const seen = new Set();
  for (const value of values || []) {
    const name = normalizeTagInput(value);
    if (!name) {
      continue;
    }
    const key = name.toLocaleLowerCase('de-DE');
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    normalized.push(name);
  }
  return normalized;
}

function findTagByName(name) {
  const normalizedName = normalizeTagInput(name).toLocaleLowerCase('de-DE');
  if (!normalizedName) {
    return null;
  }
  return tags.value.find((tag) => normalizeTagInput(tag.name).toLocaleLowerCase('de-DE') === normalizedName) || null;
}

function onTagMutated({ action, sourceId, targetId, tagId } = {}) {
  if (action === 'merged' && sourceId && activeTagId.value === sourceId) {
    activeTagId.value = targetId || null;
  }
  if (action === 'deleted' && tagId && activeTagId.value === tagId) {
    activeTagId.value = null;
  }
  void fetchTags();
  void fetchDocuments(selectedDocumentId.value);
  scheduleSidebarCountsRefresh();
}

function onSettingsReloadImports() {
  void fetchDocuments(selectedDocumentId.value);
  scheduleSidebarCountsRefresh();
}


function setListDropNotice(message) {
  listDropNotice.value = message;
  if (listDropNoticeTimer) {
    window.clearTimeout(listDropNoticeTimer);
    listDropNoticeTimer = null;
  }
  if (!message) {
    return;
  }
  listDropNoticeTimer = window.setTimeout(() => {
    listDropNotice.value = '';
    listDropNoticeTimer = null;
  }, 2800);
}

/** Empfängt rohe File-Liste vom DocumentListPanel (nach Drag & Drop). */
async function onDroppedFiles(files) {
  if (!files.length) return;

  const selection = selectPdfFiles(files, 'dnd');
  const rejectedCount = selection.skippedNonPdf + selection.skippedDuplicates;

  setListDropNotice(
    rejectedCount > 0
      ? rejectedCount === 1
        ? 'Nur PDFs werden importiert. 1 Datei wurde ignoriert.'
        : `Nur PDFs werden importiert. ${rejectedCount} Dateien wurden ignoriert.`
      : ''
  );

  if (selection.files.length === 0) return;

  const dialogRef = importStagingDialogRef.value;
  if (dialogRef && typeof dialogRef.openWithFiles === 'function') {
    await dialogRef.openWithFiles(selection.files);
  }
}

function openImportPdfPicker() {
  importPdfInputRef.value?.click?.();
}

async function onImportPdfInputChange(event) {
  const selection = selectPdfFiles(event.target?.files || [], 'file');
  event.target.value = '';

  const rejectedCount = selection.skippedNonPdf + selection.skippedDuplicates;
  if (rejectedCount > 0) {
    notify({
      type: 'warning',
      message:
        rejectedCount === 1
          ? 'Nur PDFs werden importiert. 1 Datei wurde ignoriert.'
          : `Nur PDFs werden importiert. ${rejectedCount} Dateien wurden ignoriert.`
    });
  }

  if (selection.files.length === 0) {
    return;
  }

  const dialogRef = importStagingDialogRef.value;
  if (dialogRef && typeof dialogRef.openWithFiles === 'function') {
    await dialogRef.openWithFiles(selection.files);
  }
}

async function onImportCommitted(payload) {
  if (!Array.isArray(payload?.created) || payload.created.length === 0) {
    return;
  }
  if (!Array.isArray(payload?.errors) || payload.errors.length === 0) {
    await claimActiveImportInboxItems();
  }
  await fetchDocuments(selectedDocumentId.value, { autoSelectFirst: false });
  scheduleSidebarCountsRefresh();
}

function isPdfCandidate(file) {
  const filename = String(file?.name || '').toLowerCase();
  if (filename.endsWith('.pdf')) {
    return true;
  }
  return String(file?.type || '').toLowerCase() === 'application/pdf';
}

function normalizeRelativePath(pathValue) {
  return String(pathValue || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .trim();
}

function buildSelectionDedupKey(file, relativePath = '') {
  const filename = String(file?.name || '').trim();
  const size = Number(file?.size || 0);
  const lastModified = Number(file?.lastModified || 0);
  return `${filename}|${size}|${lastModified}|${relativePath}`;
}

function selectPdfFiles(files, source) {
  const dedupe = new Set();
  const acceptedFiles = [];
  let skippedNonPdf = 0;
  let skippedDuplicates = 0;

  for (const file of files) {
    const relativePath = source === 'folder' ? normalizeRelativePath(file?.webkitRelativePath) : '';
    const dedupeKey = buildSelectionDedupKey(file, relativePath);
    if (dedupe.has(dedupeKey)) {
      skippedDuplicates += 1;
      continue;
    }
    dedupe.add(dedupeKey);

    if (!isPdfCandidate(file)) {
      skippedNonPdf += 1;
      continue;
    }

    acceptedFiles.push(file);
  }

  return {
    files: acceptedFiles,
    skippedNonPdf,
    skippedDuplicates
  };
}

function downloadSelectedDocument() {
  if (!selectedDocumentDetail.value) {
    return;
  }

  const role = resolvePreviewRole(selectedDocumentDetail.value.id);
  const url = `${apiBaseUrl}/api/documents/${selectedDocumentDetail.value.id}/file?role=${role}&download=true`;
  window.open(url, '_blank', 'noopener');
}

function downloadDocumentFromList(document) {
  const documentId = String(document?.id || '').trim();
  if (!documentId) {
    return;
  }
  if (selectedDocumentDetail.value?.id === documentId) {
    downloadSelectedDocument();
    return;
  }
  const url = `${apiBaseUrl}/api/documents/${documentId}/file?role=original&download=true`;
  window.open(url, '_blank', 'noopener');
}

async function saveMetadata(options = {}) {
  const skipDocumentReload = options.skipDocumentReload === true;
  const silentSuccess = options.silentSuccess === true;
  if (!selectedDocumentDetail.value) {
    return;
  }
  if (isSavingMetadata.value) {
    shouldRunMetadataAutosaveAfterSave = true;
    return;
  }
  if (!isMetadataDirty.value) {
    return;
  }

  metadataSuccessMessage.value = '';
  metadataErrorMessage.value = '';
  isSavingMetadata.value = true;

  try {
    const documentId = selectedDocumentDetail.value.id;
    const parsedDocumentDate = parseDocumentDateInput(metadataDocDate.value);
    if (!parsedDocumentDate.ok) {
      metadataDocDateHasError.value = true;
      return;
    }

    metadataDocDateHasError.value = false;
    metadataDocDate.value = parsedDocumentDate.display;
    const normalizedDocDate = parsedDocumentDate.iso;
    const normalizedNotes = metadataNotes.value || null;

    const patchResponse = await fetch(`${apiBaseUrl}/api/documents/${documentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_date: normalizedDocDate,
        notes: normalizedNotes
      })
    });

    if (!patchResponse.ok) {
      throw new Error(await parseResponseError(patchResponse));
    }

    let updatedDetail = null;
    try {
      updatedDetail = await patchResponse.json();
    } catch (error) {
      logDevError(error, 'json-parse');
      updatedDetail = null;
    }

    if (updatedDetail?.id) {
      selectedDocumentDetail.value = updatedDetail;
      const listIndex = documents.value.findIndex((document) => document.id === updatedDetail.id);
      if (listIndex >= 0) {
        const existing = documents.value[listIndex];
        documents.value.splice(listIndex, 1, {
          ...existing,
          ...updatedDetail
        });
      }
      applyMetadataFromDetail(updatedDetail);
    } else {
      if (selectedDocumentDetail.value?.id === documentId) {
        selectedDocumentDetail.value = {
          ...selectedDocumentDetail.value,
          document_date: normalizedDocDate,
          document_date_source: 'manual',
          document_date_confidence: null,
          document_date_candidates: null,
          notes: normalizedNotes
        };
      }
      const listIndex = documents.value.findIndex((document) => document.id === documentId);
      if (listIndex >= 0) {
        const existing = documents.value[listIndex];
        documents.value.splice(listIndex, 1, {
          ...existing,
          document_date: normalizedDocDate,
          document_date_source: 'manual',
          document_date_confidence: null,
          document_date_candidates: null,
          notes: normalizedNotes
        });
      }
      if (selectedDocumentDetail.value?.id === documentId) {
        applyMetadataFromDetail(selectedDocumentDetail.value);
      }
      if (!skipDocumentReload) {
        await fetchDocumentDetail(documentId);
      }
    }

    if (!skipDocumentReload) {
      await fetchDocuments();
    }
    if (!silentSuccess) {
      metadataSuccessMessage.value = 'Metadaten gespeichert.';
    }
  } catch (error) {
    metadataErrorMessage.value = notifyError(error, 'Speichern fehlgeschlagen.');
  } finally {
    isSavingMetadata.value = false;
    if (shouldRunMetadataAutosaveAfterSave) {
      shouldRunMetadataAutosaveAfterSave = false;
      scheduleMetadataAutosave();
    }
  }
}

async function deleteSelectedDocument() {
  if (!selectedDocumentDetail.value) {
    return;
  }
  openDeleteDocumentDialog(selectedDocumentDetail.value);
}

watch(selectedDocumentId, (nextId, previousId) => {
  if (nextId !== previousId) {
    clearPreviewRetryTimer();
    previewRetryAttemptsByDocument.value = {};
    resetDetailsSectionState();
  }
});

watch(metadataTagIds, (nextValue) => {
  if (shouldSkipTagAutosave || !selectedDocumentDetail.value) {
    return;
  }
  const sanitizedTagIds = sanitizeSelectedTagIds(nextValue);
  if (!isSameTagSelection(sanitizedTagIds, nextValue)) {
    syncTagSelectionLocal(sanitizedTagIds);
    return;
  }
  scheduleReplaceDocumentTags(sanitizedTagIds);
});

watch([metadataDocDate, metadataNotes], () => {
  if (shouldSkipMetadataAutosave || !selectedDocumentDetail.value) {
    return;
  }
  const parsedDocumentDate = parseDocumentDateInput(metadataDocDate.value);
  if (!parsedDocumentDate.ok) {
    return;
  }
  metadataDocDateHasError.value = false;
  metadataErrorMessage.value = '';
  scheduleMetadataAutosave();
});

watch(isDetailsDrawerOpen, (open) => {
  if (!open) {
    return;
  }
  void fetchTags();
});

watch(documentListSavedQueryKey, (nextKey) => {
  if (!activeSavedSearchId.value || !activeSavedSearchQuery.value) {
    return;
  }
  if (isApplyingSavedSearchQuery) {
    return;
  }
  if (nextKey) {
    leaveActiveSavedSearch();
  }
});

// ── Composables ──────────────────────────────────────────────────────────────

const {
  searchText,
  appBarSearchRef,
  parsedSearch,
  searchHintMessages,
  showSnippets,
  searchPlaceholder,
  syncSearchStateToQuery,
  triggerSearchNow,
  focusSearchFieldInput,
  onAppBarSearchInput,
  clearSearchFromInput,
  handleSearchEscape
} = useSearch({
  documentListQuery,
  documentListQueryReloadKey,
  activeView,
  activeSavedSearchId,
  activeSavedSearchName,
  activeTagId,
  tags,
  isTagView,
  selectedDocumentId,
  patchDocumentListQuery,
  fetchDocuments
});

useOcrPolling({
  documents,
  hasActiveOcrJob,
  isLoadingDocuments,
  selectedDocumentId,
  fetchDocuments
});

useGlobalKeyboard(handleGlobalKeydown);

onMounted(async () => {
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', handleSystemThemeChange);
  await fetchAppSettings();

  await Promise.all([fetchTags(), fetchSavedSearches(), fetchSidebarCounts()]);
  const restoredDocId = readStoredLastSelectedDocId();
  isRestoringLastSelectedDocument = Boolean(restoredDocId);
  try {
    await fetchDocuments(restoredDocId, {
      allowPreferredOutsideList: Boolean(restoredDocId),
      autoSelectFirst: true
    });
  } finally {
    isRestoringLastSelectedDocument = false;
  }
  persistLastSelectedDocId(selectedDocumentId.value);
  startImportInboxPolling();
});

onBeforeUnmount(() => {
  if (tagReplaceDebounceTimer) {
    window.clearTimeout(tagReplaceDebounceTimer);
  }
  if (metadataAutosaveDebounceTimer) {
    window.clearTimeout(metadataAutosaveDebounceTimer);
  }
  clearPreviewRetryTimer();
  if (listDropNoticeTimer) {
    window.clearTimeout(listDropNoticeTimer);
  }
  if (importInboxPollTimer) {
    window.clearInterval(importInboxPollTimer);
  }
  mediaQuery?.removeEventListener('change', handleSystemThemeChange);
});
</script>

<style>
/* Theme-Variablen → src/theme/theme.css */

.app-topbar {
  color: rgba(248, 250, 255, 0.96) !important;
  background: var(--pm-appbar-bg) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

.app-topbar :deep(.v-toolbar__content) {
  padding: 0;
}

.appbar-layout {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 16px;
}

.appbar-center {
  justify-self: center;
  width: min(480px, 100%);
  padding: 0 16px;
  min-width: 0;
  box-sizing: border-box;
}

.appbar-left {
  flex-shrink: 0;
}

.appbar-right {
  flex-shrink: 0;
}

.appbar-search__field {
  width: 100%;
}

.appbar-search__field :deep(.v-field) {
  border-radius: 10px;
  background-color: rgba(255, 255, 255, 0.16) !important;
  box-shadow: none !important;
  color: rgba(248, 250, 255, 0.96);
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.appbar-search__field :deep(.v-field:hover) {
  background-color: rgba(255, 255, 255, 0.22) !important;
}

.appbar-search__field :deep(.v-field--focused) {
  background-color: rgba(255, 255, 255, 0.28) !important;
}

.appbar-search__field :deep(.v-field__input),
.appbar-search__field :deep(.v-field__prepend-inner .v-icon),
.appbar-search__field :deep(.v-field__clearable .v-icon) {
  color: rgba(248, 250, 255, 0.85) !important;
}

.appbar-search__field :deep(input::placeholder) {
  color: rgba(248, 250, 255, 0.5);
}

.appbar-search__field :deep(.v-field__outline) {
  color: rgba(255, 255, 255, 0.62);
  --v-field-border-opacity: 1;
}

.appbar-search__field :deep(.v-field:hover .v-field__outline) {
  color: rgba(255, 255, 255, 0.76);
}

.appbar-search__field :deep(.v-field--focused .v-field__outline) {
  color: rgba(255, 255, 255, 0.92);
}

.papermind-app.v-theme--dark .appbar-search__field :deep(.v-field) {
  background-color: rgba(255, 255, 255, 0.2) !important;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
}

.papermind-app.v-theme--dark .appbar-search__field .v-field {
  background-color: rgba(255, 255, 255, 0.2) !important;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
}

.papermind-app.v-theme--dark .appbar-search__field .v-field__overlay,
.papermind-app.v-theme--dark .list-toolbar__search .v-field__overlay,
.papermind-app.v-theme--dark .tags-view-search .v-field__overlay {
  opacity: 0 !important;
}

.papermind-app.v-theme--dark .appbar-search__field :deep(.v-field:hover) {
  background-color: rgba(255, 255, 255, 0.25) !important;
}

.papermind-app.v-theme--dark .appbar-search__field .v-field:hover {
  background-color: rgba(255, 255, 255, 0.25) !important;
}

.papermind-app.v-theme--dark .appbar-search__field :deep(.v-field--focused) {
  background-color: rgba(255, 255, 255, 0.3) !important;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2) !important;
}

.papermind-app.v-theme--dark .appbar-search__field .v-field--focused {
  background-color: rgba(255, 255, 255, 0.3) !important;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2) !important;
}

.app-main {
  margin-top: 0 !important;
}

.papermind-app,
.app-main,
.workspace,
.panel,
.panel-right__preview,
.document-list-shell,
.document-list-body,
.document-list-content {
  opacity: 1;
  filter: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.papermind-app,
.app-main {
  background: var(--pm-app-surface);
}

.papermind-app :deep(.v-application__wrap),
.papermind-app :deep(.v-main),
.papermind-app :deep(.v-main__wrap) {
  opacity: 1 !important;
  filter: none !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  background-color: var(--pm-app-surface) !important;
}

.papermind-app :deep(.v-field__overlay),
.papermind-app :deep(.v-btn__overlay),
.papermind-app :deep(.v-list-item__overlay),
.papermind-app :deep(.v-card__overlay),
.papermind-app :deep(.v-sheet__overlay) {
  opacity: 0 !important;
}

.app-title {
  min-width: 0;
}

.app-title__brand {
  color: rgba(248, 250, 255, 0.98);
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.015em;
}

.app-title__brand-button {
  background: transparent;
  border: 0;
  padding: 0;
  cursor: pointer;
}

.appbar-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.topbar-btn {
  height: 38px;
  margin: 0 !important;
  border-radius: 999px;
  text-transform: none;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: rgba(248, 250, 255, 0.95) !important;
}

.topbar-btn--import {
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.topbar-btn--import:hover {
  background: rgba(255, 255, 255, 0.18);
}

.import-inbox-menu-item {
  color: rgb(var(--v-theme-primary));
}

.import-inbox-menu-item .v-list-item-title,
.import-inbox-menu-item .v-icon {
  color: rgb(var(--v-theme-primary));
  font-weight: 700;
}

.topbar-btn--ghost {
  padding: 0 8px;
}

.topbar-btn--ghost:hover,
.topbar-btn--icon:hover {
  background: rgba(255, 255, 255, 0.14);
}

.topbar-btn--active {
  background: rgba(255, 255, 255, 0.18);
}

.topbar-btn--icon {
  min-width: 38px;
  width: 38px;
  padding: 0;
}

.topbar-btn :deep(.v-icon) {
  color: rgba(250, 252, 255, 0.94);
}

.topbar-btn__help-label {
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1;
  color: rgba(250, 252, 255, 0.94);
  user-select: none;
}

.list-toolbar {
  position: sticky;
  top: 0;
  z-index: 2;
  display: grid;
  gap: 4px;
  padding: 14px 12px 8px;
  border-bottom: 1px solid var(--pm-divider);
  background: var(--pm-content-surface);
}

.ai-page {
  height: min(76vh, 760px);
  min-height: 520px;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 10px;
  padding: 12px;
  background: rgba(var(--v-theme-background), 0.98);
}

.ai-suggestions {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 12px;
  background: rgba(var(--v-theme-surface), 0.92);
  padding: 12px;
}

.ai-section-title {
  font-size: 0.76rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.72;
  font-weight: 700;
  margin-bottom: 10px;
}

.ai-suggestions__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
}

.ai-suggestion-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-surface), 0.7);
  color: inherit;
  padding: 10px 12px;
  min-height: 56px;
  text-align: left;
  font-size: 0.84rem;
  line-height: 1.35;
  cursor: pointer;
  transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ai-suggestion-card:hover {
  background: rgba(var(--v-theme-primary), 0.08);
  border-color: rgba(var(--v-theme-primary), 0.28);
}

.ai-chat-panel {
  min-height: 0;
  display: grid;
  grid-template-rows: 1fr auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 12px;
  background: rgba(var(--v-theme-surface), 0.92);
  overflow: hidden;
}

.ai-chat-history {
  min-height: 0;
  overflow: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-chat-empty {
  flex: 1;
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  opacity: 0.82;
}

.ai-chat-empty__icon {
  opacity: 0.66;
}

.ai-chat-empty__title {
  font-weight: 600;
}

.ai-chat-empty__subtitle {
  max-width: 440px;
  font-size: 0.84rem;
  line-height: 1.45;
  opacity: 0.76;
}

.ai-message {
  display: grid;
  gap: 8px;
}

.ai-message__bubble {
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 0.9rem;
  line-height: 1.45;
  white-space: pre-wrap;
}

.ai-message__bubble-content {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ai-message--user .ai-message__bubble {
  justify-self: end;
  max-width: min(760px, 92%);
  background: rgba(var(--v-theme-primary), 0.1);
  border: 1px solid rgba(var(--v-theme-primary), 0.22);
}

.ai-message--assistant .ai-message__bubble {
  justify-self: start;
  max-width: min(900px, 96%);
  background: rgba(var(--v-theme-surface), 0.62);
  border: 1px solid var(--pm-divider);
}

.ai-sources {
  display: grid;
  gap: 8px;
}

.ai-sources__divider {
  height: 1px;
  background: var(--pm-divider);
}

.ai-sources__label {
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.68;
  font-weight: 700;
}

.ai-citation-card {
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(var(--v-theme-surface-variant), 0.32);
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: start;
  gap: 10px;
}

.ai-citation-card__left {
  width: 18px;
  min-width: 18px;
  opacity: 0.8;
  padding-top: 2px;
}

.ai-citation-card__content {
  min-width: 0;
}

.ai-citation-card__title {
  font-size: 0.83rem;
  font-weight: 700;
  line-height: 1.3;
}

.ai-citation-card__meta {
  margin-top: 2px;
  font-size: 0.74rem;
  opacity: 0.72;
}

.ai-citation-card__snippet {
  margin-top: 4px;
  font-size: 0.78rem;
  line-height: 1.35;
  opacity: 0.82;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ai-citation-card__hint {
  margin-top: 4px;
  font-size: 0.74rem;
  line-height: 1.35;
  opacity: 0.74;
}

.ai-citation-card__actions {
  display: flex;
  align-items: center;
}

.ai-chat-input {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  padding: 10px 12px;
}

.list-toolbar__main {
  display: flex;
  align-items: stretch;
}

.list-toolbar__search {
  width: 100%;
}

.list-toolbar__search :deep(.v-field) {
  border-radius: 10px;
  background: var(--pm-app-surface-raised);
}

.list-toolbar__search :deep(.v-field--focused) {
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.34);
}

.list-toolbar__upload-hint {
  min-height: 18px;
  font-size: 0.74rem;
  opacity: 0.76;
  padding-left: 2px;
}

.list-toolbar__upload-hint--warning {
  color: rgb(var(--v-theme-warning));
  opacity: 0.92;
}

.list-toolbar__loading {
  margin-top: 2px;
}

.active-filter-row {
  padding: 8px 12px 2px;
}

.document-list-shell {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  height: 100%;
}

.docs-header {
  display: flex;
  flex-direction: column;
}

.document-list-body {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.document-list-content {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.document-list-state {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.document-list-empty-state-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.document-list-body--dragover .document-row {
  pointer-events: none;
}

.menu-item--danger .v-list-item-title,
.menu-item--danger .v-list-item__prepend,
.menu-item--danger .v-icon {
  color: rgb(var(--v-theme-error)) !important;
  opacity: 1;
}

.document-list-drop-overlay {
  position: absolute;
  top: 8px;
  left: 10px;
  right: 10px;
  bottom: 10px;
  z-index: 4;
  pointer-events: none;
  border: 1px dashed rgba(var(--v-theme-primary), 0.36);
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), 0.07);
  display: flex;
  align-items: center;
  justify-content: center;
}

.document-list-drop-overlay__inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(var(--v-theme-primary), 0.24);
  background: rgba(var(--v-theme-surface), 0.78);
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.settings-loading {
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 0.84rem;
  opacity: 0.8;
}

.settings-theme-segmented {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 4px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 14px;
  background: rgba(var(--v-theme-on-surface), 0.035);
}

.settings-theme-segmented__item {
  min-height: 40px;
  border-radius: 11px;
  border: 1px solid transparent;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease;
}

.settings-theme-segmented__item:hover:not(:disabled) {
  background: rgba(var(--v-theme-on-surface), 0.055);
  color: rgba(var(--v-theme-on-surface), 0.9);
}

.settings-theme-segmented__item:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.settings-theme-segmented__item--active {
  border-color: rgba(var(--v-theme-primary), 0.32);
  background: rgba(var(--v-theme-primary), 0.16);
  color: rgb(var(--v-theme-on-surface));
  box-shadow: 0 1px 5px rgba(var(--v-theme-primary), 0.16);
}

/* ── Farbvarianten-Picker ───────────────────────────────────────────────────── */
.settings-color-variant-picker {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.settings-color-variant-picker__item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  padding: 0;
  border-radius: 12px;
  border: 2px solid transparent;
  background: rgba(var(--v-theme-on-surface), 0.04);
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease, transform 0.12s ease;
}

.settings-color-variant-picker__item:hover:not(:disabled) {
  background: rgba(var(--v-theme-on-surface), 0.08);
  transform: translateY(-1px);
}

.settings-color-variant-picker__item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-color-variant-picker__item--active {
  border-color: var(--variant-color);
  background: color-mix(in srgb, var(--variant-color) 12%, transparent);
}

.settings-color-variant-picker__swatch {
  display: block;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--variant-color);
  box-shadow: 0 2px 6px color-mix(in srgb, var(--variant-color) 40%, transparent);
  transition: box-shadow 0.16s ease;
}

.settings-color-variant-picker__item--active .settings-color-variant-picker__swatch {
  box-shadow: 0 3px 10px color-mix(in srgb, var(--variant-color) 55%, transparent);
}

.pm-settings-sections {
  display: block;
}

.pm-settings-section {
  background: rgba(var(--v-theme-on-surface), 0.03);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 18px;
  padding: 22px;
  margin-bottom: 24px;
}

.pm-settings-section:last-child {
  margin-bottom: 0;
}

.pm-settings-title {
  margin: 0 0 18px;
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.6;
  font-weight: 700;
}

.pm-settings-content {
  display: flex;
  flex-direction: column;
}

.pm-setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 14px 0;
}

.pm-setting-row + .pm-setting-row {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.04);
}

.pm-setting-row--column {
  align-items: stretch;
  flex-direction: column;
  gap: 10px;
}

.pm-setting-content {
  min-width: 0;
  flex: 1;
}

.pm-setting-label {
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.25;
}

.pm-setting-description {
  margin-top: 4px;
  font-size: 14px;
  line-height: 1.35;
  opacity: 0.6;
}

.pm-setting-hint {
  margin-top: 4px;
  font-size: 0.76rem;
  line-height: 1.3;
  color: rgba(var(--v-theme-primary), 0.92);
}

.settings-theme-select {
  max-width: none;
}

.pm-setting-select {
  width: 100%;
  margin-top: 8px;
}

:deep(.pm-settings-body) {
  padding-top: 16px;
  padding-bottom: 12px;
}

:deep(.pm-settings-footer) {
  padding: 18px 24px;
  justify-content: flex-end;
}

:deep(.pm-settings-card .pm-dialog__content-wrap) {
  max-height: calc(min(68vh, 760px) - 15px);
}

:deep(.app-modal__body--flush) {
  padding: 0;
}

.dialog-delete-copy {
  margin: 0;
  line-height: 1.45;
}

.saved-search-summary {
  margin-top: 12px;
  padding: 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(127, 127, 127, 0.05);
}

.saved-search-summary__title {
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  opacity: 0.72;
  text-transform: uppercase;
}

.saved-search-summary__content {
  margin-top: 6px;
  font-size: 0.84rem;
  opacity: 0.84;
}

.workspace {
  display: grid;
  grid-template-columns: 268px 1fr minmax(360px, 43%);
  height: calc(100dvh - var(--v-layout-top, 0px) - var(--v-layout-bottom, 0px));
}

.panel {
  border-right: 1px solid var(--pm-divider);
  overflow-y: auto;
  background: var(--pm-content-surface);
  position: relative;
}

.panel-left {
  background: var(--pm-sidebar-surface);
  position: relative;
}

.panel-middle {
  position: relative;
  background: var(--pm-content-surface);
}

.panel-middle__view {
  min-height: 100%;
}

.panel-right {
  border-right: 0;
  overflow: hidden;
  position: relative;
}

.views-list {
  padding: 6px;
  background: transparent !important;
  border-radius: 0;
  box-shadow: none;
}

.sidebar-section-header {
  min-height: 24px;
  padding: 4px 10px 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sidebar-section-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  opacity: 0.66;
  text-transform: none;
}

.sidebar-section-toggle {
  border: 0;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.7rem;
  line-height: 1.2;
  padding: 2px 4px;
  border-radius: 6px;
  cursor: pointer;
  opacity: 0;
  transform: translateY(-2px);
  pointer-events: none;
  transition: background-color 0.16s ease, color 0.16s ease, opacity 0.16s ease, transform 0.16s ease;
}

.sidebar-section-header:hover .sidebar-section-toggle,
.sidebar-section-header:focus-within .sidebar-section-toggle {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.sidebar-section-toggle:hover {
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.9);
}

.sidebar-section-toggle:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.7);
  outline-offset: 1px;
}

.sidebar-section-content {
  overflow: hidden;
}

.sidebar-section-collapse-enter-active,
.sidebar-section-collapse-leave-active {
  transition: max-height 0.24s ease, opacity 0.2s ease, transform 0.2s ease;
  overflow: hidden;
}

.sidebar-section-collapse-enter-from,
.sidebar-section-collapse-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-6px);
}

.sidebar-section-collapse-enter-to,
.sidebar-section-collapse-leave-from {
  max-height: 2000px;
  opacity: 1;
  transform: translateY(0);
}

@media (hover: none) {
  .sidebar-section-toggle {
    opacity: 1;
    transform: none;
    pointer-events: auto;
  }
}

.sidebar-section-divider {
  margin: 10px 12px 8px;
  opacity: 1;
}

.sidebar-section-divider.v-divider {
  border-color: var(--pm-divider);
}

.sidebar-item {
  position: relative;
  border-radius: 12px;
  margin: 2px 4px;
  transition: background-color 0.16s ease;
}

.sidebar-item {
  --v-list-prepend-gap: 10px;
}

.sidebar-item :deep(.v-list-item__prepend) {
  width: 24px;
  min-width: 24px;
  justify-content: center;
}

.sidebar-item :deep(.v-list-item-title) {
  font-size: 0.9rem;
}

.sidebar-item--primary :deep(.v-list-item-title) {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.96);
}

.sidebar-item--primary :deep(.v-icon) {
  opacity: 0.95;
}

.sidebar-item--secondary {
  --v-list-item-min-height: 34px;
}

.sidebar-item--secondary :deep(.v-list-item-title) {
  font-size: 0.84rem;
  opacity: 0.76;
}

.sidebar-item--secondary :deep(.v-icon) {
  opacity: 0.62;
}

.sidebar-item--secondary.v-list-item--active :deep(.v-list-item-title),
.sidebar-item--secondary.v-list-item--active :deep(.v-icon) {
  opacity: 1;
}

.sidebar-item:hover {
  background: var(--pm-sidebar-hover);
}

.pm-nav-item:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.28);
  outline-offset: 2px;
  border-radius: 12px;
}

.sidebar-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 0;
  border-radius: 3px;
  background: rgba(var(--v-theme-primary), 0.95);
  opacity: 0;
  transition: opacity 0.16s ease, width 0.16s ease;
}

.sidebar-item.v-list-item--active {
  background: var(--pm-sidebar-active);
}

.sidebar-item.v-list-item--active::before {
  display: none;
}

.sidebar-item.v-list-item--active :deep(.v-list-item-title) {
  font-weight: 600;
}

.sidebar-item--tag .sidebar-tag-pill {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(var(--v-theme-primary), 0.13);
  color: rgba(var(--v-theme-primary), 0.94);
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background-color 0.16s ease;
}

.sidebar-item--tag:hover .sidebar-tag-pill {
  background: rgba(var(--v-theme-primary), 0.18);
}

.sidebar-item--tag.v-list-item--active .sidebar-tag-pill {
  background: rgba(var(--v-theme-primary), 0.24);
}

.sidebar-folder-menu-btn {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 10px;
}

.sidebar-item--folder-create :deep(.v-list-item-title) {
  font-weight: 500;
}

.tags-view-toolbar {
  gap: 4px;
}

.tags-view {
  display: flow-root;
}

.tags-view-search {
  max-width: none;
}

.tags-view-search__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: -4px;
}

.tags-view-search__action-btn {
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 9px;
}

.tags-view-search__action-btn--create {
  color: rgba(var(--v-theme-primary), 0.96);
}

.tags-view-toolbar__hint {
  padding-left: 2px;
  font-size: 0.74rem;
  line-height: 1.25;
  opacity: 0.64;
}

.tags-view-cloud-wrap,
.tags-view-list-wrap {
  margin: 12px;
  padding: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: var(--pm-app-surface-raised);
}

.tags-view-section-title {
  margin-bottom: 8px;
  font-size: 0.74rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.7;
  font-weight: 700;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}

.tag-cloud-item {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(var(--v-theme-primary), 0.06);
  color: inherit;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.tag-cloud-item:hover {
  border-color: rgba(var(--v-theme-primary), 0.55);
  background: rgba(var(--v-theme-primary), 0.1);
  transform: translateY(-1px);
}

.tag-cloud-item small {
  font-size: 0.72em;
  opacity: 0.75;
  font-weight: 600;
}

.tag-table {
  display: grid;
  gap: 8px;
}

.tag-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 6px 8px 6px 10px;
  background: var(--pm-app-surface-raised);
  transition: border-color 0.16s ease, background 0.16s ease;
}

.tag-row:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.08);
}

.tag-row__name {
  border: 0;
  padding: 0;
  text-align: left;
  background: transparent;
  color: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.tag-row__count {
  min-width: 2ch;
  text-align: right;
  font-size: 0.82rem;
  opacity: 0.72;
}

.document-list {
  padding: 10px 10px 12px;
}

.document-row {
  width: 100%;
  display: grid;
  grid-template-columns: 58px 1fr auto;
  gap: 10px;
  align-items: center;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 12px;
  padding: 8px;
  background: var(--pm-app-surface-raised);
  text-align: left;
  margin-bottom: 0;
  cursor: pointer;
  box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    border-color     var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    box-shadow       var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.document-row + .document-row {
  margin-top: 10px;
}

.document-row:hover {
  background: var(--pm-row-active);
  border-color: rgba(59, 130, 246, 0.16);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
}

.document-row--active {
  background: var(--pm-row-active);
  border-color: rgba(59, 130, 246, 0.22);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.1), 0 5px 16px rgba(15, 23, 42, 0.1);
}

.papermind-app.v-theme--light .panel-middle,
.papermind-app.v-theme--light .document-list-shell,
.papermind-app.v-theme--light .document-list-body,
.papermind-app.v-theme--light .document-list-content {
  background: var(--pm-content-surface);
}

.papermind-app.v-theme--light .panel-left {
  background: var(--pm-sidebar-surface);
  box-shadow: inset -1px 0 0 var(--pm-light-outline);
  padding: 12px;
}

.papermind-app.v-theme--light .panel-left .views-list {
  padding: 0;
}

.papermind-app.v-theme--light .panel-middle {
  box-shadow: inset -1px 0 0 var(--pm-light-outline);
}

.papermind-app.v-theme--light .panel-right,
.papermind-app.v-theme--light .panel-right__preview {
  background: var(--pm-viewer-surface);
}

.papermind-app.v-theme--light .document-list {
  padding: 12px;
  background: var(--pm-content-surface);
}

.papermind-app.v-theme--light .sidebar-item {
  color: var(--pm-text);
}

.papermind-app.v-theme--light .sidebar-item--secondary :deep(.v-list-item-title),
.papermind-app.v-theme--light .sidebar-item--secondary :deep(.v-icon) {
  opacity: 0.78;
}

.papermind-app.v-theme--light .panel-left::before,
.papermind-app.v-theme--light .panel-middle::before,
.papermind-app.v-theme--light .panel-right::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(1200px 600px at 20% -10%, rgba(59, 130, 246, 0.1), transparent 55%);
  opacity: 0.25;
}

.papermind-app.v-theme--dark .sidebar-item--tag .sidebar-tag-pill {
  background: rgba(196, 207, 255, 0.17);
  color: rgba(236, 241, 255, 0.95);
}

.papermind-app.v-theme--dark .sidebar-item--tag:hover .sidebar-tag-pill {
  background: rgba(196, 207, 255, 0.22);
}

.papermind-app.v-theme--dark .sidebar-item--tag.v-list-item--active .sidebar-tag-pill {
  background: rgba(196, 207, 255, 0.26);
}

.papermind-app.v-theme--dark .document-row {
  background: var(--pm-dark-card);
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.22);
}

.papermind-app.v-theme--dark .document-list {
  padding: 12px;
  background: var(--pm-content-surface);
}

.papermind-app.v-theme--dark .app-main,
.papermind-app.v-theme--dark .workspace {
  background: var(--pm-app-surface);
}

.papermind-app.v-theme--dark .panel-left {
  background: var(--pm-sidebar-surface);
  box-shadow: inset -1px 0 0 var(--pm-dark-outline);
}

.papermind-app.v-theme--dark .panel-middle,
.papermind-app.v-theme--dark .document-list-shell,
.papermind-app.v-theme--dark .document-list-body,
.papermind-app.v-theme--dark .document-list-content,
.papermind-app.v-theme--dark .list-toolbar,
.papermind-app.v-theme--dark .tags-view-toolbar {
  background: var(--pm-content-surface);
}

.papermind-app.v-theme--dark .panel-middle {
  box-shadow: inset -1px 0 0 var(--pm-dark-outline);
}

.papermind-app.v-theme--dark .panel-right,
.papermind-app.v-theme--dark .panel-right__preview {
  background: var(--pm-viewer-surface);
}

.papermind-app.v-theme--dark .list-toolbar__search :deep(.v-field),
.papermind-app.v-theme--dark .tags-view-search :deep(.v-field),
.papermind-app.v-theme--dark .document-row,
.papermind-app.v-theme--dark .tags-view-cloud-wrap,
.papermind-app.v-theme--dark .tags-view-list-wrap,
.papermind-app.v-theme--dark .tag-row {
  background: var(--pm-app-surface-raised);
}

.papermind-app.v-theme--dark .list-toolbar__search :deep(.v-field),
.papermind-app.v-theme--dark .tags-view-search :deep(.v-field) {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field,
.papermind-app.v-theme--dark .tags-view-search .v-field {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.papermind-app.v-theme--dark .list-toolbar__search :deep(.v-field:hover),
.papermind-app.v-theme--dark .tags-view-search :deep(.v-field:hover) {
  background: rgba(255, 255, 255, 0.11);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field:hover,
.papermind-app.v-theme--dark .tags-view-search .v-field:hover {
  background: rgba(255, 255, 255, 0.11);
}

.papermind-app.v-theme--dark .list-toolbar__search :deep(.v-field--focused),
.papermind-app.v-theme--dark .tags-view-search :deep(.v-field--focused) {
  background: rgba(255, 255, 255, 0.13);
  box-shadow: inset 0 0 0 1px rgba(196, 207, 255, 0.28);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field--focused,
.papermind-app.v-theme--dark .tags-view-search .v-field--focused {
  background: rgba(255, 255, 255, 0.13);
  box-shadow: inset 0 0 0 1px rgba(196, 207, 255, 0.28);
}

.papermind-app.v-theme--dark .topbar-btn--import {
  background: color-mix(in srgb, var(--pm-appbar-bg) 72%, white 28%);
  border-color: color-mix(in srgb, var(--pm-appbar-bg) 54%, white 46%);
}

.papermind-app.v-theme--dark .topbar-btn--import:hover {
  background: color-mix(in srgb, var(--pm-appbar-bg) 64%, white 36%);
}

.papermind-app.v-theme--dark .topbar-btn--ghost:hover,
.papermind-app.v-theme--dark .topbar-btn--icon:hover {
  background: color-mix(in srgb, var(--pm-appbar-bg) 70%, white 30%);
}

.papermind-app.v-theme--dark .topbar-btn--active {
  background: color-mix(in srgb, var(--pm-appbar-bg) 58%, white 42%);
  border-color: color-mix(in srgb, var(--pm-appbar-bg) 48%, white 52%);
}

.papermind-app.v-theme--dark .document-row__meta,
.papermind-app.v-theme--dark .document-row__snippet {
  opacity: 0.9;
}

.papermind-app.v-theme--dark .document-row:hover {
  background: var(--pm-row-hover);
  border-color: rgba(var(--v-theme-primary), 0.28);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.26);
}

.papermind-app.v-theme--dark .document-row--active {
  background: var(--pm-row-active);
  border-color: rgba(var(--v-theme-primary), 0.44);
  box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.18), 0 5px 16px rgba(0, 0, 0, 0.28);
}

.papermind-app.v-theme--dark .document-row--active:hover {
  background: var(--pm-row-active);
  border-color: rgba(var(--v-theme-primary), 0.5);
}

.papermind-app.v-theme--dark .panel-left::before,
.papermind-app.v-theme--dark .panel-middle::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(1200px 600px at 20% -10%, rgba(59, 130, 246, 0.1), transparent 55%);
  opacity: 0.35;
}

.document-row__thumb {
  width: 52px;
  height: 72px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  overflow: hidden;
  background: #f4f4f4;
  display: flex;
  align-items: center;
  justify-content: center;
}

.document-row__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.document-row__thumb-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: rgba(0, 0, 0, 0.55);
}

.document-row__content {
  min-width: 0;
}

.document-row__title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 7px;
}

.document-row__unread-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 999px;
  background: rgba(var(--v-theme-primary), 0.96);
}

.papermind-app.v-theme--dark .document-row__unread-dot {
  background: rgba(147, 167, 255, 0.9);
}

.document-row__name {
  font-weight: 600;
  font-size: 0.92rem;
  line-height: 1.2;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.document-row__meta {
  font-size: 0.8rem;
  opacity: 0.72;
}

.document-row__meta-line {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.document-row__tags {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  min-width: 0;
  overflow: hidden;
}

.document-row__tag-chip {
  height: 20px;
  max-width: 150px;
  font-size: 0.68rem;
  letter-spacing: 0.01em;
}

.document-row__tag-chip :deep(.v-chip__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-row__tag-chip--more {
  max-width: none;
  font-variant-numeric: tabular-nums;
}

.document-row__snippet {
  margin-top: 6px;
  font-size: 0.78rem;
  line-height: 1.35;
  opacity: 0.88;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.document-row__snippet :deep(mark) {
  background: rgba(var(--v-theme-primary), 0.16);
  color: inherit;
  padding: 0 2px;
  border-radius: 3px;
}

.pm-doc-item:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.28);
  outline-offset: 2px;
  border-radius: 12px;
}

.document-row__aside {
  align-self: center;
  justify-self: end;
  display: flex;
  flex-direction: row;
  justify-content: flex-end;
  align-items: center;
  gap: 0;
}

.document-row__actions {
  min-height: 0;
  display: flex;
  align-items: center;
}

.document-row__menu-btn {
  opacity: 0.38;
  transition: opacity 0.16s ease, background-color 0.16s ease;
}

.document-row__menu-btn :deep(.v-icon) {
  font-size: 19px;
}

.document-row:hover .document-row__menu-btn,
.document-row:focus-within .document-row__menu-btn,
.document-row__menu-btn[aria-expanded='true'] {
  opacity: 1;
}

.document-row__fav-btn {
  opacity: 0.25 !important;
  transition: opacity 0.16s ease !important;
}

.document-row__fav-btn:hover {
  opacity: 0.6 !important;
}

.document-row__fav-btn--active {
  opacity: 1 !important;
  color: #f59e0b !important;
}

.document-row__fav-btn--active:hover {
  opacity: 1 !important;
}

.document-row__chips {
  align-self: start;
  display: grid;
  justify-items: end;
  gap: 4px;
}

.document-row__ocr-chip {
  opacity: 0.9;
  border-color: rgba(var(--v-theme-primary), 0.32);
  color: rgba(var(--v-theme-primary), 0.92);
}

.papermind-app.v-theme--dark .document-row__ocr-chip {
  background: rgba(147, 167, 255, 0.16);
  color: rgb(210, 220, 255);
  border-color: rgba(147, 167, 255, 0.4);
}

.panel-right {
  border-right: 0;
  overflow: hidden;
}

.panel-right__preview {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: var(--pm-viewer-surface);
}

.preview-frame-wrap {
  flex: 1;
  min-height: 0;
  padding: 0;
  display: flex;
  align-items: stretch;
  justify-content: center;
  background: var(--pm-pdf-stage-bg);
}

.preview-frame {
  width: 100%;
  height: 100%;
  border: 0;
  outline: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.details-drawer__header {
  padding: 8px 0;
  background: transparent;
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    transform        var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    opacity          var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.details-drawer__header:hover {
  background: transparent;
}

.details-drawer__header--collapsed .details-drawer__subtitle {
  opacity: 0.9;
}

.details-drawer__header--expanded .details-drawer__subtitle {
  opacity: 0.95;
}

.details-drawer__inner {
  width: 100%;
  max-width: 720px;
  box-sizing: border-box;
  margin: 0 auto;
  padding: 0 20px;
}

.details-drawer__body {
  padding: 0;
  display: block;
}

.pm-drawer-body {
  padding: 14px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pm-drawer-section {
  margin-top: 0;
}

.pm-label {
  font-size: 0.74rem;
  font-weight: 600;
  opacity: 0.85;
  margin-bottom: 6px;
}

.pm-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.pm-section-head .pm-label {
  margin-bottom: 0;
}

.details-tags-ai-btn {
  min-width: 24px;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  opacity: 0.9;
}

.details-tags-ai-btn :deep(.v-icon) {
  font-size: 15px;
}

.details-tags-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.details-tags-combobox {
  flex: 1;
  min-width: 0;
}

.pm-date-field {
  width: 100%;
  max-width: 220px;
  margin-right: auto;
}

.pm-date-field :deep(.v-field) {
  border-radius: 8px;
}

.pm-date-field :deep(.v-field__input) {
  min-height: 30px;
  font-size: 0.82rem;
}

.pm-drawer-section :deep(.v-input),
.pm-drawer-section :deep(.v-combobox),
.pm-drawer-section :deep(.v-textarea) {
  margin-top: 0;
  margin-bottom: 0;
}

.pm-drawer-section :deep(.v-input__details) {
  display: none;
}

.details-command-bar {
  min-height: 42px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.details-command-bar__left {
  min-width: 0;
}

.details-drawer__title-row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.details-drawer__title-wrap {
  min-width: 0;
}

.details-command-bar__right {
  justify-self: end;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.details-command-bar__right :deep(.v-btn) {
  min-width: 24px;
  opacity: 0.82;
}

.details-chevron-btn {
  width: 36px;
  height: 36px;
  min-width: 36px !important;
  border-radius: 999px;
  border: 1px solid var(--pm-divider);
  background: rgba(var(--v-theme-on-surface), 0.08);
  opacity: 1 !important;
}

.details-chevron-btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.14);
}

.details-chevron-btn :deep(.v-icon) {
  font-size: 24px;
  transition: transform 200ms ease-out;
  transform: rotate(0deg);
}

.details-header-progress {
  margin-top: 4px;
  opacity: 0.7;
}

.details-drawer__subtitle {
  margin-top: 0;
  font-size: 0.9rem;
  font-weight: 650;
  opacity: 0.92;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.details-drawer__meta-line {
  margin-top: 2px;
  font-size: 0.72rem;
  opacity: 0.66;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.details-drawer__meta-part {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.details-drawer__meta-dot {
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.75;
  flex: 0 0 auto;
}

.details-date-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-radius: 10px;
  padding: 6px 0;
  background: transparent;
  cursor: pointer;
  transition: background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.details-date-row:hover,
.details-date-row:focus-within {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.details-date-row__meta {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.details-date-row__label {
  font-size: 0.75rem;
  opacity: 0.74;
  margin-bottom: 0;
}

.details-date-row__value {
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.2;
}

.details-date-row__actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.details-date-row__native-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.details-tags-combobox :deep(.v-field) {
  border-radius: 8px;
}

.details-tags-combobox :deep(.v-field__input) {
  min-height: 34px;
  padding-top: 2px;
  padding-bottom: 2px;
}

.details-tags-combobox :deep(input) {
  font-size: 0.85rem;
  line-height: 1.42;
}

.details-tags-combobox :deep(.v-chip) {
  height: 22px;
  font-size: 12px;
  padding-inline: 7px;
}

.details-tags-combobox :deep(.v-chip .v-chip__close) {
  margin-inline-start: 2px;
}

:deep(.pm-menu.pm-menu--tags) {
  border-radius: 12px;
  background: rgba(var(--v-theme-surface-2), 0.96);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.38);
  padding: 3px;
  z-index: 6000 !important;
  overflow: hidden;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  opacity: 1 !important;
}

:deep(.v-overlay-container .pm-menu.pm-menu--tags) {
  z-index: 6000 !important;
}

:deep(.pm-menu.pm-menu--tags .v-list) {
  background: transparent;
  padding: 0;
  max-height: 180px;
  overflow: auto;
}

:deep(.pm-menu.pm-menu--tags .v-list-item) {
  min-height: 32px;
  border-radius: 10px;
  margin: 1px 0;
}

:deep(.pm-menu.pm-menu--tags .v-list-item-title) {
  font-size: 0.8rem;
}

:deep(.pm-menu.pm-menu--tags .v-list-item:hover) {
  background: rgba(255, 255, 255, 0.045);
}

:deep(.pm-menu.pm-menu--tags .v-list-item--active) {
  background: rgba(255, 255, 255, 0.08);
}

.pm-notes-field :deep(.v-field) {
  border-radius: 8px;
}

.pm-notes-field :deep(.v-field__input) {
  min-height: 44px;
  transition: min-height var(--pm-duration-normal, 210ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
  padding-top: 10px;
  padding-bottom: 10px;
  align-items: flex-start;
}

.pm-notes-field :deep(textarea) {
  font-size: 0.85rem;
  line-height: 1.42;
  margin-top: 0;
  padding-top: 0;
  min-height: 0;
  overflow-y: auto;
}

.details-ocr-action-btn {
  text-transform: none;
  font-size: 0.7rem;
  letter-spacing: 0.01em;
  min-height: 24px;
  padding-inline: 10px;
  border-radius: 999px;
}

.details-ocr-chip {
  font-size: 0.66rem;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.details-drawer__empty {
  margin: 0;
}

.panel-empty {
  padding: 16px;
  opacity: 0.72;
}

@media (max-width: 1260px) {
  .workspace {
    grid-template-columns: 248px 1fr;
  }

  .panel-right {
    grid-column: 1 / -1;
    height: min(68vh, 620px);
    border-top: 1px solid var(--pm-divider);
  }

  .details-drawer__inner {
    max-width: 640px;
  }
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
    height: auto;
  }

  .panel {
    border-right: 0;
    border-bottom: 1px solid var(--pm-divider);
  }

  .panel-right {
    height: min(64vh, 520px);
  }

  .details-drawer__inner {
    width: 100%;
    max-width: none;
    padding: 0 14px;
  }

  .pm-drawer-body {
    padding: 12px 12px 14px;
  }

  .topbar-btn--import {
    min-width: 0;
    padding: 0 10px;
  }

  .tags-view-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .tags-view-search {
    max-width: none;
  }

  .ai-page {
    height: min(72vh, 640px);
    min-height: 420px;
    padding: 10px;
  }

  .ai-suggestions__grid {
    grid-template-columns: 1fr;
  }
}
</style>
