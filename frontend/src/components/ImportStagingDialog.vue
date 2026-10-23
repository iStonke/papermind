<template>
  <BaseDialog
    v-model="isOpen"
    guard-close
    :max-width="MODAL_WORK_WIDTH_SPLIT"
    :card-class="['isd-card', { 'isd-card--empty': isEmptyLayout }]"
    title="Importieren"
    header-subtitle="Seiten zu einem neuen Dokument zusammenführen"
    @request-close="requestCloseImport"
  >

    <div class="isd-body" :style="{ '--isd-props-width': `${detailsPaneWidth}px` }">
      <input ref="fileInput" class="d-none" type="file" accept="application/pdf" multiple @change="onFileInputChange" />

      <!-- Seitenliste und dauerhafte Vorschau mit schwebenden Werkzeugen. -->
      <div class="isd-left">
        <div
          class="isd-grid-scroll import-staging-scroll"
          :aria-label="isEmptyLayout ? undefined : 'Dokumentseiten'"
          @dragenter.prevent="onMiniatureDragEnter"
          @dragover.prevent="onMiniatureDragOver"
          @dragleave="onMiniatureDragLeave"
          @drop.prevent="onMiniatureDrop"
          @click="onMiniatureAreaClick"
        >

          <!-- Dropzone (empty state) -->
          <div
            v-if="isEmptyLayout"
            class="isd-dropzone"
            :class="{
              'isd-dropzone--over': isDropzoneDragOver,
              'isd-dropzone--available-pages': availablePageCount > 0,
              'isd-dropzone--scanning': scannerFeedbackVisible
            }"
            @dragenter.prevent="onDropzoneDragEnter"
            @dragover.prevent="onDropzoneDragOver"
            @dragleave="onDropzoneDragLeave"
            @drop.prevent="onDropzoneDrop"
          >
            <!-- Im Scannerzustand bleibt nur das mittlere Blatt sichtbar. -->
            <div
              class="isd-dz-scene"
              :class="{
                'isd-dz-scene--scanning': scannerFeedbackVisible,
                'isd-dz-scene--pending': isScannerFeedbackPending,
                'isd-dz-scene--complete': scannerPreviewFinalizing
              }"
              aria-hidden="true"
            >
              <div class="isd-dz-scene__art">
                <span class="isd-dz-scene__halo" />
                <span class="isd-dz-scene__table" />

                <div class="isd-dz-sheet isd-dz-sheet--pdf">
                  <span class="isd-dz-sheet__kind">PDF</span>
                  <span class="isd-dz-sheet__copy">
                    <i /><i /><i /><i />
                  </span>
                </div>

                <div class="isd-dz-sheet isd-dz-sheet--image">
                  <span class="isd-dz-sheet__photo">
                    <i class="isd-dz-sheet__sun" />
                    <i class="isd-dz-sheet__mountain isd-dz-sheet__mountain--back" />
                    <i class="isd-dz-sheet__mountain isd-dz-sheet__mountain--front" />
                  </span>
                  <span class="isd-dz-sheet__caption" />
                </div>

                <div ref="scannerPreviewSourceElement" class="isd-dz-sheet isd-dz-sheet--front">
                  <img
                    v-if="scannerLivePreviewUrl"
                    :src="scannerLivePreviewUrl"
                    class="isd-dz-sheet__live-preview"
                    alt=""
                  />
                  <template v-else>
                    <span class="isd-dz-sheet__accent" />
                    <span class="isd-dz-sheet__headline" />
                    <span class="isd-dz-sheet__copy isd-dz-sheet__copy--front">
                      <i /><i /><i /><i />
                    </span>
                  </template>
                  <span class="isd-dz-sheet__scan" />
                  <span v-if="scannerLivePreviewUrl" class="isd-dz-sheet__live-progress">
                    {{ scannerLiveProgress }}%
                  </span>
                </div>

                <span class="isd-dz-scene__merge"><v-icon size="18">mdi-plus</v-icon></span>
              </div>
            </div>

            <div class="isd-dropzone__text-shell">
              <div class="isd-dropzone__text">
                <p class="isd-dropzone__title">Seiten zu einem Dokument zusammenfügen</p>
                <p class="isd-dropzone__subtitle">{{ dropzoneSubtitle }}</p>
              </div>
            </div>
            <div
              class="isd-dropzone__actions"
              :class="{ 'isd-dropzone__actions--single': !canTriggerScan }"
              @click.stop
            >
              <ImportScannerError v-if="scannerFailure" :failure="scannerFailure" :can-retry="canTriggerScan"
                :disabled="isUploadingSources || isCommitting" @retry="emitScan('page')" />
              <div
                v-else-if="scannerFeedbackVisible"
                class="isd-dropzone__action isd-dropzone__action--scanner-active"
                :class="{ 'isd-dropzone__action--scanner-pending': isScannerFeedbackPending }"
                role="status"
                aria-live="polite"
              >
                <span class="isd-dropzone__action-icon"><v-icon size="22">mdi-scanner</v-icon></span>
                <span class="isd-dropzone__action-copy">
                  <strong>{{ scannerFeedbackStatus }}</strong>
                </span>
                <button
                  v-if="canTriggerScan && props.scannerActive"
                  type="button"
                  class="isd-dropzone__scan-cancel"
                  aria-label="Scan abbrechen"
                  :disabled="props.scanRequestPending || props.scanCancelPending"
                  @click="emitScan('cancel')"
                >
                  <v-icon size="16">mdi-close</v-icon>
                  <span>Abbrechen</span>
                </button>
              </div>
              <button
                v-else-if="canTriggerScan"
                type="button"
                class="isd-dropzone__action"
                :disabled="isUploadingSources || isCommitting || Boolean(stagingStore.pendingCommit)"
                :title="props.scanner?.name || 'Scanner'"
                @click="emitScan('page')"
              >
                <span class="isd-dropzone__action-icon"><v-icon size="22">mdi-scanner</v-icon></span>
                <span class="isd-dropzone__action-copy">
                  <strong>Scannen</strong>
                  <small>Neue Seiten direkt erfassen</small>
                </span>
              </button>
              <div class="isd-dropzone__other-sources" :inert="scannerFeedbackVisible" :aria-hidden="scannerFeedbackVisible ? 'true' : undefined">
                <div class="isd-dropzone__source-choices">
                  <button
                    type="button"
                    class="isd-dropzone__action"
                    :disabled="isUploadingSources || isCommitting || Boolean(stagingStore.pendingCommit)"
                    @click="openFilePicker"
                  >
                    <span class="isd-dropzone__action-icon">
                      <v-icon size="22">mdi-file-pdf-box</v-icon>
                    </span>
                    <span class="isd-dropzone__action-copy">
                      <strong>PDFs auswählen</strong>
                      <small>
                        {{ isIOSDevice ? 'Eine oder mehrere Dateien' : 'Eine oder mehrere PDF-Dateien' }}
                      </small>
                    </span>
                  </button>
                  <div v-if="availablePageCount > 0"
                    class="isd-dropzone__action isd-dropzone__available-pages"
                    @click="openAvailablePages">
                    <button type="button" class="isd-dropzone__available-open"
                      :disabled="isUploadingSources || isCommitting || Boolean(stagingStore.pendingCommit) || availablePagesLoading || isRemovingAvailable"
                      :aria-busy="availablePagesLoading || isRemovingAvailable" :aria-label="availablePagesLabel">
                      <v-badge class="isd-dropzone__available-badge" :content="availablePageBadgeLabel" color="error" offset-x="6" offset-y="6" aria-hidden="true">
                        <span class="isd-dropzone__action-icon"><v-icon size="22">mdi-file-document-multiple-outline</v-icon></span>
                      </v-badge>
                      <span class="isd-dropzone__action-copy">
                        <strong>Verfügbare Seiten</strong>
                        <small>{{ availablePagesLoading ? 'Seiten werden geladen…' : availablePagesSummary }}</small>
                      </span>
                    </button>
                    <button type="button" class="isd-dropzone__available-remove"
                      :disabled="!canRemoveAvailable" :aria-label="availableRemoveLabel"
                      :title="availableRemovalTooltip"
                      @click.stop="availableRemoval.remove()">
                      <v-icon size="20" aria-hidden="true">mdi-trash-can-outline</v-icon>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Einspaltige, unabhängig scrollende Seitenliste -->
          <div
            v-else
            class="isd-page-grid import-staging-pages"
            @dragover.prevent="onPagesContainerDragOver($event, documents[0]?.id)"
            @drop.prevent="onPagesContainerDrop($event, documents[0]?.id)"
          >
            <template v-for="{ doc, page, globalIndex, pageIndexInDoc } in allPagesFlat" :key="page.id">
            <div v-if="documents.length > 1 && pageIndexInDoc === 0" class="isd-document-boundary" role="heading" aria-level="3" :aria-label="`Dokument: ${doc.title}`" @click.stop>{{ doc.title || 'Ohne Namen' }}</div>
            <div
              :ref="el => setPageThumbRef(page.id, el)"
              class="isd-page-card import-staging-page"
              :data-page-id="page.id"
              role="button" :tabindex="isPageSelected(doc.id, page.id) || (!selected?.pageId && globalIndex === 0) ? 0 : -1" :aria-label="`Seite ${globalIndex + 1}, ${doc.title}`"
              :aria-pressed="isSelectMode ? isPageMultiSelected(page.id) : isPageSelected(doc.id, page.id) || isPageMultiSelected(page.id)"
              @keydown.enter.prevent="onPageGridClick($event, doc, page, globalIndex)"
              @keydown.space.prevent="onPageGridClick($event, doc, page, globalIndex)"
              :data-page-index="pageIndexInDoc"
              :draggable="!isCommitting && !stagingStore.pendingCommit"
              :class="{
                'isd-page-card--selected': isPageSelected(doc.id, page.id),
                'isd-page-card--scan-arrival': scannerPreviewFlight?.pageId === page.id,
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
              <div class="isd-page-thumb-wrap" :style="pageThumbnailFormatStyle(page)">
                <div class="isd-page-thumb-inner">
                  <img
                    v-if="page.thumbUrl"
                    :src="page.thumbUrl"
                    class="isd-page-thumb import-staging-page__thumb"
                    :style="pageThumbnailImageStyle(page)"
                    draggable="false" loading="lazy" decoding="async"
                    @load="rememberThumbnailSize($event.target); page.previewError = false; onScannerThumbnailLoaded(page.id, $event.target)"
                    @error="page.previewError = true"
                    alt=""
                  />
                  <v-icon v-else size="32" class="isd-page-thumb-placeholder-icon">mdi-file-document-outline</v-icon>
                  <Transition name="isd-scan-frame">
                    <img
                      v-if="scannerThumbnailFallback?.pageId === page.id"
                      :src="scannerThumbnailFallback.url"
                      :style="pageThumbnailImageStyle(page)"
                      class="isd-scan-thumbnail-fallback"
                      @load="rememberThumbnailSize($event.target)"
                      draggable="false" alt=""
                    />
                  </Transition>
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
              <span v-if="stagingStore.sourceMetaById.get(page.sourceFileId)?.pageQuality?.[page.pageIndex]" class="isd-page-review">{{ stagingStore.sourceMetaById.get(page.sourceFileId).pageQuality[page.pageIndex] }}</span>
              <button v-if="page.previewError" type="button" class="isd-page-review" @click.stop="retryThumbnail(page)">Vorschau erneut laden</button>
            </div>
            </template>

            <!-- Scan-in-progress placeholder: zeigt, wo die nächste Seite gleich auftaucht -->
            <div v-if="props.scannerActive" class="isd-scanning-page-card">
              <div
                class="isd-scanning-page-thumb-wrap"
                :class="{ 'isd-scanning-page-thumb-wrap--live': scannerLivePreviewUrl }"
                :style="pageThumbnailFormatStyle({ thumbUrl: scannerLivePreviewUrl })"
              >
                <img
                  v-if="scannerLivePreviewUrl"
                  :src="scannerLivePreviewUrl"
                  class="isd-scanning-page-preview"
                  :style="{ filter: pageColorFilter(stagingStore.allPagesColorMode) }"
                  @load="rememberThumbnailSize($event.target)"
                  alt="Aktuelle Scanvorschau"
                />
                <v-icon v-else size="28" class="isd-scanning-page-icon">mdi-scanner</v-icon>
                <span v-if="scannerLivePreviewUrl" class="isd-scanning-page-progress">
                  {{ scannerLiveProgress }}%
                </span>
                <v-btn
                  icon
                  size="x-small"
                  variant="text"
                  class="isd-scanning-page-cancel"
                  title="Scan abbrechen"
                  aria-label="Scan abbrechen"
                  @click.stop="emitScan('cancel')"
                >
                  <v-icon size="16">mdi-close</v-icon>
                </v-btn>
              </div>
              <div class="isd-page-num isd-scanning-page-label">{{ scannerFeedbackCardLabel }}</div>
            </div>

            <ImportScannerError v-if="scannerFailure" compact :failure="scannerFailure" :can-retry="canTriggerScan"
              :disabled="isUploadingSources || isCommitting" @retry="emitScan('page')" />

            <!-- Add-files / scan placeholder card -->
            <div
              v-if="canTriggerScan"
              class="isd-add-page-card"
              :class="{
                'isd-add-page-card--disabled': isUploadingSources || isCommitting,
                'isd-add-page-card--drag-over': isAddPageDragOver,
                'isd-add-page-card--chooser': addSourceChooserOpen
              }"
              role="button"
              tabindex="0"
              title="Seite hinzufügen"
              @click="toggleAddSourceChooser"
              @keydown.enter.prevent="toggleAddSourceChooser"
              @keydown.space.prevent="toggleAddSourceChooser"
            >
              <div class="isd-add-page-thumb-wrap">
                <div v-if="!addSourceChooserOpen" class="isd-add-page-inner">
                  <v-icon size="28">mdi-plus</v-icon>
                </div>
                <div v-else class="isd-add-page-choices" @click.stop>
                  <button
                    type="button"
                    class="isd-add-page-choice"
                    @click="choosePdfSource"
                  >
                    <v-icon size="18">mdi-file-pdf-box</v-icon>
                    <span>PDF</span>
                  </button>
                  <button
                    type="button"
                    class="isd-add-page-choice"
                    :disabled="props.scannerActive"
                    :title="props.scanner?.name || 'Scanner'"
                    @click="chooseScanSource"
                  >
                    <v-icon size="18">mdi-scanner</v-icon>
                    <span>{{ props.scannerActive ? 'Aktiv' : 'Scan' }}</span>
                  </button>
                </div>
              </div>
              <div class="isd-page-num" aria-hidden="true">&nbsp;</div>
            </div>
            <div
              v-else
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
        <div v-if="!isEmptyLayout" class="isd-pages-footer">
          <strong>Seiten</strong>
          <span class="isd-page-count" :aria-label="`${totalPages} ${totalPages === 1 ? 'Seite' : 'Seiten'}`">{{ totalPages }}</span>
          <!-- Auswahlwerkzeuge gehören zur Seitenliste. -->
          <v-btn
            icon
            size="x-small"
            :variant="isSelectMode ? 'flat' : 'text'"
            :color="isSelectMode ? 'primary' : undefined"
            :title="isSelectMode ? 'Auswahl beenden' : 'Seiten auswählen'"
            :aria-label="isSelectMode ? 'Auswahl beenden' : 'Seiten auswählen'"
            class="isd-toolbar-select-btn"
            :class="{ 'isd-toolbar-select-btn--active': isSelectMode }"
            @click="toggleSelectMode"
          >
            <v-icon size="20">mdi-checkbox-multiple-outline</v-icon>
          </v-btn>
        </div>
        <div v-if="primaryDocument?.meta?.commitError" class="isd-import-error isd-workspace-error" role="alert">
          {{ primaryDocument.meta.commitError.message }}
          <button v-if="primaryDocument.meta.commitError.existing_doc_id" type="button" @click="requestCloseImport(); emit('open-document', primaryDocument.meta.commitError.existing_doc_id)">Vorhandenes Dokument öffnen</button>
        </div>
        <div v-if="!isEmptyLayout" role="region" aria-label="Seitenvorschau" class="isd-preview-panel">
          <PreviewToolbar class="isd-toolbar" label="Seitenwerkzeuge" show-zoom :zoom="previewZoomPercent"
            :default-zoom="Math.abs(previewZoom - 1) < .001" :can-zoom-in="canPreviewZoomIn" :can-zoom-out="canPreviewZoomOut"
            reset-label="Seite einpassen"
            @zoom-in="zoomPreviewIn" @zoom-out="zoomPreviewOut" @zoom-reset="resetPreviewZoom">
            <button type="button" tabindex="0" class="isd-tool-btn isd-magnifier-btn" :class="{ 'isd-tool-btn--active': previewMagnifierEnabled }"
              aria-label="Lupe" title="Lupe (Ausschnitt vergrößern)" :aria-pressed="previewMagnifierEnabled" :disabled="!hasSelectedPreview" @click="togglePreviewMagnifier"><v-icon size="17">mdi-magnify</v-icon></button>
            <div class="isd-direct-tools">
              <span class="pm-preview-toolbar__divider" aria-hidden="true" />
              <button type="button" tabindex="0" class="isd-tool-btn" aria-label="Nach links drehen" title="Nach links drehen" :disabled="pageToolsDisabled" @click="rotateAnySelectedPage(-90)"><v-icon size="17">mdi-rotate-left</v-icon></button>
              <button type="button" tabindex="0" class="isd-tool-btn" aria-label="Nach rechts drehen" title="Nach rechts drehen" :disabled="pageToolsDisabled" @click="rotateAnySelectedPage(90)"><v-icon size="17">mdi-rotate-right</v-icon></button>
              <button type="button" tabindex="0" class="isd-tool-btn" aria-label="Ausgewählte Seiten löschen" title="Ausgewählte Seiten löschen" :disabled="!isDeleteEnabled || isCommitting || Boolean(stagingStore.pendingCommit)" @click="deleteSelectedPages"><v-icon size="17">mdi-trash-can-outline</v-icon></button>
            </div>
            <div class="isd-color-group" role="group" aria-label="Farbmodus für alle Seiten">
              <span class="pm-preview-toolbar__divider" aria-hidden="true" />
              <button v-for="option in pageColorOptions" :key="option.value" type="button" tabindex="0" class="isd-tool-btn"
                :class="{ 'isd-tool-btn--active': stagingStore.allPagesColorMode === option.value }" :aria-label="option.title" :title="`${option.title} – für alle Seiten`"
                :aria-pressed="stagingStore.allPagesColorMode === option.value" :disabled="colorToolsDisabled" @click="setImportColorMode(option.value)"><v-icon size="17">{{ option.icon }}</v-icon></button>
            </div>
          </PreviewToolbar>

          <div
            ref="previewViewport" class="isd-preview-stage"
            :class="{ 'isd-preview-stage--magnify': previewMagnifierEnabled, 'isd-preview-stage--scan-handoff': scannerPreviewFlight && scannerPreviewFlight.pageId === selectedPageEntry?.id }"
            :aria-busy="previewImageLoading" :style="{ scrollSnapType: previewAdjusting || previewZoom > 1.001 ? 'none' : undefined }"
            tabindex="0" aria-label="Dokumentseite" @wheel="onPreviewWheel" @keydown="onPreviewKeydown" @scroll="onPreviewScroll" @scrollend="onPreviewScrollEnd"
          >
            <div v-if="hasSelectedPreview" class="isd-preview-pages" :style="previewCanvasStyle">
              <div v-for="{ page, globalIndex } in allPagesFlat" :key="page.id"
                :ref="el => setPreviewPageElement(page.id, el)"
                class="isd-preview-page" :class="{ 'isd-preview-page--active': page.id === selectedPageEntry?.id }"
                :data-preview-page-id="page.id" :style="previewPageStyle(page)"
                role="group" :aria-label="`Seite ${globalIndex + 1} von ${totalPages}`">
                <img
                  v-if="shouldLoadPreview(page.id) && pagePreviewSource(page)"
                  :src="pagePreviewSource(page)"
                  :ref="el => setPreviewImageElement(page.id, el)" :style="previewImageStyle(page)"
                  @load="onPreviewImageLoad(page.id, $event.target); onScannerPreviewLoaded(page.id, $event.target)"
                  class="isd-preview-page-image" :class="{ 'isd-preview-image': page.id === selectedPageEntry?.id }"
                  :alt="`Seite ${globalIndex + 1} von ${totalPages}`"
                  draggable="false" decoding="sync"
                  @pointermove="onPreviewPointerMove($event, page)"
                  @pointerleave="hidePreviewMagnifier"
                />
                <Transition name="isd-scan-frame">
                  <div v-if="scannerPreviewFallback?.pageId === page.id" class="isd-preview-scan-frame" aria-hidden="true">
                    <img :src="scannerPreviewFallback.url" :style="previewImageStyle(page)" draggable="false" alt="" />
                  </div>
                </Transition>
                <div
                  v-if="previewMagnifier?.pageId === page.id"
                  class="isd-preview-magnifier"
                  :style="previewMagnifierStyle"
                  aria-hidden="true"
                />
                <div v-if="!pagePreviewSource(page)" class="isd-preview-empty">
                  <v-icon size="40">mdi-file-document-outline</v-icon>
                  <span>Vorschau wird vorbereitet</span>
                </div>
              </div>
            </div>
            <div v-else class="isd-preview-canvas">
              <div class="isd-preview-empty isd-preview-empty--illustrated">
                <DocumentPreviewIllustration aria-label="Keine Seite ausgewählt" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right column: document properties.
           Wird im Leerzustand ausgeblendet und erst eingeblendet (Slide/Expand),
           sobald mindestens eine Seite hinzugefügt wurde. -->
      <ImportPaneDivider v-if="!isEmptyLayout" v-model="detailsPaneWidth" :controls="detailsPaneId" />
      <Transition name="isd-props-reveal">
      <div v-if="!isEmptyLayout" :id="detailsPaneId" class="isd-props">
        <div class="isd-props-heading">
          <div class="isd-props-title">
            <h3>Dokumentdetails</h3>
            <p :class="{ 'isd-analysis-progress': prepStatus.busy }" role="status" aria-live="polite">{{ analysisHeaderStatus }}</p>
          </div>
          <v-tooltip v-model="preparationHintOpen" location="bottom end" :max-width="280"
            :open-on-hover="!analysisTouchInput" :open-on-focus="!analysisTouchInput">
            <template #activator="{ props: tooltipProps }">
              <v-btn v-bind="tooltipProps" icon size="36" variant="text" class="isd-ai-status-btn"
                :class="`isd-ai-status-btn--${prepStatus.kind}`"
                :aria-label="prepStatus.busy ? `${prepStatus.label} – Details anzeigen` : analysisActionLabel"
                :aria-busy="prepStatus.busy"
                :disabled="!prepStatus.busy && (isCommitting || Boolean(stagingStore.pendingCommit) || totalPages === 0)"
                @click.stop="onImportAnalysisClick">
                <v-progress-circular v-if="prepStatus.busy" class="isd-ai-status-ring" indeterminate size="24" width="2" color="primary" aria-hidden="true" />
                <v-icon v-if="prepStatus.busy" size="14" color="primary" aria-hidden="true">mdi-creation</v-icon>
                <v-icon v-else-if="aiAnalysis.kind === 'failed'" size="20" aria-hidden="true">mdi-alert-circle-outline</v-icon>
                <v-icon v-else size="20" aria-hidden="true">mdi-creation</v-icon>
              </v-btn>
            </template>
            <strong class="isd-ai-status-heading">{{ prepStatus.busy ? prepStatus.label : analysisActionLabel }}</strong>
            <span>{{ prepStatus.busy ? prepStatus.description : aiStatusTitle }}</span>
            <span v-if="analysisScopeHint" class="isd-analysis-scope">{{ analysisScopeHint }}</span>
          </v-tooltip>
        </div>
        <div class="isd-props-scroll">

        <RetentionStatusBar v-if="isRetentionEnabled" :model-value="docRetention" :document-date-iso="docDateIso || ''"
          :allow-suggest="false" :saving="isCommitting" :menu-props="{ maxHeight: 240, attach: 'body', zIndex: 6000 }"
          @accept="onRetentionAccept" @save="saveImportRetention" />

        <v-select v-if="documents.length > 1" :model-value="primaryDocument?.id"
          :items="documents.map(doc => ({ title: doc.title || 'Ohne Namen', value: doc.id }))" label="Dokument bearbeiten"
          density="compact" variant="outlined" @update:model-value="selectDocumentForEditing" />
        <DocumentMetadataFields :name="primaryDocTitle" :date="docDate" :category="docCategory"
          :correspondent="docCorrespondentId" :note="docNote" :categories="categoryItems" :correspondents="correspondentItems"
          :errors="{ ...fieldErrors, name: fieldErrors.title }" :sources="metadataSources" :pending="pendingMetadataFields" required-fields :disabled="isCommitting || Boolean(stagingStore.pendingCommit) || correspondentDialogOpen"
          :proposals="metadataProposals" v-model:correspondent-search="correspondentSearch"
          @field-focus="metadataFocus.focus" @field-blur="metadataFocus.blur"
          @update:name="onPrimaryDocTitleInput({ target: { value: $event } })"
          @update:date="docDate = $event; docDateTouched = true; docDateAiFilled = false"
          @update:category="docCategory = $event; docCategoryTouched = true; docCategoryAiFilled = false"
          @update:correspondent="docCorrespondentId = $event; docCorrespondentTouched = true; docCorrespondentAiFilled = false"
          @update:note="docNote = $event; docNoteTouched = true; docNoteAiFilled = false"
          @text-blur="onPrimaryDocTitleBlur" @date-blur="normalizeImportDate"
          @date-keydown="handleShortcut($event, SHORTCUT_ACTIONS.PRIMARY, normalizeImportDate, { ignoreEditable: false })"
          @correspondent-focus="correspondentStore.ensureLoaded()">
          <template #source="{ field, label }">
            <ImportFieldSource :source="metadataSources[field]" :proposal="metadataProposals[field]" :label="label"
              :text="proposalText(field)" :create="field === 'correspondent' && proposalNeedsCorrespondent"
              :disabled="isCommitting || Boolean(stagingStore.pendingCommit)" @accept="acceptMetadataProposal(field)" @dismiss="dismissMetadataProposal(field)" />
          </template>
          <template #correspondent-empty><v-list-item title="Kein Korrespondent gefunden" /></template>
          <template #correspondent-append>
            <div @keydown.enter.stop><button v-if="canCreateCorrespondent" type="button" class="isd-create-correspondent"
              @click="openCorrespondentDialog(correspondentSearch)"><v-icon size="18">mdi-plus</v-icon><span>„{{ correspondentSearch.trim() }}“ anlegen</span></button></div>
          </template>
          <template #tags="{ inputId, required, error, errorId }">
            <TagInlineEditor :model-value="primaryDocTagNames" v-model:search="tagInlineValue"
              :input-id="inputId" :required="required" :error="error" :error-id="errorId"
              :items="allTagNamesForPool" :disabled="isCommitting" :loading="isCreatingTags" :add-label="pendingMetadataFields.tags ? 'Wird ermittelt…' : 'Tag'"
              @update:model-value="onTagNamesChange" @remove="onTagNamesChange(primaryDocTagNames.filter(name => name !== $event))"
              @keydown="onImportTagKeydown" @focus="ensureStageTagsLoaded()" />
          </template>
        </DocumentMetadataFields>
        </div>
      </div>
      </Transition>
    </div>

    <template #footer>
      <div class="isd-footer">
        <span v-if="!isEmptyLayout && footerValidationHint" class="isd-footer-hint isd-review-hint" role="status">{{ footerValidationHint }}</span>
        <div class="isd-footer-end">
          <ImportReadinessHelp v-if="!isEmptyLayout && importReadinessBlockers.length && !isCommitting && !stagingStore.pendingCommit" :blockers="importReadinessBlockers" @navigate="navigateToImportField" />
          <span v-if="isCommitting" class="isd-footer-status">
            Verarbeitung läuft…
          </span>
          <v-btn
            v-if="!isEmptyLayout && hasMultiSelection"
            variant="tonal"
            color="primary"
            :disabled="isSelectionImportDisabled"
            @click="commitSelectionImport"
          >
            Auswahl importieren ({{ multiSelectionCount }})
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            class="isd-import-btn"
            :disabled="isImportActionDisabled"
            @click="commitImport()"
          >
            {{ isCommitting ? 'Verarbeitung läuft…' : stagingStore.pendingCommit ? 'Importstatus prüfen' : 'Importieren' }}
          </v-btn>
        </div>
      </div>
    </template>
  </BaseDialog>

  <Teleport to="body">
    <div v-if="scannerPreviewFlight" class="isd-scan-flight-layer" aria-hidden="true">
      <div ref="scannerPreviewFlightElement" class="isd-scan-flight" :style="scannerPreviewFlight.style">
        <img :src="scannerPreviewFlight.url" alt="" draggable="false" />
      </div>
    </div>
  </Teleport>

  <ImportCorrespondentDialog v-model="correspondentDialogOpen" :initial-name="newCorrespondentName" @created="selectCreatedCorrespondent" />
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { authedUrl, authHeaders } from '../api/client.js';
import BaseDialog from './BaseDialog.vue';
import RetentionStatusBar from './RetentionStatusBar.vue';
import DocumentMetadataFields from './DocumentMetadataFields.vue';
import ImportFieldSource from './ImportFieldSource.vue';
import ImportReadinessHelp from './ImportReadinessHelp.vue';
import ImportCorrespondentDialog from './ImportCorrespondentDialog.vue';
import ImportPaneDivider from './ImportPaneDivider.vue';
import ImportScannerError from './ImportScannerError.vue';
import { useAvailableImportRemoval } from '../composables/useAvailableImportRemoval.js';
import { useImportFieldFocus } from '../composables/useImportFieldFocus.js';
import { usefulAnalysisNote, importAnalysisScope } from '../utils/importPresentation.js';
import DocumentPreviewIllustration from './DocumentPreviewIllustration.vue';
import PreviewToolbar from './PreviewToolbar.vue';
import { useContinuousPagePreview } from '../composables/useContinuousPagePreview.js';
import TagInlineEditor from './TagInlineEditor.vue';
import { useImportDocumentForm } from '../composables/useImportDocumentForm.js';
import { useScannerPreviewTransition } from '../composables/useScannerPreviewTransition.js';
import { canOfferTitle, meaningfulSuggestion, ensureImportForm, sourcePages, analysisRevision, pageDisplayRevision, validateImportDocument, applyFieldProposal, commitSubset } from '../utils/importWorkflow.js';
import { parseDocumentDateInput } from '../utils/dates.js';
import { apiFetch } from '../api/client.js';
import { useImportPdfRenderer } from '../composables/useImportPdfRenderer.js';
import { useImportPreviewImages } from '../composables/useImportPreviewImages.js';
import { createImportAnalysisQueue, abortableDelay } from '../utils/importAnalysisQueue.js';
import { setImportAnalysisState, importProcessState } from '../utils/importProcess.js';
import { createImportDiagnostics } from '../utils/importDiagnostics.js';
import { useImportCommit } from '../composables/useImportCommit.js';
import { useImportDraftPersistence } from '../composables/useImportDraftPersistence.js';
import { suggestImportStageTitle, readImportStageAnalysis } from '../api/importStaging';
import { analysisPending, acceptAnalysisSnapshot, transientAnalysisError } from '../utils/importAnalysis.js';
import { isIOS } from '../utils/platform';
import { mapApiError, useNotifications } from '../stores/notifications';
import { useImportStagingStore } from '../stores/importStaging';
import { useSettingsStore } from '../stores/settings';
import { useCategoryStore } from '../stores/categories';
import { useCorrespondentStore } from '../stores/correspondents';
import {
  SHORTCUT_ACTIONS,
  handleShortcut,
  isEditableShortcutTarget,
  useShortcutScope
} from '../keyboard/shortcuts';


