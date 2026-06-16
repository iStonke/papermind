<template>
  <aside class="panel panel-left">
    <div v-if="$slots.head" class="sidebar-head">
      <slot name="head" />
    </div>

    <div class="sidebar-scroll">
    <!-- Bibliothek -->
    <v-list nav density="compact" class="views-list">
      <div class="sidebar-section-header sidebar-section-header--static">
        <div class="sidebar-section-label">Bibliothek</div>
      </div>

      <div class="sidebar-section-drawer">
        <div class="sidebar-section-content">
          <SidebarItem
            item-class="sidebar-item--primary sidebar-item--plain-label"
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
            v-if="settingsStore.settings.ui.sidebar_show_recent !== false"
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
            v-if="settingsStore.settings.ui.sidebar_show_untagged !== false"
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
            :action-mode="trashSidebarCount > 0 ? 'hover-active' : 'never'"
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

          <SidebarItem
            v-if="settingsStore.settings.ui.sidebar_show_chat !== false"
            item-class="sidebar-item--secondary sidebar-item--chat"
            :active="chatActive"
            @click="emit('open-chat')"
          >
            <template #icon>
              <v-icon size="18">mdi-robot-outline</v-icon>
            </template>
            KI-Chat
          </SidebarItem>
        </div>
      </div>
    </v-list>

    <v-divider class="sidebar-section-divider sidebar-section-divider--after-library" />

    <template v-for="(section, idx) in orderedSidebarSections" :key="section.key">
      <v-divider v-if="idx > 0" class="sidebar-section-divider" />

    <!-- Ordner -->
    <v-list v-if="section.key === 'ordner' && !collapsed" nav density="compact" class="views-list">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': ordnerCollapsed }"
        @click="toggleSection('ordner')"
      >
        <div class="sidebar-section-label">Ordner</div>
        <span v-if="ordnerCollapsed && sortedFolderItems.length" class="sidebar-section-count">{{ sortedFolderItems.length }}</span>
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
        </div>
      </div>
    </v-list>

    <!-- Tags -->
    <v-list v-else-if="section.key === 'tags'" nav density="compact" class="views-list">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': tagsCollapsed }"
        @click="toggleSection('tags')"
      >
        <div class="sidebar-section-label">Tags</div>
        <span v-if="tagsCollapsed && totalTagsSidebarCount" class="sidebar-section-count">{{ totalTagsSidebarCount }}</span>
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
            item-class="sidebar-item--plain-label"
            :active="isTagView"
            :count="totalTagsSidebarCount"
            @click="emit('open-tags-view')"
          >
            <template #icon>
              <v-icon size="18">mdi-tag-multiple-outline</v-icon>
            </template>
            Alle Tags
          </SidebarItem>

          <template v-if="!collapsed">
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
          </template>
        </div>
      </div>
    </v-list>

    <!-- Kategorien -->
    <v-list v-else-if="section.key === 'kategorien'" nav density="compact" class="views-list">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': kategorienCollapsed }"
        @click="toggleSection('kategorien')"
      >
        <div class="sidebar-section-label">Dokumenttypen</div>
        <span v-if="kategorienCollapsed && totalCategoriesSidebarCount" class="sidebar-section-count">{{ totalCategoriesSidebarCount }}</span>
        <button
          class="sidebar-section-toggle"
          :aria-label="kategorienCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
          tabindex="-1"
          @click.stop="toggleSection('kategorien')"
        >
          <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
        </button>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': kategorienCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            item-class="sidebar-item--plain-label"
            :active="isCategoryView"
            :count="totalCategoriesSidebarCount"
            @click="emit('open-categories-view')"
          >
            <template #icon>
              <v-icon size="18">mdi-file-document-multiple-outline</v-icon>
            </template>
            Alle Dokumenttypen
          </SidebarItem>

          <template v-if="!collapsed">
            <SidebarItem
              v-for="category in topCategoryQuicklinks"
              :key="category.id"
              item-class="sidebar-item--tag"
              :active="!isCategoryView && activeCategoryName === category.name"
              :count="Number(category.usage_count || 0)"
              @click="emit('apply-category-filter', category.name)"
            >
              <template #icon>
                <v-icon size="18">mdi-file-document-outline</v-icon>
              </template>
              <span class="sidebar-tag-pill">{{ category.name }}</span>
            </SidebarItem>
          </template>
        </div>
      </div>
    </v-list>
    </template>
    </div>

    <div v-if="$slots.foot" class="sidebar-foot">
      <slot name="foot" />
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useSidebarStore } from '../stores/sidebar.js';
import { useTagStore } from '../stores/tags.js';
import { useCategoryStore } from '../stores/categories.js';
import { useSettingsStore } from '../stores/settings.js';
import { normalizeSidebarSections } from '../utils/settingsApi.js';
import SidebarItem from './SidebarItem.vue';

