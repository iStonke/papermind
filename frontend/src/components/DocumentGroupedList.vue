<template>
  <div ref="root" class="doc-groups">
    <ListActionToolbar
      :actions="dateActions"
      :filter-toggles="filterToggles"
      :show-selection="false"
      @action-select="emit('change-date-range', $event.value)"
      @filter-toggle="emit('filter-toggle', $event)"
    />
    <div ref="scroller" v-list-reveal="{ selector: '.doc-groups__group', key: queryPath, ready: !loading }" class="doc-groups__scroll" :aria-busy="loading">
      <div v-if="error" class="doc-groups__message" role="alert">
        <span>{{ error }}</span>
        <v-btn variant="text" size="small" @click="refreshGroups">Erneut versuchen</v-btn>
      </div>
      <div v-if="loading && !groups.length" class="doc-groups__loading" role="status">
        <v-progress-circular indeterminate size="22" width="2" />
        <span>{{ groupingLabel }} werden geladen …</span>
      </div>
      <PmEmptyState
        v-else-if="!loading && !error && !groups.length"
        :icon="isDocumentTypeGrouping ? 'mdi-file-document-outline' : 'mdi-account-group-outline'"
        title="Keine Dokumente in dieser Auswahl"
        subtitle="Ändere die Suche oder die Filter."
        :animated="false"
      />
      <div v-else-if="groups.length" class="doc-groups__body">
        <section
          v-for="group in groups"
          :key="group.key"
          :data-group-key="group.key"
          class="doc-groups__group"
          :class="{
            'doc-groups__group--expanded': expanded.has(group.key),
            'doc-groups__group--active': group.key === selectedGroupKey,
            'doc-groups__group--unassigned': group.unassigned,
          }"
        >
          <button
            type="button"
            class="doc-groups__heading"
            :aria-expanded="expanded.has(group.key)"
            :aria-controls="groupRegionId(group)"
            :title="group.name || group.label"
            @click="toggleGroup(group)"
          >
            <span class="doc-groups__initials" aria-hidden="true">
              <v-icon v-if="isDocumentTypeGrouping && !group.unassigned" size="25">mdi-file-document-outline</v-icon>
              <template v-else-if="!group.unassigned">{{ correspondentInitials(group.label) }}</template>
              <v-icon v-else size="24">mdi-file-document-outline</v-icon>
            </span>
            <span class="doc-groups__identity">
              <span class="doc-groups__name">{{ group.label }}</span>
              <span v-if="group.name && group.name !== group.label" class="doc-groups__full-name">{{ group.name }}</span>
              <span v-else-if="group.unassigned" class="doc-groups__full-name">{{ isDocumentTypeGrouping ? 'Typ noch nicht zugeordnet' : 'Absender noch nicht zugeordnet' }}</span>
              <span v-if="group.kindLabel" class="doc-groups__kind">
                <v-icon size="14" aria-hidden="true">{{ group.kindIcon }}</v-icon>
                {{ group.kindLabel }}
              </span>
            </span>
            <span class="doc-groups__count">
              <span class="doc-groups__count-value">{{ group.count }}</span><span class="doc-groups__count-word">{{ group.count === 1 ? ' Dokument' : ' Dokumente' }}</span>
            </span>
            <span class="doc-groups__chevron" aria-hidden="true">
              <v-icon size="18">mdi-chevron-right</v-icon>
            </span>
          </button>
          <div
            :id="groupRegionId(group)"
            class="doc-groups__reveal"
            :aria-hidden="!expanded.has(group.key)"
            :inert="!expanded.has(group.key)"
          >
            <div class="doc-groups__clip">
              <div class="doc-groups__documents">
                <div v-if="pages[group.key]?.error" class="doc-groups__message" role="alert">
                  <span>{{ pages[group.key].error }}</span>
                  <v-btn variant="text" size="small" @click="retryGroup(group)">Erneut versuchen</v-btn>
                </div>
                <ul v-list-reveal="{ selector: '.doc-groups__document', key: expanded.has(group.key), ready: expanded.has(group.key) && !pages[group.key]?.loading }" class="doc-groups__list" :aria-label="`Dokumente: ${group.label}`">
                  <li v-for="doc in pages[group.key]?.items || []" :key="doc.id">
                    <button
                      type="button"
                      class="doc-groups__document"
                      :data-document-id="doc.id"
                      :class="{ 'doc-groups__document--active': doc.id === selectedId, 'pm-import-arrival': doc.id === landing.justArrivedDocId.value }"
                      :aria-pressed="doc.id === selectedId"
                      :title="documentTitle(doc)"
                      @click="emit('select', doc.id)"
                    >
                      <span class="doc-groups__thumbnail" :class="{ 'pm-import-awaiting': doc.id === landing.importLandingThumbDocId.value }" aria-hidden="true">
                        <img
                          v-if="!thumbnailErrors[thumbnailKey(doc)]"
                          :key="thumbnailKey(doc)"
                          :src="thumbnailUrl(doc)"
                          :data-thumbnail-key="thumbnailKey(doc)"
                          alt=""
                          loading="lazy"
                          decoding="async"
                          @load="landing.finishThumbnail(doc.id)"
                          @error="thumbnailErrors[$event.target.dataset.thumbnailKey] = true; landing.finishThumbnail(doc.id)"
                        />
                        <v-icon v-else size="22">mdi-file-document-outline</v-icon>
                      </span>
                      <span class="doc-groups__content">
                        <span class="doc-groups__title">
                          {{ documentTitle(doc) }}
                          <span v-if="doc.is_unread" class="doc-groups__unread" aria-label="Ungelesen" role="img" />
                        </span>
                        <span v-if="documentMetaLabel(doc) || doc.tags?.length" class="doc-groups__meta">
                          <span v-if="documentMetaLabel(doc)" class="doc-groups__type">{{ documentMetaLabel(doc) }}</span>
                          <span v-for="tag in visibleDocumentTags(doc)" :key="tag.id || tag.name" class="doc-groups__tag">{{ tag.name }}</span>
                        </span>
                      </span>
                      <span class="doc-groups__aside">
                        <span class="doc-groups__date">{{ documentDate(doc) }}</span>
                        <v-icon size="16" class="doc-groups__open" aria-hidden="true">mdi-arrow-top-right</v-icon>
                      </span>
                    </button>
                  </li>
                </ul>
                <div v-if="pages[group.key]?.loading" class="doc-groups__loading" role="status">
                  <v-progress-circular indeterminate size="18" width="2" />
                  <span>Dokumente werden geladen …</span>
                </div>
                <div v-else-if="pages[group.key] && !pages[group.key].error && pages[group.key].offset < group.count" class="doc-groups__more">
                  <v-btn variant="text" size="small" @click="loadGroup(group)">Weitere Dokumente laden</v-btn>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { vListReveal } from '../directives/listReveal.js';
