<template>
  <div class="ai-page">
      <section class="ai-chat-panel">
        <div ref="aiChatScrollRef" class="ai-chat-history">
          <!-- Beim initial leeren Chat bleibt der Leerzustand stehen. Der Loader
               ist nur beim Wechsel eines bereits sichtbaren Verlaufs sinnvoll. -->
          <div v-if="isVisibleSessionLoading" class="ai-chat-loading">
            <v-progress-circular size="24" width="2" indeterminate color="primary" />
            <span>Chatverlauf wird geladen…</span>
          </div>
          <div v-else-if="historyLoadError" class="ai-chat-loading ai-chat-loading--error">
            <v-icon size="24">mdi-alert-circle-outline</v-icon>
            <span>{{ historyLoadError }}</span>
            <v-btn size="small" variant="tonal" color="primary" @click="initializeChatHistory">
              Erneut versuchen
            </v-btn>
          </div>
          <template v-else-if="aiMessages.length > 0">
            <article
              v-for="message in aiMessages"
              :key="message.id"
              class="ai-message"
              :class="`ai-message--${message.role}`"
            >
              <div class="ai-message__meta">
                <span class="ai-message__meta-dot" aria-hidden="true"></span>
                {{ message.role === 'user' ? 'Du' : 'PaperMind' }}
              </div>
              <div class="ai-message__row">
                <div v-if="message.role === 'assistant'" class="ai-avatar" aria-hidden="true">
                  <v-icon size="16">mdi-robot-outline</v-icon>
                </div>
                <div class="ai-message__body">
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
                    v-if="message.role === 'assistant' && !message.isStatus && message.assistantMessageId"
                    class="ai-knowledge-actions"
                  >
                    <span v-if="message.knowledgeTrace?.used" class="ai-knowledge-badge">
                      <v-icon size="14">mdi-source-merge</v-icon>
                      Wissensbasis: {{ message.knowledgeTrace.pages?.length || 0 }} Seiten ·
                      {{ message.knowledgeTrace.claims?.length || 0 }} Aussagen
                    </span>
                    <span v-else class="ai-knowledge-badge ai-knowledge-badge--raw">
                      <v-icon size="14">mdi-file-search-outline</v-icon>
                      Direkt aus Originaldokumenten
                    </span>
                    <v-btn
                      size="x-small"
                      variant="text"
                      prepend-icon="mdi-note-plus-outline"
                      :loading="capturingMessageId === message.id"
                      :disabled="message.captureStatus === 'proposed'"
                      @click="captureAnswer(message)"
                    >{{ message.captureStatus === 'proposed' ? 'Im Prüfkorb' : 'Ins Wissen übernehmen' }}</v-btn>
                  </div>
                  <div
                    v-if="message.role === 'assistant' && !message.isStatus && message.citations.length > 0"
                    class="ai-sources"
                  >
                    <div class="ai-sources__label">
                      {{ message.citations.length }}
                      {{ message.citations.length === 1 ? 'Quelle' : 'Quellen' }}
                    </div>
                    <button
                      v-for="citation in message.citations"
                      :key="`${message.id}-${citation.doc_id}`"
                      type="button"
                      class="ai-citation-card"
                      @click="openCitation(citation)"
                    >
                      <span class="ai-citation-card__thumb" aria-hidden="true"></span>
                      <span class="ai-citation-card__content">
                        <span class="ai-citation-card__title">{{ formatCitationTitle(citation) }}</span>
                        <span v-if="citationPageLabel(citation)" class="ai-citation-card__meta">
                          {{ citationPageLabel(citation) }}
                        </span>
                        <span v-if="citation.snippet" class="ai-citation-card__snippet">{{ citation.snippet }}</span>
                        <span v-if="citationHintText(citation)" class="ai-citation-card__hint">
                          {{ citationHintText(citation) }}
                        </span>
                      </span>
                      <v-icon class="ai-citation-card__chevron" size="16">mdi-arrow-top-right</v-icon>
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </template>
          <div v-else class="ai-chat-empty">
            <v-icon size="40" class="ai-chat-empty__icon">mdi-message-text-outline</v-icon>
            <div class="ai-chat-empty__title">Stelle eine Frage zu deinen Dokumenten</div>
            <div class="ai-chat-empty__subtitle">
              Wähle rechts einen Beispielprompt oder tippe unten deine Frage. Antworten
              stützen sich auf die OCR-Texte deiner Dokumente; relevante Treffer öffnen
              sich in der Vorschau.
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
            :disabled="isAiAsking || isVisibleSessionLoading"
            @keydown="handleQuestionShortcut"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-send-outline"
                size="small"
                variant="text"
                :disabled="!aiQuestionInput.trim() || isAiAsking || isVisibleSessionLoading"
                @click="submitAiQuestion()"
              />
            </template>
          </v-text-field>
        </div>
      </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { notifyError } from '../stores/notifications';
