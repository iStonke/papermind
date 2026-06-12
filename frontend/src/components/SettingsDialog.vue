<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="820"
    card-class="pm-settings-card"
    body-class="pm-settings-body"
    footer-class="pm-settings-footer"
    title="Einstellungen"
    header-subtitle="Globale Voreinstellungen für dein PaperMind."
    description=""
    variant="info"
    primary-text="Fertig"
    :show-secondary="false"
    @primary="emit('update:modelValue', false)"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="isSettingsLoading" class="settings-loading">
      <v-progress-circular indeterminate size="20" width="2" />
      <span>Einstellungen werden geladen...</span>
    </div>
    <template v-else>
      <div class="pm-settings-layout">
        <nav class="pm-settings-nav" role="tablist" aria-label="Einstellungskategorien">
          <button
            v-for="cat in visibleCategories"
            :key="`cat-${cat.value}`"
            type="button"
            class="pm-settings-nav__item"
            :class="{ 'pm-settings-nav__item--active': activeCategory === cat.value }"
            role="tab"
            :aria-selected="activeCategory === cat.value"
            @click="activeCategory = cat.value"
          >
            <v-icon size="18" class="pm-settings-nav__icon">{{ cat.icon }}</v-icon>
            <span>{{ cat.label }}</span>
          </button>
        </nav>

        <div class="pm-settings-panel">
        <section v-show="activeCategory === 'appearance'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-palette-outline"
              title="Darstellung"
              subtitle="Farben, Thema und das Verhalten der Oberfläche anpassen."
            />

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Farbvariation</div>
                <div class="pm-setting-description">Akzentfarbe der gesamten Oberfläche.</div>
              </div>
              <div
                class="settings-color-variant-picker"
                role="radiogroup"
                aria-label="Farbvariante auswählen"
              >
                <button
                  v-for="option in colorVariantOptions"
                  :key="`variant-${option.value}`"
                  type="button"
                  class="settings-color-variant-picker__item"
                  :class="{ 'settings-color-variant-picker__item--active': currentColorVariant === option.value }"
                  :style="{ '--variant-color': option.color }"
                  role="radio"
                  :aria-label="`Farbvariante: ${option.label}`"
                  :aria-checked="currentColorVariant === option.value"
                  :disabled="isSettingSaving.color_variant"
                  :title="option.label"
                  @click="onColorVariantChange(option.value)"
                  @pointerup.prevent="onColorVariantChange(option.value)"
                  @keydown.enter.prevent="onColorVariantChange(option.value)"
                  @keydown.space.prevent="onColorVariantChange(option.value)"
                >
                  <span class="settings-color-variant-picker__swatch" />
                </button>
              </div>
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Thema</div>
                <div class="pm-setting-description">Hell, dunkel oder entsprechend Systemeinstellung.</div>
              </div>
              <div
                class="settings-theme-segmented"
                role="radiogroup"
                aria-label="Thema auswählen"
                @keydown="handleThemeModeShortcut"
              >
                <button
                  v-for="option in themeModeOptions"
                  :key="`theme-${option.value}`"
                  type="button"
                  class="settings-theme-segmented__item"
                  :class="{ 'settings-theme-segmented__item--active': settingsDraft.ui.theme_mode === option.value }"
                  role="radio"
                  :aria-label="`Thema: ${option.label}`"
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
              @keydown="handleSettingRowShortcut($event, toggleShowFilenameSuffixFromRow)"
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

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAnimationsFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAnimationsFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Animationen</div>
                <div class="pm-setting-description">Sanfte Übergänge und Einblendeffekte in der Oberfläche.</div>
              </div>
              <v-switch
                :model-value="animationsEnabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                @click.stop
                @update:model-value="onAnimationsEnabledChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleGlassEnabledFromRow"
              @keydown="handleSettingRowShortcut($event, toggleGlassEnabledFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Glass-Look (Aurora-Hintergrund)</div>
                <div class="pm-setting-description">
                  Durchscheinende Oberflächen mit animiertem Wissensgraph im Hintergrund. Nutzt die aktive
                  Farbvariante. Benötigt aktivierte Animationen.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.ui.glass_enabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :disabled="!animationsEnabled || isSettingSaving.glass_enabled"
                :loading="isSettingSaving.glass_enabled"
                @click.stop
                @update:model-value="onGlassEnabledChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleDrawerRememberStateFromRow"
              @keydown="handleSettingRowShortcut($event, toggleDrawerRememberStateFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Dokumentdetails merken</div>
                <div class="pm-setting-description">
                  Merkt sich, ob die Dokumentdetails zuletzt ein- oder ausgeklappt waren.
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
              @click="toggleTagDrawerRememberStateFromRow"
              @keydown="handleSettingRowShortcut($event, toggleTagDrawerRememberStateFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Tag-Schublade merken</div>
                <div class="pm-setting-description">
                  Merkt sich, ob die Tag-Schublade zuletzt ein- oder ausgeklappt war.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.ui.tagDrawerRememberState"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.tag_drawer_remember_state"
                :disabled="isSettingSaving.tag_drawer_remember_state"
                @click.stop
                @update:model-value="onTagDrawerRememberStateChange"
              />
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'sidebar'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-page-layout-sidebar-left"
              title="Seitenleiste"
              subtitle="Reihenfolge und Sichtbarkeit der Bereiche."
            />

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Bereiche der Seitenleiste</div>
                <div class="pm-setting-description">
                  Sortiere die Bereiche per Pfeil und blende sie mit dem Schalter komplett ein oder aus.
                  Der Bereich „Bibliothek“ bleibt immer oben.
                </div>
              </div>

              <div class="settings-sidebar-sections">
                <div
                  v-for="(section, index) in sidebarSectionsDraft"
                  :key="section.key"
                  class="settings-sidebar-section-row"
                  :class="{ 'settings-sidebar-section-row--hidden': !section.visible }"
                >
                  <div class="settings-sidebar-section-reorder">
                    <button
                      type="button"
                      class="settings-sidebar-section-arrow"
                      aria-label="Nach oben"
                      :disabled="index === 0 || isSettingSaving.sidebar_sections"
                      @click="moveSidebarSection(index, -1)"
                    >
                      <v-icon size="18">mdi-chevron-up</v-icon>
                    </button>
                    <button
                      type="button"
                      class="settings-sidebar-section-arrow"
                      aria-label="Nach unten"
                      :disabled="index === sidebarSectionsDraft.length - 1 || isSettingSaving.sidebar_sections"
                      @click="moveSidebarSection(index, 1)"
                    >
                      <v-icon size="18">mdi-chevron-down</v-icon>
                    </button>
                  </div>
                  <div class="settings-sidebar-section-icon" aria-hidden="true">
                    <v-icon size="18">{{ sidebarSectionIcon(section.key) }}</v-icon>
                  </div>
                  <div class="settings-sidebar-section-name">{{ sidebarSectionLabel(section.key) }}</div>
                  <v-switch
                    :model-value="section.visible"
                    color="primary"
                    density="comfortable"
                    hide-details
                    inset
                    :aria-label="`${sidebarSectionLabel(section.key)} ein-/ausblenden`"
                    :loading="isSettingSaving.sidebar_sections"
                    :disabled="isSettingSaving.sidebar_sections"
                    @update:model-value="(val) => setSidebarSectionVisibility(section.key, val)"
                  />
                </div>
              </div>
            </div>

            <div class="pm-setting-row">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Angezeigte Tags</div>
              </div>
              <v-select
                :model-value="settingsDraft.ui.sidebar_max_tags"
                :items="sidebarMaxOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select settings-sidebar-max-select"
                aria-label="Maximale Tags in der Seitenleiste"
                :loading="isSettingSaving.sidebar_max_tags"
                :disabled="isSettingSaving.sidebar_max_tags"
                @update:model-value="onSidebarMaxTagsChange"
              />
            </div>

            <div class="pm-setting-row">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Angezeigte Dokumenttypen</div>
              </div>
              <v-select
                :model-value="settingsDraft.ui.sidebar_max_categories"
                :items="sidebarMaxOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select settings-sidebar-max-select"
                aria-label="Maximale Dokumenttypen in der Seitenleiste"
                :loading="isSettingSaving.sidebar_max_categories"
                :disabled="isSettingSaving.sidebar_max_categories"
                @update:model-value="onSidebarMaxCategoriesChange"
              />
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'documents'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-file-document-outline"
              title="Dokumente"
              subtitle="Aufbewahrung, Zeiträume und Aufräum-Funktionen deiner Dokumente."
            />

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Zeitraum für „Zuletzt hinzugefügt"</div>
                <div class="pm-setting-description">
                  Legt fest, wie lange Dokumente nach dem Import in „Zuletzt hinzugefügt" erscheinen.
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

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Papierkorb automatisch leeren</div>
                <div class="pm-setting-description">
                  Legt fest, wann Dokumente im Papierkorb endgültig gelöscht werden.
                </div>
              </div>
              <v-select
                :model-value="settingsDraft.documents.trash_retention_days"
                :items="trashRetentionOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Papierkorb"
                :loading="isSettingSaving.trash_retention_days"
                :disabled="isSettingSaving.trash_retention_days"
                @update:model-value="onTrashRetentionChange"
              />
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Unbenutzte Tags aufräumen</div>
                <div class="pm-setting-description">
                  Entfernt Tags, die an keinem Dokument hängen (z. B. Reste früherer, nicht abgeschlossener Importe).
                </div>
              </div>

              <div v-if="!unusedTagsPreview">
                <v-btn variant="tonal" :loading="tagCleanupLoading" @click="loadUnusedTagsPreview">
                  Unbenutzte Tags suchen…
                </v-btn>
              </div>

              <div v-else class="pm-tag-cleanup">
                <div v-if="unusedTagsPreview.count === 0" class="pm-setting-description">
                  Keine unbenutzten Tags gefunden. 🎉
                </div>
                <div v-else class="pm-setting-description">
                  <strong>{{ unusedTagsPreview.count }}</strong> Tag{{ unusedTagsPreview.count === 1 ? '' : 's' }} werden entfernt:
                  <span class="pm-tag-cleanup__names">{{ unusedTagsPreview.tags.map(t => t.name).join(', ') }}</span>
                </div>
                <div class="pm-tag-cleanup__actions">
                  <v-btn variant="text" size="small" :disabled="tagCleanupLoading" @click="unusedTagsPreview = null">
                    {{ unusedTagsPreview.count === 0 ? 'Schließen' : 'Abbrechen' }}
                  </v-btn>
                  <v-btn
                    v-if="unusedTagsPreview.count > 0"
                    color="error"
                    variant="flat"
                    size="small"
                    :loading="tagCleanupLoading"
                    @click="confirmTagCleanup"
                  >
                    {{ unusedTagsPreview.count }} entfernen
                  </v-btn>
                </div>
              </div>
            </div>

          </div>
        </section>

        <section v-show="activeCategory === 'categories'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-file-document-multiple-outline"
              title="Dokumenttypen"
              subtitle="Auswahloptionen für den Import samt Dateiname-Templates verwalten."
            />

            <div class="settings-category-management">
              <div class="settings-category-header">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Verfügbare Dokumenttypen</div>
                <div class="pm-setting-description">
                  Diese Dokumenttypen stehen beim Import zur Auswahl. Die Zahl zeigt, wie viele
                  Dokumente den Typ nutzen. Löschen entfernt nur die Auswahloption –
                  bereits zugewiesene Dokumente behalten ihren Dokumenttyp.
                </div>
              </div>

                <div class="settings-category-add">
                  <v-text-field
                    v-model="newCategoryName"
                    :maxlength="VOCAB_NAME_MAX_LENGTH"
                    density="compact"
                    variant="outlined"
                    hide-details
                    placeholder="Neuer Dokumenttyp…"
                    :disabled="categoryStore.isCategoryMutationRunning"
                    @keydown.enter.prevent="addCategory"
                  />
                  <v-btn
                    variant="tonal"
                    color="primary"
                    size="default"
                    class="settings-category-add__button"
                    prepend-icon="mdi-plus"
                    :disabled="!newCategoryName.trim() || categoryStore.isCategoryMutationRunning"
                    @click="addCategory"
                  >
                    Hinzufügen
                  </v-btn>
                </div>
              </div>

              <div class="settings-categories">
                <div
                  v-for="cat in categoryStore.sortedCategories"
                  :key="cat.id"
                  class="settings-category-row"
                  :class="{ 'settings-category-row--active': selectedCategoryId === cat.id }"
                >
                  <button
                    type="button"
                    class="settings-category-summary"
                    @click="toggleCategory(cat)"
                  >
                    <div class="settings-category-main">
                      <div class="settings-category-icon" aria-hidden="true">
                        <v-icon size="16">{{ cat.is_active === false ? 'mdi-folder-outline' : 'mdi-file-document-multiple-outline' }}</v-icon>
                      </div>
                      <div class="settings-category-text">
                        <span class="settings-category-name">{{ cat.name }}</span>
                        <span class="settings-category-meta">
                          {{ cat.is_active === false ? 'inaktiv' : 'aktiv' }}
                          <template v-if="cat.naming_template"> · Template</template>
                        </span>
                      </div>
                    </div>
                    <div class="settings-category-actions">
                      <span class="settings-category-count" :title="`${cat.usage_count || 0} Dokument(e)`">
                        {{ cat.usage_count || 0 }}
                      </span>
                      <v-icon size="18">{{ selectedCategoryId === cat.id ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
                    </div>
                  </button>

                  <div
                    class="settings-category-editor-shell"
                    :class="{ 'settings-category-editor-shell--open': selectedCategoryId === cat.id }"
                    :aria-hidden="selectedCategoryId === cat.id ? 'false' : 'true'"
                    :inert="selectedCategoryId === cat.id ? null : true"
                  >
                    <div class="settings-category-editor">
                      <div class="settings-category-form">
                        <v-text-field
                          v-model="editingCategoryName"
                          :maxlength="VOCAB_NAME_MAX_LENGTH"
                          density="compact"
                          variant="outlined"
                          hide-details
                          label="Name"
                          @keydown.enter.prevent="saveSelectedCategory"
                        />
                        <v-btn
                          icon
                          variant="text"
                          color="primary"
                          class="settings-category-action-btn"
                          title="Speichern"
                          :loading="categoryStore.isCategoryMutationRunning"
                          :disabled="!canSaveSelectedCategory"
                          @click="saveSelectedCategory"
                        >
                          <v-icon size="18">mdi-content-save-outline</v-icon>
                        </v-btn>
                        <v-btn
                          icon
                          variant="text"
                          color="error"
                          class="settings-category-action-btn settings-category-action-btn--danger"
                          title="Löschen"
                          :disabled="categoryStore.isCategoryMutationRunning"
                          @click="removeCategory(cat)"
                        >
                          <v-icon size="18">mdi-trash-can-outline</v-icon>
                        </v-btn>
                      </div>
                      <div class="settings-correspondent-block">
                        <v-textarea
                          v-model="editingCategoryTemplate"
                          density="compact"
                          variant="outlined"
                          hide-details
                          rows="2"
                          auto-grow
                          label="Dateiname-Template"
                          placeholder="z. B. {betreff} {datum:dd.MM.yyyy}"
                        />
                        <div class="settings-template-preview">
                          <span class="settings-template-preview__label">Vorschau</span>
                          <span class="settings-template-preview__value">
                            <template
                              v-for="(part, index) in categoryTemplatePreviewParts"
                              :key="`${part.text}-${index}`"
                            >
                              <span
                                v-if="part.missing"
                                class="settings-template-preview__missing"
                              >{{ part.text }}</span>
                              <span v-else>{{ part.text }}</span>
                            </template>
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="categoryStore.sortedCategories.length === 0" class="settings-category-empty">
                  Noch keine Dokumenttypen angelegt.
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'correspondents'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-account-outline"
              title="Korrespondenten"
              subtitle="Absender und Aussteller mit Aliasen pflegen und zuordnen."
            />

            <div class="settings-category-management">
              <div class="settings-category-header">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Korrespondenten</div>
                  <div class="pm-setting-description">
                    Kanonische Absender/Aussteller mit Aliasen. Die Zahl zeigt, wie viele
                    Dokumente aktuell zugeordnet sind.
                  </div>
                </div>

                <div class="settings-category-add">
                  <v-text-field
                    v-model="newCorrespondentName"
                    maxlength="120"
                    density="compact"
                    variant="outlined"
                    hide-details
                    placeholder="Neuer Korrespondent…"
                    :disabled="correspondentStore.isMutationRunning"
                    @keydown.enter.prevent="addCorrespondent"
                  />
                  <v-btn
                    variant="tonal"
                    color="primary"
                    size="default"
                    class="settings-category-add__button"
                    prepend-icon="mdi-plus"
                    :disabled="!newCorrespondentName.trim() || correspondentStore.isMutationRunning"
                    @click="addCorrespondent"
                  >
                    Hinzufügen
                  </v-btn>
                </div>
              </div>

              <div class="settings-correspondents">
                <div v-if="unresolvedCorrespondents.length" class="settings-correspondent-review">
                  <div class="settings-correspondent-review__header">
                    <div>
                      <div class="settings-correspondent-block__title">Offene Zuordnungen</div>
                      <div class="pm-setting-description">
                        {{ unresolvedCorrespondents.length }} Dokument{{ unresolvedCorrespondents.length === 1 ? '' : 'e' }} ohne Korrespondent.
                      </div>
                    </div>
                    <v-btn
                      icon
                      size="small"
                      variant="text"
                      title="Aktualisieren"
                      :loading="isUnresolvedCorrespondentsLoading"
                      @click="loadUnresolvedCorrespondents"
                    >
                      <v-icon size="18">mdi-refresh</v-icon>
                    </v-btn>
                  </div>

                  <div
                    v-for="item in unresolvedCorrespondents"
                    :key="item.document_id"
                    class="settings-unresolved-row"
                  >
                    <div class="settings-unresolved-row__main">
                      <div class="settings-category-name">{{ item.title || item.original_filename }}</div>
                      <div class="settings-category-meta">
                        {{ item.sender || 'kein erkannter Absender' }}
                        <template v-if="item.document_type"> · {{ item.document_type }}</template>
                        <template v-if="item.document_date"> · {{ item.document_date }}</template>
                      </div>
                    </div>
                    <v-select
                      v-model="unresolvedSelections[item.document_id]"
                      :items="correspondentStore.correspondentOptions"
                      density="compact"
                      variant="outlined"
                      hide-details
                      placeholder="Korrespondent wählen…"
                      class="settings-unresolved-row__select"
                    />
                    <v-btn
                      icon
                      variant="tonal"
                      color="primary"
                      title="Zuordnen"
                      :disabled="!unresolvedSelections[item.document_id] || assigningUnresolvedId === item.document_id"
                      :loading="assigningUnresolvedId === item.document_id"
                      @click="assignUnresolvedCorrespondent(item, false)"
                    >
                      <v-icon size="18">mdi-check</v-icon>
                    </v-btn>
                    <v-btn
                      icon
                      variant="text"
                      color="primary"
                      title="Absender als Alias hinzufügen und zuordnen"
                      :disabled="!item.sender || !unresolvedSelections[item.document_id] || assigningUnresolvedId === item.document_id"
                      @click="assignUnresolvedCorrespondent(item, true)"
                    >
                      <v-icon size="18">mdi-tag-plus</v-icon>
                    </v-btn>
                    <v-btn
                      icon
                      variant="text"
                      color="primary"
                      title="Neuen Korrespondenten aus Absender anlegen"
                      :disabled="!item.sender || creatingUnresolvedId === item.document_id"
                      :loading="creatingUnresolvedId === item.document_id"
                      @click="createCorrespondentFromUnresolved(item)"
                    >
                      <v-icon size="18">mdi-account-plus</v-icon>
                    </v-btn>
                    <v-btn
                      icon
                      variant="text"
                      title="Bewusst leer lassen"
                      :disabled="ignoringUnresolvedId === item.document_id"
                      :loading="ignoringUnresolvedId === item.document_id"
                      @click="ignoreUnresolvedCorrespondent(item)"
                    >
                      <v-icon size="18">mdi-close</v-icon>
                    </v-btn>
                  </div>
                </div>

                <div
                  v-for="item in correspondentStore.correspondents"
                  :key="item.id"
                  class="settings-correspondent-row"
                  :class="{ 'settings-correspondent-row--active': selectedCorrespondentId === item.id }"
                >
                  <button
                    type="button"
                    class="settings-correspondent-summary"
                    @click="toggleCorrespondent(item)"
                  >
                    <span class="settings-category-main">
                      <span class="settings-category-icon" aria-hidden="true">
                        <v-icon size="16">mdi-account-outline</v-icon>
                      </span>
                      <span class="settings-category-text">
                        <span class="settings-category-name">{{ item.name }}</span>
                        <span class="settings-category-meta">
                          {{ item.short_name || 'kein Kurzname' }} · {{ item.aliases?.length || 0 }} Alias{{ (item.aliases?.length || 0) === 1 ? '' : 'e' }}
                        </span>
                      </span>
                    </span>
                    <span class="settings-correspondent-summary__right">
                      <span class="settings-category-count" :title="`${item.usage_count || 0} Dokument(e)`">
                        {{ item.usage_count || 0 }}
                      </span>
                      <v-icon size="18">{{ selectedCorrespondentId === item.id ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
                    </span>
                  </button>

                  <div
                    class="settings-correspondent-editor-shell"
                    :class="{ 'settings-correspondent-editor-shell--open': selectedCorrespondentId === item.id }"
                    :aria-hidden="selectedCorrespondentId === item.id ? 'false' : 'true'"
                    :inert="selectedCorrespondentId === item.id ? null : true"
                  >
                    <div class="settings-correspondent-editor">
                      <div class="settings-correspondent-form">
                        <v-text-field
                          v-model="editingCorrespondentName"
                          density="compact"
                          variant="outlined"
                          hide-details
                          label="Name"
                          maxlength="120"
                        />
                        <v-text-field
                          v-model="editingCorrespondentShortName"
                          density="compact"
                          variant="outlined"
                          hide-details
                          label="Kurzname"
                          maxlength="60"
                        />
                        <v-btn
                          icon
                          variant="text"
                          color="primary"
                          class="settings-correspondent-icon-action"
                          title="Speichern"
                          :loading="correspondentStore.isMutationRunning"
                          :disabled="!canSaveSelectedCorrespondent"
                          @click="saveSelectedCorrespondent"
                        >
                          <v-icon size="18">mdi-content-save-outline</v-icon>
                        </v-btn>
                        <v-btn
                          icon
                          variant="text"
                          color="error"
                          class="settings-correspondent-icon-action"
                          title="Löschen"
                          :disabled="correspondentStore.isMutationRunning || (item.usage_count || 0) > 0"
                          @click="removeSelectedCorrespondent"
                        >
                          <v-icon size="18">mdi-trash-can-outline</v-icon>
                        </v-btn>
                      </div>

                      <div class="settings-correspondent-block">
                        <div class="settings-inline-add">
                          <v-text-field
                            v-model="newAliasName"
                            density="compact"
                            variant="outlined"
                            hide-details
                            label="Aliase"
                            placeholder="Alias hinzufügen…"
                            @keydown.enter.prevent="addAliasToSelected"
                          />
                          <v-btn
                            icon
                            variant="text"
                            color="primary"
                            class="settings-correspondent-icon-action"
                            title="Alias hinzufügen"
                            :disabled="!newAliasName.trim() || correspondentStore.isMutationRunning"
                            @click="addAliasToSelected"
                          >
                            <v-icon size="18">mdi-plus</v-icon>
                          </v-btn>
                        </div>
                        <div class="settings-chip-list">
                          <v-chip
                            v-for="alias in item.aliases"
                            :key="alias.id"
                            size="small"
                            closable
                            @click:close="removeAlias(alias)"
                          >
                            {{ alias.alias }}
                          </v-chip>
                          <span v-if="!item.aliases?.length" class="settings-category-empty">Keine Aliase.</span>
                        </div>
                      </div>

                    </div>
                  </div>
                </div>

                <div v-if="correspondentStore.correspondents.length === 0" class="settings-category-empty">
                  Noch keine Korrespondenten angelegt.
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'ai'" class="pm-settings-section">
          <div class="pm-settings-content">

            <SettingsInfoCard
              icon="mdi-text-recognition"
              title="Texterkennung"
              subtitle="OCR-Qualität, Sprache und automatische Analyse."
            />

            <!-- Automatisches OCR (Grundlage für die KI-Analyse) -->
            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAutoOcrFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoOcrFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Automatisches OCR</div>
                <div class="pm-setting-description">Extrahiert den Text nach dem Import im Hintergrund – Grundlage für die KI-Analyse.</div>
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

            <!-- OCR-Lücken automatisch schließen -->
            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleOcrBackfillFromRow"
              @keydown="handleSettingRowShortcut($event, toggleOcrBackfillFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">OCR-Lücken automatisch schließen</div>
                <div class="pm-setting-description">Sucht regelmäßig im Hintergrund nach Dokumenten ohne Texterkennung und holt das OCR automatisch nach.</div>
              </div>
              <v-switch
                :model-value="settingsDraft.documents.ocr_backfill_enabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.ocr_backfill_enabled"
                :disabled="isSettingSaving.ocr_backfill_enabled"
                @click.stop
                @update:model-value="onOcrBackfillEnabledChange"
              />
            </div>

            <!-- OCR-Lücken jetzt schließen (manuelle Sofort-Aktion) -->
            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">OCR-Lücken jetzt schließen</div>
                <div class="pm-setting-description">
                  Reiht sofort OCR-Jobs für alle Dokumente ohne Texterkennung ein – ohne auf den nächsten automatischen Durchlauf zu warten.
                </div>
              </div>
              <div>
                <v-btn variant="tonal" :loading="ocrBackfillLoading" @click="runOcrBackfillNow">
                  OCR-Lücken jetzt schließen
                </v-btn>
              </div>
            </div>

            <!-- Erkennungssprache -->
            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Erkennungssprache</div>
                <div class="pm-setting-description">
                  Standardsprache für die Texterkennung.
                </div>
              </div>
              <v-select
                :model-value="settingsDraft.documents.ocr_doc_lang"
                :items="ocrDocLangOptions"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Erkennungssprache"
                :loading="isSettingSaving.ocr_doc_lang"
                :disabled="isSettingSaving.ocr_doc_lang"
                @update:model-value="onOcrDocLangChange"
              />
            </div>

            <!-- KI-gestützte Analyse: Funktion + lokale Engine (benötigt OCR) -->
            <div class="pm-setting-group">
            <div class="pm-setting-note pm-setting-note--group">
              Zwei unabhängige Optionen: <strong>Lokale KI (Ollama)</strong> bestimmt, <em>womit</em>
              analysiert wird (Engine &amp; Datenschutz). <strong>KI-Analyse nach dem Import</strong>
              bestimmt, <em>ob</em> danach automatisch Tags ergänzt werden.
            </div>
            <!-- KI-Analyse nach dem Import (benötigt Automatisches OCR) -->
            <div
              class="pm-setting-row"
              :class="{ 'pm-setting-row--disabled': !settingsDraft.documents.auto_ocr }"
              role="button"
              tabindex="0"
              @click="toggleAutoTaggingFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoTaggingFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">KI-Analyse nach dem Import</div>
                <div class="pm-setting-description">Vergibt nach dem Import automatisch Tags und macht das Dokument durchsuchbar.</div>
                <div v-if="!settingsDraft.documents.auto_ocr" class="pm-setting-hint">
                  Benötigt „Automatisches OCR" – ohne extrahierten Text gibt es nichts zu analysieren.
                </div>
                <div v-else-if="settingsDraft.documents.auto_tagging" class="pm-setting-hint">
                  Kann je nach Modell/Hardware etwas dauern.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.documents.auto_ocr && settingsDraft.documents.auto_tagging"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.auto_tagging"
                :disabled="isSettingSaving.auto_tagging || !settingsDraft.documents.auto_ocr"
                @click.stop
                @update:model-value="onAutoTaggingChange"
              />
            </div>

            <!-- Ollama enable toggle -->
            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleOllamaEnabledFromRow"
              @keydown="handleSettingRowShortcut($event, toggleOllamaEnabledFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Lokale KI (Ollama)</div>
                <div class="pm-setting-description">
                  Engine für die KI-Analyse – nutzt ein lokal laufendes Sprachmodell
                  (z.&thinsp;B. llama3.2:3b). Daten verlassen das Gerät nicht.
                </div>
                <div v-if="settingsDraft.ollama.enabled" class="pm-setting-hint">
                  Ollama muss lokal laufen. Empfohlen: llama3.2:3b (Pi 5: ~20 s/Dokument).
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.ollama.enabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.ollama_enabled"
                :disabled="isSettingSaving.ollama_enabled"
                @click.stop
                @update:model-value="onOllamaEnabledChange"
              />
            </div>

            <!-- Erweiterte Ollama-Optionen -->
            <template v-if="settingsDraft.ollama.enabled">
              <button
                type="button"
                class="pm-settings-disclosure"
                :aria-expanded="showOllamaAdvanced"
                @click="showOllamaAdvanced = !showOllamaAdvanced"
              >
                <v-icon size="16">{{ showOllamaAdvanced ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
                <span>Erweitert</span>
              </button>

              <template v-if="showOllamaAdvanced">
              <!-- Base URL -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Basis-URL</div>
                  <div class="pm-setting-description">Adresse des Ollama-Servers (Standard: http://localhost:11434).</div>
                </div>
                <v-text-field
                  :model-value="settingsDraft.ollama.base_url"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  placeholder="http://localhost:11434"
                  :loading="isSettingSaving.ollama_base_url"
                  :disabled="isSettingSaving.ollama_base_url"
                  class="pm-setting-select"
                  @change="onOllamaBaseUrlChange($event.target.value)"
                />
              </div>

              <!-- Model -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Modell</div>
                  <div class="pm-setting-description">Ollama-Modell für die Import-Analyse.</div>
                </div>
                <v-combobox
                  :model-value="settingsDraft.ollama.model"
                  :items="ollamaModelPresets"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  :loading="isSettingSaving.ollama_model"
                  :disabled="isSettingSaving.ollama_model"
                  class="pm-setting-select"
                  @update:model-value="onOllamaModelChange"
                />
              </div>

              <!-- Chat model (quality vs. speed) -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Chat-Modell (Frage &amp; Antwort)</div>
                  <div class="pm-setting-description">
                    Modell für den Dokumenten-Chat. Kleine Modelle (z.&thinsp;B. llama3.2:3b)
                    antworten schneller; größere (z.&thinsp;B. qwen2.5:7b, llama3.1:8b) liefern
                    bessere Qualität, sind auf dem Pi aber deutlich langsamer.
                  </div>
                </div>
                <v-combobox
                  :model-value="settingsDraft.ollama.chat_model"
                  :items="ollamaChatModelPresets"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  :loading="isSettingSaving.ollama_chat_model"
                  :disabled="isSettingSaving.ollama_chat_model"
                  class="pm-setting-select"
                  @update:model-value="onOllamaChatModelChange"
                />
              </div>

              <!-- Max input chars -->
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Max. Textlänge (Zeichen)</div>
                  <div class="pm-setting-description">
                    Nur die ersten N Zeichen des OCR-Texts werden ans Modell übergeben.
                    Kürzere Texte = schneller, weniger Datenweitergabe bei externen Servern.
                  </div>
                </div>
                <v-select
                  :model-value="settingsDraft.ollama.max_input_chars"
                  :items="ollamaMaxCharsOptions"
                  item-title="label"
                  item-value="value"
                  density="comfortable"
                  variant="outlined"
                  hide-details
                  :loading="isSettingSaving.ollama_max_input_chars"
                  :disabled="isSettingSaving.ollama_max_input_chars"
                  class="pm-setting-select"
                  @update:model-value="onOllamaMaxInputCharsChange"
                />
              </div>

              </template>
            </template>
            </div>
          </div>
        </section>

        <section v-show="activeCategory === 'backup'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-cloud-upload-outline"
              title="Backup auf NAS"
              subtitle="Sichert Datenbank und PDFs automatisch auf dein Netzlaufwerk."
            >
              <template #actions>
                <v-switch
                  :model-value="backup.enabled"
                  color="primary"
                  hide-details
                  density="compact"
                  :loading="backupSaving"
                  @update:model-value="onToggleBackup"
                />
              </template>
            </SettingsInfoCard>

            <div class="backup-card" :class="`backup-card--${backupCardKind}`">
              <div class="backup-card__main">
                <div class="backup-card__icon">
                  <v-progress-circular v-if="backupBusy" indeterminate size="24" width="3" />
                  <v-icon v-else size="28">{{ backupStatusIcon }}</v-icon>
                </div>
                <div class="backup-card__info">
                  <div class="backup-card__state">{{ backupStateLabel }}</div>
                  <div class="backup-card__detail">{{ backupLastLabel }}</div>
                </div>
                <div v-if="backup.enabled" class="backup-card__next">
                  <div class="backup-card__next-label">Nächster Lauf</div>
                  <div class="backup-card__next-value">{{ backupNextLabel }}</div>
                </div>
              </div>

              <div class="backup-card__section">
                <div class="backup-card__section-head">
                  <span class="backup-card__section-title">Zeitplan</span>
                  <v-btn
                    variant="text"
                    size="x-small"
                    :loading="backupSaving"
                    prepend-icon="mdi-content-save-outline"
                    @click="saveBackup"
                  >
                    Speichern
                  </v-btn>
                </div>
                <div class="backup-grid backup-grid--tight">
                  <v-select
                    v-model="backup.frequency"
                    :items="[{ title: 'Täglich', value: 'daily' }, { title: 'Wöchentlich', value: 'weekly' }]"
                    label="Häufigkeit"
                    density="compact"
                    variant="outlined"
                    hide-details
                    :menu-props="{ attach: 'body', zIndex: 6000 }"
                  />
                  <v-text-field v-model="backup.time" label="Uhrzeit" placeholder="03:00" density="compact" variant="outlined" hide-details />
                  <v-select
                    v-if="backup.frequency === 'weekly'"
                    v-model="backup.weekday"
                    :items="backupWeekdayItems"
                    label="Wochentag"
                    density="compact"
                    variant="outlined"
                    hide-details
                    :menu-props="{ attach: 'body', zIndex: 6000 }"
                  />
                  <v-text-field v-model.number="backup.retention" type="number" min="1" max="365" label="Backups behalten" density="compact" variant="outlined" hide-details />
                </div>
              </div>

              <div class="backup-card__actions">
                <v-btn
                  variant="flat"
                  color="primary"
                  size="small"
                  :disabled="!backup.enabled || backupBusy"
                  prepend-icon="mdi-backup-restore"
                  @click="onRunBackup"
                >
                  {{ backupStatusKind === 'error' ? 'Erneut versuchen' : 'Jetzt sichern' }}
                </v-btn>
                <v-btn variant="text" size="small" prepend-icon="mdi-folder-clock-outline" @click="openBackupManager">
                  Backups verwalten
                </v-btn>
              </div>
            </div>

            <v-expansion-panels v-model="backupSetupOpen" class="backup-setup" flat>
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <div class="backup-setup__head">
                    <v-icon size="20" class="mr-3">mdi-cog-outline</v-icon>
                    <div class="backup-setup__head-text">
                      <div class="backup-setup__head-title">NAS-Verbindung</div>
                      <div class="backup-setup__head-sub">{{ backupSetupSummary }}</div>
                    </div>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <div class="backup-grid">
                    <v-text-field class="backup-grid__full" v-model="backup.nas_host" label="IP-Adresse" placeholder="192.168.178.73" density="compact" variant="outlined" hide-details />
                    <v-text-field v-model="backup.nas_username" label="Benutzer" density="compact" variant="outlined" hide-details />
                    <v-text-field
                      :model-value="backupPassword"
                      @update:model-value="onBackupPasswordInput"
                      @focus="onBackupPasswordFocus"
                      @blur="onBackupPasswordBlur"
                      label="Passwort"
                      type="password"
                      autocomplete="new-password"
                      density="compact"
                      variant="outlined"
                      hide-details
                    />
                    <v-text-field v-model="backup.nas_share" label="Freigabe" placeholder="papermind-backup" density="compact" variant="outlined" hide-details />
                    <v-text-field v-model="backup.nas_folder" label="Unterordner (optional)" placeholder="papermind" density="compact" variant="outlined" hide-details />
                  </div>
                  <div class="backup-actions">
                    <v-btn variant="tonal" size="small" :loading="backupTesting" prepend-icon="mdi-lan-connect" @click="onTestBackup">
                      Verbindung testen
                    </v-btn>
                    <span
                      v-if="backupTestResult"
                      class="backup-test-result"
                      :class="backupTestResult.ok ? 'backup-test-result--ok' : 'backup-test-result--err'"
                    >
                      {{ backupTestResult.message }}
                    </span>
                    <v-spacer />
                    <v-btn color="primary" size="small" :loading="backupSaving" prepend-icon="mdi-content-save-outline" @click="saveBackup">
                      Speichern
                    </v-btn>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <!-- Backups verwalten -->
            <v-dialog v-model="backupManagerOpen" max-width="640" :persistent="restoreInProgress">
              <v-card>
                <v-card-title class="d-flex align-center">
                  <v-icon class="mr-2">mdi-folder-clock-outline</v-icon>
                  Backups verwalten
                  <v-spacer />
                  <v-btn icon="mdi-close" variant="text" size="small" :disabled="restoreInProgress" @click="backupManagerOpen = false" />
                </v-card-title>
                <v-divider />
                <v-card-text>
                  <div v-if="restoreInProgress" class="restore-progress">
                    <v-progress-circular indeterminate size="24" width="3" class="mr-3" color="primary" />
                    <div>
                      <div class="restore-progress__title">Wird wiederhergestellt …</div>
                      <div class="restore-progress__sub">Die App startet anschließend automatisch neu. Bitte dieses Fenster nicht schließen.</div>
                    </div>
                  </div>

                  <template v-else>
                    <div v-if="backupArchivesLoading" class="text-center py-6">
                      <v-progress-circular indeterminate size="28" />
                    </div>
                    <div v-else-if="backupArchivesError" class="text-error py-4">{{ backupArchivesError }}</div>
                    <div v-else-if="!backupArchives.length" class="text-medium-emphasis py-6 text-center">
                      Noch keine Backups auf dem NAS gefunden.
                    </div>
                    <v-list v-else lines="two" density="comfortable">
                      <v-list-item v-for="a in backupArchives" :key="a.name">
                        <template #prepend>
                          <v-icon :color="a.complete ? 'primary' : 'warning'">
                            {{ a.complete ? 'mdi-archive-outline' : 'mdi-alert-outline' }}
                          </v-icon>
                        </template>
                        <v-list-item-title>{{ backupFormatArchiveDate(a) }}</v-list-item-title>
                        <v-list-item-subtitle>
                          {{ backupFormatSize(a.size_bytes) }}<span v-if="!a.complete"> · unvollständig</span>
                        </v-list-item-subtitle>
                        <template #append>
                          <v-btn
                            icon="mdi-backup-restore"
                            variant="text"
                            size="small"
                            :disabled="!a.complete"
                            title="Wiederherstellen"
                            @click="askRestore(a)"
                          />
                          <v-btn
                            icon="mdi-delete-outline"
                            variant="text"
                            size="small"
                            color="error"
                            title="Löschen"
                            @click="askDeleteArchive(a)"
                          />
                        </template>
                      </v-list-item>
                    </v-list>
                  </template>
                </v-card-text>
              </v-card>
            </v-dialog>

            <!-- Restore bestätigen (Wort eintippen) -->
            <v-dialog v-model="restoreConfirmOpen" max-width="520" persistent>
              <v-card>
                <v-card-title class="text-error d-flex align-center">
                  <v-icon class="mr-2">mdi-alert</v-icon> Wiederherstellen bestätigen
                </v-card-title>
                <v-card-text>
                  <p class="mb-3">
                    Dies <strong>überschreibt die gesamte Datenbank und alle PDFs</strong> mit dem Stand vom
                    <strong>{{ restoreTarget ? backupFormatArchiveDate(restoreTarget) : '' }}</strong>.
                    Der aktuelle Stand geht verloren. Die App startet danach automatisch neu.
                  </p>
                  <p class="mb-2 text-medium-emphasis">Zum Bestätigen <code>WIEDERHERSTELLEN</code> eingeben:</p>
                  <v-text-field
                    v-model="restoreConfirmText"
                    density="compact"
                    variant="outlined"
                    hide-details
                    autofocus
                    placeholder="WIEDERHERSTELLEN"
                  />
                </v-card-text>
                <v-card-actions>
                  <v-spacer />
                  <v-btn variant="text" @click="restoreConfirmOpen = false">Abbrechen</v-btn>
                  <v-btn
                    color="error"
                    :disabled="restoreConfirmText.trim() !== 'WIEDERHERSTELLEN'"
                    :loading="restoreStarting"
                    @click="confirmRestore"
                  >
                    Wiederherstellen
                  </v-btn>
                </v-card-actions>
              </v-card>
            </v-dialog>

            <!-- Backup löschen bestätigen -->
            <v-dialog v-model="deleteArchiveOpen" max-width="460">
              <v-card>
                <v-card-title>Backup löschen?</v-card-title>
                <v-card-text>
                  Das Backup vom <strong>{{ deleteTarget ? backupFormatArchiveDate(deleteTarget) : '' }}</strong>
                  wird vom NAS entfernt. Das lässt sich nicht rückgängig machen.
                </v-card-text>
                <v-card-actions>
                  <v-spacer />
                  <v-btn variant="text" @click="deleteArchiveOpen = false">Abbrechen</v-btn>
                  <v-btn color="error" :loading="deleteArchiveBusy" @click="confirmDeleteArchive">Löschen</v-btn>
                </v-card-actions>
              </v-card>
            </v-dialog>
          </div>
        </section>

        <section v-show="activeCategory === 'controls'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-keyboard-outline"
              title="Tastaturkürzel"
              subtitle="Verfügbare Tastenkürzel und Mausgesten in PaperMind."
            />

            <div class="shortcuts-list">
                <div
                  v-for="group in shortcutGroups"
                  :key="group.label"
                  class="shortcuts-list__group"
                >
                  <div class="shortcuts-list__group-label">{{ group.label }}</div>
                  <div class="shortcuts-list__rows">
                    <div
                      v-for="item in group.items"
                      :key="item.action"
                      class="shortcuts-list__row"
                    >
                      <span class="shortcuts-list__desc">{{ item.description }}</span>
                      <span class="shortcuts-list__keys">
                        <kbd
                          v-for="key in item.keys"
                          :key="key"
                          class="shortcuts-list__kbd"
                        >{{ formatKey(key) }}</kbd>
                      </span>
                    </div>
                  </div>
                </div>

                <div class="shortcuts-list__group">
                  <div class="shortcuts-list__group-label">Mausgesten</div>
                  <div class="shortcuts-list__rows">
                    <div
                      v-for="item in mouseGestures"
                      :key="item.description"
                      class="shortcuts-list__row"
                    >
                      <span class="shortcuts-list__desc">{{ item.description }}</span>
                      <span class="shortcuts-list__keys">
                        <kbd class="shortcuts-list__kbd">{{ item.gesture }}</kbd>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
          </div>
        </section>

        <section v-show="activeCategory === 'system'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SystemStatusPanel :active="activeCategory === 'system'" />
          </div>
        </section>
        </div>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useTheme } from 'vuetify';
import BaseDialog from './BaseDialog.vue';
import SettingsInfoCard from './SettingsInfoCard.vue';
import SystemStatusPanel from './SystemStatusPanel.vue';
import { getBaseUrl } from '../api/client';
import { useAuthStore } from '../stores/auth';
import { useSettingsStore } from '../stores/settings';
import { useCategoryStore } from '../stores/categories';
import { useCorrespondentStore } from '../stores/correspondents';
import { notifyError, useNotifications } from '../stores/notifications';
import { useTagStore } from '../stores/tags';
import { cleanupUnusedTags } from '../api/tags';
import { backfillOcr, patchDocument as apiPatchDocument } from '../api/documents';
import {
  deleteBackupArchive,
  getBackupStatus,
  getRestoreStatus,
  listBackupArchives,
  restoreBackup,
  runBackupNow,
  testBackupConnection,
  updateBackupConfig,
} from '../api/backup';
import {
  ignoreUnresolvedCorrespondent as apiIgnoreUnresolvedCorrespondent,
  listUnresolvedCorrespondents as apiListUnresolvedCorrespondents
} from '../api/correspondents';
import { SHORTCUT_ACTIONS, SHORTCUTS, handleShortcut } from '../keyboard/shortcuts';
import {
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildOcrBackfillEnabledPatch,
  buildColorVariantPatch,
  buildGlassEnabledPatch,
  buildDrawerRememberStatePatch,
  buildTagDrawerRememberStatePatch,
  buildOcrDocLangPatch,
  buildRecentImportWindowPatch,
  buildShowFilenameSuffixPatch,
  buildSidebarSectionsPatch,
  buildSidebarMaxTagsPatch,
  buildSidebarMaxCategoriesPatch,
  buildThemeModePatch,
  buildTrashRetentionPatch,
  normalizeSidebarSections,
  sidebarSectionLabel
} from '../utils/settingsApi';

// ── Props / Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialCategory: { type: String, default: 'appearance' }
});

const emit = defineEmits(['update:modelValue', 'reload-imports']);

// ── Stores / Theme ───────────────────────────────────────────────────────────

const theme = useTheme();
const auth = useAuthStore();
const settingsStore = useSettingsStore();
const categoryStore = useCategoryStore();
const correspondentStore = useCorrespondentStore();

const VOCAB_NAME_MAX_LENGTH = 30;
const tagStore = useTagStore();
const { notify } = useNotifications();
const settingsDraft = settingsStore.settingsDraft;
const isSettingSaving = settingsStore.isSettingSaving;

// ── Unbenutzte Tags aufräumen ────────────────────────────────────────────────
const tagCleanupLoading = ref(false);
// null = nichts angefragt; sonst { count, tags: [{id,name}] } aus der Vorschau (dry_run)
const unusedTagsPreview = ref(null);

async function loadUnusedTagsPreview() {
  tagCleanupLoading.value = true;
  try {
    unusedTagsPreview.value = await cleanupUnusedTags(true);
  } catch (error) {
    notifyError(error, 'Unbenutzte Tags konnten nicht ermittelt werden.');
  } finally {
    tagCleanupLoading.value = false;
  }
}

async function confirmTagCleanup() {
  tagCleanupLoading.value = true;
  try {
    const result = await cleanupUnusedTags(false);
    const removed = Number(result?.removed ?? 0);
    unusedTagsPreview.value = null;
    await tagStore.fetchTags();
    notify({
      type: 'success',
      message: `${removed} unbenutzte${removed === 1 ? 's Tag' : ' Tags'} entfernt.`,
      critical: true
    });
  } catch (error) {
    notifyError(error, 'Unbenutzte Tags konnten nicht entfernt werden.');
  } finally {
    tagCleanupLoading.value = false;
  }
}

// ── OCR-Lücken jetzt schließen ───────────────────────────────────────────────
const ocrBackfillLoading = ref(false);

async function runOcrBackfillNow() {
  ocrBackfillLoading.value = true;
  try {
    const result = await backfillOcr({ dryRun: false });
    const queued = Number(result?.queued ?? 0);
    if (queued > 0) {
      notify({
        type: 'success',
        message: `${queued} Dokument${queued === 1 ? '' : 'e'} zur Texterkennung eingereiht.`
      });
    } else {
      notify({ type: 'info', message: 'Keine Dokumente ohne Texterkennung gefunden. 🎉' });
    }
  } catch (error) {
    notifyError(error, 'OCR-Lücken konnten nicht geschlossen werden.');
  } finally {
    ocrBackfillLoading.value = false;
  }
}

const isSettingsLoading = computed(() => settingsStore.isSettingsLoading);
const animationsEnabled = computed(() => settingsStore.animationsEnabled);

const currentColorVariant = computed(() => settingsStore.settingsDraft.ui.color_variant || 'teal');

// ── Einstellungsnavigation ───────────────────────────────────────────────────

const settingsCategories = [
  { value: 'appearance', label: 'Darstellung', icon: 'mdi-palette-outline' },
  { value: 'sidebar', label: 'Seitenleiste', icon: 'mdi-page-layout-sidebar-left' },
  { value: 'documents', label: 'Dokumente', icon: 'mdi-file-document-outline', adminOnly: true },
  { value: 'categories', label: 'Dokumenttypen', icon: 'mdi-file-document-multiple-outline' },
  { value: 'correspondents', label: 'Korrespondenten', icon: 'mdi-account-outline' },
  { value: 'ai', label: 'Texterkennung', icon: 'mdi-text-recognition', adminOnly: true },
  { value: 'backup', label: 'Backup', icon: 'mdi-cloud-upload-outline', adminOnly: true },
  { value: 'controls', label: 'Bedienung', icon: 'mdi-keyboard-outline' },
  { value: 'system', label: 'System', icon: 'mdi-raspberry-pi', adminOnly: true }
];
// Systemkonfigurations-Tabs nur für Admins; persönliche Darstellung sowie die
// Pro-Benutzer-Daten (Dokumenttypen/Korrespondenten) und die Kürzel-Referenz
// bleiben für alle sichtbar.
const visibleCategories = computed(() =>
  settingsCategories.filter((cat) => !cat.adminOnly || auth.isAdmin)
);

const activeCategory = ref('appearance');

// ── Backup ───────────────────────────────────────────────────────────────────
const backup = ref({
  enabled: false, nas_host: '', nas_share: '', nas_folder: '', nas_username: '',
  nas_password_set: false, frequency: 'daily', time: '03:00', weekday: 6, retention: 7,
});
const BACKUP_PW_MASK = '••••••••';
const backupPassword = ref('');
const backupPasswordDirty = ref(false);
const backupStatus = ref({ last_run: null, next_run_at: null, last_success_at: null, is_running: false });
const backupSaving = ref(false);
const backupTesting = ref(false);
const backupRunning = ref(false);
const backupTestResult = ref(null);
const backupSetupOpen = ref(undefined); // Index des offenen Panels (0) oder undefined
let backupSetupInitialized = false;
let backupPollTimer = 0;

// Backups verwalten / Wiederherstellen
const backupManagerOpen = ref(false);
const backupArchives = ref([]);
const backupArchivesLoading = ref(false);
const backupArchivesError = ref('');
const restoreConfirmOpen = ref(false);
const restoreTarget = ref(null);
const restoreConfirmText = ref('');
const restoreStarting = ref(false);
const restoreInProgress = ref(false);
let restorePollTimer = 0;
const deleteArchiveOpen = ref(false);
const deleteTarget = ref(null);
const deleteArchiveBusy = ref(false);

const backupWeekdayItems = [
  { title: 'Montag', value: 0 }, { title: 'Dienstag', value: 1 }, { title: 'Mittwoch', value: 2 },
  { title: 'Donnerstag', value: 3 }, { title: 'Freitag', value: 4 }, { title: 'Samstag', value: 5 },
  { title: 'Sonntag', value: 6 },
];

function backupFormatDate(value) {
  if (!value) return '';
  try { return new Date(value).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return String(value); }
}
function backupFormatBytes(n) {
  let v = Number(n) || 0;
  if (v < 1024) return `${v} B`;
  const units = ['KB', 'MB', 'GB']; let i = 0; v /= 1024;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(1).replace('.', ',')} ${units[i]}`;
}
function backupRelativeTime(value) {
  if (!value) return '';
  const ts = new Date(value).getTime();
  if (Number.isNaN(ts)) return String(value);
  const min = Math.round((Date.now() - ts) / 60000);
  if (min < 1) return 'gerade eben';
  if (min < 60) return `vor ${min} Min`;
  const h = Math.round(min / 60);
  if (h < 24) return `vor ${h} Std`;
  const days = Math.round(h / 24);
  if (days < 30) return `vor ${days} Tg`;
  return backupFormatDate(value);
}

const backupStatusKind = computed(() => {
  const s = backupStatus.value;
  if (s.is_running) return 'running';
  if (s.last_run?.status === 'failed') return 'error';
  if (s.last_run?.status === 'success') return 'ok';
  return 'idle';
});
// Sofort nach dem Klick aktiv (client-seitig), bis der Server-Lauf endet – damit das
// Karten-Icon ohne Verzögerung dreht, auch bevor der erste Status-Poll „is_running" meldet.
const backupBusy = computed(() => backupRunning.value || backupStatus.value.is_running);
const backupLastLabel = computed(() => {
  const s = backupStatus.value;
  if (backupBusy.value) return 'Sicherung gestartet …';
  const r = s.last_run;
  if (!r) return 'Noch nie gesichert';
  const when = backupRelativeTime(r.finished_at || r.started_at);
  if (r.status === 'success') return `${when}${r.size_bytes ? ' · ' + backupFormatBytes(r.size_bytes) : ''}`;
  return when;
});
const backupNextLabel = computed(() =>
  backup.value.enabled ? (backupFormatDate(backupStatus.value.next_run_at) || '—') : 'deaktiviert');

// Optik der Status-Karte (deaktiviert hat Vorrang vor dem letzten Lauf)
const backupCardKind = computed(() => {
  if (!backup.value.enabled) return 'disabled';
  return backupBusy.value ? 'running' : backupStatusKind.value;
});
const backupStatusIcon = computed(() => {
  switch (backupStatusKind.value) {
    case 'ok': return 'mdi-check-circle';
    case 'error': return 'mdi-alert-circle';
    default: return 'mdi-cloud-outline';
  }
});
const backupStateLabel = computed(() => {
  if (!backup.value.enabled) return 'Backup deaktiviert';
  if (backupBusy.value) return 'Backup läuft';
  switch (backupStatusKind.value) {
    case 'ok': return 'Gesichert';
    case 'error': return 'Letzte Sicherung fehlgeschlagen';
    default: return 'Aktiv – noch keine Sicherung';
  }
});

// Zusammenfassung für das eingeklappte Einrichtungs-Panel
const backupConfigured = computed(() => !!(backup.value.nas_host && backup.value.nas_share));
const backupConnectionSummary = computed(() => {
  const b = backup.value;
  if (!b.nas_host) return '';
  const user = b.nas_username ? `${b.nas_username}@` : '';
  const path = [b.nas_share, b.nas_folder].filter(Boolean).join('/');
  return `${user}${b.nas_host}${path ? ' · ' + path : ''}`;
});
const backupSetupSummary = computed(() => {
  if (!backupConfigured.value) return 'Tippen, um die Verbindung einzurichten';
  return backupConnectionSummary.value;
});

function applyBackupStatus(data) {
  const cfg = data?.config || {};
  backup.value = {
    enabled: !!cfg.enabled,
    nas_host: cfg.nas_host || '', nas_share: cfg.nas_share || '', nas_folder: cfg.nas_folder || '',
    nas_username: cfg.nas_username || '', nas_password_set: !!cfg.nas_password_set,
    frequency: cfg.frequency || 'daily', time: cfg.time || '03:00',
    weekday: typeof cfg.weekday === 'number' ? cfg.weekday : 6,
    retention: cfg.retention || 7,
  };
  backupStatus.value = {
    last_run: data?.last_run || null, next_run_at: data?.next_run_at || null,
    last_success_at: data?.last_success_at || null, is_running: !!data?.is_running,
  };
  // Gespeichertes Passwort als Punkte darstellen; Feld bleibt "gefüllt".
  backupPasswordDirty.value = false;
  backupPassword.value = backup.value.nas_password_set ? BACKUP_PW_MASK : '';
  // Einrichtung beim ersten Laden automatisch aufklappen, falls noch nichts konfiguriert
  // ist – danach steuert der Nutzer das Panel selbst (nicht bei jedem Poll überschreiben).
  if (!backupSetupInitialized) {
    backupSetupOpen.value = backupConfigured.value ? undefined : 0;
    backupSetupInitialized = true;
  }
}

function onBackupPasswordInput(value) {
  backupPassword.value = value;
  backupPasswordDirty.value = true;
}

function onBackupPasswordFocus() {
  // Beim Bearbeiten die Maske leeren, damit ein neues Passwort sauber eingegeben wird.
  if (!backupPasswordDirty.value && backupPassword.value === BACKUP_PW_MASK) {
    backupPassword.value = '';
  }
}

function onBackupPasswordBlur() {
  // Ohne Eingabe die Maske wiederherstellen – gespeichertes Passwort bleibt erhalten.
  if (!backupPasswordDirty.value && !backupPassword.value && backup.value.nas_password_set) {
    backupPassword.value = BACKUP_PW_MASK;
  }
}

async function loadBackup() {
  try { applyBackupStatus(await getBackupStatus()); }
  catch { /* Status optional */ }
}

function backupConfigPayload() {
  const b = backup.value;
  const payload = {
    enabled: b.enabled, nas_host: b.nas_host, nas_share: b.nas_share, nas_folder: b.nas_folder,
    nas_username: b.nas_username, frequency: b.frequency, time: b.time, weekday: b.weekday,
    retention: Number(b.retention) || 7,
  };
  if (backupPasswordDirty.value && backupPassword.value && backupPassword.value !== BACKUP_PW_MASK) {
    payload.nas_password = backupPassword.value;
  }
  return payload;
}

async function saveBackup() {
  backupSaving.value = true;
  try {
    applyBackupStatus(await updateBackupConfig(backupConfigPayload()));
    notify({ type: 'success', title: 'Backup', message: 'Einstellungen gespeichert.' });
  } catch (error) {
    notifyError(error, 'Backup-Einstellungen konnten nicht gespeichert werden.');
  } finally {
    backupSaving.value = false;
  }
}

async function onToggleBackup(value) {
  backup.value.enabled = value;
  await saveBackup();
}

async function onTestBackup() {
  await saveBackup();
  backupTesting.value = true;
  backupTestResult.value = null;
  try {
    backupTestResult.value = await testBackupConnection();
  } catch {
    backupTestResult.value = { ok: false, message: 'Test fehlgeschlagen.' };
  } finally {
    backupTesting.value = false;
  }
}

async function onRunBackup() {
  backupRunning.value = true;
  try {
    const res = await runBackupNow();
    notify({
      type: res.started ? 'success' : 'info',
      title: 'Backup',
      message: res.message || (res.started ? 'Backup gestartet.' : 'Läuft bereits.'),
    });
    let ticks = 0;
    if (backupPollTimer) window.clearInterval(backupPollTimer);
    backupPollTimer = window.setInterval(async () => {
      await loadBackup();
      ticks += 1;
      if (!backupStatus.value.is_running || ticks > 60) {
        window.clearInterval(backupPollTimer);
        backupPollTimer = 0;
        backupRunning.value = false;
      }
    }, 3000);
  } catch (error) {
    notifyError(error, 'Backup konnte nicht gestartet werden.');
    backupRunning.value = false;
  }
}

// ── Backups verwalten / Wiederherstellen ────────────────────────────────────
function backupFormatSize(bytes) {
  const b = Number(bytes) || 0;
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(0)} MB`;
  if (b >= 1e3) return `${(b / 1e3).toFixed(0)} KB`;
  return `${b} B`;
}

function backupFormatArchiveDate(a) {
  if (a?.created_at) return backupFormatDate(a.created_at);
  return a?.name || '';
}

async function loadBackupArchives() {
  backupArchivesLoading.value = true;
  backupArchivesError.value = '';
  try {
    const res = await listBackupArchives();
    backupArchives.value = res?.items || [];
  } catch (error) {
    backupArchivesError.value = error?.message || 'Backups konnten nicht geladen werden.';
    backupArchives.value = [];
  } finally {
    backupArchivesLoading.value = false;
  }
}

function openBackupManager() {
  backupManagerOpen.value = true;
  loadBackupArchives();
}

function askRestore(a) {
  restoreTarget.value = a;
  restoreConfirmText.value = '';
  restoreConfirmOpen.value = true;
}

async function confirmRestore() {
  if (!restoreTarget.value) return;
  restoreStarting.value = true;
  try {
    const res = await restoreBackup(restoreTarget.value.name);
    if (!res?.started) {
      notify({ type: 'info', title: 'Wiederherstellung', message: res?.message || 'Konnte nicht gestartet werden.' });
      return;
    }
    restoreConfirmOpen.value = false;
    restoreInProgress.value = true;
    watchRestoreUntilRestart();
  } catch (error) {
    notifyError(error, 'Wiederherstellung konnte nicht gestartet werden.');
  } finally {
    restoreStarting.value = false;
  }
}

function watchRestoreUntilRestart() {
  let seenDown = false;
  let ticks = 0;
  if (restorePollTimer) window.clearInterval(restorePollTimer);
  restorePollTimer = window.setInterval(async () => {
    ticks += 1;
    try {
      const st = await getRestoreStatus();
      if (st?.status === 'failed') {
        window.clearInterval(restorePollTimer);
        restorePollTimer = 0;
        restoreInProgress.value = false;
        notifyError(new Error(st.error || 'Unbekannter Fehler'), 'Wiederherstellung fehlgeschlagen.');
        loadBackupArchives();
        return;
      }
      // Erfolgreicher Request nach einem Ausfall ⇒ Backend ist neu gestartet ⇒ fertig.
      if (seenDown) {
        window.clearInterval(restorePollTimer);
        restorePollTimer = 0;
        window.location.reload();
      }
    } catch {
      seenDown = true; // Backend gerade nicht erreichbar (Neustart läuft)
    }
    if (ticks > 90) {
      window.clearInterval(restorePollTimer);
      restorePollTimer = 0;
      window.location.reload();
    }
  }, 2000);
}

function askDeleteArchive(a) {
  deleteTarget.value = a;
  deleteArchiveOpen.value = true;
}

async function confirmDeleteArchive() {
  if (!deleteTarget.value) return;
  deleteArchiveBusy.value = true;
  try {
    await deleteBackupArchive(deleteTarget.value.name);
    deleteArchiveOpen.value = false;
    notify({ type: 'success', title: 'Backup', message: 'Backup gelöscht.' });
    await loadBackupArchives();
    await loadBackup();
  } catch (error) {
    notifyError(error, 'Backup konnte nicht gelöscht werden.');
  } finally {
    deleteArchiveBusy.value = false;
  }
}

watch(activeCategory, (value) => {
  if (value === 'backup') {
    backupSetupInitialized = false; // Panel-Zustand beim Betreten neu bestimmen
    loadBackup();
  }
});

// ── Tastaturkürzel (Bereich „Bedienung") ─────────────────────────────────────

const KEY_LABELS = {
  'Enter': '↵ Enter',
  ' ': 'Leertaste',
  'Escape': 'Esc',
  'Backspace': '⌫ Backspace',
  'ArrowLeft': '←',
  'ArrowRight': '→',
  'ArrowUp': '↑',
  'ArrowDown': '↓',
  '?': '?'
};

function formatKey(key) {
  return KEY_LABELS[key] ?? key;
}

function keysFor(action) {
  return SHORTCUTS[action]?.keys ?? [];
}

const shortcutGroups = [
  {
    label: 'Allgemein',
    items: [
      { action: SHORTCUT_ACTIONS.HELP,   description: 'Tastaturkürzel anzeigen', keys: keysFor(SHORTCUT_ACTIONS.HELP) },
      { action: SHORTCUT_ACTIONS.CANCEL, description: 'Dialog / Auswahl schließen', keys: keysFor(SHORTCUT_ACTIONS.CANCEL) }
    ]
  },
  {
    label: 'Suche',
    items: [
      { action: SHORTCUT_ACTIONS.SEARCH_SUBMIT, description: 'Suche bestätigen', keys: keysFor(SHORTCUT_ACTIONS.SEARCH_SUBMIT) },
      { action: SHORTCUT_ACTIONS.SEARCH_CANCEL, description: 'Suche abbrechen',  keys: keysFor(SHORTCUT_ACTIONS.SEARCH_CANCEL) }
    ]
  },
  {
    label: 'Navigation',
    items: [
      { action: SHORTCUT_ACTIONS.MOVE_PREVIOUS, description: 'Vorheriges Element', keys: keysFor(SHORTCUT_ACTIONS.MOVE_PREVIOUS) },
      { action: SHORTCUT_ACTIONS.MOVE_NEXT,     description: 'Nächstes Element',   keys: keysFor(SHORTCUT_ACTIONS.MOVE_NEXT) },
      { action: SHORTCUT_ACTIONS.STEP_PREVIOUS, description: 'Schritt zurück',     keys: keysFor(SHORTCUT_ACTIONS.STEP_PREVIOUS) },
      { action: SHORTCUT_ACTIONS.STEP_NEXT,     description: 'Schritt vor',        keys: keysFor(SHORTCUT_ACTIONS.STEP_NEXT) }
    ]
  },
  {
    label: 'Aktionen',
    items: [
      { action: SHORTCUT_ACTIONS.TRASH,    description: 'Selektiertes Dokument in den Papierkorb', keys: keysFor(SHORTCUT_ACTIONS.TRASH) },
      { action: SHORTCUT_ACTIONS.ACTIVATE, description: 'Element aktivieren / auswählen',           keys: keysFor(SHORTCUT_ACTIONS.ACTIVATE) },
      { action: SHORTCUT_ACTIONS.PRIMARY,  description: 'Primäre Aktion bestätigen',                keys: keysFor(SHORTCUT_ACTIONS.PRIMARY) }
    ]
  }
];

const mouseGestures = [
  { description: 'Auswahlmodus aktivieren & Dokument selektieren', gesture: '⌘ Cmd + Klick' }
];

// ── Konstanten ───────────────────────────────────────────────────────────────

const themeModeOptions = [
  { label: 'Hell', value: 'light' },
  { label: 'Dunkel', value: 'dark' },
  { label: 'System', value: 'system' }
];

const recentImportWindowOptions = [
  { label: '1 Stunde', value: 1 },
  { label: '6 Stunden', value: 6 },
  { label: '24 Stunden', value: 24 },
  { label: '3 Tage', value: 72 },
  { label: '7 Tage', value: 168 }
];

const trashRetentionOptions = [
  { label: 'Nie automatisch', value: 0 },
  { label: 'Nach 1 Tag', value: 1 },
  { label: 'Nach 7 Tagen', value: 7 },
  { label: 'Nach 14 Tagen', value: 14 },
  { label: 'Nach 30 Tagen', value: 30 },
  { label: 'Nach 90 Tagen', value: 90 }
];


const THEME_MODE_VALUES = new Set(['light', 'dark', 'system']);
const COLOR_VARIANT_VALUES = new Set(['teal', 'violet', 'blue']);
const RECENT_IMPORT_WINDOW_VALUES = new Set(recentImportWindowOptions.map((e) => e.value));
const TRASH_RETENTION_VALUES = new Set(trashRetentionOptions.map((e) => e.value));

const ocrDocLangOptions = [
  { title: 'Deutsch (Standard)', value: 'de' },
  { title: 'Englisch', value: 'en' },
  { title: 'Automatisch erkennen', value: 'auto' },
  { title: 'Mehrsprachig', value: 'multi' }
];

const OCR_DOC_LANG_VALUES = new Set(ocrDocLangOptions.map((e) => e.value));


// ── Theme ────────────────────────────────────────────────────────────────────

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(mode) {
  theme.global.name.value = resolveThemeName(mode);
}

// ── Shared save helper ───────────────────────────────────────────────────────

async function patchSettingsWithRevert({ patch, controlKey, revert }) {
  try {
    const saved = await settingsStore.saveSettingPatch(getBaseUrl(), { patch, controlKey });
    return saved !== false;
  } catch (error) {
    if (typeof revert === 'function') revert();
    notifyError(error, 'Konnte Einstellung nicht speichern.');
    return false;
  }
}

// ── Theme-Modus ──────────────────────────────────────────────────────────────

function stepThemeMode(step) {
  const ordered = themeModeOptions.map((e) => e.value);
  const currentIndex = ordered.indexOf(settingsDraft.ui.theme_mode);
  const safeIndex = currentIndex >= 0 ? currentIndex : 0;
  const nextIndex = (safeIndex + step + ordered.length) % ordered.length;
  void onThemeModeChange(ordered[nextIndex]);
}

function handleThemeModeShortcut(event) {
  if (handleShortcut(event, SHORTCUT_ACTIONS.STEP_PREVIOUS, () => stepThemeMode(-1), { ignoreEditable: false })) {
    return;
  }
  handleShortcut(event, SHORTCUT_ACTIONS.STEP_NEXT, () => stepThemeMode(1), { ignoreEditable: false });
}

function handleSettingRowShortcut(event, handler) {
  handleShortcut(event, SHORTCUT_ACTIONS.ACTIVATE, handler, { ignoreEditable: false });
}

async function onThemeModeChange(nextValue) {
  if (isSettingSaving.theme_mode) return;
  const nextMode = THEME_MODE_VALUES.has(String(nextValue)) ? String(nextValue) : 'system';
  if (nextMode === settingsDraft.ui.theme_mode) return;
  const previousMode = settingsDraft.ui.theme_mode;
  settingsStore.setDraftPatch({ ui: { theme_mode: nextMode } });
  applyTheme(nextMode);
  await patchSettingsWithRevert({
    patch: buildThemeModePatch(nextMode),
    controlKey: 'theme_mode',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { theme_mode: previousMode } });
      applyTheme(previousMode);
    }
  });
}

