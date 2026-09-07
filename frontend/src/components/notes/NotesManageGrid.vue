<!--
  NotesManageGrid — großflächige Verwaltungsfläche des Notizbereichs.
  Rendert die Notizen als mehrspaltiges Kartenraster (statt schmaler Liste)
  mit kartenbezogenen Aktionsmenüs und Inline-Umbenennen. Die Umschaltung
  zwischen Notizen und Vorlagen liegt in der Kopfzeile von NotesWorkspace. Wird
  dort in einer eigenständigen, vollbreiten Verwaltungsfläche gezeigt.
-->
<template>
  <div class="nmg">
    <div class="nmg__body">
      <!-- Inhalt -->
      <div class="nmg__scroll">
        <Transition name="nmg-content" mode="out-in">
        <section v-if="isGlobalSearching" key="global-search" class="nmg-search-results" aria-label="Globale Suchergebnisse">
          <header class="nmg-search-results__header">
            <div>
              <h2>{{ globalSearchResultLabel }}</h2>
              <p>Titel, Inhalte, Tags und Notizbücher</p>
            </div>
            <v-progress-circular
              v-if="globalSearchLoading"
              indeterminate
              size="20"
              width="2"
              aria-label="Notizen werden durchsucht"
            />
          </header>

          <section v-if="globalSearchNotebooks.length" class="nmg-search-results__group">
            <h3>Notizbücher <span>{{ globalSearchNotebooks.length }}</span></h3>
            <div class="nmg-search-results__notebooks">
              <button
                v-for="notebook in globalSearchNotebooks"
                :key="notebook.id"
                type="button"
                class="nmg-search-notebook"
                @click="$emit('select-search-notebook', notebook)"
              >
                <span class="nmg-search-notebook__icon"><v-icon size="18">mdi-notebook-outline</v-icon></span>
                <span class="nmg-search-notebook__name">
                  <span
                    v-for="(part, index) in globalSearchHighlightParts(notebook.name)"
                    :key="index"
                    :class="{ 'is-match': part.match }"
                  >{{ part.text }}</span>
                </span>
                <span class="nmg-search-notebook__count">
                  {{ notebook.note_count }} {{ notebook.note_count === 1 ? 'Notiz' : 'Notizen' }}
                </span>
                <v-icon size="16">mdi-chevron-right</v-icon>
              </button>
            </div>
          </section>

          <section v-if="filteredGlobalSearchNotes.length" class="nmg-search-results__group">
            <h3>Notizen <span>{{ filteredGlobalSearchNotes.length }}</span></h3>
            <ul class="nmg-search-results__notes">
              <li v-for="note in filteredGlobalSearchNotes" :key="note.id">
                <button type="button" class="nmg-search-note" @click="$emit('open-search-note', note)">
                  <span class="nmg-search-note__icon"><v-icon size="18">mdi-note-outline</v-icon></span>
                  <span class="nmg-search-note__content">
                    <strong :class="{ 'is-untitled': !note.title?.trim() }">
                      <span
                        v-for="(part, index) in globalSearchHighlightParts(note.title?.trim() || 'Ohne Titel')"
                        :key="index"
                        :class="{ 'is-match': part.match }"
                      >{{ part.text }}</span>
                    </strong>
                    <span class="nmg-search-note__preview">
                      <span
                        v-for="(part, index) in globalSearchHighlightParts(note.preview)"
                        :key="index"
                        :class="{ 'is-match': part.match }"
                      >{{ part.text }}</span>
                    </span>
                    <span v-if="note.tags?.length" class="nmg-search-note__tags">
                      <span v-for="tag in note.tags.slice(0, 3)" :key="tag.id">{{ tag.name }}</span>
                      <span v-if="note.tags.length > 3">+{{ note.tags.length - 3 }}</span>
                    </span>
                  </span>
                  <span class="nmg-search-note__meta">
                    <span v-if="notebookFor(note)"><v-icon size="13">mdi-notebook-outline</v-icon>{{ notebookFor(note).name }}</span>
                    <time>{{ formatDate(note.updated_at) }}</time>
                  </span>
                  <v-icon class="nmg-search-note__open" size="17">mdi-chevron-right</v-icon>
                </button>
              </li>
            </ul>
          </section>

          <div
            v-if="!globalSearchLoading && !globalSearchNotebooks.length && !filteredGlobalSearchNotes.length"
            class="nmg-search-results__empty"
          >
            <v-icon size="28">mdi-note-search-outline</v-icon>
            <strong>Keine passenden Notizen oder Notizbücher</strong>
            <span>Probiere einen anderen Suchbegriff.</span>
          </div>
        </section>

        <Vorlagenmappe
          v-else-if="facet === 'templates'"
          key="templates"
          class="nmg__vorlagenmappe"
          @open-note="(id, opts) => $emit('open-note', id, opts)"
          @changed="$emit('changed')"
        />

        <div
          v-else-if="facet === 'notes' && !visibleItems.length && (normalizedQuery || dateRange)"
          key="empty-search"
          class="nmg__empty"
        >
          <PmEmptyState
            :icon="emptyState.icon"
            :title="emptyState.title"
            :subtitle="emptyState.subtitle"
            size="sm"
          />
        </div>

        <div
          v-else-if="facet === 'notes' && !visibleItems.length"
          key="empty-ghosts"
          class="nmg__ghost-empty"
        >
          <div class="nmg__grid nmg__ghosts">
            <div v-for="i in 3" :key="i" class="nmg-ghost" aria-hidden="true">
              <div class="nmg-ghost__preview">
                <span class="nmg-ghost__line" style="width: 88%" />
                <span class="nmg-ghost__line" style="width: 66%" />
                <span class="nmg-ghost__line" style="width: 78%" />
              </div>
              <div class="nmg-ghost__meta"><span class="nmg-ghost__chip" /><span class="nmg-ghost__name" /></div>
            </div>
            <GhostAddCard
              title="Noch keine Notiz"
              subtitle="Neue Notiz anlegen"
              @click="$emit('create-note')"
            />
          </div>
        </div>

        <div v-else-if="facet === 'notes'" key="items" class="nmg__groups">
          <section v-for="group in groupedItems" :key="group.key" class="nmg__group">
            <h3 v-if="group.label" class="nmg__group-heading">{{ group.label }}</h3>
            <ul class="nmg__grid">
              <li
                v-for="note in group.notes"
                :key="note.id"
                class="nmg-card"
                :class="{ 'is-editing': editingId === note.id, 'is-dragging': draggingNoteId === note.id, 'is-in-collection': !!note.collection_id }"
                :style="collectionAccentStyle(note)"
                :title="notebookFor(note) ? `Notizbuch: ${notebookFor(note).name}` : undefined"
                role="button"
                tabindex="0"
                draggable="true"
                @click="onCardClick(note)"
                @keydown.enter="onCardClick(note)"
                @dragstart="onCardDragStart($event, note)"
                @dragend="onCardDragEnd"
              >
                <div class="nmg-card__preview">
                  <p class="nmg-card__snippet">{{ snippet(note) }}</p>
                  <span
                    v-if="note.link_count > 0"
                    class="nmg-card__links"
                    :title="`${note.link_count} Verknüpfung${note.link_count === 1 ? '' : 'en'}`"
                  >
                    <v-icon size="12">mdi-link-variant</v-icon>{{ note.link_count }}
                  </span>
                  <div class="nmg-card__actions" @click.stop>
                    <span
                      class="nmg-card__fav-wrap"
                      :class="{ 'nmg-card__fav-wrap--pop': animatingFavoriteId === note.id }"
                    >
                      <button
                        type="button"
                        class="nmg-card__act nmg-card__act--fav"
                        :class="{ 'is-active': note.is_favorite }"
                        :title="note.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'"
                        :aria-label="note.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'"
                        :aria-pressed="String(!!note.is_favorite)"
                        @click="toggleFavorite(note)"
                      >
                        <v-icon size="15">{{ note.is_favorite ? 'mdi-star' : 'mdi-star-outline' }}</v-icon>
                      </button>
                    </span>
                    <v-menu location="bottom end" :offset="4">
                      <template #activator="{ props: moveProps }">
                        <button type="button" class="nmg-card__act" v-bind="moveProps" title="In Notizbuch verschieben" aria-label="In Notizbuch verschieben">
                          <v-icon size="15">mdi-notebook-outline</v-icon>
                        </button>
                      </template>
                      <v-list density="compact" min-width="200" max-height="320" class="nmg__move-list">
                        <v-list-subheader>In Notizbuch verschieben</v-list-subheader>
                        <v-list-item
                          v-for="nb in notebooks"
                          :key="nb.id"
                          :title="nb.name"
                          :active="note.notebook_id === nb.id"
                          @click="moveNoteToNotebook(note, nb.id)"
                        >
                          <template #prepend><v-icon size="16">mdi-notebook-outline</v-icon></template>
                          <template v-if="note.notebook_id === nb.id" #append><v-icon size="15">mdi-check</v-icon></template>
                        </v-list-item>
                        <v-list-item
                          v-if="note.notebook_id"
                          title="Aus Notizbuch nehmen"
                          @click="moveNoteToNotebook(note, null)"
                        >
                          <template #prepend><v-icon size="16">mdi-inbox-outline</v-icon></template>
                        </v-list-item>
                        <v-list-item v-if="!notebooks.length" title="Neues Notizbuch anlegen …" @click="openSidebarAndCreateNotebook">
                          <template #prepend><v-icon size="16">mdi-plus</v-icon></template>
                        </v-list-item>
                        <template v-if="collections.length > 1">
                          <v-divider class="nmg__move-divider" />
                          <v-list-subheader>In Sammlung verschieben</v-list-subheader>
                          <v-list-item
                            v-for="c in collections"
                            :key="`coll-${c.id}`"
                            :title="c.name"
                            :active="note.collection_id === c.id"
                            :disabled="note.collection_id === c.id"
                            @click="moveNoteToCollection(note, c.id)"
                          >
                            <template #prepend><span class="nmg__coll-dot" :style="collectionDotStyle(c)"></span></template>
                            <template v-if="note.collection_id === c.id" #append><v-icon size="15">mdi-check</v-icon></template>
                          </v-list-item>
                        </template>
                      </v-list>
                    </v-menu>
                    <button type="button" class="nmg-card__act" title="Als Vorlage speichern" aria-label="Als Vorlage speichern" @click="saveNoteAsTemplate(note)">
                      <v-icon size="15">mdi-content-copy</v-icon>
                    </button>
                    <button type="button" class="nmg-card__act nmg-card__act--danger" title="In Papierkorb" aria-label="In Papierkorb" @click="trashNote(note)">
                      <v-icon size="15">mdi-trash-can-outline</v-icon>
                    </button>
                  </div>
                </div>

                <div class="nmg-card__meta">
                  <input
                    v-if="editingId === note.id"
                    ref="titleInputRef"
                    v-model="editingTitle"
                    class="nmg-card__title-input"
                    type="text"
                    maxlength="500"
                    placeholder="Titel …"
                    @click.stop
                    @keydown.enter.prevent.stop="commitRename(note)"
                    @keydown.esc.prevent.stop="cancelRename"
                    @blur="commitRename(note)"
                  />
                  <span
                    v-else
                    class="nmg-card__title"
                    :class="{ 'is-untitled': !note.title?.trim() }"
                    role="button"
                    tabindex="0"
                    title="Titel bearbeiten"
                    @click.stop="startRename(note)"
                    @keydown.enter.stop.prevent="startRename(note)"
                  >{{ note.title?.trim() || 'Ohne Titel' }}</span>
                </div>

                <div class="nmg-card__foot" @click.stop>
                  <!-- Tags nur als ruhiger Zähler; Bearbeiten im Popover. -->
                  <v-menu :close-on-content-click="false" location="top start" :offset="6">
                    <template #activator="{ props: tagProps }">
                      <button
                        type="button"
                        class="nmg-card__tag-btn"
                        :class="{ 'is-empty': !(note.tags && note.tags.length) }"
                        v-bind="tagProps"
                        :aria-label="(note.tags && note.tags.length) ? `${note.tags.length} Tag${note.tags.length === 1 ? '' : 's'} bearbeiten` : 'Tags hinzufügen'"
                        :title="(note.tags || []).map((t) => t.name).join(', ') || 'Tags hinzufügen'"
                        @click.stop
                      >
                        <v-icon size="14">{{ (note.tags && note.tags.length) ? 'mdi-tag' : 'mdi-tag-outline' }}</v-icon>
                        <span class="nmg-card__tag-count">{{ (note.tags && note.tags.length) || 'Tag' }}</span>
                      </button>
                    </template>
                    <div class="nmg-card__tag-pop" @click.stop>
                      <NoteTagBar
                        :tag-ids="(note.tags || []).map((t) => t.id)"
                        :all-tags="allTagsForCard(note)"
                        compact
                        :create-tag-by-name="tagStore.ensureTagIdByName"
                        :load-tags="tagStore.fetchTags"
                        @update:tag-ids="(ids) => applyCardTags(note, ids)"
                      />
                    </div>
                  </v-menu>

                  <span class="nmg-card__date">{{ formatDate(note.updated_at) }}</span>
                </div>
              </li>
            </ul>
          </section>
        </div>
        </Transition>
      </div>

      <button
        v-if="(facet === 'notes' || isGlobalSearching) && !tagSidebarOpen"
        type="button"
        class="nmg__tag-sidebar-toggle"
        aria-label="Filter öffnen"
        @click="tagSidebarOpen = true"
      >
        <v-icon size="18">mdi-filter-variant</v-icon>
      </button>

      <aside
        v-if="facet === 'notes' || isGlobalSearching"
        class="nmg__tag-sidebar"
        :class="{ 'is-open': tagSidebarOpen }"
        aria-label="Notizen filtern"
      >
        <div class="nmg__tag-sidebar-head">
          <div class="nmg__tag-sidebar-actions">
            <button
              type="button"
              class="nmg__tag-sidebar-action nmg__tag-sidebar-close"
              aria-label="Filter schließen"
              @click="tagSidebarOpen = false"
            >
              <v-icon size="18">mdi-close</v-icon>
            </button>
          </div>
        </div>

        <!-- Sammlung: oberste Schale (harter Space-Wechsel). Kein „Alle" – genau
             eine ist aktiv und scopt Notizbücher + Notizen darunter. -->
        <div class="nmg__filter-section nmg__collections" role="group" aria-label="Sammlung">
          <div class="nmg__filter-section-head">
            <span class="nmg__filter-section-title">Sammlung</span>
            <button
              type="button"
              class="nmg__filter-section-add"
              aria-label="Neue Sammlung"
              title="Neue Sammlung"
              @click="startCreateCollection"
            >
              <v-icon size="16">mdi-plus</v-icon>
            </button>
          </div>

          <div class="nmg__coll-list">
            <div
              v-for="c in collections"
              :key="c.id"
              class="nmg__coll-row"
              :class="{ 'is-active': c.id === activeCollectionId }"
            >
              <div v-if="editingCollectionId === c.id" class="nmg__coll-editing">
                <span class="nmg__coll-dot" :style="collectionDotStyle(c)"></span>
                <input
                  ref="collectionInputRef"
                  v-model="editingCollectionName"
                  class="nmg__nb-name-input"
                  type="text"
                  maxlength="120"
                  placeholder="Name …"
                  @keydown.enter.prevent.stop="commitRenameCollection(c)"
                  @keydown.esc.prevent.stop="cancelRenameCollection"
                  @blur="commitRenameCollection(c)"
                />
              </div>

              <template v-else>
                <button
                  type="button"
                  class="nmg__coll-chip"
                  :class="{ 'is-active': c.id === activeCollectionId }"
                  :aria-pressed="String(c.id === activeCollectionId)"
                  @click="chooseCollection(c.id)"
                >
                  <span class="nmg__coll-dot" :style="collectionDotStyle(c)"></span>
                  <span class="nmg__coll-name">{{ c.name }}</span>
                  <span class="nmg__coll-count">{{ c.note_count }}</span>
                </button>
                <v-menu location="bottom end" :offset="4">
                  <template #activator="{ props: menuProps }">
                    <button
                      type="button"
                      class="nmg__nb-kebab"
                      v-bind="menuProps"
                      aria-label="Sammlungs-Aktionen"
                      title="Aktionen"
                      @click.stop
                    >
                      <v-icon size="16">mdi-dots-horizontal</v-icon>
                    </button>
                  </template>
                  <v-list density="compact" min-width="164" class="nmg__action-menu">
                    <v-list-item title="Umbenennen" @click="startRenameCollection(c)">
                      <template #prepend><v-icon size="16">mdi-pencil-outline</v-icon></template>
                    </v-list-item>
                    <div class="nmg__nb-colors" role="group" aria-label="Farbe">
                      <button
                        type="button"
                        class="nmg__nb-color nmg__nb-color--none"
                        :class="{ 'is-active': !c.color }"
                        title="Keine Farbe"
                        aria-label="Keine Farbe"
                        @click.stop="setCollectionColor(c, null)"
                      ><v-icon size="13">mdi-close</v-icon></button>
                      <button
                        v-for="color in COLLECTION_COLORS"
                        :key="color"
                        type="button"
                        class="nmg__nb-color"
                        :class="{ 'is-active': c.color === color }"
                        :style="{ '--nb-swatch': color }"
                        :title="`Farbe ${color}`"
                        :aria-label="`Farbe ${color}`"
                        @click.stop="setCollectionColor(c, color)"
                      />
                    </div>
                    <v-list-item
                      title="Löschen"
                      class="nmg__nb-menu-danger"
                      :disabled="collections.length <= 1"
                      @click="requestCollectionDeletion(c)"
                    >
                      <template #prepend><v-icon size="16">mdi-trash-can-outline</v-icon></template>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </template>
            </div>

            <div v-if="creatingCollection" class="nmg__coll-create">
              <span class="nmg__coll-dot nmg__coll-dot--ghost"></span>
              <input
                ref="createCollectionInputRef"
                v-model="newCollectionName"
                class="nmg__nb-name-input"
                type="text"
                maxlength="120"
                placeholder="Neue Sammlung …"
                @keydown.enter.prevent.stop="commitCreateCollection"
                @keydown.esc.prevent.stop="cancelCreateCollection"
                @blur="commitCreateCollection"
              />
            </div>
          </div>
        </div>

        <!-- Notizbücher: flache Ablageebene. Genau eines aktiv (all | id | none). -->
        <div class="nmg__filter-section" role="group" aria-label="Notizbücher">
          <div class="nmg__filter-section-head">
            <span class="nmg__filter-section-title">Notizbücher</span>
            <button
              type="button"
              class="nmg__filter-section-add"
              aria-label="Neues Notizbuch"
              title="Neues Notizbuch"
              @click="startCreateNotebook"
            >
              <v-icon size="16">mdi-plus</v-icon>
            </button>
          </div>

          <div ref="notebookListRef" class="nmg__tag-cloud-items nmg__tag-cloud-items--stack">
            <button
              type="button"
              class="nmg__tag-cloud-chip"
              :class="{ 'is-active': activeNotebookId === 'all' }"
              :aria-pressed="String(activeNotebookId === 'all')"
              @click="activeNotebookId = 'all'"
            >
              <span class="nmg__tag-cloud-name"><v-icon size="15" class="nmg__nb-glyph">mdi-notebook-multiple</v-icon>Alle Notizen</span>
              <span class="nmg__tag-cloud-count">{{ allNotes.length }}</span>
            </button>

            <div
              v-for="nb in notebooks"
              :key="nb.id"
              class="nmg__nb-row"
              :class="{ 'is-active': activeNotebookId === nb.id }"
              :data-nb-id="nb.id"
            >
              <!-- Bearbeiten: eigenständige Eingabezeile (NICHT in einem Button
                   geschachtelt – sonst schluckt der Button Fokus/Tastatur). -->
              <div v-if="editingNotebookId === nb.id" class="nmg__nb-editing">
                <v-icon size="15" class="nmg__nb-glyph">mdi-notebook-outline</v-icon>
                <input
                  ref="notebookInputRef"
                  v-model="editingNotebookName"
                  class="nmg__nb-name-input"
                  type="text"
                  maxlength="120"
                  placeholder="Name …"
                  @keydown.enter.prevent.stop="commitRenameNotebook(nb)"
                  @keydown.esc.prevent.stop="cancelRenameNotebook"
                  @blur="commitRenameNotebook(nb)"
                />
              </div>

              <template v-else>
                <button
                  type="button"
                  class="nmg__tag-cloud-chip nmg__nb-chip"
                  :class="{ 'is-active': activeNotebookId === nb.id, 'is-drop-target': dropTargetId === nb.id }"
                  :aria-pressed="String(activeNotebookId === nb.id)"
                  @click="activeNotebookId = nb.id"
                  @dragover="onNotebookDragOver($event, nb.id)"
                  @dragleave="onNotebookDragLeave(nb.id)"
                  @drop="onDropOnNotebook($event, nb.id)"
                >
                  <span class="nmg__tag-cloud-name">
                    <v-icon size="15" class="nmg__nb-glyph">mdi-notebook-outline</v-icon>
                    <span class="nmg__nb-name-text">{{ nb.name }}</span>
                  </span>
                  <span class="nmg__tag-cloud-count">{{ nb.note_count }}</span>
                </button>
                <v-menu location="bottom end" :offset="4">
                  <template #activator="{ props: menuProps }">
                    <button
                      type="button"
                      class="nmg__nb-kebab"
                      v-bind="menuProps"
                      aria-label="Notizbuch-Aktionen"
                      title="Aktionen"
                      @click.stop
                    >
                      <v-icon size="16">mdi-dots-horizontal</v-icon>
                    </button>
                  </template>
                  <v-list density="compact" min-width="164" class="nmg__action-menu">
                    <v-list-item title="Umbenennen" @click="startRenameNotebook(nb)">
                      <template #prepend><v-icon size="16">mdi-pencil-outline</v-icon></template>
                    </v-list-item>
                    <v-list-item title="Löschen" class="nmg__nb-menu-danger" @click="requestNotebookDeletion(nb)">
                      <template #prepend><v-icon size="16">mdi-trash-can-outline</v-icon></template>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </template>
            </div>

            <button
              type="button"
              class="nmg__tag-cloud-chip"
              :class="{ 'is-active': activeNotebookId === 'none', 'is-drop-target': dropTargetId === 'none' }"
              :aria-pressed="String(activeNotebookId === 'none')"
              @click="activeNotebookId = 'none'"
              @dragover="onNotebookDragOver($event, 'none')"
              @dragleave="onNotebookDragLeave('none')"
              @drop="onDropOnNotebook($event, 'none')"
            >
              <span class="nmg__tag-cloud-name"><v-icon size="15" class="nmg__nb-glyph">mdi-inbox-outline</v-icon>Ohne Notizbuch</span>
              <span class="nmg__tag-cloud-count">{{ notesWithoutNotebookCount }}</span>
            </button>

            <div v-if="creatingNotebook" class="nmg__nb-create">
              <v-icon size="15" class="nmg__nb-glyph">mdi-notebook-plus-outline</v-icon>
              <input
                ref="createNotebookInputRef"
                v-model="newNotebookName"
                class="nmg__nb-name-input"
                type="text"
                maxlength="120"
                placeholder="Notizbuchname …"
                @keydown.enter.prevent.stop="commitCreateNotebook"
                @keydown.esc.prevent.stop="cancelCreateNotebook"
                @blur="commitCreateNotebook"
              />
            </div>
          </div>
        </div>

        <div class="nmg__filter-section" role="group" aria-label="Verwendete Tags">
          <div class="nmg__filter-section-head">
            <span class="nmg__filter-section-title">Tags</span>
          </div>
          <div class="nmg__tag-cloud-items nmg__tag-cloud-items--tags">
            <button
              type="button"
              class="nmg__tag-cloud-chip"
              :class="{ 'is-active': !activeTagId }"
              :aria-pressed="String(!activeTagId)"
              @click="activeTagId = null"
            >
              <span class="nmg__tag-cloud-name">Alle Tags</span>
            </button>

            <button
              v-for="tag in tagCloudItems"
              :key="tag.id"
              type="button"
              class="nmg__tag-cloud-chip"
              :class="{ 'is-active': activeTagId === tag.id }"
              :aria-pressed="String(activeTagId === tag.id)"
              @click="toggleTagFilter(tag.id)"
            >
              <span class="nmg__tag-cloud-name">{{ tag.name }}</span>
              <span class="nmg__tag-cloud-count">{{ tag.count }}</span>
            </button>
          </div>

          <div v-if="!tagCloudItems.length" class="nmg__tag-cloud-empty">
            <span class="nmg__tag-cloud-empty-glyph" aria-hidden="true"><v-icon size="24">mdi-tag-outline</v-icon></span>
            <p class="nmg__tag-cloud-empty-title">Noch keine Tags</p>
            <p class="nmg__tag-cloud-empty-text">Weise einer Notiz ein Tag zu, dann kannst du hier danach filtern.</p>
          </div>
        </div>

        <div class="nmg__filter-section" role="group" aria-label="Ansicht">
          <div class="nmg__filter-section-head">
            <span class="nmg__filter-section-title">Ansicht</span>
          </div>
          <v-menu location="bottom start" :offset="4" :max-height="520" :close-on-content-click="false">
            <template #activator="{ props: sortProps }">
              <button type="button" class="nmg__sort-btn" aria-label="Sortierung" :title="sortLabel" v-bind="sortProps" :disabled="busy">
                <v-icon size="15">mdi-sort</v-icon>
                <span class="nmg__sort-label">{{ sortLabel }}</span>
                <v-icon size="15">mdi-chevron-down</v-icon>
              </button>
            </template>
            <v-list density="compact" class="nmg__sort-list nmg__action-menu">
              <v-list-subheader>Sortieren nach</v-list-subheader>
              <v-list-item
                v-for="opt in NOTE_SORT_OPTIONS"
                :key="opt.value"
                :title="opt.label"
                :active="sortMode === opt.value"
                @click="sortMode = opt.value"
              >
                <template v-if="sortMode === opt.value" #append>
                  <v-icon size="16">mdi-check</v-icon>
                </template>
              </v-list-item>
              <v-divider />
              <v-list-subheader>Reihenfolge</v-list-subheader>
              <v-list-item
                v-for="direction in sortDirectionOptions"
                :key="String(direction.value)"
                :title="direction.label"
                :active="reverseSort === direction.value"
                @click="reverseSort = direction.value"
              >
                <template v-if="reverseSort === direction.value" #append>
                  <v-icon size="16">mdi-check</v-icon>
                </template>
              </v-list-item>
            </v-list>
          </v-menu>
          <v-menu v-for="menu in extraListMenus" :key="menu.key" location="bottom start" :offset="4" :max-height="520">
            <template #activator="{ props: menuProps }">
              <button type="button" class="nmg__sort-btn" v-bind="menuProps" :disabled="busy" :aria-label="menu.label" :title="menu.label">
                <v-icon size="15">{{ menu.key === 'grouping' ? 'mdi-view-agenda-outline' : 'mdi-calendar-range' }}</v-icon>
                <span class="nmg__sort-label">{{ menu.options.find(option => option.value === menu.value)?.label }}</span>
                <v-icon size="15">mdi-chevron-down</v-icon>
              </button>
            </template>
            <v-list density="compact" class="nmg__sort-list nmg__action-menu">
              <v-list-subheader>{{ menu.label }}</v-list-subheader>
              <v-list-item v-for="option in menu.options" :key="option.value" :title="option.label" :active="option.value === menu.value" @click="selectListOption(menu.key, option.value)">
                <template v-if="option.value === menu.value" #append><v-icon size="16">mdi-check</v-icon></template>
              </v-list-item>
              <div v-if="menu.key === 'dateRange'" class="nmg__period-hint">Nach letzter Bearbeitung</div>
            </v-list>
          </v-menu>
        </div>

      </aside>
    </div>

    <DestructiveDialog
      v-model="confirm.open"
      :title="confirm.title"
      :header-subtitle="confirm.subtitle"
      :primary-text="confirm.primaryText"
      secondary-text="Zurück"
      icon="mdi-trash-can-outline"
      :max-width="480"
      :loading="busy"
      :persistent="busy"
      @primary="confirm.onPrimary"
      @close="closeConfirm"
    />

    <DestructiveDialog
      v-model="collectionDelete.open"
      title="Sammlung löschen"
      :header-subtitle="`„${collectionDelete.collection?.name || ''}“ wird gelöscht. Enthaltene Notizen und Notizbücher werden in eine andere Sammlung verschoben.`"
      primary-text="Sammlung löschen"
      secondary-text="Zurück"
      icon="mdi-trash-can-outline"
      :max-width="480"
      :loading="busy"
      :persistent="busy"
      @primary="confirmDeleteCollection"
      @close="closeCollectionDelete"
    >
      <div class="nmg__coll-reassign">
        <label class="nmg__coll-reassign-label">Inhalte verschieben nach</label>
        <v-select
          v-model="collectionDelete.reassignTo"
          :items="collectionDeleteTargets"
          item-title="name"
          item-value="id"
          density="compact"
          variant="outlined"
          hide-details
          :disabled="busy"
        />
      </div>
    </DestructiveDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { noteCollectionColor } from '../../utils/noteCollectionColor.js';
