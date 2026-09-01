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

test('workspace exposes outline, in-note search, keyboard access, and highlighted results', () => {
  assert.doesNotMatch(workspaceSource, /aria-label="Gliederung öffnen"/);
  assert.equal((workspaceSource.match(/class="note-workspace-editor__navigation-toggle"/g) || []).length, 1);
  assert.match(workspaceSource, /aria-label="Gliederung und Suche öffnen"/);
  assert.match(workspaceSource, /@click="toggleNoteNavigation"/);
  assert.match(workspaceSource, /NOTE_NAVIGATION_MODE_STORAGE_KEY = 'pm-note-navigation-mode-v1'/);
  assert.match(workspaceSource, /localStorage\.setItem\(NOTE_NAVIGATION_MODE_STORAGE_KEY, mode\)/);
  assert.match(workspaceSource, /NOTE_NAVIGATION_OPEN_STORAGE_KEY = 'pm-note-navigation-open-v1'/);
  assert.match(workspaceSource, /navigationOpen = ref\(loadNoteNavigationOpen\(\)\)/);
  assert.match(workspaceSource, /localStorage\.getItem\(NOTE_NAVIGATION_OPEN_STORAGE_KEY\) === 'true'/);
  assert.match(workspaceSource, /localStorage\.setItem\(NOTE_NAVIGATION_OPEN_STORAGE_KEY, String\(Boolean\(open\)\)\)/);
  assert.match(workspaceSource, /navigationOpen\.value = true;[\s\S]*?persistNoteNavigationOpen\(true\)/);
  assert.match(workspaceSource, /navigationOpen\.value = false;[\s\S]*?persistNoteNavigationOpen\(false\)/);
  assert.match(workspaceSource, /event\.metaKey && !event\.ctrlKey/);
  assert.match(workspaceSource, /@keydown\.enter\.prevent="moveNoteSearch/);
  assert.match(workspaceSource, /Shift\+Enter/);
  assert.match(workspaceSource, /jumpToOutlineItem\(item\)/);
  assert.match(editorSource, /NoteSearch,/);
  assert.match(editorSource, /pm-note-search-match--active/);
  assert.match(editorSource, /scrollToDocumentPosition/);
});

test('dark mode keeps the navigator divider without a bright edge shadow', () => {
  assert.match(
    workspaceSource,
    /:global\(\.v-theme--dark\s+\.note-workspace-editor__navigator\)\s*{\s*box-shadow:\s*none;/,
  );
});

test('the right note navigator animates its width and slide transition', () => {
  assert.match(
    workspaceSource,
    /<Transition name="note-navigator">[\s\S]*?<aside[\s\S]*?v-if="navigationOpen"[\s\S]*?note-workspace-editor__navigator-content[\s\S]*?<\/aside>[\s\S]*?<\/Transition>/,
  );
  assert.match(
    workspaceSource,
    /\.note-navigator-enter-active,[\s\S]*?\.note-navigator-leave-active\s*{[\s\S]*?width 260ms[\s\S]*?min-width 260ms[\s\S]*?opacity 180ms[\s\S]*?transform 260ms/,
  );
  assert.match(
    workspaceSource,
    /\.note-navigator-enter-from,[\s\S]*?\.note-navigator-leave-to\s*{[\s\S]*?width:\s*0;[\s\S]*?min-width:\s*0;[\s\S]*?opacity:\s*0;[\s\S]*?translateX\(18px\)/,
  );
  assert.match(
    workspaceSource,
    /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.note-navigator-enter-active,[\s\S]*?\.note-navigator-leave-active\s*{\s*transition:\s*none;/,
  );
  assert.match(
    workspaceSource,
    /:global\(\.pm-no-animations\s+\.note-navigator-enter-active\),[\s\S]*?:global\(\.pm-no-animations\s+\.note-navigator-leave-active\)\s*{\s*transition:\s*none;/,
  );
  assert.match(
    workspaceSource,
    /\.note-workspace-editor__navigator\s*{[\s\S]*?--pm-note-navigator-width:\s*clamp\(270px, 27vw, 320px\);[\s\S]*?width:\s*var\(--pm-note-navigator-width\);[\s\S]*?overflow:\s*hidden;/,
  );
  assert.match(
    workspaceSource,
    /\.note-workspace-editor__navigator-content\s*{[\s\S]*?position:\s*absolute;[\s\S]*?inset:\s*0 0 0 auto;[\s\S]*?width:\s*var\(--pm-note-navigator-width\);[\s\S]*?min-width:\s*var\(--pm-note-navigator-width\);/,
  );
});
