<template>
  <aside ref="rootRef" class="panel panel-left">
    <div v-if="$slots.head" class="sidebar-head">
      <slot name="head" />
    </div>

    <div class="sidebar-scroll" @mouseleave="scheduleFlyoutClose">
    <!-- Bibliothek -->
    <v-list nav density="compact" class="views-list" @mouseenter="onRailSectionEnter('bibliothek', $event)">
      <div class="sidebar-section-header sidebar-section-header--static">
        <div class="sidebar-section-label">Bibliothek</div>
      </div>

      <div class="sidebar-section-drawer">
        <div class="sidebar-section-content">
          <SidebarItem
            item-class="sidebar-item--primary sidebar-item--plain-label"
            :active="isViewActive('dashboard')"
            @click="emit('select-view', 'dashboard')"
          >
            <template #icon>
              <v-icon size="18">mdi-view-dashboard-outline</v-icon>
            </template>
            Übersicht
          </SidebarItem>

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
            v-if="settingsStore.settings.ui.sidebar_show_no_text !== false"
            item-class="sidebar-item--secondary"
            :active="isViewActive('no_text')"
            :count="noTextSidebarCount"
            @click="emit('select-view', 'no_text')"
          >
            <template #icon>
              <v-icon size="18">mdi-text-box-remove-outline</v-icon>
            </template>
            Nicht durchsuchbar
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
    <v-list v-if="section.key === 'ordner'" nav density="compact" class="views-list" @mouseenter="onRailSectionEnter('ordner', $event)">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': ordnerCollapsed }"
        @click="toggleSection('ordner')"
      >
        <div class="sidebar-section-label">Ordner</div>
        <div class="sidebar-section-header-actions">
          <button
            type="button"
            class="sidebar-section-icon-action"
            aria-label="Ordner erstellen"
            @click.stop="emit('create-folder')"
          >
            <v-icon size="15">mdi-folder-plus-outline</v-icon>
          </button>
          <button
            type="button"
            class="sidebar-section-toggle"
            :aria-label="ordnerCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
            tabindex="-1"
            @click.stop="toggleSection('ordner')"
          >
            <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
          </button>
        </div>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': ordnerCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            v-if="collapsed"
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
    <v-list v-else-if="section.key === 'tags'" nav density="compact" class="views-list" @mouseenter="onRailSectionEnter('tags', $event)">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': tagsCollapsed }"
        @click="toggleSection('tags')"
      >
        <div class="sidebar-section-label">Tags</div>
        <div class="sidebar-section-header-actions">
          <button
            type="button"
            class="sidebar-section-icon-action"
            aria-label="Alle Tags anzeigen"
            @click.stop="emit('open-tags-view')"
          >
            <v-icon size="15">mdi-view-grid-outline</v-icon>
          </button>
          <button
            type="button"
            class="sidebar-section-toggle"
            :aria-label="tagsCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
            tabindex="-1"
            @click.stop="toggleSection('tags')"
          >
            <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
          </button>
        </div>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': tagsCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            v-if="collapsed"
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

          <div v-if="!collapsed && topTagQuicklinks.length" class="sidebar-chips">
            <button
              v-for="tag in topTagQuicklinks"
              :key="tag.id"
              type="button"
              class="sidebar-chip"
              :class="{ 'sidebar-chip--active': !isTagView && activeTagId === tag.id }"
              @click="emit('apply-tag-filter', tag.id)"
            >
              <span class="sidebar-chip__label">{{ tag.name }}</span>
              <span class="sidebar-chip__count">{{ sidebarStore.tagCount(tag.id, tag.usage_count ?? 0) }}</span>
            </button>
          </div>
        </div>
      </div>
    </v-list>

    <!-- Kategorien -->
    <v-list v-else-if="section.key === 'kategorien'" nav density="compact" class="views-list" @mouseenter="onRailSectionEnter('kategorien', $event)">
      <div
        class="sidebar-section-header"
        :class="{ 'sidebar-section-header--collapsed': kategorienCollapsed }"
        @click="toggleSection('kategorien')"
      >
        <div class="sidebar-section-label">Dokumenttypen</div>
        <div class="sidebar-section-header-actions">
          <button
            type="button"
            class="sidebar-section-icon-action"
            aria-label="Alle Dokumenttypen anzeigen"
            @click.stop="emit('open-categories-view')"
          >
            <v-icon size="15">mdi-view-grid-outline</v-icon>
          </button>
          <button
            type="button"
            class="sidebar-section-toggle"
            :aria-label="kategorienCollapsed ? 'Bereich einblenden' : 'Bereich ausblenden'"
            tabindex="-1"
            @click.stop="toggleSection('kategorien')"
          >
            <v-icon size="13" class="sidebar-section-toggle-icon">mdi-chevron-down</v-icon>
          </button>
        </div>
      </div>

      <div class="sidebar-section-drawer" :class="{ 'sidebar-section-drawer--collapsed': kategorienCollapsed }">
        <div class="sidebar-section-content">
          <SidebarItem
            v-if="collapsed"
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

          <div v-if="!collapsed" class="sidebar-chips">
            <button
              v-for="category in topCategoryQuicklinks"
              :key="category.id"
              type="button"
              class="sidebar-chip"
              :class="{ 'sidebar-chip--active': !isCategoryView && activeCategoryName === category.name }"
              @click="emit('apply-category-filter', category.name)"
            >
              <span class="sidebar-chip__label">{{ category.name }}</span>
              <span class="sidebar-chip__count">{{ Number(category.usage_count || 0) }}</span>
            </button>
          </div>
        </div>
      </div>
    </v-list>
    </template>
    </div>

    <!-- Rail-Flyout (Vorlage 6b): Sektion öffnet sich beim Hover -->
    <div
      v-if="collapsed && railFlyoutSection"
      class="sidebar-rail-flyout"
      :style="{ top: railFlyoutTop + 'px' }"
      @mouseenter="keepFlyoutOpen"
      @mouseleave="scheduleFlyoutClose"
    >
      <div class="sidebar-rail-flyout__arrow"></div>
      <div class="sidebar-rail-flyout__title">{{ flyoutTitle }}</div>
      <button
        v-for="row in flyoutRows"
        :key="row.id"
        type="button"
        class="sidebar-rail-flyout__row"
        :class="{ 'sidebar-rail-flyout__row--active': row.active }"
        @click="runFlyout(row)"
      >
        <v-icon size="17" class="sidebar-rail-flyout__icon">{{ row.icon }}</v-icon>
        <span class="sidebar-rail-flyout__label">{{ row.label }}</span>
        <span
          v-if="row.count !== null && row.count !== undefined"
          class="sidebar-rail-flyout__count"
        >{{ row.count }}</span>
      </button>
      <div v-if="flyoutChips.length" class="sidebar-chips sidebar-chips--flyout">
        <button
          v-for="chip in flyoutChips"
          :key="chip.id"
          type="button"
          class="sidebar-chip"
          :class="{ 'sidebar-chip--active': chip.active }"
          @click="runFlyout(chip)"
        >
          <span class="sidebar-chip__label">{{ chip.name }}</span>
          <span class="sidebar-chip__count">{{ chip.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="$slots.foot" class="sidebar-foot">
      <slot name="foot" />
    </div>
  </aside>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
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
  if (viewKey === 'no_text')   return props.activeView === 'no_text';
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
const noTextSidebarCount    = computed(() => Number(sidebarCounts.value.no_text_count   || 0));
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

// ── Rail-Flyout (Vorlage 6b) ────────────────────────────────────────────────
const rootRef = ref(null);
const railFlyoutSection = ref(null);
const railFlyoutTop = ref(0);
let flyoutCloseTimer = null;

const flyoutTitle = computed(() => ({
  bibliothek: 'Bibliothek',
  ordner: 'Ordner',
  tags: 'Tags',
  kategorien: 'Dokumenttypen',
}[railFlyoutSection.value] || ''));

const flyoutRows = computed(() => {
  const ui = settingsStore.settings.ui;
  switch (railFlyoutSection.value) {
    case 'bibliothek': {
      const rows = [{
        id: 'dashboard', icon: 'mdi-view-dashboard-outline', label: 'Übersicht',
        count: null, active: isViewActive('dashboard'),
        run: () => emit('select-view', 'dashboard'),
      }, {
        id: 'all', icon: 'mdi-book-open-page-variant-outline', label: 'Alle Dokumente',
        count: allDocumentsSidebarCount.value, active: isViewActive('all'),
        run: () => emit('select-view', 'all'),
      }];
      if (ui.sidebar_show_recent !== false) rows.push({
        id: 'imports', icon: 'mdi-tray-arrow-down', label: 'Zuletzt hinzugefügt',
        count: importsSidebarCount.value, active: isViewActive('imports'),
        run: () => emit('select-view', 'imports'),
      });
      if (ui.sidebar_show_untagged !== false) rows.push({
        id: 'untagged', icon: 'mdi-tag-off-outline', label: 'Ohne Tags',
        count: untaggedSidebarCount.value, active: isViewActive('untagged'),
        run: () => emit('select-view', 'untagged'),
      });
      rows.push({
        id: 'favorites', icon: 'mdi-star-outline', label: 'Favoriten',
        count: favoritesSidebarCount.value, active: isViewActive('favorites'),
        run: () => emit('select-view', 'favorites'),
      });
      if (ui.sidebar_show_no_text !== false) rows.push({
        id: 'no_text', icon: 'mdi-text-box-remove-outline', label: 'Nicht durchsuchbar',
        count: noTextSidebarCount.value, active: isViewActive('no_text'),
        run: () => emit('select-view', 'no_text'),
      });
      rows.push({
        id: 'trash', icon: 'mdi-trash-can-outline', label: 'Papierkorb',
        count: trashSidebarCount.value, active: isViewActive('trash'),
        run: () => emit('select-view', 'trash'),
      });
      if (ui.sidebar_show_chat !== false) rows.push({
        id: 'chat', icon: 'mdi-robot-outline', label: 'KI-Chat',
        count: null, active: props.chatActive, run: () => emit('open-chat'),
      });
      return rows;
    }
    case 'ordner': {
      const rows = [{
        id: 'create', icon: 'mdi-folder-plus-outline', label: 'Ordner erstellen',
        count: null, active: false, run: () => emit('create-folder'),
      }];
      for (const folder of sortedFolderItems.value) {
        rows.push({
          id: folder.id,
          icon: folderSidebarIcon(folder, props.activeSavedSearchId === folder.id),
          label: folder.name,
          count: sidebarStore.savedSearchCount(folder.id),
          active: props.activeSavedSearchId === folder.id,
          run: () => emit('open-saved-search', folder.id),
        });
      }
      return rows;
    }
    case 'tags':
      return [{
        id: 'all-tags', icon: 'mdi-view-grid-outline', label: 'Alle Tags',
        count: totalTagsSidebarCount.value, active: props.isTagView,
        run: () => emit('open-tags-view'),
      }];
    case 'kategorien':
      return [{
        id: 'all-cats', icon: 'mdi-view-grid-outline', label: 'Alle Dokumenttypen',
        count: totalCategoriesSidebarCount.value, active: props.isCategoryView,
        run: () => emit('open-categories-view'),
      }];
    default:
      return [];
  }
});

const flyoutChips = computed(() => {
  if (railFlyoutSection.value === 'tags') {
    return topTagQuicklinks.value.map((tag) => ({
      id: tag.id, name: tag.name,
      count: sidebarStore.tagCount(tag.id, tag.usage_count ?? 0),
      active: !props.isTagView && props.activeTagId === tag.id,
      run: () => emit('apply-tag-filter', tag.id),
    }));
  }
  if (railFlyoutSection.value === 'kategorien') {
    return topCategoryQuicklinks.value.map((category) => ({
      id: category.id, name: category.name,
      count: Number(category.usage_count || 0),
      active: !props.isCategoryView && props.activeCategoryName === category.name,
      run: () => emit('apply-category-filter', category.name),
    }));
  }
  return [];
});

function onRailSectionEnter(key, evt) {
  if (!props.collapsed) return;
  if (flyoutCloseTimer) { clearTimeout(flyoutCloseTimer); flyoutCloseTimer = null; }
  const asideEl = rootRef.value;
  const listEl = evt?.currentTarget;
  if (asideEl && listEl) {
    const asideRect = asideEl.getBoundingClientRect();
    const listRect = listEl.getBoundingClientRect();
    railFlyoutTop.value = Math.max(8, Math.round(listRect.top - asideRect.top));
  }
  railFlyoutSection.value = key;
}

function scheduleFlyoutClose() {
  if (!props.collapsed) return;
  if (flyoutCloseTimer) clearTimeout(flyoutCloseTimer);
  flyoutCloseTimer = setTimeout(() => { railFlyoutSection.value = null; }, 160);
}

function keepFlyoutOpen() {
  if (flyoutCloseTimer) { clearTimeout(flyoutCloseTimer); flyoutCloseTimer = null; }
}

function runFlyout(item) {
  item?.run?.();
  railFlyoutSection.value = null;
  if (flyoutCloseTimer) { clearTimeout(flyoutCloseTimer); flyoutCloseTimer = null; }
}

onBeforeUnmount(() => {
  if (flyoutCloseTimer) clearTimeout(flyoutCloseTimer);
});
</script>

<style scoped>
.sidebar-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px 10px;
}

/* ── Section Header ───────────────────────────────────────────────────── */
.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 0;
  padding: 8px 10px 5px;
  margin-bottom: 4px;
  cursor: pointer;
  border-radius: 8px;
  user-select: none;
  gap: 8px;
  transition: background 0.12s ease, margin-bottom 0.12s ease;
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

.sidebar-section-header-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex: 0 0 70px;
  gap: 5px;
  margin-inline-start: auto;
  min-width: 0;
}