// ── Farbvariante ─────────────────────────────────────────────────────────────

const colorVariantOptions = [
  { label: 'Teal', value: 'teal', color: '#0891B2' },
  { label: 'Violett', value: 'violet', color: '#7C3AED' },
  { label: 'Blau', value: 'blue', color: '#2563EB' }
];

async function onColorVariantChange(nextValue) {
  if (isSettingSaving.color_variant) return;
  const nextVariant = COLOR_VARIANT_VALUES.has(String(nextValue)) ? String(nextValue) : 'teal';
  if (nextVariant === currentColorVariant.value) return;
  const previousVariant = currentColorVariant.value;
  settingsStore.setDraftPatch({ ui: { color_variant: nextVariant } });
  await patchSettingsWithRevert({
    patch: buildColorVariantPatch(nextVariant),
    controlKey: 'color_variant',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { color_variant: previousVariant } });
    }
  });
}

// ── Seitenleiste (Reihenfolge & Sichtbarkeit) ────────────────────────────────

const SIDEBAR_SECTION_ICONS = {
  ordner: 'mdi-folder-outline',
  tags: 'mdi-tag-multiple-outline',
  kategorien: 'mdi-file-document-multiple-outline'
};

function sidebarSectionIcon(key) {
  return SIDEBAR_SECTION_ICONS[key] || 'mdi-shape-outline';
}

