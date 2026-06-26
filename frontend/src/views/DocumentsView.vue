<template>
  <v-main class="app-main">
      <BatchTagDialog
        v-model="isBatchTagDialogOpen"
        :tags="tags"
        :count="selectionIds.size"
        :loading="isBatchTagSaving"
        @confirm="executeBatchTag"
      />

      <BaseDialog
        v-model="isBatchCategoryDialogOpen"
        max-width="460"
        title="Dokumenttyp zuweisen"
        description="Den ausgewählten Dokumenten einen Dokumenttyp zuweisen."
        primary-text="Zuweisen"
        secondary-text="Abbrechen"
        :loading="isBatchCategorySaving"
        :primary-disabled="!batchCategoryValue"
        @primary="executeBatchCategory"
        @close="closeBatchCategoryDialog"
      >
        <div class="text-body-2 mb-3">
          {{ selectionIds.size }} {{ selectionIds.size === 1 ? 'Dokument erhält' : 'Dokumente erhalten' }} den gewählten Dokumenttyp.
        </div>
        <v-autocomplete
          v-model="batchCategoryValue"
          :items="categoryNames"
          label="Dokumenttyp"
          density="comfortable"
          variant="outlined"
          hide-details
          clearable
        />
      </BaseDialog>

      <BaseDialog
        v-model="isBatchTagMergeDialogOpen"
        max-width="460"
        title="Tags zusammenführen"
        description="Ausgewählte Tags auf einen Ziel-Tag verschieben."
        primary-text="Zusammenführen"
        secondary-text="Abbrechen"
        :loading="isBatchTagMerging"
        :primary-disabled="!batchTagMergeTargetId"
        @primary="submitBatchTagMerge"
        @close="closeBatchTagMergeDialog"
      >
        <div class="text-body-2 mb-3">
          {{ selectedTagIds.size }} {{ selectedTagIds.size === 1 ? 'Tag wird' : 'Tags werden' }} auf den Ziel-Tag übertragen.
        </div>
        <v-autocomplete
          v-model="batchTagMergeTargetId"
          :items="batchTagMergeCandidates"
          item-title="name"
          item-value="id"
          :return-object="false"
          label="Ziel-Tag"
          density="comfortable"
          variant="outlined"
          hide-details
        />
      </BaseDialog>

      <ImportStagingDialog
        ref="importStagingDialogRef"
        v-model="isUploadDialogOpen"
        :api-base-url="apiBaseUrl"
        :auto-embed="true"
        @minimize="onImportMinimized"
        @committed="onImportCommitted"
        @discarded-sources="onImportSourcesDiscarded"
      />
      <input
        ref="importPdfInputRef"
        class="d-none"
        type="file"
        accept="application/pdf"
        multiple
        @change="onImportPdfInputChange"
      />

      <Transition name="import-tray">
        <div v-if="isImportTrayVisible" class="import-tray" role="status" aria-live="polite">
          <div class="import-tray__icon">
            <v-icon size="20">mdi-file-import-outline</v-icon>
          </div>
          <div class="import-tray__content">
            <div class="import-tray__title">Import vorbereitet</div>
            <div class="import-tray__meta">{{ importTraySummary }}</div>
          </div>
          <div class="import-tray__actions">
            <v-btn size="small" variant="text" class="import-tray__action" @click="restoreMinimizedImport">
              Öffnen
            </v-btn>
            <v-btn
              size="small"
              variant="text"
              color="error"
              class="import-tray__action"
              @click="discardMinimizedImport"
            >
              Verwerfen
            </v-btn>
          </div>
        </div>
      </Transition>

      <TagDialogs ref="tagDialogsRef" @tag-mutated="onTagMutated" />
      <CategoryDialogs ref="categoryDialogsRef" @category-mutated="onCategoryMutated" />

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
        :categories="categoryNames"
        :api-base-url="apiBaseUrl"
        @save="handleSmartFolderSave"
        @close="closeSmartFolderEditor"
      />

      <AiDialog
        v-model="isAiDialogOpen"
        :api-base-url="apiBaseUrl"
        @open-citation="openCitation"
      />

      <div
        class="workspace"
        :class="{
          'workspace--rail': sidebarRailActive,
          'workspace--sidebar-transitioning': sidebarRailTransitioning,
          'workspace--sidebar-collapsing': sidebarRailTransitioning && sidebarCollapsed,
          'workspace--sidebar-expanding': sidebarRailTransitioning && !sidebarCollapsed
        }"
      >
        <AppSidebar
          :collapsed="sidebarContentCollapsed"
          :chat-active="isAiDialogOpen"
          :active-view="activeView"
          :active-saved-search-id="activeSavedSearchId"
          :active-tag-id="activeTagId"
          :is-tag-view="isTagView"
          :active-category-name="activeCategoryName"
          :is-category-view="isCategoryView"
          @select-view="selectView"
          @open-chat="openAiView"
          @open-saved-search="openSavedSearch"
          @create-folder="openCreateSavedSearchDialog"
          @edit-folder="openEditSavedSearchDialog"
          @delete-folder="deleteSavedSearch"
          @empty-trash="emptyTrash"
          @open-tags-view="openTagsView"
          @apply-tag-filter="applyTagFilterFromSidebar"
          @open-categories-view="openCategoriesView"
          @apply-category-filter="applyCategoryFilterFromSidebar"
        >
          <template #head>
            <div class="sidebar-head__top">
              <button type="button" class="sidebar-brand" @click="selectView('all')">
                <span class="sidebar-brand__mark"><v-icon size="18">mdi-brain</v-icon></span>
                <span class="sidebar-brand__name">PaperMind</span>
              </button>
              <button
                type="button"
                class="sidebar-rail-toggle"
                :aria-label="sidebarCollapsed ? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen'"
                @click="toggleSidebarRail"
              >
                <v-icon size="18">mdi-page-layout-sidebar-left</v-icon>
              </button>
            </div>
            <v-text-field
              ref="appBarSearchRef"
              v-model="searchText"
              class="sidebar-search__field"
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
          </template>

          <template #foot>
            <v-btn
              icon="mdi-cog-outline"
              variant="text"
              size="small"
              class="sidebar-foot__rail-settings"
              aria-label="Einstellungen"
              @click="uiStore.openSettings()"
            />
            <SidebarAccount />
            <div class="sidebar-foot__actions">
              <v-btn
                icon="mdi-cog-outline"
                variant="text"
                size="small"
                class="sidebar-foot__btn"
                aria-label="Einstellungen"
                @click="uiStore.openSettings()"
              />
              <ActivityIndicator ref="activityIndicatorRef" @open-backup="openBackupSettings" />
            </div>
          </template>
        </AppSidebar>

        <section
          class="panel panel-middle"
          :class="{ 'panel-middle--tag-filter-open': showTagFilterDrawer && isTagFilterDrawerOpen }"
          :style="tagFilterDrawerOffsetStyle"
        >
          <div class="panel-middle__header">
            <div class="panel-middle__heading">{{ panelHeading }}</div>
            <div v-if="!isTagView && !isCategoryView && !isTrashView" class="panel-middle__actions">
              <v-badge
                :model-value="pendingImportInboxCount > 0"
                :content="pendingImportInboxBadgeLabel"
                color="error"
                offset-x="6"
                offset-y="6"
              >
                <v-btn
                  class="list-header-btn"
                  color="primary"
                  variant="tonal"
                  @click="openImport"
                >
                  <v-icon size="18" class="mr-1">mdi-tray-arrow-up</v-icon>
                  Importieren
                </v-btn>
              </v-badge>
            </div>

            <div v-if="isTrashView" class="panel-middle__actions">
              <v-btn
                class="list-header-btn"
                color="error"
                variant="tonal"
                :disabled="!sidebarCounts.trash_count"
                @click="emptyTrash"
              >
                <v-icon size="18" class="mr-1">mdi-delete-forever-outline</v-icon>
                Endgültig löschen
              </v-btn>
            </div>
          </div>

          <Transition name="pm-panel">
            <div v-if="isTagView" key="tags" class="panel-middle__view tags-view">
              <ListActionToolbar
                :actions="tagToolbarActions"
                :right-actions="tagToolbarRightActions"
                :selection-mode="isTagSelectionMode"
                :selection-count="selectedTagIds.size"
                :selection-disabled="filteredTags.length === 0"
                @action-select="handleTagToolbarAction"
                @right-action="handleTagToolbarRightAction"
                @toggle-selection="toggleTagSelectionMode"
                @select-all="selectAllVisibleTags"
              />

              <div class="tags-view-list-wrap">
                <div v-if="filteredTags.length > 0" class="tag-table">
                  <div
                    v-for="tag in filteredTags"
                    :key="`row-${tag.id}`"
                    class="tag-row"
                    :class="{
                      'tag-row--selection-mode': isTagSelectionMode,
                      'tag-row--selected': selectedTagIds.has(tag.id)
                    }"
                    role="button"
                    tabindex="0"
                    @click="onTagRowClick(tag.id)"
                    @keydown.enter.prevent="onTagRowClick(tag.id)"
                    @keydown.space.prevent="onTagRowClick(tag.id)"
                  >
                    <div v-if="isTagSelectionMode" class="tag-row__checkbox" aria-hidden="true">
                      <v-icon v-if="selectedTagIds.has(tag.id)" size="14">mdi-check</v-icon>
                    </div>
                    <button type="button" class="tag-row__name" @click.stop="onTagRowClick(tag.id)">
                      {{ tag.name }}
                    </button>
                    <span class="tag-row__count">{{ tag.usage_count ?? 0 }}</span>
                    <v-menu location="bottom end">
                      <template #activator="{ props }">
                        <v-btn icon="mdi-dots-vertical" size="small" variant="text" v-bind="props" @click.stop />
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

            <div v-else-if="isCategoryView" key="categories" class="panel-middle__view tags-view">
              <ListActionToolbar
                :actions="categoryToolbarActions"
                :right-actions="categoryToolbarRightActions"
                :selection-mode="isCategorySelectionMode"
                :selection-count="selectedCategoryIds.size"
                :selection-disabled="filteredCategories.length === 0"
                @action-select="handleCategoryToolbarAction"
                @right-action="handleCategoryToolbarRightAction"
                @toggle-selection="toggleCategorySelectionMode"
                @select-all="selectAllVisibleCategories"
              />

              <div class="tags-view-list-wrap">
                <div v-if="filteredCategories.length > 0" class="tag-table">
                  <div
                    v-for="category in filteredCategories"
                    :key="`cat-row-${category.id}`"
                    class="tag-row"
                    :class="{
                      'tag-row--selection-mode': isCategorySelectionMode,
                      'tag-row--selected': selectedCategoryIds.has(category.id)
                    }"
                    role="button"
                    tabindex="0"
                    @click="onCategoryRowClick(category.id)"
                    @keydown.enter.prevent="onCategoryRowClick(category.id)"
                    @keydown.space.prevent="onCategoryRowClick(category.id)"
                  >
                    <div v-if="isCategorySelectionMode" class="tag-row__checkbox" aria-hidden="true">
                      <v-icon v-if="selectedCategoryIds.has(category.id)" size="14">mdi-check</v-icon>
                    </div>
                    <button type="button" class="tag-row__name" @click.stop="onCategoryRowClick(category.id)">
                      {{ category.name }}
                    </button>
                    <span class="tag-row__count">{{ category.usage_count ?? 0 }}</span>
                    <v-menu location="bottom end">
                      <template #activator="{ props }">
                        <v-btn icon="mdi-dots-vertical" size="small" variant="text" v-bind="props" @click.stop />
                      </template>
                      <v-list density="compact">
                        <v-list-item @click.stop="categoryDialogsRef?.openRename(category)">
                          <template #prepend>
                            <v-icon size="16">mdi-pencil-outline</v-icon>
                          </template>
                          <v-list-item-title>Umbenennen</v-list-item-title>
                        </v-list-item>
                        <v-list-item class="menu-item--danger" @click.stop="categoryDialogsRef?.openDelete(category)">
                          <template #prepend>
                            <v-icon size="16">mdi-trash-can-outline</v-icon>
                          </template>
                          <v-list-item-title>Löschen…</v-list-item-title>
                        </v-list-item>
                      </v-list>
                    </v-menu>
                  </div>
                </div>
                <div v-else class="panel-empty">Keine Dokumenttypen verfügbar.</div>
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
              :show-document-list-loading-state="showDocumentListLoadingState"
              :show-document-list-empty-state="showDocumentListEmptyState"
              :document-list-empty-state="documentListEmptyState"
              :show-snippets="showSnippets"
              :is-selection-mode="isSelectionMode"
              :selection-disabled="isAllDocumentsSelectionDisabled"
              :selection-ids="selectionIds"
              :current-sort="currentSort"
              :current-date-range="currentDateRange"
              :show-tag-filter-toggle="showTagFilterDrawer"
              :tag-filter-drawer-open="isTagFilterDrawerOpen"
              :bottom-spacer-height="tagFilterDocumentListSpacerHeight"
              :has-more-documents="hasMoreDocuments"
              :is-loading-more-documents="isLoadingMoreDocuments"
              :loaded-document-count="documentListLoadedCount"
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
              @change-date-range="applyDateRange"
              @toggle-tag-filter-drawer="toggleTagFilterDrawer"
              @load-more="loadMoreDocuments"
            />
          </Transition>
          <Transition :name="isTagFilterDrawerAnimationReady ? 'tag-filter-drawer' : ''">
            <div
              v-if="showTagFilterDrawer"
              ref="tagFilterDrawerRef"
              class="tag-filter-drawer pm-drawer"
              :class="[
                isTagFilterDrawerOpen
                  ? 'tag-filter-drawer--open pm-drawer--expanded'
                  : 'tag-filter-drawer--closed pm-drawer--collapsed',
                { 'tag-filter-drawer--animate': isTagFilterDrawerAnimationReady }
              ]"
              :aria-hidden="String(!isTagFilterDrawerOpen)"
            >
              <div class="tag-filter-drawer__panel">
                <div class="tag-filter-drawer__panel-inner">
                  <div class="tag-filter-drawer__body">
                    <TransitionGroup
                      tag="div"
                      name="tag-filter-chip-list"
                      class="tag-filter-drawer__chips"
                      aria-label="Tag-Filter"
                    >
                      <button
                        v-for="tag in visibleTagFilterOptions"
                        :key="`tag-filter-${tag.id}`"
                        type="button"
                        class="tag-filter-chip"
                        :class="{ 'tag-filter-chip--active': activeTagFilterIdsSet.has(tag.id) }"
                        :tabindex="isTagFilterDrawerOpen ? 0 : -1"
                        @click="toggleTagFilter(tag.id)"
                      >
                        <v-icon
                          v-if="activeTagFilterIdsSet.has(tag.id)"
                          class="tag-filter-chip__check"
                          size="13"
                        >
                          mdi-check
                        </v-icon>
                        <span class="tag-filter-chip__name">{{ tag.name }}</span>
                        <span class="tag-filter-chip__count">{{ tagFilterOptionCount(tag) }}</span>
                      </button>
                      <div v-if="visibleTagFilterOptions.length === 0" class="tag-filter-drawer__empty">
                        Keine Tags
                      </div>
                    </TransitionGroup>

                    <div class="tag-filter-drawer__footer">
                      <button
                        type="button"
                        class="tag-filter-drawer__footer-btn tag-filter-drawer__footer-btn--all"
                        :tabindex="isTagFilterDrawerOpen ? 0 : -1"
                        @click="showAllTagFilters"
                      >
                        Alle Tags
                      </button>
                      <button
                        type="button"
                        class="tag-filter-drawer__footer-btn tag-filter-drawer__footer-btn--reset"
                        :disabled="activeTagFilterCount === 0"
                        :tabindex="isTagFilterDrawerOpen ? 0 : -1"
                        @click="resetTagFilters"
                      >
                        Zurücksetzen
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>
          <BatchActionsBar
            v-if="isSelectionMode"
            :count="selectionIds.size"
            :actions="documentBatchActions"
            @tag="openBatchTagDialog"
            @favorite="executeBatchFavorite"
            @category="openBatchCategoryDialog"
            @delete="confirmBatchDelete"
          />
          <BatchActionsBar
            v-if="isTagSelectionMode"
            :count="selectedTagIds.size"
            singular-label="Tag"
            plural-label="Tags"
            :actions="tagBatchActions"
            @merge="openBatchTagMergeDialog"
            @delete="confirmBatchTagDelete"
          />
          <BatchActionsBar
            v-if="isCategorySelectionMode"
            :count="selectedCategoryIds.size"
            singular-label="Dokumenttyp"
            plural-label="Dokumenttypen"
            :actions="categoryBatchActions"
            @delete="confirmBatchCategoryDelete"
          />
        </section>

        <section class="panel panel-right">
          <DocumentPreviewLayout
            class="panel-right__preview"
            :show-drawer="!isTagView && !isCategoryView && Boolean(selectedDocumentDetail)"
            :is-open="isDetailsDrawerOpen"
            :collapsed-height="DETAILS_DRAWER_COLLAPSED_HEIGHT"
            :expanded-height="detailsDrawerHeight"
            :default-expanded-height="DETAILS_DRAWER_DEFAULT_HEIGHT"
            @update:expanded-height="setDetailsDrawerHeight"
          >
            <template #viewer>
              <div
                v-if="isTagView"
                class="tag-focus-panel"
              >
                <div class="tag-focus-panel__stats" role="group" aria-label="Tag-Filter">
                  <button
                    type="button"
                    class="tag-focus-stat"
                    :class="{ 'tag-focus-stat--active': tagUsageFilter === 'all' }"
                    :aria-pressed="tagUsageFilter === 'all'"
                    @click="setTagUsageFilter('all')"
                  >
                    <strong>{{ tagCloudStats.total }}</strong>
                    <span>Gesamt</span>
                  </button>
                  <button
                    type="button"
                    class="tag-focus-stat"
                    :class="{ 'tag-focus-stat--active': tagUsageFilter === 'used' }"
                    :aria-pressed="tagUsageFilter === 'used'"
                    @click="setTagUsageFilter('used')"
                  >
                    <strong>{{ tagCloudStats.assigned }}</strong>
                    <span>Genutzt</span>
                  </button>
                  <button
                    type="button"
                    class="tag-focus-stat"
                    :class="{ 'tag-focus-stat--active': tagUsageFilter === 'unused' }"
                    :aria-pressed="tagUsageFilter === 'unused'"
                    @click="setTagUsageFilter('unused')"
                  >
                    <strong>{{ tagCloudStats.unused }}</strong>
                    <span>Leer</span>
                  </button>
                </div>

                <Transition name="tag-cloud-swap" mode="out-in">
                <div
                  v-if="filteredTags.length > 0"
                  :key="tagUsageFilter"
                  class="tag-focus-cloud"
                  :class="{ 'tag-focus-cloud--selection-mode': isTagSelectionMode }"
                  aria-label="Tag-Wolke"
                >
                  <div
                    v-for="item in tagCloudItems"
                    :key="`focus-cloud-${item.tag.id}`"
                    class="tag-focus-cloud__item"
                    :class="{ 'tag-focus-cloud__item--selected': selectedTagIds.has(item.tag.id) }"
                    :style="item.style"
                  >
                    <button
                      type="button"
                      class="tag-focus-chip"
                      @click="onTagRowClick(item.tag.id)"
                    >
                      <span class="tag-focus-chip__name">{{ item.tag.name }}</span>
                      <span class="tag-focus-chip__count">{{ item.usage }}</span>
                    </button>
                    <v-menu location="bottom end">
                      <template #activator="{ props }">
                        <v-btn
                          icon="mdi-dots-vertical"
                          size="x-small"
                          variant="text"
                          class="tag-focus-chip__menu"
                          aria-label="Tag-Aktionen"
                          v-bind="props"
                        />
                      </template>
                      <v-list density="compact">
                        <v-list-item @click.stop="tagDialogsRef?.openRename(item.tag)">
                          <template #prepend>
                            <v-icon size="16">mdi-pencil-outline</v-icon>
                          </template>
                          <v-list-item-title>Umbenennen</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click.stop="tagDialogsRef?.openMerge(item.tag)">
                          <template #prepend>
                            <v-icon size="16">mdi-source-merge</v-icon>
                          </template>
                          <v-list-item-title>Zusammenführen</v-list-item-title>
                        </v-list-item>
                        <v-list-item class="menu-item--danger" @click.stop="tagDialogsRef?.openDelete(item.tag)">
                          <template #prepend>
                            <v-icon size="16">mdi-trash-can-outline</v-icon>
                          </template>
                          <v-list-item-title>Löschen…</v-list-item-title>
                        </v-list-item>
                      </v-list>
                    </v-menu>
                  </div>
                </div>
                <PmEmptyState
                  v-else
                  key="empty"
                  icon="mdi-tag-search-outline"
                  title="Keine Tags gefunden"
                  subtitle="Passe die Suche an oder erstelle einen neuen Tag."
                  size="md"
                />
                </Transition>

              </div>
              <div
                v-else-if="isCategoryView"
                class="tag-focus-panel"
              >
                <div class="tag-focus-panel__stats" role="group" aria-label="Dokumenttyp-Filter">
                  <button
                    type="button"
                    class="tag-focus-stat"
                    :class="{ 'tag-focus-stat--active': categoryUsageFilter === 'all' }"
                    :aria-pressed="categoryUsageFilter === 'all'"
                    @click="setCategoryUsageFilter('all')"
                  >
                    <strong>{{ categoryCloudStats.total }}</strong>
                    <span>Gesamt</span>
                  </button>
                  <button
                    type="button"
                    class="tag-focus-stat"
                    :class="{ 'tag-focus-stat--active': categoryUsageFilter === 'used' }"
                    :aria-pressed="categoryUsageFilter === 'used'"
                    @click="setCategoryUsageFilter('used')"
                  >
                    <strong>{{ categoryCloudStats.assigned }}</strong>
                    <span>Genutzt</span>
                  </button>
                  <button
                    type="button"
                    class="tag-focus-stat"
                    :class="{ 'tag-focus-stat--active': categoryUsageFilter === 'unused' }"
                    :aria-pressed="categoryUsageFilter === 'unused'"
                    @click="setCategoryUsageFilter('unused')"
                  >
                    <strong>{{ categoryCloudStats.unused }}</strong>
                    <span>Leer</span>
                  </button>
                </div>

                <Transition name="tag-cloud-swap" mode="out-in">
                <div
                  v-if="filteredCategories.length > 0"
                  :key="categoryUsageFilter"
                  class="tag-focus-cloud"
                  :class="{ 'tag-focus-cloud--selection-mode': isCategorySelectionMode }"
                  aria-label="Dokumenttyp-Wolke"
                >
                  <div
                    v-for="item in categoryCloudItems"
                    :key="`focus-cloud-cat-${item.category.id}`"
                    class="tag-focus-cloud__item"
                    :class="{ 'tag-focus-cloud__item--selected': selectedCategoryIds.has(item.category.id) }"
                    :style="item.style"
                  >
                    <button
                      type="button"
                      class="tag-focus-chip"
                      @click="onCategoryRowClick(item.category.id)"
                    >
                      <span class="tag-focus-chip__name">{{ item.category.name }}</span>
                      <span class="tag-focus-chip__count">{{ item.usage }}</span>
                    </button>
                    <v-menu location="bottom end">
                      <template #activator="{ props }">
                        <v-btn
                          icon="mdi-dots-vertical"
                          size="x-small"
                          variant="text"
                          class="tag-focus-chip__menu"
                          aria-label="Dokumenttyp-Aktionen"
                          v-bind="props"
                        />
                      </template>
                      <v-list density="compact">
                        <v-list-item @click.stop="categoryDialogsRef?.openRename(item.category)">
                          <template #prepend>
                            <v-icon size="16">mdi-pencil-outline</v-icon>
                          </template>
                          <v-list-item-title>Umbenennen</v-list-item-title>
                        </v-list-item>
                        <v-list-item class="menu-item--danger" @click.stop="categoryDialogsRef?.openDelete(item.category)">
                          <template #prepend>
                            <v-icon size="16">mdi-trash-can-outline</v-icon>
                          </template>
                          <v-list-item-title>Löschen…</v-list-item-title>
                        </v-list-item>
                      </v-list>
                    </v-menu>
                  </div>
                </div>
                <PmEmptyState
                  v-else
                  key="empty-categories"
                  icon="mdi-file-search-outline"
                  title="Keine Dokumenttypen gefunden"
                  subtitle="Passe die Suche an oder erstelle einen neuen Dokumenttyp."
                  size="md"
                />
                </Transition>

              </div>
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
                  @open-original="openSelectedDocumentInNewTab"
                />
              </div>
              <PmEmptyState
                v-else
                icon="mdi-file-document-outline"
                title="Kein Dokument ausgewählt"
                subtitle="Wähle ein Dokument aus der Liste, um die Vorschau zu öffnen."
                size="md"
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
                          <div v-if="headerMetaParts.length || headerOcrStatus" class="details-drawer__meta-line">
                            <template v-for="(part, index) in headerMetaParts" :key="`meta-${index}`">
                              <span class="details-drawer__meta-part">{{ part }}</span>
                              <span
                                v-if="index < headerMetaParts.length - 1 || headerOcrStatus"
                                class="details-drawer__meta-dot"
                                aria-hidden="true"
                              />
                            </template>
                            <span
                              v-if="headerOcrStatus"
                              class="details-ocr-status"
                              :class="`details-ocr-status--${headerOcrStatus.tone}`"
                            >
                              <v-progress-circular
                                v-if="headerOcrStatus.tone === 'progress'"
                                indeterminate
                                size="11"
                                width="2"
                              />
                              <v-icon v-else size="13">{{ headerOcrStatus.icon }}</v-icon>
                              {{ headerOcrStatus.text }}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="details-command-bar__right" @click.stop>
                      <!-- Primäre Aktion: KI-Befüllung (hervorgehoben) -->
                      <v-tooltip text="Leere Felder mit KI befüllen" location="bottom">
                        <template #activator="{ props: aiTooltipProps }">
                          <v-btn
                            v-if="hasEmptyMetadataField"
                            v-bind="aiTooltipProps"
                            size="small"
                            density="comfortable"
                            variant="text"
                            class="details-action-btn details-action-btn--primary"
                            :loading="isRunningAiAnalysis"
                            :disabled="isRunningAiAnalysis"
                            aria-label="Leere Felder mit KI befüllen"
                            @click="runAiAnalysis"
                          >
                            <v-icon size="18" color="primary">mdi-auto-fix</v-icon>
                          </v-btn>
                        </template>
                      </v-tooltip>

                      <!-- Sekundäre Aktionen: Überlauf-Menü (leise) -->
                      <v-menu v-if="headerMenuActions.length" location="bottom end">
                        <template #activator="{ props: menuProps }">
                          <v-btn
                            v-bind="menuProps"
                            icon="mdi-dots-vertical"
                            size="small"
                            density="comfortable"
                            variant="text"
                            class="details-action-btn details-action-btn--quiet"
                            aria-label="Weitere Aktionen"
                          />
                        </template>
                        <v-list density="compact">
                          <v-list-item
                            v-for="action in headerMenuActions"
                            :key="action.key"
                            @click.stop="action.handler"
                          >
                            <template #prepend>
                              <v-icon size="16">{{ action.icon }}</v-icon>
                            </template>
                            <v-list-item-title>{{ action.label }}</v-list-item-title>
                          </v-list-item>
                        </v-list>
                      </v-menu>

                      <!-- Disclosure: Auf-/Zuklappen (leise, strukturell) -->
                      <v-btn
                        :icon="detailsDrawerChevronIcon"
                        size="small"
                        density="comfortable"
                        variant="text"
                        class="details-action-btn details-action-btn--quiet details-chevron-btn"
                        :class="{ 'details-chevron-btn--expanded': isDetailsDrawerChevronExpanded }"
                        aria-label="Details ein- oder ausklappen"
                        @click="toggleDetailsDrawer"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <template #drawer-body>
              <div v-if="selectedDocumentDetail" class="details-drawer__body">
                <div
                  class="details-drawer__inner pm-drawer-body"
                  @focusin="handleDetailsEditorFocusIn"
                  @focusout="handleDetailsEditorFocusOut"
                >
                  <div class="pm-prop">
                    <div class="pm-prop-row">
                      <label class="pm-prop-key">Dokumentname</label>
                      <div class="pm-prop-val">
                        <div class="pm-prop-field">
                          <v-text-field
                            v-model="metadataDocName"
                            class="pm-name-field"
                            density="compact"
                            variant="plain"
                            placeholder="Dokumentname…"
                            hide-details
                            @blur="commitMetadataTextFields"
                          />
                        </div>
                      </div>
                    </div>

                    <div class="pm-prop-row">
                      <label class="pm-prop-key">Dokumentdatum</label>
                      <div class="pm-prop-val">
                        <div class="pm-prop-field pm-prop-field--inline">
                          <v-text-field
                            v-model="metadataDocDate"
                            class="pm-date-field"
                            density="compact"
                            variant="plain"
                            placeholder="TT.MM.JJJJ"
                            inputmode="numeric"
                            maxlength="10"
                            hide-details
                            :error="metadataDocDateHasError"
                            @blur="handleDocumentDateBlur"
                            @keydown="handleDocumentDateShortcut"
                          />
                        </div>
                      </div>
                    </div>

                    <div class="pm-prop-row">
                      <label class="pm-prop-key">Dokumenttyp</label>
                      <div class="pm-prop-val">
                        <div class="pm-prop-value-with-action">
                          <div class="pm-prop-field">
                            <v-select
                              :model-value="metadataDocCategory"
                              :items="categoryDrawerItems"
                              density="compact"
                              variant="plain"
                              hide-details
                              clearable
                              placeholder="Dokumenttyp wählen…"
                              :loading="isSavingCategory"
                              :menu-props="detailsCategoryMenuProps"
                              @update:model-value="onMetadataCategoryChange"
                            />
                          </div>
                          <v-btn
                            icon
                            variant="text"
                            size="small"
                            class="pm-prop-settings-link"
                            title="Dokumenttypen verwalten"
                            aria-label="Dokumenttypen verwalten"
                            @click="openDocumentTypeSettings"
                          >
                            <v-icon size="17">mdi-cog-outline</v-icon>
                          </v-btn>
                        </div>
                      </div>
                    </div>

                    <div class="pm-prop-row">
                      <label class="pm-prop-key">Korrespondent</label>
                      <div class="pm-prop-val">
                        <div class="pm-prop-value-with-action">
                          <div class="pm-prop-field">
                            <v-combobox
                              :model-value="metadataCorrespondentDraft"
                              :items="correspondentDrawerItems"
                              item-title="title"
                              item-value="value"
                              :return-object="false"
                              density="compact"
                              variant="plain"
                              hide-details
                              clearable
                              placeholder="Korrespondent wählen oder neu anlegen…"
                              :loading="isSavingCorrespondent || correspondentStore.isMutationRunning"
                              :menu-props="detailsCorrespondentMenuProps"
                              @update:model-value="onMetadataCorrespondentInput"
                              @keydown.enter.prevent="commitMetadataCorrespondent"
                              @blur="handleMetadataCorrespondentBlur"
                              @focus="correspondentStore.ensureLoaded()"
                            >
                              <template #item="{ props: itemProps, item }">
                                <v-list-item v-bind="itemProps" :prepend-icon="undefined" :title="undefined">
                                  <template #title>
                                    <span class="pm-corr-opt">
                                      <span class="pm-corr-opt__icon">
                                        <v-icon v-if="item.raw?.kind === 'collection'" size="16">mdi-shape-outline</v-icon>
                                      </span>
                                      <span class="pm-corr-opt__label">
                                        {{ item.raw?.name || item.title }}<template v-if="item.raw?.kind === 'collection'"> · Sammlung</template>
                                      </span>
                                    </span>
                                  </template>
                                </v-list-item>
                              </template>
                              <template #selection="{ item }">
                                {{ item.raw?.short_name || item.raw?.name || item.title }}
                                <span v-if="item.raw?.kind === 'collection'"> · Sammlung</span>
                              </template>
                              <template #no-data>
                                <v-list-item title="Als neuen Korrespondenten anlegen" />
                              </template>
                            </v-combobox>
                          </div>
                          <v-btn
                            icon
                            variant="text"
                            size="small"
                            class="pm-prop-settings-link"
                            title="Korrespondenten verwalten"
                            aria-label="Korrespondenten verwalten"
                            @click="openCorrespondentSettings"
                          >
                            <v-icon size="17">mdi-cog-outline</v-icon>
                          </v-btn>
                        </div>
                      </div>
                    </div>

                    <div class="pm-prop-row pm-prop-row--top">
                      <label class="pm-prop-key">Tags</label>
                      <div class="pm-prop-val">
                        <div class="pm-tags-input" :class="{ 'pm-tags-input--disabled': isRunningAiAnalysis }">
                          <v-chip
                            v-for="name in metadataTagNames"
                            :key="name"
                            size="small"
                            closable
                            class="pm-tags-input__chip"
                            @click:close="removeMetadataTag(name)"
                          >
                            {{ name }}
                          </v-chip>
                          <v-combobox
                            ref="metadataTagsCombobox"
                            v-model="metadataTagNames"
                            v-model:search="metadataTagSearch"
                            :items="allTagNames"
                            multiple
                            hide-selected
                            :clearable="false"
                            density="compact"
                            variant="plain"
                            hide-details
                            class="pm-tags-input__field"
                            :placeholder="metadataTagNames.length ? '' : 'Tag hinzufügen…'"
                            :loading="isSavingTags || isResolvingTagNames"
                            :disabled="isRunningAiAnalysis"
                            :menu-props="detailsTagsMenuProps"
                            @update:model-value="onMetadataTagNamesChange"
                            @keydown="handleMetadataTagShortcut"
                          >
                            <template #selection></template>
                          </v-combobox>
                        </div>
                      </div>
                    </div>

                    <div class="pm-prop-row pm-prop-row--top">
                      <label class="pm-prop-key">Notizen</label>
                      <div class="pm-prop-val">
                        <div class="pm-prop-field pm-prop-field--area">
                          <v-textarea
                            v-model="metadataNotes"
                            :rows="3"
                            :max-rows="8"
                            auto-grow
                            density="compact"
                            variant="plain"
                            placeholder="Notiz hinzufügen…"
                            hide-details
                            class="pm-notes-field"
                            @blur="commitMetadataTextFields"
                          />
                        </div>
                      </div>
                    </div>
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
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useTheme } from 'vuetify';
import BaseDialog from '../components/BaseDialog.vue';
import PmEmptyState from '../components/PmEmptyState.vue';
import DocumentPreviewLayout from '../components/DocumentPreviewLayout.vue';
import NotificationStack from '../components/NotificationStack.vue';
import AppSidebar from '../components/AppSidebar.vue';
import SidebarAccount from '../components/SidebarAccount.vue';
import ActivityIndicator from '../components/ActivityIndicator.vue';
import DocumentListPanel from '../components/DocumentListPanel.vue';
import ListActionToolbar from '../components/ListActionToolbar.vue';
import BatchActionsBar from '../components/BatchActionsBar.vue';
// Ref-basiert geöffnet (ref.open()) → müssen synchron als Instanz verfügbar
// sein, daher eager.
import TagDialogs from '../components/TagDialogs.vue';
import CategoryDialogs from '../components/CategoryDialogs.vue';
import RenameDocumentDialog from '../components/RenameDocumentDialog.vue';