// ── Props & Emits ──────────────────────────────────────────────────────────
const props = defineProps({
  activeView:        { type: String,  default: 'all' },
  activeSavedSearchId: { type: String,  default: null },
  activeTagId:       { type: String,  default: null },
  isTagView:         { type: Boolean, default: false },
  activeCategoryName: { type: String,  default: null },
  isCategoryView:    { type: Boolean, default: false },
  collapsed:         { type: Boolean, default: false },
  chatActive:        { type: Boolean, default: false },
});

const emit = defineEmits([
  'select-view',
  'open-chat',
  'open-saved-search',
  'create-folder',
  'edit-folder',
  'delete-folder',
  'empty-trash',
  'open-tags-view',
  'apply-tag-filter',
  'open-categories-view',
  'apply-category-filter',
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const sidebarStore  = useSidebarStore();
const tagStore      = useTagStore();
const categoryStore = useCategoryStore();
const settingsStore = useSettingsStore();

const { sidebarCounts, savedSearches } = storeToRefs(sidebarStore);
const { tags }                         = storeToRefs(tagStore);
const { categories }                   = storeToRefs(categoryStore);

onMounted(() => {
  void categoryStore.ensureLoaded();
});

// ── Konfigurierbare Sektionen (Reihenfolge + Sichtbarkeit) ──────────────────
const orderedSidebarSections = computed(() =>
  normalizeSidebarSections(settingsStore.settings.ui.sidebar_sections)
    .filter((section) => section.visible !== false)
);

function clampSidebarMax(value, fallback = 5) {
  const parsed = Math.round(Number(value));
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(50, Math.max(0, parsed));
}

const maxSidebarTags = computed(() => clampSidebarMax(settingsStore.settings.ui.sidebar_max_tags));
const maxSidebarCategories = computed(() => clampSidebarMax(settingsStore.settings.ui.sidebar_max_categories));

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
const kategorienCollapsed = ref(loadCollapsed('kategorien'));

const sectionStates = {
  bibliothek: bibliothekCollapsed,
  ordner:     ordnerCollapsed,
  tags:       tagsCollapsed,
  kategorien: kategorienCollapsed,
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
    // Bei aktivem Tag-Filter NICHT „Alle Dokumente" markieren – der Tag bleibt aktiv.
    return props.activeView === 'all' && !props.activeTagId && !props.activeCategoryName;
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
    .slice(0, maxSidebarTags.value)
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

// ── Kategorien (Dokumenttypen) ──────────────────────────────────────────────
const activeCategories = computed(() =>
  categories.value.filter((category) => category?.is_active !== false)
);

const topCategoryQuicklinks = computed(() =>
  [...activeCategories.value]
    .filter((category) => Number(category?.usage_count || 0) > 0)
    .sort((l, r) => {
      const lc = Number(l?.usage_count || 0);
      const rc = Number(r?.usage_count || 0);
      if (lc !== rc) return rc - lc;
      return tagNameCollator.compare(normalizeTagInput(l?.name || ''), normalizeTagInput(r?.name || ''));
    })
    .slice(0, maxSidebarCategories.value)
);

const totalCategoriesSidebarCount = computed(() => {
  const used = activeCategories.value.filter((category) => Number(category?.usage_count || 0) > 0).length;
  if (used > 0 || activeCategories.value.length === 0) return used;
  return activeCategories.value.length;
});
</script>

<style scoped>
.sidebar-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 12px 10px;
}

/* ── Section Header ───────────────────────────────────────────────────── */
.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 24px;
  padding: 4px 8px 6px 10px;
  cursor: pointer;
  border-radius: 6px;
  user-select: none;
  gap: 7px;
  transition: background 0.12s ease;
}

.sidebar-section-header:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}

/* Bibliothek: statischer Kopf, nicht einklappbar (Kern-Navigation). */
.sidebar-section-header--static {
  cursor: default;
}

.sidebar-section-header--static:hover {
  background: transparent;
}

/* ── Zähler-Chip (nur im eingeklappten Zustand) ───────────────────────── */
.sidebar-section-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1;
  color: rgba(var(--v-theme-on-surface), 0.6);
  background: rgba(var(--v-theme-on-surface), 0.07);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 999px;
  white-space: nowrap;
  user-select: none;
  transition: color 0.12s ease, background 0.12s ease, border-color 0.12s ease;
}

.sidebar-section-header:hover .sidebar-section-count {
  color: rgba(var(--v-theme-on-surface), 0.78);
  background: rgba(var(--v-theme-on-surface), 0.1);
  border-color: rgba(var(--v-theme-on-surface), 0.16);
}

/* ── Toggle button ────────────────────────────────────────────────────── */
.sidebar-section-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: auto;
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
.sidebar-section-header:focus-within .sidebar-section-toggle,
.sidebar-section-header--collapsed .sidebar-section-toggle {
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
