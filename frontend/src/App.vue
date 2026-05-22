<template>
  <v-app class="papermind-app">
    <v-app-bar class="app-topbar" flat height="64">
      <v-app-bar-title class="app-title">
        <button type="button" class="app-title__brand app-title__brand-button" @click="openLibraryView">
          PaperMind
        </button>
      </v-app-bar-title>

      <template #append>
        <div class="appbar-actions">
          <v-menu location="bottom end" offset="8">
            <template #activator="{ props: importMenuProps }">
              <v-btn class="topbar-btn topbar-btn--import" variant="text" v-bind="importMenuProps">
                <v-icon size="18" class="mr-1">mdi-tray-arrow-up</v-icon>
                Importieren
              </v-btn>
            </template>
            <v-list density="compact" min-width="240">
              <v-list-item
                prepend-icon="mdi-file-upload-outline"
                title="PDF hochladen..."
                @click="openImportPdfPicker"
              />
              <v-list-item
                prepend-icon="mdi-cellphone"
                title="Dokument scannen..."
                @click="openImportPhoneScan"
              />
            </v-list>
          </v-menu>

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
      </template>
    </v-app-bar>

    <v-main class="app-main">
      <BaseDialog
        v-model="isSettingsDialogOpen"
        max-width="640"
        card-class="pm-settings-card"
        body-class="pm-settings-body"
        footer-class="pm-settings-footer"
        title="Einstellungen"
        header-subtitle="Globale Voreinstellungen für dein PaperMind."
        description=""
        variant="info"
        primary-text="Fertig"
        :show-secondary="false"
        @primary="isSettingsDialogOpen = false"
      >
        <div v-if="isSettingsLoading" class="settings-loading">
          <v-progress-circular indeterminate size="20" width="2" />
          <span>Einstellungen werden geladen...</span>
        </div>
        <template v-else>
          <div class="pm-settings-sections">
            <section class="pm-settings-section">
              <h3 class="pm-settings-title">Erscheinungsbild</h3>
              <div class="pm-settings-content">
                <div class="pm-setting-row pm-setting-row--column">
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Theme-Modus</div>
                    <div class="pm-setting-description">Hell, dunkel oder entsprechend Systemeinstellung.</div>
                  </div>
                  <div
                    class="settings-theme-segmented"
                    role="radiogroup"
                    aria-label="Theme-Modus auswählen"
                    @keydown.left.prevent="stepThemeMode(-1)"
                    @keydown.right.prevent="stepThemeMode(1)"
                  >
                    <button
                      v-for="option in themeModeOptions"
                      :key="`theme-${option.value}`"
                      type="button"
                      class="settings-theme-segmented__item"
                      :class="{ 'settings-theme-segmented__item--active': settingsDraft.ui.theme_mode === option.value }"
                      role="radio"
                      :aria-label="`Theme: ${option.label}`"
                      :aria-checked="settingsDraft.ui.theme_mode === option.value"
                      :disabled="isSettingSaving.theme_mode"
                      @click="onThemeModeChange(option.value)"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                </div>

                <div
                  class="pm-setting-row"
                  role="button"
                  tabindex="0"
                  @click="toggleShowFilenameSuffixFromRow"
                  @keydown.enter.prevent="toggleShowFilenameSuffixFromRow"
                  @keydown.space.prevent="toggleShowFilenameSuffixFromRow"
                >
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Dateiendung anzeigen</div>
                    <div class="pm-setting-description">Blendet .pdf in Listen und Details ein/aus.</div>
                  </div>
                  <v-switch
                    :model-value="settingsDraft.ui.showFilenameSuffix"
                    color="primary"
                    density="comfortable"
                    hide-details
                    inset
                    :loading="isSettingSaving.show_filename_suffix"
                    :disabled="isSettingSaving.show_filename_suffix"
                    @click.stop
                    @update:model-value="onShowFilenameSuffixChange"
                  />
                </div>
              </div>
            </section>

            <section class="pm-settings-section">
              <h3 class="pm-settings-title">Dokumente</h3>
              <div class="pm-settings-content">
                <div
                  class="pm-setting-row"
                  role="button"
                  tabindex="0"
                  @click="toggleAutoOcrFromRow"
                  @keydown.enter.prevent="toggleAutoOcrFromRow"
                  @keydown.space.prevent="toggleAutoOcrFromRow"
                >
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Automatisches OCR</div>
                    <div class="pm-setting-description">Beim Import wird Text automatisch extrahiert.</div>
                  </div>
                  <v-switch
                    :model-value="settingsDraft.documents.auto_ocr"
                    color="primary"
                    density="comfortable"
                    hide-details
                    inset
                    :loading="isSettingSaving.auto_ocr"
                    :disabled="isSettingSaving.auto_ocr"
                    @click.stop
                    @update:model-value="onAutoOcrChange"
                  />
                </div>

                <div
                  class="pm-setting-row"
                  role="button"
                  tabindex="0"
                  @click="toggleAutoTaggingFromRow"
                  @keydown.enter.prevent="toggleAutoTaggingFromRow"
                  @keydown.space.prevent="toggleAutoTaggingFromRow"
                >
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Automatisches Tagging (KI)</div>
                    <div class="pm-setting-description">Neue Dokumente werden automatisch verschlagwortet.</div>
                    <div v-if="settingsDraft.documents.auto_tagging" class="pm-setting-hint">
                      Kann je nach Modell/Hardware etwas dauern.
                    </div>
                  </div>
                  <v-switch
                    :model-value="settingsDraft.documents.auto_tagging"
                    color="primary"
                    density="comfortable"
                    hide-details
                    inset
                    :loading="isSettingSaving.auto_tagging"
                    :disabled="isSettingSaving.auto_tagging"
                    @click.stop
                    @update:model-value="onAutoTaggingChange"
                  />
                </div>

                <div class="pm-setting-row pm-setting-row--column">
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Sortierung</div>
                    <div class="pm-setting-description">Legt die Standardreihenfolge in der Dokumentliste fest.</div>
                  </div>
                  <v-select
                    :model-value="settingsDraft.documents.sort_order"
                    :items="sortOrderOptions"
                    item-title="label"
                    item-value="value"
                    density="comfortable"
                    hide-details
                    variant="outlined"
                    class="settings-theme-select pm-setting-select"
                    label="Sortierung"
                    :loading="isSettingSaving.sort_order"
                    :disabled="isSettingSaving.sort_order"
                    @update:model-value="onSortOrderChange"
                  />
                </div>

                <div class="pm-setting-row pm-setting-row--column">
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Zeitraum für „Zuletzt hinzugefügt“</div>
                    <div class="pm-setting-description">
                      Legt fest, wie lange Dokumente nach dem Import in „Zuletzt hinzugefügt“ erscheinen.
                    </div>
                  </div>
                  <v-select
                    :model-value="settingsDraft.documents.recent_import_window_hours"
                    :items="recentImportWindowOptions"
                    item-title="label"
                    item-value="value"
                    density="comfortable"
                    hide-details
                    variant="outlined"
                    class="settings-theme-select pm-setting-select"
                    label="Zeitraum"
                    :loading="isSettingSaving.recent_import_window_hours"
                    :disabled="isSettingSaving.recent_import_window_hours"
                    @update:model-value="onRecentImportWindowChange"
                  />
                </div>
              </div>
            </section>

            <section class="pm-settings-section">
              <h3 class="pm-settings-title">Vorschau</h3>
              <div class="pm-settings-content">
                <div
                  class="pm-setting-row"
                  role="button"
                  tabindex="0"
                  @click="toggleDrawerRememberStateFromRow"
                  @keydown.enter.prevent="toggleDrawerRememberStateFromRow"
                  @keydown.space.prevent="toggleDrawerRememberStateFromRow"
                >
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Dokumentdetails merken</div>
                    <div class="pm-setting-description">
                      Merkt sich, ob die Schublade zuletzt ein- oder ausgeklappt war.
                    </div>
                  </div>
                  <v-switch
                    :model-value="settingsDraft.ui.drawerRememberState"
                    color="primary"
                    density="comfortable"
                    hide-details
                    inset
                    :loading="isSettingSaving.drawer_remember_state"
                    :disabled="isSettingSaving.drawer_remember_state"
                    @click.stop
                    @update:model-value="onDrawerRememberStateChange"
                  />
                </div>

                <div
                  class="pm-setting-row"
                  role="button"
                  tabindex="0"
                  @click="toggleDrawerAlwaysExpandedFromRow"
                  @keydown.enter.prevent="toggleDrawerAlwaysExpandedFromRow"
                  @keydown.space.prevent="toggleDrawerAlwaysExpandedFromRow"
                >
                  <div class="pm-setting-content">
                    <div class="pm-setting-label">Dokumentdetails immer ausgeklappt</div>
                    <div class="pm-setting-description">Die Schublade bleibt dauerhaft geöffnet.</div>
                  </div>
                  <v-switch
                    :model-value="settingsDraft.ui.drawerAlwaysExpanded"
                    color="primary"
                    density="comfortable"
                    hide-details
                    inset
                    :loading="isSettingSaving.drawer_always_expanded"
                    :disabled="isSettingSaving.drawer_always_expanded"
                    @click.stop
                    @update:model-value="onDrawerAlwaysExpandedChange"
                  />
                </div>
              </div>
            </section>
          </div>
        </template>
      </BaseDialog>

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

      <BaseDialog
        v-model="isCreateTagDialogOpen"
        max-width="420"
        title="Tag erstellen"
        description="Neuen Tag für die Dokumentorganisation anlegen."
        primary-text="Erstellen"
        secondary-text="Abbrechen"
        :loading="isTagMutationRunning"
        @primary="submitCreateTag"
        @close="closeCreateTagDialog"
      >
        <v-text-field
          v-model="createTagName"
          label="Name"
          density="comfortable"
          variant="outlined"
          hide-details
          @keydown.enter.prevent="submitCreateTag"
        />
      </BaseDialog>

      <BaseDialog
        v-model="isRenameTagDialogOpen"
        max-width="420"
        title="Tag umbenennen"
        description="Bestehenden Tag-Namen aktualisieren."
        primary-text="Speichern"
        secondary-text="Abbrechen"
        :loading="isTagMutationRunning"
        @primary="submitRenameTag"
        @close="closeRenameTagDialog"
      >
        <v-text-field
          v-model="renameTagName"
          label="Neuer Name"
          density="comfortable"
          variant="outlined"
          hide-details
          @keydown.enter.prevent="submitRenameTag"
        />
      </BaseDialog>

      <BaseDialog
        v-model="isMergeTagDialogOpen"
        max-width="460"
        title="Tag zusammenführen"
        description="Verknüpfungen vom Quell-Tag auf einen Ziel-Tag verschieben."
        primary-text="Zusammenführen"
        secondary-text="Abbrechen"
        :loading="isTagMutationRunning"
        :primary-disabled="!mergeTargetTagId"
        @primary="submitMergeTag"
        @close="closeMergeTagDialog"
      >
        <div class="text-body-2 mb-3">
          Alle Verknüpfungen von
          <strong>{{ mergeSourceTag?.name }}</strong>
          werden auf den Ziel-Tag übertragen. Der Quell-Tag wird gelöscht.
        </div>
        <v-autocomplete
          v-model="mergeTargetTagId"
          :items="mergeTargetCandidates"
          item-title="name"
          item-value="id"
          :return-object="false"
          label="Ziel-Tag"
          density="comfortable"
          variant="outlined"
          hide-details
        />
      </BaseDialog>

      <BaseDialog
        v-model="isDeleteTagDialogOpen"
        max-width="420"
        variant="destructive"
        title="Tag löschen"
        description="Tag und seine Verknüpfungen entfernen."
        primary-text="Tag löschen"
        secondary-text="Abbrechen"
        :loading="isTagMutationRunning"
        @primary="submitDeleteTag"
        @close="closeDeleteTagDialog"
      >
        <p class="dialog-delete-copy">
          Tag <strong>„{{ deleteTagTarget?.name }}“</strong> wird gelöscht.
        </p>
      </BaseDialog>

      <DeleteDocumentDialog
        v-model="isDeleteDocumentDialogOpen"
        :document-name="formatDocumentTitle(deleteDocumentTarget)"
        @close="closeDeleteDocumentDialog"
        :loading="isDeletingDocument"
        @confirm="confirmDeleteDocumentFromDialog"
      />

      <BaseDialog
        v-model="isRenameDocumentDialogOpen"
        max-width="460"
        title="Dokument umbenennen"
        description="Anzeigenamen für die Liste und Details ändern."
        primary-text="Speichern"
        secondary-text="Abbrechen"
        :loading="isRenamingDocument"
        @primary="submitRenameDocument"
        @close="closeRenameDocumentDialog"
      >
        <v-text-field
          v-model="renameDocumentName"
          label="Name"
          density="comfortable"
          variant="outlined"
          hide-details
          @keydown.enter.prevent="submitRenameDocument"
        >
          <template #append-inner>
            <v-tooltip text="Titel mit KI vorschlagen" location="top">
              <template #activator="{ props: tooltipProps }">
                <v-btn
                  v-bind="tooltipProps"
                  icon="mdi-robot-outline"
                  variant="text"
                  size="small"
                  aria-label="Titel mit KI vorschlagen"
                  :loading="isSuggestingRenameDocumentTitle"
                  :disabled="isSuggestingRenameDocumentTitle || isRenamingDocument || !renameDocumentTarget?.id"
                  @click.stop="suggestRenameDocumentTitle"
                />
              </template>
            </v-tooltip>
          </template>
        </v-text-field>
      </BaseDialog>

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

      <BaseDialog
        v-model="isAiDialogOpen"
        max-width="1080"
        width="calc(100% - 48px)"
        body-class="app-modal__body--flush"
        title="KI-Chat"
        description="Fragen stellen und Quellen direkt öffnen."
        variant="info"
        primary-text="Fertig"
        :show-secondary="false"
        @primary="isAiDialogOpen = false"
      >
        <div class="ai-page">
          <section class="ai-suggestions">
            <div class="ai-section-title">Vorschlagsfragen</div>
            <div class="ai-suggestions__grid">
              <button
                v-for="suggestion in aiSuggestedQuestions"
                :key="`suggestion-${suggestion}`"
                type="button"
                class="ai-suggestion-card"
                @click="askAiSuggestion(suggestion)"
              >
                {{ suggestion }}
              </button>
            </div>
          </section>

          <section class="ai-chat-panel">
            <div ref="aiChatScrollRef" class="ai-chat-history">
              <template v-if="aiMessages.length > 0">
                <article
                  v-for="message in aiMessages"
                  :key="message.id"
                  class="ai-message"
                  :class="`ai-message--${message.role}`"
                >
                  <div class="ai-message__bubble">
                    <div class="ai-message__bubble-content">
                      <v-progress-circular
                        v-if="message.isStatus"
                        size="14"
                        width="2"
                        indeterminate
                        color="primary"
                      />
                      <span>{{ message.text }}</span>
                    </div>
                  </div>
                  <div
                    v-if="message.role === 'assistant' && !message.isStatus && message.citations.length > 0"
                    class="ai-sources"
                  >
                    <div class="ai-sources__divider" />
                    <div class="ai-sources__label">Quellen</div>
                    <article
                      v-for="citation in message.citations"
                      :key="`${message.id}-${citation.doc_id}`"
                      class="ai-citation-card"
                    >
                      <div class="ai-citation-card__left">
                        <v-icon size="16">mdi-file-document-outline</v-icon>
                      </div>
                      <div class="ai-citation-card__content">
                        <div class="ai-citation-card__title">{{ formatCitationTitle(citation) }}</div>
                        <div v-if="citationPageLabel(citation)" class="ai-citation-card__meta">
                          {{ citationPageLabel(citation) }}
                        </div>
                        <div v-if="citation.snippet" class="ai-citation-card__snippet">{{ citation.snippet }}</div>
                        <div v-if="citationHintText(citation)" class="ai-citation-card__hint">
                          {{ citationHintText(citation) }}
                        </div>
                      </div>
                      <div class="ai-citation-card__actions">
                        <v-btn size="x-small" variant="text" color="primary" @click="openCitation(citation)">
                          Öffnen
                        </v-btn>
                      </div>
                    </article>
                  </div>
                </article>
              </template>
              <div v-else class="ai-chat-empty">
                <v-icon size="44" class="ai-chat-empty__icon">mdi-robot-outline</v-icon>
                <div class="ai-chat-empty__title">Stelle eine Frage zu deinen Dokumenten</div>
                <div class="ai-chat-empty__subtitle">
                  Die Antwort basiert auf Retrieval über OCR-Texte und zeigt Quellenkarten.
                </div>
              </div>
            </div>

            <div class="ai-chat-input">
              <v-text-field
                v-model="aiQuestionInput"
                placeholder="Frage zu deinen Dokumenten stellen..."
                density="comfortable"
                variant="outlined"
                hide-details
                :disabled="isAiAsking"
                @keydown.enter.prevent="submitAiQuestion()"
              >
                <template #append-inner>
                  <v-btn
                    icon="mdi-send-outline"
                    size="small"
                    variant="text"
                    :loading="isAiAsking"
                    :disabled="!aiQuestionInput.trim() || isAiAsking"
                    @click="submitAiQuestion()"
                  />
                </template>
              </v-text-field>
            </div>
          </section>
        </div>

      </BaseDialog>

      <div class="workspace">
        <aside class="panel panel-left">
          <v-list nav density="compact" class="views-list">
            <div class="sidebar-section-header">
              <div class="sidebar-section-label">Bibliothek</div>
            </div>
            <div class="sidebar-section-content">
              <SidebarItem
                item-class="sidebar-item--primary"
                :active="isViewActive('all')"
                :count="allDocumentsSidebarCount"
                @click="selectView('all')"
              >
                <template #icon>
                  <v-icon size="18">{{ allDocumentsView.icon }}</v-icon>
                </template>
                {{ allDocumentsView.label }}
              </SidebarItem>

              <SidebarItem
                item-class="sidebar-item--secondary sidebar-item--imports"
                :active="isViewActive('imports')"
                :count="importsSidebarCount"
                @click="selectView('imports')"
              >
                <template #icon>
                  <v-icon size="18">{{ importsView.icon }}</v-icon>
                </template>
                {{ importsView.label }}
              </SidebarItem>

              <SidebarItem
                item-class="sidebar-item--secondary"
                :active="isViewActive('untagged')"
                :count="untaggedSidebarCount"
                @click="selectView('untagged')"
              >
                <template #icon>
                  <v-icon size="18">{{ untaggedView.icon }}</v-icon>
                </template>
                {{ untaggedView.label }}
              </SidebarItem>
            </div>
          </v-list>

          <v-divider class="sidebar-section-divider" />

          <v-list nav density="compact" class="views-list">
            <div class="sidebar-section-header">
              <div class="sidebar-section-label">Ordner</div>
              <button
                type="button"
                class="sidebar-section-toggle"
                :aria-expanded="String(isSidebarSectionVisible('folders'))"
                aria-label="Ordner ein- oder ausblenden"
                @click="toggleSidebarSection('folders')"
              >
                {{ sidebarSectionToggleLabel('folders') }}
              </button>
            </div>

            <transition name="sidebar-section-collapse">
              <div v-if="isSidebarSectionVisible('folders')" class="sidebar-section-content">
              <SidebarItem
                item-class="sidebar-item--secondary sidebar-item--folder-create"
                @click="openCreateSavedSearchDialog"
              >
                <template #icon>
                  <v-icon size="18">mdi-folder-plus-outline</v-icon>
                </template>
                Ordner erstellen
              </SidebarItem>

              <SidebarItem
                v-for="savedSearch in sortedFolderItems"
                :key="savedSearch.id"
                item-class="sidebar-item--secondary"
                :active="activeSavedSearchId === savedSearch.id"
                :count="savedSearchUsageCount(savedSearch.id)"
                action-mode="hover-active"
                @click="openSavedSearch(savedSearch.id)"
              >
                <template #icon>
                  <v-icon size="18">{{ folderSidebarIcon(savedSearch, activeSavedSearchId === savedSearch.id) }}</v-icon>
                </template>
                {{ savedSearch.name }}
                <template #action>
                  <v-menu location="bottom end">
                    <template #activator="{ props }">
                      <v-btn
                        class="sidebar-folder-menu-btn"
                        icon="mdi-dots-horizontal"
                        size="small"
                        density="comfortable"
                        variant="text"
                        v-bind="props"
                        aria-label="Ordner-Menü"
                        @click.stop
                      />
                    </template>
                    <v-list density="compact">
                      <v-list-item @click.stop="openEditSavedSearchDialog(savedSearch)">
                        <template #prepend>
                          <v-icon size="16">mdi-pencil-outline</v-icon>
                        </template>
                        <v-list-item-title>Bearbeiten</v-list-item-title>
                      </v-list-item>
                      <v-list-item class="menu-item--danger" @click.stop="deleteSavedSearch(savedSearch)">
                        <template #prepend>
                          <v-icon size="16">mdi-trash-can-outline</v-icon>
                        </template>
                        <v-list-item-title>Löschen…</v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-menu>
                </template>
              </SidebarItem>

              <v-list-item v-if="!isLoadingSavedSearches && sortedFolderItems.length === 0">
                <v-list-item-title class="text-caption">Noch keine Ordner</v-list-item-title>
              </v-list-item>
              </div>
            </transition>
          </v-list>

          <v-divider class="sidebar-section-divider" />

          <v-list nav density="compact" class="views-list">
            <div class="sidebar-section-header">
              <div class="sidebar-section-label">Tags</div>
              <button
                type="button"
                class="sidebar-section-toggle"
                :aria-expanded="String(isSidebarSectionVisible('tags'))"
                aria-label="Tags ein- oder ausblenden"
                @click="toggleSidebarSection('tags')"
              >
                {{ sidebarSectionToggleLabel('tags') }}
              </button>
            </div>

            <transition name="sidebar-section-collapse">
              <div v-if="isSidebarSectionVisible('tags')" class="sidebar-section-content">
              <SidebarItem :active="isTagView" :count="totalTagsSidebarCount" @click="openTagsView">
                <template #icon>
                  <v-icon size="18">mdi-tag-multiple-outline</v-icon>
                </template>
                Alle Tags
              </SidebarItem>

              <SidebarItem
                v-for="tag in topTagQuicklinks"
                :key="tag.id"
                item-class="sidebar-item--tag"
                :active="!isTagView && activeTagId === tag.id"
                :count="tagUsageCount(tag.id, tag.usage_count ?? 0)"
                @click="applyTagFilterFromSidebar(tag.id)"
              >
                <template #icon>
                  <v-icon size="18">mdi-tag-text-outline</v-icon>
                </template>
                <span class="sidebar-tag-pill">{{ tag.name }}</span>
              </SidebarItem>

              <v-list-item v-if="topTagQuicklinks.length === 0">
                <v-list-item-title class="text-caption">Noch keine Tags</v-list-item-title>
              </v-list-item>
              </div>
            </transition>
          </v-list>
        </aside>

        <section class="panel panel-middle">
          <template v-if="isTagView">
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
                  @keydown.enter.prevent="onTagToolbarEnter"
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
                      <v-list-item @click.stop="openRenameTagDialog(tag)">
                        <template #prepend>
                          <v-icon size="16">mdi-pencil-outline</v-icon>
                        </template>
                        <v-list-item-title>Umbenennen</v-list-item-title>
                      </v-list-item>
                      <v-list-item @click.stop="openMergeTagDialog(tag)">
                        <template #prepend>
                          <v-icon size="16">mdi-source-merge</v-icon>
                        </template>
                        <v-list-item-title>Zusammenführen</v-list-item-title>
                      </v-list-item>
                      <v-list-item class="menu-item--danger" @click.stop="openDeleteTagDialog(tag)">
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
          </template>

          <template v-else>
            <div
              class="document-list-shell docs-column"
            >
              <div class="docs-header">
                <div class="list-toolbar">
                  <div class="list-toolbar__main">
                    <v-text-field
                      ref="searchField"
                      v-model="searchText"
                      class="list-toolbar__search"
                      prepend-inner-icon="mdi-magnify"
                      clearable
                      clear-icon="mdi-close"
                      placeholder="Suchen (Dateiname, Notizen, OCR-Text)..."
                      density="comfortable"
                      variant="outlined"
                      :messages="searchHintMessages"
                      hide-details="auto"
                      @keydown.enter.prevent="triggerSearchNow"
                      @keydown.esc.prevent="handleSearchEscape"
                      @click:clear="clearSearchFromInput"
                    />
                  </div>
                  <div
                    v-if="listDropNotice"
                    class="list-toolbar__upload-hint"
                    :class="{ 'list-toolbar__upload-hint--warning': Boolean(listDropNotice) }"
                  >
                    {{ listDropNotice }}
                  </div>
                  <v-progress-linear v-if="isLoadingDocuments" indeterminate height="2" class="list-toolbar__loading" />
                </div>

                <div
                  v-if="activeStatusFilterLabel && !isImportsView"
                  class="active-filter-row"
                >
                  <v-chip size="small" variant="outlined">
                    Status: {{ activeStatusFilterLabel }}
                  </v-chip>
                </div>

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
                    <div class="document-list-empty-state">
                      <v-icon class="document-list-empty-state__icon" :icon="documentListEmptyState.icon" size="56" />
                      <div class="document-list-empty-state__title">{{ documentListEmptyState.title }}</div>
                      <div class="document-list-empty-state__subtitle">{{ documentListEmptyState.subtitle }}</div>
                    </div>
                  </div>

                  <div v-else class="document-list">
                    <div
                      v-for="document in documents"
                      :key="document.id"
                      class="document-row pm-doc-item"
                      :class="{ 'document-row--active': document.id === selectedDocumentId }"
                      role="button"
                      tabindex="0"
                      @click="selectDocument(document.id)"
                      @keydown.enter.prevent="selectDocument(document.id)"
                      @keydown.space.prevent="selectDocument(document.id)"
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
                            <v-list density="compact">
                              <v-list-item @click.stop="downloadDocumentFromList(document)">
                                <template #prepend>
                                  <v-icon size="16">mdi-download-outline</v-icon>
                                </template>
                                <v-list-item-title>Herunterladen</v-list-item-title>
                              </v-list-item>
                              <v-list-item @click.stop="openRenameDocumentDialog(document)">
                                <template #prepend>
                                  <v-icon size="16">mdi-pencil-outline</v-icon>
                                </template>
                                <v-list-item-title>Umbenennen</v-list-item-title>
                              </v-list-item>
                              <v-list-item @click.stop="openTagManagerFromList(document)">
                                <template #prepend>
                                  <v-icon size="16">mdi-tag-multiple-outline</v-icon>
                                </template>
                                <v-list-item-title>Tags verwalten</v-list-item-title>
                              </v-list-item>
                              <v-list-item class="menu-item--danger" @click.stop="openDeleteDocumentDialog(document)">
                                <template #prepend>
                                  <v-icon size="16">mdi-trash-can-outline</v-icon>
                                </template>
                                <v-list-item-title>Löschen…</v-list-item-title>
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
        </section>

        <section class="panel panel-right">
          <DocumentPreviewLayout
            class="panel-right__preview"
            :show-drawer="!isTagView && Boolean(selectedDocumentDetail)"
            :is-open="isDetailsDrawerOpen"
            :collapsed-height="DETAILS_DRAWER_COLLAPSED_HEIGHT"
          >
            <template #viewer>
              <div v-if="isTagView" class="preview-empty-state">
                <v-icon size="44" class="preview-empty-state__icon">mdi-tag-multiple-outline</v-icon>
                <div class="preview-empty-state__title">Tag-Ansicht aktiv</div>
                <div class="preview-empty-state__subtitle">
                  Wähle einen Tag, um die Dokumentliste zu filtern.
                </div>
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
                />
              </div>
              <div v-else class="preview-empty-state">
                <v-icon size="44" class="preview-empty-state__icon">mdi-file-document-outline</v-icon>
                <div class="preview-empty-state__title">Kein Dokument ausgewählt</div>
                <div class="preview-empty-state__subtitle">Wähle ein Dokument aus der Liste, um die Vorschau zu öffnen.</div>
              </div>
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
                        :icon="DRAWER_CHEVRON_ICON"
                        size="small"
                        density="comfortable"
                        variant="text"
                        class="details-chevron-btn"
                        :class="{ 'details-chevron-btn--expanded': isDetailsDrawerOpen }"
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
                      @keydown.enter.prevent="handleDocumentDateEnter"
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
                        @keydown.enter.stop.prevent="handleMetadataTagEnter"
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
import { useTheme } from 'vuetify';
import BaseDialog from './components/BaseDialog.vue';
import DeleteDocumentDialog from './components/DeleteDocumentDialog.vue';
import DocumentPreviewLayout from './components/DocumentPreviewLayout.vue';
import ImportStagingDialog from './components/ImportStagingDialog.vue';
import NotificationStack from './components/NotificationStack.vue';
import SidebarItem from './components/SidebarItem.vue';
import SmartFolderEditor from './components/SmartFolderEditor.vue';
import { mapApiError, useNotifications } from './stores/notifications';
import { useSettingsStore } from './stores/settings';
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

