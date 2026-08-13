<template>
  <div class="dossier-main" :class="{ 'dossier-main--embedded': embedded }">
    <div class="dossier-shell">
      <aside v-if="!embedded" class="dossier-sidebar">
        <div class="dossier-sidebar__head">
          <button class="dossier-brand" type="button" @click="goToDossiers">
            <span class="dossier-brand__mark"><v-icon size="18">mdi-brain</v-icon></span>
            <span>PaperMind</span>
          </button>
          <nav class="dossier-nav" aria-label="Hauptnavigation">
            <button type="button" @click="router.push('/')">
              <v-icon size="18">mdi-book-open-page-variant-outline</v-icon>
              <span>Dokumente</span>
            </button>
            <button class="dossier-nav__active" type="button" @click="goToDossiers">
              <v-icon size="18">mdi-file-document-multiple-outline</v-icon>
              <span>Akten</span>
              <span class="dossier-nav__count">{{ dossiers.length }}</span>
            </button>
          </nav>
          <v-text-field
            v-model="sidebarSearch"
            class="dossier-sidebar__search"
            prepend-inner-icon="mdi-magnify"
            placeholder="Akten suchen"
            density="compact"
            variant="outlined"
            hide-details
            clearable
          />
        </div>

        <div class="dossier-sidebar__list">
          <button
            v-for="entry in filteredSidebarDossiers"
            :key="entry.id"
            type="button"
            class="dossier-sidebar__entry"
            :class="{ 'dossier-sidebar__entry--active': entry.id === dossierId }"
            @click="openDossier(entry.id)"
          >
            <span class="dossier-sidebar__entry-icon" :style="{ '--dossier-color': entry.color || '#3b8f83' }">
              <v-icon size="16">mdi-folder-outline</v-icon>
            </span>
            <span class="dossier-sidebar__entry-copy">
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.document_count }} Dokumente</small>
            </span>
          </button>
          <div v-if="!loading && filteredSidebarDossiers.length === 0" class="dossier-sidebar__empty">
            Keine Akten gefunden.
          </div>
        </div>

        <div class="dossier-sidebar__foot">
          <button type="button" @click="uiStore.openSettings()">
            <v-icon size="18">mdi-cog-outline</v-icon><span>Einstellungen</span>
          </button>
        </div>
      </aside>

      <section v-if="!dossierId" key="overview" class="dossier-overview">
        <header class="dsr-ov__head">
          <div class="dsr-ov__heading">
            <h1>Leuchttische</h1>
            <p class="dsr-ov__sub">{{ overviewMeta }}</p>
          </div>
          <button v-if="!isTrueOverviewEmpty" type="button" class="dsr-btn dsr-btn--primary" @click="quickCreateDossier">
            <v-icon size="18">mdi-plus</v-icon>Neuer Leuchttisch
          </button>
        </header>

        <div class="dsr-ov__filters">
          <div class="dsr-seg" role="tablist" aria-label="Statusfilter">
            <button
              v-for="opt in overviewStateOptions"
              :key="opt.value"
              type="button"
              role="tab"
              class="dsr-seg__btn"
              :class="{ 'dsr-seg__btn--on': overviewState === opt.value }"
              @click="overviewState = opt.value"
            >{{ opt.label }}</button>
          </div>
          <div class="dsr-ov__spacer"></div>
          <v-menu location="bottom end">
            <template #activator="{ props }">
              <button type="button" class="dsr-sort" v-bind="props">
                <v-icon size="16">mdi-sort-variant</v-icon>
                {{ overviewSortLabel }}
                <v-icon size="15">mdi-chevron-down</v-icon>
              </button>
            </template>
            <v-list density="compact" min-width="190">
              <v-list-item
                v-for="option in overviewSortOptions"
                :key="option.value"
                :active="overviewSort === option.value"
                :title="option.label"
                @click="overviewSort = option.value"
              >
                <template #prepend>
                  <v-icon size="17">{{ overviewSort === option.value ? 'mdi-check' : 'mdi-sort' }}</v-icon>
                </template>
              </v-list-item>
            </v-list>
          </v-menu>
          <label class="dsr-search">
            <v-icon size="16">mdi-magnify</v-icon>
            <input v-model="overviewSearch" type="text" placeholder="Leuchttische durchsuchen" />
            <button v-if="overviewSearch" type="button" class="dsr-search__clear" aria-label="Suche leeren" @click="overviewSearch = ''">
              <v-icon size="15">mdi-close</v-icon>
            </button>
          </label>
        </div>

        <div v-if="loading" class="dsr-overview-grid dsr-overview-grid--loading" aria-label="Leuchttische werden geladen">
          <div v-for="index in 3" :key="index" class="dsr-tile dsr-tile--skeleton" aria-hidden="true">
            <div class="dsr-tile__preview"><span class="dsr-skeleton-block"></span></div>
            <div class="dsr-tile__body"><span></span><span></span><span></span></div>
          </div>
        </div>
        <div v-else-if="filteredOverviewDossiers.length" class="dsr-overview-scroll">
          <div
            class="dsr-overview-grid"
            :class="{
              'dsr-overview-grid--stagger': staggerOverviewTiles,
              'dsr-overview-grid--stagger-pending': overviewStaggerPending,
            }"
          >
            <article
              v-for="(entry, index) in filteredOverviewDossiers"
              :key="entry.id"
              class="dsr-tile"
              :style="{ '--dsr-tile-enter-delay': `${Math.min(index, 12) * 45}ms` }"
              role="button"
              tabindex="0"
              :aria-label="`${entry.title} öffnen`"
              @click="openDossier(entry.id)"
              @keydown.enter.prevent="openDossier(entry.id)"
              @keydown.space.prevent="openDossier(entry.id)"
            >
              <div class="dsr-tile__preview">
                <div class="dsr-tile__grid" aria-hidden="true"></div>
                <div class="dsr-tile__actions">
                  <button
                    type="button"
                    class="dsr-tile__action dsr-tile__favorite"
                    :class="{ 'dsr-tile__favorite--on': entry.is_favorite }"
                    :aria-label="entry.is_favorite ? 'Favorit entfernen' : 'Als Favorit markieren'"
                    :aria-pressed="Boolean(entry.is_favorite)"
                    @click.stop="toggleFavorite(entry)"
                  >
                    <v-icon size="16">{{ entry.is_favorite ? 'mdi-star' : 'mdi-star-outline' }}</v-icon>
                  </button>
                  <v-menu location="bottom end">
                    <template #activator="{ props }">
                      <button type="button" class="dsr-tile__action" aria-label="Leuchttisch-Aktionen" v-bind="props" @click.stop>
                        <v-icon size="17">mdi-dots-horizontal</v-icon>
                      </button>
                    </template>
                    <v-list density="compact" min-width="196" @click.stop>
                      <v-list-item prepend-icon="mdi-arrow-right" title="Öffnen" @click="openDossier(entry.id)" />
                      <v-list-item prepend-icon="mdi-pencil-outline" title="Umbenennen" @click="openEditDossier(entry)" />
                      <v-list-item prepend-icon="mdi-content-copy" title="Duplizieren" @click="duplicateOverviewDossier(entry)" />
                      <v-list-item
                        :prepend-icon="entry.archived_at ? 'mdi-restore' : 'mdi-archive-outline'"
                        :title="entry.archived_at ? 'Wiederherstellen' : 'Archivieren'"
                        @click="toggleArchive(entry)"
                      />
                      <v-divider />
                      <v-list-item prepend-icon="mdi-trash-can-outline" title="Löschen…" class="text-error" @click="askDeleteDossier(entry)" />
                    </v-list>
                  </v-menu>
                </div>

                <div class="dsr-stack">
                  <span
                    v-for="(documentId, index) in previewSlots(entry)"
                    :key="documentId || `empty-${index}`"
                    class="dsr-stack__doc"
                    :class="[`dsr-stack__doc--${index}`, {
                      'dsr-thumb': documentId,
                      'dsr-thumb--loaded': documentId && loadedThumbs.has(documentId),
                      'dsr-thumb--error': documentId && erroredThumbs.has(documentId),
                    }]"
                  >
                    <img
                      v-if="documentId"
                      :src="documentThumbnailUrl(documentId)"
                      alt=""
                      loading="lazy"
                      @load="markThumbLoaded(documentId)"
                      @error="markThumbErrored(documentId)"
                    />
                    <span v-else class="dsr-stack__paper-lines" aria-hidden="true"></span>
                  </span>
                </div>
              </div>

              <div class="dsr-tile__body">
                <h2>{{ entry.title }}</h2>
                <p class="dsr-tile__description">{{ overviewDescription(entry) }}</p>
                <footer class="dsr-tile__meta">
                  <span>{{ elementsSummary(entry) }}</span>
                  <span>{{ formatOverviewDate(entry) }}</span>
                </footer>
              </div>
            </article>

          </div>
        </div>
        <div v-else class="dossier-empty dossier-empty--overview">
          <div v-if="isTrueOverviewEmpty" class="dsr-board-empty__visual dsr-overview-empty__visual" aria-hidden="true">
            <span class="dsr-board-empty__sheet dsr-board-empty__sheet--note">
              <v-icon size="17">mdi-note-outline</v-icon>
              <i></i><i></i><i></i>
            </span>
            <span class="dsr-board-empty__sheet dsr-board-empty__sheet--document">
              <v-icon size="18">mdi-file-document-outline</v-icon>
              <i></i><i></i><i></i><i></i>
            </span>
            <span class="dsr-board-empty__sheet dsr-board-empty__sheet--link">
              <v-icon size="17">mdi-link-variant</v-icon>
              <i></i><i></i>
            </span>
            <span class="dsr-board-empty__plus"><v-icon size="18">mdi-plus</v-icon></span>
          </div>
          <v-icon v-else size="36">{{ overviewState === 'archived' ? 'mdi-archive-outline' : 'mdi-magnify' }}</v-icon>
          <h2>{{ overviewEmptyTitle }}</h2>
          <p>{{ overviewEmptyDescription }}</p>
          <button v-if="isTrueOverviewEmpty" type="button" class="dsr-btn dsr-btn--primary dsr-overview-empty__action" @click="quickCreateDossier">
            <v-icon size="18">mdi-plus</v-icon>Neuer Leuchttisch
          </button>
        </div>
      </section>

      <section v-else :key="`board-${dossierId}`" class="dossier-board-page">
        <div v-if="loading && !currentDossier" class="dossier-loading"><v-progress-circular indeterminate color="primary" /></div>
        <template v-else-if="currentDossier">
          <header class="dossier-board-header">
            <nav class="dossier-crumbs" aria-label="Brotkrumen">
              <button type="button" class="dossier-crumbs__root" @click="goToDossiers">
                <v-icon size="16">mdi-view-grid-outline</v-icon>Leuchttische
              </button>
              <v-icon size="15" class="dossier-crumbs__sep">mdi-chevron-right</v-icon>
              <span class="dossier-crumbs__current">
                <input
                  ref="boardTitleInput"
                  :value="currentDossier.title"
                  class="dossier-crumbs__title"
                  aria-label="Leuchttisch benennen"
                  spellcheck="false"
                  @change="commitBoardTitle"
                  @keydown.enter.prevent="$event.target.blur()"
                />
              </span>
            </nav>
            <label class="dsr-search dsr-search--board dossier-board-header__search">
              <v-icon size="16">mdi-magnify</v-icon>
              <input v-model="boardSearch" type="text" placeholder="Auf diesem Tisch suchen" aria-label="Auf diesem Tisch suchen" />
              <button v-if="boardSearch" type="button" class="dsr-search__clear" aria-label="Suche leeren" @click="boardSearch = ''"><v-icon size="15">mdi-close</v-icon></button>
            </label>
            <div class="dossier-board-header__right">
              <span class="dossier-board-header__meta">
                {{ items.length }} {{ items.length === 1 ? 'Element' : 'Elemente' }} · {{ formatRelativeDate(currentDossier.updated_at) }}
              </span>
              <button
                type="button"
                class="dsr-btn dsr-btn--icon"
                :class="{ 'dsr-btn--active': inspectorOpen && inspectorMode === 'dossier' }"
                aria-label="Leuchttisch-Eigenschaften"
                @click="toggleDossierInspector"
              >
                <v-icon size="18">mdi-information-outline</v-icon>
              </button>
            </div>
          </header>

          <div class="dossier-toolbar" role="toolbar" aria-label="Aktenwerkzeuge">
            <v-menu location="bottom start">
              <template #activator="{ props }">
                <button type="button" class="dsr-btn dsr-btn--primary" v-bind="props">
                  <v-icon size="18">mdi-plus</v-icon>Hinzufügen<v-icon size="16" class="dsr-btn__caret">mdi-chevron-down</v-icon>
                </button>
              </template>
              <v-list density="compact">
                <v-list-item prepend-icon="mdi-book-open-page-variant-outline" title="Aus Bibliothek" @click="openDocumentPicker" />
                <v-list-item prepend-icon="mdi-file-upload-outline" title="PDF hochladen" @click="uploadInput?.click()" />
                <v-divider />
                <v-list-item prepend-icon="mdi-note-plus-outline" title="Notiz" @click="openNoteDialog" />
                <v-list-item prepend-icon="mdi-link-variant-plus" title="Link" @click="openLinkDialog" />
              </v-list>
            </v-menu>
            <input ref="uploadInput" class="d-none" type="file" accept="application/pdf" multiple @change="uploadDocuments" />

            <template v-if="selectedItems.length">
              <div class="dossier-toolbar__divider"></div>
              <button
                v-if="selectedItems.length === 1 && selectedPdfItem"
                type="button"
                class="dsr-btn"
                :class="{ 'dsr-btn--active': inspectorOpen && inspectorMode === 'preview' }"
                :title="inspectorOpen && inspectorMode === 'preview' ? 'Vorschau schließen' : 'Vorschau öffnen'"
                @click="toggleSelectedPdfPreview"
              >
                <v-icon size="18">mdi-eye</v-icon>Vorschau
              </button>
              <button
                v-if="selectedItems.length === 1 && selectedAttachableItem"
                type="button"
                class="dsr-btn"
                :class="{ 'dsr-btn--active': selectedAttachableItem.attached_to_item_id }"
                @click="openConnectionDialog"
              >
                <v-icon size="18">mdi-link-variant</v-icon>{{ selectedAttachableItem.attached_to_item_id ? 'Verbindung' : 'Verbinden' }}
              </button>
              <v-menu location="bottom start">
                <template #activator="{ props }">
                  <button type="button" class="dsr-btn" v-bind="props">
                    <v-icon size="18">mdi-group</v-icon>Gruppieren<v-icon size="15">mdi-chevron-down</v-icon>
                  </button>
                </template>
                <v-list density="compact" min-width="210">
                  <v-list-item prepend-icon="mdi-plus" title="Neue Gruppe…" @click="openGroupDialog" />
                  <v-divider v-if="groups.length" />
                  <v-list-item
                    v-for="group in groups"
                    :key="group.id"
                    prepend-icon="mdi-shape-outline"
                    :title="group.title"
                    @click="assignSelectionToGroup(group.id, group.title)"
                  />
                  <v-divider />
                  <v-list-item prepend-icon="mdi-account-group-outline" title="Gruppierung lösen" @click="assignSelectionToGroup(null, 'Gruppierung lösen')" />
                </v-list>
              </v-menu>
              <v-menu v-if="selectedItems.length > 1" location="bottom start">
                <template #activator="{ props }">
                  <button type="button" class="dsr-btn" v-bind="props">
                    <v-icon size="18">mdi-align-horizontal-left</v-icon>Ausrichten<v-icon size="15">mdi-chevron-down</v-icon>
                  </button>
                </template>
                <v-list density="compact" min-width="190">
                  <v-list-subheader>Horizontal</v-list-subheader>
                  <v-list-item prepend-icon="mdi-align-horizontal-left" title="Links" @click="alignSelection('left', 'Links ausrichten')" />
                  <v-list-item prepend-icon="mdi-align-horizontal-center" title="Mittig" @click="alignSelection('center-x', 'Horizontal mittig ausrichten')" />
                  <v-list-item prepend-icon="mdi-align-horizontal-right" title="Rechts" @click="alignSelection('right', 'Rechts ausrichten')" />
                  <v-list-subheader>Vertikal</v-list-subheader>
                  <v-list-item prepend-icon="mdi-align-vertical-top" title="Oben" @click="alignSelection('top', 'Oben ausrichten')" />
                  <v-list-item prepend-icon="mdi-align-vertical-center" title="Mittig" @click="alignSelection('center-y', 'Vertikal mittig ausrichten')" />
                  <v-list-item prepend-icon="mdi-align-vertical-bottom" title="Unten" @click="alignSelection('bottom', 'Unten ausrichten')" />
                </v-list>
              </v-menu>
              <button type="button" class="dsr-btn dsr-btn--danger" @click="askRemoveSelectedItem"><v-icon size="18">mdi-delete-outline</v-icon>{{ selectedItems.length > 1 ? 'Entfernen' : 'Entfernen' }}</button>
            </template>

            <div class="dossier-toolbar__spacer"></div>
            <div class="dsr-history-actions" role="group" aria-label="Rückgängig und wiederholen">
              <button
                type="button"
                class="dsr-btn dsr-btn--icon dsr-fit-button"
                :disabled="!canUndo"
                :title="undoLabel ? `Rückgängig: ${undoLabel}` : 'Nichts rückgängig zu machen'"
                aria-label="Rückgängig"
                @click="undoBoardAction"
              ><v-icon size="18">mdi-undo</v-icon></button>
              <button
                type="button"
                class="dsr-btn dsr-btn--icon dsr-fit-button"
                :disabled="!canRedo"
                :title="redoLabel ? `Wiederholen: ${redoLabel}` : 'Nichts zu wiederholen'"
                aria-label="Wiederholen"
                @click="redoBoardAction"
              ><v-icon size="18">mdi-redo</v-icon></button>
            </div>
            <button
              v-if="items.length > 1"
              type="button"
              class="dsr-btn dsr-btn--icon dsr-fit-button"
              title="Sauber anordnen"
              aria-label="Elemente geordnet und ohne Überlappungen ausrichten"
              :disabled="arrangingBoard || drag.active"
              @click="arrangeBoard"
            >
              <v-icon size="18">mdi-auto-fix</v-icon>
            </button>
            <button
              v-if="items.length"
              type="button"
              class="dsr-btn dsr-btn--icon dsr-fit-button"
              title="Tisch einpassen"
              aria-label="Alle Elemente auf dem Leuchttisch einpassen"
              :disabled="arrangingBoard || drag.active"
              @click="fitBoardToViewport"
            >
              <v-icon size="18">mdi-arrow-expand</v-icon>
            </button>
            <v-menu location="bottom end">
              <template #activator="{ props }">
                <button
                  type="button"
                  class="dsr-size-picker"
                  v-bind="props"
                  :aria-label="`Miniaturgröße: ${densityLabel}`"
                >
                  <v-icon size="16">mdi-view-grid-outline</v-icon>
                  <span>{{ densityLabel }}</span>
                  <v-icon size="14" class="dsr-size-picker__caret">mdi-chevron-down</v-icon>
                </button>
              </template>
              <v-list density="compact" min-width="154" aria-label="Miniaturgröße">
                <v-list-item
                  v-for="opt in densityOptions"
                  :key="opt.value"
                  :title="opt.label"
                  :active="density === opt.value"
                  color="primary"
                  @click="density = opt.value"
                >
                  <template #append>
                    <v-icon v-if="density === opt.value" size="16">mdi-check</v-icon>
                  </template>
                </v-list-item>
              </v-list>
            </v-menu>
          </div>

          <div class="dossier-board-wrap">
            <main
              ref="wrapEl"
              class="dsr-canvas-wrap"
              :class="{ 'dsr-canvas-wrap--pan-ready': pan.spacePressed, 'dsr-canvas-wrap--panning': pan.active, 'dsr-canvas-wrap--fitting': viewFitting }"
              :style="boardViewportStyle"
              @pointerdown.capture="onBoardPointerDown"
              @wheel="onBoardWheel"
            >
              <div class="dsr-canvas-sizer">
                <div
                  ref="canvasEl"
                  class="dsr-canvas"
                  :class="{ 'dsr-canvas--dragging': drag.active, 'dsr-canvas--fitting': viewFitting }"
                  :style="{ width: canvasSize.w + 'px', height: canvasSize.h + 'px', transform: `translate3d(${boardView.x}px, ${boardView.y}px, 0) scale(${boardScale})` }"
                  @pointerdown="onCanvasBackgroundDown"
                >
                  <svg
                    v-if="dossierConnections.length"
                    class="dsr-connections"
                    :width="canvasSize.w"
                    :height="canvasSize.h"
                    :viewBox="`0 0 ${canvasSize.w} ${canvasSize.h}`"
                    aria-hidden="true"
                  >
                    <g
                      v-for="connection in dossierConnections"
                      :key="connection.id"
                      class="dsr-connection"
                      :class="{ 'dsr-connection--active': selectedItemIds.has(connection.sourceId) || selectedItemIds.has(connection.targetId) }"
                    >
                      <path class="dsr-connection__halo" :d="connection.path"></path>
                      <path class="dsr-connection__line" :d="connection.path"></path>
                    </g>
                  </svg>
                  <span
                    v-if="drag.guideX"
                    class="dsr-smart-guide dsr-smart-guide--vertical"
                    :style="smartGuideStyle(drag.guideX, 'x')"
                    aria-hidden="true"
                  ></span>
                  <span
                    v-if="drag.guideY"
                    class="dsr-smart-guide dsr-smart-guide--horizontal"
                    :style="smartGuideStyle(drag.guideY, 'y')"
                    aria-hidden="true"
                  ></span>
                  <span
                    v-if="selectionBox.active && selectionBox.moved"
                    class="dsr-selection-box"
                    :style="selectionBoxStyle"
                    aria-hidden="true"
                  ></span>
                  <div
                    v-for="item in items"
                    :key="item.id"
                    class="dsr-node"
                    :class="nodeClass(item)"
                    :style="nodeStyle(item)"
                    @pointerdown="startItemDrag(item, $event)"
                    @dblclick="openItem(item)"
                  >
                    <DossierItemCard
                      :item="item"
                      :selected="selectedItemIds.has(item.id)"
                      :dimmed="isDimmed(item)"
                      :thumbnail-url="documentThumbnailUrl"
                      :group-title="groupTitle(item.group_id)"
                    />
                  </div>
                </div>
              </div>

              <section v-if="!items.length" class="dsr-board-empty" aria-labelledby="dossier-empty-title">
                <div class="dsr-board-empty__content">
                  <div class="dsr-board-empty__visual" aria-hidden="true">
                    <span class="dsr-board-empty__sheet dsr-board-empty__sheet--note">
                      <v-icon size="17">mdi-note-outline</v-icon>
                      <i></i><i></i><i></i>
                    </span>
                    <span class="dsr-board-empty__sheet dsr-board-empty__sheet--document">
                      <v-icon size="18">mdi-file-document-outline</v-icon>
                      <i></i><i></i><i></i><i></i>
                    </span>
                    <span class="dsr-board-empty__sheet dsr-board-empty__sheet--link">
                      <v-icon size="17">mdi-link-variant</v-icon>
                      <i></i><i></i>
                    </span>
                    <span class="dsr-board-empty__plus"><v-icon size="18">mdi-plus</v-icon></span>
                  </div>

                  <h2 id="dossier-empty-title">Noch ist dieser Leuchttisch leer</h2>
                  <p>Füge ein Dokument, eine Notiz oder einen Link hinzu, um loszulegen.</p>

                  <div class="dsr-board-empty__actions" aria-label="Erstes Element hinzufügen">
                    <button type="button" class="dsr-board-empty__choice" @click="openDocumentPicker">
                      <span class="dsr-board-empty__choice-icon"><v-icon size="19">mdi-book-open-page-variant-outline</v-icon></span>
                      <span><strong>Aus Bibliothek</strong><small>Dokument auswählen</small></span>
                    </button>
                    <button type="button" class="dsr-board-empty__choice" @click="uploadInput?.click()">
                      <span class="dsr-board-empty__choice-icon"><v-icon size="19">mdi-file-upload-outline</v-icon></span>
                      <span><strong>PDF hochladen</strong><small>Neue Datei ablegen</small></span>
                    </button>
                    <button type="button" class="dsr-board-empty__choice" @click="openNoteDialog">
                      <span class="dsr-board-empty__choice-icon"><v-icon size="19">mdi-note-plus-outline</v-icon></span>
                      <span><strong>Notiz</strong><small>Gedanken festhalten</small></span>
                    </button>
                    <button type="button" class="dsr-board-empty__choice" @click="openLinkDialog">
                      <span class="dsr-board-empty__choice-icon"><v-icon size="19">mdi-link-variant-plus</v-icon></span>
                      <span><strong>Link</strong><small>Webseite verknüpfen</small></span>
                    </button>
                  </div>
                </div>
              </section>
            </main>

            <Transition name="dsr-inspector-slide">
              <div v-if="inspectorOpen" class="dsr-inspector-shell" :class="{ 'dsr-inspector-shell--preview': inspectorMode === 'preview' }">
                <aside class="dsr-inspector" :class="{ 'dsr-inspector--preview': inspectorMode === 'preview' }">
                  <template v-if="inspectorMode === 'preview'">
                    <button
                      type="button"
                      class="dsr-btn dsr-btn--icon dsr-btn--sm dsr-preview-close"
                      aria-label="Vorschau schließen"
                      title="Vorschau schließen"
                      @click="inspectorOpen = false"
                    >
                      <v-icon size="18">mdi-close</v-icon>
                    </button>
                    <div class="dsr-preview-body">
                      <PdfPreview
                        v-if="previewItem?.document_id"
                        :key="previewItem.id"
                        class="dsr-sidebar-pdf"
                        :src="documentFileUrl(previewItem.document_id, 'searchable')"
                        @first-page="previewReady = true"
                        @failed="previewReady = true"
                      />
                      <div v-else class="dsr-preview-empty">
                        <v-icon size="34">mdi-file-document-outline</v-icon>
                        <strong>Keine PDF ausgewählt</strong>
                        <span>Wähle eine einzelne PDF auf dem Leuchttisch aus.</span>
                      </div>
                      <Transition name="dsr-fade">
                        <div v-if="previewItem?.document_id && !previewReady" class="dsr-preview-skeleton" aria-hidden="true">
                          <div class="dsr-preview-skeleton__page">
                            <span class="dsr-skel-bar dsr-skel-bar--title"></span>
                            <span class="dsr-skel-bar dsr-skel-bar--sub"></span>
                            <span class="dsr-skel-block"></span>
                            <span class="dsr-skel-bar"></span>
                            <span class="dsr-skel-bar dsr-skel-bar--short"></span>
                            <span class="dsr-skel-bar"></span>
                            <span class="dsr-skel-bar"></span>
                            <span class="dsr-skel-bar dsr-skel-bar--short"></span>
                            <span class="dsr-preview-skeleton__sheen"></span>
                          </div>
                          <span class="dsr-preview-skeleton__caption">
                            <span class="dsr-preview-skeleton__dots"><i></i><i></i><i></i></span>
                            Vorschau wird geladen
                          </span>
                        </div>
                      </Transition>
                    </div>

                    <div v-if="previewItem" class="dsr-inspector__foot">
                      <button type="button" class="dsr-btn dsr-btn--primary dsr-btn--block" @click="openInLibrary(previewItem)">
                        <v-icon size="18">mdi-book-open-page-variant-outline</v-icon>Im Dokument öffnen
                      </button>
                    </div>
                  </template>

                  <template v-else>
                    <div class="dsr-inspector__head">
                      <div class="dsr-inspector__eyebrow">
                        <span>Leuchttisch</span>
                        <button type="button" class="dsr-btn dsr-btn--icon dsr-btn--sm" aria-label="Schließen" @click="inspectorOpen = false"><v-icon size="18">mdi-close</v-icon></button>
                      </div>
                      <strong class="dsr-inspector__title">{{ currentDossier.title }}</strong>
                      <div class="dsr-seg dsr-seg--full">
                        <button
                          v-for="tab in inspectorTabs"
                          :key="tab.value"
                          type="button"
                          class="dsr-seg__btn"
                          :class="{ 'dsr-seg__btn--on': inspectorTab === tab.value }"
                          @click="inspectorTab = tab.value"
                        >{{ tab.label }}</button>
                      </div>
                    </div>

                    <div class="dsr-inspector__body">
                      <dl v-if="inspectorTab === 'stamm'" class="dsr-kv">
                        <dt>Titel</dt><dd>{{ currentDossier.title }}</dd>
                        <template v-if="currentDossier.dossier_type"><dt>Art</dt><dd><span class="dsr-chip">{{ currentDossier.dossier_type }}</span></dd></template>
                        <template v-if="currentDossier.reference"><dt>Kennung</dt><dd class="dsr-mono">{{ currentDossier.reference }}</dd></template>
                        <template v-if="currentDossier.description"><dt>Notiz</dt><dd>{{ currentDossier.description }}</dd></template>
                      </dl>

                      <div v-else-if="inspectorTab === 'eigen'" class="dsr-props">
                        <template v-if="currentDossier.properties?.length">
                          <div v-for="property in currentDossier.properties" :key="property.id" class="dsr-props__row">
                            <span class="dsr-props__key">{{ property.label }}</span>
                            <span class="dsr-props__val">{{ propertyValue(property) }}</span>
                          </div>
                        </template>
                        <p v-else class="dsr-inspector__empty">Noch keine freien Eigenschaften. Zum Beispiel Kennzeichen, Vertragsnummer oder Ablageort.</p>
                      </div>

                      <p v-else class="dsr-inspector__empty">Es wird noch kein Verlauf aufgezeichnet.</p>
                    </div>

                    <div class="dsr-inspector__foot">
                      <button type="button" class="dsr-btn dsr-btn--primary dsr-btn--block" @click="openEditDossier(currentDossier)">
                        <v-icon size="18">mdi-pencil-outline</v-icon>Details bearbeiten
                      </button>
                    </div>
                  </template>
                </aside>
              </div>
            </Transition>
          </div>
        </template>
      </section>
    </div>

    <BaseDialog
      v-model="dossierDialogOpen"
      :title="dossierDialogMode === 'create' ? 'Neuer Leuchttisch' : 'Leuchttisch bearbeiten'"
      :description="'Titel genügt – alles Weitere ist optional.'"
      :primary-text="dossierDialogMode === 'create' ? 'Anlegen' : 'Speichern'"
      :loading="saving"
      :primary-disabled="!dossierDraft.title.trim()"
      max-width="720"
      scrollable
      @primary="saveDossier"
    >
      <div class="dossier-form">
        <v-text-field v-model="dossierDraft.title" label="Titel" variant="outlined" density="comfortable" autofocus />
        <div class="dossier-form__row">
          <v-combobox v-model="dossierDraft.dossier_type" :items="knownDossierTypes" label="Art (optional)" variant="outlined" density="comfortable" clearable />
          <v-text-field v-model="dossierDraft.reference" label="Kennung (optional)" variant="outlined" density="comfortable" clearable />
        </div>
        <v-textarea v-model="dossierDraft.description" label="Notiz (optional)" variant="outlined" density="comfortable" rows="2" auto-grow />
        <div class="dossier-form__color-row">
          <span>Farbe</span>
          <button
            v-for="color in dossierColors"
            :key="color"
            type="button"
            class="dossier-form__swatch"
            :class="{ 'dossier-form__swatch--active': dossierDraft.color === color }"
            :style="{ background: color }"
            :aria-label="`Farbe ${color}`"
            @click="dossierDraft.color = color"
          ></button>
        </div>
        <div class="dossier-properties-editor">
          <div class="dossier-properties-editor__head"><strong>Freie Eigenschaften</strong><v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="addPropertyDraft">Eigenschaft</v-btn></div>
          <div v-for="(property, index) in dossierDraft.properties" :key="property.localId" class="dossier-property-row">
            <v-text-field v-model="property.label" label="Bezeichnung" variant="outlined" density="compact" hide-details />
            <v-select v-model="property.value_type" :items="propertyTypeOptions" item-title="label" item-value="value" label="Typ" variant="outlined" density="compact" hide-details />
            <v-text-field v-if="property.value_type === 'date'" v-model="property.value" type="date" label="Wert" variant="outlined" density="compact" hide-details />
            <v-select v-else-if="property.value_type === 'boolean'" v-model="property.value" :items="booleanOptions" item-title="label" item-value="value" label="Wert" variant="outlined" density="compact" hide-details />
            <v-text-field v-else v-model="property.value" :type="property.value_type === 'number' ? 'number' : 'text'" label="Wert" variant="outlined" density="compact" hide-details />
            <v-btn icon="mdi-close" size="small" variant="text" aria-label="Eigenschaft entfernen" @click="dossierDraft.properties.splice(index, 1)" />
          </div>
          <div v-if="!dossierDraft.properties.length" class="dossier-properties-editor__empty">Zum Beispiel Kennzeichen, Vertragsnummer oder Adresse.</div>
        </div>
      </div>
    </BaseDialog>

    <BaseDialog
      v-model="noteDialogOpen"
      :title="editingItem ? 'Notiz bearbeiten' : 'Neue Notiz'"
      primary-text="Speichern"
      max-width="500"
      @primary="saveNote"
    >
      <div class="note-editor">
        <v-text-field
          v-model="noteDraft.title"
          label="Titel"
          variant="outlined"
          density="comfortable"
          hide-details
          autofocus
        />
        <v-textarea
          v-model="noteDraft.body"
          label="Notiz"
          variant="outlined"
          density="comfortable"
          rows="4"
          hide-details
          no-resize
        />
        <div class="note-editor__color-row">
          <span class="note-editor__color-label">Farbe</span>
          <div class="note-editor__palette" role="radiogroup" aria-label="Notizfarbe">
            <button
              v-for="option in noteColorOptions"
              :key="option.value"
              type="button"
              class="note-editor__swatch"
              :class="{ 'note-editor__swatch--active': noteDraft.color === option.value }"
              :style="{ '--note-swatch': option.value }"
              role="radio"
              :aria-checked="noteDraft.color === option.value"
              :aria-label="option.label"
              :title="option.label"
              @click="noteDraft.color = option.value"
            >
              <v-icon v-if="noteDraft.color === option.value" size="15">mdi-check</v-icon>
            </button>
          </div>
          <strong class="note-editor__color-name">{{ selectedNoteColorLabel }}</strong>
        </div>
      </div>
    </BaseDialog>

    <BaseDialog v-model="linkDialogOpen" :title="editingItem ? 'Link bearbeiten' : 'Link hinzufügen'" primary-text="Speichern" :primary-disabled="!linkDraft.url.trim()" @primary="saveLink">
      <v-text-field v-model="linkDraft.title" label="Titel" variant="outlined" density="comfortable" />
      <v-text-field v-model="linkDraft.url" label="https://…" variant="outlined" density="comfortable" />
      <v-textarea v-model="linkDraft.description" label="Beschreibung" variant="outlined" rows="2" />
    </BaseDialog>

    <BaseDialog
      v-model="connectionDialogOpen"
      title="Mit Dokument verbinden"
      description="Wähle das Dokument, zu dem dieser Zettel gehört. Die Verbindung bleibt beim Verschieben sichtbar."
      primary-text="Verbindung speichern"
      :loading="connectionSaving"
      max-width="620"
      scrollable
      @primary="saveConnection"
    >
      <div class="dossier-connection-picker" role="radiogroup" aria-label="Verbindungsziel">
        <button
          type="button"
          class="dossier-connection-choice dossier-connection-choice--none"
          :class="{ 'dossier-connection-choice--selected': connectionTargetId === null }"
          role="radio"
          :aria-checked="connectionTargetId === null"
          @click="connectionTargetId = null"
        >
          <span class="dossier-connection-choice__icon"><v-icon size="20">mdi-link-off</v-icon></span>
          <span><strong>Keine Verbindung</strong><small>Bestehende Verbindung lösen</small></span>
          <v-icon size="20">{{ connectionTargetId === null ? 'mdi-check-circle' : 'mdi-circle-outline' }}</v-icon>
        </button>
        <button
          v-for="documentItem in documentItems"
          :key="documentItem.id"
          type="button"
          class="dossier-connection-choice"
          :class="{ 'dossier-connection-choice--selected': connectionTargetId === documentItem.id }"
          role="radio"
          :aria-checked="connectionTargetId === documentItem.id"
          @click="connectionTargetId = documentItem.id"
        >
          <img :src="documentThumbnailUrl(documentItem.document_id)" alt="" loading="lazy" />
          <span><strong>{{ itemTitle(documentItem) }}</strong><small>{{ documentItem.document?.document_type || 'Dokument' }} · {{ dossierDocumentPageLabel(documentItem.document) || 'Seitenzahl unbekannt' }}</small></span>
          <v-icon size="20">{{ connectionTargetId === documentItem.id ? 'mdi-check-circle' : 'mdi-circle-outline' }}</v-icon>
        </button>
      </div>
    </BaseDialog>

    <BaseDialog v-model="pickerOpen" title="Dokumente hinzufügen" description="Wähle vorhandene Dokumente aus der PaperMind-Bibliothek." primary-text="Hinzufügen" :primary-disabled="!pickerSelection.size" :loading="pickerLoading" max-width="780" scrollable @primary="addPickedDocuments">
      <v-text-field v-model="pickerSearch" prepend-inner-icon="mdi-magnify" placeholder="Dokumente suchen" variant="outlined" density="comfortable" clearable @update:model-value="schedulePickerSearch" />
      <div class="dossier-picker-list">
        <button
          v-for="document in pickerDocuments"
          :key="document.id"
          type="button"
          class="dossier-picker-row"
          :class="{ 'dossier-picker-row--selected': pickerSelection.has(document.id), 'dossier-picker-row--disabled': assignedDocumentIds.has(document.id) }"
          :disabled="assignedDocumentIds.has(document.id)"
          @click="togglePickerDocument(document.id)"
        >
          <img :src="documentThumbnailUrl(document.id)" alt="" loading="lazy" />
          <span><strong>{{ documentTitle(document) }}</strong><small>{{ document.document_type || 'Dokument' }} · {{ formatDate(document.document_date) }}</small></span>
          <v-icon size="20">{{ assignedDocumentIds.has(document.id) ? 'mdi-check-circle-outline' : pickerSelection.has(document.id) ? 'mdi-check-circle' : 'mdi-checkbox-multiple-outline' }}</v-icon>
        </button>
        <div v-if="!pickerLoading && !pickerDocuments.length" class="dossier-picker-empty">Keine Dokumente gefunden.</div>
      </div>
    </BaseDialog>

    <BaseDialog v-model="deleteDialog.open" :title="deleteDialog.title" :description="deleteDialog.description" variant="destructive" :primary-text="deleteDialog.primaryText" @primary="confirmDelete" />

    <BaseDialog
      v-model="groupDialogOpen"
      title="Neue Gruppe"
      description="Die ausgewählten Karten werden dieser Gruppe zugeordnet."
      primary-text="Gruppe anlegen"
      :primary-disabled="!groupDraft.title.trim()"
      @primary="createGroupFromSelection"
    >
      <v-text-field v-model="groupDraft.title" label="Gruppenname" variant="outlined" density="comfortable" autofocus />
      <div class="dossier-form__color-row">
        <span>Farbe</span>
        <button
          v-for="color in dossierColors"
          :key="color"
          type="button"
          class="dossier-form__swatch"
          :class="{ 'dossier-form__swatch--active': groupDraft.color === color }"
          :style="{ background: color }"
          :aria-label="`Farbe ${color}`"
          @click="groupDraft.color = color"
        ></button>
      </div>
    </BaseDialog>

    <v-snackbar v-model="snackbar.open" :color="snackbar.color" timeout="3500">
      {{ snackbar.message }}
      <template v-if="canUndo && !snackbar.color" #actions>
        <v-btn variant="text" @click="undoBoardAction">Rückgängig</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, resolveComponent, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router';

