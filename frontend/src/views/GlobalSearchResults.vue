<template>
  <section class="global-results" aria-label="Globale Suchergebnisse">
    <header class="global-results__header">
      <div class="panel-middle__header">
        <div class="panel-middle__title">
          <h1 class="panel-middle__heading global-results__heading">Suchergebnisse</h1>
          <div class="panel-middle__count">
            {{ resultCountLine }}
          </div>
        </div>
        <div class="panel-middle__actions">
          <v-btn
            class="pm-header-icon-btn"
            color="primary"
            variant="tonal"
            icon
            :disabled="!normalizedQuery"
            aria-label="Als Ordner speichern (nur Dokumenttreffer)"
            title="Als Ordner speichern – übernimmt die Dokumenttreffer (Titel oder OCR-Text)"
            @click="emit('save-as-folder', normalizedQuery)"
          >
            <v-icon size="20">mdi-folder-plus-outline</v-icon>
          </v-btn>
          <v-btn
            class="pm-header-icon-btn"
            color="primary"
            variant="tonal"
            icon
            aria-label="Suche beenden"
            title="Suche beenden"
            @click="emit('close')"
          >
            <v-icon size="20">mdi-close</v-icon>
          </v-btn>
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

        <section v-if="visibleDocuments.length" class="global-results__group" aria-label="Dokumente">
          <h2 class="global-results__group-heading">Dokumente <span>{{ documentTotal }}</span></h2>
          <ul class="global-results__cards">
            <li v-for="document in visibleDocuments" :key="document.id">
              <button
                type="button"
                class="global-results__card"
                :class="{ 'is-selected': isSelected('document', document.id) }"
                :aria-pressed="isSelected('document', document.id)"
                @click="selectResult('document', document)"
              >
                <span class="global-results__thumb" aria-hidden="true">
                  <img
                    v-if="!thumbnailErrors[document.id]"
                    :src="thumbnailUrl(document)"
                    alt=""
                    loading="lazy"
                    decoding="async"
                    @error="thumbnailErrors[document.id] = true"
                  />
                  <v-icon v-else size="20">mdi-file-document-outline</v-icon>
                </span>
                <span class="global-results__card-body">
                  <span class="global-results__title">
                    <span
                      v-for="(part, index) in highlight(documentTitle(document))"
                      :key="`t-${index}`"
                      :class="{ 'global-results__mark': part.match }"
                    >{{ part.text }}</span>
                  </span>
                  <span v-if="documentMeta(document)" class="global-results__meta">{{ documentMeta(document) }}</span>
                  <span
                    v-if="document.snippet"
                    class="global-results__snippet"
                    v-html="formatSearchSnippet(document.snippet)"
                  />
                </span>
              </button>
            </li>
          </ul>
          <button v-if="documents.length < documentTotal" type="button" class="global-results__more" :disabled="loadingMore" @click="loadMoreDocuments">
            {{ loadingMore ? 'Lade …' : `Weitere ${documentTotal - documents.length} Dokumente anzeigen` }}
          </button>
        </section>

        <section v-if="visibleNotes.length" class="global-results__group" aria-label="Notizen">
          <h2 class="global-results__group-heading">Notizen <span>{{ visibleNotes.length }}</span></h2>
          <ul class="global-results__cards global-results__cards--rows">
            <li v-for="note in visibleNotes" :key="note.id">
              <button
                type="button"
                class="global-results__card"
                :class="{ 'is-selected': isSelected('note', note.id) }"
                :aria-pressed="isSelected('note', note.id)"
                @click="selectResult('note', note)"
              >
                <span class="global-results__thumb global-results__thumb--note" aria-hidden="true">
                  <v-icon size="20">mdi-note-outline</v-icon>
                </span>
                <span class="global-results__card-body">
                  <span class="global-results__title">
                    <span
                      v-for="(part, index) in highlight(note.title?.trim() || 'Ohne Titel')"
                      :key="`t-${index}`"
                      :class="{ 'global-results__mark': part.match }"
                    >{{ part.text }}</span>
                  </span>
                  <span v-if="noteMeta(note)" class="global-results__meta">{{ noteMeta(note) }}</span>
                  <span v-if="note.preview" class="global-results__snippet">
                    <span
                      v-for="(part, index) in highlight(centerOnMatch(note.preview, normalizedQuery))"
                      :key="`s-${index}`"
                      :class="{ 'global-results__mark': part.match }"
                    >{{ part.text }}</span>
                  </span>
                </span>
              </button>
            </li>
          </ul>
        </section>

        <div v-if="visibleTags.length || visibleCategories.length" class="global-results__chip-groups">
          <section v-if="visibleTags.length" class="global-results__group" aria-label="Tags">
            <h2 class="global-results__group-heading">Tags <span>{{ visibleTags.length }}</span></h2>
            <div class="global-results__chips">
              <button
                v-for="tag in visibleTags"
                :key="tag.id"
                type="button"
                class="global-results__chip"
                :class="{ 'is-selected': isSelected('tag', tag.id) }"
                :aria-pressed="isSelected('tag', tag.id)"
                @click="selectResult('tag', tag)"
              >
                <span class="global-results__chip-label">
                  <span
                    v-for="(part, index) in highlight(tag.name)"
                    :key="`g-${index}`"
                    :class="{ 'global-results__mark': part.match }"
                  >{{ part.text }}</span>
                </span>
                <span v-if="tag.usage_count != null" class="global-results__chip-count">{{ tag.usage_count }}</span>
              </button>
            </div>
          </section>

          <section v-if="visibleCategories.length" class="global-results__group" aria-label="Dokumenttypen">
            <h2 class="global-results__group-heading">Dokumenttypen <span>{{ visibleCategories.length }}</span></h2>
            <div class="global-results__chips">
              <button
                v-for="category in visibleCategories"
                :key="category.name"
                type="button"
                class="global-results__chip"
                :class="{ 'is-selected': isSelected('category', category.name) }"
                :aria-pressed="isSelected('category', category.name)"
                @click="selectResult('category', category)"
              >
                <span class="global-results__chip-label">
                  <span
                    v-for="(part, index) in highlight(category.name)"
                    :key="`c-${index}`"
                    :class="{ 'global-results__mark': part.match }"
                  >{{ part.text }}</span>
                </span>
                <span v-if="category.usage_count != null" class="global-results__chip-count">{{ category.usage_count }}</span>
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { listDocuments } from '../api/documents.js';
import { listNotes } from '../api/notes.js';
import ListActionToolbar from '../components/ListActionToolbar.vue';
import { formatSearchSnippet } from '../utils/searchSnippet.js';
import { centerOnMatch, highlightParts } from '../utils/searchHighlight.js';
import { authedUrl, getBaseUrl } from '../api/client.js';
import { useNotesStore } from '../stores/notes.js';
import { useSettingsStore } from '../stores/settings.js';