const VOCAB_NAME_MIN_LENGTH = 2;
const VOCAB_NAME_MAX_LENGTH = 30;

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  apiBaseUrl: { type: String, default: '' },
  autoEmbed: { type: Boolean, default: true },
  scannerActive: { type: Boolean, default: false },
  scannerFeedbackState: {
    type: String,
    default: 'idle',
    validator: (value) => ['idle', 'scanning', 'pending'].includes(value)
  },
  // Auslösbarer Scanner des aktuellen Benutzers (oder null). Siehe ScannerTriggerInfo.
  scanner: { type: Object, default: null },
  scannerJobs: { type: Array, default: () => [] },
  scanRequestPending: { type: Boolean, default: false },
  scanCancelPending: { type: Boolean, default: false },
  availablePages: { type: Number, default: 0 },
  availablePagesLoading: { type: Boolean, default: false },
  availableItems: { type: Array, default: () => [] },
});

const emit = defineEmits(['update:modelValue', 'committed', 'discarded-sources', 'scan', 'open-document', 'open-available-pages', 'available-pages-removed']);
const sourceChoicesRequested = ref(false);

// Im Live-Modus erzeugt jede Seite sofort ein eigenes Dokument -> kein "Fertig".
// Im Batch-Modus sammelt der Scanner und braucht ein explizites Abschließen.
const availablePageCount = computed(() => stagingStore.availablePageCount
  + (sourceChoicesRequested.value && !stagingStore.pendingCommit ? stagingStore.activeScannerPageCount : 0)
  + (Number.isFinite(props.availablePages) ? Math.max(0, Math.floor(props.availablePages)) : 0));
const availablePagesLabel = computed(() => `${availablePageCount.value} verfügbare ${availablePageCount.value === 1 ? 'Seite öffnen' : 'Seiten öffnen'}`);
const availablePageBadgeLabel = computed(() => availablePageCount.value > 99 ? '99+' : String(availablePageCount.value));
const availableRemoveLabel = computed(() => `${availablePageCount.value} verfügbare ${availablePageCount.value === 1 ? 'Seite entfernen' : 'Seiten entfernen'}`);
const availablePagesSummary = computed(() => availablePageCount.value === 1 ? '1 Seite wartet auf den Import' : `${availablePageCount.value} Seiten warten auf den Import`);
const canTriggerScan = computed(() => Boolean(props.scanner?.id));
const isScannerFeedbackPending = computed(() => props.scannerFeedbackState === 'pending');
const scannerLivePreviewCandidateUrl = computed(() => {
  const raw = String(props.scanner?.live_preview_url || '').trim();
  return raw ? authedUrl(buildApiResourceUrl(raw)) : '';
});
let scanFrameSeen = false;
watch(() => props.scannerActive, active => { if (active) { scanFrameSeen = false; diagnostics.start('scan', 'scan_start'); } });
watch(scannerLivePreviewCandidateUrl, url => { if (url && !scanFrameSeen) { scanFrameSeen = true; diagnostics.end('scan', 'first_scan_frame'); } });
const ignoredScannerErrors = ref(new Set());
function scannerErrorKey(job) { return `${job.id}:${job.updated_at || job.created_at}:${job.error_kind}`; }
const scannerFailure = computed(() => {
  if (props.scannerActive || props.scanRequestPending || props.scanCancelPending
    || props.scannerJobs.some(job => ['queued', 'scanning', 'processing'].includes(job.state))) return null;
  const cutoff = Math.max(stagingStore.createdAt || 0, Date.now() - 300000);
  const errorTime = job => Date.parse(job.updated_at || job.created_at);
  const job = props.scannerJobs.filter(job => job.state === 'error' && job.error_kind !== 'cancelled'
    && errorTime(job) > cutoff && !ignoredScannerErrors.value.has(scannerErrorKey(job))
    && (!job.scanner_device_id || !props.scanner?.id || job.scanner_device_id === props.scanner.id))
    .sort((left, right) => errorTime(right) - errorTime(left))[0];
  if (!job) return null;
  return {
    timeout: { title: 'Zeitlimit überschritten', message: 'Der Scanner hat nicht rechtzeitig geantwortet.' },
    scanner_offline: { title: 'Scanner nicht erreichbar', message: 'Prüfe die Verbindung zum Scanner.' },
    file_missing: { title: 'Seite nicht verfügbar', message: 'Die gescannte Seite wurde nicht übertragen.' },
  }[job.error_kind] || { title: 'Scan fehlgeschlagen', message: 'Bitte prüfe den Scanner und versuche es erneut.' };
});
const scannerFeedbackVisible = computed(() => !scannerFailure.value
  && (props.scannerActive || props.scanRequestPending || props.scanCancelPending || scannerPreviewFinalizing.value));
const scannerFeedbackStatus = computed(() => (
  props.scanCancelPending ? 'Abbruch angefordert' : props.scanRequestPending ? 'Scan wird angefordert' :
    props.scannerJobs.some(job => job.state === 'queued') ? 'Scanner wartet auf den Auftrag' :
    scannerPreviewFinalizing.value || isScannerFeedbackPending.value ? 'Scan wird übernommen' : 'Seite wird gescannt'
));
const scannerFeedbackCardLabel = computed(() => (
  isScannerFeedbackPending.value ? 'Wird übernommen…' : 'Scanne…'
));
function emitScan(command) {
  if (!canTriggerScan.value || props.scanRequestPending || props.scanCancelPending || stagingStore.pendingCommit) {
    return;
  }
  if (command === 'page' || command === 'cancel') resetScannerPreview();
  if (command === 'page') {
    ignoredScannerErrors.value = new Set([...ignoredScannerErrors.value, ...props.scannerJobs.filter(job => job.state === 'error').map(scannerErrorKey)]);
    sourceChoicesRequested.value = false;
  }
  emit('scan', command);
}

const { notify } = useNotifications();
const stagingStore = useImportStagingStore();
const settingsStore = useSettingsStore();
const categoryStore = useCategoryStore();
const correspondentStore = useCorrespondentStore();
const { documents, documentCount, totalPages, emptyDocuments } = storeToRefs(stagingStore);
const draftPersistence = useImportDraftPersistence(stagingStore, {
  saved: fields => diagnostics.record('draft_saved', fields),
  restored: () => {
    if (!props.modelValue || sourceChoicesRequested.value) {
      void nextTick(() => parkClosedImport(true));
    } else {
      notify({ type: 'info', message: 'Dein offener Import wurde wiederhergestellt.' });
    }
  },
  failed: error => notify({ type: 'warning', message: error?.name === 'DraftConflictError'
    ? 'Dieser Import wurde in einem anderen Fenster geändert. Hier bleiben deine Eingaben erhalten; bitte im anderen Fenster fortfahren.'
    : 'Der Importentwurf konnte nicht lokal gesichert werden. Bitte dieses Fenster bis zum Import geöffnet lassen.' }),
});
const availableRemoval = useAvailableImportRemoval(stagingStore, {
  save: async () => { await draftPersistence.loaded; return draftPersistence.save(); },
  items: () => props.availableItems,
  finalized: payload => emit('available-pages-removed', payload),
});
const isRemovingAvailable = availableRemoval.busy;
const isAvailableRemovalBlocked = availableRemoval.blocked;
const canRemoveAvailable = computed(() => !isRemovingAvailable.value && !isUploadingSources.value
  && !isCommitting.value && !stagingStore.pendingCommit && !props.availablePagesLoading && !isAvailableRemovalBlocked.value && !stagingStore.availableDraft?.pendingCommit);
const availableRemovalTooltip = computed(() => isAvailableRemovalBlocked.value
  ? 'Seiten können erst nach erfolgreicher Entwurfssicherung entfernt werden.'
  : stagingStore.availableDraft?.pendingCommit ? 'Bitte zuerst den Importstatus prüfen.' : availableRemoveLabel.value);


const isDropzoneDragOver = ref(false);
const dropDragDepth = ref(0);
const documentDragDepth = ref({});
const isBodyFileDragOver = ref(false);
const bodyFileDragDepth = ref(0);
const isAddPageDragOver = ref(false);
const addPageDragDepth = ref(0);
const addSourceChooserOpen = ref(false);
const selected = ref(null);
const activeDocumentId = ref('');
const primaryDocument = computed(() => documents.value.find(doc => doc.id === (selected.value?.stageId || activeDocumentId.value)) || documents.value[0] || null);
const peek = ref({ open: false, x: 0, y: 0 });
const isUploadingSources = ref(false);
const remoteSourceLoads = ref(0);
const isCommitting = ref(false);
const preparationProgress = ref({ done: 0, total: 0 });
const sourceRefreshCount = ref(0);
const remoteSourceStageBySession = new Map();
const analysisQueue = createImportAnalysisQueue();
const titleSuggestJobByStage = analysisQueue.jobs;
const diagnostics = createImportDiagnostics();
let analysisDisposed = false;
const importTimingBySource = new Map();


// Scanner-Seiten werden nach dem sichtbaren Import erst bereinigt und dann im
// Worker analysiert. Auf dem Pi darf diese Warteschlange mehrere Minuten
// dauern; die UI pollt daher den Worker-Cache, statt voreilig rot zu melden.

const previewImageSrc = ref('');
const previewImageLoading = ref(false);
const previewIsThumbnail = ref(false);
let previewImages = null;
const stageTagPool = ref([]);
const fileInput = ref(null);
const peekPanelRef = ref(null);
const peekAnchorEl = ref(null);
const bodyScrollRef = ref(null);
const docsListRef = ref(null);
const titleInputRefs = new Map();

const pageThumbRefs = new Map();
const pdfRenderer = useImportPdfRenderer(() => stagingStore.stagingFiles);
const { renderPdfThumbnails, renderLargePreview, thumbnailQuality } = pdfRenderer;
const lazyThumbnailJobs = new Set();
let thumbnailRenderChain = Promise.resolve();
let thumbnailObserver = null;
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
let closeParkTimer = 0;
let viewSwitchTimer = 0;
const autoScrollState = {
  container: null,
  dx: 0,
  dy: 0
};
const isViewSwitching = ref(false);

const { docDate, docCategory, docNote, docCorrespondentId, docRetention,
  docTitleTouched, docDateTouched, docCategoryTouched, docTagsTouched, docNoteTouched, docCorrespondentTouched,
  docRetentionTouched, docTitleAiFilled, docDateAiFilled, docCategoryAiFilled, docTagsAiFilled,
  docNoteAiFilled, docCorrespondentAiFilled, importForm } = useImportDocumentForm(primaryDocument);
