<template>
  <section class="global-results" aria-label="Globale Suchergebnisse">
    <header class="global-results__header">
      <div class="panel-middle__header">
        <div class="panel-middle__title">
          <h1 class="panel-middle__heading global-results__heading">Suchergebnisse</h1>
          <div class="panel-middle__count">
            {{ normalizedQuery ? `Überall für „${normalizedQuery}“${loading ? ' · Suche läuft …' : ` · ${visibleResultCount} Treffer`}` : 'Dokumente, Notizen, Tags und Dokumenttypen' }}
          </div>
        </div>
      </div>
      <ListActionToolbar
        :actions="toolbarActions"
        :show-selection="false"
        @action-select="handleToolbarAction"
      />
    </header>

    <div class="global-results__content">
      <div v-if="loading" class="global-results__state" role="status">
        <v-progress-circular indeterminate size="22" width="2" /> Suche läuft …
      </div>
      <div v-else-if="error && !resultCount" class="global-results__state" role="alert">
        {{ error }}
        <button type="button" @click="search">Erneut versuchen</button>
      </div>
      <div v-else-if="normalizedQuery && !visibleResultCount" class="global-results__state">
        Keine Treffer für „{{ normalizedQuery }}“.
      </div>
      <div v-else-if="normalizedQuery" class="global-results__body">
        <p v-if="error" class="global-results__state" role="alert">{{ error }}</p>

      <section v-if="visibleDocuments.length" class="global-results__group">
        <h2>Dokumente <span>{{ documentTotal }}</span></h2>
        <ul>
          <li v-for="document in visibleDocuments" :key="document.id">
            <button type="button" :class="{ 'is-selected': isSelected('document', document.id) }" :aria-pressed="isSelected('document', document.id)" @click="selectResult('document', document)">
              <v-icon size="19">mdi-file-document-outline</v-icon>
              <span class="global-results__item-body">
                <strong>{{ document.display_name || document.original_filename }}</strong>
                <small>{{ document.document_type || 'Dokument' }}<template v-if="document.document_date"> · {{ document.document_date }}</template></small>
                <span v-if="document.snippet" class="global-results__snippet" v-html="formatSearchSnippet(document.snippet)" />
              </span>
            </button>
          </li>
        </ul>
        <button v-if="documents.length < documentTotal" type="button" class="global-results__more" :disabled="loadingMore" @click="loadMoreDocuments">
          {{ loadingMore ? 'Lade …' : 'Weitere Dokumente anzeigen' }}
        </button>
      </section>

      <section v-if="visibleNotes.length" class="global-results__group">
        <h2>Notizen <span>{{ visibleNotes.length }}</span></h2>
        <ul>
          <li v-for="note in visibleNotes" :key="note.id">
            <button type="button" :class="{ 'is-selected': isSelected('note', note.id) }" :aria-pressed="isSelected('note', note.id)" @click="selectResult('note', note)">
              <v-icon size="19">mdi-note-outline</v-icon>
              <span class="global-results__item-body">
                <strong>{{ note.title || 'Ohne Titel' }}</strong>
                <small>Notiz</small>
                <span v-if="note.preview" class="global-results__snippet">{{ note.preview }}</span>
              </span>
            </button>
          </li>
        </ul>
      </section>

      <section v-if="visibleTags.length" class="global-results__group">
        <h2>Tags <span>{{ visibleTags.length }}</span></h2>
        <ul>
          <li v-for="tag in visibleTags" :key="tag.id">
            <button type="button" :class="{ 'is-selected': isSelected('tag', tag.id) }" :aria-pressed="isSelected('tag', tag.id)" @click="selectResult('tag', tag)"><v-icon size="19">mdi-tag-outline</v-icon><strong>{{ tag.name }}</strong></button>
          </li>
        </ul>
      </section>

      <section v-if="visibleCategories.length" class="global-results__group">
        <h2>Dokumenttypen <span>{{ visibleCategories.length }}</span></h2>
        <ul>
          <li v-for="category in visibleCategories" :key="category.name">
            <button type="button" :class="{ 'is-selected': isSelected('category', category.name) }" :aria-pressed="isSelected('category', category.name)" @click="selectResult('category', category)"><v-icon size="19">mdi-shape-outline</v-icon><strong>{{ category.name }}</strong></button>
          </li>
        </ul>
      </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { listDocuments } from '../api/documents.js';
import { listNotes } from '../api/notes.js';
import ListActionToolbar from '../components/ListActionToolbar.vue';
import { formatSearchSnippet } from '../utils/searchSnippet.js';

