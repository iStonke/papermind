<!--
  UnassignedCorrespondentDocuments — „Ohne Korrespondent“ bzw. „Genauer
  zuordnen“ als Seite wie „Mögliche Doppelte“: eine Karte pro Dokument
  (CorrespondentAssignmentCard), jede mit eigener Zuordnung. Ein Klick aufs
  Vorschaubild öffnet eine große Vorschau als Overlay (DocumentPreviewOverlay),
  nicht im Dokumentbereich.

  Kopf: Sammelaktion für eindeutige Vorschläge („Alle Vorschläge übernehmen“
  bzw. „Genannte Mitglieder übernehmen“, mit Bestätigung) und „Ausgeblendete“
  zum Zurückholen bewusst belassener Fälle.
-->
<template>
  <section class="assign" :aria-label="texts.region" :aria-busy="isLoading">
    <slot name="back" />
    <header class="assign__head">
      <span class="assign__icon" aria-hidden="true"><v-icon size="22">{{ texts.icon }}</v-icon></span>
      <div class="assign__heading">
        <h1 :id="titleId" ref="titleRef" tabindex="-1" class="assign__title">{{ texts.title }}</h1>
        <p class="assign__subtitle">{{ subtitle }}</p>
      </div>
      <!-- Kopfaktionen wie im Profilkopf: umrandete Icon-Buttons, Zahl als Plakette. -->
      <div class="assign__head-actions">
        <!-- Immer sichtbar; ohne Treffer ausgegraut, der Tooltip (am Rahmen, weil
             deaktivierte Buttons keinen zeigen) sagt warum. -->
        <span v-if="!showHidden" class="assign__action" :title="bulkTitle">
          <v-btn
            class="pm-header-icon-btn assign__head-btn"
            variant="outlined"
            icon="mdi-check-all"
            :disabled="!bulkCandidates.length || Boolean(pending) || isLoading"
            :aria-label="bulkTitle"
            aria-haspopup="dialog"
            @click="bulkDialogOpen = true"
          />
          <span v-if="bulkCandidates.length" class="assign__badge assign__badge--accent" aria-hidden="true">{{ bulkCandidates.length }}</span>
        </span>
        <span class="assign__action" :title="hiddenTitle">
          <v-btn
            class="pm-header-icon-btn assign__head-btn"
            :class="{ 'is-active': showHidden }"
            variant="outlined"
            :icon="showHidden ? 'mdi-arrow-left' : 'mdi-eye-off-outline'"
            :disabled="!showHidden && !hiddenItems.length"
            :aria-pressed="showHidden"
            :aria-label="showHidden ? 'Offene anzeigen' : `Ausgeblendete (${hiddenItems.length})`"
            @click="toggleHidden"
          />
          <span v-if="!showHidden && hiddenItems.length" class="assign__badge" aria-hidden="true">{{ hiddenItems.length }}</span>
        </span>
      </div>
    </header>

    <div ref="scrollRef" class="assign__scroll">
      <div v-if="loadError" class="assign__state" role="alert">
        {{ texts.loadError }}
        <button type="button" class="assign__link" @click="emit('reload')">Erneut versuchen</button>
      </div>

      <template v-if="showHidden">
        <TransitionGroup
          v-if="hiddenItems.length"
          tag="ul"
          name="assign-card"
          class="assign__list"
          :aria-label="texts.hiddenRegion"
        >
          <CorrespondentAssignmentCard
            v-for="item in hiddenItems"
            :key="item.document_id"
            :item="item"
            :mode="mode"
            hidden
            :disabled="Boolean(restoringId)"
            :pending-action="restoringId === item.document_id ? 'restore' : ''"
            @open-document="previewId = $event"
            @restore="restore"
          />
        </TransitionGroup>
        <div v-else-if="hiddenLoading" class="assign__state" role="status">
          <v-progress-circular indeterminate size="20" width="2" />
          Wird geladen …
        </div>
        <PmEmptyState v-else icon="mdi-eye-off-outline" title="Nichts ausgeblendet." size="md" role="status" />
      </template>

      <TransitionGroup
        v-else-if="sortedItems.length"
        tag="ul"
        name="assign-card"
        class="assign__list"
        :aria-labelledby="titleId"
        @focusin="onFocusIn"
      >
        <CorrespondentAssignmentCard
          v-for="item in sortedItems"
          :key="item.document_id"
          :item="item"
          :mode="mode"
          :disabled="Boolean(pending) || isLoading"
          :pending-action="pending?.id === item.document_id ? pending.action : ''"
          :shortcut-label="shortcutLabel"
          :mentioned-member-id="mentionedMembers[item.document_id] || null"
          @open-document="previewId = $event"
          @submit="resolve"
        />
      </TransitionGroup>
      <div v-else-if="isLoading && !loadError" class="assign__state" role="status">
        <v-progress-circular indeterminate size="20" width="2" />
        {{ texts.loading }}
      </div>
      <PmEmptyState
        v-else-if="!loadError"
        icon="mdi-check-circle-outline"
        :title="texts.empty"
        subtitle="Neue Fälle erscheinen hier automatisch."
        size="md"
        role="status"
      />
    </div>

    <DocumentPreviewOverlay
      v-model="previewId"
      :items="showHidden ? hiddenItems : sortedItems"
      @closed="focusThumb"
    />

    <ConfirmDialog
      v-model="bulkDialogOpen"
      :title="texts.bulkTitle"
      :description="bulkDescription"
      :primary-text="bulkCandidates.length === 1 ? '1 Dokument zuordnen' : `${bulkCandidates.length} Dokumente zuordnen`"
      icon="mdi-check-all"
      :max-width="520"
      :loading="pending?.id === BULK"
      :primary-disabled="!bulkCandidates.length"
      @primary="runBulk"
    >
      <ul class="assign__bulk-list">
        <li v-for="entry in bulkCandidates.slice(0, BULK_PREVIEW)" :key="entry.item.document_id">
          <span class="assign__bulk-doc">{{ titleOf(entry.item) }}</span>
          <v-icon size="14" aria-hidden="true">mdi-arrow-right</v-icon>
          <span class="assign__bulk-target">{{ entry.correspondent.name }}</span>
          <span v-if="entry.guess" class="assign__bulk-guess" title="Vorschlag aus Namensähnlichkeit – bitte kurz prüfen">ähnlich</span>
        </li>
        <li v-if="bulkCandidates.length > BULK_PREVIEW" class="assign__bulk-more">
          und {{ bulkCandidates.length - BULK_PREVIEW }} weitere
        </li>
      </ul>
    </ConfirmDialog>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import ConfirmDialog from './ConfirmDialog.vue';
