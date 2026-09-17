import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  MAX_NOTE_ARCHIVE_BYTES,
  isNoteArchiveFile,
  selectNoteArchiveFiles
} from '../src/utils/noteArchiveDrop.js';

const workspaceSource = await readFile(
  new URL('../src/views/NotesWorkspace.vue', import.meta.url),
  'utf8'
);

test('note archive drops accept PaperMind exports and JSON files', () => {
  assert.equal(isNoteArchiveFile({ name: 'Plan.papermind.json', type: '' }), true);
  assert.equal(isNoteArchiveFile({ name: 'Notiz.json', type: 'application/json' }), true);
});

test('note archive drops reject unrelated files', () => {
  const archive = { name: 'Notiz.papermind.json', type: 'application/json' };
  const pdf = { name: 'Dokument.pdf', type: 'application/pdf' };
  assert.deepEqual(selectNoteArchiveFiles([archive, pdf]), [archive]);
  assert.equal(MAX_NOTE_ARCHIVE_BYTES, 100 * 1024 * 1024);
});

test('notes list imports dropped archives through the existing notes API', () => {
  assert.match(workspaceSource, /@dragenter="onNoteImportDragEnter"/);
  assert.match(workspaceSource, /@drop="onNoteImportDrop"/);
  assert.match(workspaceSource, /await importNoteArchive\(file\)/);
  assert.match(workspaceSource, /class="notes-ws__drop-overlay-inner"[\s\S]*?Notizarchive hier ablegen/);
  assert.match(workspaceSource, /prefers-reduced-motion:\s*reduce[\s\S]*?notes-ws__drop-overlay-inner/);
});