const metadataFocus = useImportFieldFocus(primaryDocument);
const detailsPaneWidth = ref(360);
const detailsPaneId = `import-details-${useId()}`;
const correspondentSearch = ref('');
const correspondentDialogOpen = ref(false);
const newCorrespondentName = ref('');
let correspondentTarget = null;
const canCreateCorrespondent = computed(() => {
  const name = correspondentSearch.value.replace(/\s+/gu, ' ').trim();
  return name.length >= 2 && name.length <= 120 && !correspondentStore.findByName(name) && !isCommitting.value && !stagingStore.pendingCommit;
});
const metadataProposals = computed(() => {
  const doc = primaryDocument.value;
  if (!doc) return {};
  const proposals = {};
  for (const [key, proposal] of Object.entries(ensureImportForm(doc).proposals)) {
    if (!['title', 'date', 'category', 'correspondent', 'tags', 'note'].includes(key)) continue;
    if (key === 'category' && validateTagName(String(proposal.value || ''))) continue;
    if (key === 'note' && !usefulAnalysisNote(proposal.value, doc.meta.titleSuggestionMeta)) continue;
    proposals[key === 'title' ? 'name' : key] = proposal;
  }
  if (!proposals.name && canOfferTitle(doc)) proposals.name = { value:doc.meta.titleSuggestion, origin:'KI' };
  return proposals;
});
const proposalNeedsCorrespondent = computed(() => {
  const value = normalizeCorrespondentInput(metadataProposals.value.correspondent?.value);
  return Boolean(value && !correspondentStore.findById(value) && !correspondentStore.findByName(value));
});
function proposalText(field) {
  const value = metadataProposals.value[field]?.value;
  if (field === 'correspondent') return correspondentStore.findById(normalizeCorrespondentInput(value))?.name || String(value || '');
  return Array.isArray(value) ? value.join(', ') : String(value || '');
}
function writeChosenMetadata(doc, field, value, origin) {
  const form = ensureImportForm(doc);
  if (field === 'title') stagingStore.setDocumentTitleDraft(doc.id, String(value).trim().slice(0, 200));
  else if (field === 'tags') {
    const names = value.map(name => normalizeTagName(name)).filter(name => name && !validateTagName(name));
    stagingStore.setDocumentTags(doc.id, names.map(findStageTagIdByName).filter(Boolean));
    doc.meta.pendingTagNames = names.filter(name => !findStageTagIdByName(name));
  } else form[({ correspondent:'correspondentId' })[field] || field] = value;
  form.touched[field] = true;
  form.revisions[field] = (form.revisions[field] || 0) + 1;
  form.aiFilled[field] = origin || false;
  delete form.proposals[field];
}
function acceptMetadataProposal(field) {
  const doc = primaryDocument.value;
  const proposal = metadataProposals.value[field];
  if (!doc || !proposal || isCommitting.value || stagingStore.pendingCommit) return;
  if (field === 'correspondent') {
    const value = normalizeCorrespondentInput(proposal.value);
    const correspondent = correspondentStore.findById(value) || correspondentStore.findByName(value);
    if (!correspondent) { openCorrespondentDialog(value, proposal.origin); return; }
    writeChosenMetadata(doc, field, correspondent.id, proposal.origin);
  } else writeChosenMetadata(doc, field === 'name' ? 'title' : field, proposal.value, proposal.origin);
}
function dismissMetadataProposal(field) {
  const doc = primaryDocument.value;
  const proposal = metadataProposals.value[field];
  if (!doc || !proposal) return;
  const key = field === 'name' ? 'title' : field;
  const form = ensureImportForm(doc);
  form.dismissed[key] = proposal.value;
  delete form.proposals[key];
  if (key === 'title') doc.meta.dismissedTitle = proposal.value;
}
function openCorrespondentDialog(name, origin = null) {
  if (!primaryDocument.value || isCommitting.value || stagingStore.pendingCommit) return;
  correspondentTarget = { id:primaryDocument.value.id, origin };
  newCorrespondentName.value = String(name || '').replace(/\s+/gu, ' ').trim();
  correspondentDialogOpen.value = true;
}
function selectCreatedCorrespondent(id) {
  const doc = getDocumentById(correspondentTarget?.id);
  if (doc) writeChosenMetadata(doc, 'correspondent', id, correspondentTarget.origin);
  correspondentSearch.value = '';
  correspondentTarget = null;
  void nextTick(() => document.querySelector('.isd-props [data-field="correspondent"] input')?.focus());
}
const validationAttempted = ref(false);
const fieldErrors = computed(() => {
  if (!primaryDocument.value) return {};
  // Leere Felder blockieren den Import, erhalten aber keine rote Fehlermeldung.
  const result = validateImportDocument(primaryDocument.value, { requireComplete: false });
  return Object.fromEntries(Object.entries(result).filter(([key]) => validationAttempted.value || importForm.value.touched[key]));
});
const metadataSources = computed(() => Object.fromEntries(Object.entries(importForm.value.aiFilled)
  .filter(([, value]) => value).map(([key, value]) => [
    ({ title: 'name', correspondent: 'correspondent', category: 'category' })[key] || key,
    value,
  ])));
const retentionExpanded = ref(false);
const isRetentionEnabled = computed(() => settingsStore.settings?.retention?.enabled !== false);
const aiFieldGlowActive = ref(false);
const isRetryingAnalysis = ref(false);
let aiFieldGlowTimer = 0;

// Auswählbare Dokumenttypen aus der zentral verwalteten Liste (Einstellungen).
// Ein bereits gesetzter / KI-vorgeschlagener Wert, der (noch) nicht im
// Vokabular steht, wird trotzdem als Option ergänzt, damit er sichtbar bleibt.
const categoryItems = computed(() => {
  const names = [...categoryStore.categoryNames];
  const current = docCategory.value;
  if (current && !names.includes(current)) {
    names.unshift(current);
  }
  return names;
});

// Korrespondenten-Optionen für die Combobox ({ title, value }).
const correspondentItems = computed(() => correspondentStore.correspondentOptions);


function normalizeCorrespondentInput(value) {
  if (value && typeof value === 'object') {
    return String(value.value || value.id || value.title || value.name || '').replace(/\s+/g, ' ').trim();
  }
  return String(value || '').replace(/\s+/g, ' ').trim();
}

// Ein Korrespondenten-Wert ist „noch nicht angelegt", wenn er weder einer bekannten
// ID noch einem bekannten Namen entspricht (→ gestrichelter Chip, Anlage beim Import).


const docDateIso = computed(() => parseDocumentDateInput(docDate.value).iso);


// Ablaufdatum lokal aus Dokumentdatum + Frist (Backend rechnet es beim Commit final neu).
function computeRetainUntilIso(periodYears) {
  const iso = docDateIso.value;
  if (!iso || periodYears === null || periodYears === undefined || Number(periodYears) === -1) return null;
  const years = Number(periodYears);
  if (!Number.isFinite(years) || years <= 0) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
  if (!match) return null;
  const [, y, m, d] = match.map(Number);
  const target = new Date(y + years, m - 1, d);
  if (target.getMonth() !== m - 1) target.setDate(0);
  const mm = String(target.getMonth() + 1).padStart(2, '0');
  const dd = String(target.getDate()).padStart(2, '0');
  return `${target.getFullYear()}-${mm}-${dd}`;
}

function onRetentionAccept() {
  if (!docRetention.value) return;
  docRetention.value = { ...docRetention.value, status: 'accepted' };
  docRetentionTouched.value = true;
}

// Kompakte Zusammenfassung für den eingeklappten Zustand.


// Ablaufdatum-Vorschau (dd.mm.yyyy) aus Dokumentdatum + Frist.


// Ändert sich das Dokumentdatum, die Ablaufdatum-Vorschau mitziehen.
watch(docDateIso, () => {
  if (!docRetention.value) return;
  const next = computeRetainUntilIso(docRetention.value.period_years);
  if (next !== docRetention.value.retain_until) {
    docRetention.value = { ...docRetention.value, retain_until: next };
  }
});


const tagInlineValue = ref('');
const isCreatingTags = ref(false);

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

const isIOSDevice = computed(() => isIOS());
const isEmpty = computed(() => documentCount.value === 0 && totalPages.value === 0);
// Die zuletzt sichtbare Anordnung bleibt während der Schließanimation erhalten,
// auch wenn gespeicherte oder abgelegte Seiten bereits aus dem aktiven Entwurf entfallen.
const isEmptyLayout = ref(isEmpty.value);
watch([() => props.modelValue, isEmpty, sourceChoicesRequested], ([open, empty, sourceChoices]) => {
  if (open) isEmptyLayout.value = empty || sourceChoices;
});
const dropzoneSubtitle = computed(() => {
  if (isDropzoneDragOver.value) return 'Die neuen Seiten werden gleich für die Vorschau vorbereitet';
  if (canTriggerScan.value) return 'PDFs hier ablegen oder direkt vom Scanner übernehmen';
  return 'PDFs hier ablegen';
});