// Boolean-gesteuerte Dialoge (öffnen über v-model). Erst bei Bedarf gebraucht
// und teils sehr groß (ImportStagingDialog/SmartFolderEditor) → eigene Chunks,
// damit sie nicht den kritischen Boot-Pfad von DocumentsView blockieren.
const DeleteDocumentDialog = defineAsyncComponent(() => import('../components/DeleteDocumentDialog.vue'));
const ImportStagingDialog = defineAsyncComponent(() => import('../components/ImportStagingDialog.vue'));
const BatchTagDialog = defineAsyncComponent(() => import('../components/BatchTagDialog.vue'));
const SmartFolderEditor = defineAsyncComponent(() => import('../components/SmartFolderEditor.vue'));
const AiDialog = defineAsyncComponent(() => import('../components/AiDialog.vue'));
import { mapApiError, notifyError, logDevError, useNotifications } from '../stores/notifications';
import { useSettingsStore } from '../stores/settings';
import { useUiStore } from '../stores/ui';
import { useDocumentStore } from '../stores/documents';
import { useTagStore } from '../stores/tags';
import { useCategoryStore } from '../stores/categories';
import { useCorrespondentStore } from '../stores/correspondents';
import { useSidebarStore } from '../stores/sidebar';
import { useImportStagingStore } from '../stores/importStaging';
import {
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildDrawerRememberStatePatch,
  buildRecentImportWindowPatch,
  buildShowFilenameSuffixPatch,
  buildSortOrderPatch,
  buildThemeModePatch
} from '../utils/settingsApi';
import { formatDateTime, formatDocumentDateInputFromIso, parseDocumentDateInput } from '../utils/dates';
import { useOcrPolling } from '../composables/useOcrPolling';
import { useGlobalKeyboard } from '../composables/useGlobalKeyboard';
import { useSearch } from '../composables/useSearch';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts';
import { authedUrl, getBaseUrl } from '../api/client.js';
import { assignImportInboxItems, claimImportInboxItems, discardImportInboxItems, getImportInbox } from '../api/importInbox.js';
import { applyPaperMindVuetifyColors, resolvePaperMindColorVariant } from '../theme/tokens';

const PdfPreview = defineAsyncComponent(() => import('../components/PdfPreview.vue'));

const apiBaseUrl = getBaseUrl();

const SETTINGS_SORT_TO_QUERY = {
  newest: { sort: 'document_date', order: 'desc' },
  oldest: { sort: 'document_date', order: 'asc' },
  document_date_desc: { sort: 'document_date', order: 'desc' },
  document_date_asc: { sort: 'document_date', order: 'asc' },
  name_asc: { sort: 'name', order: 'asc' },
  name_desc: { sort: 'name', order: 'desc' },
  last_opened: { sort: 'updated_at', order: 'desc' },
  favorites: { sort: 'favorite', order: 'desc' }
};
const TAG_USAGE_FILTER_OPTIONS = Object.freeze([
  { value: 'all', label: 'Alle Tags' },
  { value: 'used', label: 'Genutzte Tags' },
  { value: 'unused', label: 'Leere Tags' }
]);
const TAG_SORT_OPTIONS = Object.freeze([
  { value: 'usage_desc', label: 'Meist genutzt' },
  { value: 'usage_asc', label: 'Wenig genutzt' },
  { value: 'used_first', label: 'Genutzt zuerst' },
  { value: 'unused_first', label: 'Ungenutzt zuerst' }
]);
const TAG_BATCH_ACTIONS = Object.freeze([
  { key: 'merge', label: 'Zusammenführen', icon: 'mdi-source-merge' },
  { key: 'delete', label: 'Löschen', icon: 'mdi-trash-can-outline', color: 'error' }
]);
const CATEGORY_USAGE_FILTER_OPTIONS = Object.freeze([
  { value: 'all', label: 'Alle Dokumenttypen' },
  { value: 'used', label: 'Genutzte Dokumenttypen' },
  { value: 'unused', label: 'Leere Dokumenttypen' }
]);
const CATEGORY_SORT_OPTIONS = Object.freeze([
  { value: 'usage_desc', label: 'Meist genutzt' },
  { value: 'usage_asc', label: 'Wenig genutzt' },
  { value: 'name_asc', label: 'Name A–Z' },
  { value: 'name_desc', label: 'Name Z–A' }
]);
const CATEGORY_BATCH_ACTIONS = Object.freeze([
  { key: 'delete', label: 'Löschen', icon: 'mdi-trash-can-outline', color: 'error' }
]);
const DOCUMENT_BATCH_ACTIONS = Object.freeze([
  { key: 'tag', label: 'Tags', icon: 'mdi-tag-multiple-outline' },
  { key: 'category', label: 'Dokumenttyp', icon: 'mdi-file-document-outline' },
  { key: 'delete', label: 'In Papierkorb', icon: 'mdi-trash-can-outline', color: 'error' }
]);

const TAG_REPLACE_DEBOUNCE_MS = 300;
const METADATA_AUTOSAVE_DEBOUNCE_MS = 900;
const PREVIEW_RETRY_BASE_DELAY_MS = 600;
const PREVIEW_RETRY_MAX_DELAY_MS = 4500;
const PREVIEW_RETRY_MAX_ATTEMPTS = 5;
const IMPORTS_RECENT_LIMIT = 100;
const VOCAB_NAME_MIN_LENGTH = 2;
const VOCAB_NAME_MAX_LENGTH = 30;
const DETAILS_MENU_BASE_PROPS = Object.freeze({
  location: 'top start',
  origin: 'bottom start',
  offset: 10,
  attach: 'body',
  zIndex: 6000,
  scrollStrategy: 'reposition'
});
const detailsCategoryMenuProps = Object.freeze({
  ...DETAILS_MENU_BASE_PROPS,
  maxHeight: 240,
  contentClass: 'pm-menu'
});
const detailsCorrespondentMenuProps = Object.freeze({
  ...DETAILS_MENU_BASE_PROPS,
  maxHeight: 240,
  contentClass: 'pm-menu pm-menu--correspondent'
});
const detailsTagsMenuProps = Object.freeze({
  ...DETAILS_MENU_BASE_PROPS,
  maxHeight: 180,
  closeOnContentClick: false,
  contentClass: 'pm-menu pm-menu--tags'
});

const DETAILS_DRAWER_COLLAPSED_HEIGHT = 72;
const DETAILS_DRAWER_DEFAULT_HEIGHT = 320;
const LAST_SELECTED_DOC_KEY = 'pm.lastSelectedDocumentId';
const DOCUMENT_TOOLBAR_STATE_KEY = 'pm.documentToolbarState';
const TAG_TOOLBAR_STATE_KEY = 'pm.tagToolbarState';
const DOCUMENT_TOOLBAR_VIEW_KEYS = Object.freeze(['all', 'imports', 'untagged', 'favorites', 'no_text', 'trash']);
const DOCUMENT_STATUS_FILTER_VALUES = Object.freeze(['imported', 'processing', 'ready', 'failed']);
const DOCUMENT_DATE_RANGE_VALUES = Object.freeze(['this_year', 'last_year', 'last_30_days', 'last_12_months']);

function readStoredLastSelectedDocId() {
  try { return window.localStorage.getItem(LAST_SELECTED_DOC_KEY) || null; } catch { return null; }
}

function persistLastSelectedDocId(id) {
  try {
    if (id) window.localStorage.setItem(LAST_SELECTED_DOC_KEY, String(id));
    else     window.localStorage.removeItem(LAST_SELECTED_DOC_KEY);
  } catch { /* ignore */ }
}

function readStoredJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function writeStoredJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch { /* ignore */ }
}

function normalizeDocumentSortKey(value) {
  const key = String(value || '').trim();
  return SETTINGS_SORT_TO_QUERY[key] ? key : null;
}

function normalizeDocumentStatusFilter(value) {
  const key = String(value || '').trim();
  return DOCUMENT_STATUS_FILTER_VALUES.includes(key) ? key : null;
}

function normalizeDocumentDateRange(value) {
  const key = String(value || '').trim();
  return DOCUMENT_DATE_RANGE_VALUES.includes(key) ? key : null;
}

function toIsoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Übersetzt ein Zeitraum-Preset in konkrete document_date-Grenzen (lokale Zeit).
function computeDateRangeBounds(rangeKey) {
  const key = normalizeDocumentDateRange(rangeKey);
  if (!key) {
    return { dateFrom: null, dateTo: null };
  }
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (key === 'this_year') {
    return { dateFrom: `${today.getFullYear()}-01-01`, dateTo: `${today.getFullYear()}-12-31` };
  }
  if (key === 'last_year') {
    const year = today.getFullYear() - 1;
    return { dateFrom: `${year}-01-01`, dateTo: `${year}-12-31` };
  }
  if (key === 'last_30_days') {
    const from = new Date(today);
    from.setDate(from.getDate() - 29);
    return { dateFrom: toIsoDate(from), dateTo: toIsoDate(today) };
  }
  if (key === 'last_12_months') {
    const from = new Date(today);
    from.setMonth(from.getMonth() - 12);
    return { dateFrom: toIsoDate(from), dateTo: toIsoDate(today) };
  }
  return { dateFrom: null, dateTo: null };
}

function normalizeTagUsageFilter(value) {
  const key = String(value || '').trim();
  return TAG_USAGE_FILTER_OPTIONS.some((option) => option.value === key) ? key : 'all';
}

function normalizeTagSortMode(value) {
  const key = String(value || '').trim();
  return TAG_SORT_OPTIONS.some((option) => option.value === key) ? key : 'usage_desc';
}

function readDocumentToolbarState() {
  const raw = readStoredJson(DOCUMENT_TOOLBAR_STATE_KEY, {});
  const sourceViews = raw?.views && typeof raw.views === 'object' ? raw.views : raw;
  const views = {};
  for (const viewKey of DOCUMENT_TOOLBAR_VIEW_KEYS) {
    const entry = sourceViews?.[viewKey] && typeof sourceViews[viewKey] === 'object'
      ? sourceViews[viewKey]
      : {};
    const sort = normalizeDocumentSortKey(entry.sort);
    const status = normalizeDocumentStatusFilter(entry.status);
    const dateRange = normalizeDocumentDateRange(entry.dateRange);
    if (sort || status || dateRange) {
      views[viewKey] = { sort, status, dateRange };
    }
  }
  return { views };
}

function readTagToolbarState() {
  const raw = readStoredJson(TAG_TOOLBAR_STATE_KEY, {});
  return {
    usage: normalizeTagUsageFilter(raw?.usage),
    sort: normalizeTagSortMode(raw?.sort)
  };
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
const uiStore = useUiStore();
const docStore     = useDocumentStore();
const tagStore     = useTagStore();
const categoryStore = useCategoryStore();
const correspondentStore = useCorrespondentStore();
const sidebarStore = useSidebarStore();
const importStagingStore = useImportStagingStore();

const { documents, selectedDocumentId, selectedDocumentDetail, isLoadingDocuments } = storeToRefs(docStore);
const { tags, isTagMutationRunning } = storeToRefs(tagStore);
const { categoryNames, categories, sortedCategories } = storeToRefs(categoryStore);
const {
  documentCount: importTrayDocumentCount,
  totalPages: importTrayPageCount
} = storeToRefs(importStagingStore);

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
watch(activeView, (nextView, previousView) => {
  if (nextView === previousView) {
    return;
  }
  exitSelectionMode();
  exitTagSelectionMode();
  closeBatchTagMergeDialog();
});
const activeSavedSearchId = ref(null);
const activeSavedSearchQuery = ref(null);
const documentToolbarState = reactive(readDocumentToolbarState());
const initialDocumentToolbarState = documentToolbarState.views.all || {};
const initialDocumentSort = SETTINGS_SORT_TO_QUERY[normalizeDocumentSortKey(initialDocumentToolbarState.sort) || 'newest'];
const initialDateRange = computeDateRangeBounds(normalizeDocumentDateRange(initialDocumentToolbarState.dateRange));
const documentListQuery = reactive({
  q: null,
  tagId: null,
  tagIds: [],
  documentType: null,
  untagged: null,
  status: normalizeDocumentStatusFilter(initialDocumentToolbarState.status),
  dateFrom: initialDateRange.dateFrom,
  dateTo: initialDateRange.dateTo,
  sort: initialDocumentSort.sort,
  order: initialDocumentSort.order,
  limit: 50,
  offset: 0
});
const documentListTotal = ref(0);
const documentListLoadedCount = ref(0);
const isLoadingMoreDocuments = ref(false);
const hasMoreDocuments = computed(() =>
  documentListLoadedCount.value < documentListTotal.value
);
let documentListRequestGeneration = 0;

// Stale-while-revalidate-Cache für die erste Seite je Ansicht/Filter/Sortierung.
// Beim Wechsel zwischen Ordnern/Tags/Ansichten wird die zuletzt gesehene Liste
// sofort gezeigt (kein Skeleton-Flash) und im Hintergrund neu geladen. Wird durch
// jeden fetchDocuments-Aufruf nach Mutationen automatisch frisch gehalten.
const DOCUMENT_LIST_CACHE_LIMIT = 12;
const documentListCache = new Map();

function readDocumentListCache(key) {
  return documentListCache.get(key) || null;
}

function writeDocumentListCache(key, entry) {
  // LRU: vorhandenen Key ans Ende rücken, ältesten verdrängen.
  if (documentListCache.has(key)) {
    documentListCache.delete(key);
  } else if (documentListCache.size >= DOCUMENT_LIST_CACHE_LIMIT) {
    const oldest = documentListCache.keys().next().value;
    if (oldest !== undefined) documentListCache.delete(oldest);
  }
  documentListCache.set(key, entry);
}

const activeTagId = computed({
  get: () => {
    const ids = normalizeTagIds(documentListQuery.tagIds);
    if (ids.length === 1) {
      return ids[0];
    }
    return documentListQuery.tagId;
  },
  set: (value) => {
    documentListQuery.tagId = value || null;
    documentListQuery.tagIds = value ? [value] : [];
  }
});
const tagSearchText = ref('');
const isTagFilterDrawerOpen = ref(false);
const isTagFilterDrawerAnimationReady = ref(false);
const tagFilterDrawerRef = ref(null);
const tagFilterDrawerHeight = ref(0);
const initialTagToolbarState = readTagToolbarState();
const tagUsageFilter = ref(initialTagToolbarState.usage);
const tagSortMode = ref(initialTagToolbarState.sort);
const isTagSelectionMode = ref(false);
const selectedTagIds = ref(new Set());
const isBatchTagMergeDialogOpen = ref(false);
const batchTagMergeTargetId = ref(null);
const isBatchTagMerging = ref(false);
const isBatchTagDeleting = ref(false);

const tagSearchField = ref(null);
const isSavingSavedSearch = ref(false);
const isSmartFolderEditorOpen = ref(false);
const smartFolderEditorMode = ref('create');
const smartFolderEditorTarget = ref(null);

const tagDialogsRef = ref(null);

// ── Kategorie-Verwaltungsansicht (analog Tag-Ansicht) ──────────────────────
const categorySearchText = ref('');
const categoryUsageFilter = ref('all');
const categorySortMode = ref('usage_desc');
const isCategorySelectionMode = ref(false);
const selectedCategoryIds = ref(new Set());
const isBatchCategoryDeleting = ref(false);
const categoryDialogsRef = ref(null);

const previewTargetPage    = ref(null);
const previewHighlightText = ref('');


const importStagingDialogRef = ref(null);
const activityIndicatorRef = ref(null);
const importPdfInputRef = ref(null);
const importInboxItems = ref([]);
const isImportInboxLoading = ref(false);
const importInboxSuppressedItemIds = ref(new Set());
const activeImportInboxItemIds = ref(new Set());
const activeImportInboxSourceToItemId = ref(new Map());
const isClaimingImportInbox = ref(false);
// Unterscheidet Minimieren (Items behalten) von echtem Schließen ohne Commit (verwerfen).
const isMinimizingImport = ref(false);
const isDocumentListSettling = ref(false);
let documentListSettleTimer = null;
const notifiedOcrQualityKeys = new Set();
let hasCompletedInitialImportInboxRefresh = false;
let knownImportInboxItemIds = new Set();
let isAutoOpeningImportInbox = false;

// ── Batch-Auswahl ──────────────────────────────────────────────────────────
const isSelectionMode = ref(false);
const selectionIds    = ref(new Set());
const isBatchFavoriteSaving = ref(false);

function toggleSelectionMode() {
  if (!isSelectionMode.value && isAllDocumentsSelectionDisabled.value) {
    return;
  }
  isSelectionMode.value = !isSelectionMode.value;
  if (isSelectionMode.value) {
    isTagFilterDrawerOpen.value = false;
  }
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

const currentDateRange = computed(() => {
  if (activeSavedSearchId.value) {
    return '';
  }
  return resolveDocumentToolbarState(activeView.value).dateRange || '';
});

function documentToolbarViewKey(viewKey = activeView.value) {
  const normalized = String(viewKey || '').trim();
  return DOCUMENT_TOOLBAR_VIEW_KEYS.includes(normalized) ? normalized : 'all';
}

function documentToolbarEntry(viewKey = activeView.value) {
  const key = documentToolbarViewKey(viewKey);
  if (!documentToolbarState.views[key]) {
    documentToolbarState.views[key] = { sort: null, status: null, dateRange: null };
  }
  return documentToolbarState.views[key];
}

function persistDocumentToolbarState() {
  writeStoredJson(DOCUMENT_TOOLBAR_STATE_KEY, {
    views: DOCUMENT_TOOLBAR_VIEW_KEYS.reduce((result, viewKey) => {
      const entry = documentToolbarState.views[viewKey] || {};
      const sort = normalizeDocumentSortKey(entry.sort);
      const status = normalizeDocumentStatusFilter(entry.status);
      const dateRange = normalizeDocumentDateRange(entry.dateRange);
      if (sort || status || dateRange) {
        result[viewKey] = { sort, status, dateRange };
      }
      return result;
    }, {})
  });
}

function updateDocumentToolbarState(viewKey, patch) {
  const entry = documentToolbarEntry(viewKey);
  if (Object.prototype.hasOwnProperty.call(patch, 'sort')) {
    entry.sort = normalizeDocumentSortKey(patch.sort);
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'status')) {
    entry.status = normalizeDocumentStatusFilter(patch.status);
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'dateRange')) {
    entry.dateRange = normalizeDocumentDateRange(patch.dateRange);
  }
  persistDocumentToolbarState();
}