const PdfPreview = defineAsyncComponent(() => import('./components/PdfPreview.vue'));

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

const allDocumentsView = {
  key: 'all',
  label: 'Alle Dokumente',
  icon: 'mdi-book-open-page-variant-outline'
};
const importsView = {
  key: 'imports',
  label: 'Zuletzt hinzugefügt',
  icon: 'mdi-tray-arrow-down'
};
const untaggedView = {
  key: 'untagged',
  label: 'Ohne Tags',
  icon: 'mdi-tag-off-outline'
};
const themeModeOptions = [
  { label: 'Hell', value: 'light' },
  { label: 'Dunkel', value: 'dark' },
  { label: 'System', value: 'system' }
];
const sortOrderOptions = [
  { label: 'Neueste zuerst', value: 'newest' },
  { label: 'Älteste zuerst', value: 'oldest' },
  { label: 'Name A–Z', value: 'name_asc' },
  { label: 'Name Z–A', value: 'name_desc' },
  { label: 'Zuletzt geöffnet', value: 'last_opened' }
];
const recentImportWindowOptions = [
  { label: '1 Stunde', value: 1 },
  { label: '6 Stunden', value: 6 },
  { label: '12 Stunden', value: 12 },
  { label: '24 Stunden', value: 24 },
  { label: '48 Stunden', value: 48 }
];
const THEME_MODE_VALUES = new Set(['light', 'dark', 'system']);
const SETTINGS_SORT_ORDER_VALUES = new Set(['newest', 'oldest', 'name_asc', 'name_desc', 'last_opened']);
const RECENT_IMPORT_WINDOW_VALUES = new Set(recentImportWindowOptions.map((entry) => entry.value));
const SETTINGS_SORT_TO_QUERY = {
  newest: { sort: 'created_at', order: 'desc' },
  oldest: { sort: 'created_at', order: 'asc' },
  name_asc: { sort: 'name', order: 'asc' },
  name_desc: { sort: 'name', order: 'desc' },
  last_opened: { sort: 'updated_at', order: 'desc' }
};

