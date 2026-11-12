<template>
  <BaseDialog
    :model-value="modelValue"
    title="Zusammenführen"
    :header-subtitle="correspondentDisplayName(correspondent)"
    icon="mdi-source-merge"
    variant="destructive"
    primary-text="Zusammenführen"
    :primary-disabled="!other || !target || busy"
    :loading="busy"
    :persistent="busy"
    max-width="520"
    card-class="corr-merge-dialog"
    @update:model-value="close"
    @primary="submit"
  >
    <div class="corr-merge">
      <v-autocomplete
        ref="otherRef"
        v-model="otherId"
        :items="options"
        item-title="name"
        item-value="id"
        :custom-filter="correspondentFilter"
        label="Zusammenführen mit"
        density="comfortable"
        variant="outlined"
        hide-details
        auto-select-first
        no-data-text="Keine passenden Einträge"
        :disabled="busy"
      >
        <template #item="{ props: itemProps, item }">
          <v-list-item v-bind="itemProps" :subtitle="optionMeta(item.raw)">
            <template #prepend>
              <v-icon size="18" aria-hidden="true">{{ kindIcon(item.raw.kind) }}</v-icon>
            </template>
          </v-list-item>
        </template>
      </v-autocomplete>

      <template v-if="other">
        <div class="corr-merge__keep">
          <span id="corr-merge-keep-label" class="corr-merge__label">Bleibt erhalten</span>
          <div class="corr-merge__segment" role="radiogroup" aria-labelledby="corr-merge-keep-label">
            <button
              v-for="entry in pair"
              :key="entry.id"
              type="button"
              role="radio"
              class="corr-merge__option"
              :class="{ 'is-active': keepId === entry.id }"
              :aria-checked="keepId === entry.id"
              :disabled="busy"
              @click="keepId = entry.id"
            >
              <span class="corr-merge__option-name" :title="entry.name">{{ correspondentDisplayName(entry) }}</span>
              <span class="corr-merge__option-meta">{{ documentsLabel(entry) }}</span>
            </button>
          </div>
        </div>

        <ul class="corr-merge__summary" aria-label="Was passiert">
          <li v-for="line in summary" :key="line">{{ line }}</li>
        </ul>
        <p class="corr-merge__warning">„{{ correspondentDisplayName(source) }}“ wird danach gelöscht. Das lässt sich nicht rückgängig machen.</p>
      </template>
      <p v-if="error" class="corr-merge__error" role="alert">{{ error }}</p>
    </div>
  </BaseDialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import BaseDialog from './BaseDialog.vue';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { correspondentDisplayName, correspondentKindIcon, correspondentKindLabel } from '../utils/correspondentHierarchy.js';
import { canMergeCorrespondents, findDuplicateCandidates, preferredMergeTarget } from '../utils/correspondentDuplicates.js';
import { mapApiError } from '../stores/notifications.js';
import { useSettingsStore } from '../stores/settings.js';
import { createCorrespondentItemFilter } from '../utils/correspondentFilter.js';

const props = defineProps({
  modelValue: Boolean,
  correspondent: { type: Object, default: null },
  initialOtherId: { type: String, default: null },
});
const emit = defineEmits(['update:modelValue', 'merged']);
const store = useCorrespondentStore();
const settingsStore = useSettingsStore();
const correspondentFilter = createCorrespondentItemFilter(() => settingsStore.settings?.ui?.correspondent_search_aliases !== false);

const otherRef = ref(null);
const otherId = ref(null);
const keepId = ref(null);
const busy = ref(false);
const error = ref('');

const other = computed(() => store.findById(otherId.value));
const pair = computed(() => (other.value ? [props.correspondent, other.value] : []));
const target = computed(() => pair.value.find(entry => entry.id === keepId.value) || null);
const source = computed(() => pair.value.find(entry => entry.id !== keepId.value) || null);

// Wahrscheinliche Doppel zuerst, danach alle übrigen passenden Einträge.
const options = computed(() => {
  if (!props.correspondent) return [];
  const duplicates = findDuplicateCandidates(store.correspondents, props.correspondent).map(match => match.correspondent);
  const duplicateIds = new Set(duplicates.map(entry => entry.id));
  const rest = store.correspondents
    .filter(entry => !duplicateIds.has(entry.id) && canMergeCorrespondents(entry, props.correspondent))
    .sort((a, b) => a.name.localeCompare(b.name, 'de-DE'));
  return [...duplicates, ...rest];
});

watch(() => props.modelValue, async open => {
  if (!open) return;
  error.value = '';
  otherId.value = props.initialOtherId || null;
  keepId.value = null;
  await nextTick();
  if (!otherId.value) otherRef.value?.focus?.();
}, { immediate: true });

