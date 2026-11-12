<!--
  CorrespondentsWorkspace — Korrespondenten als eigene Ansicht unter DOKUMENTE.
  Links die Übersicht (Organisationen mit eingerückten Personen, Typfilter,
  Suche, Personen per Ziehen einer Organisation zuordnen), rechts die
  Profilblatt mit Zugehörigkeit, Dokumenten und Erkennung. Dokumente
  öffnen und „In Dokumenten zeigen“ laufen über Events des DocumentsWorkspace.
-->
<template>
  <section class="corr panel" :class="{ 'corr--has-profile': selected || isSpecialViewOpen }" aria-label="Korrespondenten">
    <!-- ── Übersicht ─────────────────────────────────────────────── -->
    <div
      ref="directoryRef"
      v-list-reveal="{ selector: '.corr-row', ready: !isDirectoryLoading, maxItems: Infinity }"
      class="corr-list"
    >
      <PmListHeader
        v-model:search="query"
        title="Korrespondenten"
        search-label="Korrespondenten durchsuchen"
        create-label="Neuer Korrespondent"
        @create="openCreateDialog"
      />
      <ListActionToolbar
        :actions="toolbarActions"
        :right-actions="cleanupActions"
        :show-selection="false"
        @action-select="handleToolbarAction"
        @right-action="isCleanupOpen = true"
      />
      <button v-if="unassignedLoadError" type="button" class="corr-link corr-list__retry" @click="loadUnassignedDocuments">
        Offene Zuordnungen erneut laden
      </button>

      <div v-if="isDirectoryLoading" class="corr-state">
        <v-progress-circular indeterminate size="22" width="2" color="primary" />
      </div>
      <div v-else-if="visibleTree.length || visibleUnassignedDocuments.length || visibleCollectionDocuments.length || visibleDuplicatePairs.length" class="corr-tree" role="tree" aria-label="Korrespondenten">
        <div v-if="visibleUnassignedDocuments.length" class="corr-inbox" role="group" aria-label="Ohne Korrespondent">
          <div
            class="corr-inbox__row"
            :class="{ 'is-selected': isUnassignedOpen }"
            role="treeitem"
            :aria-selected="isUnassignedOpen"
            aria-label="Ohne Korrespondent"
            :aria-description="unassignedCountLabel"
            tabindex="0"
            @click="openUnassigned"
            @keydown.enter.prevent="openUnassigned"
            @keydown.space.prevent="openUnassigned"
          >
            <span class="corr-inbox__icon" aria-hidden="true">
              <v-icon size="20">mdi-inbox-outline</v-icon>
            </span>
            <span class="corr-inbox__text">
              <span class="corr-inbox__title">Ohne Korrespondent</span>
              <span class="corr-inbox__subtitle">Dokumente zum Zuordnen</span>
            </span>
            <span class="corr-inbox__count" aria-hidden="true">{{ unassignedCountText }}</span>
            <v-icon class="corr-inbox__chevron" size="18" aria-hidden="true">mdi-chevron-right</v-icon>
          </div>
        </div>
        <div v-if="visibleCollectionDocuments.length" class="corr-inbox" role="group" aria-label="Genauer zuordnen">
          <div
            class="corr-inbox__row corr-inbox__row--collection"
            :class="{ 'is-selected': isCollectionReviewOpen }"
            role="treeitem"
            :aria-selected="isCollectionReviewOpen"
            aria-label="Genauer zuordnen"
            :aria-description="collectionCountLabel"
            tabindex="0"
            @click="openCollectionReview"
            @keydown.enter.prevent="openCollectionReview"
            @keydown.space.prevent="openCollectionReview"
          >
            <span class="corr-inbox__icon" aria-hidden="true">
              <v-icon size="20">mdi-shape-outline</v-icon>
            </span>
            <span class="corr-inbox__text">
              <span class="corr-inbox__title">Genauer zuordnen</span>
              <span class="corr-inbox__subtitle">Dokumente an Sammlungen</span>
            </span>
            <span class="corr-inbox__count" aria-hidden="true">{{ collectionCountText }}</span>
            <v-icon class="corr-inbox__chevron" size="18" aria-hidden="true">mdi-chevron-right</v-icon>
          </div>
        </div>
        <div v-if="visibleDuplicatePairs.length" class="corr-inbox" role="group" aria-label="Mögliche Doppelte">
          <div
            class="corr-inbox__row corr-inbox__row--dupes"
            :class="{ 'is-selected': isDuplicatesOpen }"
            role="treeitem"
            :aria-selected="isDuplicatesOpen"
            aria-label="Mögliche Doppelte"
            :aria-description="duplicateCountLabel"
            tabindex="0"
            @click="openDuplicates"
            @keydown.enter.prevent="openDuplicates"
            @keydown.space.prevent="openDuplicates"
          >
            <span class="corr-inbox__icon" aria-hidden="true">
              <v-icon size="20">mdi-source-merge</v-icon>
            </span>
            <span class="corr-inbox__text">
              <span class="corr-inbox__title">Mögliche Doppelte</span>
              <span class="corr-inbox__subtitle">Einträge zum Zusammenführen</span>
            </span>
            <span class="corr-inbox__count" aria-hidden="true">{{ visibleDuplicatePairs.length }}</span>
            <v-icon class="corr-inbox__chevron" size="18" aria-hidden="true">mdi-chevron-right</v-icon>
          </div>
        </div>
        <section v-for="section in visibleSections" :key="section.key" class="corr-section" role="group" :aria-label="section.label">
          <h3 class="corr-section__head">
            {{ section.label }}<span class="corr-section__count">{{ section.count }}</span>
          </h3>
          <ul class="corr-section__list">
            <template v-for="node in section.nodes" :key="node.id">
              <li
                class="corr-row"
                :class="{
                  'is-selected': !isSpecialViewOpen && selectedId === node.id,
                  'is-muted': node.context_only || !node.kind,
                  'is-drop-target': dropTargetId === node.id,
                  'is-draggable': isDraggable(node),
                  'is-dragging': draggedId === node.id,
                }"
                role="treeitem"
                :data-correspondent-id="node.id"
                :aria-description="kindLabel(node.kind)"
                :aria-selected="!isSpecialViewOpen && selectedId === node.id"
                :aria-expanded="node.members.length ? isExpanded(node.id) : undefined"
                :draggable="isDraggable(node)"
                :title="rowTitle(node, node.last_activity)"
                tabindex="0"
                @click="select(node.id)"
                @keydown.enter.self.prevent="select(node.id)"
                @keydown.right.prevent="setExpanded(node.id, true)"
                @keydown.left.prevent="setExpanded(node.id, false)"
                @dragstart="onDragStart($event, node)"
                @dragend="onDragEnd"
                @dragover="onDragOver($event, node)"
                @dragleave="onDragLeave(node)"
                @drop="onDrop($event, node)"
              >
                <button
                  v-if="node.members.length"
                  type="button"
                  class="corr-row__toggle"
                  :aria-label="isExpanded(node.id) ? 'Mitglieder einklappen' : 'Mitglieder ausklappen'"
                  @click.stop="toggleExpanded(node.id)"
                >
                  <v-icon size="16" aria-hidden="true">mdi-chevron-right</v-icon>
                </button>
                <span v-else class="corr-row__toggle" aria-hidden="true" />
                <v-icon class="corr-row__type" size="18" aria-hidden="true">{{ kindIcon(node.kind) }}</v-icon>
                <span class="corr-row__name" :title="rowFullName(node)">{{ rowLabel(node) }}</span>
                <span
                  v-if="node.members.length && !isExpanded(node.id)"
                  class="corr-row__chip"
                >{{ memberSummaryLabel(node.members) }}</span>
                <span class="corr-row__count" :title="countTitle(node)">{{ node.total_count }}</span>
              </li>
              <Transition name="corr-branch" @before-leave="disableClosingBranch">
                <li v-if="node.members.length && isExpanded(node.id)" class="corr-branch" role="presentation">
                  <ul class="corr-branch__rows" role="presentation">
                    <template v-for="(member, index) in node.members" :key="member.id">
                      <li
                        class="corr-row corr-row--member"
                        :class="{
                          'is-selected': !isSpecialViewOpen && selectedId === member.id,
                          'is-last': index === node.members.length - 1,
                          'is-muted': member.context_only,
                          'is-drop-target': dropTargetId === member.id,
                          'is-draggable': isDraggable(member),
                          'is-dragging': draggedId === member.id,
                          'has-toggle': hasNestedMembers(node),
                        }"
                        role="treeitem"
                        :data-correspondent-id="member.id"
                        :aria-description="kindLabel(member.kind)"
                        :aria-selected="!isSpecialViewOpen && selectedId === member.id"
                        :aria-expanded="member.members.length ? isExpanded(member.id) : undefined"
                        :title="rowTitle(member, member.last_activity)"
                        :draggable="isDraggable(member)"
                        tabindex="0"
                        @click="select(member.id)"
                        @keydown.enter.self.prevent="select(member.id)"
                        @keydown.right.prevent="setExpanded(member.id, true)"
                        @keydown.left.prevent="setExpanded(member.id, false)"
                        @dragstart="onDragStart($event, member)"
                        @dragend="onDragEnd"
                        @dragover="onDragOver($event, member)"
                        @dragleave="onDragLeave(member)"
                        @drop="onDrop($event, member)"
                      >
                        <span class="corr-row__branch" aria-hidden="true" />
                        <button
                          v-if="member.members.length"
                          type="button"
                          class="corr-row__toggle"
                          :aria-label="isExpanded(member.id) ? 'Personen einklappen' : 'Personen ausklappen'"
                          @click.stop="toggleExpanded(member.id)"
                        >
                          <v-icon size="16" aria-hidden="true">mdi-chevron-right</v-icon>
                        </button>
                        <span v-else-if="hasNestedMembers(node)" class="corr-row__toggle" aria-hidden="true" />
                        <v-icon class="corr-row__type" size="18" aria-hidden="true">{{ kindIcon(member.kind) }}</v-icon>
                        <span class="corr-row__name" :title="rowFullName(member)">{{ rowLabel(member) }}</span>
                        <span
                          v-if="member.members.length && !isExpanded(member.id)"
                          class="corr-row__chip"
                        >{{ memberSummaryLabel(member.members) }}</span>
                        <span class="corr-row__count" :title="countTitle(member)">{{ member.total_count }}</span>
                      </li>
                      <Transition name="corr-branch" @before-leave="disableClosingBranch">
                        <li v-if="member.members.length && isExpanded(member.id)" class="corr-branch" role="presentation">
                          <ul class="corr-branch__rows" role="presentation">
                            <li
                              v-for="(person, personIndex) in member.members"
                              :key="person.id"
                              class="corr-row corr-row--member corr-row--nested"
                              :class="{
                                'is-selected': !isSpecialViewOpen && selectedId === person.id,
                                'is-last': personIndex === member.members.length - 1,
                                'has-rail': index < node.members.length - 1,
                                'is-draggable': isDraggable(person),
                                'is-dragging': draggedId === person.id,
                              }"
                              role="treeitem"
                              :data-correspondent-id="person.id"
                              :aria-description="kindLabel(person.kind)"
                              :aria-selected="!isSpecialViewOpen && selectedId === person.id"
                              :title="rowTitle(person, person.last_activity)"
                              :draggable="isDraggable(person)"
                              tabindex="0"
                              @click="select(person.id)"
                              @keydown.enter.prevent="select(person.id)"
                              @dragstart="onDragStart($event, person)"
                              @dragend="onDragEnd"
                            >
                              <span class="corr-row__rail" aria-hidden="true" />
                              <span class="corr-row__branch" aria-hidden="true" />
                              <v-icon class="corr-row__type" size="18" aria-hidden="true">{{ kindIcon(person.kind) }}</v-icon>
                              <span class="corr-row__name" :title="rowFullName(person)">{{ rowLabel(person) }}</span>
                              <span class="corr-row__count">{{ person.total_count }}</span>
                            </li>
                          </ul>
                        </li>
                      </Transition>
                    </template>
                  </ul>
                </li>
              </Transition>
            </template>
          </ul>
        </section>
      </div>
      <PmEmptyState v-else v-bind="directoryEmptyState" class="corr-list__empty" role="status" />
    </div>

    <div v-if="hasOpenedUnassigned" v-show="isUnassignedOpen" class="corr-profile">
      <UnassignedCorrespondentDocuments
        :document-id="unassignedDocumentId"
        :active="isUnassignedOpen"
        :items="unassignedDocuments"
        :is-loading="isLoadingUnassigned"
        :load-error="unassignedLoadError"
        @reload="loadUnassignedDocuments"
        @resolved="onUnassignedResolved"
        @select="unassignedDocumentId = $event"
      >
        <template #back>
          <button type="button" class="corr-profile__back corr-unassigned-back corr-link" @click="backToDirectory">
            <v-icon size="16" aria-hidden="true">mdi-arrow-left</v-icon>
            Korrespondenten
          </button>
        </template>
      </UnassignedCorrespondentDocuments>
    </div>

    <div v-if="hasOpenedCollectionReview" v-show="isCollectionReviewOpen" class="corr-profile">
      <UnassignedCorrespondentDocuments
        mode="collection"
        :document-id="collectionDocumentId"
        :active="isCollectionReviewOpen"
        :items="collectionDocuments"
        :is-loading="isLoadingCollectionDocuments"
        :load-error="collectionDocumentsLoadError"
        @reload="loadCollectionDocuments"
        @resolved="onCollectionDocumentsResolved"
        @select="collectionDocumentId = $event"
      >
        <template #back>
          <button type="button" class="corr-profile__back corr-unassigned-back corr-link" @click="backToDirectory">
            <v-icon size="16" aria-hidden="true">mdi-arrow-left</v-icon>
            Korrespondenten
          </button>
        </template>
      </UnassignedCorrespondentDocuments>
    </div>

    <div v-if="isDuplicatesOpen" class="corr-profile">
      <CorrespondentDuplicatesPanel
        ref="duplicatesPanelRef"
        :pairs="visibleDuplicatePairs"
        :hidden-pairs="hiddenDuplicatePairs"
        :cleanup-count="cleanupCount"
        :busy-key="dismissingDuplicateKey"
        @merge="openMergeFor"
        @dismiss="dismissDuplicate"
        @restore="restoreDuplicate"
        @cleanup="isCleanupOpen = true"
        @open="openFromDuplicates"
      >
        <template #back>
          <button type="button" class="corr-profile__back corr-unassigned-back corr-link" @click="backToDirectory">
            <v-icon size="16" aria-hidden="true">mdi-arrow-left</v-icon>
            Korrespondenten
          </button>
        </template>
      </CorrespondentDuplicatesPanel>
    </div>

    <!-- ── Profil ────────────────────────────────────────────────── -->
    <div v-show="!isSpecialViewOpen" class="corr-profile" :aria-busy="isProfileSwitching">
      <div v-if="!selected && isProfileSwitching" class="corr-state corr-profile__loading" role="status" aria-label="Korrespondent wird geladen">
        <v-progress-circular indeterminate size="22" width="2" color="primary" />
      </div>
      <CorrespondentProfileIllustration v-else-if="!selected" />
      <template v-else>
        <header class="corr-profile__head" :inert="isProfileSwitching">
          <button ref="profileBackRef" type="button" class="corr-profile__back corr-link" @click="backToDirectory">
            <v-icon size="16" aria-hidden="true">mdi-arrow-left</v-icon>
            Korrespondenten
          </button>
          <div class="corr-avatar" :class="`corr-avatar--${selected.kind || 'untyped'}`" aria-hidden="true">
            <v-icon size="23">{{ kindIcon(selected.kind) }}</v-icon>
          </div>
          <div class="corr-profile__heading">
            <div
              v-if="isEditingPersonName"
              class="corr-profile__person-name"
              role="group"
              aria-label="Personennamen bearbeiten"
              @keydown.enter="submitPersonNameOnEnter"
              @keydown.esc.stop.prevent="closePersonName()"
              @focusout="onPersonNameFocusOut"
              @input="personNameInvalid = false"
            >
              <div class="corr-profile__person-name-fields">
                <label>
                  Vorname
                  <input
                    ref="personNameInputRef"
                    v-model="personNameDraft.firstName"
                    class="corr-profile__name corr-profile__name-input"
                    type="text"
                    maxlength="120"
                    :readonly="isSaving"
                  >
                </label>
                <label>
                  Nachname
                  <input
                    v-model="personNameDraft.lastName"
                    class="corr-profile__name corr-profile__name-input"
                    type="text"
                    maxlength="120"
                    :readonly="isSaving"
                  >
                </label>
              </div>
              <p v-if="personNameInvalid" class="corr-profile__person-name-hint corr-profile__person-name-error" role="alert">
                Der vollständige Name muss 2 bis 120 Zeichen lang sein.
              </p>
              <p v-else-if="!hasStoredPersonName" class="corr-profile__person-name-hint">
                Bitte prüfe die vorgeschlagene Aufteilung.
              </p>
            </div>
            <input
              v-else-if="isRenaming"
              ref="renameInputRef"
              v-model="renameValue"
              class="corr-profile__name corr-profile__name-input"
              type="text"
              maxlength="120"
              aria-label="Name des Korrespondenten"
              @keydown.enter.prevent="commitRename"
              @keydown.esc.prevent="cancelRename"
              @blur="commitRename"
            >
            <h1 v-else class="corr-profile__name">
              <button ref="profileNameRef" type="button" class="corr-profile__name-btn" :title="`Vollständigen Namen bearbeiten: ${selected.name}`" @click="startRename">{{ rowLabel(selected) }}</button>
            </h1>
            <div class="corr-profile__meta corr-muted">
              <template v-if="profile">
                <span class="corr-profile__meta-value">{{ documentCountLabel(profile.document_count) }}</span>
                <span v-if="inheritedDocumentCount" class="corr-profile__meta-value">{{ profile.own_document_count }} direkt, {{ inheritedDocumentCount }} über {{ membersWord }}</span>
                <span v-if="periodRange" class="corr-profile__meta-value">{{ periodRange }}</span>
              </template>
              <span>
                <button
                  ref="profileKindRef"
                  type="button"
                  class="corr-profile__meta-action"
                  :aria-label="`Typ ändern: ${kindLabel(selected.kind)}`"
                  aria-haspopup="dialog"
                  :aria-expanded="isKindDialogOpen"
                  :disabled="isSaving"
                  @click="openKindDialog"
                >
                  <v-icon size="13" aria-hidden="true">{{ kindIcon(selected.kind) }}</v-icon>
                  {{ kindLabel(selected.kind) }}
                </button>
              </span>
              <span v-if="!isCollection">
                <button
                  ref="shortNameButtonRef"
                  type="button"
                  class="corr-profile__meta-action"
                  :aria-label="selected.short_name ? `Kurzname bearbeiten: ${selected.short_name}` : 'Kurzname hinzufügen'"
                  :aria-expanded="isShortNameOpen"
                  :disabled="isSaving"
                  aria-haspopup="dialog"
                  title="Kurzname bearbeiten"
                  @click="openShortName"
                >
                  <v-icon size="13" aria-hidden="true">mdi-pencil-outline</v-icon>
                  <span class="corr-profile__short-name">Kurzname</span>
                </button>
              </span>
            </div>
          </div>
          <v-btn
            v-if="canMergeSelected"
            ref="profileMergeRef"
            class="pm-header-icon-btn corr-profile-action"
            variant="outlined"
            icon="mdi-source-merge"
            :disabled="isSaving || correspondentStore.isMutationRunning"
            aria-label="Zusammenführen …"
            aria-haspopup="dialog"
            title="Mit einem anderen Eintrag zusammenführen"
            @click="openMerge()"
          />
          <v-btn
            ref="profileActionRef"
            class="pm-header-icon-btn corr-profile-action"
            variant="outlined"
            :icon="profileAction.icon"
            :disabled="isSaving || correspondentStore.isMutationRunning"
            :aria-label="profileAction.label"
            aria-haspopup="dialog"
            :title="profileAction.label"
            @click="openProfileAction"
          />
        </header>
        <div ref="profileScrollRef" class="corr-profile__scroll" :inert="isProfileSwitching">
          <div class="corr-sheet">
            <section v-if="isCollection" class="corr-collection" aria-labelledby="corr-members-title">
              <PmInfoHeading
                title="Mitglieder"
                heading-id="corr-members-title"
                :reset-key="selectedId"
                info-label="Was sind Mitglieder?"
              >
                <p>Eine Sammlung bündelt Organisationen und Personen zu einem Thema. Die Dokumente ihrer Mitglieder erscheinen auch in der Sammlung.</p>
                <p>Das Band zeigt, wie viele Dokumente von welchem Mitglied stammen. Eine Kachel klappt die Dokumente des Mitglieds hier auf; ein Klick auf ein Dokument zeigt es groß in einer Vorschau.</p>
              </PmInfoHeading>
              <p v-if="documentsFailed && !profile" class="corr-muted corr-empty" role="status">
                Mitglieder konnten nicht geladen werden.
                <button type="button" class="corr-link" :disabled="isLoadingProfile" @click="reloadSelected">Erneut versuchen</button>
              </p>
              <template v-else>
                <CollectionShareBand
                  v-if="collectionShareVisible"
                  class="corr-collection__band"
                  :collection-id="selected.id"
                  :summaries="collectionSummaries"
                  :active-id="openMemberId"
                  @select="toggleCollectionMember"
                />
                <CollectionMemberTiles
                  ref="memberTilesRef"
                  :key="selected.id"
                  :collection-id="selected.id"
                  :collection-name="rowLabel(selected)"
                  :summaries="collectionSummaries"
                  :disabled="isSaving"
                  @open-change="openMemberId = $event"
                  @open-profile="selectFromProfile"
                  @remove="detachMemberById"
                >
                  <template #add>
                    <CorrespondentConnectionMenu
                      :key="selectedId"
                      :correspondent="selected"
                      :options="connectKinds"
                      :find-candidates="findConnectCandidates"
                      :candidate-initials="initials"
                      :save-connection="connectTo"
                      :disabled="isSaving"
                    >
                      <template #activator="{ props: menuProps }">
                        <button v-bind="menuProps" type="button" class="corr-placeholder corr-placeholder--collection" :disabled="isSaving" aria-label="Mitglied hinzufügen">
                          <span class="corr-placeholder__badge" aria-hidden="true">
                            <v-icon size="22">mdi-account-plus</v-icon>
                          </span>
                          <span class="corr-placeholder__title">Mitglied hinzufügen</span>
                          <span class="corr-placeholder__hint">Person oder Organisation auswählen</span>
                        </button>
                      </template>
                    </CorrespondentConnectionMenu>
                  </template>
                </CollectionMemberTiles>
              </template>
            </section>

            <section v-if="!isCollection" aria-labelledby="corr-docs-title">
              <div class="corr-section-head">
                <h2 id="corr-docs-title">Dokumente</h2>
                <button v-if="documentTotal" type="button" class="corr-link corr-section-action" @click="showDocuments">
                  {{ documentTotal === 1 ? 'In Dokumenten zeigen' : `Alle ${documentTotal} anzeigen` }}
                  <v-icon size="15" aria-hidden="true">mdi-arrow-right</v-icon>
                </button>
              </div>
              <p v-if="documentsFailed" class="corr-muted corr-empty" role="status">
                Dokumente konnten nicht geladen werden.
                <button type="button" class="corr-link" :disabled="isLoadingProfile" @click="reloadSelected">Erneut versuchen</button>
              </p>
              <!-- Eine waagerecht scrollende Reihe; ein Klick öffnet eine große Vorschau als Overlay. -->
              <CorrespondentDocumentGrid
                v-else
                :key="selected.id"
                layout="row"
                :documents="documents"
                :total="documentsResultTotal"
                :loading-more="isLoadingMoreDocuments"
                :load-more-failed="moreDocumentsFailed"
                :label="`Dokumente von ${rowLabel(selected)}`"
                show-type
                @load-more="loadMoreDocuments"
              >
                <template #empty>
                  <p class="corr-empty corr-docs-empty">
                    <span class="corr-docs-empty__badge" aria-hidden="true">
                      <v-icon size="16">mdi-file-document-outline</v-icon>
                    </span>
                    Keine Dokumente zugeordnet
                  </p>
                </template>
              </CorrespondentDocumentGrid>
            </section>

            <section class="corr-profile-data" aria-label="Profildaten">
              <section v-if="!isCollection" class="corr-section-info" aria-labelledby="corr-structure-title">
                <PmInfoHeading
                  :title="structureTitle"
                  heading-id="corr-structure-title"
                  :reset-key="selectedId"
                  :info-label="isCollection ? 'Was sind Mitglieder?' : 'Was sind Zugehörigkeiten?'"
                >
                  <template v-if="selected.kind" #default>
                    <p v-if="isCollection">Eine Sammlung bündelt Organisationen und Personen zu einem Thema. Die Dokumente ihrer Mitglieder erscheinen auch in der Sammlung.</p>
                    <template v-else>
                      <p v-if="selected.kind === 'organization'">Hier siehst du, zu welcher Sammlung die Organisation gehört und welche Personen ihr zugeordnet sind.</p>
                      <p v-else>Hier siehst du, zu welcher Organisation oder Sammlung die Person gehört.</p>
                      <p>Auch Verbindungen wie Nachfolge oder Aufträge stehen hier.</p>
                    </template>
                  </template>
                </PmInfoHeading>

                <ul class="corr-structure" :class="{ 'corr-structure--tiles': showStructureTiles }">
                  <template v-if="selected.kind || structureConnections.length">
                    <CorrespondentProfileRow
                      v-if="selectedParent"
                      :name="rowLabel(selectedParent)"
                      :icon="kindIcon(selectedParent.kind)"
                      :subtitle="kindLabel(selectedParent.kind)"
                      :remove-label="`Zuordnung zu ${rowLabel(selectedParent)} lösen`"
                      :tile="showStructureTiles"
                      :disabled="isSaving"
                      @open="selectFromProfile(selectedParent.id)"
                      @remove="detachFromParent(selected)"
                    />
                    <CorrespondentProfileRow
                      v-for="member in selectedMembers"
                      :key="member.id"
                      :name="rowLabel(member)"
                      :icon="kindIcon(member.kind)"
                      :subtitle="kindLabel(member.kind)"
                      :count-label="memberCounts.has(member.id) ? documentCountLabel(memberCounts.get(member.id)) : ''"
                      :remove-label="`Zuordnung von ${rowLabel(member)} lösen`"
                      :tile="showStructureTiles"
                      :disabled="isSaving"
                      @open="selectFromProfile(member.id)"
                      @remove="detachFromParent(member)"
                    />
                    <CorrespondentProfileRow
                      v-for="item in structureConnections"
                      :key="item.key"
                      :name="item.name"
                      :icon="kindIcon(item.kind)"
                      :subtitle="item.label"
                      :remove-label="`Verbindung zu ${item.name} entfernen`"
                      :tile="showStructureTiles"
                      :disabled="isSaving"
                      @open="selectFromProfile(item.id)"
                      @remove="removeConnection(item)"
                    />
                  </template>
                  <li class="corr-structure__add-action">
                    <button
                      v-if="!selected.kind"
                      type="button"
                      class="corr-placeholder"
                      aria-haspopup="dialog"
                      :aria-expanded="isKindDialogOpen"
                      :disabled="isSaving"
                      @click="openKindDialog"
                    >
                      <v-icon size="16" aria-hidden="true">mdi-plus</v-icon>
                      Typ festlegen
                    </button>
                    <CorrespondentConnectionMenu
                      v-else
                      :key="selectedId"
                      :correspondent="selected"
                      :options="connectKinds"
                      :find-candidates="findConnectCandidates"
                      :candidate-initials="initials"
                      :save-connection="connectTo"
                      :disabled="isSaving"
                    >
                      <template #activator="{ props: menuProps }">
                        <button
                          v-bind="menuProps"
                          type="button"
                          class="corr-placeholder"
                          :class="{ 'corr-placeholder--affiliation-chip': !showStructureTiles }"
                          :disabled="isSaving"
                        >
                          <v-icon size="16" aria-hidden="true">mdi-plus</v-icon>
                          {{ isCollection ? 'Mitglied hinzufügen' : 'Zugehörigkeit hinzufügen' }}
                        </button>
                      </template>
                    </CorrespondentConnectionMenu>
                  </li>
                </ul>

              </section>

              <section v-if="isCollection && connectionItems.length" class="corr-section-info" aria-labelledby="corr-connections-title">
                <PmInfoHeading
                  title="Verbindungen"
                  heading-id="corr-connections-title"
                  :reset-key="selectedId"
                  info-label="Was bedeuten die Verbindungen?"
                >
                  <p><strong>Nachfolge</strong> verbindet einen früheren Namen mit dem heutigen, etwa nach einer Fusion. <strong>Auftrag</strong> zeigt, wer für wen handelt, etwa eine Hausverwaltung oder ein Inkassobüro.</p>
                  <p>Über das X kannst du eine bestehende Verbindung lösen.</p>
                </PmInfoHeading>
                <ul class="corr-structure">
                  <CorrespondentProfileRow
                    v-for="item in connectionItems"
                    :key="item.key"
                    :name="item.name"
                    :icon="kindIcon(item.kind)"
                    :subtitle="item.label"
                    :remove-label="`Verbindung zu ${item.name} entfernen`"
                    :disabled="isSaving"
                    @open="selectFromProfile(item.id)"
                    @remove="removeConnection(item)"
                  />
                </ul>
              </section>

              <CorrespondentRecognition :key="selected.id" class="corr-section-info" :correspondent="selected" heading-id="corr-recognition-title" />

              <section aria-labelledby="corr-note-section-title">
                <div class="corr-section-head">
                  <h2 id="corr-note-section-title">Notiz</h2>
                </div>
                <textarea
                  v-if="isEditingNote"
                  ref="noteInputRef"
                  v-model="noteValue"
                  class="corr-note corr-note--input"
                  :class="{ 'corr-note--full-width': selected.notes }"
                  cols="28"
                  rows="3"
                  maxlength="2000"
                  aria-label="Notiz zum Korrespondenten"
                  :readonly="isSaving"
                  @keydown.esc.prevent="!isSaving && cancelNote(true)"
                  @keydown.meta.enter.prevent="commitNote"
                  @keydown.ctrl.enter.prevent="commitNote"
                  @blur="commitNote"
                />
                <button
                  v-else
                  ref="noteButtonRef"
                  type="button"
                  class="corr-note"
                  :class="{ 'corr-note--empty corr-placeholder': !selected.notes }"
                  :disabled="isSaving"
                  @click="startNote"
                >
                  <template v-if="selected.notes">{{ selected.notes }}</template>
                  <template v-else>
                    <v-icon size="16" aria-hidden="true">mdi-plus</v-icon>
                    <span>Notiz hinzufügen</span>
                  </template>
                </button>
              </section>
            </section>
          </div>
        </div>
      </template>
    </div>

    <CorrespondentCleanupDialog v-model="isCleanupOpen" />

    <CorrespondentMergeDialog
      v-if="mergeSubject"
      v-model="isMergeOpen"
      :correspondent="mergeSubject"
      :initial-other-id="mergeOtherId"
      @merged="onMerged"
      @update:model-value="!$event && restoreMergeFocus()"
    />

    <BaseDialog
      :model-value="isProfileActionOpen"
      :title="profileActionTitle"
      :aria-label="profileActionTitle"
      :description="profileActionDescription"
      :variant="isUnlinkAction ? 'confirm' : 'destructive'"
      :icon="isUnlinkAction ? 'mdi-link-off' : 'mdi-trash-can-outline'"
      :primary-text="isUnlinkAction ? 'Zuordnungen lösen' : 'Löschen'"
      :primary-disabled="!isUnlinkAction && directDocumentCount > 0"
      :loading="isSaving"
      :persistent="isSaving"
      @update:model-value="closeProfileAction"
      @primary="applyProfileAction"
    >
      <p v-if="profileActionError" class="corr-kind-error" role="alert">{{ profileActionError }}</p>
    </BaseDialog>

    <BaseDialog
      v-if="selected"
      :model-value="isKindDialogOpen"
      :title="selected.kind ? 'Typ ändern' : 'Typ festlegen'"
      :aria-label="selected.kind ? 'Typ ändern' : 'Typ festlegen'"
      :header-subtitle="rowLabel(selected)"
      primary-text="Typ übernehmen"
      :primary-disabled="!canApplyKind"
      :loading="isSaving"
      :persistent="isSaving"
      max-width="510"
      @update:model-value="closeKindDialog"
      @after-enter="focusKindChoice"
      @primary="applyKind"
    >
      <div ref="kindOptionsRef" class="corr-kind-options" role="radiogroup" aria-label="Korrespondententyp">
        <label
          v-for="option in kindChoices"
          :key="option.value"
          class="corr-kind-option"
          :class="{ 'is-selected': draftKind === option.value, 'is-unavailable': option.reason }"
        >
          <input
            v-model="draftKind"
            type="radio"
            name="corr-profile-kind"
            :value="option.value"
            :disabled="isSaving || Boolean(option.reason)"
            :aria-labelledby="`corr-kind-label-${option.value}`"
            :aria-describedby="`corr-kind-detail-${option.value}`"
            @change="kindError = ''"
          >
          <span class="corr-kind-option__icon"><v-icon size="22" aria-hidden="true">{{ option.icon }}</v-icon></span>
          <span class="corr-kind-option__text">
            <span class="corr-kind-option__heading">
              <strong :id="`corr-kind-label-${option.value}`">{{ option.label }}</strong>
              <span v-if="selected.kind === option.value" class="corr-kind-option__current">Aktuell</span>
            </span>
            <span :id="`corr-kind-detail-${option.value}`" class="corr-kind-option__detail">
              {{ option.description }}
              <span v-if="option.reason" class="corr-kind-option__reason">
                <v-icon size="13" aria-hidden="true">mdi-lock-outline</v-icon>
                {{ option.reason }}
              </span>
            </span>
          </span>
        </label>
      </div>
      <CorrespondentPersonNameFields
        v-if="draftKind === 'person' && selected.kind !== 'person'"
        v-model:first-name="kindPersonName.firstName"
        v-model:last-name="kindPersonName.lastName"
        class="mt-3"
        :disabled="isSaving"
        @submit="applyKind"
      />
      <p v-if="kindLosesParent" class="corr-kind-notice" role="status">
        Die Zuordnung zu <strong>{{ correspondentParentName(selected, correspondentStore.findById) || 'einem übergeordneten Eintrag' }}</strong> wird beim Wechsel gelöst.
      </p>
      <p v-if="kindError" class="corr-kind-error" role="alert">{{ kindError }}</p>
    </BaseDialog>


    <BaseDialog
      v-model="isShortNameOpen"
      title="Kurzname bearbeiten"
      description="Der Kurzname wird in PaperMind und in Dateinamen verwendet, wenn er hinterlegt ist."
      primary-text="Speichern"
      :loading="isSaving"
      :persistent="isSaving"
      @primary="commitShortName"
      @close="focusShortNameButton"
    >
      <v-text-field
        v-model="shortNameDraft"
        label="Kurzname"
        maxlength="60"
        density="comfortable"
        variant="outlined"
        hide-details
        autofocus
        :readonly="isSaving"
        @keydown.enter.prevent="commitShortName"
      />
    </BaseDialog>

    <BaseDialog
      v-model="isCreateOpen"
      title="Neuer Korrespondent"
      icon="mdi-account-plus"
      :primary-text="createSuggestions.length && !createHasExactMatch ? 'Trotzdem anlegen' : 'Anlegen'"
      :loading="isCreating"
      :primary-disabled="!validCorrespondentName(createNamePayload.name) || createHasExactMatch || !correspondentStore.isLoaded"
      :persistent="isCreating"
      max-width="520"
      card-class="corr-create-dialog"
      @primary="submitCreate"
    >
      <!-- Kein <form>: Safari merkt sich sonst abgeschickte Werte und bietet sie als AutoFill an. -->
      <div class="corr-create">
        <div class="corr-filter corr-filter--segment" role="group" aria-label="Typ wählen">
          <button
            v-for="option in typeOptions"
            :key="option.value"
            type="button"
            class="corr-filter__btn"
            :class="{ 'is-active': createKind === option.value }"
            :aria-pressed="createKind === option.value"
            :disabled="isCreating"
            @click="setCreateKind(option.value)"
          ><v-icon v-if="option.icon" size="14">{{ option.icon }}</v-icon>{{ option.label }}</button>
        </div>
        <CorrespondentPersonNameFields
          v-if="createKind === 'person'"
          v-model:first-name="createPersonName.firstName"
          v-model:last-name="createPersonName.lastName"
          :disabled="isCreating"
          autofocus
          @submit="submitCreate"
        />
        <v-text-field
          v-else
          v-model="createName"
          :disabled="isCreating"
          label="Name"
          maxlength="120"
          density="comfortable"
          variant="outlined"
          hide-details="auto"
          name="pm-correspondent-search"
          autocomplete="off"
          autofocus
          @keydown.enter.prevent="submitCreate"
        />
        <CorrespondentSuggestions
          v-if="isCreateOpen"
          :matches="createSuggestions"
          :name="createNamePayload.name"
          :exact="createHasExactMatch"
          :busy="isCreating"
          @use="useExistingCorrespondent"
          @alias="useExistingCorrespondent($event, true)"
        />
        <v-text-field
          v-if="createKind !== 'collection'"
          :model-value="createShortName"
          :disabled="isCreating"
          label="Kurzname (optional)"
          maxlength="60"
          density="comfortable"
          variant="outlined"
          name="pm-correspondent-short-search"
          autocomplete="off"
          :hint="createShortNameHint"
          :persistent-hint="Boolean(createShortNameHint)"
          :hide-details="!createShortNameHint"
          @update:model-value="setCreateShortName"
          @keydown.enter.prevent="submitCreate"
        />
        <p v-if="!correspondentStore.isLoaded" role="status">
          {{ correspondentStore.isLoading ? 'Korrespondenten werden geprüft …' : 'Korrespondenten konnten nicht geladen werden.' }}
          <v-btn v-if="!correspondentStore.isLoading" variant="text" size="small" @click="correspondentStore.fetchCorrespondents()">Erneut versuchen</v-btn>
        </p>
        <button
          v-if="canCreateWithParent && !showCreateParent"
          type="button"
          class="corr-link corr-create__parent-link"
          :disabled="isCreating"
          @click="openCreateParent"
        ><v-icon size="16" aria-hidden="true">mdi-plus</v-icon>Gehört zu …</button>
        <v-select
          v-else-if="canCreateWithParent"
          ref="createParentRef"
          v-model="createParentId"
          :disabled="isCreating"
          :items="createParentOptions"
          :item-title="rowLabel"
          item-value="id"
          label="Gehört zu"
          no-data-text="Keine passenden Einträge"
          density="comfortable"
          variant="outlined"
          clearable
          hide-details
        />
      </div>
    </BaseDialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import BaseDialog from '../components/BaseDialog.vue';
