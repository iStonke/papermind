<template>
  <div class="stage-tags">
    <v-menu
      v-model="isMenuOpen"
      :close-on-content-click="false"
      location="bottom start"
      offset="8"
    >
      <template #activator="{ props: menuProps }">
        <v-btn
          variant="text"
          size="small"
          class="stage-toolbar-btn stage-tags__trigger"
          :disabled="disabled"
          :title="triggerTitle"
          :style="buttonStyle || undefined"
          v-bind="menuProps"
        >
          <v-icon size="16" start>mdi-tag-outline</v-icon>
          Tags<span v-if="selectedTags.length"> · {{ selectedTags.length }}</span>
        </v-btn>
      </template>

      <v-sheet class="stage-tags__menu" rounded="lg">
        <v-autocomplete
          v-model="selectedItem"
          v-model:search="searchValue"
          :items="filteredItems"
          :loading="isLoadingTags"
          item-title="title"
          return-object
          density="compact"
          variant="outlined"
          hide-details
          clearable
          no-filter
          label="Tag hinzufügen..."
          :menu-props="{ maxHeight: 240 }"
          class="stage-tags__autocomplete"
          @update:model-value="onSelectItem"
          @keydown="handleTagInputShortcut"
        />

        <div class="stage-tags__list-wrap">
          <div class="stage-tags__list-title">Aktive Tags</div>
          <v-list density="compact" class="stage-tags__list">
            <v-list-item
              v-for="tag in selectedTags"
              :key="tag.id"
              :title="tag.name"
              class="stage-tags__list-item"
            >
              <template #append>
                <v-btn
                  size="x-small"
                  variant="text"
                  :icon="'mdi-close'"
                  aria-label="Tag entfernen"
                  @click="removeTag(tag.id)"
                />
              </template>
            </v-list-item>
            <div v-if="selectedTags.length === 0" class="stage-tags__empty">Noch keine Tags</div>
          </v-list>
        </div>
      </v-sheet>
    </v-menu>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts';

const props = defineProps({
  tagIds: {
    type: Array,
    default: () => []
  },
  allTags: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  },
  createTagByName: {
    type: Function,
    default: null
  },
  loadTags: {
    type: Function,
    default: null
  },
  buttonStyle: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['update:tagIds']);

const isMenuOpen = ref(false);
const searchValue = ref('');
const selectedItem = ref(null);
const isCreatingTag = ref(false);
const isLoadingTags = ref(false);

const normalizedTagIds = computed(() => {
  const seen = new Set();
  const values = [];
  for (const rawValue of props.tagIds || []) {
    const tagId = String(rawValue || '').trim();
    if (!tagId || seen.has(tagId)) {
      continue;
    }
    seen.add(tagId);
    values.push(tagId);
  }
  return values;
});

const tagById = computed(() => {
  const lookup = new Map();
  for (const entry of props.allTags || []) {
    const id = String(entry?.id || '').trim();
    if (!id) {
      continue;
    }
    lookup.set(id, {
      id,
      name: String(entry?.name || '').trim() || id
    });
  }
  return lookup;
});

const selectedTags = computed(() =>
  normalizedTagIds.value.map((tagId) => tagById.value.get(tagId) || { id: tagId, name: tagId })
);
const triggerTitle = computed(() => selectedTags.value.map((entry) => entry.name).join(', '));

const availableTags = computed(() => {
  const selectedIds = new Set(normalizedTagIds.value);
  return (props.allTags || [])
    .map((entry) => ({
      id: String(entry?.id || '').trim(),
      name: String(entry?.name || '').trim()
    }))
    .filter((entry) => entry.id && entry.name && !selectedIds.has(entry.id));
});

const normalizedSearchValue = computed(() => String(searchValue.value || '').replace(/\s+/g, ' ').trim());

function findTagByName(name) {
  const normalized = String(name || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE');
  if (!normalized) {
    return null;
  }
  return (
    (props.allTags || []).find(
      (entry) => String(entry?.name || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE') === normalized
    ) || null
  );
}

const createCandidateItem = computed(() => {
  const search = normalizedSearchValue.value;
  if (!search) {
    return null;
  }
  if (findTagByName(search)) {
    return null;
  }
  return {
    id: `__create__:${search}`,
    name: search,
    title: `Neuen Tag anlegen: "${search}"`,
    __create: true
  };
});

const filteredItems = computed(() => {
  const query = normalizedSearchValue.value.toLocaleLowerCase('de-DE');
  const base = availableTags.value
    .filter((entry) => !query || entry.name.toLocaleLowerCase('de-DE').includes(query))
    .map((entry) => ({
      ...entry,
      title: entry.name
    }));
  if (createCandidateItem.value) {
    return [createCandidateItem.value, ...base];
  }
  return base;
});

function addTag(tagId) {
  const normalized = String(tagId || '').trim();
  if (!normalized || normalizedTagIds.value.includes(normalized)) {
    return;
  }
  emit('update:tagIds', [...normalizedTagIds.value, normalized]);
}

function removeTag(tagId) {
  const normalized = String(tagId || '').trim();
  if (!normalized) {
    return;
  }
  emit(
    'update:tagIds',
    normalizedTagIds.value.filter((entry) => entry !== normalized)
  );
}

function resetInput() {
  selectedItem.value = null;
  searchValue.value = '';
}

async function attachOrCreate(search) {
  const normalizedSearch = String(search || '').replace(/\s+/g, ' ').trim();
  if (!normalizedSearch) {
    return;
  }
  const existingTag = findTagByName(normalizedSearch);
  if (existingTag?.id) {
    addTag(existingTag.id);
    return;
  }
  if (typeof props.createTagByName !== 'function') {
    return;
  }
  if (isCreatingTag.value) {
    return;
  }
  isCreatingTag.value = true;
  try {
    const createdTagId = await props.createTagByName(normalizedSearch);
    const normalizedId = String(createdTagId || '').trim();
    if (normalizedId) {
      addTag(normalizedId);
    }
  } finally {
    isCreatingTag.value = false;
  }
}

async function onSelectItem(item) {
  if (!item) {
    return;
  }
  if (item.__create) {
    await attachOrCreate(item.name || normalizedSearchValue.value);
  } else if (item.id) {
    addTag(item.id);
  }
  resetInput();
}

async function onEnter() {
  if (selectedItem.value) {
    await onSelectItem(selectedItem.value);
    return;
  }
  await attachOrCreate(normalizedSearchValue.value);
  resetInput();
}

function handleTagInputShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, onEnter, { ignoreEditable: false });
}