import BaseDialog from '../components/BaseDialog.vue';
import PdfPreview from '../components/PdfPreview.vue';
import { apiFetch } from '../api/client.js';
import { documentFileUrl, documentThumbnailUrl, listDocuments } from '../api/documents.js';
import { useDossierStore } from '../stores/dossiers.js';
import { useUiStore } from '../stores/ui.js';
import { useCommandHistory } from '../composables/useCommandHistory.js';
import {
  DOSSIER_OVERVIEW_SORTS,
  dossierElementsSummary,
  filterAndSortDossiers,
} from '../utils/dossierOverview.js';
import { arrangeDossierRects } from '../utils/dossierArrange.js';
import { dossierDocumentCardTitle, dossierDocumentPageLabel } from '../utils/dossierCards.js';
import { resolveDossierConnectionPath } from '../utils/dossierConnections.js';
import { DEFAULT_DOSSIER_TITLE, shouldDiscardDossierDraft } from '../utils/dossierDraft.js';
import { consumeDossierSidebarEntryAnimation } from '../utils/dossierEntryAnimation.js';
import { isPdfDossierItem } from '../utils/dossierPreview.js';
import { resolveDossierSmartGuides } from '../utils/dossierSmartGuides.js';
import { alignDossierRects, dossierSelectionIds } from '../utils/dossierSelection.js';
import { resolveDossierFit } from '../utils/dossierViewport.js';