import CorrespondentSuggestions from '../components/CorrespondentSuggestions.vue';
import { findCorrespondentSuggestions } from '../utils/correspondentSuggestions.js';
import { splitLegalForm } from '../utils/legalForms.js';
import CorrespondentConnectionMenu from '../components/CorrespondentConnectionMenu.vue';
import CorrespondentPersonNameFields from '../components/CorrespondentPersonNameFields.vue';
import CorrespondentProfileIllustration from '../components/CorrespondentProfileIllustration.vue';
import CorrespondentProfileRow from '../components/CorrespondentProfileRow.vue';
import CorrespondentDocumentGrid from '../components/CorrespondentDocumentGrid.vue';
import CorrespondentRecognition from '../components/CorrespondentRecognition.vue';
import ListActionToolbar from '../components/ListActionToolbar.vue';
import PmEmptyState from '../components/PmEmptyState.vue';
import PmInfoHeading from '../components/PmInfoHeading.vue';
import PmListHeader from '../components/PmListHeader.vue';
import UnassignedCorrespondentDocuments from '../components/UnassignedCorrespondentDocuments.vue';
import { listDocuments } from '../api/documents.js';
import { addCorrespondentRelation, deleteCorrespondentRelation, getCorrespondentProfile, listCollectionDocuments, listUnresolvedCorrespondents } from '../api/correspondents.js';
import { vListReveal } from '../directives/listReveal.js';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { mapApiError, notifyError } from '../stores/notifications.js';
import CorrespondentMergeDialog from '../components/CorrespondentMergeDialog.vue';
import CorrespondentCleanupDialog from '../components/CorrespondentCleanupDialog.vue';
import { cleanupSuggestionCount, findCleanupSuggestions } from '../utils/correspondentCleanup.js';
import { canMergeCorrespondents, findDuplicatePairs } from '../utils/correspondentDuplicates.js';
import CorrespondentDuplicatesPanel from '../components/CorrespondentDuplicatesPanel.vue';
import { useSettingsStore } from '../stores/settings.js';
import { getBaseUrl } from '../api/client.js';
import { animateInlinePlaceholderResize } from '../utils/inlinePlaceholderMotion.js';
import { personNameParts, personNamePayload, validCorrespondentName } from '../utils/correspondentPersonName.js';
import {
  CORRESPONDENT_CONNECTION_ROLES,
  CORRESPONDENT_KIND_META,
  CORRESPONDENT_SORT_OPTIONS,
  canAssignToParent,
  connectionCandidates as findConnectionCandidates,
  connectionKindOptions,
  correspondentKindIcon,
  correspondentKindLabel,
  filterCorrespondentTree,
  groupCorrespondentTree,
  memberSummaryLabel,
  sortCorrespondentTree,
  correspondentDisplayName,
  correspondentParentName,
} from '../utils/correspondentHierarchy.js';
import { collectionMemberSummaries } from '../utils/correspondentProfileStats.js';
import CollectionMemberTiles from '../components/CollectionMemberTiles.vue';
import CollectionShareBand from '../components/CollectionShareBand.vue';

