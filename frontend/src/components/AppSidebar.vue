<template>
  <aside class="panel panel-left">
    <!-- Bibliothek -->
    <v-list nav density="compact" class="views-list">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': bibliothekCollapsed }"
        @click="toggleSection('bibliothek')"
      >
        <div class="sidebar-section-label">Bibliothek</div>
        <button
          class="sidebar-section-toggle"
          :aria-label="bibliothekCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
          tabindex="-1"
          @click.stop="toggleSection('bibliothek')"
        >
          <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
        </button>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': bibliothekCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            item-class="sidebar-item--primary"
            :active="isViewActive('all')"
            :count="allDocumentsSidebarCount"
            @click="emit('select-view', 'all')"
          >
            <template #icon>
              <v-icon size="18">mdi-book-open-page-variant-outline</v-icon>
            </template>
            Alle Dokumente
          </SidebarItem>

          <SidebarItem
            item-class="sidebar-item--secondary sidebar-item--imports"
            :active="isViewActive('imports')"
            :count="importsSidebarCount"
            @click="emit('select-view', 'imports')"
          >
            <template #icon>
              <v-icon size="18">mdi-tray-arrow-down</v-icon>
            </template>
            Zuletzt hinzugefügt
          </SidebarItem>

          <SidebarItem
            item-class="sidebar-item--secondary"
            :active="isViewActive('untagged')"
            :count="untaggedSidebarCount"
            @click="emit('select-view', 'untagged')"
          >
            <template #icon>
              <v-icon size="18">mdi-tag-off-outline</v-icon>
            </template>
            Ohne Tags
          </SidebarItem>

          <SidebarItem
            item-class="sidebar-item--secondary sidebar-item--favorites"
            :active="isViewActive('favorites')"
            :count="favoritesSidebarCount"
            @click="emit('select-view', 'favorites')"
          >
            <template #icon>
              <v-icon size="18">mdi-star-outline</v-icon>
            </template>
            Favoriten
          </SidebarItem>

          <SidebarItem
            item-class="sidebar-item--secondary sidebar-item--trash"
            :active="isViewActive('trash')"
            :count="trashSidebarCount"
            action-mode="hover-active"
            @click="emit('select-view', 'trash')"
          >
            <template #icon>
              <v-icon size="18">mdi-trash-can-outline</v-icon>
            </template>
            Papierkorb
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
                    aria-label="Papierkorb-Menü"
                    @click.stop
                  />
                </template>
                <v-list density="compact">
                  <v-list-item class="menu-item--danger" @click.stop="emit('empty-trash')">
                    <template #prepend>
                      <v-icon size="16">mdi-delete-forever-outline</v-icon>
                    </template>
                    <v-list-item-title>Alle endgültig löschen…</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-menu>
            </template>
          </SidebarItem>
        </div>
      </div>
    </v-list>

    <v-divider class="sidebar-section-divider" />

    <!-- Ordner -->
    <v-list nav density="compact" class="views-list">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': ordnerCollapsed }"
        @click="toggleSection('ordner')"
      >
        <div class="sidebar-section-label">Ordner</div>
        <button
          class="sidebar-section-toggle"
          :aria-label="ordnerCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
          tabindex="-1"
          @click.stop="toggleSection('ordner')"
        >
          <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
        </button>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': ordnerCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            item-class="sidebar-item--secondary sidebar-item--folder-create"
            @click="emit('create-folder')"
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
            :count="sidebarStore.savedSearchCount(savedSearch.id)"
            action-mode="hover-active"
            @click="emit('open-saved-search', savedSearch.id)"
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
                  <v-list-item @click.stop="emit('edit-folder', savedSearch)">
                    <template #prepend>
                      <v-icon size="16">mdi-pencil-outline</v-icon>
                    </template>
                    <v-list-item-title>Bearbeiten</v-list-item-title>
                  </v-list-item>
                  <v-list-item class="menu-item--danger" @click.stop="emit('delete-folder', savedSearch)">
                    <template #prepend>
                      <v-icon size="16">mdi-trash-can-outline</v-icon>
                    </template>
                    <v-list-item-title>Löschen…</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-menu>
            </template>
          </SidebarItem>

          <v-list-item v-if="!sidebarStore.isLoadingSavedSearches && sortedFolderItems.length === 0">
            <v-list-item-title class="text-caption">Noch keine Ordner</v-list-item-title>
          </v-list-item>
        </div>
      </div>
    </v-list>

    <v-divider class="sidebar-section-divider" />

    <!-- Tags -->
    <v-list nav density="compact" class="views-list">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': tagsCollapsed }"
        @click="toggleSection('tags')"
      >
        <div class="sidebar-section-label">Tags</div>
        <button
          class="sidebar-section-toggle"
          :aria-label="tagsCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
          tabindex="-1"
          @click.stop="toggleSection('tags')"
        >
          <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
        </button>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': tagsCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            :active="isTagView"
            :count="totalTagsSidebarCount"
            @click="emit('open-tags-view')"
          >
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
            :count="sidebarStore.tagCount(tag.id, tag.usage_count ?? 0)"
            @click="emit('apply-tag-filter', tag.id)"
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
      </div>
    </v-list>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useSidebarStore } from '../stores/sidebar.js';
