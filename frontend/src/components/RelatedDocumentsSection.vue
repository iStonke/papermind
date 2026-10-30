<template>
  <DocumentSectionCard class="related-documents" title="Ähnliche Dokumente"
    :count="total" :loading="loading && !items.length" loading-label="Ähnliche Dokumente werden gesucht …"
    :empty="!inTrash && !error && !items.length" :empty-message="emptyMessage">
    <template #toolbar>
      <div v-if="!inTrash" class="related-documents__filters" role="group" aria-label="Ähnliche Dokumente eingrenzen">
        <button v-for="option in modes" :key="option.value" type="button" class="related-documents__filter"
          :aria-pressed="mode === option.value" @click="mode = option.value">{{ option.label }}</button>
      </div>
    </template>
    <p v-if="inTrash" class="related-documents__state">Für Dokumente im Papierkorb werden keine Vorschläge angezeigt.</p>
    <div v-else-if="error" class="related-documents__state" role="status">
      <span>{{ items.length ? 'Weitere Dokumente konnten nicht geladen werden.' : 'Ähnliche Dokumente konnten nicht geladen werden.' }}</span>
      <button type="button" class="related-documents__retry" @click="load({ append: items.length > 0, force: true })">Erneut versuchen</button>
    </div>
    <ul v-if="items.length && !inTrash" class="related-documents__list">
      <li v-for="item in items" :key="item.id">
        <component :is="readOnly ? 'div' : 'button'" :type="readOnly ? undefined : 'button'" class="related-documents__item"
          :class="{ 'related-documents__item--readonly': readOnly }" :title="formatTitle(item.title)" @click="!readOnly && emit('open-document', item.id)">
          <span class="related-documents__icon" aria-hidden="true"><v-icon size="20">mdi-file-document-outline</v-icon></span>
          <span class="related-documents__copy">
            <span class="related-documents__title">{{ formatTitle(item.title) }}</span>
            <span class="related-documents__reasons">
              <span v-if="item.same_series">Gleiche Dokumentserie</span>
              <span v-else-if="item.similar_title">Ähnlicher Titel</span>
              <span v-if="item.same_correspondent">{{ item.same_type ? 'Gleicher Korrespondent und Dokumenttyp' : 'Gleicher Korrespondent' }}</span>
              <span v-else-if="item.same_type">Gleicher Dokumenttyp</span>
              <span v-if="item.shared_tag_count" :title="tagExplanation(item)">{{ tagExplanation(item, true) }}</span>
            </span>
          </span>
          <time v-if="item.document_date" class="related-documents__date" :datetime="item.document_date">{{ formatDate(item.document_date) }}</time>
          <v-icon v-if="!readOnly" class="related-documents__arrow" size="17" aria-hidden="true">mdi-chevron-right</v-icon>
        </component>
      </li>
    </ul>
    <div v-if="items.length && !inTrash" class="related-documents__footer">
      <span aria-live="polite">{{ total > items.length ? `${items.length} von ${total} Vorschlägen` : `${items.length} ${items.length === 1 ? 'Vorschlag' : 'Vorschläge'}` }}</span>
      <button v-if="hasMore" type="button" class="related-documents__more" :disabled="loading" :aria-busy="loading"
        @click="load({ append: true })">{{ loading ? 'Wird geladen …' : 'Mehr anzeigen' }}</button>
    </div>
  </DocumentSectionCard>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import DocumentSectionCard from './DocumentSectionCard.vue';
import { getRelatedDocuments } from '../api/documents.js';
import { normalizeRelatedPreferences } from '../utils/relatedPreferences.js';
const props = defineProps({ documentId: String, matchKey: { type: String, default: '' }, enabled: Boolean, inTrash: Boolean, showSuffix: { type: Boolean, default: false }, preferences: Object, readOnly: Boolean });
const emit = defineEmits(['open-document', 'loading-change']);
const modes = [{ value: 'recommended', label: 'Empfohlen' }, { value: 'correspondent', label: 'Gleicher Absender' }, { value: 'tags', label: 'Gemeinsame Tags' }];
const mode = ref('recommended');
const items = ref([]), total = ref(0), hasMore = ref(false), loading = ref(false), error = ref(false);
const cache = new Map();
let revision = 0, context = '', nextOffset = 0;
const preferences = computed(() => props.preferences ? normalizeRelatedPreferences(props.preferences) : undefined);
const preferencesKey = computed(() => JSON.stringify(preferences.value) || '');
function key() { return `${props.documentId || ''}|${props.matchKey}|${mode.value}|${preferencesKey.value}`; }
const emptyMessage = computed(() => mode.value === 'recommended'
  ? 'Keine Vorschläge. Probiere „Gleicher Absender“ oder „Gemeinsame Tags“.'
  : mode.value === 'correspondent' ? 'Für diesen Korrespondenten wurden keine weiteren Dokumente gefunden.'
    : 'Es wurden keine weiteren Dokumente mit gemeinsamen Tags gefunden.');