const props = defineProps({
  selectedId: { type: String, default: null },
});
const emit = defineEmits(['update:selectedId', 'show-documents', 'open-document', 'documents-changed']);

const correspondentStore = useCorrespondentStore();
const RECENT_DOCUMENT_LIMIT = 12;

const query = ref('');
const kindFilter = ref('all');
const expanded = ref(new Set());
const displayedProfileId = ref(null);
const profile = ref(null);
const documents = ref([]);
const documentsResultTotal = ref(0);
const documentsFailed = ref(false);
const documentOffset = ref(0);
const hasMoreDocuments = computed(() => documentOffset.value < documentsResultTotal.value);
const isLoadingMoreDocuments = ref(false);
const moreDocumentsFailed = ref(false);
const isLoadingProfile = ref(false);
const isSaving = ref(false);
const draggedId = ref(null);
const dropTargetId = ref(null);
const directoryRef = ref(null);
const profileBackRef = ref(null);
const profileScrollRef = ref(null);
const profileNameRef = ref(null);
const profileKindRef = ref(null);
const profileActionRef = ref(null);
let profileSeq = 0;
let focusNameAfterSwitch = false;

const typeDescriptions = {
  organization: 'Firma, Behörde oder Verein. Kann Personen enthalten.',
  person: 'Einzelner Kontakt, bei Bedarf einer Organisation oder Sammlung zugeordnet.',
  collection: 'Bündelt Organisationen und Personen zu einem Thema.',
};
const typeOptions = Object.entries(CORRESPONDENT_KIND_META).map(([value, meta]) => ({
  value,
  ...meta,
  description: typeDescriptions[value],
}));