function importTimingNow() {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

function importTimingDateMs(value) {
  const parsed = Date.parse(String(value || ''));
  return Number.isFinite(parsed) ? parsed : null;
}

function getImportTimingState(sourceFileId) {
  const normalized = String(sourceFileId || '').trim();
  if (!normalized) {
    return null;
  }
  if (!importTimingBySource.has(normalized)) {
    importTimingBySource.set(normalized, {});
  }
  return importTimingBySource.get(normalized);
}

function msSinceImportSourceSeen(sourceFileId) {
  const state = getImportTimingState(sourceFileId);
  if (!state?.seenAt) {
    return null;
  }
  return Math.round((importTimingNow() - state.seenAt) * 10) / 10;
}

function logImportTiming(event, fields = {}) {
  const name = { dialog_source_seen: 'source_received', preview_visible: 'preview_render' }[event];
  if (name) diagnostics.record(name, { pages: Number(fields.page_count || 0), network_ms: fields.server_created_to_dialog_ms, browser_ms: fields.ms_since_dialog_source_seen });
}

function rememberImportSourceTiming(source) {
  const sourceFileId = String(source?.source_file_id || '').trim();
  const state = getImportTimingState(sourceFileId);
  if (!state) {
    return;
  }
  if (!state.seenAt) {
    state.seenAt = importTimingNow();
    const createdAtMs = importTimingDateMs(source?.created_at);
    state.createdAtMs = createdAtMs;
    logImportTiming('dialog_source_seen', {
      source_file_id: sourceFileId,
      source_type: String(source?.source_type || ''),
      page_count: Number(source?.page_count || 0),
      server_created_to_dialog_ms: createdAtMs == null ? null : Math.max(0, Date.now() - createdAtMs)
    });
  }
}

function logPreviewVisibleTiming(sourceFileId, { fast = false, pageCount = 0, stageId = '' } = {}) {
  nextTick(() => {
    logImportTiming('preview_visible', {
      source_file_id: sourceFileId,
      stage_id: stageId,
      fast_preview: Boolean(fast),
      page_count: Number(pageCount || 0),
      ms_since_dialog_source_seen: msSinceImportSourceSeen(sourceFileId)
    });
  });
}

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
  // Noch nicht angelegte ("neue") Tag-Namen für dieses Dokument. Sie werden im
  // Dialog gestrichelt dargestellt und erst beim Import real angelegt.
  if (!Array.isArray(documentEntry.meta.pendingTagNames)) {
    documentEntry.meta.pendingTagNames = [];
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
  if (typeof documentEntry.meta.appliedImportAnalysisKey !== 'string') {
    documentEntry.meta.appliedImportAnalysisKey = '';
  }
  return documentEntry.meta;
}

function isDefaultScanTitle(title) {
  return String(title || '').trim() === 'Neuer Scan';
}


function isScanTitleBusy(documentEntry) {
  const status = String(documentEntry?.meta?.titleSuggestionStatus || '');
  if (status === 'working') return true;
  if (status === 'pending_ocr') return !Boolean(documentEntry?.meta?.titleSuggestionPollExhausted);
  return false;
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
const MODAL_WORK_WIDTH_SPLIT = 1200;


const primaryDocTitle = computed(() => primaryDocument.value?.title || '');


const primaryDocTags = computed(() => {
  if (!primaryDocument.value) return [];
  return (primaryDocument.value.tags || [])
    .map(id => stageTagPool.value.find(t => t.id === id) || { id, name: id });
});

const primaryDocPendingTagNames = computed(() =>
  Array.isArray(primaryDocument.value?.meta?.pendingTagNames)
    ? primaryDocument.value.meta.pendingTagNames
    : []
);
// Bestehende Tags zuerst, danach die noch nicht angelegten ("neuen") Namen.
const primaryDocTagNames = computed(() => [
  ...primaryDocTags.value.map(t => t.name),
  ...primaryDocPendingTagNames.value
]);
const allTagNamesForPool = computed(() => {
  const query = tagInlineValue.value.trim().toLocaleLowerCase('de-DE');
  const selectedNames = new Set(primaryDocTagNames.value.map(name => name.toLocaleLowerCase('de-DE')));
  return stageTagPool.value.map(tag => tag.name).filter(name => !selectedNames.has(name.toLocaleLowerCase('de-DE')) && (!query || name.toLocaleLowerCase('de-DE').includes(query))).slice(0, 12);
});

// Ein Tag-Name ist "neu", wenn dazu (noch) kein bestehendes Tag existiert –
// er würde beim Import erst angelegt. Solche Chips werden gestrichelt dargestellt.

const hasAnySelectedPage = computed(() => Boolean(selected.value?.pageId));
// Der Farbmodus gilt für den gesamten Import, unabhängig von der Seitenauswahl.
const pageToolsDisabled = computed(() => !hasSelectedPreview.value || isCommitting.value || Boolean(stagingStore.pendingCommit));
const colorToolsDisabled = computed(() => totalPages.value === 0 || isCommitting.value || Boolean(stagingStore.pendingCommit));
const pageColorOptions = [
  { value: 'color', title: 'Originalfarbe des Scans', icon: 'mdi-image-outline' },
  { value: 'grayscale', title: 'Graustufen', icon: 'mdi-circle-half-full' },
  { value: 'auto', title: 'Automatische Scanbereinigung beibehalten', icon: 'mdi-palette-outline' },
];
function pageColorFilter(mode) {
  return mode === 'grayscale' ? 'grayscale(1)' : mode === 'bw' ? 'grayscale(1) contrast(4)' : undefined;
}
const thumbnailSizes = ref(new Map());
function rememberThumbnailSize(image) {
  const url = image?.getAttribute('src');
  const width = image?.naturalWidth;
  const height = image?.naturalHeight;
  if (!url || !width || !height) return;
  const previous = thumbnailSizes.value.get(url);
  if (previous?.width !== width || previous?.height !== height) thumbnailSizes.value.set(url, { width, height });
}
function thumbnailRotation(page) {
  return ((Number(page?.rotation || 0) % 360) + 360) % 360;
}
function pageThumbnailImageStyle(page) {
  const rotation = thumbnailRotation(page);
  const { width, height } = pageThumbnailSize(page);
  const quarterTurn = [90, 270].includes(rotation);
  return {
    transform: rotation ? `rotate(${rotation}deg)` : undefined,
    filter: pageColorFilter(page.colorMode),
    width: quarterTurn ? `${(width / height) * 100}%` : undefined,
    height: quarterTurn ? `${(height / width) * 100}%` : undefined,
  };
}
function autoCropForPage(page) {
  const sourceFileId = String(page?.sourceFileId || '').trim();
  const pageIndex = Number(page?.pageIndex);
  const pages = stagingStore.sourceMetaById?.get?.(sourceFileId)?.scanCleanup?.auto_crop?.pages;
  if (!Array.isArray(pages) || !Number.isInteger(pageIndex)) {
    return null;
  }
  return pages.find(result => Number(result?.page_index) === pageIndex) || null;
}
function pageThumbnailSize(page) {
  const fallback = scannerThumbnailFallback.value;
  const loaded = thumbnailSizes.value.get(page.thumbUrl)
    || (fallback && fallback.pageId === page.id && thumbnailSizes.value.get(fallback.url));
  if (loaded) return loaded;
  const crop = autoCropForPage(page);
  const size = crop?.cropped_size_pixels;
  if (!crop?.applied || !Array.isArray(size) || size.length !== 2) {
    return { width: 3, height: 4 };
  }
  const width = Number(size[0]);
  const height = Number(size[1]);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { width: 3, height: 4 };
  }
  return { width, height };
}
function pageThumbnailFormatStyle(page) {
  let { width, height } = pageThumbnailSize(page);
  if ([90, 270].includes(thumbnailRotation(page))) {
    [width, height] = [height, width];
  }
  return { aspectRatio: `${width} / ${height}` };
}
// Die KI-Analyse gilt als abgeschlossen, sobald nichts mehr vorbereitet wird
// und der Analyse-Status nicht mehr "busy" (läuft) ist. Ein fehlgeschlagener
// Lauf zählt ebenfalls als abgeschlossen – die Felder lassen sich dann manuell
// befüllen.


// Notizen sind optional; alle übrigen Metadaten werden vor dem Import geprüft.
const areRequiredFieldsFilled = computed(() => documents.value.every(doc => Object.keys(validateImportDocument(doc)).length === 0));
const importReadinessBlockers = computed(() => documents.value.map(doc => {
  const errors = validateImportDocument(doc);
  const invalid = validateImportDocument(doc, { requireComplete:false });
  const labels = { title:'Dokumentname', date:'Dokumentdatum', category:'Dokumenttyp', correspondent:'Korrespondent', tags:'Tags', note:'Notizen', pages:'Seiten' };
  return { id:doc.id, title:doc.title, fields:Object.keys(errors).map(key => ({ key, label:labels[key], invalid:Boolean(invalid[key]) })) };
}).filter(item => item.fields.length));
async function navigateToImportField({ id, field }) {
  const doc = getDocumentById(id);
  if (!doc) return;
  activeDocumentId.value = id;
  const entry = allPagesFlat.value.find(item => item.doc.id === id);
  if (entry) selectPage(id, entry.page.id, entry.globalIndex);
  await nextTick();
  if (field === 'pages') { openFilePicker(); return; }
  const row = document.querySelector(`.isd-props [data-field="${field === 'title' ? 'name' : field}"]`);
  row?.scrollIntoView({ block:'nearest' });
  row?.querySelector('input:not([type="hidden"]), textarea')?.focus({ preventScroll:true });
}
const footerValidationHint = computed(() => {
  if (validationAttempted.value && Object.keys(fieldErrors.value).length) return 'Bitte die markierten Eingaben korrigieren.';
  return '';
});
const processState = computed(() => importProcessState({
  committing: isCommitting.value, scanning: props.scannerActive, cleanup: isScanCleanupRunning.value,
  uploading: isUploadingSources.value, refreshing: sourceRefreshCount.value > 0, pages: totalPages.value,
  analysis: primaryDocument.value?.meta?.analysisState, lookup: primaryDocument.value?.meta?.analysisLookupPending, conflict: draftPersistence.conflict.value,
}));
const isImportActionBusy = computed(() => processState.value.blocksCommit);
// Ein ausstehender Import wird mit seinem bereits geprüften, gespeicherten
// Request wiederholt. Für neue Importe müssen die aktuellen Felder gültig sein.
const isImportActionDisabled = computed(() => isImportActionBusy.value || (!stagingStore.pendingCommit && (isEmptyLayout.value || !areRequiredFieldsFilled.value)));

/* ── Multi-Selektion ── */
const multiSelectedPageIds = ref(new Set());
const hasMultiSelection = computed(() => multiSelectedPageIds.value.size > 0);
const multiSelectionCount = computed(() => multiSelectedPageIds.value.size);
const isSelectionImportDisabled = computed(() => {
  if (isImportActionBusy.value || !hasMultiSelection.value) return true;
  if (stagingStore.pendingCommit) return false;
  const entries = commitSubset(documents.value, multiSelectedPageIds.value);
  return !entries.length || entries.some(({ document, pages }) => Object.keys(validateImportDocument({ ...document, pages })).length > 0);
});
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


function toggleSelectMode() {
  isSelectMode.value = !isSelectMode.value;
  if (!isSelectMode.value) {
    clearMultiSelection();
  }
}

function selectDocumentForEditing(documentId) {
  activeDocumentId.value = documentId;
  clearMultiSelection();
  const firstPage = allPagesFlat.value.find(({ doc }) => doc.id === documentId);
  if (firstPage) selectPage(documentId, firstPage.page.id, firstPage.globalIndex);
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
    selectPage(doc.id, page.id, globalIndex);
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

function onMiniatureAreaClick(event) {
  if (isUploadingSources.value || isCommitting.value) {
    return;
  }
  // WICHTIG: nicht target.closest() verwenden. Ein Klick auf die Add-Karte
  // öffnet den Wähler und ersetzt dabei per v-if das geklickte Element noch
  // während der Ereignisausbreitung – target wäre dann losgelöst und closest()
  // liefert null, sodass dieser Handler den Klick fälschlich als „ins Leere"
  // wertet und sofort wieder zumacht. Der beim Auslösen erfasste composedPath()
  // bleibt dagegen gültig.
  const path = typeof event?.composedPath === 'function' ? event.composedPath() : [];
  const interactiveSelector =
    '.isd-page-card, .isd-add-page-card, .isd-scanning-page-card, button, input, textarea, select, a, [role="button"]';
  const hitInteractive = path.some(
    (node) => node instanceof Element && node.matches?.(interactiveSelector)
  );
  if (hitInteractive) {
    return;
  }
  // Ein Klick ins Leere klappt auch den PDF/Scan-Wähler wieder zu – dieselbe
  // Geste wie das Aufheben der Seitenauswahl. Bewusst vor der Auswahl-Prüfung
  // und ohne isEmpty-Abbruch: die Add-Karte ist auch im Leerzustand sichtbar,
  // dort gibt es aber keine Auswahl, die aufzuheben wäre.
  addSourceChooserOpen.value = false;
  if (!selected.value?.pageId && multiSelectedPageIds.value.size === 0) {
    return;
  }
  clearActiveSelection();
}

async function commitSelectionImport() {
  if (isSelectionImportDisabled.value) return;
  await commitImport(new Set(multiSelectedPageIds.value));
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
const {
  previewUrl: scannerLivePreviewUrl, progress: scannerLiveProgress,
  finalizing: scannerPreviewFinalizing, sourceElement: scannerPreviewSourceElement,
  flightElement: scannerPreviewFlightElement, flight: scannerPreviewFlight,
  thumbnailFallback: scannerThumbnailFallback, thumbnailLoaded: onScannerThumbnailLoaded,
  previewFallback: scannerPreviewFallback, previewLoaded: onScannerPreviewLoaded,
  reset: resetScannerPreview,
} = useScannerPreviewTransition({
  scanner: () => props.scanner, active: () => props.scannerActive,
  candidateUrl: scannerLivePreviewCandidateUrl, open: () => props.modelValue, empty: isEmpty,
  firstPage: () => allPagesFlat.value[0]?.page,
  acceptsPage: page => stagingStore.sourceMetaById.get(page.sourceFileId)?.sourceType === 'scanner',
  getThumbnail: pageId => pageThumbRefs.get(pageId)?.querySelector('.isd-page-thumb-wrap'),
  getPreview: pageId => selectedPageEntry.value?.id === pageId ? previewImageElement.value : null,
  isPreviewReady: pageId => selectedPageEntry.value?.id === pageId && !previewIsThumbnail.value,
  animationsEnabled: () => settingsStore.animationsEnabled,
});
const {
  viewport: previewViewport, image: previewImageElement, scrolling: previewScrolling, adjusting: previewAdjusting,
  zoom: previewZoom, zoomPercent: previewZoomPercent, canZoomIn: canPreviewZoomIn, canZoomOut: canPreviewZoomOut,
  canvasStyle: previewCanvasStyle, pageStyle: previewPageStyle, imageStyle: previewImageStyle, shouldLoad: shouldLoadPreview,
  setPageElement: setPreviewPageElement, setImageElement: setPreviewImageElement, onImageLoad: onPreviewImageLoad,
  onScroll: onPreviewScroll, onScrollEnd: onPreviewScrollEnd, scrollToPage: scrollPreviewToPage,
  resetZoom: resetPreviewZoom, zoomIn: zoomPreviewIn, zoomOut: zoomPreviewOut, onWheel: onPreviewWheel, onKeydown: onPreviewKeydown,
  magnifierEnabled: previewMagnifierEnabled, magnifier: previewMagnifier, magnifierStyle: previewMagnifierStyle,
  hideMagnifier: hidePreviewMagnifier, toggleMagnifier: togglePreviewMagnifier, onPointerMove: onPreviewPointerMove,
} = useContinuousPagePreview({ pages: () => allPagesFlat.value.map(({ page }) => page), pageId: () => selectedPageEntry.value?.id,
  source: pagePreviewSource, thumbnail: pagePreviewIsThumbnail, size: pagePreviewSize, onVisiblePage: onPreviewVisiblePage });
watch(
  () => [...allPagesFlat.value.map(({ page }) => page.thumbUrl), scannerThumbnailFallback.value?.url, scannerLivePreviewUrl.value],
  urls => {
    const used = new Set(urls);
    for (const url of thumbnailSizes.value.keys()) if (!used.has(url)) thumbnailSizes.value.delete(url);
  }
);
const preparationProgressLabel = computed(() => {
  const total = Math.max(0, Number(preparationProgress.value.total || 0));
  const done = Math.max(0, Number(preparationProgress.value.done || 0));
  if (total <= 0) {
    return '';
  }
  return `Vorbereiten: ${Math.min(done, total)}/${total}`;
});
previewImages = useImportPreviewImages({ store: stagingStore, allPagesFlat, selectedPageEntry,
  scannerPreviewFallback, previewScrolling, previewImageSrc, previewImageLoading, previewIsThumbnail,
  thumbnailSizes, pageThumbnailSize, thumbnailRotation, renderServerColorPreview, renderLargePreview,
  hidePreviewMagnifier, diagnostics, sourceElapsed: msSinceImportSourceSeen });

/* ── Dokumentweiter KI-Analyse-Status für den Formularheader ──
 * Spiegelt den titleSuggestionStatus des primären Dokuments auf vier UI-Zustände:
 *   busy     – Analyse läuft
 *   success  – fertig, mindestens ein Feld automatisch befüllt
 *   partial  – fertig, aber keine Felder ergänzt
 *   failed   – Analyse fehlgeschlagen/abgebrochen (Retry anbieten)
 *   idle     – noch keine Analyse
 */
// Läuft für irgendeine noch offene Scan-Quelle die Seitenverbesserung? Bewusst
// dialogweit statt pro Seite: der Status lebt einzig im Formularheader, ein
// zusätzlicher Spinner pro Thumbnail wäre unruhig.
const isScanCleanupRunning = computed(() => {
  const metaMap = stagingStore.sourceMetaById;
  if (!metaMap || typeof metaMap.values !== 'function') {
    return false;
  }
  for (const meta of metaMap.values()) {
    const status = String(meta?.scanCleanup?.status || '');
    if (status === 'pending' || status === 'running') {
      return true;
    }
  }
  return false;
});

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
  if (docCategoryAiFilled.value) fields.push('Dokumenttyp');
  if (docCorrespondentAiFilled.value) fields.push('Korrespondent');
  if (docTagsAiFilled.value) fields.push('Tags');
  if (docNoteAiFilled.value) fields.push('Notiz');

  if (status === 'working' || (status === 'pending_ocr' && !exhausted)) {
    return { kind: 'busy', fields: [] };
  }
  if (status === 'error') {
    return { kind: fields.length ? 'partial' : 'failed', fields };
  }
  if (status === 'interrupted') {
    return { kind: 'interrupted', fields };
  }
  if (status === 'pending_ocr' && exhausted) {
    return { kind: 'partial', fields: [] };
  }
  if (status === 'ready' || status === 'applied') {
    if (doc.meta?.titleSuggestionMeta?.refinement_failed) return { kind: 'partial', fields };
    return { kind: fields.length ? 'success' : 'partial', fields };
  }
  return { kind: 'idle', fields: [] };
});

// Vereint Seitenverbesserung und KI-Analyse im Formularheader.
// Priorität: erst wird der Scan bereinigt, dann analysiert die KI – nie beides
// als getrennter Spinner.
const prepStatus = computed(() => {
  const phase = processState.value.phase;
  if (phase === 'scanning') {
    return { busy: true, label: 'Scan läuft', description: 'Der Scanner erfasst weitere Seiten für den Import.', kind: 'busy' };
  }
  if (phase === 'cleanup') {
    return { busy: true, label: 'Scan wird verbessert', description: 'Die Scan-Seiten werden noch verbessert. Der Import ist verfügbar, sobald die Vorbereitung abgeschlossen ist.', kind: 'busy' };
  }
  if (phase === 'refreshing') {
    return { busy: true, label: 'Vorschau wird geladen', description: 'Die aktualisierten Seiten werden für die Vorschau vorbereitet.', kind: 'busy' };
  }
  if (phase === 'uploading') {
    return { busy: true, label: preparationProgressLabel.value || 'Dateien werden vorbereitet', description: 'Die Seiten werden für die Vorschau und den Import vorbereitet.', kind: 'busy' };
  }
  if (isRetryingAnalysis.value || aiAnalysis.value.kind === 'busy') {
    const meta = primaryDocument.value?.meta || {};
    const label = meta.analysisReconnecting ? 'Status wird aktualisiert' : ({ queued: 'Wartet auf Erkennung', ocr: 'Text wird erkannt', llm: 'KI analysiert Dokument' })[meta.analysisPhase] || 'KI analysiert Dokument';
    const description = meta.analysisReconnecting ? 'Die Verbindung wird erneut geprüft. Bereits erkannte Angaben bleiben erhalten.'
      : meta.analysisSlow ? 'Die Erkennung dauert etwas länger und läuft im Hintergrund weiter. Du kannst die Formularfelder bereits bearbeiten.'
        : 'Verfügbare Angaben erscheinen nach und nach. Du kannst die Formularfelder bereits bearbeiten.';
    return { busy: true, label, description, kind: 'busy' };
  }
  if (primaryDocument.value?.meta?.analysisLookupPending) {
    return { busy: true, label: 'Absender wird zugeordnet', description: 'Die erkannten Angaben sind bereits verfügbar. Der passende Korrespondent wird noch zugeordnet.', kind: 'busy', lookupOnly: true };
  }
  return { busy: false, label: '', kind: aiAnalysis.value.kind };
});
const preparationHintOpen = ref(false);
watch(() => [prepStatus.value.busy, props.modelValue, primaryDocument.value?.id], ([busy, open, id], previous) => {
  if (!busy || !open || id !== previous?.[2]) preparationHintOpen.value = false;
});
const analysisTouchInput = ref(false);
let analysisInputMedia;
function updateAnalysisTouchInput() { analysisTouchInput.value = Boolean(analysisInputMedia?.matches); }
function onAnalysisHintKeydown(event) {
  if (event.key !== 'Escape' || !preparationHintOpen.value || !props.modelValue) return;
  preparationHintOpen.value = false;
  event.preventDefault();
  event.stopImmediatePropagation();
}
onMounted(() => {
  analysisInputMedia = window.matchMedia('(hover: none), (pointer: coarse)');
  updateAnalysisTouchInput();
  analysisInputMedia.addEventListener('change', updateAnalysisTouchInput);
  window.addEventListener('keydown', onAnalysisHintKeydown, true);
});
onBeforeUnmount(() => {
  analysisInputMedia?.removeEventListener('change', updateAnalysisTouchInput);
  window.removeEventListener('keydown', onAnalysisHintKeydown, true);
});
const pendingMetadataFields = computed(() => {
  if (!prepStatus.value.busy) return {};
  const form = importForm.value;
  const values = { name: primaryDocTitle.value, date: form.date, category: form.category,
    correspondent: form.correspondentId, note: form.note, tags: primaryDocTagNames.value.length };
  return Object.fromEntries(Object.entries(values).map(([field, value]) => [field,
    !value && !form.touched[field === 'name' ? 'title' : field] && (!prepStatus.value.lookupOnly || field === 'correspondent')]));
});

const aiStatusTitle = computed(() => {
  const kind = aiAnalysis.value.kind;
  if (kind === 'interrupted') {
    return 'Der aktuelle Status ist nicht verfügbar — Klicken, um vorhandene Ergebnisse erneut abzufragen';
  }
  if (kind === 'success') {
    return `Ergänzte Angaben: ${aiAnalysis.value.fields.join(', ')} — Klicken, um die Analyse erneut zu starten`;
  }
  if (kind === 'partial') {
    if (aiAnalysis.value.fields.length) return `Teilweise erkannt: ${aiAnalysis.value.fields.join(', ')} — Klicken, um die Analyse erneut zu starten`;
    if (String(primaryDocument.value?.meta?.titleSuggestionStatus || '') === 'pending_ocr') {
      return 'Analyse wird im Hintergrund vorbereitet — Klicken, um sie erneut abzufragen';
    }
    return 'Analyse abgeschlossen – keine Felder ergänzt — Klicken, um die Analyse erneut zu starten';
  }
  if (kind === 'failed') {
    return 'Keine automatische Erkennung — Klicken, um die Analyse erneut zu starten';
  }
  return 'Die KI erkennt Dokumentname, Datum, Dokumenttyp, Korrespondent, Tags und Notizen.';
});
const analysisActionLabel = computed(() => ({ failed: 'Analyse wiederholen', interrupted: 'Analysestatus aktualisieren' })[aiAnalysis.value.kind] || 'Angaben automatisch ausfüllen');
const analysisHeaderStatus = computed(() => prepStatus.value.busy ? prepStatus.value.label
  : ({ failed: 'Erkennung fehlgeschlagen', interrupted: 'Status nicht verfügbar' })[aiAnalysis.value.kind] || 'Nur Notizen sind optional.');
const analysisScopeHint = computed(() => {
  const doc = primaryDocument.value;
  if (!doc || doc.meta.analysisRevision !== analysisRevision(doc, stagingStore.sourceMetaById)) return '';
  return importAnalysisScope(doc.meta.titleSuggestionMeta, doc.pages);
});

async function onImportAnalysisClick() {
  if (prepStatus.value.busy) { preparationHintOpen.value = true; return; }
  if (isCommitting.value || stagingStore.pendingCommit || totalPages.value === 0) return;
  if (aiAnalysis.value.kind === 'interrupted') {
    await requestScanTitleSuggestion(primaryDocument.value.id, 'all_pages', { silent: true });
  } else {
    await retryAnalysis(false);
  }
}


function resetScanSuggestionMeta(documentEntry) {
  const meta = ensureScanMeta(documentEntry);
  if (!meta) {
    return null;
  }
  meta.titleSuggestion = '';
  setImportAnalysisState(meta, 'idle');
  meta.titleSuggestionUsedFallback = false;
  meta.titleSuggestionPollExhausted = false;
  meta.titleSuggestionMeta = null;
  meta.appliedImportAnalysisKey = '';
  return meta;
}

function triggerAiFieldGlow() {
  if (typeof window !== 'undefined' && aiFieldGlowTimer) {
    window.clearTimeout(aiFieldGlowTimer);
  }
  aiFieldGlowActive.value = false;
  nextTick(() => {
    aiFieldGlowActive.value = true;
    if (typeof window !== 'undefined') {
      aiFieldGlowTimer = window.setTimeout(() => {
        aiFieldGlowActive.value = false;
        aiFieldGlowTimer = 0;
      }, 1450);
    }
  });
}

/* ── Datum-Hilfsfunktionen ── */


function isoToGermanDate(iso) {
  if (!iso) return '';
  const [yyyy, mm, dd] = iso.split('-');
  return `${dd}.${mm}.${yyyy}`;
}

function normalizeTagName(rawName) {
  return String(rawName || '').replace(/\s+/g, ' ').trim();
}

function validateTagName(name) {
  if (name.length < VOCAB_NAME_MIN_LENGTH) {
    return `Tag muss mindestens ${VOCAB_NAME_MIN_LENGTH} Zeichen enthalten.`;
  }
  if (name.length > VOCAB_NAME_MAX_LENGTH) {
    return `Tag darf maximal ${VOCAB_NAME_MAX_LENGTH} Zeichen enthalten.`;
  }
  return '';
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

function parkClosedImport(force = false) {
  if ((!force && props.modelValue) || isUploadingSources.value || isCommitting.value || remoteSourceLoads.value) return;
  analysisQueue.clear();
  for (const doc of documents.value) {
    if (['working', 'pending_ocr'].includes(doc.meta?.titleSuggestionStatus)) setImportAnalysisState(doc.meta, 'idle');
    if (doc.meta) { doc.meta.analysisPending = false; doc.meta.analysisLookupPending = false; }
  }
  const replaced = stagingStore.parkDraft();
  selected.value = null;
  peek.value = { open: false, x: 0, y: 0 };
  peekAnchorEl.value = null;
  remoteSourceStageBySession.clear();
  importTimingBySource.clear();
  previewImageSrc.value = '';
  previewImageLoading.value = false;
  previewImages.clear();
  pdfRenderer.clear();
  metadataFocus.reset();
  pageThumbRefs.clear();
  void draftPersistence.save().then(saved => {
    if (!saved || !replaced || draftPersistence.conflict.value) return;
    const kept = new Set([...stagingStore.sourceMetaById.keys(), ...(stagingStore.availableDraft?.sourceMeta || []).map(([id]) => id)]);
    const removed = replaced.sourceMeta.filter(([id]) => !kept.has(id));
    if (removed.length) emit('discarded-sources', {
      sourceFileIds: removed.map(([id]) => id),
      inboxItems: removed.filter(([, meta]) => meta.inboxItemId).map(([id, meta]) => [id, meta.inboxItemId]),
    });
  });
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      // A fast reopen still starts with the source choices after closing.
      if (closeParkTimer) {
        window.clearTimeout(closeParkTimer);
        closeParkTimer = 0;
        parkClosedImport(true);
      }
      void categoryStore.fetchCategories();
      void correspondentStore.ensureLoaded();
      return;
    }
    if (viewSwitchTimer) {
      window.clearTimeout(viewSwitchTimer);
      viewSwitchTimer = 0;
      isViewSwitching.value = false;
    }
    isDropzoneDragOver.value = false;
    dropDragDepth.value = 0;
    isBodyFileDragOver.value = false;
    bodyFileDragDepth.value = 0;
    isAddPageDragOver.value = false;
    addPageDragDepth.value = 0;
    documentDragDepth.value = {};
    correspondentDialogOpen.value = false;
    correspondentSearch.value = '';
    correspondentTarget = null;
    resetPageDragState();
    clearSettledPage();
    stopAutoScroll();
    detachPeekGlobalListeners();
    // Keep the visible page and working width through the normal leave animation.
    window.clearTimeout(closeParkTimer);
    closeParkTimer = window.setTimeout(() => {
      closeParkTimer = 0;
      parkClosedImport();
    }, 280);
  }
);
// Uploads and commits may finish after the window has already closed. Their
// result is parked only once they settle; closing never cancels or loses it.
watch([isUploadingSources, isCommitting, remoteSourceLoads], () => {
  if ((!props.modelValue || sourceChoicesRequested.value) && !closeParkTimer) parkClosedImport(sourceChoicesRequested.value);
});

watch(
  isEmpty,
  (empty) => {
    if (empty) validationAttempted.value = false;
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
      addSourceChooserOpen.value = false;
      retentionExpanded.value = false;
      aiFieldGlowActive.value = false;
      return;
    }
    nextTick(() => {
      setupBodyLayoutObserver();
      scheduleBodyContentLayoutStateUpdate();
      // Unterbrochene Analysen fortsetzen, ohne bereits fertige Werte zu ändern.
      // Die Queue verhindert doppelte Jobs für dieselbe Dokumentrevision.
      for (const doc of documents.value) {
        const status = String(doc.meta?.titleSuggestionStatus || '');
        const isTerminalGood = status === 'ready' || status === 'applied';
        const hasPages = Number(doc.pages?.length || 0) > 0;
        if (!isTerminalGood && hasPages && !titleSuggestJobByStage.has(doc.id)) {
          const recoverMeta = ensureScanMeta(doc);
          if (recoverMeta) {
            setImportAnalysisState(recoverMeta, 'idle');
            recoverMeta.titleSuggestionPollExhausted = false;
          }
          void requestScanTitleSuggestion(doc.id, 'first_page', { silent: true });
        }
      }
    });
    void ensureStageTagsLoaded().catch((error) => {
      notify({ type: 'error', message: mapApiError(error, 'Tags konnten nicht geladen werden.') });
    });
  },
  { immediate: true }
);

watch(canTriggerScan, (enabled) => {
  if (!enabled) {
    addSourceChooserOpen.value = false;
  }
});

watch(
  () => allPagesFlat.value.map(({ doc, page }) => `${doc.id}:${page.id}`).join('|'),
  () => {
    const flat = allPagesFlat.value;
    const currentIndex = flat.findIndex(({ page }) => page.id === selected.value?.pageId);
    const current = flat[currentIndex];
    if (current) {
      if (selected.value.stageId !== current.doc.id || selected.value.pageIndex !== currentIndex) {
        selectPage(current.doc.id, current.page.id, currentIndex);
      }
      if (peek.value.open) schedulePeekReposition();
    } else if (flat.length) {
      const next = flat[Math.min(selected.value?.pageIndex || 0, flat.length - 1)];
      selectPage(next.doc.id, next.page.id, next.globalIndex);
    } else {
      clearActiveSelection();
    }
  },
  { immediate: true }
);