import { noteMatchesDateRange } from '../../utils/noteDateFilter.js';
import { sortNoteItems } from '../../utils/noteSort.js';
import { useNoteListPreferences } from './composables/useNoteListPreferences.js';
import Sortable from 'sortablejs';
import DestructiveDialog from '../DestructiveDialog.vue';
import PmEmptyState from '../PmEmptyState.vue';
import { notifyNoteDeleted } from '../../utils/noteDeletionFeedback.js';
import { patchNote } from '../../api/notes.js';
import { useNotesStore } from '../../stores/notes.js';
import { useTagStore } from '../../stores/tags.js';
import { useSettingsStore } from '../../stores/settings.js';
import { notifyError, useNotifications } from '../../stores/notifications.js';
import NoteTagBar from './NoteTagBar.vue';
import Vorlagenmappe from './Vorlagenmappe.vue';
import GhostAddCard from './GhostAddCard.vue';

const props = defineProps({
  facet: { type: String, default: 'notes' },
  searchQuery: { type: String, default: '' },
  searchScope: { type: String, default: 'all' },
  globalSearchQuery: { type: String, default: '' },
  globalSearchNotes: { type: Array, default: () => [] },
  globalSearchNotebooks: { type: Array, default: () => [] },
  globalSearchLoading: { type: Boolean, default: false },
});

