<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="820"
    card-class="pm-settings-card"
    body-class="pm-settings-body"
    title="Einstellungen"
    header-subtitle="Globale Voreinstellungen für dein PaperMind."
    description=""
    variant="info"
    :show-footer="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="isSettingsLoading" class="settings-loading">
      <v-progress-circular indeterminate size="20" width="2" />
      <span>Einstellungen werden geladen...</span>
    </div>
    <template v-else>
      <div class="pm-settings-layout">
        <nav class="pm-settings-nav" role="tablist" aria-label="Einstellungskategorien">
          <div
            v-for="group in visibleCategoryGroups"
            :key="`settings-group-${group.key}`"
            class="pm-settings-nav__group"
          >
            <div class="pm-settings-nav__group-label">{{ group.label }}</div>
            <button
              v-for="cat in group.items"
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
          </div>
        </nav>

        <div class="pm-settings-panel">
        <section v-if="activeCategory === 'appearance'" class="pm-settings-section">
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

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Startseite</div>
                <div class="pm-setting-description">Womit die App nach dem Login startet.</div>
              </div>
              <v-select
                :model-value="currentStartView"
                :items="startViewOptions"
                item-title="label"
                item-value="value"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Startseite"
                aria-label="Startseite auswählen"
                :loading="isSettingSaving.start_view"
                :disabled="isSettingSaving.start_view"
                @update:model-value="onStartViewChange"
              />
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
              @click="toggleScanLineAnimationFromRow"
              @keydown="handleSettingRowShortcut($event, toggleScanLineAnimationFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Scan-Balken bei KI-Analyse</div>
                <div class="pm-setting-description">
                  Wandernder Balken im Importfenster, solange die KI ein Dokument analysiert.
                </div>
              </div>
              <v-switch
                :model-value="scanLineAnimationEnabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                @click.stop
                @update:model-value="onScanLineAnimationEnabledChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="togglePreviewDrawerGradientFromRow"
              @keydown="handleSettingRowShortcut($event, togglePreviewDrawerGradientFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Vorschau-Verlauf</div>
                <div class="pm-setting-description">
                  Blendet den Bereich hinter den Dokumentdetails weich aus.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.ui.previewDrawerGradientEnabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.preview_drawer_gradient"
                :disabled="isSettingSaving.preview_drawer_gradient"
                @click.stop
                @update:model-value="onPreviewDrawerGradientChange"
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

        <section v-if="activeCategory === 'sidebar'" class="pm-settings-section">
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
                  <v-select
                    v-if="section.key === 'tags'"
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
                    @click.stop
                    @update:model-value="onSidebarMaxTagsChange"
                  />
                  <v-select
                    v-else-if="section.key === 'kategorien'"
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
                    @click.stop
                    @update:model-value="onSidebarMaxCategoriesChange"
                  />
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

            <div class="settings-sidebar-library">
              <div class="pm-setting-row settings-sidebar-library-row">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Zuletzt hinzugefügt</div>
                  <div class="pm-setting-description">Bibliothek-Eintrag in der Seitenleiste anzeigen.</div>
                </div>
                <v-switch
                  :model-value="settingsDraft.ui.sidebar_show_recent"
                  color="primary"
                  density="comfortable"
                  hide-details
                  inset
                  :loading="isSettingSaving.sidebar_show_recent"
                  :disabled="isSettingSaving.sidebar_show_recent"
                  @update:model-value="onSidebarShowRecentChange"
                />
              </div>

              <div class="pm-setting-row settings-sidebar-library-row">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Ohne Tags</div>
                  <div class="pm-setting-description">Bibliothek-Eintrag in der Seitenleiste anzeigen.</div>
                </div>
                <v-switch
                  :model-value="settingsDraft.ui.sidebar_show_untagged"
                  color="primary"
                  density="comfortable"
                  hide-details
                  inset
                  :loading="isSettingSaving.sidebar_show_untagged"
                  :disabled="isSettingSaving.sidebar_show_untagged"
                  @update:model-value="onSidebarShowUntaggedChange"
                />
              </div>

              <div class="pm-setting-row settings-sidebar-library-row">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Nicht durchsuchbar</div>
                  <div class="pm-setting-description">Bibliothek-Eintrag in der Seitenleiste anzeigen.</div>
                </div>
                <v-switch
                  :model-value="settingsDraft.ui.sidebar_show_no_text"
                  color="primary"
                  density="comfortable"
                  hide-details
                  inset
                  :loading="isSettingSaving.sidebar_show_no_text"
                  :disabled="isSettingSaving.sidebar_show_no_text"
                  @update:model-value="onSidebarShowNoTextChange"
                />
              </div>

              <div class="pm-setting-row settings-sidebar-library-row">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">KI-Chat</div>
                  <div class="pm-setting-description">Bibliothek-Eintrag in der Seitenleiste anzeigen.</div>
                </div>
                <v-switch
                  :model-value="settingsDraft.ui.sidebar_show_chat"
                  color="primary"
                  density="comfortable"
                  hide-details
                  inset
                  :loading="isSettingSaving.sidebar_show_chat"
                  :disabled="isSettingSaving.sidebar_show_chat"
                  @update:model-value="onSidebarShowChatChange"
                />
              </div>
            </div>

          </div>
        </section>

        <section v-if="activeCategory === 'documents'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-archive-outline"
              title="Bibliothek"
              subtitle="Listenansichten, Papierkorb und Datenpflege."
            />

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">„Zuletzt hinzugefügt" anzeigen für</div>
                <div class="pm-setting-description">
                  Bestimmt, wie lange neue Dokumente in der Seitenleiste unter „Zuletzt hinzugefügt" auftauchen.
                  In „Alle Dokumente" bleiben sie dauerhaft sichtbar.
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
                label="Anzeigen für"
                :loading="isSettingSaving.recent_import_window_hours"
                :disabled="isSettingSaving.recent_import_window_hours"
                @update:model-value="onRecentImportWindowChange"
              />
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Papierkorb endgültig löschen nach</div>
                <div class="pm-setting-description">
                  Gelöschte Dokumente bleiben zuerst im Papierkorb. Nach diesem Zeitraum werden sie dauerhaft entfernt.
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
                label="Endgültig löschen"
                :loading="isSettingSaving.trash_retention_days"
                :disabled="isSettingSaving.trash_retention_days"
                @update:model-value="onTrashRetentionChange"
              />
            </div>

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Leere Tags entfernen</div>
                <div class="pm-setting-description">
                  Sucht Tags, die an keinem Dokument hängen. Es werden nur diese leeren Tags gelöscht,
                  keine Dokumente und keine verwendeten Tags.
                </div>
              </div>

              <div v-if="!unusedTagsPreview">
                <v-btn
                  variant="tonal"
                  class="pm-tag-cleanup__button"
                  :loading="tagCleanupLoading"
                  @click="loadUnusedTagsPreview"
                >
                  Leere Tags suchen
                </v-btn>
              </div>

              <div v-else class="pm-tag-cleanup">
                <div v-if="unusedTagsPreview.count === 0" class="pm-setting-description">
                  Keine leeren Tags gefunden.
                </div>
                <div v-else class="pm-setting-description">
                  <strong>{{ unusedTagsPreview.count }}</strong> leere{{ unusedTagsPreview.count === 1 ? 'r Tag wird' : ' Tags werden' }} gelöscht:
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

        <section v-if="activeCategory === 'import'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-tray-arrow-up"
              title="Importieren"
              subtitle="Scanner, Scan-Eingang und automatische Schritte nach dem Import."
            />

            <div class="pm-settings-subhead">Scanner</div>

            <div v-if="scannerSettingsLoading" class="scanner-settings-state">
              <v-progress-circular indeterminate size="22" width="2" />
              <span>Scanner werden geladen...</span>
            </div>

            <div v-else-if="scannerSettingsError" class="scanner-settings-state scanner-settings-state--error">
              <v-icon size="20">mdi-alert-circle-outline</v-icon>
              <span>{{ scannerSettingsError }}</span>
              <v-btn variant="text" size="small" @click="loadScannerSettings">Erneut laden</v-btn>
            </div>

            <div v-else-if="scannerDrafts.length === 0" class="scanner-empty">
              <v-icon size="28">mdi-scanner-off</v-icon>
              <div>
                <div class="scanner-empty__title">Noch kein Scanner erkannt</div>
                <div class="scanner-empty__text">Der erste Scan legt den Scanner automatisch an.</div>
              </div>
            </div>

            <div v-else class="scanner-list">
              <div
                v-for="scanner in scannerDrafts"
                :key="scanner.id"
                class="scanner-card"
                :class="{ 'scanner-card--disabled': !scanner.enabled }"
              >
                <div class="scanner-card__header">
                  <div class="scanner-card__identity">
                    <v-icon class="scanner-card__glyph" size="26">mdi-scanner</v-icon>
                    <div class="scanner-card__identity-text">
                      <div class="scanner-card__device-line">
                        <span class="scanner-card__device-key">{{ scanner.device_key }}</span>
                        <span
                          class="scanner-card__presence"
                          :class="scannerIsOnline(scanner) ? 'is-online' : 'is-offline'"
                          :title="scannerIsOnline(scanner) ? 'Bereit' : 'Längere Zeit nicht erreichbar'"
                        />
                      </div>
                      <span class="scanner-card__meta">{{ scannerLastSeenLabel(scanner) }}</span>
                    </div>
                  </div>
                  <div class="scanner-card__header-end">
                    <span
                      v-if="scannerSavingIds.has(scanner.id)"
                      class="scanner-card__savestate"
                    >
                      <v-progress-circular indeterminate size="13" width="2" />
                      Speichern…
                    </span>
                    <span
                      v-else-if="scannerSavedIds.has(scanner.id)"
                      class="scanner-card__savestate scanner-card__savestate--done"
                    >
                      <v-icon size="14">mdi-check</v-icon>
                      Gespeichert
                    </span>
                    <v-switch
                      v-model="scanner.enabled"
                      color="primary"
                      density="compact"
                      hide-details
                      inset
                      @update:model-value="() => scheduleScannerSave(scanner, 200)"
                    />
                  </div>
                </div>

                <div class="scanner-card__grid">
                  <v-text-field
                    v-model="scanner.name"
                    label="Name"
                    density="compact"
                    variant="outlined"
                    hide-details
                    @update:model-value="() => scheduleScannerSave(scanner)"
                  />
                  <v-autocomplete
                    v-model="scanner.recipient_user_ids"
                    :items="scannerUserOptions"
                    label="Empfänger"
                    density="compact"
                    variant="outlined"
                    hide-details
                    chips
                    closable-chips
                    multiple
                    :menu-props="{ attach: 'body', zIndex: 6000 }"
                    @update:model-value="() => scheduleScannerSave(scanner, 200)"
                  >
                    <template #chip="{ props: chipProps, item }">
                      <v-chip
                        v-bind="chipProps"
                        color="primary"
                        variant="tonal"
                        size="small"
                        class="scanner-card__recipient-chip"
                      >
                        <template #prepend>
                          <UserAvatar
                            :user="item.raw.user"
                            :size="20"
                            class="scanner-card__recipient-avatar"
                          />
                        </template>
                        {{ item.title }}
                      </v-chip>
                    </template>
                    <template #item="{ props: itemProps, item }">
                      <v-list-item v-bind="itemProps">
                        <template #prepend>
                          <UserAvatar :user="item.raw.user" :size="28" />
                        </template>
                      </v-list-item>
                    </template>
                  </v-autocomplete>
                </div>
              </div>
            </div>

            <div class="pm-settings-subhead">Import</div>
            <div class="pm-settings-subhead-hint">Gilt für alle Scanner und Importquellen.</div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAutoOpenImportInboxFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoOpenImportInboxFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Importfenster bei neuen Scans öffnen</div>
                <div class="pm-setting-description">
                  Öffnet automatisch den Importdialog, sobald neue Scans im Posteingang erkannt werden.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.documents.auto_open_import_inbox"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.auto_open_import_inbox"
                :disabled="isSettingSaving.auto_open_import_inbox"
                @click.stop
                @update:model-value="onAutoOpenImportInboxChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleScanLivePageModeFromRow"
              @keydown="handleSettingRowShortcut($event, toggleScanLivePageModeFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Seiten sofort senden</div>
                <div class="pm-setting-description">
                  Jede gescannte Seite wird sofort ins Importfenster gesendet, ohne auf die
                  Abschluss-Taste zu warten.
                </div>
              </div>
              <v-switch
                :model-value="settingsDraft.documents.scan_live_page_mode"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.scan_live_page_mode"
                :disabled="isSettingSaving.scan_live_page_mode"
                @click.stop
                @update:model-value="onScanLivePageModeChange"
              />
            </div>

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleAutoOcrFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoOcrFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Automatisches OCR</div>
                <div class="pm-setting-description">
                  Extrahiert Text nach dem Import im Hintergrund und macht neue Dokumente durchsuchbar.
                </div>
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
              :class="{ 'pm-setting-row--disabled': !settingsDraft.documents.auto_ocr }"
              role="button"
              tabindex="0"
              @click="toggleAutoTaggingFromRow"
              @keydown="handleSettingRowShortcut($event, toggleAutoTaggingFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">KI-Analyse nach dem Import</div>
                <div class="pm-setting-description">
                  Ergänzt nach dem Import automatisch Metadaten und Tags.
                </div>
                <div v-if="!settingsDraft.documents.auto_ocr" class="pm-setting-hint">
                  Benötigt „Automatisches OCR" – ohne extrahierten Text gibt es nichts zu analysieren.
                </div>
                <div v-else-if="settingsDraft.documents.auto_tagging" class="pm-setting-hint">
                  Nutzt die unter „Texterkennung" konfigurierte lokale KI.
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

            <div class="pm-setting-row pm-setting-row--column">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Erkennungssprache</div>
                <div class="pm-setting-description">
                  Standardsprache für die Texterkennung beim Import.
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

            <div
              class="pm-setting-row"
              role="button"
              tabindex="0"
              @click="toggleScanEnhancementFromRow"
              @keydown="handleSettingRowShortcut($event, toggleScanEnhancementFromRow)"
            >
              <div class="pm-setting-content">
                <div class="pm-setting-label">Seitenverbesserung</div>
                <div class="pm-setting-description">
                  Glättet Faltenschatten und ungleichmäßige Beleuchtung, damit gescannte Seiten
                  einen richtig weißen Hintergrund bekommen. Wirkt auf das durchsuchbare Dokument
                  nach dem Import.
                </div>
              </div>
              <v-switch
                :model-value="scanEnhancementEnabled"
                color="primary"
                density="comfortable"
                hide-details
                inset
                :loading="isSettingSaving.scan_cleanup"
                :disabled="isSettingSaving.scan_cleanup"
                @click.stop
                @update:model-value="onScanEnhancementToggle"
              />
            </div>

            <div v-if="scanEnhancementEnabled" class="pm-setting-row pm-setting-row--column pm-setting-row--nested">
              <div class="pm-setting-content">
                <div class="pm-setting-label">Modus der Seitenverbesserung</div>
                <div class="pm-setting-description">
                  Schwarz-Weiß liefert einen sauberen S/W-Scan; „Weiß" erhält farbige Logos.
                </div>
              </div>
              <v-select
                :model-value="settingsDraft.ocr.scan_cleanup"
                :items="scanEnhancementModeOptions"
                density="comfortable"
                hide-details
                variant="outlined"
                class="settings-theme-select pm-setting-select"
                label="Modus"
                :loading="isSettingSaving.scan_cleanup"
                :disabled="isSettingSaving.scan_cleanup"
                @update:model-value="onScanCleanupChange"
              />
            </div>
          </div>
        </section>

        <section v-if="activeCategory === 'categories'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-file-document-multiple-outline"
              title="Dokumenttypen"
              subtitle="Auswahloptionen für den Import samt Dateiname-Templates verwalten."
            />

            <div class="settings-category-management">
              <div class="settings-category-header">
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

              <div class="settings-category-filter">
                <v-chip-group
                  v-model="documentTypeAreaFilter"
                  mandatory
                  selected-class="text-primary"
                >
                  <v-chip value="all" size="small" variant="outlined" filter>
                    Alle {{ categoryStore.sortedCategories.length }}
                  </v-chip>
                  <v-chip
                    v-for="area in documentTypeAreas"
                    :key="area.value"
                    :value="area.value"
                    size="small"
                    variant="outlined"
                    filter
                  >
                    {{ area.label }} {{ documentTypeAreaCounts[area.value] || 0 }}
                  </v-chip>
                  <v-chip value="unassigned" size="small" variant="outlined" filter>
                    Ohne Zuordnung {{ documentTypeAreaCounts.unassigned || 0 }}
                  </v-chip>
                </v-chip-group>
              </div>

              <div class="settings-categories">
                <div
                  v-for="cat in displayedDocumentTypes"
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
                          {{ documentTypeAreaLabel(cat.area) }}
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
                          @keydown.enter.prevent="scheduleCategoryAutosave(true)"
                          @blur="scheduleCategoryAutosave(true)"
                        />
                        <v-select
                          v-model="editingCategoryArea"
                          :items="documentTypeAreas"
                          item-title="label"
                          item-value="value"
                          density="compact"
                          variant="outlined"
                          hide-details
                          clearable
                          label="Bereich"
                          placeholder="Ohne Zuordnung"
                          @update:model-value="scheduleCategoryAutosave(true)"
                        />
                        <transition name="fade">
                          <span
                            v-if="categorySaveState !== 'idle'"
                            class="settings-correspondent-savestate"
                            :class="`settings-correspondent-savestate--${categorySaveState}`"
                          >
                            <v-icon size="14">
                              {{ categorySaveState === 'saving' ? 'mdi-cloud-sync-outline' : 'mdi-check-circle-outline' }}
                            </v-icon>
                            {{ categorySaveState === 'saving' ? 'Speichert…' : 'Gespeichert' }}
                          </span>
                        </transition>
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
                          @blur="scheduleCategoryAutosave(true)"
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

                <div
                  v-if="categoryStore.isLoading && categoryStore.sortedCategories.length === 0"
                  class="settings-vocab-loading"
                >
                  <v-progress-circular indeterminate size="24" width="2" color="primary" />
                  <span>Dokumenttypen werden geladen…</span>
                </div>
                <div v-else-if="displayedDocumentTypes.length === 0" class="settings-category-empty">
                  {{ categoryStore.sortedCategories.length === 0
                    ? 'Noch keine Dokumenttypen angelegt.'
                    : 'Keine Dokumenttypen in diesem Bereich.' }}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeCategory === 'retention'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-folder-clock-outline"
              title="Aufbewahrung"
              subtitle="Grundlagen, aus denen die KI ihre Aufbewahrungs-Einschätzung ableitet."
            >
              <template #actions>
                <v-switch
                  :model-value="settingsDraft.retention.enabled"
                  color="primary"
                  hide-details
                  density="compact"
                  :true-value="true"
                  :false-value="false"
                  :loading="isSettingSaving.retention_enabled"
                  :disabled="isSettingSaving.retention_enabled"
                  @update:model-value="onRetentionEnabledChange"
                />
              </template>
            </SettingsInfoCard>

            <div
              class="settings-retention-config"
              :class="{ 'settings-retention-config--disabled': !settingsDraft.retention.enabled }"
            >
              <div class="pm-setting-row pm-setting-row--column">
                <div class="pm-setting-content">
                  <div class="pm-setting-label">Nutzung</div>
                  <div class="pm-setting-description">
                    Bestimmt den rechtlichen Rahmen: geschäftlich gelten die Fristen aus § 147 AO und § 257 HGB,
                    privat bestehen für die meisten Dokumente keine gesetzlichen Aufbewahrungspflichten.
                  </div>
                </div>
                <v-select
                  :model-value="settingsDraft.retention.usage_mode"
                  :items="retentionUsageOptions"
                  item-title="label"
                  item-value="value"
                  density="comfortable"
                  hide-details
                  variant="outlined"
                  class="settings-theme-select pm-setting-select"
                  label="Nutzung"
                  aria-label="Nutzung auswählen"
                  :loading="isSettingSaving.retention_usage_mode"
                  :disabled="!settingsDraft.retention.enabled || isSettingSaving.retention_usage_mode"
                  @update:model-value="onRetentionUsageChange"
                />
              </div>

              <div class="pm-setting-group">
                <div class="pm-setting-note pm-setting-note--group">
                  <strong>Regeltabelle</strong> — kuratierte Standardvorgaben pro Dokumenttyp. Sie fließen als Hausregel
                  in die KI-Bewertung ein; die KI übernimmt sie und beurteilt nur die Randfälle selbst.
                </div>

                <div class="settings-retention-rules">
                  <div
                    v-for="(rule, index) in settingsDraft.retention.rules"
                    :key="`rule-${index}-${rule.document_type}`"
                    class="settings-retention-rule"
                  >
                    <div class="settings-retention-rule__head">
                      <span class="settings-retention-rule__type">{{ rule.document_type }}</span>
                      <v-btn
                        icon="mdi-close"
                        size="x-small"
                        variant="text"
                        class="settings-retention-rule__remove"
                        :aria-label="`Regel für ${rule.document_type} entfernen`"
                        :disabled="!settingsDraft.retention.enabled || isSettingSaving.retention_rules"
                        @click="removeRetentionRule(index)"
                      />
                    </div>
                    <div class="settings-retention-rule__controls">
                      <v-select
                        :model-value="rule.paper_original"
                        :items="retentionPaperItems"
                        label="Papieroriginal"
                        density="compact"
                        variant="outlined"
                        hide-details
                        :disabled="!settingsDraft.retention.enabled || isSettingSaving.retention_rules"
                        @update:model-value="value => updateRetentionRule(index, 'paper_original', value)"
                      />
                      <v-select
                        :model-value="rule.period_years"
                        :items="retentionPeriodItems"
                        label="Frist"
                        density="compact"
                        variant="outlined"
                        hide-details
                        :disabled="!settingsDraft.retention.enabled || isSettingSaving.retention_rules"
                        @update:model-value="value => updateRetentionRule(index, 'period_years', value)"
                      />
                      <v-text-field
                        :model-value="rule.basis"
                        label="Grundlage"
                        density="compact"
                        variant="outlined"
                        hide-details
                        placeholder="z. B. § 147 AO"
                        class="settings-retention-rule__basis"
                        :disabled="!settingsDraft.retention.enabled || isSettingSaving.retention_rules"
                        @change="event => updateRetentionRule(index, 'basis', event.target.value)"
                      />
                    </div>
                  </div>

                  <div v-if="settingsDraft.retention.rules.length === 0" class="settings-retention-empty">
                    Noch keine Regeln. Füge unten einen Dokumenttyp hinzu.
                  </div>
                </div>

                <div class="settings-retention-add">
                  <v-select
                    v-model="newRetentionRuleType"
                    :items="availableRetentionRuleTypes"
                    placeholder="Dokumenttyp wählen…"
                    density="comfortable"
                    variant="outlined"
                    hide-details
                    no-data-text="Alle Dokumenttypen haben bereits eine Regel"
                    class="settings-retention-add__select"
                    :disabled="!settingsDraft.retention.enabled"
                  />
                  <v-btn
                    variant="tonal"
                    :disabled="!settingsDraft.retention.enabled || !newRetentionRuleType || isSettingSaving.retention_rules"
                    @click="addRetentionRule"
                  >
                    Regel hinzufügen
                  </v-btn>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeCategory === 'correspondents'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SettingsInfoCard
              icon="mdi-account-outline"
              title="Korrespondenten"
              subtitle="Absender, Aussteller und Sammelkorrespondenten pflegen und zuordnen."
            >
              <template #actions>
                <v-btn
                  icon
                  variant="tonal"
                  size="small"
                  class="settings-unresolved-info-action"
                  title="Offene Zuordnungen"
                  :loading="isUnresolvedCorrespondentsLoading"
                  @click="openUnresolvedCorrespondentsDialog"
                >
                  <v-icon size="19">mdi-file-document-outline</v-icon>
                  <span v-if="unresolvedCorrespondents.length" class="settings-unresolved-info-action__badge">
                    {{ unresolvedCorrespondents.length }}
                  </span>
                </v-btn>
              </template>
            </SettingsInfoCard>

            <div class="settings-category-management">
              <div class="settings-correspondent-create">
                <div class="settings-category-add settings-correspondent-add">
                  <v-text-field
                    v-model="newCorrespondentName"
                    maxlength="120"
                    density="compact"
                    variant="outlined"
                    hide-details
                    :placeholder="newCorrespondentPlaceholder"
                    :disabled="correspondentStore.isMutationRunning"
                    @keydown.enter.prevent="addCorrespondent"
                  >
                    <template #prepend-inner>
                      <v-menu>
                        <template #activator="{ props: activatorProps }">
                          <v-btn
                            v-bind="activatorProps"
                            icon
                            variant="text"
                            size="small"
                            class="settings-correspondent-kind-menu"
                            :title="correspondentKindLabel(newCorrespondentKind)"
                          >
                            <v-icon size="19">{{ correspondentKindIcon({ kind: newCorrespondentKind }) }}</v-icon>
                          </v-btn>
                        </template>
                        <v-list density="compact">
                          <v-list-item
                            title="Organisation"
                            prepend-icon="mdi-domain"
                            :active="newCorrespondentKind === 'organization'"
                            @click="newCorrespondentKind = 'organization'"
                          />
                          <v-list-item
                            title="Person"
                            prepend-icon="mdi-account-outline"
                            :active="newCorrespondentKind === 'person'"
                            @click="newCorrespondentKind = 'person'"
                          />
                          <v-list-item
                            title="Sammlung"
                            prepend-icon="mdi-shape-outline"
                            :active="newCorrespondentKind === 'collection'"
                            @click="newCorrespondentKind = 'collection'"
                          />
                        </v-list>
                      </v-menu>
                    </template>
                  </v-text-field>
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

              <div class="settings-correspondent-filter">
                <v-chip-group
                  v-model="correspondentTypeFilter"
                  mandatory
                  selected-class="text-primary"
                >
                  <v-chip value="all" size="small" variant="outlined" filter>
                    Alle {{ correspondentStore.correspondents.length }}
                  </v-chip>
                  <v-chip value="organization" size="small" variant="outlined" filter>
                    Organisationen {{ organizationCorrespondentCount }}
                  </v-chip>
                  <v-chip value="person" size="small" variant="outlined" filter>
                    Personen {{ personCorrespondentCount }}
                  </v-chip>
                  <v-chip value="collection" size="small" variant="outlined" filter>
                    Sammlungen {{ collectionCorrespondentCount }}
                  </v-chip>
                </v-chip-group>
              </div>

              <div class="settings-correspondents">
                <div
                  v-for="item in displayedCorrespondents"
                  :key="item.id"
                  class="settings-correspondent-row"
                  :class="{
                    'settings-correspondent-row--active': selectedCorrespondentId === item.id,
                    'settings-correspondent-row--nested':
                      correspondentTypeFilter === 'all' && correspondentIsNested(item),
                  }"
                >
                  <button
                    type="button"
                    class="settings-correspondent-summary"
                    @click="toggleCorrespondent(item)"
                  >
                    <span class="settings-category-main">
                      <span class="settings-category-icon" aria-hidden="true">
                        <v-icon size="16">{{ correspondentKindIcon(item) }}</v-icon>
                      </span>
                      <span class="settings-category-text">
                        <span class="settings-category-name">{{ item.name }}</span>
                        <span class="settings-category-meta">
                          {{ correspondentMetaText(item) }}
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
                      <div class="settings-correspondent-editor__head">
                        <v-btn-toggle
                          :model-value="editingCorrespondentKind"
                          density="compact"
                          variant="outlined"
                          divided
                          class="settings-correspondent-kind-toggle"
                          @update:model-value="onEditingKindChange"
                        >
                          <v-btn value="organization" size="small">
                            <v-icon size="16" start>mdi-domain</v-icon>Organisation
                          </v-btn>
                          <v-btn value="person" size="small">
                            <v-icon size="16" start>mdi-account-outline</v-icon>Person
                          </v-btn>
                          <v-btn value="collection" size="small">
                            <v-icon size="16" start>mdi-shape-outline</v-icon>Sammlung
                          </v-btn>
                        </v-btn-toggle>

                        <v-spacer />

                        <transition name="fade">
                          <span
                            v-if="correspondentSaveState !== 'idle'"
                            class="settings-correspondent-savestate"
                            :class="`settings-correspondent-savestate--${correspondentSaveState}`"
                          >
                            <v-icon size="14">
                              {{ correspondentSaveState === 'saving' ? 'mdi-cloud-sync-outline' : 'mdi-check-circle-outline' }}
                            </v-icon>
                            {{ correspondentSaveState === 'saving' ? 'Speichert…' : 'Gespeichert' }}
                          </span>
                        </transition>

                        <span class="settings-correspondent-delete-wrapper">
                          <v-btn
                            v-if="(item.usage_count || 0) > 0"
                            icon
                            variant="text"
                            size="small"
                            color="primary"
                            class="settings-correspondent-icon-action settings-correspondent-unlink"
                            :title="correspondentUnlinkTitle(item)"
                            :disabled="correspondentStore.isMutationRunning"
                            @click="openCorrespondentUnlinkConfirm(item)"
                          >
                            <v-icon size="18">mdi-link-off</v-icon>
                          </v-btn>
                          <v-btn
                            v-else
                            icon
                            variant="text"
                            size="small"
                            color="error"
                            class="settings-correspondent-icon-action settings-correspondent-delete"
                            title="Korrespondent löschen"
                            :disabled="correspondentStore.isMutationRunning"
                            @click="removeSelectedCorrespondent"
                          >
                            <v-icon size="18">mdi-trash-can-outline</v-icon>
                          </v-btn>
                        </span>
                      </div>

                      <div class="settings-correspondent-fields">
                        <div class="settings-correspondent-fields__name-row">
                          <v-text-field
                            v-model="editingCorrespondentName"
                            density="compact"
                            variant="outlined"
                            hide-details="auto"
                            label="Name"
                            maxlength="120"
                            :rules="[(v) => (v || '').trim().length >= 2 || 'Mindestens 2 Zeichen']"
                            @blur="scheduleCorrespondentAutosave(true)"
                          />
                          <v-text-field
                            v-model="editingCorrespondentShortName"
                            density="compact"
                            variant="outlined"
                            hide-details
                            label="Kurzname"
                            placeholder="optional"
                            maxlength="60"
                            @blur="scheduleCorrespondentAutosave(true)"
                          />
                        </div>
                        <v-select
                          v-if="editingCorrespondentKind === 'person'"
                          :model-value="editingCorrespondentParentId"
                          :items="organizationOptions.filter((o) => o.value !== item.id)"
                          density="compact"
                          variant="outlined"
                          hide-details
                          clearable
                          label="Gehört zu Organisation"
                          placeholder="Keine Zuordnung"
                          class="settings-correspondent-parent-select"
                          @update:model-value="onEditingParentChange"
                        />
                      </div>

                      <div class="settings-correspondent-block">
                        <div class="settings-inline-add">
                          <v-text-field
                            v-model="newAliasName"
                            density="compact"
                            variant="outlined"
                            hide-details
                            :label="correspondentAliasLabel(item)"
                            :placeholder="correspondentAliasPlaceholder(item)"
                            @keydown.enter.prevent="addAliasToSelected"
                          />
                          <v-btn
                            icon
                            variant="text"
                            color="primary"
                            class="settings-correspondent-icon-action"
                            :title="correspondentAliasAddTitle(item)"
                            :disabled="!newAliasName.trim() || correspondentStore.isMutationRunning"
                            @click="addAliasToSelected"
                          >
                            <v-icon size="18">mdi-plus</v-icon>
                          </v-btn>
                        </div>
                        <div v-if="item.aliases?.length" class="settings-chip-list">
                          <v-chip
                            v-for="alias in item.aliases"
                            :key="alias.id"
                            size="small"
                            closable
                            @click:close="removeAlias(alias)"
                          >
                            {{ alias.alias }}
                          </v-chip>
                        </div>
                      </div>

                    </div>
                  </div>
                </div>

                <div
                  v-if="correspondentStore.isLoading && correspondentStore.correspondents.length === 0"
                  class="settings-vocab-loading"
                >
                  <v-progress-circular indeterminate size="24" width="2" color="primary" />
                  <span>Korrespondenten werden geladen…</span>
                </div>
                <div v-else-if="correspondentStore.correspondents.length === 0" class="settings-category-empty">
                  Noch keine Korrespondenten angelegt.
                </div>
              </div>
            </div>

            <v-dialog v-model="unresolvedCorrespondentsDialogOpen" max-width="920">
              <v-card class="settings-unresolved-dialog">
                <v-card-title class="settings-unresolved-dialog__title">
                  <div>
                    <div>Offene Zuordnungen</div>
                    <div class="pm-setting-description">
                      {{ unresolvedCorrespondents.length }} Dokument{{ unresolvedCorrespondents.length === 1 ? '' : 'e' }} ohne Korrespondent.
                    </div>
                  </div>
                  <v-spacer />
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
                  <v-btn
                    icon
                    size="small"
                    variant="text"
                    title="Schließen"
                    @click="unresolvedCorrespondentsDialogOpen = false"
                  >
                    <v-icon size="18">mdi-close</v-icon>
                  </v-btn>
                </v-card-title>
                <v-divider />
                <v-card-text class="settings-unresolved-dialog__body">
                  <div v-if="isUnresolvedCorrespondentsLoading && !unresolvedCorrespondents.length" class="settings-unresolved-empty">
                    <v-progress-circular indeterminate size="22" width="2" />
                    <span>Offene Zuordnungen werden geladen…</span>
                  </div>
                  <div v-else-if="!unresolvedCorrespondents.length" class="settings-unresolved-empty">
                    Keine offenen Zuordnungen.
                  </div>
                  <div v-else class="settings-correspondent-review settings-correspondent-review--dialog">
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
                        :title="unresolvedRecognitionTitle(item.document_id)"
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
                </v-card-text>
              </v-card>
            </v-dialog>

            <ConfirmDialog
              v-model="collectionTypeConfirmOpen"
              title="In eine Sammlung umwandeln?"
              :description="collectionTypeConfirmDescription"
              primary-text="In Sammlung umwandeln"
              secondary-text="Abbrechen"
              icon="mdi-shape-outline"
              max-width="520"
              @primary="confirmCollectionTypeChange"
              @secondary="cancelCollectionTypeChange"
              @close="cancelCollectionTypeChange"
            />

            <ConfirmDialog
              v-model="correspondentUnlinkConfirmOpen"
              title="Alle Dokumentzuordnungen lösen?"
              :description="correspondentUnlinkConfirmDescription"
              primary-text="Zuordnungen lösen"
              secondary-text="Abbrechen"
              icon="mdi-link-off"
              max-width="540"
              :loading="correspondentStore.isMutationRunning"
              @primary="confirmCorrespondentUnlink"
              @secondary="cancelCorrespondentUnlink"
              @close="cancelCorrespondentUnlink"
            />
          </div>
        </section>

        <section v-if="activeCategory === 'ai'" class="pm-settings-section">
          <div class="pm-settings-content">

            <SettingsInfoCard
              icon="mdi-text-recognition"
              title="Texterkennung"
              subtitle="OCR-Wartung, Qualität und lokale KI-Engine."
            />

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

            <!-- Lokale KI-Engine für Import-Analyse und Chat. -->
            <div class="pm-setting-group">
            <div class="pm-setting-note pm-setting-note--group">
              <strong>Lokale KI (Ollama)</strong> bestimmt, womit Import-Analyse und Dokumenten-Chat arbeiten.
              Ob neue Importe automatisch analysiert werden, stellst du unter „Importieren" ein.
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

        <section v-if="activeCategory === 'backup'" class="pm-settings-section">
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

            <DestructiveDialog
              v-model="restoreConfirmOpen"
              max-width="540"
              persistent
              title="Wiederherstellen bestätigen"
              :header-subtitle="restoreTarget ? backupFormatArchiveDate(restoreTarget) : ''"
              primary-text="Wiederherstellen"
              secondary-text="Zurück"
              icon="mdi-backup-restore"
              danger-require-confirm-text="WIEDERHERSTELLEN"
              :loading="restoreStarting"
              @primary="confirmRestore"
            >
              <p class="backup-confirm-copy">
                Dies überschreibt die gesamte Datenbank und alle PDFs. Der aktuelle Stand geht verloren.
                Die App startet danach automatisch neu.
              </p>
            </DestructiveDialog>

            <DestructiveDialog
              v-model="deleteArchiveOpen"
              max-width="460"
              title="Backup löschen?"
              :header-subtitle="deleteTarget ? backupFormatArchiveDate(deleteTarget) : ''"
              primary-text="Löschen"
              secondary-text="Zurück"
              icon="mdi-delete-forever-outline"
              :loading="deleteArchiveBusy"
              @primary="confirmDeleteArchive"
            >
              <p class="backup-confirm-copy">
                Das Backup wird vom NAS entfernt. Das lässt sich nicht rückgängig machen.
              </p>
            </DestructiveDialog>
          </div>
        </section>

        <section v-if="activeCategory === 'controls'" class="pm-settings-section">
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

        <section v-if="activeCategory === 'system'" class="pm-settings-section">
          <div class="pm-settings-content">
            <SystemStatusPanel :active="activeCategory === 'system'" />
          </div>
        </section>

        <section v-if="activeCategory === 'services'" class="pm-settings-section">
          <div class="pm-settings-content">
            <ServiceStatusPanel :active="activeCategory === 'services'" />
          </div>
        </section>
        </div>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useTheme } from 'vuetify';