import CorrespondentAssignmentCard from './CorrespondentAssignmentCard.vue';
import DocumentPreviewOverlay from './DocumentPreviewOverlay.vue';
import PmEmptyState from './PmEmptyState.vue';
import {
  getCorrespondentRefinements,
  ignoreUnresolvedCorrespondent,
  keepCollectionDocument,
  listCollectionDocuments,
  listUnresolvedCorrespondents,
  restoreCollectionDocument,
  restoreUnresolvedCorrespondent,
} from '../api/correspondents.js';
import { patchDocument } from '../api/documents.js';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { useSettingsStore } from '../stores/settings.js';
import { notifyError, useNotifications } from '../stores/notifications.js';
import { senderKey } from '../utils/senderKey.js';
import { isSimilarityGuess, suggestCorrespondent } from '../utils/correspondentSuggestion.js';

const BULK = '__bulk';
const BULK_PREVIEW = 8;
const REFINEMENT_CONCURRENCY = 4;

const props = defineProps({
  active: Boolean,
  items: { type: Array, required: true },
  /** Dokument, dessen Karte beim Öffnen in den Blick rückt (zuletzt bearbeitet). */
  documentId: { type: String, default: null },
  isLoading: Boolean,
  loadError: Boolean,
  // 'unassigned' = ohne Korrespondent; 'collection' = direkt an einer Sammlung → genauer zuordnen.
  mode: { type: String, default: 'unassigned' },
});
const emit = defineEmits(['reload', 'resolved', 'select']);
const store = useCorrespondentStore();
const settingsStore = useSettingsStore();
const showSuggestions = computed(() => settingsStore.settings.ui.correspondent_show_suggestions !== false);
const { notify } = useNotifications();
const titleId = `assign-title-${useId()}`;
const titleRef = ref(null);
const scrollRef = ref(null);
const pending = ref(null);
let focusIndexAfterResolve = -1;
const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');
const shortcutLabel = isMac ? '⌘↵' : 'Strg+↵';

