<template>
  <section class="unassigned" aria-label="Dokumente ohne Korrespondenten" :aria-busy="isLoading" @keydown="onShortcut">
    <slot name="back" />
    <div v-if="loadError" class="unassigned-state" role="alert">
      Offene Zuordnungen konnten nicht geladen werden.
      <button type="button" class="unassigned-link" @click="emit('reload')">Erneut versuchen</button>
    </div>

    <DocumentPreviewLayout
      v-if="selectedDocument"
      class="panel-right__preview panel-right__preview--details-panel unassigned-layout"
      show-drawer
      :is-open="drawerOpen"
      :content-key="selectedDocument.document_id"
      :body-id="drawerBodyId"
    >
      <template #viewer>
        <div class="preview-frame-wrap" role="region" :aria-label="`Dokumentvorschau: ${documentTitle}`">
          <PdfPreview ref="previewRef" :key="selectedDocument.document_id" class="preview-frame" :src="previewSrc" fit-page />
        </div>
      </template>
      <template #drawer-header>
        <DocumentDrawerHeader
          ref="drawerHeaderRef"
          :open="drawerOpen"
          :body-id="drawerBodyId"
          :title="documentTitle"
          title-tag="h1"
          :document-type="selectedDocument.document_type || ''"
          :page-count-label="pageCountLabel"
          @toggle="drawerOpen = !drawerOpen"
        >
          <template v-if="documentDate" #meta>
            <span class="details-drawer__meta-part">{{ documentDate }}</span>
          </template>
          <template #actions>
            <div v-if="items.length > 1" class="unassigned-strip">
              <TransitionGroup
                ref="stripRef"
                tag="div"
                name="unassigned-thumb"
                class="unassigned-strip__track"
                role="listbox"
                aria-label="Offene Dokumente"
                aria-orientation="horizontal"
                aria-multiselectable="true"
                @keydown="onStripKeydown"
              >
                <button
                  v-for="item in items"
                  :key="item.document_id"
                  type="button"
                  class="unassigned-thumb"
                  :class="{ 'is-active': item.document_id === documentId, 'is-checked': checkedIds.has(item.document_id) }"
                  role="option"
                  :aria-selected="checkedIds.size ? checkedIds.has(item.document_id) : item.document_id === documentId"
                  :aria-label="itemLabel(item)"
                  :title="itemLabel(item)"
                  :tabindex="item.document_id === documentId ? 0 : -1"
                  :data-document-id="item.document_id"
                  @click="onThumbClick($event, item.document_id)"
                >
                  <img
                    v-if="!brokenThumbnails.has(item.document_id)"
                    class="unassigned-thumb__image"
                    :src="documentThumbnailUrl(item.document_id)"
                    alt=""
                    loading="lazy"
                    decoding="async"
                    draggable="false"
                    @error="markThumbnailBroken(item.document_id)"
                  >
                  <v-icon v-else class="unassigned-thumb__fallback" size="18" aria-hidden="true">mdi-file-document-outline</v-icon>
                  <span v-if="hasSuggestion(item)" class="unassigned-thumb__dot" aria-hidden="true" />
                  <v-icon v-if="checkedIds.has(item.document_id)" class="unassigned-thumb__check" size="14" aria-hidden="true">mdi-check</v-icon>
                </button>
              </TransitionGroup>
              <span class="unassigned-strip__position" aria-live="polite">{{ positionLabel }}</span>
            </div>
            <v-menu :key="selectedDocument.document_id" location="top end" :offset="4">
              <template #activator="{ props: menuProps }">
                <v-btn
                  v-bind="menuProps"
                  type="button"
                  icon="mdi-dots-horizontal"
                  size="small"
                  density="comfortable"
                  variant="text"
                  class="details-action-btn details-action-btn--quiet"
                  aria-label="Weitere Aktionen"
                  :disabled="isLoading || Boolean(pending)"
                />
              </template>
              <v-list class="pm-menu" density="compact">
                <v-list-item v-if="detectedSender" title="Absender als Alias übernehmen" prepend-icon="mdi-tag-plus" @click="openAssignmentEditor('alias')" />
                <v-list-item title="Korrespondent anlegen" prepend-icon="mdi-account-plus" @click="openAssignmentEditor('create')" />
                <v-list-item title="Bewusst ohne Korrespondent" prepend-icon="mdi-close" @click="resolveDocument('ignore')" />
              </v-list>
            </v-menu>
          </template>
        </DocumentDrawerHeader>
      </template>
      <template #drawer-body>
        <div class="details-drawer__body">
          <section class="details-drawer__inner pm-drawer-body unassigned-assignment" :aria-labelledby="assignmentTitleId">
            <h2 :id="assignmentTitleId">Zuordnung</h2>
            <p v-if="targets.length > 1" class="unassigned-multi" role="status">
              {{ targets.length }} Dokumente ausgewählt
              <button type="button" class="unassigned-link" :disabled="Boolean(pending)" @click="clearChecked">Auswahl aufheben</button>
            </p>
            <form class="unassigned-editor" @submit.prevent="resolveDocument(submitAction)">
              <v-text-field
                v-if="action === 'create'"
                v-model="newName"
                label="Name des Korrespondenten"
                maxlength="120"
                :disabled="isLoading || Boolean(pending)"
                autofocus
                density="compact"
                variant="outlined"
                hide-details
              />
              <DocumentMetadataFields
                v-else
                :key="`${selectedDocument.document_id}-${action}`"
                v-model:correspondent="correspondentSelection"
                :field-keys="['correspondent']"
                :correspondents="correspondentOptions"
                :correspondent-autofocus="action === 'alias'"
                :disabled="isLoading || Boolean(pending)"
              >
                <template #correspondent-suffix>
                  <v-chip
                    v-if="showsSuggestion"
                    class="unassigned-suggestion"
                    color="primary"
                    variant="tonal"
                    size="x-small"
                    rounded="pill"
                  >Vorschlag</v-chip>
                </template>
              </DocumentMetadataFields>
              <div class="unassigned-editor__actions">
                <button v-if="action !== 'assign'" type="button" class="unassigned-link" :disabled="Boolean(pending)" @click="setAction('assign')">Abbrechen</button>
                <v-btn
                  class="unassigned-submit"
                  type="submit"
                  color="primary"
                  variant="tonal"
                  prepend-icon="mdi-check"
                  :disabled="!canSubmit"
                  :loading="pending?.id === selectedDocument.document_id && pending.action !== 'ignore'"
                  :title="`${submitLabel} (${shortcutLabel})`"
                >{{ submitLabel }}</v-btn>
                <span class="unassigned-shortcut" aria-hidden="true">{{ shortcutLabel }}</span>
              </div>
            </form>
          </section>
        </div>
      </template>
    </DocumentPreviewLayout>

    <div v-else-if="isLoading && !loadError" class="unassigned-state" role="status">
      <v-progress-circular indeterminate size="20" width="2" />
      Offene Zuordnungen werden geladen …
    </div>
    <PmEmptyState v-else-if="!loadError" icon="mdi-file-document-outline" title="Keine offenen Zuordnungen." size="md" role="status" />
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, ref, useId, watch } from 'vue';
import DocumentDrawerHeader from './DocumentDrawerHeader.vue';
import DocumentMetadataFields from './DocumentMetadataFields.vue';
import DocumentPreviewLayout from './DocumentPreviewLayout.vue';
import PmEmptyState from './PmEmptyState.vue';
import { ignoreUnresolvedCorrespondent } from '../api/correspondents.js';
import { documentFileUrl, documentThumbnailUrl, patchDocument } from '../api/documents.js';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { notifyError, useNotifications } from '../stores/notifications.js';
import { formatDocumentDateInputFromIso } from '../utils/dates.js';