const sortBy = ref('name');
const activityFilter = ref('all');

const KIND_FILTER_OPTIONS = [
  { value: 'all', label: 'Alle Typen' },
  { value: 'organization', label: 'Organisationen' },
  { value: 'person', label: 'Personen' },
  { value: 'collection', label: 'Sammlungen' },
  { value: 'untyped', label: 'Ohne Typ' },
];
const ACTIVITY_FILTER_OPTIONS = [
  { value: 'all', label: 'Jede Aktivität' },
  { value: 'active', label: 'Kontakt in 12 Monaten' },
  { value: 'dormant', label: 'Länger als 1 Jahr still' },
  { value: 'empty', label: 'Ohne Dokumente' },
];
const optionLabel = (options, value) => options.find((o) => o.value === value)?.label || options[0].label;

const toolbarActions = computed(() => [
  {
    key: 'sort',
    icon: 'mdi-sort',
    label: optionLabel(CORRESPONDENT_SORT_OPTIONS, sortBy.value),
    value: sortBy.value,
    options: CORRESPONDENT_SORT_OPTIONS,
    minWidth: 190,
  },
  {
    key: 'kind',
    icon: 'mdi-shape-outline',
    label: kindFilter.value === 'all' ? 'Typ' : optionLabel(KIND_FILTER_OPTIONS, kindFilter.value),
    value: kindFilter.value,
    active: kindFilter.value !== 'all',
    collapsible: kindFilter.value === 'all',
    options: KIND_FILTER_OPTIONS,
    minWidth: 180,
  },
  {
    key: 'activity',
    icon: 'mdi-calendar-range',
    label: activityFilter.value === 'all' ? 'Aktivität' : optionLabel(ACTIVITY_FILTER_OPTIONS, activityFilter.value),
    value: activityFilter.value,
    active: activityFilter.value !== 'all',
    collapsible: activityFilter.value === 'all',
    options: ACTIVITY_FILTER_OPTIONS,
    minWidth: 210,
  },
]);
const isUnassignedOpen = ref(false);
const hasOpenedUnassigned = ref(false);
const UNASSIGNED_LIMIT = 50;
const unassignedDocuments = ref([]);
const isLoadingUnassigned = ref(false);
const unassignedLoadError = ref(false);
const unassignedDocumentId = ref(null);
const visibleUnassignedDocuments = computed(() => {
  const term = query.value.trim().toLocaleLowerCase('de-DE');
  return term ? unassignedDocuments.value.filter(doc => [doc.title, doc.original_filename, doc.sender]
    .some(value => value?.toLocaleLowerCase('de-DE').includes(term))) : unassignedDocuments.value;
});

function handleToolbarAction({ action, value }) {
  if (action === 'sort') sortBy.value = value;
  else if (action === 'kind') kindFilter.value = value;
  else if (action === 'activity') activityFilter.value = value;
}
const unassignedCountText = computed(() => {
  const count = visibleUnassignedDocuments.value.length;
  return count === UNASSIGNED_LIMIT ? `${count}+` : String(count);
});
const unassignedCountLabel = computed(() => {
  const count = visibleUnassignedDocuments.value.length;
  return `${unassignedCountText.value} ${count === 1 ? 'Dokument' : 'Dokumente'} zum Zuordnen`;
});
let lastUnassignedDocumentId = null;

function openUnassignedDocument(id) {
  isDuplicatesOpen.value = false;
  isCollectionReviewOpen.value = false;
  hasOpenedUnassigned.value = true;
  isUnassignedOpen.value = true;
  unassignedDocumentId.value = id;
}
watch(unassignedDocumentId, id => { if (id) lastUnassignedDocumentId = id; });

function openUnassigned() {
  // Resume where the user left off; otherwise start with the first (search) match.
  const visible = visibleUnassignedDocuments.value;
  const resume = visible.find(doc => doc.document_id === lastUnassignedDocumentId);
  const target = resume ?? visible[0];
  openUnassignedDocument(target?.document_id ?? null);
}

async function loadUnassignedDocuments() {
  if (isLoadingUnassigned.value) return;
  isLoadingUnassigned.value = true;
  unassignedLoadError.value = false;
  try {
    // Vorhandene Korrespondenten zuerst: das Backend sucht sie im Absender und im Dokumenttext.
    const result = await listUnresolvedCorrespondents({ limit: UNASSIGNED_LIMIT, excerptChars: 0, suggest: true });
    replaceUnassignedDocuments(result.items ?? []);
  } catch {
    unassignedLoadError.value = true;
  } finally {
    isLoadingUnassigned.value = false;
  }
}

function replaceUnassignedDocuments(documents) {
  const id = unassignedDocumentId.value;
  const previousIndex = unassignedDocuments.value.findIndex(doc => doc.document_id === id);
  unassignedDocuments.value = documents;
  if (isUnassignedOpen.value && !documents.some(doc => doc.document_id === id)) {
    const nextIndex = Math.max(0, Math.min(previousIndex, documents.length - 1));
    unassignedDocumentId.value = documents[nextIndex]?.document_id ?? null;
  }
}

// ── Genauer zuordnen: Dokumente direkt an Sammlungen (wie „Ohne Korrespondent“) ──
const isCollectionReviewOpen = ref(false);
const hasOpenedCollectionReview = ref(false);
const collectionDocuments = ref([]);
const isLoadingCollectionDocuments = ref(false);
const collectionDocumentsLoadError = ref(false);
const collectionDocumentId = ref(null);
let lastCollectionDocumentId = null;
const visibleCollectionDocuments = computed(() => {
  const term = query.value.trim().toLocaleLowerCase('de-DE');
  return term ? collectionDocuments.value.filter(doc => [doc.title, doc.original_filename, doc.sender, doc.correspondent_name]
    .some(value => value?.toLocaleLowerCase('de-DE').includes(term))) : collectionDocuments.value;
});
const collectionCountText = computed(() => {
  const count = visibleCollectionDocuments.value.length;
  return count === UNASSIGNED_LIMIT ? `${count}+` : String(count);
});
const collectionCountLabel = computed(() => {
  const count = visibleCollectionDocuments.value.length;
  return `${collectionCountText.value} ${count === 1 ? 'Dokument' : 'Dokumente'} direkt an Sammlungen`;
});
watch(collectionDocumentId, id => { if (id) lastCollectionDocumentId = id; });

function openCollectionDocument(id) {
  isUnassignedOpen.value = false;
  isDuplicatesOpen.value = false;
  hasOpenedCollectionReview.value = true;
  isCollectionReviewOpen.value = true;
  collectionDocumentId.value = id;
}

function openCollectionReview() {
  const visible = visibleCollectionDocuments.value;
  const target = visible.find(doc => doc.document_id === lastCollectionDocumentId) ?? visible[0];
  openCollectionDocument(target?.document_id ?? null);
}

async function loadCollectionDocuments() {
  if (isLoadingCollectionDocuments.value) return;
  isLoadingCollectionDocuments.value = true;
  collectionDocumentsLoadError.value = false;
  try {
    const result = await listCollectionDocuments({ limit: UNASSIGNED_LIMIT });
    replaceCollectionDocuments(result.items ?? []);
  } catch {
    collectionDocumentsLoadError.value = true;
  } finally {
    isLoadingCollectionDocuments.value = false;
  }
}

function replaceCollectionDocuments(documents) {
  const id = collectionDocumentId.value;
  const previousIndex = collectionDocuments.value.findIndex(doc => doc.document_id === id);
  collectionDocuments.value = documents;
  if (isCollectionReviewOpen.value && !documents.some(doc => doc.document_id === id)) {
    const nextIndex = Math.max(0, Math.min(previousIndex, documents.length - 1));
    collectionDocumentId.value = documents[nextIndex]?.document_id ?? null;
  }
}

function onCollectionDocumentsResolved(ids, assigned) {
  const resolved = new Set(Array.isArray(ids) ? ids : [ids]);
  replaceCollectionDocuments(collectionDocuments.value.filter(doc => !resolved.has(doc.document_id)));
  void loadCollectionDocuments();
  if (assigned) {
    emit('documents-changed');
    void correspondentStore.fetchCorrespondents();
    if (props.selectedId) void reloadSelected();
  }
}

function onUnassignedResolved(ids, assigned) {
  const resolved = new Set(Array.isArray(ids) ? ids : [ids]);
  replaceUnassignedDocuments(unassignedDocuments.value.filter(doc => !resolved.has(doc.document_id)));
  void loadUnassignedDocuments();
  // Wer einer Sammlung zugeordnet wurde, erscheint unter „Genauer zuordnen“.
  void loadCollectionDocuments();
  if (assigned) {
    emit('documents-changed');
    void correspondentStore.fetchCorrespondents();
    if (props.selectedId) void reloadSelected();
  }
}

const visibleTree = computed(() =>
  sortCorrespondentTree(
    filterCorrespondentTree(correspondentStore.tree, {
      kind: kindFilter.value,
      query: query.value,
      searchAliases: settingsStore.settings.ui.correspondent_search_aliases,
      activity: activityFilter.value,
    }),
    sortBy.value,
  )
);
const rowLabel = correspondentDisplayName;
const rowFullName = (correspondent) => {
  const label = rowLabel(correspondent);
  return label !== correspondent.name ? correspondent.name : undefined;
};
const isDirectoryLoading = computed(() => !correspondentStore.isLoaded && correspondentStore.isLoading);
const directoryEmptyState = computed(() => correspondentStore.correspondents.length
  ? { icon: 'mdi-magnify', title: 'Keine Korrespondenten gefunden', subtitle: 'Passe die Suche oder die Filter an.' }
  : {
    icon: 'mdi-account-group-outline',
    title: 'Noch keine Korrespondenten',
    subtitle: 'Lege über das Plus eine Person, Organisation oder Sammlung an.',
  });
const byName = (a, b) => rowLabel(a).localeCompare(rowLabel(b), 'de-DE');
/** Mögliche übergeordnete Einträge für einen Typ: Person → Organisation/Sammlung, Organisation → Sammlung. */
const parentCandidatesFor = (kind) =>
  correspondentStore.correspondents
    .filter((c) => c.kind === 'collection' || (kind === 'person' && c.kind === 'organization'))
    .slice()
    .sort(byName);
const createParentOptions = computed(() => parentCandidatesFor(createKind.value));
const isCollection = computed(() => selected.value?.kind === 'collection');
const membersWord = computed(() => (isCollection.value ? 'Mitglieder' : 'Personen'));
const structureTitle = computed(() => {
  if (isCollection.value) return 'Mitglieder';
  return selected.value?.kind ? 'Zugehörigkeiten' : 'Einordnung';
});
const isProfileSwitching = computed(() => Boolean(props.selectedId) && displayedProfileId.value !== props.selectedId);
const selected = computed(() => correspondentStore.findById(displayedProfileId.value));
const selectedParent = computed(() =>
  selected.value?.parent_id ? correspondentStore.findById(selected.value.parent_id) : null
);
const selectedMembers = computed(() =>
  correspondentStore.membersOf(displayedProfileId.value).sort(byName)
);