import { useTagStore } from '../stores/tags.js';
import SidebarItem from './SidebarItem.vue';

// ── Props & Emits ──────────────────────────────────────────────────────────
const props = defineProps({
  activeView:        { type: String,  default: 'all' },
  activeSavedSearchId: { type: String,  default: null },
  activeTagId:       { type: String,  default: null },
  isTagView:         { type: Boolean, default: false },
});

const emit = defineEmits([
  'select-view',
  'open-saved-search',
  'create-folder',
  'edit-folder',
  'delete-folder',
  'empty-trash',
  'open-tags-view',
  'apply-tag-filter',
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const sidebarStore = useSidebarStore();
const tagStore     = useTagStore();

const { sidebarCounts, savedSearches } = storeToRefs(sidebarStore);
const { tags }                         = storeToRefs(tagStore);

// ── Collapsible sections ───────────────────────────────────────────────────
function loadCollapsed(key) {
  try { return localStorage.getItem(`pm-sidebar-collapsed-${key}`) === 'true'; } catch { return false; }
}

function saveCollapsed(key, value) {
  try { localStorage.setItem(`pm-sidebar-collapsed-${key}`, String(value)); } catch { /* ignore */ }
}

const bibliothekCollapsed = ref(loadCollapsed('bibliothek'));
const ordnerCollapsed     = ref(loadCollapsed('ordner'));
const tagsCollapsed       = ref(loadCollapsed('tags'));

const sectionStates = {
  bibliothek: bibliothekCollapsed,
  ordner:     ordnerCollapsed,
  tags:       tagsCollapsed,
};

function toggleSection(key) {
  const state = sectionStates[key];
  if (!state) return;
  state.value = !state.value;
  saveCollapsed(key, state.value);
}

// ── Helpers ────────────────────────────────────────────────────────────────
const tagNameCollator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });

function normalizeTagInput(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function resolveFolderKind(folder) {
  const explicitKind = String(
    folder?.folder_type || folder?.kind || folder?.type || folder?.category || ''
  ).trim().toLocaleLowerCase('de-DE');

  if (explicitKind) {
    if (['manual', 'folder', 'static'].includes(explicitKind)) return 'manual';
    if (['smart', 'smart_folder', 'smart-folder', 'intelligent', 'query'].includes(explicitKind)) return 'smart';
  }
  if (folder?.is_manual === true || folder?.isManual === true) return 'manual';
  if (folder?.is_smart  === true || folder?.isSmart  === true) return 'smart';
  if (folder?.query_json && typeof folder.query_json === 'object') return 'smart';
  return 'smart';
}

function isSmartFolderItem(folder) {
  return resolveFolderKind(folder) === 'smart';
}

function folderSidebarIcon(folder, isActive = false) {
  if (isSmartFolderItem(folder)) return 'mdi-folder-search-outline';
  return isActive ? 'mdi-folder' : 'mdi-folder-outline';
}

// ── Navigation helpers ─────────────────────────────────────────────────────
function isViewActive(viewKey) {
  if (props.isTagView || props.activeSavedSearchId) return false;
  if (viewKey === 'all') {
    return props.activeView === 'all' && !props.activeTagId;
  }
  if (viewKey === 'imports')   return props.activeView === 'imports';
  if (viewKey === 'untagged')  return props.activeView === 'untagged';
  if (viewKey === 'favorites') return props.activeView === 'favorites';
  if (viewKey === 'trash')     return props.activeView === 'trash';
  return props.activeView === viewKey;
}

// ── Computed counts ────────────────────────────────────────────────────────
const allDocumentsSidebarCount = computed(() => Number(sidebarCounts.value.all_documents || 0));
const importsSidebarCount = computed(
  () => Number(sidebarCounts.value.imports?.recent_total || sidebarCounts.value.imports?.imported || 0)
);
const untaggedSidebarCount  = computed(() => Number(sidebarCounts.value.untagged       || 0));
const favoritesSidebarCount = computed(() => Number(sidebarCounts.value.favorites_count || 0));
const trashSidebarCount     = computed(() => Number(sidebarCounts.value.trash_count     || 0));

const sortedTagsByName = computed(() =>
  [...tags.value].sort((l, r) =>
    tagNameCollator.compare(normalizeTagInput(l?.name || ''), normalizeTagInput(r?.name || ''))
  )
);

const sidebarTagsByName = computed(() =>
  sortedTagsByName.value.filter((tag) => sidebarStore.tagCount(tag.id, tag.usage_count ?? 0) > 0)
);

const topTagQuicklinks = computed(() =>
  [...sidebarTagsByName.value]
    .sort((l, r) => {
      const lc = sidebarStore.tagCount(l.id, l.usage_count ?? 0);
      const rc = sidebarStore.tagCount(r.id, r.usage_count ?? 0);
      if (lc !== rc) return rc - lc;
      return tagNameCollator.compare(normalizeTagInput(l?.name || ''), normalizeTagInput(r?.name || ''));
    })
    .slice(0, 5)
);

const totalTagsSidebarCount = computed(() => {
  const tagsWithAssignments = Object.values(sidebarCounts.value.tags || {})
    .filter((v) => Number(v || 0) > 0).length;
  if (tagsWithAssignments > 0 || tags.value.length === 0) return tagsWithAssignments;
  return sidebarTagsByName.value.length;
});

const sortedFolderItems = computed(() =>
  [...savedSearches.value].sort((l, r) => {
    const lw = isSmartFolderItem(l) ? 1 : 0;
    const rw = isSmartFolderItem(r) ? 1 : 0;
    if (lw !== rw) return lw - rw;
    return tagNameCollator.compare(normalizeTagInput(l?.name || ''), normalizeTagInput(r?.name || ''));
  })
);
</script>

<style scoped>
/* ── Section Header ───────────────────────────────────────────────────── */
.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
  padding: 4px 8px 6px 10px;
  cursor: pointer;
  border-radius: 6px;
  user-select: none;
  gap: 4px;
  transition: background 0.12s ease;
}

.sidebar-section-header:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}

/* ── Toggle button ────────────────────────────────────────────────────── */
.sidebar-section-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.5);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, background 0.12s ease, color 0.12s ease;
}

.sidebar-section-header:hover .sidebar-section-toggle,
.sidebar-section-header:focus-within .sidebar-section-toggle {
  opacity: 1;
  pointer-events: auto;
}

.sidebar-section-toggle:hover {
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.8);
}

.sidebar-section-toggle:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.7);
  outline-offset: 1px;
  opacity: 1;
  pointer-events: auto;
}

/* ── Chevron rotation ─────────────────────────────────────────────────── */
.sidebar-section-toggle-icon {
  display: block;
  transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-section-header--collapsed .sidebar-section-toggle-icon {
  transform: rotate(-90deg);
}

/* ── Drawer animation (grid trick) ────────────────────────────────────── */
.sidebar-section-drawer {
  display: grid;
  grid-template-rows: 1fr;
  transition: grid-template-rows 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-section-drawer--collapsed {
  grid-template-rows: 0fr;
}

.sidebar-section-content {
  min-height: 0;
  overflow: hidden;
}

/* Eingeklappte Items aus Tab-Reihenfolge entfernen */
.sidebar-section-drawer--collapsed .sidebar-section-content {
  visibility: hidden;
}

/* Touch-Geräte: Toggle immer sichtbar */
@media (hover: none) {
  .sidebar-section-toggle {
    opacity: 1;
    pointer-events: auto;
  }
}
</style>