import { SHORTCUT_ACTIONS, handleShortcut } from '../keyboard/shortcuts';
import { captureChatAnswer } from '../api/wiki.js';
import {
  archiveChatSession,
  askQuestion,
  getChatSession,
  getLatestChatSession,
  listChatSessions,
} from '../api/ai.js';

// ── Props / Emits ────────────────────────────────────────────────────────────

defineProps({
  apiBaseUrl: { type: String, default: '' }
});

const emit = defineEmits(['open-citation']);

// ── Konstanten ───────────────────────────────────────────────────────────────

const AI_DEFAULT_TOP_K = 3;
const AI_MAX_VISIBLE_CITATIONS = 3;
const AI_PHASE_MIN_MS = 300;
const CHAT_SESSION_STORAGE_KEY = 'pm.ai.chat-session-id';
const CHAT_HISTORY_WATCHDOG_MS = 7000;

// ── State ────────────────────────────────────────────────────────────────────

const aiMessages = ref([]);
const aiQuestionInput = ref('');
const aiSessionId = ref('');
const isAiAsking = ref(false);
const aiChatScrollRef = ref(null);
const capturingMessageId = ref('');
const chatSessions = ref([]);
const isLoadingSession = ref(true);
const isLoadingSessions = ref(false);
const historyLoadError = ref('');
// Die initiale Wiederherstellung läuft still im Hintergrund. Erst wenn bereits
// Nachrichten sichtbar sind (Wechsel zwischen gespeicherten Chats), ersetzt der
// Ladezustand den Verlauf und blockiert den Composer sichtbar.
const isVisibleSessionLoading = computed(() => isLoadingSession.value && aiMessages.value.length > 0);
let historyInitializationPromise = null;
let historyLoadAttempt = 0;
let historyLoadWatchdog = null;

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
    storeCurrentSessionId(aiSessionId.value);
  }
  return aiSessionId.value;
}

function readCurrentSessionId() {
  try { return String(localStorage.getItem(CHAT_SESSION_STORAGE_KEY) || '').trim(); }
  catch { return ''; }
}

function storeCurrentSessionId(sessionId) {
  try {
    if (sessionId) localStorage.setItem(CHAT_SESSION_STORAGE_KEY, String(sessionId));
    else localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
  } catch { /* Web Storage ist optional; der Server bleibt maßgeblich. */ }
}

function scrollChatToEnd() {
  const toEnd = () => {
    const container = aiChatScrollRef.value;
    if (container) container.scrollTop = container.scrollHeight;
  };
  // Mehrfach anstoßen: direkt nach dem DOM-Update, nach dem nächsten Paint und
  // nach der Panel-Transition – sonst steht scrollHeight beim Öffnen noch nicht
  // final und der Verlauf landet nicht ganz unten.
  nextTick(toEnd);
  requestAnimationFrame(() => {
    toEnd();
    requestAnimationFrame(toEnd);
  });
  window.setTimeout(toEnd, 260);
}

function applySessionPayload(payload) {
  const sessionId = String(payload?.session_id || '').trim();
  if (!sessionId) return false;
  aiSessionId.value = sessionId;
  aiMessages.value = (Array.isArray(payload?.messages) ? payload.messages : [])
    .filter((message) => ['user', 'assistant'].includes(message?.role))
    .map((message) => ({
      id: String(message.id || makeUiId('ai-msg')),
      role: message.role,
      text: String(message.content || ''),
      isStatus: false,
      citations: Array.isArray(message.citations)
        ? message.citations.slice(0, AI_MAX_VISIBLE_CITATIONS)
        : [],
      knowledgeTrace: message.knowledge_trace || null,
      assistantMessageId: message.role === 'assistant' ? String(message.id || '') : null,
      sessionId,
      captureStatus: null,
    }));
  storeCurrentSessionId(sessionId);
  scrollChatToEnd();
  return true;
}