const PdfPreview = defineAsyncComponent(() => import('./PdfPreview.vue'));
const props = defineProps({
  active: Boolean,
  items: { type: Array, required: true },
  documentId: { type: String, default: null },
  isLoading: Boolean,
  loadError: Boolean,
});
const emit = defineEmits(['reload', 'resolved', 'select']);
const store = useCorrespondentStore();
const { notify } = useNotifications();
const instanceId = useId();
const drawerBodyId = `unassigned-details-${instanceId}`;
const assignmentTitleId = `unassigned-assignment-${instanceId}`;
const drawerHeaderRef = ref(null);
const previewRef = ref(null);
const stripRef = ref(null);
const brokenThumbnails = ref(new Set());
let keepStripFocus = false;
const drawerOpen = ref(true);
const pending = ref(null);
const action = ref('assign');
const selectedCorrespondentId = ref();
const newSenderValue = 'unassigned:new-sender';
const newName = ref('');
const actionLabels = {
  assign: 'Zuordnen',
  alias: 'Alias übernehmen und zuordnen',
  create: 'Anlegen und zuordnen',
};
// Mehrfachauswahl im Streifen (⌘/Strg-Klick, Umschalt-Klick, Leertaste): alle gemeinsam zuordnen.
const checkedIds = ref(new Set());
const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');
const shortcutLabel = isMac ? '⌘↵' : 'Strg+↵';