const props = defineProps({
  query: { type: String, default: '' },
  tags: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
  selectedResult: { type: Object, default: null },
});
const emit = defineEmits(['select-result', 'save-as-folder', 'close']);
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
// Subline wie in den übrigen Listen: nur die Anzahl. Der Suchbegriff steht
// bereits im Suchfeld der Seitenleiste und wird hier nicht wiederholt.
const resultCountLine = computed(() => {
  if (!normalizedQuery.value) return 'Dokumente, Notizen, Tags und Dokumenttypen';
  if (loading.value) return 'Suche läuft …';
  return `${visibleResultCount.value} Treffer`;
});
// ── Darstellung der Treffer (Titel, Metazeile, Vorschaubild) ────────────────
const notesStore = useNotesStore();
const settingsStore = useSettingsStore();
const thumbnailErrors = reactive({});
const highlight = (value) => highlightParts(value, normalizedQuery.value);
const shortDate = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });

function parseDate(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  const date = dateOnly ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3])) : new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

function documentTitle(document) {
  const displayName = String(document?.display_name || '').trim();
  if (displayName) return displayName;
  const filename = String(document?.original_filename || '').trim();
  if (settingsStore.settings.ui.showFilenameSuffix !== false) return filename;
  return filename.replace(/\.[A-Za-z][A-Za-z0-9]{0,7}$/, '');
}

function documentMeta(document) {
  const correspondent = String(
    document?.correspondent_name || document?.correspondent_short_name
      || document?.correspondent?.short_name || document?.correspondent?.name || '',
  ).trim();
  const type = String(document?.document_type || document?.category || '').trim();
  const date = parseDate(document?.document_date);
  return [correspondent, type, date && shortDate.format(date)].filter(Boolean).join(' · ');
}

function noteMeta(note) {
  const notebook = note?.notebook_id
    ? notesStore.notebooks.find((entry) => entry.id === note.notebook_id)?.name
    : '';
  const collection = !notebook && note?.collection_id
    ? notesStore.collections.find((entry) => entry.id === note.collection_id)?.name
    : '';
  const updated = parseDate(note?.updated_at);
  let edited = '';
  if (updated) {
    edited = `bearbeitet ${shortDate.format(updated)}`;
  }
  return [notebook || collection, edited].filter(Boolean).join(' · ');
}

const thumbnailUrl = (document) => {
  const base = authedUrl(`${getBaseUrl()}/api/documents/${document.id}/thumbnail`);
  const version = encodeURIComponent(document.updated_at || '');
  return `${base}${base.includes('?') ? '&' : '?'}thumb_v=${version}`;
};

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
.global-results__content { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 0 12px 22px; background: var(--pm-list-canvas); }
.global-results__body { max-width: 850px; margin: 0 auto; }
.global-results__group { margin: 0 0 14px; }