function resolveDocumentToolbarState(viewKey = activeView.value) {
  const entry = documentToolbarState.views[documentToolbarViewKey(viewKey)] || {};
  const sortKey = normalizeDocumentSortKey(entry.sort) || appSettings.value.documents.sort_order || 'newest';
  const mapping = SETTINGS_SORT_TO_QUERY[sortKey] || SETTINGS_SORT_TO_QUERY.newest;
  const dateRange = normalizeDocumentDateRange(entry.dateRange);
  const { dateFrom, dateTo } = computeDateRangeBounds(dateRange);
  return {
    sortKey,
    status: normalizeDocumentStatusFilter(entry.status),
    dateRange,
    dateFrom,
    dateTo,
    sort: mapping.sort,
    order: mapping.order
  };
}

function resolveToolbarStatus(viewKey = activeView.value) {
  if (activeSavedSearchId.value) {
    return null;
  }
  return resolveDocumentToolbarState(viewKey).status;
}

function persistTagToolbarState() {
  writeStoredJson(TAG_TOOLBAR_STATE_KEY, {
    usage: normalizeTagUsageFilter(tagUsageFilter.value),
    sort: normalizeTagSortMode(tagSortMode.value)
  });
}

function applySort(sortKey) {
  const mapping = SETTINGS_SORT_TO_QUERY[sortKey];
  if (!mapping) return;
  updateDocumentToolbarState(activeView.value, { sort: sortKey });
  documentListQuery.sort  = mapping.sort;
  documentListQuery.order = mapping.order;
  void fetchDocuments(selectedDocumentId.value);
}

function applyDateRange(rangeKey) {
  const normalized = normalizeDocumentDateRange(rangeKey);
  updateDocumentToolbarState(activeView.value, { dateRange: normalized });
  const { dateFrom, dateTo } = computeDateRangeBounds(normalized);
  documentListQuery.dateFrom = dateFrom;
  documentListQuery.dateTo = dateTo;
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
      await docStore.syncTags(docId, mergedTagIds);
    }
    notify({ type: 'success', title: 'Tags', message: `${ids.length} ${ids.length === 1 ? 'Dokument' : 'Dokumente'} getaggt.` });
    isBatchTagDialogOpen.value = false;
    exitSelectionMode();
    await fetchTags();
    scheduleSidebarCountsRefresh();
    await fetchDocuments(selectedDocumentId.value, { allowPreferredOutsideList: true });
  } catch (error) {
    notifyError(error, 'Tags konnten nicht gespeichert werden.');
  } finally {
    isBatchTagSaving.value = false;
  }
}

// ── Batch Dokumenttyp-Dialog ───────────────────────────────────────────────
const isBatchCategoryDialogOpen = ref(false);
const isBatchCategorySaving     = ref(false);
const batchCategoryValue        = ref(null);

function openBatchCategoryDialog() {
  if (selectionIds.value.size === 0) return;
  batchCategoryValue.value = null;
  void categoryStore.ensureLoaded();
  isBatchCategoryDialogOpen.value = true;
}

function closeBatchCategoryDialog() {
  isBatchCategoryDialogOpen.value = false;
}

async function executeBatchCategory() {
  const value = String(batchCategoryValue.value || '').trim();
  if (!value || selectionIds.value.size === 0) return;
  const validationMessage = validateVocabName(value, 'Dokumenttyp');
  if (validationMessage) {
    notify({ type: 'warning', message: validationMessage });
    return;
  }
  isBatchCategorySaving.value = true;
  const ids = Array.from(selectionIds.value);
  try {
    for (const docId of ids) {
      await docStore.patchDocument(docId, { document_type: value });
    }
    notify({ type: 'success', title: 'Dokumenttyp', message: `${ids.length} ${ids.length === 1 ? 'Dokument' : 'Dokumente'} aktualisiert.` });
    isBatchCategoryDialogOpen.value = false;
    batchCategoryValue.value = null;
    exitSelectionMode();
    await categoryStore.fetchCategories();
    scheduleSidebarCountsRefresh();
    await fetchDocuments(selectedDocumentId.value, { allowPreferredOutsideList: true });
  } catch (error) {
    notifyError(error, 'Dokumenttyp konnte nicht gespeichert werden.');
  } finally {
    isBatchCategorySaving.value = false;
  }
}

// ── Batch Favoriten ───────────────────────────────────────────────────────
async function executeBatchFavorite() {
  if (selectionIds.value.size === 0 || isBatchFavoriteSaving.value) return;

  const targetFavoriteState = !areAllSelectedDocumentsFavorites.value;
  const documentsToUpdate = selectedDocuments.value.filter(
    (document) => Boolean(document.is_favorite) !== targetFavoriteState
  );
  if (documentsToUpdate.length === 0) return;

  const updatedDocumentIds = [];
  isBatchFavoriteSaving.value = true;
  try {
    for (const document of documentsToUpdate) {
      const response = await fetch(`${apiBaseUrl}/api/documents/${document.id}/favorite`, { method: 'POST' });
      if (!response.ok) throw new Error(await parseResponseError(response));
      const updated = await response.json();
      favoriteStateByDocumentId.set(updated.id, {
        value: Boolean(updated.is_favorite),
        updatedAt: Date.parse(String(updated.updated_at || '')) || Date.now()
      });
      updatedDocumentIds.push(updated.id);
    }

    const count = documentsToUpdate.length;
    notify({
      type: 'success',
      title: 'Favoriten',
      message: targetFavoriteState
        ? `${count} ${count === 1 ? 'Dokument wurde' : 'Dokumente wurden'} als Favorit markiert.`
        : `${count} ${count === 1 ? 'Dokument wurde' : 'Dokumente wurden'} aus den Favoriten entfernt.`
    });
    exitSelectionMode();
    scheduleSidebarCountsRefresh();
    await fetchDocuments(
      targetFavoriteState || !isFavoritesView.value ? selectedDocumentId.value : null,
      { autoSelectFirst: isFavoritesView.value }
    );
  } catch (error) {
    notifyError(error, 'Favoriten-Status konnte nicht für alle Dokumente geändert werden.');
    await fetchDocuments(selectedDocumentId.value, { autoSelectFirst: isFavoritesView.value });
    if (updatedDocumentIds.length > 0) {
      const visibleDocumentIds = new Set(documents.value.map((document) => document.id));
      selectionIds.value = new Set(
        Array.from(selectionIds.value).filter((documentId) => visibleDocumentIds.has(documentId))
      );
      if (selectionIds.value.size === 0) {
        exitSelectionMode();
      }
    }
    scheduleSidebarCountsRefresh();
  } finally {
    isBatchFavoriteSaving.value = false;
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
const isImportTrayVisible = ref(false);
const listDropNotice = ref('');
const previewReloadNonce = ref(0);
const importTraySummary = computed(() => {
  const docs = Number(importTrayDocumentCount.value || 0);
  const pages = Number(importTrayPageCount.value || 0);
  const docLabel = `${docs} ${docs === 1 ? 'Dokument' : 'Dokumente'}`;
  const pageLabel = `${pages} ${pages === 1 ? 'Seite' : 'Seiten'}`;
  return `${docLabel} · ${pageLabel}`;
});

const isDetailsDrawerOpen = computed({
  get: () => settingsStore.drawerExpanded,
  set: (value) => {
    settingsStore.setDrawerExpanded(value);
  }
});
const isDetailsDrawerChevronExpanded = computed(() => isDetailsDrawerOpen.value);
const detailsDrawerChevronIcon = computed(() =>
  isDetailsDrawerChevronExpanded.value ? 'mdi-chevron-down' : 'mdi-chevron-up'
);
const detailsDrawerHeight = computed(() => settingsStore.drawerHeight);
function setDetailsDrawerHeight(value) {
  settingsStore.setDrawerHeight(value);
}
const metadataTagsCombobox = ref(null);

const metadataDocName = ref('');
const metadataDocDate = ref('');
const metadataDocDateHasError = ref(false);
const metadataDocCategory = ref(null);
const isSavingCategory = ref(false);
const metadataCorrespondentId = ref(null);
const metadataCorrespondentDraft = ref(null);
const isSavingCorrespondent = ref(false);
const metadataNotes = ref('');
const metadataTagIds = ref([]);
const metadataTagNames = ref([]);
const metadataTagSearch = ref('');
const metadataDraftDocumentId = ref(null);
const metadataDraftRevision = ref(0);
const metadataTagDraftRevision = ref(0);
const detailsEditorHasFocus = ref(false);
const isSavingMetadata = ref(false);
const isSavingTags = ref(false);
const isResolvingTagNames = ref(false);
const isRunningAiAnalysis = ref(false);
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

// OCR läuft gerade für das ausgewählte Dokument (POST unterwegs, aktiver OCR-Job
// oder Dokument 'processing' und noch nicht OCR-fertig). Steuert den Spinner, der
// in diesem Fall den "OCR durchführen"-Button ersetzt.
const isOcrInProgress = computed(() => {
  if (isQueueingHeaderOcr.value || hasActiveOcrJob.value) {
    return true;
  }
  const detail = selectedDocumentDetail.value;
  return Boolean(detail && detail.status === 'processing' && detail.ocr_status !== 'done');
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
  // Grüner Chip nur bei tatsächlich OCR-analysierten Dokumenten. Für nicht
  // OCR-analysierte (auch mit eingebetteter Textebene) greift stattdessen der
  // "OCR durchführen"-Button (showHeaderOcrActionButton = !showGreenOcrChip).
  return hasCompletedOcr.value;
});
const showHeaderOcrActionButton = computed(() => {
  return Boolean(selectedDocumentDetail.value) && !showGreenOcrChip.value;
});
// OCR-Status für die Meta-Zeile (Status, keine Aktion): fertig/unsicher/fehler oder laufend.
// Wenn OCR noch aussteht, liefert dies null – die Aktion liegt dann im Überlauf-Menü.
const headerOcrStatus = computed(() => {
  if (!selectedDocumentDetail.value) {
    return null;
  }
  if (isOcrInProgress.value) {
    return { tone: 'progress', text: 'OCR läuft…', icon: '' };
  }
  if (showGreenOcrChip.value) {
    const status = String(selectedDocumentDetail.value?.ocr_quality_status || '').toLowerCase();
    if (status === 'error') {
      return { tone: 'error', text: 'OCR prüfen', icon: 'mdi-alert-circle-outline' };
    }
    if (status === 'warning') {
      return { tone: 'warning', text: 'OCR unsicher', icon: 'mdi-alert-circle-outline' };
    }
    return { tone: 'done', text: 'OCR', icon: 'mdi-check-circle-outline' };
  }
  return null;
});
// Sekundäre Aktionen für das Überlauf-Menü (⋮). Wächst künftig hier zentral.
const headerMenuActions = computed(() => {
  const actions = [];
  if (showHeaderOcrActionButton.value) {
    actions.push({
      key: 'ocr',
      label: 'OCR durchführen',
      icon: 'mdi-text-recognition',
      handler: queueOcrFromHeader
    });
  }
  return actions;
});
const isTagView       = computed(() => activeView.value === 'tags');
const isCategoryView  = computed(() => activeView.value === 'categories');
const activeCategoryName = computed(() => documentListQuery.documentType || null);
const isImportsView   = computed(() => activeView.value === 'imports');
const isUntaggedView  = computed(() => activeView.value === 'untagged');
const isFavoritesView = computed(() => activeView.value === 'favorites');
const isNoTextView    = computed(() => activeView.value === 'no_text');
const isTrashView     = computed(() => activeView.value === 'trash');
const isAllDocumentsSelectionDisabled = computed(() => {
  return activeView.value === 'all' &&
    !isLoadingSidebarCounts.value &&
    Number(sidebarCounts.value.all_documents || 0) <= 0;
});
const tagNameCollator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });
const tagCloudAccentPalette = Object.freeze([
  '44, 114, 182',
  '42, 135, 121',
  '191, 122, 44',
  '126, 96, 191',
  '177, 77, 103',
  '90, 132, 64'
]);
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
  return sortedTagsByName.value
    .filter((tag) => {
      const usage = Number(tag?.usage_count || 0);
      if (tagUsageFilter.value === 'used' && usage <= 0) {
        return false;
      }
      if (tagUsageFilter.value === 'unused' && usage > 0) {
        return false;
      }
      if (!query) {
        return true;
      }
      return tag.name.toLocaleLowerCase('de-DE').includes(query);
    })
    .sort(compareTagsForCurrentSort);
});
const tagUsageFilterLabel = computed(() => {
  return TAG_USAGE_FILTER_OPTIONS.find((option) => option.value === tagUsageFilter.value)?.label || 'Alle Tags';
});
const tagSortLabel = computed(() => {
  return TAG_SORT_OPTIONS.find((option) => option.value === tagSortMode.value)?.label || 'Meist genutzt';
});
const tagToolbarActions = computed(() => [
  {
    key: 'sort',
    icon: 'mdi-sort',
    label: tagSortLabel.value,
    value: tagSortMode.value,
    options: TAG_SORT_OPTIONS,
    minWidth: 170
  },
  {
    key: 'usage',
    icon: 'mdi-filter-variant',
    label: tagUsageFilterLabel.value,
    value: tagUsageFilter.value,
    active: tagUsageFilter.value !== 'all',
    options: TAG_USAGE_FILTER_OPTIONS,
    minWidth: 170
  }
]);
const tagToolbarRightActions = computed(() => [
  {
    key: 'create',
    label: 'Hinzufügen',
    disabled: isTagSelectionMode.value
  }
]);
const tagBatchActions = computed(() => TAG_BATCH_ACTIONS);
const selectedDocuments = computed(() => {
  const selected = selectionIds.value;
  return documents.value.filter((document) => selected.has(document.id));
});
const areAllSelectedDocumentsFavorites = computed(() =>
  selectedDocuments.value.length > 0
  && selectedDocuments.value.every((document) => Boolean(document.is_favorite))
);
const documentBatchActions = computed(() => {
  if (isTrashView.value) {
    return DOCUMENT_BATCH_ACTIONS;
  }
  const favoriteAction = {
    key: 'favorite',
    label: areAllSelectedDocumentsFavorites.value ? 'Stern entfernen' : 'Favorit',
    icon: areAllSelectedDocumentsFavorites.value ? 'mdi-star-off-outline' : 'mdi-star-outline',
    color: areAllSelectedDocumentsFavorites.value ? 'warning' : undefined,
    disabled: isBatchFavoriteSaving.value,
    loading: isBatchFavoriteSaving.value
  };
  return [
    DOCUMENT_BATCH_ACTIONS[0],
    favoriteAction,
    ...DOCUMENT_BATCH_ACTIONS.slice(1)
  ];
});
const selectedTags = computed(() => {
  const selected = selectedTagIds.value;
  return sortedTagsByName.value.filter((tag) => selected.has(tag.id));
});
const batchTagMergeCandidates = computed(() => {
  const selected = selectedTagIds.value;
  return sortedTagsByName.value.filter((tag) => !selected.has(tag.id));
});
const visibleTagIds = computed(() => filteredTags.value.map((tag) => tag.id).filter(Boolean));
watch(filteredTags, () => {
  if (!isTagSelectionMode.value || selectedTagIds.value.size === 0) {
    return;
  }
  const visibleIds = new Set(visibleTagIds.value);
  selectedTagIds.value = new Set([...selectedTagIds.value].filter((tagId) => visibleIds.has(tagId)));
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
const tagCloudItems = computed(() => {
  return [...filteredTags.value]
    .map((tag, index) => ({
      tag,
      usage: Number(tag?.usage_count || 0),
      style: tagCloudItemStyle(tag, index)
    }));
});
const tagCloudStats = computed(() => {
  const source = sortedTagsByName.value;
  const assigned = source.filter((tag) => Number(tag?.usage_count || 0) > 0).length;
  return {
    total: source.length,
    assigned,
    unused: Math.max(0, source.length - assigned)
  };
});

// ── Kategorie-Verwaltungsansicht: abgeleiteter Zustand ──────────────────────
const activeCategoriesForView = computed(() =>
  sortedCategories.value.filter((category) => category?.is_active !== false)
);
const filteredCategories = computed(() => {
  const query = categorySearchText.value.trim().toLocaleLowerCase('de-DE');
  return activeCategoriesForView.value
    .filter((category) => {
      const usage = Number(category?.usage_count || 0);
      if (categoryUsageFilter.value === 'used' && usage <= 0) return false;
      if (categoryUsageFilter.value === 'unused' && usage > 0) return false;
      if (!query) return true;
      return String(category?.name || '').toLocaleLowerCase('de-DE').includes(query);
    })
    .sort(compareCategoriesForCurrentSort);
});
const categoryUsageFilterLabel = computed(() =>
  CATEGORY_USAGE_FILTER_OPTIONS.find((option) => option.value === categoryUsageFilter.value)?.label || 'Alle Dokumenttypen'
);
const categorySortLabel = computed(() =>
  CATEGORY_SORT_OPTIONS.find((option) => option.value === categorySortMode.value)?.label || 'Meist genutzt'
);
const categoryToolbarActions = computed(() => [
  {
    key: 'sort',
    icon: 'mdi-sort',
    label: categorySortLabel.value,
    value: categorySortMode.value,
    options: CATEGORY_SORT_OPTIONS,
    minWidth: 170
  },
  {
    key: 'usage',
    icon: 'mdi-filter-variant',
    label: categoryUsageFilterLabel.value,
    value: categoryUsageFilter.value,
    active: categoryUsageFilter.value !== 'all',
    options: CATEGORY_USAGE_FILTER_OPTIONS,
    minWidth: 190
  }
]);
const categoryToolbarRightActions = computed(() => [
  {
    key: 'create',
    label: 'Hinzufügen',
    disabled: isCategorySelectionMode.value
  }
]);
const categoryBatchActions = computed(() => CATEGORY_BATCH_ACTIONS);
const visibleCategoryIds = computed(() => filteredCategories.value.map((category) => category.id).filter(Boolean));
watch(filteredCategories, () => {
  if (!isCategorySelectionMode.value || selectedCategoryIds.value.size === 0) {
    return;
  }
  const visibleIds = new Set(visibleCategoryIds.value);
  selectedCategoryIds.value = new Set([...selectedCategoryIds.value].filter((id) => visibleIds.has(id)));
});
const maxCategoryUsageCount = computed(() => {
  if (!activeCategoriesForView.value.length) return 1;
  return Math.max(...activeCategoriesForView.value.map((category) => Number(category.usage_count || 0)), 1);
});
const categoryCloudItems = computed(() =>
  [...filteredCategories.value].map((category, index) => ({
    category,
    usage: Number(category?.usage_count || 0),
    style: categoryCloudItemStyle(category, index)
  }))
);
const categoryCloudStats = computed(() => {
  const source = activeCategoriesForView.value;
  const assigned = source.filter((category) => Number(category?.usage_count || 0) > 0).length;
  return {
    total: source.length,
    assigned,
    unused: Math.max(0, source.length - assigned)
  };
});

const activeTagFilterIds = computed(() => normalizeTagIds(documentListQuery.tagIds));
const activeTagFilterIdsSet = computed(() => new Set(activeTagFilterIds.value));
const activeTagFilterCount = computed(() => activeTagFilterIds.value.length);
const showTagFilterDrawer = computed(() =>
  activeView.value === 'all' &&
  !activeSavedSearchId.value &&
  !isSelectionMode.value &&
  !isTagSelectionMode.value &&
  sortedTagsByName.value.length > 0
);
const tagFilterResultCounts = computed(() => {
  const counts = new Map();
  for (const document of documents.value || []) {
    for (const tag of document?.tags || []) {
      const tagId = String(tag?.id || '').trim();
      if (!tagId) {
        continue;
      }
      counts.set(tagId, (counts.get(tagId) || 0) + 1);
    }
  }
  return counts;
});
const visibleTagFilterOptions = computed(() => {
  if (activeTagFilterCount.value > 0) {
    const resultCounts = tagFilterResultCounts.value;
    return sortedTagsByName.value
      .filter((tag) => activeTagFilterIdsSet.value.has(tag.id) || resultCounts.has(tag.id))
      .slice(0, 48);
  }
  return sortedTagsByName.value
    .filter((tag) => tagUsageCount(tag.id, tag.usage_count ?? 0) > 0)
    .slice(0, 48);
});
const tagFilterDrawerOffsetStyle = computed(() => ({
  '--tag-filter-drawer-height': showTagFilterDrawer.value && isTagFilterDrawerOpen.value
    ? `${tagFilterDrawerHeight.value}px`
    : '0px'
}));
const tagFilterDocumentListSpacerHeight = computed(() => (
  showTagFilterDrawer.value && isTagFilterDrawerOpen.value
    ? 20
    : 0
));
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
      activeTagFilterCount.value > 0 ||
      documentListQuery.untagged ||
      documentListQuery.status ||
      documentListQuery.dateFrom ||
      documentListQuery.dateTo
  );
});
const showDocumentListLoadingState = computed(() =>
  isDocumentListSettling.value || (documents.value.length === 0 && isLoadingDocuments.value)
);
const showDocumentListEmptyState = computed(() =>
  !isDocumentListSettling.value && !isLoadingDocuments.value && documents.value.length === 0
);
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
  if (isNoTextView.value) {
    return {
      icon: 'mdi-text-box-remove-outline',
      title: 'Alle Dokumente sind durchsuchbar',
      subtitle: 'Hier erscheinen Dokumente ohne erkannten Text (keine Texterkennung möglich oder ausstehend).'
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
    tagIds: activeTagFilterIds.value,
    untagged: documentListQuery.untagged,
    documentType: documentListQuery.documentType,
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
    tagIds: activeTagFilterIds.value,
    untagged: documentListQuery.untagged,
    documentType: documentListQuery.documentType,
    status: documentListQuery.status,
    dateFrom: documentListQuery.dateFrom,
    dateTo: documentListQuery.dateTo,
    sort: documentListQuery.sort,
    order: documentListQuery.order,
    limit: documentListQuery.limit,
    offset: documentListQuery.offset,
    recentImports: isImportsView.value,
    favoritesOnly: isFavoritesView.value,
    withoutText: isNoTextView.value,
    inTrash: isTrashView.value
  })
);
const isMetadataDirty = computed(() => {
  if (
    !selectedDocumentDetail.value
    || metadataDraftDocumentId.value !== selectedDocumentDetail.value.id
  ) {
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

  const draftName = normalizeDocumentName(metadataDocName.value);
  if (draftName && draftName !== getDocumentNameDraft(selectedDocumentDetail.value)) {
    return true;
  }

  return (metadataNotes.value || '') !== detailNotes;
});
const isTagSelectionDirty = computed(() => {
  if (
    !selectedDocumentDetail.value
    || metadataDraftDocumentId.value !== selectedDocumentDetail.value.id
  ) {
    return false;
  }
  const detailTagIds = normalizeTagIds((selectedDocumentDetail.value.tags || []).map((tag) => tag.id));
  return !isSameTagSelection(metadataTagIds.value, detailTagIds);
});

// Steuert die Sichtbarkeit des KI-Befüllen-Buttons: nur anzeigen, wenn mindestens
// eines der bearbeitbaren Felder (Name, Datum, Kategorie, Notizen, Tags) leer ist.
const hasEmptyMetadataField = computed(() => {
  if (!selectedDocumentDetail.value) {
    return false;
  }
  const nameEmpty = !normalizeDocumentName(metadataDocName.value);
  const dateEmpty = !String(metadataDocDate.value || '').trim();
  const categoryEmpty = !String(metadataDocCategory.value || '').trim();
  const notesEmpty = !String(metadataNotes.value || '').trim();
  const tagsEmpty = metadataTagNames.value.length === 0;
  return nameEmpty || dateEmpty || categoryEmpty || notesEmpty || tagsEmpty;
});

let mediaQuery = null;
const tagReplaceDebounceTimers = new Map();
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
let isDocumentTagSaveRunning = false;
const queuedDocumentTagSaves = new Map();
const previewRetryAttemptsByDocument = ref({});
const favoriteStateByDocumentId = new Map();

function applyKnownFavoriteState(document) {
  const knownState = document?.id ? favoriteStateByDocumentId.get(document.id) : null;
  if (!knownState) {
    return document;
  }
  const incomingUpdatedAt = Date.parse(String(document.updated_at || '')) || 0;
  if (incomingUpdatedAt > knownState.updatedAt) {
    favoriteStateByDocumentId.delete(document.id);
    return document;
  }
  return {
    ...document,
    is_favorite: knownState.value
  };
}

function applyKnownFavoriteStates(items) {
  return (Array.isArray(items) ? items : []).map(applyKnownFavoriteState);
}

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyColorVariant(variant) {
  applyPaperMindVuetifyColors(theme, variant);
}

function applyThemeFromSettings() {
  theme.global.name.value = resolveThemeName(appSettings.value.ui.theme_mode);
  applyColorVariant(appSettings.value.ui.color_variant || 'teal');
}

watch(
  () => settingsStore.settingsDraft.ui.color_variant,
  (variant) => {
    applyColorVariant(variant || 'teal');
  }
);

// ── Sidebar ein-/ausklappen (Icon-Rail, manuell + responsiv) ────────────────
function loadSidebarRail() {
  try { return localStorage.getItem('pm-sidebar-rail') === 'true'; } catch { return false; }
}
const sidebarManualCollapsed = ref(loadSidebarRail());
const sidebarNarrow = ref(typeof window !== 'undefined' ? window.innerWidth < 700 : false);
const sidebarCollapsed = computed(() => sidebarManualCollapsed.value || sidebarNarrow.value);
const sidebarRailActive = ref(sidebarCollapsed.value);
const sidebarRailTransitioning = ref(false);
let sidebarRailEndTimer = null;
const sidebarContentCollapsed = computed(() => sidebarRailActive.value && !sidebarRailTransitioning.value);

function clearSidebarRailTimers() {
  if (typeof window === 'undefined') return;
  if (sidebarRailEndTimer) {
    window.clearTimeout(sidebarRailEndTimer);
    sidebarRailEndTimer = null;
  }
}

function animateSidebarRail(nextCollapsed) {
  if (typeof window === 'undefined') return;
  clearSidebarRailTimers();
  sidebarRailTransitioning.value = true;
  sidebarRailActive.value = nextCollapsed;

  // Knapp nach Ende der Breiten-Animation (240ms) settled der Inhalt (Labels aus,
  // Icons zentriert), damit es keinen separaten Nach-Sprung gibt.
  sidebarRailEndTimer = window.setTimeout(() => {
    sidebarRailActive.value = nextCollapsed;
    sidebarRailTransitioning.value = false;
    sidebarRailEndTimer = null;
  }, 260);
}

function toggleSidebarRail() {
  const nextCollapsed = !sidebarManualCollapsed.value;
  sidebarManualCollapsed.value = nextCollapsed;
  animateSidebarRail(sidebarCollapsed.value);
  try { localStorage.setItem('pm-sidebar-rail', String(sidebarManualCollapsed.value)); } catch { /* ignore */ }
}

function updateSidebarNarrow() {
  const nextNarrow = window.innerWidth < 700;
  if (sidebarNarrow.value !== nextNarrow) {
    sidebarNarrow.value = nextNarrow;
    animateSidebarRail(sidebarCollapsed.value);
    void nextTick(measureTagFilterDrawerHeight);
    return;
  }
  sidebarNarrow.value = nextNarrow;
  void nextTick(measureTagFilterDrawerHeight);
}

onMounted(() => window.addEventListener('resize', updateSidebarNarrow, { passive: true }));
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateSidebarNarrow);
  clearSidebarRailTimers();
});