watch(other, entry => {
  keepId.value = entry ? preferredMergeTarget(props.correspondent, entry).id : null;
}, { immediate: true });

const count = (n, one, many) => (n === 1 ? `1 ${one}` : `${n} ${many}`);
function documentsLabel(entry) {
  return count(Number(entry?.usage_count || 0), 'Dokument', 'Dokumente');
}
function kindIcon(kind) {
  return correspondentKindIcon(kind) || 'mdi-help-circle-outline';
}
function optionMeta(entry) {
  return [entry.kind ? correspondentKindLabel(entry.kind) : 'Ohne Typ', documentsLabel(entry)].join(' · ');
}

const summary = computed(() => {
  const from = source.value;
  const into = target.value;
  if (!from || !into) return [];
  const documents = Number(from.usage_count || 0);
  const aliases = (from.aliases || []).length;
  const members = store.membersOf(from.id).length;
  return [
    documents
      ? `${count(documents, 'Dokument', 'Dokumente')} von „${correspondentDisplayName(from)}“ ${documents === 1 ? 'wird' : 'werden'} „${correspondentDisplayName(into)}“ zugeordnet.`
      : `„${correspondentDisplayName(from)}“ hat keine Dokumente.`,
    `„${from.name}“ wird als Alias gespeichert, damit diese Schreibweise weiter erkannt wird.`,
    aliases ? `${count(aliases, 'weiterer Alias', 'weitere Aliase')} und die Erkennungsregeln werden übernommen.` : '',
    members ? `${count(members, 'zugeordneter Eintrag wechselt', 'zugeordnete Einträge wechseln')} zu „${correspondentDisplayName(into)}“.` : '',
    (from.notes || '').trim() ? `Die Notiz von „${correspondentDisplayName(from)}“ wird angehängt.` : '',
    'Verbindungen und Verweise in Notizen zeigen danach auf den verbleibenden Eintrag.',
  ].filter(Boolean);
});

function close(open = false) {
  if (busy.value) return;
  emit('update:modelValue', open);
}

async function submit() {
  if (!target.value || !source.value || busy.value) return;
  busy.value = true;
  error.value = '';
  const targetId = target.value.id;
  try {
    await store.mergeCorrespondents(targetId, source.value.id);
    emit('merged', targetId);
    emit('update:modelValue', false);
  } catch (err) {
    error.value = mapApiError(err, 'Die Einträge konnten nicht zusammengeführt werden.');
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.corr-merge { display: flex; flex-direction: column; gap: 16px; }
.corr-merge__keep { display: flex; flex-direction: column; gap: 6px; }
.corr-merge__label { color: rgb(var(--v-theme-on-surface-variant)); font-size: 12px; }
.corr-merge__segment {
  display: grid;
  grid-template-columns: 1fr 1fr;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), .16);
  border-radius: 8px;
}
.corr-merge__option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  min-height: 48px;
  padding: 8px 12px;
  border: 0;
  background: transparent;
  color: rgb(var(--v-theme-on-surface));
  font: inherit;
  text-align: start;
  cursor: pointer;
  transition: background-color 160ms ease;
}
.corr-merge__option + .corr-merge__option { border-inline-start: 1px solid rgba(var(--v-theme-on-surface), .16); }
.corr-merge__option.is-active { background: rgba(var(--v-theme-primary), .12); }
.corr-merge__option:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -2px; }
.corr-merge__option:disabled { cursor: default; opacity: .6; }
.corr-merge__option-name { max-width: 100%; overflow: hidden; font-size: 14px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.corr-merge__option.is-active .corr-merge__option-name { color: rgb(var(--v-theme-primary)); }
.corr-merge__option-meta { color: rgb(var(--v-theme-on-surface-variant)); font-size: 12px; }
.corr-merge__summary { display: flex; flex-direction: column; gap: 6px; margin: 0; padding-inline-start: 18px; font-size: 13px; line-height: 1.4; }
.corr-merge__warning { margin: 0; color: rgb(var(--v-theme-error)); font-size: 13px; }
.corr-merge__error { margin: 0; color: rgb(var(--v-theme-error)); font-size: 13px; }
:global(.pm-no-animations .corr-merge__option) { transition: none; }
@media (max-width: 420px) {
  .corr-merge__segment { grid-template-columns: 1fr; }
  .corr-merge__option + .corr-merge__option { border-inline-start: 0; border-block-start: 1px solid rgba(var(--v-theme-on-surface), .16); }
}
</style>
