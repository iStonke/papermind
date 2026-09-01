import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  NOTE_CALLOUT_OPTIONS,
  normalizeNoteCalloutKind,
  noteCalloutMeta,
} from '../src/utils/noteCallouts.js';

const nodeSource = await readFile(
  new URL('../src/components/notes/nodes/callout.js', import.meta.url),
  'utf8',
);
const viewSource = await readFile(
  new URL('../src/components/notes/nodes/CalloutView.vue', import.meta.url),
  'utf8',
);
const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const previewSource = await readFile(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);

test('PaperMind exposes the five structured callout kinds', () => {
  assert.deepEqual(
    NOTE_CALLOUT_OPTIONS.map(({ value, label }) => ({ value, label })),
    [
      { value: 'important', label: 'Wichtig' },
      { value: 'question', label: 'Frage' },
      { value: 'decision', label: 'Entscheidung' },
      { value: 'deadline', label: 'Frist' },
      { value: 'source', label: 'Fundstelle' },
    ],
  );
  assert.equal(normalizeNoteCalloutKind('decision'), 'decision');
  assert.equal(normalizeNoteCalloutKind('unknown'), 'important');
  assert.equal(noteCalloutMeta('source').label, 'Fundstelle');
});

test('callouts remain editable structured nodes and can change kind', () => {
  assert.match(nodeSource, /name: 'callout'/);
  assert.match(nodeSource, /content: 'block\+'/);
  assert.match(nodeSource, /data-callout/);
  assert.match(nodeSource, /insertCallout/);
  assert.match(nodeSource, /setCalloutKind/);
  assert.match(viewSource, /<node-view-content class="pm-callout__content"/);
  assert.match(viewSource, /props\.updateAttributes\(\{ kind:/);
  assert.match(viewSource, /editor\.isEditable/);
});

test('new callouts stage their accent line, glyph and content without replaying later', () => {
  assert.match(nodeSource, /insertedAt: \{/);
  assert.match(nodeSource, /insertedAt: new Date\(\)\.toISOString\(\)/);
  assert.match(viewSource, /'is-arriving': isArriving/);
  assert.match(viewSource, /props\.editor\.isEditable/);
  assert.match(viewSource, /Math\.abs\(Date\.now\(\) - insertedAt\) <= 4000/);
  assert.match(viewSource, /pm-callout-line-grow/);
  assert.match(viewSource, /pm-callout-glyph-arrive/);
  assert.match(viewSource, /pm-callout-content-arrive/);
  assert.match(viewSource, /prefers-reduced-motion: reduce/);
  assert.match(viewSource, /pm-no-animations/);
});

test('callouts are available through slash commands and in read-only previews', () => {
  assert.match(editorSource, /NOTE_CALLOUT_OPTIONS\.map/);
  assert.match(editorSource, /chain\.insertCallout\(option\.value\)/);
  assert.match(editorSource, /Callout,/);
  assert.match(previewSource, /Callout,/);
  assert.match(viewSource, /is-question/);
  assert.match(viewSource, /is-decision/);
  assert.match(viewSource, /is-deadline/);
  assert.match(viewSource, /is-source/);
});

test('slash commands are grouped without breaking their flat keyboard index', () => {
  assert.match(editorSource, /key: 'frequent',[\s\S]*?label: 'Häufig benutzt'/);
  assert.match(editorSource, /frequentSlashCommands\.value\.filter/);
  assert.match(editorSource, /recordSlashCommandUsage\(cmd\.key\)/);
  assert.match(editorSource, /label: 'PaperMind'/);
  assert.match(editorSource, /label: 'Hinweisblöcke'/);
  assert.match(editorSource, /label: 'Überschriften'/);
  assert.match(editorSource, /label: 'Listen & Blöcke'/);
  assert.match(editorSource, /const slashGroups = computed/);
  assert.match(editorSource, /const slashMenuEntries = computed/);
  assert.match(editorSource, /index: flatIndex\+\+/);
  assert.match(editorSource, /v-for="group in slashGroups"/);
  assert.match(editorSource, /entry\.index === slash\.index/);
  assert.match(editorSource, /runSlash\(entry\.command\)/);
  assert.match(editorSource, /const entry = entries\[slash\.index\] \|\| entries\[0\];[\s\S]*?runSlash\(entry\.command\)/);
  assert.match(editorSource, /\.pm-slash__group \+ \.pm-slash__group/);
  assert.match(editorSource, /'is-frequent': group\.key === 'frequent'/);
  assert.match(editorSource, /\.pm-slash__group\.is-frequent \.pm-slash__chip/);
  assert.match(editorSource, /--pm-frequent-accent/);
  assert.match(
    editorSource,
    /label: 'Hinweisblöcke'[\s\S]*label: 'Überschriften'[\s\S]*label: 'Listen & Blöcke'[\s\S]*label: 'PaperMind'/,
  );
});

test('keyboard navigation keeps the active slash action inside the visible menu', () => {
  assert.match(editorSource, /ref="slashMenuEl"/);
  assert.match(editorSource, /:data-slash-index="entry\.index"/);
  assert.match(editorSource, /moveSlashSelection\(1, n\)/);
  assert.match(editorSource, /moveSlashSelection\(-1, n\)/);
  assert.match(editorSource, /menu\.scrollTop [+-]=/);
});

test('heading actions use the note title as H1 and expose H2 through H4', () => {
  assert.doesNotMatch(editorSource, /key: 'h1', group: 'headings'/);
  assert.doesNotMatch(editorSource, /mk\('h1'/);
  assert.match(editorSource, /key: 'h4', group: 'headings'/);
  assert.match(editorSource, /runToolbar\('h4'\)/);
  assert.match(editorSource, /toggleHeading\(\{ level: 4 \}\)/);
  assert.match(editorSource, /heading: \{ levels: \[1, 2, 3, 4\] \}/);
  assert.match(previewSource, /heading: \{ levels: \[1, 2, 3, 4\] \}/);
});