defineProps({
  embedded: { type: Boolean, default: false },
});

const route = useRoute();
const router = useRouter();
const dossierStore = useDossierStore();
const uiStore = useUiStore();
const { dossiers, currentDossier, groups, items, documentItems, loading, saving } = storeToRefs(dossierStore);

const dossierId = computed(() => String(route.params.dossierId || ''));
const sidebarSearch = ref('');
const overviewSearch = ref('');
const overviewState = ref('all');
const overviewSort = ref(readOverviewSort());
const overviewStaggerPending = ref(route.name === 'dossiers' && consumeDossierSidebarEntryAnimation());
const staggerOverviewTiles = ref(false);
const boardSearch = ref('');
const inspectorOpen = ref(false);
const inspectorMode = ref('dossier');
const inspectorTab = ref('stamm');
const previewItemId = ref(null);
const density = ref(readStoredDensity());
const selectedItemId = ref(null);
const selectedItemIds = ref(new Set());
const wrapEl = ref(null);
const canvasEl = ref(null);
const boardTitleInput = ref(null);
const drag = reactive({ active: false, ids: [], itemId: null, dx: 0, dy: 0, moved: false, guideX: null, guideY: null, reduceOnClick: false, beforePlacements: [] });
const selectionBox = reactive({ active: false, moved: false, x1: 0, y1: 0, x2: 0, y2: 0, initialIds: [] });
const pan = reactive({ active: false, spacePressed: false, startX: 0, startY: 0, startViewX: 0, startViewY: 0 });
const boardView = reactive({ x: 0, y: 0 });
const fittedScale = ref(null);
const viewFitting = ref(false);
const arrangingBoard = ref(false);
const settlingIds = reactive(new Set());
let dragStart = null;
let pendingDragPoint = null;
let dragFrame = 0;
let pendingPanPoint = null;
let panFrame = 0;
let fitTimer = null;
let overviewStaggerTimer = null;
const settlingTimers = new Map();
const uploadInput = ref(null);
const snackbar = reactive({ open: false, message: '', color: '' });

const dossierDialogOpen = ref(false);
const dossierDialogMode = ref('create');
const editingDossierId = ref(null);
const dossierDraft = reactive({ title: '', dossier_type: '', reference: '', description: '', state: 'active', opened_on: '', closed_on: '', color: '#3b8f83', properties: [] });
const noteDialogOpen = ref(false);
const linkDialogOpen = ref(false);
const editingItem = ref(null);
const connectionDialogOpen = ref(false);
const connectionItemId = ref(null);
const connectionTargetId = ref(null);
const connectionSaving = ref(false);
const noteDraft = reactive({ title: '', body: '', color: '#f4df8b' });
const linkDraft = reactive({ title: '', url: '', description: '' });
const groupDialogOpen = ref(false);
const groupDraft = reactive({ title: '', color: '#3b8f83' });
const pickerOpen = ref(false);
const pickerLoading = ref(false);
const pickerSearch = ref('');
const pickerDocuments = ref([]);
const pickerSelection = ref(new Set());
const deleteDialog = reactive({ open: false, type: '', target: null, title: '', description: '', primaryText: 'Löschen' });
let pickerSearchTimer = null;

const {
  busy: historyBusy,
  canUndo,
  canRedo,
  undoLabel,
  redoLabel,
  record: recordHistory,
  clear: clearHistory,
  undo: undoHistory,
  redo: redoHistory,
} = useCommandHistory({ limit: 60 });

const dossierColors = ['#3b8f83', '#3976a8', '#7963a7', '#ae6a43', '#9b4d64', '#65736f'];
const noteColorOptions = [
  { label: 'Sonnengelb', value: '#f4df8b' },
  { label: 'Salbeigrün', value: '#d8e7a5' },
  { label: 'Himmelblau', value: '#b9dded' },
  { label: 'Lavendel', value: '#d8c5ed' },
  { label: 'Koralle', value: '#efc4b8' },
];
const selectedNoteColorLabel = computed(
  () => noteColorOptions.find((option) => option.value === noteDraft.color)?.label || 'Eigene Farbe',
);
const overviewStateOptions = [{ label: 'Alle', value: 'all' }, { label: 'Archiv', value: 'archived' }];
const overviewSortOptions = DOSSIER_OVERVIEW_SORTS;
const propertyTypeOptions = [{ label: 'Text', value: 'text' }, { label: 'Datum', value: 'date' }, { label: 'Zahl', value: 'number' }, { label: 'Ja/Nein', value: 'boolean' }];
const booleanOptions = [{ label: 'Ja', value: true }, { label: 'Nein', value: false }];

const DENSITY_SCALE = { kompakt: 0.78, normal: 1, gross: 1.2 };
const densityOptions = [{ label: 'Kompakt', value: 'kompakt' }, { label: 'Normal', value: 'normal' }, { label: 'Groß', value: 'gross' }];
function readStoredDensity() {
  const stored = localStorage.getItem('pm.dossier.density');
  return stored === 'kompakt' || stored === 'normal' || stored === 'gross' ? stored : 'gross';
}
function readOverviewSort() {
  const stored = localStorage.getItem('pm.dossier.overviewSort');
  return DOSSIER_OVERVIEW_SORTS.some((option) => option.value === stored) ? stored : 'updated_desc';
}
const densityScale = computed(() => DENSITY_SCALE[density.value] || 1);
const boardScale = computed(() => fittedScale.value ?? densityScale.value);
const densityLabel = computed(() => densityOptions.find((option) => option.value === density.value)?.label || 'Groß');
const inspectorTabs = [
  { label: 'Stammdaten', value: 'stamm' },
  { label: 'Eigenschaften', value: 'eigen' },
  { label: 'Verlauf', value: 'verlauf' },
];

const knownDossierTypes = computed(() => [...new Set(dossiers.value.map((entry) => entry.dossier_type).filter(Boolean))].sort());
const filteredSidebarDossiers = computed(() => {
  const query = sidebarSearch.value.trim().toLocaleLowerCase('de-DE');
  return dossiers.value.filter((entry) => !query || `${entry.title} ${entry.reference || ''}`.toLocaleLowerCase('de-DE').includes(query));
});
const overviewScopeDossiers = computed(() => filterAndSortDossiers(dossiers.value, {
  state: overviewState.value,
  sort: overviewSort.value,
}));
const filteredOverviewDossiers = computed(() => filterAndSortDossiers(dossiers.value, {
  state: overviewState.value,
  query: overviewSearch.value,
  sort: overviewSort.value,
}));
const overviewSortLabel = computed(() => (
  overviewSortOptions.find((option) => option.value === overviewSort.value)?.label || 'Zuletzt geändert'
));
const overviewMeta = computed(() => {
  const total = overviewScopeDossiers.value.length;
  const elements = overviewScopeDossiers.value.reduce((sum, entry) => sum + Number(entry.item_count || 0), 0);
  return `${total} ${total === 1 ? 'Leuchttisch' : 'Leuchttische'} · ${elements} ${elements === 1 ? 'Element' : 'Elemente'}`;
});
const isTrueOverviewEmpty = computed(() => (
  overviewState.value === 'all'
  && !overviewSearch.value.trim()
  && !dossiers.value.some((entry) => !entry.archived_at)
));
const overviewEmptyTitle = computed(() => {
  if (overviewSearch.value.trim()) return 'Keine passenden Leuchttische';
  if (overviewState.value === 'archived') return 'Das Archiv ist leer';
  return 'Kein Leuchttisch angelegt';
});
const overviewEmptyDescription = computed(() => {
  if (overviewSearch.value.trim()) return 'Passe den Suchbegriff an oder leere die Suche.';
  if (overviewState.value === 'archived') return 'Archivierte Leuchttische erscheinen hier und können jederzeit wiederhergestellt werden.';
  return 'Ein Leuchttisch sammelt Dokumente, Notizen und Links zu einem Vorgang und lässt sie frei anordnen.';
});
function elementsSummary(entry) { return dossierElementsSummary(entry); }
function previewSlots(entry) {
  const ids = Array.isArray(entry.preview_document_ids) ? entry.preview_document_ids.slice(0, 3) : [];
  return Array.from({ length: 3 }, (_, index) => ids[index] || null);
}
// Miniatur-Platzhalter: Shimmer läuft, bis das Thumbnail geladen ist (oder scheitert).
// Reaktiv nach document_id verfolgt, damit der Zustand Re-Renders übersteht.
const loadedThumbs = reactive(new Set());
const erroredThumbs = reactive(new Set());
function markThumbLoaded(documentId) { if (documentId) loadedThumbs.add(documentId); }
function markThumbErrored(documentId) { if (documentId) erroredThumbs.add(documentId); }
function overviewDescription(entry) {
  if (entry.description) return entry.description;
  return [entry.dossier_type, entry.reference].filter(Boolean).join(' · ') || '\u00a0';
}
const assignedDocumentIds = computed(() => new Set(documentItems.value.map((item) => item.document_id)));
const selectedItems = computed(() => items.value.filter((item) => selectedItemIds.value.has(item.id)));
const groupMap = computed(() => new Map(groups.value.map((group) => [group.id, group])));
function groupTitle(groupId) { return groupId ? groupMap.value.get(groupId)?.title || '' : ''; }

// ── Freie Leuchttisch-Fläche: Kartenmaße, Raster, Positionsmodell ──────────
const CARD = { document: { w: 184, h: 292 }, note: { w: 184, h: 124 }, link: { w: 184, h: 96 } };
const GRID = 26;
const SMART_GUIDE_THRESHOLD = 7;
const sizeOf = (item) => CARD[item.item_type] || CARD.document;
const snap = (value) => Math.round(value / GRID) * GRID;

function itemTitle(item) {
  if (item.item_type === 'document') return item.document?.title || 'Dokument';
  if (item.item_type === 'note') return item.note_title || 'Notiz';
  return item.link_title || item.link_url || 'Link';
}
function hostOf(url) {
  try { return new URL(url).host.replace(/^www\./i, ''); }
  catch { return String(url || '').replace(/^https?:\/\/(?:www\.)?/i, '').replace(/\/.*$/, ''); }
}

const DossierItemCard = defineComponent({
  name: 'DossierItemCard',
  props: { item: Object, selected: Boolean, dimmed: Boolean, thumbnailUrl: Function, groupTitle: String },
  setup(props) {
    const VIcon = resolveComponent('VIcon');
    // Reaktiver Ladezustand: als Teil des Renders überlebt er Re-Renders (anders als
    // eine imperativ gesetzte Klasse, die beim nächsten Render verloren ginge).
    const thumbLoaded = ref(false);
    const thumbError = ref(false);
    watch(() => props.item?.document_id, () => { thumbLoaded.value = false; thumbError.value = false; });
    return () => {
      const it = props.item;
      const cls = ['dsr-card', `dsr-card--${it.item_type}`, { 'dsr-card--selected': props.selected, 'dsr-card--dim': props.dimmed }];
      if (it.item_type === 'document') {
        const title = dossierDocumentCardTitle(it.document);
        const source = it.document?.correspondent_name || it.document?.document_type || 'Dokument';
        const pageLabel = dossierDocumentPageLabel(it.document);
        return h('div', { class: cls }, [
          h('div', { class: ['dsr-card__thumb', 'dsr-thumb', { 'dsr-thumb--loaded': thumbLoaded.value, 'dsr-thumb--error': thumbError.value }] }, [
            h('img', {
              src: props.thumbnailUrl(it.document_id),
              alt: '',
              // Kein loading="lazy": auf der transformierten/gescrollten Board-Fläche
              // triggert der Lazy-Loader nicht zuverlässig – die Miniaturen blieben leer.
              draggable: 'false',
              onLoad: () => { thumbLoaded.value = true; },
              onError: () => { thumbError.value = true; },
            }),
            h('span', { class: 'dsr-card__format', 'aria-hidden': 'true' }, 'PDF'),
            props.groupTitle ? h('span', { class: 'dsr-card__group', title: props.groupTitle }, props.groupTitle) : null,
          ]),
          h('div', { class: 'dsr-card__content' }, [
            h('div', { class: 'dsr-card__title', title: title.full }, title.display),
            h('div', { class: 'dsr-card__meta' }, [
              h('span', { class: 'dsr-card__source', title: source }, source),
              pageLabel ? h('span', { class: 'dsr-card__pages' }, pageLabel) : null,
            ]),
          ]),
        ]);
      }
      const isNote = it.item_type === 'note';
      const linkHost = hostOf(it.link_url);
      const title = isNote ? (it.note_title || 'Notiz') : (it.link_title || linkHost || 'Link');
      const style = { '--slip-accent': isNote && it.note_color ? it.note_color : '#5c9fc9' };
      return h('div', { class: cls, style }, [
        h('div', { class: 'dsr-card__slip-head' }, [
          h('div', { class: 'dsr-card__kind' }, [
            h('span', { class: 'dsr-card__kind-icon', 'aria-hidden': 'true' }, [h(VIcon, { size: 13, icon: isNote ? 'mdi-note-outline' : 'mdi-link-variant' })]),
            h('span', null, isNote ? 'Notiz' : 'Link'),
          ]),
          !isNote ? h(VIcon, { class: 'dsr-card__external', size: 14, icon: 'mdi-open-in-new', 'aria-hidden': 'true' }) : null,
        ]),
        props.groupTitle ? h('div', { class: 'dsr-card__group dsr-card__group--slip', title: props.groupTitle }, props.groupTitle) : null,
        h('div', { class: 'dsr-card__title dsr-card__title--slip', title }, title),
        isNote
          ? h('div', { class: 'dsr-card__body' }, it.note_body || '')
          : h('div', { class: 'dsr-card__addr', title: linkHost }, linkHost),
      ]);
    };
  },
});

const itemMap = computed(() => new Map(items.value.map((item) => [item.id, item])));
function itemById(id) { return itemMap.value.get(id) || null; }
const selectedItem = computed(() => itemById(selectedItemId.value));
const selectedPdfItem = computed(() => (isPdfDossierItem(selectedItem.value) ? selectedItem.value : null));
const selectedAttachableItem = computed(() => (
  selectedItem.value && ['note', 'link'].includes(selectedItem.value.item_type) ? selectedItem.value : null
));
const connectionItem = computed(() => itemById(connectionItemId.value));
const previewItem = computed(() => {
  const item = itemById(previewItemId.value);
  return isPdfDossierItem(item) ? item : null;
});
// Vorschau-Schublade: Seiten-Skeleton läuft, bis PdfPreview die erste Seite gerendert hat.
// An den Render-Key (previewItem.id) koppeln, damit das Skeleton bei jedem
// (Neu-)Mount der Vorschau erneut anläuft.
const previewReady = ref(false);
watch(() => previewItem.value?.id, () => { previewReady.value = false; });

// Tidy default layout for items that have no stored position yet.
const autoLayout = computed(() => {
  const map = new Map();
  const COL_GAP = 16;
  const ROW_GAP = 16;
  const START_X = 32;
  const START_Y = 28;
  const maxRowW = 5 * (CARD.document.w + COL_GAP);
  let cx = START_X;
  let cy = START_Y;
  let rowH = 0;
  const orderedItems = [...items.value].sort((a, b) => a.sort_order - b.sort_order);
  for (const item of orderedItems) {
    const size = sizeOf(item);
    if (cx > START_X && cx + size.w > START_X + maxRowW) {
      cx = START_X;
      cy += rowH + ROW_GAP;
      rowH = 0;
    }
    map.set(item.id, { x: cx, y: cy });
    cx += size.w + COL_GAP;
    rowH = Math.max(rowH, size.h);
  }
  return map;
});
function basePos(item) {
  if (item.pos_x != null && item.pos_y != null) return { x: item.pos_x, y: item.pos_y };
  return autoLayout.value.get(item.id) || { x: 32, y: 28 };
}
function renderPos(item) {
  const pos = basePos(item);
  if (drag.active && drag.ids.includes(item.id)) return { x: pos.x + drag.dx, y: pos.y + drag.dy };
  return pos;
}
const canvasSize = computed(() => {
  let maxX = 1200;
  let maxY = 720;
  for (const item of items.value) { const pos = basePos(item); const size = sizeOf(item); maxX = Math.max(maxX, pos.x + size.w); maxY = Math.max(maxY, pos.y + size.h); }
  return { w: Math.ceil(maxX) + 180, h: Math.ceil(maxY) + 180 };
});
const dossierConnections = computed(() => items.value.flatMap((source) => {
  if (!source.attached_to_item_id || !['note', 'link'].includes(source.item_type)) return [];
  const target = itemById(source.attached_to_item_id);
  if (!target || target.item_type !== 'document') return [];
  const sourcePosition = renderPos(source);
  const targetPosition = renderPos(target);
  const sourceSize = sizeOf(source);
  const targetSize = sizeOf(target);
  return [{
    id: `${target.id}-${source.id}`,
    sourceId: source.id,
    targetId: target.id,
    path: resolveDossierConnectionPath(
      { x: targetPosition.x, y: targetPosition.y, w: targetSize.w, h: targetSize.h },
      { x: sourcePosition.x, y: sourcePosition.y, w: sourceSize.w, h: sourceSize.h },
    ),
  }];
}));
const boardViewportStyle = computed(() => ({
  '--dsr-grid-size': `${GRID * boardScale.value}px`,
  '--dsr-grid-x': `${boardView.x + (GRID * boardScale.value) / 2}px`,
  '--dsr-grid-y': `${boardView.y + (GRID * boardScale.value) / 2}px`,
}));
const selectionBoxStyle = computed(() => {
  const left = Math.min(selectionBox.x1, selectionBox.x2);
  const top = Math.min(selectionBox.y1, selectionBox.y2);
  return {
    width: `${Math.abs(selectionBox.x2 - selectionBox.x1)}px`,
    height: `${Math.abs(selectionBox.y2 - selectionBox.y1)}px`,
    transform: `translate3d(${left}px, ${top}px, 0)`,
  };
});