const emit = defineEmits([
  'open-note',
  'open-search-note',
  'select-search-notebook',
  'changed',
  'create-note',
  'notebook-selection-change',
]);

const notesStore = useNotesStore();
const tagStore = useTagStore();
const settingsStore = useSettingsStore();
const { notify } = useNotifications();

const loadingTemplates = ref(false);
const busy = ref(false);
const activeTagId = ref(null);
const tagSidebarOpen = ref(false);

// Notizbuch-Facette: 'all' (alle) | <notebook.id> | 'none' (Ohne Notizbuch).
const activeNotebookId = ref('all');
const editingNotebookId = ref(null);
const editingNotebookName = ref('');
const notebookInputRef = ref(null);
const creatingNotebook = ref(false);
const newNotebookName = ref('');
const createNotebookInputRef = ref(null);

// --- Sammlungen (oberste Ebene, harter Space-Wechsel) ----------------------
const collections = computed(() => notesStore.collections);
const activeCollectionId = computed(() => notesStore.activeCollectionId);
const creatingCollection = ref(false);
const newCollectionName = ref('');
const createCollectionInputRef = ref(null);
const editingCollectionId = ref(null);
const editingCollectionName = ref('');
const collectionInputRef = ref(null);
const collectionDelete = ref({ open: false, collection: null, reassignTo: null });
const collectionDeleteTargets = computed(() =>
  collections.value.filter((c) => c.id !== collectionDelete.value.collection?.id),
);
function collectionDotStyle(c) {
  return { '--nmg-coll-dot': c?.color || 'var(--pm-accent, #006b75)' };
}

const notebooks = computed(() => notesStore.notebooks);
const notesWithoutNotebookCount = computed(
  () => allNotes.value.filter((n) => !n.notebook_id).length,
);

// --- Notizbücher per Drag umsortieren (SortableJS) -------------------------
const notebookListRef = ref(null);
let notebookSortable = null;

function setupNotebookSortable() {
  if (notebookSortable || !notebookListRef.value) return;
  notebookSortable = Sortable.create(notebookListRef.value, {
    animation: 160,
    // Nur echte Notizbuch-Zeilen sind sortierbar; „Alle Notizen"/„Ohne Notizbuch"
    // und die Anlege-Zeile bleiben fix. Der Griff ist der Chip (Kebab ausgenommen).
    draggable: '.nmg__nb-row',
    handle: '.nmg__nb-chip',
    filter: '.nmg__nb-kebab',
    ghostClass: 'nmg__nb-row--drag-ghost',
    chosenClass: 'nmg__nb-row--drag-chosen',
    // Pointer-basierter Drag (wie im DocumentReader): einheitlich, kollidiert
    // nicht mit dem nativen HTML5-DnD der Karten (#5).
    forceFallback: true,
    fallbackTolerance: 4,
    onEnd: onNotebookSortEnd,
  });
}

function teardownNotebookSortable() {
  notebookSortable?.destroy();
  notebookSortable = null;
}

async function onNotebookSortEnd() {
  const rows = notebookListRef.value
    ? [...notebookListRef.value.querySelectorAll('.nmg__nb-row')]
    : [];
  const ids = rows.map((el) => el.getAttribute('data-nb-id')).filter(Boolean);
  if (!ids.length) return;
  // Reihenfolge unverändert? Nichts tun.
  const current = notebooks.value.map((nb) => nb.id);
  if (ids.length === current.length && ids.every((id, i) => id === current[i])) return;
  try {
    await notesStore.reorderNotebooks(ids);
  } catch (error) {
    notifyError(error, 'Die Reihenfolge konnte nicht gespeichert werden.');
    notesStore.fetchNotebooks().catch(() => {});
  }
}
const activeNotebookLabel = computed(() => {
  if (facet.value !== 'notes' || activeNotebookId.value === 'all') return '';
  if (activeNotebookId.value === 'none') return 'Ohne Notizbuch';
  return notebooks.value.find((nb) => nb.id === activeNotebookId.value)?.name || '';
});