const props = defineProps({
  query: { type: String, default: '' },
  tags: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
  selectedResult: { type: Object, default: null },
});
const emit = defineEmits(['select-result']);
const normalizedQuery = computed(() => String(props.query || '').trim().slice(0, 256));
const documents = ref([]);
const documentTotal = ref(0);
const notes = ref([]);
const loading = ref(false);
const loadingMore = ref(false);
const error = ref('');
const typeFilter = ref('all');
const sortMode = ref('default');
let timer = null;
let revision = 0;

const TYPE_OPTIONS = Object.freeze([
  { value: 'all', label: 'Alle Treffer' },
  { value: 'document', label: 'Dokumente' },
  { value: 'note', label: 'Notizen' },
  { value: 'tag', label: 'Tags' },
  { value: 'category', label: 'Dokumenttypen' },
]);
const SORT_OPTIONS = Object.freeze([
  { value: 'default', label: 'Standard' },
  { value: 'name_asc', label: 'Name A–Z' },
  { value: 'name_desc', label: 'Name Z–A' },
  { value: 'newest', label: 'Zuletzt aktualisiert' },
  { value: 'oldest', label: 'Älteste zuerst' },
]);
const toolbarActions = computed(() => [
  { key: 'sort', icon: 'mdi-sort', label: SORT_OPTIONS.find((option) => option.value === sortMode.value)?.label || 'Standard', value: sortMode.value, options: SORT_OPTIONS },
  { key: 'type', icon: 'mdi-filter-variant', label: TYPE_OPTIONS.find((option) => option.value === typeFilter.value)?.label || 'Alle Treffer', value: typeFilter.value, active: typeFilter.value !== 'all', options: TYPE_OPTIONS },
]);
const includesType = (type) => typeFilter.value === 'all' || typeFilter.value === type;
const nameOf = (item) => item.display_name || item.original_filename || item.title || item.name || '';
const byName = new Intl.Collator('de-DE', { numeric: true, sensitivity: 'base' });
function sortItems(items) {
  if (sortMode.value === 'default') return items;
  const sorted = [...items];
  if (sortMode.value.startsWith('name_')) {
    const direction = sortMode.value === 'name_desc' ? -1 : 1;
    return sorted.sort((left, right) => direction * byName.compare(nameOf(left), nameOf(right)));
  }
  const direction = sortMode.value === 'oldest' ? 1 : -1;
  return sorted.sort((left, right) => direction * (
    Date.parse(left.updated_at || left.created_at || '') - Date.parse(right.updated_at || right.created_at || '') || 0
  ));
}
function handleToolbarAction({ action, value }) {
  if (action === 'sort' && SORT_OPTIONS.some((option) => option.value === value)) sortMode.value = value;
  if (action === 'type' && TYPE_OPTIONS.some((option) => option.value === value)) {
    typeFilter.value = value;
    const selectedType = props.selectedResult?.type;
    if (selectedType && !includesType(selectedType)) {
      emit('select-result', firstVisibleResult.value);
    }
  }
}

const matches = (name) => String(name || '').toLocaleLowerCase('de-DE').includes(normalizedQuery.value.toLocaleLowerCase('de-DE'));
const matchingTags = computed(() => normalizedQuery.value ? props.tags.filter((tag) => matches(tag.name)) : []);
const matchingCategories = computed(() => normalizedQuery.value ? props.categories.filter((category) => matches(category.name)) : []);
const resultCount = computed(() => documentTotal.value + notes.value.length + matchingTags.value.length + matchingCategories.value.length);
const visibleDocuments = computed(() => includesType('document') ? sortItems(documents.value) : []);
const visibleNotes = computed(() => includesType('note') ? sortItems(notes.value) : []);
const visibleTags = computed(() => includesType('tag') ? sortItems(matchingTags.value) : []);
const visibleCategories = computed(() => includesType('category') ? sortItems(matchingCategories.value) : []);
const visibleResultCount = computed(() => (
  (includesType('document') ? documentTotal.value : 0)
  + visibleNotes.value.length + visibleTags.value.length + visibleCategories.value.length
));
const firstVisibleResult = computed(() => (
  visibleDocuments.value[0] && { type: 'document', item: visibleDocuments.value[0] }
  || visibleNotes.value[0] && { type: 'note', item: visibleNotes.value[0] }
  || visibleTags.value[0] && { type: 'tag', item: visibleTags.value[0] }
  || visibleCategories.value[0] && { type: 'category', item: visibleCategories.value[0] }
  || null
));
const isSelected = (type, id) => props.selectedResult?.type === type
  && String(props.selectedResult?.item?.[type === 'category' ? 'name' : 'id']) === String(id);
const selectResult = (type, item) => emit('select-result', { type, item });