async function loadTagsIfNeeded() {
  if (typeof props.loadTags !== 'function') {
    return;
  }
  isLoadingTags.value = true;
  try {
    await props.loadTags();
  } finally {
    isLoadingTags.value = false;
  }
}

watch(isMenuOpen, (open) => {
  if (!open) {
    return;
  }
  void loadTagsIfNeeded();
});
</script>

<style scoped>
.stage-tags {
  min-width: 0;
}

.stage-tags__trigger {
  height: 36px;
  min-height: 36px;
  min-width: auto;
  border-radius: 10px;
  text-transform: none;
  letter-spacing: 0;
  padding-inline: 12px;
  font-size: 0.78rem;
  font-weight: 500;
  white-space: nowrap;
  color: var(--pm-toolbar-icon-color, rgba(15, 23, 42, 0.68));
  background: transparent !important;
}

.stage-tags__trigger:hover {
  background: var(--pm-dm-hover, rgba(0, 0, 0, 0.06)) !important;
  color: var(--pm-dm-text, inherit) !important;
}

:deep(.v-theme--dark) .importer-dialog .stage-tags__trigger:hover {
  background: var(--pm-dm-hover, rgba(255, 255, 255, 0.10)) !important;
}

:deep(.v-theme--dark .importer-dialog .stage-tags__trigger),
:deep(.v-theme--dark .importer-dialog .stage-tags__trigger .v-btn__content),
:deep(.v-theme--dark .importer-dialog .stage-tags__trigger .v-icon) {
  color: var(--pm-dm-text2, rgba(255, 255, 255, 0.70)) !important;
  opacity: 1 !important;
}

:deep(.v-theme--dark) .importer-dialog .stage-tags__trigger.v-btn--disabled {
  color: var(--pm-dm-text2, rgba(255, 255, 255, 0.70)) !important;
  opacity: 1;
}

.stage-tags__trigger.v-btn--disabled,
.stage-tags__trigger.v-btn--disabled .v-btn__content,
.stage-tags__trigger.v-btn--disabled .v-icon {
  color: var(--pm-toolbar-disabled-color, rgba(15, 23, 42, 0.34)) !important;
  --v-btn-color: var(--pm-toolbar-disabled-color, rgba(15, 23, 42, 0.34)) !important;
  opacity: 0.5 !important;
}

.stage-tags__menu {
  width: min(380px, calc(100vw - 32px));
  max-width: 420px;
  padding: 14px;
  display: grid;
  gap: 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  background: rgb(var(--v-theme-surface-2, var(--v-theme-surface)));
}

:deep(.v-theme--dark) .importer-dialog .stage-tags__menu {
  border-color: var(--pm-dm-divider, rgba(255, 255, 255, 0.14));
  background: rgba(255, 255, 255, 0.06);
}

.stage-tags__autocomplete {
  margin-top: 2px;
}

.stage-tags__list-wrap {
  display: grid;
  gap: 6px;
}

.stage-tags__list-title {
  font-size: 0.74rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

:deep(.v-theme--dark) .importer-dialog .stage-tags__list-title {
  color: var(--pm-dm-text2, rgba(255, 255, 255, 0.70));
}

.stage-tags__list {
  border-radius: 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  background: rgb(var(--v-theme-surface));
  overflow: hidden;
}

:deep(.v-theme--dark) .importer-dialog .stage-tags__list {
  border-color: var(--pm-dm-divider, rgba(255, 255, 255, 0.14));
  background: rgba(255, 255, 255, 0.04);
}

.stage-tags__list-item {
  min-height: 32px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

:deep(.v-theme--dark) .importer-dialog .stage-tags__list-item {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.stage-tags__list-item:last-child {
  border-bottom: 0;
}

.stage-tags__empty {
  font-size: 0.76rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding: 8px 12px;
}
</style>