const SEARCH_DEBOUNCE_MS = 300;
const SEARCHABLE_STATUSES = new Set(['imported', 'processing', 'ready', 'failed']);
const TAG_REPLACE_DEBOUNCE_MS = 300;
const METADATA_AUTOSAVE_DEBOUNCE_MS = 450;
const PREVIEW_RETRY_BASE_DELAY_MS = 600;
const PREVIEW_RETRY_MAX_DELAY_MS = 4500;
const PREVIEW_RETRY_MAX_ATTEMPTS = 5;
const IMPORTS_RECENT_LIMIT = 100;
const AI_DEFAULT_TOP_K = 3;
const AI_MAX_VISIBLE_CITATIONS = 3;
const AI_PHASE_MIN_MS = 300;
const DRAWER_CHEVRON_ICON = 'mdi-chevron-up';
const DETAILS_DRAWER_COLLAPSED_HEIGHT = 72;
const AI_SUGGESTED_QUESTIONS = [
  'Welche offenen Rechnungen gibt es im aktuellen Monat?',
  'Welche Dokumente enthalten Hinweise auf Kündigungsfristen?',
  'Fasse die wichtigsten Zahlungsbedingungen zusammen.',
  'Welche Verträge nennen eine automatische Verlängerung?',
  'Gibt es Dokumente mit Mahnung oder Zahlungsverzug?',
  'Welche Dokumente gehören thematisch zu KFZ-Kosten?'
];
const SIDEBAR_SECTION_VISIBILITY_STORAGE_KEY = 'pm.sidebar.section_visibility.v1';
const SIDEBAR_SECTION_DEFAULT_VISIBILITY = Object.freeze({
  folders: true,
  tags: true
});

const theme = useTheme();
const { notify } = useNotifications();
const settingsStore = useSettingsStore();
const appSettings = computed(() => settingsStore.settings);
const settingsDraft = settingsStore.settingsDraft;
const isSettingsLoading = computed(() => settingsStore.isSettingsLoading);
const isSettingSaving = settingsStore.isSettingSaving;
const showPdfSuffix = computed(() => settingsStore.settingsDraft.ui.showFilenameSuffix);

const searchText = ref('');
const searchField = ref(null);
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
const sidebarSectionVisibility = ref({ ...SIDEBAR_SECTION_DEFAULT_VISIBILITY });

function sanitizeSidebarSectionVisibility(rawValue) {
  const source = rawValue && typeof rawValue === 'object' ? rawValue : {};
  return {
    folders: typeof source.folders === 'boolean' ? source.folders : SIDEBAR_SECTION_DEFAULT_VISIBILITY.folders,
    tags: typeof source.tags === 'boolean' ? source.tags : SIDEBAR_SECTION_DEFAULT_VISIBILITY.tags
  };
}

function loadSidebarSectionVisibility() {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const raw = window.localStorage.getItem(SIDEBAR_SECTION_VISIBILITY_STORAGE_KEY);
    if (!raw) {
      return;
    }
    const parsed = JSON.parse(raw);
    sidebarSectionVisibility.value = sanitizeSidebarSectionVisibility(parsed);
  } catch {
    sidebarSectionVisibility.value = { ...SIDEBAR_SECTION_DEFAULT_VISIBILITY };
  }
}

function persistSidebarSectionVisibility() {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(
      SIDEBAR_SECTION_VISIBILITY_STORAGE_KEY,
      JSON.stringify(sidebarSectionVisibility.value)
    );
  } catch {
    // ignore storage errors to keep sidebar usable
  }
}

function isSidebarSectionVisible(sectionKey) {
  return Boolean(sidebarSectionVisibility.value?.[sectionKey]);
}

function sidebarSectionToggleLabel(sectionKey) {
  return isSidebarSectionVisible(sectionKey) ? 'Ausblenden' : 'Einblenden';
}

function toggleSidebarSection(sectionKey) {
  if (!(sectionKey in SIDEBAR_SECTION_DEFAULT_VISIBILITY)) {
    return;
  }
  sidebarSectionVisibility.value = {
    ...sidebarSectionVisibility.value,
    [sectionKey]: !isSidebarSectionVisible(sectionKey)
  };
  persistSidebarSectionVisibility();
}
const tagSearchField = ref(null);
const savedSearches = ref([]);
const isLoadingSavedSearches = ref(false);
const isLoadingSidebarCounts = ref(false);
const sidebarCounts = ref({
  all_documents: 0,
  untagged: 0,
  unread_total: 0,
  tags_total: 0,
  imports: {
    imported: 0,
    processing: 0,
    ready: 0,
    failed: 0,
    recent_total: 0
  },
  tags: {},
  smart_folders: {},
  saved_searches: {}
});
const isSavingSavedSearch = ref(false);
const isSmartFolderEditorOpen = ref(false);
const smartFolderEditorMode = ref('create');
const smartFolderEditorTarget = ref(null);