// Zusammenführen: wahrscheinliche Doppel im Profil anbieten, Ziel/Quelle im Dialog wählen.
const isMergeOpen = ref(false);
const mergeOtherId = ref(null);
// Beim Öffnen festgehalten: wird der angezeigte Eintrag selbst zusammengeführt,
// verschwindet er aus dem Store – der Dialog muss sein Ergebnis trotzdem melden.
const mergeSubject = ref(null);
const profileMergeRef = ref(null);
const canMergeSelected = computed(() =>
  Boolean(selected.value) && correspondentStore.correspondents.some(entry => canMergeCorrespondents(entry, selected.value))
);
function openMerge(otherId = null) {
  if (!selected.value || isSaving.value || correspondentStore.isMutationRunning) return;
  mergeOtherId.value = otherId;
  mergeSubject.value = selected.value;
  isMergeOpen.value = true;
}
let mergeCompleted = false;
// Mögliche Doppelte: eigene Kachel wie „Ohne Korrespondent“; „Kein Doppel“ merkt sich das Paar je Benutzer.
const settingsStore = useSettingsStore();
const isDuplicatesOpen = ref(false);
const isSpecialViewOpen = computed(() => isUnassignedOpen.value || isDuplicatesOpen.value || isCollectionReviewOpen.value);
const duplicatesPanelRef = ref(null);
const dismissingDuplicateKey = ref('');
const duplicateDismissals = computed(() => settingsStore.settings?.ui?.correspondent_duplicate_dismissals || []);
const duplicatePairs = computed(() => (correspondentStore.isLoaded
  ? findDuplicatePairs(correspondentStore.correspondents, duplicateDismissals.value)
  : []));
// Als „Kein Doppel“ markierte Paare, die es noch gibt (zum Wiederanzeigen).
const hiddenDuplicatePairs = computed(() => {
  if (!correspondentStore.isLoaded || !duplicateDismissals.value.length) return [];
  const dismissed = new Set(duplicateDismissals.value);
  return findDuplicatePairs(correspondentStore.correspondents, []).filter(pair => dismissed.has(pair.key));
});
const visibleDuplicatePairs = computed(() => {
  const term = query.value.trim().toLocaleLowerCase('de-DE');
  return term
    ? duplicatePairs.value.filter(pair => [pair.a.name, pair.b.name].some(name => name.toLocaleLowerCase('de-DE').includes(term)))
    : duplicatePairs.value;
});
const duplicateCountLabel = computed(() => {
  const count = visibleDuplicatePairs.value.length;
  return count === 1 ? '1 Paar zum Prüfen' : `${count} Paare zum Prüfen`;
});
async function openDuplicates() {
  isUnassignedOpen.value = false;
  isCollectionReviewOpen.value = false;
  isDuplicatesOpen.value = true;
  await nextTick();
  duplicatesPanelRef.value?.focusTitle();
}
function openFromDuplicates(id) {
  void select(id, true);
}
async function dismissDuplicate(key) {
  if (dismissingDuplicateKey.value) return;
  dismissingDuplicateKey.value = key;
  try {
    await settingsStore.patchSettings(getBaseUrl(), {
      ui: { correspondent_duplicate_dismissals: [...duplicateDismissals.value, key] },
    });
  } catch (error) {
    notifyError(error, 'Die Markierung konnte nicht gespeichert werden.');
  } finally {
    dismissingDuplicateKey.value = '';
  }
}

async function restoreDuplicate(key) {
  if (dismissingDuplicateKey.value) return;
  dismissingDuplicateKey.value = key;
  try {
    await settingsStore.patchSettings(getBaseUrl(), {
      ui: { correspondent_duplicate_dismissals: duplicateDismissals.value.filter(entry => entry !== key) },
    });
  } catch (error) {
    notifyError(error, 'Das Paar konnte nicht wieder angezeigt werden.');
  } finally {
    dismissingDuplicateKey.value = '';
  }
}

// Aufräumen: Kurznamen nachtragen, leere Einträge löschen, Doppelte zusammenführen.
const isCleanupOpen = ref(false);
const cleanupCount = computed(() => (correspondentStore.isLoaded
  ? cleanupSuggestionCount(findCleanupSuggestions(correspondentStore.correspondents, correspondentStore.membersOf))
  : 0));
const cleanupActions = computed(() => (cleanupCount.value
  ? [{ key: 'cleanup', icon: 'mdi-broom', label: String(cleanupCount.value), ariaLabel: `Aufräumen: ${cleanupCount.value} Vorschläge` }]
  : []));
function openMergeFor({ subjectId, otherId }) {
  const subject = correspondentStore.findById(subjectId);
  if (!subject) return;
  mergeOtherId.value = otherId;
  mergeSubject.value = subject;
  isMergeOpen.value = true;
}
function restoreMergeFocus() {
  // Nach dem Zusammenführen übernimmt das (neue) Profil den Fokus.
  if (mergeCompleted) { mergeCompleted = false; return; }
  nextTick(() => profileMergeRef.value?.$el?.focus());
}
function onMerged(targetId) {
  mergeCompleted = true;
  // In der Doppelte-Ansicht bleiben: das nächste Paar wartet schon.
  if (isDuplicatesOpen.value) return;
  if (targetId !== props.selectedId) void select(targetId, true);
  else void reloadSelected();
}

const isProfileActionOpen = ref(false);
const pendingProfileAction = ref(null);
const profileActionError = ref('');
const directDocumentCount = computed(() => profile.value?.own_document_count ?? Number(selected.value?.usage_count || 0));
const profileAction = computed(() => directDocumentCount.value > 0
  ? { kind: 'unlink', label: 'Zuordnung lösen', icon: 'mdi-link-off' }
  : { kind: 'delete', label: 'Löschen', icon: 'mdi-trash-can-outline' }
);
const isUnlinkAction = computed(() => pendingProfileAction.value?.kind === 'unlink');
const profileActionTitle = computed(() => {
  if (isUnlinkAction.value) return 'Dokumentzuordnungen lösen?';
  const kind = pendingProfileAction.value?.correspondent.kind;
  return `${kind ? kindLabel(kind) : 'Korrespondent'} löschen?`;
});
const profileActionDescription = computed(() => {
  const action = pendingProfileAction.value;
  if (!action) return '';
  const name = rowLabel(action.correspondent);
  if (isUnlinkAction.value) {
    return `Alle direkten Dokumentzuordnungen zu „${name}“ werden gelöst. Die Dokumente bleiben erhalten.`;
  }
  return [
    `„${name}“ wird dauerhaft gelöscht.`,
    selectedMembers.value.length ? 'Die direkt zugeordneten Einträge und deren Dokumente bleiben erhalten. Ihre Zugehörigkeit zu diesem Profil wird gelöst.' : '',
    relations.value.length ? 'Die fachlichen Verbindungen dieses Profils werden entfernt.' : '',
  ].filter(Boolean).join(' ');
});

function openProfileAction() {
  if (!selected.value || isSaving.value || correspondentStore.isMutationRunning) return;
  profileActionError.value = '';
  pendingProfileAction.value = { kind: profileAction.value.kind, correspondent: selected.value };
  isProfileActionOpen.value = true;
}

function closeProfileAction() {
  if (isSaving.value) return;
  isProfileActionOpen.value = false;
  nextTick(() => profileActionRef.value?.$el?.focus());
}

async function applyProfileAction() {
  const action = pendingProfileAction.value;
  if (!isProfileActionOpen.value || !action || isSaving.value || correspondentStore.isMutationRunning) return;
  const { id } = action.correspondent;
  const unlink = action.kind === 'unlink';
  if (props.selectedId !== id || (!unlink && directDocumentCount.value)) return;
  isSaving.value = true;
  profileActionError.value = '';
  try {
    if (unlink) await correspondentStore.unlinkDocuments(id);
    else await correspondentStore.deleteCorrespondent(id);
  } catch (error) {
    if (isProfileActionOpen.value && pendingProfileAction.value === action) {
      profileActionError.value = mapApiError(error, unlink
        ? 'Dokumentzuordnungen konnten nicht gelöst werden.'
        : 'Der Korrespondent konnte nicht gelöscht werden.');
      if (error?.status === 409) reloadSelected();
    }
    return;
  } finally {
    isSaving.value = false;
  }
  if (props.selectedId !== id) return;
  if (unlink) {
    reloadSelected();
    closeProfileAction();
  } else {
    isProfileActionOpen.value = false;
    await backToDirectory();
  }
}

const isKindDialogOpen = ref(false);
const draftKind = ref(null);
const kindPersonName = ref(personNameParts({}));
const kindError = ref('');
const kindOptionsRef = ref(null);
let kindDialogTrigger = null;
const kindChoices = computed(() => typeOptions.map((option) => ({
  ...option,
  reason: kindChangeBlock(option.value),
})));
const canApplyKind = computed(() =>
  draftKind.value !== selected.value?.kind
  && kindChoices.value.some((option) => option.value === draftKind.value && !option.reason)
  && (draftKind.value !== 'person' || validCorrespondentName(personNamePayload(kindPersonName.value).name))
);
const kindLosesParent = computed(() =>
  Boolean(selected.value?.parent_id && canApplyKind.value
    && !canAssignToParent({ id: selected.value.id, kind: draftKind.value }, selectedParent.value))
);

function kindChangeBlock(kind) {
  if (kind === 'person' && selectedMembers.value.length) return 'Löse zuerst die Zuordnung der Mitglieder.';
  if (kind === 'organization' && selectedMembers.value.some((member) => member.kind === 'organization')) {
    return 'Löse zuerst die Zuordnung der Organisationen.';
  }
  return '';
}

function openKindDialog(event) {
  kindDialogTrigger = event.currentTarget;
  draftKind.value = selected.value.kind;
  kindPersonName.value = personNameParts(selected.value);
  kindError.value = '';
  isKindDialogOpen.value = true;
}

function closeKindDialog() {
  isKindDialogOpen.value = false;
  const trigger = kindDialogTrigger;
  kindDialogTrigger = null;
  nextTick(() => (trigger?.isConnected ? trigger : profileKindRef.value)?.focus());
}

function focusKindChoice() {
  const choices = kindOptionsRef.value;
  const input = choices?.querySelector('input:checked') || choices?.querySelector('input:not(:disabled)');
  input?.focus();
}

watch(() => props.selectedId, () => {
  kindDialogTrigger = null;
  isKindDialogOpen.value = false;
  isProfileActionOpen.value = false;
});

// Organisationen starten eingeklappt; Suche/Filter klappen sie auf, damit
// Treffer sichtbar sind.
const isExpanded = (id) =>
  Boolean(query.value.trim()) || kindFilter.value !== 'all' || activityFilter.value !== 'all' || expanded.value.has(id);
function setExpanded(id, open) {
  if (expanded.value.has(id) === open) return;
  const next = new Set(expanded.value);
  if (open) next.add(id); else next.delete(id);
  expanded.value = next;
}
function toggleExpanded(id) {
  setExpanded(id, !expanded.value.has(id));
}
function disableClosingBranch(branch) {
  branch.inert = true;
}
// Ausgewählter Eintrag bleibt sichtbar: alle übergeordneten Einträge aufklappen.
watch(
  () => {
    const parent = correspondentStore.findById(correspondentStore.findById(props.selectedId)?.parent_id);
    return [parent?.id, parent?.parent_id].filter(Boolean).join(',');
  },
  (chain) => { for (const id of chain ? chain.split(',') : []) setExpanded(id, true); },
  { immediate: true }
);

const visibleSections = computed(() => groupCorrespondentTree(visibleTree.value));
const hasNestedMembers = (node) => node.members.some((m) => m.members.length);
function countTitle(node) {
  if (!node.members.length) return undefined;
  const via = node.kind === 'collection' ? 'Mitglieder' : 'Personen';
  return `${node.own_count} direkt, ${node.total_count - node.own_count} über ${via}`;
}
function rowTitle(c, lastDate) {
  return lastDate ? `Letzter Kontakt: ${formatShortDate(lastDate)}` : undefined;
}

async function select(id, focusProfile = false) {
  isUnassignedOpen.value = false;
  isDuplicatesOpen.value = false;
  isCollectionReviewOpen.value = false;
  unassignedDocumentId.value = null;
  focusNameAfterSwitch = focusProfile;
  emit('update:selectedId', id);
  await nextTick();
  if (displayedProfileId.value === id) focusSelectedProfile(focusProfile);
}

function focusSelectedProfile(focusName) {
  if (profileBackRef.value?.getClientRects().length) profileBackRef.value.focus();
  else if (focusName) profileNameRef.value?.focus();
}

function selectFromProfile(id) {
  void select(id, true);
}

async function backToDirectory() {
  const row = directoryRef.value?.querySelector('[aria-selected="true"]');
  isUnassignedOpen.value = false;
  isDuplicatesOpen.value = false;
  isCollectionReviewOpen.value = false;
  unassignedDocumentId.value = null;
  collectionDocumentId.value = null;
  emit('update:selectedId', null);
  await nextTick();
  const target = row?.isConnected ? row : directoryRef.value?.querySelector('input');
  target?.focus();
}

