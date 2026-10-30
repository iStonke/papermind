<template>
  <div v-if="!preview" class="related-settings">
    <h3 class="pm-settings-subhead">Ähnliche Dokumente</h3>
    <p class="pm-setting-description">Bestimme, welche Gemeinsamkeiten für dich zählen. Gilt für Detailleiste und Dokumentrückseite.</p>
    <div class="related-settings__profiles" role="group" aria-label="Gewichtungsprofil">
      <button v-for="profile in relatedProfiles" :key="profile.value" type="button" :aria-pressed="preferences.profile === profile.value"
        :disabled="saving" @click="save({ profile: profile.value })">
        <strong>{{ profile.label }}</strong><span>{{ profile.description }}</span>
      </button>
    </div>
    <p v-if="preferences.profile === 'custom'" class="related-settings__hint">Individuelle Gewichtung aktiv</p>
    <details class="related-settings__adjust" :open="preferences.profile === 'custom'">
      <summary>Gewichtung anpassen</summary>
      <div v-for="feature in relatedFeatures" :key="feature.key" class="related-settings__feature">
        <div><strong :id="`related-weight-${feature.key}`">{{ feature.label }}</strong><p>{{ feature.description }}</p></div>
        <div role="group" :aria-labelledby="`related-weight-${feature.key}`" class="related-settings__levels">
          <button v-for="level in levels" :key="level.value" type="button" :disabled="saving"
            :aria-pressed="preferences.weights[feature.key] === level.value" @click="setWeight(feature.key, level.value)">{{ level.label }}</button>
        </div>
      </div>
    </details>
    <p class="related-settings__hint">Die Vorschläge basieren auf Titeln und Metadaten. Dokumentinhalte und Vertragsnummern werden noch nicht ausgewertet.</p>
    <div class="related-settings__footer">
      <v-btn variant="text" size="small" :disabled="saving || preferences.profile === 'balanced'" @click="save({ profile: 'balanced' })">Auf Standard zurücksetzen</v-btn>
      <span v-if="saving" role="status">Wird gespeichert …</span>
    </div>
    <p v-if="saveError" class="related-settings__error" role="alert">{{ saveError }}</p>
  </div>
  <div v-else class="related-settings-preview">
    <h3>Beispielvorschau</h3>
    <p>Wähle ein Dokument und sieh, wie sich die Vorschläge mit deiner Gewichtung verändern.</p>
    <v-autocomplete v-model="selectedId" v-model:search="search" :items="documents" item-title="label" item-value="id"
      label="Beispieldokument" aria-label="Beispieldokument" variant="outlined" density="comfortable" hide-details clearable no-filter
      :loading="searching" no-data-text="Keine Dokumente gefunden" />
    <p v-if="searchError" role="alert" class="related-settings__error">Dokumente konnten nicht geladen werden.
      <button type="button" @click="loadDocuments()">Erneut versuchen</button>
    </p>
    <RelatedDocumentsSection v-if="selectedId" :document-id="selectedId" :preferences="preferences" enabled read-only
      :show-suffix="store.settings.ui.showFilenameSuffix" />
    <p v-else-if="!searching && !searchError" class="related-settings__hint">Wähle ein vorhandenes Dokument, um die Vorschläge zu vergleichen.</p>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useSettingsStore } from '../stores/settings.js';
