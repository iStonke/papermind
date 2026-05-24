<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="1080"
    width="calc(100% - 48px)"
    body-class="app-modal__body--flush"
    title="KI-Chat"
    description="Fragen stellen und Quellen direkt öffnen."
    variant="info"
    primary-text="Fertig"
    :show-secondary="false"
    @primary="emit('update:modelValue', false)"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="ai-page">
      <section class="ai-suggestions">
        <div class="ai-section-title">Vorschlagsfragen</div>
        <div class="ai-suggestions__grid">
          <button
            v-for="suggestion in AI_SUGGESTED_QUESTIONS"
            :key="`suggestion-${suggestion}`"
            type="button"
            class="ai-suggestion-card"
            @click="askAiSuggestion(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
      </section>

      <section class="ai-chat-panel">
        <div ref="aiChatScrollRef" class="ai-chat-history">
          <template v-if="aiMessages.length > 0">
            <article
              v-for="message in aiMessages"
              :key="message.id"
              class="ai-message"
              :class="`ai-message--${message.role}`"
            >
              <div class="ai-message__bubble">
                <div class="ai-message__bubble-content">
                  <v-progress-circular
                    v-if="message.isStatus"
                    size="14"
                    width="2"
                    indeterminate
                    color="primary"
                  />
                  <span>{{ message.text }}</span>
                </div>
              </div>
              <div
                v-if="message.role === 'assistant' && !message.isStatus && message.citations.length > 0"
                class="ai-sources"
              >
                <div class="ai-sources__divider" />
                <div class="ai-sources__label">Quellen</div>
                <article
                  v-for="citation in message.citations"
                  :key="`${message.id}-${citation.doc_id}`"
                  class="ai-citation-card"
                >
                  <div class="ai-citation-card__left">
                    <v-icon size="16">mdi-file-document-outline</v-icon>
                  </div>
                  <div class="ai-citation-card__content">
                    <div class="ai-citation-card__title">{{ formatCitationTitle(citation) }}</div>
                    <div v-if="citationPageLabel(citation)" class="ai-citation-card__meta">
                      {{ citationPageLabel(citation) }}
                    </div>
                    <div v-if="citation.snippet" class="ai-citation-card__snippet">{{ citation.snippet }}</div>
                    <div v-if="citationHintText(citation)" class="ai-citation-card__hint">
                      {{ citationHintText(citation) }}
                    </div>
                  </div>
                  <div class="ai-citation-card__actions">
                    <v-btn size="x-small" variant="text" color="primary" @click="openCitation(citation)">
                      Öffnen
                    </v-btn>
                  </div>
                </article>
              </div>
            </article>
          </template>
          <div v-else class="ai-chat-empty">
            <v-icon size="44" class="ai-chat-empty__icon">mdi-robot-outline</v-icon>
            <div class="ai-chat-empty__title">Stelle eine Frage zu deinen Dokumenten</div>
            <div class="ai-chat-empty__subtitle">
              Die Antwort basiert auf Retrieval über OCR-Texte und zeigt Quellenkarten.
            </div>
          </div>
        </div>

        <div class="ai-chat-input">
          <v-text-field
            v-model="aiQuestionInput"
            placeholder="Frage zu deinen Dokumenten stellen..."
            density="comfortable"
            variant="outlined"
            hide-details
            :disabled="isAiAsking"
            @keydown.enter.prevent="submitAiQuestion()"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-send-outline"
                size="small"
                variant="text"
                :loading="isAiAsking"
                :disabled="!aiQuestionInput.trim() || isAiAsking"
                @click="submitAiQuestion()"
              />
            </template>
          </v-text-field>
        </div>
      </section>
    </div>
  </BaseDialog>
</template>

<script setup>
import { ref, nextTick } from 'vue';
import BaseDialog from './BaseDialog.vue';
import { notifyError } from '../stores/notifications';

// ── Props / Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  apiBaseUrl: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'open-citation']);

// ── Konstanten ───────────────────────────────────────────────────────────────

const AI_DEFAULT_TOP_K = 3;
const AI_MAX_VISIBLE_CITATIONS = 3;
const AI_PHASE_MIN_MS = 300;

const AI_SUGGESTED_QUESTIONS = [
  'Was sind meine letzten Rechnungen?',
  'Gibt es Dokumente mit Bankdaten?',
  'Welche Versicherungen habe ich?',
  'Zeige Verträge aus diesem Jahr.'
];

// ── State ────────────────────────────────────────────────────────────────────

const aiMessages = ref([]);
const aiQuestionInput = ref('');
const aiSessionId = ref('');
const isAiAsking = ref(false);
const aiChatScrollRef = ref(null);

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