const selectedDocument = computed(() => props.items.find(item => item.document_id === props.documentId));
const documentTitle = computed(() => selectedDocument.value?.title || selectedDocument.value?.original_filename || 'Ohne Titel');
const documentDate = computed(() => formatDocumentDateInputFromIso(selectedDocument.value?.document_date));
const pageCountLabel = computed(() => {
  const count = previewRef.value?.pageCount;
  if (!count) return '';
  return count === 1 ? '1 Seite' : `${count} Seiten`;
});
const activeIndex = computed(() => props.items.findIndex(item => item.document_id === props.documentId));
const positionLabel = computed(() => activeIndex.value < 0 ? '' : `${activeIndex.value + 1} / ${props.items.length}`);
const previewSrc = computed(() => props.documentId ? documentFileUrl(props.documentId, 'searchable') : '');

function senderKey(name) {
  return String(name || '').normalize('NFKC').toLocaleLowerCase('de-DE').replace(/[^\p{L}\p{N}]/gu, '');
}

const detectedSender = computed(() => selectedDocument.value?.sender?.trim().replace(/\s+/g, ' ') ?? '');
const suggestedCorrespondent = computed(() => {
  const sender = detectedSender.value;
  const key = senderKey(sender);
  if (!key) return null;
  const exactMatch = store.findByName(sender);
  if (exactMatch) return exactMatch;
  const matches = store.correspondents.filter(correspondent =>
    [correspondent.name, ...(correspondent.aliases || []).map(alias => alias.alias)].some(name => senderKey(name) === key));
  return matches.length === 1 ? matches[0] : null;
});
const newSenderOption = computed(() => {
  if (action.value !== 'assign' || !detectedSender.value || suggestedCorrespondent.value) return null;
  return {
    title: detectedSender.value,
    value: newSenderValue,
    props: { subtitle: 'Neuen Korrespondenten anlegen' },
  };
});
const correspondentOptions = computed(() => newSenderOption.value
  ? [newSenderOption.value, ...store.correspondentOptions]
  : store.correspondentOptions);
const correspondentSelection = computed({
  get: () => selectedCorrespondentId.value === undefined
    ? suggestedCorrespondent.value?.id ?? newSenderOption.value?.value ?? null
    : selectedCorrespondentId.value,
  set: value => { selectedCorrespondentId.value = value; },
});
const showsSuggestion = computed(() => action.value === 'assign' && Boolean(correspondentSelection.value)
  && correspondentSelection.value === (suggestedCorrespondent.value?.id ?? newSenderOption.value?.value));
const submitAction = computed(() => correspondentSelection.value === newSenderValue ? 'create' : action.value);
const targets = computed(() => {
  if (!checkedIds.value.size) return selectedDocument.value ? [selectedDocument.value] : [];
  return props.items.filter(item => checkedIds.value.has(item.document_id));
});
const submitLabel = computed(() => {
  const count = targets.value.length;
  if (count < 2) return actionLabels[submitAction.value];
  return { assign: `${count} Dokumente zuordnen`, alias: `Alias übernehmen und ${count} zuordnen`, create: `Anlegen und ${count} zuordnen` }[submitAction.value];
});
const nameToCreate = computed(() => action.value === 'create' ? newName.value.trim() : detectedSender.value);
const canSubmit = computed(() => Boolean(selectedDocument.value && !pending.value && !props.isLoading
  && (submitAction.value === 'create' ? nameToCreate.value.length >= 2 && nameToCreate.value.length <= 120 : correspondentSelection.value)));