function applyPage(page) {
  items.value = page.items; total.value = page.total; hasMore.value = page.hasMore; nextOffset = page.nextOffset;
}
async function load({ append = false, force = false } = {}) {
  if (!props.enabled || !props.documentId || props.inTrash) return;
  const currentKey = key();
  if (!append && !force && cache.has(currentKey)) { applyPage(cache.get(currentKey)); return; }
  if (append && loading.value) return;
  const request = ++revision;
  const offset = append ? nextOffset : 0;
  loading.value = true;
  error.value = false;
  try {
    const result = await getRelatedDocuments(props.documentId, { mode: mode.value, offset, preferences: preferences.value });
    if (request !== revision || currentKey !== key()) return;
    const batch = result.items || [];
    const combined = append ? [...items.value, ...batch] : batch;
    const page = { items: [...new Map(combined.map(item => [item.id, item])).values()],
      total: result.total ?? combined.length, hasMore: result.has_more === true, nextOffset: offset + batch.length };
    applyPage(page);
    cache.set(currentKey, page);
  } catch {
    if (request === revision) error.value = true;
  } finally {
    if (request === revision) loading.value = false;
  }
}
watch(() => [props.documentId, props.matchKey, props.enabled, props.inTrash, mode.value, preferencesKey.value], (current, previous) => {
  revision++;
  loading.value = false; error.value = false;
  const nextContext = `${props.documentId || ''}|${props.matchKey}|${props.inTrash}|${preferencesKey.value}`;
  if (context !== nextContext) { cache.clear(); context = nextContext; }
  // Detail metadata may arrive after selection. Keep the current results in
  // place during that refresh instead of collapsing the card to a spinner.
  const metadataRefresh = previous && current[0] === previous[0] && current[1] !== previous[1]
    && current.slice(2).every((value, index) => value === previous[index + 2]);
  if (!metadataRefresh) applyPage(cache.get(key()) || { items: [], total: 0, hasMore: false, nextOffset: 0 });
  if (props.enabled) void load();
}, { immediate: true });
watch(loading, value => emit('loading-change', value), { immediate: true, flush: 'sync' });
onBeforeUnmount(() => { revision++; });
function tagExplanation(item, compact = false) {
  const count = item.shared_tag_count;
  const tags = item.shared_tags || [];
  if (!tags.length) return `${count} ${count === 1 ? 'gemeinsames Tag' : 'gemeinsame Tags'}`;
  const remaining = Math.max(0, count - tags.length);
  const prefix = compact ? (count === 1 ? 'Gemeinsames Tag' : 'Gemeinsame Tags') : `${count} ${count === 1 ? 'gemeinsames Tag' : 'gemeinsame Tags'}`;
  return `${prefix}${tags.length ? `: ${tags.join(', ')}` : ''}${remaining ? ` (+${remaining})` : ''}`;
}
function formatTitle(value) {
  const title = String(value || '').trim();
  return props.showSuffix ? title : title.replace(/\.[A-Za-z][A-Za-z0-9]{0,7}$/, '');
}
function formatDate(value) { return String(value).slice(0, 10).split('-').reverse().join('.'); }
</script>
<style scoped>
.related-documents__state { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 18px 0; font-size: 13px; color: var(--pm-muted); }
.related-documents__retry, .related-documents__more { color: var(--pm-accent); font: inherit; font-weight: 600; }
.related-documents__list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.related-documents__item { width: 100%; display: grid; grid-template-columns: 34px minmax(0, 1fr) auto 17px; align-items: center; gap: 12px; padding: 13px 14px; text-align: left; color: var(--pm-text); background: var(--pm-app-surface); border: 1px solid color-mix(in srgb, var(--pm-muted) 32%, var(--pm-divider)); border-radius: 10px; cursor: pointer; transition: background-color 160ms ease, border-color 160ms ease; }
.related-documents__item:hover { background: color-mix(in srgb, var(--pm-accent) 7%, var(--pm-app-surface)); border-color: color-mix(in srgb, var(--pm-accent) 35%, var(--pm-divider)); }
.related-documents__item--readonly { cursor:default; grid-template-columns:34px minmax(0, 1fr); }
.related-documents__item--readonly:hover { background:var(--pm-app-surface); border-color:color-mix(in srgb, var(--pm-muted) 32%, var(--pm-divider)); }
.related-documents__item--readonly .related-documents__date { display:none; }
.related-documents__icon { display: grid; place-items: center; width: 34px; height: 40px; border-radius: 6px; background: color-mix(in srgb, var(--pm-accent) 8%, transparent); color: var(--pm-accent); }
.related-documents__copy { min-width: 0; display: grid; gap: 6px; }
.related-documents__title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.related-documents__reasons { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 11px; color: var(--pm-muted); }
.related-documents__date { font-size: 11px; color: var(--pm-muted); white-space: nowrap; }
.related-documents__arrow { color: var(--pm-muted); }
@container (max-width: 520px) { .related-documents__item { grid-template-columns: 28px minmax(0, 1fr) 17px; gap: 10px; padding-inline: 10px; } .related-documents__date { display: none; } .related-documents__icon { width: 28px; height: 36px; } }
:global(.pm-no-animations .related-documents__item) { transition: none; }
@media (prefers-reduced-motion: reduce) { .related-documents__item { transition: none; } }
.related-documents__filters { display:flex; flex-wrap:wrap; gap:6px; }
.related-documents__filter { padding:5px 10px; border:1px solid var(--pm-divider); border-radius:100px; color:var(--pm-muted); background:transparent; font:inherit; font-size:11px; cursor:pointer; }
.related-documents__filter[aria-pressed="true"] { color:var(--pm-accent); border-color:color-mix(in srgb, var(--pm-accent) 45%, var(--pm-divider)); background:color-mix(in srgb, var(--pm-accent) 9%, transparent); }
.related-documents__filter:focus-visible, .related-documents__more:focus-visible { outline:2px solid var(--pm-accent); outline-offset:3px; }
.related-documents__footer { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; color:var(--pm-muted); font-size:11px; }
.related-documents__more { cursor:pointer; padding:4px 0; }
.related-documents__more:disabled { cursor:progress; opacity:.65; }
</style>