const isCreateTagDialogOpen = ref(false);
const createTagName = ref('');
const isRenameTagDialogOpen = ref(false);
const renameTagName = ref('');
const renameTargetTag = ref(null);
const isMergeTagDialogOpen = ref(false);
const mergeSourceTag = ref(null);
const mergeTargetTagId = ref(null);
const isDeleteTagDialogOpen = ref(false);
const deleteTagTarget = ref(null);
const isTagMutationRunning = ref(false);

const documents = ref([]);
const tags = ref([]);
const selectedDocumentId = ref(null);
const selectedDocumentDetail = ref(null);

const isLoadingDocuments = ref(false);
const previewTargetPage    = ref(null);
const previewHighlightText = ref('');

const aiSuggestedQuestions = AI_SUGGESTED_QUESTIONS;
const aiMessages = ref([]);
const aiQuestionInput = ref('');
const aiSessionId = ref('');
const isAiAsking = ref(false);
const aiChatScrollRef = ref(null);

const importStagingDialogRef = ref(null);
const importPdfInputRef = ref(null);
const isSettingsDialogOpen = ref(false);
const isUploadDialogOpen = ref(false);
const isListDragOver = ref(false);
const listDropDragDepth = ref(0);
const listDropNotice = ref('');
const previewReloadNonce = ref(0);

const isDetailsDrawerOpen = computed({
  get: () => settingsStore.drawerExpanded,
  set: (value) => {
    settingsStore.setDrawerExpanded(value);
  }
});
const isDrawerAlwaysExpanded = computed(() => appSettings.value.ui.drawerAlwaysExpanded);
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
const isRenameDocumentDialogOpen = ref(false);
const renameDocumentTarget = ref(null);
const renameDocumentName = ref('');
const isRenamingDocument = ref(false);
const isSuggestingRenameDocumentTitle = ref(false);

const thumbnailErrorMap = ref({});
const STATUS_POLL_INTERVAL_MS = 5000;

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
const isTagView = computed(() => activeView.value === 'tags');
const isImportsView = computed(() => activeView.value === 'imports');
const isUntaggedView = computed(() => activeView.value === 'untagged');
const tagNameCollator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });
const sortedTagsByName = computed(() => {
  return [...tags.value].sort((left, right) => {
    const leftName = normalizeTagInput(left?.name || '');
    const rightName = normalizeTagInput(right?.name || '');
    return tagNameCollator.compare(leftName, rightName);
  });
});
const allTagNames = computed(() => sortedTagsByName.value.map((tag) => tag.name));
const sidebarTagsByName = computed(() => {
  return sortedTagsByName.value.filter((tag) => tagUsageCount(tag.id, tag.usage_count ?? 0) > 0);
});
const topTagQuicklinks = computed(() => {
  return [...sidebarTagsByName.value]
    .sort((left, right) => {
      const leftCount = tagUsageCount(left.id, left.usage_count ?? 0);
      const rightCount = tagUsageCount(right.id, right.usage_count ?? 0);
      if (leftCount !== rightCount) {
        return rightCount - leftCount;
      }
      const leftName = normalizeTagInput(left?.name || '');
      const rightName = normalizeTagInput(right?.name || '');
      return tagNameCollator.compare(leftName, rightName);
    })
    .slice(0, 5);
});
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
function resolveFolderKind(folder) {
  const explicitKind = String(
    folder?.folder_type || folder?.kind || folder?.type || folder?.category || ''
  )
    .trim()
    .toLocaleLowerCase('de-DE');

  if (explicitKind) {
    if (['manual', 'folder', 'static'].includes(explicitKind)) {
      return 'manual';
    }
    if (['smart', 'smart_folder', 'smart-folder', 'intelligent', 'query'].includes(explicitKind)) {
      return 'smart';
    }
  }

  if (folder?.is_manual === true || folder?.isManual === true) {
    return 'manual';
  }
  if (folder?.is_smart === true || folder?.isSmart === true) {
    return 'smart';
  }
  if (folder?.query_json && typeof folder.query_json === 'object') {
    return 'smart';
  }
  return 'smart';
}

function isSmartFolderItem(folder) {
  return resolveFolderKind(folder) === 'smart';
}

function folderSidebarIcon(folder, isActive = false) {
  if (isSmartFolderItem(folder)) {
    return 'mdi-folder-search-outline';
  }
  return isActive ? 'mdi-folder' : 'mdi-folder-outline';
}

const sortedFolderItems = computed(() => {
  return [...savedSearches.value].sort((left, right) => {
    const leftSmartWeight = isSmartFolderItem(left) ? 1 : 0;
    const rightSmartWeight = isSmartFolderItem(right) ? 1 : 0;
    if (leftSmartWeight !== rightSmartWeight) {
      return leftSmartWeight - rightSmartWeight;
    }

    const leftName = normalizeTagInput(left?.name || '');
    const rightName = normalizeTagInput(right?.name || '');
    return tagNameCollator.compare(leftName, rightName);
  });
});
const allDocumentsSidebarCount = computed(() => Number(sidebarCounts.value.all_documents || 0));
const importsSidebarCount = computed(
  () => Number(sidebarCounts.value.imports?.recent_total || sidebarCounts.value.imports?.imported || 0)
);
const untaggedSidebarCount = computed(() => Number(sidebarCounts.value.untagged || 0));
const totalTagsSidebarCount = computed(() => {
  const tagsWithAssignments = Object.values(sidebarCounts.value.tags || {}).filter((value) => Number(value || 0) > 0).length;
  if (tagsWithAssignments > 0 || tags.value.length === 0) {
    return tagsWithAssignments;
  }
  return sidebarTagsByName.value.length;
});
const mergeTargetCandidates = computed(() => {
  if (!mergeSourceTag.value) {
    return [];
  }
  return sortedTagsByName.value.filter((tag) => tag.id !== mergeSourceTag.value.id);
});

const parsedSearch = computed(() => parseSearchText(searchText.value));
const searchHintMessages = computed(() =>
  parsedSearch.value.warning ? [parsedSearch.value.warning] : []
);
const showSnippets = computed(() => Boolean(parsedSearch.value.q));
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
    recentImports: isImportsView.value
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

let searchDebounceTimer = null;
let mediaQuery = null;
let statusPollTimer = null;
let tagReplaceDebounceTimer = null;
let metadataAutosaveDebounceTimer = null;
let previewRetryTimer = null;
let listDropNoticeTimer = null;
let sidebarCountsRefreshTimer = null;
let shouldSkipTagAutosave = false;
let shouldSkipMetadataAutosave = false;
let shouldRunMetadataAutosaveAfterSave = false;
let isApplyingSavedSearchQuery = false;
let shouldSkipTagNameSync = false;
const previewRetryAttemptsByDocument = ref({});

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') {
    return mode;
  }
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  return prefersDark ? 'dark' : 'light';
}

function applyThemeFromSettings() {
  theme.global.name.value = resolveThemeName(appSettings.value.ui.theme_mode);
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
      const message = mapApiError(error, 'Einstellungen konnten nicht geladen werden.');
      notify({ type: 'error', message });
    }
  }
}

async function patchSettingsWithRevert({ patch, controlKey, revert }) {
  try {
    const saved = await settingsStore.saveSettingPatch(apiBaseUrl, { patch, controlKey });
    if (!saved) {
      return false;
    }
    syncUiFromSettings();
    return true;
  } catch (error) {
    if (typeof revert === 'function') {
      revert();
    }
    notify({ type: 'error', message: 'Konnte Einstellung nicht speichern.' });
    return false;
  }
}

function stepThemeMode(step) {
  const ordered = themeModeOptions.map((entry) => entry.value);
  const currentIndex = ordered.indexOf(settingsDraft.ui.theme_mode);
  const safeIndex = currentIndex >= 0 ? currentIndex : 0;
  const nextIndex = (safeIndex + step + ordered.length) % ordered.length;
  void onThemeModeChange(ordered[nextIndex]);
}

async function onThemeModeChange(nextValue) {
  if (isSettingSaving.theme_mode) {
    return;
  }
  const nextMode = THEME_MODE_VALUES.has(String(nextValue)) ? String(nextValue) : 'system';
  if (nextMode === settingsDraft.ui.theme_mode) {
    return;
  }
  const previousMode = settingsDraft.ui.theme_mode;
  settingsStore.setDraftPatch({ ui: { theme_mode: nextMode } });
  theme.global.name.value = resolveThemeName(nextMode);
  await patchSettingsWithRevert({
    patch: buildThemeModePatch(nextMode),
    controlKey: 'theme_mode',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { theme_mode: previousMode } });
      applyThemeFromSettings();
    }
  });
}

async function onAutoOcrChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_ocr) {
    return;
  }
  const previous = settingsDraft.documents.auto_ocr;
  settingsStore.setDraftPatch({ documents: { auto_ocr: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoOcrPatch(nextBool),
    controlKey: 'auto_ocr',
    revert: () => {
      settingsStore.setDraftPatch({ documents: { auto_ocr: previous } });
    }
  });
}

function toggleAutoOcrFromRow() {
  if (isSettingSaving.auto_ocr) {
    return;
  }
  void onAutoOcrChange(!settingsDraft.documents.auto_ocr);
}

async function onAutoTaggingChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_tagging) {
    return;
  }
  const previous = settingsDraft.documents.auto_tagging;
  settingsStore.setDraftPatch({ documents: { auto_tagging: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoTaggingPatch(nextBool),
    controlKey: 'auto_tagging',
    revert: () => {
      settingsStore.setDraftPatch({ documents: { auto_tagging: previous } });
    }
  });
}

function toggleAutoTaggingFromRow() {
  if (isSettingSaving.auto_tagging) {
    return;
  }
  void onAutoTaggingChange(!settingsDraft.documents.auto_tagging);
}

async function onSortOrderChange(nextValue) {
  if (isSettingSaving.sort_order) {
    return;
  }
  const nextSortOrder = SETTINGS_SORT_ORDER_VALUES.has(String(nextValue))
    ? String(nextValue)
    : settingsDraft.documents.sort_order;
  if (nextSortOrder === settingsDraft.documents.sort_order) {
    return;
  }
  const previous = settingsDraft.documents.sort_order;
  settingsStore.setDraftPatch({ documents: { sort_order: nextSortOrder } });
  const saved = await patchSettingsWithRevert({
    patch: buildSortOrderPatch(nextSortOrder),
    controlKey: 'sort_order',
    revert: () => {
      settingsStore.setDraftPatch({ documents: { sort_order: previous } });
    }
  });
  if (!saved) {
    return;
  }
}

async function onRecentImportWindowChange(nextValue) {
  if (isSettingSaving.recent_import_window_hours) {
    return;
  }
  const parsedHours = Number(nextValue);
  const nextHours = RECENT_IMPORT_WINDOW_VALUES.has(parsedHours)
    ? parsedHours
    : settingsDraft.documents.recent_import_window_hours;
  if (nextHours === settingsDraft.documents.recent_import_window_hours) {
    return;
  }

  const previous = settingsDraft.documents.recent_import_window_hours;
  settingsStore.setDraftPatch({ documents: { recent_import_window_hours: nextHours } });
  const saved = await patchSettingsWithRevert({
    patch: buildRecentImportWindowPatch(nextHours),
    controlKey: 'recent_import_window_hours',
    revert: () => {
      settingsStore.setDraftPatch({ documents: { recent_import_window_hours: previous } });
    }
  });
  if (!saved) {
    return;
  }

  await fetchSidebarCounts();
  if (isImportsView.value && !activeSavedSearchId.value) {
    await fetchDocuments(selectedDocumentId.value);
  }
}