import { computed, onBeforeUnmount, reactive, ref, useId, watch } from 'vue';
import { apiGet } from '../api/client.js';
import { documentThumbnailUrl, getDocument } from '../api/documents.js';
import { useDocumentImportLanding } from '../composables/useDocumentImportLanding.js';
import { importLayoutReady } from '../utils/importLanding.js';
import { apiSessionOwner, onApiSessionReset } from '../api/session.js';
import { loadGroupExpansion, saveGroupExpansion } from '../workspaces/documents/groupExpansion.js';
import { documentTypeGroupKey, documentTypeRequestPath, prepareDocumentTypeGroups } from '../workspaces/documents/documentTypeView.js';
import { correspondentInitials, correspondentRequestPath, prepareCorrespondentGroups, visibleDocumentTags } from '../workspaces/documents/correspondentView.js';
import ListActionToolbar from './ListActionToolbar.vue';
import PmEmptyState from './PmEmptyState.vue';

const props = defineProps({
  grouping: { type: String, default: 'correspondents' },
  queryPath: { type: String, required: true },
  refreshKey: { type: Number, default: 0 },
  selectedId: { type: String, default: null },
  selectedDocument: { type: Object, default: null },
  documents: { type: Array, default: () => [] },
  showSuffix: { type: Boolean, default: true },
  currentDateRange: { type: String, default: '' },
  showTypeFilter: { type: Boolean, default: false },
  typeFilterOpen: { type: Boolean, default: false },
  showTagFilter: { type: Boolean, default: false },
  tagFilterOpen: { type: Boolean, default: false },
});
const emit = defineEmits(['select', 'change-date-range', 'filter-toggle']);
const isDocumentTypeGrouping = computed(() => props.grouping === 'document_types');
const groupingLabel = computed(() => isDocumentTypeGrouping.value ? 'Dokumenttypen' : 'Korrespondenten');
const requestPath = (options) => isDocumentTypeGrouping.value
  ? documentTypeRequestPath(props.queryPath, options) : correspondentRequestPath(props.queryPath, options);