const sidebarSectionsDraft = computed(() => normalizeSidebarSections(settingsDraft.ui.sidebar_sections));

async function persistSidebarSections(nextSections) {
  if (isSettingSaving.sidebar_sections) return;
  const previous = normalizeSidebarSections(settingsDraft.ui.sidebar_sections);
  const normalized = normalizeSidebarSections(nextSections);
  settingsStore.setDraftPatch({ ui: { sidebar_sections: normalized } });
  await patchSettingsWithRevert({
    patch: buildSidebarSectionsPatch(normalized),
    controlKey: 'sidebar_sections',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { sidebar_sections: previous } });
    }
  });
}

function moveSidebarSection(index, delta) {
  const sections = normalizeSidebarSections(settingsDraft.ui.sidebar_sections);
  const target = index + delta;
  if (target < 0 || target >= sections.length) return;
  const next = [...sections];
  [next[index], next[target]] = [next[target], next[index]];
  void persistSidebarSections(next);
}

function setSidebarSectionVisibility(key, visible) {
  const sections = normalizeSidebarSections(settingsDraft.ui.sidebar_sections);
  const next = sections.map((section) => (
    section.key === key ? { ...section, visible: Boolean(visible) } : section
  ));
  void persistSidebarSections(next);
}

const sidebarMaxOptions = [
  { label: 'Keine', value: 0 },
  { label: '3', value: 3 },
  { label: '5', value: 5 },
  { label: '8', value: 8 },
  { label: '10', value: 10 },
  { label: '15', value: 15 },
  { label: '20', value: 20 },
  { label: 'Alle', value: 50 }
];

