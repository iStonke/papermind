import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { noteContentToPlainText, noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

const slideSource = await read('../src/components/notes/nodes/lectureSlide.js');
const mediaViewSource = await read('../src/components/notes/nodes/LectureSlideMediaView.vue');
const editorSource = await read('../src/components/notes/NoteEditor.vue');
const previewSource = await read('../src/components/notes/NotePreview.vue');
const workspaceEditorSource = await read('../src/components/notes/NoteWorkspaceEditor.vue');
const notesWorkspaceSource = await read('../src/views/NotesWorkspace.vue');
const documentNodeSource = await read('../src/components/notes/nodes/noteDocument.js');
const cssSource = await read('../src/components/notes/styles/lectureSlide.css');

test('lecture slide pairs a regular image node with block notes', () => {
  assert.match(slideSource, /content: 'lectureSlideMedia lectureSlideNotes'/);
  // Gewöhnlicher image-Knoten → Upload, Kopieren und Archiv-Export unverändert.
  assert.match(slideSource, /name: 'lectureSlideMedia',\s*content: 'image\?'/);
  assert.match(slideSource, /name: 'lectureSlideNotes',\s*content: 'block\+'/);
  assert.match(slideSource, /insertLectureSlide:/);
  assert.match(slideSource, /setLectureSlideImage:/);
  assert.match(mediaViewSource, /Screenshot einfügen/);
  assert.match(mediaViewSource, /extension\.options\.onRequestImage\?\.\(props\.getPos\(\)\)/);
});

test('lecture mode is a note attribute that only switches the presentation', () => {
  assert.match(documentNodeSource, /lectureMode: \{ default: false \}/);
  assert.match(editorSource, /'note-editor--lecture pm-lecture-mode': lectureMode/);
  assert.match(previewSource, /'pm-lecture-mode': Boolean\(bodyJson\?\.attrs\?\.lectureMode\)/);
  assert.match(cssSource, /\.pm-lecture-mode \.pm-lecture-slide__columns \{[\s\S]*?grid-template-columns: repeat\(auto-fit/);
  assert.match(workspaceEditorSource, /function toggleLectureMode\(\) \{\s*patchBodyAttributes\(\{ lectureMode: !lectureMode\.value \}\);/);
});

test('pasted screenshots fill an empty slide or start a new section in lecture mode', () => {
  assert.match(editorSource, /function slideImageTarget\(ed, position = null\)/);
  assert.match(editorSource, /context && context\.node\.firstChild\.childCount === 0\) return \{ mediaPos: context\.pos \+ 1 \}/);
  assert.match(editorSource, /if \(lectureMode\.value\) return \{ newSlide: true,/);
  assert.doesNotMatch(editorSource, /LECTURE_BLOCK_ID/);
});

test('a lecture note can be created from the new-note menu', () => {
  assert.doesNotMatch(notesWorkspaceSource, /@click="createLectureNote"/);
  assert.match(notesWorkspaceSource, /v-for="template in notesStore\.templates"/);
});

test('switching notes resets root attributes instead of leaking them', () => {
  // TipTap setContent ersetzt nur den Inhalt – Wurzel-Attribute müssen
  // explizit nachgezogen werden (sonst erbt die neue Notiz z. B. die
  // Dokument-Verknüpfung der vorherigen).
  assert.match(editorSource, /setContent\(next \|\| '', \{ emitUpdate: false \}\);\s*syncDocAttributes\(ed, next\?\.attrs\);/);
  assert.match(editorSource, /function syncDocAttributes\(ed, attrs\)[\s\S]*?tr\.setDocAttribute\(name, value\)[\s\S]*?setMeta\('preventUpdate', true\)\.setMeta\('addToHistory', false\)/);
});

test('exports keep slide and notes side by side', () => {
  const body = {
    type: 'doc',
    attrs: { lectureMode: true },
    content: [{
      type: 'lectureSlide',
      content: [
        { type: 'lectureSlideMedia', content: [] },
        { type: 'lectureSlideNotes', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Rotation um den Ursprung' }] }] },
      ],
    }],
  };
  assert.match(noteToMarkdown({ title: 'Mitschrift', body }), /Rotation um den Ursprung/);
  assert.match(noteContentToPlainText(body), /Rotation um den Ursprung/);
  const html = noteToPrintableHtml({ title: 'Mitschrift', body });
  assert.match(html, /<section class="lecture-slide"><div class="lecture-slide-media"><\/div><div class="lecture-slide-notes"><p>Rotation um den Ursprung<\/p><\/div><\/section>/);
});