const documentMetaLabel = doc => isDocumentTypeGrouping.value
  ? doc.correspondent_name : doc.document_type || doc.category;
const groups = ref([]);
const root = ref(null);
const scroller = ref(null);
const landing = useDocumentImportLanding({ root, scroller, thumbnailSelector: '.doc-groups__thumbnail', beforeLocate: revealImportedDocument });
defineExpose(landing);
let expansionOwner = apiSessionOwner();
const expanded = ref(loadGroupExpansion(expansionOwner, undefined, props.grouping));
const pages = reactive({});
const loading = ref(false);
const error = ref('');
const regionPrefix = useId();
const groupRegionId = group => `${regionPrefix}-group-${group.key}`;
const selectedGroupKey = computed(() => {
  const selected = props.selectedDocument?.id === props.selectedId
    ? props.selectedDocument : props.documents.find(doc => doc.id === props.selectedId);
  if (!selected) return null;
  return isDocumentTypeGrouping.value ? documentTypeGroupKey(selected.document_type || selected.category)
    : selected.correspondent_id || 'unassigned';
});
const thumbnailErrors = reactive({});
const thumbnailUrls = new Map();
const thumbnailKey = doc => `${doc.id}:${doc.updated_at || ''}`;
function thumbnailUrl(doc) {
  const cached = thumbnailUrls.get(doc.id);
  if (cached?.version === doc.updated_at) return cached.url;
  const url = documentThumbnailUrl(doc.id);
  thumbnailUrls.set(doc.id, { version: doc.updated_at, url });
  return url;
}
const dateOptions = [
  { value: '', label: 'Alle Zeiträume' },
  { value: 'this_year', label: 'Dieses Jahr' },
  { value: 'last_year', label: 'Letztes Jahr' },
  { value: 'last_30_days', label: 'Letzte 30 Tage' },
  { value: 'last_12_months', label: 'Letzte 12 Monate' },
];
const dateActions = computed(() => [{
  key: 'dateRange', icon: 'mdi-calendar-range', value: props.currentDateRange,
  label: /^year:\d{4}$/.test(props.currentDateRange) ? props.currentDateRange.slice(5)
    : /^until:\d{4}$/.test(props.currentDateRange) ? `bis ${props.currentDateRange.slice(6)}`
      : dateOptions.find(option => option.value === props.currentDateRange)?.label || 'Zeitraum',
  active: Boolean(props.currentDateRange), collapsible: !props.currentDateRange,
  options: dateOptions, minWidth: 180,
}]);
const filterToggles = computed(() => [
  ...(props.showTypeFilter ? [{ key: 'documentTypeFilter', icon: 'mdi-file-document-outline', label: 'Typen', collapsible: true,
    ariaLabel: props.typeFilterOpen ? 'Dokumenttyp-Filter ausblenden' : 'Dokumenttyp-Filter einblenden', active: props.typeFilterOpen }] : []),
  ...(props.showTagFilter ? [{ key: 'tagFilter', icon: 'mdi-tag-multiple-outline', label: 'Tags', collapsible: true,
    ariaLabel: props.tagFilterOpen ? 'Tag-Filter ausblenden' : 'Tag-Filter einblenden', active: props.tagFilterOpen }] : []),
]);
let generation = 0;
let controller = new AbortController();
let currentQueryPath = '';
let groupRefreshPromise = Promise.resolve();

