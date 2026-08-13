import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const toggleSource = await readFile(new URL('../src/components/AiKnowledgeToggle.vue', import.meta.url), 'utf8');
const sidebarSource = await readFile(new URL('../src/components/AppSidebar.vue', import.meta.url), 'utf8');
const workspaceSource = await readFile(new URL('../src/views/DocumentsWorkspace.vue', import.meta.url), 'utf8');
const knowledgeSource = await readFile(new URL('../src/views/WikiWorkspace.vue', import.meta.url), 'utf8');
const routerSource = await readFile(new URL('../src/router/index.js', import.meta.url), 'utf8');
const settingsSource = await readFile(new URL('../src/components/SettingsDialog.vue', import.meta.url), 'utf8');
const commandsSource = await readFile(new URL('../src/components/commandPalette/commands.js', import.meta.url), 'utf8');
const aiDialogSource = await readFile(new URL('../src/components/AiDialog.vue', import.meta.url), 'utf8');
const knowledgeStageSource = await readFile(new URL('../src/components/KnowledgeStage.vue', import.meta.url), 'utf8');

test('knowledge is an accessible mode of Wissen instead of a separate sidebar destination', () => {
  // Chat ↔ Wissen ist ein Moduswechsel (kein eigener Sidebar-Eintrag): Einstieg
  // ins Wissen über die Chat-Bühne (openKnowledgeArea), Rückweg über den
  // "Zum Chat"-Link in der Wissen-Toolbar (setAiWorkspaceMode('chat')).
  assert.match(workspaceSource, /isChatView \|\| isWikiRoute/);
  assert.match(workspaceSource, /openKnowledgeArea/);
  assert.match(workspaceSource, /setAiWorkspaceMode/);
  assert.match(knowledgeSource, /wiki-toolbar__back/);
  assert.match(knowledgeSource, /show-chat/);
  assert.doesNotMatch(workspaceSource, /<AiKnowledgeToggle/);
  assert.doesNotMatch(sidebarSource, /open-wiki|wikiActive|sidebar-item--wiki/);
});

test('legacy knowledge links still open the integrated mode', () => {
  assert.match(routerSource, /path: 'wissen'/);
  assert.match(workspaceSource, /route\.name === 'wiki'/);
  assert.match(workspaceSource, /@show-chat="setAiWorkspaceMode\('chat'\)"/);
});

test('knowledge UI keeps trust controls while removing secondary dashboards and filters', () => {
  assert.match(knowledgeSource, /Revision \{\{/);
  assert.match(knowledgeSource, /Fakt korrigieren/);
  assert.match(knowledgeSource, /Fakt zurückziehen/);
  assert.match(knowledgeSource, /Zu prüfen/);
  assert.match(knowledgeSource, /belegt/);
  assert.doesNotMatch(knowledgeSource, /wiki-metrics|wiki-filter-row|wiki-rendered|wiki-links/);
});

test('knowledge base uses the simplified PaperMind split view with source-backed facts', () => {
  assert.match(knowledgeSource, /class="wiki-toolbar__views"/);
  assert.match(knowledgeSource, /class="wiki-nav"/);
  assert.match(knowledgeSource, /Quelle · /);
  assert.match(knowledgeSource, /var\(--pm-content-surface\)/);
  assert.match(knowledgeSource, /var\(--pm-app-surface-raised\)/);
  assert.match(knowledgeSource, /var\(--pm-divider\)/);
  assert.doesNotMatch(knowledgeSource, /wiki-review-button/);
});

test('large knowledge backfills start as a canary and remain controllable', () => {
  assert.match(knowledgeSource, /Testlauf mit 20 Dokumenten/);
  assert.match(knowledgeSource, /Alle Dokumente abgleichen/);
  assert.match(knowledgeSource, /batchSize: 1, documentLimit/);
  assert.match(knowledgeSource, /controlBackfill\('pause'\)/);
  assert.match(knowledgeSource, /controlBackfill\('resume'\)/);
  assert.match(knowledgeSource, /controlBackfill\('cancel'\)/);
  assert.match(knowledgeSource, /aktuell begonnene Dokument darf noch sauber abschließen/);
});

test('the former KI-Chat is named Wissen in every user-facing entry point', () => {
  const userFacingSources = [toggleSource, sidebarSource, workspaceSource, knowledgeSource, settingsSource, commandsSource];
  assert.match(sidebarSource, />\s*Wissen\s*</);
  assert.match(workspaceSource, /chat: 'Wissen'/);
  assert.match(settingsSource, /title="Wissen"/);
  assert.match(settingsSource, /Wissen in der Seitenleiste anzeigen/);
  assert.match(commandsSource, /label: 'Wissen'/);
  assert.match(toggleSource, />Wissensbasis</);
  for (const source of userFacingSources) {
    assert.doesNotMatch(source, /KI[- ]Chat/i);
  }
});

test('assistant answers use the robot icon instead of the PM monogram', () => {
  assert.match(aiDialogSource, /class="ai-avatar"[\s\S]*?<v-icon size="16">mdi-robot-outline<\/v-icon>/);
  assert.doesNotMatch(aiDialogSource, /class="ai-avatar"[^>]*>PM<\/div>/);
});

test('Wissen uses changing graphical examples without the old text-heavy prompt showcase', () => {
  // Der Chat-Leerzustand ist die grafische Wissens-Bühne (KnowledgeStage): Canvas-
  // Konstellation + wechselnde Prompt-Karten aus Wissensseiten/Tags/Dokumenttypen.
  assert.match(workspaceSource, /<KnowledgeStage/);
  assert.match(knowledgeStageSource, /class="kstage__canvas"/);
  assert.match(knowledgeStageSource, /class="kstage__prompt"/);
  assert.match(workspaceSource, /function refreshStagePrompts\(\)/);
  assert.match(workspaceSource, /sortedCategories\.value/);
  assert.match(workspaceSource, /tags\.value/);
  assert.match(workspaceSource, /:show-drawer="[^"]*\(!isChatView \|\| chatPreviewVisible\)"/);
  assert.doesNotMatch(workspaceSource, /chat-showcase|chatShowcasePrompts|pmRot|pmBreath|pmDrift|pmSweep/);
});
