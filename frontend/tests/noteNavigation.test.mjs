import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { findNoteSearchRanges } from '../src/components/notes/extensions/noteSearch.js';
import { extractNoteOutline, nextWrappedIndex } from '../src/utils/noteNavigation.js';

const workspaceSource = await readFile(
  new URL('../src/components/notes/NoteWorkspaceEditor.vue', import.meta.url),
  'utf8',
);
const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);

test('outline extracts H2 through H4 with ProseMirror document positions', () => {
  const body = {
    type: 'doc',
    content: [
      { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Start' }] },
      { type: 'paragraph', content: [{ type: 'text', text: 'Text' }] },
      {
        type: 'blockquote',
        content: [{
          type: 'heading',
          attrs: { level: 3 },
          content: [
            { type: 'text', text: 'Unter', marks: [{ type: 'bold' }] },
            { type: 'text', text: 'punkt' },
          ],
        }],
      },
      { type: 'heading', attrs: { level: 1 }, content: [{ type: 'text', text: 'Altbestand' }] },
      { type: 'heading', attrs: { level: 4 }, content: [{ type: 'text', text: 'Detail' }] },
    ],
  };

  assert.deepEqual(
    extractNoteOutline(body).map(({ level, text, position }) => ({ level, text, position })),
    [
      { level: 2, text: 'Start', position: 0 },
      { level: 3, text: 'Unterpunkt', position: 14 },
      { level: 4, text: 'Detail', position: 39 },
    ],
  );
});

test('note search matches case-insensitively and wraps result navigation', () => {
  const doc = {
    descendants(callback) {
      callback({
        isTextblock: true,
        descendants(innerCallback) {
          innerCallback({ isText: true, text: 'Pap' }, 0);
          innerCallback({ isText: true, text: 'ier papier' }, 3);
        },
      }, 0);
      callback({
        isTextblock: true,
        descendants(innerCallback) {
          innerCallback({ isText: true, text: 'PAPIER unrelated' }, 0);
        },
      }, 20);
    },
  };

  assert.deepEqual(findNoteSearchRanges(doc, 'papier'), [
    { from: 1, to: 7 },
    { from: 8, to: 14 },
    { from: 21, to: 27 },
  ]);
  assert.equal(nextWrappedIndex(0, 3, 1), 1);
  assert.equal(nextWrappedIndex(2, 3, 1), 0);
  assert.equal(nextWrappedIndex(0, 3, -1), 2);
  assert.equal(nextWrappedIndex(0, 0, 1), -1);
});

test('workspace exposes an inline find-and-replace bar with highlighted results', () => {
  // Die rechte Navigator-Seitenleiste (Gliederung + Suche) ist entfallen.
  assert.doesNotMatch(workspaceSource, /note-workspace-editor__navigator\b/);
  assert.doesNotMatch(workspaceSource, /note-navigator/);
  // Schwebende Suchen-&-Ersetzen-Leiste ersetzt sie:
  assert.match(workspaceSource, /class="note-workspace-editor__find"/);
  assert.match(workspaceSource, /v-if="findBarOpen"/);
  assert.match(workspaceSource, /v-model="noteSearchQuery"/);
  assert.match(workspaceSource, /@keydown\.enter\.prevent="moveNoteSearch\(\$event\.shiftKey \? -1 : 1\)"/);
  assert.match(workspaceSource, /Shift\+Enter/);
  // Ersetzen:
  assert.match(workspaceSource, /v-model="replaceValue"/);
  assert.match(workspaceSource, /placeholder="Ersetzen durch"/);
  assert.match(workspaceSource, /@click="doReplaceActive"/);
  assert.match(workspaceSource, /@click="doReplaceAll"/);
  // Toggle-Button + Tastatur (Cmd/Ctrl+F):
  assert.match(workspaceSource, /aria-label="Suchen und ersetzen"/);
  assert.match(workspaceSource, /@click="toggleFindBar"/);
  assert.match(workspaceSource, /event\.metaKey && !event\.ctrlKey/);
  assert.match(workspaceSource, /openFindBar\(\)/);
  // Editor-Engine: Suche, Ersetzen, Treffer-Hervorhebung.
  assert.match(editorSource, /NoteSearch,/);
  assert.match(editorSource, /pm-note-search-match--active/);
  assert.match(editorSource, /replaceActiveNoteSearch/);
  assert.match(editorSource, /replaceAllNoteSearch/);
});

test('find-and-replace bar enters and leaves with subtle reduced-motion-safe animation', () => {
  assert.match(
    workspaceSource,
    /<Transition name="note-find">[\s\S]*?v-if="findBarOpen"[\s\S]*?<\/Transition>/,
  );
  assert.match(
    workspaceSource,
    /\.note-find-enter-active\s*{[\s\S]*?opacity 160ms[\s\S]*?transform 180ms/,
  );
  assert.match(
    workspaceSource,
    /\.note-find-leave-active\s*{[\s\S]*?opacity 120ms[\s\S]*?transform 140ms/,
  );
  assert.match(
    workspaceSource,
    /\.note-find-enter-from,[\s\S]*?\.note-find-leave-to\s*{[\s\S]*?opacity:\s*0;[\s\S]*?translateY\(-5px\) scale\(0\.985\)/,
  );
  assert.match(
    workspaceSource,
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.note-find-enter-active,[\s\S]*?\.note-find-leave-active\s*{\s*transition:\s*none;/,
  );
  assert.match(
    workspaceSource,
    /:global\(\.pm-no-animations \.note-find-enter-active\),[\s\S]*?:global\(\.pm-no-animations \.note-find-leave-active\)\s*{\s*transition:\s*none;/,
  );
});