async function refreshGroups() {
  const reset = currentQueryPath !== props.queryPath;
  currentQueryPath = props.queryPath;
  const requestGeneration = ++generation;
  controller.abort();
  controller = new AbortController();
  const signal = controller.signal;
  if (reset) {
    groups.value = [];
    for (const key of Object.keys(pages)) delete pages[key];
  } else {
    for (const page of Object.values(pages)) page.loading = false;
  }
  loading.value = true;
  error.value = '';
  try {
    const payload = await apiGet(requestPath(), { signal });
    if (requestGeneration !== generation) return;
    const rawGroups = isDocumentTypeGrouping.value ? payload?.document_type_groups : payload?.correspondent_groups;
    if (!Array.isArray(rawGroups)) throw new Error('Gruppen fehlen');
    const previousCounts = new Map(groups.value.map(group => [group.key, group.count]));
    groups.value = isDocumentTypeGrouping.value ? prepareDocumentTypeGroups(rawGroups) : prepareCorrespondentGroups(rawGroups);
    const keys = new Set(groups.value.map(group => group.key));
    for (const key of Object.keys(pages)) {
      if (!keys.has(key)) delete pages[key];
    }
    const groupLoads = [];
    for (const group of groups.value) {
      if (previousCounts.get(group.key) !== group.count) delete pages[group.key];
      if (expanded.value.has(group.key) && (!pages[group.key] || !pages[group.key].offset)) groupLoads.push(loadGroup(group));
    }
    await Promise.all(groupLoads);
  } catch (cause) {
    if (requestGeneration === generation && !signal.aborted) error.value = `${groupingLabel.value} konnten nicht geladen werden.`;
  } finally {
    if (requestGeneration === generation) loading.value = false;
  }
}

async function loadGroup(group) {
  let page = pages[group.key];
  if (page?.loading || (page && !page.error && page.offset >= group.count)) return;
  if (!page) {
    pages[group.key] = { items: [], offset: 0, loading: false, error: '' };
    page = pages[group.key];
  }
  const requestGeneration = generation;
  const signal = controller.signal;
  page.loading = true;
  page.error = '';
  try {
    const payload = await apiGet(requestPath({ group, offset: page.offset }), { signal });
    if (requestGeneration !== generation) return;
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const existing = new Set(page.items.map(doc => doc.id));
    page.items.push(...items.filter(doc => !existing.has(doc.id)));
    page.offset += items.length;
    if (!items.length && page.offset < group.count) {
      page.error = 'Die Auswahl hat sich geändert. Bitte lade die Gruppe erneut.';
    }
    reconcileDocuments();
  } catch (cause) {
    if (requestGeneration === generation && !signal.aborted) page.error = 'Dokumente konnten nicht geladen werden.';
  } finally {
    if (requestGeneration === generation) page.loading = false;
  }
}

function toggleGroup(group) {
  const next = new Set(expanded.value);
  if (next.has(group.key)) next.delete(group.key);
  else {
    next.add(group.key);
    if (!pages[group.key]?.offset || pages[group.key]?.error) void loadGroup(group);
  }
  expanded.value = next;
}

async function retryGroup(group) {
  delete pages[group.key];
  await refreshGroups();
}

function reconcileDocuments() {
  const known = new Map(props.documents.map(doc => [doc.id, doc]));
  if (props.selectedDocument?.id) known.set(props.selectedDocument.id, props.selectedDocument);
  for (const page of Object.values(pages)) {
    page.items = page.items.map(doc => known.has(doc.id) ? { ...doc, ...known.get(doc.id) } : doc);
  }
}