function clampSidebarMaxCount(value) {
  const parsed = Math.round(Number(value));
  if (!Number.isFinite(parsed)) return 5;
  return Math.min(50, Math.max(0, parsed));
}

async function onSidebarMaxTagsChange(nextValue) {
  if (isSettingSaving.sidebar_max_tags) return;
  const next = clampSidebarMaxCount(nextValue);
  const previous = settingsDraft.ui.sidebar_max_tags;
  if (next === previous) return;
  settingsStore.setDraftPatch({ ui: { sidebar_max_tags: next } });
  await patchSettingsWithRevert({
    patch: buildSidebarMaxTagsPatch(next),
    controlKey: 'sidebar_max_tags',
    revert: () => settingsStore.setDraftPatch({ ui: { sidebar_max_tags: previous } })
  });
}

async function onSidebarMaxCategoriesChange(nextValue) {
  if (isSettingSaving.sidebar_max_categories) return;
  const next = clampSidebarMaxCount(nextValue);
  const previous = settingsDraft.ui.sidebar_max_categories;
  if (next === previous) return;
  settingsStore.setDraftPatch({ ui: { sidebar_max_categories: next } });
  await patchSettingsWithRevert({
    patch: buildSidebarMaxCategoriesPatch(next),
    controlKey: 'sidebar_max_categories',
    revert: () => settingsStore.setDraftPatch({ ui: { sidebar_max_categories: previous } })
  });
}