// Titel der mittleren Spalte (aktueller View/Filter) für die Kopfzeile.
const panelHeading = computed(() => {
  if (activeSavedSearchId.value) return activeSavedSearchName.value || 'Ordner';
  if (isTagView.value) return 'Tags';
  if (isCategoryView.value) return 'Dokumenttypen';
  if (activeCategoryName.value) return activeCategoryName.value;
  if (activeTagId.value) {
    const tag = tags.value.find((t) => t.id === activeTagId.value);
    return tag ? tag.name : 'Tag';
  }
  const labels = {
    all: 'Alle Dokumente',
    imports: 'Zuletzt hinzugefügt',
    untagged: 'Ohne Tags',
    favorites: 'Favoriten',
    no_text: 'Nicht durchsuchbar',
    trash: 'Papierkorb'
  };
  return labels[activeView.value] || 'Dokumente';
});

// ── Sidebar-Counts ────────────────────────────────────────────────────────

async function fetchSidebarCounts() {
  await sidebarStore.fetchCounts();
}

function scheduleSidebarCountsRefresh() {
  sidebarStore.scheduleCounts();
}

const pendingImportInboxCount = computed(() => {
  const loadedPageCount = importInboxItems.value.reduce(
    (sum, item) => sum + Math.max(0, Number(item?.page_count || 0)),
    0
  );
  return Math.max(loadedPageCount, Number(sidebarCounts.value.pending_import_inbox_count || 0));
});
const pendingImportInboxBadgeLabel = computed(() => {
  const count = pendingImportInboxCount.value;
  return count > 99 ? '99+' : String(count);
});
const pendingImportInboxMenuTitle = computed(() => {
  const count = pendingImportInboxCount.value;
  return count === 1 ? 'Neue Scan-Seite anzeigen' : 'Neue Scans anzeigen';
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
      source_type: String(item?.source_type || 'shortcut').trim() || 'shortcut',
      scanner_device_id: String(item?.scanner_device_id || '').trim(),
      is_assigned_to_me: item?.is_assigned_to_me !== false,
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

function buildImportInboxItemIdSet(items) {
  return new Set(
    (Array.isArray(items) ? items : [])
      .map((item) => String(item?.id || '').trim())
      .filter(Boolean)
  );
}

function shouldAutoOpenImportInbox(nextItems, newItemIds) {
  // nextItems ist serverseitig schon auf "für mich sichtbar" eingeschränkt
  // (eigene Items + Scanner-Items mit registrierter Empfängerschaft) - ein
  // neues Item muss dafür nicht zusätzlich bereits zugewiesen sein.
  // openImportInboxScans() übernimmt unzugewiesene Scanner-Items selbst.
  return Boolean(settingsStore.settings?.documents?.auto_open_import_inbox) &&
    Array.isArray(nextItems) &&
    nextItems.length > 0 &&
    newItemIds.length > 0 &&
    !isUploadDialogOpen.value &&
    !isImportTrayVisible.value &&
    activeImportInboxItemIds.value.size === 0 &&
    !isClaimingImportInbox.value &&
    !isAutoOpeningImportInbox;
}

async function autoOpenImportInboxScans() {
  isAutoOpeningImportInbox = true;
  try {
    await openImportInboxScans({ refresh: false });
  } finally {
    isAutoOpeningImportInbox = false;
  }
}

async function refreshImportInbox({ silent = true, allowAutoOpen = true } = {}) {
  if (isImportInboxLoading.value) {
    return;
  }
  isImportInboxLoading.value = true;
  let shouldAutoOpen = false;
  try {
    const payload = await getImportInbox({ limit: 50 });
    const nextItems = normalizeImportInboxItems(payload);
    const nextItemIds = buildImportInboxItemIdSet(nextItems);
    const newItemIds = [...nextItemIds].filter((itemId) => !knownImportInboxItemIds.has(itemId));
    importInboxItems.value = nextItems;
    knownImportInboxItemIds = nextItemIds;

    if (!hasCompletedInitialImportInboxRefresh) {
      hasCompletedInitialImportInboxRefresh = true;
      return;
    }

    shouldAutoOpen = allowAutoOpen && shouldAutoOpenImportInbox(nextItems, newItemIds);
  } catch (error) {
    if (!silent) {
      notify({ type: 'error', message: mapApiError(error, 'Neue Scans konnten nicht geladen werden.') });
    }
  } finally {
    isImportInboxLoading.value = false;
  }

  if (shouldAutoOpen) {
    await autoOpenImportInboxScans();
  }
}

function startImportInboxPolling() {
  if (importInboxPollTimer) {
    window.clearTimeout(importInboxPollTimer);
  }
  void refreshImportInbox({ silent: true, allowAutoOpen: false });
  scheduleImportInboxPoll();
}

function scheduleImportInboxPoll(delay = null) {
  if (importInboxPollTimer) {
    window.clearTimeout(importInboxPollTimer);
  }
  const nextDelay = delay ?? (document.hidden ? 60000 : 15000);
  importInboxPollTimer = window.setTimeout(async () => {
    await refreshImportInbox({ silent: true });
    scheduleImportInboxPoll();
  }, nextDelay);
}

function handleImportInboxVisibilityChange() {
  scheduleImportInboxPoll(document.hidden ? 60000 : 0);
}

async function openImportInboxScans({ refresh = true } = {}) {
  if (refresh) {
    await refreshImportInbox({ silent: false, allowAutoOpen: false });
  }
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
    const assignableItemIds = items
      .filter((item) => !item.is_assigned_to_me && item.source_type === 'scanner')
      .map((item) => item.id)
      .filter(Boolean);
    if (assignableItemIds.length > 0) {
      const assignResult = await assignImportInboxItems(assignableItemIds);
      if (Number(assignResult?.assigned || 0) !== assignableItemIds.length) {
        notify({ type: 'info', message: 'Einige Scanner-Scans wurden bereits übernommen.' });
        await refreshImportInbox({ silent: true, allowAutoOpen: false });
        return;
      }
      for (const item of items) {
        if (assignableItemIds.includes(item.id)) {
          item.is_assigned_to_me = true;
        }
      }
    }
    await dialogRef.openWithRemoteSources({
      sources: items,
      sessionId: 'import-inbox'
    });
    const itemIds = items.map((item) => item.id).filter(Boolean);
    if (itemIds.length > 0) {
      const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
      const nextActive = new Set(activeImportInboxItemIds.value);
      const nextSourceMap = new Map(activeImportInboxSourceToItemId.value);
      for (const itemId of itemIds) {
        nextSuppressed.add(itemId);
        nextActive.add(itemId);
      }
      for (const item of items) {
        nextSourceMap.set(String(item.source_file_id || '').trim(), String(item.id || '').trim());
      }
      importInboxSuppressedItemIds.value = nextSuppressed;
      activeImportInboxItemIds.value = nextActive;
      activeImportInboxSourceToItemId.value = nextSourceMap;
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
    activeImportInboxSourceToItemId.value = new Map();
    const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
    for (const itemId of itemIds) {
      nextSuppressed.delete(itemId);
    }
    importInboxSuppressedItemIds.value = nextSuppressed;
    await refreshImportInbox({ silent: true, allowAutoOpen: false });
  } catch (error) {
    notify({ type: 'warning', message: mapApiError(error, 'Import-Inbox konnte nicht aktualisiert werden.') });
  } finally {
    isClaimingImportInbox.value = false;
  }
}

async function onImportSourcesDiscarded(payload = {}) {
  const sourceFileIds = Array.isArray(payload?.sourceFileIds) ? payload.sourceFileIds : [];
  const itemIds = [];
  const nextActive = new Set(activeImportInboxItemIds.value);
  const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
  const nextSourceMap = new Map(activeImportInboxSourceToItemId.value);

  for (const rawSourceFileId of sourceFileIds) {
    const sourceFileId = String(rawSourceFileId || '').trim();
    const itemId = nextSourceMap.get(sourceFileId);
    if (!itemId) {
      continue;
    }
    itemIds.push(itemId);
    nextActive.delete(itemId);
    nextSuppressed.delete(itemId);
    nextSourceMap.delete(sourceFileId);
  }

  if (itemIds.length === 0) {
    return;
  }

  activeImportInboxItemIds.value = nextActive;
  importInboxSuppressedItemIds.value = nextSuppressed;
  activeImportInboxSourceToItemId.value = nextSourceMap;

  try {
    await discardImportInboxItems(itemIds);
    await refreshImportInbox({ silent: true, allowAutoOpen: false });
  } catch (error) {
    notify({ type: 'warning', message: mapApiError(error, 'Gelöschte SMB-Scans konnten nicht endgültig gelöscht werden.') });
  }
}

watch(isUploadDialogOpen, async (open) => {
  if (open) {
    isImportTrayVisible.value = false;
    return;
  }
  // Minimieren ist kein echtes Schließen: Items für späteres Wiederherstellen behalten.
  if (isMinimizingImport.value) {
    isMinimizingImport.value = false;
    return;
  }
  // Commit-Pfad setzt isClaimingImportInbox/leert die aktiven Items → hier nichts tun.
  if (isClaimingImportInbox.value || activeImportInboxItemIds.value.size === 0) {
    return;
  }
  // Dialog ohne Commit geschlossen (Abbrechen/Esc/Klick außerhalb): geöffnete
  // Inbox-Scans verwerfen – aber erst nach Sicherheitsabfrage.
  const itemIds = Array.from(activeImportInboxItemIds.value);
  activeImportInboxItemIds.value = new Set();
  activeImportInboxSourceToItemId.value = new Map();
  const nextSuppressed = new Set(importInboxSuppressedItemIds.value);
  for (const itemId of itemIds) {
    nextSuppressed.delete(itemId);
  }
  importInboxSuppressedItemIds.value = nextSuppressed;

  const count = itemIds.length;
  const confirmed = window.confirm(
    `${count} gescannte${count === 1 ? 'n Import' : ' Importe'} verwerfen? `
      + 'Die Dateien werden endgültig gelöscht. Mit „Abbrechen" bleiben sie im Posteingang.'
  );
  if (!confirmed) {
    // Behalten: Scans wandern zurück in den Posteingang.
    await refreshImportInbox({ silent: true, allowAutoOpen: false });
    return;
  }
  try {
    await discardImportInboxItems(itemIds);
  } catch (error) {
    notify({ type: 'warning', message: mapApiError(error, 'Verworfene Scans konnten nicht gelöscht werden.') });
  }
  await refreshImportInbox({ silent: true, allowAutoOpen: false });
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
  try {
    const id = await tagStore.ensureTagIdByName(normalizeTagInput(typedName));
    if (id) scheduleSidebarCountsRefresh();
    return id;
  } catch (error) {
    metadataTagErrorMessage.value = notifyError(error, 'Tag konnte nicht erstellt werden.');
    return '';
  }
}

async function syncMetadataTagsFromNames(nextNames) {
  if (!selectedDocumentDetail.value) return;
  const documentId = selectedDocumentDetail.value.id;
  const revision = ++metadataTagDraftRevision.value;
  const normalizedNames = normalizeTagNames(nextNames);
  metadataTagErrorMessage.value = '';
  isResolvingTagNames.value = true;

  try {
    const resolvedTagIds = [];
    for (const name of normalizedNames) {
      let tagId = findTagByName(name)?.id || '';
      if (!tagId) tagId = await ensureTagIdByName(name);
      if (
        revision !== metadataTagDraftRevision.value
        || selectedDocumentId.value !== documentId
      ) {
        return;
      }
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
  } finally {
    if (revision === metadataTagDraftRevision.value) {
      isResolvingTagNames.value = false;
    }
  }
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

function removeMetadataTag(name) {
  if (isRunningAiAnalysis.value) return;
  metadataTagDraftRevision.value += 1;
  isResolvingTagNames.value = false;
  const normalizedName = normalizeTagInput(name).toLocaleLowerCase('de-DE');
  const tagId = (
    tags.value.find((tag) => normalizeTagInput(tag.name).toLocaleLowerCase('de-DE') === normalizedName)
    || selectedDocumentDetail.value?.tags?.find(
      (tag) => normalizeTagInput(tag.name).toLocaleLowerCase('de-DE') === normalizedName
    )
  )?.id;
  if (!tagId) {
    metadataTagNames.value = metadataTagNames.value.filter(
      (entry) => normalizeTagInput(entry).toLocaleLowerCase('de-DE') !== normalizedName
    );
    return;
  }
  const nextIds = metadataTagIds.value.filter((id) => id !== tagId);
  syncTagSelectionLocal(nextIds);
  scheduleReplaceDocumentTags(
    selectedDocumentDetail.value.id,
    nextIds,
    metadataTagDraftRevision.value
  );
}

// Auswählbare Kategorien (zentral in den Einstellungen gepflegt). Ein bereits am
// Dokument gesetzter Wert, der (noch) nicht in der Liste steht, wird ergänzt,
// damit er im Select sichtbar bleibt.
const categoryDrawerItems = computed(() => {
  const names = [...categoryNames.value];
  const current = String(metadataDocCategory.value || '').trim();
  if (current && !names.some((n) => n.toLocaleLowerCase('de-DE') === current.toLocaleLowerCase('de-DE'))) {
    names.unshift(current);
  }
  return names;
});

async function onMetadataCategoryChange(nextCategory) {
  if (!selectedDocumentDetail.value) return;
  const documentId = selectedDocumentDetail.value.id;
  const value = String(nextCategory || '').trim() || null;
  if (value) {
    const validationMessage = validateVocabName(value, 'Dokumenttyp');
    if (validationMessage) {
      notify({ type: 'warning', message: validationMessage });
      metadataDocCategory.value = selectedDocumentDetail.value?.document_type || selectedDocumentDetail.value?.category || null;
      return;
    }
  }
  metadataDocCategory.value = value;
  isSavingCategory.value = true;
  try {
    await docStore.patchDocument(documentId, { document_type: value });
    // Seitenleiste (Dokumenttyp-Quicklinks + Zähler) hängt an categoryStore.usage_count
    // und wird nur über fetchCategories aktualisiert – sonst bleibt die Zuweisung
    // in der Sidebar unsichtbar.
    await categoryStore.fetchCategories();
    scheduleSidebarCountsRefresh();
  } catch (error) {
    notifyError(error, 'Dokumenttyp konnte nicht gespeichert werden.');
    // Bei Fehler wieder auf den gespeicherten Stand zurücksetzen
    metadataDocCategory.value = selectedDocumentDetail.value?.document_type || selectedDocumentDetail.value?.category || null;
  } finally {
    isSavingCategory.value = false;
  }
}

// Korrespondenten-Optionen für das Detail-Drawer; aktuelle Auswahl bleibt
// sichtbar, falls sie (noch) nicht in der geladenen Liste steht.
const correspondentDrawerItems = computed(() => {
  const items = correspondentStore.correspondentOptions.map((o) => ({ ...o }));
  const currentId = metadataCorrespondentId.value;
  if (currentId && !items.some((o) => o.value === currentId)) {
    const name = selectedDocumentDetail.value?.correspondent_name || 'Korrespondent';
    items.unshift({ title: name, value: currentId });
  }
  return items;
});

function normalizeCorrespondentInput(value) {
  if (value && typeof value === 'object') {
    return String(value.value || value.id || value.title || value.name || '').replace(/\s+/g, ' ').trim();
  }
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function onMetadataCorrespondentInput(nextValue) {
  metadataCorrespondentDraft.value = nextValue;
  const rawValue = normalizeCorrespondentInput(nextValue);
  if (!rawValue || correspondentStore.findById(rawValue)) {
    void commitMetadataCorrespondent();
  }
}

function handleMetadataCorrespondentBlur() {
  window.setTimeout(() => {
    void commitMetadataCorrespondent();
  }, 0);
}

async function commitMetadataCorrespondent() {
  if (isSavingCorrespondent.value) return;
  if (!selectedDocumentDetail.value) return;
  const documentId = selectedDocumentDetail.value.id;
  const previousId = selectedDocumentDetail.value?.correspondent_id || null;
  const rawValue = normalizeCorrespondentInput(metadataCorrespondentDraft.value);
  let phase = 'resolving';
  isSavingCorrespondent.value = true;
  try {
    let correspondentId = null;
    if (rawValue) {
      await correspondentStore.ensureLoaded();
      const existing = correspondentStore.findById(rawValue) || correspondentStore.findByName(rawValue);
      if (existing?.id) {
        correspondentId = existing.id;
      } else {
        phase = 'creating';
        const result = await correspondentStore.createCorrespondentByName(rawValue);
        if (!result?.ok || !result.id) {
          metadataCorrespondentId.value = previousId;
          metadataCorrespondentDraft.value = previousId;
          return;
        }
        correspondentId = result.id;
      }
    }

    metadataCorrespondentId.value = correspondentId;
    metadataCorrespondentDraft.value = correspondentId;
    phase = 'patching';
    await docStore.patchDocument(documentId, { correspondent_id: correspondentId });
  } catch (error) {
    // Das Anlegen meldet API-Fehler bereits zentral über den Korrespondenten-Store.
    if (phase !== 'creating') {
      notifyError(error, 'Korrespondent konnte nicht gespeichert werden.');
    }
    metadataCorrespondentId.value = previousId;
    metadataCorrespondentDraft.value = previousId;
  } finally {
    isSavingCorrespondent.value = false;
  }
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

function resolveDefaultSortQuery(viewKey = activeView.value) {
  const toolbarState = resolveDocumentToolbarState(viewKey);
  return { sort: toolbarState.sort, order: toolbarState.order };
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


async function openShortcutsHelp() {
  await fetchAppSettings();
  uiStore.openSettings('controls');
}

async function openBackupSettings() {
  await fetchAppSettings();
  uiStore.openSettings('backup');
}

function openDocumentTypeSettings() {
  uiStore.openSettings('categories');
}

function openCorrespondentSettings() {
  uiStore.openSettings('correspondents');
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

function normalizeDocumentName(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function getDocumentNameDraft(document) {
  return normalizeDocumentName(stripPdfSuffix(getDocumentTitle(document)));
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
  const toolbarState = resolveDocumentToolbarState('all');
  patchDocumentListQuery({
    q: null,
    tagId: null,
    untagged: null,
    status: toolbarState.status,
    dateFrom: toolbarState.dateFrom,
    dateTo: toolbarState.dateTo,
    sort: toolbarState.sort,
    order: toolbarState.order,
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

function tagCloudItemStyle(tag, index = 0) {
  const usage = Number(tag?.usage_count || 0);
  const ratio = Math.min(1, usage / maxTagUsageCount.value);
  const fontSizeRem = 0.82 + ratio * 0.54;
  const opacity = 0.72 + ratio * 0.28;
  const fontWeight = Math.round(540 + ratio * 140);
  const accent = tagCloudAccentPalette[index % tagCloudAccentPalette.length];
  const floatDirection = index % 2 === 0 ? 1 : -1;
  return {
    '--tag-accent': accent,
    '--tag-float-offset': `${floatDirection * (2 + (index % 3))}px`,
    '--tag-float-duration': `${10 + (index % 5)}s`,
    '--tag-float-delay': `${-(index % 7) * 0.85}s`,
    fontSize: `${fontSizeRem.toFixed(3)}rem`,
    opacity: opacity.toFixed(2),
    fontWeight: String(fontWeight)
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
  return authedUrl(`${apiBaseUrl}/api/documents/${documentId}/file?role=${selectedRole}`);
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
  if (Array.isArray(value)) {
    return [...value];
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
    const currentValue = documentListQuery[key];
    const changed = Array.isArray(currentValue) || Array.isArray(nextValue)
      ? JSON.stringify(currentValue || []) !== JSON.stringify(nextValue || [])
      : currentValue !== nextValue;
    if (changed) {
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
  metadataDraftDocumentId.value = detail?.id || null;
  metadataTagDraftRevision.value += 1;
  isResolvingTagNames.value = false;
  metadataDocName.value = getDocumentNameDraft(detail);
  metadataDocDate.value = formatDocumentDateInputFromIso(detail?.document_date);
  metadataDocDateHasError.value = false;
  metadataDocCategory.value = detail?.document_type || detail?.category || null;
  void categoryStore.ensureLoaded();
  metadataCorrespondentId.value = detail?.correspondent_id || null;
  metadataCorrespondentDraft.value = metadataCorrespondentId.value;
  void correspondentStore.ensureLoaded();
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

function notifyOcrQualityIfNeeded(detail) {
  const status = String(detail?.ocr_quality_status || '').toLowerCase();
  if (!['warning', 'error'].includes(status) || detail?.ocr_status !== 'done') {
    return;
  }
  const confidence = Number(detail?.ocr_confidence_score);
  const confidenceLabel = Number.isFinite(confidence) ? `${Math.round(confidence)}%` : 'unbekannt';
  const key = `${detail.id}:${status}:${confidenceLabel}`;
  if (notifiedOcrQualityKeys.has(key)) {
    return;
  }
  notifiedOcrQualityKeys.add(key);
  notify({
    type: status === 'error' ? 'error' : 'warning',
    title: 'OCR-Qualität',
    message: detail?.ocr_quality_message || `OCR-Konfidenz ${confidenceLabel}. KI-Ergebnisse können unzuverlässig sein.`
  });
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

function applyTagsFromDetail(detail) {
  const nextTagIds = normalizeTagIds((detail?.tags || []).map((tag) => tag.id));
  metadataTagIds.value = nextTagIds;
  metadataTagNames.value = (detail?.tags || []).map((tag) => normalizeTagInput(tag.name)).filter(Boolean);
  metadataTagSearch.value = '';
  metadataTagErrorMessage.value = '';
}

async function persistDocumentTags(documentId, tagIds, draftRevision) {
  const nextTagIds = sanitizeSelectedTagIds(tagIds);
  const sourceDocument = selectedDocumentDetail.value?.id === documentId
    ? selectedDocumentDetail.value
    : documents.value.find((document) => document.id === documentId);
  const previousTagIds = normalizeTagIds((sourceDocument?.tags || []).map((tag) => tag.id));

  if (isSameTagSelection(nextTagIds, previousTagIds)) {
    if (
      selectedDocumentId.value === documentId
      && draftRevision === metadataTagDraftRevision.value
      && isSameTagSelection(metadataTagIds.value, nextTagIds)
    ) {
      syncTagSelectionLocal(nextTagIds);
    }
    return;
  }

  metadataTagErrorMessage.value = '';

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
      detail = applyKnownFavoriteState(detail);
      docStore.patchDocumentInList(detail);
      if (selectedDocumentId.value === documentId) {
        selectedDocumentDetail.value = detail;
        if (
          draftRevision === metadataTagDraftRevision.value
          && isSameTagSelection(metadataTagIds.value, nextTagIds)
        ) {
          shouldSkipTagAutosave = true;
          applyTagsFromDetail(detail);
          window.setTimeout(() => {
            shouldSkipTagAutosave = false;
          }, 0);
        }
      }
    }
    // Zähler laufen debounced im Hintergrund und stören weder die offene
    // Tag-Combobox noch die Liste. Bewusst KEIN fetchTags() hier: neu erstellte
    // Tags sind bereits über createTagByName im Store – ein zweiter Refetch würde
    // nur die Combobox/Liste neu sortieren und rendern (die optische Unruhe).
    scheduleSidebarCountsRefresh();
    // Die Dokumentliste nur dann neu laden, wenn ihre Zusammensetzung tatsächlich
    // von Tags abhängt (aktiver Tag-Filter oder gespeicherte/Smart-Suche). Sonst
    // genügt die bereits in-place aktualisierte Zeile (patchDocumentInList) –
    // kein Komplett-Reload von Liste und Vorschau.
    if (activeTagFilterCount.value > 0 || activeSavedSearchId.value) {
      await fetchDocuments(documentId, { autoSelectFirst: false, allowPreferredOutsideList: true });
    }
  } catch (error) {
    metadataTagErrorMessage.value = notifyError(error, 'Tags konnten nicht gespeichert werden.');
    if (
      selectedDocumentId.value === documentId
      && draftRevision === metadataTagDraftRevision.value
      && isSameTagSelection(metadataTagIds.value, nextTagIds)
    ) {
      syncTagSelectionLocal(previousTagIds);
    }
  }
}

async function replaceDocumentTags(documentId, tagIds, draftRevision) {
  queuedDocumentTagSaves.set(documentId, {
    tagIds: normalizeTagIds(tagIds),
    draftRevision
  });
  if (isDocumentTagSaveRunning) {
    return;
  }

  isDocumentTagSaveRunning = true;
  isSavingTags.value = true;
  try {
    while (queuedDocumentTagSaves.size > 0) {
      const [nextDocumentId, nextSave] = queuedDocumentTagSaves.entries().next().value;
      queuedDocumentTagSaves.delete(nextDocumentId);
      await persistDocumentTags(nextDocumentId, nextSave.tagIds, nextSave.draftRevision);
    }
  } finally {
    isDocumentTagSaveRunning = false;
    isSavingTags.value = false;
  }
}

// Globale KI-Analyse: analysiert das Dokument und befüllt ausschließlich leere
// Felder (Name, Datum, Kategorie, Notizen, Tags). Vorhandene Eingaben bleiben
// unangetastet. Das Speichern läuft über die bestehenden Autosave-Pfade.
async function runAiAnalysis() {
  if (!selectedDocumentDetail.value || isRunningAiAnalysis.value) {
    return;
  }

  const documentId = selectedDocumentDetail.value.id;
  isRunningAiAnalysis.value = true;
  metadataTagErrorMessage.value = '';

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/ai-metadata`, {
      method: 'POST'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    let suggestion = null;
    try {
      suggestion = await response.json();
    } catch (error) {
      logDevError(error, 'json-parse');
      suggestion = null;
    }
    if (!suggestion) {
      notify({ type: 'warning', title: 'KI', message: 'Keine Analyseergebnisse erhalten.' });
      return;
    }

    let filledCount = 0;

    // Schritt 1: Name/Datum/Notizen in die Felder schreiben (nur wenn leer) und
    // gemeinsam persistieren – BEVOR Kategorie/Tags das Detail neu laden, sonst
    // würden die noch ungespeicherten Werte beim Refresh überschrieben.
    const suggestedName = normalizeDocumentName(suggestion.display_name);
    if (suggestedName && !normalizeDocumentName(metadataDocName.value)) {
      metadataDocName.value = suggestedName;
      filledCount += 1;
    }
    if (suggestion.document_date && !String(metadataDocDate.value || '').trim()) {
      metadataDocDate.value = formatDocumentDateInputFromIso(suggestion.document_date);
      filledCount += 1;
    }
    const suggestedNotes = String(suggestion.notes || '').trim();
    if (suggestedNotes && !String(metadataNotes.value || '').trim()) {
      metadataNotes.value = suggestedNotes;
      filledCount += 1;
    }
    if (isMetadataDirty.value) {
      await saveMetadata({ skipDocumentReload: true, silentSuccess: true });
    }

    // Schritt 2: Kategorie nur befüllen, wenn keine gesetzt ist.
    const suggestedCategory = String(suggestion.document_type || suggestion.category || '').trim();
    if (suggestedCategory && !String(metadataDocCategory.value || '').trim()) {
      await onMetadataCategoryChange(suggestedCategory);
      filledCount += 1;
    }

    // Schritt 3: Korrespondent nur befüllen, wenn keiner gesetzt ist.
    const suggestedCorrespondentId = String(suggestion.correspondent_id || '').trim();
    if (suggestedCorrespondentId && !metadataCorrespondentId.value) {
      await correspondentStore.ensureLoaded();
      metadataCorrespondentDraft.value = suggestedCorrespondentId;
      await commitMetadataCorrespondent();
      filledCount += 1;
    }

    // Schritt 4: Tags nur befüllen, wenn noch keine vorhanden sind.
    const suggestedTags = Array.isArray(suggestion.tags) ? suggestion.tags.filter(Boolean) : [];
    if (suggestedTags.length && metadataTagNames.value.length === 0) {
      await syncMetadataTagsFromNames(suggestedTags);
      await fetchTags();
      scheduleSidebarCountsRefresh();
      filledCount += 1;
    }

    if (filledCount > 0) {
      notify({ type: 'success', title: 'KI', message: 'Leere Felder per KI befüllt.' });
    } else {
      notify({ type: 'info', title: 'KI', message: 'Keine neuen Daten für leere Felder gefunden.' });
    }
  } catch (error) {
    metadataTagErrorMessage.value = notifyError(error, 'KI-Analyse konnte nicht ausgeführt werden.');
  } finally {
    isRunningAiAnalysis.value = false;
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
          ocr_quality_status: detail.ocr_quality_status,
          ocr_confidence_score: detail.ocr_confidence_score,
          ocr_quality_message: detail.ocr_quality_message,
          ocr_processing_seconds: detail.ocr_processing_seconds,
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
              ocr_quality_status: detail.ocr_quality_status,
              ocr_confidence_score: detail.ocr_confidence_score,
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

function scheduleReplaceDocumentTags(documentId, tagIds, draftRevision) {
  const existingTimer = tagReplaceDebounceTimers.get(documentId);
  if (existingTimer) {
    window.clearTimeout(existingTimer);
  }
  const timer = window.setTimeout(() => {
    tagReplaceDebounceTimers.delete(documentId);
    void replaceDocumentTags(documentId, tagIds, draftRevision);
  }, TAG_REPLACE_DEBOUNCE_MS);
  tagReplaceDebounceTimers.set(documentId, timer);
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

function commitMetadataTextFields() {
  if (metadataAutosaveDebounceTimer) {
    window.clearTimeout(metadataAutosaveDebounceTimer);
    metadataAutosaveDebounceTimer = null;
  }
  if (!selectedDocumentDetail.value || !isMetadataDirty.value) {
    return;
  }
  if (isSavingMetadata.value) {
    shouldRunMetadataAutosaveAfterSave = true;
    return;
  }
  void saveMetadata({ skipDocumentReload: true, silentSuccess: true });
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

function handleDetailsEditorFocusIn() {
  detailsEditorHasFocus.value = true;
}

function handleDetailsEditorFocusOut(event) {
  if (event.currentTarget?.contains(event.relatedTarget)) {
    return;
  }
  detailsEditorHasFocus.value = false;
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
  if (handleShortcut(event, SHORTCUT_ACTIONS.HELP, openShortcutsHelp)) {
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

function buildDocumentListQuery(options = {}) {
  const limit = options.limit ?? documentListQuery.limit;
  const offset = options.offset ?? documentListQuery.offset;
  const includeTotal = options.includeTotal !== false;
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  if (!includeTotal) {
    params.set('include_total', 'false');
  }
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
  } else if (activeTagFilterIds.value.length > 0) {
    params.set('tag_id', activeTagFilterIds.value[0]);
    for (const tagId of activeTagFilterIds.value) {
      params.append('tag_ids', tagId);
    }
  } else if (documentListQuery.tagId) {
    params.set('tag_id', documentListQuery.tagId);
  }

  if (documentListQuery.documentType) {
    params.set('document_type', documentListQuery.documentType);
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

  if (isNoTextView.value) {
    params.set('without_text', 'true');
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

function buildSmartFolderDocumentsQuery(options = {}) {
  const limit = options.limit ?? documentListQuery.limit;
  const offset = options.offset ?? documentListQuery.offset;
  const includeTotal = options.includeTotal !== false;
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  if (!includeTotal) {
    params.set('include_total', 'false');
  }
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

function filterDocumentsByActiveTagFilters(items) {
  const requiredTagIds = activeTagFilterIds.value;
  if (!requiredTagIds.length) {
    return Array.isArray(items) ? items : [];
  }
  return (Array.isArray(items) ? items : []).filter((document) => {
    const documentTagIds = new Set(
      (document?.tags || [])
        .map((tag) => String(tag?.id || '').trim())
        .filter(Boolean)
    );
    return requiredTagIds.every((tagId) => documentTagIds.has(tagId));
  });
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
  const toolbarState = resolveDocumentToolbarState('all');
  patchDocumentListQuery(
    {
      q: null,
      tagId: null,
      untagged: null,
      status: toolbarState.status,
      dateFrom: null,
      dateTo: null,
      sort: toolbarState.sort,
      order: toolbarState.order,
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

async function fetchDocumentDetail(documentId, options = {}) {
  const forceApplyMetadata = options.forceApplyMetadata === true;
  if (!documentId) {
    selectedDocumentDetail.value = null;
    metadataDraftDocumentId.value = null;
    return;
  }

  const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  const detail = applyKnownFavoriteState(await parseJsonResponse(response));
  if (selectedDocumentId.value !== documentId) {
    return detail;
  }
  const hasLocalDraft =
    !forceApplyMetadata
    &&
    metadataDraftDocumentId.value === documentId
    && (
      detailsEditorHasFocus.value
      || isMetadataDirty.value
      || isTagSelectionDirty.value
      || isSavingMetadata.value
      || isSavingTags.value
    );
  selectedDocumentDetail.value = detail;
  const ocrDone =
    detail?.ocr_status === 'done' ||
    detail?.jobs?.some((job) => job.type === 'OCR' && job.status === 'done');
  if (ocrDone && !hasOcrFile(detail)) {
    console.warn('OCR status indicates completion but ocr file is missing; falling back to original preview.', {
      documentId
    });
  }
  if (!hasLocalDraft) {
    applyMetadataFromDetail(detail);
  }
  notifyOcrQualityIfNeeded(detail);
}

async function refreshDocumentStatuses(documentIds) {
  const uniqueIds = [...new Set(documentIds)].filter(Boolean).slice(0, 100);
  if (uniqueIds.length === 0) {
    return;
  }

  const params = new URLSearchParams();
  for (const documentId of uniqueIds) {
    params.append('document_ids', documentId);
  }
  const response = await fetch(`${apiBaseUrl}/api/documents/statuses?${params}`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  const payload = await parseJsonResponse(response);
  const statusById = new Map(
    (payload.items || []).map((item) => [item.id, item])
  );
  if (statusById.size === 0) {
    return;
  }

  let selectedStatusChanged = false;
  documents.value = documents.value.map((document) => {
    const statusUpdate = statusById.get(document.id);
    if (!statusUpdate) {
      return document;
    }
    if (
      document.id === selectedDocumentId.value
      && (
        document.status !== statusUpdate.status
        || document.ocr_status !== statusUpdate.ocr_status
      )
    ) {
      selectedStatusChanged = true;
    }
    return { ...document, ...statusUpdate };
  });

  if (
    selectedDocumentId.value
    && statusById.has(selectedDocumentId.value)
    && (selectedStatusChanged || hasActiveOcrJob.value)
  ) {
    await fetchDocumentDetail(selectedDocumentId.value);
  }
}

function startDocumentListSettle() {
  if (documentListSettleTimer) {
    window.clearTimeout(documentListSettleTimer);
    documentListSettleTimer = null;
  }
  isDocumentListSettling.value = true;
}

function finishDocumentListSettle() {
  if (documentListSettleTimer) {
    window.clearTimeout(documentListSettleTimer);
    documentListSettleTimer = null;
  }
  isDocumentListSettling.value = false;
}

function documentListEndpoint({ offset = 0, includeTotal = true } = {}) {
  const queryOptions = { limit: documentListQuery.limit, offset, includeTotal };
  const query = activeSavedSearchId.value
    ? buildSmartFolderDocumentsQuery(queryOptions)
    : buildDocumentListQuery(queryOptions);
  return activeSavedSearchId.value
    ? `${apiBaseUrl}/api/smart-folders/${activeSavedSearchId.value}/documents?${query}`
    : `${apiBaseUrl}/api/documents?${query}`;
}

async function loadMoreDocuments() {
  if (isLoadingMoreDocuments.value || !hasMoreDocuments.value) {
    return;
  }

  const generation = documentListRequestGeneration;
  const offset = documentListLoadedCount.value;
  isLoadingMoreDocuments.value = true;
  try {
    const response = await fetch(documentListEndpoint({ offset, includeTotal: false }));
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    const payload = await parseJsonResponse(response);
    if (generation !== documentListRequestGeneration) {
      return;
    }

    const incoming = applyKnownFavoriteStates(payload.items || []);
    const existingIds = new Set(documents.value.map((document) => document.id));
    const appended = incoming.filter((document) => !existingIds.has(document.id));
    documents.value = sortDocumentsForCurrentView(
      filterDocumentsByActiveTagFilters([...documents.value, ...appended])
    );
    documentListLoadedCount.value = Math.max(
      documentListLoadedCount.value,
      Number(payload.offset || offset) + incoming.length
    );
    documentListTotal.value = Number(payload.total ?? documentListTotal.value);
  } catch (error) {
    notifyError(error, 'Weitere Dokumente konnten nicht geladen werden.');
  } finally {
    if (generation === documentListRequestGeneration) {
      isLoadingMoreDocuments.value = false;
    }
  }
}

async function fetchDocuments(preferredDocumentId = null, options = {}) {
  const generation = ++documentListRequestGeneration;
  const autoSelectFirst = options.autoSelectFirst === true;
  const allowPreferredOutsideList = options.allowPreferredOutsideList === true;
  // Stiller Hintergrund-Refresh (z. B. OCR-Status-Polling): kein Settle/Skeleton
  // und kein Lade-Flag, damit die Dokumentenliste während der Analyse nicht flackert.
  const silent = options.silent === true;
  isLoadingMoreDocuments.value = false;

  // Cache-Treffer → zuletzt gesehene Liste sofort zeigen und ohne Skeleton im
  // Hintergrund revalidieren. Cache-Key bildet Ansicht/Filter/Sortierung ab.
  const cacheKey = documentListEndpoint({ offset: 0, includeTotal: false });
  const cached = silent ? null : readDocumentListCache(cacheKey);
  if (cached) {
    documents.value = cached.items;
    documentListTotal.value = cached.total;
    documentListLoadedCount.value = cached.loadedCount;
  }

  // Skeleton nur zeigen, wenn wir nichts Vorbefülltes anzeigen können.
  const showSkeleton = !silent && !cached;
  if (showSkeleton) {
    startDocumentListSettle();
    isLoadingDocuments.value = true;
  }

  try {
    const response = await fetch(documentListEndpoint({ offset: 0 }));
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const payload = await parseJsonResponse(response);
    if (generation !== documentListRequestGeneration) {
      return;
    }
    let pageItems = applyKnownFavoriteStates(payload.items || []);
    const total = Number(payload.total ?? pageItems.length);
    let loadedCount = Number(payload.offset || 0) + pageItems.length;

    // Hintergrundaktualisierungen (z. B. OCR-Polling) dürfen eine bereits
    // weitergeladene Liste nicht wieder auf die ersten 100 Einträge kürzen.
    const refreshTarget = silent
      ? Math.min(total, Math.max(documentListLoadedCount.value, documentListQuery.limit))
      : loadedCount;
    while (loadedCount < refreshTarget) {
      const nextResponse = await fetch(documentListEndpoint({ offset: loadedCount }));
      if (!nextResponse.ok) {
        throw new Error(await parseResponseError(nextResponse));
      }
      const nextPayload = await parseJsonResponse(nextResponse);
      if (generation !== documentListRequestGeneration) {
        return;
      }
      const nextItems = applyKnownFavoriteStates(nextPayload.items || []);
      if (!nextItems.length) {
        break;
      }
      pageItems = [...pageItems, ...nextItems];
      loadedCount = Number(nextPayload.offset || loadedCount) + nextItems.length;
    }

    documentListTotal.value = total;
    documentListLoadedCount.value = loadedCount;
    documents.value = sortDocumentsForCurrentView(
      filterDocumentsByActiveTagFilters(pageItems)
    );

    // Frische erste Seite für diese Ansicht cachen (für sofortiges Zurückwechseln).
    writeDocumentListCache(cacheKey, {
      items: documents.value,
      total: documentListTotal.value,
      loadedCount: documentListLoadedCount.value
    });

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

    const selectionChanged = selectedDocumentId.value !== resolvedSelectionId;
    selectedDocumentId.value = resolvedSelectionId;
    if (!resolvedSelectionId) {
      selectedDocumentDetail.value = null;
      return;
    }

    try {
      await fetchDocumentDetail(resolvedSelectionId, { forceApplyMetadata: selectionChanged });
      void markDocumentViewedOptimistic(resolvedSelectionId);
    } catch (error) {
      if (!allowPreferredOutsideList || resolvedSelectionId !== preferredDocumentId) {
        throw error;
      }
      persistLastSelectedDocId(null);
      selectedDocumentId.value = autoSelectFirst ? documents.value[0]?.id || null : null;
      selectedDocumentDetail.value = null;
      if (selectedDocumentId.value) {
        await fetchDocumentDetail(selectedDocumentId.value, { forceApplyMetadata: true });
        void markDocumentViewedOptimistic(selectedDocumentId.value);
      }
    }
  } catch (error) {
    notifyError(error, 'Dokumente konnten nicht geladen werden.');
  } finally {
    if (!silent) {
      isLoadingDocuments.value = false;
      finishDocumentListSettle();
    }
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
  // Ein expliziter Dokumentwechsel verwirft den Formularbezug zum vorherigen
  // Dokument sofort. Hintergrund-Refreshes desselben Dokuments schützen dagegen
  // weiterhin aktive Eingaben.
  metadataDraftDocumentId.value = null;
  detailsEditorHasFocus.value = false;
  selectedDocumentId.value = documentId;
  metadataSuccessMessage.value = '';
  metadataErrorMessage.value = '';
  metadataTagErrorMessage.value = '';
  try {
    await fetchDocumentDetail(documentId, { forceApplyMetadata: true });
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
  updated = applyKnownFavoriteState(updated);
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
      message: isPermanent ? 'Dokument endgültig gelöscht.' : 'Dokument in den Papierkorb verschoben.',
      critical: isPermanent
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

async function emptyTrash() {
  const count = Number(sidebarCounts.value.trash_count || 0);
  if (count <= 0) {
    notify({ type: 'info', title: 'Papierkorb', message: 'Der Papierkorb ist leer.' });
    return;
  }
  const confirmed = window.confirm(
    `${count} ${count === 1 ? 'Dokument' : 'Dokumente'} endgültig löschen? Diese Aktion kann nicht rückgängig gemacht werden.`
  );
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/trash`, { method: 'DELETE' });
    if (!response.ok) throw new Error(await parseResponseError(response));
    const payload = await response.json().catch(() => ({}));
    const deletedCount = Number(payload?.deleted_count ?? count);
    notify({
      type: 'success',
      title: 'Papierkorb',
      message: `${deletedCount} ${deletedCount === 1 ? 'Dokument endgültig gelöscht' : 'Dokumente endgültig gelöscht'}.`,
      critical: true
    });
    if (isTrashView.value) {
      selectedDocumentId.value = null;
      selectedDocumentDetail.value = null;
      isDetailsDrawerOpen.value = false;
      await fetchDocuments(null, { autoSelectFirst: false });
    }
    scheduleSidebarCountsRefresh();
    await fetchTags();
  } catch (error) {
    notifyError(error, 'Papierkorb konnte nicht geleert werden.');
  }
}

/** Favoriten-Status eines Dokuments umschalten. */
async function toggleDocumentFavorite(document) {
  if (!document?.id) return;
  const documentId = document.id;
  const nextValue = !Boolean(document.is_favorite);

  // Generation festhalten: wechselt der Nutzer während des Requests die Ansicht
  // (fetchDocuments erhöht den Zähler), dürfen wir die Liste nicht mehr anfassen.
  const generation = documentListRequestGeneration;

  // Rollback-Snapshots.
  const previousDocuments = documents.value;
  const previousSelectedId = selectedDocumentId.value;
  const previousDetail = selectedDocumentDetail.value;
  const previousFavoriteState = favoriteStateByDocumentId.get(documentId);

  // Optimistisch: Stern sofort umschalten (Liste + Detail + bekannter Zustand),
  // damit der Klick ohne Roundtrip-Verzögerung reagiert. Das Entfernen aus der
  // Favoriten-Ansicht bleibt bewusst bis zur Server-Bestätigung, um komplexe
  // Selektions-Rollbacks zu vermeiden.
  favoriteStateByDocumentId.set(documentId, { value: nextValue, updatedAt: Date.now() });
  documents.value = documents.value.map((doc) =>
    doc.id === documentId ? { ...doc, is_favorite: nextValue } : doc
  );
  if (selectedDocumentDetail.value?.id === documentId) {
    selectedDocumentDetail.value = { ...selectedDocumentDetail.value, is_favorite: nextValue };
  }

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/favorite`, { method: 'POST' });
    if (!response.ok) throw new Error(await parseResponseError(response));
    const updated = await response.json();
    const serverValue = Boolean(updated.is_favorite);

    // Server ist autoritativ.
    favoriteStateByDocumentId.set(updated.id, {
      value: serverValue,
      updatedAt: Date.parse(String(updated.updated_at || '')) || Date.now()
    });

    // Ansicht inzwischen gewechselt → Listenmutationen überspringen; der bekannte
    // Favoritenzustand oben wird beim nächsten Laden ohnehin angewandt.
    if (generation !== documentListRequestGeneration) {
      scheduleSidebarCountsRefresh();
      return;
    }

    // Widerspricht der Server der Annahme, korrigieren.
    if (serverValue !== nextValue) {
      documents.value = documents.value.map((doc) =>
        doc.id === updated.id ? { ...doc, is_favorite: serverValue } : doc
      );
      if (selectedDocumentDetail.value?.id === updated.id) {
        selectedDocumentDetail.value = { ...selectedDocumentDetail.value, is_favorite: serverValue };
      }
    }

    if (isFavoritesView.value && serverValue === false) {
      documents.value = documents.value.filter((doc) => doc.id !== updated.id);
      if (selectedDocumentId.value === updated.id) {
        const nextDocument = documents.value[0] || null;
        selectedDocumentId.value = nextDocument?.id || null;
        selectedDocumentDetail.value = null;
        if (nextDocument?.id) {
          await fetchDocumentDetail(nextDocument.id, { forceApplyMetadata: true });
          void markDocumentViewedOptimistic(nextDocument.id);
        } else {
          isDetailsDrawerOpen.value = false;
        }
      }
    } else if (isFavoriteSortQuery() && !isFavoritesView.value) {
      await fetchDocuments(selectedDocumentId.value);
    }
    scheduleSidebarCountsRefresh();
  } catch (error) {
    // Optimistische Änderung zurücknehmen (nur wenn die Ansicht unverändert ist).
    if (generation === documentListRequestGeneration) {
      documents.value = previousDocuments;
      selectedDocumentId.value = previousSelectedId;
      selectedDocumentDetail.value = previousDetail;
    }
    if (previousFavoriteState) {
      favoriteStateByDocumentId.set(documentId, previousFavoriteState);
    } else {
      favoriteStateByDocumentId.delete(documentId);
    }
    notifyError(error, 'Favoriten-Status konnte nicht geändert werden.');
  }
}

function selectView(viewKey) {
  if ((viewKey === 'tags' || viewKey === 'categories') && !closeDetailsDrawerWithGuard()) {
    return;
  }
  if (viewKey !== 'tags') {
    clearTagFeedbackMessages();
  }

  if (viewKey === 'all') {
    const toolbarState = resolveDocumentToolbarState('all');
    const hadActiveSavedSearch = Boolean(activeSavedSearchId.value);
    activeView.value = 'all';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      tagIds: [],
      untagged: null,
      documentType: null,
      status: toolbarState.status,
      dateFrom: toolbarState.dateFrom,
      dateTo: toolbarState.dateTo,
      sort: toolbarState.sort,
      order: toolbarState.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    if (hadActiveSavedSearch) {
      void fetchDocuments(selectedDocumentId.value);
    }
    return;
  }

  if (viewKey === 'imports') {
    const toolbarState = resolveDocumentToolbarState('imports');
    activeView.value = 'imports';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      untagged: null,
      tagIds: [],
      documentType: null,
      status: toolbarState.status,
      dateFrom: toolbarState.dateFrom,
      dateTo: toolbarState.dateTo,
      sort: toolbarState.sort,
      order: toolbarState.order,
      limit: IMPORTS_RECENT_LIMIT
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'untagged') {
    const toolbarState = resolveDocumentToolbarState('untagged');
    activeView.value = 'untagged';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      tagIds: [],
      untagged: true,
      documentType: null,
      status: toolbarState.status,
      dateFrom: toolbarState.dateFrom,
      dateTo: toolbarState.dateTo,
      sort: toolbarState.sort,
      order: toolbarState.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'favorites') {
    const toolbarState = resolveDocumentToolbarState('favorites');
    activeView.value = 'favorites';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      tagIds: [],
      untagged: null,
      documentType: null,
      status: toolbarState.status,
      dateFrom: toolbarState.dateFrom,
      dateTo: toolbarState.dateTo,
      sort: toolbarState.sort,
      order: toolbarState.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'no_text') {
    const toolbarState = resolveDocumentToolbarState('no_text');
    activeView.value = 'no_text';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      tagIds: [],
      untagged: null,
      documentType: null,
      status: toolbarState.status,
      dateFrom: toolbarState.dateFrom,
      dateTo: toolbarState.dateTo,
      sort: toolbarState.sort,
      order: toolbarState.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'trash') {
    const toolbarState = resolveDocumentToolbarState('trash');
    activeView.value = 'trash';
    leaveActiveSavedSearch();
    patchDocumentListQuery({
      tagId: null,
      tagIds: [],
      untagged: null,
      documentType: null,
      status: toolbarState.status,
      dateFrom: toolbarState.dateFrom,
      dateTo: toolbarState.dateTo,
      sort: toolbarState.sort,
      order: toolbarState.order
    });
    syncSearchStateToQuery({ resetOffset: false });
    return;
  }

  if (viewKey === 'tags' || viewKey === 'categories') {
    leaveActiveSavedSearch();
  }
  activeView.value = viewKey;
}

function clearTagFeedbackMessages() {
  // no-op: legacy local tag error banner removed in favor of global notifications
}

function setTagUsageFilter(value) {
  tagUsageFilter.value = TAG_USAGE_FILTER_OPTIONS.some((option) => option.value === value) ? value : 'all';
  persistTagToolbarState();
  selectedTagIds.value = new Set();
}

function setTagSortMode(value) {
  tagSortMode.value = TAG_SORT_OPTIONS.some((option) => option.value === value) ? value : 'usage_desc';
  persistTagToolbarState();
}

function handleTagToolbarAction({ action, value }) {
  if (action === 'sort') {
    setTagSortMode(value);
    return;
  }
  if (action === 'usage') {
    setTagUsageFilter(value);
  }
}

function handleTagToolbarRightAction(action) {
  if (action === 'create') {
    tagDialogsRef.value?.openCreate();
  }
}

function toggleTagSelectionMode() {
  if (!isTagSelectionMode.value && filteredTags.value.length === 0) {
    return;
  }
  isTagSelectionMode.value = !isTagSelectionMode.value;
  if (!isTagSelectionMode.value) {
    selectedTagIds.value = new Set();
  }
}

function selectAllVisibleTags() {
  selectedTagIds.value = new Set(visibleTagIds.value);
}

function toggleTagSelection(tagId) {
  const next = new Set(selectedTagIds.value);
  if (next.has(tagId)) {
    next.delete(tagId);
  } else {
    next.add(tagId);
  }
  selectedTagIds.value = next;
}

function onTagRowClick(tagId) {
  if (isTagSelectionMode.value) {
    toggleTagSelection(tagId);
    return;
  }
  openTagDocuments(tagId);
}

function compareTagsForCurrentSort(left, right) {
  const leftUsage = Number(left?.usage_count || 0);
  const rightUsage = Number(right?.usage_count || 0);
  const nameOrder = tagNameCollator.compare(
    normalizeTagInput(left?.name || ''),
    normalizeTagInput(right?.name || '')
  );

  switch (tagSortMode.value) {
    case 'usage_asc': {
      const usageDelta = leftUsage - rightUsage;
      return usageDelta || nameOrder;
    }
    case 'used_first': {
      const usedDelta = Number(rightUsage > 0) - Number(leftUsage > 0);
      if (usedDelta !== 0) return usedDelta;
      return rightUsage - leftUsage || nameOrder;
    }
    case 'unused_first': {
      const unusedDelta = Number(rightUsage === 0) - Number(leftUsage === 0);
      if (unusedDelta !== 0) return unusedDelta;
      return leftUsage - rightUsage || nameOrder;
    }
    case 'usage_desc':
    default: {
      const usageDelta = rightUsage - leftUsage;
      return usageDelta || nameOrder;
    }
  }
}

function exitTagSelectionMode() {
  isTagSelectionMode.value = false;
  selectedTagIds.value = new Set();
}

function openBatchTagMergeDialog() {
  if (selectedTagIds.value.size === 0 || batchTagMergeCandidates.value.length === 0) {
    return;
  }
  batchTagMergeTargetId.value = null;
  isBatchTagMergeDialogOpen.value = true;
}

function closeBatchTagMergeDialog() {
  isBatchTagMergeDialogOpen.value = false;
  batchTagMergeTargetId.value = null;
}

async function submitBatchTagMerge() {
  const targetId = batchTagMergeTargetId.value;
  if (!targetId || selectedTagIds.value.size === 0) {
    return;
  }
  const sourceIds = Array.from(selectedTagIds.value).filter((tagId) => tagId !== targetId);
  if (sourceIds.length === 0) {
    return;
  }
  isBatchTagMerging.value = true;
  try {
    for (const sourceId of sourceIds) {
      await tagStore.mergeTag(sourceId, targetId);
    }
    notify({
      type: 'success',
      title: 'Tags',
      message: `${sourceIds.length} ${sourceIds.length === 1 ? 'Tag' : 'Tags'} zusammengeführt.`,
      critical: true
    });
    closeBatchTagMergeDialog();
    exitTagSelectionMode();
    await fetchTags();
    scheduleSidebarCountsRefresh();
    await fetchDocuments(selectedDocumentId.value, { allowPreferredOutsideList: true });
  } catch (error) {
    notifyError(error, 'Tags konnten nicht zusammengeführt werden.');
  } finally {
    isBatchTagMerging.value = false;
  }
}

async function confirmBatchTagDelete() {
  if (selectedTagIds.value.size === 0 || isBatchTagDeleting.value) {
    return;
  }
  const selected = selectedTags.value;
  const count = selected.length;
  const previewNames = selected.slice(0, 6).map((tag) => tag.name).join(', ');
  const suffix = selected.length > 6 ? ` und ${selected.length - 6} weitere` : '';
  const confirmed = window.confirm(
    `${count} ${count === 1 ? 'Tag' : 'Tags'} löschen?\n\n${previewNames}${suffix}`
  );
  if (!confirmed) {
    return;
  }
  isBatchTagDeleting.value = true;
  try {
    for (const tag of selected) {
      await tagStore.deleteTag(tag.id);
    }
    notify({
      type: 'success',
      title: 'Tags',
      message: `${count} ${count === 1 ? 'Tag gelöscht' : 'Tags gelöscht'}.`,
      critical: true
    });
    exitTagSelectionMode();
    await fetchTags();
    scheduleSidebarCountsRefresh();
    await fetchDocuments(selectedDocumentId.value, { allowPreferredOutsideList: true });
  } catch (error) {
    notifyError(error, 'Tags konnten nicht gelöscht werden.');
  } finally {
    isBatchTagDeleting.value = false;
  }
}

function openTagsView() {
  selectView('tags');
}

function selectTagFilter(tagId) {
  patchDocumentListQuery({
    tagId,
    tagIds: tagId ? [tagId] : [],
    untagged: null,
    status: resolveToolbarStatus('all')
  });
}

function clearTagFilter() {
  leaveActiveSavedSearch();
  patchDocumentListQuery({
    tagId: null,
    tagIds: []
  });
  syncSearchStateToQuery({ resetOffset: false });
}

function tagUsageCount(tagId, fallback = 0) {
  return sidebarStore.tagCount(tagId, fallback);
}

function tagFilterOptionCount(tag) {
  if (!tag?.id) {
    return 0;
  }
  if (activeTagFilterCount.value > 0) {
    return tagFilterResultCounts.value.get(tag.id) || 0;
  }
  return tagUsageCount(tag.id, tag.usage_count ?? 0);
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
    tagIds: tagId ? [tagId] : [],
    untagged: null,
    documentType: null,
    status: resolveToolbarStatus('all'),
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
    tagIds: tagId ? [tagId] : [],
    untagged: null,
    documentType: null,
    status: resolveToolbarStatus('all'),
    dateFrom: null,
    dateTo: null
  });
  syncSearchStateToQuery({ resetOffset: false });
}

// ── Kategorien (Dokumenttypen): Verwaltungsansicht & Filter ─────────────────
function openCategoriesView() {
  selectView('categories');
}

function openCategoryDocuments(categoryName) {
  const name = String(categoryName || '').trim();
  if (!name) return;
  activeView.value = 'all';
  leaveActiveSavedSearch();
  searchText.value = '';
  patchDocumentListQuery({
    q: null,
    tagId: null,
    tagIds: [],
    untagged: null,
    documentType: name,
    status: resolveToolbarStatus('all'),
    dateFrom: null,
    dateTo: null
  });
  syncSearchStateToQuery({ resetOffset: false });
}

function applyCategoryFilterFromSidebar(categoryName) {
  openCategoryDocuments(categoryName);
}

function setCategoryUsageFilter(value) {
  categoryUsageFilter.value = CATEGORY_USAGE_FILTER_OPTIONS.some((option) => option.value === value) ? value : 'all';
  selectedCategoryIds.value = new Set();
}

function setCategorySortMode(value) {
  categorySortMode.value = CATEGORY_SORT_OPTIONS.some((option) => option.value === value) ? value : 'usage_desc';
}

function handleCategoryToolbarAction({ action, value }) {
  if (action === 'sort') {
    setCategorySortMode(value);
    return;
  }
  if (action === 'usage') {
    setCategoryUsageFilter(value);
  }
}

function handleCategoryToolbarRightAction(action) {
  if (action === 'create') {
    categoryDialogsRef.value?.openCreate();
  }
}

function toggleCategorySelectionMode() {
  if (!isCategorySelectionMode.value && filteredCategories.value.length === 0) {
    return;
  }
  isCategorySelectionMode.value = !isCategorySelectionMode.value;
  if (!isCategorySelectionMode.value) {
    selectedCategoryIds.value = new Set();
  }
}

function selectAllVisibleCategories() {
  selectedCategoryIds.value = new Set(visibleCategoryIds.value);
}

function toggleCategorySelection(categoryId) {
  const next = new Set(selectedCategoryIds.value);
  if (next.has(categoryId)) {
    next.delete(categoryId);
  } else {
    next.add(categoryId);
  }
  selectedCategoryIds.value = next;
}

function onCategoryRowClick(categoryId) {
  if (isCategorySelectionMode.value) {
    toggleCategorySelection(categoryId);
    return;
  }
  const category = categories.value.find((item) => item.id === categoryId);
  if (category?.name) {
    openCategoryDocuments(category.name);
  }
}

function compareCategoriesForCurrentSort(left, right) {
  const leftUsage = Number(left?.usage_count || 0);
  const rightUsage = Number(right?.usage_count || 0);
  const nameOrder = tagNameCollator.compare(
    normalizeTagInput(left?.name || ''),
    normalizeTagInput(right?.name || '')
  );
  switch (categorySortMode.value) {
    case 'usage_asc':
      return (leftUsage - rightUsage) || nameOrder;
    case 'name_asc':
      return nameOrder;
    case 'name_desc':
      return -nameOrder;
    case 'usage_desc':
    default:
      return (rightUsage - leftUsage) || nameOrder;
  }
}

function categoryCloudItemStyle(category, index = 0) {
  const usage = Number(category?.usage_count || 0);
  const ratio = Math.min(1, usage / maxCategoryUsageCount.value);
  const fontSizeRem = 0.82 + ratio * 0.54;
  const opacity = 0.72 + ratio * 0.28;
  const fontWeight = Math.round(540 + ratio * 140);
  const accent = tagCloudAccentPalette[index % tagCloudAccentPalette.length];
  const floatDirection = index % 2 === 0 ? 1 : -1;
  return {
    '--tag-accent': accent,
    '--tag-float-offset': `${floatDirection * (2 + (index % 3))}px`,
    '--tag-float-duration': `${10 + (index % 5)}s`,
    '--tag-float-delay': `${-(index % 7) * 0.85}s`,
    fontSize: `${fontSizeRem.toFixed(3)}rem`,
    opacity: opacity.toFixed(2),
    fontWeight: String(fontWeight)
  };
}

async function confirmBatchCategoryDelete() {
  if (isBatchCategoryDeleting.value || selectedCategoryIds.value.size === 0) {
    return;
  }
  isBatchCategoryDeleting.value = true;
  try {
    for (const id of [...selectedCategoryIds.value]) {
      await categoryStore.deleteCategory(id);
    }
    selectedCategoryIds.value = new Set();
    isCategorySelectionMode.value = false;
    await categoryStore.fetchCategories();
    sidebarStore.scheduleCounts();
  } catch (error) {
    logDevError(error, 'store-notified');
  } finally {
    isBatchCategoryDeleting.value = false;
  }
}

function onCategoryMutated() {
  void categoryStore.fetchCategories();
  sidebarStore.scheduleCounts();
}

function toggleTagFilterDrawer() {
  isTagFilterDrawerOpen.value = !isTagFilterDrawerOpen.value;
  if (settingsStore.settings.ui.tagDrawerRememberState) {
    settingsStore.persistTagDrawerExpanded(isTagFilterDrawerOpen.value);
  }
  void nextTick(measureTagFilterDrawerHeight);
}

function measureTagFilterDrawerHeight() {
  if (!showTagFilterDrawer.value || !isTagFilterDrawerOpen.value) {
    tagFilterDrawerHeight.value = 0;
    return;
  }
  const drawer = tagFilterDrawerRef.value;
  if (!drawer) {
    tagFilterDrawerHeight.value = 0;
    return;
  }
  const viewportCap = Math.round(Math.min(window.innerHeight * 0.40, 320));
  tagFilterDrawerHeight.value = Math.min(Math.ceil(drawer.scrollHeight), viewportCap);
}

function applyTagFilters(tagIds) {
  const normalized = normalizeTagIds(tagIds);
  activeView.value = 'all';
  leaveActiveSavedSearch();
  patchDocumentListQuery({
    tagId: normalized.length === 1 ? normalized[0] : null,
    tagIds: normalized,
    untagged: null,
    status: resolveToolbarStatus('all'),
    dateFrom: null,
    dateTo: null
  });
  syncSearchStateToQuery({ resetOffset: false });
}

function toggleTagFilter(tagId) {
  const normalizedTagId = String(tagId || '').trim();
  if (!normalizedTagId) {
    return;
  }
  const next = new Set(activeTagFilterIds.value);
  if (next.has(normalizedTagId)) {
    next.delete(normalizedTagId);
  } else {
    next.add(normalizedTagId);
  }
  applyTagFilters([...next]);
}

function removeTagFilter(tagId) {
  const next = activeTagFilterIds.value.filter((id) => id !== tagId);
  applyTagFilters(next);
}

function resetTagFilters() {
  applyTagFilters([]);
}

function showAllTagFilters() {
  applyTagFilters([]);
  openTagsView();
}

function normalizeTagInput(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function validateVocabName(value, label = 'Name') {
  const normalized = normalizeTagInput(value);
  if (normalized.length < VOCAB_NAME_MIN_LENGTH) {
    return `${label} muss mindestens ${VOCAB_NAME_MIN_LENGTH} Zeichen enthalten.`;
  }
  if (normalized.length > VOCAB_NAME_MAX_LENGTH) {
    return `${label} darf maximal ${VOCAB_NAME_MAX_LENGTH} Zeichen enthalten.`;
  }
  return '';
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

// Der SettingsDialog ist global gemountet (AppLayout); reload-imports kommt
// als Signal über den ui-Store herein.
watch(() => uiStore.importsReloadSignal, () => onSettingsReloadImports());

function onImportMinimized() {
  // Markieren, damit der Close-Watcher die Inbox-Scans NICHT verwirft (nur Tray).
  isMinimizingImport.value = true;
  isImportTrayVisible.value = importTrayPageCount.value > 0 || importTrayDocumentCount.value > 0;
}

function restoreMinimizedImport() {
  if (importTrayPageCount.value <= 0 && importTrayDocumentCount.value <= 0) {
    isImportTrayVisible.value = false;
    return;
  }
  isUploadDialogOpen.value = true;
  isImportTrayVisible.value = false;
}

async function discardMinimizedImport() {
  const sourceFileIds = Array.from(importStagingStore.stagingFiles?.keys?.() || []);
  importStagingStore.reset();
  isImportTrayVisible.value = false;
  if (sourceFileIds.length > 0) {
    await onImportSourcesDiscarded({ sourceFileIds });
  }
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

// Importieren-Button: bei vorhandenen Posteingang-Scans direkt die Miniaturen,
// sonst das Import-Fenster mit Drag&Drop-Zone öffnen (kein FileChooser mehr).
async function openImport() {
  if (pendingImportInboxCount.value > 0) {
    await openImportInboxScans();
  } else {
    isUploadDialogOpen.value = true;
  }
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
  isImportTrayVisible.value = false;
  if (!Array.isArray(payload?.created) || payload.created.length === 0) {
    return;
  }
  // Aktivitätsindikator sofort aufwecken: nach dem Import sind OCR/INDEX/TAG-Jobs
  // frisch eingereiht und oft sehr kurz – ein sofortiger Poll-Schub stellt sicher,
  // dass das Icon/Menü dafür erscheint.
  activityIndicatorRef.value?.refresh();
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

function openSelectedDocumentInNewTab() {
  const documentId = selectedDocumentId.value;
  if (!documentId) {
    return;
  }
  // URL beim Klick frisch bauen, damit der aktuelle file-scoped Token (Query-Param)
  // anhängt – ein neuer Tab kann keinen Authorization-Header senden.
  const role = resolvePreviewRole(documentId);
  const url = authedUrl(`${apiBaseUrl}/api/documents/${documentId}/file?role=${role}`);
  window.open(url, '_blank', 'noopener');
}

function downloadSelectedDocument() {
  if (!selectedDocumentDetail.value) {
    return;
  }

  const role = resolvePreviewRole(selectedDocumentDetail.value.id);
  const url = authedUrl(`${apiBaseUrl}/api/documents/${selectedDocumentDetail.value.id}/file?role=${role}&download=true`);
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
  const url = authedUrl(`${apiBaseUrl}/api/documents/${documentId}/file?role=original&download=true`);
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
  const documentId = selectedDocumentDetail.value.id;
  const saveRevision = metadataDraftRevision.value;
  const draftDocumentName = metadataDocName.value;
  const draftDocumentDate = metadataDocDate.value;
  const draftNotes = metadataNotes.value;

  try {
    const parsedDocumentDate = parseDocumentDateInput(draftDocumentDate);
    if (!parsedDocumentDate.ok) {
      metadataDocDateHasError.value = true;
      return;
    }

    metadataDocDateHasError.value = false;
    if (metadataDraftRevision.value === saveRevision) {
      metadataDocDate.value = parsedDocumentDate.display;
    }
    const normalizedDocDate = parsedDocumentDate.iso;
    const normalizedNotes = draftNotes || null;

    const patchBody = {
      document_date: normalizedDocDate,
      notes: normalizedNotes
    };

    const normalizedDocName = normalizeDocumentName(draftDocumentName);
    if (normalizedDocName && normalizedDocName !== getDocumentNameDraft(selectedDocumentDetail.value)) {
      patchBody.display_name = normalizedDocName;
    }

    const patchResponse = await fetch(`${apiBaseUrl}/api/documents/${documentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchBody)
    });

    if (!patchResponse.ok) {
      throw new Error(await parseResponseError(patchResponse));
    }

    let updatedDetail = null;
    try {
      updatedDetail = applyKnownFavoriteState(await patchResponse.json());
    } catch (error) {
      logDevError(error, 'json-parse');
      updatedDetail = null;
    }

    if (updatedDetail?.id) {
      const listIndex = documents.value.findIndex((document) => document.id === updatedDetail.id);
      if (listIndex >= 0) {
        const existing = documents.value[listIndex];
        documents.value.splice(listIndex, 1, {
          ...existing,
          ...updatedDetail
        });
      }
      if (selectedDocumentId.value === documentId) {
        selectedDocumentDetail.value = updatedDetail;
      }
      if (selectedDocumentId.value === documentId && metadataDraftRevision.value === saveRevision) {
        applyMetadataFromDetail(updatedDetail);
      }
    } else {
      const localPatch = {
        document_date: normalizedDocDate,
        document_date_source: 'manual',
        document_date_confidence: null,
        document_date_candidates: null,
        notes: normalizedNotes
      };
      if (patchBody.display_name) {
        localPatch.display_name = patchBody.display_name;
      }
      if (selectedDocumentDetail.value?.id === documentId) {
        selectedDocumentDetail.value = {
          ...selectedDocumentDetail.value,
          ...localPatch
        };
      }
      const listIndex = documents.value.findIndex((document) => document.id === documentId);
      if (listIndex >= 0) {
        const existing = documents.value[listIndex];
        documents.value.splice(listIndex, 1, {
          ...existing,
          ...localPatch
        });
      }
      if (selectedDocumentDetail.value?.id === documentId) {
        if (metadataDraftRevision.value === saveRevision) {
          applyMetadataFromDetail(selectedDocumentDetail.value);
        }
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
    if (
      selectedDocumentId.value === documentId
      && (shouldRunMetadataAutosaveAfterSave || isMetadataDirty.value)
    ) {
      shouldRunMetadataAutosaveAfterSave = false;
      scheduleMetadataAutosave();
    } else {
      shouldRunMetadataAutosaveAfterSave = false;
      if (selectedDocumentId.value !== documentId && isMetadataDirty.value) {
        scheduleMetadataAutosave();
      }
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
    metadataDraftDocumentId.value = null;
    metadataTagDraftRevision.value += 1;
    isResolvingTagNames.value = false;
    detailsEditorHasFocus.value = false;
    metadataDraftRevision.value += 1;
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
  scheduleReplaceDocumentTags(
    selectedDocumentDetail.value.id,
    sanitizedTagIds,
    metadataTagDraftRevision.value
  );
});

watch([metadataDocName, metadataDocDate, metadataNotes], () => {
  if (shouldSkipMetadataAutosave || !selectedDocumentDetail.value) {
    return;
  }
  metadataDraftRevision.value += 1;
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
  fetchDocuments,
  resolveToolbarStatus
});

watch(
  () => parsedSearch.value.q,
  (query) => {
    previewTargetPage.value = null;
    previewHighlightText.value = query || '';
  }
);

watch(documentListQueryReloadKey, () => {
  if (isTagView.value || isCategoryView.value) {
    return;
  }
  startDocumentListSettle();
});

// Beim Wechsel des Bereichs/Filters automatisch das erste Dokument der neuen Liste
// selektieren und in der Vorschau anzeigen.
const documentViewContextKey = computed(() =>
  [
    activeView.value,
    activeSavedSearchId.value || '',
    activeTagId.value || '',
    activeCategoryName.value || ''
  ].join('|')
);

let pendingSelectFirstDocument = false;

watch(documentViewContextKey, () => {
  if (isTagView.value || isCategoryView.value) return;
  pendingSelectFirstDocument = true;
});

watch(documents, (list) => {
  if (!pendingSelectFirstDocument) return;
  pendingSelectFirstDocument = false;
  const first = Array.isArray(list) ? list[0] : null;
  if (first?.id) {
    void selectDocument(first.id);
  }
});

useOcrPolling({
  documents,
  hasActiveOcrJob,
  isLoadingDocuments,
  selectedDocumentId,
  refreshDocumentStatuses
});

useGlobalKeyboard(handleGlobalKeydown);

onMounted(async () => {
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', handleSystemThemeChange);
  await fetchAppSettings();
  isTagFilterDrawerOpen.value = settingsStore.settings.ui.tagDrawerRememberState
    ? settingsStore.readStoredTagDrawerExpanded()
    : false;

  await Promise.all([fetchTags(), fetchSavedSearches(), fetchSidebarCounts(), categoryStore.ensureLoaded()]);
  await nextTick();
  isTagFilterDrawerAnimationReady.value = true;
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
  document.addEventListener('visibilitychange', handleImportInboxVisibilityChange);
  startImportInboxPolling();
});

watch(
  () => settingsStore.settings.ui.tagDrawerRememberState,
  (rememberEnabled) => {
    if (!rememberEnabled) {
      isTagFilterDrawerOpen.value = false;
      return;
    }
    settingsStore.persistTagDrawerExpanded(isTagFilterDrawerOpen.value);
  }
);

watch(
  [showTagFilterDrawer, isTagFilterDrawerOpen, visibleTagFilterOptions],
  () => {
    void nextTick(measureTagFilterDrawerHeight);
  },
  { flush: 'post' }
);

onBeforeUnmount(() => {
  for (const timer of tagReplaceDebounceTimers.values()) {
    window.clearTimeout(timer);
  }
  tagReplaceDebounceTimers.clear();
  if (metadataAutosaveDebounceTimer) {
    window.clearTimeout(metadataAutosaveDebounceTimer);
  }
  clearPreviewRetryTimer();
  if (listDropNoticeTimer) {
    window.clearTimeout(listDropNoticeTimer);
  }
  if (importInboxPollTimer) {
    window.clearTimeout(importInboxPollTimer);
  }
  document.removeEventListener('visibilitychange', handleImportInboxVisibilityChange);
  if (documentListSettleTimer) {
    window.clearTimeout(documentListSettleTimer);
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

.app-topbar .v-toolbar__content {
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

.appbar-search__field .v-field {
  border-radius: 10px;
  background-color: rgba(255, 255, 255, 0.16) !important;
  box-shadow: none !important;
  color: rgba(248, 250, 255, 0.96);
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.appbar-search__field .v-field:hover {
  background-color: rgba(255, 255, 255, 0.22) !important;
}

.appbar-search__field .v-field--focused {
  background-color: rgba(255, 255, 255, 0.28) !important;
}

.appbar-search__field .v-field__input,
.appbar-search__field .v-field__prepend-inner .v-icon,
.appbar-search__field .v-field__clearable .v-icon {
  color: rgba(248, 250, 255, 0.85) !important;
}

.appbar-search__field input::placeholder {
  color: rgba(248, 250, 255, 0.5);
}

.appbar-search__field .v-field__outline {
  color: rgba(255, 255, 255, 0.62);
  --v-field-border-opacity: 1;
}

.appbar-search__field .v-field:hover .v-field__outline {
  color: rgba(255, 255, 255, 0.76);
}

/* ── Sidebar-Kopf (Marke + Suche) ──────────────────────────────────────────── */
.sidebar-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 12px 10px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  background: transparent;
  border: 0;
  padding: 2px;
  cursor: pointer;
  color: var(--pm-text);
  font-size: 1.05rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.sidebar-brand__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--pm-accent);
  color: var(--pm-accent-contrast);
}

.sidebar-brand__name {
  line-height: 1;
}

.sidebar-search__field {
  width: 100%;
}

.sidebar-search__field .v-field {
  border-radius: 10px;
  background-color: var(--pm-app-surface-raised);
  box-shadow: none !important;
}

.sidebar-search__field .v-field__input,
.sidebar-search__field .v-field__clearable .v-icon {
  color: var(--pm-text) !important;
}

.sidebar-search__field .v-field__prepend-inner .v-icon {
  color: var(--pm-accent) !important;
}

.sidebar-search__field input::placeholder {
  color: var(--pm-muted);
}

.sidebar-search__field .v-field__outline {
  color: var(--pm-divider);
  --v-field-border-opacity: 1;
}

.sidebar-search__field .v-field--focused .v-field__outline {
  color: var(--pm-accent);
}

/* ── Sidebar-Fuß (Konto + Einstellungen + Aktivität) ───────────────────────── */
.sidebar-foot {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  border-top: 1px solid var(--pm-divider);
}

.sidebar-foot__btn {
  color: var(--pm-muted);
}

.sidebar-foot__rail-settings {
  display: none !important;
  color: var(--pm-muted);
}

.appbar-search__field .v-field--focused .v-field__outline {
  color: rgba(255, 255, 255, 0.92);
}

.papermind-app.v-theme--dark .appbar-search__field .v-field {
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

.papermind-app.v-theme--dark .appbar-search__field .v-field:hover {
  background-color: rgba(255, 255, 255, 0.25) !important;
}

.papermind-app.v-theme--dark .appbar-search__field .v-field:hover {
  background-color: rgba(255, 255, 255, 0.25) !important;
}

.papermind-app.v-theme--dark .appbar-search__field .v-field--focused {
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

.import-tray {
  position: fixed;
  left: 20px;
  bottom: 20px;
  z-index: 3200;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  width: min(440px, calc(100vw - 40px));
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-surface), 0.9);
  color: rgb(var(--v-theme-on-surface));
  box-shadow: 0 16px 38px rgba(15, 23, 42, 0.2);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.import-tray__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
}

.import-tray__content {
  min-width: 0;
}

.import-tray__title {
  font-size: 0.88rem;
  font-weight: 700;
  line-height: 1.25;
}

.import-tray__meta {
  margin-top: 1px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.76rem;
  line-height: 1.3;
}

.import-tray__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.import-tray__action {
  text-transform: none;
  letter-spacing: 0;
}

.import-tray-enter-active,
.import-tray-leave-active {
  transition:
    transform 220ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    opacity 220ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.import-tray-enter-from,
.import-tray-leave-to {
  opacity: 0;
  transform: translate3d(0, 18px, 0) scale(0.98);
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

.papermind-app .v-application__wrap,
.papermind-app .v-main,
.papermind-app .v-main__wrap {
  opacity: 1 !important;
  filter: none !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  background-color: var(--pm-app-surface) !important;
}

.papermind-app .v-field__overlay,
.papermind-app .v-btn__overlay,
.papermind-app .v-list-item__overlay,
.papermind-app .v-card__overlay,
.papermind-app .v-sheet__overlay {
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

.topbar-btn .v-icon {
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

.list-toolbar__search .v-field {
  border-radius: 10px;
  background: var(--pm-document-row-bg, var(--pm-app-surface-raised));
}

.list-toolbar__search .v-field--focused {
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

.tag-filter-drawer {
  --tag-drawer-duration: 360ms;
  --tag-drawer-content-duration: 280ms;
  --tag-drawer-easing: cubic-bezier(0.22, 1, 0.36, 1);
  flex: 0 0 auto;
  position: relative;
  z-index: 4;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: auto;
  max-height: 0;
  border-top: 1px solid var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  background: var(--pm-drawer-bg-collapsed, rgb(var(--v-theme-surface) / 0.6));
  transform-origin: bottom center;
  transition:
    max-height var(--tag-drawer-duration) var(--tag-drawer-easing),
    margin-top var(--tag-drawer-duration) var(--tag-drawer-easing),
    background-color 240ms ease,
    border-color 240ms ease,
    box-shadow 240ms ease;
  will-change: max-height, margin-top;
}

.tag-filter-drawer--open {
  max-height: min(40vh, 320px);
  background: rgba(255, 255, 255, 0.64);
  border-top-color: var(--pm-drawer-border-expanded, rgb(var(--v-theme-on-surface) / 0.16));
  backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.08);
  pointer-events: auto;
}

.tag-filter-drawer--closed {
  max-height: 0;
  border-top-color: transparent;
  background: var(--pm-drawer-bg-collapsed, rgb(var(--v-theme-surface) / 0.6));
  backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  box-shadow: none;
  pointer-events: none;
}

.tag-filter-drawer__body {
  min-height: 0;
  padding: 10px 18px;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
}

.tag-filter-drawer__panel {
  flex: 0 1 auto;
  min-height: 0;
  overflow: hidden;
  opacity: 0;
  transform: translate3d(0, 10px, 0);
  display: flex;
  flex-direction: column;
  will-change: opacity, transform;
}

.tag-filter-drawer--animate .tag-filter-drawer__panel {
  transition:
    opacity var(--tag-drawer-content-duration) ease,
    transform var(--tag-drawer-duration) var(--tag-drawer-easing);
}

.tag-filter-drawer--open .tag-filter-drawer__panel {
  opacity: 1;
  transform: translate3d(0, 0, 0);
}

.tag-filter-drawer__panel-inner {
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
}

/* Nur die Chip-Fläche scrollt; der Footer bleibt dadurch immer sichtbar. */
.tag-filter-drawer__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: center;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px 10px 10px;
  margin: 0 auto;
  max-width: 980px;
  scrollbar-width: thin;
}

.tag-filter-chip {
  appearance: none;
  -webkit-appearance: none;
  min-height: 26px;
  max-width: 100%;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 2px 8px;
  background: rgba(var(--v-theme-on-surface), 0.075);
  color: rgba(var(--v-theme-on-surface), 0.74);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.75rem;
  font-weight: 680;
  cursor: pointer;
  transform: translateY(0) scale(1);
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.tag-filter-chip:hover {
  background: rgba(var(--v-theme-on-surface), 0.115);
  color: rgba(var(--v-theme-on-surface), 0.9);
  transform: translateY(-1px);
}

.tag-filter-chip--active {
  border-color: transparent;
  background: #4b5a6f;
  background-image: none;
  color: #fff;
  box-shadow: none;
  text-shadow: none;
  transform: translateY(-1px);
}

.tag-filter-chip--active:hover {
  background: #4b5a6f;
  background-image: none;
  color: #fff;
  transform: translateY(-2px);
}

.tag-filter-chip--active .tag-filter-chip__name {
  color: #fff !important;
}

.tag-filter-chip__check {
  flex: 0 0 auto;
  opacity: 0.96;
}

.tag-filter-chip__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-filter-chip__count {
  color: rgba(var(--v-theme-on-surface), 0.46);
  font-size: 0.7rem;
  font-weight: 700;
}

.tag-filter-chip--active .tag-filter-chip__count {
  color: rgba(255, 255, 255, 0.82) !important;
}

.tag-filter-chip-list-move,
.tag-filter-chip-list-enter-active,
.tag-filter-chip-list-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.tag-filter-chip-list-enter-from {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.tag-filter-chip-list-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}

.tag-filter-drawer__empty {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 0.8rem;
}

.tag-filter-drawer__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  width: 100%;
  max-width: 980px;
  margin: 2px auto 0;
  padding: 0 10px;
}

.tag-filter-drawer__footer-btn {
  border: none;
  border-radius: 6px;
  padding: 3px 7px;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 0.72rem;
  font-weight: 650;
  cursor: pointer;
}

.tag-filter-drawer__footer-btn:hover:not(:disabled) {
  background: rgba(var(--v-theme-on-surface), 0.07);
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.tag-filter-drawer__footer-btn--all {
  color: rgba(var(--v-theme-primary), 0.84);
}

.tag-filter-drawer__footer-btn--reset {
  margin-left: auto;
}

.tag-filter-drawer__footer-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tag-filter-drawer-enter-active,
.tag-filter-drawer-leave-active {
  transition:
    opacity 240ms ease,
    transform 360ms cubic-bezier(0.22, 1, 0.36, 1);
}

.tag-filter-drawer-enter-from,
.tag-filter-drawer-leave-to {
  opacity: 0;
  transform: translate3d(0, 10px, 0);
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

.pm-settings-layout {
  display: flex;
  align-items: stretch;
  gap: 0;
  height: 100%;
}

.pm-settings-nav {
  flex: 0 0 220px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 16px 20px 18px;
  overflow-y: auto;
}

.pm-settings-nav__group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pm-settings-nav__group + .pm-settings-nav__group {
  padding-top: 14px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.pm-settings-nav__group-label {
  padding: 0 14px 4px;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.2;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.46);
}

.pm-settings-nav__item {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  min-width: 0;
  padding: 10px 14px;
  border: 1px solid transparent;
  border-radius: 12px;
  font-size: 0.9rem;
  font-weight: 600;
  text-align: left;
  color: rgba(var(--v-theme-on-surface), 0.74);
  background: transparent;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.pm-settings-nav__item:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.pm-settings-nav__item--active {
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.pm-settings-nav__icon {
  flex: 0 0 20px;
  opacity: 0.85;
}

.pm-settings-nav__item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pm-settings-panel {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  padding: 12px 24px 20px 22px;
  overflow-y: auto;
  border-left: 1px solid rgba(var(--v-theme-on-surface), 0.12);
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

.pm-settings-panel > .pm-settings-section {
  margin-bottom: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
}

@media (max-width: 640px) {
  .pm-settings-layout {
    flex-direction: column;
    gap: 0;
  }

  .pm-settings-nav {
    flex: 0 0 auto;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 12px;
    width: 100%;
    overflow: visible;
    padding: 16px 16px 12px;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  }

  .pm-settings-nav__group {
    flex: 1 1 100%;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 6px;
  }

  .pm-settings-nav__group + .pm-settings-nav__group {
    padding-top: 10px;
  }

  .pm-settings-nav__group-label {
    flex: 1 1 100%;
    padding: 0 4px 2px;
  }

  .pm-settings-nav__item {
    width: auto;
    flex: 1 1 auto;
    justify-content: center;
  }

  .pm-settings-panel {
    flex: 1 1 auto;
    min-height: 0;
    padding: 12px 16px 16px;
    border-left: none;
  }
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

.pm-settings-body {
  padding-top: 16px;
  padding-bottom: 12px;
}

.pm-settings-footer {
  padding: 18px 24px;
  justify-content: flex-end;
}

/* Feste Höhe, damit der Dialog beim Wechsel der Abschnitte nicht springt.
   Unscoped global → ohne :deep, mit erhöhter Spezifität gegenüber BaseDialog. */
.pm-dialog.pm-settings-card .pm-dialog__content-wrap {
  height: min(62vh, 600px);
  overflow: hidden;
}

.pm-dialog.pm-settings-card .pm-dialog__content {
  height: 100%;
  padding: 0;
  overflow: hidden;
  box-sizing: border-box;
}

.app-modal__body--flush {
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
  --pm-sidebar-rail-duration: 240ms;
  display: grid;
  grid-template-columns: 288px 1fr minmax(360px, 43%);
  height: calc(100dvh - var(--v-layout-top, 0px) - var(--v-layout-bottom, 0px));
  /* Sanftes Ein-/Ausklappen der Seitenleiste: Nur die LINKE Spalte schrumpft,
     die Mitte wächst; die rechte Vorschau-Spalte (minmax …, 43%) bleibt konstant
     breit → kein PDF-Re-Render. Zusammen mit der Breiten-Toleranz im PdfPreview-
     onResize ruckelt das nicht mehr, vermeidet aber den abrupten Sprung. */
  transition: grid-template-columns var(--pm-sidebar-rail-duration) cubic-bezier(0.4, 0, 0.2, 1);
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: background-color var(--pm-duration-fast, 140ms) ease;
  will-change: width;
}

.sidebar-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  border-top: 1px solid color-mix(in srgb, var(--pm-divider) 65%, transparent);
  margin-top: 12px;
  padding-top: 12px;
}

/* Kopfbereich und Profilbereich bleiben außerhalb des Scrollbereichs. */
.panel-left > .sidebar-head,
.panel-left > .sidebar-foot {
  flex: none;
}

.panel-middle__header {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(var(--v-theme-surface), 0.68);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--pm-divider);
}

.panel-middle__heading {
  font-size: 0.98rem;
  font-weight: 600;
  color: var(--pm-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.panel-middle__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
}

.panel-middle__header .v-btn {
  text-transform: none;
  letter-spacing: 0;
  border-radius: 10px;
}

.list-header-btn--active {
  color: rgb(var(--v-theme-primary));
}

/* ── Sidebar-Kopfzeile + Einklapp-Toggle ───────────────────────────────────── */
.sidebar-head__top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-head__top .sidebar-brand {
  flex: 1 1 auto;
  min-width: 0;
}

.sidebar-rail-toggle {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 0;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}

.sidebar-rail-toggle:hover {
  background: var(--pm-sidebar-hover);
  color: var(--pm-accent);
}

.sidebar-foot__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.panel-left .v-list-item-title,
.panel-left .v-list-item__content,
.panel-left .v-list-item__append,
.panel-left .sidebar-item-right,
.panel-left .sidebar-section-header,
.sidebar-brand__name,
.sidebar-search__field,
.sidebar-account__info,
.sidebar-account__chev,
.sidebar-foot__actions {
  transition:
    opacity 180ms ease,
    transform var(--pm-sidebar-rail-duration) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

/* ── Eingeklappte Icon-Spalte ──────────────────────────────────────────────── */
.workspace.workspace--rail {
  grid-template-columns: 64px 1fr minmax(360px, 43%);
}

.workspace--sidebar-transitioning .panel-left {
  pointer-events: none;
}

.workspace--sidebar-collapsing .panel-left .v-list-item-title,
.workspace--sidebar-collapsing .panel-left .v-list-item__content,
.workspace--sidebar-collapsing .panel-left .v-list-item__append,
.workspace--sidebar-collapsing .panel-left .sidebar-item-right,
.workspace--sidebar-collapsing .panel-left .sidebar-section-header,
.workspace--sidebar-collapsing .sidebar-brand__name,
.workspace--sidebar-collapsing .sidebar-search__field,
.workspace--sidebar-collapsing .sidebar-account__info,
.workspace--sidebar-collapsing .sidebar-account__chev,
.workspace--sidebar-collapsing .sidebar-foot__actions {
  opacity: 0;
  transform: translateX(-10px);
}

.workspace--sidebar-expanding .panel-left .v-list-item-title,
.workspace--sidebar-expanding .panel-left .v-list-item__content,
.workspace--sidebar-expanding .panel-left .v-list-item__append,
.workspace--sidebar-expanding .panel-left .sidebar-item-right,
.workspace--sidebar-expanding .panel-left .sidebar-section-header,
.workspace--sidebar-expanding .sidebar-brand__name,
.workspace--sidebar-expanding .sidebar-search__field,
.workspace--sidebar-expanding .sidebar-account__info,
.workspace--sidebar-expanding .sidebar-account__chev,
.workspace--sidebar-expanding .sidebar-foot__actions {
  animation: sidebar-rail-content-in 220ms var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)) both;
  animation-delay: 90ms;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .v-list-item-title,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .v-list-item__content,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .v-list-item__append,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item-right,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-section-header,
.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-brand__name,
.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-search__field,
.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-account__info,
.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-account__chev,
.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-foot__actions {
  display: none !important;
}

@keyframes sidebar-rail-content-in {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* Sektions-Sammelpunkte ("Alle Tags"/"Alle Dokumenttypen") im Rail immer zeigen. */
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-section-drawer {
  grid-template-rows: 1fr !important;
}
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-section-content {
  visibility: visible !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .views-list {
  padding: 6px 0;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .v-list-item {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  padding: 0 !important;
  min-height: 42px;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .v-list-item__prepend {
  position: absolute !important;
  inset: 0 !important;
  width: 42px !important;
  min-width: 42px !important;
  height: 42px !important;
  margin: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .v-list-item__spacer {
  display: none !important;
  width: 0 !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item {
  position: relative;
  display: block !important;
  width: 42px;
  height: 42px;
  min-height: 42px !important;
  margin: 3px auto;
  border-radius: 14px;
  padding: 0 !important;
  overflow: hidden;
  box-sizing: border-box;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item::before {
  display: none !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item .v-list-item__overlay,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item .v-list-item__underlay {
  border-radius: inherit;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item .v-list-item__prepend,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item .v-list-item__content,
.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item .v-list-item__append {
  transform: none !important;
  transition: none !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item .v-icon {
  transform: none !important;
  transition: color 0.16s ease, opacity 0.16s ease !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-item:hover .v-icon {
  transform: none !important;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-head {
  align-items: center;
  padding-inline: 0;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-head__top {
  flex-direction: column;
  gap: 8px;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-head__top .sidebar-brand {
  flex: none;
  justify-content: center;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-foot {
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding-inline: 0;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-foot__rail-settings {
  display: inline-flex !important;
  width: 38px;
  height: 38px;
  border-radius: 12px;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .sidebar-foot .sidebar-account {
  flex: none;
  justify-content: center;
  padding: 5px;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-section-divider {
  margin-inline: 16px;
}

.workspace--rail:not(.workspace--sidebar-transitioning) .panel-left .sidebar-section-divider--after-library {
  display: none;
}

.panel-middle {
  position: relative;
  background: var(--pm-content-surface);
  --tag-filter-drawer-gap: 20px;
  /* Eigene Spalten-Layout-Steuerung: View scrollt intern, Drawer bleibt Footer.
     Überschreibt das overflow-y:auto von .panel, damit der Panel-Container nicht
     als Ganzes scrollt (sonst würde der Tag-Filter-Drawer zusätzliche Scrollhöhe
     erzeugen und die Liste unter die Toolbar schieben). */
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-middle__view {
  flex: 1 1 auto;
  min-height: 0;
  height: auto;
  overflow-y: auto;
  position: relative;
  width: 100%;
  box-sizing: border-box;
}

.panel-middle--tag-filter-open .panel-middle__view {
  scroll-padding-bottom: calc(var(--tag-filter-drawer-height, 0px) + var(--tag-filter-drawer-gap));
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

.sidebar-section-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  opacity: 0.66;
  text-transform: none;
}

.sidebar-section-divider {
  margin: 14px 12px 12px;
  opacity: 0.65;
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

.sidebar-item .v-list-item__prepend {
  width: 42px;
  min-width: 42px;
  justify-content: center;
}

.sidebar-item .v-list-item-title {
  font-size: 0.9rem;
}

.sidebar-item--primary .v-list-item-title {
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.96);
}

.sidebar-item--primary .v-icon {
  opacity: 0.95;
}

.sidebar-item--secondary {
  --v-list-item-min-height: 34px;
}

.sidebar-item--secondary .v-list-item-title {
  font-size: 0.84rem;
  opacity: 0.76;
}

.sidebar-item--secondary .v-icon {
  opacity: 0.62;
}

.sidebar-item--secondary.v-list-item--active .v-list-item-title,
.sidebar-item--secondary.v-list-item--active .v-icon {
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

.sidebar-item.v-list-item--active .v-list-item-title {
  font-weight: 600;
}

.sidebar-item--plain-label .v-list-item-title,
.sidebar-item--plain-label.v-list-item--active .v-list-item-title {
  font-weight: 400;
}

.sidebar-item--tag .sidebar-tag-pill {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  width: fit-content;
  max-width: 100%;
  min-height: 24px;
  padding: 1px 10px 2px;
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

.sidebar-item--folder-create .v-list-item-title {
  font-weight: 500;
}

/* Konzept „Icon-Frische": alle Navigations-Icons tragen den Akzent-Ton. */
.papermind-app .panel-left .sidebar-item .v-icon {
  color: rgb(var(--v-theme-primary)) !important;
  opacity: 1;
}

/* Aktiver Eintrag: klares Teal-Pill (Tint + Akzentrand) + Titel im Akzent. */
.papermind-app .panel-left .sidebar-item.v-list-item--active {
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 18%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, rgb(var(--v-theme-primary)) 32%, transparent);
}

.papermind-app .panel-left .sidebar-item.v-list-item--active .v-list-item-title {
  color: rgb(var(--v-theme-primary));
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

.tags-view-list-wrap {
  margin: 12px;
  padding: 0;
}

.tags-view-section-title {
  margin-bottom: 8px;
  font-size: 0.74rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.7;
  font-weight: 700;
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

.tag-row--selection-mode {
  grid-template-columns: 22px 1fr auto auto;
  cursor: pointer;
}

.tag-row--selected {
  border-color: rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.1);
}

.tag-row:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.08);
}

.tag-row:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.25);
  outline-offset: 2px;
}

.tag-row__checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.22);
  border-radius: 6px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-surface), 0.72);
}

.tag-row--selected .tag-row__checkbox {
  border-color: rgba(var(--v-theme-primary), 0.6);
  background: rgba(var(--v-theme-primary), 0.16);
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
  content-visibility: auto;
  contain-intrinsic-block-size: auto 104px;
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
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    border-color     var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.document-row + .document-row {
  margin-top: 10px;
}

.document-row:hover {
  background: var(--pm-row-hover);
  border-color: rgba(59, 130, 246, 0.16);
}

.document-row--active {
  background: var(--pm-row-active);
  border-color: rgba(59, 130, 246, 0.22);
}

.document-row--active:hover {
  background: var(--pm-row-active);
  border-color: rgba(59, 130, 246, 0.28);
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
  /* Keine theme-spezifischen Abstände: Light nutzt dieselben Sidebar-Maße wie
     Dark (kein panel-left-Padding, views-list 6px aus der Basisregel). Das hält
     beide Themes konsistent und richtet die Marke an der Bereichsüberschrift aus. */
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

.papermind-app.v-theme--light .sidebar-item--secondary .v-list-item-title,
.papermind-app.v-theme--light .sidebar-item--secondary .v-icon {
  opacity: 0.78;
}

.papermind-app.v-theme--light .panel-left::before,
.papermind-app.v-theme--light .panel-middle::before,
.papermind-app.v-theme--light .panel-right::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(1200px 600px at 20% -10%, rgba(8, 145, 178, 0.1), transparent 55%);
  opacity: 0.22;
}

.papermind-app.v-theme--dark .sidebar-item--tag .sidebar-tag-pill {
  background: rgba(var(--v-theme-primary), 0.16);
  color: rgb(var(--v-theme-primary));
}

.papermind-app.v-theme--dark .sidebar-item--tag:hover .sidebar-tag-pill {
  background: rgba(var(--v-theme-primary), 0.24);
}

.papermind-app.v-theme--dark .sidebar-item--tag.v-list-item--active .sidebar-tag-pill {
  background: rgba(var(--v-theme-primary), 0.30);
}

.papermind-app.v-theme--dark .document-row {
  background: var(--pm-document-row-bg, var(--pm-app-surface-raised));
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

/* Tag-Schublade im Darkmode: flache Oberfläche wie die Detailschublade,
   kein heller Farbverlauf und keine hellen Glanzkanten. */
.papermind-app.v-theme--dark .tag-filter-drawer--open {
  border-top: 1px solid var(--pm-drawer-border-expanded);
  background: rgba(20, 27, 40, 0.72);
  box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.08);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field,
.papermind-app.v-theme--dark .tags-view-search .v-field,
.papermind-app.v-theme--dark .tags-view-list-wrap,
.papermind-app.v-theme--dark .tag-row {
  background: var(--pm-app-surface-raised);
}

.papermind-app.v-theme--dark .tag-focus-panel {
  background:
    linear-gradient(145deg, rgba(87, 143, 210, 0.14), transparent 38%),
    linear-gradient(28deg, rgba(77, 158, 138, 0.11), transparent 44%),
    var(--pm-viewer-surface);
}

.papermind-app.v-theme--dark .tag-focus-stat {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.1);
}

.papermind-app.v-theme--dark .tag-focus-chip {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent),
    rgba(var(--tag-accent), 0.22);
  border-color: rgba(var(--tag-accent), 0.38);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.16);
}

.papermind-app.v-theme--dark .tag-focus-chip:hover,
.papermind-app.v-theme--dark .tag-focus-chip:focus-visible {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.12), transparent),
    rgba(var(--tag-accent), 0.32);
  border-color: rgba(var(--tag-accent), 0.68);
}

.papermind-app.v-theme--dark .tag-focus-cloud--selection-mode .tag-focus-chip {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent),
    rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.13);
  color: rgba(var(--v-theme-on-surface), 0.68);
  box-shadow: none;
}

.papermind-app.v-theme--dark .tag-focus-cloud--selection-mode .tag-focus-chip:hover,
.papermind-app.v-theme--dark .tag-focus-cloud--selection-mode .tag-focus-chip:focus-visible {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent),
    rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.22);
}

.papermind-app.v-theme--dark .tag-focus-cloud--selection-mode .tag-focus-cloud__item--selected .tag-focus-chip {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.12), transparent),
    rgba(var(--tag-accent), 0.34);
  border-color: rgba(var(--tag-accent), 0.68);
  color: rgba(var(--v-theme-on-surface), 0.94);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field,
.papermind-app.v-theme--dark .tags-view-search .v-field {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field,
.papermind-app.v-theme--dark .tags-view-search .v-field {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field:hover,
.papermind-app.v-theme--dark .tags-view-search .v-field:hover {
  background: rgba(255, 255, 255, 0.11);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field:hover,
.papermind-app.v-theme--dark .tags-view-search .v-field:hover {
  background: rgba(255, 255, 255, 0.11);
}

.papermind-app.v-theme--dark .list-toolbar__search .v-field--focused,
.papermind-app.v-theme--dark .tags-view-search .v-field--focused {
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
}

.papermind-app.v-theme--dark .document-row--active {
  background: var(--pm-document-row-active-bg, var(--pm-row-active));
  border-color: rgba(var(--v-theme-primary), 0.42);
}

.papermind-app.v-theme--dark .document-row--active:hover {
  background: var(--pm-document-row-active-bg, var(--pm-row-active));
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
  min-width: 0;
  max-width: min(150px, 42%);
  font-size: 0.68rem;
  letter-spacing: 0.01em;
}

.document-row__tag-chip .v-chip__content {
  display: block;
  min-width: 0;
  max-width: 100%;
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

.document-row__snippet mark {
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

.document-row__fav-btn,
.document-row__menu-btn {
  width: 36px !important;
  height: 36px !important;
  min-width: 36px !important;
  flex: 0 0 36px;
  padding: 0 !important;
  transform: none !important;
  transition-property: opacity, background-color !important;
}

.document-row__fav-btn:hover,
.document-row__fav-btn:focus-visible,
.document-row__fav-btn:active,
.document-row__menu-btn:hover,
.document-row__menu-btn:focus-visible,
.document-row__menu-btn:active {
  transform: none !important;
}

.document-row__fav-btn .v-btn__content,
.document-row__menu-btn .v-btn__content,
.document-row__fav-btn .v-icon,
.document-row__menu-btn .v-icon {
  transform: none !important;
  transition: none !important;
}

.document-row__menu-btn {
  opacity: 0.38;
  transition: opacity 0.16s ease, background-color 0.16s ease;
}

.document-row__menu-btn .v-icon {
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

.tag-focus-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.94);
  background:
    linear-gradient(145deg, rgba(44, 114, 182, 0.09), transparent 36%),
    linear-gradient(28deg, rgba(42, 135, 121, 0.08), transparent 42%),
    var(--pm-viewer-surface);
}

.tag-focus-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.tag-focus-panel__eyebrow {
  margin-bottom: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-primary), 0.92);
}

.tag-focus-panel__header h2 {
  margin: 0;
  font-size: clamp(1.35rem, 1.8vw, 2rem);
  line-height: 1.05;
  font-weight: 760;
}

.tag-focus-panel__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.tag-focus-stat {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.09);
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.72);
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.12s ease;
}

.tag-focus-stat:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.06);
}

.tag-focus-stat:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.55);
  outline-offset: 2px;
}

.tag-focus-stat--active {
  border-color: rgba(var(--v-theme-primary), 0.7);
  background: rgba(var(--v-theme-primary), 0.12);
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.45);
}

.tag-focus-stat--active strong {
  color: rgb(var(--v-theme-primary));
}

.tag-focus-stat--active span {
  opacity: 0.9;
}

.tag-focus-stat strong {
  display: block;
  font-size: 1.05rem;
  line-height: 1.15;
  font-weight: 760;
}

.tag-focus-stat span {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  font-size: 0.72rem;
  line-height: 1.2;
  opacity: 0.7;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-focus-cloud {
  flex: 1;
  min-height: 0;
  align-content: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  overflow-y: auto;
  padding: 8px 2px 12px;
  scrollbar-width: thin;
}

/* Wolke wechselt animiert, wenn ein anderer Filter (Gesamt/Genutzt/Leer) gewählt wird */
.tag-cloud-swap-enter-active,
.tag-cloud-swap-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.tag-cloud-swap-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.985);
}

.tag-cloud-swap-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.985);
}

@media (prefers-reduced-motion: reduce) {
  .tag-cloud-swap-enter-active,
  .tag-cloud-swap-leave-active {
    transition: opacity 0.12s ease;
  }
  .tag-cloud-swap-enter-from,
  .tag-cloud-swap-leave-to {
    transform: none;
  }
}

.tag-focus-cloud__item {
  --tag-accent: 44, 114, 182;
  --tag-float-offset: 3px;
  --tag-float-duration: 12s;
  --tag-float-delay: 0s;
  position: relative;
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  border-radius: 999px;
  animation: tagFloat var(--tag-float-duration) ease-in-out infinite;
  animation-delay: var(--tag-float-delay);
}

.tag-focus-cloud__item:hover,
.tag-focus-cloud__item:focus-within {
  z-index: 2;
  animation-play-state: paused;
}

.tag-focus-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 7px;
  max-width: min(100%, 320px);
  min-height: 34px;
  border: 1px solid rgba(var(--tag-accent), 0.34);
  border-radius: 999px;
  padding: 7px 34px 7px 12px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.28), transparent),
    rgba(var(--tag-accent), 0.14);
  color: inherit;
  cursor: pointer;
  font: inherit;
  box-shadow: 0 8px 18px rgba(var(--tag-accent), 0.08);
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.tag-focus-chip:hover,
.tag-focus-chip:focus-visible {
  border-color: rgba(var(--tag-accent), 0.68);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.34), transparent),
    rgba(var(--tag-accent), 0.22);
  box-shadow: 0 12px 26px rgba(var(--tag-accent), 0.15);
  transform: translateY(-1px);
}

.tag-focus-cloud--selection-mode .tag-focus-chip {
  border-color: rgba(var(--v-theme-on-surface), 0.16);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), transparent),
    rgba(var(--v-theme-on-surface), 0.07);
  box-shadow: none;
  color: rgba(var(--v-theme-on-surface), 0.68);
}

.tag-focus-cloud--selection-mode .tag-focus-chip:hover,
.tag-focus-cloud--selection-mode .tag-focus-chip:focus-visible {
  border-color: rgba(var(--v-theme-on-surface), 0.28);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.24), transparent),
    rgba(var(--v-theme-on-surface), 0.1);
  box-shadow: none;
}

.tag-focus-cloud--selection-mode .tag-focus-cloud__item--selected .tag-focus-chip {
  border-color: rgba(var(--tag-accent), 0.68);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.34), transparent),
    rgba(var(--tag-accent), 0.24);
  box-shadow: 0 12px 26px rgba(var(--tag-accent), 0.14);
  color: inherit;
}

.tag-focus-chip:focus-visible {
  outline: 2px solid rgba(var(--tag-accent), 0.32);
  outline-offset: 2px;
}

.tag-focus-chip__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-focus-chip__count {
  flex: 0 0 auto;
  font-size: 0.72em;
  font-weight: 760;
  opacity: 0.72;
}

.tag-focus-chip__menu {
  position: absolute;
  top: 50%;
  right: 2px;
  width: 28px;
  height: 28px;
  min-width: 28px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  transform: translateY(-50%);
}

.tag-focus-chip__menu:hover,
.tag-focus-chip__menu:focus-visible {
  color: rgba(var(--v-theme-on-surface), 0.92);
}

@keyframes tagFloat {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(var(--tag-float-offset));
  }
}

@media (prefers-reduced-motion: reduce) {
  .tag-focus-cloud__item {
    animation: none;
  }

  .tag-focus-chip {
    transition: none;
  }
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
  opacity: 1;
}

.details-drawer__header--expanded .details-drawer__subtitle {
  opacity: 1;
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
  padding: 4px 16px 12px;
}

/* Interaktive Elemente in der Detailsschublade dürfen bei Hover/Fokus ihre
   Geometrie nicht verändern. Vuetify bringt für Buttons, Icons und Felder
   Transform-Transitions mit, die hier als leichtes Wackeln sichtbar werden. */
.details-drawer__header .v-btn,
.details-drawer__header .v-btn__content,
.details-drawer__header .v-icon,
.details-drawer__body .v-btn,
.details-drawer__body .v-btn__content,
.details-drawer__body .v-chip,
.details-drawer__body .v-chip__content,
.details-drawer__body .v-chip__close,
.details-drawer__body .v-icon,
.details-drawer__body .v-field,
.details-drawer__body .v-field__input,
.details-drawer__body .pm-prop-field,
.details-drawer__body .pm-tags-input {
  transform: none !important;
  translate: none !important;
}

.details-drawer__header .v-btn,
.details-drawer__body .v-btn,
.details-drawer__body .v-chip,
.details-drawer__body .v-field,
.details-drawer__body .pm-prop-field,
.details-drawer__body .pm-tags-input {
  transition-property: background-color, border-color, box-shadow, color, opacity !important;
}

/* Eigenschaftslisten-Layout: Label links, Wert rechts, Hairline-Trennlinien.
   Felder sind rahmenlos und „erwachen" erst bei Hover/Fokus (.pm-prop-field). */
.pm-prop {
  display: flex;
  flex-direction: column;
}

.pm-prop-row {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.07);
}

.pm-prop-row:first-child {
  border-top: none;
}

.pm-prop-row--top {
  align-items: start;
}

.pm-prop-key {
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  line-height: 1.3;
  padding: 4px 0;
}

.pm-prop-row--top .pm-prop-key {
  padding-top: 15px;
}

.pm-prop-val {
  min-width: 0;
  padding: 5px 0;
}

.pm-prop-field {
  min-width: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  transition:
    background-color 0.12s ease,
    border-color 0.12s ease,
    box-shadow 0.12s ease;
}

.pm-prop-value-with-action {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 32px;
  align-items: center;
  gap: 4px;
}

.pm-prop-settings-link {
  width: 30px !important;
  height: 30px !important;
  min-width: 30px !important;
  color: rgba(var(--v-theme-on-surface), 0.46) !important;
}

.pm-prop-settings-link:hover {
  color: rgb(var(--v-theme-primary)) !important;
  background: rgba(var(--v-theme-primary), 0.08);
}

.pm-prop-field:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
  border-color: rgba(var(--v-theme-on-surface), 0.12);
}

.pm-prop-field:focus-within {
  background: rgb(var(--v-theme-surface));
  border-color: rgba(var(--v-theme-primary), 0.6);
  box-shadow: 0 0 0 3px rgba(var(--v-theme-primary), 0.12);
}

/* Datum braucht keine volle Spaltenbreite */
.pm-prop-field--inline {
  max-width: 190px;
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

/* Einheitliches Icon-Button-System für die Header-Aktionen */
.details-action-btn {
  width: 34px !important;
  height: 34px !important;
  min-width: 34px !important;
  padding: 0 !important;
  border-radius: 999px;
  border: 1px solid transparent;
  opacity: 1 !important;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.details-action-btn .v-btn__content {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Primäre Aktion (KI-Befüllung): hervorgehoben mit Primary-Tint */
.details-action-btn--primary {
  border-color: rgba(var(--v-theme-primary), 0.4);
  background: rgba(var(--v-theme-primary), 0.12);
}

.details-action-btn--primary:hover {
  border-color: rgba(var(--v-theme-primary), 0.65);
  background: rgba(var(--v-theme-primary), 0.2);
}

/* Leise Aktionen (Überlauf-Menü, Disclosure): randlos, gedämpft */
.details-action-btn--quiet .v-btn__content {
  opacity: 0.6;
  transition: opacity 0.16s ease;
}

.details-action-btn--quiet:hover {
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.details-action-btn--quiet:hover .v-btn__content {
  opacity: 0.95;
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

.pm-drawer-body .v-input,
.pm-drawer-body .v-combobox,
.pm-drawer-body .v-textarea {
  margin-top: 0;
  margin-bottom: 0;
}

.pm-drawer-body .v-input__details {
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

.details-chevron-btn .v-icon {
  font-size: 20px;
  transition: transform 200ms ease-out;
}

.details-drawer__subtitle {
  margin-top: 0;
  font-size: 0.9rem;
  font-weight: 650;
  opacity: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.details-drawer__meta-line {
  margin-top: 2px;
  font-size: 0.72rem;
  opacity: 0.80;
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

/* OCR-Status als dezenter Hinweis in der Meta-Zeile (Status, keine Aktion) */
.details-ocr-status {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex: 0 0 auto;
  font-weight: 600;
}

.details-ocr-status--done {
  color: rgb(var(--v-theme-success));
}

.details-ocr-status--warning {
  color: rgb(var(--v-theme-warning));
}

.details-ocr-status--error {
  color: rgb(var(--v-theme-error));
}

.details-ocr-status--progress {
  color: rgb(var(--v-theme-primary));
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

.details-tags-combobox input {
  font-size: 0.85rem;
  line-height: 1.42;
}

.details-tags-combobox .v-chip {
  height: 22px;
  font-size: 12px;
  padding-inline: 7px;
}

.details-tags-combobox .v-chip .v-chip__close {
  margin-inline-start: 2px;
}

/* Eigenes Tag-Feld: Chips + Eingabe in EINEM umbrechenden Rahmen (Gmail-Stil).
   Ein simpler flex-wrap-Container wächst zuverlässig mit – im Gegensatz zu
   Vuetifys v-input-Grid, das die flex-wrap-Eingabe nur an max-content (eine
   Zeile) bemisst und umgebrochene Chips überlaufen lässt. */
.pm-tags-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  /* Links 10px wie die übrigen Felder, rechts 8px (gleicher Pfeil-Inset) */
  padding: 4px 8px 4px 10px;
  /* rahmenlos wie die übrigen Eigenschaftsfelder; erwacht bei Hover/Fokus */
  min-height: 34px;
  border: 1px solid transparent;
  border-radius: 8px;
  transition:
    background-color 0.12s ease,
    border-color 0.12s ease,
    box-shadow 0.12s ease;
}
.details-drawer__body .v-field {
  border-radius: 8px;
}
.pm-tags-input:hover {
  background: rgba(var(--v-theme-on-surface), 0.04);
  border-color: rgba(var(--v-theme-on-surface), 0.12);
}
.pm-tags-input:focus-within {
  background: rgb(var(--v-theme-surface));
  border-color: rgba(var(--v-theme-primary), 0.6);
  box-shadow: 0 0 0 3px rgba(var(--v-theme-primary), 0.12);
}
.pm-tags-input--disabled {
  opacity: 0.6;
  pointer-events: none;
}
.pm-tags-input__chip {
  font-size: 12px;
}
.pm-tags-input__field {
  flex: 1 1 90px;
  min-width: 90px;
}
/* Plain-Combobox nahtlos einbetten: kein Eigenrand/Padding. */
.pm-tags-input__field .v-field {
  padding: 0;
  --v-field-padding-start: 0;
  --v-field-padding-end: 0;
}
/* Eingabe EXAKT auf Chip-Höhe (26px) zwingen: Die Plain-Variante bringt sonst
   48px Control-Height mit, wodurch mehrzeilig die untere (Eingabe-)Zeile höher
   wird als die reinen Chip-Zeilen → ungleiche Abstände oben/unten. */
.pm-tags-input__field .v-input__control,
.pm-tags-input__field .v-field,
.pm-tags-input__field .v-field__field,
.pm-tags-input__field .v-field__input,
.pm-tags-input__field .v-field__append-inner {
  min-height: 26px !important;
  height: 26px !important;
}
/* Eingabe + Cursor vertikal mittig (Plain-Variante richtet sonst oben aus). */
.pm-tags-input__field .v-field__field,
.pm-tags-input__field .v-field__input {
  align-items: center !important;
}
.pm-tags-input__field .v-field__input {
  padding: 0;
  font-size: 0.85rem;
}
/* Höhere Spezifität als die globale .pm-drawer-body-Regel: der 10px-Inset liegt
   schon auf dem .pm-tags-input-Container, das Combobox-Feld selbst bleibt bündig,
   damit Platzhalter (links) und Pfeil (rechts) mit den übrigen Feldern fluchten. */
.pm-drawer-body .pm-tags-input__field .v-field__input {
  padding: 0 !important;
}
.pm-drawer-body .pm-tags-input__field .v-field__append-inner {
  padding-left: 4px !important;
  padding-right: 0 !important;
}


/* Einheitliches Overlay-Menü für ALLE Detail-Drawer-Selects (Dokumenttyp,
   Korrespondent, Tags): Hairline-Rahmen + flacher Schatten wie das Formular,
   funktioniert in hell und dunkel. */
.pm-menu {
  border-radius: 12px;
  background: rgba(var(--v-theme-surface-2), 0.98);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.16);
  padding: 3px;
  z-index: 6000 !important;
  overflow: hidden;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  opacity: 1 !important;
}

.v-overlay-container .pm-menu {
  z-index: 6000 !important;
}

.pm-menu .v-list {
  background: transparent;
  padding: 0;
  overflow: auto;
}

.pm-menu .v-list-item {
  min-height: 32px;
  border-radius: 10px;
  margin: 1px 0;
}

.pm-menu .v-list-item-title {
  font-size: 0.8rem;
}

/* Korrespondenten-Dropdown: jede Option rendert eine feste Icon-Spalte im
   Textfluss (Symbol bei Sammlungen, sonst leer), sodass die Beschriftungen
   aller Einträge in einer Flucht stehen – ohne Überlappung. */
.pm-corr-opt {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.pm-corr-opt__icon {
  flex: 0 0 auto;
  display: inline-flex;
  justify-content: center;
  width: 20px;
  margin-inline-end: 8px;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.pm-corr-opt__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pm-menu .v-list-item:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.pm-menu .v-list-item--active {
  background: rgba(var(--v-theme-on-surface), 0.1);
}

/* Tag-Menü behält seine begrenzte Höhe */
.pm-menu.pm-menu--tags .v-list {
  max-height: 180px;
}

.pm-notes-field .v-field__input {
  transition: min-height var(--pm-duration-normal, 210ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
  align-items: flex-start;
}

.pm-notes-field textarea {
  font-size: 0.85rem;
  line-height: 1.42;
  margin-top: 0;
  padding-top: 0;
  min-height: 0;
  overflow-y: auto;
}

/* Felder in der Dokumentdetail-Schublade: rahmenlose Plain-Variante, die erst
   bei Hover/Fokus aufwacht. Rahmen + Hintergrund liegen auf .pm-prop-field /
   .pm-tags-input; das v-field selbst bleibt transparent. */
.pm-drawer-body .v-field {
  --v-input-control-height: 34px !important;
  --v-field-padding-start: 0 !important;
  --v-field-padding-end: 0 !important;
  min-height: 34px !important;
  background: transparent !important;
  border-radius: 8px !important;
}

/* Plain-Variante dämpft den Inhalt sonst auf ~0.62 Opazität */
.pm-drawer-body .v-field--variant-plain {
  opacity: 1 !important;
}

.pm-drawer-body .v-field__input {
  min-height: 34px !important;
  padding: 0 10px !important;
  align-items: center !important;
  font-size: 0.85rem;
  line-height: 1.35;
}

.pm-drawer-body .v-select__selection,
.pm-drawer-body .v-select__selection-text,
.pm-drawer-body .v-combobox__selection,
.pm-drawer-body .v-field input {
  display: flex;
  align-items: center;
  min-height: 34px;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.35;
}

.pm-drawer-body input::placeholder,
.pm-drawer-body textarea::placeholder,
.pm-drawer-body .v-field__input input::placeholder {
  color: rgba(var(--v-theme-on-surface), 0.42);
}

.pm-drawer-body .v-select.v-input--dirty .v-field__input,
.pm-drawer-body .v-select.v-input--dirty .v-select__selection,
.pm-drawer-body .v-select.v-input--dirty .v-select__selection-text,
.pm-drawer-body .v-combobox.v-input--dirty .v-field__input,
.pm-drawer-body .v-combobox.v-input--dirty .v-combobox__selection,
.pm-drawer-body .v-combobox.v-input--dirty .v-chip {
  color: rgb(var(--v-theme-on-surface));
}

.pm-drawer-body .v-select:not(.v-input--dirty) .v-field__input,
.pm-drawer-body .v-combobox:not(.v-input--dirty) .v-field__input {
  color: rgba(var(--v-theme-on-surface), 0.42);
}

.pm-drawer-body .v-field:focus,
.pm-drawer-body .v-field:focus-visible,
.pm-drawer-body .v-field__input:focus,
.pm-drawer-body .v-field__input:focus-visible,
.pm-drawer-body input:focus,
.pm-drawer-body input:focus-visible,
.pm-drawer-body textarea:focus,
.pm-drawer-body textarea:focus-visible {
  outline: none !important;
}

/* Dropdown-Pfeil (append-inner) und Clear-„X" (clearable) vertikal mittig:
   align-self überschreibt die obere Ausrichtung des Feld-Grids, align-items
   zentriert das Icon innerhalb der Box. */
.pm-drawer-body .v-field__append-inner,
.pm-drawer-body .v-field__clearable {
  min-height: 34px !important;
  height: 34px !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  padding-left: 4px !important;
  padding-right: 8px !important;
  align-self: center !important;
  display: flex !important;
  align-items: center !important;
}

.pm-drawer-body .v-textarea .v-field {
  height: auto !important;
  min-height: 84px !important;
}

.pm-drawer-body .v-textarea .v-field__input {
  min-height: 84px !important;
  padding: 8px 10px !important;
  align-items: flex-start;
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
    grid-template-columns: 260px 1fr;
  }

  .panel-right {
    grid-column: 1 / -1;
    height: min(68vh, 620px);
    border-top: 1px solid var(--pm-divider);
  }

  .details-drawer__inner {
    max-width: 640px;
  }

  .tag-focus-panel {
    min-height: 520px;
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

  .tag-focus-panel {
    min-height: 0;
    padding: 18px;
  }

  .tag-focus-panel__stats {
    grid-template-columns: 1fr;
  }

  .tag-focus-cloud {
    align-content: flex-start;
    justify-content: flex-start;
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
