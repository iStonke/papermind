import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { noteContentToPlainText, noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';
import { lectureLayoutAttrs, lectureLayoutClasses, lectureLayoutOf } from '../src/components/notes/nodes/lectureLayout.js';

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

test('lecture layout is a note attribute that only switches the presentation', () => {
  assert.match(documentNodeSource, /lectureMode: \{ default: false \}/);
  assert.match(documentNodeSource, /lectureLayout: \{ default: null \}/);
  assert.match(editorSource, /lectureClasses,/);
  assert.match(previewSource, /lectureLayoutClasses\(bodyJson\?\.attrs\)/);
  assert.match(cssSource, /\.pm-lecture-mode \.pm-lecture-slide__columns \{[\s\S]*?grid-template-columns: minmax\(0, 46fr\) minmax\(0, 54fr\)/);
  assert.match(cssSource, /\.pm-lecture-text \.pm-lecture-slide__media \{\s*display: none;/);
  assert.match(cssSource, /@container \(max-width: 620px\)/);
  assert.match(workspaceEditorSource, /function setLectureLayout\(layout\) \{[\s\S]*?patchBodyAttributes\(lectureLayoutAttrs\(layout\)\);/);
  assert.doesNotMatch(workspaceEditorSource, /toggleLectureMode/);
});

test('lecture layout falls back to the legacy flag and keeps it in sync', () => {
  assert.equal(lectureLayoutOf({ lectureMode: true }), 'side');
  assert.equal(lectureLayoutOf({}), 'stacked');
  assert.equal(lectureLayoutOf(undefined), 'stacked');
  assert.equal(lectureLayoutOf({ lectureMode: true, lectureLayout: 'text' }), 'text');
  assert.equal(lectureLayoutOf({ lectureLayout: 'kaputt', lectureMode: true }), 'side');
  assert.deepEqual(lectureLayoutAttrs('side'), { lectureLayout: 'side', lectureMode: true });
  assert.deepEqual(lectureLayoutAttrs('stacked'), { lectureLayout: 'stacked', lectureMode: false });
  assert.deepEqual(lectureLayoutAttrs('text'), { lectureLayout: 'text', lectureMode: false });
  assert.deepEqual(lectureLayoutClasses({ lectureLayout: 'text' }), { 'pm-lecture-mode': false, 'pm-lecture-text': true });
  assert.deepEqual(lectureLayoutClasses({ lectureMode: true }), { 'pm-lecture-mode': true, 'pm-lecture-text': false });
});

test('pasted screenshots fill an empty slide or start a new section in lecture mode', () => {
  assert.match(editorSource, /function slideImageTarget\(ed, position = null\)/);
  assert.match(editorSource, /context && context\.node\.firstChild\.childCount === 0\) return \{ mediaPos: context\.pos \+ 1 \}/);
  assert.match(editorSource, /if \(lectureMode\.value\) return \{ newSlide: true,/);
  // „Nur Mitschrift": Bilder landen sichtbar im Text statt in ausgeblendeten Folien.
  assert.match(editorSource, /if \(lectureLayout\.value === 'text'\) return null;/);
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
  assert.match(html, /<section class="lecture-slide lecture-slide--side"><div class="lecture-slide-media"><\/div><div class="lecture-slide-notes"><p>Rotation um den Ursprung<\/p><\/div><\/section>/);
});

test('text-only lecture exports leave hidden slides out', () => {
  const body = {
    type: 'doc',
    attrs: { lectureMode: false, lectureLayout: 'text' },
    content: [{
      type: 'lectureSlide',
      content: [
        { type: 'lectureSlideMedia', content: [{ type: 'image', attrs: { src: '/api/notes/n/images/i/file', alt: 'Folie 1' } }] },
        { type: 'lectureSlideNotes', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Nur der Text' }] }] },
      ],
    }],
  };
  const markdown = noteToMarkdown({ title: 'Mitschrift', body });
  assert.match(markdown, /Nur der Text/);
  assert.doesNotMatch(markdown, /Folie 1|\/api\/notes/);
  const html = noteToPrintableHtml({ title: 'Mitschrift', body });
  assert.match(html, /<section class="lecture-slide lecture-slide--text"><div class="lecture-slide-notes"><p>Nur der Text<\/p><\/div><\/section>/);
  assert.doesNotMatch(html, /lecture-slide-media"/);
});

test('slide headers never count positions beyond the current document', async () => {
  const viewSource = await read('../src/components/notes/nodes/LectureSlideView.vue');
  // Ausgebaute Abschnitte melden beim Notizwechsel kurz ihre alte Position.
  assert.match(viewSource, /function currentPos\(\) \{[\s\S]*?pos >= doc\.content\.size\) return null;[\s\S]*?doc\.nodeAt\(pos\)\?\.type\.name === 'lectureSlide'/);
  assert.match(viewSource, /function updatePosition\(\) \{\s*const pos = currentPos\(\);/);
  assert.match(viewSource, /Eine Kopfzeile darf nie eine Editor-Transaktion/);
});