import BaseDialog from './BaseDialog.vue';
import ConfirmDialog from './ConfirmDialog.vue';
import DestructiveDialog from './DestructiveDialog.vue';
import SettingsInfoCard from './SettingsInfoCard.vue';
import UserAvatar from './UserAvatar.vue';
// Nur in den Admin-Tabs „Dienste"/„System" sichtbar → als eigene Chunks lazy
// geladen, damit sie den Haupt-Chunk des Dialogs nicht aufblähen.
const ServiceStatusPanel = defineAsyncComponent(() => import('./ServiceStatusPanel.vue'));
const SystemStatusPanel = defineAsyncComponent(() => import('./SystemStatusPanel.vue'));
import { getBaseUrl } from '../api/client';
import { useAuthStore } from '../stores/auth';
import { useSettingsStore } from '../stores/settings';
import { useCategoryStore } from '../stores/categories';
import { useCorrespondentStore } from '../stores/correspondents';
import { notifyError, useNotifications } from '../stores/notifications';
import { useTagStore } from '../stores/tags';
import { cleanupUnusedTags } from '../api/tags';
import { backfillOcr, patchDocument as apiPatchDocument } from '../api/documents';
import { listScanners, updateScanner } from '../api/scanners';
import { listUsers } from '../api/users';
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
  buildAutoOpenImportInboxPatch,
  buildScanLivePageModePatch,
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildOcrBackfillEnabledPatch,
  buildColorVariantPatch,
  buildDrawerRememberStatePatch,
  buildTagDrawerRememberStatePatch,
  buildSidebarShowRecentPatch,
  buildSidebarShowUntaggedPatch,
  buildSidebarShowNoTextPatch,
  buildSidebarShowChatPatch,
  buildOcrDocLangPatch,
  buildOcrScanCleanupPatch,
  buildPreviewDrawerGradientPatch,
  buildRecentImportWindowPatch,
  buildShowFilenameSuffixPatch,
  buildSidebarSectionsPatch,
  buildSidebarMaxTagsPatch,
  buildSidebarMaxCategoriesPatch,
  buildThemeModePatch,
  buildStartViewPatch,
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