// ── Auto-OCR ─────────────────────────────────────────────────────────────────

async function onAutoOcrChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_ocr) return;
  const previous = settingsDraft.documents.auto_ocr;
  settingsStore.setDraftPatch({ documents: { auto_ocr: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoOcrPatch(nextBool),
    controlKey: 'auto_ocr',
    revert: () => settingsStore.setDraftPatch({ documents: { auto_ocr: previous } })
  });
}

function toggleAutoOcrFromRow() {
  if (isSettingSaving.auto_ocr) return;
  void onAutoOcrChange(!settingsDraft.documents.auto_ocr);
}

async function onOcrBackfillEnabledChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.ocr_backfill_enabled) return;
  const previous = settingsDraft.documents.ocr_backfill_enabled;
  settingsStore.setDraftPatch({ documents: { ocr_backfill_enabled: nextBool } });
  await patchSettingsWithRevert({
    patch: buildOcrBackfillEnabledPatch(nextBool),
    controlKey: 'ocr_backfill_enabled',
    revert: () => settingsStore.setDraftPatch({ documents: { ocr_backfill_enabled: previous } })
  });
}

function toggleOcrBackfillFromRow() {
  if (isSettingSaving.ocr_backfill_enabled) return;
  void onOcrBackfillEnabledChange(!settingsDraft.documents.ocr_backfill_enabled);
}