.sidebar-section-icon-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}

.sidebar-section-icon-action:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: var(--pm-text);
}

.sidebar-section-icon-action:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.7);
  outline-offset: 1px;
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
  margin-left: 0;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.5);
  opacity: 0.55;
  pointer-events: auto;
  transition: opacity 0.15s ease, background 0.12s ease, color 0.12s ease;
}

.sidebar-section-header:hover .sidebar-section-toggle,
.sidebar-section-header:focus-within .sidebar-section-toggle,
.sidebar-section-header--collapsed .sidebar-section-toggle {
  opacity: 0.86;
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

/* ── Drawer animation ─────────────────────────────────────────────────── */
.sidebar-section-drawer {
  max-height: var(--pm-sidebar-section-open-height, 420px);
  overflow: hidden;
  opacity: 1;
  transition:
    max-height 0.24s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.16s ease;
}

.sidebar-section-drawer--collapsed {
  max-height: 0;
  opacity: 0;
}

.sidebar-section-header--collapsed {
  margin-bottom: 0;
}

.sidebar-section-content {
  overflow: hidden;
  visibility: visible;
  transition: visibility 0s linear 0s;
}

/* Eingeklappte Items aus Tab-Reihenfolge entfernen */
.sidebar-section-drawer--collapsed .sidebar-section-content {
  visibility: hidden;
  transition: visibility 0s linear 0.24s;
}

/* ── Chip-Wolke (Tags & Dokumenttypen, Vorlage 6a) ────────────────────── */
.sidebar-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 5px 10px 6px;
}