const SETTINGS_ACTIVE_CATEGORY_STORAGE_KEY = 'pm.settings.activeCategory';

// ── Stores / Theme ───────────────────────────────────────────────────────────

const theme = useTheme();
const auth = useAuthStore();
const settingsStore = useSettingsStore();
const categoryStore = useCategoryStore();
const correspondentStore = useCorrespondentStore();

const VOCAB_NAME_MAX_LENGTH = 30;
const documentTypeAreas = [
  { value: 'finance', label: 'Finanzen' },
  { value: 'contracts_law', label: 'Verträge & Recht' },
  { value: 'insurance', label: 'Versicherungen' },
  { value: 'government_tax', label: 'Behörden & Steuern' },
  { value: 'employment', label: 'Personal' },
  { value: 'health', label: 'Gesundheit' },
  { value: 'access_it', label: 'Zugang & IT' },
  { value: 'other', label: 'Sonstiges' },
];
const documentTypeAreaLabels = Object.fromEntries(
  documentTypeAreas.map((area) => [area.value, area.label])
);
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
const scanLineAnimationEnabled = computed(() => settingsStore.scanLineAnimationEnabled);

const currentColorVariant = computed(() => settingsStore.settingsDraft.ui.color_variant || 'teal');

// ── Scanner-Einstellungen ───────────────────────────────────────────────────