/* Gruppenkopf wie die Tagesüberschriften der Notizliste: klein, Versalien, klebend. */
.global-results__group-heading {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  margin: 0;
  padding: 12px 4px 7px;
  background: var(--pm-list-canvas);
  color: var(--pm-muted);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.075em;
  line-height: 1.2;
  text-transform: uppercase;
}
.global-results__group-heading span { font-weight: 500; opacity: 0.75; }

/* Listen-Sprache (theme/lists.css): Dokumenttreffer als weiche Karten wie
   die Dokumentliste (B), Notiztreffer als kompakte Zeilen wie die Notizliste (A). */
.global-results__cards { list-style: none; padding: 0; margin: 0; }
.global-results__cards li + li { margin-top: 8px; }
.global-results__card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  min-width: 0;
  padding: 11px 13px;
  text-align: left;
  color: var(--pm-text);
  border: 0;
  border-radius: 12px;
  background: var(--pm-list-card);
  box-shadow: var(--pm-list-card-shadow);
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, ease),
    box-shadow var(--pm-duration-fast, 140ms) var(--pm-easing, ease);
}
.global-results__card:hover { box-shadow: var(--pm-list-card-shadow), inset 0 0 0 1px var(--pm-list-hover-ring); }
.global-results__card:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.global-results__card.is-selected,
.global-results__card.is-selected:hover {
  background: linear-gradient(var(--pm-list-selected), var(--pm-list-selected)), var(--pm-list-card);
  box-shadow: var(--pm-list-card-shadow), inset 0 0 0 2px var(--pm-list-accent);
}

.global-results__cards--rows li + li { margin-top: 0; }
.global-results__cards--rows li:not(:last-child) .global-results__card { border-bottom: 1px solid var(--pm-list-divider); }
.global-results__cards--rows .global-results__card { border-radius: 0; background: transparent; box-shadow: none; }
.global-results__cards--rows .global-results__card:hover { box-shadow: none; background: var(--pm-list-hover); }
.global-results__cards--rows .global-results__card.is-selected,
.global-results__cards--rows .global-results__card.is-selected:hover {
  background: var(--pm-list-selected);
  box-shadow: inset 3px 0 0 var(--pm-list-accent);
}

.global-results__thumb {
  flex: none;
  display: grid;
  place-items: center;
  width: 38px;
  height: 50px;
  overflow: hidden;
  border-radius: 6px;
  background: var(--pm-thumb-bg, rgba(15, 23, 42, 0.08));
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.12);
  color: var(--pm-muted);
}
.global-results__thumb img { width: 100%; height: 100%; object-fit: cover; object-position: top; background: #fff; }
.global-results__thumb--note { height: 38px; border-radius: 10px; box-shadow: none; background: var(--pm-list-chip-bg); }

.global-results__card-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1 1 auto; }
.global-results__title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--pm-list-title);
  overflow-wrap: anywhere;
}
.global-results__meta { color: var(--pm-list-meta); font-size: 0.75rem; line-height: 1.35; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.global-results__snippet {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin-top: 3px;
  color: var(--pm-list-meta);
  font-size: 0.8rem;
  line-height: 1.45;
}

/* Treffer-Markierung wie in der Notizliste. */
.global-results__mark,
.global-results__snippet :deep(mark) {
  border-radius: 3px;
  background: color-mix(in srgb, var(--pm-accent) 22%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--pm-accent) 8%, transparent);
  color: inherit;
  padding: 0 0.08em;
}

/* Tags und Dokumenttypen als Chips; bei genug Breite nebeneinander. */
.global-results__chip-groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); column-gap: 20px; }
.global-results__chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 2px 2px 0; }
.global-results__chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--pm-list-chip-bg);
  color: var(--pm-list-chip-text);
  font-size: 0.8rem;
  transition: background-color var(--pm-duration-fast, 140ms) var(--pm-easing, ease);
}
.global-results__chip:hover { background: color-mix(in srgb, var(--pm-text) 11%, transparent); }
.global-results__chip:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.global-results__chip.is-selected { background: var(--pm-list-selected); box-shadow: inset 0 0 0 2px var(--pm-list-accent); color: var(--pm-list-title); }
.global-results__chip-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.global-results__chip-count { color: var(--pm-list-meta-soft); font-size: 0.72rem; font-variant-numeric: tabular-nums; }

.global-results__state { max-width: 850px; margin: 30px auto; display: flex; gap: 12px; align-items: center; color: var(--pm-muted); }
.global-results__state button, .global-results__more { color: var(--pm-accent); text-decoration: underline; }
.global-results__more { margin: 10px 4px 0; font-size: 0.82rem; }
</style>
