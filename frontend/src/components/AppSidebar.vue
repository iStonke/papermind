<template>
  <aside class="panel panel-left">
    <!-- Bibliothek -->
    <v-list nav density="compact" class="views-list">
      <div class="sidebar-section-header">
        <div class="sidebar-section-label">Bibliothek</div>
      </div>
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
      </div>
    </v-list>

    <v-divider class="sidebar-section-divider" />

    <!-- Ordner -->
    <v-list nav density="compact" class="views-list">
      <div class="sidebar-section-header">
        <div class="sidebar-section-label">Ordner</div>
      </div>

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
    </v-list>

    <v-divider class="sidebar-section-divider" />

    <!-- Tags -->
    <v-list nav density="compact" class="views-list">
      <div class="sidebar-section-header">
        <div class="sidebar-section-label">Tags</div>
      </div>

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
    </v-list>
  </aside>
</template>

<script setup>
import { computed } from 'vue';
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
  'open-tags-view',
  'apply-tag-filter',
]);

// ── Stores ─────────────────────────────────────────────────────────────────
const sidebarStore = useSidebarStore();
const tagStore     = useTagStore();

const { sidebarCounts, savedSearches } = storeToRefs(sidebarStore);
const { tags }                         = storeToRefs(tagStore);

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
  if (viewKey === 'imports')  return props.activeView === 'imports';
  if (viewKey === 'untagged') return props.activeView === 'untagged';
  return props.activeView === viewKey;
}

// ── Computed counts ────────────────────────────────────────────────────────
const allDocumentsSidebarCount = computed(() => Number(sidebarCounts.value.all_documents || 0));
const importsSidebarCount = computed(
  () => Number(sidebarCounts.value.imports?.recent_total || sidebarCounts.value.imports?.imported || 0)
);
const untaggedSidebarCount = computed(() => Number(sidebarCounts.value.untagged || 0));

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