function onPreviewVisiblePage(pageId) {
  if (!isOpen.value) return;
  const index = allPagesFlat.value.findIndex(({ page }) => page.id === pageId);
  const entry = allPagesFlat.value[index];
  if (!entry || selected.value?.pageId === pageId) return;
  selectPage(entry.doc.id, pageId, index);
  closePeek();
  void nextTick(() => pageThumbRefs.get(pageId)?.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
}

function pagePreviewSource(page) { return previewImages?.pagePreviewSource(page) || page.thumbUrl || ''; }
function pagePreviewIsThumbnail(page) { return previewImages?.pagePreviewIsThumbnail(page) ?? true; }
function pagePreviewSize(page) { return previewImages?.pagePreviewSize(page) || pageThumbnailSize(page); }

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

function requestCloseImport() {
  isOpen.value = false;
}

async function openAvailablePages() {
  if (props.availablePagesLoading || isUploadingSources.value || isCommitting.value || stagingStore.pendingCommit || isRemovingAvailable.value) return;
  sourceChoicesRequested.value = false;
  const restored = stagingStore.restoreAvailableDraft();
  await nextTick();
  if (restored) for (const doc of documents.value) {
    if (!['ready', 'applied'].includes(doc.meta?.titleSuggestionStatus)) {
      void requestScanTitleSuggestion(doc.id, 'first_page', { silent: true });
    }
  }
  emit('open-available-pages', { restored });
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
  const uploaded = [];
  const failures = [];
  for (const file of files) {
    try {
      if (!file.size || await file.slice(0, 5).text() !== '%PDF-') throw new Error('Die Datei enthält kein lesbares PDF.');
      const formData = new FormData();
      formData.append('files', file);
      const payload = await apiFetch('/api/import/source', { method: 'POST', body: formData, timeoutMs: 90000 });
      if (!payload?.items?.length) throw new Error('Der Server hat keine importierbaren Seiten zurückgegeben.');
      uploaded.push(...payload.items.map(item => ({ ...item, localFile: file })));
    } catch (error) { failures.push(`${file.name}: ${mapApiError(error, 'Datei konnte nicht vorbereitet werden.')}`); }
  }
  if (failures.length) notify({ type: 'warning', message: failures.join(' · ') });
  return uploaded;
}

function ensurePdfFilename(filename) {
  const normalized = String(filename || '').trim() || 'Scan Upload.pdf';
  return /\.pdf$/i.test(normalized) ? normalized : `${normalized}.pdf`;
}

async function downloadStagingSourceFile(sourceFileId, originalName = '') {
  const response = await fetch(`${props.apiBaseUrl}/api/import/source/${encodeURIComponent(sourceFileId)}/file`, {
    cache: 'no-store',
    headers: { ...authHeaders() }
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

function buildApiResourceUrl(pathOrUrl) {
  const raw = String(pathOrUrl || '').trim();
  if (!raw) {
    return '';
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  const base = String(props.apiBaseUrl || '').replace(/\/+$/, '');
  const path = raw.startsWith('/') ? raw : `/${raw}`;
  return `${base}${path}`;
}

function remotePreviewThumbUrls(source, pageCount) {
  const total = Math.max(0, Number(pageCount || 0));
  if (total <= 0) {
    return [];
  }
  const rawPreviewUrl = buildApiResourceUrl(source?.preview_url);
  if (!rawPreviewUrl) {
    return [];
  }
  const previewUrl = authedUrl(rawPreviewUrl);
  const thumbs = Array.from({ length: total }, () => '');
  thumbs[0] = previewUrl;
  return thumbs;
}

function normalizeRemoteScanCleanup(source) {
  const payload = source?.scan_cleanup;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null;
  }
  const status = String(payload.status || '').trim();
  if (!status) {
    return null;
  }
  return {
    ...payload,
    status,
    mode: String(payload.mode || '').trim(),
    updated_at: String(payload.updated_at || '').trim(),
    revision: String(payload.revision || '').trim()
  };
}

function scanCleanupKey(cleanup) {
  if (!cleanup || typeof cleanup !== 'object') {
    return '';
  }
  return [
    String(cleanup.status || ''),
    String(cleanup.mode || ''),
    String(cleanup.revision || ''),
    String(cleanup.updated_at || '')
  ].join('|');
}

function isScanCleanupReady(cleanup) {
  return String(cleanup?.status || '').trim() === 'ready';
}

// Erst nach einem erfolgreich durchgelaufenen Refresh gilt eine Bereinigung als
// im Dialog angekommen. Der Status allein reicht nicht: schlägt der Download
// fehl oder läuft gerade einer, käme sonst nie ein zweiter Versuch, weil der
// Status sich nicht mehr ändert.
const appliedScanCleanupKeys = new Map();

function shouldRefreshForScanCleanup(sourceFileId, nextCleanup) {
  if (!isScanCleanupReady(nextCleanup)) {
    return false;
  }
  return appliedScanCleanupKeys.get(String(sourceFileId || '').trim()) !== scanCleanupKey(nextCleanup);
}

function markScanCleanupApplied(sourceFileId, cleanup) {
  const normalized = String(sourceFileId || '').trim();
  if (normalized) {
    appliedScanCleanupKeys.set(normalized, scanCleanupKey(cleanup));
  }
}

function forgetScanCleanupApplied(sourceFileId) {
  appliedScanCleanupKeys.delete(String(sourceFileId || '').trim());
}

function upgradeRemoteSourceFile(sourceFileId, originalName, pageCount, { hadFastPreview = false } = {}) {
  const normalized = String(sourceFileId || '').trim();
  if (!normalized || remoteSourceUpgradeInFlight.has(normalized)) {
    return;
  }
  remoteSourceUpgradeInFlight.add(normalized);
  const cleanupKeyBeforeDownload = scanCleanupKey(stagingStore.sourceMetaById?.get?.(normalized)?.scanCleanup);
  void (async () => {
    try {
      const stagingFile = await downloadStagingSourceFile(normalized, originalName);
      let thumbUrls = [];
      try {
        thumbUrls = await renderPdfThumbnails(stagingFile, Number(pageCount || 0));
      } catch {
        thumbUrls = [];
      }
      const usedSourceIds = typeof stagingStore.collectUsedSourceFileIds === 'function'
        ? stagingStore.collectUsedSourceFileIds()
        : new Set();
      if (!usedSourceIds.has(normalized)) {
        const draft = stagingStore.availableDraft;
        const metadata = draft?.sourceMeta.find(([id]) => id === normalized)?.[1];
        if (metadata && scanCleanupKey(metadata.scanCleanup) === cleanupKeyBeforeDownload) {
          // A download begun while the window was open still belongs to the
          // closed draft. Retain its PDF locally without reopening the window.
          draft.files = draft.files.filter(([id]) => id !== normalized);
          draft.files.push([normalized, stagingFile]);
          metadata.pageQuality = thumbnailQuality.get(stagingFile) || [];
          for (const doc of draft.documents) for (const page of doc.pages) {
            if (page.sourceFileId === normalized && thumbUrls[page.pageIndex]) page.thumbUrl = thumbUrls[page.pageIndex];
          }
        }
        return;
      }
      const currentMeta = stagingStore.sourceMetaById?.get?.(normalized);
      // Während des Downloads kann die Bereinigung fertig geworden sein. Dann
      // hält diese Datei noch den Rohscan und darf die bereinigte Fassung nicht
      // überschreiben - der Refresh-Pfad lädt sie ohnehin neu.
      if (scanCleanupKey(currentMeta?.scanCleanup) !== cleanupKeyBeforeDownload) {
        forgetScanCleanupApplied(normalized);
        return;
      }
      stagingStore.setStagingFile(normalized, stagingFile, {
        originalName: originalName || stagingFile.name,
        pageCount: Number(pageCount || 0),
        isImportInbox: true,
        inboxItemId: currentMeta?.inboxItemId,
        analysis: currentMeta?.analysis,
        scanCleanup: currentMeta?.scanCleanup,
        colorPageIndices: currentMeta?.colorPageIndices,
        colorDetectionAvailable: currentMeta?.colorDetectionAvailable
      });
      if (thumbUrls.some((url) => String(url || '').trim())) {
        const metadata = stagingStore.sourceMetaById.get(normalized);
        if (metadata) metadata.pageQuality = thumbnailQuality.get(stagingFile) || [];
        stagingStore.updateSourceThumbnails(normalized, thumbUrls);
        clearPreviewCacheForSource(normalized);
        logPreviewVisibleTiming(normalized, {
          fast: false,
          pageCount,
          stageId: findStageIdsForSourceFile(normalized)[0] || ''
        });
      }
    } catch {
      if (!hadFastPreview) {
        notify({
          type: 'warning',
          message: 'Eine Scan-Datei konnte noch nicht für die Detailvorschau geladen werden.'
        });
      }
    } finally {
      remoteSourceUpgradeInFlight.delete(normalized);
    }
  })();
}

async function renderServerColorPreview(pageEntry, colorMode, signal) {
  const sourceFileId = normalizeSourceFileId(pageEntry?.sourceFileId);
  if (!sourceFileId) return '';
  const query = new URLSearchParams({
    page_index: String(Math.max(0, Number(pageEntry?.pageIndex || 0))),
    mode: String(colorMode || 'auto'), rotation: String(Number(pageEntry.rotation || 0))
  });
  try {
    const response = await fetch(
      `${props.apiBaseUrl}/api/import/source/${encodeURIComponent(sourceFileId)}/color-preview?${query}`,
      { cache: 'no-store', headers: { ...authHeaders() }, signal }
    );
    if (!response.ok) return '';
    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) return '';
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
      reader.onerror = () => resolve('');
      reader.readAsDataURL(blob);
    });
  } catch {
    return '';
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

  sourceChoicesRequested.value = false;
  isUploadingSources.value = true;
  preparationProgress.value = { done: 0, total: accepted.length };
  const touchedDocumentIds = new Set();
  try {
    const uploaded = await uploadSources(accepted.map((entry) => entry.file));
    if (!uploaded.length) return;

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
      const file = source.localFile || accepted[index].file;
      const pageCount = Number(source?.page_count || 0);
      const title = stripPdfSuffix(source?.original_name || file?.name || 'Neues Dokument');
      let thumbs = [];
      try {
        thumbs = await renderPdfThumbnails(file, pageCount);
      } catch {
        // Thumbnails are optional; a failed render must not abort the entire batch.
      }

      stagingStore.setStagingFile(source.source_file_id, file, {
        sourceType: 'local',
        originalName: source?.original_name || file?.name || '',
        sourceRevision: source?.source_revision,
        pageQuality: thumbnailQuality.get(file) || [],
        pageCount,
        colorPageIndices: source?.color_page_indices,
        colorDetectionAvailable: source?.color_detection_available
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
        void requestScanTitleSuggestion(docId, 'first_page', { silent: true });
      }
    }
    preparationProgress.value = { done: 0, total: 0 };
  }
}

// Serialisiert addRemoteSources-Aufrufe. SSE-Push und Polling können fast
// gleichzeitig dieselbe neue Scan-Quelle einspielen; ohne Serialisierung liefen
// zwei Aufrufe durch ihre awaits verschränkt, bestünden beide den
// sourceMetaById-Check, bevor einer setStagingFile() aufruft - und legten
// dieselbe Seite (und ggf. ein zweites Scan-Dokument) doppelt an.
let remoteSourcesChain = Promise.resolve();
const remoteSourceUpgradeInFlight = new Set();
const remoteSourceRefreshInFlight = new Map();

function addRemoteSources(payload = []) {
  remoteSourceLoads.value++;
  const run = remoteSourcesChain.then(() => addRemoteSourcesImpl(payload)).finally(() => { remoteSourceLoads.value--; });
  // Kette am Leben halten, auch wenn ein Lauf fehlschlägt.
  remoteSourcesChain = run.then(() => {}, () => {});
  return run;
}

async function addRemoteSourcesImpl(payload = []) {
  const items = Array.isArray(payload) ? payload : Array.isArray(payload?.sources) ? payload.sources : [];
  const preferredTargetStageId = String(payload?.targetStageId || '').trim() || null;
  const sessionId = String(payload?.sessionId || '').trim() || '__scan_default__';
  if (items.length === 0) {
    return;
  }

  let addedCount = 0;
  let addedScannerCount = 0;
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
    rememberImportSourceTiming(source);
    if (stagingStore.sourceMetaById?.has?.(sourceFileId)) {
      const nextCleanup = normalizeRemoteScanCleanup(source);
      if (source.source_revision) stagingStore.sourceMetaById.get(sourceFileId).sourceRevision = source.source_revision;
      if (typeof stagingStore.setSourceScanCleanup === 'function') {
        stagingStore.setSourceScanCleanup(sourceFileId, nextCleanup);
      }
      await applySourceAnalysisToExistingStages(sourceFileId, source?.analysis);
      if (shouldRefreshForScanCleanup(sourceFileId, nextCleanup)) {
        // Bewusst nicht abgewartet: ein langsamer Download/Render darf die
        // Verarbeitung der uebrigen Quellen (und damit deren Spinner-Status)
        // nicht aufhalten.
        void refreshImportInboxSourceFile(sourceFileId, pageCount, { scanCleanup: nextCleanup });
      }
      continue;
    }

    const originalName = String(source?.original_name || '').trim() || 'Scan Upload.pdf';
    const sourceTitle = getRemoteSourceTitle(source);
    const thumbUrls = remotePreviewThumbUrls(source, pageCount);
    const hadFastPreview = thumbUrls.some((url) => String(url || '').trim());
    logImportTiming('source_added_to_dialog', {
      source_file_id: sourceFileId,
      page_count: pageCount,
      fast_preview: hadFastPreview,
      ms_since_dialog_source_seen: msSinceImportSourceSeen(sourceFileId)
    });

    stagingStore.setStagingFile(sourceFileId, null, {
      originalName,
      sourceRevision: source.source_revision,
      pageCount,
      isImportInbox: true,
      inboxItemId: source.id,
      sourceType: source.source_type,
      analysis: source?.analysis,
      scanCleanup: normalizeRemoteScanCleanup(source),
      colorPageIndices: source?.color_page_indices,
      colorDetectionAvailable: source?.color_detection_available
    });
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
      await applyCachedImportAnalysis(targetStageId, source?.analysis);
      if (hadFastPreview) {
        logPreviewVisibleTiming(sourceFileId, { fast: true, pageCount, stageId: targetStageId });
      }
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
        await applyCachedImportAnalysis(fallbackStageId, source?.analysis);
        if (hadFastPreview) {
          logPreviewVisibleTiming(sourceFileId, { fast: true, pageCount, stageId: fallbackStageId });
        }
        touchedStageIds.add(fallbackStageId);
      } else {
        const createdDoc = stagingStore.addDocumentFromSource({
          sourceFileId,
          title: sourceTitle,
          pageCount,
          thumbUrls
        });
        await applyCachedImportAnalysis(createdDoc?.id, source?.analysis);
        if (hadFastPreview) {
          logPreviewVisibleTiming(sourceFileId, { fast: true, pageCount, stageId: createdDoc?.id || '' });
        }
      }
    }
    addedCount += 1;
    if (String(source?.source_type || '').trim() === 'scanner') {
      addedScannerCount += 1;
    }
    upgradeRemoteSourceFile(sourceFileId, originalName, pageCount, { hadFastPreview });
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
    const label =
      addedScannerCount === addedCount
        ? `Scan-Seite${addedCount === 1 ? '' : 'n'}`
        : addedScannerCount === 0
          ? `iPhone-Upload${addedCount === 1 ? '' : 's'}`
          : `Datei${addedCount === 1 ? '' : 'en'}`;
    notify({
      type: 'success',
      message: `${addedCount} ${label} hinzugefügt.`
    });
  }
}


function getImportAnalysisCacheKey(analysis) {
  if (!analysis || typeof analysis !== 'object') {
    return '';
  }
  const meta = analysis.meta && typeof analysis.meta === 'object' ? analysis.meta : {};
  return [
    String(meta.result_revision || meta.cached_at || ''),
    String(meta.analysis_job_id || ''), String(meta.analysis_sequence || ''),
    String(meta.analysis_phase || ''),
    String(analysis.status || ''),
    String(analysis.suggestion || ''), String(analysisPending(analysis))
  ].join('|');
}

function findStageIdsForSourceFile(sourceFileId) {
  const normalized = String(sourceFileId || '').trim();
  if (!normalized) {
    return [];
  }
  const ids = [];
  for (const doc of documents.value || []) {
    const metaIds = Array.isArray(doc?.meta?.scanSourceFileIds)
      ? doc.meta.scanSourceFileIds.map((entry) => String(entry || '').trim())
      : [];
    const pageIds = Array.isArray(doc?.pages)
      ? doc.pages.map((page) => String(page?.sourceFileId || '').trim())
      : [];
    if ([...metaIds, ...pageIds].includes(normalized)) {
      ids.push(doc.id);
    }
  }
  return ids;
}

async function applyImportAnalysisPayload(stageId, payload, options = {}) {
  const doc = getDocumentById(stageId);
  if (!doc || !payload || payload.status === 'unknown') return false;
  const meta = ensureScanMeta(doc);
  const resultMeta = payload.meta || {};
  const revision = analysisRevision(doc, stagingStore.sourceMetaById);
  const expected = options.documentRevision || resultMeta.document_revision;
  if (expected && expected !== revision || !acceptAnalysisSnapshot(meta, payload, revision)) return false;
  const pending = analysisPending(payload);
  const incomingPhase = resultMeta.progress_phase || (resultMeta.refinement_pending ? 'llm' : 'ocr');
  setImportAnalysisState(meta, pending ? (['queued', 'ocr', 'llm'].includes(incomingPhase) ? incomingPhase : 'ocr') : 'complete');
  const status = String(payload.status || 'ready');
  if (['error', 'failed'].includes(status)) {
    if (!pending) setImportAnalysisState(meta, 'error');
    return false;
  }
  if (status === 'pending_ocr') return false;
  const form = ensureImportForm(doc);
  const revisions = options.fieldRevisions || { ...form.revisions };
  const token = getImportAnalysisCacheKey(payload);
  meta.analysisFieldsToken = token;
  meta.titleSuggestion = meaningfulSuggestion(payload.suggestion);
  meta.titleSuggestionUsedFallback = Boolean(payload.usedFallback ?? payload.used_fallback);
  meta.titleSuggestionMeta = resultMeta;
  if (!pending) setImportAnalysisState(meta, 'complete');
  meta.analysisRevision = revision;
  const origin = field => resultMeta.field_origins?.[field] || (resultMeta.analysis_phase === 'llm' ? 'KI' : 'Regeln');
  let changed = false;
  const apply = (field, value, read, write) => {
    if (metadataFocus.defer(stageId, field, () => {
      if (getDocumentById(stageId) !== doc || analysisRevision(doc, stagingStore.sourceMetaById) !== revision) return;
      if (applyFieldProposal(doc, field, value, revisions[field] || 0, read, write, origin(field))) triggerAiFieldGlow();
    })) return false;
    const applied = applyFieldProposal(doc, field, value, revisions[field] || 0, read, write, origin(field));
    changed ||= applied;
    return applied;
  };
  if (meta.titleSuggestion && !meta.titleSuggestionUsedFallback) {
    apply('title', meta.titleSuggestion, () => doc.title, value => stagingStore.renameDocument(stageId, value));
  }
  const parsedDate = isoToGermanDate(resultMeta.date);
  if (parsedDate && parseDocumentDateInput(parsedDate).ok) apply('date', parsedDate, () => form.date, value => { form.date = value; });
  const category = meaningfulSuggestion(resultMeta.document_type || resultMeta.category);
  if (category) {
    if (categoryStore.categoryNames.includes(category)) apply('category', category, () => form.category, value => { form.category = value; });
    else if (form.dismissed.category !== category) form.proposals.category = { value: category, origin: origin('category') };
  }
  const note = usefulAnalysisNote(resultMeta.note, { ...resultMeta, title:doc.title });
  if (note) apply('note', note, () => form.note, value => { form.note = value; });
  if (isRetentionEnabled.value && resultMeta.retention) apply('retention', resultMeta.retention, () => form.retention, value => { form.retention = value; });
  const tagNames = (resultMeta.tags || []).map(name => normalizeTagName(String(name || ''))).filter(name => meaningfulSuggestion(name) && !validateTagName(name));
  if (tagNames.length) apply('tags', tagNames, () => [...(doc.tags || []).map(id => stageTagPool.value.find(tag => tag.id === id)?.name).filter(Boolean), ...(meta.pendingTagNames || [])], names => {
    const ids = names.map(findStageTagIdByName).filter(Boolean);
    stagingStore.setDocumentTags(stageId, ids);
    meta.pendingTagNames = names.filter(name => !findStageTagIdByName(name));
  });
  // Vocabulary requests must never hold back title, date, note or tag names.
  const applyCorrespondent = () => {
    const correspondent = resultMeta.correspondent?.id;
    if (correspondent && correspondentStore.findById(correspondent)) {
      apply('correspondent', correspondent, () => form.correspondentId, value => { form.correspondentId = value; });
    } else {
      const sender = meaningfulSuggestion(resultMeta.sender_raw || resultMeta.correspondent?.name);
      if (sender && form.dismissed.correspondent !== sender) form.proposals.correspondent = { value: sender, origin: origin('correspondent') };
    }
  };
  meta.analysisLookupPending = !correspondentStore.isLoaded && Boolean(resultMeta.correspondent?.id || resultMeta.sender_raw);
  if (correspondentStore.isLoaded) applyCorrespondent();
  else if (meta.analysisLookupPending) {
    let timeout;
    void Promise.race([correspondentStore.ensureLoaded(), new Promise((_, reject) => {
      timeout = window.setTimeout(() => reject(new Error('lookup timeout')), 10000);
    })]).then(() => {
      if (!analysisDisposed && getDocumentById(stageId) === doc && meta.analysisFieldsToken === token && revision === analysisRevision(doc, stagingStore.sourceMetaById)) applyCorrespondent();
    }).catch(() => {}).finally(() => {
      window.clearTimeout(timeout);
      if (meta.analysisFieldsToken === token) meta.analysisLookupPending = false;
    });
  }
  void ensureStageTagsLoaded().catch(() => {});
  if (changed) { diagnostics.once(`${stageId}:${revision}`, 'first_metadata', { duration_ms: diagnostics.elapsed(`analysis:${stageId}`) }); triggerAiFieldGlow(); }
  if (!pending) diagnostics.end(`analysis:${stageId}`, 'analysis_complete', { pages: doc.pages.length, ocr_ms: resultMeta.timings?.ocr_ms, ai_ms: resultMeta.timings?.ai_ms });
  return true;
}

async function applyCachedImportAnalysis(stageId, analysis) {
  if (!analysis || typeof analysis !== 'object') {
    return false;
  }
  const documentEntry = getDocumentById(stageId);
  const meta = ensureScanMeta(documentEntry);
  if (!meta || documentEntry.pages.length !== 1 || documentEntry.pages[0].pageIndex !== 0 || documentEntry.pages[0].rotation) return false;
  const cacheKey = getImportAnalysisCacheKey(analysis);
  if (cacheKey && meta.appliedImportAnalysisKey === cacheKey) {
    return false;
  }
  const applied = await applyImportAnalysisPayload(stageId, analysis, { silent: true, documentRevision: analysisRevision(documentEntry, stagingStore.sourceMetaById) });
  if (applied && cacheKey) {
    meta.appliedImportAnalysisKey = cacheKey;
  }
  if (analysisPending(analysis) && !titleSuggestJobByStage.has(stageId)) {
    void requestScanTitleSuggestion(stageId, 'all_pages', { silent: true });
  }
  return applied;
}

