import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const illustrationSource = await readFile(
  new URL('../src/components/DocumentPreviewIllustration.vue', import.meta.url),
  'utf8',
);

test('empty document preview uses its own hand-drawn illustration', () => {
  assert.match(workspaceSource, /<DocumentPreviewIllustration\s+[\s\S]*?v-else[\s\S]*?\/>/);
  assert.match(workspaceSource, /import DocumentPreviewIllustration from '\.\.\/components\/DocumentPreviewIllustration\.vue'/);
  assert.match(illustrationSource, /viewBox="0 0 560 360"/);
  assert.match(illustrationSource, /document-preview-illustration__sheet-echo/);
  assert.match(illustrationSource, /document-preview-illustration__image-frame/);
  assert.match(illustrationSource, /document-preview-illustration__magnifier/);
});

test('document preview illustration stays subtle, accessible, and motion-safe', () => {
  assert.match(illustrationSource, /role="status"[\s\S]*?aria-label="Kein Dokument ausgewählt/);
  assert.doesNotMatch(illustrationSource, /drop-shadow|filter:\s*blur|infinite/);
  assert.match(illustrationSource, /prefers-reduced-motion:\s*reduce/);
  assert.match(illustrationSource, /:global\(\.pm-no-animations\)/);
});