function setAction(nextAction) {
  action.value = nextAction;
  selectedCorrespondentId.value = nextAction === 'assign' ? undefined : null;
  newName.value = detectedSender.value;
}

function openAssignmentEditor(nextAction) {
  drawerOpen.value = true;
  setAction(nextAction);
}

function itemLabel(item) {
  return item.title || item.original_filename || 'Ohne Titel';
}

function hasSuggestion(item) {
  return Boolean(item.sender?.trim());
}

function markThumbnailBroken(id) {
  brokenThumbnails.value = new Set(brokenThumbnails.value).add(id);
}

function stripElement() {
  return stripRef.value?.$el ?? null;
}

function thumbFor(id) {
  return [...(stripElement()?.querySelectorAll('.unassigned-thumb') ?? [])].find(el => el.dataset.documentId === id) ?? null;
}

function selectFromStrip(id, focus = false) {
  if (!id) return;
  // Strip navigation keeps focus in the strip instead of jumping to the title.
  keepStripFocus = true;
  if (id !== props.documentId) emit('select', id);
  if (focus) void nextTick(() => thumbFor(id)?.focus());
}

function toggleChecked(id) {
  const next = new Set(checkedIds.value);
  // Die erste Markierung nimmt das gerade offene Dokument mit.
  if (!next.size && props.documentId && props.documentId !== id) next.add(props.documentId);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  checkedIds.value = next.size > 1 ? next : new Set();
}

function clearChecked() {
  checkedIds.value = new Set();
}

function onThumbClick(event, id) {
  if (event.metaKey || event.ctrlKey) {
    toggleChecked(id);
    return;
  }
  if (event.shiftKey && activeIndex.value >= 0) {
    const to = props.items.findIndex(item => item.document_id === id);
    const [from, until] = [Math.min(activeIndex.value, to), Math.max(activeIndex.value, to)];
    const range = props.items.slice(from, until + 1).map(item => item.document_id);
    checkedIds.value = range.length > 1 ? new Set(range) : new Set();
    return;
  }
  clearChecked();
  selectFromStrip(id);
}

function onShortcut(event) {
  // ⌘/Strg+Enter: Vorschlag bzw. Auswahl übernehmen – danach öffnet sich das nächste Dokument.
  if (event.key !== 'Enter' || !(event.metaKey || event.ctrlKey) || event.isComposing) return;
  event.preventDefault();
  if (canSubmit.value) void resolveDocument(submitAction.value);
}

function onStripKeydown(event) {
  const count = props.items.length;
  if (!count) return;
  if (event.key === ' ' && event.target?.dataset?.documentId) {
    event.preventDefault();
    toggleChecked(event.target.dataset.documentId);
    return;
  }
  const current = Math.max(0, activeIndex.value);
  const targets = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: count - 1 };
  if (!(event.key in targets)) return;
  event.preventDefault();
  const next = Math.min(count - 1, Math.max(0, targets[event.key]));
  selectFromStrip(props.items[next].document_id, true);
}

watch(() => props.documentId, () => setAction('assign'), { immediate: true });
watch(drawerOpen, open => { if (open) previewRef.value?.resetZoom(); });
watch([() => props.active, () => props.documentId], async ([active]) => {
  if (!active) return;
  const fromStrip = keepStripFocus;
  keepStripFocus = false;
  if (!fromStrip) drawerOpen.value = true;
  await nextTick();
  thumbFor(props.documentId)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  if (props.active && !fromStrip) drawerHeaderRef.value?.focusTitle();
}, { immediate: true });

function senderMatches(correspondent, sender) {
  const key = senderKey(sender);
  return [correspondent?.name, correspondent?.short_name, ...(correspondent?.aliases || []).map(alias => alias.alias)]
    .some(name => name && senderKey(name) === key);
}

