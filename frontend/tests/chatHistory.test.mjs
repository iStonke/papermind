import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  archiveChatSession,
  getChatSession,
  getLatestChatSession,
  listChatSessions,
} from '../src/api/ai.js';
import { setToken } from '../src/api/client.js';

const dialogSource = await readFile(new URL('../src/components/AiDialog.vue', import.meta.url), 'utf8');
const workspaceSource = await readFile(new URL('../src/views/DocumentsWorkspace.vue', import.meta.url), 'utf8');
const searchSource = await readFile(new URL('../src/composables/useSearch.js', import.meta.url), 'utf8');
const knowledgeStageSource = await readFile(new URL('../src/components/KnowledgeStage.vue', import.meta.url), 'utf8');

test('chat history API loads, lists and archives owner-scoped sessions with authentication', async () => {
  const previousFetch = globalThis.fetch;
  const calls = [];
  setToken('chat-test-token');
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => [],
    };
  };

  try {
    await listChatSessions({ limit: 20 });
    await getLatestChatSession({ messageLimit: 300 });
    await getChatSession('session-1', { messageLimit: 100 });
    await archiveChatSession('session-1');
  } finally {
    globalThis.fetch = previousFetch;
    setToken('');
  }

  assert.equal(calls[0].url, '/api/ai/sessions?limit=20');
  assert.equal(calls[1].url, '/api/ai/sessions/latest?message_limit=300');
  assert.equal(calls[2].url, '/api/ai/sessions/session-1?message_limit=100');
  assert.equal(calls[3].url, '/api/ai/sessions/session-1/archive');
  assert.equal(calls[3].options.method, 'POST');
  assert.equal(calls[3].options.headers.Authorization, 'Bearer chat-test-token');
  assert.ok(calls.every((call) => call.options.signal instanceof AbortSignal));
});

test('chat UI restores the selected session and starts new chats without deleting history', () => {
  assert.match(dialogSource, /historyInitializationPromise = initializeChatHistory\(\)/);
  assert.match(dialogSource, /CHAT_SESSION_STORAGE_KEY/);
  assert.match(dialogSource, /await getChatSession\(storedSessionId\)/);
  assert.match(dialogSource, /await archiveChatSession\(aiSessionId\.value\)/);
  assert.match(workspaceSource, /Gespeicherte Chats/);
  assert.match(workspaceSource, /Neuer Chat/);
});

test('chat controls live in the primary header without a separate save-state toolbar', () => {
  assert.doesNotMatch(dialogSource, /<Teleport|chat-header-controls/);
  assert.match(workspaceSource, /<div v-if="isChatView" class="panel-middle__actions panel-middle__actions--chat">/);
  assert.match(workspaceSource, /class="list-header-viewmode"\s+icon="mdi-clock-outline"\s+density="comfortable"/);
  assert.match(workspaceSource, /class="list-header-btn"\s+color="primary"\s+variant="tonal"/);
  assert.match(workspaceSource, /<v-icon size="18" class="mr-1">mdi-plus<\/v-icon>/);
  assert.doesNotMatch(workspaceSource, /ai-chat-header-btn|chat-header-controls/);
  assert.doesNotMatch(dialogSource, /Verlauf gespeichert/);
  assert.doesNotMatch(dialogSource, /ai-chat-save-state/);
  assert.doesNotMatch(dialogSource, /ai-chat-toolbar/);
});

test('chat mounts synchronously outside the panel transition to avoid null component instances', () => {
  assert.match(workspaceSource, /import AiDialog from '\.\.\/components\/AiDialog\.vue';/);
  assert.doesNotMatch(workspaceSource, /defineAsyncComponent\(\(\) => import\('\.\.\/components\/AiDialog\.vue'\)\)/);
  assert.match(workspaceSource, /<AiDialog\s+v-else-if="isChatView"[\s\S]*?\/>\s*<Transition v-else name="pm-panel">/);
});

test('empty chat stays visible while the initial history lookup is running', () => {
  assert.match(dialogSource, /v-if="isVisibleSessionLoading"/);
  assert.match(dialogSource, /v-else class="ai-chat-empty"/);
  assert.match(dialogSource, /const isVisibleSessionLoading = computed\(\(\) => isLoadingSession\.value && aiMessages\.value\.length > 0\)/);
  assert.match(dialogSource, /historyInitializationPromise && isLoadingSession\.value && aiMessages\.value\.length === 0/);
});

test('entering Wissen cannot activate an outgoing document skeleton', () => {
  assert.match(workspaceSource, /const showDocumentListLoadingState = computed\(\(\) =>\s*!isChatView\.value/s);
  assert.match(workspaceSource, /if \(isChatView\.value \|\| isTagView\.value \|\| isCategoryView\.value\)/);
  assert.match(searchSource, /activeView\.value === 'chat'/);
  assert.match(knowledgeStageSource, /drawFrame\(window\.performance\?\.now\?\.\(\) \|\| 0\)/);
  assert.doesNotMatch(knowledgeStageSource, /kstage-enter/);
  assert.doesNotMatch(knowledgeStageSource, /backdrop-filter:/);
});

test('chat composer is narrow and floats above a softly veiled history', () => {
  assert.match(workspaceSource, /\.ai-chat-panel\s*{[^}]*position: relative;[^}]*grid-template-rows: 1fr;/s);
  assert.match(workspaceSource, /\.ai-chat-panel::after\s*{[^}]*height: 150px;[^}]*linear-gradient/s);
  assert.doesNotMatch(workspaceSource, /\.ai-chat-panel::after\s*{[^}]*(?:backdrop-filter|mask-image):/s);
  assert.match(workspaceSource, /\.ai-chat-history\s*{[^}]*padding: 18px 18px 128px;/s);
  assert.match(workspaceSource, /\.ai-chat-input\s*{[^}]*position: absolute;[^}]*bottom: 28px;[^}]*width: min\(520px, calc\(100% - 36px\)\);/s);
  assert.match(workspaceSource, /\.ai-chat-input \.v-field\s*{[^}]*border-radius: 18px;/s);
  assert.match(workspaceSource, /\.ai-chat-input \.v-field__outline\s*{[^}]*color: rgb\(var\(--v-theme-primary\)\);[^}]*--v-field-border-opacity: 1;/s);
  assert.doesNotMatch(workspaceSource, /\.ai-chat-input \.v-field(?:--focused)?\s*{[^}]*0 0 0 [12]px/s);
  assert.doesNotMatch(workspaceSource, /\.ai-chat-input \.v-field\s*{[^}]*backdrop-filter:/s);
  assert.doesNotMatch(workspaceSource, /\.ai-chat-input\s*{[^}]*border-top:/s);
});

test('chat restoration has a bounded payload, timeout and recoverable error state', () => {
  assert.match(dialogSource, /v-else-if="historyLoadError"/);
  assert.match(dialogSource, /@click="initializeChatHistory"/);
  assert.match(dialogSource, /historyLoadError\.value = error\?\.code === 'REQUEST_TIMEOUT'/);
  assert.match(dialogSource, /CHAT_HISTORY_WATCHDOG_MS = 7000/);
  assert.match(dialogSource, /window\.setTimeout\(\(\) => \{[^}]*isLoadingSession\.value = false;/s);
  assert.match(dialogSource, /onBeforeUnmount\(\(\) => \{/);
});