// ── Ollama ───────────────────────────────────────────────────────────────────

const showOllamaAdvanced = ref(false);

const ollamaModelPresets = [
  'llama3.2:1b',
  'llama3.2:3b',
  'llama3.1:8b',
  'phi3.5:mini',
  'mistral:7b',
  'gemma2:2b',
];

const ollamaChatModelPresets = [
  'llama3.2:3b',
  'qwen2.5:3b',
  'qwen2.5:7b',
  'llama3.1:8b',
  'gemma2:2b',
];

const ollamaMaxCharsOptions = [
  { label: '400 Zeichen (sehr schnell)', value: 400 },
  { label: '800 Zeichen (empfohlen)', value: 800 },
  { label: '1600 Zeichen (detaillierter)', value: 1600 },
  { label: '3200 Zeichen (langsam)', value: 3200 },
];

async function onOllamaEnabledChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ollama.enabled) return;
  const previous = settingsDraft.ollama.enabled;
  settingsStore.setDraftPatch({ ollama: { enabled: nextBool } });
  await patchSettingsWithRevert({
    patch: { ollama: { enabled: nextBool } },
    controlKey: 'ollama_enabled',
    revert: () => settingsStore.setDraftPatch({ ollama: { enabled: previous } })
  });
}

function toggleOllamaEnabledFromRow() {
  if (isSettingSaving.ollama_enabled) return;
  void onOllamaEnabledChange(!settingsDraft.ollama.enabled);
}

async function onOllamaBaseUrlChange(nextValue) {
  const url = String(nextValue || '').trim() || 'http://localhost:11434';
  if (url === settingsDraft.ollama.base_url) return;
  const previous = settingsDraft.ollama.base_url;
  settingsStore.setDraftPatch({ ollama: { base_url: url } });
  await patchSettingsWithRevert({
    patch: { ollama: { base_url: url } },
    controlKey: 'ollama_base_url',
    revert: () => settingsStore.setDraftPatch({ ollama: { base_url: previous } })
  });
}

async function onOllamaModelChange(nextValue) {
  const model = String(nextValue || '').trim() || 'llama3.2:3b';
  if (model === settingsDraft.ollama.model) return;
  const previous = settingsDraft.ollama.model;
  settingsStore.setDraftPatch({ ollama: { model } });
  await patchSettingsWithRevert({
    patch: { ollama: { model } },
    controlKey: 'ollama_model',
    revert: () => settingsStore.setDraftPatch({ ollama: { model: previous } })
  });
}

async function onOllamaChatModelChange(nextValue) {
  const chatModel = String(nextValue || '').trim() || 'llama3.2:3b';
  if (chatModel === settingsDraft.ollama.chat_model) return;
  const previous = settingsDraft.ollama.chat_model;
  settingsStore.setDraftPatch({ ollama: { chat_model: chatModel } });
  await patchSettingsWithRevert({
    patch: { ollama: { chat_model: chatModel } },
    controlKey: 'ollama_chat_model',
    revert: () => settingsStore.setDraftPatch({ ollama: { chat_model: previous } })
  });
}

async function onOllamaMaxInputCharsChange(nextValue) {
  const chars = Number(nextValue) || 800;
  if (chars === settingsDraft.ollama.max_input_chars) return;
  const previous = settingsDraft.ollama.max_input_chars;
  settingsStore.setDraftPatch({ ollama: { max_input_chars: chars } });
  await patchSettingsWithRevert({
    patch: { ollama: { max_input_chars: chars } },
    controlKey: 'ollama_max_input_chars',
    revert: () => settingsStore.setDraftPatch({ ollama: { max_input_chars: previous } })
  });
}

// ── Auto-Tagging ─────────────────────────────────────────────────────────────

async function onAutoTaggingChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_tagging) return;
  const previous = settingsDraft.documents.auto_tagging;
  settingsStore.setDraftPatch({ documents: { auto_tagging: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoTaggingPatch(nextBool),
    controlKey: 'auto_tagging',
    revert: () => settingsStore.setDraftPatch({ documents: { auto_tagging: previous } })
  });
}

function toggleAutoTaggingFromRow() {
  if (isSettingSaving.auto_tagging) return;
  // Abhängigkeit: KI-Analyse benötigt Automatisches OCR.
  if (!settingsDraft.documents.auto_ocr) return;
  void onAutoTaggingChange(!settingsDraft.documents.auto_tagging);
}

// ── Import-Zeitraum ──────────────────────────────────────────────────────────

async function onRecentImportWindowChange(nextValue) {
  if (isSettingSaving.recent_import_window_hours) return;
  const parsedHours = Number(nextValue);
  const nextHours = RECENT_IMPORT_WINDOW_VALUES.has(parsedHours)
    ? parsedHours
    : settingsDraft.documents.recent_import_window_hours;
  if (nextHours === settingsDraft.documents.recent_import_window_hours) return;
  const previous = settingsDraft.documents.recent_import_window_hours;
  settingsStore.setDraftPatch({ documents: { recent_import_window_hours: nextHours } });
  const saved = await patchSettingsWithRevert({
    patch: buildRecentImportWindowPatch(nextHours),
    controlKey: 'recent_import_window_hours',
    revert: () => settingsStore.setDraftPatch({ documents: { recent_import_window_hours: previous } })
  });
  if (saved) {
    emit('reload-imports');
  }
}

// ── Papierkorb-Aufbewahrung ────────────────────────────────────────────────

async function onTrashRetentionChange(nextValue) {
  if (isSettingSaving.trash_retention_days) return;
  const parsedDays = Number(nextValue);
  const nextDays = TRASH_RETENTION_VALUES.has(parsedDays)
    ? parsedDays
    : settingsDraft.documents.trash_retention_days;
  if (nextDays === settingsDraft.documents.trash_retention_days) return;
  const previous = settingsDraft.documents.trash_retention_days;
  settingsStore.setDraftPatch({ documents: { trash_retention_days: nextDays } });
  await patchSettingsWithRevert({
    patch: buildTrashRetentionPatch(nextDays),
    controlKey: 'trash_retention_days',
    revert: () => settingsStore.setDraftPatch({ documents: { trash_retention_days: previous } })
  });
}

// ── OCR-Sprache (Dokument-Import) ─────────────────────────────────────────────