function isDimmed(item) {
  const query = boardSearch.value.trim().toLocaleLowerCase('de-DE');
  return !!query && !itemTitle(item).toLocaleLowerCase('de-DE').includes(query);
}

function itemPlacement(item, position = basePos(item)) {
  return {
    item_id: item.id,
    group_id: item.group_id ?? null,
    sort_order: Number(item.sort_order || 0),
    pos_x: Math.round(position.x),
    pos_y: Math.round(position.y),
  };
}

function placementsFor(targetItems) {
  return targetItems.map((item) => itemPlacement(item));
}

function recordPlacementHistory(label, before, after) {
  const boardId = dossierId.value;
  recordHistory({
    label,
    undo: () => dossierStore.setItemPlacements(boardId, before),
    redo: () => dossierStore.setItemPlacements(boardId, after),
  });
}

function replaceSelection(ids, activeId = null) {
  selectedItemIds.value = new Set(ids);
  selectedItemId.value = activeId && selectedItemIds.value.has(activeId)
    ? activeId
    : [...selectedItemIds.value][0] || null;
}

function toggleSelection(itemId) {
  const next = new Set(selectedItemIds.value);
  if (next.has(itemId)) next.delete(itemId);
  else next.add(itemId);
  replaceSelection(next, next.has(itemId) ? itemId : [...next][0] || null);
}

