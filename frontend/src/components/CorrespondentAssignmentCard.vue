<!--
  CorrespondentAssignmentCard — eine Karte pro Dokument in „Ohne Korrespondent“
  bzw. „Genauer zuordnen“ (Aufbau wie „Mögliche Doppelte“): Vorschaubild,
  Titel und Angaben, darunter die Zuordnung mit Vorschlag und Knopf.

  Die Karte hält nur ihren Bearbeitungszustand und meldet die gewünschte
  Aktion per `submit`; Speichern und Meldungen übernimmt die Liste
  (UnassignedCorrespondentDocuments).
-->
<template>
  <li
    ref="cardEl"
    class="assign-card"
    :class="{ 'is-pending': isPending, 'is-hidden': hidden }"
    tabindex="-1"
    :data-document-id="item.document_id"
    :aria-label="title"
    @keydown="onKeydown"
  >
    <button
      type="button"
      class="assign-card__thumb"
      :aria-label="`${title} groß anzeigen`"
      :title="`${title} groß anzeigen`"
      @click="emit('open-document', item.document_id)"
    >
      <v-icon size="22" aria-hidden="true">mdi-file-document-outline</v-icon>
      <img
        v-if="!thumbBroken"
        :src="documentThumbnailUrl(item.document_id)"
        alt=""
        loading="lazy"
        decoding="async"
        draggable="false"
        @error="thumbBroken = true"
      >
    </button>

    <div class="assign-card__body">
      <div class="assign-card__head">
        <div class="assign-card__heading">
          <h2 class="assign-card__title" :title="title">{{ title }}</h2>
          <p class="assign-card__meta">
            <span v-if="item.document_type" class="assign-card__meta-part">
              <v-icon size="13" aria-hidden="true">mdi-file-document-outline</v-icon>{{ item.document_type }}
            </span>
            <span v-if="documentDate" class="assign-card__meta-part">{{ documentDate }}</span>
            <span v-if="collectionName" class="assign-card__meta-part assign-card__collection">
              <v-icon size="13" aria-hidden="true">mdi-shape-outline</v-icon>{{ collectionName }}
            </span>
          </p>
        </div>
        <v-btn
          v-if="hidden"
          type="button"
          class="assign-card__restore"
          variant="text"
          size="small"
          prepend-icon="mdi-undo"
          :loading="isPending"
          :disabled="disabled"
          :aria-label="`${title} zurückholen`"
          @click="emit('restore', item.document_id)"
        >Zurückholen</v-btn>
        <v-menu v-else location="bottom end" :offset="4">
          <template #activator="{ props: menuProps }">
            <v-btn
              v-bind="menuProps"
              type="button"
              icon="mdi-dots-horizontal"
              size="small"
              density="comfortable"
              variant="text"
              class="assign-card__more"
              :aria-label="`Weitere Aktionen für ${title}`"
              :disabled="disabled"
            />
          </template>
          <v-list class="pm-menu" density="compact">
            <v-list-item v-if="detectedSender" title="Absender als Alias übernehmen" prepend-icon="mdi-tag-plus" @click="setAction('alias', true)" />
            <v-list-item title="Korrespondent anlegen" prepend-icon="mdi-account-plus" @click="setAction('create', true)" />
            <v-list-item :title="ignoreLabel" :prepend-icon="isCollectionMode ? 'mdi-shape-outline' : 'mdi-close'" @click="submit('ignore')" />
          </v-list>
        </v-menu>
      </div>

      <form v-if="!hidden" class="assign-card__editor" @submit.prevent="submit(submitAction)">
        <v-text-field
          v-if="action === 'create'"
          ref="nameFieldRef"
          v-model="newName"
          label="Name des Korrespondenten"
          maxlength="120"
          :disabled="disabled"
          density="compact"
          variant="outlined"
          hide-details
        />
        <DocumentMetadataFields
          v-else
          :key="action"
          v-model:correspondent="correspondentSelection"
          :field-keys="['correspondent']"
          :correspondents="correspondentOptions"
          :correspondent-autofocus="action === 'alias'"
          :disabled="disabled"
        >
          <template #correspondent-suffix>
            <v-chip
              v-if="showsSuggestion"
              :title="suggestionTitle"
              class="assign-card__suggestion"
              color="primary"
              variant="tonal"
              size="x-small"
              rounded="pill"
            >Vorschlag</v-chip>
          </template>
          <template #after-correspondent>
            <!-- Vor dem Anlegen: ähnliche vorhandene Korrespondenten zum Anklicken. -->
            <div
              v-if="similarExisting.length"
              class="assign-card__similar"
              role="group"
              aria-label="Ähnlich vorhanden:"
            >
              <span class="assign-card__similar-label">Ähnlich vorhanden:</span>
              <button
                v-for="entry in similarExisting"
                :key="entry.id"
                type="button"
                class="assign-card__similar-chip"
                :disabled="disabled"
                :title="entry.name"
                :aria-label="`Vorhandenen Korrespondenten wählen: ${entry.name}`"
                @click="correspondentSelection = entry.id"
              >{{ entry.short_name || entry.name }}</button>
            </div>
            <CorrespondentRefineHint
              :document-id="item.document_id"
              :correspondent-id="correspondentSelection === NEW_SENDER ? null : correspondentSelection"
              :disabled="disabled"
              @apply="correspondentSelection = $event"
            />
          </template>
        </DocumentMetadataFields>
        <div class="assign-card__actions">
          <button v-if="action !== 'assign'" type="button" class="assign-card__link" :disabled="disabled" @click="setAction('assign')">Abbrechen</button>
          <v-btn
            class="assign-card__submit"
            type="submit"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-check"
            :disabled="!canSubmit"
            :loading="isPending && pendingAction !== 'ignore'"
            :title="`${submitLabel} (${shortcutLabel})`"
          >{{ submitLabel }}</v-btn>
        </div>
      </form>
    </div>
  </li>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import DocumentMetadataFields from './DocumentMetadataFields.vue';