const isCollectionMode = computed(() => props.mode === 'collection');
const texts = computed(() => (isCollectionMode.value
  ? {
    title: 'Genauer zuordnen',
    icon: 'mdi-shape-outline',
    region: 'Dokumente an Sammlungen',
    loadError: 'Dokumente an Sammlungen konnten nicht geladen werden.',
    loading: 'Dokumente an Sammlungen werden geladen …',
    empty: 'Alle Dokumente sind genauer zugeordnet.',
    task: 'genauer zuordnen',
    bulk: 'Genannte Mitglieder übernehmen',
    bulkTitle: 'Genannte Mitglieder übernehmen?',
    bulkHint: 'Diese Dokumente nennen genau ein Mitglied ihrer Sammlung und werden ihm zugeordnet.',
    bulkNone: 'Kein Dokument nennt eindeutig ein Mitglied',
    hiddenRegion: 'Bei der Sammlung belassene Dokumente',
    hiddenTask: 'bei der Sammlung belassen',
  }
  : {
    title: 'Ohne Korrespondent',
    icon: 'mdi-inbox-outline',
    region: 'Dokumente ohne Korrespondenten',
    loadError: 'Offene Zuordnungen konnten nicht geladen werden.',
    loading: 'Offene Zuordnungen werden geladen …',
    empty: 'Keine offenen Zuordnungen.',
    task: 'zuordnen',
    bulk: 'Alle Vorschläge übernehmen',
    bulkTitle: 'Alle Vorschläge übernehmen?',
    bulkHint: 'Jedes Dokument wird seinem vorgeschlagenen, bereits vorhandenen Korrespondenten zugeordnet; Vorschläge aus Namensähnlichkeit sind markiert. Neue Korrespondenten werden nicht angelegt.',
    bulkNone: 'Keine Vorschläge vorhanden',
    hiddenRegion: 'Bewusst ohne Korrespondent belassene Dokumente',
    hiddenTask: 'bewusst ohne Korrespondent',
  }));
const subtitle = computed(() => {
  if (showHidden.value) {
    const hiddenCount = hiddenItems.value.length;
    return `${hiddenCount === 1 ? '1 Dokument' : `${hiddenCount} Dokumente`} · ${texts.value.hiddenTask}`;
  }
  const count = props.items.length;
  if (!count) return props.isLoading ? 'Wird geladen …' : 'Alles erledigt';
  return `${count === 1 ? '1 Dokument' : `${count} Dokumente`} · ${texts.value.task}`;
});

function titleOf(item) {
  return item.title || item.original_filename || 'Ohne Titel';
}

// ── Genannte Mitglieder (Sammlungsmodus): für Karten und Sammelaktion ──
const mentionedMembers = ref({});
const requestedRefinements = new Set();
async function loadMentionedMembers() {
  if (!isCollectionMode.value || !props.active) return;
  const queue = props.items.filter(item => item.correspondent_id && !requestedRefinements.has(item.document_id));
  queue.forEach(item => requestedRefinements.add(item.document_id));
  const worker = async () => {
    for (let item = queue.shift(); item; item = queue.shift()) {
      try {
        const result = await getCorrespondentRefinements(item.correspondent_id, item.document_id);
        const mentioned = (result?.items || []).filter(entry => entry.mentioned);
        if (mentioned.length === 1) mentionedMembers.value = { ...mentionedMembers.value, [item.document_id]: mentioned[0].id };
      } catch {
        // Ohne Vorschlag bleibt die Sammlung ausgewählt; die Mitglieder-Chips helfen weiter.
      }
    }
  };
  await Promise.all(Array.from({ length: REFINEMENT_CONCURRENCY }, worker));
}
watch([() => props.items, () => props.active], () => { void loadMentionedMembers(); }, { immediate: true });

// ── Reihenfolge: erst Dokumente mit vorhandenem Vorschlag, dann die, für die
// ein neuer Korrespondent angelegt werden müsste (je Gruppe stabil). ──
function suggestionFor(item) {
  if (!showSuggestions.value) return null;
  const mentionedMemberId = mentionedMembers.value[item.document_id] || null;
  const correspondent = suggestCorrespondent(item, store, { mentionedMemberId, collectionMode: isCollectionMode.value });
  return correspondent && correspondent.id !== item.correspondent_id ? correspondent : null;
}
const sortedItems = computed(() => {
  const withSuggestion = [];
  const rest = [];
  for (const item of props.items) (suggestionFor(item) ? withSuggestion : rest).push(item);
  return [...withSuggestion, ...rest];
});