async function search() {
  const query = normalizedQuery.value;
  const currentRevision = ++revision;
  if (timer) clearTimeout(timer);
  if (!query) {
    documents.value = [];
    documentTotal.value = 0;
    notes.value = [];
    error.value = '';
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = '';
  const params = documentSearchParams(query, 0);
  const results = await Promise.allSettled([listDocuments(params.toString()), listNotes({ q: query })]);
  if (currentRevision !== revision) return;
  documents.value = results[0].status === 'fulfilled' ? results[0].value.items || [] : [];
  documentTotal.value = results[0].status === 'fulfilled' ? Number(results[0].value.total || 0) : 0;
  notes.value = results[1].status === 'fulfilled' ? results[1].value.items || [] : [];
  if (results.some((result) => result.status === 'rejected')) {
    error.value = results.every((result) => result.status === 'rejected')
      ? 'Die Suche konnte nicht geladen werden.'
      : 'Ein Teil der Ergebnisse konnte nicht geladen werden.';
  }
  const selected = props.selectedResult;
  const selectedStillVisible = selected && includesType(selected.type) && (
    selected.type === 'document' ? documents.value.some((item) => item.id === selected.item.id)
      : selected.type === 'note' ? notes.value.some((item) => item.id === selected.item.id)
        : selected.type === 'tag' ? matchingTags.value.some((item) => item.id === selected.item.id)
          : matchingCategories.value.some((item) => item.name === selected.item.name)
  );
  if (!selectedStillVisible) emit('select-result', firstVisibleResult.value);
  loading.value = false;
}

function documentSearchParams(query, offset) {
  const params = new URLSearchParams({ q: query, limit: '50', offset: String(offset) });
  const sort = {
    name_asc: ['name', 'asc'], name_desc: ['name', 'desc'],
    newest: ['updated_at', 'desc'], oldest: ['updated_at', 'asc'],
  }[sortMode.value];
  if (sort) {
    params.set('sort', sort[0]);
    params.set('order', sort[1]);
  }
  return params;
}

async function loadMoreDocuments() {
  if (loadingMore.value || documents.value.length >= documentTotal.value) return;
  const currentRevision = revision;
  loadingMore.value = true;
  try {
    const params = documentSearchParams(normalizedQuery.value, documents.value.length);
    const result = await listDocuments(params.toString());
    if (currentRevision !== revision) return;
    documents.value = [...documents.value, ...(result.items || [])];
    documentTotal.value = Number(result.total || documents.value.length);
  } catch {
    if (currentRevision === revision) error.value = 'Weitere Dokumente konnten nicht geladen werden.';
  } finally {
    if (currentRevision === revision) loadingMore.value = false;
  }
}

watch([normalizedQuery, sortMode], () => {
  ++revision;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => { timer = null; void search(); }, 250);
}, { immediate: true });
onBeforeUnmount(() => {
  ++revision;
  if (timer) clearTimeout(timer);
});
</script>

<style scoped>
.global-results { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; color: var(--pm-text); background: var(--pm-content-surface); border-right: 1px solid var(--pm-divider); }
.global-results__header { flex: none; }
.global-results__heading { margin: 0; }
.global-results__content { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 8px clamp(14px, 2vw, 28px) 22px; }
.global-results__body { max-width: 850px; margin: 0 auto; }
.global-results__group h2 span { color: var(--pm-muted); }
.global-results__group { margin: 22px 0 30px; }
.global-results__group h2 { display: flex; gap: 8px; align-items: baseline; font-size: 1rem; margin: 0 0 9px; }
.global-results__group h2 span { font-size: .82rem; font-weight: 400; }
.global-results__group ul { list-style: none; padding: 0; margin: 0; border: 1px solid var(--pm-divider); border-radius: 12px; overflow: hidden; }
.global-results__group li + li { border-top: 1px solid var(--pm-divider); }
.global-results__group li button { display: flex; align-items: flex-start; gap: 12px; width: 100%; min-width: 0; padding: 13px 15px; text-align: left; color: var(--pm-text); background: transparent; }
.global-results__group li button:hover, .global-results__group li button:focus-visible { background: var(--pm-field-bg); }
.global-results__group li button.is-selected { background: color-mix(in srgb, var(--pm-accent) 12%, var(--pm-content-surface)); box-shadow: inset 3px 0 var(--pm-accent); }
.global-results__item-body { display: flex; flex-direction: column; min-width: 0; }
.global-results__item-body strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.global-results__item-body small, .global-results__snippet { color: var(--pm-muted); }
.global-results__snippet { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.global-results__snippet :deep(mark) { color: inherit; background: color-mix(in srgb, var(--pm-accent) 26%, transparent); border-radius: 2px; padding: 0 1px; }
.global-results__state { max-width: 850px; margin: 30px auto; display: flex; gap: 12px; align-items: center; color: var(--pm-muted); }
.global-results__state button, .global-results__more { color: var(--pm-accent); text-decoration: underline; }
.global-results__more { margin-top: 13px; }
</style>