async function applySourceAnalysisToExistingStages(sourceFileId, analysis) {
  const normalized = String(sourceFileId || '').trim();
  if (!normalized || !analysis || typeof analysis !== 'object') {
    return false;
  }
  if (typeof stagingStore.setSourceAnalysis === 'function') {
    stagingStore.setSourceAnalysis(normalized, analysis);
  }
  let applied = false;
  for (const stageId of findStageIdsForSourceFile(normalized)) {
    applied = (await applyCachedImportAnalysis(stageId, analysis)) || applied;
  }
  return applied;
}

async function requestScanTitleSuggestion(stageId, pageScope = 'all_pages', options = {}) {
  const doc = getDocumentById(stageId);
  if (!doc?.pages?.length || props.scannerActive || isCommitting.value) return;
  if (titleSuggestJobByStage.has(stageId)) return titleSuggestJobByStage.get(stageId);
  const revision = analysisRevision(doc, stagingStore.sourceMetaById);
  const analysisPages = options.analysisPageIds ? doc.pages.filter(page => options.analysisPageIds.has(page.id)) : doc.pages;
  const pages = sourcePages({ ...doc, pages: analysisPages }, stagingStore.sourceMetaById).map(page => ({ ...page, color_mode: 'auto' }));
  if (!pages.length) return;
  const sourceFileIds = [...new Set(pages.map(page => page.source_file_id))];
  const meta = ensureScanMeta(doc);
  const fieldRevisions = { ...ensureImportForm(doc).revisions };
  if (options.force) meta.analysisSnapshot = null;
  setImportAnalysisState(meta, 'queued');
  diagnostics.start(`analysis:${stageId}`, 'analysis_start');
  meta.titleSuggestionPollExhausted = false;
  meta.analysisSlow = false;
  const job = analysisQueue.enqueue(stageId, revision, async signal => {
    const current = () => !signal.aborted && !analysisDisposed && getDocumentById(stageId) === doc
      && titleSuggestJobByStage.get(stageId) === job && analysisRevision(doc, stagingStore.sourceMetaById) === revision;
    const slowTimer = window.setTimeout(() => { if (current()) meta.analysisSlow = true; }, 20000);
    let response = null;
    let responseError = null;
    let settled = false;
    let consumed = false;
    let misses = 0;
    const start = () => {
      const oneOriginalPage = pages.length === 1 && pages[0].page_index === 0 && !pages[0].rotation;
      return suggestImportStageTitle(props.apiBaseUrl, stageId, {
        sourceFileIds, pageScope: oneOriginalPage ? 'first_page' : 'all_pages',
        pages: oneOriginalPage && !options.force && !options.repeatOcr ? [] : pages,
        documentRevision: revision, force: Boolean(options.force), repeatOcr: Boolean(options.repeatOcr), signal: signal,
      }).then(payload => { response = payload; settled = true; }, error => { responseError = error; settled = true; });
    };
    const request = start();
    try {
      // Observe progress while the original request is still running. Its HTTP
      // timeout does not cancel the server job or discard earlier results.
      await Promise.race([request, abortableDelay(1200, signal)]);
      for (let attempts = 0; attempts < 100 && current(); attempts++) {
        let payload;
        if (settled && !consumed) {
          consumed = true;
          if (responseError) {
            if (!transientAnalysisError(responseError)) throw responseError;
            meta.analysisReconnecting = true;
          } else payload = response;
        }
        if (!payload) {
          try {
            payload = await readImportStageAnalysis(stageId, { sourceFileIds, documentRevision: revision, signal: signal });
          } catch (error) {
            if (!transientAnalysisError(error)) throw error;
            meta.analysisReconnecting = true;
          }
        }
        if (!current()) return;
        if (!payload || !['ready', 'pending_ocr', 'error', 'failed'].includes(payload.status)) {
          if (++misses >= 4) break;
        } else {
          misses = 0;
          if (options.analysisPageIds) payload.meta = { ...payload.meta, analysis_selection: true };
          await applyImportAnalysisPayload(stageId, payload, { ...options, documentRevision: revision, fieldRevisions });
          if (!analysisPending(payload) && !meta.analysisPending) return;
          if (payload.meta?.restart_after_cleanup && !isScanCleanupRunning.value) {
            // The previous request only observed cleanup and did no analysis.
            response = null; responseError = null; settled = false; consumed = false;
            void start();
          }
        }
        await abortableDelay(Math.min(10000, 1500 + attempts * 500), signal);
      }
      if (current()) setImportAnalysisState(meta, 'interrupted');
    } catch (error) {
      if (current()) {
        setImportAnalysisState(meta, transientAnalysisError(error) ? 'interrupted' : 'error');
      }
    } finally {
      window.clearTimeout(slowTimer);
      if (getDocumentById(stageId) === doc && revision !== analysisRevision(doc, stagingStore.sourceMetaById)) {
        setImportAnalysisState(meta, 'idle');
        scheduleDocumentAnalysis();
      }
    }
  });
  return job;
}

let documentAnalysisTimer = 0;
function scheduleDocumentAnalysis() {
  window.clearTimeout(documentAnalysisTimer);
  documentAnalysisTimer = window.setTimeout(() => {
    if (props.scannerActive || isCommitting.value || isScanCleanupRunning.value || isUploadingSources.value) return;
    for (const doc of documents.value) {
      if (doc.pages.length && doc.meta?.analysisRevision !== analysisRevision(doc, stagingStore.sourceMetaById)) {
        void requestScanTitleSuggestion(doc.id, 'all_pages', { silent: true });
      }
    }
  }, 700);
}
watch(() => documents.value.map(doc => [doc.id, analysisRevision(doc, stagingStore.sourceMetaById)]), entries => analysisQueue.reconcile(new Map(entries)));
watch(() => [documents.value.map(doc => analysisRevision(doc, stagingStore.sourceMetaById)).join('|'), props.scannerActive, isScanCleanupRunning.value, isUploadingSources.value], scheduleDocumentAnalysis);

function onImportTagKeydown(event) {
  if (event.key === 'Enter' && tagInlineValue.value.trim() && !event.target?.getAttribute('aria-activedescendant')) {
    event.preventDefault();
    onTagNamesChange([...primaryDocTagNames.value, tagInlineValue.value]);
    tagInlineValue.value = '';
  }
}
function saveImportRetention(value) {
  docRetention.value = { ...value, status: 'manual', retain_until: computeRetainUntilIso(value.period_years) };
  docRetentionTouched.value = true;
}
async function retryAnalysis(repeatOcr = false) {
  if (isRetryingAnalysis.value) {
    return;
  }
  const docs = documents.value || [];
  let started = 0;
  const jobs = [];
  isRetryingAnalysis.value = true;
  for (const doc of docs) {
    const id = String(doc?.id || '').trim();
    if (!id || Number(doc?.pages?.length || 0) === 0) {
      continue;
    }
    resetScanSuggestionMeta(doc);
    jobs.push(requestScanTitleSuggestion(id, 'all_pages', { silent: true, force: true, repeatOcr }));
    started += 1;
  }
  if (started === 0) {
    isRetryingAnalysis.value = false;
    notify({ type: 'info', message: 'Keine Seiten zum Analysieren vorhanden.' });
    return;
  }
  notify({
    type: 'info',
    message: started === 1
      ? 'Analyse wird wiederholt…'
      : `Analyse für ${started} Dokumente wird wiederholt…`
  });
  try {
    await Promise.allSettled(jobs);
  } finally {
    isRetryingAnalysis.value = false;
  }
}


function openFilePicker() {
  addSourceChooserOpen.value = false;
  fileInput.value?.click();
}

function toggleAddSourceChooser() {
  if (isUploadingSources.value || isCommitting.value) {
    return;
  }
  addSourceChooserOpen.value = !addSourceChooserOpen.value;
}

function choosePdfSource() {
  openFilePicker();
}

function chooseScanSource() {
  if (props.scannerActive) {
    return;
  }
  addSourceChooserOpen.value = false;
  emitScan('page');
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


function focusDocumentTitle(documentId) {
  const target = titleInputRefs.get(documentId);
  target?.focus?.();
  target?.select?.();
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

function setImportColorMode(colorMode) {
  if (colorToolsDisabled.value) return;
  stagingStore.setAllPagesColorMode(colorMode);
}


function onTagNamesChange(newNames) {
  if (!primaryDocument.value) return;
  docTagsTouched.value = true;
  docTagsAiFilled.value = false;
  // Bestehende Tags als IDs, noch nicht existierende Namen als "pending" halten
  // (werden erst beim Import angelegt). Kein sofortiges Anlegen mehr.
  const ids = [];
  const pending = [];
  const seenPending = new Set();
  for (const name of newNames) {
    if (!name || typeof name !== 'string') continue;
    const norm = normalizeTagName(name);
    if (!norm) continue;
    const validation = validateTagName(norm);
    if (validation) { notify({ type: 'warning', message: validation }); continue; }
    const id = findStageTagIdByName(norm);
    if (id) {
      if (!ids.includes(id)) ids.push(id);
    } else {
      const key = norm.toLocaleLowerCase('de-DE');
      if (!seenPending.has(key)) {
        seenPending.add(key);
        pending.push(norm);
      }
    }
  }
  stagingStore.setDocumentTags(primaryDocument.value.id, ids);
  const meta = ensureScanMeta(primaryDocument.value);
  if (meta) meta.pendingTagNames = pending;
}

function normalizeImportDate() {
  const parsed = parseDocumentDateInput(docDate.value);
  if (parsed.ok) docDate.value = parsed.display;
}

function normalizeSourceFileId(sourceFileId) {
  return String(sourceFileId || '').trim();
}


function notifyDiscardedSourceFileIds(sourceFileIds = []) {
  const candidates = Array.from(new Set((sourceFileIds || []).map(normalizeSourceFileId).filter(Boolean)));
  if (candidates.length === 0) {
    return;
  }
  const usedSourceIds = stagingStore.collectUsedSourceFileIds();
  for (const [id] of stagingStore.availableDraft?.sourceMeta || []) usedSourceIds.add(id);
  const discarded = candidates.filter((sourceFileId) => !usedSourceIds.has(sourceFileId));
  if (discarded.length > 0) {
    emit('discarded-sources', { sourceFileIds: discarded });
  }
}


function clearPreviewCacheForSource(sourceFileId) {
  pdfRenderer.invalidate(sourceFileId);
  previewImages.invalidate(sourceFileId);
}

async function refreshImportInboxSourceFile(sourceFileId, pageCount, metaPatch = {}) {
  const normalized = normalizeSourceFileId(sourceFileId);
  const sourceMeta = stagingStore.sourceMetaById?.get?.(normalized);
  if (!normalized || !sourceMeta) {
    return;
  }
  // Pro Quelle darf immer nur ein Refresh laufen. Zwei parallele Laeufe laden
  // die Datei zu unterschiedlichen Zeitpunkten; straddelt einer das serverseitige
  // Ersetzen, haelt er noch den Rohscan und ueberschreibt als letzter Schreiber
  // die bereits bereinigte Vorschau.
  const running = remoteSourceRefreshInFlight.get(normalized);
  if (running) {
    return running;
  }
  sourceRefreshCount.value += 1;
  const task = (async () => {
    try {
      const refreshedFile = await downloadStagingSourceFile(normalized, sourceMeta.originalName || '');
      const thumbUrls = await renderPdfThumbnails(refreshedFile, Number(pageCount || sourceMeta.pageCount || 0));
      const nextScanCleanup = Object.prototype.hasOwnProperty.call(metaPatch, 'scanCleanup')
        ? metaPatch.scanCleanup
        : sourceMeta.scanCleanup;
      if (!stagingStore.sourceMetaById.has(normalized)) return;
      stagingStore.setStagingFile(normalized, refreshedFile, {
        originalName: sourceMeta.originalName || refreshedFile.name,
        pageCount: Number(pageCount || sourceMeta.pageCount || 0),
        isImportInbox: true,
        inboxItemId: sourceMeta.inboxItemId,
        analysis: sourceMeta.analysis,
        scanCleanup: nextScanCleanup,
        colorPageIndices: sourceMeta.colorPageIndices,
        colorDetectionAvailable: sourceMeta.colorDetectionAvailable
      });
      stagingStore.updateSourceThumbnails(normalized, thumbUrls);
      const metadata = stagingStore.sourceMetaById.get(normalized);
      if (metadata) metadata.pageQuality = thumbnailQuality.get(refreshedFile) || [];
      clearPreviewCacheForSource(normalized);
      if (isScanCleanupReady(nextScanCleanup)) {
        markScanCleanupApplied(normalized, nextScanCleanup);
      }
    } catch {
      // Die bisherigen Thumbnails bleiben nutzbar. Der Versuch wird nicht als
      // erledigt vermerkt, damit der nächste Inbox-Push ihn wiederholt.
    } finally {
      remoteSourceRefreshInFlight.delete(normalized);
      sourceRefreshCount.value = Math.max(0, sourceRefreshCount.value - 1);
    }
  })();
  remoteSourceRefreshInFlight.set(normalized, task);
  return task;
}

async function removePage(pageId) {
  if (isCommitting.value || stagingStore.pendingCommit) return;
  stagingStore.removePage(pageId);
}

async function removeSelectedPage(documentId) {
  const selectedPage = resolveSelectedPage(documentId);
  if (!selectedPage) {
    return;
  }
  await removePage(selectedPage.id);
}

function deleteDocument(documentId) {
  stagingStore.deleteDocument(documentId);
}

async function retryThumbnail(page) {
  if (lazyThumbnailJobs.has(page.id)) return;
  lazyThumbnailJobs.add(page.id);
  const revision = pageDisplayRevision(page, stagingStore.sourceMetaById);
  const task = thumbnailRenderChain.catch(() => {}).then(async () => {
    try {
      if (!stagingStore.findPageLocation(page.id)) return;
      const rendered = await renderServerColorPreview(page, page.colorMode || 'auto');
      if (revision !== pageDisplayRevision(page, stagingStore.sourceMetaById)) return;
      if (rendered) { page.thumbUrl = rendered; page.previewError = false; }
      else page.previewError = true;
    } finally { lazyThumbnailJobs.delete(page.id); }
  });
  thumbnailRenderChain = task;
  return task;
}

function setPageThumbRef(pageId, element) {
  if (!element) {
    const previous = pageThumbRefs.get(pageId);
    if (previous) thumbnailObserver?.unobserve(previous);
    pageThumbRefs.delete(pageId);
    return;
  }
  pageThumbRefs.set(pageId, element);
  if (typeof IntersectionObserver === 'undefined') return;
  if (!thumbnailObserver) thumbnailObserver = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      const page = stagingStore.findPageLocation(entry.target.dataset.pageId)?.page;
      if (page && !page.thumbUrl) void retryThumbnail(page);
    }
  }, { rootMargin: '300px' });
  thumbnailObserver.observe(element);
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
  void scrollPreviewToPage(pageId);
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


function isPageSelected(documentId, pageId) {
  return (
    selected.value?.stageId === String(documentId || '').trim() &&
    selected.value?.pageId === String(pageId || '').trim()
  );
}

function isDraggingPage(pageId) {
  return pageDragState.value.active && pageDragState.value.pageId === String(pageId || '');
}


function rotateSelectedPage(documentId, delta) {
  const selectedPage = resolveSelectedPage(documentId);
  if (!selectedPage) {
    return;
  }
  stagingStore.rotatePage(selectedPage.id, Number(delta) < 0 ? 'left' : 'right');
}


function shiftSelection(step, { focus = true } = {}) {
  const flat = allPagesFlat.value;
  const currentIndex = flat.findIndex(({ page }) => page.id === selected.value?.pageId);
  const nextIndex = Math.max(0, Math.min(flat.length - 1, currentIndex + step));
  const next = flat[nextIndex];
  if (!next || nextIndex === currentIndex) return false;
  selectPage(next.doc.id, next.page.id, nextIndex, { anchorEl: pageThumbRefs.get(next.page.id) || null });
  void nextTick(() => {
    const element = pageThumbRefs.get(next.page.id);
    if (focus) element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  });
  return true;
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
  if (!isOpen.value || correspondentDialogOpen.value || event.defaultPrevented
    || event.target?.closest?.('.isd-field-proposal, .isd-readiness-card')) {
    return;
  }
  // Enter activates the focused button. It must not also submit the import.
  if (event.key !== 'Escape' && event.target?.closest?.('button')) return;
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
  const docsContainer = startElement?.closest?.('.isd-grid-scroll, .import-staging-scroll');
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


function clearDocumentDragDepth(documentId) {
  if (!(documentId in documentDragDepth.value)) {
    return;
  }
  const nextState = { ...documentDragDepth.value };
  delete nextState[documentId];
  documentDragDepth.value = nextState;
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
  const before = event.clientY < itemRect.top + itemRect.height / 2;
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
  const nearestDocument = allPagesFlat.value.find(({ page }) => page.id === nearestPageId)?.doc;
  updatePageDropTargetFromElement(event, nearestDocument?.id || targetDocId, nearestPageId, nearestIndex, nearest.element);
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
  const resolvedDocId = pageDragState.value.overDocId || targetDocId;
  const targetDoc = documents.value.find((entry) => entry.id === resolvedDocId);
  const fallbackIndex = targetDoc?.pages?.length ?? 0;
  const insertionIndex = getResolvedDropIndex(resolvedDocId, fallbackIndex);
  stagingStore.movePage(draggedPageId, resolvedDocId, insertionIndex);
  markSettledPage(draggedPageId);
  resetPageDragState();
}


const commitTransaction = useImportCommit({
  store: stagingStore, correspondents: correspondentStore, settings: settingsStore, retentionEnabled: isRetentionEnabled,
  autoEmbed: () => props.autoEmbed, persistence: draftPersistence, notify, diagnostics,
  onCreated: payload => emit('committed', payload), onEmpty: () => { isOpen.value = false; },
  onSelectionCleared: () => { clearMultiSelection(); clearActiveSelection(); },
});

async function commitImport(selectedPageIds = null) {
  if (isEmptyLayout.value && stagingStore.pendingCommit && !isImportActionBusy.value) {
    sourceChoicesRequested.value = false;
    await nextTick();
  }
  if (isEmptyLayout.value || isImportActionBusy.value) return;
  const entries = commitSubset(documents.value, selectedPageIds instanceof Set ? selectedPageIds : null);
  if (!entries.length) return;
  validationAttempted.value = true;
  const invalid = entries.find(({ document, pages }) => Object.keys(validateImportDocument({ ...document, pages })).length);
  if (invalid && !stagingStore.pendingCommit) {
    activeDocumentId.value = invalid.document.id;
    const page = invalid.pages[0];
    selectPage(invalid.document.id, page.id, allPagesFlat.value.findIndex(entry => entry.page.id === page.id));
    await nextTick();
    const invalidField = Object.keys(validateImportDocument({ ...invalid.document, pages: invalid.pages }))[0];
    const row = document.querySelector(`.isd-props [data-field="${invalidField === 'title' ? 'name' : invalidField}"]`);
    const invalidInput = row?.querySelector('input:not([type="hidden"]), textarea');
    (invalidInput || document.querySelector('.isd-props input'))?.focus();
    return;
  }
  isCommitting.value = true;
  try { await commitTransaction.run(entries); }
  finally { isCommitting.value = false; }
}

async function openWithFiles(files) {
  const candidates = Array.from(files || []).map((file) => ({ file, relativePath: '' }));
  if (candidates.length <= 0) {
    return;
  }

  try {
    sourceChoicesRequested.value = false;
    isOpen.value = true;
    await addFilesToStaging(candidates);
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Import-Quellen konnten nicht hochgeladen werden.') });
  }
}

async function openWithRemoteSources(payload = {}) {
  sourceChoicesRequested.value = false;
  isOpen.value = true;
  await nextTick();
  await addRemoteSources(payload);
}

function openDialog() {
  isOpen.value = true;
}

function openStartScreen() {
  sourceChoicesRequested.value = true;
  window.clearTimeout(closeParkTimer);
  closeParkTimer = 0;
  parkClosedImport(true);
  isOpen.value = true;
}

// Ursprung für die Import-Fluganimation: Rechteck + Thumbnail des Dokuments im
// Commit-Moment (Dialog noch offen). Für einen pixelgenauen FLIP-Start wird der
// sichtbare RAHMEN der Miniatur gemessen, nicht nur das darin liegende Bild.
// Dadurch stimmen Größe, Rundung, Border und der `contain`-Bildzuschnitt beim
// Überblenden exakt überein.
function getFlightOrigin() {
  if (typeof document === 'undefined') return null;
  const isVisible = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return r && r.width >= 4 && r.height >= 4 ? { element: el, rect: r } : null;
  };
  const firstVisible = (selectors) => {
    for (const sel of selectors) {
      const match = isVisible(document.querySelector(sel));
      if (match) return match;
    }
    return null;
  };
  const origin = firstVisible([
    '.isd-page-card--selected .isd-page-thumb-wrap',
    '.isd-page-card .isd-page-thumb-wrap',
    '.isd-preview-image',
    '.isd-card'
  ]);
  if (!origin) return null;

  const { element, rect } = origin;
  const thumbImg = element instanceof HTMLImageElement
    ? element
    : element.querySelector('.isd-page-thumb, img');

  // Genau das Bild der gemessenen Kachel verwenden. Ein anderes (z. B. die
  // größere Detailvorschau) kann leicht abweichend beschnitten sein und wäre
  // beim deckungsgleichen Start als Doppelkontur sichtbar.
  const thumbUrl = thumbImg?.currentSrc || thumbImg?.getAttribute('src') || previewImageSrc.value || '';

  const numberValue = (value, fallback = 0) => {
    const parsed = Number.parseFloat(String(value || ''));
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const frameStyle = window.getComputedStyle(element);
  const imageStyle = thumbImg ? window.getComputedStyle(thumbImg) : null;
  // Der Flug verwendet einen echten DOM-Klon dieser sichtbaren Kachel. So
  // bleiben intrinsische Bildgröße, object-fit, Drehung und Clip identisch und
  // können nicht durch einen zweiten Renderpfad auseinanderlaufen.
  const visualClone = element.cloneNode(true);

  // Farbmodus (S/W, Graustufen, Farbe) und eventuelle Drehung liegen als CSS
  // auf dem Bild. Auch diese Darstellungseigenschaften werden übernommen.
  let thumbFilter = 'none';
  if (imageStyle?.filter && imageStyle.filter !== 'none') {
    thumbFilter = imageStyle.filter;
  }

  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    thumbUrl,
    visualClone,
    thumbFilter,
    thumbTransform: imageStyle?.transform || 'none',
    imageFit: imageStyle?.objectFit || 'contain',
    imagePosition: imageStyle?.objectPosition || 'center center',
    borderRadius: numberValue(frameStyle.borderTopLeftRadius, 4),
    borderWidth: numberValue(frameStyle.borderTopWidth, 0),
    borderColor: frameStyle.borderTopColor || 'transparent',
    borderStyle: frameStyle.borderTopStyle || 'solid',
    backgroundColor: frameStyle.backgroundColor || '#fff',
    boxShadow: frameStyle.boxShadow || 'none',
    outlineWidth: numberValue(frameStyle.outlineWidth, 0),
    outlineColor: frameStyle.outlineColor || 'transparent',
    outlineStyle: frameStyle.outlineStyle || 'solid',
    outlineOffset: numberValue(frameStyle.outlineOffset, 0)
  };
}