async function refreshChatSessions({ silent = true } = {}) {
  isLoadingSessions.value = true;
  try {
    chatSessions.value = await listChatSessions({ limit: 30 });
  } catch (error) {
    if (!silent) notifyError(error, 'Gespeicherte Chats konnten nicht geladen werden.', { title: 'Wissen' });
  } finally {
    isLoadingSessions.value = false;
  }
}

async function initializeChatHistory() {
  const attempt = ++historyLoadAttempt;
  if (historyLoadWatchdog) window.clearTimeout(historyLoadWatchdog);
  isLoadingSession.value = true;
  historyLoadError.value = '';
  historyLoadWatchdog = window.setTimeout(() => {
    if (attempt !== historyLoadAttempt || !isLoadingSession.value) return;
    isLoadingSession.value = false;
    historyLoadError.value = 'Der Chatverlauf antwortet gerade nicht.';
  }, CHAT_HISTORY_WATCHDOG_MS);
  try {
    let restored = false;
    const storedSessionId = readCurrentSessionId();
    if (storedSessionId) {
      try {
        restored = applySessionPayload(await getChatSession(storedSessionId));
      } catch (error) {
        if (error?.status !== 404) throw error;
        storeCurrentSessionId('');
      }
    }
    if (!restored) {
      const latest = await getLatestChatSession();
      if (latest) applySessionPayload(latest);
    }
    if (attempt === historyLoadAttempt) historyLoadError.value = '';
  } catch (error) {
    if (attempt !== historyLoadAttempt) return;
    historyLoadError.value = error?.code === 'REQUEST_TIMEOUT'
      ? 'Der Chatverlauf antwortet gerade nicht.'
      : 'Der Chatverlauf konnte nicht geladen werden.';
    notifyError(error, 'Chatverlauf konnte nicht wiederhergestellt werden.', { title: 'Wissen' });
  } finally {
    if (attempt === historyLoadAttempt) {
      if (historyLoadWatchdog) window.clearTimeout(historyLoadWatchdog);
      historyLoadWatchdog = null;
      isLoadingSession.value = false;
    }
  }
}

async function openSavedSession(sessionId) {
  if (!sessionId || isAiAsking.value || sessionId === aiSessionId.value) return;
  isLoadingSession.value = true;
  try {
    applySessionPayload(await getChatSession(sessionId));
  } catch (error) {
    notifyError(error, 'Gespeicherter Chat konnte nicht geöffnet werden.', { title: 'Wissen' });
  } finally {
    isLoadingSession.value = false;
  }
}

async function startNewChat() {
  if (isAiAsking.value) return;
  try {
    if (aiSessionId.value && aiMessages.value.length) {
      await archiveChatSession(aiSessionId.value);
    }
    aiMessages.value = [];
    aiQuestionInput.value = '';
    aiSessionId.value = '';
    storeCurrentSessionId('');
    await refreshChatSessions();
  } catch (error) {
    notifyError(error, 'Ein neuer Chat konnte nicht gestartet werden.', { title: 'Wissen' });
  }
}