// ── Neuer Korrespondent ──────────────────────────────────────────────────
const isCreateOpen = ref(false);
const isCreating = ref(false);
const createName = ref('');
const createPersonName = ref(personNameParts({}));
const createKind = ref('organization');
// Kurzname: bei Organisationen automatisch der Name ohne Rechtsform, bis man ihn selbst ändert.
const createShortName = ref('');
const createShortNameTouched = ref(false);
const createLegalForm = computed(() => (createKind.value === 'organization' ? splitLegalForm(createName.value) : { legalForm: null }));
const createShortNameHint = computed(() =>
  !createShortNameTouched.value && createLegalForm.value.legalForm && createShortName.value
    ? `Vorschlag ohne Rechtsform ${createLegalForm.value.legalForm}`
    : ''
);
watch(createLegalForm, ({ base, legalForm }) => {
  if (!createShortNameTouched.value) createShortName.value = legalForm ? base.slice(0, 60).trimEnd() : '';
});
function setCreateShortName(value) {
  createShortNameTouched.value = true;
  createShortName.value = value ?? '';
}
const createParentId = ref(null);
const showCreateParent = ref(false);
const createParentRef = ref(null);
// Only offer the link when there is something to belong to.
const canCreateWithParent = computed(() => (createKind.value === 'person' || createKind.value === 'organization')
  && createParentOptions.value.length > 0);
const createNamePayload = computed(() =>
  createKind.value === 'person' ? personNamePayload(createPersonName.value) : { name: createName.value }
);

const createSuggestions = computed(() => findCorrespondentSuggestions(correspondentStore.correspondents, createNamePayload.value.name));
const createHasExactMatch = computed(() => createSuggestions.value.some(match => match.exact));

async function useExistingCorrespondent(id, addAlias = false) {
  if (isCreating.value) return;
  isCreating.value = true;
  try {
    if (addAlias && !(await correspondentStore.addAlias(id, createNamePayload.value.name))?.ok) return;
    isCreateOpen.value = false;
    query.value = '';
    void select(id);
  } catch {
    // Fehlermeldung zeigt der Store; der Dialog bleibt geöffnet.
  } finally { isCreating.value = false; }
}

function openCreateDialog() {
  void correspondentStore.ensureLoaded();
  createName.value = query.value.trim();
  createShortNameTouched.value = false;
  createShortName.value = '';
  createPersonName.value = personNameParts({});
  createKind.value = 'organization';
  createParentId.value = null;
  showCreateParent.value = false;
  isCreateOpen.value = true;
}

function setCreateKind(kind) {
  if (createKind.value === kind) return;
  const personName = personNamePayload(createPersonName.value).name;
  if (createKind.value === 'person') createName.value = personName;
  if (kind === 'person' && createName.value !== personName) {
    createPersonName.value = personNameParts({ name: createName.value });
  }
  createKind.value = kind;
}

async function openCreateParent() {
  showCreateParent.value = true;
  await nextTick();
  createParentRef.value?.focus();
  if (createParentRef.value) createParentRef.value.menu = true;
}

async function submitCreate() {
  if (isCreating.value || !validCorrespondentName(createNamePayload.value.name) || createHasExactMatch.value || !correspondentStore.isLoaded) return;
  isCreating.value = true;
  try {
    const { name, ...nameParts } = createNamePayload.value;
    // Ausdrücklich mitsenden (auch null), damit das Backend keinen eigenen Vorschlag setzt.
    const short_name = createKind.value === 'collection' ? undefined : (createShortName.value.replace(/\s+/gu, ' ').trim() || null);
    const result = await correspondentStore.createCorrespondentByName(name, { kind: createKind.value, ...nameParts, short_name });
    if (!result?.ok) return;
    if ((createKind.value === 'person' || createKind.value === 'organization') && createParentId.value) {
      await correspondentStore.updateCorrespondent(result.id, { parent_id: createParentId.value }, { silent: true });
    }
    isCreateOpen.value = false;
    query.value = '';
    void select(result.id);
  } catch {
    // Fehlermeldung zeigt der Store.
  } finally {
    isCreating.value = false;
  }
}

const kindIcon = (kind) => correspondentKindIcon(kind) || 'mdi-help-circle-outline';
const kindLabel = (kind) => correspondentKindLabel(kind);

function initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || '') + (parts.length > 1 ? parts.at(-1)[0] : parts[0]?.[1] || '')).toUpperCase() || '?';
}

function parseDate(iso) {
  if (!iso) return null;
  const d = new Date(String(iso).length <= 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? null : d;
}
function formatShortDate(iso) {
  const d = parseDate(iso);
  return d ? d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '–';
}
const yearOf = (iso) => parseDate(iso)?.getFullYear() || '';

const inheritedDocumentCount = computed(() =>
  profile.value ? profile.value.document_count - profile.value.own_document_count : 0
);
const periodRange = computed(() => yearSpan(profile.value?.first_document_date, profile.value?.last_document_date));
const activity = computed(() => profile.value?.activity || []);
const documentTotal = computed(() => profile.value?.document_count ?? documentsResultTotal.value);

// Sammlung: Kacheln je Mitglied und Anteilsband teilen dieselbe Auswertung.
const collectionSummaries = computed(() =>
  // Mitglieder aus dem Store: neu zugeordnete erscheinen sofort, auch ohne Dokumente.
  collectionMemberSummaries(activity.value, selectedMembers.value, {
    ownId: profile.value?.correspondent?.id,
    parentOf: (id) => correspondentStore.findById(id)?.parent_id || null,
  })
);
const collectionShareVisible = computed(() => {
  const { rows, direct } = collectionSummaries.value;
  return rows.filter((row) => row.count > 0).length + (direct.count ? 1 : 0) > 1;
});
const memberTilesRef = ref(null);
const openMemberId = ref(null);
watch(() => props.selectedId, () => { openMemberId.value = null; });
function toggleCollectionMember(id) {
  memberTilesRef.value?.toggleMember(id);
}
function detachMemberById(id) {
  const member = selectedMembers.value.find((entry) => entry.id === id);
  if (member) detachFromParent(member);
}

function yearSpan(first, last) {
  const a = yearOf(first);
  const b = yearOf(last);
  if (!a || !b) return a || b || '';
  return a === b ? String(a) : `${a}–${b}`;
}

function documentCountLabel(n) {
  return `${n} ${n === 1 ? 'Dokument' : 'Dokumente'}`;
}

const memberCounts = computed(() => new Map((profile.value?.members || []).map((m) => [m.id, m.document_count])));
const relations = computed(() => profile.value?.relations || []);
const connectionItems = computed(() => relations.value.map((relation) => {
  const role = CORRESPONDENT_CONNECTION_ROLES.find((item) => item.value === relation.role);
  const other = correspondentStore.findById(relation.other_id) ?? {
    name: relation.other_name,
    short_name: relation.other_short_name,
    kind: relation.other_kind,
  };
  return {
    key: relation.id,
    id: relation.other_id,
    name: rowLabel(other),
    kind: other.kind,
    label: [
      role?.label,
      relation.role === 'predecessor' && yearSpan(relation.first_document_date, relation.last_document_date),
      relation.document_count ? documentCountLabel(relation.document_count) : '',
    ].filter(Boolean).join(' · '),
  };
}));
const structureConnections = computed(() => isCollection.value ? [] : connectionItems.value);
const showStructureTiles = computed(() => Boolean(selected.value?.kind
  && (selectedParent.value || selectedMembers.value.length || structureConnections.value.length)));

const connectKinds = computed(() => connectionKindOptions(selected.value, relations.value));

function findConnectCandidates(role, query) {
  const linkedRelations = role === 'member'
    ? [...relations.value, ...selectedMembers.value.map(member => ({ role, other_id: member.id }))]
    : relations.value;
  return findConnectionCandidates(selected.value, role, correspondentStore.correspondents, linkedRelations, query).sort(byName);
}

async function connectTo(candidate, role) {
  if (!selected.value || isSaving.value || isProfileSwitching.value) return false;
  const current = selected.value;
  let ok;
  if (role === 'parent') {
    ok = await saveCorrespondent(current.id, { parent_id: candidate.id });
  } else if (role === 'member') {
    ok = await saveCorrespondent(candidate.id, { parent_id: current.id });
  } else {
    isSaving.value = true;
    try {
      await addCorrespondentRelation(current.id, { role, other_id: candidate.id });
      ok = true;
    } finally {
      isSaving.value = false;
    }
  }
  if (ok && props.selectedId === current.id) reloadSelected();
  return ok;
}

async function removeConnection(item) {
  if (!selected.value || isSaving.value) return;
  isSaving.value = true;
  try {
    await deleteCorrespondentRelation(selected.value.id, item.key);
  } catch (error) {
    console.warn('Verbindung konnte nicht entfernt werden:', error?.message || error);
  } finally {
    isSaving.value = false;
  }
  reloadSelected();
}

function fetchRecentDocuments(id, offset = 0) {
  return listDocuments(new URLSearchParams({
    correspondent_id: id,
    correspondent_members: 'true',
    sort: 'correspondent_date',
    order: 'desc',
    limit: String(RECENT_DOCUMENT_LIMIT),
    offset: String(offset),
  }).toString());
}

async function loadMoreDocuments() {
  const id = props.selectedId;
  if (!id || displayedProfileId.value !== id || !hasMoreDocuments.value || isLoadingProfile.value || isLoadingMoreDocuments.value) return;
  const seq = profileSeq;
  isLoadingMoreDocuments.value = true;
  try {
    const result = await fetchRecentDocuments(id, documentOffset.value);
    if (seq !== profileSeq) return;

    const items = result.items || [];
    const loadedIds = new Set(documents.value.map(doc => doc.id));
    documents.value = [...documents.value, ...items.filter(doc => !loadedIds.has(doc.id))];
    documentOffset.value += items.length;
    documentsResultTotal.value = items.length ? Number(result.total ?? documentOffset.value) : documentOffset.value;
    moreDocumentsFailed.value = false;
  } catch {
    if (seq === profileSeq) moreDocumentsFailed.value = true;
  } finally {
    if (seq === profileSeq) isLoadingMoreDocuments.value = false;
  }
}

async function reloadSelected() {
  const id = props.selectedId;
  const seq = ++profileSeq;
  isLoadingMoreDocuments.value = false;
  moreDocumentsFailed.value = false;
  if (!id) {
    displayedProfileId.value = null;
    profile.value = null;
    documents.value = [];
    documentsResultTotal.value = 0;
    documentOffset.value = 0;
    documentsFailed.value = false;
    isLoadingProfile.value = false;
    focusNameAfterSwitch = false;
    return;
  }
  isLoadingProfile.value = true;
  // Profil und Dokumente gemeinsam anzeigen, damit beim Wechsel keine Zwischenstände aufblitzen.
  const [profileResult, documentsResult] = await Promise.allSettled([
    getCorrespondentProfile(id),
    fetchRecentDocuments(id),
  ]);
  if (seq !== profileSeq || props.selectedId !== id) return;

  const switching = displayedProfileId.value !== id;
  profile.value = profileResult.status === 'fulfilled' ? profileResult.value : null;
  documents.value = documentsResult.value?.items || [];
  documentOffset.value = documents.value.length;
  documentsResultTotal.value = Number(documentsResult.value?.total ?? documents.value.length);
  documentsFailed.value = documentsResult.status === 'rejected';
  if (profileResult.status === 'rejected') {
    console.warn('Korrespondenten-Profil konnte nicht geladen werden:', profileResult.reason?.message || profileResult.reason);
  }
  if (documentsFailed.value) {
    console.warn('Dokumente des Korrespondenten konnten nicht geladen werden:', documentsResult.reason?.message || documentsResult.reason);
  }
  displayedProfileId.value = id;
  isLoadingProfile.value = false;
  if (switching) {
    await nextTick();
    if (props.selectedId !== id) return;
    if (profileScrollRef.value) profileScrollRef.value.scrollTop = 0;
    if (!isSpecialViewOpen.value) focusSelectedProfile(focusNameAfterSwitch);
  }
}

watch(() => props.selectedId, reloadSelected, { immediate: true });

function showDocuments() {
  if (!selected.value) return;
  emit('show-documents', { id: selected.value.id, includeMembers: true });
}

async function saveCorrespondent(id, payload) {
  if (isSaving.value) return false;
  isSaving.value = true;
  try {
    const result = await correspondentStore.updateCorrespondent(id, payload);
    return Boolean(result?.ok);
  } finally {
    isSaving.value = false;
  }
}

// ── Namen im Kopf direkt bearbeiten ───────────────────────────────────────
const isShortNameOpen = ref(false);
const shortNameDraft = ref('');
const shortNameButtonRef = ref(null);

function openShortName() {
  if (!selected.value || isCollection.value) return;
  shortNameDraft.value = selected.value.short_name || '';
  isShortNameOpen.value = true;
}

function focusShortNameButton() {
  nextTick(() => shortNameButtonRef.value?.focus());
}

async function commitShortName() {
  if (!isShortNameOpen.value || isSaving.value || !selected.value || isCollection.value) return;
  const { id, short_name: previous } = selected.value;
  const shortName = String(shortNameDraft.value || '').trim() || null;
  try {
    if (shortName !== (previous || null) && !await saveCorrespondent(id, { short_name: shortName })) return;
    isShortNameOpen.value = false;
    focusShortNameButton();
  } catch {
    // Der Store meldet den Fehler. Die Eingabe bleibt offen.
  }
}

watch(() => props.selectedId, () => { isShortNameOpen.value = false; });

const isRenaming = ref(false);
const renameValue = ref('');
const renameInputRef = ref(null);
const isEditingPersonName = ref(false);
const personNameDraft = ref(personNameParts({}));
const personNameInputRef = ref(null);
const personNameInvalid = ref(false);
const hasStoredPersonName = computed(() => selected.value?.first_name != null || selected.value?.last_name != null);

function startRename() {
  if (!selected.value || isSaving.value) return;
  if (selected.value.kind === 'person') {
    personNameDraft.value = personNameParts(selected.value);
    personNameInvalid.value = false;
    isEditingPersonName.value = true;
    nextTick(() => {
      personNameInputRef.value?.focus();
      personNameInputRef.value?.select();
    });
    return;
  }
  renameValue.value = selected.value.name;
  isRenaming.value = true;
  nextTick(() => {
    renameInputRef.value?.focus();
    renameInputRef.value?.select();
  });
}
function cancelRename() {
  isRenaming.value = false;
}
async function commitRename() {
  if (!isRenaming.value || !selected.value) return;
  const name = renameValue.value.trim();
  isRenaming.value = false;
  if (!name || name === selected.value.name) return;
  isSaving.value = true;
  try {
    await correspondentStore.updateCorrespondent(selected.value.id, { name }, { silent: true });
  } catch {
    // Fehlermeldung (z. B. Name schon vergeben) zeigt der Store; der alte Name bleibt.
  } finally {
    isSaving.value = false;
  }
}
function closePersonName(restoreFocus = true) {
  if (isSaving.value) return;
  isEditingPersonName.value = false;
  if (restoreFocus) nextTick(() => profileNameRef.value?.focus());
}
function submitPersonNameOnEnter(event) {
  if (event.isComposing) return;
  event.preventDefault();
  void commitPersonName();
}
function onPersonNameFocusOut(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) void commitPersonName(true);
}
async function commitPersonName(fromBlur = false) {
  if (!isEditingPersonName.value || selected.value?.kind !== 'person' || isSaving.value || isProfileSwitching.value) return;
  const { id } = selected.value;
  const payload = personNamePayload(personNameDraft.value);
  const original = personNamePayload(personNameParts(selected.value));
  if ((fromBlur || hasStoredPersonName.value)
      && payload.first_name === original.first_name && payload.last_name === original.last_name) {
    closePersonName(!fromBlur);
    return;
  }
  if (!validCorrespondentName(payload.name)) {
    personNameInvalid.value = true;
    return;
  }
  try {
    if (await saveCorrespondent(id, payload) && props.selectedId === id) closePersonName(!fromBlur);
  } catch {
    // Der Store meldet den Fehler. Die Eingabe bleibt zum erneuten Speichern offen.
  }
}
watch(() => props.selectedId, () => {
  cancelRename();
  isEditingPersonName.value = false;
});