defineExpose({
  openDialog,
  openStartScreen,
  isSourceChoicePending: () => sourceChoicesRequested.value,
  openWithFiles,
  openWithRemoteSources,
  getFlightOrigin,
  diagnostics: () => diagnostics.snapshot()
});

onBeforeUnmount(() => {
  analysisDisposed = true;
  analysisQueue.close();
  if (typeof window !== 'undefined' && closeParkTimer) {
    window.clearTimeout(closeParkTimer);
    closeParkTimer = 0;
  }
  if (typeof window !== 'undefined' && viewSwitchTimer) {
    window.clearTimeout(viewSwitchTimer);
    viewSwitchTimer = 0;
  }
  if (typeof window !== 'undefined' && aiFieldGlowTimer) {
    window.clearTimeout(aiFieldGlowTimer);
    aiFieldGlowTimer = 0;
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
  thumbnailObserver?.disconnect();
  pageThumbRefs.clear();
  previewImages.clear();
  window.clearTimeout(documentAnalysisTimer);
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
  /* Arbeitsbreite für Seitenliste, Vorschau und Formular. Im Leerzustand kleiner.
     Die Breitenänderung wird animiert, wenn die erste Seite hinzukommt. */
  width: 1200px;
  max-width: 100%;
  /* Der Overlay-Container (.v-overlay__content) verwendet die Arbeitsbreite mit
     justify:flex-start; das schmale Leer-Fenster bliebe sonst linksbündig.
     auto-Ränder zentrieren die Karte und halten sie beim Aufziehen mittig. */
  margin-inline: auto;
  transition:
    width 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    height 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    min-height 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    max-height 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Leerzustand: deutlich schmaleres Fenster (nur Dropzone). */
.isd-card--empty.pm-dialog {
  width: 680px;
  height: min(740px, 88vh) !important;
  min-height: min(740px, 88vh) !important;
  max-height: min(740px, 88vh) !important;
}

@media (max-width: 720px) {
  .isd-card--empty.pm-dialog {
    width: calc(100vw - 24px);
  }
}

.pm-no-animations .isd-card.pm-dialog {
  transition: none !important;
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

.isd-correspondent-menu .v-list {
  padding: 4px 0;
}

.isd-correspondent-menu__item.v-list-item {
  min-height: 40px;
  padding-inline: 12px 16px;
}

.isd-correspondent-menu__item .v-list-item__prepend {
  width: 28px;
  margin-inline-end: 10px;
}

.isd-correspondent-menu__item .v-list-item__spacer {
  width: 0;
}

.isd-correspondent-menu__icon {
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.isd-correspondent-menu__title {
  font-size: 0.92rem;
  line-height: 1.25;
}

.isd-correspondent-menu__meta {
  color: rgba(var(--v-theme-on-surface), 0.58);
}
</style>

<style scoped>
.isd-dropzone__available-badge { flex: none; }
.isd-dropzone__action.isd-dropzone__available-pages {
  padding: 0; gap: 0; cursor: pointer;
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 7%, rgb(var(--v-theme-surface)));
  border-color: rgba(var(--v-theme-primary), .24);
}
.isd-dropzone__available-pages:hover, .isd-dropzone__available-pages:focus-within {
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 10%, rgb(var(--v-theme-surface)));
  border-color: rgba(var(--v-theme-primary), .4);
}
.isd-dropzone__available-open {
  display: flex; align-items: center; gap: 12px; flex: 1; align-self: stretch; min-width: 0;
  padding: 11px 13px; text-align: left; font: inherit; color: inherit; cursor: pointer;
}
.isd-dropzone__available-remove {
  display: grid; place-items: center; flex: none; width: 36px; height: 36px; margin-right: 8px;
  border-radius: 9px; color: rgba(var(--v-theme-on-surface), .6); cursor: pointer;
}
.isd-dropzone__available-remove:hover:not(:disabled) { background: rgba(var(--v-theme-on-surface), .07); color: rgb(var(--v-theme-on-surface)); }
.isd-dropzone__available-open:focus-visible, .isd-dropzone__available-remove:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -3px; }
.isd-dropzone__available-remove:disabled, .isd-dropzone__available-open:disabled { opacity: .45; cursor: default; }
@media (any-pointer: coarse) { .isd-dropzone__available-remove { width: 44px; height: 44px; margin-right: 4px; } }
.isd-create-correspondent { display:flex; align-items:center; gap:12px; padding:12px 16px; width:100%; text-align:left; color:inherit; }
.isd-create-correspondent:hover, .isd-create-correspondent:focus-visible { background:rgba(var(--v-theme-on-surface), .06); }
/* ── Seitenliste, Arbeitsvorschau und Dokumentdetails ── */
.isd-body {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  --isd-bar-height: 49px;
}

.isd-left {
  --isd-rail-width: 144px;
  flex: 1 1 auto;
  min-width: 0;
  position: relative;
  display: grid;
  grid-template-columns: var(--isd-rail-width) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) var(--isd-bar-height) auto;
  grid-template-areas: 'pages preview' 'pages-footer preview' 'error error';
  min-height: 0;
  overflow: hidden;
  border-right: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
}

.isd-card--empty .isd-left { display: flex; flex-direction: column; border-right: 0; }

.isd-pages-footer {
  grid-area: pages-footer;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 0 12px;
  background: var(--pm-import-pages-footer-bg);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
  border-top: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  border-right: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
}
.isd-pages-footer strong { font-size: 12px; font-weight: 650; }
.isd-pages-footer .isd-toolbar-select-btn { margin-left: auto; }
.isd-pages-footer .isd-page-count { padding: 2px 6px; }

.isd-grid-scroll {
  grid-area: pages;
  grid-row: 1 / 3;
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  padding: 16px;
  padding-bottom: calc(16px + var(--isd-bar-height));
  scroll-padding-bottom: calc(12px + var(--isd-bar-height));
  border-right: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  background: rgba(var(--v-theme-on-surface), .018);
}
.isd-card--empty .isd-grid-scroll {
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-right: 0;
  background: transparent;
}
.isd-workspace-error { grid-area: error; }

/* ── Dropzone ── */
@keyframes isd-dz-scan {
  0% { top: 8%; opacity: 0; }
  4% { opacity: 0.82; }
  23% { top: 82%; opacity: 0.62; }
  28%, 100% { top: 86%; opacity: 0; }
}

@keyframes isd-dz-scan-active {
  0% { top: 8%; opacity: 0; }
  16% { opacity: 0.92; }
  78% { top: 82%; opacity: 0.68; }
  100% { top: 86%; opacity: 0; }
}

.isd-dropzone {
  --isd-dz-scale: 1;
  position: relative;
  width: 100%;
  flex: 1 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 30px;
  overflow: visible;
  text-align: center;
  border: 1px solid transparent;
  border-radius: 18px;
  cursor: default;
  box-sizing: border-box;
  background-color: transparent;
  transition:
    background-color 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    padding-block 320ms cubic-bezier(0.22, 1, 0.36, 1);
}

.isd-dropzone::before {
  content: '';
  position: absolute;
  inset: 18px;
  z-index: 0;
  pointer-events: none;
  opacity: 0.28;
  background:
    linear-gradient(90deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) left top / 58px 1px no-repeat,
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) left top / 1px 58px no-repeat,
    linear-gradient(270deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) right top / 58px 1px no-repeat,
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) right top / 1px 58px no-repeat,
    linear-gradient(90deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) left bottom / 58px 1px no-repeat,
    linear-gradient(0deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) left bottom / 1px 58px no-repeat,
    linear-gradient(270deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) right bottom / 58px 1px no-repeat,
    linear-gradient(0deg, rgba(var(--v-theme-primary), 0.72) 0 34px, transparent 34px) right bottom / 1px 58px no-repeat;
  transition: inset 180ms ease, opacity 180ms ease;
}

.isd-dropzone > * {
  position: relative;
  z-index: 1;
}

.isd-dropzone--over {
  border-color: rgba(var(--v-theme-primary), 0.62);
  background-color: rgba(var(--v-theme-primary), 0.05);
  box-shadow:
    inset 0 0 0 1px rgba(var(--v-theme-primary), 0.42),
    inset 0 0 72px rgba(var(--v-theme-primary), 0.06),
    0 0 54px rgba(var(--v-theme-primary), 0.12);
}

.isd-dropzone--over::before {
  inset: 13px;
  opacity: 0.88;
}

/* Grafische Papierwerkstatt (reines CSS): drei Quellen werden zu einer Seite. */
.isd-dz-scene {
  position: relative;
  width: calc(270px * var(--isd-dz-scale));
  height: calc(194px * var(--isd-dz-scale));
  max-width: 100%;
  flex: none;
  margin-bottom: 20px;
  transition:
    width 320ms cubic-bezier(0.22, 1, 0.36, 1),
    height 320ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.2, 0.82, 0.24, 1);
}

/* Die Skalierung hat eine eigene Ebene und einen gleich großen Layoutplatz.
   Einblendung und Scannerwechsel können sie dadurch nicht überschreiben. */
.isd-dz-scene__art {
  position: absolute;
  top: 0;
  left: 50%;
  width: 270px;
  height: 194px;
  transform: translateX(-50%) scale(var(--isd-dz-scale));
  transform-origin: top center;
  transition: transform 320ms cubic-bezier(0.22, 1, 0.36, 1);
}

.isd-dz-scene__halo {
  position: absolute;
  inset: 4px -22px -12px;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at center,
    rgba(var(--v-theme-primary), 0.15) 0%,
    rgba(var(--v-theme-primary), 0.06) 43%,
    transparent 72%
  );
  filter: blur(1px);
}

.isd-dz-scene__table {
  position: absolute;
  left: 26px;
  right: 20px;
  bottom: 3px;
  height: 34px;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.12);
  filter: blur(14px);
  transform: scaleY(0.48);
}

.isd-dz-sheet {
  --isd-dz-transform: translate3d(0, 0, 0);
  position: absolute;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.14);
  transform: var(--isd-dz-transform);
  transform-origin: center bottom;
  transition:
    opacity 220ms ease,
    transform 340ms cubic-bezier(0.2, 0.82, 0.24, 1),
    box-shadow 220ms ease;
}

.isd-dz-sheet--pdf {
  --isd-dz-transform: rotate(-12deg);
  left: 23px;
  top: 48px;
  z-index: 1;
  width: 105px;
  height: 132px;
  padding: 14px 12px;
  color: rgba(var(--v-theme-on-surface), 0.66);
  background: color-mix(in srgb, rgb(var(--v-theme-surface-2)) 78%, rgb(var(--v-theme-surface)));
  transition-duration: 260ms, 440ms, 220ms;
  transition-delay: 0ms, 25ms, 0ms;
}

.isd-dz-sheet--image {
  --isd-dz-transform: rotate(11deg);
  right: 20px;
  top: 39px;
  z-index: 2;
  width: 112px;
  height: 132px;
  padding: 10px;
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 6%, rgb(var(--v-theme-surface)));
  transition-duration: 280ms, 460ms, 220ms;
  transition-delay: 35ms, 70ms, 0ms;
}

.isd-dz-sheet--front {
  --isd-dz-transform: translate3d(0, 0, 0);
  left: 78px;
  top: 18px;
  z-index: 3;
  width: 118px;
  height: 152px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 17px 15px;
  background: linear-gradient(155deg, rgb(var(--v-theme-surface)), rgb(var(--v-theme-surface-2)));
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.19);
}

.isd-dz-sheet__live-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.isd-dz-sheet__live-progress {
  position: absolute;
  right: 7px;
  bottom: 7px;
  z-index: 2;
  padding: 2px 5px;
  border-radius: 999px;
  color: #fff;
  background: rgba(15, 23, 42, 0.68);
  font-size: 8px;
  font-weight: 750;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}

.isd-dz-sheet__kind {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  min-height: 19px;
  padding: 0 7px;
  border-radius: 5px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  font-size: 8px;
  font-weight: 780;
  letter-spacing: 0.08em;
}

.isd-dz-sheet__copy {
  display: grid;
  gap: 7px;
  margin-top: 13px;
}

.isd-dz-sheet__copy i,
.isd-dz-sheet__headline,
.isd-dz-sheet__caption {
  display: block;
  height: 4px;
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.15);
}

.isd-dz-sheet__copy i:nth-child(2) { width: 82%; }
.isd-dz-sheet__copy i:nth-child(3) { width: 92%; }
.isd-dz-sheet__copy i:nth-child(4) { width: 58%; }

.isd-dz-sheet__photo {
  position: relative;
  display: block;
  height: 76px;
  overflow: hidden;
  border-radius: 7px;
  background: linear-gradient(155deg, rgba(var(--v-theme-primary), 0.18), rgba(var(--v-theme-primary), 0.05));
}

.isd-dz-sheet__sun {
  position: absolute;
  top: 13px;
  right: 14px;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.6);
}

.isd-dz-sheet__mountain {
  position: absolute;
  right: -3px;
  bottom: 0;
  left: -3px;
  height: 48px;
  clip-path: polygon(0 100%, 0 76%, 26% 39%, 44% 63%, 68% 18%, 100% 67%, 100% 100%);
  background: rgba(var(--v-theme-primary), 0.22);
}

.isd-dz-sheet__mountain--front {
  height: 38px;
  clip-path: polygon(0 100%, 0 78%, 23% 40%, 39% 70%, 58% 28%, 78% 69%, 100% 48%, 100% 100%);
  background: rgba(var(--v-theme-on-surface), 0.15);
}

.isd-dz-sheet__caption {
  width: 62%;
  margin-top: 11px;
}

.isd-dz-sheet__accent {
  display: block;
  width: 61%;
  height: 7px;
  flex: none;
  border-radius: 999px;
  background: rgb(var(--v-theme-primary));
}

.isd-dz-sheet__headline {
  width: 86%;
  height: 7px;
  margin-top: 2px;
  background: rgba(var(--v-theme-on-surface), 0.26);
}

.isd-dz-sheet__copy--front {
  gap: 8px;
  margin-top: 1px;
}

.isd-dz-sheet__scan {
  position: absolute;
  top: 8%;
  right: 7px;
  left: 7px;
  height: 32px;
  pointer-events: none;
  opacity: 0;
  border-top: 1px solid rgba(var(--v-theme-primary), 0.86);
  background: linear-gradient(to bottom, rgba(var(--v-theme-primary), 0.24), transparent);
  filter: drop-shadow(0 -2px 5px rgba(var(--v-theme-primary), 0.35));
  animation: isd-dz-scan 6.2s 720ms ease-in-out infinite;
}

.isd-dz-scene__merge {
  position: absolute;
  right: 25px;
  bottom: 2px;
  z-index: 5;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: 4px solid rgb(var(--v-theme-surface));
  border-radius: 50%;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
  box-shadow: 0 7px 18px rgba(var(--v-theme-primary), 0.32);
  transition:
    opacity 160ms ease,
    transform 180ms cubic-bezier(0.2, 0.82, 0.24, 1),
    box-shadow 180ms ease;
}

.isd-dropzone--over .isd-dz-scene {
  transform: translateY(-2px);
}

.isd-dropzone--over .isd-dz-sheet--pdf {
  transform: translate3d(-15px, -7px, 0) rotate(-17deg);
}

.isd-dropzone--over .isd-dz-sheet--image {
  transform: translate3d(15px, -9px, 0) rotate(16deg);
}

.isd-dropzone--over .isd-dz-sheet--front {
  transform: translate3d(0, -9px, 0) scale(1.025);
  box-shadow: 0 23px 46px rgba(15, 23, 42, 0.22);
}

.isd-dropzone--over .isd-dz-sheet__scan {
  animation: isd-dz-scan-active 1.15s ease-in-out infinite;
}

.isd-dropzone--over .isd-dz-scene__merge {
  transform: scale(1.1) rotate(8deg);
  box-shadow: 0 9px 24px rgba(var(--v-theme-primary), 0.44);
}

.isd-dropzone--scanning::before {
  opacity: 0.5;
}

/* Der Platz der ausgeblendeten Quellen geht während des Scans an die Vorschau.
   Beide Größen ändern sich gemeinsam, ohne einen leeren Restblock zu behalten. */
.isd-dropzone--scanning .isd-dropzone__other-sources {
  grid-template-rows: 0fr;
  visibility: hidden;
  pointer-events: none;
}
.isd-dropzone--scanning .isd-dropzone__actions { row-gap: 0; }

.isd-dz-scene--scanning .isd-dz-scene__halo {
  background: radial-gradient(
    ellipse at center,
    rgba(var(--v-theme-primary), 0.2) 0%,
    rgba(var(--v-theme-primary), 0.08) 45%,
    transparent 72%
  );
}

.isd-dz-scene--scanning .isd-dz-sheet--pdf {
  opacity: 0;
  transform: translate3d(55px, -18px, 0) rotate(-2deg) scale(0.84);
}

.isd-dz-scene--scanning .isd-dz-sheet--image {
  opacity: 0;
  transform: translate3d(-60px, -12px, 0) rotate(2deg) scale(0.84);
}

.isd-dz-scene--scanning .isd-dz-sheet--front {
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.16);
}

.isd-dz-scene--scanning .isd-dz-sheet__scan {
  animation: isd-dz-scan-active 1.5s 320ms ease-in-out infinite;
}

.isd-dz-scene--complete .isd-dz-sheet__scan {
  animation: none;
  opacity: 0;
}

.isd-dz-scene--scanning .isd-dz-scene__merge {
  opacity: 0;
  transform: scale(0.72) rotate(18deg);
}

.isd-dropzone__text-shell {
  flex: none;
  width: 100%;
  min-height: 58px;
  display: grid;
  place-items: center;
}

.isd-dropzone__text {
  grid-area: 1 / 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.isd-dropzone__title {
  margin: 0;
  font-size: 20px;
  font-weight: 680;
  line-height: 1.3;
  letter-spacing: -0.018em;
  color: rgb(var(--v-theme-on-surface));
}

.isd-dropzone__subtitle {
  max-width: 440px;
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: rgb(var(--v-theme-text-muted));
}

.isd-dropzone__actions {
  flex: none;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  width: 400px;
  max-width: 100%;
  margin-top: 25px;
  transition: row-gap 320ms cubic-bezier(0.22, 1, 0.36, 1);
}

.isd-dropzone__other-sources {
  display: grid;
  grid-template-rows: 1fr;
  min-width: 0;
  transition: grid-template-rows 320ms cubic-bezier(0.22, 1, 0.36, 1);
}

.isd-dropzone__source-choices {
  display: grid;
  gap: 10px;
  min-height: 0;
  min-width: 0;
  clip-path: inset(-4px -40px);
}

.isd-dropzone__actions--single {
  width: 400px;
}

.isd-dropzone__action {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  width: 100%;
  min-width: 0;
  min-height: 68px;
  padding: 11px 13px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  border-radius: 12px;
  background: color-mix(
    in srgb,
    rgb(var(--v-theme-surface-2)) 48%,
    rgb(var(--v-theme-surface))
  );
  color: rgba(var(--v-theme-on-surface), 0.82);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.055);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    transform 160ms cubic-bezier(0.2, 0.82, 0.24, 1),
    box-shadow 160ms ease,
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.isd-dropzone__action-icon {
  width: 40px;
  height: 40px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.11);
}

.isd-dropzone__action-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.isd-dropzone__action-copy strong {
  font-size: 13.5px;
  font-weight: 680;
  line-height: 1.25;
}

.isd-dropzone__action-copy small {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.54);
  font-size: 10.5px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