// ── Sammelaktion: nur eindeutige Vorschläge auf bestehende Korrespondenten ──
const bulkDialogOpen = ref(false);
const bulkCandidates = computed(() => {
  if (!showSuggestions.value) return [];
  return props.items.flatMap((item) => {
    const mentionedMemberId = mentionedMembers.value[item.document_id] || null;
    if (isCollectionMode.value && !mentionedMemberId) return [];
    const correspondent = suggestCorrespondent(item, store, { mentionedMemberId, collectionMode: isCollectionMode.value });
    if (!correspondent || correspondent.id === item.correspondent_id) return [];
    if (isCollectionMode.value && correspondent.id !== mentionedMemberId) return [];
    return [{ item, correspondent, guess: isSimilarityGuess(item, correspondent) }];
  });
});
const bulkDescription = computed(() => texts.value.bulkHint);
const bulkTitle = computed(() => {
  if (bulkCandidates.value.length) return `${texts.value.bulk} (${bulkCandidates.value.length})`;
  if (!showSuggestions.value) return `${texts.value.bulk}: Vorschläge sind in den Einstellungen ausgeschaltet`;
  return `${texts.value.bulk}: ${texts.value.bulkNone}`;
});
const hiddenTitle = computed(() => {
  if (showHidden.value) return 'Offene anzeigen';
  return hiddenItems.value.length ? `Ausgeblendete (${hiddenItems.value.length})` : 'Ausgeblendete: Nichts ausgeblendet';
});

async function runBulk() {
  const candidates = bulkCandidates.value;
  if (!candidates.length || pending.value) return;
  pending.value = { id: BULK, action: 'bulk' };
  const done = [];
  try {
    for (const { item, correspondent } of candidates) {
      await patchDocument(item.document_id, { correspondent_id: correspondent.id });
      done.push(item.document_id);
    }
    const subject = done.length === 1 ? '1 Dokument' : `${done.length} Dokumente`;
    notify({ type: 'success', title: 'Korrespondent', message: `${subject} ${isCollectionMode.value ? 'genauer ' : ''}zugeordnet.` });
  } catch (error) {
    notifyError(error, done.length
      ? `${done.length} von ${candidates.length} Dokumenten zugeordnet; danach ist ein Fehler aufgetreten.`
      : 'Dokumente konnten nicht zugeordnet werden.');
  } finally {
    pending.value = null;
    bulkDialogOpen.value = false;
    if (done.length) emit('resolved', done, true);
  }
}

// ── Ausgeblendete: bewusst belassene Fälle ansehen und zurückholen ──
const showHidden = ref(false);
const hiddenItems = ref([]);
const hiddenLoading = ref(false);
const restoringId = ref('');
async function loadHidden() {
  hiddenLoading.value = true;
  try {
    const result = isCollectionMode.value
      ? await listCollectionDocuments({ limit: 200, hidden: true })
      : await listUnresolvedCorrespondents({ limit: 200, excerptChars: 0, hidden: true });
    hiddenItems.value = result?.items || [];
  } catch {
    hiddenItems.value = [];
  } finally {
    hiddenLoading.value = false;
  }
}
watch(() => props.active, (active) => { if (active) void loadHidden(); }, { immediate: true });

async function toggleHidden() {
  showHidden.value = !showHidden.value;
  if (showHidden.value) void loadHidden();
  await nextTick();
  titleRef.value?.focus();
}

async function restore(id) {
  if (restoringId.value) return;
  restoringId.value = id;
  try {
    if (isCollectionMode.value) await restoreCollectionDocument(id);
    else await restoreUnresolvedCorrespondent(id);
    hiddenItems.value = hiddenItems.value.filter(item => item.document_id !== id);
    notify({ type: 'success', title: 'Korrespondent', message: `Dokument ist wieder ${isCollectionMode.value ? 'zum genaueren Zuordnen' : 'zum Zuordnen'} offen.` });
    emit('reload');
  } catch (error) {
    notifyError(error, 'Dokument konnte nicht zurückgeholt werden.');
  } finally {
    restoringId.value = '';
  }
}