// ── Notiz: freier Text am Korrespondenten (Kundennummer, Fristen …) ───────
const isEditingNote = ref(false);
const noteValue = ref('');
const noteInputRef = ref(null);
const noteButtonRef = ref(null);
function startNote() {
  if (isSaving.value) return;
  const placeholderBounds = noteButtonRef.value?.getBoundingClientRect();
  noteValue.value = selected.value?.notes || '';
  isEditingNote.value = true;
  nextTick(() => {
    const editor = noteInputRef.value;
    animateInlinePlaceholderResize(editor, placeholderBounds);
    editor?.focus();
  });
}
function cancelNote(restoreFocus = false) {
  const editorBounds = noteInputRef.value?.getBoundingClientRect();
  const correspondentId = selected.value?.id;
  isEditingNote.value = false;
  nextTick(() => {
    if (selected.value?.id !== correspondentId) return;
    const placeholder = noteButtonRef.value;
    animateInlinePlaceholderResize(placeholder, editorBounds);
    if (restoreFocus) placeholder?.focus();
  });
}
async function commitNote(event) {
  if (!isEditingNote.value || !selected.value || isSaving.value) return;
  const { id, notes: savedNotes } = selected.value;
  const restoreFocus = event.type === 'keydown';
  const notes = noteValue.value.trim();
  if (notes === (savedNotes || '').trim()) {
    cancelNote(restoreFocus);
    return;
  }
  isSaving.value = true;
  try {
    await correspondentStore.updateCorrespondent(id, { notes: notes || null }, { silent: true });
    if (props.selectedId === id) cancelNote(restoreFocus);
  } catch {
    // Der Store meldet den Fehler. Die Eingabe bleibt zum erneuten Speichern offen.
  } finally {
    isSaving.value = false;
  }
}
watch(() => props.selectedId, () => { isEditingNote.value = false; });

async function applyKind() {
  if (!selected.value || !canApplyKind.value || isSaving.value) return;
  const { id } = selected.value;
  const kind = draftKind.value;
  const payload = kindLosesParent.value ? { kind, parent_id: null } : { kind };
  if (kind === 'person') Object.assign(payload, personNamePayload(kindPersonName.value));
  kindError.value = '';
  try {
    if (await saveCorrespondent(id, payload) && props.selectedId === id) {
      closeKindDialog();
      reloadSelected();
    }
  } catch {
    if (props.selectedId === id) kindError.value = 'Der Typ konnte nicht geändert werden. Versuche es erneut.';
  }
}

async function detachFromParent(correspondent) {
  if (await saveCorrespondent(correspondent.id, { parent_id: null })) reloadSelected();
}

// ── Ziehen & Ablegen: Personen und Organisationen zuordnen ──────────────
function isDraggable(node) {
  return !node.context_only && (node.kind === 'person' || node.kind === 'organization');
}
function onDragStart(event, item) {
  draggedId.value = item.id;
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', item.name);
}
function onDragEnd() {
  draggedId.value = null;
  dropTargetId.value = null;
}
function acceptsDrop(target) {
  const dragged = correspondentStore.findById(draggedId.value);
  return canAssignToParent(dragged, target);
}
function onDragOver(event, target) {
  if (!draggedId.value || !acceptsDrop(target)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  dropTargetId.value = target.id;
}
function onDragLeave(target) {
  if (dropTargetId.value === target.id) dropTargetId.value = null;
}
async function onDrop(event, target) {
  const id = draggedId.value;
  if (!id || !acceptsDrop(target)) return;
  event.preventDefault();
  onDragEnd();
  if (await saveCorrespondent(id, { parent_id: target.id })) {
    setExpanded(target.id, true);
    if (props.selectedId === id || props.selectedId === target.id) reloadSelected();
  }
}

onMounted(() => {
  void correspondentStore.fetchCorrespondents();
  void loadUnassignedDocuments();
  void loadCollectionDocuments();
});
</script>

<style scoped>
.corr {
  display: grid;
  grid-template-columns: clamp(360px, 40%, 460px) minmax(0, 1fr);
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  background: var(--pm-app-surface);
}
.corr-muted { color: var(--pm-muted); }

/* Übersicht */
.corr-list {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--pm-divider);
}
.corr-list__empty { flex: 1; min-height: 0; height: auto; }
.corr-list__retry { align-self: flex-start; margin: 10px 16px 0; font-size: 0.8rem; }

.corr-create { display: flex; flex-direction: column; gap: 12px; }
.corr-filter { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 10px; }
.corr-filter--inline { margin-block-end: 8px; padding: 0; }
/* Type choice in the create dialog: one full-width segmented control. */
.corr-filter--segment {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  margin-block-end: 8px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
}
.corr-filter--segment .corr-filter__btn {
  justify-content: center;
  min-height: 34px;
  border: 0;
  border-radius: 0;
  font-size: 0.82rem;
}
.corr-filter--segment .corr-filter__btn + .corr-filter__btn { border-inline-start: 1px solid var(--pm-divider); }
.corr-filter--segment .corr-filter__btn.is-active { background: color-mix(in srgb, var(--pm-accent) 12%, transparent); }
.corr-create__parent-link { display: inline-flex; align-items: center; gap: 4px; align-self: flex-start; min-height: 32px; font-size: 0.86rem; }
.corr-filter__btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border: 1px solid var(--pm-divider);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted);
  font-size: 0.78rem;
  font-weight: 550;
  cursor: pointer;
  transition: border-color var(--pm-duration-fast) var(--pm-easing), color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing);
}
.corr-filter__btn:hover:not(:disabled) { color: var(--pm-text); border-color: var(--pm-outline); }
.corr-filter__btn.is-active {
  color: var(--pm-accent-text);
  border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent);
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
}
.corr-filter__btn:disabled { opacity: 0.45; cursor: not-allowed; }
.corr-filter__count {
  min-width: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-warning) 18%, transparent);
  color: var(--pm-text);
  font-size: 0.7rem;
  text-align: center;
}

.corr-tree {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 12px 20px;
}
/* Documents without correspondent: one distinct entry instead of document rows. */
.corr-inbox { padding: 12px 0 6px; }
.corr-inbox__row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: 8px 10px 8px 12px;
  border: 1px solid var(--pm-divider);
  border-radius: 10px;
  background: color-mix(in srgb, var(--pm-warning) 5%, transparent);
  color: var(--pm-list-title);
  cursor: pointer;
  outline: none;
  transition:
    background-color var(--pm-duration-normal) var(--pm-easing),
    border-color var(--pm-duration-normal) var(--pm-easing),
    box-shadow var(--pm-duration-normal) var(--pm-easing);
}
.corr-inbox__row:hover {
  background: color-mix(in srgb, var(--pm-warning) 9%, transparent);
  border-color: color-mix(in srgb, var(--pm-warning) 35%, var(--pm-divider));
}
.corr-inbox__row:focus-visible { border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent); }
.corr-inbox__row.is-selected,
.corr-inbox__row.is-selected:hover {
  border-color: transparent;
  background-color: var(--pm-list-card-selected);
  box-shadow: var(--pm-list-card-shadow);
}
.corr-inbox__row.is-selected::before {
  content: '';
  position: absolute;
  inset: 9px auto 9px 4px;
  width: 3px;
  border-radius: 4px;
  background: var(--pm-list-accent);
  pointer-events: none;
}
.corr-inbox__icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  color: var(--pm-error);
  background: color-mix(in srgb, currentColor 14%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, currentColor 40%, transparent);
}
.corr-inbox__text { display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; line-height: 1.25; }
.corr-inbox__title { font-size: 0.9rem; font-weight: 600; }
.corr-inbox__subtitle { color: var(--pm-muted); font-size: 0.76rem; }
.corr-inbox__count {
  flex: none;
  min-width: 22px;
  padding: 1px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-warning) 18%, transparent);
  color: var(--pm-text);
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.corr-inbox__chevron { flex: none; color: var(--pm-muted); }
.corr-inbox + .corr-inbox { padding-top: 0; }
.corr-inbox + .corr-section { margin-top: 6px; border-top: 1px solid var(--pm-divider); }
.corr-section + .corr-section {
  margin-top: 6px;
  border-top: 1px solid var(--pm-divider);
}
.corr-section__head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0;
  padding: 18px 14px 8px;
  color: var(--pm-muted);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.corr-section__count { font-weight: 500; letter-spacing: 0.04em; font-variant-numeric: tabular-nums; }
.corr-section__list,
.corr-branch__rows { list-style: none; margin: 0; padding: 0; }
.corr-branch {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: 1fr;
}
.corr-branch__rows { min-height: 0; }
.corr-branch-enter-active,
.corr-branch-leave-active {
  transition:
    grid-template-rows var(--pm-duration-normal) var(--pm-easing),
    opacity var(--pm-duration-fast) var(--pm-easing);
}
.corr-branch-enter-active > .corr-branch__rows,
.corr-branch-leave-active > .corr-branch__rows { overflow: hidden; }
.corr-branch-enter-from,
.corr-branch-leave-to { grid-template-rows: 0fr; opacity: 0; }

.corr-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 14px 0 6px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--pm-list-title);
  font-size: 0.9rem;
  cursor: pointer;
  outline: none;
  transition:
    background-color var(--pm-duration-normal) var(--pm-easing),
    box-shadow var(--pm-duration-normal) var(--pm-easing);
}
.corr-row:hover {
  background-color: var(--pm-list-hover);
  box-shadow: inset 0 0 0 1px var(--pm-list-hover-ring);
}
.corr-row:focus-visible { border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent); }
.corr-row.is-selected,
.corr-row.is-selected:hover {
  background-color: var(--pm-list-card-selected);
  box-shadow: var(--pm-list-card-shadow);
}
.corr-row.is-selected::before {
  content: '';
  position: absolute;
  inset: 7px auto 7px 6px;
  width: 3px;
  border-radius: 4px;
  background: var(--pm-list-accent);
  pointer-events: none;
}
.corr-row.is-draggable { cursor: grab; }
.corr-row.is-muted .corr-row__name { color: var(--pm-muted); }
.corr-row.is-drop-target,
.corr-row.is-drop-target:hover {
  border-style: dashed;
  border-color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
  box-shadow: none;
}
.corr-row__toggle {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}
.corr-row__toggle:hover { background: var(--pm-row-hover); color: var(--pm-text); }
.corr-row__toggle .v-icon { transition: transform var(--pm-duration-normal) var(--pm-easing); }
.corr-row[aria-expanded="true"] > .corr-row__toggle .v-icon { transform: rotate(90deg); }
.corr-row__type { flex: none; color: var(--pm-accent-text); }
.corr-row.is-muted .corr-row__type { color: var(--pm-muted); }
.corr-row__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 400;
}
.corr-row__chip {
  flex: 0 0 auto;
  padding: 1px 7px;
  border: 1px solid color-mix(in srgb, var(--pm-muted) 75%, var(--pm-chip-bg));
  border-radius: 6px;
  background: var(--pm-chip-bg);
  color: var(--pm-text);
  font-size: 0.74rem;
  line-height: 1.35;
  white-space: nowrap;
}
.corr-row__count {
  flex: 0 0 auto;
  min-width: 28px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--pm-muted);
}

/* Personen: eingerückt, mit Baumlinie zur Organisation. */
.corr-row--member { padding-left: 52px; }
.corr-row__branch {
  position: absolute;
  left: 18px;
  top: -1px;
  bottom: -1px;
  width: 22px;
  pointer-events: none;
}
.corr-row__branch::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  border-left: 1px solid var(--pm-divider);
}
.corr-row__branch::after {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 14px;
  border-top: 1px solid var(--pm-divider);
}
.corr-row--member.is-last .corr-row__branch::before { bottom: 50%; }
/* In Sammlungen: Mitglieder mit eigenen Personen bekommen einen Aufklapper. */
.corr-row--member.has-toggle { padding-left: 40px; }
.corr-row--member.has-toggle .corr-row__branch::after { width: 18px; }
/* Dritte Ebene: Personen einer Organisation innerhalb einer Sammlung. */
.corr-row--member.corr-row--nested { padding-left: 80px; }
.corr-row--nested .corr-row__branch { left: 51px; }
.corr-row__rail { display: none; }
.corr-row--nested.has-rail .corr-row__rail {
  display: block;
  position: absolute;
  left: 18px;
  top: -1px;
  bottom: -1px;
  border-left: 1px solid var(--pm-divider);
  pointer-events: none;
}