async function onShowFilenameSuffixChange(nextValue) {
  if (isSettingSaving.show_filename_suffix) {
    return;
  }
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.showFilenameSuffix) {
    return;
  }
  const previous = settingsDraft.ui.showFilenameSuffix;
  settingsStore.setDraftPatch({ ui: { showFilenameSuffix: nextBool } });
  await patchSettingsWithRevert({
    patch: buildShowFilenameSuffixPatch(nextBool),
    controlKey: 'show_filename_suffix',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { showFilenameSuffix: previous } });
    }
  });
}

function toggleShowFilenameSuffixFromRow() {
  if (isSettingSaving.show_filename_suffix) {
    return;
  }
  void onShowFilenameSuffixChange(!settingsDraft.ui.showFilenameSuffix);
}

async function onDrawerRememberStateChange(nextValue) {
  if (isSettingSaving.drawer_remember_state) {
    return;
  }
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.drawerRememberState) {
    return;
  }
  const previous = settingsDraft.ui.drawerRememberState;
  settingsStore.setDraftPatch({ ui: { drawerRememberState: nextBool } });
  const saved = await patchSettingsWithRevert({
    patch: buildDrawerRememberStatePatch(nextBool),
    controlKey: 'drawer_remember_state',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { drawerRememberState: previous } });
    }
  });
  if (!saved) {
    return;
  }
}

function toggleDrawerRememberStateFromRow() {
  if (isSettingSaving.drawer_remember_state) {
    return;
  }
  void onDrawerRememberStateChange(!settingsDraft.ui.drawerRememberState);
}

async function onDrawerAlwaysExpandedChange(nextValue) {
  if (isSettingSaving.drawer_always_expanded) {
    return;
  }
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.drawerAlwaysExpanded) {
    return;
  }
  const previous = settingsDraft.ui.drawerAlwaysExpanded;
  settingsStore.setDraftPatch({ ui: { drawerAlwaysExpanded: nextBool } });
  const saved = await patchSettingsWithRevert({
    patch: buildDrawerAlwaysExpandedPatch(nextBool),
    controlKey: 'drawer_always_expanded',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { drawerAlwaysExpanded: previous } });
    }
  });
  if (!saved) {
    return;
  }
}

function toggleDrawerAlwaysExpandedFromRow() {
  if (isSettingSaving.drawer_always_expanded) {
    return;
  }
  void onDrawerAlwaysExpandedChange(!settingsDraft.ui.drawerAlwaysExpanded);
}

async function openSettingsDialog() {
  isSettingsDialogOpen.value = true;
  await fetchAppSettings();
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

function formatCitationTitle(citation) {
  const formatted = formatDocumentFilename(citation?.document_title || '');
  return formatted || 'Dokument';
}

function createEmptySidebarCounts() {
  return {
    all_documents: 0,
    untagged: 0,
    unread_total: 0,
    tags_total: 0,
    imports: {
      imported: 0,
      processing: 0,
      ready: 0,
      failed: 0,
      recent_total: 0
    },
    tags: {},
    smart_folders: {},
    saved_searches: {}
  };
}

function normalizeSidebarCounts(payload) {
  const fallback = createEmptySidebarCounts();
  const normalizedImports = payload?.imports && typeof payload.imports === 'object'
    ? payload.imports
    : {};
  const normalizedTags = payload?.tags && typeof payload.tags === 'object' ? payload.tags : {};
  const normalizedSmartFolders =
    payload?.smart_folders && typeof payload.smart_folders === 'object' ? payload.smart_folders : {};
  const normalizedSavedSearches =
    payload?.saved_searches && typeof payload.saved_searches === 'object' ? payload.saved_searches : {};

  return {
    all_documents: Number(payload?.all_documents || 0),
    untagged: Number(payload?.untagged || 0),
    unread_total: Number(payload?.unread_total || 0),
    tags_total: Number(payload?.tags_total || 0),
    imports: {
      imported: Number(normalizedImports.imported || 0),
      processing: Number(normalizedImports.processing || 0),
      ready: Number(normalizedImports.ready || 0),
      failed: Number(normalizedImports.failed || 0),
      recent_total: Number(normalizedImports.recent_total || 0)
    },
    tags: Object.fromEntries(
      Object.entries(normalizedTags).map(([key, value]) => [key, Number(value || 0)])
    ),
    smart_folders: Object.fromEntries(
      Object.entries(normalizedSmartFolders).map(([key, value]) => [key, Number(value || 0)])
    ),
    saved_searches: Object.fromEntries(
      Object.entries(normalizedSavedSearches).map(([key, value]) => [key, Number(value || 0)])
    )
  } || fallback;
}

function tagUsageCount(tagId, fallbackValue = 0) {
  if (!tagId) {
    return Number(fallbackValue || 0);
  }
  return Number(sidebarCounts.value.tags?.[tagId] ?? fallbackValue ?? 0);
}

function savedSearchUsageCount(savedSearchId) {
  if (!savedSearchId) {
    return 0;
  }
  const smartFolderCount = Number(sidebarCounts.value.smart_folders?.[savedSearchId] || 0);
  if (smartFolderCount > 0) {
    return smartFolderCount;
  }
  return Number(sidebarCounts.value.saved_searches?.[savedSearchId] || 0);
}

async function fetchSidebarCounts() {
  isLoadingSidebarCounts.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/sidebar/counts`);
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    const payload = await response.json();
    sidebarCounts.value = normalizeSidebarCounts(payload);
  } catch (error) {
    console.warn('sidebar counts could not be loaded', error);
  } finally {
    isLoadingSidebarCounts.value = false;
  }
}

function scheduleSidebarCountsRefresh(delay = 240) {
  if (sidebarCountsRefreshTimer) {
    window.clearTimeout(sidebarCountsRefreshTimer);
  }
  sidebarCountsRefreshTimer = window.setTimeout(() => {
    sidebarCountsRefreshTimer = null;
    void fetchSidebarCounts();
  }, delay);
}

function statusChipLabel(status) {
  switch (status) {
    case 'ready':
      return 'Ready';
    case 'processing':
      return 'Processing';
    case 'failed':
      return 'Failed';
    case 'imported':
      return 'Imported';
    default:
      return status;
  }
}

function makeUiId(prefix) {
  if (window.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createAiSessionId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  const randomHex = () => Math.floor(Math.random() * 0x10000).toString(16).padStart(4, '0');
  return `${randomHex()}${randomHex()}-${randomHex()}-4${randomHex().slice(1)}-a${randomHex().slice(1)}-${randomHex()}${randomHex()}${randomHex()}`;
}

function ensureAiSessionId() {
  if (!aiSessionId.value) {
    aiSessionId.value = createAiSessionId();
  }
  return aiSessionId.value;
}

function sleepMs(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function ensureMinPhaseDuration(startTs, minDurationMs = AI_PHASE_MIN_MS) {
  const elapsed = Date.now() - Number(startTs || 0);
  if (elapsed < minDurationMs) {
    await sleepMs(minDurationMs - elapsed);
  }
}

function openLibraryView() {
  isAiDialogOpen.value = false;
}

function openAiView() {
  ensureAiSessionId();
  isAiDialogOpen.value = true;
}

function pushAiMessage(payload) {
  const message = {
    id: payload.id || makeUiId('ai-msg'),
      role: payload.role,
      text: payload.text,
      isStatus: Boolean(payload.isStatus),
      citations: Array.isArray(payload.citations) ? payload.citations : []
    };
  aiMessages.value.push(message);
  nextTick(() => {
    const container = aiChatScrollRef.value;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });
  return message.id;
}

function updateAiMessage(messageId, patch) {
  const index = aiMessages.value.findIndex((message) => message.id === messageId);
  if (index < 0) {
    return;
  }
  aiMessages.value[index] = {
    ...aiMessages.value[index],
    ...patch
  };
}

function removeAiMessage(messageId) {
  const index = aiMessages.value.findIndex((message) => message.id === messageId);
  if (index < 0) {
    return;
  }
  aiMessages.value.splice(index, 1);
}

function citationPageLabel(citation) {
  const from = Number(citation?.page_from || 0);
  const to = Number(citation?.page_to || 0);
  if (from > 0 && to > 0) {
    if (from === to) {
      return `Seite ${from}`;
    }
    return `Seite ${from}-${to}`;
  }
  if (from > 0) {
    return `Seite ${from}`;
  }
  if (to > 0) {
    return `Seite ${to}`;
  }
  return '';
}

function citationHintText(citation) {
  const snippet = String(citation?.snippet || '').trim().toLowerCase();
  if (snippet === 'bankdaten nicht gefunden') {
    return 'Prüfe Bankdaten im Dokument (Fußzeile).';
  }
  return '';
}

async function askAiSuggestion(question) {
  aiQuestionInput.value = String(question || '').trim();
  await submitAiQuestion();
}

async function submitAiQuestion() {
  const question = String(aiQuestionInput.value || '').trim();
  if (!question || isAiAsking.value) {
    return;
  }

  const sessionId = ensureAiSessionId();
  pushAiMessage({ role: 'user', text: question });
  aiQuestionInput.value = '';
  isAiAsking.value = true;
  const statusMessageId = pushAiMessage({
    role: 'assistant',
    text: 'Suche relevante Stellen…',
    isStatus: true,
    citations: []
  });
  const phaseOneStartedAt = Date.now();

  try {
    const response = await fetch(`${apiBaseUrl}/api/ai/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        question,
        top_k: AI_DEFAULT_TOP_K
      })
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    await ensureMinPhaseDuration(phaseOneStartedAt);
    updateAiMessage(statusMessageId, { text: 'Formuliere Antwort…' });
    const phaseTwoStartedAt = Date.now();

    const payload = await response.json();
    if (payload?.meta?.session_id && !aiSessionId.value) {
      aiSessionId.value = String(payload.meta.session_id);
    }

    await ensureMinPhaseDuration(phaseTwoStartedAt);
    updateAiMessage(statusMessageId, {
      isStatus: false,
      text: String(payload?.answer || 'Keine Antwort verfügbar.'),
      citations: Array.isArray(payload?.citations) ? payload.citations.slice(0, AI_MAX_VISIBLE_CITATIONS) : []
    });
  } catch (error) {
    removeAiMessage(statusMessageId);
    const message = mapApiError(error, 'KI-Anfrage fehlgeschlagen.');
    notify({ type: 'error', title: 'KI', message });
  } finally {
    isAiAsking.value = false;
  }
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
    const message = mapApiError(error, 'Quelle konnte nicht geöffnet werden.');
    notify({ type: 'error', title: 'KI', message });
  }
}

function formatDate(value) {
  if (!value) {
    return '-';
  }
  const normalized = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    const [year, month, day] = normalized.split('-').map((part) => Number(part));
    return new Intl.DateTimeFormat('de-DE').format(new Date(year, month - 1, day));
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return '-';
  }
  return new Intl.DateTimeFormat('de-DE').format(parsed);
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '-';
  }
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(parsed);
}

function formatDocumentDateInputFromIso(value) {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '';
  }
  const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return '';
  }
  return `${match[3]}.${match[2]}.${match[1]}`;
}

function parseDocumentDateInput(rawValue) {
  const normalized = String(rawValue || '').trim();
  if (!normalized) {
    return { ok: true, iso: null, display: '' };
  }

  const match = normalized.match(/^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$/);
  if (!match) {
    return { ok: false, iso: null, display: normalized };
  }

  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const dateValue = new Date(year, month - 1, day);
  if (
    Number.isNaN(dateValue.getTime()) ||
    dateValue.getFullYear() !== year ||
    dateValue.getMonth() !== month - 1 ||
    dateValue.getDate() !== day
  ) {
    return { ok: false, iso: null, display: normalized };
  }

  const dd = String(day).padStart(2, '0');
  const mm = String(month).padStart(2, '0');
  return {
    ok: true,
    iso: `${year}-${mm}-${dd}`,
    display: `${dd}.${mm}.${year}`
  };
}