// ── Zeiger-basiertes Ziehen mit Raster-Einrasten ─────────────────────────
function beginDrag(item, event) {
  if ((event.button !== undefined && event.button !== 0) || historyBusy.value) return;
  const additive = Boolean(event.metaKey || event.ctrlKey || event.shiftKey);
  const wasSelected = selectedItemIds.value.has(item.id);
  const previousCount = selectedItemIds.value.size;
  if (additive) toggleSelection(item.id);
  else if (!wasSelected) replaceSelection([item.id], item.id);
  if (!selectedItemIds.value.has(item.id)) return;

  dragStart = { clientX: event.clientX, clientY: event.clientY };
  pendingDragPoint = null;
  const ids = [...selectedItemIds.value];
  Object.assign(drag, {
    active: true,
    dx: 0,
    dy: 0,
    moved: false,
    ids,
    itemId: item.id,
    guideX: null,
    guideY: null,
    reduceOnClick: !additive && wasSelected && previousCount > 1,
    beforePlacements: placementsFor(ids.map(itemById).filter(Boolean)),
  });
  window.addEventListener('pointermove', onDragMove);
  window.addEventListener('pointerup', onDragUp, { once: true });
  window.addEventListener('pointercancel', onDragCancel, { once: true });
}
function startItemDrag(item, event) { event.stopPropagation(); beginDrag(item, event); }
function applyDragPoint(point) {
  if (!dragStart || !point) return;
  const scale = boardScale.value || 1;
  const rawDx = (point.clientX - dragStart.clientX) / scale;
  const rawDy = (point.clientY - dragStart.clientY) / scale;
  if (!drag.moved && (Math.abs(rawDx) > 4 || Math.abs(rawDy) > 4)) drag.moved = true;

  drag.guideX = null;
  drag.guideY = null;
  if (!drag.moved) {
    drag.dx = rawDx;
    drag.dy = rawDy;
    return;
  }

  const item = itemById(drag.itemId);
  if (!item) return;
  const position = basePos(item);
  const size = sizeOf(item);
  const guides = resolveDossierSmartGuides(
    { x: position.x + rawDx, y: position.y + rawDy, w: size.w, h: size.h },
    items.value
      .filter((other) => !drag.ids.includes(other.id))
      .map((other) => {
        const otherPosition = basePos(other);
        const otherSize = sizeOf(other);
        return { x: otherPosition.x, y: otherPosition.y, w: otherSize.w, h: otherSize.h };
      }),
    SMART_GUIDE_THRESHOLD,
  );
  drag.guideX = guides.x;
  drag.guideY = guides.y;
  drag.dx = rawDx + (guides.x?.delta || 0);
  drag.dy = rawDy + (guides.y?.delta || 0);
}
function flushDragFrame(point = pendingDragPoint) {
  if (dragFrame) cancelAnimationFrame(dragFrame);
  dragFrame = 0;
  pendingDragPoint = null;
  applyDragPoint(point);
}
function onDragMove(event) {
  event.preventDefault();
  pendingDragPoint = { clientX: event.clientX, clientY: event.clientY };
  if (dragFrame) return;
  dragFrame = requestAnimationFrame(() => flushDragFrame());
}
async function onDragUp(event) {
  window.removeEventListener('pointermove', onDragMove);
  window.removeEventListener('pointercancel', onDragCancel);
  flushDragFrame(event && typeof event.clientX === 'number'
    ? { clientX: event.clientX, clientY: event.clientY }
    : pendingDragPoint);
  const { moved, itemId } = drag;
  try {
    if (!moved) {
      const item = itemById(itemId);
      if (item && drag.reduceOnClick) replaceSelection([item.id], item.id);
    } else {
      // Paint the exact release point once before switching to the snapped
      // destination, so the short settle transition always has a clean origin.
      await nextTick();
      markSettling(drag.ids);
      const save = commitItemDrop();
      // setItemPlacements updates optimistically. Clear the live pointer offset
      // immediately so it cannot be added to the stored position a second time.
      resetDrag();
      await save;
    }
  } catch (error) {
    showMessage(error.message || 'Verschieben fehlgeschlagen.', 'error');
  } finally {
    if (drag.active) resetDrag();
  }
}
function onDragCancel() {
  window.removeEventListener('pointermove', onDragMove);
  window.removeEventListener('pointerup', onDragUp);
  resetDrag();
}
function markSettling(ids) {
  for (const id of ids) {
    settlingIds.add(id);
    if (settlingTimers.has(id)) clearTimeout(settlingTimers.get(id));
    settlingTimers.set(id, setTimeout(() => {
      settlingIds.delete(id);
      settlingTimers.delete(id);
    }, 220));
  }
}
function resetDrag() {
  if (dragFrame) cancelAnimationFrame(dragFrame);
  dragFrame = 0;
  pendingDragPoint = null;
  Object.assign(drag, { active: false, ids: [], itemId: null, dx: 0, dy: 0, moved: false, guideX: null, guideY: null, reduceOnClick: false, beforePlacements: [] });
  dragStart = null;
}
async function commitItemDrop() {
  const item = itemById(drag.itemId);
  if (!item) return;
  const before = drag.beforePlacements.map((placement) => ({ ...placement }));
  const after = drag.ids.map(itemById).filter(Boolean).map((movedItem) => {
    const pos = basePos(movedItem);
    const useGuides = movedItem.id === item.id;
    const nx = useGuides && drag.guideX ? Math.round(pos.x + drag.dx) : snap(pos.x + drag.dx);
    const ny = useGuides && drag.guideY ? Math.round(pos.y + drag.dy) : snap(pos.y + drag.dy);
    return itemPlacement(movedItem, { x: nx, y: ny });
  });
  await dossierStore.setItemPlacements(dossierId.value, after);
  recordPlacementHistory(after.length > 1 ? `${after.length} Elemente verschieben` : 'Element verschieben', before, after);
}
function stopViewTransition() {
  if (fitTimer) clearTimeout(fitTimer);
  fitTimer = null;
  viewFitting.value = false;
}
function applyPanPoint(point = pendingPanPoint) {
  if (!pan.active || !point) return;
  boardView.x = pan.startViewX + point.clientX - pan.startX;
  boardView.y = pan.startViewY + point.clientY - pan.startY;
}
function flushPanFrame(point = pendingPanPoint) {
  if (panFrame) cancelAnimationFrame(panFrame);
  panFrame = 0;
  pendingPanPoint = null;
  applyPanPoint(point);
}
function onPanMove(event) {
  event.preventDefault();
  pendingPanPoint = { clientX: event.clientX, clientY: event.clientY };
  if (panFrame) return;
  panFrame = requestAnimationFrame(() => flushPanFrame());
}
function finishPan(event) {
  window.removeEventListener('pointermove', onPanMove);
  window.removeEventListener('pointerup', finishPan);
  window.removeEventListener('pointercancel', cancelPan);
  flushPanFrame(event && typeof event.clientX === 'number'
    ? { clientX: event.clientX, clientY: event.clientY }
    : pendingPanPoint);
  pan.active = false;
}
function cancelPan() {
  window.removeEventListener('pointermove', onPanMove);
  window.removeEventListener('pointerup', finishPan);
  window.removeEventListener('pointercancel', cancelPan);
  if (panFrame) cancelAnimationFrame(panFrame);
  panFrame = 0;
  pendingPanPoint = null;
  pan.active = false;
}
function boardPoint(event) {
  const rect = wrapEl.value?.getBoundingClientRect();
  const scale = boardScale.value || 1;
  if (!rect) return { x: 0, y: 0 };
  return {
    x: (event.clientX - rect.left - boardView.x) / scale,
    y: (event.clientY - rect.top - boardView.y) / scale,
  };
}
function selectionCards() {
  return items.value.map((item) => {
    const position = basePos(item);
    const size = sizeOf(item);
    return { id: item.id, x: position.x, y: position.y, w: size.w, h: size.h };
  });
}
function applySelectionPoint(event) {
  if (!selectionBox.active) return;
  const point = boardPoint(event);
  selectionBox.x2 = point.x;
  selectionBox.y2 = point.y;
  if (!selectionBox.moved && Math.hypot(selectionBox.x2 - selectionBox.x1, selectionBox.y2 - selectionBox.y1) > 4) {
    selectionBox.moved = true;
  }
  if (!selectionBox.moved) return;
  const hits = dossierSelectionIds(selectionBox, selectionCards());
  replaceSelection(new Set([...selectionBox.initialIds, ...hits]), hits.at(-1) || selectionBox.initialIds.at(-1) || null);
}
function finishSelection(event) {
  window.removeEventListener('pointermove', applySelectionPoint);
  window.removeEventListener('pointerup', finishSelection);
  window.removeEventListener('pointercancel', cancelSelection);
  applySelectionPoint(event);
  selectionBox.active = false;
}
function cancelSelection() {
  window.removeEventListener('pointermove', applySelectionPoint);
  window.removeEventListener('pointerup', finishSelection);
  window.removeEventListener('pointercancel', cancelSelection);
  selectionBox.active = false;
  selectionBox.moved = false;
}
function beginSelection(event) {
  const additive = Boolean(event.metaKey || event.ctrlKey || event.shiftKey);
  const point = boardPoint(event);
  Object.assign(selectionBox, {
    active: true,
    moved: false,
    x1: point.x,
    y1: point.y,
    x2: point.x,
    y2: point.y,
    initialIds: additive ? [...selectedItemIds.value] : [],
  });
  if (!additive) clearSelection();
  window.addEventListener('pointermove', applySelectionPoint);
  window.addEventListener('pointerup', finishSelection);
  window.addEventListener('pointercancel', cancelSelection);
}
function onBoardPointerDown(event) {
  const wantsPan = event.button === 1 || (event.button === 0 && pan.spacePressed);
  const interactiveTarget = event.target instanceof Element
    && event.target.closest('.dsr-node, button, input, textarea, select, [contenteditable="true"]');
  if (!wantsPan) {
    if (event.button === 0 && !interactiveTarget && !historyBusy.value) {
      event.preventDefault();
      event.stopPropagation();
      beginSelection(event);
    }
    return;
  }
  if (interactiveTarget && !event.target.closest('.dsr-node')) return;
  event.preventDefault();
  event.stopPropagation();
  stopViewTransition();
  Object.assign(pan, {
    active: true,
    startX: event.clientX,
    startY: event.clientY,
    startViewX: boardView.x,
    startViewY: boardView.y,
  });
  window.addEventListener('pointermove', onPanMove);
  window.addEventListener('pointerup', finishPan);
  window.addEventListener('pointercancel', cancelPan);
}
function onBoardWheel(event) {
  if (event.ctrlKey) return;
  event.preventDefault();
  stopViewTransition();
  const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? wrapEl.value?.clientHeight || 1 : 1;
  boardView.x -= event.deltaX * unit;
  boardView.y -= event.deltaY * unit;
}
function isBoardKeyboardTarget(target) {
  return target instanceof Element && !!target.closest('input, textarea, select, button, [contenteditable="true"], .dsr-inspector, .v-overlay');
}
function boardInteractionBlocked() {
  return dossierDialogOpen.value || noteDialogOpen.value || linkDialogOpen.value || connectionDialogOpen.value || groupDialogOpen.value || pickerOpen.value || deleteDialog.open || historyBusy.value;
}
function onBoardKeyDown(event) {
  if (!dossierId.value || boardInteractionBlocked() || isBoardKeyboardTarget(event.target)) return;
  const commandKey = event.metaKey || event.ctrlKey;
  const key = String(event.key || '').toLowerCase();
  if (commandKey && key === 'z') {
    event.preventDefault();
    if (event.shiftKey) void redoBoardAction();
    else void undoBoardAction();
    return;
  }
  if (commandKey && key === 'y') {
    event.preventDefault();
    void redoBoardAction();
    return;
  }
  if (commandKey && key === 'a') {
    event.preventDefault();
    replaceSelection(items.value.map((item) => item.id), items.value.at(-1)?.id || null);
    return;
  }
  if ((event.key === 'Delete' || event.key === 'Backspace') && selectedItems.value.length) {
    event.preventDefault();
    askRemoveSelectedItem();
    return;
  }
  if (event.key === 'Escape' && selectedItems.value.length) {
    event.preventDefault();
    clearSelection();
    return;
  }
  if (event.code === 'Space') {
    event.preventDefault();
    pan.spacePressed = true;
  }
}
function onBoardKeyUp(event) {
  if (event.code === 'Space') pan.spacePressed = false;
}
function onWindowBlur() {
  pan.spacePressed = false;
  cancelPan();
  cancelSelection();
}
function resetBoardView() {
  stopViewTransition();
  cancelPan();
  pan.spacePressed = false;
  fittedScale.value = null;
  boardView.x = 0;
  boardView.y = 0;
}
function boardInspectorWidth() {
  return wrapEl.value?.parentElement?.querySelector('.dsr-inspector-shell')?.offsetWidth || 0;
}
async function arrangeBoard() {
  const wrap = wrapEl.value;
  if (!wrap || items.value.length < 2 || arrangingBoard.value) return;
  const usableLogicalWidth = Math.max(
    CARD.document.w,
    (wrap.clientWidth - boardInspectorWidth() - 64) / densityScale.value,
  );
  const columns = Math.max(1, Math.min(5, Math.floor((usableLogicalWidth + 20) / 208)));
  const before = placementsFor(items.value);
  const arranged = arrangeDossierRects(items.value.map((item) => {
    const position = basePos(item);
    const size = sizeOf(item);
    return {
      id: item.id,
      x: position.x,
      y: position.y,
      w: size.w,
      h: size.h,
      sortOrder: item.sort_order || 0,
    };
  }), { columns, grid: GRID, startX: GRID, startY: GRID, gap: 20 });
  const arrangedById = new Map(arranged.map((placement) => [placement.id, placement]));
  const placements = items.value.map((item) => {
    const placement = arrangedById.get(item.id);
    return {
      item_id: item.id,
      group_id: item.group_id ?? null,
      sort_order: item.sort_order || 0,
      pos_x: placement.x,
      pos_y: placement.y,
    };
  });

  arrangingBoard.value = true;
  try {
    markSettling(items.value.map((item) => item.id));
    await nextTick();
    await dossierStore.setItemPlacements(dossierId.value, placements);
    recordPlacementHistory('Leuchttisch sauber anordnen', before, placements);
    await nextTick();
    await fitBoardToViewport();
    showMessage('Leuchttisch sauber angeordnet.');
  } catch (error) {
    showMessage(error.message || 'Der Leuchttisch konnte nicht angeordnet werden.', 'error');
  } finally {
    arrangingBoard.value = false;
  }
}
async function fitBoardToViewport({ animate = true } = {}) {
  const wrap = wrapEl.value;
  if (!wrap || !items.value.length) return;
  const inspectorWidth = boardInspectorWidth();
  const rects = items.value.map((item) => {
    const position = basePos(item);
    const size = sizeOf(item);
    return { x: position.x, y: position.y, w: size.w, h: size.h };
  });
  const fit = resolveDossierFit(
    rects,
    { width: Math.max(1, wrap.clientWidth - inspectorWidth), height: wrap.clientHeight },
    { maxScale: densityScale.value, minScale: 0.32, padding: 48 },
  );
  if (!fit) return;

  stopViewTransition();
  if (animate) {
    viewFitting.value = true;
    await nextTick();
  }
  fittedScale.value = fit.scale;
  boardView.x = fit.x;
  boardView.y = fit.y;
  if (animate) fitTimer = setTimeout(stopViewTransition, 300);
}
function onCanvasBackgroundDown(event) { if (event.target === canvasEl.value && !selectionBox.active) clearSelection(); }
function nodeStyle(item) {
  const pos = renderPos(item);
  const active = drag.active && drag.ids.includes(item.id);
  return { transform: `translate3d(${pos.x}px, ${pos.y}px, 0)`, zIndex: active ? 40 : (selectedItemIds.value.has(item.id) ? 20 : 10) };
}
function smartGuideStyle(guide, axis) {
  if (!guide) return {};
  const scale = boardScale.value || 1;
  if (axis === 'x') {
    return {
      height: `${Math.max(0, guide.to - guide.from)}px`,
      transform: `translate3d(${guide.coordinate}px, ${guide.from}px, 0)`,
      width: `${1 / scale}px`,
    };
  }
  return {
    height: `${1 / scale}px`,
    transform: `translate3d(${guide.from}px, ${guide.coordinate}px, 0)`,
    width: `${Math.max(0, guide.to - guide.from)}px`,
  };
}
function nodeClass(item) {
  return {
    'dsr-node--dragging': drag.active && drag.moved && drag.ids.includes(item.id),
    'dsr-node--settling': settlingIds.has(item.id),
  };
}
async function undoBoardAction() {
  try {
    const command = await undoHistory();
    if (command) showMessage(`Rückgängig: ${command.label}`);
  } catch (error) {
    showMessage(error.message || 'Rückgängig konnte nicht ausgeführt werden.', 'error');
  }
}
async function redoBoardAction() {
  try {
    const command = await redoHistory();
    if (command) showMessage(`Wiederholt: ${command.label}`);
  } catch (error) {
    showMessage(error.message || 'Wiederholen konnte nicht ausgeführt werden.', 'error');
  }
}
async function alignSelection(mode, label) {
  if (selectedItems.value.length < 2 || historyBusy.value) return;
  const before = placementsFor(selectedItems.value);
  const aligned = alignDossierRects(selectedItems.value.map((item) => {
    const position = basePos(item);
    const size = sizeOf(item);
    return { id: item.id, x: position.x, y: position.y, w: size.w, h: size.h };
  }), mode);
  const alignedById = new Map(aligned.map((placement) => [placement.id, placement]));
  const after = selectedItems.value.map((item) => itemPlacement(item, alignedById.get(item.id)));
  try {
    markSettling(selectedItems.value.map((item) => item.id));
    await dossierStore.setItemPlacements(dossierId.value, after);
    recordPlacementHistory(label, before, after);
  } catch (error) {
    showMessage(error.message || 'Ausrichten fehlgeschlagen.', 'error');
  }
}
async function assignSelectionToGroup(groupId, label = 'Gruppierung ändern') {
  if (!selectedItems.value.length || historyBusy.value) return;
  const before = placementsFor(selectedItems.value);
  const after = before.map((placement) => ({ ...placement, group_id: groupId }));
  if (before.every((placement) => placement.group_id === groupId)) return;
  try {
    await dossierStore.setItemPlacements(dossierId.value, after);
    recordPlacementHistory(groupId ? `Gruppe „${label}“ zuweisen` : label, before, after);
    showMessage(groupId ? `Auswahl der Gruppe „${label}“ zugeordnet.` : 'Gruppierung gelöst.');
  } catch (error) {
    showMessage(error.message || 'Gruppieren fehlgeschlagen.', 'error');
  }
}
function openGroupDialog() {
  if (!selectedItems.value.length) return;
  Object.assign(groupDraft, { title: '', color: dossierColors[groups.value.length % dossierColors.length] });
  groupDialogOpen.value = true;
}
async function createGroupFromSelection() {
  const title = groupDraft.title.trim();
  const color = groupDraft.color;
  const targets = [...selectedItems.value];
  if (!title || !targets.length || historyBusy.value) return;
  const boardId = dossierId.value;
  const before = placementsFor(targets);
  let currentGroupId = null;
  const assignToCurrentGroup = async () => {
    const after = before.map((placement) => ({ ...placement, group_id: currentGroupId }));
    await dossierStore.setItemPlacements(boardId, after);
  };
  try {
    const created = await dossierStore.addGroup(boardId, { title, color });
    currentGroupId = created.id;
    try {
      await assignToCurrentGroup();
    } catch (error) {
      await dossierStore.removeGroup(boardId, currentGroupId);
      throw error;
    }
    groupDialogOpen.value = false;
    recordHistory({
      label: `Gruppe „${title}“ anlegen`,
      undo: async () => {
        await dossierStore.setItemPlacements(boardId, before);
        await dossierStore.removeGroup(boardId, currentGroupId);
      },
      redo: async () => {
        const recreated = await dossierStore.addGroup(boardId, { title, color });
        currentGroupId = recreated.id;
        try {
          await assignToCurrentGroup();
        } catch (error) {
          await dossierStore.removeGroup(boardId, currentGroupId);
          throw error;
        }
      },
    });
    showMessage(`Gruppe „${title}“ angelegt.`);
  } catch (error) {
    showMessage(error.message || 'Gruppe konnte nicht angelegt werden.', 'error');
  }
}
function showMessage(message, color = '') { snackbar.message = message; snackbar.color = color; snackbar.open = true; }
function goToDossiers() { router.push({ name: 'dossiers' }); }
function openDossier(id, { draft = false } = {}) {
  router.push({
    name: 'dossier-board',
    params: { dossierId: id },
    query: draft ? { draft: '1' } : {},
  });
}
function formatDate(value) { if (!value) return 'Ohne Datum'; const date = new Date(`${String(value).slice(0, 10)}T12:00:00`); return new Intl.DateTimeFormat('de-DE').format(date); }
function formatRelativeDate(value) { if (!value) return ''; return `geändert ${new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'short' }).format(new Date(value))}`; }
function formatOverviewDate(entry) {
  const value = entry.archived_at || entry.updated_at;
  if (!value) return '';
  const label = entry.archived_at ? 'archiviert' : 'geändert';
  return `${label} ${new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'short' }).format(new Date(value))}`;
}
function documentTitle(document) { return document.display_name || document.original_filename || 'Dokument'; }
function propertyValue(property) {
  if (property.value_type === 'date') return formatDate(property.value_date);
  if (property.value_type === 'number') return property.value_number ?? '';
  if (property.value_type === 'boolean') return property.value_boolean ? 'Ja' : 'Nein';
  return property.value_text || '';
}
function propertyDraftValue(property) {
  if (property.value_type === 'date') return property.value_date || '';
  if (property.value_type === 'number') return property.value_number ?? '';
  if (property.value_type === 'boolean') return property.value_boolean ?? false;
  return property.value_text || '';
}
function resetDossierDraft(entry = null) {
  Object.assign(dossierDraft, {
    title: entry?.title || '', dossier_type: entry?.dossier_type || '', reference: entry?.reference || '', description: entry?.description || '',
    state: entry?.state || 'active', opened_on: entry?.opened_on || '', closed_on: entry?.closed_on || '', color: entry?.color || '#3b8f83',
    properties: (entry?.properties || []).map((property) => ({ localId: property.id || crypto.randomUUID(), label: property.label, value_type: property.value_type, value: propertyDraftValue(property) })),
  });
}
function addPropertyDraft() { dossierDraft.properties.push({ localId: crypto.randomUUID(), label: '', value_type: 'text', value: '' }); }
function propertyPayload(property) {
  const base = { label: property.label.trim(), value_type: property.value_type, value_text: null, value_date: null, value_number: null, value_boolean: null };
  if (property.value_type === 'date') base.value_date = property.value || null;
  else if (property.value_type === 'number') base.value_number = property.value === '' ? null : Number(property.value);
  else if (property.value_type === 'boolean') base.value_boolean = Boolean(property.value);
  else base.value_text = String(property.value || '').trim() || null;
  return base;
}
function openCreateDossier() { dossierDialogMode.value = 'create'; editingDossierId.value = null; resetDossierDraft(); dossierDialogOpen.value = true; }
function openEditDossier(entry) { dossierDialogMode.value = 'edit'; editingDossierId.value = entry.id; resetDossierDraft(entry); dossierDialogOpen.value = true; }
async function quickCreateDossier() {
  if (saving.value) return;
  try {
    const color = dossierColors[Math.floor(Math.random() * dossierColors.length)];
    const created = await dossierStore.add({ title: DEFAULT_DOSSIER_TITLE, state: 'active', color });
    openDossier(created.id, { draft: true });
  } catch (error) {
    showMessage(error.message || 'Leuchttisch konnte nicht angelegt werden.', 'error');
  }
}
async function commitBoardTitle(event) {
  const value = (event.target.value || '').trim();
  const current = currentDossier.value?.title || '';
  if (!value) { event.target.value = current; return; }
  if (value === current) return;
  try {
    await dossierStore.update(dossierId.value, { title: value });
    const boardId = dossierId.value;
    recordHistory({
      label: 'Leuchttisch umbenennen',
      undo: () => dossierStore.update(boardId, { title: current }),
      redo: () => dossierStore.update(boardId, { title: value }),
    });
  } catch (error) {
    event.target.value = current;
    showMessage(error.message || 'Umbenennen fehlgeschlagen.', 'error');
  }
}
function dossierPayloadFromEntry(entry) {
  return {
    title: entry.title,
    dossier_type: entry.dossier_type || null,
    reference: entry.reference || null,
    description: entry.description || null,
    state: entry.state,
    opened_on: entry.opened_on || null,
    closed_on: entry.closed_on || null,
    color: entry.color || null,
    properties: (entry.properties || []).map((property) => ({
      label: property.label,
      value_type: property.value_type,
      value_text: property.value_text ?? null,
      value_date: property.value_date ?? null,
      value_number: property.value_number ?? null,
      value_boolean: property.value_boolean ?? null,
    })),
  };
}
async function saveDossier() {
  const payload = {
    title: dossierDraft.title.trim(), dossier_type: dossierDraft.dossier_type || null, reference: dossierDraft.reference || null,
    description: dossierDraft.description || null, state: dossierDraft.state, opened_on: dossierDraft.opened_on || null,
    closed_on: dossierDraft.closed_on || null, color: dossierDraft.color,
    properties: dossierDraft.properties.filter((property) => property.label.trim()).map(propertyPayload),
  };
  try {
    const editingId = editingDossierId.value;
    const before = dossierDialogMode.value === 'edit' && currentDossier.value?.id === editingId
      ? dossierPayloadFromEntry(currentDossier.value)
      : null;
    const result = dossierDialogMode.value === 'create' ? await dossierStore.add(payload) : await dossierStore.update(editingDossierId.value, payload);
    dossierDialogOpen.value = false;
    if (dossierDialogMode.value === 'create') openDossier(result.id, { draft: true });
    else {
      if (before) {
        recordHistory({
          label: 'Leuchttisch bearbeiten',
          undo: () => dossierStore.update(editingId, before),
          redo: () => dossierStore.update(editingId, payload),
        });
      }
      showMessage('Leuchttisch gespeichert.');
    }
  } catch (error) { showMessage(error.message || 'Leuchttisch konnte nicht gespeichert werden.', 'error'); }
}
async function toggleArchive(entry) { try { await dossierStore.update(entry.id, { archived: !entry.archived_at }); await refreshList(); } catch (error) { showMessage(error.message, 'error'); } }
async function toggleFavorite(entry) {
  try {
    await dossierStore.setFavorite(entry.id, !entry.is_favorite);
  } catch (error) {
    showMessage(error.message || 'Favorit konnte nicht geändert werden.', 'error');
  }
}
async function duplicateOverviewDossier(entry) {
  try {
    const created = await dossierStore.duplicate(entry.id);
    showMessage(`„${created.title}“ wurde angelegt.`);
  } catch (error) {
    showMessage(error.message || 'Leuchttisch konnte nicht dupliziert werden.', 'error');
  }
}
function askDeleteDossier(entry) { Object.assign(deleteDialog, { open: true, type: 'dossier', target: entry, title: 'Leuchttisch löschen?', description: `Der Leuchttisch „${entry.title}“ wird gelöscht. Die enthaltenen Dokumente bleiben in der Bibliothek erhalten.`, primaryText: 'Löschen' }); }
function openNoteDialog() { editingItem.value = null; Object.assign(noteDraft, { title: '', body: '', color: '#f4df8b' }); noteDialogOpen.value = true; }
function openLinkDialog() { editingItem.value = null; Object.assign(linkDraft, { title: '', url: '', description: '' }); linkDialogOpen.value = true; }
function editItem(item) { editingItem.value = item; if (item.item_type === 'note') { Object.assign(noteDraft, { title: item.note_title || '', body: item.note_body || '', color: item.note_color || '#f4df8b' }); noteDialogOpen.value = true; } else if (item.item_type === 'link') { Object.assign(linkDraft, { title: item.link_title || '', url: item.link_url || '', description: item.link_description || '' }); linkDialogOpen.value = true; } }
function cloneItemSnapshots(targets) { return targets.map((item) => structuredClone(item)); }
function recordCreatedItems(created, label) {
  if (!created.length) return;
  const boardId = dossierId.value;
  const snapshots = cloneItemSnapshots(created);
  const ids = snapshots.map((item) => item.id);
  recordHistory({
    label,
    undo: () => dossierStore.removeItems(boardId, ids),
    redo: () => dossierStore.restoreItems(boardId, snapshots),
  });
}
async function saveNote() {
  const payload = { note_title: noteDraft.title || null, note_body: noteDraft.body || null, note_color: noteDraft.color };
  try {
    if (editingItem.value) {
      const itemId = editingItem.value.id;
      const before = { note_title: editingItem.value.note_title, note_body: editingItem.value.note_body, note_color: editingItem.value.note_color };
      await dossierStore.updateItem(dossierId.value, itemId, payload);
      const boardId = dossierId.value;
      recordHistory({ label: 'Notiz bearbeiten', undo: () => dossierStore.updateItem(boardId, itemId, before), redo: () => dossierStore.updateItem(boardId, itemId, payload) });
    } else {
      const created = await dossierStore.addItem(dossierId.value, { item_type: 'note', ...payload });
      recordCreatedItems([created], 'Notiz hinzufügen');
      replaceSelection([created.id], created.id);
    }
    noteDialogOpen.value = false;
  } catch (error) { showMessage(error.message, 'error'); }
}
async function saveLink() {
  const payload = { link_title: linkDraft.title || null, link_url: linkDraft.url.trim(), link_description: linkDraft.description || null };
  try {
    if (editingItem.value) {
      const itemId = editingItem.value.id;
      const before = { link_title: editingItem.value.link_title, link_url: editingItem.value.link_url, link_description: editingItem.value.link_description };
      await dossierStore.updateItem(dossierId.value, itemId, payload);
      const boardId = dossierId.value;
      recordHistory({ label: 'Link bearbeiten', undo: () => dossierStore.updateItem(boardId, itemId, before), redo: () => dossierStore.updateItem(boardId, itemId, payload) });
    } else {
      const created = await dossierStore.addItem(dossierId.value, { item_type: 'link', ...payload });
      recordCreatedItems([created], 'Link hinzufügen');
      replaceSelection([created.id], created.id);
    }
    linkDialogOpen.value = false;
  } catch (error) { showMessage(error.message || 'Der Link ist ungültig.', 'error'); }
}
function selectItem(item, event = null) {
  if (event?.metaKey || event?.ctrlKey || event?.shiftKey) toggleSelection(item.id);
  else replaceSelection([item.id], item.id);
}
function clearSelection() { replaceSelection([]); }
function openConnectionDialog() {
  const item = selectedAttachableItem.value;
  if (!item) return;
  if (!documentItems.value.length) {
    showMessage('Füge zuerst ein Dokument zum Leuchttisch hinzu.');
    return;
  }
  connectionItemId.value = item.id;
  connectionTargetId.value = item.attached_to_item_id || null;
  connectionDialogOpen.value = true;
}
async function saveConnection() {
  const item = connectionItem.value;
  if (!item || connectionSaving.value) return;
  connectionSaving.value = true;
  try {
    const beforeTargetId = item.attached_to_item_id || null;
    const afterTargetId = connectionTargetId.value;
    await dossierStore.updateItem(dossierId.value, item.id, {
      attached_to_item_id: afterTargetId,
    });
    const boardId = dossierId.value;
    const itemId = item.id;
    recordHistory({
      label: afterTargetId ? 'Verbindung bearbeiten' : 'Verbindung lösen',
      undo: () => dossierStore.updateItem(boardId, itemId, { attached_to_item_id: beforeTargetId }),
      redo: () => dossierStore.updateItem(boardId, itemId, { attached_to_item_id: afterTargetId }),
    });
    connectionDialogOpen.value = false;
    showMessage(connectionTargetId.value ? 'Verbindung gespeichert.' : 'Verbindung gelöst.');
  } catch (error) {
    showMessage(error.message || 'Die Verbindung konnte nicht gespeichert werden.', 'error');
  } finally {
    connectionSaving.value = false;
  }
}
function toggleDossierInspector() {
  if (inspectorOpen.value && inspectorMode.value === 'dossier') {
    inspectorOpen.value = false;
    return;
  }
  inspectorMode.value = 'dossier';
  inspectorOpen.value = true;
}
function showSelectedPdfPreview() {
  const item = selectedPdfItem.value;
  if (!item) return;
  previewItemId.value = item.id;
  inspectorMode.value = 'preview';
  inspectorOpen.value = true;
}
function toggleSelectedPdfPreview() {
  const item = selectedPdfItem.value;
  if (!item) return;
  if (inspectorOpen.value && inspectorMode.value === 'preview' && previewItemId.value === item.id) {
    inspectorOpen.value = false;
    return;
  }
  showSelectedPdfPreview();
}
function openItem(item) { if (item.item_type === 'document') uiStore.requestWorkspace('openDocumentReader', item.document_id); else if (item.item_type === 'link') window.open(item.link_url, '_blank', 'noopener,noreferrer'); else editItem(item); }
function askRemoveSelectedItem() {
  const targets = [...selectedItems.value];
  if (!targets.length) return;
  const isSingleDocument = targets.length === 1 && targets[0].item_type === 'document';
  Object.assign(deleteDialog, {
    open: true,
    type: 'item',
    target: targets.map((item) => item.id),
    title: targets.length > 1 ? `${targets.length} Elemente entfernen?` : isSingleDocument ? 'Vom Tisch nehmen?' : 'Element löschen?',
    description: targets.length > 1
      ? 'Die ausgewählten Dokumente werden nur vom Leuchttisch genommen. Ausgewählte Notizen und Links werden gelöscht. Diese Aktion kann direkt rückgängig gemacht werden.'
      : isSingleDocument
      ? 'Das Dokument wird nur von diesem Leuchttisch genommen und bleibt in der Bibliothek erhalten.'
      : `„${itemTitle(targets[0])}“ wird gelöscht. Die Aktion kann direkt rückgängig gemacht werden.`,
    primaryText: targets.length > 1 || isSingleDocument ? 'Entfernen' : 'Löschen',
  });
}
async function confirmDelete() {
  try {
    if (deleteDialog.type === 'dossier') {
      await dossierStore.remove(deleteDialog.target.id);
      deleteDialog.open = false;
      goToDossiers();
    } else if (deleteDialog.type === 'item') {
      const ids = [...deleteDialog.target];
      const idSet = new Set(ids);
      const snapshots = cloneItemSnapshots(items.value.filter((item) => idSet.has(item.id)));
      const affectedAttachments = items.value
        .filter((item) => !idSet.has(item.id) && idSet.has(item.attached_to_item_id))
        .map((item) => ({ itemId: item.id, targetId: item.attached_to_item_id }));
      const boardId = dossierId.value;
      await dossierStore.removeItems(boardId, ids);
      clearSelection();
      deleteDialog.open = false;
      recordHistory({
        label: ids.length > 1 ? `${ids.length} Elemente entfernen` : 'Element entfernen',
        undo: async () => {
          await dossierStore.restoreItems(boardId, snapshots);
          for (const attachment of affectedAttachments) {
            await dossierStore.updateItem(boardId, attachment.itemId, { attached_to_item_id: attachment.targetId });
          }
          replaceSelection(ids, ids[0]);
        },
        redo: async () => {
          await dossierStore.removeItems(boardId, ids);
          clearSelection();
        },
      });
    }
  } catch (error) { showMessage(error.message, 'error'); }
}
async function openDocumentPicker() { pickerOpen.value = true; pickerSelection.value = new Set(); await loadPickerDocuments(); }
async function loadPickerDocuments() { pickerLoading.value = true; try { const params = new URLSearchParams({ limit: '100', offset: '0', include_total: 'false', sort: 'created_at', order: 'desc' }); if (pickerSearch.value.trim()) params.set('q', pickerSearch.value.trim()); const payload = await listDocuments(params.toString()); pickerDocuments.value = payload.items || []; } catch (error) { showMessage(error.message, 'error'); } finally { pickerLoading.value = false; } }
function schedulePickerSearch() { clearTimeout(pickerSearchTimer); pickerSearchTimer = setTimeout(loadPickerDocuments, 280); }
function togglePickerDocument(id) { const next = new Set(pickerSelection.value); next.has(id) ? next.delete(id) : next.add(id); pickerSelection.value = next; }
async function addPickedDocuments() { pickerLoading.value = true; try { const result = await dossierStore.addDocuments(dossierId.value, [...pickerSelection.value]); pickerOpen.value = false; recordCreatedItems(result.items || [], `${result.items.length} Dokumente hinzufügen`); replaceSelection((result.items || []).map((item) => item.id)); showMessage(`${result.items.length} Dokumente hinzugefügt.`); } catch (error) { showMessage(error.message, 'error'); } finally { pickerLoading.value = false; } }
async function uploadDocuments(event) { const files = [...(event.target.files || [])]; event.target.value = ''; if (!files.length) return; try { const ids = []; for (const file of files) { const body = new FormData(); body.append('file', file); const created = await apiFetch('/api/documents/upload', { method: 'POST', body }); ids.push(created.id); } const result = await dossierStore.addDocuments(dossierId.value, ids); recordCreatedItems(result.items || [], `${result.items.length} PDFs hinzufügen`); replaceSelection((result.items || []).map((item) => item.id)); showMessage(`${ids.length} PDF${ids.length === 1 ? '' : 's'} hochgeladen und hinzugefügt.`); } catch (error) { showMessage(error.message || 'Upload fehlgeschlagen.', 'error'); } }
function openInLibrary(item) { if (!item?.document_id) return; uiStore.requestWorkspace('openDocument', item.document_id); router.push('/'); window.setTimeout(() => uiStore.requestWorkspace('openDocument', item.document_id), 350); }
async function refreshList() { await dossierStore.fetchList({ includeArchived: true }); }
function scheduleOverviewStaggerEnd() {
  if (overviewStaggerTimer) clearTimeout(overviewStaggerTimer);
  const staggeredCount = Math.min(filteredOverviewDossiers.value.length, 13);
  overviewStaggerTimer = setTimeout(() => {
    staggerOverviewTiles.value = false;
    overviewStaggerTimer = null;
  }, 360 + staggeredCount * 42);
}

