import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const previewSource = await readFile(new URL('../src/components/PdfPreview.vue', import.meta.url), 'utf8');

test('PDF preview builds up document content instead of using a loading bar or scan line', () => {
  assert.match(previewSource, /pdf-preview__loading-sheet--front/);
  assert.match(previewSource, /pdf-loading-content-resolve/);
  assert.doesNotMatch(previewSource, /pdf-preview__progress-(?:wrap|bar)/);
  assert.doesNotMatch(previewSource, /pdf-preview__loading-scan/);
});

test('PDF preview loading remains accessible and respects reduced motion', () => {
  assert.match(previewSource, /role="progressbar"/);
  assert.match(previewSource, /:aria-valuenow="loadIndeterminate \? undefined : loadProgress"/);
  assert.match(previewSource, /prefers-reduced-motion: reduce/);
  assert.match(previewSource, /pm-no-animations/);
});