const scannerDrafts = ref([]);
const scannerUsers = ref([]);
const scannerSettingsLoading = ref(false);
const scannerSettingsError = ref('');
const scannerDirtyIds = ref(new Set());
const scannerSavingIds = ref(new Set());
const scannerSavedIds = ref(new Set());
// Pro Scanner laufende Debounce-/Flash-Timer für das automatische Speichern.
const scannerSaveTimers = new Map();
const scannerSavedTimers = new Map();
let scannerSettingsLoaded = false;

const scannerUserOptions = computed(() =>
  scannerUsers.value
    .filter((user) => user?.is_active !== false)
    .map((user) => ({
      title: user.display_name || user.username,
      value: user.id,
      user,
      props: {
        subtitle: user.email || user.username
      }
    }))
);

function normalizeScannerDraft(scanner) {
  return {
    id: String(scanner?.id || '').trim(),
    device_key: String(scanner?.device_key || '').trim(),
    name: String(scanner?.name || '').trim(),
    enabled: scanner?.enabled !== false,
    last_seen_at: scanner?.last_seen_at || null,
    recipient_user_ids: Array.isArray(scanner?.recipients)
      ? scanner.recipients.map((user) => String(user?.id || '').trim()).filter(Boolean)
      : []
  };
}

function scannerLastSeenLabel(scanner) {
  if (!scanner?.last_seen_at) return 'noch nicht gesehen';
  try {
    return `zuletzt gesehen ${new Intl.DateTimeFormat('de-DE', {
      dateStyle: 'short',
      timeStyle: 'short'
    }).format(new Date(scanner.last_seen_at))}`;
  } catch {
    return 'zuletzt gesehen';
  }
}

// Optimistische Statusanzeige: Der Scanner gilt als in Ordnung (grün), solange
// er sich innerhalb der letzten 24 h gemeldet hat. Grau erst bei einem echten
// Problem – noch nie gesehen oder länger als 24 h stumm.
const SCANNER_STALE_MS = 24 * 60 * 60 * 1000;

function scannerIsOnline(scanner) {
  if (!scanner?.last_seen_at) return false;
  const seen = new Date(scanner.last_seen_at).getTime();
  if (Number.isNaN(seen)) return false;
  return Date.now() - seen <= SCANNER_STALE_MS;
}

