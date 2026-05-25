<template>
  <BaseDialog
    v-model="isOpen"
    max-width="460"
    title="Dokument umbenennen"
    description="Anzeigenamen für die Liste und Details ändern."
    primary-text="Speichern"
    secondary-text="Abbrechen"
    :loading="isRenaming"
    @primary="submitRename"
    @close="close"
  >
    <v-text-field
      v-model="documentName"
      label="Name"
      density="comfortable"
      variant="outlined"
      hide-details
      @keydown="handleRenameShortcut"
    >
      <template #append-inner>
        <v-tooltip text="Titel mit KI vorschlagen" location="top">
          <template #activator="{ props: tooltipProps }">
            <v-btn
              v-bind="tooltipProps"
              icon="mdi-robot-outline"
              variant="text"
              size="small"
              aria-label="Titel mit KI vorschlagen"
              :loading="isSuggesting"
              :disabled="isSuggesting || isRenaming || !target?.id"
              @click.stop="suggestTitle"
            />
          </template>
        </v-tooltip>
      </template>
    </v-text-field>
  </BaseDialog>
</template>

<script setup>
import { ref } from 'vue';
import BaseDialog from './BaseDialog.vue';
import { notifyError, logDevError, useNotifications } from '../stores/notifications';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts';

// ── Props / Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  apiBaseUrl: { type: String, default: '' }
});

const emit = defineEmits(['saved']);

// ── Notifications ────────────────────────────────────────────────────────────

const { notify } = useNotifications();

// ── State ────────────────────────────────────────────────────────────────────

const isOpen = ref(false);
const target = ref(null);
const documentName = ref('');
const isRenaming = ref(false);
const isSuggesting = ref(false);

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

function normalizeInput(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function stripPdfSuffix(filename) {
  return String(filename || '').trim().replace(/\.pdf$/i, '');
}

function getDocumentTitle(doc) {
  if (!doc || typeof doc !== 'object') return '';
  const displayName = String(doc.display_name || '').trim();
  return displayName || String(doc.original_filename || '').trim();
}

async function parseResponseError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

function normalizeAiTitleSuggestion(rawValue) {
  const lines = String(rawValue || '')
    .split('\n')
    .map((line) => normalizeInput(line))
    .filter(Boolean);
  if (!lines.length) return '';
  let candidate = lines[0];
  candidate = candidate.replace(/^titel\s*[:\-]\s*/i, '');
  candidate = candidate.replace(/^[\-\*•\d\.\)\(\s]+/, '');
  candidate = candidate.replace(/^[`"'„"‚']+/, '').replace(/[`"'„"‚']+$/, '');
  candidate = stripPdfSuffix(normalizeInput(candidate));
  if (candidate.length > 200) candidate = candidate.slice(0, 200).trim();
  return candidate;
}

// ── Open / Close ─────────────────────────────────────────────────────────────

function open(document) {
  if (!document?.id) return;
  target.value = {
    id: document.id,
    original_filename: document.original_filename,
    display_name: document.display_name || null
  };
  documentName.value = stripPdfSuffix(getDocumentTitle(document));
  isOpen.value = true;
}

function close(force = false) {
  if (isRenaming.value && !force) return;
  isOpen.value = false;
  target.value = null;
  documentName.value = '';
  isSuggesting.value = false;
}

// ── KI-Titelvorschlag ─────────────────────────────────────────────────────────

async function suggestTitle() {
  if (!target.value?.id || isSuggesting.value || isRenaming.value) return;
  isSuggesting.value = true;
  try {
    const response = await fetch(`${props.apiBaseUrl}/api/ai/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'Schlage einen kurzen, präzisen deutschen Dokumenttitel vor. Antworte nur mit dem Titel ohne Zusatztext.',
        doc_id: target.value.id,
        request_type: 'summary',
        top_k: 8
      })
    });
    if (!response.ok) throw new Error(await parseResponseError(response));
    const payload = await response.json();
    const suggestion = normalizeAiTitleSuggestion(payload?.answer);
    if (!suggestion) {
      notify({ type: 'warning', title: 'KI', message: 'Kein brauchbarer Titelvorschlag gefunden.' });
      return;
    }
    documentName.value = suggestion;
    notify({ type: 'success', title: 'KI', message: 'Titelvorschlag übernommen.' });
  } catch (error) {
    notifyError(error, 'Titelvorschlag fehlgeschlagen.', { title: 'KI' });
  } finally {
    isSuggesting.value = false;
  }
}

// ── Speichern ─────────────────────────────────────────────────────────────────

async function submitRename() {
  if (!target.value?.id || isRenaming.value || isSuggesting.value) return;
  const nextName = normalizeInput(documentName.value);
  if (!nextName) {
    notify({ type: 'warning', message: 'Name darf nicht leer sein.' });
    return;
  }

  isRenaming.value = true;
  try {
    const response = await fetch(`${props.apiBaseUrl}/api/documents/${target.value.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: nextName })
    });
    if (!response.ok) throw new Error(await parseResponseError(response));
    const updated = await response.json();
    emit('saved', updated);
    close(true);
    notify({ type: 'success', title: 'Dokument', message: 'Name gespeichert.' });
  } catch (error) {
    notifyError(error, 'Dokument konnte nicht umbenannt werden.');
  } finally {
    isRenaming.value = false;
  }
}

function handleRenameShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, submitRename, { ignoreEditable: false });
}

// ── Public API ────────────────────────────────────────────────────────────────

defineExpose({ open });
</script>