import CorrespondentRefineHint from './CorrespondentRefineHint.vue';
import { documentThumbnailUrl } from '../api/documents.js';
import { useSettingsStore } from '../stores/settings.js';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { formatDocumentDateInputFromIso } from '../utils/dates.js';
import { normalizedSender, suggestCorrespondent, suggestionReason } from '../utils/correspondentSuggestion.js';

const NEW_SENDER = 'unassigned:new-sender';
const ACTION_LABELS = {
  assign: 'Zuordnen',
  alias: 'Alias übernehmen und zuordnen',
  create: 'Anlegen und zuordnen',
};

const props = defineProps({
  item: { type: Object, required: true },
  // 'unassigned' = ohne Korrespondent; 'collection' = direkt an einer Sammlung → genauer zuordnen.
  mode: { type: String, default: 'unassigned' },
  disabled: Boolean,
  pendingAction: { type: String, default: '' },
  shortcutLabel: { type: String, default: '⌘↵' },
  /** Sammlungsmodus: im Dokument genanntes Mitglied (lädt die Liste). */
  mentionedMemberId: { type: String, default: null },
  /** Ausgeblendete Fälle: nur Angaben und „Zurückholen“. */
  hidden: Boolean,
});
const emit = defineEmits(['submit', 'open-document', 'restore']);

const store = useCorrespondentStore();
const settingsStore = useSettingsStore();
const showSuggestions = computed(() => settingsStore.settings.ui.correspondent_show_suggestions !== false);

const cardEl = ref(null);
const nameFieldRef = ref(null);
const thumbBroken = ref(false);
const action = ref('assign');
const selectedCorrespondentId = ref();
const newName = ref('');

const isCollectionMode = computed(() => props.mode === 'collection');
const isPending = computed(() => Boolean(props.pendingAction));
const ignoreLabel = computed(() => (isCollectionMode.value ? 'Bei der Sammlung lassen' : 'Bewusst ohne Korrespondent'));
const title = computed(() => props.item.title || props.item.original_filename || 'Ohne Titel');
const documentDate = computed(() => formatDocumentDateInputFromIso(props.item.document_date));
const collectionId = computed(() => (isCollectionMode.value ? props.item.correspondent_id || null : null));
const collectionName = computed(() => (isCollectionMode.value
  ? props.item.correspondent_name || store.findById(collectionId.value)?.name || ''
  : ''));
const detectedSender = computed(() => normalizedSender(props.item));

