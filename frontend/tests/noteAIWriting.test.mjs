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
const promptDefaultsSource = await readFile(
  new URL('../src/constants/promptDefaults.js', import.meta.url),
  'utf8',
);

test('toolbar shows the quiet natural-language AI prompt without an extra click', () => {
  assert.match(editorSource, /label: 'Mit KI schreiben'/);
  assert.match(editorSource, /kind: 'generate-ai'/);
  assert.match(editorSource, /terms: \['ki', 'ai', 'prompt'/);
  assert.match(editorSource, /<template v-if="aiAvailable">[\s\S]*?class="note-editor__toolbar-ai"/);
  assert.match(editorSource, /placeholder="Einfach losschreiben …"/);
  assert.match(editorSource, /@submit\.prevent="generateAIText"/);
  assert.match(editorSource, /@pointerdown\.stop="prepareToolbarAIPromptTarget"/);
  assert.doesNotMatch(editorSource, /<Teleport[^>]*>\s*<Transition name="pm-ai-prompt"/);
  assert.doesNotMatch(editorSource, /note-editor__toolbar-btn--ai/);
  assert.match(editorSource, /streamNoteText/);
});

test('toolbar AI prompt snapshots the current editor target before input focus', () => {
  assert.match(editorSource, /function prepareAIPromptTarget\(presentation = 'toolbar'/);
  assert.match(editorSource, /const selection = ed\.state\.selection/);
  assert.match(editorSource, /aiPrompt\.anchorPos = hasCaret[\s\S]*?directTarget\?\.anchorPos \?\? \(selectedText \? to : from\)/);
  assert.match(editorSource, /function ensureToolbarAIPromptTarget\(\)[\s\S]*?prepareToolbarAIPromptTarget\(\)/);
  assert.doesNotMatch(editorSource, /AIPromptAnchor|aiPromptMountEl|pm-ai-inline-anchor/);
});

test('toolbar AI prompt inserts at the caret, or at the note end when there is none', () => {
  // Ohne Editor-Fokus (keine Schreibmarke) hängt der Toolbar-Prompt den Text ans Ende.
  assert.match(editorSource, /const hasCaret = presentation !== 'toolbar' \|\| ed\.view\.hasFocus\(\)/);
  assert.match(
    editorSource,
    /aiPrompt\.anchorPos = hasCaret\s*\?\s*\(directTarget\?\.anchorPos \?\? \(selectedText \? to : from\)\)\s*:\s*ed\.state\.doc\.content\.size/,
  );
  // Ein Direkt-Container (Callout/Tabelle/Zitat) wird nur bei vorhandener Schreibmarke gesucht.
  assert.match(editorSource, /const directTarget = hasCaret \? directAITargetForSelection\(ed, selection\) : null/);
  // Der Einfügepunkt der Generierung folgt der Schreibmarke bzw. dem Notizende.
  assert.match(
    editorSource,
    /const insertionPos = Math\.min\(\s*aiPrompt\.anchorPos \?\? ed\.state\.selection\.from,\s*ed\.state\.doc\.content\.size,\s*\)/,
  );
});

test('slash and bubble AI actions open the complete prompt dialog', () => {
  assert.match(editorSource, /run: \(\) => openAIPrompt\(\)/);
  assert.match(editorSource, /if \(kind === 'generate-ai'\) \{ openAIPrompt\(\); return; \}/);
  assert.match(editorSource, /function openAIPrompt\(\) \{[\s\S]*?prepareAIPromptTarget\('dialog'/);
  assert.match(editorSource, /aiPrompt\.presentation === 'dialog'/);
  assert.match(editorSource, /class="pm-float pm-ai-prompt pm-ai-prompt--writing"/);
  assert.match(editorSource, /positionAIPrompt\(\)/);
});

test('AI writing and inline cleanup review open and close with subtle, reduced-motion-safe transitions', () => {
  // Nur der vollständige Prompt bleibt schwebend; Aufräumen sitzt im Textfluss.
  assert.equal((editorSource.match(/<Transition name="pm-ai-prompt">/g) || []).length, 2);
  assert.match(
    editorSource,
    /<Transition name="pm-ai-prompt">[\s\S]*?aiPrompt\.presentation === 'dialog'[\s\S]*?<\/Transition>/,
  );
  assert.match(editorSource, /<Teleport v-if="editor && cleanupAnchorEl" :to="cleanupAnchorEl">/);
  assert.match(editorSource, /<Transition name="pm-cleanup-review" appear>/);
  assert.match(editorSource, /class="pm-cleanup-review"/);
  assert.doesNotMatch(editorSource, /class="pm-float pm-ai-prompt pm-cleanup"/);
  assert.match(editorSource, /\.pm-ai-prompt-enter-active\s*\{[\s\S]*?opacity 160ms[\s\S]*?transform 180ms/);
  assert.match(editorSource, /\.pm-ai-prompt-leave-active\s*\{[\s\S]*?opacity 120ms[\s\S]*?transform 140ms/);
  assert.match(
    editorSource,
    /\.pm-ai-prompt-enter-from,[\s\S]*?\.pm-ai-prompt-leave-to\s*\{[\s\S]*?opacity:\s*0;[\s\S]*?translateY\(-6px\) scale\(0\.985\)/,
  );
  assert.match(
    editorSource,
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.pm-ai-prompt-enter-active,[\s\S]*?\.pm-ai-prompt-leave-active\s*\{\s*transition:\s*none;/,
  );
  assert.match(
    editorSource,
    /:global\(\.pm-no-animations \.pm-ai-prompt-enter-active\),[\s\S]*?:global\(\.pm-no-animations \.pm-ai-prompt-leave-active\)\s*\{\s*transition:\s*none;/,
  );
  // Der Fenstertitel nutzt die Standard-UI-Schrift statt Monospace bei normalem Abstand.
  assert.match(
    editorSource,
    /\.pm-ai-prompt__head\s*\{[\s\S]*?font-family:\s*inherit;[\s\S]*?letter-spacing:\s*normal;[\s\S]*?word-spacing:\s*normal;/,
  );
  assert.doesNotMatch(editorSource, /@keyframes pm-ai-prompt-in/);
  assert.doesNotMatch(editorSource, /animation:\s*pm-ai-prompt-in/);
  assert.match(editorSource, /\.pm-cleanup-review-enter-active\s*\{[\s\S]*?animation: pm-cleanup-review-appear 240ms/);
  assert.match(editorSource, /prefers-reduced-motion: reduce[\s\S]*?\.pm-cleanup-review-enter-active/);
});

test('the bubble broom immediately opens a controllable cleanup proposal in the text flow', () => {
  assert.match(editorSource, /key: 'ai-cleanup',[\s\S]*?label: 'Aufräumen \(sinnwahrend\)'[\s\S]*?icon: 'mdi-broom'[\s\S]*?run: \(\) => startCleanup\(\)/);
  assert.match(editorSource, /cleanup\.open = true;[\s\S]*?showCleanupReviewAnchor\(ed, cleanup\.anchorPos\);[\s\S]*?await requestCleanup\(\)/);
  assert.match(editorSource, /Vorschlag · noch nicht übernommen/);
  assert.match(editorSource, /Original[\s\S]*?Vergleich[\s\S]*?Bereinigt/);
  assert.match(editorSource, /v-model="cleanup\.draftBlocks\[index\]"/);
  assert.match(editorSource, /Ursprung wiederherstellen/);
});

test('cleanup accepts selected headings and list text without painting the review with the native selection', () => {
  assert.match(editorSource, /scoped && node\.isTextblock/);
  assert.match(editorSource, /node\.type\.name === 'codeBlock'/);
  assert.match(editorSource, /const contentFrom = pos \+ 1/);
  assert.match(editorSource, /const targetFrom = Math\.max\(from, contentFrom\)/);
  assert.match(editorSource, /showCleanupReviewAnchor\(ed, cleanup\.anchorPos\);[\s\S]*?ed\.commands\.setTextSelection\(selectionTo\)/);
  assert.match(editorSource, /Kein bereinigbarer Text gefunden\. Codeblöcke bleiben zum Schutz ihres Inhalts unverändert\./);
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

test('slash menu applies its keyboard selection atomically on Enter', () => {
  assert.match(editorSource, /if \(event\.key === 'Enter' \|\| event\.key === 'Tab'\) \{[\s\S]*?event\.preventDefault\(\);[\s\S]*?event\.stopPropagation\(\);[\s\S]*?runSlash\(entry\.command\);/);
  assert.match(editorSource, /cmd\.action\(ed\.chain\(\)\.focus\(\)\.deleteRange\(range\)\)\.run\(\)/);
  assert.doesNotMatch(editorSource, /deleteRange\(\{ from: slash\.from, to \}\)\.run\(\);[\s\S]*?cmd\.action\(ed\.chain\(\)\.focus\(\)\)\.run\(\)/);
});

test('generated text outside a direct-editing container is inserted as a permanently attributed AI block', () => {
  assert.match(editorSource, /\.insertAiBlock\(\{/);
  assert.match(editorSource, /provider: aiPrompt\.provider/);
  assert.match(editorSource, /model: aiPrompt\.model/);
  assert.match(aiNodeSource, /provider: \{ default: '' \}/);
  assert.match(aiNodeSource, /generatedAt: \{ default: null \}/);
  assert.match(aiViewSource, /KI-generiert/);
  assert.match(aiViewSource, /Übernehmen/);
  assert.match(aiViewSource, /noteMarkdownToTipTap/);
  assert.match(aiViewSource, /block\.type === 'bulletList'/);
  assert.match(editorSource, /emit\('history-checkpoint', 'ai'\)/);
  assert.match(workspaceEditorSource, /@history-checkpoint="markHistoryCheckpoint"/);
});

test('selected note text opens a dedicated selection-only AI workflow', () => {
  assert.match(editorSource, /aiPrompt\.mode = selectedText \? 'selection' : 'context'/);
  assert.match(editorSource, /aiPrompt\.mode === 'selection' \? '' : noteContextBeforeAnchor\(ed\)/);
  assert.match(editorSource, /selected_text: aiPrompt\.mode === 'selection' \? aiPrompt\.selectedText : ''/);
});

test('toolbar selection generation replaces in place while dialog offers both result actions', () => {
  assert.match(editorSource, /selectionSnapshotIsCurrent\(ed\)/);
  assert.match(editorSource, /if \(aiPrompt\.presentation === 'dialog'\) return;/);
  assert.match(editorSource, /applySelectionAIResult\('replace'\)/);
  assert.match(editorSource, /insertContentAt\(\{ from, to \}, \{ type: 'aiBlock', attrs \}\)/);
  assert.match(editorSource, /Auswahl ersetzen/);
  assert.match(editorSource, /Danach einfügen/);
});

test('AI started inside a callout inserts normal editable content directly into that callout', () => {
  assert.match(editorSource, /function directAITargetForSelection\(ed, selection\)/);
  assert.match(editorSource, /function insertDirectAIResult\(ed,/);
  assert.match(editorSource, /noteMarkdownToTipTap\(aiPrompt\.preview\.trim\(\)\)/);
  assert.match(editorSource, /targetReplaceFrom/);
  assert.match(editorSource, /insertDirectAIResult\(ed, replaceEmptyParagraph/);
  assert.match(editorSource, /Number\.isInteger\(aiPrompt\.targetContainerFrom\)/);

  const directInsertion = editorSource.slice(
    editorSource.indexOf('function insertDirectAIResult'),
    editorSource.indexOf('function applySelectionAIResult'),
  );
  assert.match(directInsertion, /insertContent(?:At)?\(/);
  assert.doesNotMatch(directInsertion, /insertAiBlock|type: 'aiBlock'/);
});

test('AI started inside a table cell uses the same direct editable insertion path', () => {
  assert.match(editorSource, /'tableCell',[\s\S]*?'tableHeader'/);
  assert.match(editorSource, /end\.type !== start\.type \|\| end\.from !== start\.from/);
  assert.match(editorSource, /node\?\.type\.name === type && from \+ node\.nodeSize === to/);
});

test('AI started inside a quote or code block is inserted directly without an AI block', () => {
  assert.match(editorSource, /'blockquote',[\s\S]*?'codeBlock'/);
  assert.match(editorSource, /noteAITextForCodeBlock\(aiPrompt\.preview\)/);
  assert.match(editorSource, /slash\.codeOnly[\s\S]*?command\.kind === 'generate-ai'/);
  assert.match(editorSource, /slash\.codeOnly = \$from\.parent\.type\.name === 'codeBlock'/);
});

test('AI writing has generation feedback without additional caret-like markers', () => {
  assert.match(editorSource, /'is-generating': aiPrompt\.loading/);
  assert.match(editorSource, /v-if="aiPrompt\.presentation === 'toolbar' && aiPrompt\.loading"[\s\S]*?class="note-editor__toolbar-ai-spinner"/);
  assert.match(editorSource, /v-if="aiPrompt\.loading" class="pm-ai-prompt__spinner"/);
  assert.doesNotMatch(editorSource, /pm-ai-anchor/);
  assert.doesNotMatch(editorSource, /pm-ai-prompt__stream-caret/);
  assert.match(editorSource, /insertAiBlock\([\s\S]*?focus\('end'\)[\s\S]*?scrollIntoView\(\)/);
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
  assert.match(editorSource, /!props\.aiAvailable && \(command\.kind === 'generate-ai' \|\| command\.kind === 'cleanup'\)/);
  assert.match(editorSource, /mdi-auto-fix/);
  assert.match(workspaceEditorSource, /:ai-available="aiAvailable"/);
  assert.match(workspaceEditorSource, /aiCredentialStatus\.value\?\.\[provider\]\?\.configured === true/);
  assert.match(workspaceEditorSource, /String\(config\[modelKey\] \|\| ''\)\.trim\(\)/);
});

test('complete AI dialog renders configured suggestion chips without adding them to the toolbar field', () => {
  assert.match(settingsSource, /Beispielprompts/);
  assert.match(settingsSource, /v-model="notePromptSuggestionsDraft\[index\]"/);
  assert.match(settingsSource, /notePromptSuggestionsDraft\.length >= 6/);
  assert.match(settingsSource, /prompt_suggestions: normalizedNotePromptSuggestionsDraft\.value/);
  assert.match(workspaceEditorSource, /:ai-prompt-suggestions="aiPromptSuggestions"/);
  assert.match(editorSource, /props\.aiPromptSuggestions/);
  assert.match(editorSource, /class="pm-ai-prompt__suggestions"/);
});

test('AI writing offers a table prompt backed by valid Markdown guidance', () => {
  assert.match(promptDefaultsSource, /Als Tabelle strukturieren/);
  assert.match(promptDefaultsSource, /gültige Markdown-Tabelle/);
});

test('AI dialog and toolbar options control output length', () => {
  assert.match(editorSource, /aiPrompt\.lengthLevel/);
  assert.match(editorSource, /class="pm-ai-prompt__length"/);
  assert.match(editorSource, /type="range"/);
  assert.match(editorSource, /\{ label: 'Automatisch', lineHint: 'nach Prompt', instruction: '' \}/);
  assert.match(editorSource, /\{ label: 'Kurz', lineHint: 'ca\. 1–3 Zeilen'/);
  assert.match(editorSource, /\{ label: 'Mittel', lineHint: 'ca\. 4–8 Zeilen'/);
  assert.match(editorSource, /\{ label: 'Lang', lineHint: 'ca\. 9–16 Zeilen'/);
  assert.match(editorSource, /lengthLevel: 0/);
  assert.match(editorSource, /activeAILengthOption\.label \}\} · \{\{ activeAILengthOption\.lineHint/);
  assert.match(editorSource, /length_instruction: activeAILengthOption\.value\.instruction/);
});