.sidebar-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 4px 9px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.09);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.07);
  color: color-mix(in srgb, var(--pm-text) 80%, transparent);
  font-size: 0.78rem;
  font-weight: 500;
  line-height: 1.35;
  cursor: pointer;
  transition: background-color 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}

.sidebar-chip:hover {
  background: rgba(var(--v-theme-on-surface), 0.1);
  border-color: rgba(var(--v-theme-on-surface), 0.14);
}

.sidebar-chip__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-chip__count {
  flex: none;
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--pm-muted);
  font-variant-numeric: tabular-nums;
}

.sidebar-chip--active {
  background: color-mix(in srgb, var(--pm-accent) 16%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 42%, transparent);
  color: var(--pm-accent);
}

.sidebar-chip--active .sidebar-chip__count {
  color: var(--pm-accent);
}

.sidebar-chip:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--pm-accent) 55%, transparent);
  outline-offset: 1px;
}

/* ── Rail-Flyout (Vorlage 6b) ─────────────────────────────────────────── */
.sidebar-rail-flyout {
  position: absolute;
  left: calc(100% + 6px);
  z-index: 60;
  width: 216px;
  padding: 8px;
  background: var(--pm-app-surface-raised);
  border: 1px solid color-mix(in srgb, var(--pm-text) 13%, transparent);
  border-radius: 12px;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.5);
  animation: sidebar-flyout-in 0.14s ease;
}