// ── Große Vorschau als Overlay ────────────────────────────────────
const previewId = ref(null);
function focusThumb(id) {
  void nextTick(() => cardElement(id)?.querySelector('.assign-card__thumb')?.focus({ preventScroll: true }));
}
watch(() => props.active, (active) => { if (!active) previewId.value = null; });

function cardElement(id) {
  return scrollRef.value?.querySelector(`.assign-card[data-document-id="${CSS.escape(id)}"]`) || null;
}

function onFocusIn(event) {
  const id = event.target?.closest?.('.assign-card')?.dataset?.documentId;
  if (id && id !== props.documentId) emit('select', id);
}

// Nach dem Erledigen rückt der Fokus auf die nächste Karte.
watch(sortedItems, (list) => {
  if (focusIndexAfterResolve >= 0) {
    const index = Math.min(focusIndexAfterResolve, list.length - 1);
    focusIndexAfterResolve = -1;
    void nextTick(() => {
      const next = list[index];
      if (next) cardElement(next.document_id)?.focus({ preventScroll: false });
      else titleRef.value?.focus();
    });
  }
}, { flush: 'post' });

// ── Öffnen: zuletzt bearbeitete Karte in den Blick, sonst die Überschrift ──
watch(() => props.active, async (active) => {
  if (!active) return;
  await nextTick();
  const card = props.documentId ? cardElement(props.documentId) : null;
  if (card) {
    card.scrollIntoView({ block: 'nearest' });
    card.focus({ preventScroll: true });
  } else {
    titleRef.value?.focus();
  }
}, { immediate: true });

// ── Speichern ─────────────────────────────────────────────────────
function senderMatches(correspondent, sender) {
  const key = senderKey(sender);
  return [correspondent?.name, correspondent?.short_name, ...(correspondent?.aliases || []).map(alias => alias.alias)]
    .some(name => name && senderKey(name) === key);
}

async function resolve({ key, item, correspondentId: chosenId, name, collectionId }) {
  if (pending.value || props.isLoading) return;
  const id = item.document_id;
  focusIndexAfterResolve = sortedItems.value.findIndex(entry => entry.document_id === id);
  let correspondentId = chosenId;
  pending.value = { id, action: key };
  const done = [];
  try {
    if (key === 'ignore') {
      if (isCollectionMode.value) await keepCollectionDocument(id);
      else await ignoreUnresolvedCorrespondent(id, 'Bewusst ohne Korrespondent');
      done.push(id);
    } else {
      if (key === 'create') {
        // Im Sammlungsmodus entsteht eine Organisation, die gleich zur Sammlung gehört.
        const result = await store.createCorrespondentByName(name, isCollectionMode.value ? { kind: 'organization' } : {});
        if (!result?.id) return;
        correspondentId = result.id;
        if (collectionId) await store.updateCorrespondent(correspondentId, { parent_id: collectionId }, { silent: true });
      }
      if (key === 'alias') {
        const result = await store.addAlias(correspondentId, item.sender);
        if (!result.ok) return;
      }
      await patchDocument(id, { correspondent_id: correspondentId });
      done.push(id);
    }
    notifyResolved(key, key === 'assign' ? aliasOffer(correspondentId, item) : null);
  } catch (error) {
    notifyError(error, key === 'ignore' ? 'Fall konnte nicht ausgeblendet werden.' : 'Dokument konnte nicht zugeordnet werden.');
  } finally {
    if (!done.length) focusIndexAfterResolve = -1;
    pending.value = null;
    if (done.length) emit('resolved', done, key !== 'ignore');
    if (done.length && key === 'ignore') void loadHidden();
  }
}

/** Weicht der erkannte Absender von allen bekannten Schreibweisen ab, bietet die Meldung an, ihn als Alias zu merken. */
function aliasOffer(correspondentId, item) {
  const correspondent = store.findById(correspondentId);
  const sender = item.sender?.trim().replace(/\s+/g, ' ');
  if (!correspondent || !sender || sender.length < 2 || senderMatches(correspondent, sender)) return null;
  return {
    message: `„${sender}“ als Schreibweise von ${correspondent.name} merken?`,
    action: {
      label: 'Als Alias merken',
      errorMessage: 'Alias konnte nicht gespeichert werden.',
      onClick: () => store.addAlias(correspondentId, sender),
    },
  };
}