// Notizbuch einer Notiz (für den Zugehörigkeits-Chip auf der Karte). Als Map,
// damit die Auflösung je Karte nicht linear über alle Notizbücher läuft.
const notebooksById = computed(() => {
  const map = new Map();
  for (const nb of notebooks.value) map.set(nb.id, nb);
  return map;
});
function notebookFor(note) {
  return note.notebook_id ? notebooksById.value.get(note.notebook_id) || null : null;
}
// Die Sammlung bestimmt die Farbe aller enthaltenen Notizen und Notizbücher.
function collectionAccentStyle(note) {
  return { '--nmg-collection-accent': noteCollectionColor(note, collections.value) || 'var(--pm-accent, #006b75)' };
}

function selectNotebook(notebookId) {
  if (notebookId !== 'none' && !notebooks.value.some((notebook) => notebook.id === notebookId)) return;
  activeNotebookId.value = notebookId;
  tagSidebarOpen.value = true;
}

function openFilterSidebar() {
  tagSidebarOpen.value = true;
}

defineExpose({ selectNotebook, openFilterSidebar });

// Gleiche Sortieroptionen wie in der Liste, unabhängig davon gespeichert.
const NOTE_SORT_OPTIONS = [
  { value: 'updated', label: 'Zuletzt bearbeitet' },
  { value: 'created', label: 'Erstellungsdatum' },
  { value: 'title', label: 'Titel' },
];
const { sortMode, reverseSort, grouping, dateRange } = useNoteListPreferences(
  () => settingsStore.settingsDraft.ui.notes_sort_order,
  undefined,
  'pm-notes-manage-preferences-v1',
);
const GROUPING_OPTIONS = [
  { value: 'auto', label: 'Automatisch' },
  { value: 'date', label: 'Nach Datum' },
  { value: 'notebook', label: 'Nach Notizbuch' },
  { value: 'none', label: 'Ohne Gruppen' },
];
const DATE_RANGE_OPTIONS = [
  { value: '', label: 'Alle Zeiträume' },
  { value: 'today', label: 'Heute' },
  { value: 'last_7_days', label: 'Letzte 7 Tage' },
  { value: 'last_30_days', label: 'Letzte 30 Tage' },
];
const extraListMenus = computed(() => [
  { key: 'grouping', label: 'Gruppierung', value: grouping.value, options: GROUPING_OPTIONS },
  { key: 'dateRange', label: 'Zeitraum', value: dateRange.value, options: DATE_RANGE_OPTIONS },
]);
function selectListOption(key, value) {
  if (key === 'grouping') grouping.value = value;
  if (key === 'dateRange') dateRange.value = value;
}
const sortDirectionOptions = computed(() => sortMode.value === 'title'
  ? [{ value: false, label: 'A–Z' }, { value: true, label: 'Z–A' }]
  : [{ value: false, label: 'Neueste zuerst' }, { value: true, label: 'Älteste zuerst' }]);
const sortLabel = computed(() => {
  const label = NOTE_SORT_OPTIONS.find(option => option.value === sortMode.value)?.label || 'Sortierung';
  const direction = sortDirectionOptions.value.find(option => option.value === reverseSort.value).label;
  return `${label} · ${direction}`;
});
function sortItems(items) {
  return sortNoteItems(items, sortMode.value, reverseSort.value);
}

const editingId = ref(null);
const editingTitle = ref('');
const titleInputRef = ref(null);

const confirm = ref({ open: false, title: '', subtitle: '', primaryText: '', onPrimary: () => {} });

// Bewusst Kopien: Der Store mutiert `notes` teils in-place (z. B. unshift beim
// Anlegen). Ein Spread liest Länge und alle Indizes und stellt so die tiefe
// Reaktivität her – sonst bliebe der Computed an der unveränderten Referenz hängen.
const allNotes = computed(() => [...notesStore.notes]);
const templateNotes = computed(() => [...notesStore.templates]);

const facet = computed(() => (props.facet === 'templates' ? 'templates' : 'notes'));

const facetItems = computed(() => {
  if (facet.value === 'templates') return templateNotes.value;
  return allNotes.value;
});

const normalizedQuery = computed(() => String(props.searchQuery || '').trim().toLocaleLowerCase('de-DE'));
const normalizedGlobalSearchQuery = computed(() => String(props.globalSearchQuery || '').trim());
const isGlobalSearching = computed(() => Boolean(normalizedGlobalSearchQuery.value));

watch(isGlobalSearching, (active, wasActive) => {
  if (!active || wasActive) return;
  activeNotebookId.value = 'all';
  activeTagId.value = null;
});

const filteredGlobalSearchNotes = computed(() => {
  let items = [...props.globalSearchNotes];
  if (activeNotebookId.value === 'none') {
    items = items.filter((note) => !note.notebook_id);
  } else if (activeNotebookId.value !== 'all') {
    items = items.filter((note) => note.notebook_id === activeNotebookId.value);
  }
  if (activeTagId.value) {
    items = items.filter((note) => (note.tags || []).some((tag) => tag.id === activeTagId.value));
  }
  return sortItems(items.filter(note => noteMatchesDateRange(note, dateRange.value)));
});

const globalSearchResultLabel = computed(() => {
  if (props.globalSearchLoading && !props.globalSearchNotes.length && !props.globalSearchNotebooks.length) return 'Suche …';
  const total = filteredGlobalSearchNotes.value.length + props.globalSearchNotebooks.length;
  return `${total} Treffer für „${normalizedGlobalSearchQuery.value}“`;
});

