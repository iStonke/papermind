import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';
import { normalizeNoteHref, noteHrefLabel } from '../src/utils/noteLinks.js';

const editorSource = fs.readFileSync(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const previewSource = fs.readFileSync(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);
const iconsSource = fs.readFileSync(
  new URL('../src/plugins/mdiIcons.js', import.meta.url),
  'utf8',
);

test('note hyperlinks normalize common input and reject unsafe protocols', () => {
  assert.equal(normalizeNoteHref('papermind.example/quelle'), 'https://papermind.example/quelle');
  assert.equal(normalizeNoteHref('https://example.org/a?q=1#fundstelle'), 'https://example.org/a?q=1#fundstelle');
  assert.equal(normalizeNoteHref('name@example.org'), 'mailto:name@example.org');
  assert.equal(noteHrefLabel('name@example.org'), 'name@example.org');
  assert.equal(normalizeNoteHref('javascript:alert(1)'), '');
  assert.equal(normalizeNoteHref('data:text/html,boom'), '');
  assert.equal(normalizeNoteHref('https://example.org/mit leerzeichen'), '');
  assert.equal(normalizeNoteHref('mailto:kein-postfach'), '');
});

test('hyperlinks are available from toolbar, selection bubble, shortcut, slash menu, and URL paste', () => {
  assert.match(editorSource, /key: 'link',[\s\S]*?label: 'Hyperlink',[\s\S]*?run: \(\) => openLinkEditor\(\)/);
  assert.match(editorSource, /key: 'link', group: 'inline',[\s\S]*?kind: 'link-editor'/);
  assert.match(editorSource, /key\.toLowerCase\(\) === 'k'[\s\S]*?event\.preventDefault\(\)[\s\S]*?openLinkEditor\(\)/);
  assert.match(editorSource, /function handleEditorPaste\(event\)[\s\S]*?selection\.empty[\s\S]*?setLink\(/);
  assert.match(editorSource, /placeholder="https:\/\/\u2026 oder name@domain\.de"/);
  assert.match(editorSource, />Öffnen</);
  assert.match(editorSource, />Entfernen</);
  assert.match(editorSource, /key: 'verweis',[\s\S]*?kind: 'pick-target'/);
  assert.match(editorSource, /const insertItems = \[[\s\S]*?label: 'Hyperlink',[\s\S]*?action: 'link'/);
  assert.match(editorSource, /label: 'Verweis',[\s\S]*?action: 'target'/);
  assert.match(iconsSource, /mdiLinkVariant/);
  assert.match(iconsSource, /mdiLinkOff/);
  assert.match(iconsSource, /mdiOpenInNew/);
});

test('read-only preview and note exports preserve safe external hyperlinks', () => {
  const body = {
    type: 'doc',
    content: [{
      type: 'paragraph',
      content: [
        {
          type: 'text',
          text: 'Quelle',
          marks: [{ type: 'link', attrs: { href: 'https://example.org/studie' } }],
        },
        { type: 'text', text: ' und unsicher' },
        {
          type: 'text',
          text: ' nicht öffnen',
          marks: [{ type: 'link', attrs: { href: 'javascript:alert(1)' } }],
        },
      ],
    }],
  };

  const markdown = noteToMarkdown({ title: 'Links', body });
  const html = noteToPrintableHtml({ title: 'Links', body });

  assert.match(previewSource, /openOnClick: true/);
  assert.match(previewSource, /target: '_blank', rel: 'noopener noreferrer'/);
  assert.match(markdown, /\[Quelle\]\(https:\/\/example\.org\/studie\)/);
  assert.doesNotMatch(markdown, /javascript:/);
  assert.match(html, /href="https:\/\/example\.org\/studie" target="_blank" rel="noopener noreferrer"/);
  assert.doesNotMatch(html, /javascript:/);
});