function notifyResolved(key, offer) {
  const base = key === 'ignore'
    ? `Dokument bleibt ${isCollectionMode.value ? 'bei der Sammlung' : 'ohne Korrespondenten'}.`
    : `Dokument ${isCollectionMode.value ? 'genauer ' : ''}zugeordnet.`;
  if (!offer) {
    notify({ type: 'success', title: 'Korrespondent', message: base });
    return;
  }
  // Erfolgsmeldungen bleiben sonst stumm; das Angebot braucht aber eine sichtbare Aktion.
  notify({ type: 'info', critical: true, title: 'Korrespondent', message: `${base} ${offer.message}`, action: offer.action, timeoutMs: 9000 });
}

defineExpose({ focusTitle: () => titleRef.value?.focus() });
</script>

<style scoped>
.assign { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; }
.assign__head {
  flex: none;
  display: flex;
  align-items: center;
  gap: 14px;
  box-sizing: border-box;
  min-height: calc(57px + var(--notes-meta-row-height, 36px));
  padding: 10px clamp(18px, 3vw, 40px);
  border-bottom: 1px solid var(--pm-divider);
  background: var(--pm-app-surface);
}
.assign__icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--pm-warning) 12%, transparent);
  color: var(--pm-warning);
}
.assign__heading { flex: 1; min-width: 0; }
.assign__head-actions { display: flex; flex: none; align-items: center; gap: 10px; }
.assign__action { position: relative; display: inline-flex; }
.assign__head-btn.v-btn { border-color: var(--pm-divider); color: var(--pm-muted); }
.assign__head-btn.v-btn.is-active { border-color: var(--pm-accent); color: var(--pm-accent-text); }
/* Zahl an der Ecke des Buttons, wie eine Plakette. */
.assign__badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border: 2px solid var(--pm-app-surface);
  border-radius: 999px;
  background: var(--pm-muted);
  color: var(--pm-app-surface);
  font-size: 0.66rem;
  font-weight: 700;
  line-height: 14px;
  text-align: center;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.assign__badge--accent { background: var(--pm-accent); color: var(--pm-accent-contrast, #fff); }
.assign__bulk-list { display: grid; gap: 6px; margin: 4px 0 0; padding: 0; list-style: none; font-size: 0.86rem; }
.assign__bulk-list li { display: flex; align-items: center; gap: 8px; min-width: 0; }
.assign__bulk-list .v-icon { flex: none; color: var(--pm-muted); }
.assign__bulk-guess {
  flex: none;
  padding: 0 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-warning, #b7791f) 14%, transparent);
  color: var(--pm-warning, #b7791f);
  font-size: 0.72rem;
}
.assign__bulk-doc { min-width: 0; overflow: hidden; color: var(--pm-muted); text-overflow: ellipsis; white-space: nowrap; }
.assign__bulk-target { flex: none; max-width: 50%; overflow: hidden; color: var(--pm-text); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.assign__bulk-more { color: var(--pm-muted); }
.assign__title { margin: 0; font-size: 1.5rem; font-weight: 700; line-height: 1.2; outline: none; }
.assign__subtitle { margin: 4px 0 0; color: var(--pm-muted); font-size: 0.86rem; }
.assign__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 22px clamp(16px, 3vw, 40px) 40px;
  container-type: inline-size;
}
.assign__list { display: flex; flex-direction: column; gap: 12px; margin: 0; padding: 0; list-style: none; }
.assign__state { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 0; color: var(--pm-muted); font-size: 0.86rem; }
.assign__link {
  min-height: 32px;
  padding: 0 4px;
  border: 0;
  background: transparent;
  color: var(--pm-accent-text);
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.assign__link:hover:not(:disabled) { text-decoration: underline; }
.assign__link:disabled { opacity: .55; cursor: default; }
.assign__link:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }

.assign-card-leave-active { transition: opacity 180ms ease, transform 220ms cubic-bezier(.22, 1, .36, 1); }
.assign-card-leave-to { opacity: 0; transform: translateX(12px); }
.assign-card-move { transition: transform 240ms cubic-bezier(.22, 1, .36, 1); }
:global(.pm-no-animations .assign-card-leave-active),
:global(.pm-no-animations .assign-card-move) { transition: none; }
@media (prefers-reduced-motion: reduce) {
  .assign-card-leave-active, .assign-card-move { transition: none; }
}
@media (pointer: coarse) { .assign__link { min-height: 44px; } }
</style>