const suggestedCorrespondent = computed(() => (showSuggestions.value
  ? suggestCorrespondent(props.item, store, { mentionedMemberId: props.mentionedMemberId, collectionMode: isCollectionMode.value })
  : null));
const suggestionTitle = computed(() => suggestionReason(props.item, suggestedCorrespondent.value));
// Ähnliche vorhandene Einträge (Backend), solange nichts Vorhandenes gewählt ist.
const similarExisting = computed(() => {
  if (action.value !== 'assign') return [];
  const selection = correspondentSelection.value;
  if (selection && selection !== NEW_SENDER && selection !== collectionId.value) return [];
  return (props.item.similar || [])
    .map(entry => store.findById(entry.correspondent_id))
    .filter(Boolean);
});
const newSenderOption = computed(() => {
  if (!showSuggestions.value || action.value !== 'assign' || !detectedSender.value || suggestedCorrespondent.value) return null;
  return { title: detectedSender.value, value: NEW_SENDER, props: { subtitle: 'Neuen Korrespondenten anlegen' } };
});
const correspondentOptions = computed(() => (newSenderOption.value
  ? [newSenderOption.value, ...store.correspondentOptions]
  : store.correspondentOptions));
const correspondentSelection = computed({
  get: () => (selectedCorrespondentId.value === undefined
    ? suggestedCorrespondent.value?.id ?? newSenderOption.value?.value ?? collectionId.value ?? null
    : selectedCorrespondentId.value),
  set: (value) => { selectedCorrespondentId.value = value; },
});
const showsSuggestion = computed(() => action.value === 'assign' && Boolean(correspondentSelection.value)
  && correspondentSelection.value === (suggestedCorrespondent.value?.id ?? newSenderOption.value?.value));
const submitAction = computed(() => (correspondentSelection.value === NEW_SENDER ? 'create' : action.value));
const nameToCreate = computed(() => (action.value === 'create' ? newName.value.trim() : detectedSender.value));
const submitLabel = computed(() => ACTION_LABELS[submitAction.value]);
const canSubmit = computed(() => Boolean(!props.disabled
  && (submitAction.value === 'create'
    ? nameToCreate.value.length >= 2 && nameToCreate.value.length <= 120
    // Im Sammlungsmodus nur, wenn es wirklich genauer wird.
    : correspondentSelection.value && correspondentSelection.value !== collectionId.value)));

async function setAction(nextAction, focus = false) {
  action.value = nextAction;
  selectedCorrespondentId.value = nextAction === 'assign' ? undefined : null;
  newName.value = detectedSender.value;
  if (focus && nextAction === 'create') {
    await nextTick();
    nameFieldRef.value?.focus?.();
  }
}

function submit(key) {
  if (props.disabled || props.hidden) return;
  if (key !== 'ignore' && !canSubmit.value) return;
  emit('submit', {
    key,
    item: props.item,
    correspondentId: correspondentSelection.value === NEW_SENDER ? null : correspondentSelection.value,
    name: nameToCreate.value,
    collectionId: collectionId.value,
  });
}

function onKeydown(event) {
  // ⌘/Strg+Enter: Vorschlag bzw. Auswahl dieser Karte übernehmen.
  if (event.key !== 'Enter' || !(event.metaKey || event.ctrlKey) || event.isComposing) return;
  event.preventDefault();
  event.stopPropagation();
  submit(submitAction.value);
}

watch(() => props.item.document_id, () => { void setAction('assign'); }, { immediate: true });

defineExpose({ focus: () => cardEl.value?.focus({ preventScroll: true }), el: cardEl });
</script>

<style scoped>
.assign-card {
  position: relative;
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  align-items: start;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  background: var(--pm-app-surface);
  outline: none;
  transition: border-color 140ms ease, box-shadow 140ms ease;
}
.assign-card:focus-visible,
.assign-card:focus-within { border-color: color-mix(in srgb, var(--pm-text) 22%, transparent); }
.assign-card.is-pending { opacity: 0.7; }
.assign-card.is-hidden { grid-template-columns: 52px minmax(0, 1fr); padding-block: 10px; }
.assign-card.is-hidden .assign-card__thumb { width: 52px; height: 68px; }
.assign-card.is-hidden .assign-card__head { align-items: center; }
.assign-card__restore.v-btn { flex: none; letter-spacing: 0; text-transform: none; }