@keyframes sidebar-flyout-in {
  from { opacity: 0; transform: translateX(-4px); }
  to   { opacity: 1; transform: translateX(0); }
}

.sidebar-rail-flyout__arrow {
  position: absolute;
  left: -5px;
  top: 18px;
  width: 10px;
  height: 10px;
  background: var(--pm-app-surface-raised);
  border-left: 1px solid color-mix(in srgb, var(--pm-text) 13%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--pm-text) 13%, transparent);
  transform: rotate(45deg);
}

.sidebar-rail-flyout__title {
  font-size: 0.66rem;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--pm-muted);
  padding: 5px 8px 6px;
}

.sidebar-rail-flyout__row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 9px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--pm-text);
  cursor: pointer;
  text-align: left;
  font-size: 0.82rem;
  transition: background-color 0.14s ease;
}

.sidebar-rail-flyout__row:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.sidebar-rail-flyout__icon {
  flex: none;
  color: var(--pm-muted) !important;
}

.sidebar-rail-flyout__label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-rail-flyout__count {
  flex: none;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--pm-muted);
  font-variant-numeric: tabular-nums;
}

.sidebar-rail-flyout__row--active {
  background: color-mix(in srgb, var(--pm-accent) 12%, transparent);
  box-shadow: none;
}

.sidebar-rail-flyout__row--active .sidebar-rail-flyout__label,
.sidebar-rail-flyout__row--active .sidebar-rail-flyout__count,
.sidebar-rail-flyout__row--active .sidebar-rail-flyout__icon {
  color: var(--pm-accent) !important;
}

.sidebar-chips--flyout {
  padding: 6px 4px 2px;
}

/* Touch-Geräte: Toggle immer sichtbar */
@media (hover: none) {
  .sidebar-section-toggle {
    opacity: 1;
    pointer-events: auto;
  }
}
</style>