function onHistoryMenuToggle(open) {
  if (open) void refreshChatSessions({ silent: false });
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

// ── Nachrichten-Verwaltung ───────────────────────────────────────────────────

function pushAiMessage(payload) {
  const message = {
    id: payload.id || makeUiId('ai-msg'),
    role: payload.role,
    text: payload.text,
    isStatus: Boolean(payload.isStatus),
    citations: Array.isArray(payload.citations) ? payload.citations : [],
    knowledgeTrace: payload.knowledgeTrace || null,
    assistantMessageId: payload.assistantMessageId || null,
    sessionId: payload.sessionId || null,
    captureStatus: payload.captureStatus || null
  };
  aiMessages.value.push(message);
  scrollChatToEnd();
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
  return String(citation?.document_title || citation?.display_name || citation?.original_filename || citation?.doc_id || '').trim() || 'Unbekanntes Dokument';
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

// ── Wissensanfragen ──────────────────────────────────────────────────────────

async function askAiSuggestion(question) {
  if (historyInitializationPromise) await historyInitializationPromise;
  aiQuestionInput.value = String(question || '').trim();
  await submitAiQuestion();
}

// Von der Elternkomponente aufgerufen, wenn rechts ein Beispielprompt der
// Bühne angeklickt wird: Frage in den Verlauf übernehmen und abschicken.
defineExpose({
  askQuestion: askAiSuggestion,
  aiSessionId,
  chatSessions,
  isAiAsking,
  isLoadingSessions,
  onHistoryMenuToggle,
  openSavedSession,
  startNewChat,
});

async function submitAiQuestion() {
  // Der initial leere Composer bleibt optisch stabil und benutzbar. Eine sehr
  // frühe Eingabe wartet intern auf die Sitzungswiederherstellung, damit keine
  // parallelen Chat-Sitzungen entstehen.
  if (historyInitializationPromise && isLoadingSession.value && aiMessages.value.length === 0) {
    await historyInitializationPromise;
  }
  const question = String(aiQuestionInput.value || '').trim();
  if (!question || isAiAsking.value || isLoadingSession.value) return;

  const sessionId = ensureAiSessionId();
  const userMessageId = pushAiMessage({ role: 'user', text: question });
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
    const payload = await askQuestion({ session_id: sessionId, question, top_k: AI_DEFAULT_TOP_K });

    await ensureMinPhaseDuration(phaseOneStartedAt);
    updateAiMessage(statusMessageId, { text: 'Formuliere Antwort…' });
    const phaseTwoStartedAt = Date.now();

    if (payload?.meta?.session_id) {
      aiSessionId.value = String(payload.meta.session_id);
      storeCurrentSessionId(aiSessionId.value);
    }

    await ensureMinPhaseDuration(phaseTwoStartedAt);
    updateAiMessage(statusMessageId, {
      isStatus: false,
      text: String(payload?.answer || 'Keine Antwort verfügbar.'),
      citations: Array.isArray(payload?.citations)
        ? payload.citations.slice(0, AI_MAX_VISIBLE_CITATIONS)
        : [],
      knowledgeTrace: payload?.knowledge_trace || null,
      assistantMessageId: payload?.meta?.assistant_message_id || null,
      sessionId: payload?.meta?.session_id || sessionId
    });
    void refreshChatSessions();
  } catch (error) {
    removeAiMessage(statusMessageId);
    removeAiMessage(userMessageId);
    if (!aiQuestionInput.value) aiQuestionInput.value = question;
    notifyError(error, 'Anfrage konnte nicht beantwortet werden.', { title: 'Wissen' });
  } finally {
    isAiAsking.value = false;
  }
}

function handleQuestionShortcut(event) {
  handleShortcut(event, SHORTCUT_ACTIONS.PRIMARY, submitAiQuestion, { ignoreEditable: false });
}

function openCitation(citation) {
  emit('open-citation', citation);
}

async function captureAnswer(message) {
  if (!message?.assistantMessageId || !message?.sessionId || message.captureStatus === 'proposed') return;
  const suggestedTitle = String(message.text || '').split(/[.!?\n]/)[0].trim().slice(0, 80) || 'Wissensanalyse';
  const title = window.prompt('Titel der Arbeitsnotiz im Wissensbereich', suggestedTitle);
  if (!title?.trim()) return;
  capturingMessageId.value = message.id;
  try {
    await captureChatAnswer({
      session_id: message.sessionId,
      message_id: message.assistantMessageId,
      title: title.trim(),
    });
    updateAiMessage(message.id, { captureStatus: 'proposed' });
  } catch (error) {
    notifyError(error, 'Antwort konnte nicht in den Wissens-Prüfkorb gelegt werden.', { title: 'Wissen' });
  } finally {
    capturingMessageId.value = '';
  }
}

onMounted(() => {
  historyInitializationPromise = initializeChatHistory();
});

onBeforeUnmount(() => {
  historyLoadAttempt += 1;
  if (historyLoadWatchdog) window.clearTimeout(historyLoadWatchdog);
  historyLoadWatchdog = null;
});
</script>

<style scoped>
.ai-chat-loading {
  display: flex;
  min-height: 240px;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--pm-muted);
  font-size: .78rem;
}

.ai-knowledge-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: -2px;
}

.ai-knowledge-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 7px;
  border-radius: 999px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.09);
  font-size: 0.66rem;
  font-weight: 650;
}

.ai-knowledge-badge--raw {
  color: var(--pm-muted);
  background: rgba(var(--v-theme-on-surface), 0.055);
}
</style>