function prepareSidebarOverviewEntryAnimation() {
  if (overviewStaggerTimer) {
    clearTimeout(overviewStaggerTimer);
    overviewStaggerTimer = null;
  }
  staggerOverviewTiles.value = false;
  overviewStaggerPending.value = !dossierId.value && consumeDossierSidebarEntryAnimation();
}

function activateSidebarOverviewEntryAnimation() {
  if (dossierId.value || !overviewStaggerPending.value) return;
  staggerOverviewTiles.value = true;
  overviewStaggerPending.value = false;
  scheduleOverviewStaggerEnd();
}

let draftCleanupPromise = null;
async function discardIncompleteDraft(from) {
  if (from.name !== 'dossier-board' || from.query.draft !== '1') return;
  const draftId = String(from.params.dossierId || '');
  if (!draftId) return;
  const draftIsKnown = currentDossier.value?.id === draftId || dossiers.value.some((entry) => entry.id === draftId);
  if (!draftIsKnown) return;
  if (draftCleanupPromise) return draftCleanupPromise;

  draftCleanupPromise = (async () => {
    if (currentDossier.value?.id !== draftId) await dossierStore.fetchBoard(draftId);

    const pendingTitle = String(boardTitleInput.value?.value || '').trim();
    if (pendingTitle && pendingTitle !== currentDossier.value?.title) {
      await dossierStore.update(draftId, { title: pendingTitle });
    }

    if (shouldDiscardDossierDraft(currentDossier.value, items.value)) {
      await dossierStore.remove(draftId);
    }
  })();

  try {
    await draftCleanupPromise;
  } finally {
    draftCleanupPromise = null;
  }
}

async function handleDraftNavigation(to, from) {
  if (to.fullPath === from.fullPath) return true;
  if (
    to.name === 'dossier-board'
    && from.name === 'dossier-board'
    && String(to.params.dossierId || '') === String(from.params.dossierId || '')
  ) return true;
  try {
    await discardIncompleteDraft(from);
    return true;
  } catch (error) {
    showMessage(error.message || 'Der neue Leuchttisch konnte nicht geprüft werden.', 'error');
    return false;
  }
}

onBeforeRouteUpdate(handleDraftNavigation);
onBeforeRouteLeave(handleDraftNavigation);

watch(density, (value) => {
  localStorage.setItem('pm.dossier.density', value);
  if (fittedScale.value == null) return;
  const oldScale = fittedScale.value || 1;
  const nextScale = DENSITY_SCALE[value] || 1;
  const wrap = wrapEl.value;
  const centerX = (wrap?.clientWidth || 0) / 2;
  const centerY = (wrap?.clientHeight || 0) / 2;
  const logicalCenterX = (centerX - boardView.x) / oldScale;
  const logicalCenterY = (centerY - boardView.y) / oldScale;
  fittedScale.value = null;
  boardView.x = centerX - logicalCenterX * nextScale;
  boardView.y = centerY - logicalCenterY * nextScale;
});
watch(overviewSort, (value) => localStorage.setItem('pm.dossier.overviewSort', value));
watch(selectedPdfItem, (item) => {
  if (!inspectorOpen.value || inspectorMode.value !== 'preview') return;
  previewItemId.value = item?.id || null;
});
watch(() => route.query.status, (status) => {
  if (typeof status === 'string' && overviewStateOptions.some((option) => option.value === status)) {
    overviewState.value = status;
  }
}, { immediate: true });
let quickCreatePending = false;
watch(() => route.query.new, async (isNew) => {
  if (route.name === 'dossiers' && isNew && !quickCreatePending) {
    quickCreatePending = true;
    await router.replace({ name: 'dossiers', query: {} });
    await quickCreateDossier();
    quickCreatePending = false;
  }
}, { immediate: true });
watch(dossierId, (id) => {
  if (!id) prepareSidebarOverviewEntryAnimation();
  else {
    overviewStaggerPending.value = false;
    staggerOverviewTiles.value = false;
  }
}, { flush: 'sync' });
watch(dossierId, async (id) => {
  resetBoardView();
  clearSelection();
  clearHistory();
  connectionDialogOpen.value = false;
  connectionItemId.value = null;
  connectionTargetId.value = null;
  inspectorOpen.value = false;
  inspectorMode.value = 'dossier';
  previewItemId.value = null;
  if (id) {
    await dossierStore.fetchBoard(id);
    await nextTick();
    await fitBoardToViewport({ animate: false });
  } else {
    currentDossier.value = null;
    await refreshList();
    activateSidebarOverviewEntryAnimation();
  }
});
onMounted(async () => {
  window.addEventListener('keydown', onBoardKeyDown);
  window.addEventListener('keyup', onBoardKeyUp);
  window.addEventListener('blur', onWindowBlur);
  await refreshList();
  if (!dossierId.value) activateSidebarOverviewEntryAnimation();
  if (dossierId.value) {
    if (currentDossier.value?.id !== dossierId.value) await dossierStore.fetchBoard(dossierId.value);
    await nextTick();
    await fitBoardToViewport({ animate: false });
  }
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onBoardKeyDown);
  window.removeEventListener('keyup', onBoardKeyUp);
  window.removeEventListener('blur', onWindowBlur);
  window.removeEventListener('pointermove', onDragMove);
  window.removeEventListener('pointerup', onDragUp);
  window.removeEventListener('pointercancel', onDragCancel);
  cancelSelection();
  if (dragFrame) cancelAnimationFrame(dragFrame);
  cancelPan();
  stopViewTransition();
  if (overviewStaggerTimer) clearTimeout(overviewStaggerTimer);
  for (const timer of settlingTimers.values()) clearTimeout(timer);
  settlingTimers.clear();
});
</script>

<style scoped>
.dossier-main {
  /* Konzept-Token → echtes PaperMind-System ("Kontur") */
  --dsr-bg: var(--pm-content-surface);
  --dsr-card: var(--pm-v-card, var(--pm-app-surface-raised));
  --dsr-reader: var(--pm-pdf-stage-bg, var(--pm-content-surface));
  --dsr-border: var(--pm-divider);
  --dsr-row-border: var(--pm-row-border, var(--pm-divider));
  --dossier-sidebar-width: 272px;
  height: 100dvh; overflow: hidden; background: var(--dsr-bg); color: var(--pm-text);
}
.dossier-shell { display: grid; grid-template-columns: var(--dossier-sidebar-width) minmax(0, 1fr); height: 100%; }
.dossier-main--embedded .dossier-shell { grid-template-columns: minmax(0, 1fr); }
@keyframes dossier-view-open {
  from { opacity: .28; transform: translateY(12px) scale(.982); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.dossier-sidebar { display: flex; flex-direction: column; min-width: 0; overflow: hidden; background: var(--pm-sidebar-surface); color: var(--pm-sidebar-text); border-right: 1px solid var(--pm-sidebar-border); }
.dossier-sidebar__head { display: grid; gap: 14px; padding: 16px 14px 12px; }
.dossier-brand { display: flex; align-items: center; gap: 10px; border: 0; background: none; color: inherit; font-size: .98rem; font-weight: 720; cursor: pointer; }
.dossier-brand__mark { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 10px; background: var(--pm-sidebar-accent); color: var(--pm-sidebar-surface); }
.dossier-nav { display: grid; gap: 4px; }
.dossier-nav button, .dossier-sidebar__foot button { display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 10px; border: 0; border-radius: 9px; background: transparent; color: var(--pm-sidebar-muted); text-align: left; cursor: pointer; }
.dossier-nav button:hover, .dossier-sidebar__foot button:hover { background: var(--pm-sidebar-hover); color: var(--pm-sidebar-text); }
.dossier-nav .dossier-nav__active { background: color-mix(in srgb, var(--pm-sidebar-accent) 16%, transparent); color: var(--pm-sidebar-accent); }
.dossier-nav__count { margin-left: auto; font-size: .7rem; }
.dossier-sidebar__search :deep(.v-field) { color: var(--pm-sidebar-text); background: color-mix(in srgb, var(--pm-sidebar-text) 6%, transparent); }
.dossier-sidebar__list { flex: 1; min-height: 0; overflow-y: auto; padding: 5px 10px 16px; }
.dossier-sidebar__entry { display: flex; align-items: center; gap: 9px; width: 100%; padding: 8px; border: 0; border-radius: 10px; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.dossier-sidebar__entry:hover { background: var(--pm-sidebar-hover); }
.dossier-sidebar__entry--active { background: color-mix(in srgb, var(--pm-sidebar-accent) 13%, transparent); }
.dossier-sidebar__entry-icon { width: 30px; height: 30px; flex: none; display: grid; place-items: center; border-radius: 8px; background: color-mix(in srgb, var(--dossier-color) 20%, transparent); color: var(--dossier-color); }
.dossier-sidebar__entry-copy { min-width: 0; display: grid; gap: 2px; }
.dossier-sidebar__entry-copy strong { overflow: hidden; font-size: .78rem; font-weight: 620; text-overflow: ellipsis; white-space: nowrap; }
.dossier-sidebar__entry-copy small { color: var(--pm-sidebar-muted); font-size: .67rem; }
.dossier-sidebar__empty { padding: 18px 8px; color: var(--pm-sidebar-muted); font-size: .76rem; text-align: center; }
.dossier-sidebar__foot { padding: 10px 14px 14px; border-top: 1px solid var(--pm-sidebar-border); }
.dossier-overview { min-width: 0; display: flex; flex-direction: column; overflow: hidden; background: var(--dsr-bg); }
.dsr-ov__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 26px; padding: 26px 36px 18px; flex: none; }
.dsr-kicker { display: block; color: var(--pm-muted); font-size: .68rem; font-weight: 640; letter-spacing: .1em; text-transform: uppercase; }
.dsr-ov__heading h1 { margin: 0; font-size: 2.125rem; font-weight: 680; letter-spacing: -.02em; line-height: 1.25; }
.dsr-ov__sub { margin: 5px 0 0; color: var(--pm-muted); font-size: .78rem; }
.dsr-ov__filters { display: flex; align-items: center; gap: 10px; padding: 0 36px 18px; border-bottom: 1px solid var(--dsr-border); flex: none; }
.dsr-ov__spacer { flex: 1; }

/* Segmented control */
.dsr-seg { display: inline-flex; padding: 3px; border-radius: 9px; background: var(--pm-track); }
.dsr-seg__btn { appearance: none; border: 0; padding: 5px 12px; border-radius: 7px; background: transparent; color: var(--pm-muted); font-size: .78rem; font-weight: 600; cursor: pointer; white-space: nowrap; transition: color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing); }
.dsr-seg__btn:hover { color: var(--pm-text); }
.dsr-seg__btn--on { background: var(--dsr-card); color: var(--pm-text); box-shadow: 0 1px 2px rgba(0, 0, 0, .1); }

/* Search field */
.dsr-search { display: inline-flex; align-items: center; gap: 7px; width: 300px; max-width: 46vw; height: 34px; padding: 0 10px; border: 1px solid var(--dsr-border); border-radius: 9px; background: var(--dsr-card); color: var(--pm-muted); }
.dsr-search:focus-within { border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent); }
.dsr-search input { flex: 1; min-width: 0; border: 0; background: transparent; color: var(--pm-text); font-size: .84rem; outline: none; }
.dsr-search__clear { display: grid; place-items: center; width: 20px; height: 20px; border: 0; border-radius: 6px; background: transparent; color: var(--pm-muted); cursor: pointer; }
.dsr-search__clear:hover { background: var(--pm-track); color: var(--pm-text); }

/* Startbereich 2a/2b: Stapelkacheln */
.dsr-sort { display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--pm-muted); font: inherit; font-size: .78rem; font-weight: 600; cursor: pointer; white-space: nowrap; }
.dsr-sort:hover, .dsr-sort[aria-expanded="true"] { border-color: var(--dsr-border); background: var(--pm-chip-bg); color: var(--pm-text); }
.dsr-overview-scroll { flex: 1; min-height: 0; overflow-y: auto; }
.dsr-overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 380px)); justify-content: start; gap: 18px; padding: 26px 36px 36px; align-items: stretch; }
.dsr-tile { min-width: 0; display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--dsr-border); border-radius: 14px; background: var(--dsr-card); color: var(--pm-text); cursor: pointer; opacity: 1; transform: translate3d(0, 0, 0) scale(1); backface-visibility: hidden; transition: border-color var(--pm-duration-fast) var(--pm-easing), box-shadow var(--pm-duration-base) var(--pm-easing), opacity var(--pm-duration-fast) var(--pm-easing); }
.dsr-overview-grid--stagger-pending .dsr-tile { opacity: 0; }
.dsr-overview-grid--stagger .dsr-tile {
  animation: dsr-tile-sidebar-enter 320ms cubic-bezier(.22, .72, .2, 1) var(--dsr-tile-enter-delay, 0ms) backwards;
  will-change: opacity, transform;
}
@keyframes dsr-tile-sidebar-enter {
  from { opacity: 0; transform: translate3d(0, 10px, 0) scale(.992); }
  to { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
}
.dsr-tile:hover, .dsr-tile:focus-within { border-color: var(--pm-accent); box-shadow: 0 1px 2px rgba(0, 0, 0, .06), 0 6px 18px rgba(0, 0, 0, .08); }
.dsr-tile:focus-visible { outline: 2px solid color-mix(in srgb, var(--pm-accent) 62%, transparent); outline-offset: 2px; }
.dsr-tile__preview { position: relative; height: 160px; flex: none; overflow: hidden; border-bottom: 1px solid var(--dsr-row-border); background: var(--dsr-reader); }
.dsr-tile__grid { position: absolute; inset: 0; background-image: radial-gradient(var(--pm-thumb-line) 1px, transparent 1px); background-size: 13px 13px; opacity: .55; }
.dsr-tile__actions { position: absolute; top: 8px; right: 8px; z-index: 5; display: flex; align-items: center; gap: 4px; }
.dsr-tile__action { width: 28px; height: 28px; display: grid; place-items: center; padding: 0; border: 1px solid var(--dsr-border); border-radius: 7px; background: var(--dsr-card); color: var(--pm-muted); cursor: pointer; opacity: 0; transition: opacity var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing), color var(--pm-duration-fast) var(--pm-easing); }
.dsr-tile:hover .dsr-tile__action, .dsr-tile:focus-within .dsr-tile__action, .dsr-tile__favorite--on { opacity: 1; }
.dsr-tile__action:hover { background: var(--pm-chip-bg); color: var(--pm-text); }
.dsr-tile__favorite--on { color: var(--pm-star); }
.dsr-stack { position: absolute; left: 0; right: 0; bottom: -16px; display: flex; align-items: flex-end; justify-content: center; }
.dsr-stack__doc { position: relative; width: 104px; height: 136px; flex: none; overflow: hidden; padding: 8px; border: 1px solid var(--pm-thumb-line); border-radius: 4px; background: var(--pm-thumb-bg); box-sizing: border-box; box-shadow: 0 6px 14px rgba(48, 62, 67, .14); transform-origin: bottom center; transition: transform 300ms cubic-bezier(.2, .82, .24, 1), box-shadow 300ms var(--pm-easing); }
.dsr-stack__doc--0 { transform: rotate(-6deg) translate(8px, 8px); }
.dsr-stack__doc--1 { z-index: 2; margin: 0 -18px; }
.dsr-stack__doc--2 { transform: rotate(6deg) translate(-8px, 8px); }
.dsr-tile:hover .dsr-stack__doc--0, .dsr-tile:focus-within .dsr-stack__doc--0 { transform: rotate(-8deg) translate(3px, 2px); }
.dsr-tile:hover .dsr-stack__doc--1, .dsr-tile:focus-within .dsr-stack__doc--1 { transform: translateY(-7px); box-shadow: 0 12px 24px rgba(48, 62, 67, .18); }
.dsr-tile:hover .dsr-stack__doc--2, .dsr-tile:focus-within .dsr-stack__doc--2 { transform: rotate(8deg) translate(-3px, 2px); }
.dsr-stack__doc img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; background: var(--pm-thumb-bg); }
.dsr-stack__paper-lines { display: block; width: 100%; height: 100%; background: repeating-linear-gradient(to bottom, transparent 0 6px, var(--pm-thumb-line) 6px 8px); opacity: .78; }
.dsr-stack__doc.dsr-thumb { background: var(--pm-chip-bg); }
.dsr-stack__doc.dsr-thumb::after { content: ''; position: absolute; z-index: 0; inset: 0; background-image: linear-gradient(90deg, var(--pm-chip-bg) 25%, color-mix(in srgb, var(--pm-chip-bg) 45%, var(--dsr-card)) 50%, var(--pm-chip-bg) 75%); background-size: 240% 100%; opacity: 1; animation: dsr-skeleton 1.3s linear infinite; transition: opacity 220ms ease-out; pointer-events: none; }
.dsr-stack__doc.dsr-thumb img { z-index: 1; opacity: 0; transition: opacity 260ms ease-out; }
.dsr-stack__doc.dsr-thumb--loaded::after { opacity: 0; animation-play-state: paused; }
.dsr-stack__doc.dsr-thumb--loaded img { opacity: 1; }
.dsr-stack__doc.dsr-thumb--error::after { opacity: 0; animation-play-state: paused; }
.dsr-stack__doc.dsr-thumb--error img { display: none; }
.dsr-tile__body { flex: 1; display: flex; flex-direction: column; gap: 8px; padding: 14px 18px 16px; }
.dsr-tile__body h2 { margin: 0; overflow: hidden; font-size: 15.5px; font-weight: 660; letter-spacing: -.015em; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.dsr-tile__description { min-height: 20px; margin: 0; overflow: hidden; color: var(--pm-muted); font-size: 12.5px; line-height: 1.6; text-overflow: ellipsis; white-space: nowrap; }
.dsr-tile__meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: auto; padding-top: 8px; border-top: 1px solid var(--dsr-row-border); color: var(--pm-muted); font-size: 12px; }
.dsr-tile__meta span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dsr-tile__meta span:last-child { flex: none; }
.dsr-overview-grid--loading { flex: 1; }
.dsr-tile--skeleton { pointer-events: none; }
.dsr-tile--skeleton .dsr-tile__preview { display: grid; place-items: center; }
.dsr-skeleton-block, .dsr-tile--skeleton .dsr-tile__body span { display: block; border-radius: 6px; background: linear-gradient(90deg, var(--pm-chip-bg) 25%, color-mix(in srgb, var(--pm-chip-bg) 45%, var(--dsr-card)) 50%, var(--pm-chip-bg) 75%); background-size: 240% 100%; animation: dsr-skeleton 1.3s linear infinite; }
.dsr-skeleton-block { width: 132px; height: 68px; }
.dsr-tile--skeleton .dsr-tile__body span:nth-child(1) { width: 55%; height: 18px; }
.dsr-tile--skeleton .dsr-tile__body span:nth-child(2) { width: 82%; height: 14px; }
.dsr-tile--skeleton .dsr-tile__body span:nth-child(3) { width: 100%; height: 28px; margin-top: auto; }
@keyframes dsr-skeleton { to { background-position: -240% 0; } }
@keyframes dsr-sheen { 0% { transform: translateX(-118%); } 55% { transform: translateX(118%); } 100% { transform: translateX(118%); } }
@keyframes dsr-skel-dot { 0%, 100% { opacity: .3; } 50% { opacity: 1; } }
.dossier-empty--overview { flex: 1; padding: 36px; }
.dossier-empty--overview p { max-width: 390px; margin-top: 2px; color: color-mix(in srgb, var(--pm-text) 68%, var(--pm-muted)); font-size: .8rem; line-height: 1.6; }
.dossier-empty--overview h2 { font-size: 1.08rem; font-weight: 680; letter-spacing: -.018em; }
.dsr-overview-empty__visual { margin-bottom: 12px; }
.dsr-overview-empty__action { height: 40px; margin-top: 6px; padding-inline: 17px; box-shadow: 0 6px 16px color-mix(in srgb, var(--pm-accent) 14%, transparent); }
.dossier-loading, .dossier-empty { min-height: 350px; display: grid; place-items: center; align-content: center; gap: 10px; color: var(--pm-muted); text-align: center; }
.dossier-empty h2, .dossier-empty p { margin: 0; }
.dossier-board-page { min-width: 0; display: grid; grid-template-rows: auto auto minmax(0, 1fr); overflow: hidden; background: var(--pm-content-surface); animation: dossier-view-open 320ms cubic-bezier(.2, .82, .24, 1) both; transform-origin: 50% 18%; }
.dossier-board-header { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) minmax(230px, 360px) minmax(0, 1fr); align-items: center; gap: 16px; min-height: 58px; padding: 8px 18px; border-bottom: 1px solid var(--pm-divider); background: var(--pm-content-surface); }
.dossier-crumbs { min-width: 0; display: flex; align-items: center; gap: 8px; }
.dossier-crumbs__root { flex: none; display: inline-flex; align-items: center; gap: 6px; margin-left: -8px; padding: 4px 8px; border: 0; border-radius: 8px; background: transparent; color: var(--pm-muted); font-size: .82rem; font-weight: 600; cursor: pointer; transition: color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing); }
.dossier-crumbs__root:hover { color: var(--pm-text); background: rgba(var(--v-theme-on-surface), .05); }
.dossier-crumbs__sep { flex: none; color: var(--pm-muted); opacity: .5; }
.dossier-crumbs__current { min-width: 0; display: flex; align-items: center; gap: 8px; }
.dossier-crumbs__current strong { min-width: 0; overflow: hidden; font-size: .95rem; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.dossier-crumbs__title { min-width: 60px; max-width: 46vw; padding: 3px 8px; margin-left: -8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--pm-text); font-size: .95rem; font-weight: 600; font-family: inherit; text-overflow: ellipsis; cursor: text; transition: border-color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing); }
.dossier-crumbs__title:hover { background: rgba(var(--v-theme-on-surface), .04); }
.dossier-crumbs__title:focus { outline: none; border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent); background: var(--dsr-card); }
.dossier-board-header__search { width: 100%; max-width: 360px; justify-self: center; }
.dossier-board-header__right { min-width: 0; display: flex; align-items: center; justify-self: end; gap: 12px; }
.dossier-board-header__meta { color: var(--pm-muted); font-size: .72rem; white-space: nowrap; }
.dossier-toolbar { min-width: 0; display: flex; align-items: center; gap: 8px; padding: 9px 16px; overflow-x: auto; border-bottom: 1px solid var(--pm-divider); background: var(--pm-content-surface); }
.dossier-toolbar__divider { width: 1px; height: 22px; background: var(--pm-divider); margin: 0 2px; }