.corr-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 20px;
  font-size: 0.86rem;
  text-align: center;
}

/* Profil */
/* position: relative – das Vorschau-Overlay (DocumentPreviewOverlay) deckt nur diesen Bereich ab. */
.corr-profile { position: relative; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.corr-profile__loading { flex: 1; }
/* Kopf bleibt oben stehen; nur der Inhalt darunter scrollt. Seine Unterkante
   fluchtet mit der Linie unter Listenkopf (57 px) + Filterleiste links. */
.corr-profile__head {
  flex: none;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  box-sizing: border-box;
  min-height: calc(57px + var(--notes-meta-row-height, 36px));
  padding: 10px clamp(18px, 3vw, 40px);
  border-bottom: 1px solid var(--pm-divider);
  background: var(--pm-app-surface);
}
.corr-profile__scroll { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 22px clamp(16px, 3vw, 40px) 40px; container-type: inline-size; }
.corr-profile__back { display: none; }
.corr-avatar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--pm-accent) 14%, transparent);
  color: var(--pm-accent-text);
  font-weight: 650;
  letter-spacing: 0.02em;
}
/* Organisationen und Sammlungen stehen im abgerundeten Quadrat. */
.corr-avatar--organization,
.corr-avatar--collection { border-radius: 13px; }
.corr-profile__heading { min-width: 0; flex: 1 1 0; container: corr-profile-heading / inline-size; }
.corr-profile__name { margin: 0; font-size: clamp(1.25rem, 2.5vw, 1.9rem); font-weight: 650; line-height: 1.2; color: var(--pm-text); }
/* Klick auf den Namen öffnet das Feld; beide sitzen pixelgleich, damit nichts springt. */
.corr-profile__name-btn {
  max-width: 100%;
  margin: 0 -6px;
  padding: 1px 6px;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 8px;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  overflow-wrap: anywhere;
  cursor: text;
  transition: background-color var(--pm-duration-fast, 140ms) var(--pm-easing), border-color var(--pm-duration-fast, 140ms) var(--pm-easing);
}
.corr-profile__name-btn:hover { background: var(--pm-row-hover); }
.corr-profile__name-btn:focus-visible { outline: none; border-color: var(--pm-accent); }
.corr-profile__name-input {
  display: block;
  box-sizing: border-box;
  field-sizing: content;
  min-width: min(2ch, 100%);
  max-width: calc(100% + 12px);
  margin: 0 -6px;
  padding: 1px 6px;
  border: 1px solid var(--pm-accent);
  border-radius: 8px;
  outline: none;
  background: var(--pm-metadata-field-bg);
  caret-color: var(--pm-accent-text);
  font-family: inherit;
}
.corr-profile__name-input::selection {
  background: color-mix(in srgb, var(--pm-accent) 24%, var(--pm-metadata-field-bg));
  color: var(--pm-text);
}
.corr-profile__person-name { margin-bottom: 4px; }
.corr-profile__person-name-fields {
  display: grid;
  grid-template-columns: repeat(2, fit-content(calc((100% - 8px) / 2)));
  gap: 6px 8px;
}
.corr-profile__person-name-fields label {
  display: grid;
  align-content: start;
  gap: 2px;
  min-width: 0;
  color: var(--pm-muted);
  font-size: 0.74rem;
}
.corr-profile__person-name-fields input { max-width: 100%; margin: 0; }
.corr-profile__person-name-fields input:not(:focus) { border-color: var(--pm-divider); }
.corr-profile__person-name-hint { margin: 4px 0 0; color: var(--pm-muted); font-size: 0.74rem; }
.corr-profile__person-name-error { color: var(--pm-error); }
.corr-profile__meta-action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 24px;
  padding: 2px calc(var(--pm-detail-meta-inset) - 1px);
  border: 1px solid transparent;
  border-radius: 999px;
  background: none;
  color: var(--pm-muted);
  font: inherit;
  white-space: nowrap;
  cursor: pointer;
}
.corr-profile__meta-action:hover:not(:disabled) {
  border-color: color-mix(in srgb, currentColor 55%, transparent);
  background: color-mix(in srgb, currentColor 8%, transparent);
}
.corr-profile__meta-action:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.corr-profile__short-name { max-width: 18ch; overflow: hidden; text-overflow: ellipsis; }
.corr-profile__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--pm-detail-meta-gap);
  margin-block-start: var(--pm-detail-meta-top);
  font-size: 0.8rem;
  line-height: 1.25;
}
.corr-profile__meta > span { display: inline-flex; align-items: center; gap: var(--pm-detail-meta-gap); }
.corr-profile__meta > .corr-profile__meta-value {
  column-gap: calc(var(--pm-detail-meta-gap) + var(--pm-detail-meta-inset));
  padding-inline-end: var(--pm-detail-meta-inset);
}
.corr-profile__meta > span + span::before {
  flex: none;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.48;
  content: '';
}
@container corr-profile-heading (max-width: 300px) {
  .corr-profile__person-name-fields { grid-template-columns: fit-content(100%); }
  .corr-profile__meta > .corr-profile__meta-value { padding-inline-end: 0; }
  .corr-profile__meta > span + span::before { content: none; }
}
.corr-link {
  padding: 0;
  border: 0;
  background: none;
  color: var(--pm-accent-text);
  font: inherit;
  cursor: pointer;
}
.corr-link:hover:not(:disabled) { text-decoration: underline; }

.corr-profile-action { border-color: var(--pm-divider); color: var(--pm-muted); }


.corr-kind-options { display: grid; gap: 8px; }
.corr-kind-option {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  grid-template-areas: "icon text choice";
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--pm-divider);
  border-radius: 10px;
  color: var(--pm-text);
  cursor: pointer;
}
.corr-kind-option:hover:not(.is-selected, .is-unavailable) { background: var(--pm-row-hover); }
.corr-kind-option.is-selected {
  border-color: color-mix(in srgb, var(--pm-accent) 58%, var(--pm-divider));
  background: color-mix(in srgb, var(--pm-accent) 8%, transparent);
}
.corr-kind-option:has(input:focus-visible) { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.corr-kind-option.is-unavailable {
  background: color-mix(in srgb, var(--pm-muted) 6%, transparent);
  color: var(--pm-muted);
  cursor: default;
}
.corr-kind-option input { grid-area: choice; width: 16px; height: 16px; margin: 0; accent-color: var(--pm-accent); }
.corr-kind-option input:focus-visible { outline: none; }
.corr-kind-option__icon {
  grid-area: icon;
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 9px;
  background: var(--pm-chip-bg);
  color: var(--pm-accent-text);
}
.corr-kind-option.is-unavailable .corr-kind-option__icon {
  background: color-mix(in srgb, var(--pm-muted) 10%, transparent);
  color: var(--pm-muted);
}
.corr-kind-option__text { grid-area: text; display: grid; gap: 3px; min-width: 0; }
.corr-kind-option__heading { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; }
.corr-kind-option__heading strong { font-size: 0.95rem; font-weight: 650; }
.corr-kind-option__current { color: var(--pm-accent-text); font-size: 0.75rem; font-weight: 600; }
.corr-kind-option__detail, .corr-kind-notice, .corr-kind-error { color: var(--pm-muted); font-size: 0.82rem; line-height: 1.4; }
.corr-kind-option__reason { display: flex; align-items: baseline; gap: 4px; margin-top: 4px; font-weight: 550; }
.corr-kind-option__reason .v-icon { flex: none; align-self: center; }
.corr-kind-notice {
  margin: 12px 0 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--pm-accent) 6%, transparent);
  overflow-wrap: anywhere;
}
.corr-kind-error { margin: 12px 0 0; color: var(--pm-error); }

.corr-empty { margin: 0; font-size: 0.84rem; line-height: 1.45; }
.corr-sheet {
  --corr-section-content-gap: 8px;
  --corr-sheet-gap: 18px;
  --corr-profile-divider-spacing: 26px;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--corr-sheet-gap);
  max-width: 820px;
}
.corr-profile-data {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  margin-block-start: calc(var(--corr-profile-divider-spacing) - var(--corr-sheet-gap));
  border-block-start: 1px solid color-mix(in srgb, var(--pm-list-divider) 65%, transparent);
  padding-block-start: var(--corr-profile-divider-spacing);
}
.corr-section-head,
.corr-section-info :deep(.pm-info-heading__row) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 12px;
  min-height: 32px;
}
.corr-section-head,
.corr-section-info :deep(.pm-info-heading) { margin-bottom: var(--corr-section-content-gap); }
.corr-section-head h2,
.corr-section-info :deep(.pm-info-heading__title) {
  margin: 0;
  color: var(--pm-text);
  font-size: 0.95rem;
  font-weight: 650;
}
.corr-section-info :deep(.pm-info-heading__row) { gap: 4px; }
.corr-section-action { display: inline-flex; align-items: center; gap: 5px; min-height: 32px; font-size: 0.83rem; font-weight: 600; }
.corr-placeholder:hover:not(:disabled) { color: var(--pm-text); }
.corr-placeholder .v-icon { color: var(--pm-accent-text); }
.corr-placeholder:disabled, .corr-note:disabled { cursor: default; }
.corr-section-action { margin-inline-start: auto; }
.corr-structure { margin: 0; padding: 0; list-style: none; }
.corr-structure:not(.corr-structure--tiles) > li + .corr-structure__add-action { margin-block-start: 8px; }
.corr-structure:not(.corr-structure--tiles) > li + .corr-structure__row { border-top: 1px solid var(--pm-divider); }
.corr-structure--tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 286px), 1fr));
  grid-auto-rows: minmax(62px, 1fr);
  gap: 10px;
}
.corr-structure--tiles > .corr-structure__add-action { display: grid; }
.corr-structure--tiles .corr-structure__add-action > .corr-placeholder { width: 100%; }
.corr-collection { container-type: inline-size; }
.corr-collection__band { margin-bottom: 14px; }

/* Notiz: Text mit einem Klick bearbeiten. */
.corr-note, .corr-placeholder {
  box-sizing: border-box;
  display: block;
  width: fit-content;
  max-width: 100%;
  min-height: 38px;
  padding: 8px 10px;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  background: none;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.86rem;
  line-height: 1.45;
  text-align: left;
  overflow-wrap: anywhere;
}
.corr-note { white-space: pre-wrap; cursor: text; }
button.corr-note:where(:not(.corr-note--empty)) {
  border-color: color-mix(in srgb, var(--pm-divider) 65%, transparent);
  background: color-mix(in srgb, var(--pm-accent) 5%, var(--pm-app-surface));
}
.corr-note:hover, .corr-placeholder:hover { border-color: color-mix(in srgb, var(--pm-accent) 45%, var(--pm-divider)); }
.corr-placeholder {
  display: flex;
  align-items: center;
  gap: 8px;
  border-style: dashed;
  border-color: color-mix(in srgb, var(--pm-muted) 45%, var(--pm-divider));
  color: var(--pm-muted);
  cursor: pointer;
}
.corr-placeholder--affiliation-chip {
  gap: 5px;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
}
.corr-placeholder.corr-placeholder--collection {
  flex-direction: column;
  gap: 4px;
  padding: 14px 10px;
  border-color: color-mix(in srgb, var(--pm-accent) 36%, var(--pm-divider));
  text-align: center;
}
.corr-placeholder--collection:hover:not(:disabled) {
  border-color: var(--pm-accent);
  background-color: color-mix(in srgb, var(--pm-accent) 6%, transparent);
}
.corr-placeholder--collection:focus-visible {
  outline: 2px solid var(--pm-accent);
  outline-offset: -2px;
}
.corr-placeholder__badge {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  margin-block-end: 5px;
  border: 1px solid color-mix(in srgb, var(--pm-accent) 22%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--pm-accent) 12%, transparent);
}
.corr-placeholder__title { color: var(--pm-text); font-weight: 600; }
.corr-placeholder__hint { color: var(--pm-muted); font-size: 0.75rem; }
.corr-docs-empty { display: flex; align-items: center; gap: 10px; color: var(--pm-muted); }
.corr-docs-empty__badge {
  display: grid;
  place-items: center;
  flex: 0 0 30px;
  height: 30px;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  color: var(--pm-accent-text);
}
.corr-note--input {
  width: auto;
  min-width: min(28ch, 100%);
  border-color: var(--pm-accent);
  outline: none;
  resize: vertical;
  field-sizing: content;
  min-height: 76px;
}
.corr-note--full-width { width: 100%; }

@media (max-width: 860px) {
  .corr { grid-template-columns: minmax(0, 1fr); }
  .corr-list { border-right: 0; }
  .corr:not(.corr--has-profile) .corr-profile,
  .corr--has-profile .corr-list { display: none; }
  .corr-profile__head { padding-block: 12px; }
  .corr-profile__head .corr-profile__back,
  .corr-unassigned-back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    text-align: start;
  }
  .corr-profile__head .corr-profile__back { flex-basis: 100%; }
  .corr-unassigned-back { align-self: flex-start; margin: 4px 16px; }
}
@media (pointer: coarse) {
  .corr-profile__head .corr-profile__back, .corr-section-action,
  .corr-placeholder { min-height: 44px; }
}
</style>
