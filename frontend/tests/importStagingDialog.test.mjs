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

test('marks pages that were automatically cropped by scan cleanup', () => {
  assert.match(dialogSource, /v-if="autoCropForPage\(page\)\?\.applied"/);
  assert.match(dialogSource, /class="isd-page-crop-badge"/);
  assert.match(dialogSource, /Number\(result\?\.page_index\) === pageIndex/);
});