async function onOcrDocLangChange(nextValue) {
  if (isSettingSaving.ocr_doc_lang) return;
  const nextLang = OCR_DOC_LANG_VALUES.has(String(nextValue))
    ? String(nextValue)
    : settingsDraft.documents.ocr_doc_lang;
  if (nextLang === settingsDraft.documents.ocr_doc_lang) return;
  const previous = settingsDraft.documents.ocr_doc_lang;
  settingsStore.setDraftPatch({ documents: { ocr_doc_lang: nextLang } });
  await patchSettingsWithRevert({
    patch: buildOcrDocLangPatch(nextLang),
    controlKey: 'ocr_doc_lang',
    revert: () => settingsStore.setDraftPatch({ documents: { ocr_doc_lang: previous } })
  });
}

// ── Dateiendung ──────────────────────────────────────────────────────────────

async function onShowFilenameSuffixChange(nextValue) {
  if (isSettingSaving.show_filename_suffix) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.showFilenameSuffix) return;
  const previous = settingsDraft.ui.showFilenameSuffix;
  settingsStore.setDraftPatch({ ui: { showFilenameSuffix: nextBool } });
  await patchSettingsWithRevert({
    patch: buildShowFilenameSuffixPatch(nextBool),
    controlKey: 'show_filename_suffix',
    revert: () => settingsStore.setDraftPatch({ ui: { showFilenameSuffix: previous } })
  });
}

function toggleShowFilenameSuffixFromRow() {
  if (isSettingSaving.show_filename_suffix) return;
  void onShowFilenameSuffixChange(!settingsDraft.ui.showFilenameSuffix);
}

// ── Glass-Look (Aurora-Hintergrund) ──────────────────────────────────────────

async function onGlassEnabledChange(nextValue) {
  if (isSettingSaving.glass_enabled) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.glass_enabled) return;
  const previous = settingsDraft.ui.glass_enabled;
  settingsStore.setDraftPatch({ ui: { glass_enabled: nextBool } });
  await patchSettingsWithRevert({
    patch: buildGlassEnabledPatch(nextBool),
    controlKey: 'glass_enabled',
    revert: () => settingsStore.setDraftPatch({ ui: { glass_enabled: previous } })
  });
}

function toggleGlassEnabledFromRow() {
  if (isSettingSaving.glass_enabled) return;
  void onGlassEnabledChange(!settingsDraft.ui.glass_enabled);
}

// ── Drawer: Zustand merken ───────────────────────────────────────────────────

async function onDrawerRememberStateChange(nextValue) {
  if (isSettingSaving.drawer_remember_state) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.drawerRememberState) return;
  const previous = settingsDraft.ui.drawerRememberState;
  settingsStore.setDraftPatch({ ui: { drawerRememberState: nextBool } });
  await patchSettingsWithRevert({
    patch: buildDrawerRememberStatePatch(nextBool),
    controlKey: 'drawer_remember_state',
    revert: () => settingsStore.setDraftPatch({ ui: { drawerRememberState: previous } })
  });
}

function toggleDrawerRememberStateFromRow() {
  if (isSettingSaving.drawer_remember_state) return;
  void onDrawerRememberStateChange(!settingsDraft.ui.drawerRememberState);
}

// ── Tag-Schublade: Zustand merken ────────────────────────────────────────────

async function onTagDrawerRememberStateChange(nextValue) {
  if (isSettingSaving.tag_drawer_remember_state) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.tagDrawerRememberState) return;
  const previous = settingsDraft.ui.tagDrawerRememberState;
  settingsStore.setDraftPatch({ ui: { tagDrawerRememberState: nextBool } });
  await patchSettingsWithRevert({
    patch: buildTagDrawerRememberStatePatch(nextBool),
    controlKey: 'tag_drawer_remember_state',
    revert: () => settingsStore.setDraftPatch({ ui: { tagDrawerRememberState: previous } })
  });
}

function toggleTagDrawerRememberStateFromRow() {
  if (isSettingSaving.tag_drawer_remember_state) return;
  void onTagDrawerRememberStateChange(!settingsDraft.ui.tagDrawerRememberState);
}

// ── Animationen ──────────────────────────────────────────────────────────────

function onAnimationsEnabledChange(nextValue) {
  settingsStore.setAnimationsEnabled(Boolean(nextValue));
}

function toggleAnimationsFromRow() {
  settingsStore.setAnimationsEnabled(!settingsStore.animationsEnabled);
}

// ── Dokumenttypen-Verwaltung ───────────────────────────────────────────────────

const newCategoryName = ref('');
const selectedCategoryId = ref(null);
const editingCategoryName = ref('');
const editingCategoryTemplate = ref('');

const newCorrespondentName = ref('');
const selectedCorrespondentId = ref(null);
const editingCorrespondentName = ref('');
const editingCorrespondentShortName = ref('');
const newAliasName = ref('');
const unresolvedCorrespondents = ref([]);
const unresolvedSelections = ref({});
const isUnresolvedCorrespondentsLoading = ref(false);
const assigningUnresolvedId = ref(null);
const creatingUnresolvedId = ref(null);
const ignoringUnresolvedId = ref(null);

const selectedCorrespondent = computed(() =>
  selectedCorrespondentId.value ? correspondentStore.findById(selectedCorrespondentId.value) : null
);

const selectedCategory = computed(() =>
  selectedCategoryId.value ? categoryStore.findById(selectedCategoryId.value) : null
);

const canSaveSelectedCategory = computed(() => {
  const current = selectedCategory.value;
  if (!current) return false;
  const nextName = editingCategoryName.value.trim();
  if (!nextName) return false;
  return (
    nextName !== current.name ||
    editingCategoryTemplate.value.trim() !== (current.naming_template || '')
  );
});

const categoryTemplatePreviewParts = computed(() =>
  renderCategoryTemplatePreviewParts(editingCategoryTemplate.value)
);

const canSaveSelectedCorrespondent = computed(() => {
  const current = selectedCorrespondent.value;
  if (!current) return false;
  const nextName = editingCorrespondentName.value.trim();
  if (!nextName) return false;
  return nextName !== current.name || editingCorrespondentShortName.value.trim() !== (current.short_name || '');
});

function templatePreviewValues() {
  return {
    korrespondent: 'HUK',
    absender: 'HUK',
    aussteller: 'HUK',
    betreff: 'Kfz-Versicherung',
    gegenstand: 'Kfz-Versicherung',
    sparte: 'Kfz-Versicherung',
    datum: '01.01.2024',
    betrag: '87,30€',
    monat: 'Januar',
    jahr: '2024',
  };
}

function renderCategoryTemplatePreviewParts(template) {
  const source = String(template || '').trim();
  if (!source) return [{ text: 'Kein Template gesetzt.', missing: false }];
  const values = templatePreviewValues();
  const parts = [];
  let lastIndex = 0;
  const placeholderPattern = /\{([a-zA-Z_][a-zA-Z0-9_]*)(?::[^{}]+)?\}/g;
  for (const match of source.matchAll(placeholderPattern)) {
    if (match.index > lastIndex) {
      parts.push({ text: source.slice(lastIndex, match.index), missing: false });
    }
    const key = match[1];
    if (Object.prototype.hasOwnProperty.call(values, key)) {
      parts.push({ text: values[key], missing: false });
    } else {
      parts.push({ text: match[0], missing: true });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < source.length) {
    parts.push({ text: source.slice(lastIndex), missing: false });
  }
  return parts.length ? parts : [{ text: source, missing: false }];
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      const allowed = visibleCategories.value.some((cat) => cat.value === props.initialCategory);
      activeCategory.value = allowed ? props.initialCategory : 'appearance';
      void categoryStore.fetchCategories();
      void correspondentStore.fetchCorrespondents();
      void loadUnresolvedCorrespondents();
    }
  },
  { immediate: true }
);

watch(
  () => correspondentStore.correspondents,
  (items) => {
    if (!Array.isArray(items) || items.length === 0) {
      selectedCorrespondentId.value = null;
      return;
    }
    if (selectedCorrespondentId.value && !items.some((item) => item.id === selectedCorrespondentId.value)) {
      selectedCorrespondentId.value = null;
      return;
    }
    if (selectedCorrespondentId.value) {
      const selected = items.find((item) => item.id === selectedCorrespondentId.value);
      if (selected) syncCorrespondentEditor(selected);
    }
  },
  { deep: true }
);

watch(
  () => categoryStore.categories,
  (items) => {
    if (!Array.isArray(items) || items.length === 0) {
      selectedCategoryId.value = null;
      return;
    }
    if (selectedCategoryId.value && !items.some((item) => item.id === selectedCategoryId.value)) {
      selectedCategoryId.value = null;
      return;
    }
    if (selectedCategoryId.value) {
      const selected = items.find((item) => item.id === selectedCategoryId.value);
      if (selected) syncCategoryEditor(selected);
    }
  },
  { deep: true }
);