function displayListDate(document) {
  if (document.document_date) {
    return `Dokumentdatum: ${formatDate(document.document_date)}`;
  }
  return 'Dokumentdatum: —';
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

function thumbnailUrl(documentId) {
  return `${apiBaseUrl}/api/documents/${documentId}/thumbnail`;
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

function hasThumbnailError(documentId) {
  return Boolean(thumbnailErrorMap.value[documentId]);
}

function onThumbnailError(documentId) {
  thumbnailErrorMap.value = {
    ...thumbnailErrorMap.value,
    [documentId]: true
  };
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

async function markDocumentViewedOptimistic(documentId) {
  if (!documentId) {
    return;
  }

  const listDocument = documents.value.find((item) => item.id === documentId);
  const detailDocument = selectedDocumentDetail.value?.id === documentId ? selectedDocumentDetail.value : null;
  const wasUnread = Boolean(listDocument?.is_unread ?? detailDocument?.is_unread);
  if (!wasUnread) {
    return;
  }

  setDocumentUnreadState(documentId, false);
  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${documentId}/mark-viewed`, {
      method: 'POST'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
  } catch (error) {
    setDocumentUnreadState(documentId, true);
    console.warn('mark viewed failed', error);
  }
}

function isValidIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function parseSearchText(rawSearch) {
  const normalized = (rawSearch || '').trim();
  if (!normalized) {
    return { q: '', status: '', dateFrom: '', dateTo: '', warning: '' };
  }

  const freeTerms = [];
  const warnings = [];
  let statusFilter = '';
  let dateFrom = '';
  let dateTo = '';

  for (const rawToken of normalized.split(/\s+/)) {
    const token = rawToken.trim();
    const lowerToken = token.toLowerCase();

    if (lowerToken.startsWith('status:')) {
      const statusValue = lowerToken.slice('status:'.length);
      if (SEARCHABLE_STATUSES.has(statusValue)) {
        statusFilter = statusValue;
      } else {
        warnings.push('Ungültiger status: Filter. Er wird als Freitext behandelt.');
        freeTerms.push(token);
      }
      continue;
    }

    if (lowerToken.startsWith('date:')) {
      const rangeValue = token.slice('date:'.length);
      const [fromDate, toDate, extraPart] = rangeValue.split('..');
      const isValidRange =
        !extraPart &&
        isValidIsoDate(fromDate || '') &&
        isValidIsoDate(toDate || '') &&
        fromDate <= toDate;

      if (isValidRange) {
        dateFrom = fromDate;
        dateTo = toDate;
      } else {
        warnings.push('Ungültiger date: Bereich. Er wird als Freitext behandelt.');
        freeTerms.push(token);
      }
      continue;
    }

    freeTerms.push(token);
  }

  return {
    q: freeTerms.join(' ').trim(),
    status: statusFilter,
    dateFrom,
    dateTo,
    warning: warnings[0] || ''
  };
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

function statusFromView(viewKey) {
  return null;
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

function syncSearchStateToQuery(options = {}) {
  const parsed = parsedSearch.value;
  const resolvedStatus = activeView.value === 'imports' ? null : parsed.status || statusFromView(activeView.value);
  return patchDocumentListQuery(
    {
      q: parsed.q || null,
      status: resolvedStatus,
      dateFrom: parsed.dateFrom || null,
      dateTo: parsed.dateTo || null
    },
    options
  );
}

function isViewActive(viewKey) {
  if (viewKey === 'all') {
    return (
      !isTagView.value &&
      !activeSavedSearchId.value &&
      activeView.value === 'all' &&
      !documentListQuery.tagId &&
      !documentListQuery.untagged
    );
  }
  if (viewKey === 'imports') {
    return !isTagView.value && !activeSavedSearchId.value && activeView.value === 'imports';
  }
  if (viewKey === 'untagged') {
    return !isTagView.value && !activeSavedSearchId.value && activeView.value === 'untagged';
  }
  return activeView.value === viewKey;
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
    } catch {
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
    metadataTagErrorMessage.value = mapApiError(error, 'Tags konnten nicht gespeichert werden.');
    notify({ type: 'error', message: metadataTagErrorMessage.value });
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
    } catch {
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
    metadataTagErrorMessage.value = mapApiError(error, 'KI-Tagging konnte nicht ausgeführt werden.');
    notify({ type: 'error', message: metadataTagErrorMessage.value });
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
    } catch {
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
    notify({ type: 'error', message: mapApiError(error, 'OCR konnte nicht gestartet werden.') });
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
  if (event.key !== 'Escape') {
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
  params.set('sort', documentListQuery.sort);
  params.set('order', documentListQuery.order);

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

  return params.toString();
}

function mapDocumentSortToSmartFolderSort() {
  if (documentListQuery.sort === 'name' && documentListQuery.order === 'asc') {
    return 'title_asc';
  }
  if (
    (documentListQuery.sort === 'doc_date' || documentListQuery.sort === 'document_date') &&
    documentListQuery.order === 'desc'
  ) {
    return 'doc_date_desc';
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

async function parseResponseError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
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
  isLoadingSavedSearches.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/smart-folders`);
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const payload = await response.json();
    savedSearches.value = Array.isArray(payload?.items) ? payload.items : [];

    if (
      activeSavedSearchId.value &&
      !savedSearches.value.some((savedSearch) => savedSearch.id === activeSavedSearchId.value)
    ) {
      leaveActiveSavedSearch();
      void fetchDocuments(selectedDocumentId.value);
    }
  } catch (error) {
    const message = mapApiError(error, 'Ordner konnten nicht geladen werden.');
    notify({ type: 'error', message });
  } finally {
    isLoadingSavedSearches.value = false;
  }
}

async function fetchSavedSearchDetail(savedSearchId) {
  const response = await fetch(`${apiBaseUrl}/api/smart-folders/${savedSearchId}`);
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }
  return await response.json();
}

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
    const message = mapApiError(error, 'Ordner konnte nicht geladen werden.');
    notify({ type: 'error', message });
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
    const message = mapApiError(error, 'Ordner konnte nicht gespeichert werden.');
    notify({ type: 'error', message });
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
    const message = mapApiError(error, 'Ordner konnte nicht gelöscht werden.');
    notify({ type: 'error', message });
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
    const message = mapApiError(error, 'Ordner konnte nicht geöffnet werden.');
    notify({ type: 'error', message });
    isApplyingSavedSearchQuery = false;
  }
}

async function fetchTags() {
  try {
    const response = await fetch(`${apiBaseUrl}/api/tags?include_count=true`);
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const payload = await response.json();
    tags.value = payload.items || [];
    ensureActiveTagFilterIsValid();
  } catch (error) {
    console.error(error);
  }
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

  const detail = await response.json();
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

    const payload = await response.json();
    documents.value = payload.items || [];

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
        resolvedSelectionId = autoSelectFirst ? documents.value[0].id : null;
      }
    }

    selectedDocumentId.value = resolvedSelectionId;
    if (!resolvedSelectionId) {
      selectedDocumentDetail.value = null;
      return;
    }

    await fetchDocumentDetail(resolvedSelectionId);
    void markDocumentViewedOptimistic(resolvedSelectionId);
  } catch (error) {
    const message = mapApiError(error, 'Dokumente konnten nicht geladen werden.');
    notify({ type: 'error', message });
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
    previewHighlightText.value = '';
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
    metadataErrorMessage.value = mapApiError(error, 'Dokumentdetails konnten nicht geladen werden.');
    notify({ type: 'error', message: metadataErrorMessage.value });
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
      metadataErrorMessage.value = mapApiError(error, 'Dokumentdetails konnten nicht geladen werden.');
      notify({ type: 'error', message: metadataErrorMessage.value });
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
}

function openRenameDocumentDialog(document) {
  if (!document?.id) {
    return;
  }
  renameDocumentTarget.value = {
    id: document.id,
    original_filename: document.original_filename,
    display_name: document.display_name || null
  };
  renameDocumentName.value = stripPdfSuffix(getDocumentTitle(document));
  isRenameDocumentDialogOpen.value = true;
}

function closeRenameDocumentDialog(force = false) {
  if (isRenamingDocument.value && !force) {
    return;
  }
  isRenameDocumentDialogOpen.value = false;
  renameDocumentTarget.value = null;
  renameDocumentName.value = '';
  isSuggestingRenameDocumentTitle.value = false;
}

function normalizeAiTitleSuggestion(rawValue) {
  const lines = String(rawValue || '')
    .split('\n')
    .map((line) => normalizeTagInput(line))
    .filter(Boolean);
  if (lines.length <= 0) {
    return '';
  }
  let candidate = lines[0];
  candidate = candidate.replace(/^titel\s*[:\-]\s*/i, '');
  candidate = candidate.replace(/^[\-\*\u2022\d\.\)\(\s]+/, '');
  candidate = candidate.replace(/^[`"'„“‚‘]+/, '').replace(/[`"'„“‚‘]+$/, '');
  candidate = stripPdfSuffix(normalizeTagInput(candidate));
  if (candidate.length > 200) {
    candidate = candidate.slice(0, 200).trim();
  }
  return candidate;
}

async function suggestRenameDocumentTitle() {
  const target = renameDocumentTarget.value;
  if (!target?.id || isSuggestingRenameDocumentTitle.value || isRenamingDocument.value) {
    return;
  }

  isSuggestingRenameDocumentTitle.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/ai/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'Schlage einen kurzen, präzisen deutschen Dokumenttitel vor. Antworte nur mit dem Titel ohne Zusatztext.',
        doc_id: target.id,
        request_type: 'summary',
        top_k: 8
      })
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }
    const payload = await response.json();
    const suggestion = normalizeAiTitleSuggestion(payload?.answer);
    if (!suggestion) {
      notify({ type: 'warning', title: 'KI', message: 'Kein brauchbarer Titelvorschlag gefunden.' });
      return;
    }
    renameDocumentName.value = suggestion;
    notify({ type: 'success', title: 'KI', message: 'Titelvorschlag übernommen.' });
  } catch (error) {
    notify({ type: 'error', title: 'KI', message: mapApiError(error, 'Titelvorschlag fehlgeschlagen.') });
  } finally {
    isSuggestingRenameDocumentTitle.value = false;
  }
}

async function submitRenameDocument() {
  const target = renameDocumentTarget.value;
  if (!target?.id || isRenamingDocument.value || isSuggestingRenameDocumentTitle.value) {
    return;
  }

  const nextName = normalizeTagInput(renameDocumentName.value);
  if (!nextName) {
    notify({ type: 'warning', message: 'Name darf nicht leer sein.' });
    return;
  }

  isRenamingDocument.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${target.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: nextName })
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const updated = await response.json();
    documents.value = documents.value.map((document) => (
      document.id === updated.id ? { ...document, ...updated } : document
    ));
    if (selectedDocumentId.value === updated.id) {
      selectedDocumentDetail.value = updated;
      applyMetadataFromDetail(updated);
    }
    closeRenameDocumentDialog(true);
    notify({ type: 'success', title: 'Dokument', message: 'Name gespeichert.' });
  } catch (error) {
    const message = mapApiError(error, 'Dokument konnte nicht umbenannt werden.');
    notify({ type: 'error', message });
  } finally {
    isRenamingDocument.value = false;
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

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/${targetDocumentId}`, {
      method: 'DELETE'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    isDeleteDocumentDialogOpen.value = false;
    deleteDocumentTarget.value = null;

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
    notify({ type: 'success', title: 'Dokument', message: 'Dokument gelöscht.' });
  } catch (error) {
    const message = mapApiError(error, 'Dokument konnte nicht gelöscht werden.');
    notify({ type: 'error', message });
  } finally {
    isDeletingDocument.value = false;
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
  selectTagFilter(tagId);
  syncSearchStateToQuery({ resetOffset: false });
}

function openTagDocuments(tagId) {
  clearTagFeedbackMessages();
  activeView.value = 'all';
  leaveActiveSavedSearch();
  selectTagFilter(tagId);
  syncSearchStateToQuery({ resetOffset: false });
}

function triggerSearchNow() {
  syncSearchStateToQuery();
  if (searchDebounceTimer) {
    window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }
  void fetchDocuments(selectedDocumentId.value);
}

function focusSearchFieldInput() {
  const inputEl = searchField.value?.$el?.querySelector('input');
  inputEl?.focus?.();
}

function clearSearchFromInput() {
  searchText.value = '';
  triggerSearchNow();
  nextTick(() => {
    focusSearchFieldInput();
  });
}

function handleSearchEscape() {
  if (!searchText.value) {
    return;
  }
  clearSearchFromInput();
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

function openCreateTagDialog() {
  clearTagFeedbackMessages();
  createTagName.value = '';
  isCreateTagDialogOpen.value = true;
}

function closeCreateTagDialog() {
  isCreateTagDialogOpen.value = false;
  createTagName.value = '';
}

function clearTagToolbarQuery() {
  tagSearchText.value = '';
}

function onTagToolbarEnter() {
  if (!canCreateTagFromToolbar.value || isTagMutationRunning.value) {
    return;
  }
  void createTagFromToolbar();
}

async function createTagByName(rawName) {
  const name = normalizeTagInput(rawName);
  if (!name) {
    return { ok: false, reason: 'empty', name: '' };
  }

  if (findTagByName(name)) {
    return { ok: false, reason: 'exists', name };
  }

  const response = await fetch(`${apiBaseUrl}/api/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  if (!response.ok) {
    throw new Error(await parseResponseError(response));
  }

  await fetchTags();
  scheduleSidebarCountsRefresh();
  return { ok: true, reason: 'created', name };
}