async function resolveDocument(key) {
  const item = selectedDocument.value;
  if (!item || pending.value || props.isLoading || (key !== 'ignore' && !canSubmit.value)) return;
  const id = item.document_id;
  const batch = targets.value.map(entry => entry.document_id);
  let correspondentId = correspondentSelection.value;
  pending.value = { id, action: key };
  const done = [];
  try {
    if (key === 'ignore') {
      for (const documentId of batch) {
        await ignoreUnresolvedCorrespondent(documentId, 'Bewusst ohne Korrespondent');
        done.push(documentId);
      }
    } else {
      if (key === 'create') {
        const result = await store.createCorrespondentByName(nameToCreate.value);
        if (!result?.id) return;
        correspondentId = result.id;
        if (props.documentId === id && action.value === 'assign') selectedCorrespondentId.value = correspondentId;
      }
      if (key === 'alias') {
        const result = await store.addAlias(correspondentId, item.sender);
        if (!result.ok) return;
      }
      for (const documentId of batch) {
        await patchDocument(documentId, { correspondent_id: correspondentId });
        done.push(documentId);
      }
    }
    clearChecked();
    notifyResolved(key, done.length, key === 'assign' ? aliasOffer(correspondentId, batch) : null);
  } catch (error) {
    notifyError(error, key === 'ignore' ? 'Fall konnte nicht ausgeblendet werden.' : 'Dokument konnte nicht zugeordnet werden.');
  } finally {
    if (done.length) emit('resolved', done, key !== 'ignore');
    pending.value = null;
  }
}

/** Weicht der erkannte Absender von allen bekannten Schreibweisen ab, bietet die Meldung an, ihn als Alias zu merken. */
function aliasOffer(correspondentId, documentIds) {
  const correspondent = store.findById(correspondentId);
  const senders = [...new Set(props.items
    .filter(entry => documentIds.includes(entry.document_id))
    .map(entry => entry.sender?.trim().replace(/\s+/g, ' '))
    .filter(sender => sender && sender.length >= 2 && !senderMatches(correspondent, sender)))];
  if (!correspondent || senders.length !== 1) return null;
  const [sender] = senders;
  return {
    message: `„${sender}“ als Schreibweise von ${correspondent.name} merken?`,
    action: {
      label: 'Als Alias merken',
      errorMessage: 'Alias konnte nicht gespeichert werden.',
      onClick: () => store.addAlias(correspondentId, sender),
    },
  };
}

function notifyResolved(key, count, offer) {
  const subject = count === 1 ? 'Dokument' : `${count} Dokumente`;
  const base = key === 'ignore'
    ? `${subject} ${count === 1 ? 'bleibt' : 'bleiben'} ohne Korrespondenten.`
    : `${subject} zugeordnet.`;
  if (!offer) {
    notify({ type: 'success', title: 'Korrespondent', message: base });
    return;
  }
  // Erfolgsmeldungen bleiben sonst stumm; das Angebot braucht aber eine sichtbare Aktion.
  notify({ type: 'info', critical: true, title: 'Korrespondent', message: `${base} ${offer.message}`, action: offer.action, timeoutMs: 9000 });
}
</script>

