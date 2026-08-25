import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const aiNodeSource = await readFile(
  new URL('../src/components/notes/nodes/aiBlock.js', import.meta.url),
  'utf8',
);
const aiViewSource = await readFile(
  new URL('../src/components/notes/nodes/AiBlockView.vue', import.meta.url),
  'utf8',
);
const notesApiSource = await readFile(new URL('../src/api/notes.js', import.meta.url), 'utf8');
const settingsSource = await readFile(
  new URL('../src/components/SettingsDialog.vue', import.meta.url),
  'utf8',
);
const workspaceEditorSource = await readFile(
  new URL('../src/components/notes/NoteWorkspaceEditor.vue', import.meta.url),
  'utf8',
);

test('slash menu opens a compact natural-language AI writing prompt', () => {
  assert.match(editorSource, /label: 'Mit KI schreiben'/);
  assert.match(editorSource, /kind: 'generate-ai'/);
  assert.match(editorSource, /terms: \['ki', 'ai', 'prompt'/);
  assert.match(editorSource, /Was soll PaperMind schreiben\?/);
  assert.match(editorSource, /visibleAIPromptSuggestions/);
  assert.match(editorSource, /streamNoteText/);
});

test('slash menu unfolds at the cursor and glides its active selection', () => {
  assert.match(editorSource, /pm-slash pm-slash--commands/);
  assert.match(editorSource, /class="pm-slash__selection"/);
  assert.match(editorSource, /function updateSlashSelection\(\)/);
  assert.match(editorSource, /const menuScale = menu\.offsetWidth \? menuRect\.width \/ menu\.offsetWidth : 1/);
  assert.match(editorSource, /transform: `translateY\(\$\{\(itemRect\.top - menuRect\.top\) \/ menuScale \+ menu\.scrollTop\}px\)`/);
  assert.match(editorSource, /@keyframes pm-slash-open/);
  assert.match(editorSource, /translateY\(-10px\) scale\(0\.925\)/);
  assert.match(editorSource, /translateY\(1px\) scale\(1\.012\)/);
  assert.match(editorSource, /\.pm-slash__item\.is-active \.pm-slash__chip/);
  assert.match(editorSource, /\.pm-slash__selection \{[\s\S]*?transform 165ms/);
  assert.match(editorSource, /prefers-reduced-motion: reduce[\s\S]*?\.pm-slash--commands/);
});

test('generated text is inserted as a permanently attributed AI block', () => {
  assert.match(editorSource, /\.insertAiBlock\(\{/);
  assert.match(editorSource, /provider: aiPrompt\.provider/);
  assert.match(editorSource, /model: aiPrompt\.model/);
  assert.match(aiNodeSource, /provider: \{ default: '' \}/);
  assert.match(aiNodeSource, /generatedAt: \{ default: null \}/);
  assert.match(aiViewSource, /KI-generiert/);
  assert.match(aiViewSource, /Übernehmen/);
  assert.match(aiViewSource, /noteMarkdownToTipTap/);
  assert.match(aiViewSource, /block\.type === 'bulletList'/);
});

test('selected note text opens a dedicated selection-only AI workflow', () => {
  assert.match(editorSource, /label: 'Auswahl mit KI bearbeiten'/);
  assert.match(editorSource, /aiPrompt\.mode = selectedText \? 'selection' : 'context'/);
  assert.match(editorSource, /Kontext: nur Auswahl/);
  assert.match(editorSource, /Kontext: Notiztext bis zum Cursor/);
  assert.match(editorSource, /note_context: aiPrompt\.mode === 'selection' \? '' : noteContextBeforeAnchor\(ed\)/);
  assert.match(editorSource, /selected_text: aiPrompt\.mode === 'selection' \? aiPrompt\.selectedText : ''/);
});

test('selection AI result requires an explicit replace or insert action', () => {
  assert.match(editorSource, /Auswahl ersetzen/);
  assert.match(editorSource, /Danach einfügen/);
  assert.match(editorSource, /selectionSnapshotIsCurrent\(ed\)/);
  assert.match(editorSource, /insertContentAt\(\{ from, to \}, \{ type: 'aiBlock', attrs \}\)/);
});

test('AI writing has state-driven, reduced-motion-safe generation feedback', () => {
  assert.match(editorSource, /aiPrompt\.open && aiPrompt\.loading/);
  assert.match(editorSource, /class="pm-ai-anchor"/);
  assert.match(editorSource, /class="pm-ai-prompt__progress"/);
  assert.match(editorSource, /class="pm-ai-prompt__stream-caret"/);
  assert.match(editorSource, /prefers-reduced-motion: reduce/);
  assert.match(aiViewSource, /'is-arriving': isArriving/);
  assert.match(aiViewSource, /Math\.abs\(Date\.now\(\) - generatedAt\) > 4000/);
  assert.match(aiViewSource, /pm-aiblock-sweep/);
  assert.match(aiViewSource, /--pm-ai-arrival-delay/);
  assert.match(aiViewSource, /prefers-reduced-motion: reduce/);
});

test('note AI client consumes streamed NDJSON without exposing credentials', () => {
  assert.match(notesApiSource, /application\/x-ndjson|split\('\\n'\)/);
  assert.match(notesApiSource, /event\.type === 'error'/);
  assert.doesNotMatch(notesApiSource, /api[_-]?key/i);
});

test('cloud credentials can be saved without exposing infrastructure setup', () => {
  assert.match(settingsSource, /:disabled="!activeCredentialDraft\.trim\(\) \|\| aiCredentialsSaving"/);
  assert.match(settingsSource, /activeCredentialStatus\.masked \|\| '••••••••••••'/);
  assert.doesNotMatch(settingsSource, /AI_CREDENTIALS_ENCRYPTION_KEY oder BACKUP_ENCRYPTION_KEY/);
});

test('AI writing controls only appear for a usable provider and model', () => {
  assert.match(editorSource, /v-if="aiAvailable"/);
  assert.match(editorSource, /!props\.aiAvailable && command\.kind === 'generate-ai'/);
  assert.match(editorSource, /mdi-auto-fix/);
  assert.match(workspaceEditorSource, /:ai-available="aiAvailable"/);
  assert.match(workspaceEditorSource, /aiCredentialStatus\.value\?\.\[provider\]\?\.configured === true/);
  assert.match(workspaceEditorSource, /String\(config\[modelKey\] \|\| ''\)\.trim\(\)/);
});

test('AI prompt suggestion chips are globally configurable and capped at six', () => {
  assert.match(settingsSource, /Beispielprompts/);
  assert.match(settingsSource, /v-model="notePromptSuggestionsDraft\[index\]"/);
  assert.match(settingsSource, /notePromptSuggestionsDraft\.length >= 6/);
  assert.match(settingsSource, /prompt_suggestions: normalizedNotePromptSuggestionsDraft\.value/);
  assert.match(workspaceEditorSource, /:ai-prompt-suggestions="aiPromptSuggestions"/);
  assert.match(editorSource, /props\.aiPromptSuggestions/);
  assert.match(editorSource, /\.slice\(0, 6\)/);
});
