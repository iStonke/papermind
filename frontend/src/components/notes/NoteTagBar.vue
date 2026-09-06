<!--
  NoteTagBar — Inline-Tag-Chips einer Notiz mit „+ Tag"-Menü. Nutzt das
  gemeinsame PaperMind-Tag-Vokabular; Auswahl bestehender Tags oder Anlegen
  neuer (createTagByName). Autocomplete-Muster von StageTags übernommen
  (v-autocomplete + no-filter + return-object), um die combobox-search-desync-
  Falle zu vermeiden. Gibt die Tag-ID-Liste via update:tagIds nach oben.
-->
<template>
  <TagInlineEditor
    v-if="compact"
    :model-value="compactTagNames"
    :search="searchValue"
    :items="compactTagItems"
    :loading="isLoadingTags || isCreatingTag"
    :disabled="disabled"
    :single-line="singleLine"
    @update:model-value="onCompactTagNamesChange"
    @update:search="searchValue = $event"
    @remove="removeCompactTag"
    @focus="loadTagsIfNeeded"
  />

  <div v-else class="note-tag-bar">
    <span
      v-for="tag in visibleSelectedTags"
      :key="tag.id"
      class="note-tag-bar__chip"
    >
      <v-icon size="12" class="note-tag-bar__chip-ic">mdi-tag</v-icon>
      <span class="note-tag-bar__chip-label">{{ tag.name }}</span>
      <button
        v-if="!disabled"
        type="button"
        class="note-tag-bar__chip-remove"
        :aria-label="`Tag ${tag.name} entfernen`"
        @click="removeTag(tag.id)"
      >
        <v-icon size="12">mdi-close</v-icon>
      </button>
    </span>

    <span v-if="hiddenTagCount" class="note-tag-bar__overflow" :title="hiddenTagTitle">
      +{{ hiddenTagCount }}
    </span>

    <v-menu
      v-model="isMenuOpen"
      :close-on-content-click="false"
      location="bottom start"
      offset="6"
    >
      <template #activator="{ props: menuProps }">
        <button
          type="button"
          class="note-tag-bar__add"
          :class="{ 'is-empty': !selectedTags.length }"
          :disabled="disabled"
          :aria-label="selectedTags.length ? 'Weiteres Tag hinzufügen' : 'Tag hinzufügen'"
          v-bind="menuProps"
        >
          <v-icon size="13">mdi-plus</v-icon>
          <span>{{ selectedTags.length ? 'Tag' : 'Tag hinzufügen' }}</span>
        </button>
      </template>

      <v-sheet class="note-tag-bar__menu" rounded="lg">
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
          autofocus
          no-filter
          label="Tag suchen oder anlegen …"
          :menu-props="{ maxHeight: 240 }"
          class="note-tag-bar__autocomplete"
          @update:model-value="onSelectItem"
          @keydown.enter.prevent="onEnter"
        />
      </v-sheet>
    </v-menu>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import TagInlineEditor from '../TagInlineEditor.vue';

const props = defineProps({
  tagIds: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  singleLine: { type: Boolean, default: false },
  maxVisible: { type: Number, default: 0 },
  createTagByName: { type: Function, default: null },
  loadTags: { type: Function, default: null },
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
  for (const raw of props.tagIds || []) {
    const id = String(raw || '').trim();
    if (id && !seen.has(id)) { seen.add(id); values.push(id); }
  }
  return values;
});

const tagById = computed(() => {
  const lookup = new Map();
  for (const entry of props.allTags || []) {
    const id = String(entry?.id || '').trim();
    if (id) lookup.set(id, { id, name: String(entry?.name || '').trim() || id });
  }
  return lookup;
});

const selectedTags = computed(() =>
  normalizedTagIds.value.map((id) => tagById.value.get(id) || { id, name: id }),
);

const compactTagNames = ref([]);

const visibleSelectedTags = computed(() => {
  const limit = Number(props.maxVisible) || 0;
  return limit > 0 ? selectedTags.value.slice(0, limit) : selectedTags.value;
});

const hiddenTagCount = computed(() => Math.max(0, selectedTags.value.length - visibleSelectedTags.value.length));
const hiddenTagTitle = computed(() => selectedTags.value
  .slice(visibleSelectedTags.value.length)
  .map((tag) => tag.name)
  .join(', '));

const availableTags = computed(() => {
  const selected = new Set(normalizedTagIds.value);
  return (props.allTags || [])
    .map((e) => ({ id: String(e?.id || '').trim(), name: String(e?.name || '').trim() }))
    .filter((e) => e.id && e.name && !selected.has(e.id));
});