import { getBaseUrl } from '../api/client.js';
import { listDocuments } from '../api/documents.js';
import { normalizeRelatedPreferences, relatedFeatures, relatedProfiles } from '../utils/relatedPreferences.js';
import RelatedDocumentsSection from './RelatedDocumentsSection.vue';
const props = defineProps({ preview: Boolean });
const store = useSettingsStore();
const preferences = computed(() => normalizeRelatedPreferences(store.settingsDraft.ui.related_documents));
const saving = computed(() => Boolean(store.isSettingSaving.related_documents));
const saveError = ref('');
const levels = [{ value: 'low', label: 'Gering' }, { value: 'normal', label: 'Normal' }, { value: 'high', label: 'Stark' }];
async function save(value) {
  if (saving.value) return;
  const previous = preferences.value;
  const next = normalizeRelatedPreferences(value);
  if (JSON.stringify(previous) === JSON.stringify(next)) return;
  saveError.value = '';
  store.setDraftPatch({ ui: { related_documents: next } });
  try {
    await store.saveSettingPatch(getBaseUrl(), { patch: { ui: { related_documents: next } }, controlKey: 'related_documents' });
  } catch {
    store.setDraftPatch({ ui: { related_documents: previous } });
    saveError.value = 'Die Gewichtung konnte nicht gespeichert werden. Die bisherige Einstellung wurde wiederhergestellt. Bitte erneut versuchen.';
  }
}
function setWeight(key, value) { void save({ profile: 'custom', weights: { ...preferences.value.weights, [key]: value } }); }
const documents = ref([]), selectedId = ref(null), search = ref(''), searching = ref(false), searchError = ref(false);
let searchTimer, requestId = 0;
async function loadDocuments(selectFirst = false) {
  const revision = ++requestId;
  searching.value = true; searchError.value = false;
  const query = new URLSearchParams({ limit: '20', offset: '0', search_scope: 'title' });
  if (search.value.trim()) query.set('q', search.value.trim());
  try {
    const result = await listDocuments(query.toString());
    if (revision !== requestId) return;
    const selected = documents.value.find(item => item.id === selectedId.value);
    const options = (result.items || []).filter(item => !item.is_deleted).map(item => {
      const title = String(item.display_name || item.original_filename || 'Unbenanntes Dokument').trim();
      return { id: item.id, label: store.settings.ui.showFilenameSuffix ? title : title.replace(/\.[A-Za-z][A-Za-z0-9]{0,7}$/, '') };
    });
    if (selected && !options.some(item => item.id === selected.id)) options.unshift(selected);
    documents.value = options;
    if (selectFirst && !selectedId.value) selectedId.value = options[0]?.id || null;
  } catch { if (revision === requestId) searchError.value = true; }
  finally { if (revision === requestId) searching.value = false; }
}
watch(search, value => {
  if (!props.preview || value === documents.value.find(item => item.id === selectedId.value)?.label) return;
  clearTimeout(searchTimer);
  requestId++; // Invalidate a previous search while the next one is debounced.
  searchTimer = setTimeout(() => { void loadDocuments(); }, 250);
});
onMounted(() => { if (props.preview) void loadDocuments(true); });
onBeforeUnmount(() => { requestId++; clearTimeout(searchTimer); });
</script>
<style scoped>
.related-settings { border-top:1px solid var(--pm-divider); margin-top:22px; padding-top:18px; }
.related-settings__profiles { display:grid; gap:8px; margin:16px 0; }
.related-settings__profiles button { display:grid; gap:5px; padding:12px 14px; text-align:left; background:var(--pm-app-surface); border:1px solid var(--pm-divider); border-radius:12px; color:var(--pm-text); }
.related-settings__profiles button span { color:var(--pm-muted); font-size:12px; line-height:1.5; }
.related-settings__profiles button[aria-pressed="true"], .related-settings__levels button[aria-pressed="true"] { border-color:var(--pm-accent); background:color-mix(in srgb, var(--pm-accent) 10%, var(--pm-app-surface)); }
.related-settings button:focus-visible, .related-settings summary:focus-visible { outline:2px solid var(--pm-accent); outline-offset:3px; }
.related-settings button:disabled { opacity:.65; cursor:wait; }
.related-settings__adjust { border:1px solid var(--pm-divider); border-radius:12px; padding:12px 14px; }
.related-settings__adjust summary { cursor:pointer; font-weight:600; }
.related-settings__feature { display:grid; gap:10px; padding:16px 0; border-bottom:1px solid var(--pm-divider); }
.related-settings__feature:last-child { border-bottom:0; padding-bottom:2px; }
.related-settings__feature strong { font-size:13px; }
.related-settings__feature p, .related-settings__hint { font-size:12px; color:var(--pm-muted); line-height:1.55; margin:5px 0 0; }
.related-settings__hint { margin:12px 0; }
.related-settings__levels { display:flex; gap:4px; }
.related-settings__levels button { flex:1; padding:6px 8px; border:1px solid var(--pm-divider); border-radius:100px; color:var(--pm-text); font-size:12px; }
.related-settings__footer { display:flex; align-items:center; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--pm-muted); }
.related-settings__error { color:rgb(var(--v-theme-error)); font-size:12px; line-height:1.5; margin-top:12px; }
.related-settings__error button { text-decoration:underline; }
.related-settings-preview { container-type:inline-size; min-width:0; }
.related-settings-preview > h3 { font-size:15px; margin-bottom:8px; }
.related-settings-preview > p { font-size:12px; line-height:1.6; color:var(--pm-muted); margin-bottom:16px; }
.related-settings-preview :deep(.related-documents) { margin-top:16px; padding:12px; }
.related-settings-preview :deep(.related-documents__item--readonly) { grid-template-columns:28px minmax(0, 1fr); }
.related-settings-preview :deep(.document-section-card__heading) { font-size:14px; }
</style>