function markScannerDirty(scannerId) {
  const next = new Set(scannerDirtyIds.value);
  next.add(scannerId);
  scannerDirtyIds.value = next;
}

// Auto-Save: Jede Änderung wird automatisch gesichert. Toggles/Empfänger
// speichern quasi sofort (kurzer Delay coalesct schnelle Mehrfachklicks),
// das Namensfeld wird beim Tippen entprellt.
function scheduleScannerSave(scanner, delay = 700) {
  if (!scanner?.id) return;
  const id = scanner.id;
  markScannerDirty(id);
  const existing = scannerSaveTimers.get(id);
  if (existing) clearTimeout(existing);
  const timer = setTimeout(() => {
    scannerSaveTimers.delete(id);
    // Läuft noch ein Speichervorgang, kurz später erneut versuchen.
    if (scannerSavingIds.value.has(id)) {
      scheduleScannerSave(scanner, 200);
      return;
    }
    saveScanner(scanner);
  }, delay);
  scannerSaveTimers.set(id, timer);
}

function flashScannerSaved(id) {
  const next = new Set(scannerSavedIds.value);
  next.add(id);
  scannerSavedIds.value = next;
  const existing = scannerSavedTimers.get(id);
  if (existing) clearTimeout(existing);
  const timer = setTimeout(() => {
    const done = new Set(scannerSavedIds.value);
    done.delete(id);
    scannerSavedIds.value = done;
    scannerSavedTimers.delete(id);
  }, 2000);
  scannerSavedTimers.set(id, timer);
}

onBeforeUnmount(() => {
  scannerSaveTimers.forEach((timer) => clearTimeout(timer));
  scannerSavedTimers.forEach((timer) => clearTimeout(timer));
  scannerSaveTimers.clear();
  scannerSavedTimers.clear();
});

async function loadScannerSettings({ force = false } = {}) {
  if (!auth.isAdmin) return;
  if (scannerSettingsLoading.value) return;
  if (scannerSettingsLoaded && !force) return;
  scannerSettingsLoading.value = true;
  scannerSettingsError.value = '';
  try {
    const [scannerPayload, userPayload] = await Promise.all([
      listScanners(),
      listUsers()
    ]);
    scannerDrafts.value = Array.isArray(scannerPayload?.items)
      ? scannerPayload.items.map(normalizeScannerDraft).filter((scanner) => scanner.id)
      : [];
    scannerUsers.value = Array.isArray(userPayload?.items) ? userPayload.items : [];
    scannerDirtyIds.value = new Set();
    scannerSettingsLoaded = true;
  } catch (error) {
    scannerSettingsError.value = error?.message || 'Scanner-Einstellungen konnten nicht geladen werden.';
    notifyError(error, 'Scanner-Einstellungen konnten nicht geladen werden.');
  } finally {
    scannerSettingsLoading.value = false;
  }
}

async function saveScanner(scanner) {
  if (!scanner?.id || scannerSavingIds.value.has(scanner.id)) return;
  const normalizedName = String(scanner.name || '').trim();
  // Auto-Save: bei (noch) leerem Namen nichts speichern, aber auch nicht stören.
  if (!normalizedName) return;
  const nextSaving = new Set(scannerSavingIds.value);
  nextSaving.add(scanner.id);
  scannerSavingIds.value = nextSaving;
  try {
    await updateScanner(scanner.id, {
      name: normalizedName,
      enabled: Boolean(scanner.enabled),
      recipient_user_ids: Array.isArray(scanner.recipient_user_ids) ? scanner.recipient_user_ids : []
    });
    // Den Draft bewusst NICHT durch die Server-Antwort ersetzen: Sonst würde
    // ein parallel weiter getipptes Namensfeld zurückspringen.
    const nextDirty = new Set(scannerDirtyIds.value);
    nextDirty.delete(scanner.id);
    scannerDirtyIds.value = nextDirty;
    flashScannerSaved(scanner.id);
  } catch (error) {
    notifyError(error, 'Scanner-Einstellungen konnten nicht gespeichert werden.');
  } finally {
    const doneSaving = new Set(scannerSavingIds.value);
    doneSaving.delete(scanner.id);
    scannerSavingIds.value = doneSaving;
  }
}

// ── Einstellungsnavigation ───────────────────────────────────────────────────

const settingsCategories = [
  { value: 'appearance', label: 'Darstellung', icon: 'mdi-palette-outline', group: 'surface' },
  { value: 'controls', label: 'Bedienung', icon: 'mdi-keyboard-outline', group: 'surface' },
  { value: 'sidebar', label: 'Seitenleiste', icon: 'mdi-page-layout-sidebar-left', group: 'surface' },
  { value: 'documents', label: 'Bibliothek', icon: 'mdi-archive-outline', group: 'surface', adminOnly: true },
  { value: 'import', label: 'Importieren', icon: 'mdi-tray-arrow-up', group: 'import', adminOnly: true },
  { value: 'ai', label: 'Texterkennung', icon: 'mdi-text-recognition', group: 'import', adminOnly: true },
  { value: 'categories', label: 'Dokumenttypen', icon: 'mdi-file-document-multiple-outline', group: 'documents' },
  { value: 'correspondents', label: 'Korrespondenten', icon: 'mdi-account-outline', group: 'documents' },
  { value: 'retention', label: 'Aufbewahrung', icon: 'mdi-folder-clock-outline', group: 'documents', adminOnly: true },
  { value: 'backup', label: 'Backup', icon: 'mdi-cloud-upload-outline', group: 'system', adminOnly: true },
  { value: 'services', label: 'Dienste', icon: 'mdi-server-network', group: 'system', adminOnly: true },
  { value: 'system', label: 'System', icon: 'mdi-raspberry-pi', group: 'system', adminOnly: true }
];
const settingsCategoryGroups = [
  { key: 'surface', label: 'Oberfläche' },
  { key: 'import', label: 'Import' },
  { key: 'documents', label: 'Dokumente' },
  { key: 'system', label: 'System' }
];
// Systemkonfigurations-Tabs nur für Admins; persönliche Darstellung sowie die
// Pro-Benutzer-Daten (Dokumenttypen/Korrespondenten) und die Kürzel-Referenz
// bleiben für alle sichtbar.
const visibleCategories = computed(() =>
  settingsCategories.filter((cat) => !cat.adminOnly || auth.isAdmin)
);
const visibleCategoryGroups = computed(() =>
  settingsCategoryGroups
    .map((group) => ({
      ...group,
      items: visibleCategories.value.filter((cat) => cat.group === group.key)
    }))
    .filter((group) => group.items.length > 0)
);

const activeCategory = ref('appearance');

function isVisibleCategory(categoryValue) {
  return visibleCategories.value.some((cat) => cat.value === categoryValue);
}

function readStoredSettingsCategory() {
  try {
    const stored = window.localStorage.getItem(SETTINGS_ACTIVE_CATEGORY_STORAGE_KEY);
    return isVisibleCategory(stored) ? stored : null;
  } catch {
    return null;
  }
}

function persistSettingsCategory(categoryValue) {
  if (!isVisibleCategory(categoryValue)) return;
  try {
    window.localStorage.setItem(SETTINGS_ACTIVE_CATEGORY_STORAGE_KEY, categoryValue);
  } catch {
    // ignore storage access errors
  }
}

function fallbackSettingsCategory() {
  return readStoredSettingsCategory() || visibleCategories.value[0]?.value || 'appearance';
}

function resolveInitialSettingsCategory(categoryValue) {
  if (categoryValue && isVisibleCategory(categoryValue)) {
    return categoryValue;
  }
  return fallbackSettingsCategory();
}

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

// Faules Laden der Sektionsdaten: Kategorien/Korrespondenten werden nicht mehr
// blockierend beim Rendern geholt. Die Flags verhindern, dass dieselben Daten
// innerhalb einer Dialog-Sitzung mehrfach nachgeladen werden; sie werden beim
// Öffnen zurückgesetzt (siehe modelValue-Watcher weiter unten).
let categoriesSectionLoaded = false;
let correspondentsSectionLoaded = false;
let unresolvedCorrespondentsLoaded = false;

function ensureCategoriesLoaded() {
  if (categoriesSectionLoaded) return;
  categoriesSectionLoaded = true;
  void categoryStore.fetchCategories();
}

function ensureCorrespondentsLoaded() {
  if (correspondentsSectionLoaded) return;
  correspondentsSectionLoaded = true;
  void correspondentStore.fetchCorrespondents();
}

function ensureUnresolvedCorrespondentsLoaded() {
  if (unresolvedCorrespondentsLoaded) return;
  unresolvedCorrespondentsLoaded = true;
  void loadUnresolvedCorrespondents();
}

function loadSectionData(value) {
  switch (value) {
    // „Aufbewahrung" nutzt die Dokumenttypen für die Regel-Auswahl, braucht die
    // Kategorien also ebenso wie der Kategorien-Tab selbst.
    case 'categories':
    case 'retention':
      ensureCategoriesLoaded();
      break;
    case 'correspondents':
      ensureCorrespondentsLoaded();
      ensureUnresolvedCorrespondentsLoaded();
      break;
    case 'import':
      void loadScannerSettings();
      break;
    case 'backup':
      backupSetupInitialized = false; // Panel-Zustand beim Betreten neu bestimmen
      loadBackup();
      break;
  }
}