const compactTagItems = computed(() => {
  const query = String(searchValue.value || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE');
  return (props.allTags || [])
    .map((entry) => String(entry?.name || '').replace(/\s+/g, ' ').trim())
    .filter((name) => name && (!query || name.toLocaleLowerCase('de-DE').includes(query)))
    .sort((left, right) => left.localeCompare(right, 'de-DE'));
});

const normalizedSearch = computed(() => String(searchValue.value || '').replace(/\s+/g, ' ').trim());

function findTagByName(name) {
  const norm = String(name || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE');
  if (!norm) return null;
  return (props.allTags || []).find(
    (e) => String(e?.name || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE') === norm,
  ) || null;
}

const createCandidate = computed(() => {
  const search = normalizedSearch.value;
  if (!search || findTagByName(search)) return null;
  return { id: `__create__:${search}`, name: search, title: `Neuen Tag anlegen: „${search}"`, __create: true };
});

const filteredItems = computed(() => {
  const query = normalizedSearch.value.toLocaleLowerCase('de-DE');
  const base = availableTags.value
    .filter((e) => !query || e.name.toLocaleLowerCase('de-DE').includes(query))
    .map((e) => ({ ...e, title: e.name }));
  return createCandidate.value ? [createCandidate.value, ...base] : base;
});

function addTag(id) {
  const norm = String(id || '').trim();
  if (!norm || normalizedTagIds.value.includes(norm)) return;
  emit('update:tagIds', [...normalizedTagIds.value, norm]);
}

function removeTag(id) {
  const norm = String(id || '').trim();
  if (!norm) return;
  emit('update:tagIds', normalizedTagIds.value.filter((e) => e !== norm));
}

function normalizeNames(values) {
  const seen = new Set();
  const names = [];
  for (const value of values || []) {
    const name = String(value?.title ?? value?.name ?? value ?? '').replace(/\s+/g, ' ').trim();
    const key = name.toLocaleLowerCase('de-DE');
    if (name && !seen.has(key)) {
      seen.add(key);
      names.push(name);
    }
  }
  return names;
}

async function onCompactTagNamesChange(values) {
  const names = normalizeNames(values);
  compactTagNames.value = names;
  const ids = [];
  isCreatingTag.value = true;
  try {
    for (const name of names) {
      let id = String(findTagByName(name)?.id || '').trim();
      if (!id && typeof props.createTagByName === 'function') {
        id = String(await props.createTagByName(name) || '').trim();
      }
      if (id && !ids.includes(id)) ids.push(id);
    }
    emit('update:tagIds', ids);
    searchValue.value = '';
  } finally {
    isCreatingTag.value = false;
  }
}

function removeCompactTag(name) {
  const key = String(name || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE');
  const tag = selectedTags.value.find(
    (entry) => entry.name.replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE') === key,
  );
  compactTagNames.value = compactTagNames.value.filter(
    (entry) => entry.replace(/\s+/g, ' ').trim().toLocaleLowerCase('de-DE') !== key,
  );
  if (tag?.id) removeTag(tag.id);
}

function resetInput() {
  selectedItem.value = null;
  searchValue.value = '';
}

async function attachOrCreate(search) {
  const norm = String(search || '').replace(/\s+/g, ' ').trim();
  if (!norm) return;
  const existing = findTagByName(norm);
  if (existing?.id) { addTag(existing.id); return; }
  if (typeof props.createTagByName !== 'function' || isCreatingTag.value) return;
  isCreatingTag.value = true;
  try {
    const createdId = await props.createTagByName(norm);
    const id = String(createdId || '').trim();
    if (id) addTag(id);
  } finally {
    isCreatingTag.value = false;
  }
}

async function onSelectItem(item) {
  if (!item) return;
  if (item.__create) await attachOrCreate(item.name || normalizedSearch.value);
  else if (item.id) addTag(item.id);
  resetInput();
}

async function onEnter() {
  if (selectedItem.value) { await onSelectItem(selectedItem.value); return; }
  await attachOrCreate(normalizedSearch.value);
  resetInput();
}

async function loadTagsIfNeeded() {
  if (typeof props.loadTags !== 'function') return;
  isLoadingTags.value = true;
  try { await props.loadTags(); } finally { isLoadingTags.value = false; }
}

watch(isMenuOpen, (open) => { if (open) void loadTagsIfNeeded(); else resetInput(); });
watch(selectedTags, (tags) => {
  compactTagNames.value = tags.map((tag) => tag.name);
}, { immediate: true });
</script>

<style scoped>
.note-tag-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.note-tag-bar__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px 2px 8px;
  border-radius: 999px;
  background: var(--pm-accent-wash, rgba(0, 107, 117, 0.1));
  color: var(--pm-accent-strong, #00555f);
  border: 1px solid rgba(var(--v-theme-primary, 0 107 117), 0.28);
  font-size: 0.76rem;
  font-weight: 500;
  line-height: 1.5;
  max-width: 220px;
}
.note-tag-bar__chip-ic { opacity: 0.7; flex: none; }
.note-tag-bar__chip-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-tag-bar__chip-remove {
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  border-radius: 999px;
  transition: opacity 120ms ease;
}
.note-tag-bar__chip-remove:hover { opacity: 1; }

.note-tag-bar__overflow {
  display: inline-flex;
  height: 22px;
  flex: none;
  align-items: center;
  padding: 0 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-divider, #cbd5d8) 34%, transparent);
  color: var(--pm-muted, #64748b);
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1;
}

.note-tag-bar__add {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 9px 2px 6px;
  border-radius: 999px;
  border: 1px dashed var(--pm-divider, #cbd5d8);
  background: transparent;
  color: var(--pm-muted, #64748b);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}
.note-tag-bar__add:hover:not(:disabled) {
  color: var(--pm-accent-strong, #00555f);
  border-color: rgba(var(--v-theme-primary, 0 107 117), 0.5);
  background: var(--pm-accent-wash, rgba(0, 107, 117, 0.06));
}
.note-tag-bar__add:disabled { opacity: 0.5; cursor: default; }

.note-tag-bar__menu { padding: 10px; min-width: 280px; }

@media (prefers-reduced-motion: reduce) {
  .note-tag-bar__chip-remove,
  .note-tag-bar__add { transition: none; }
}
</style>