async function revealImportedDocument(id) {
  await groupRefreshPromise;
  const requestGeneration = generation;
  let doc = props.documents.find(item => item.id === id)
    || Object.values(pages).flatMap(page => page.items).find(item => item.id === id);
  if (!doc) {
    try { doc = await getDocument(id); } catch { return; }
  }
  if (requestGeneration !== generation) return;
  const key = isDocumentTypeGrouping.value ? documentTypeGroupKey(doc.document_type || doc.category)
    : doc.correspondent_id || 'unassigned';
  const group = groups.value.find(entry => entry.key === key);
  if (!group) return;
  // Nur die passende Gruppe laden. Bei sehr großen oder gefilterten Gruppen
  // übernimmt nach höchstens drei Seiten das Sidebar-Ziel die Rückmeldung.
  for (let attempt = 0; attempt < 3; attempt++) {
    if (pages[key]?.items.some(item => item.id === id)) break;
    await loadGroup(group);
    if (requestGeneration !== generation || pages[key]?.error) return;
    if (pages[key]?.offset >= group.count) break;
  }
  if (!pages[key]?.items.some(item => item.id === id)) return;
  expanded.value = new Set([...expanded.value, key]);
  await importLayoutReady();
  const section = Array.from(root.value?.querySelectorAll('[data-group-key]') || [])
    .find(element => element.dataset.groupKey === key);
  const reveal = section?.querySelector('.doc-groups__reveal');
  // Erst nach dem Aufklappen messen, damit sich das Ziel im Flug nicht bewegt.
  await Promise.all((reveal?.getAnimations() || []).map(animation => animation.finished.catch(() => {})));
}

function documentTitle(doc) {
  const title = String(doc.display_name || doc.original_filename || '').trim() || 'Ohne Titel';
  return props.showSuffix ? title : title.replace(/\.[A-Za-z][A-Za-z0-9]{0,7}$/, '');
}
const dateFormatter = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
function documentDate(doc) {
  if (!doc.document_date) return '—';
  const value = String(doc.document_date);
  const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value);
  return Number.isNaN(parsed.getTime()) ? '—' : dateFormatter.format(parsed);
}

// Hidden groups retain their preference when a search or filter narrows the list.
watch(expanded, next => saveGroupExpansion(expansionOwner, next, undefined, props.grouping), { flush: 'sync' });
const stopSessionReset = onApiSessionReset(() => {
  generation += 1;
  controller.abort();
  currentQueryPath = '';
  groups.value = [];
  for (const key of Object.keys(pages)) delete pages[key];
  for (const key of Object.keys(thumbnailErrors)) delete thumbnailErrors[key];
  thumbnailUrls.clear();
  loading.value = false;
  error.value = '';
  expansionOwner = apiSessionOwner();
  expanded.value = loadGroupExpansion(expansionOwner, undefined, props.grouping);
});
watch(() => [props.queryPath, props.refreshKey], () => {
  groupRefreshPromise = refreshGroups();
}, { immediate: true });
watch(() => [props.documents, props.selectedDocument], reconcileDocuments, { deep: true });
watch(() => props.selectedDocument && [
  props.selectedDocument.id, props.selectedDocument.updated_at, props.selectedDocument.correspondent_id,
  props.selectedDocument.document_type, props.selectedDocument.document_date, props.selectedDocument.is_unread,
  props.selectedDocument.is_deleted,
].join('|'), (next, previous) => {
  if (!next || !previous || next.split('|')[0] !== previous.split('|')[0]) return;
  const before = previous.split('|');
  const after = next.split('|');
  // Reading a document or refreshing its processing status must keep loaded pages.
  // Changes to grouping, date order or classification invalidate the affected page.
  if ([2, 3, 4, 6].some(index => before[index] !== after[index])) {
    for (const [key, page] of Object.entries(pages)) {
      if (page.items.some(doc => doc.id === props.selectedId)) delete pages[key];
    }
  }
  void refreshGroups();
});
watch(() => props.selectedId, id => {
  if (!id) return;
  const group = groups.value.find(entry => pages[entry.key]?.items.some(doc => doc.id === id));
  if (group) expanded.value = new Set([...expanded.value, group.key]);
});
onBeforeUnmount(() => { generation += 1; controller.abort(); stopSessionReset(); });
</script>