watch(activeCategory, (value) => {
  persistSettingsCategory(value);
  loadSectionData(value);
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

const scanCleanupOptions = [
  { title: 'Schwarz-Weiß (empfohlen)', value: 'bw' },
  { title: 'Weiß, Farben erhalten', value: 'white' },
  { title: 'Aus (Original behalten)', value: 'off' }
];

const SCAN_CLEANUP_VALUES = new Set(scanCleanupOptions.map((e) => e.value));

// Seitenverbesserung als Ein/Aus-Schalter + Modus: „off" = aus, sonst
// „bw"/„white". scanEnhancementMode merkt sich den zuletzt aktiven Modus, damit
// Aus→Ein den vorherigen Modus wiederherstellt (Default S/W).
const scanEnhancementModeOptions = [
  { title: 'Schwarz-Weiß (empfohlen)', value: 'bw' },
  { title: 'Weiß, Farben erhalten', value: 'white' }
];
const scanEnhancementMode = ref('bw');
const scanEnhancementEnabled = computed(() => settingsDraft.ocr.scan_cleanup !== 'off');
watch(
  () => settingsDraft.ocr.scan_cleanup,
  (value) => {
    if (value === 'white' || value === 'bw') {
      scanEnhancementMode.value = value;
    }
  },
  { immediate: true }
);


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

// ── Startseite ───────────────────────────────────────────────────────────────

const START_VIEW_VALUES = new Set(['dashboard', 'all']);
const startViewOptions = [
  { label: 'Übersicht', value: 'dashboard' },
  { label: 'Alle Dokumente', value: 'all' }
];
const currentStartView = computed(() =>
  START_VIEW_VALUES.has(settingsDraft.ui.start_view) ? settingsDraft.ui.start_view : 'all'
);

async function onStartViewChange(nextValue) {
  if (isSettingSaving.start_view) return;
  const nextView = START_VIEW_VALUES.has(String(nextValue)) ? String(nextValue) : 'all';
  if (nextView === currentStartView.value) return;
  const previousView = currentStartView.value;
  settingsStore.setDraftPatch({ ui: { start_view: nextView } });
  await patchSettingsWithRevert({
    patch: buildStartViewPatch(nextView),
    controlKey: 'start_view',
    revert: () => {
      settingsStore.setDraftPatch({ ui: { start_view: previousView } });
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

async function onAutoOpenImportInboxChange(nextValue) {
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.auto_open_import_inbox) return;
  const previous = settingsDraft.documents.auto_open_import_inbox;
  settingsStore.setDraftPatch({ documents: { auto_open_import_inbox: nextBool } });
  await patchSettingsWithRevert({
    patch: buildAutoOpenImportInboxPatch(nextBool),
    controlKey: 'auto_open_import_inbox',
    revert: () => settingsStore.setDraftPatch({ documents: { auto_open_import_inbox: previous } })
  });
}

function toggleAutoOpenImportInboxFromRow() {
  if (isSettingSaving.auto_open_import_inbox) return;
  void onAutoOpenImportInboxChange(!settingsDraft.documents.auto_open_import_inbox);
}

async function onScanLivePageModeChange(nextValue) {
  if (isSettingSaving.scan_live_page_mode) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.documents.scan_live_page_mode) return;
  const previous = settingsDraft.documents.scan_live_page_mode;
  settingsStore.setDraftPatch({ documents: { scan_live_page_mode: nextBool } });
  await patchSettingsWithRevert({
    patch: buildScanLivePageModePatch(nextBool),
    controlKey: 'scan_live_page_mode',
    revert: () => settingsStore.setDraftPatch({ documents: { scan_live_page_mode: previous } })
  });
}

function toggleScanLivePageModeFromRow() {
  if (isSettingSaving.scan_live_page_mode) return;
  void onScanLivePageModeChange(!settingsDraft.documents.scan_live_page_mode);
}

// Seitenverbesserung ein/aus: aus → scan_cleanup='off', ein → gemerkter Modus.
async function onScanEnhancementToggle(nextValue) {
  if (isSettingSaving.scan_cleanup) return;
  const enable = Boolean(nextValue);
  const nextMode = enable ? (scanEnhancementMode.value || 'bw') : 'off';
  await onScanCleanupChange(nextMode);
}

function toggleScanEnhancementFromRow() {
  if (isSettingSaving.scan_cleanup) return;
  void onScanEnhancementToggle(!scanEnhancementEnabled.value);
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

// ── Aufbewahrungsregeln ──────────────────────────────────────────────────────

const retentionUsageOptions = [
  { value: 'private', label: 'Privat' },
  { value: 'business', label: 'Geschäftlich' }
];
const retentionPaperItems = [
  { title: 'Unklar', value: 'unclear' },
  { title: 'Original behalten', value: 'keep' },
  { title: 'Scan reicht', value: 'scan_sufficient' },
  { title: 'Kein Original nötig', value: 'not_applicable' }
];
const retentionPeriodItems = [
  { title: 'Unklar', value: null },
  { title: '2 Jahre', value: 2 },
  { title: '3 Jahre', value: 3 },
  { title: '6 Jahre', value: 6 },
  { title: '10 Jahre', value: 10 },
  { title: '30 Jahre', value: 30 },
  { title: 'Unbegrenzt', value: -1 }
];
const newRetentionRuleType = ref(null);

const availableRetentionRuleTypes = computed(() => {
  const used = new Set(
    settingsDraft.retention.rules.map((rule) => String(rule.document_type || '').trim().toLocaleLowerCase('de-DE'))
  );
  return categoryStore.categoryNames.filter(
    (name) => !used.has(String(name || '').trim().toLocaleLowerCase('de-DE'))
  );
});

function currentRetentionRulesSnapshot() {
  return settingsDraft.retention.rules.map((rule) => ({ ...rule }));
}

async function saveRetentionRules(nextRules, previousRules) {
  settingsStore.setDraftPatch({ retention: { rules: nextRules } });
  await patchSettingsWithRevert({
    patch: { retention: { rules: nextRules } },
    controlKey: 'retention_rules',
    revert: () => settingsStore.setDraftPatch({ retention: { rules: previousRules } })
  });
}

async function onRetentionEnabledChange(nextValue) {
  const enabled = nextValue !== false;
  if (enabled === settingsDraft.retention.enabled) return;
  const previous = settingsDraft.retention.enabled;
  settingsStore.setDraftPatch({ retention: { enabled } });
  await patchSettingsWithRevert({
    patch: { retention: { enabled } },
    controlKey: 'retention_enabled',
    revert: () => settingsStore.setDraftPatch({ retention: { enabled: previous } })
  });
}

async function onRetentionUsageChange(nextValue) {
  if (nextValue === settingsDraft.retention.usage_mode) return;
  const previous = settingsDraft.retention.usage_mode;
  settingsStore.setDraftPatch({ retention: { usage_mode: nextValue } });
  await patchSettingsWithRevert({
    patch: { retention: { usage_mode: nextValue } },
    controlKey: 'retention_usage_mode',
    revert: () => settingsStore.setDraftPatch({ retention: { usage_mode: previous } })
  });
}

async function addRetentionRule() {
  const name = String(newRetentionRuleType.value || '').trim();
  if (!name) return;
  const previous = currentRetentionRulesSnapshot();
  if (previous.some((rule) => String(rule.document_type).toLocaleLowerCase('de-DE') === name.toLocaleLowerCase('de-DE'))) {
    return;
  }
  const next = [...previous, { document_type: name, paper_original: 'unclear', period_years: null, basis: '' }];
  newRetentionRuleType.value = null;
  await saveRetentionRules(next, previous);
}

async function removeRetentionRule(index) {
  const previous = currentRetentionRulesSnapshot();
  if (index < 0 || index >= previous.length) return;
  const next = previous.filter((_, i) => i !== index);
  await saveRetentionRules(next, previous);
}

async function updateRetentionRule(index, field, value) {
  const previous = currentRetentionRulesSnapshot();
  if (index < 0 || index >= previous.length) return;
  let nextValue = value;
  if (field === 'basis') {
    nextValue = String(value || '').trim().slice(0, 200);
  } else if (field === 'period_years') {
    nextValue = value === null || value === '' ? null : Number(value);
  }
  if (previous[index][field] === nextValue) return;
  const next = previous.map((rule, i) => (i === index ? { ...rule, [field]: nextValue } : rule));
  await saveRetentionRules(next, previous);
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

// ── Scan-Bereinigung (weißer Hintergrund / S-W beim Import) ───────────────────

async function onScanCleanupChange(nextValue) {
  if (isSettingSaving.scan_cleanup) return;
  const nextMode = SCAN_CLEANUP_VALUES.has(String(nextValue))
    ? String(nextValue)
    : settingsDraft.ocr.scan_cleanup;
  if (nextMode === settingsDraft.ocr.scan_cleanup) return;
  const previous = settingsDraft.ocr.scan_cleanup;
  settingsStore.setDraftPatch({ ocr: { scan_cleanup: nextMode } });
  await patchSettingsWithRevert({
    patch: buildOcrScanCleanupPatch(nextMode),
    controlKey: 'scan_cleanup',
    revert: () => settingsStore.setDraftPatch({ ocr: { scan_cleanup: previous } })
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

// ── Vorschau-Verlauf ─────────────────────────────────────────────────────────

async function onPreviewDrawerGradientChange(nextValue) {
  if (isSettingSaving.preview_drawer_gradient) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.previewDrawerGradientEnabled) return;
  const previous = settingsDraft.ui.previewDrawerGradientEnabled;
  settingsStore.setDraftPatch({ ui: { previewDrawerGradientEnabled: nextBool } });
  await patchSettingsWithRevert({
    patch: buildPreviewDrawerGradientPatch(nextBool),
    controlKey: 'preview_drawer_gradient',
    revert: () => settingsStore.setDraftPatch({ ui: { previewDrawerGradientEnabled: previous } })
  });
}

function togglePreviewDrawerGradientFromRow() {
  if (isSettingSaving.preview_drawer_gradient) return;
  void onPreviewDrawerGradientChange(!settingsDraft.ui.previewDrawerGradientEnabled);
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

// ── Bibliothek-Einträge (optionale Sichtbarkeit) ─────────────────────────────

async function onSidebarShowRecentChange(nextValue) {
  if (isSettingSaving.sidebar_show_recent) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.sidebar_show_recent) return;
  const previous = settingsDraft.ui.sidebar_show_recent;
  settingsStore.setDraftPatch({ ui: { sidebar_show_recent: nextBool } });
  await patchSettingsWithRevert({
    patch: buildSidebarShowRecentPatch(nextBool),
    controlKey: 'sidebar_show_recent',
    revert: () => settingsStore.setDraftPatch({ ui: { sidebar_show_recent: previous } })
  });
}

async function onSidebarShowUntaggedChange(nextValue) {
  if (isSettingSaving.sidebar_show_untagged) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.sidebar_show_untagged) return;
  const previous = settingsDraft.ui.sidebar_show_untagged;
  settingsStore.setDraftPatch({ ui: { sidebar_show_untagged: nextBool } });
  await patchSettingsWithRevert({
    patch: buildSidebarShowUntaggedPatch(nextBool),
    controlKey: 'sidebar_show_untagged',
    revert: () => settingsStore.setDraftPatch({ ui: { sidebar_show_untagged: previous } })
  });
}

async function onSidebarShowNoTextChange(nextValue) {
  if (isSettingSaving.sidebar_show_no_text) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.sidebar_show_no_text) return;
  const previous = settingsDraft.ui.sidebar_show_no_text;
  settingsStore.setDraftPatch({ ui: { sidebar_show_no_text: nextBool } });
  await patchSettingsWithRevert({
    patch: buildSidebarShowNoTextPatch(nextBool),
    controlKey: 'sidebar_show_no_text',
    revert: () => settingsStore.setDraftPatch({ ui: { sidebar_show_no_text: previous } })
  });
}

async function onSidebarShowChatChange(nextValue) {
  if (isSettingSaving.sidebar_show_chat) return;
  const nextBool = Boolean(nextValue);
  if (nextBool === settingsDraft.ui.sidebar_show_chat) return;
  const previous = settingsDraft.ui.sidebar_show_chat;
  settingsStore.setDraftPatch({ ui: { sidebar_show_chat: nextBool } });
  await patchSettingsWithRevert({
    patch: buildSidebarShowChatPatch(nextBool),
    controlKey: 'sidebar_show_chat',
    revert: () => settingsStore.setDraftPatch({ ui: { sidebar_show_chat: previous } })
  });
}

// ── Animationen ──────────────────────────────────────────────────────────────

function onAnimationsEnabledChange(nextValue) {
  settingsStore.setAnimationsEnabled(Boolean(nextValue));
}

function toggleAnimationsFromRow() {
  settingsStore.setAnimationsEnabled(!settingsStore.animationsEnabled);
}

function onScanLineAnimationEnabledChange(nextValue) {
  settingsStore.setScanLineAnimationEnabled(Boolean(nextValue));
}

function toggleScanLineAnimationFromRow() {
  settingsStore.setScanLineAnimationEnabled(!settingsStore.scanLineAnimationEnabled);
}

// ── Dokumenttypen-Verwaltung ───────────────────────────────────────────────────

const newCategoryName = ref('');
const documentTypeAreaFilter = ref('all');
const selectedCategoryId = ref(null);
const editingCategoryName = ref('');
const editingCategoryTemplate = ref('');
const editingCategoryArea = ref(null);
// Auto-Speichern (analog Korrespondenten): dezenter Status statt Speichern-Button.
const categorySaveState = ref('idle'); // 'idle' | 'saving' | 'saved'
let categoryAutosaveTimer = null;
let categorySavedResetTimer = null;
let suppressCategoryAutosave = false;

const newCorrespondentName = ref('');
const newCorrespondentKind = ref('organization');
const correspondentTypeFilter = ref('all');
const selectedCorrespondentId = ref(null);
const editingCorrespondentName = ref('');
const editingCorrespondentShortName = ref('');
const editingCorrespondentKind = ref(null);
const editingCorrespondentParentId = ref(null);
const collectionTypeConfirmOpen = ref(false);
const pendingCorrespondentKind = ref(null);
const correspondentUnlinkConfirmOpen = ref(false);
const pendingCorrespondentUnlink = ref(null);
// Auto-Speichern: Status für die dezente Anzeige statt eines Speichern-Buttons.
const correspondentSaveState = ref('idle'); // 'idle' | 'saving' | 'saved'
let correspondentAutosaveTimer = null;
let correspondentSavedResetTimer = null;
let suppressCorrespondentAutosave = false;
const newAliasName = ref('');
const unresolvedCorrespondents = ref([]);
const unresolvedSelections = ref({});
const unresolvedCorrespondentsDialogOpen = ref(false);
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

const documentTypeAreaCounts = computed(() => {
  const counts = { unassigned: 0 };
  for (const category of categoryStore.sortedCategories) {
    const key = category?.area || 'unassigned';
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
});

const displayedDocumentTypes = computed(() => {
  if (documentTypeAreaFilter.value === 'all') return categoryStore.sortedCategories;
  if (documentTypeAreaFilter.value === 'unassigned') {
    return categoryStore.sortedCategories.filter((category) => !category?.area);
  }
  return categoryStore.sortedCategories.filter(
    (category) => category?.area === documentTypeAreaFilter.value
  );
});

function documentTypeAreaLabel(area) {
  return documentTypeAreaLabels[area] || 'Ohne Zuordnung';
}

/** Weicht der Kategorie-Editor vom gespeicherten Stand ab? (steuert Auto-Speichern) */
function categoryEditorDirty() {
  const current = selectedCategory.value;
  if (!current) return false;
  const nextName = editingCategoryName.value.trim();
  if (!nextName) return false;
  return (
    nextName !== current.name ||
    editingCategoryTemplate.value.trim() !== (current.naming_template || '') ||
    (editingCategoryArea.value || null) !== (current.area || null)
  );
}

const categoryTemplatePreviewParts = computed(() =>
  renderCategoryTemplatePreviewParts(editingCategoryTemplate.value)
);

/**
 * Weicht der Editor-Zustand vom gespeicherten Korrespondenten ab? Steuert das
 * Auto-Speichern und schützt laufende Eingaben vor dem Re-Sync bei Listen-Reload.
 * Personen ohne Organisation sind erlaubt (Privatperson); eine Organisation
 * trägt nie einen Parent (UI erzwingt das beim Umschalten).
 */
function correspondentEditorDirty() {
  const current = selectedCorrespondent.value;
  if (!current) return false;
  const nextName = editingCorrespondentName.value.trim();
  if (!nextName) return false;
  const nextParentId =
    editingCorrespondentKind.value === 'person' ? editingCorrespondentParentId.value || null : null;
  return (
    nextName !== current.name ||
    (editingCorrespondentShortName.value.trim() || '') !== (current.short_name || '') ||
    (editingCorrespondentKind.value || null) !== (current.kind || null) ||
    nextParentId !== (current.parent_id || null)
  );
}

const correspondentNameSort = (a, b) => a.name.localeCompare(b.name, 'de-DE');

/** Organisationen als Auswahl für den Parent-Picker einer Person. */
const organizationOptions = computed(() =>
  correspondentStore.correspondents
    .filter((c) => c.kind === 'organization')
    .slice()
    .sort(correspondentNameSort)
    .map((c) => ({ title: c.name, value: c.id }))
);

const organizationCorrespondentCount = computed(
  () => correspondentStore.correspondents.filter((c) => c.kind === 'organization').length
);

const personCorrespondentCount = computed(
  () => correspondentStore.correspondents.filter((c) => c.kind === 'person').length
);

const collectionCorrespondentCount = computed(
  () => correspondentStore.correspondents.filter((c) => c.kind === 'collection').length
);

const newCorrespondentPlaceholder = computed(() => {
  if (newCorrespondentKind.value === 'person') return 'Neue Person…';
  if (newCorrespondentKind.value === 'collection') return 'Neue Sammlung…';
  return 'Neue Organisation…';
});

const collectionTypeConfirmDescription = computed(() => {
  if (editingCorrespondentKind.value === 'person') {
    return 'Die Person wird zu einer Sammlung. Eine bestehende Zuordnung zu einer Organisation wird dabei entfernt. Dokumentzuordnungen und Aliase bleiben erhalten.';
  }
  return 'Die Organisation wird zu einer Sammlung. Dokumentzuordnungen und Aliase bleiben erhalten; Aliase werden anschließend als Erkennungsnamen verwendet.';
});

/**
 * Korrespondenten gruppiert für die Liste: zuerst Sammelkorrespondenten, dann
 * jede Organisation gefolgt von ihren zugeordneten Personen, danach Personen
 * ohne Organisation und noch nicht typisierte Einträge.
 */
const displayedCorrespondents = computed(() => {
  const all = correspondentStore.correspondents;
  const byId = new Map(all.map((c) => [c.id, c]));
  const collections = all.filter((c) => c.kind === 'collection').slice().sort(correspondentNameSort);
  const orgs = all.filter((c) => c.kind === 'organization').slice().sort(correspondentNameSort);
  const personsByParent = new Map();
  const orphanPersons = [];
  const untyped = [];
  for (const c of all) {
    if (c.kind === 'person') {
      if (c.parent_id && byId.has(c.parent_id)) {
        if (!personsByParent.has(c.parent_id)) personsByParent.set(c.parent_id, []);
        personsByParent.get(c.parent_id).push(c);
      } else {
        orphanPersons.push(c);
      }
    } else if (c.kind !== 'organization' && c.kind !== 'collection') {
      untyped.push(c);
    }
  }
  const ordered = [...collections];
  for (const org of orgs) {
    ordered.push(org);
    for (const p of (personsByParent.get(org.id) || []).slice().sort(correspondentNameSort)) {
      ordered.push(p);
    }
  }
  for (const p of orphanPersons.slice().sort(correspondentNameSort)) ordered.push(p);
  for (const u of untyped.slice().sort(correspondentNameSort)) ordered.push(u);

  const filter = correspondentTypeFilter.value;
  if (filter === 'collection') return ordered.filter((c) => c.kind === 'collection');
  if (filter === 'organization') return ordered.filter((c) => c.kind === 'organization');
  if (filter === 'person') return ordered.filter((c) => c.kind === 'person');
  return ordered;
});

/** Einrückung: eine Person, die einer (vorhandenen) Organisation zugeordnet ist. */
function correspondentIsNested(item) {
  return Boolean(
    item?.kind === 'person' &&
      item?.parent_id &&
      correspondentStore.correspondents.some((c) => c.id === item.parent_id)
  );
}

function correspondentKindIcon(item) {
  if (item?.kind === 'organization') return 'mdi-domain';
  if (item?.kind === 'person') return 'mdi-account-outline';
  if (item?.kind === 'collection') return 'mdi-shape-outline';
  return 'mdi-help-circle-outline';
}

function correspondentKindLabel(kind) {
  if (kind === 'person') return 'Person';
  if (kind === 'collection') return 'Sammelkorrespondent';
  if (kind === 'organization') return 'Organisation';
  return 'Ohne Typ';
}

function correspondentAliasLabel(item) {
  return item?.kind === 'collection' ? 'Erkennungsnamen' : 'Aliase';
}

function correspondentAliasPlaceholder(item) {
  return item?.kind === 'collection' ? 'Erkennungsname hinzufügen…' : 'Alias hinzufügen…';
}

function correspondentAliasAddTitle(item) {
  return item?.kind === 'collection' ? 'Erkennungsname hinzufügen' : 'Alias hinzufügen';
}

function correspondentUnlinkTitle(item) {
  const usageCount = Number(item?.usage_count || 0);
  if (usageCount === 1) return 'Zuordnung zu 1 Dokument lösen';
  return `Zuordnungen zu ${usageCount} Dokumenten lösen`;
}

const correspondentUnlinkConfirmDescription = computed(() => {
  const item = pendingCorrespondentUnlink.value;
  const usageCount = Number(item?.usage_count || 0);
  if (!item || usageCount <= 0) return '';
  const assignmentText = usageCount === 1
    ? 'Die Zuordnung zu 1 Dokument'
    : `Die Zuordnungen zu ${usageCount} Dokumenten`;
  return `${assignmentText} werden gelöst. Der Korrespondent „${item.name}“ sowie seine Aliase bleiben erhalten.`;
});

function unresolvedRecognitionTitle(documentId) {
  const correspondent = correspondentStore.findById(unresolvedSelections.value[documentId]);
  return correspondent?.kind === 'collection'
    ? 'Absender als Erkennungsname hinzufügen und zuordnen'
    : 'Absender als Alias hinzufügen und zuordnen';
}

function correspondentMetaText(item) {
  const parts = [];
  if (item?.kind === 'person' && item?.parent_name) parts.push(item.parent_name);
  else if (!item?.kind) parts.push('ohne Typ');
  parts.push(item?.short_name || 'kein Kurzname');
  if (item?.kind === 'organization') {
    const personCount = correspondentStore.correspondents.filter(
      (correspondent) => correspondent.kind === 'person' && correspondent.parent_id === item.id
    ).length;
    parts.push(`${personCount} ${personCount === 1 ? 'Person' : 'Personen'}`);
  }
  const aliasCount = item?.aliases?.length || 0;
  if (item?.kind === 'collection') {
    parts.push(`${aliasCount} Erkennungsname${aliasCount === 1 ? '' : 'n'}`);
  } else {
    parts.push(`${aliasCount} Alias${aliasCount === 1 ? '' : 'e'}`);
  }
  return parts.join(' · ');
}

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
      // Neue Sitzung: Sektionsdaten dürfen wieder frisch geladen werden.
      categoriesSectionLoaded = false;
      correspondentsSectionLoaded = false;
      unresolvedCorrespondentsLoaded = false;
      const next = resolveInitialSettingsCategory(props.initialCategory);
      const unchanged = activeCategory.value === next;
      activeCategory.value = next;
      // Ändert sich die Kategorie, lädt der activeCategory-Watcher die Daten der
      // Zielsektion. Bleibt sie gleich (erneutes Öffnen auf denselben Tab), feuert
      // der Watcher nicht – dann stoßen wir das Laden hier direkt an.
      if (unchanged) loadSectionData(next);
      // Vorabladen im Hintergrund (nicht render-blockierend): Dokumenttypen und
      // Korrespondenten sind dadurch beim späteren Tab-Wechsel meist schon da.
      // Das schwerere „unresolved" bleibt bewusst tab-lokal.
      ensureCategoriesLoaded();
      ensureCorrespondentsLoaded();
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
      // Nur re-synchronisieren, wenn der Nutzer gerade nichts Ungespeichertes tippt
      // (verhindert, dass ein nebenläufiger Reload aktive Eingaben überschreibt).
      if (selected && !correspondentEditorDirty()) syncCorrespondentEditor(selected);
    }
  }
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
      // Laufende Eingaben nicht überschreiben.
      if (selected && !categoryEditorDirty()) syncCategoryEditor(selected);
    }
  }
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
  // Programmatisches Setzen darf kein Auto-Speichern auslösen.
  suppressCategoryAutosave = true;
  editingCategoryName.value = category?.name || '';
  editingCategoryTemplate.value = category?.naming_template || '';
  editingCategoryArea.value = category?.area || null;
  categorySaveState.value = 'idle';
  nextTick(() => {
    suppressCategoryAutosave = false;
  });
}

/** Speichert die Dokumenttyp-Änderungen automatisch (still, ohne Erfolgs-Toast). */
async function runCategoryAutosave() {
  const current = selectedCategory.value;
  if (!current) return;
  if (!editingCategoryName.value.trim()) return; // leerer Name: nicht speichern
  if (!categoryEditorDirty()) return;
  categorySaveState.value = 'saving';
  try {
    await categoryStore.updateCategory(
      current.id,
      {
        name: editingCategoryName.value.trim(),
        naming_template: editingCategoryTemplate.value.trim() || null,
        area: editingCategoryArea.value || null,
      },
      { silent: true }
    );
    categorySaveState.value = 'saved';
    if (categorySavedResetTimer) clearTimeout(categorySavedResetTimer);
    categorySavedResetTimer = setTimeout(() => {
      if (categorySaveState.value === 'saved') categorySaveState.value = 'idle';
    }, 1800);
  } catch {
    // Fehler wird im Store als Notification gemeldet.
    categorySaveState.value = 'idle';
  }
}

/** Plant das Auto-Speichern: ``immediate`` beim Verlassen des Felds, sonst entprellt. */
function scheduleCategoryAutosave(immediate = false) {
  if (suppressCategoryAutosave) return;
  if (categoryAutosaveTimer) {
    clearTimeout(categoryAutosaveTimer);
    categoryAutosaveTimer = null;
  }
  if (immediate) {
    runCategoryAutosave();
    return;
  }
  categoryAutosaveTimer = setTimeout(runCategoryAutosave, 700);
}

// Felder: entprelltes Auto-Speichern beim Tippen.
watch(
  [editingCategoryName, editingCategoryTemplate, editingCategoryArea],
  () => scheduleCategoryAutosave(false)
);

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


function syncCorrespondentEditor(correspondent) {
  // Programmatisches Setzen darf kein Auto-Speichern auslösen.
  suppressCorrespondentAutosave = true;
  editingCorrespondentName.value = correspondent?.name || '';
  editingCorrespondentShortName.value = correspondent?.short_name || '';
  editingCorrespondentKind.value = correspondent?.kind || null;
  editingCorrespondentParentId.value = correspondent?.parent_id || null;
  correspondentSaveState.value = 'idle';
  // Erst nach dem Durchlaufen der Watches wieder freigeben.
  nextTick(() => {
    suppressCorrespondentAutosave = false;
  });
}

function clearCorrespondentAutosaveTimer() {
  if (!correspondentAutosaveTimer) return;
  clearTimeout(correspondentAutosaveTimer);
  correspondentAutosaveTimer = null;
}

/** Speichert die Editor-Änderungen automatisch (still, ohne Erfolgs-Toast). */
async function runCorrespondentAutosave() {
  const current = selectedCorrespondent.value;
  if (!current) return;
  const name = editingCorrespondentName.value.trim();
  if (name.length < 2) return; // ungültiger Name: nicht speichern (Feld zeigt Hinweis)
  if (!correspondentEditorDirty()) return;
  correspondentSaveState.value = 'saving';
  try {
    await correspondentStore.updateCorrespondent(
      current.id,
      {
        name,
        short_name: editingCorrespondentShortName.value.trim() || null,
        kind: editingCorrespondentKind.value || null,
        parent_id:
          editingCorrespondentKind.value === 'person' ? editingCorrespondentParentId.value || null : null,
      },
      { silent: true }
    );
    correspondentSaveState.value = 'saved';
    if (correspondentSavedResetTimer) clearTimeout(correspondentSavedResetTimer);
    correspondentSavedResetTimer = setTimeout(() => {
      if (correspondentSaveState.value === 'saved') correspondentSaveState.value = 'idle';
    }, 1800);
  } catch {
    // Fehler wird im Store als Notification gemeldet.
    correspondentSaveState.value = 'idle';
  }
}

/** Plant das Auto-Speichern: ``immediate`` für Typ/Organisation, sonst entprellt. */
function scheduleCorrespondentAutosave(immediate = false) {
  if (suppressCorrespondentAutosave) return;
  clearCorrespondentAutosaveTimer();
  if (immediate) {
    runCorrespondentAutosave();
    return;
  }
  correspondentAutosaveTimer = setTimeout(runCorrespondentAutosave, 700);
}

// Textfelder: entprelltes Auto-Speichern beim Tippen.
watch([editingCorrespondentName, editingCorrespondentShortName], () => scheduleCorrespondentAutosave(false));

/** Beim Umschalten des Typs die Zwei-Ebenen-Regel spiegeln und sofort speichern. */
function onEditingKindChange(nextKind) {
  const current = selectedCorrespondent.value;
  if (!current || !nextKind || nextKind === editingCorrespondentKind.value) return;
  if (nextKind === 'collection' && editingCorrespondentKind.value !== 'collection') {
    if (current.kind === 'organization') {
      const assignedPersons = correspondentStore.correspondents.filter(
        (correspondent) => correspondent.kind === 'person' && correspondent.parent_id === current.id
      ).length;
      if (assignedPersons > 0) {
        notify({
          type: 'warning',
          message: `Typ kann nicht geändert werden: ${assignedPersons} ${
            assignedPersons === 1 ? 'Person ist' : 'Personen sind'
          } dieser Organisation zugeordnet.`,
        });
        return;
      }
    }
    pendingCorrespondentKind.value = nextKind;
    collectionTypeConfirmOpen.value = true;
    return;
  }
  applyEditingKindChange(nextKind);
}

function applyEditingKindChange(nextKind) {
  editingCorrespondentKind.value = nextKind || null;
  // Nur Personen dürfen einer Organisation zugeordnet sein.
  if (nextKind !== 'person') {
    editingCorrespondentParentId.value = null;
  }
  scheduleCorrespondentAutosave(true);
}

function confirmCollectionTypeChange() {
  const nextKind = pendingCorrespondentKind.value;
  collectionTypeConfirmOpen.value = false;
  pendingCorrespondentKind.value = null;
  if (nextKind) applyEditingKindChange(nextKind);
}

function cancelCollectionTypeChange() {
  collectionTypeConfirmOpen.value = false;
  pendingCorrespondentKind.value = null;
}

/** Organisations-Zuordnung geändert → sofort speichern. */
function onEditingParentChange(value) {
  editingCorrespondentParentId.value = value || null;
  scheduleCorrespondentAutosave(true);
}

function selectCorrespondent(correspondent) {
  // Ein Timer des vorherigen Editors darf nicht nach dem Wechsel mit dessen
  // Feldwerten auf dem neu ausgewählten Korrespondenten speichern.
  clearCorrespondentAutosaveTimer();
  selectedCorrespondentId.value = correspondent?.id || null;
  syncCorrespondentEditor(correspondent);
  newAliasName.value = '';
}

function toggleCorrespondent(correspondent) {
  if (selectedCorrespondentId.value === correspondent?.id) {
    clearCorrespondentAutosaveTimer();
    selectedCorrespondentId.value = null;
    return;
  }
  selectCorrespondent(correspondent);
}

async function addCorrespondent() {
  const name = newCorrespondentName.value.trim();
  if (!name || correspondentStore.isMutationRunning) return;
  try {
    const result = await correspondentStore.createCorrespondentByName(name, {
      kind: newCorrespondentKind.value,
    });
    if (result.ok) {
      newCorrespondentName.value = '';
      // createCorrespondentByName lädt die Liste neu. Den vollständigen neuen
      // Datensatz in den Editor übernehmen, statt nur seine ID zu selektieren
      // und dadurch die Feldwerte der zuvor geöffneten Karte beizubehalten.
      const created = correspondentStore.findById(result.id);
      if (created) selectCorrespondent(created);
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

function openUnresolvedCorrespondentsDialog() {
  unresolvedCorrespondentsDialogOpen.value = true;
  void loadUnresolvedCorrespondents();
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

async function removeSelectedCorrespondent() {
  const current = selectedCorrespondent.value;
  if (!current || (current.usage_count || 0) > 0) return;
  try {
    await correspondentStore.deleteCorrespondent(current.id);
  } catch {
    /* Fehler wird im Store als Notification gemeldet */
  }
}

function openCorrespondentUnlinkConfirm(item) {
  if (!item || Number(item.usage_count || 0) <= 0) return;
  pendingCorrespondentUnlink.value = item;
  correspondentUnlinkConfirmOpen.value = true;
}

function cancelCorrespondentUnlink() {
  if (correspondentStore.isMutationRunning) return;
  correspondentUnlinkConfirmOpen.value = false;
  pendingCorrespondentUnlink.value = null;
}

async function confirmCorrespondentUnlink() {
  const item = pendingCorrespondentUnlink.value;
  if (!item || correspondentStore.isMutationRunning) return;
  try {
    await correspondentStore.unlinkDocuments(item.id);
    correspondentUnlinkConfirmOpen.value = false;
    pendingCorrespondentUnlink.value = null;
    emit('reload-imports');
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

<style scoped src="./SettingsDialog.styles.css"></style>