async function addCategory() {
  const name = newCategoryName.value.trim();
  if (!name || categoryStore.isCategoryMutationRunning) return;
  try {
    const result = await categoryStore.createCategoryByName(name);
    if (result.ok || result.reason === 'exists') {
      newCategoryName.value = '';
    }
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

async function removeCategory(category) {
  if (categoryStore.isCategoryMutationRunning) return;
  try {
    await categoryStore.deleteCategory(category.id);
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

function syncCategoryEditor(category) {
  editingCategoryName.value = category?.name || '';
  editingCategoryTemplate.value = category?.naming_template || '';
}

function selectCategory(category) {
  selectedCategoryId.value = category?.id || null;
  syncCategoryEditor(category);
}

function toggleCategory(category) {
  if (selectedCategoryId.value === category?.id) {
    selectedCategoryId.value = null;
    return;
  }
  selectCategory(category);
}

async function saveSelectedCategory() {
  const current = selectedCategory.value;
  if (!current || !canSaveSelectedCategory.value) return;
  try {
    await categoryStore.updateCategory(current.id, {
      name: editingCategoryName.value.trim(),
      naming_template: editingCategoryTemplate.value.trim() || null,
    });
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

function syncCorrespondentEditor(correspondent) {
  editingCorrespondentName.value = correspondent?.name || '';
  editingCorrespondentShortName.value = correspondent?.short_name || '';
}

function selectCorrespondent(correspondent) {
  selectedCorrespondentId.value = correspondent?.id || null;
  syncCorrespondentEditor(correspondent);
  newAliasName.value = '';
}

function toggleCorrespondent(correspondent) {
  if (selectedCorrespondentId.value === correspondent?.id) {
    selectedCorrespondentId.value = null;
    return;
  }
  selectCorrespondent(correspondent);
}

async function addCorrespondent() {
  const name = newCorrespondentName.value.trim();
  if (!name || correspondentStore.isMutationRunning) return;
  try {
    const result = await correspondentStore.createCorrespondentByName(name);
    if (result.ok) {
      newCorrespondentName.value = '';
      selectedCorrespondentId.value = result.id;
    }
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

async function loadUnresolvedCorrespondents() {
  isUnresolvedCorrespondentsLoading.value = true;
  try {
    const payload = await apiListUnresolvedCorrespondents({ limit: 50, excerptChars: 240 });
    unresolvedCorrespondents.value = payload?.items ?? [];
    const validIds = new Set(unresolvedCorrespondents.value.map((item) => item.document_id));
    unresolvedSelections.value = Object.fromEntries(
      Object.entries(unresolvedSelections.value).filter(([id]) => validIds.has(id))
    );
  } catch (error) {
    notifyError(error, 'Offene Korrespondenten konnten nicht geladen werden.');
  } finally {
    isUnresolvedCorrespondentsLoading.value = false;
  }
}

async function assignUnresolvedCorrespondent(item, addSenderAlias = false) {
  const documentId = item?.document_id;
  const correspondentId = unresolvedSelections.value[documentId];
  if (!documentId || !correspondentId) return;
  assigningUnresolvedId.value = documentId;
  try {
    if (addSenderAlias && item.sender) {
      await correspondentStore.addAlias(correspondentId, item.sender);
    }
    await apiPatchDocument(documentId, { correspondent_id: correspondentId });
    await Promise.all([
      correspondentStore.fetchCorrespondents(),
      loadUnresolvedCorrespondents(),
    ]);
    emit('reload-imports');
    notify({ type: 'success', title: 'Korrespondent', message: 'Dokument zugeordnet.' });
  } catch (error) {
    notifyError(error, 'Korrespondent konnte nicht zugeordnet werden.');
  } finally {
    assigningUnresolvedId.value = null;
  }
}

async function createCorrespondentFromUnresolved(item) {
  const documentId = item?.document_id;
  const name = String(item?.sender || '').trim();
  if (!documentId || !name) return;
  creatingUnresolvedId.value = documentId;
  try {
    const result = await correspondentStore.createCorrespondentByName(name);
    const correspondentId = result?.id;
    if (!correspondentId) return;
    unresolvedSelections.value = {
      ...unresolvedSelections.value,
      [documentId]: correspondentId,
    };
    await apiPatchDocument(documentId, { correspondent_id: correspondentId });
    await Promise.all([
      correspondentStore.fetchCorrespondents(),
      loadUnresolvedCorrespondents(),
    ]);
    emit('reload-imports');
    notify({ type: 'success', title: 'Korrespondent', message: 'Korrespondent angelegt und Dokument zugeordnet.' });
  } catch (error) {
    notifyError(error, 'Korrespondent konnte nicht angelegt werden.');
  } finally {
    creatingUnresolvedId.value = null;
  }
}

async function ignoreUnresolvedCorrespondent(item) {
  const documentId = item?.document_id;
  if (!documentId) return;
  ignoringUnresolvedId.value = documentId;
  try {
    await apiIgnoreUnresolvedCorrespondent(documentId, 'Bewusst ohne Korrespondent');
    await loadUnresolvedCorrespondents();
    notify({ type: 'success', title: 'Korrespondent', message: 'Fall ausgeblendet.' });
  } catch (error) {
    notifyError(error, 'Fall konnte nicht ausgeblendet werden.');
  } finally {
    ignoringUnresolvedId.value = null;
  }
}

async function saveSelectedCorrespondent() {
  const current = selectedCorrespondent.value;
  if (!current || !canSaveSelectedCorrespondent.value) return;
  try {
    await correspondentStore.updateCorrespondent(current.id, {
      name: editingCorrespondentName.value.trim(),
      short_name: editingCorrespondentShortName.value.trim() || null,
    });
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

async function removeSelectedCorrespondent() {
  const current = selectedCorrespondent.value;
  if (!current || (current.usage_count || 0) > 0) return;
  try {
    await correspondentStore.deleteCorrespondent(current.id);
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

async function addAliasToSelected() {
  const current = selectedCorrespondent.value;
  const alias = newAliasName.value.trim();
  if (!current || !alias) return;
  try {
    await correspondentStore.addAlias(current.id, alias);
    newAliasName.value = '';
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

async function removeAlias(alias) {
  const current = selectedCorrespondent.value;
  if (!current || !alias?.id) return;
  try {
    await correspondentStore.deleteAlias(current.id, alias.id);
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}
</script>

<style scoped>
/* ── Backup ── */
.backup-card {
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.02);
  transition: border-color 0.2s ease, background 0.2s ease;
}
.backup-card--ok { border-color: rgba(76, 175, 80, 0.4); background: rgba(76, 175, 80, 0.06); }
.backup-card--error { border-color: rgba(var(--v-theme-error), 0.4); background: rgba(var(--v-theme-error), 0.06); }
.backup-card--running { border-color: rgba(var(--v-theme-primary), 0.4); background: rgba(var(--v-theme-primary), 0.06); }
.backup-card--disabled { opacity: 0.6; }
.backup-card__main {
  display: flex;
  align-items: center;
  gap: 14px;
}
.backup-card__icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.07);
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.backup-card--ok .backup-card__icon { background: rgba(76, 175, 80, 0.16); color: rgb(76, 175, 80); }
.backup-card--error .backup-card__icon { background: rgba(var(--v-theme-error), 0.16); color: rgb(var(--v-theme-error)); }
.backup-card--running .backup-card__icon { background: rgba(var(--v-theme-primary), 0.16); color: rgb(var(--v-theme-primary)); }
.backup-card__info { flex: 1; min-width: 0; }
.backup-card__state { font-size: 0.95rem; font-weight: 600; }
.backup-card__detail { font-size: 0.82rem; opacity: 0.7; margin-top: 2px; }
.backup-card__next { text-align: right; flex-shrink: 0; }
.backup-card__next-label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.5;
}
.backup-card__next-value { font-size: 0.82rem; font-weight: 500; margin-top: 2px; }
.backup-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 22px;
  padding-top: 14px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.backup-card__section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.backup-card__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.backup-card__section-title {
  font-size: 0.8rem;
  font-weight: 600;
  opacity: 0.8;
}
.backup-setup { margin-bottom: 4px; }
.backup-setup :deep(.v-expansion-panel) {
  background: transparent;
  border: none;
  border-radius: 10px !important;
}
.backup-setup :deep(.v-expansion-panel__shadow) { display: none; }
.backup-setup :deep(.v-expansion-panel-title) {
  min-height: 56px;
  padding-inline: 16px;
  border-radius: 10px;
  transition: background 0.15s ease;
}
.backup-setup :deep(.v-expansion-panel-title:hover) {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.backup-setup :deep(.v-expansion-panel-text__wrapper) { padding-inline: 16px; }
.backup-setup__head { display: flex; align-items: center; min-width: 0; }
.backup-setup__head-text { min-width: 0; }
.backup-setup__head-title { font-size: 0.9rem; font-weight: 600; }
.backup-setup__head-sub {
  font-size: 0.78rem;
  opacity: 0.6;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.restore-progress {
  display: flex;
  align-items: center;
  padding: 8px 4px;
}
.restore-progress__title { font-weight: 600; }
.restore-progress__sub { font-size: 0.8rem; opacity: 0.7; margin-top: 2px; }
.backup-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 12px;
  margin: 8px 0 24px;
}
.backup-grid--tight { margin: 0; }
.backup-grid__full { grid-column: 1 / -1; }
.backup-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.backup-actions--end { justify-content: flex-end; }
.backup-test-result { font-size: 0.8rem; }
.backup-test-result--ok { color: rgb(76, 175, 80); }
.backup-test-result--err { color: rgb(var(--v-theme-error)); }
.settings-category-management {
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 100%;
}

.settings-category-header {
  position: sticky;
  top: 0;
  z-index: 4;
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin: 0;
  padding: 14px 0;
  background: rgb(var(--v-theme-surface));
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  box-shadow: 0 -24px 0 rgb(var(--v-theme-surface));
}

.settings-categories {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding-top: 12px;
}

/* ── Seitenleisten-Sektionen (Reihenfolge & Sichtbarkeit) ───────────────── */
.settings-sidebar-sections {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding-top: 12px;
}

.settings-sidebar-section-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 6px 10px 6px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.07);
  border-radius: 8px;
  transition: opacity 0.15s ease, border-color 0.15s ease;
}

.settings-sidebar-section-row--hidden {
  opacity: 0.55;
}

.settings-sidebar-section-reorder {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.settings-sidebar-section-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 18px;
  padding: 0;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.55);
  transition: background 0.12s ease, color 0.12s ease;
}

.settings-sidebar-section-arrow:hover:not(:disabled) {
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.85);
}

.settings-sidebar-section-arrow:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.settings-sidebar-section-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.settings-sidebar-section-name {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.92rem;
  font-weight: 500;
}

/* Kompaktes Anzahl-Select (Schnellzugriff-Limits) */
.settings-sidebar-max-select {
  flex: 0 0 auto;
  width: 108px;
  min-width: 108px;
}

.settings-category-row {
  display: flex;
  flex-direction: column;
  width: 100%;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.07);
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.68);
  overflow: hidden;
  transition:
    border-color 160ms ease,
    background-color 160ms ease;
}

.settings-category-row:hover,
.settings-category-row--active {
  border-color: rgba(var(--v-theme-primary), 0.24);
  background: rgba(var(--v-theme-primary), 0.055);
}

.settings-category-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 54px;
  padding: 8px 10px;
  background: transparent;
  border: 0;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.settings-category-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.settings-category-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: rgba(var(--v-theme-primary), 0.9);
  background: rgba(var(--v-theme-primary), 0.1);
}

.settings-category-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.settings-category-name {
  min-width: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.9);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-category-meta {
  min-width: 0;
  font-size: 0.72rem;
  font-weight: 650;
  color: rgba(var(--v-theme-on-surface), 0.52);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-category-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.settings-category-count {
  flex: 0 0 auto;
  min-width: 28px;
  text-align: center;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.075);
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-variant-numeric: tabular-nums;
}

.settings-category-action-btn {
  width: 28px !important;
  height: 28px !important;
  min-width: 28px !important;
  border-radius: 50% !important;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.settings-category-action-btn .v-btn__overlay,
.settings-category-action-btn .v-btn__underlay {
  border-radius: 50% !important;
}

.settings-category-action-btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.88);
}

.settings-category-action-btn--danger:hover {
  background: rgba(var(--v-theme-error), 0.08);
}

.settings-category-editor-shell {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transform: translateY(-4px);
  transition:
    grid-template-rows 220ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 160ms ease,
    transform 180ms ease;
}

.settings-category-editor-shell--open {
  grid-template-rows: 1fr;
  opacity: 1;
  overflow: visible;
  pointer-events: auto;
  transform: translateY(0);
}

.settings-category-editor {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding: 0 12px 0 50px;
  overflow: hidden;
  transition: padding-bottom 220ms cubic-bezier(0.22, 1, 0.36, 1);
}

.settings-category-editor-shell--open > .settings-category-editor {
  padding-top: 6px;
  padding-bottom: 12px;
}

.settings-category-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 36px 36px;
  gap: 8px;
  align-items: center;
}

.settings-template-preview {
  display: flex;
  gap: 6px;
  align-items: baseline;
  min-width: 0;
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.settings-template-preview__label {
  flex: 0 0 auto;
  font-weight: 750;
}

.settings-template-preview__value {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  min-width: 0;
  line-height: 1.6;
}

.settings-template-preview__missing {
  display: inline-flex;
  align-items: center;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(var(--v-theme-warning), 0.14);
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.settings-category-empty {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  padding: 6px 10px;
}

.settings-category-add {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.settings-category-add :deep(.v-field) {
  border-radius: 8px;
}

.settings-category-add__button {
  align-self: stretch;
  min-height: 40px;
}

.settings-correspondents {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding-top: 12px;
  min-height: 0;
}

.settings-correspondent-review {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 4px;
  padding: 10px;
  border: 1px solid rgba(var(--v-theme-primary), 0.18);
  border-radius: 8px;
  background: rgba(var(--v-theme-primary), 0.04);
}

.settings-correspondent-review__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.settings-unresolved-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(170px, 220px) repeat(4, 32px);
  gap: 8px;
  align-items: center;
  min-height: 44px;
  padding: 7px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.7);
}

.settings-unresolved-row__main {
  min-width: 0;
}

.settings-unresolved-row__select {
  min-width: 0;
}

.settings-unresolved-row :deep(.v-btn) {
  width: 32px;
  height: 32px;
}

.settings-correspondent-row {
  display: flex;
  flex-direction: column;
  width: 100%;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.07);
  border-radius: 8px;
  background: rgba(var(--v-theme-surface), 0.68);
  overflow: hidden;
  transition:
    border-color 160ms ease,
    background-color 160ms ease;
}

.settings-correspondent-row:hover,
.settings-correspondent-row--active {
  border-color: rgba(var(--v-theme-primary), 0.24);
  background: rgba(var(--v-theme-primary), 0.055);
}

.settings-correspondent-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 54px;
  padding: 8px 10px;
  background: transparent;
  border: 0;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.settings-correspondent-summary__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.settings-correspondent-editor-shell {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transform: translateY(-4px);
  transition:
    grid-template-rows 220ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 160ms ease,
    transform 180ms ease;
}

.settings-correspondent-editor-shell--open {
  grid-template-rows: 1fr;
  opacity: 1;
  overflow: visible;
  pointer-events: auto;
  transform: translateY(0);
}

.settings-correspondent-editor {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding: 0 12px 0 50px;
  overflow: hidden;
  transition: padding-bottom 220ms cubic-bezier(0.22, 1, 0.36, 1);
}

.settings-correspondent-editor-shell--open > .settings-correspondent-editor {
  padding-top: 6px;
  padding-bottom: 12px;
}

.settings-correspondent-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px 36px 36px;
  gap: 8px;
  align-items: center;
}

.settings-correspondent-icon-action {
  width: 28px !important;
  height: 28px !important;
  min-width: 28px !important;
  border-radius: 50% !important;
  box-shadow: none !important;
}

.settings-correspondent-icon-action::before,
.settings-correspondent-icon-action .v-btn__overlay,
.settings-correspondent-icon-action .v-btn__underlay {
  border-radius: 50% !important;
}

.settings-correspondent-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.settings-correspondent-block__title {
  font-size: 0.78rem;
  font-weight: 750;
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.settings-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 24px;
}

.settings-inline-add {
  display: grid;
  gap: 8px;
  align-items: center;
}

.settings-inline-add {
  grid-template-columns: minmax(0, 1fr) auto;
}

@media (max-width: 760px) {
  .settings-unresolved-row,
  .settings-category-editor,
  .settings-category-form,
  .settings-correspondent-form {
    grid-template-columns: 1fr;
  }

  .settings-category-editor,
  .settings-correspondent-editor {
    padding-left: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .settings-correspondent-row,
  .settings-category-row,
  .settings-category-editor-shell,
  .settings-category-editor,
  .settings-correspondent-editor-shell,
  .settings-correspondent-editor {
    transition: none;
  }
}

/* Texterkennung: Hinweis, gruppierter KI-Block, Erweitert-Aufklapper */
.pm-setting-note {
  font-size: 0.84rem;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.62);
  padding: 2px 0 8px;
}

.pm-setting-group {
  border-left: 2px solid rgba(var(--v-theme-primary), 0.3);
  padding-left: 14px;
  margin: 2px 0 4px;
}

.pm-setting-note--group {
  padding: 0 0 6px;
  font-size: 0.82rem;
}

.pm-setting-group + .pm-setting-row {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.04);
}

.pm-settings-disclosure {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0 2px;
  padding: 4px 0;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 600;
  color: rgb(var(--v-theme-primary));
}

.pm-settings-disclosure:hover {
  text-decoration: underline;
}

.pm-setting-row--disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.pm-setting-row--disabled .pm-setting-hint {
  opacity: 1;
}

/* Tastaturkürzel-Liste (Bereich „Bedienung") */
.shortcuts-list {
  display: grid;
  gap: 20px;
  width: 100%;
}

.shortcuts-list__group-label {
  margin: 0 0 8px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.shortcuts-list__rows {
  display: grid;
  gap: 2px;
}

.shortcuts-list__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.06));
}

.shortcuts-list__row:last-child {
  border-bottom: none;
}

.shortcuts-list__desc {
  font-size: 0.88rem;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.shortcuts-list__keys {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.shortcuts-list__kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  padding: 2px 7px;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 500;
  line-height: 1.4;
  border-radius: 5px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  color: rgba(var(--v-theme-on-surface), 0.72);
  white-space: nowrap;
}

.pm-tag-cleanup {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pm-tag-cleanup__names {
  display: block;
  margin-top: 2px;
  max-height: 120px;
  overflow-y: auto;
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 0.82rem;
  word-break: break-word;
}
.pm-tag-cleanup__actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