button.isd-dropzone__action:hover:not(:disabled),
button.isd-dropzone__action:focus-visible {
  border-color: rgba(var(--v-theme-primary), 0.4);
  background: color-mix(
    in srgb,
    rgb(var(--v-theme-primary)) 5%,
    rgb(var(--v-theme-surface))
  );
  color: rgb(var(--v-theme-on-surface));
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.1);
  transform: translateY(-1px);
  outline: none;
}

button.isd-dropzone__action:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.48);
  outline-offset: 3px;
}

button.isd-dropzone__action:active:not(:disabled) {
  transform: translateY(0) scale(0.99);
  box-shadow: 0 2px 7px rgba(15, 23, 42, 0.08);
}

.isd-dropzone__action:disabled {
  cursor: default;
  opacity: 0.48;
  transform: none;
}

.isd-dropzone__action--scanner-active {
  border-color: rgba(var(--v-theme-primary), 0.34);
  opacity: 1;
  background: color-mix(
    in srgb,
    rgb(var(--v-theme-primary)) 7%,
    rgb(var(--v-theme-surface))
  );
  color: rgb(var(--v-theme-on-surface));
  cursor: default;
  box-shadow:
    0 0 0 1px rgba(var(--v-theme-primary), 0.08),
    0 5px 14px rgba(15, 23, 42, 0.07);
}

.isd-dropzone__action--scanner-active .isd-dropzone__action-icon {
  background: rgba(var(--v-theme-primary), 0.17);
}

.isd-dropzone__action--scanner-active .isd-dropzone__action-copy {
  flex: 1 1 auto;
}

.isd-dropzone__action--scanner-pending {
  border-color: rgba(var(--v-theme-primary), 0.46);
  background: color-mix(
    in srgb,
    rgb(var(--v-theme-primary)) 10%,
    rgb(var(--v-theme-surface))
  );
}

.isd-dropzone__scan-cancel {
  min-height: 30px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.13);
  border-radius: 8px;
  color: rgba(var(--v-theme-on-surface), 0.66);
  background: rgba(var(--v-theme-surface), 0.64);
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  cursor: pointer;
  transition: border-color 140ms ease, background-color 140ms ease, color 140ms ease;
}

.isd-dropzone__scan-cancel:hover {
  border-color: rgba(var(--v-theme-on-surface), 0.26);
  color: rgb(var(--v-theme-on-surface));
  background: rgb(var(--v-theme-surface));
}

.isd-dropzone__scan-cancel:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.48);
  outline-offset: 2px;
}

.isd-dropzone__scan-cancel:active {
  transform: scale(0.97);
}

/* ── Einspaltige Seitenliste ── */
.isd-page-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
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
  border-top: 3px solid rgb(var(--v-theme-primary));
}

.isd-page-card--drop-after .isd-page-thumb-wrap {
  border-bottom: 3px solid rgb(var(--v-theme-primary));
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
  box-sizing: border-box;
  width: 100%;
  aspect-ratio: 3 / 4;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border-radius: 4px;
  overflow: hidden;
  border: 0;
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-on-surface), 0.1);
  transition: box-shadow 0.12s;
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
  flex: 0 0 auto;
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.isd-page-card--scan-arrival {
  animation: isd-scan-thumbnail-arrive 260ms ease-out;
}

@keyframes isd-scan-thumbnail-arrive {
  from { opacity: 0; }
  to { opacity: 1; }
}

.isd-scan-thumbnail-fallback {
  position: absolute;
  top: 50%;
  left: 50%;
  translate: -50% -50%;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.isd-scan-flight-layer {
  position: fixed;
  inset: 0;
  z-index: 3200;
  pointer-events: none;
}

.isd-scan-flight {
  position: absolute;
  left: 0;
  top: 0;
  overflow: hidden;
  box-sizing: border-box;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.16);
  will-change: transform, width, height;
}

.isd-scan-flight img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
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
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
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

.isd-add-page-card--chooser .isd-add-page-thumb-wrap {
  border-color: rgba(var(--v-theme-primary), 0.38);
  background: rgba(var(--v-theme-primary), 0.045);
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

.isd-add-page-choices {
  position: absolute;
  inset: 10px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.isd-add-page-choice {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 34px;
  width: 100%;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 7px;
  background: rgba(var(--v-theme-surface), 0.86);
  color: rgba(var(--v-theme-on-surface), 0.74);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}

.isd-add-page-choice:hover:not(:disabled) {
  border-color: rgba(var(--v-theme-primary), 0.35);
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
}

.isd-add-page-choice:disabled {
  cursor: default;
  opacity: 0.44;
}

/* ── Scan-in-progress placeholder card ── */
.isd-scanning-page-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-radius: 5px;
}

.isd-scanning-page-thumb-wrap {
  position: relative;
  box-sizing: content-box;
  width: calc(100% - 4px);
  aspect-ratio: 3 / 4;
  background: rgba(var(--v-theme-primary), 0.06);
  border-radius: 4px;
  border: 2px solid rgba(var(--v-theme-primary), 0.3);
  animation: isd-scanning-pulse 1.4s ease-in-out infinite;
}

.isd-scanning-page-thumb-wrap--live {
  width: calc(100% - 2px);
  border-width: 1px;
  background: #fff;
  animation: none;
}

.isd-scanning-page-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.isd-scanning-page-progress {
  position: absolute;
  right: 6px;
  bottom: 6px;
  z-index: 2;
  min-width: 30px;
  padding: 2px 6px;
  border-radius: 999px;
  color: #fff;
  background: rgba(15, 23, 42, 0.7);
  font-size: 9px;
  font-weight: 750;
  line-height: 1.4;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.isd-scanning-page-cancel {
  position: absolute;
  top: 6px;
  right: 6px;
  min-width: 26px !important;
  width: 26px;
  height: 26px;
  color: rgba(var(--v-theme-on-surface), 0.72);
  background: rgba(var(--v-theme-surface), 0.8);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.16);
}

.isd-scanning-page-cancel:hover {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-surface), 0.96);
}

.isd-scanning-page-icon {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 28px;
  height: 28px;
  color: rgb(var(--v-theme-primary));
}

.isd-scanning-page-label {
  color: rgb(var(--v-theme-primary));
}

@keyframes isd-scanning-pulse {
  0%, 100% {
    opacity: 0.55;
    border-color: rgba(var(--v-theme-primary), 0.3);
  }
  50% {
    opacity: 1;
    border-color: rgba(var(--v-theme-primary), 0.7);
  }
}

.isd-toolbar { --pdf-toolbar-group-gap: 6px; row-gap: 6px; }
.isd-direct-tools, .isd-color-group { display: flex; align-items: center; flex: 0 0 auto; gap: 4px; }
.isd-tool-btn {
  display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto; width: 28px; height: 26px;
  border: 0; border-radius: 8px; padding: 0; background: transparent; color: var(--pdf-toolbar-icon); cursor: pointer;
}
.isd-tool-btn:hover:not(:disabled) { background: var(--pdf-toolbar-hover-bg); color: var(--pdf-toolbar-text); }
.isd-tool-btn--active { background: rgba(var(--v-theme-primary), .12); color: rgb(var(--v-theme-primary)); }
.isd-tool-btn:disabled { opacity: .3; cursor: default; }
.isd-tool-btn:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 1px; }
.isd-toolbar-select-btn--active { box-shadow: 0 0 0 3px rgba(var(--v-theme-primary), .22); }

.isd-page-card {
  position: relative;
}

.isd-ai-status-btn {
  flex-shrink: 0;
  color: rgba(var(--v-theme-on-surface), .72);
}

.isd-ai-status-ring {
  position: absolute;
  inset: 0;
  margin: auto;
}

.isd-ai-status-heading {
  display: block;
  margin-bottom: 4px;
}

.isd-page-count {
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.6);
  flex-shrink: 0;
}

/* Werkzeuggruppen umbrechen bei wenig Platz; alle Aktionen bleiben direkt erreichbar. */
@container isd-preview (max-width: 360px) {
  .isd-direct-tools > .pm-preview-toolbar__divider, .isd-color-group > .pm-preview-toolbar__divider,
  .isd-toolbar :deep(.pm-preview-toolbar__zoom-divider) { display: none; }
  .isd-toolbar { --pdf-toolbar-divider-margin: 2px; padding-inline: 4px; max-width: calc(100% - 16px); }
}

/* Rechts bleiben die Formulare unabhängig von der Seitenliste scrollbar. */
.isd-props {
  flex: 0 0 var(--isd-props-width, 360px);
  max-width: 50%;
  min-width: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* Rechte Leiste einblenden, sobald die erste Seite da ist: aus 0-Breite
   aufziehen + einblenden/hereinschieben. Umgekehrt beim Leeren. */

@keyframes isd-ai-field-glow {
  0% {
    background: rgba(var(--v-theme-primary), 0);
    box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0);
  }
  22% {
    background: rgba(var(--v-theme-primary), 0.08);
    box-shadow: 0 0 0 1px rgba(var(--v-theme-primary), 0.18), 0 10px 26px rgba(var(--v-theme-primary), 0.12);
  }
  100% {
    background: rgba(var(--v-theme-primary), 0);
    box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0);
  }
}

.isd-props-heading {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex: 0 0 auto;
  min-height: var(--isd-bar-height);
  margin: 0;
  padding: 6px 20px;
  background: rgb(var(--v-theme-surface));
  border-bottom: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  font-size: 12px;
  font-weight: 650;
}
.isd-props-title { min-width: 0; }
.isd-props-heading h3 { margin: 0; font-size: inherit; font-weight: inherit; }
.isd-props-heading p { margin: 2px 0 0; color: var(--pm-muted, #687076); font-size: 11px; font-weight: 400; }
.isd-props-heading .isd-analysis-progress { color: rgb(var(--v-theme-primary)); }

.isd-props-scroll {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 18px 20px;
}

.isd-preview-panel {
  position: relative;
  container: isd-preview / inline-size;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  grid-area: preview;
  min-width: 0;
  overflow: hidden;
  padding: 12px 8px;
  background: rgba(var(--v-theme-on-surface), .035);
}

.isd-preview-stage {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 0;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  overflow-anchor: none;
  scroll-snap-type: y mandatory;
  cursor: default;
}

.isd-preview-stage--magnify:has(.isd-preview-image:hover) {
  cursor: crosshair;
}

.isd-preview-canvas {
  position: relative;
  min-width: 100%;
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.isd-preview-pages {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding-inline: 12px;
  box-sizing: border-box;
  min-width: 100%;
}

.isd-preview-page {
  position: relative;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  scroll-snap-align: center;
}

.isd-preview-page-image {
  display: block;
  flex: 0 0 auto;
  object-fit: contain;
  filter: drop-shadow(0 4px 12px rgba(15, 23, 42, .12));
}

.isd-preview-scan-frame {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.isd-preview-scan-frame img { flex: 0 0 auto; object-fit: contain; background: #fff; }
.isd-preview-stage--scan-handoff .isd-preview-image,
.isd-preview-stage--scan-handoff .isd-preview-scan-frame { visibility: hidden; }

.isd-preview-magnifier {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  pointer-events: none;
  border: 2px solid rgba(var(--v-theme-surface), 0.96);
  border-radius: 8px;
  background-repeat: no-repeat;
  box-shadow:
    0 10px 28px rgba(15, 23, 42, 0.28),
    inset 0 0 0 1px rgba(15, 23, 42, 0.12);
  will-change: transform, background-position;
}

.isd-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: rgba(var(--v-theme-on-surface), 0.45);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}

.isd-preview-empty--illustrated {
  width: 100%;
  padding: 24px;
}

.isd-preview-empty--illustrated .document-preview-illustration { height: auto; }
.isd-preview-empty--illustrated :deep(.document-preview-illustration__canvas) {
  width: min(100%, 640px);
  min-width: 0;
  max-height: min(58vh, 520px);
  animation: none;
}

/* ── Fields ── */
/* Aufbewahrung: farblich abgehobene, fest integrierte Sektion in der Feldspalte. */

/* Formularkörper: Trenner zur Kopfzeile, gleichmäßige Flucht der Felder. */

.isd-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: -5px -8px;
  padding: 5px 8px;
  border-radius: 8px;
}

/* Neues, noch nicht angelegtes Tag: gestrichelter Rahmen + transparenter Grund,
   damit sofort erkennbar ist, dass es beim Import erst erstellt würde. */


/* ── Divider & Toggles ── */

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
  margin-left: auto;
}

.isd-footer-status {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.54);
}

/* ── Import-Button: Zustände klar differenzieren ──────────────────────────
   Deaktiviert (Analyse läuft noch oder Pflichtfelder fehlen): gedämpfte,
   neutrale Fläche mit blasser Schrift – liest sich eindeutig als inaktiv.
   Aktiviert (bereit zum Import): volle Primary-Farbe mit Hervorhebung. */
.isd-import-btn.v-btn--disabled {
  opacity: 1;
  background-color: rgba(15, 23, 42, 0.06) !important;
  color: rgba(15, 23, 42, 0.38) !important;
  box-shadow: none !important;
}

.isd-import-btn.v-theme--dark.v-btn--disabled {
  background-color: rgba(255, 255, 255, 0.07) !important;
  color: rgba(255, 255, 255, 0.40) !important;
}

.isd-import-btn.v-btn--disabled :deep(.v-btn__overlay) {
  opacity: 0 !important;
}

/* Aktivierter Zustand: deutlich als Call-to-Action erkennbar. */
.isd-import-btn:not(.v-btn--disabled) {
  font-weight: 700;
  box-shadow: 0 2px 12px rgba(var(--v-theme-primary), 0.42) !important;
}

/* Three source choices need the compact illustration at every window height.
   The start screen grows with its content; its outer area scrolls when needed. */
.isd-dropzone--available-pages {
  --isd-dz-scale: 0.72;
  padding-block: 10px;
}

.isd-dropzone--available-pages .isd-dropzone__actions {
  margin-top: 14px;
}

@media (max-height: 760px) and (min-width: 601px) {
  .isd-card--empty .isd-grid-scroll { padding: 16px; }

  .isd-dropzone {
    min-height: 430px;
    padding: 22px;
    overflow: visible;
  }

  .isd-dropzone:not(.isd-dropzone--available-pages) { --isd-dz-scale: 0.84; }

  .isd-dropzone--available-pages {
    --isd-dz-scale: 0.64;
    padding-block: 10px;
  }

  .isd-dropzone--available-pages .isd-dz-scene { margin-bottom: 16px; }

  .isd-dropzone__actions {
    margin-top: 14px;
  }

}

@media (max-width: 600px) {
  .isd-card--empty .isd-grid-scroll {
    padding: 16px;
  }

  .isd-dropzone {
    padding: 24px 18px;
    overflow: visible;
  }

  .isd-dropzone::before {
    inset: 11px;
  }

  .isd-dropzone:not(.isd-dropzone--available-pages) { --isd-dz-scale: 0.84; }

  .isd-dropzone__title {
    font-size: 18px;
  }

  .isd-dropzone__actions,
  .isd-dropzone__actions--single {
    width: min(320px, 100%);
    grid-template-columns: minmax(0, 1fr);
    margin-top: 20px;
  }

  .isd-dropzone__action {
    min-height: 62px;
  }

  .isd-footer-status {
    display: none;
  }
}

.isd-dropzone.isd-dropzone--scanning {
  --isd-dz-scale: 1.6;
  padding-block: 10px;
  min-height: 0;
}

@media (max-height: 800px) and (min-width: 601px) {
  .isd-dropzone.isd-dropzone--scanning { --isd-dz-scale: 1.35; }
}

@media (max-width: 600px) {
  .isd-dropzone.isd-dropzone--scanning { --isd-dz-scale: 1.35; }
}

@media (max-height: 660px) {
  .isd-dropzone.isd-dropzone--scanning { --isd-dz-scale: 0.6; }
  .isd-dropzone--scanning .isd-dz-scene { margin-bottom: 12px; }
}

@media (prefers-reduced-motion: reduce) {
  :global(.isd-card.pm-dialog) { transition: none; }
  .isd-dz-scene,
  .isd-dz-scene__art,
  .isd-dropzone__actions,
  .isd-dropzone__other-sources,
  .isd-dz-sheet,
  .isd-dz-scene__merge,
  .isd-dz-sheet__scan,
  .isd-page-card--scan-arrival {
    animation: none;
  }

  .isd-dz-scene,
  .isd-dz-scene__art,
  .isd-dropzone__actions,
  .isd-dropzone__other-sources,
  .isd-dz-sheet,
  .isd-dz-scene__merge,
  .isd-dropzone,
  .isd-dropzone::before,
  .isd-dropzone__action,
  .isd-page-thumb-wrap,
  .isd-scan-frame-leave-active {
    transition: none;
  }
}

:global(.pm-no-animations) .isd-dz-scene,
:global(.pm-no-animations) .isd-dz-sheet,
:global(.pm-no-animations) .isd-dz-scene__merge,
:global(.pm-no-animations) .isd-dz-sheet__scan,
:global(.pm-no-animations) .isd-page-card--scan-arrival {
  animation: none;
}

:global(.pm-no-animations) .isd-page-thumb-wrap {
  transition: none;
}

:global(.pm-no-animations) .isd-dz-scene,
:global(.pm-no-animations) .isd-dz-scene__art,
:global(.pm-no-animations) .isd-dropzone__actions,
:global(.pm-no-animations) .isd-dropzone__other-sources { transition: none; }
</style>

<style>
.isd-document-boundary { padding:12px 0 8px; border-top:1px solid var(--pm-divider-soft); font-size:11px; font-weight:600; color:var(--pm-muted); overflow-wrap:anywhere; }
.isd-document-boundary:first-child { padding-top:0; border-top:0; }
.isd-analysis-scope { display:block; margin-top:8px; font-size:12px; }
@media (min-width:961px) { .isd-card:not(.isd-card--empty) .isd-left { border-right:0; } }
@media (any-pointer:coarse) {
  .isd-card .isd-tool-btn { width:44px; height:44px; }
  .isd-card .isd-toolbar { gap:2px; padding:4px; border-radius:24px; }
  .isd-card .isd-toolbar .isd-direct-tools, .isd-card .isd-toolbar .isd-color-group { display:contents; }
  .isd-card .isd-toolbar .pm-preview-toolbar__divider { display:none; }
  .isd-card .isd-toolbar .pdf-preview__zoom-seg { width:44px; height:44px; }
  .isd-card .isd-toolbar .pdf-preview__zoom-value { min-width:44px; height:44px; }
  .isd-card .isd-ai-status-btn.v-btn, .isd-card .isd-toolbar-select-btn.v-btn,
  .isd-card .pm-dialog__close-btn.v-btn { min-width:44px; min-height:44px; width:44px; height:44px; }
  .isd-card .isd-props .pm-metadata-row { row-gap:12px; }
  .isd-card .isd-props .pm-metadata-control .v-field__input { min-height:44px; }
  .isd-card .isd-props .v-field__clearable .v-icon { width:44px; height:44px; }
  .isd-card .isd-props .pm-tags-input__chip { min-height:44px; }
  .isd-card .isd-props .pm-tags-input__chip .v-chip__close { min-width:44px; min-height:44px; }
}
.isd-review-hint, .isd-page-review { font-size:12px; color:var(--pm-muted,#687076); margin:8px 0; }
.isd-page-review { display:block; text-align:center; }
.isd-suggestion-row { display:flex; align-items:center; flex-wrap:wrap; gap:8px; min-height:34px; }
.isd-suggestion-dismiss { font-size:12px; color:var(--pm-muted,#687076); }
.isd-card .isd-props { container-type:inline-size; }
@media (max-width:1100px) and (min-width:961px) {
  .isd-card .isd-left { --isd-rail-width: 128px; }
  .isd-card .isd-props { flex-basis: var(--isd-props-width, 330px); }
}
@media (max-width:960px) {
  .isd-card:not(.isd-card--empty) .isd-body { flex-direction:column; overflow-y:auto; }
  .isd-card:not(.isd-card--empty) .isd-left { --isd-rail-width:112px; flex:0 0 clamp(280px, 45vh, 420px); width:100%; border-right:0; border-bottom:1px solid rgba(var(--v-theme-on-surface),.1); }
  .isd-card .isd-props { flex:0 0 auto; width:100%; max-width:none; min-height:0; overflow:visible; }
  .isd-card .isd-props-scroll { overflow:visible; padding:16px 20px; }
  .isd-card .isd-props-heading { min-height:42px; }
}
@media (max-width:600px) {
  .isd-card:not(.isd-card--empty) .isd-left { --isd-rail-width:88px; flex-basis:clamp(260px, 40vh, 340px); }
  .isd-card .isd-grid-scroll { padding:12px; }
  .isd-card:not(.isd-card--empty) .isd-grid-scroll { padding-bottom:calc(12px + var(--isd-bar-height)); }
  .isd-card .isd-pages-footer { justify-content:center; gap:4px; padding:0 6px; }
  .isd-card .isd-pages-footer strong { display:none; }
  .isd-card .isd-pages-footer .isd-toolbar-select-btn { margin-left:0; }
  .isd-card .isd-preview-panel { padding:10px 6px; }
  .isd-card .isd-props-scroll { padding:12px 16px; }
  .isd-card .isd-footer { flex-wrap:wrap; gap:4px; }
  .isd-card .isd-footer-end { margin-left:auto; min-width:0; flex-wrap:wrap; }
  .isd-card .isd-footer-hint { min-width:0; }
}
@media (max-width:400px) {
  .isd-card:not(.isd-card--empty) .isd-left { --isd-rail-width:76px; }
  .isd-card .isd-grid-scroll { padding-inline:10px; }
}
</style>