async function createTagFromToolbar() {
  if (!canCreateTagFromToolbar.value || isTagMutationRunning.value) {
    return;
  }

  isTagMutationRunning.value = true;
  try {
    const result = await createTagByName(tagSearchText.value);
    if (!result.ok) {
      return;
    }
    notify({ type: 'success', title: 'Tag', message: `Tag "${result.name}" erstellt.` });
    clearTagToolbarQuery();
    await nextTick();
    tagSearchField.value?.focus?.();
  } catch (error) {
    const message = mapApiError(error, 'Tag konnte nicht erstellt werden.');
    notify({ type: 'error', message });
  } finally {
    isTagMutationRunning.value = false;
  }
}

async function ensureTagIdByName(typedName) {
  const normalized = normalizeTagInput(typedName);
  if (!normalized) {
    return '';
  }

  const existingId = findTagByName(normalized)?.id || '';
  if (existingId) {
    return existingId;
  }

  isSavingTags.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: normalized })
    });

    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    const createdTag = await response.json();
    await fetchTags();
    scheduleSidebarCountsRefresh();
    return createdTag?.id || findTagByName(normalized)?.id || '';
  } catch (error) {
    metadataTagErrorMessage.value =
      error instanceof Error ? error.message : 'Tag konnte nicht erstellt werden.';
    notify({ type: 'error', message: metadataTagErrorMessage.value });
    return '';
  } finally {
    isSavingTags.value = false;
  }
}

async function syncMetadataTagsFromNames(nextNames) {
  if (!selectedDocumentDetail.value) {
    return;
  }

  const normalizedNames = normalizeTagNames(nextNames);
  metadataTagErrorMessage.value = '';

  const resolvedTagIds = [];
  for (const name of normalizedNames) {
    let tagId = findTagByName(name)?.id || '';
    if (!tagId) {
      tagId = await ensureTagIdByName(name);
    }
    if (!tagId) {
      continue;
    }
    resolvedTagIds.push(tagId);
  }

  const canonicalIds = normalizeTagIds(resolvedTagIds);
  const canonicalNames = canonicalIds.map((tagId) => tags.value.find((tag) => tag.id === tagId)?.name || tagId);
  const sanitizedNames = normalizeTagNames(canonicalNames);

  shouldSkipTagNameSync = true;
  metadataTagNames.value = sanitizedNames;
  window.setTimeout(() => {
    shouldSkipTagNameSync = false;
  }, 0);

  metadataTagIds.value = canonicalIds;
}

async function onMetadataTagNamesChange(nextValues) {
  if (shouldSkipTagNameSync || !selectedDocumentDetail.value) {
    return;
  }
  await syncMetadataTagsFromNames(nextValues);
}

async function handleMetadataTagEnter() {
  if (!selectedDocumentDetail.value) {
    return;
  }

  const normalizedNames = normalizeTagNames([...metadataTagNames.value, metadataTagSearch.value]);
  if (!normalizedNames.length) {
    return;
  }
  await syncMetadataTagsFromNames(normalizedNames);
  metadataTagSearch.value = '';
}

function openRenameTagDialog(tag) {
  clearTagFeedbackMessages();
  renameTargetTag.value = tag;
  renameTagName.value = tag?.name || '';
  isRenameTagDialogOpen.value = true;
}

function closeRenameTagDialog() {
  isRenameTagDialogOpen.value = false;
  renameTagName.value = '';
  renameTargetTag.value = null;
}

function openMergeTagDialog(tag) {
  clearTagFeedbackMessages();
  mergeSourceTag.value = tag;
  mergeTargetTagId.value = null;
  isMergeTagDialogOpen.value = true;
}

function closeMergeTagDialog() {
  isMergeTagDialogOpen.value = false;
  mergeSourceTag.value = null;
  mergeTargetTagId.value = null;
}

function openDeleteTagDialog(tag) {
  clearTagFeedbackMessages();
  deleteTagTarget.value = tag;
  isDeleteTagDialogOpen.value = true;
}

function closeDeleteTagDialog() {
  isDeleteTagDialogOpen.value = false;
  deleteTagTarget.value = null;
}

async function submitCreateTag() {
  if (!normalizeTagInput(createTagName.value)) {
    const message = 'Tag-Name darf nicht leer sein.';
    notify({ type: 'warning', message });
    return;
  }

  isTagMutationRunning.value = true;
  try {
    const result = await createTagByName(createTagName.value);
    if (!result.ok) {
      if (result.reason === 'exists') {
        notify({ type: 'warning', message: `Tag "${result.name}" existiert bereits.` });
      }
      return;
    }

    notify({ type: 'success', title: 'Tag', message: `Tag "${result.name}" erstellt.` });
    closeCreateTagDialog();
  } catch (error) {
    const message = mapApiError(error, 'Tag konnte nicht erstellt werden.');
    notify({ type: 'error', message });
  } finally {
    isTagMutationRunning.value = false;
  }
}

async function submitRenameTag() {
  if (!renameTargetTag.value) {
    return;
  }
  const newName = normalizeTagInput(renameTagName.value);
  if (!newName) {
    const message = 'Tag-Name darf nicht leer sein.';
    notify({ type: 'warning', message });
    return;
  }

  isTagMutationRunning.value = true;
  try {
    const response = await fetch(`${apiBaseUrl}/api/tags/${renameTargetTag.value.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName })
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    await fetchTags();
    scheduleSidebarCountsRefresh();
    notify({ type: 'success', title: 'Tag', message: `Tag "${renameTargetTag.value.name}" umbenannt.` });
    closeRenameTagDialog();
  } catch (error) {
    const message = mapApiError(error, 'Tag konnte nicht umbenannt werden.');
    notify({ type: 'error', message });
  } finally {
    isTagMutationRunning.value = false;
  }
}

async function submitMergeTag() {
  if (!mergeSourceTag.value || !mergeTargetTagId.value) {
    return;
  }

  isTagMutationRunning.value = true;
  try {
    const sourceId = mergeSourceTag.value.id;
    const targetId = mergeTargetTagId.value;
    const targetName = tags.value.find((tag) => tag.id === targetId)?.name || 'Ziel-Tag';
    const response = await fetch(`${apiBaseUrl}/api/tags/${sourceId}/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_id: targetId })
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    if (activeTagId.value === sourceId) {
      activeTagId.value = targetId;
    }
    await fetchTags();
    await fetchDocuments(selectedDocumentId.value);
    scheduleSidebarCountsRefresh();
    notify({ type: 'success', title: 'Tag', message: `Tag wurde in "${targetName}" zusammengeführt.` });
    closeMergeTagDialog();
  } catch (error) {
    const message = mapApiError(error, 'Tag konnte nicht zusammengeführt werden.');
    notify({ type: 'error', message });
  } finally {
    isTagMutationRunning.value = false;
  }
}