function globalSearchHighlightParts(value) {
  const text = String(value || '');
  const terms = [...new Set(
    normalizedGlobalSearchQuery.value.split(/\s+/).map((term) => term.trim()).filter(Boolean),
  )].sort((a, b) => b.length - a.length);
  if (!terms.length) return [{ text, match: false }];
  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(${escaped.join('|')})`, 'giu');
  const normalizedTerms = new Set(terms.map((term) => term.toLocaleLowerCase('de-DE')));
  return text.split(pattern).filter(Boolean).map((part) => ({
    text: part,
    match: normalizedTerms.has(part.toLocaleLowerCase('de-DE')),
  }));
}

const visibleItems = computed(() => {
  let items = facetItems.value;
  // Notizbuch-Facette (nur Notizen). 'all' zeigt alles, 'none' nur ohne Buch.
  if (facet.value === 'notes' && activeNotebookId.value !== 'all') {
    if (activeNotebookId.value === 'none') {
      items = items.filter((n) => !n.notebook_id);
    } else {
      items = items.filter((n) => n.notebook_id === activeNotebookId.value);
    }
  }
  // Tag-Filter (nur Notizen; Vorlagen tragen im Verwaltungsfluss keine Tags).
  if (facet.value === 'notes' && activeTagId.value) {
    items = items.filter((n) => (n.tags || []).some((t) => t.id === activeTagId.value));
  }
  const q = normalizedQuery.value;
  if (q) {
    const terms = q.split(/\s+/).filter(Boolean);
    const scope = props.searchScope;
    items = items.filter((n) => {
      const title = String(n.title || '').toLocaleLowerCase('de-DE');
      const body = String(n.preview || '').toLocaleLowerCase('de-DE');
      const hay = scope === 'title' ? title : scope === 'body' ? body : `${title} ${body}`;
      return terms.every((t) => hay.includes(t));
    });
  }
  return sortItems(facet.value === 'notes'
    ? items.filter(note => noteMatchesDateRange(note, dateRange.value))
    : items);
});

// Datumsgruppen folgen der Sortierrichtung. Titel werden ohne Datumsgruppen
// alphabetisch sortiert; Favoriten bleiben als eigene Gruppe oben.
const GROUP_ORDER = ['favorites', 'today', 'yesterday', 'week', 'month', 'older'];
const GROUP_LABELS = {
  favorites: 'Favoriten',
  notes: 'Notizen',
  today: 'Heute',
  yesterday: 'Gestern',
  week: 'Diese Woche',
  month: 'Diesen Monat',
  older: 'Älter',
};
function startOfDay(value) {
  const d = new Date(value);
  d.setHours(0, 0, 0, 0);
  return d;
}
function groupBucket(note) {
  // Favorisierte Notizen stehen – unabhängig vom Datum – oben in einer eigenen Gruppe.
  if (note.is_favorite) return 'favorites';
  if (grouping.value === 'auto' && sortMode.value === 'title') return 'notes';
  const raw = (sortMode.value === 'created' ? note.created_at : note.updated_at) || note.updated_at;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return 'older';
  const now = new Date();
  const diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  if (diffDays <= 0) return 'today';
  if (diffDays === 1) return 'yesterday';
  if (diffDays <= 6) return 'week';
  if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) return 'month';
  return 'older';
}
const groupedItems = computed(() => {
  if (grouping.value === 'none') return [{ key: 'all', label: '', notes: visibleItems.value }];
  if (grouping.value === 'notebook') {
    const groups = new Map();
    for (const note of visibleItems.value) {
      const key = note.notebook_id || 'none';
      if (!groups.has(key)) groups.set(key, { key, label: notebooksById.value.get(key)?.name || 'Ohne Notizbuch', notes: [] });
      groups.get(key).notes.push(note);
    }
    return [...groups.values()].sort((a, b) => a.key === 'none' ? 1 : b.key === 'none' ? -1 : a.label.localeCompare(b.label, 'de-DE'));
  }
  const buckets = new Map();
  for (const note of visibleItems.value) {
    const key = groupBucket(note);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(note);
  }
  const dates = GROUP_ORDER.filter(key => key !== 'favorites');
  const order = grouping.value === 'auto' && sortMode.value === 'title'
    ? ['favorites', 'notes']
    : ['favorites', ...(reverseSort.value ? dates.reverse() : dates)];
  return order
    .filter((key) => buckets.has(key))
    .map((key) => ({ key, label: GROUP_LABELS[key], notes: buckets.get(key) }));
});

// Nur tatsächlich vergebene Tags (mit Häufigkeit) als Filter-Wolke anbieten.
const usedTags = computed(() => {
  if (facet.value !== 'notes' && !isGlobalSearching.value) return [];
  const counts = new Map();
  for (const note of allNotes.value) {
    for (const tag of note.tags || []) {
      const entry = counts.get(tag.id) || { id: tag.id, name: tag.name, count: 0 };
      entry.count += 1;
      counts.set(tag.id, entry);
    }
  }
  return [...counts.values()].sort((a, b) => a.name.localeCompare(b.name, 'de-DE'));
});

const tagCloudItems = computed(() => usedTags.value);

// allTags-Pool für den Karten-Picker: alle Owner-Tags + die der Notiz (Namen).
function allTagsForCard(note) {
  const map = new Map();
  for (const t of tagStore.tags || []) map.set(String(t.id), { id: String(t.id), name: t.name });
  for (const t of note.tags || []) if (!map.has(String(t.id))) map.set(String(t.id), { id: String(t.id), name: t.name });
  return [...map.values()];
}

function toggleTagFilter(tagId) {
  activeTagId.value = activeTagId.value === tagId ? null : tagId;
}

async function applyCardTags(note, tagIds) {
  try {
    const updated = await notesStore.setTags(note.id, { tagIds });
    note.tags = updated.tags || [];
    // Gefiltertes Tag entfernt? Filter zurücksetzen, damit die Karte nicht springt.
    if (activeTagId.value && !(note.tags || []).some((t) => t.id === activeTagId.value)) {
      // nur zurücksetzen, wenn keine Notiz mehr das Tag trägt
      if (!allNotes.value.some((n) => (n.tags || []).some((t) => t.id === activeTagId.value))) {
        activeTagId.value = null;
      }
    }
  } catch (error) {
    notifyError(error, 'Tags konnten nicht gespeichert werden.');
  }
}

const isLoading = computed(() => facet.value === 'templates' && loadingTemplates.value);

const emptyState = computed(() => {
  if (dateRange.value && !normalizedQuery.value) {
    return { title: 'Keine Notizen in diesem Zeitraum', subtitle: 'Wähle einen anderen Zeitraum oder alle Zeiträume.' };
  }
  if (normalizedQuery.value) {
    return { icon: 'mdi-note-search-outline', title: 'Keine Treffer', subtitle: 'Passe den Suchbegriff an oder leere die globale Suche.' };
  }
  if (facet.value === 'templates') {
    return { icon: 'mdi-file-document-multiple-outline', title: 'Keine Vorlagen', subtitle: 'Speichere eine Notiz als Vorlage, um sie hier zu verwalten.' };
  }
  return { icon: 'mdi-note-outline', title: 'Noch keine Notizen', subtitle: 'Halte Gedanken und Fundstellen an einem Ort fest.' };
});

onMounted(async () => {
  tagStore.fetchTags().catch(() => {});
  notesStore.ensureCollectionsLoaded().catch(() => {});
  notesStore.ensureNotebooksLoaded().catch(() => {});
  nextTick(setupNotebookSortable);
  if (notesStore.templatesLoaded) return;
  loadingTemplates.value = true;
  try {
    await notesStore.ensureTemplatesLoaded();
  } finally {
    loadingTemplates.value = false;
  }
});

// Der Notizbuch-Container existiert nur im Notizen-Facet; Sortable an- bzw.
// abmelden, wenn er auftaucht/verschwindet.
watch(notebookListRef, (el) => {
  if (el) setupNotebookSortable();
  else teardownNotebookSortable();
});

onBeforeUnmount(teardownNotebookSortable);

watch(facet, () => {
  cancelRename();
  closeConfirm();
  activeTagId.value = null;
  activeNotebookId.value = 'all';
  cancelCreateNotebook();
  cancelRenameNotebook();
  tagSidebarOpen.value = false;
});

watch(
  activeNotebookLabel,
  (label) => emit('notebook-selection-change', label),
  { immediate: true },
);

watch(usedTags, (tags) => {
  if (activeTagId.value && !tags.some((tag) => tag.id === activeTagId.value)) {
    activeTagId.value = null;
  }
});

// Gefiltertes Notizbuch verschwunden (gelöscht)? Auf „Alle" zurückfallen.
watch(notebooks, (list) => {
  if (
    activeNotebookId.value !== 'all'
    && activeNotebookId.value !== 'none'
    && !list.some((nb) => nb.id === activeNotebookId.value)
  ) {
    activeNotebookId.value = 'all';
  }
});

function onCardClick(note) {
  if (facet.value === 'notes') emit('open-note', note.id);
}

// --- Inline-Umbenennen -----------------------------------------------------
function startRename(note) {
  editingId.value = note.id;
  editingTitle.value = note.title || '';
  nextTick(() => {
    const el = Array.isArray(titleInputRef.value) ? titleInputRef.value[0] : titleInputRef.value;
    el?.focus?.();
    el?.select?.();
  });
}

function cancelRename() { editingId.value = null; }

async function commitRename(note) {
  if (editingId.value !== note.id) return;
  const title = editingTitle.value.trim().slice(0, 500);
  editingId.value = null;
  if (title === (note.title || '').trim()) return;
  try {
    const updated = await patchNote(note.id, { title });
    // Das Listenobjekt ist dieselbe Referenz wie im Store → Mutation genügt.
    note.title = updated.title;
    note.updated_at = updated.updated_at;
  } catch (error) {
    notifyError(error, 'Der Titel konnte nicht gespeichert werden.');
  }
}

// --- Kartenaktionen --------------------------------------------------------
// Favoriten-Stern wie bei den Dokumenten: Die Pop-Animation läuft bewusst nur
// beim aktiven Setzen (nicht am Zustand), damit sie nicht bei jedem Rerender feuert.
const animatingFavoriteId = ref(null);
let favoriteAnimTimer = null;

async function toggleFavorite(note) {
  if (!note?.id) return;
  const next = !note.is_favorite;
  if (next) {
    animatingFavoriteId.value = note.id;
    if (favoriteAnimTimer) window.clearTimeout(favoriteAnimTimer);
    favoriteAnimTimer = window.setTimeout(() => {
      animatingFavoriteId.value = null;
      favoriteAnimTimer = null;
    }, 480);
  }
  try {
    await notesStore.setFavorite(note.id, next);
    emit('changed');
  } catch (error) {
    notifyError(error, 'Der Favoriten-Status konnte nicht gespeichert werden.');
  }
}

async function trashNote(note) {
  if (busy.value || !note?.id) return;
  busy.value = true;
  try {
    await notesStore.remove(note.id);
    emit('changed');
    notifyNoteDeleted(note, { restore: notesStore.restore, onRestored: () => emit('changed') });
  } catch (error) {
    notifyError(error, 'Die Notiz konnte nicht in den Papierkorb verschoben werden.');
  } finally {
    busy.value = false;
  }
}

async function saveNoteAsTemplate(note) {
  if (busy.value || !note?.id) return;
  busy.value = true;
  try {
    const template = await notesStore.saveAsTemplate(note.id, { title: note.title || '' });
    const title = template.title?.trim() || 'Ohne Titel';
    notify({
      type: 'success',
      title: 'Vorlage gespeichert',
      message: `„${title}“ wurde zu deinen Vorlagen hinzugefügt.`,
      critical: true,
    });
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Vorlage konnte nicht gespeichert werden.');
  } finally {
    busy.value = false;
  }
}

async function createNoteFromTemplate(template) {
  if (busy.value || !template?.id) return;
  busy.value = true;
  try {
    const note = await notesStore.createFromTemplate(template.id);
    emit('changed');
    emit('open-note', note.id, { cursorPosition: 'end' });
  } catch (error) {
    notifyError(error, 'Aus der Vorlage konnte keine Notiz erstellt werden.');
  } finally {
    busy.value = false;
  }
}

function requestTemplateDeletion(template) {
  if (busy.value || !template?.id) return;
  const title = template.title?.trim() || 'Ohne Titel';
  openConfirm({
    title: 'Vorlage löschen?',
    subtitle: `„${title}“ wird unwiderruflich gelöscht.`,
    primaryText: 'Endgültig löschen',
    onPrimary: () => deleteTemplate(template),
  });
}

async function deleteTemplate(template) {
  if (busy.value || !template?.id) return;
  busy.value = true;
  try {
    await notesStore.deletePermanently(template.id);
    await notesStore.fetchTemplates();
    confirm.value = { ...confirm.value, open: false };
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Vorlage konnte nicht gelöscht werden.');
  } finally {
    busy.value = false;
  }
}

function openConfirm({ title, subtitle, primaryText, onPrimary }) {
  confirm.value = { open: true, title, subtitle, primaryText, onPrimary };
}

function closeConfirm() {
  if (busy.value) return;
  confirm.value = { ...confirm.value, open: false };
}

// --- Notizbücher -----------------------------------------------------------
// --- Karte per Drag in ein Notizbuch ziehen (natives HTML5-DnD) -----------
// Kollidiert nicht mit dem forceFallback-Sortable der Notizbuchliste (das nutzt
// Pointer-Events, kein natives DnD).
const draggingNoteId = ref(null);
const dropTargetId = ref(null);
let draggedNote = null;

function onCardDragStart(event, note) {
  // Aus interaktiven Bereichen (Titel-Edit, Tags, Aktionsbuttons) KEINE
  // Karten-Verschiebung starten – dort will man tippen/klicken, nicht ziehen.
  if (event.target?.closest?.('input, button, a, .nmg-card__foot, .nmg-card__actions')) {
    event.preventDefault();
    return;
  }
  draggedNote = note;
  draggingNoteId.value = note.id;
  try {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', note.id);
  } catch { /* dataTransfer kann in manchen Umgebungen fehlen */ }
}

function onCardDragEnd() {
  draggingNoteId.value = null;
  dropTargetId.value = null;
  draggedNote = null;
}

function onNotebookDragOver(event, targetId) {
  if (!draggingNoteId.value) return; // nur bei laufendem Karten-Drag
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  dropTargetId.value = targetId;
}

function onNotebookDragLeave(targetId) {
  if (dropTargetId.value === targetId) dropTargetId.value = null;
}

async function onDropOnNotebook(event, targetId) {
  if (!draggingNoteId.value) return;
  event.preventDefault();
  const note = draggedNote;
  dropTargetId.value = null;
  const notebookId = targetId === 'none' ? null : targetId;
  await moveNoteToNotebook(note, notebookId);
}

async function moveNoteToNotebook(note, notebookId) {
  if (!note?.id || note.notebook_id === notebookId) return;
  try {
    await notesStore.moveToNotebook([note.id], notebookId);
    const target = notebookId
      ? notebooks.value.find((nb) => nb.id === notebookId)?.name
      : null;
    notify({
      type: 'success',
      title: target ? 'Verschoben' : 'Aus Notizbuch genommen',
      message: target ? `Notiz nach „${target}“ verschoben.` : 'Notiz liegt nun in keinem Notizbuch.',
    });
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Notiz konnte nicht verschoben werden.');
  }
}

async function moveNoteToCollection(note, collectionId) {
  if (!note?.id || note.collection_id === collectionId) return;
  try {
    await notesStore.moveToCollection([note.id], collectionId);
    const target = collections.value.find((c) => c.id === collectionId)?.name;
    notify({
      type: 'success',
      title: 'In Sammlung verschoben',
      message: `Notiz nach „${target}“ verschoben (Notizbuch entfernt).`,
    });
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Notiz konnte nicht in die Sammlung verschoben werden.');
  }
}

function focusInput(refValue) {
  nextTick(() => {
    const el = Array.isArray(refValue.value) ? refValue.value[0] : refValue.value;
    el?.focus?.();
    el?.select?.();
  });
}

function startCreateNotebook() {
  cancelRenameNotebook();
  creatingNotebook.value = true;
  newNotebookName.value = '';
  focusInput(createNotebookInputRef);
}

function openSidebarAndCreateNotebook() {
  tagSidebarOpen.value = true;
  startCreateNotebook();
}

function cancelCreateNotebook() {
  creatingNotebook.value = false;
  newNotebookName.value = '';
}

async function commitCreateNotebook() {
  if (!creatingNotebook.value) return;
  const name = newNotebookName.value.trim();
  // Beim Verlassen ohne Namen einfach abbrechen (kein Fehler).
  creatingNotebook.value = false;
  newNotebookName.value = '';
  if (!name) return;
  try {
    const nb = await notesStore.createNotebook({ name });
    activeNotebookId.value = nb.id;
  } catch (error) {
    notifyError(error, 'Das Notizbuch konnte nicht angelegt werden.');
  }
}

function startRenameNotebook(nb) {
  cancelCreateNotebook();
  editingNotebookId.value = nb.id;
  editingNotebookName.value = nb.name;
  focusInput(notebookInputRef);
}

function cancelRenameNotebook() {
  editingNotebookId.value = null;
  editingNotebookName.value = '';
}

async function commitRenameNotebook(nb) {
  if (editingNotebookId.value !== nb.id) return;
  const name = editingNotebookName.value.trim().slice(0, 120);
  editingNotebookId.value = null;
  if (!name || name === nb.name) return;
  try {
    await notesStore.updateNotebook(nb.id, { name });
  } catch (error) {
    notifyError(error, 'Das Notizbuch konnte nicht umbenannt werden.');
  }
}

// Kompakte, in beiden Themes tragfähige Sammlungsfarben.
const COLLECTION_COLORS = ['#0d9488', '#2563eb', '#7c3aed', '#db2777', '#c2410c', '#ca8a04', '#4b5563'];

function requestNotebookDeletion(nb) {
  if (busy.value || !nb?.id) return;
  openConfirm({
    title: 'Notizbuch löschen?',
    subtitle: `„${nb.name}“ wird gelöscht. Die enthaltenen Notizen bleiben erhalten und liegen danach in keinem Notizbuch.`,
    primaryText: 'Notizbuch löschen',
    onPrimary: () => deleteNotebook(nb),
  });
}

async function deleteNotebook(nb) {
  if (busy.value || !nb?.id) return;
  busy.value = true;
  try {
    await notesStore.deleteNotebook(nb.id);
    if (activeNotebookId.value === nb.id) activeNotebookId.value = 'all';
    confirm.value = { ...confirm.value, open: false };
    emit('changed');
  } catch (error) {
    notifyError(error, 'Das Notizbuch konnte nicht gelöscht werden.');
  } finally {
    busy.value = false;
  }
}

// --- Sammlungen: Wechsel + CRUD --------------------------------------------
async function chooseCollection(id) {
  if (busy.value || id === activeCollectionId.value) return;
  activeNotebookId.value = 'all'; // Notizbuch-Facette gehört zur alten Sammlung.
  try {
    await notesStore.setActiveCollection(id);
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Sammlung konnte nicht gewechselt werden.');
  }
}

function startCreateCollection() {
  cancelRenameCollection();
  tagSidebarOpen.value = true;
  creatingCollection.value = true;
  newCollectionName.value = '';
  focusInput(createCollectionInputRef);
}

function cancelCreateCollection() {
  creatingCollection.value = false;
  newCollectionName.value = '';
}

async function commitCreateCollection() {
  if (!creatingCollection.value) return;
  const name = newCollectionName.value.trim();
  creatingCollection.value = false;
  newCollectionName.value = '';
  if (!name) return;
  try {
    const c = await notesStore.createCollection({ name });
    await chooseCollection(c.id);
  } catch (error) {
    notifyError(error, 'Die Sammlung konnte nicht angelegt werden.');
  }
}

function startRenameCollection(c) {
  cancelCreateCollection();
  editingCollectionId.value = c.id;
  editingCollectionName.value = c.name;
  focusInput(collectionInputRef);
}

function cancelRenameCollection() {
  editingCollectionId.value = null;
  editingCollectionName.value = '';
}

async function commitRenameCollection(c) {
  if (editingCollectionId.value !== c.id) return;
  const name = editingCollectionName.value.trim().slice(0, 120);
  editingCollectionId.value = null;
  if (!name || name === c.name) return;
  try {
    await notesStore.updateCollection(c.id, { name });
  } catch (error) {
    notifyError(error, 'Die Sammlung konnte nicht umbenannt werden.');
  }
}

async function setCollectionColor(c, color) {
  const next = c.color === color ? null : color; // erneute Wahl = zurücksetzen
  try {
    await notesStore.updateCollection(c.id, { color: next });
  } catch (error) {
    notifyError(error, 'Die Farbe konnte nicht gespeichert werden.');
  }
}

function requestCollectionDeletion(c) {
  if (busy.value || !c?.id || collections.value.length <= 1) return;
  const target = collections.value.find((x) => x.id !== c.id) || null;
  collectionDelete.value = { open: true, collection: c, reassignTo: target?.id || null };
}

function closeCollectionDelete() {
  collectionDelete.value = { ...collectionDelete.value, open: false };
}

async function confirmDeleteCollection() {
  const target = collectionDelete.value;
  if (busy.value || !target.collection?.id) return;
  busy.value = true;
  try {
    await notesStore.deleteCollection(target.collection.id, { reassignTo: target.reassignTo });
    activeNotebookId.value = 'all';
    collectionDelete.value = { open: false, collection: null, reassignTo: null };
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Sammlung konnte nicht gelöscht werden.');
  } finally {
    busy.value = false;
  }
}

function snippet(note) {
  return note.preview?.trim().replace(/\s+/g, ' ') || 'Leer';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const time = date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  if (date.toDateString() === now.toDateString()) return `heute ${time}`;
  if (date.toDateString() === yesterday.toDateString()) return `gestern ${time}`;
  return date.toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'short',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  });
}
</script>

<style scoped>
.nmg {
  display: flex;
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

/* Raster und Filter teilen sich die Verwaltungsfläche. */
.nmg__body {
  position: relative;
  display: flex;
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.nmg__tag-sidebar {
  display: flex;
  width: clamp(270px, 27vw, 320px);
  min-height: 0;
  flex: none;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
  border-left: 1px solid var(--pm-divider, #d8dfe1);
  background: color-mix(in srgb, var(--pm-app-surface, #fff) 96%, var(--pm-accent, #006b75));
}

.nmg__tag-sidebar-head,
.nmg__tag-sidebar-actions {
  display: flex;
  align-items: center;
}

.nmg__tag-sidebar-head {
  display: none;
  justify-content: flex-end;
  min-height: 49px;
  flex: 0 0 auto;
  gap: 8px;
  padding: 7px 8px 7px 12px;
}

.nmg__tag-sidebar-actions {
  flex: 0 0 auto;
  gap: 2px;
}

.nmg__tag-sidebar-action,
.nmg__tag-sidebar-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: var(--pm-muted, #64748b);
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}

.nmg__tag-sidebar-action {
  width: 30px;
  height: 30px;
  border-radius: 8px;
}

.nmg__tag-sidebar-action:hover,
.nmg__tag-sidebar-action:focus-visible,
.nmg__tag-sidebar-toggle:hover,
.nmg__tag-sidebar-toggle:focus-visible {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 52%, transparent);
  color: var(--pm-text, #0e181b);
  outline: none;
}

.nmg__tag-sidebar-close,
.nmg__tag-sidebar-toggle {
  display: none;
}

.nmg__tag-cloud {
  --pm-detail-chip-bg: var(--pm-chip-bg, rgba(var(--v-theme-on-surface), 0.06));
  --pm-detail-chip-border: color-mix(in srgb, var(--pm-chip-text, var(--pm-text)) 14%, transparent);
  --pm-detail-chip-count: var(--pm-chip-count, var(--pm-muted));
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding: 4px 16px 18px;
}

/* Einheitliche Filter-Chips */
.nmg__tag-cloud-items {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  align-items: center;
  gap: 7px;
}
.nmg__tag-cloud-items--tags {
  --pm-detail-chip-border: var(--pm-divider, #d8dfe1);
}

.nmg__tag-cloud-chip {
  display: inline-flex;
  height: 26px;
  width: auto;
  max-width: min(220px, 100%);
  min-width: 0;
  flex: 0 1 auto;
  align-items: center;
  gap: 5px;
  padding: 0 7px 0 11px;
  border: 1px solid var(--pm-detail-chip-border);
  border-radius: 15px;
  background: var(--pm-detail-chip-bg);
  box-shadow: none;
  color: rgba(var(--v-theme-on-surface), 0.88);
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1.2;
  text-align: left;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}
.nmg__tag-cloud-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nmg__tag-cloud-count {
  flex: none;
  min-width: 18px;
  margin-inline-start: 1px;
  padding: 0;
  border-radius: 0;
  font-size: 0.7rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: center;
  color: var(--pm-detail-chip-count);
  background: transparent;
}
.nmg__tag-cloud-chip:hover,
.nmg__tag-cloud-chip:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 30%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 7%, var(--pm-chip-bg, #e7eef0));
  color: var(--pm-text, #0e181b);
  outline: none;
}
.nmg__tag-cloud-chip.is-active {
  border-color: var(--pm-accent, #006b75);
  background: var(--pm-accent, #006b75);
  color: var(--pm-on-accent, #fff);
  font-weight: 600;
}
.nmg__tag-cloud-chip.is-active .nmg__tag-cloud-count {
  color: var(--pm-on-accent, #fff);
  background: transparent;
}

/* Leerzustand */
.nmg__tag-cloud-empty {
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 2px;
  padding: 24px 12px;
}
.nmg__tag-cloud-empty-glyph {
  margin-bottom: 7px;
  color: var(--pm-muted, #64748b);
  opacity: 0.52;
}
.nmg__tag-cloud-empty-title { margin: 0; font-size: 0.82rem; font-weight: 620; color: var(--pm-text, #0f172a); }
.nmg__tag-cloud-empty-text { margin: 0; max-width: 24ch; font-size: 0.74rem; line-height: 1.5; color: var(--pm-muted, #64748b); }

/* Filter-Abschnitte (Notizbücher + Tags in einer Seitenleiste) */
.nmg__filter-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 16px 14px;
}
.nmg__filter-section + .nmg__filter-section {
  border-top: 1px solid color-mix(in srgb, var(--pm-text, #0f172a) 8%, transparent);
  padding-top: 14px;
}
.nmg__tag-sidebar-head + .nmg__filter-section {
  padding-top: 16px;
}
.nmg__period-hint { padding: 4px 16px 8px; color: var(--pm-muted); font-size: 0.7rem; }

.nmg__filter-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.nmg__filter-section-title {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pm-muted, #64748b);
}

/* --- Sammlungs-Switcher (oberste Schale) --------------------------------- */
.nmg__coll-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.nmg__coll-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.nmg__coll-chip {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 10px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--pm-text, #0f172a);
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  transition: background 0.16s ease, border-color 0.16s ease;
}
.nmg__coll-chip:hover,
.nmg__coll-chip:focus-visible {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 8%, transparent);
}
.nmg__coll-chip.is-active {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 14%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 32%, transparent);
}
.nmg__coll-dot {
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--nmg-coll-dot, var(--pm-accent, #006b75));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #000 12%, transparent);
}
.nmg__coll-dot--ghost {
  background: transparent;
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--pm-muted, #64748b) 55%, transparent);
}
.nmg__coll-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nmg__coll-count {
  flex: 0 0 auto;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--pm-muted, #64748b);
}
.nmg__coll-chip.is-active .nmg__coll-count {
  color: var(--pm-accent, #006b75);
}
/* Umbenennen/Anlegen einer Sammlung: identisches gerahmtes Feld wie bei
   Notizbüchern (nmg__nb-editing / nmg__nb-create) – solider Rahmen beim
   Umbenennen, gestrichelter beim Anlegen. */
.nmg__coll-editing,
.nmg__coll-create {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 30px;
  padding: 0 11px;
  border-radius: 15px;
}
.nmg__coll-editing {
  border: 1px solid var(--pm-accent, #006b75);
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0f172a);
}
.nmg__coll-create {
  border: 1px dashed color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 5%, transparent);
}
.nmg__coll-reassign {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}
.nmg__coll-reassign-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--pm-muted, #64748b);
}
.nmg__move-divider {
  margin: 4px 0;
}
.nmg__filter-section-add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 1px solid var(--pm-detail-chip-border, rgba(15, 23, 42, 0.14));
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #64748b);
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}
.nmg__filter-section-add:hover,
.nmg__filter-section-add:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 34%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 8%, transparent);
  color: var(--pm-accent, #006b75);
  outline: none;
}

/* Notizbücher: vertikale, vollbreite Zeilen statt Chip-Wolke */
.nmg__tag-cloud-items--stack {
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: stretch;
  gap: 4px;
}
.nmg__tag-cloud-items--stack > .nmg__tag-cloud-chip {
  width: 100%;
  max-width: 100%;
  height: 30px;
  justify-content: space-between;
  /* Kebab-Spalte rechts freihalten (26px Button + 2px Zeilen-Gap + 7px Basis-
     Padding), damit die Zähler dieser buttonlosen Zeilen in einer Flucht mit den
     Zählern der Notizbuch-Zeilen stehen. */
  padding-right: 35px;
}
.nmg__nb-glyph {
  margin-inline-end: 5px;
  opacity: 0.72;
  flex: none;
}
.nmg__tag-cloud-chip.is-active .nmg__nb-glyph { opacity: 0.95; }
.nmg__nb-row {
  display: flex;
  align-items: center;
  gap: 2px;
  border-radius: 15px;
}
/* Drag-Reorder (SortableJS): der Griff ist der Chip. */
.nmg__nb-chip { cursor: grab; }
.nmg__nb-row--drag-chosen .nmg__nb-chip { cursor: grabbing; }

/* Karte auf ein Notizbuch ziehen (#5): Drop-Ziel deutlich hervorheben. */
.nmg__tag-cloud-chip.is-drop-target {
  border-color: var(--pm-accent, #006b75);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 16%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-accent, #006b75) 45%, transparent);
}
.nmg-card.is-dragging { opacity: 0.5; }
.nmg__nb-row--drag-ghost {
  opacity: 0.4;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  border-radius: 15px;
}
.nmg__nb-row--drag-chosen { z-index: 2; }
.nmg__nb-chip {
  flex: 1 1 auto;
  min-width: 0;
  /* Volle Zeilenbreite (die 220px-Kappung der Basis-Chips aufheben) und Zähler
     rechtsbündig – so steht er in einer Flucht mit den buttonlosen Zeilen, und
     der Kebab rückt in die feste rechte Spalte. */
  max-width: 100%;
  justify-content: space-between;
}
.nmg__nb-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nmg__nb-name-input {
  min-width: 0;
  width: 100%;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  padding: 0;
  outline: none;
}
.nmg__nb-kebab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex: none;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--pm-muted, #64748b);
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
}
.nmg__nb-row:hover .nmg__nb-kebab,
.nmg__nb-kebab:hover,
.nmg__nb-kebab:focus-visible {
  opacity: 1;
  background: color-mix(in srgb, var(--pm-text, #0f172a) 7%, transparent);
  color: var(--pm-text, #0f172a);
  outline: none;
}
.nmg__nb-create {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 11px;
  border: 1px dashed color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
  border-radius: 15px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 5%, transparent);
}
/* Umbenennen-Zeile: wie die Anlege-Zeile, aber solider Rahmen und deutlicher
   Lesekontrast (Feld erbt die normale Textfarbe, nicht die Aktiv-Weißschrift). */
.nmg__nb-editing {
  display: flex;
  align-items: center;
  width: 100%;
  height: 30px;
  padding: 0 11px;
  border: 1px solid var(--pm-accent, #006b75);
  border-radius: 15px;
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0f172a);
}
.nmg__nb-menu-danger :deep(.v-list-item-title) { color: var(--pm-danger, #c62828); }

/* Notizbuch-Farbauswahl im Kebab-Menü */
/* Kompakte, elegante Kebab-Aktionsmenüs (Sammlung + Notizbuch): Vuetifys
   großzügige Zeilenhöhe, Icon-Abstand und Schrift zähmen. */
.nmg__action-menu {
  padding: 4px;
}
.nmg__action-menu :deep(.v-list-item) {
  min-height: 0;
  padding-block: 6px;
  padding-inline: 10px;
  border-radius: 8px;
}
.nmg__action-menu :deep(.v-list-item__spacer) {
  width: 9px;
}
.nmg__action-menu :deep(.v-list-item__prepend > .v-icon) {
  opacity: 0.62;
}
.nmg__action-menu :deep(.v-list-item-title) {
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.3;
  letter-spacing: 0.005em;
}
.nmg__nb-colors {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: nowrap;
  justify-content: space-between;
  padding: 6px 10px 5px;
}
.nmg__action-menu .nmg__nb-color {
  width: 16px;
  height: 16px;
}
.nmg__nb-color {
  width: 18px;
  height: 18px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--pm-text, #0f172a) 18%, transparent);
  border-radius: 999px;
  background: var(--nb-swatch, transparent);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--pm-muted, #64748b);
  transition: transform 100ms ease, box-shadow 100ms ease;
}
.nmg__nb-color:hover { transform: scale(1.12); }
.nmg__nb-color.is-active {
  box-shadow: 0 0 0 2px var(--pm-app-surface, #fff), 0 0 0 4px color-mix(in srgb, var(--nb-swatch, var(--pm-text, #0f172a)) 60%, transparent);
}
.nmg__nb-color--none { background: transparent; }
.nmg__nb-color--none.is-active {
  box-shadow: 0 0 0 2px var(--pm-app-surface, #fff), 0 0 0 4px color-mix(in srgb, var(--pm-text, #0f172a) 40%, transparent);
}

/* Inhalt */
.nmg__scroll {
  position: relative;
  display: flex;
  width: 0;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
}

.nmg-content-enter-active,
.nmg-content-leave-active {
  transition: opacity 150ms ease, transform 170ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1));
}

.nmg-content-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.nmg-content-leave-to {
  opacity: 0;
  transform: translateY(-3px);
}

.nmg-search-results {
  width: 100%;
  padding: 22px 26px 32px;
}

.nmg-search-results__header {
  display: flex;
  min-height: 52px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
  padding-bottom: 14px;
}

.nmg-search-results__header h2,
.nmg-search-results__header p {
  margin: 0;
}

.nmg-search-results__header h2 {
  color: var(--pm-text, #0f172a);
  font-size: 1rem;
  font-weight: 680;
  line-height: 1.35;
}

.nmg-search-results__header p {
  margin-top: 3px;
  color: var(--pm-muted, #64748b);
  font-size: 0.74rem;
}

.nmg-search-results__header .v-progress-circular {
  margin: 4px 3px 0 0;
  color: var(--pm-accent, #006b75);
}

.nmg-search-results__group {
  margin-top: 22px;
}

.nmg-search-results__group > h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 9px;
  color: var(--pm-muted, #64748b);
  font-size: 0.7rem;
  font-weight: 720;
  letter-spacing: 0.065em;
  text-transform: uppercase;
}

.nmg-search-results__group > h3 span {
  min-width: 19px;
  padding: 1px 5px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-muted, #64748b) 12%, transparent);
  font-size: 0.65rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  text-align: center;
}

.nmg-search-results__notebooks {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 9px;
}

.nmg-search-notebook,
.nmg-search-note {
  border: 1px solid var(--pm-divider, #d8dfe1);
  background: var(--pm-content-surface, #fff);
  color: var(--pm-text, #0f172a);
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color 130ms ease, background-color 130ms ease, box-shadow 130ms ease;
}

.nmg-search-notebook {
  display: grid;
  min-width: 0;
  min-height: 54px;
  grid-template-columns: 32px minmax(0, 1fr) auto 16px;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  border-radius: 10px;
}

.nmg-search-notebook:hover,
.nmg-search-notebook:focus-visible,
.nmg-search-note:hover,
.nmg-search-note:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 42%, var(--pm-divider, #d8dfe1));
  background: color-mix(in srgb, var(--pm-accent, #006b75) 4%, var(--pm-content-surface, #fff));
  box-shadow: 0 4px 14px -10px rgba(15, 23, 42, 0.55);
  outline: none;
}

.nmg-search-notebook__icon,
.nmg-search-note__icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
  color: var(--pm-accent, #006b75);
}

.nmg-search-notebook__name,
.nmg-search-notebook__count {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nmg-search-notebook__name {
  font-size: 0.84rem;
  font-weight: 630;
}

.nmg-search-notebook__count {
  color: var(--pm-muted, #64748b);
  font-size: 0.7rem;
}

.nmg-search-results__notes {
  overflow: hidden;
  margin: 0;
  padding: 0;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  list-style: none;
}

.nmg-search-results__notes li + li {
  border-top: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 76%, transparent);
}

.nmg-search-note {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 76px;
  grid-template-columns: 32px minmax(0, 1fr) minmax(90px, auto) 18px;
  align-items: center;
  gap: 11px;
  padding: 11px 13px;
  border: 0;
  border-radius: 0;
}

.nmg-search-note__content {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.nmg-search-note__content strong,
.nmg-search-note__preview {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nmg-search-note__content strong {
  font-size: 0.84rem;
  font-weight: 650;
}

.nmg-search-note__content strong.is-untitled {
  color: var(--pm-muted, #64748b);
  font-style: italic;
  font-weight: 540;
}

.nmg-search-note__preview {
  color: var(--pm-muted, #64748b);
  font-size: 0.74rem;
  line-height: 1.35;
}

.nmg-search-note__tags {
  display: flex;
  min-width: 0;
  gap: 5px;
  overflow: hidden;
}

.nmg-search-note__tags > span {
  overflow: hidden;
  max-width: 130px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--pm-chip-bg, rgba(var(--v-theme-on-surface), 0.06));
  color: var(--pm-muted, #64748b);
  font-size: 0.66rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nmg-search-note__meta {
  display: flex;
  max-width: 160px;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  color: var(--pm-muted, #64748b);
  font-size: 0.7rem;
}

.nmg-search-note__meta > span {
  display: flex;
  max-width: 100%;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nmg-search-note__meta time {
  white-space: nowrap;
}

.nmg-search-note__open {
  color: var(--pm-muted, #64748b);
  opacity: 0.68;
}

.nmg-search-results .is-match {
  border-radius: 3px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 19%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--pm-accent, #006b75) 8%, transparent);
  padding-inline: 0.08em;
}

.nmg-search-results__empty {
  display: flex;
  min-height: 300px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 6px;
  color: var(--pm-muted, #64748b);
  text-align: center;
}

.nmg-search-results__empty .v-icon {
  margin-bottom: 5px;
  color: var(--pm-accent, #006b75);
  opacity: 0.62;
}

.nmg-search-results__empty strong {
  color: var(--pm-text, #0f172a);
  font-size: 0.9rem;
}

.nmg-search-results__empty span {
  font-size: 0.76rem;
}

.nmg__sort-btn {
  display: flex;
  width: 100%;
  height: 32px;
  min-width: 0;
  align-items: center;
  gap: 5px;
  padding: 0 9px 0 10px;
  border-radius: 8px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  background: transparent;
  color: var(--pm-text, #0f172a);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.nmg__sort-btn > .v-icon:first-child { color: var(--pm-muted, #64748b); }
.nmg__sort-btn > .v-icon:last-child { margin-inline-start: auto; }
.nmg__sort-btn:hover:not(:disabled) {
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.05));
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
}
.nmg__sort-btn:disabled { opacity: 0.5; cursor: default; }
.nmg__sort-label {
  min-width: 0;
  overflow: hidden;
  color: var(--pm-muted, #64748b);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nmg__sort-list {
  width: min(272px, calc(100vw - 32px));
  padding: 5px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 76%, transparent);
  border-radius: 12px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
}
.nmg__sort-list :deep(.v-list-item) {
  min-height: 0;
  padding-block: 6px;
  padding-inline: 10px;
}
/* Kompakte Zwischenüberschriften in den Ansicht-Menüs. */
.nmg__action-menu :deep(.v-list-subheader) {
  min-height: 0;
  padding-block: 5px 3px;
  padding-inline: 10px;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.9;
}

@media (prefers-reduced-motion: reduce) {
  .nmg__sort-btn { transition: none; }
}

.nmg__state {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--pm-muted);
  font-size: 0.84rem;
}

.nmg__empty {
  display: flex;
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  align-items: center;
  justify-content: center;
}

/* Vorlagen-Facet: die Vorlagenmappe füllt den Scrollbereich selbst. */
.nmg__vorlagenmappe { flex: none; padding: 22px 26px 28px; }

.nmg__groups {
  padding: 22px 26px 28px;
}

.nmg__group + .nmg__group {
  margin-top: 22px;
}

.nmg__group-heading {
  margin: 0 0 11px;
  color: var(--pm-muted, #64748b);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.nmg__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(258px, 1fr));
  align-content: start;
  align-items: start;
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

/* ── Notiz-Karten (grafisch, wie Vorlagenmappe) ─────────────────────────── */
.nmg-card {
  --nmg-accent: var(--pm-accent, #006b75);
  position: relative;
  display: flex;
  box-sizing: border-box;
  height: 207px;
  flex-direction: column;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  overflow: hidden;
  cursor: pointer;
  /* Weicher, neutraler Ruheschatten wie die Leuchttisch-Karten. */
  box-shadow: 0 3px 10px rgba(27, 43, 48, 0.09);
  transition: box-shadow 130ms ease, border-color 130ms ease;
}
.nmg-card:hover {
  /* Dezente, neutrale Rahmen-Abdunklung wie beim Leuchttisch – kein Anheben,
     kein Akzentschimmer. */
  border-color: color-mix(in srgb, var(--pm-text, #1b2b30) 22%, var(--pm-divider, #d8dfe1));
  box-shadow: 0 4px 14px rgba(27, 43, 48, 0.12);
}
.nmg-card:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--pm-content-surface, #fff), 0 0 0 4px color-mix(in srgb, var(--nmg-accent) 55%, transparent);
}
.nmg-card.is-editing { cursor: default; }

.nmg-card__preview {
  position: relative;
  box-sizing: border-box;
  /* Vorschaubox umschließt ihren Inhalt (kein Dehnen) – so bleibt darunter keine
     getönte Leere. Der überschüssige Platz landet als ungetönter Kartenhintergrund
     zwischen Titel und Fußzeile; die Fußzeile wird per margin-top:auto an den
     Kachelboden geschoben, damit die Tags kartenübergreifend fluchten. */
  flex: none;
  padding: 13px 15px;
  overflow: hidden;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 3.5%, var(--pm-content-surface, #fff));
}
.nmg-card__snippet {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--pm-muted, #535e62);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.nmg-card__links {
  position: absolute;
  bottom: 9px;
  right: 12px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px 1px 6px;
  border-radius: 20px;
  font-size: 0.72rem;
  color: var(--pm-muted, #535e62);
  background: color-mix(in srgb, var(--pm-text, #0e181b) 6%, var(--pm-content-surface, #fff));
}

.nmg-card__actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 3px;
  padding: 3px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 80%, transparent);
  backdrop-filter: blur(3px);
  opacity: 0;
  transform: translateY(-2px);
  pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease;
}
.nmg-card:hover .nmg-card__actions,
.nmg-card:focus-within .nmg-card__actions { opacity: 1; transform: none; pointer-events: auto; }
.nmg-card__act {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  transition: color 120ms ease, background 120ms ease;
}
.nmg-card__act:hover { background: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent); color: var(--pm-text, #0e181b); }
.nmg-card__act--danger:hover { color: var(--pm-danger, #c0392b); background: color-mix(in srgb, var(--pm-danger, #c0392b) 12%, transparent); }

/* ── Favoriten-Stern im Hover-Aktionsmenü (Gold + Pop-Animation wie Dokumente) ── */
.nmg-card__fav-wrap {
  position: relative;
  display: inline-flex;
}
.nmg-card__act--fav.is-active { color: var(--pm-star, #f5b301); }
.nmg-card__act--fav.is-active:hover { color: var(--pm-star, #f5b301); background: color-mix(in srgb, var(--pm-star, #f5b301) 14%, transparent); }

.nmg-card__fav-wrap--pop {
  animation: nmg-fav-star-pop 420ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.nmg-card__fav-wrap--pop::after {
  content: '';
  position: absolute;
  inset: 0;
  margin: auto;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 2px solid var(--pm-star, #f5b301);
  pointer-events: none;
  animation: nmg-fav-star-ring 480ms ease-out forwards;
}
@keyframes nmg-fav-star-pop {
  0%   { transform: scale(1); }
  35%  { transform: scale(1.32); }
  60%  { transform: scale(0.94); }
  100% { transform: scale(1); }
}
@keyframes nmg-fav-star-ring {
  0%   { transform: scale(0.5); opacity: 0.55; }
  100% { transform: scale(1.8); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .nmg-card__fav-wrap--pop,
  .nmg-card__fav-wrap--pop::after { animation: none; }
}
:global(.pm-no-animations) .nmg-card__fav-wrap--pop,
:global(.pm-no-animations) .nmg-card__fav-wrap--pop::after { animation: none; }

.nmg-card__meta {
  display: flex;
  box-sizing: border-box;
  flex: none;
  /* Höhe wächst mit dem Titel (1 vs. 2 Zeilen); die Vorschau darüber gleicht das
     aus, die Kachel bleibt gleich hoch. Oben ausgerichtet, damit das Datum auf
     Höhe der ersten Titelzeile sitzt. */
  align-items: flex-start;
  gap: 9px;
  padding: 9px 13px 3px;
}
.nmg-card__title {
  min-width: 0;
  flex: 1 1 auto;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--pm-text, #0e181b);
  /* Bis zu zwei Zeilen (statt harter Kürzung) – gibt langen Titeln mehr Platz,
     ohne Datum oder Tags zu verdrängen. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  /* Direkt per Klick editierbar (wie die Tags) – Hover signalisiert das. */
  padding: 2px 6px;
  margin: -2px -6px;
  border-radius: 6px;
  cursor: text;
  text-decoration-line: underline;
  text-decoration-color: transparent;
  text-decoration-thickness: 1px;
  text-underline-offset: 4px;
  transition: text-decoration-color 200ms ease;
}
.nmg-card__title:hover {
  text-decoration-color: color-mix(in srgb, currentColor 35%, transparent);
}
.nmg-card__title:focus-visible {
  outline: 2px solid var(--nmg-accent);
  outline-offset: 2px;
  text-decoration-color: color-mix(in srgb, currentColor 35%, transparent);
}
@media (prefers-reduced-motion: reduce) {
  .nmg-card__title { transition: none; }
}
:global(.pm-no-animations) .nmg-card__title { transition: none; }
.nmg-card__title.is-untitled { color: var(--pm-muted, #8a969b); font-style: italic; font-weight: 500; }

/* Notizbuch-Zugehörigkeit: klickbarer Chip (filtert das Raster auf das Buch). */
/* Notizbuch-Zugehörigkeit: farbiger Rand-Akzent links (statt Chip in der
   Titelzeile). Folgt der Kachelrundung dank overflow:hidden am Card-Element. */
.nmg-card.is-in-collection::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--nmg-collection-accent, var(--pm-accent, #006b75));
  z-index: 1;
}
.nmg-card__title-input {
  min-width: 0;
  flex: 1;
  border: 1px solid var(--pm-accent, #006b75);
  border-radius: 7px;
  padding: 5px 8px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0e181b);
  outline: none;
}

.nmg-card__foot {
  display: flex;
  box-sizing: border-box;
  height: 49px;
  flex: none;
  /* An den Kachelboden schieben: der überschüssige Platz sammelt sich darüber,
     die Fußzeile (Tags) fluchtet bei allen Kacheln auf gleicher Höhe. */
  margin-top: auto;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 4px 13px 11px;
}

/* Ruhiger Tag-Zähler auf der Karte; Bearbeiten öffnet ein Popover. */
.nmg-card__tag-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  height: 26px;
  padding: 0 10px 0 8px;
  border: 1px solid var(--pm-detail-chip-border, color-mix(in srgb, var(--pm-text, #0f172a) 14%, transparent));
  border-radius: 13px;
  background: var(--pm-chip-bg, rgba(var(--v-theme-on-surface), 0.06));
  color: rgba(var(--v-theme-on-surface), 0.82);
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}
.nmg-card__tag-btn:hover {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 34%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 8%, var(--pm-chip-bg, #e7eef0));
  color: var(--pm-accent-strong, #00555f);
}
/* Ohne Tags: dezente, gestrichelte „Tag hinzufügen"-Andeutung. */
.nmg-card__tag-btn.is-empty {
  border-style: dashed;
  background: transparent;
  color: var(--pm-muted, #64748b);
  font-weight: 500;
}
.nmg-card__tag-count { line-height: 1; }
.nmg-card__tag-pop {
  min-width: 260px;
  max-width: 320px;
  padding: 10px 12px;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.16);
}

.nmg-card__date {
  flex: none;
  font-size: 0.72rem;
  color: var(--pm-muted, #8a969b);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
  .nmg-card, .nmg-card__actions { transition: none; }
  .nmg-card:hover { transform: none; }
}

/* ── Leerzustand: Geisterkarten (wie Vorlagenmappe) ─────────────────────── */
.nmg__ghost-empty {
  flex: none;
  padding: 24px 26px 28px;
}
.nmg-ghost {
  display: flex;
  flex-direction: column;
  border: 1px dashed color-mix(in srgb, var(--pm-text, #0e181b) 12%, var(--pm-divider, #d8dfe1));
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  overflow: hidden;
  opacity: 0.7;
}
.nmg-ghost__preview {
  height: 112px;
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 9px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 3.5%, var(--pm-content-surface, #fff));
}
.nmg-ghost__line { height: 7px; border-radius: 4px; background: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent); }
.nmg-ghost__line:nth-child(2) { opacity: 0.72; }
.nmg-ghost__line:nth-child(3) { opacity: 0.85; }
.nmg-ghost__meta {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 13px;
  border-top: 1px dashed color-mix(in srgb, var(--pm-text, #0e181b) 10%, var(--pm-divider, #d8dfe1));
}
.nmg-ghost__chip { width: 28px; height: 28px; flex: none; border-radius: 8px; background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent); }
.nmg-ghost__name { height: 9px; width: 58%; border-radius: 4px; background: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent); }

@media (max-width: 760px) {
  .nmg-search-results {
    padding: 18px 16px 26px;
  }

  .nmg-search-note {
    grid-template-columns: 32px minmax(0, 1fr) 16px;
  }

  .nmg-search-note__meta {
    display: none;
  }

  .nmg__tag-sidebar {
    position: absolute;
    z-index: 8;
    top: 0;
    right: 0;
    bottom: 0;
    width: clamp(270px, 88vw, 320px);
    transform: translateX(calc(100% + 36px));
    transition: transform 220ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1));
  }

  .nmg__tag-sidebar.is-open {
    transform: translateX(0);
  }

  .nmg__tag-sidebar-head {
    display: flex;
  }

  .nmg__tag-sidebar-close {
    display: inline-flex;
  }

  .nmg__tag-sidebar-toggle {
    position: absolute;
    z-index: 7;
    top: 12px;
    right: 12px;
    display: inline-flex;
    width: 38px;
    height: 38px;
    border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 80%, transparent);
    border-radius: 11px;
    background: var(--pm-app-surface-raised, #fff);
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    color: var(--pm-accent, #006b75);
  }
}

@media (prefers-reduced-motion: reduce) {
  .nmg__tag-sidebar,
  .nmg__tag-sidebar-action,
  .nmg__tag-sidebar-toggle,
  .nmg__tag-cloud-chip,
  .nmg-search-notebook,
  .nmg-search-note,
  .nmg-content-enter-active,
  .nmg-content-leave-active {
    transition-duration: 0ms;
  }
}

:global(.pm-no-animations) .nmg-card,
:global(.pm-no-animations) .nmg__tag-sidebar,
:global(.pm-no-animations) .nmg__tag-sidebar-action,
:global(.pm-no-animations) .nmg__tag-sidebar-toggle,
:global(.pm-no-animations) .nmg__tag-cloud-chip,
:global(.pm-no-animations) .nmg-search-notebook,
:global(.pm-no-animations) .nmg-search-note,
:global(.pm-no-animations) .nmg-content-enter-active,
:global(.pm-no-animations) .nmg-content-leave-active {
  transition-duration: 0ms;
}
</style>
