import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const dialogSource = await readFile(
  new URL('../src/components/ImportStagingDialog.vue', import.meta.url),
  'utf8',
);

test('minimizing an import requires at least one staged page', () => {
  assert.match(dialogSource, /:disabled="isCommitting \|\| !hasStagedPages"/);
  assert.match(
    dialogSource,
    /function minimizeDialog\(\) \{\s*if \(isCommitting\.value \|\| !hasStagedPages\.value\) \{\s*return;/,
  );
});

test('shows an automatically cropped page in its actual thumbnail format', () => {
  assert.match(dialogSource, /:style="pageThumbnailFormatStyle\(page\)"/);
  assert.match(dialogSource, /crop\?\.cropped_size_pixels/);
  assert.match(dialogSource, /return \{ paddingTop: `\$\{\(height \/ width\) \* 100\}%` \}/);
  assert.doesNotMatch(dialogSource, /isd-page-crop-badge/);
  assert.doesNotMatch(dialogSource, /isd-crop-feedback/);
});