async function submitDeleteTag() {
  if (!deleteTagTarget.value) {
    return;
  }

  isTagMutationRunning.value = true;
  try {
    const tagId = deleteTagTarget.value.id;
    const response = await fetch(`${apiBaseUrl}/api/tags/${tagId}`, {
      method: 'DELETE'
    });
    if (!response.ok) {
      throw new Error(await parseResponseError(response));
    }

    if (activeTagId.value === tagId) {
      activeTagId.value = null;
    }
    await fetchTags();
    await fetchDocuments(selectedDocumentId.value);
    scheduleSidebarCountsRefresh();
    notify({ type: 'success', title: 'Tag', message: 'Tag gelöscht.' });
    closeDeleteTagDialog();
  } catch (error) {
    const message = mapApiError(error, 'Tag konnte nicht gelöscht werden.');
    notify({ type: 'error', message });
  } finally {
    isTagMutationRunning.value = false;
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

function hasFileDragPayload(event) {
  const types = Array.from(event.dataTransfer?.types || []);
  return types.includes('Files');
}

function onListDragEnter(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  listDropDragDepth.value += 1;
  isListDragOver.value = true;
}

function onListDragOver(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy';
  }
  if (!isListDragOver.value) {
    isListDragOver.value = true;
  }
}

function onListDragLeave(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  listDropDragDepth.value = Math.max(0, listDropDragDepth.value - 1);
  if (listDropDragDepth.value === 0) {
    isListDragOver.value = false;
  }
}

async function onListDrop(event) {
  if (!hasFileDragPayload(event)) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  isListDragOver.value = false;
  listDropDragDepth.value = 0;

  const files = Array.from(event.dataTransfer?.files || []);
  if (files.length === 0) {
    return;
  }

  const selection = selectPdfFiles(files, 'dnd');
  const rejectedCount = selection.skippedNonPdf + selection.skippedDuplicates;

  if (rejectedCount > 0) {
    setListDropNotice(
      rejectedCount === 1
        ? 'Nur PDFs werden importiert. 1 Datei wurde ignoriert.'
        : `Nur PDFs werden importiert. ${rejectedCount} Dateien wurden ignoriert.`
    );
  } else {
    setListDropNotice('');
  }

  if (selection.files.length === 0) {
    return;
  }

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

async function openImportPhoneScan() {
  const dialogRef = importStagingDialogRef.value;
  if (dialogRef && typeof dialogRef.openForPhoneScan === 'function') {
    await dialogRef.openForPhoneScan();
  }
}

async function onImportCommitted(payload) {
  if (!Array.isArray(payload?.created) || payload.created.length === 0) {
    return;
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
    } catch {
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
    metadataErrorMessage.value = mapApiError(error, 'Speichern fehlgeschlagen.');
    notify({ type: 'error', message: metadataErrorMessage.value });
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

watch(
  () => [
    parsedSearch.value.q,
    parsedSearch.value.status,
    parsedSearch.value.dateFrom,
    parsedSearch.value.dateTo,
    activeView.value
  ],
  () => {
    if (isTagView.value) {
      return;
    }
    syncSearchStateToQuery();
  }
);

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

watch(documentListQueryReloadKey, () => {
  if (searchDebounceTimer) {
    window.clearTimeout(searchDebounceTimer);
  }

  searchDebounceTimer = window.setTimeout(() => {
    if (isTagView.value) {
      return;
    }
    void fetchDocuments(selectedDocumentId.value);
  }, SEARCH_DEBOUNCE_MS);
});

async function pollOcrStatus() {
  if (isLoadingDocuments.value) {
    return;
  }

  const listHasProcessing = documents.value.some((document) => document.status === 'processing');
  if (!listHasProcessing && !hasActiveOcrJob.value) {
    return;
  }

  try {
    await fetchDocuments(selectedDocumentId.value);
  } catch {
    // ignore polling errors; foreground requests handle user-visible errors
  }
}

onMounted(async () => {
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', handleSystemThemeChange);
  window.addEventListener('keydown', handleGlobalKeydown);
  loadSidebarSectionVisibility();
  await fetchAppSettings();

  await Promise.all([fetchTags(), fetchSavedSearches(), fetchSidebarCounts()]);
  await fetchDocuments(null, { autoSelectFirst: true });
  statusPollTimer = window.setInterval(() => {
    void pollOcrStatus();
  }, STATUS_POLL_INTERVAL_MS);
});

onBeforeUnmount(() => {
  if (searchDebounceTimer) {
    window.clearTimeout(searchDebounceTimer);
  }
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
  if (sidebarCountsRefreshTimer) {
    window.clearTimeout(sidebarCountsRefreshTimer);
  }
  window.removeEventListener('keydown', handleGlobalKeydown);
  mediaQuery?.removeEventListener('change', handleSystemThemeChange);
  if (statusPollTimer) {
    window.clearInterval(statusPollTimer);
  }
});
</script>

<style scoped>
.papermind-app {
  --pm-indigo-rgb: 48, 57, 112;
  --pm-dark-bg: #0b1220;
  --pm-dark-panel-left: #0f1a2a;
  --pm-dark-panel-mid: #111f33;
  --pm-dark-panel-right: #0c1626;
  --pm-dark-card: #162a44;
  --pm-dark-card-hover: #1b3556;
  --pm-dark-card-active: #22406a;
  --pm-dark-sep: rgba(255, 255, 255, 0.08);
  --pm-dark-outline: rgba(255, 255, 255, 0.06);
  --pm-dark-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  --pm-light-sep: rgba(15, 23, 42, 0.1);
  --pm-light-outline: rgba(15, 23, 42, 0.06);
  --pm-light-shadow: 0 10px 30px rgba(15, 23, 42, 0.1);
  --pm-text: rgba(15, 23, 42, 0.92);
  --pm-muted: rgba(15, 23, 42, 0.6);
  --pm-divider: rgba(var(--v-theme-on-surface), 0.08);
  --pm-app-surface: #f3f6fb;
  --pm-content-surface: #f6f9fe;
  --pm-sidebar-surface: #eef3fa;
  --pm-viewer-surface: #f2f6fd;
  --pm-app-surface-raised: #ffffff;
  --pm-app-surface-contrast: #ffffff;
  --pm-pdf-stage-bg: #f2f6fd;
  --pm-sidebar-hover: rgba(59, 130, 246, 0.06);
  --pm-sidebar-active: rgba(59, 130, 246, 0.1);
  --pm-sidebar-count-opacity: 0.68;
  --pm-row-hover: #f3f7ff;
  --pm-row-active: #eaf2ff;
  --pm-drawer-bg-expanded: rgba(255, 255, 255, 0.9);
  --pm-drawer-bg-collapsed: rgba(255, 255, 255, 0.68);
  --pm-drawer-blur-expanded: 5px;
  --pm-drawer-blur-collapsed: 11px;
  --pm-drawer-border-expanded: rgba(255, 255, 255, 0.16);
  --pm-drawer-border-collapsed: rgba(255, 255, 255, 0.14);
  --pm-drawer-scrim: transparent;
}

.papermind-app.v-theme--light {
  --pm-divider: var(--pm-light-sep);
  --pm-app-surface: #f3f6fb;
  --pm-content-surface: #f6f9fe;
  --pm-sidebar-surface: #eef3fa;
  --pm-viewer-surface: #f2f6fd;
  --pm-app-surface-raised: #ffffff;
  --pm-app-surface-contrast: #ffffff;
  --pm-pdf-stage-bg: #f2f6fd;
  --pm-sidebar-hover: rgba(59, 130, 246, 0.06);
  --pm-sidebar-active: rgba(59, 130, 246, 0.1);
  --pm-row-hover: #f3f7ff;
  --pm-row-active: #eaf2ff;
  --pm-drawer-bg-expanded: rgba(255, 255, 255, 0.9);
  --pm-drawer-bg-collapsed: rgba(255, 255, 255, 0.68);
  --pm-drawer-blur-expanded: 5px;
  --pm-drawer-blur-collapsed: 11px;
  --pm-drawer-border-expanded: rgba(0, 0, 0, 0.12);
  --pm-drawer-border-collapsed: rgba(0, 0, 0, 0.1);
  --pm-drawer-scrim: transparent;
}

.papermind-app.v-theme--dark {
  --v-theme-overlay-multiplier: 0;
  --pm-divider: var(--pm-dark-sep);
  --pm-app-surface: var(--pm-dark-bg);
  --pm-content-surface: var(--pm-dark-panel-mid);
  --pm-sidebar-surface: var(--pm-dark-panel-left);
  --pm-viewer-surface: var(--pm-dark-panel-right);
  --pm-app-surface-raised: var(--pm-dark-card);
  --pm-app-surface-contrast: var(--pm-dark-card);
  --pm-pdf-stage-bg: var(--pm-dark-panel-right);
  --pm-sidebar-hover: var(--pm-dark-card-hover);
  --pm-sidebar-active: #1c2b40;
  --pm-sidebar-count-opacity: 0.9;
  --pm-row-hover: var(--pm-dark-card-hover);
  --pm-row-active: var(--pm-dark-card-active);
  --pm-drawer-bg-expanded: rgba(28, 37, 51, 0.96);
  --pm-drawer-bg-collapsed: rgba(28, 37, 51, 0.9);
  --pm-drawer-blur-expanded: 2px;
  --pm-drawer-blur-collapsed: 6px;
  --pm-drawer-border-expanded: rgba(255, 255, 255, 0.08);
  --pm-drawer-border-collapsed: rgba(255, 255, 255, 0.06);
  --pm-drawer-scrim: transparent;
}

.app-topbar {
  color: rgba(248, 250, 255, 0.96) !important;
  background: rgb(var(--pm-indigo-rgb)) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

.app-topbar :deep(.v-toolbar__content) {
  padding: 0 16px;
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
  min-width: 180px;
}

.app-title__brand {
  color: rgba(248, 250, 255, 0.98);
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
  background: rgba(var(--pm-indigo-rgb), 0.08);
  border-color: rgba(var(--pm-indigo-rgb), 0.28);
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
  background: rgba(var(--pm-indigo-rgb), 0.1);
  border: 1px solid rgba(var(--pm-indigo-rgb), 0.22);
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
  box-shadow: inset 0 0 0 1px rgba(var(--pm-indigo-rgb), 0.34);
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
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.document-list-empty-state-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 16px 20px;
}

.document-list-empty-state {
  max-width: 460px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 10px;
}

.document-list-empty-state__icon {
  opacity: 0.56;
}

.document-list-empty-state__title {
  margin-top: 2px;
  font-size: 1.02rem;
  font-weight: 600;
  line-height: 1.25;
}

.document-list-empty-state__subtitle {
  max-width: 460px;
  font-size: 0.84rem;
  line-height: 1.4;
  opacity: 0.72;
}

.document-list-body--dragover .document-row {
  pointer-events: none;
}

.menu-item--danger :deep(.v-list-item-title),
.menu-item--danger :deep(.v-icon) {
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
  border: 1px dashed rgba(var(--pm-indigo-rgb), 0.36);
  border-radius: 10px;
  background: rgba(var(--pm-indigo-rgb), 0.07);
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
  border: 1px solid rgba(var(--pm-indigo-rgb), 0.24);
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
  gap: 6px;
}

.settings-theme-segmented__item {
  min-height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.2);
  background: rgba(var(--v-theme-surface-variant), 0.3);
  color: rgba(var(--v-theme-on-surface), 0.88);
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease, color 0.16s ease;
}

.settings-theme-segmented__item:hover:not(:disabled) {
  border-color: rgba(var(--v-theme-primary), 0.42);
  background: rgba(var(--v-theme-primary), 0.12);
}

.settings-theme-segmented__item:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.settings-theme-segmented__item--active {
  border-color: rgba(var(--v-theme-primary), 0.72);
  background: rgba(var(--v-theme-primary), 0.2);
  color: rgb(var(--v-theme-on-surface));
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
  grid-template-columns: 240px 1fr minmax(360px, 43%);
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

.sidebar-item :deep(.v-list-item__prepend) {
  width: 30px;
  min-width: 30px;
  justify-content: center;
}

.sidebar-item :deep(.v-list-item__prepend > .v-list-item__spacer) {
  width: 5px;
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
  background: rgba(var(--pm-indigo-rgb), 0.95);
  opacity: 0;
  transition: opacity 0.16s ease, width 0.16s ease;
}

.sidebar-item.v-list-item--active {
  background: var(--pm-sidebar-active);
}

.sidebar-item.v-list-item--active::before {
  width: 3px;
  opacity: 1;
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
  background: rgba(var(--pm-indigo-rgb), 0.13);
  color: rgba(var(--pm-indigo-rgb), 0.94);
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background-color 0.16s ease;
}

.sidebar-item--tag:hover .sidebar-tag-pill {
  background: rgba(var(--pm-indigo-rgb), 0.18);
}

.sidebar-item--tag.v-list-item--active .sidebar-tag-pill {
  background: rgba(var(--pm-indigo-rgb), 0.24);
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
  color: rgba(var(--pm-indigo-rgb), 0.96);
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
  transform: translateY(0);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
  transition: background-color 150ms ease, border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.document-row + .document-row {
  margin-top: 10px;
}

.document-row:hover {
  background: var(--pm-row-hover);
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
}

.document-row--active {
  background: var(--pm-row-active);
  border-color: rgba(59, 130, 246, 0.22);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.1), 0 12px 26px rgba(15, 23, 42, 0.14);
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
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
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

.papermind-app.v-theme--dark .topbar-btn--import {
  background: #4a5586;
  border-color: #616da8;
}

.papermind-app.v-theme--dark .topbar-btn--import:hover {
  background: #536099;
}

.papermind-app.v-theme--dark .topbar-btn--ghost:hover,
.papermind-app.v-theme--dark .topbar-btn--icon:hover {
  background: #485380;
}

.papermind-app.v-theme--dark .topbar-btn--active {
  background: #56639b;
}

.papermind-app.v-theme--dark .document-row__meta,
.papermind-app.v-theme--dark .document-row__snippet,
.papermind-app.v-theme--dark .preview-empty-state__subtitle {
  opacity: 0.9;
}

.papermind-app.v-theme--dark .document-row:hover {
  background: var(--pm-dark-card-hover);
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.3);
}

.papermind-app.v-theme--dark .document-row--active {
  background: var(--pm-dark-card-active);
  border-color: rgba(96, 165, 250, 0.3);
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.18), 0 12px 26px rgba(0, 0, 0, 0.32);
}

.papermind-app.v-theme--dark .document-row--active:hover {
  background: var(--pm-dark-card-active);
  transform: translateY(0);
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
  background: rgba(var(--pm-indigo-rgb), 0.96);
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

.document-row__chips {
  align-self: start;
  display: grid;
  justify-items: end;
  gap: 4px;
}

.document-row__ocr-chip {
  opacity: 0.9;
  border-color: rgba(var(--pm-indigo-rgb), 0.32);
  color: rgba(var(--pm-indigo-rgb), 0.92);
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

.preview-empty-state {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  padding: 24px;
}

.preview-empty-state__icon {
  opacity: 0.58;
}

.preview-empty-state__title {
  font-size: 0.96rem;
  font-weight: 600;
  line-height: 1.25;
}

.preview-empty-state__subtitle {
  max-width: 320px;
  font-size: 0.82rem;
  line-height: 1.4;
  opacity: 0.72;
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
  transition: background-color 0.18s ease, transform 0.2s ease, opacity 0.2s ease;
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
}

.details-chevron-btn--expanded :deep(.v-icon) {
  transform: rotate(180deg);
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
  transition: background-color 0.18s ease;
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
  transition: min-height 0.18s ease;
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
    grid-template-columns: 220px 1fr;
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
