import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';

const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const previewSource = await readFile(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);
const imageNodeSource = await readFile(
  new URL('../src/components/notes/nodes/noteImage.js', import.meta.url),
  'utf8',
);
const imageViewSource = await readFile(
  new URL('../src/components/notes/nodes/NoteImageView.vue', import.meta.url),
  'utf8',
);
const apiSource = await readFile(new URL('../src/api/notes.js', import.meta.url), 'utf8');
const packageJson = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));

const imageBody = {
  type: 'doc',
  content: [{
    type: 'image',
    attrs: {
      src: '/api/notes/note-1/images/image-1/file',
      alt: 'Skizze des Grundrisses',
      caption: 'Grundriss Erdgeschoss',
      displayWidth: 70,
    },
  }],
};

test('note editor supports validated image upload through all intended entry points', () => {
  assert.equal(packageJson.dependencies['@tiptap/extension-image'], '^3.30.2');
  assert.equal(packageJson.dependencies['@tiptap/extension-file-handler'], '^3.30.2');
  assert.match(editorSource, /import FileHandler from '@tiptap\/extension-file-handler'/);
  assert.match(editorSource, /NoteImage,/);
  assert.match(editorSource, /FileHandler\.configure\(\{[\s\S]*?onPaste:[\s\S]*?onDrop:/);
  assert.match(editorSource, /const insertItems = \[[\s\S]*?key: 'image'[\s\S]*?label: 'Bild einfügen'[\s\S]*?action: 'image'/);
  assert.match(editorSource, /key: 'image'[\s\S]*?kind: 'image-upload'/);
  assert.match(editorSource, /accept="image\/jpeg,image\/png,image\/webp"/);
  assert.match(apiSource, /export const uploadNoteImage/);
});

test('private image URLs stay token-free in JSON and are authenticated only for rendering', () => {
  assert.match(imageNodeSource, /stable, token-free API/);
  assert.match(imageViewSource, /const assetUrl = absoluteAssetUrl\(props\.node\.attrs\.src\);[\s\S]*?if \(!assetUrl\) return '';[\s\S]*?authedUrl\(assetUrl\)/);
  assert.match(imageViewSource, /short-lived file token can never be attached to a third-party URL/);
  assert.match(imageViewSource, /refreshFileToken\(\)/);
  assert.doesNotMatch(imageNodeSource, /allowBase64:\s*true/);
  assert.match(previewSource, /import \{ NoteImage \}/);
});

test('image captions and sizing survive Markdown and printable PDF export', () => {
  const markdown = noteToMarkdown({ title: 'Plan', body: imageBody });
  const html = noteToPrintableHtml({
    title: 'Plan',
    body: imageBody,
    imageUrl: (src) => `https://paper.local${src}?token=short-lived`,
  });

  assert.match(markdown, /!\[Skizze des Grundrisses\]\(\/api\/notes\/note-1\/images\/image-1\/file\)/);
  assert.match(markdown, /_Grundriss Erdgeschoss_/);
  assert.match(html, /class="note-image" style="width:70%"/);
  assert.match(html, /https:\/\/paper\.local\/api\/notes\/note-1\/images\/image-1\/file\?token=short-lived/);
  assert.match(html, /<figcaption>Grundriss Erdgeschoss<\/figcaption>/);
});