<style scoped>
.unassigned {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.unassigned-layout { flex: 1; min-height: 0; }
.unassigned-multi {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  margin: 0 0 10px;
  color: var(--pm-muted);
  font-size: 0.82rem;
}
.unassigned-shortcut { color: var(--pm-muted); font-size: 0.75rem; font-variant-numeric: tabular-nums; }
@media (pointer: coarse) { .unassigned-shortcut { display: none; } }
/* The strip sits in the title row, filling the space before the actions. */
.unassigned-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  max-width: min(55cqi, 520px);
  margin-inline-end: 8px;
}
.unassigned-strip__track {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 4px;
  margin: -4px;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  scrollbar-width: none;
}
.unassigned-strip__track::-webkit-scrollbar { display: none; }
.unassigned-strip__position {
  flex: none;
  color: var(--pm-muted);
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
}
.unassigned-thumb {
  position: relative;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 44px;
  padding: 0;
  border: 1px solid var(--pm-divider);
  border-radius: 4px;
  background: var(--pm-viewer-surface, rgb(var(--v-theme-surface)));
  cursor: pointer;
  opacity: .72;
  transition:
    opacity var(--pm-duration-fast, 120ms) var(--pm-easing, ease),
    box-shadow var(--pm-duration-fast, 120ms) var(--pm-easing, ease),
    transform var(--pm-duration-fast, 120ms) var(--pm-easing, ease);
}
.unassigned-thumb:hover { opacity: 1; transform: translateY(-1px); }
.unassigned-thumb.is-active {
  opacity: 1;
  box-shadow: 0 0 0 2px var(--preview-drawer-card-bg, rgb(var(--v-theme-surface))), 0 0 0 4px var(--pm-list-accent, var(--pm-accent));
}
.unassigned-thumb:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; }
.unassigned-thumb__image {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 3px;
  object-fit: cover;
  object-position: top center;
  pointer-events: none;
}
.unassigned-thumb__fallback { color: var(--pm-muted); }
.unassigned-thumb__dot {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 9px;
  height: 9px;
  border: 2px solid var(--preview-drawer-card-bg, rgb(var(--v-theme-surface)));
  border-radius: 50%;
  background: var(--pm-accent);
}
/* Markiert für gemeinsames Zuordnen: Haken unten rechts, Rahmen in Akzentfarbe. */
.unassigned-thumb.is-checked {
  opacity: 1;
  box-shadow: 0 0 0 2px var(--pm-list-accent, var(--pm-accent));
}
.unassigned-thumb.is-checked.is-active {
  box-shadow: 0 0 0 2px var(--preview-drawer-card-bg, rgb(var(--v-theme-surface))), 0 0 0 4px var(--pm-list-accent, var(--pm-accent));
}
.unassigned-thumb__check {
  position: absolute;
  right: -5px;
  bottom: -5px;
  border: 2px solid var(--preview-drawer-card-bg, rgb(var(--v-theme-surface)));
  border-radius: 50%;
  background: var(--pm-list-accent, var(--pm-accent));
  color: #fff;
}
.unassigned-thumb-move { transition: transform var(--pm-duration-normal, 200ms) var(--pm-easing, ease); }
.unassigned-thumb-leave-active {
  transition:
    opacity var(--pm-duration-normal, 200ms) var(--pm-easing, ease),
    transform var(--pm-duration-normal, 200ms) var(--pm-easing, ease),
    width var(--pm-duration-normal, 200ms) var(--pm-easing, ease),
    margin var(--pm-duration-normal, 200ms) var(--pm-easing, ease);
}
.unassigned-thumb-leave-to { width: 0; margin-inline-end: -10px; opacity: 0; transform: scale(.6); }
@media (prefers-reduced-motion: reduce) {
  .unassigned-thumb, .unassigned-thumb-move, .unassigned-thumb-leave-active { transition: none; }
}
.unassigned-assignment { padding-block-start: 16px; }
.unassigned-assignment h2 { margin: 0 0 10px; color: var(--pm-text); font-size: 0.95rem; font-weight: 650; }
.unassigned-editor { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px 10px; }
.unassigned-editor :deep(.pm-metadata-row) { grid-template-columns: minmax(0, 1fr); grid-template-areas: 'value'; gap: 0; }
.unassigned-editor :deep(.pm-metadata-label) {
  position: absolute;
  inline-size: 1px;
  block-size: 1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.unassigned-editor__actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.unassigned-suggestion.v-chip { flex-shrink: 0; margin-inline: 6px; font-weight: 400; letter-spacing: 0; }
.unassigned-submit.v-btn {
  max-width: 100%;
  height: auto;
  min-height: 36px;
  padding-block: 6px;
  border-radius: 8px;
  text-transform: none;
  letter-spacing: 0;
}
@container (max-width: 480px) {
  .unassigned-editor { grid-template-columns: minmax(0, 1fr); }
}
.unassigned-submit :deep(.v-btn__content) { white-space: normal; }
.unassigned-link { min-height: 32px; color: var(--pm-accent-text); font-size: 0.82rem; cursor: pointer; }
.unassigned-link:hover:not(:disabled) { text-decoration: underline; }
.unassigned-link:disabled { opacity: .55; cursor: default; }
.unassigned-link:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }
.unassigned-state { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 18px; color: var(--pm-muted); font-size: 0.86rem; }
@media (pointer: coarse) {
  .unassigned-link, .unassigned-submit.v-btn { min-height: 44px; }
}
</style>
