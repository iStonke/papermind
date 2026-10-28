<template>
  <DocumentSectionCard class="related-documents" title="Ähnliche Dokumente" icon="mdi-file-document-outline"
    :count="items.length" :loading="loading" loading-label="Ähnliche Dokumente werden gesucht …"
    :empty="!inTrash && !error && !items.length" empty-icon="mdi-file-document-outline"
    empty-title="Keine ähnlichen Dokumente gefunden"
    empty-description="Gemeinsame Tags und Korrespondenten verbinden Dokumente miteinander.">
    <p v-if="inTrash" class="related-documents__state">Für Dokumente im Papierkorb werden keine Vorschläge angezeigt.</p>
    <div v-else-if="error" class="related-documents__state" role="status">
      <span>Ähnliche Dokumente konnten nicht geladen werden.</span>
      <button type="button" class="related-documents__retry" @click="load(true)">Erneut versuchen</button>
    </div>
    <ul v-else class="related-documents__list">
      <li v-for="item in items" :key="item.id">
        <button type="button" class="related-documents__item" :title="item.title" @click="emit('open-document', item.id)">
          <span class="related-documents__icon" aria-hidden="true"><v-icon size="20">mdi-file-document-outline</v-icon></span>
          <span class="related-documents__copy">
            <span class="related-documents__title">{{ item.title }}</span>
            <span class="related-documents__reasons">
              <span v-if="item.same_correspondent">Gleicher Korrespondent</span>
              <span v-if="item.same_type">Gleicher Dokumenttyp</span>
              <span v-if="item.shared_tag_count" :title="item.shared_tags.join(', ')">
                {{ item.shared_tag_count === 1 ? '1 gemeinsames Tag' : `${item.shared_tag_count} gemeinsame Tags` }}
              </span>
            </span>
          </span>
          <time v-if="item.document_date" class="related-documents__date" :datetime="item.document_date">{{ formatDate(item.document_date) }}</time>
          <v-icon class="related-documents__arrow" size="17" aria-hidden="true">mdi-chevron-right</v-icon>
        </button>
      </li>
    </ul>
  </DocumentSectionCard>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import DocumentSectionCard from './DocumentSectionCard.vue';
import { getRelatedDocuments } from '../api/documents.js';
const props = defineProps({ documentId: String, matchKey: { type: String, default: '' }, enabled: Boolean, inTrash: Boolean });
const emit = defineEmits(['open-document']);
const items = ref([]), loading = ref(false), error = ref(false);
let revision = 0, loadedKey = '', requestedKey = '';
function key() { return `${props.documentId || ''}|${props.matchKey}`; }
async function load(force = false) {
  if (!props.enabled || !props.documentId || props.inTrash) return;
  const currentKey = key();
  if (!force && loadedKey === currentKey) return;
  const request = ++revision;
  requestedKey = currentKey;
  loading.value = true;
  error.value = false;
  try {
    const result = await getRelatedDocuments(props.documentId);
    if (request !== revision || currentKey !== key()) return;
    items.value = result.items || [];
    loadedKey = currentKey;
  } catch {
    if (request === revision) { items.value = []; error.value = true; }
  } finally {
    if (request === revision) loading.value = false;
  }
}
watch(() => [props.documentId, props.matchKey, props.enabled, props.inTrash], () => {
  revision++;
  loading.value = false;
  if (requestedKey !== key() || props.inTrash) {
    items.value = []; loadedKey = ''; error.value = false;
  }
  if (props.enabled) void load();
}, { immediate: true });
onBeforeUnmount(() => { revision++; });
function formatDate(value) { return String(value).slice(0, 10).split('-').reverse().join('.'); }
</script>
<style scoped>
.related-documents__state { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 18px 0; font-size: 13px; color: var(--pm-muted); }
.related-documents__retry { color: var(--pm-accent); font: inherit; font-weight: 600; }
.related-documents__list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.related-documents__item { width: 100%; display: grid; grid-template-columns: 34px minmax(0, 1fr) auto 17px; align-items: center; gap: 12px; padding: 13px 14px; text-align: left; color: var(--pm-text); background: var(--pm-app-surface); border: 1px solid color-mix(in srgb, var(--pm-muted) 32%, var(--pm-divider)); border-radius: 10px; cursor: pointer; transition: background-color 160ms ease, border-color 160ms ease; }
.related-documents__item:hover { background: color-mix(in srgb, var(--pm-accent) 7%, var(--pm-app-surface)); border-color: color-mix(in srgb, var(--pm-accent) 35%, var(--pm-divider)); }
.related-documents__icon { display: grid; place-items: center; width: 34px; height: 40px; border-radius: 6px; background: color-mix(in srgb, var(--pm-accent) 8%, transparent); color: var(--pm-accent); }
.related-documents__copy { min-width: 0; display: grid; gap: 6px; }
.related-documents__title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.related-documents__reasons { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 11px; color: var(--pm-muted); }
.related-documents__date { font-size: 11px; color: var(--pm-muted); white-space: nowrap; }
.related-documents__arrow { color: var(--pm-muted); }
@container (max-width: 520px) { .related-documents__item { grid-template-columns: 28px minmax(0, 1fr) 17px; gap: 10px; padding-inline: 10px; } .related-documents__date { display: none; } .related-documents__icon { width: 28px; height: 36px; } }
:global(.pm-no-animations .related-documents__item) { transition: none; }
@media (prefers-reduced-motion: reduce) { .related-documents__item { transition: none; } }
</style>
