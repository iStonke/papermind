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
            v-for="cat in settingsCategories"
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

        <section v-show="activeCategory === 'documents'" class="pm-settings-section">
          <div class="pm-settings-content">
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
                          placeholder="z. B. Rechnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"
                        />
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

            <!-- Hinweis: Import-Vorschau wird immer analysiert -->
            <div class="pm-setting-note">
              Im Import-Fenster werden hinzugefügte Dokumente <strong>immer</strong> automatisch
              analysiert (Vorschau für Titel, Datum, Dokumenttyp und Tags). Die folgenden Optionen
              steuern Qualität und Sprache dieser Analyse sowie die automatische
              Weiterverarbeitung <strong>nach</strong> dem Import.
            </div>

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

        <section v-show="activeCategory === 'controls'" class="pm-settings-section">
          <div class="pm-settings-content">
            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Tastaturkürzel</div>
                <div class="pm-setting-description">Verfügbare Tastenkürzel und Mausgesten in PaperMind.</div>
              </div>

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
import { getBaseUrl } from '../api/client';
import { useSettingsStore } from '../stores/settings';
import { useCategoryStore } from '../stores/categories';
import { useCorrespondentStore } from '../stores/correspondents';
import { notifyError, useNotifications } from '../stores/notifications';
import { useTagStore } from '../stores/tags';
import { cleanupUnusedTags } from '../api/tags';
import { backfillOcr, patchDocument as apiPatchDocument } from '../api/documents';
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
  buildDrawerRememberStatePatch,
  buildTagDrawerRememberStatePatch,
  buildOcrDocLangPatch,
  buildRecentImportWindowPatch,
  buildShowFilenameSuffixPatch,
  buildThemeModePatch,
  buildTrashRetentionPatch
} from '../utils/settingsApi';

// ── Props / Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialCategory: { type: String, default: 'appearance' }
});

const emit = defineEmits(['update:modelValue', 'reload-imports']);

// ── Stores / Theme ───────────────────────────────────────────────────────────

const theme = useTheme();
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

const currentColorVariant = computed(() => settingsStore.settingsDraft.ui.color_variant || 'slate');

// ── Einstellungsnavigation ───────────────────────────────────────────────────

const settingsCategories = [
  { value: 'appearance', label: 'Darstellung', icon: 'mdi-palette-outline' },
  { value: 'documents', label: 'Dokumente', icon: 'mdi-file-document-outline' },
  { value: 'categories', label: 'Dokumenttypen', icon: 'mdi-file-document-multiple-outline' },
  { value: 'correspondents', label: 'Korrespondenten', icon: 'mdi-account-outline' },
  { value: 'ai', label: 'Texterkennung', icon: 'mdi-robot-outline' },
  { value: 'controls', label: 'Bedienung', icon: 'mdi-keyboard-outline' }
];

const activeCategory = ref('appearance');

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
const COLOR_VARIANT_VALUES = new Set(['indigo', 'forest', 'teal', 'slate', 'stone']);
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
  { label: 'Steingrau', value: 'stone', color: '#57534E' },
  { label: 'Schieferblau', value: 'slate', color: '#475569' },
  { label: 'Indigo', value: 'indigo',  color: '#2563EB' },
  { label: 'Waldgrün', value: 'forest',  color: '#16A34A' },
  { label: 'Teal',  value: 'teal',   color: '#0F766E' }
];

async function onColorVariantChange(nextValue) {
  if (isSettingSaving.color_variant) return;
  const nextVariant = COLOR_VARIANT_VALUES.has(String(nextValue)) ? String(nextValue) : 'slate';
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

const canSaveSelectedCorrespondent = computed(() => {
  const current = selectedCorrespondent.value;
  if (!current) return false;
  const nextName = editingCorrespondentName.value.trim();
  if (!nextName) return false;
  return nextName !== current.name || editingCorrespondentShortName.value.trim() !== (current.short_name || '');
});

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      activeCategory.value = props.initialCategory;
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