<style scoped>
.doc-groups {
  display: flex; flex-direction: column; min-height: 0;
  background: var(--pm-content-surface); container: documents-list / inline-size;
}
.doc-groups__scroll {
  flex: 1; min-height: 0; overflow: auto;
  background: color-mix(in srgb, var(--pm-text) 2.5%, var(--pm-content-surface));
}
.doc-groups__body { display: flex; flex-direction: column; gap: 12px; padding: 22px 18px 28px; }
.doc-groups__group {
  flex: none; min-width: 0; border-radius: 16px;
  background: var(--pm-list-card); box-shadow: var(--pm-list-card-shadow);
  transition: box-shadow var(--pm-duration-slow, 340ms) var(--pm-easing, ease);
}
.doc-groups__group:hover { box-shadow: inset 0 0 0 1px var(--pm-list-hover-ring), 0 3px 8px color-mix(in srgb, var(--pm-text) 5%, transparent); }
.doc-groups__group--active, .doc-groups__group--active:hover { box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--pm-accent) 60%, transparent), 0 3px 8px color-mix(in srgb, var(--pm-text) 5%, transparent); }
.doc-groups__heading {
  display: grid; grid-template-columns: 54px minmax(0, 1fr) auto 26px;
  align-items: center; gap: 14px; width: 100%; min-height: 96px;
  padding: 18px; border: 0; border-radius: 16px;
  background: transparent; color: var(--pm-text); text-align: left; cursor: pointer;
  transition: background-color 140ms ease;
}
.doc-groups__heading:hover { background: var(--pm-list-hover); }
.doc-groups__group--expanded > .doc-groups__heading {
  background: color-mix(in srgb, var(--pm-accent) 5.5%, transparent);
  border-radius: 16px 16px 0 0;
}
.doc-groups__heading:focus-visible, .doc-groups__document:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -3px; }
.doc-groups__initials {
  display: grid; place-items: center; width: 54px; height: 54px; border-radius: 15px;
  color: var(--pm-content-surface); background: var(--pm-text);
  font-size: 15px; font-weight: 650; letter-spacing: -0.035em;
  transition: background-color var(--pm-duration-slow, 340ms) var(--pm-easing, ease), color var(--pm-duration-slow, 340ms) var(--pm-easing, ease);
}
.doc-groups__group--active .doc-groups__initials { color: var(--pm-accent-contrast, var(--pm-content-surface)); background: var(--pm-accent); }
.doc-groups__group--unassigned .doc-groups__initials { color: var(--pm-list-meta); background: var(--pm-list-chip-bg); }
.doc-groups__identity { display: flex; flex-direction: column; min-width: 0; gap: 5px; }
.doc-groups__name { display: block; font-size: 17px; font-weight: 650; line-height: 1.3; letter-spacing: -0.018em; overflow-wrap: anywhere; }
.doc-groups__full-name { display: block; min-width: 0; color: var(--pm-list-meta); font-size: 12px; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-groups__kind { display: inline-flex; align-items: center; gap: 5px; color: var(--pm-list-meta); font-size: 12px; line-height: 1.4; }
.doc-groups__count { display: inline-flex; align-items: baseline; gap: 4px; color: var(--pm-list-meta); white-space: nowrap; font-variant-numeric: tabular-nums; }
.doc-groups__count-value { font-size: 13px; font-weight: 500; line-height: 1.4; }
.doc-groups__count-word { font-size: 12px; line-height: 1.4; }
.doc-groups__chevron { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--pm-list-hover); color: var(--pm-list-meta); }
.doc-groups__chevron :deep(.v-icon) { transition: transform var(--pm-duration-normal, 240ms) var(--pm-easing, cubic-bezier(0.22, 1, 0.36, 1)); }
.doc-groups__group--expanded .doc-groups__chevron :deep(.v-icon) { transform: rotate(90deg); }
.doc-groups__reveal {
  display: grid; grid-template-rows: 0fr; opacity: 0; visibility: hidden;
  pointer-events: none;
  transition:
    grid-template-rows var(--pm-duration-normal, 240ms) var(--pm-easing, cubic-bezier(0.22, 1, 0.36, 1)),
    opacity var(--pm-duration-fast, 160ms) ease,
    visibility 0s var(--pm-duration-normal, 240ms);
}
.doc-groups__group--expanded .doc-groups__reveal {
  grid-template-rows: 1fr; opacity: 1; visibility: visible; pointer-events: auto;
  transition-delay: 0s;
}
.doc-groups__clip { min-height: 0; overflow: hidden; }
.doc-groups__documents { margin: 0 12px; padding: 8px 0 10px; }
.doc-groups__list { margin: 0; padding: 0; list-style: none; }
.doc-groups__list > li + li { margin-top: 3px; }
.doc-groups__document { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 82px; padding: 11px 10px; border: 0; border-radius: 10px; background: transparent; color: var(--pm-text); text-align: left; cursor: pointer; transition: background-color var(--pm-duration-slow, 340ms) var(--pm-easing, ease); }
.doc-groups__document:hover { background: var(--pm-list-hover); }
.doc-groups__document--active, .doc-groups__document--active:hover { background: var(--pm-list-selected); }
.doc-groups__thumbnail { display: grid; place-items: center; flex: none; width: 40px; height: 54px; overflow: hidden; border-radius: 6px; color: var(--pm-list-meta); background: var(--pm-list-chip-bg); box-shadow: inset 0 0 0 1px var(--pm-list-card-ring); }
.doc-groups__thumbnail img { width: 100%; height: 100%; object-fit: contain; }
.doc-groups__content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 7px; }
.doc-groups__title { display: block; font-size: 14px; font-weight: 500; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-groups__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 5px 8px; font-size: 11px; line-height: 1.4; color: var(--pm-list-meta); }
.doc-groups__type { max-width: 100%; padding: 2px 6px; border-radius: 5px; background: var(--pm-list-chip-bg); color: var(--pm-list-chip-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-groups__tag { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-groups__aside { flex: none; display: flex; align-items: flex-end; flex-direction: column; gap: 12px; }
.doc-groups__date { font-size: 11px; color: var(--pm-list-date); white-space: nowrap; font-variant-numeric: tabular-nums; }
.doc-groups__open { color: var(--pm-list-meta); opacity: 0.45; transition: color var(--pm-duration-slow, 340ms) var(--pm-easing, ease), opacity var(--pm-duration-slow, 340ms) var(--pm-easing, ease); }
.doc-groups__document:hover .doc-groups__open, .doc-groups__document--active .doc-groups__open { color: var(--pm-accent); opacity: 1; }
.doc-groups__unread { display: inline-block; width: 6px; height: 6px; margin-left: 5px; border-radius: 50%; background: var(--pm-accent); vertical-align: middle; }
.doc-groups__loading, .doc-groups__message { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 18px 10px; color: var(--pm-list-meta); font-size: 13px; }
.doc-groups__scroll > .doc-groups__loading, .doc-groups__scroll > .doc-groups__message { padding: 24px; }
.doc-groups__more { display: flex; justify-content: center; padding: 9px 0 0; }
@container documents-list (max-width: 430px) {
  .doc-groups__body { padding: 18px 10px 24px; gap: 10px; }
  .doc-groups__heading { grid-template-columns: 46px minmax(0, 1fr) auto 24px; gap: 10px; padding: 15px 13px; min-height: 86px; }
  .doc-groups__initials { width: 46px; height: 46px; border-radius: 13px; font-size: 13px; }
  .doc-groups__name { font-size: 15px; }
  .doc-groups__count-word { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  .doc-groups__chevron { width: 24px; height: 24px; }
  .doc-groups__documents { margin: 0 9px; }
  .doc-groups__document { display: grid; grid-template-columns: 32px minmax(0, 1fr); align-items: center; gap: 6px 10px; padding: 11px 7px; }
  .doc-groups__thumbnail { width: 32px; height: 44px; grid-row: 1 / 3; }
  .doc-groups__aside { grid-column: 2; flex-direction: row; align-items: center; justify-content: space-between; gap: 10px; }
  .doc-groups__content { min-width: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .doc-groups__group, .doc-groups__heading, .doc-groups__document, .doc-groups__initials, .doc-groups__open,
  .doc-groups__reveal, .doc-groups__chevron :deep(.v-icon) { transition: none; }
}
</style>