/* Einheitliches Button-System (an .dash-btn des Dashboards angelehnt) */
.dsr-btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; flex: none; height: 36px; padding: 0 13px; border: 1px solid var(--pm-divider); border-radius: 9px; background: transparent; color: var(--pm-muted); font-size: 13px; font-weight: 600; line-height: 1; white-space: nowrap; cursor: pointer; transition: background var(--pm-duration-fast) var(--pm-easing), color var(--pm-duration-fast) var(--pm-easing), border-color var(--pm-duration-fast) var(--pm-easing); }
.dsr-btn:hover { color: var(--pm-text); border-color: color-mix(in srgb, var(--pm-text) 22%, transparent); background: rgba(var(--v-theme-on-surface), .04); }
.dsr-btn:focus-visible { outline: 2px solid color-mix(in srgb, var(--pm-accent) 55%, transparent); outline-offset: 1px; }
.dsr-btn:disabled { opacity: .42; cursor: default; pointer-events: none; }
.dsr-btn :deep(.v-icon) { opacity: .82; }
.dsr-btn__caret { margin: 0 -3px 0 1px; opacity: .7; }
.dsr-btn--primary { color: var(--pm-accent); background: color-mix(in srgb, var(--pm-accent) 13%, transparent); border-color: color-mix(in srgb, var(--pm-accent) 32%, transparent); }
.dsr-btn--primary:hover { color: var(--pm-accent); background: color-mix(in srgb, var(--pm-accent) 20%, transparent); border-color: color-mix(in srgb, var(--pm-accent) 45%, transparent); }
.dsr-btn--danger { color: var(--pm-error); }
.dsr-btn--danger:hover { color: var(--pm-error); background: color-mix(in srgb, var(--pm-error) 12%, transparent); border-color: color-mix(in srgb, var(--pm-error) 35%, transparent); }
.dsr-btn--ghost { border-color: transparent; background: transparent; }
.dsr-btn--ghost:hover { border-color: color-mix(in srgb, var(--pm-text) 18%, transparent); }
.dsr-btn--icon { width: 36px; padding: 0; border-color: transparent; }
.dsr-btn--icon:hover { border-color: color-mix(in srgb, var(--pm-text) 18%, transparent); }
.dsr-btn--sm { height: 30px; width: 30px; border-radius: 8px; }
.dsr-btn--block { width: 100%; }
.dsr-btn--active { color: var(--pm-accent); background: color-mix(in srgb, var(--pm-accent) 12%, transparent); border-color: color-mix(in srgb, var(--pm-accent) 30%, transparent); }
.dsr-btn--active :deep(.v-icon) { opacity: 1; }
.dossier-toolbar__spacer { flex: 1; }
.dsr-history-actions { display: inline-flex; gap: 4px; }
.dsr-size-picker { height: 32px; display: inline-flex; align-items: center; gap: 5px; padding: 0 8px 0 9px; border: 1px solid var(--dsr-border); border-radius: 8px; background: transparent; color: var(--pm-muted); font: inherit; font-size: .75rem; font-weight: 620; line-height: 1; white-space: nowrap; cursor: pointer; transition: color var(--pm-duration-fast) var(--pm-easing), border-color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing); }
.dsr-size-picker:hover, .dsr-size-picker[aria-expanded="true"] { color: var(--pm-text); border-color: color-mix(in srgb, var(--pm-text) 20%, transparent); background: rgba(var(--v-theme-on-surface), .04); }
.dsr-size-picker:focus-visible { outline: 2px solid color-mix(in srgb, var(--pm-accent) 55%, transparent); outline-offset: 1px; }
.dsr-size-picker__caret { margin-left: 1px; opacity: .62; }
.dsr-fit-button { width: 32px; height: 32px; flex: none; border-color: var(--dsr-border); border-radius: 8px; color: var(--pm-muted); }
.dsr-fit-button:hover { color: var(--pm-text); }
.dsr-search--board { height: 34px; flex: none; }
.dossier-board-wrap { position: relative; min-height: 0; display: flex; overflow: hidden; }
.dsr-canvas-wrap { position: relative; flex: 1; min-width: 0; overflow: hidden; overscroll-behavior: contain; background: var(--dsr-reader); background-image: radial-gradient(rgba(var(--v-theme-on-surface), 0.25) 1px, transparent 1px); background-size: var(--dsr-grid-size, 26px) var(--dsr-grid-size, 26px); background-position: var(--dsr-grid-x, 13px) var(--dsr-grid-y, 13px); }
.dsr-canvas-wrap--pan-ready { cursor: grab; }
.dsr-canvas-wrap--panning { cursor: grabbing; }
.dsr-canvas-wrap--panning * { cursor: grabbing !important; }
.dsr-canvas-wrap--fitting { transition: background-position 260ms cubic-bezier(.2, .82, .24, 1), background-size 260ms cubic-bezier(.2, .82, .24, 1); }
.dsr-canvas-sizer { position: relative; width: 100%; height: 100%; }
.dsr-canvas { position: absolute; top: 0; left: 0; transform-origin: top left; touch-action: none; backface-visibility: hidden; will-change: transform; }
.dsr-canvas--fitting { transition: transform 260ms cubic-bezier(.2, .82, .24, 1); }
.dsr-connections { position: absolute; top: 0; left: 0; z-index: 5; overflow: visible; pointer-events: none; }
.dsr-connection path { fill: none; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.dsr-connection__halo { stroke: color-mix(in srgb, var(--dsr-reader) 88%, transparent); stroke-width: 5px; }
.dsr-connection__line { stroke: color-mix(in srgb, var(--pm-text) 34%, var(--pm-accent)); stroke-width: 1.4px; opacity: .72; transition: stroke var(--pm-duration-fast) var(--pm-easing), stroke-width var(--pm-duration-fast) var(--pm-easing), opacity var(--pm-duration-fast) var(--pm-easing); }
.dsr-connection--active .dsr-connection__line { stroke: var(--pm-accent); stroke-width: 2px; opacity: .96; }
.dsr-smart-guide { position: absolute; top: 0; left: 0; z-index: 35; display: block; border-radius: 999px; background: color-mix(in srgb, var(--pm-accent) 86%, white); box-shadow: 0 0 7px color-mix(in srgb, var(--pm-accent) 34%, transparent); opacity: .9; pointer-events: none; backface-visibility: hidden; will-change: transform; animation: dsr-smart-guide-in 90ms ease-out both; }
.dsr-smart-guide--vertical { transform-origin: top center; }
.dsr-smart-guide--horizontal { transform-origin: left center; }
@keyframes dsr-smart-guide-in { from { opacity: 0; } to { opacity: .9; } }

/* Leerer Leuchttisch – bewusst ohne umschließende Karte, damit die Fläche offen bleibt. */
.dsr-board-empty { position: absolute; inset: 0; z-index: 3; display: grid; place-items: center; padding: 32px; pointer-events: none; }
.dsr-board-empty__content { width: min(390px, 100%); display: flex; flex-direction: column; align-items: center; transform: translateY(-3vh); color: var(--pm-text); text-align: center; pointer-events: auto; animation: dsr-board-empty-enter 380ms cubic-bezier(.2, .82, .24, 1) both; }
.dsr-board-empty__visual { position: relative; width: 230px; height: 142px; margin-bottom: 18px; }
.dsr-board-empty__visual::before { content: ''; position: absolute; z-index: 0; inset: -34px -54px -24px; border-radius: 50%; background: radial-gradient(ellipse at center, color-mix(in srgb, var(--dsr-card) 76%, transparent) 0%, color-mix(in srgb, var(--dsr-card) 38%, transparent) 52%, transparent 76%); pointer-events: none; }
.dsr-board-empty__sheet { --empty-sheet-transform: translate3d(0, 0, 0); position: absolute; bottom: 7px; z-index: 1; width: 76px; height: 102px; display: flex; flex-direction: column; gap: 7px; padding: 11px 10px; border: 1px solid color-mix(in srgb, var(--pm-text) 17%, var(--pm-thumb-line)); border-radius: 8px; background: var(--pm-thumb-bg); color: color-mix(in srgb, var(--pm-text) 54%, var(--pm-muted)); box-shadow: 0 12px 28px rgba(30, 48, 54, .16); box-sizing: border-box; transform: var(--empty-sheet-transform); transform-origin: bottom center; animation: dsr-board-empty-sheet 460ms cubic-bezier(.2, .82, .24, 1) both; }
.dsr-board-empty__sheet i { display: block; height: 4px; flex: none; border-radius: 999px; background: color-mix(in srgb, var(--pm-text) 18%, var(--pm-thumb-line)); opacity: .86; }
.dsr-board-empty__sheet i:nth-of-type(2) { width: 78%; }
.dsr-board-empty__sheet i:nth-of-type(3) { width: 88%; }
.dsr-board-empty__sheet i:nth-of-type(4) { width: 62%; }
.dsr-board-empty__sheet--note { --empty-sheet-transform: translate3d(22px, 5px, 0) rotate(-8deg); left: 14px; height: 88px; color: color-mix(in srgb, var(--pm-accent) 78%, var(--pm-text)); background: color-mix(in srgb, var(--pm-accent) 14%, var(--pm-thumb-bg)); animation-delay: 45ms; }
.dsr-board-empty__sheet--document { --empty-sheet-transform: translate3d(0, -9px, 0); left: 77px; z-index: 2; width: 82px; height: 112px; color: var(--pm-accent); animation-delay: 90ms; }
.dsr-board-empty__sheet--link { --empty-sheet-transform: translate3d(-22px, 6px, 0) rotate(8deg); right: 13px; height: 84px; color: color-mix(in srgb, #3976a8 80%, var(--pm-text)); background: color-mix(in srgb, #3976a8 13%, var(--pm-thumb-bg)); animation-delay: 135ms; }
.dsr-board-empty__plus { position: absolute; right: 22px; bottom: 0; z-index: 4; width: 36px; height: 36px; display: grid; place-items: center; border: 3px solid var(--dsr-reader); border-radius: 50%; background: var(--pm-accent); color: var(--pm-content-surface); box-shadow: 0 6px 14px color-mix(in srgb, var(--pm-accent) 28%, transparent); animation: dsr-board-empty-plus 400ms 210ms cubic-bezier(.2, .82, .24, 1) both; }
.dsr-board-empty h2 { margin: 0; font-size: 1.08rem; font-weight: 680; letter-spacing: -.018em; line-height: 1.3; }
.dsr-board-empty p { max-width: 340px; margin: 8px 0 18px; color: color-mix(in srgb, var(--pm-text) 68%, var(--pm-muted)); font-size: .8rem; line-height: 1.55; }
.dsr-board-empty__actions { width: 100%; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.dsr-board-empty__choice { min-width: 0; display: flex; align-items: center; gap: 10px; padding: 10px 11px; border: 1px solid color-mix(in srgb, var(--pm-text) 16%, var(--dsr-border)); border-radius: 10px; background: color-mix(in srgb, var(--dsr-card) 96%, var(--dsr-reader)); color: var(--pm-text); box-shadow: 0 2px 8px rgba(30, 48, 54, .07); font: inherit; text-align: left; cursor: pointer; transition: border-color var(--pm-duration-fast) var(--pm-easing), box-shadow var(--pm-duration-fast) var(--pm-easing), color var(--pm-duration-fast) var(--pm-easing); }
.dsr-board-empty__choice:hover { border-color: color-mix(in srgb, var(--pm-accent) 48%, var(--dsr-border)); color: var(--pm-accent); box-shadow: 0 7px 18px rgba(30, 48, 54, .09); }
.dsr-board-empty__choice:focus-visible { outline: 2px solid color-mix(in srgb, var(--pm-accent) 55%, transparent); outline-offset: 2px; }
.dsr-board-empty__choice-icon { width: 32px; height: 32px; flex: none; display: grid; place-items: center; border-radius: 8px; background: color-mix(in srgb, var(--pm-accent) 16%, var(--dsr-card)); color: color-mix(in srgb, var(--pm-accent) 88%, var(--pm-text)); }
.dsr-board-empty__choice > span:last-child { min-width: 0; display: grid; gap: 2px; }
.dsr-board-empty__choice strong { overflow: hidden; font-size: .75rem; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.dsr-board-empty__choice small { overflow: hidden; color: color-mix(in srgb, var(--pm-text) 62%, var(--pm-muted)); font-size: .65rem; text-overflow: ellipsis; white-space: nowrap; }
@keyframes dsr-board-empty-enter { from { opacity: 0; transform: translateY(calc(-3vh + 10px)); } to { opacity: 1; transform: translateY(-3vh); } }
@keyframes dsr-board-empty-sheet { from { opacity: 0; transform: translate3d(0, 18px, 0) scale(.9); } to { opacity: 1; transform: var(--empty-sheet-transform); } }
@keyframes dsr-board-empty-plus { from { opacity: 0; transform: scale(.68) rotate(-20deg); } to { opacity: 1; transform: scale(1) rotate(0); } }

/* Freischwebende Element-Knoten */
.dsr-node { position: absolute; top: 0; left: 0; cursor: grab; touch-action: none; user-select: none; backface-visibility: hidden; transform-origin: top left; }
.dsr-selection-box { position: absolute; top: 0; left: 0; z-index: 60; box-sizing: border-box; pointer-events: none; border: 1px solid color-mix(in srgb, var(--pm-accent) 82%, transparent); border-radius: 4px; background: color-mix(in srgb, var(--pm-accent) 12%, transparent); box-shadow: 0 0 0 1px color-mix(in srgb, var(--dsr-card) 54%, transparent) inset; }
.dsr-canvas--dragging .dsr-node { cursor: grabbing; }
.dsr-node--dragging { opacity: .9; filter: saturate(.96); will-change: transform, opacity; }
.dsr-node--dragging :deep(.dsr-card) { box-shadow: 0 16px 34px rgba(27, 43, 48, .18); }
.dsr-node--settling { z-index: 39 !important; will-change: transform, opacity; transition: transform 180ms cubic-bezier(.2, .82, .24, 1); animation: dsr-node-settle 200ms cubic-bezier(.2, .82, .24, 1) both; }
.dsr-canvas--dragging .dsr-node:hover :deep(.dsr-card--document .dsr-card__thumb img) { transform: none; }
@keyframes dsr-node-settle {
  0% { opacity: .78; }
  55% { opacity: .94; }
  100% { opacity: 1; }
}

/* Elementkarten – Typunterschied über Material und Anatomie, nicht Farbe */
:deep(.dsr-card) { box-sizing: border-box; border: 1px solid var(--dsr-border); border-radius: 10px; background: var(--dsr-card); transition: border-color var(--pm-duration-fast) var(--pm-easing), box-shadow var(--pm-duration-fast) var(--pm-easing), opacity var(--pm-duration-fast) var(--pm-easing); }
:deep(.dsr-card--dim) { opacity: .32; }
:deep(.dsr-card--selected) { border-color: var(--pm-accent); box-shadow: 0 0 0 1px var(--pm-accent), 0 10px 26px rgba(27, 43, 48, .14); background: var(--dsr-card); }
:deep(.dsr-card--document.dsr-card--selected) { background: var(--dsr-card); box-shadow: 0 0 0 1px var(--pm-accent), 0 10px 26px rgba(27, 43, 48, .14); }
.dsr-node:hover :deep(.dsr-card) { border-color: color-mix(in srgb, var(--pm-text) 22%, var(--dsr-border)); }
.dsr-node:hover :deep(.dsr-card--selected) { border-color: var(--pm-accent); }
:deep(.dsr-card--document) { position: relative; width: 184px; height: 292px; display: grid; grid-template-rows: 198px minmax(0, 1fr); overflow: hidden; border-radius: 12px; box-shadow: 0 3px 10px rgba(27, 43, 48, .09); }
:deep(.dsr-card__thumb) { position: relative; min-width: 0; min-height: 0; overflow: hidden; border-bottom: 1px solid var(--dsr-row-border); background-color: var(--pm-pdf-stage-bg, var(--pm-thumb-bg, #fff)); background-image: linear-gradient(90deg, var(--pm-chip-bg) 25%, color-mix(in srgb, var(--pm-chip-bg) 45%, var(--dsr-card)) 50%, var(--pm-chip-bg) 75%); background-size: 240% 100%; animation: dsr-skeleton 1.3s linear infinite; }
:deep(.dsr-card__thumb img) { width: 100%; height: 100%; display: block; object-fit: cover; object-position: top center; opacity: 0; transition: opacity 320ms ease, transform 220ms cubic-bezier(.2, .82, .24, 1); }
:deep(.dsr-card__thumb.dsr-thumb--loaded) { animation: none; background-image: none; }
:deep(.dsr-card__thumb.dsr-thumb--loaded img) { opacity: 1; }
:deep(.dsr-card__thumb.dsr-thumb--error) { animation: none; background-image: none; }
:deep(.dsr-card__thumb.dsr-thumb--error img) { display: none; }
:deep(.dsr-card__format) { position: absolute; left: 8px; top: 8px; z-index: 1; padding: 3px 6px; border: 1px solid rgba(255, 255, 255, .66); border-radius: 5px; background: rgba(28, 42, 47, .72); color: #fff; font-size: 8px; font-weight: 760; letter-spacing: .08em; line-height: 1; box-shadow: 0 2px 6px rgba(20, 32, 36, .12); }
:deep(.dsr-card__group) { position: absolute; right: 8px; top: 8px; z-index: 1; max-width: 116px; overflow: hidden; padding: 3px 6px; border: 1px solid rgba(255, 255, 255, .58); border-radius: 5px; background: rgba(28, 42, 47, .72); color: #fff; font-size: 8px; font-weight: 690; line-height: 1; text-overflow: ellipsis; white-space: nowrap; }
:deep(.dsr-card__group--slip) { position: static; max-width: 100%; align-self: flex-start; margin: 0 0 1px; border-color: var(--dsr-border); background: var(--pm-chip-bg); color: var(--pm-chip-text); font-size: 8.5px; }
:deep(.dsr-card__content) { min-width: 0; display: flex; flex-direction: column; gap: 7px; padding: 10px 12px 11px; background: var(--dsr-card); }
:deep(.dsr-card--document .dsr-card__title) { flex: none; height: 35px; overflow: hidden; color: var(--pm-text); font-size: 13px; line-height: 1.35; font-weight: 660; letter-spacing: -.01em; overflow-wrap: break-word; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
:deep(.dsr-card__meta) { min-width: 0; display: flex; align-items: center; gap: 7px; color: var(--pm-muted); font-size: 11.5px; line-height: 1.35; }
:deep(.dsr-card__source) { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
:deep(.dsr-card__pages) { flex: none; padding: 2px 6px; border-radius: 5px; background: var(--pm-chip-bg); color: var(--pm-chip-text); font-size: 10.5px; font-weight: 620; white-space: nowrap; }
.dsr-node:hover :deep(.dsr-card--document:not(.dsr-card--selected)) { box-shadow: 0 9px 24px rgba(27, 43, 48, .13); }
.dsr-node:hover :deep(.dsr-card--document .dsr-card__thumb img) { transform: scale(1.015); }
:deep(.dsr-card--note), :deep(.dsr-card--link) { width: 184px; display: flex; flex-direction: column; gap: 4px; overflow: hidden; padding: 10px 11px; border-radius: 11px; box-shadow: 0 2px 8px rgba(27, 43, 48, .08); }
:deep(.dsr-card--note) { height: 124px; }
:deep(.dsr-card--link) { height: 96px; }
:deep(.dsr-card__slip-head) { min-width: 0; height: 20px; flex: none; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
:deep(.dsr-card__kind) { min-width: 0; display: flex; align-items: center; gap: 6px; color: var(--pm-muted); font-size: 9.5px; font-weight: 660; letter-spacing: .055em; line-height: 1; text-transform: uppercase; }
:deep(.dsr-card__kind-icon) { width: 20px; height: 20px; flex: none; display: grid; place-items: center; border-radius: 6px; background: color-mix(in srgb, var(--slip-accent) 34%, var(--dsr-card)); color: color-mix(in srgb, var(--pm-text) 80%, var(--slip-accent)); }
:deep(.dsr-card__external) { flex: none; color: var(--pm-muted); opacity: .5; }
:deep(.dsr-card__title--slip) { min-height: 0; overflow: hidden; color: var(--pm-text); font-size: 12.5px; line-height: 1.3; font-weight: 660; letter-spacing: -.005em; overflow-wrap: break-word; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
:deep(.dsr-card__body) { min-height: 0; overflow: hidden; color: var(--pm-muted); font-size: 11.25px; line-height: 1.42; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
:deep(.dsr-card__addr) { min-width: 0; overflow: hidden; color: var(--pm-muted); font-size: 10.75px; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.dsr-node:hover :deep(.dsr-card--note:not(.dsr-card--selected)), .dsr-node:hover :deep(.dsr-card--link:not(.dsr-card--selected)) { box-shadow: 0 9px 24px rgba(27, 43, 48, .13); }
/* Inspector – der äußere Clip animiert das Layout, das feste innere Panel nur per GPU. */
/* Rechte Inspector-Schublade: schwebt als Overlay über der rechten Boardkante
   und gleitet rein rein per transform (GPU-composited) – kein Layout, kein Neuzeichnen
   der Fläche, daher ruckelfrei. */
.dsr-inspector-shell { --dsr-inspector-size: 340px; position: absolute; top: 0; right: 0; bottom: 0; width: var(--dsr-inspector-size); max-width: 100%; z-index: 8; }
.dsr-inspector-shell--preview { --dsr-inspector-size: min(440px, 42vw); }
.dsr-inspector { position: absolute; inset: 0; width: 100%; display: flex; flex-direction: column; overflow: hidden; border-left: 1px solid var(--dsr-border); background: var(--dsr-bg); box-shadow: -20px 0 44px -16px rgba(0, 0, 0, .28); }
.dsr-inspector--preview { background: var(--pm-pdf-stage-bg, var(--dsr-bg)); }
.dsr-preview-close { position: absolute; top: 12px; right: 12px; z-index: 12; background: var(--dsr-card); box-shadow: 0 2px 8px rgba(27, 43, 48, .14); }
.dsr-inspector-slide-enter-active, .dsr-inspector-slide-leave-active { will-change: transform; transition: transform 300ms cubic-bezier(.32, .78, .28, 1); }
.dsr-inspector-slide-enter-from, .dsr-inspector-slide-leave-to { transform: translateX(100%); }
.dsr-inspector__head { display: flex; flex-direction: column; gap: 10px; padding: 14px; border-bottom: 1px solid var(--dsr-border); }
.dsr-inspector__eyebrow { display: flex; align-items: center; justify-content: space-between; }
.dsr-inspector__eyebrow span { color: var(--pm-muted); font-size: .66rem; font-weight: 640; letter-spacing: .08em; text-transform: uppercase; }
.dsr-inspector__title { overflow: hidden; font-size: .95rem; font-weight: 620; text-overflow: ellipsis; white-space: nowrap; }
.dsr-preview-body { position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.dsr-sidebar-pdf { flex: 1; min-height: 0; }
.dsr-sidebar-pdf :deep(.pdf-preview__rotate-controls),
.dsr-sidebar-pdf :deep(.pdf-preview__zoom-controls > .pdf-preview__tool-btn) { display: none; }
.dsr-sidebar-pdf :deep(.pdf-preview__pages) { gap: 10px; padding: 10px 10px 14px; }
.dsr-sidebar-pdf :deep(.pdf-preview__page) { box-shadow: 0 3px 12px rgba(27, 43, 48, .12); }
.dsr-preview-empty { flex: 1; display: grid; place-items: center; align-content: center; gap: 8px; padding: 28px; color: var(--pm-muted); text-align: center; }
.dsr-preview-empty strong { color: var(--pm-text); font-size: .86rem; }
.dsr-preview-empty span { max-width: 250px; font-size: .76rem; line-height: 1.5; }
/* Platzhalter, solange die PDF-Vorschau lädt (keine leere Schublade mehr) */
.dsr-preview-skeleton { position: absolute; inset: 0; z-index: 3; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 18px; padding: 26px 22px; background: var(--pm-pdf-stage-bg, var(--dsr-bg)); }
.dsr-preview-skeleton__page { position: relative; box-sizing: border-box; width: min(100%, 290px); max-height: 100%; aspect-ratio: 1 / 1.414; display: flex; flex-direction: column; gap: 13px; padding: 30px 26px; overflow: hidden; border-radius: 10px; background: color-mix(in srgb, var(--pm-thumb-bg, #fff) 90%, var(--pm-muted, #7f9098)); box-shadow: 0 22px 48px -22px rgba(20, 40, 48, .5), 0 2px 6px rgba(20, 40, 48, .08); }
.dsr-skel-bar, .dsr-skel-block { flex: none; border-radius: 5px; background: color-mix(in srgb, var(--pm-muted, #7f9098) 30%, transparent); }
.dsr-skel-bar { height: 11px; width: 100%; }
.dsr-skel-bar--title { height: 19px; width: 66%; border-radius: 6px; background: color-mix(in srgb, var(--pm-muted, #7f9098) 46%, transparent); }
.dsr-skel-bar--sub { width: 42%; }
.dsr-skel-bar--short { width: 58%; }
.dsr-skel-block { height: 78px; margin: 4px 0 8px; border-radius: 8px; }
.dsr-preview-skeleton__sheen { position: absolute; inset: 0; pointer-events: none; background: linear-gradient(105deg, transparent 42%, color-mix(in srgb, #fff 68%, transparent) 50%, transparent 58%); transform: translateX(-118%); animation: dsr-sheen 2s ease-in-out infinite; }
.dsr-preview-skeleton__caption { display: inline-flex; align-items: center; gap: 8px; color: var(--pm-muted); font-size: .76rem; letter-spacing: .01em; }
.dsr-preview-skeleton__dots { display: inline-flex; gap: 3px; }
.dsr-preview-skeleton__dots i { width: 4px; height: 4px; border-radius: 50%; background: currentColor; animation: dsr-skel-dot 1.1s ease-in-out infinite; }
.dsr-preview-skeleton__dots i:nth-child(2) { animation-delay: .16s; }
.dsr-preview-skeleton__dots i:nth-child(3) { animation-delay: .32s; }
.dsr-fade-enter-active, .dsr-fade-leave-active { transition: opacity 240ms ease; }
.dsr-fade-enter-from, .dsr-fade-leave-to { opacity: 0; }
.dsr-seg--full { display: flex; }
.dsr-seg--full .dsr-seg__btn { flex: 1; }
.dsr-inspector__body { flex: 1; min-height: 0; overflow-y: auto; padding: 14px; }
.dsr-kv { display: grid; grid-template-columns: 92px 1fr; gap: 10px 14px; margin: 0; }
.dsr-kv dt { color: var(--pm-muted); font-size: .78rem; }
.dsr-kv dd { display: flex; align-items: center; gap: 7px; margin: 0; font-size: .82rem; }
.dsr-mono { font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; font-size: .8rem; }
.dsr-props { display: flex; flex-direction: column; gap: 6px; }
.dsr-props__row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.dsr-props__key { overflow: hidden; padding: 5px 8px; border: 1px solid var(--pm-code-border); border-radius: 5px; background: var(--pm-code-bg); color: var(--pm-code-text); font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; font-size: .74rem; text-overflow: ellipsis; white-space: nowrap; }
.dsr-props__val { padding: 5px 8px; border: 1px solid var(--dsr-border); border-radius: 5px; font-size: .78rem; }
.dsr-inspector__empty { margin: 0; color: var(--pm-muted); font-size: .78rem; line-height: 1.5; }
.dsr-inspector__foot { flex: none; padding: 14px; border-top: 1px solid var(--dsr-border); }
.dossier-form { display: grid; gap: 13px; }.dossier-form__row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.dossier-form__row--three { grid-template-columns: 1fr 1fr 1fr; }
.dossier-form__color-row { display: flex; align-items: center; gap: 8px; min-height: 32px; }.dossier-form__color-row > span { margin-right: 5px; color: var(--pm-muted); font-size: .73rem; }
.dossier-form__swatch { width: 25px; height: 25px; padding: 0; border: 2px solid transparent; border-radius: 50%; cursor: pointer; }.dossier-form__swatch--active { outline: 2px solid var(--pm-text); outline-offset: 2px; }

.note-editor {
  display: grid;
  gap: 16px;
}

.note-editor__color-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 34px;
  padding: 1px 2px;
}

.note-editor__color-label,
.note-editor__color-name {
  color: var(--pm-muted);
  font-size: .72rem;
  font-weight: 650;
}

.note-editor__color-name {
  color: var(--pm-text);
  font-size: .68rem;
  text-align: right;
}

.note-editor__palette {
  display: flex;
  align-items: center;
  gap: 9px;
}

.note-editor__swatch {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 2px solid color-mix(in srgb, var(--pm-text) 10%, transparent);
  border-radius: 50%;
  outline: 0;
  color: rgba(24, 39, 43, .76);
  background: var(--note-swatch);
  cursor: pointer;
  transition: border-color var(--pm-duration-fast) var(--pm-easing), box-shadow var(--pm-duration-fast) var(--pm-easing);
}

.note-editor__swatch:hover {
  border-color: color-mix(in srgb, var(--pm-accent) 58%, transparent);
}

.note-editor__swatch:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--pm-accent) 48%, transparent);
  outline-offset: 3px;
}

.note-editor__swatch--active {
  border-color: rgb(var(--v-theme-surface-2, var(--v-theme-surface)));
  box-shadow: 0 0 0 2px var(--pm-accent);
}
.dossier-properties-editor { padding: 12px; border: 1px solid var(--pm-divider); border-radius: 11px; }.dossier-properties-editor__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }.dossier-property-row { display: grid; grid-template-columns: 1fr 130px 1fr 34px; gap: 8px; margin-top: 8px; }.dossier-properties-editor__empty { color: var(--pm-muted); font-size: .72rem; }
.dossier-picker-list { max-height: 420px; overflow-y: auto; border: 1px solid var(--pm-divider); border-radius: 11px; }.dossier-picker-row { display: grid; grid-template-columns: 42px 1fr 24px; align-items: center; gap: 10px; width: 100%; padding: 8px 10px; border: 0; border-bottom: 1px solid color-mix(in srgb, var(--pm-divider) 60%, transparent); background: transparent; color: var(--pm-text); text-align: left; cursor: pointer; }.dossier-picker-row:hover { background: var(--pm-row-hover); }.dossier-picker-row--selected { background: color-mix(in srgb, var(--pm-accent) 10%, transparent); }.dossier-picker-row--disabled { opacity: .48; cursor: default; }.dossier-picker-row img { width: 38px; height: 48px; object-fit: cover; border-radius: 3px; background: var(--pm-chip-bg); }.dossier-picker-row span { min-width: 0; display: grid; gap: 2px; }.dossier-picker-row strong { overflow: hidden; font-size: .76rem; text-overflow: ellipsis; white-space: nowrap; }.dossier-picker-row small { color: var(--pm-muted); font-size: .66rem; }.dossier-picker-empty { padding: 30px; color: var(--pm-muted); text-align: center; }
.dossier-connection-picker { display: grid; gap: 7px; max-height: 390px; overflow-y: auto; padding: 2px; }
.dossier-connection-choice { display: grid; grid-template-columns: 44px minmax(0, 1fr) 22px; align-items: center; gap: 11px; width: 100%; min-height: 62px; padding: 7px 10px; border: 1px solid var(--dsr-border); border-radius: 10px; background: var(--dsr-card); color: var(--pm-text); font: inherit; text-align: left; cursor: pointer; transition: border-color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing), box-shadow var(--pm-duration-fast) var(--pm-easing); }
.dossier-connection-choice:hover { border-color: color-mix(in srgb, var(--pm-text) 24%, var(--dsr-border)); }
.dossier-connection-choice--selected { border-color: color-mix(in srgb, var(--pm-accent) 62%, var(--dsr-border)); background: color-mix(in srgb, var(--pm-accent) 8%, var(--dsr-card)); box-shadow: 0 0 0 1px color-mix(in srgb, var(--pm-accent) 18%, transparent); }
.dossier-connection-choice img { width: 38px; height: 50px; object-fit: cover; border: 1px solid var(--pm-thumb-line); border-radius: 4px; background: var(--pm-thumb-bg); }
.dossier-connection-choice > span:nth-child(2) { min-width: 0; display: grid; gap: 3px; }
.dossier-connection-choice strong, .dossier-connection-choice small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dossier-connection-choice strong { font-size: .78rem; font-weight: 650; }
.dossier-connection-choice small { color: var(--pm-muted); font-size: .68rem; }
.dossier-connection-choice__icon { width: 38px; height: 38px; display: grid !important; place-items: center; border-radius: 9px; background: var(--pm-chip-bg); color: var(--pm-muted); }
@media (max-width: 1180px) { .dsr-overview-grid { grid-template-columns: repeat(2, minmax(236px, 360px)); } }
@media (max-width: 1080px) { .dossier-board-header__meta { display: none; }.dsr-inspector-shell { --dsr-inspector-size: min(340px, 100vw); }.dsr-inspector-shell--preview { --dsr-inspector-size: min(440px, 100vw); } }
@media (max-width: 720px) {
  .dsr-ov__head { align-items: flex-start; flex-direction: column; padding: 22px 20px 16px; }
  .dsr-ov__heading h1 { font-size: 1.8rem; }
  .dsr-ov__filters { align-items: stretch; flex-wrap: wrap; padding: 0 20px 16px; }
  .dsr-ov__spacer { display: none; }
  .dsr-search { width: 100%; max-width: none; order: 3; }
  .dossier-board-header { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: 'crumbs actions' 'search search'; gap: 8px 12px; }
  .dossier-crumbs { grid-area: crumbs; }
  .dossier-board-header__search { grid-area: search; width: min(420px, 100%); max-width: 100%; order: initial; }
  .dossier-board-header__right { grid-area: actions; }
  .dsr-overview-grid { grid-template-columns: minmax(0, 1fr); padding: 20px; }
  .dossier-form__row, .dossier-form__row--three, .dossier-property-row { grid-template-columns: 1fr; }
  .dossier-toolbar__divider { display: none; }
  .dsr-board-empty { padding: 24px; }
  .dsr-board-empty__visual { transform: scale(.9); margin-bottom: 10px; }
  .dsr-board-empty__actions { grid-template-columns: minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .dossier-board-page { animation: none; }
  .dsr-node--settling { transition: none; animation: none; }
  .dsr-canvas--fitting { transition: none; }
  .dsr-canvas-wrap--fitting { transition: none; }
  .dsr-smart-guide { animation: none; }
  .dsr-stack__doc { transition: none; }
  .dsr-inspector-slide-enter-active, .dsr-inspector-slide-leave-active,
  .dsr-inspector-slide-enter-active .dsr-inspector, .dsr-inspector-slide-leave-active .dsr-inspector { transition: none; }
  .dsr-board-empty__content, .dsr-board-empty__sheet, .dsr-board-empty__plus { animation: none; }
  :deep(.dsr-card__thumb img) { transition: none; }
  .dsr-node:hover :deep(.dsr-card--document .dsr-card__thumb img) { transform: none; }
  .dsr-skeleton-block, .dsr-tile--skeleton .dsr-tile__body span { animation: none; }
  .dsr-preview-skeleton__sheen, .dsr-preview-skeleton__dots i { animation: none; }
  .dsr-preview-skeleton__sheen { display: none; }
  .dsr-fade-enter-active, .dsr-fade-leave-active { transition: none; }
  .dsr-overview-grid--stagger .dsr-tile { animation: none; }
  :deep(.dsr-card__thumb), .dsr-stack__doc.dsr-thumb::after { animation: none; }
  .dsr-stack__doc.dsr-thumb img { transition: none; }
  .note-editor__swatch { transition: none; }
}
</style>