function makeUiId(prefix) {
  if (window.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createAiSessionId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  const hex = () => Math.floor(Math.random() * 0x10000).toString(16).padStart(4, '0');
  return `${hex()}${hex()}-${hex()}-4${hex().slice(1)}-a${hex().slice(1)}-${hex()}${hex()}${hex()}`;
}

function ensureAiSessionId() {
  if (!aiSessionId.value) {
    aiSessionId.value = createAiSessionId();
  }
  return aiSessionId.value;
}

function sleepMs(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function ensureMinPhaseDuration(startTs, minDurationMs = AI_PHASE_MIN_MS) {
  const elapsed = Date.now() - Number(startTs || 0);
  if (elapsed < minDurationMs) {
    await sleepMs(minDurationMs - elapsed);
  }
}

async function parseResponseError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

// ── Nachrichten-Verwaltung ───────────────────────────────────────────────────

function pushAiMessage(payload) {
  const message = {
    id: payload.id || makeUiId('ai-msg'),
    role: payload.role,
    text: payload.text,
    isStatus: Boolean(payload.isStatus),
    citations: Array.isArray(payload.citations) ? payload.citations : []
  };
  aiMessages.value.push(message);
  nextTick(() => {
    const container = aiChatScrollRef.value;
    if (container) container.scrollTop = container.scrollHeight;
  });
  return message.id;
}

function updateAiMessage(messageId, patch) {
  const index = aiMessages.value.findIndex((m) => m.id === messageId);
  if (index >= 0) {
    aiMessages.value[index] = { ...aiMessages.value[index], ...patch };
  }
}

function removeAiMessage(messageId) {
  const index = aiMessages.value.findIndex((m) => m.id === messageId);
  if (index >= 0) aiMessages.value.splice(index, 1);
}

// ── Formatierung ─────────────────────────────────────────────────────────────

function formatCitationTitle(citation) {
  return String(citation?.display_name || citation?.original_filename || citation?.doc_id || '').trim() || 'Unbekanntes Dokument';
}

function citationPageLabel(citation) {
  const from = Number(citation?.page_from || 0);
  const to = Number(citation?.page_to || 0);
  if (from > 0 && to > 0) return from === to ? `Seite ${from}` : `Seite ${from}-${to}`;
  if (from > 0) return `Seite ${from}`;
  if (to > 0) return `Seite ${to}`;
  return '';
}

function citationHintText(citation) {
  const snippet = String(citation?.snippet || '').trim().toLowerCase();
  if (snippet === 'bankdaten nicht gefunden') return 'Prüfe Bankdaten im Dokument (Fußzeile).';
  return '';
}

// ── KI-Anfragen ──────────────────────────────────────────────────────────────

async function askAiSuggestion(question) {
  aiQuestionInput.value = String(question || '').trim();
  await submitAiQuestion();
}

async function submitAiQuestion() {
  const question = String(aiQuestionInput.value || '').trim();
  if (!question || isAiAsking.value) return;

  const sessionId = ensureAiSessionId();
  pushAiMessage({ role: 'user', text: question });
  aiQuestionInput.value = '';
  isAiAsking.value = true;

  const statusMessageId = pushAiMessage({
    role: 'assistant',
    text: 'Suche relevante Stellen…',
    isStatus: true,
    citations: []
  });
  const phaseOneStartedAt = Date.now();

  try {
    const response = await fetch(`${props.apiBaseUrl}/api/ai/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, question, top_k: AI_DEFAULT_TOP_K })
    });
    if (!response.ok) throw new Error(await parseResponseError(response));

    await ensureMinPhaseDuration(phaseOneStartedAt);
    updateAiMessage(statusMessageId, { text: 'Formuliere Antwort…' });
    const phaseTwoStartedAt = Date.now();

    const payload = await response.json();
    if (payload?.meta?.session_id && !aiSessionId.value) {
      aiSessionId.value = String(payload.meta.session_id);
    }

    await ensureMinPhaseDuration(phaseTwoStartedAt);
    updateAiMessage(statusMessageId, {
      isStatus: false,
      text: String(payload?.answer || 'Keine Antwort verfügbar.'),
      citations: Array.isArray(payload?.citations)
        ? payload.citations.slice(0, AI_MAX_VISIBLE_CITATIONS)
        : []
    });
  } catch (error) {
    removeAiMessage(statusMessageId);
    notifyError(error, 'KI-Anfrage fehlgeschlagen.', { title: 'KI' });
  } finally {
    isAiAsking.value = false;
  }
}

function openCitation(citation) {
  emit('open-citation', citation);
}
</script>