/* Vorschaubild: das Blatt selbst, ohne Kasten dahinter. Klick öffnet die Vorschau. */
.assign-card__thumb {
  position: relative;
  display: grid;
  place-items: center;
  width: 68px;
  height: 88px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--pm-text) 10%, transparent);
  border-radius: 3px;
  background: #fff;
  box-shadow: 0 1px 3px color-mix(in srgb, #000 14%, transparent);
  color: color-mix(in srgb, #000 30%, #fff);
  cursor: zoom-in;
  overflow: hidden;
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.assign-card__thumb:hover { transform: translateY(-2px); box-shadow: 0 4px 10px color-mix(in srgb, #000 18%, transparent); }
.assign-card__thumb:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.assign-card__thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: top center; }

.assign-card__body { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.assign-card__head { display: flex; align-items: flex-start; gap: 8px; min-width: 0; }
.assign-card__heading { flex: 1; min-width: 0; }
.assign-card__title {
  margin: 0;
  overflow: hidden;
  color: var(--pm-list-title, var(--pm-text));
  font-size: 0.98rem;
  font-weight: 650;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.assign-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 0;
  margin: 3px 0 0;
  color: var(--pm-muted);
  font-size: 0.8rem;
}
.assign-card__meta-part { display: inline-flex; align-items: center; gap: 4px; }
.assign-card__meta-part + .assign-card__meta-part::before {
  content: '·';
  margin: 0 8px;
  color: color-mix(in srgb, var(--pm-muted) 70%, transparent);
}
.assign-card__more { flex: none; margin: -4px -6px 0 0; }

.assign-card__editor { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px 10px; }
.assign-card__editor :deep(.pm-metadata-row) { grid-template-columns: minmax(0, 1fr); grid-template-areas: 'value'; gap: 0; }
.assign-card__editor :deep(.pm-metadata-label) {
  position: absolute;
  inline-size: 1px;
  block-size: 1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.assign-card__actions { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.assign-card__similar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; font-size: 0.8rem; }
.assign-card__similar-label { color: var(--pm-muted); }
.assign-card__similar-chip {
  display: inline-flex;
  align-items: center;
  max-width: 220px;
  min-height: 26px;
  padding: 0 9px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--pm-accent) 55%, transparent);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-accent-text);
  font: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color 140ms ease;
}
.assign-card__similar-chip:hover:not(:disabled) { background: color-mix(in srgb, var(--pm-accent) 8%, transparent); }
.assign-card__similar-chip:disabled { opacity: .5; cursor: default; }
.assign-card__similar-chip:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
@media (pointer: coarse) { .assign-card__similar-chip { min-height: 44px; } }
.assign-card__suggestion.v-chip { flex-shrink: 0; margin-inline: 6px; font-weight: 400; letter-spacing: 0; }
.assign-card__submit.v-btn {
  max-width: 100%;
  height: auto;
  min-height: 36px;
  padding-block: 6px;
  border-radius: 8px;
  text-transform: none;
  letter-spacing: 0;
}
.assign-card__submit :deep(.v-btn__content) { white-space: normal; }
.assign-card__link {
  min-height: 32px;
  padding: 0 4px;
  border: 0;
  background: transparent;
  color: var(--pm-accent-text);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.assign-card__link:hover:not(:disabled) { text-decoration: underline; }
.assign-card__link:disabled { opacity: .55; cursor: default; }
.assign-card__link:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }

@container (max-width: 560px) {
  .assign-card { grid-template-columns: 52px minmax(0, 1fr); gap: 10px; }
  .assign-card__thumb { width: 52px; height: 68px; }
  .assign-card__editor { grid-template-columns: minmax(0, 1fr); }
}
@media (pointer: coarse) {
  .assign-card__link, .assign-card__submit.v-btn { min-height: 44px; }
}
@media (prefers-reduced-motion: reduce) {
  .assign-card, .assign-card__thumb { transition: none; }
}
:global(.pm-no-animations) .assign-card,
:global(.pm-no-animations) .assign-card__thumb { transition: none; }
</style>
