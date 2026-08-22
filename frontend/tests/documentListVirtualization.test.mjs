import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const componentSource = await readFile(
  new URL('../src/components/DocumentListPanel.vue', import.meta.url),
  'utf8',
);
const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);

test('velocity overscan measures against the last rendered window', () => {
  assert.match(
    componentSource,
    /applyScrollVelocityOverscan\(nextScrollTop - listScrollTop\.value\)/,
  );
  assert.doesNotMatch(
    componentSource,
    /applyScrollVelocityOverscan\(nextScrollTop - lastHandledListScrollTop\)/,
  );
});

test('scroll direction tracking does not replace the rendered-window position', () => {
  assert.match(
    componentSource,
    /const scrollingDown = nextScrollTop >= lastHandledListScrollTop;\s*lastHandledListScrollTop = nextScrollTop;/,
  );
  assert.match(componentSource, /listScrollTop\.value = nextScrollTop;/);
});

test('the next document page is prefetched before it enters the viewport', () => {
  assert.match(componentSource, /const LOAD_MORE_AHEAD_ROWS = 18;/);
  assert.match(componentSource, /const LOAD_MORE_AHEAD_VIEWPORTS = 2;/);
  assert.match(
    componentSource,
    /Math\.max\(\s*LOAD_MORE_AHEAD_ROWS \* virtualRowStep\.value,\s*element\.clientHeight \* LOAD_MORE_AHEAD_VIEWPORTS\s*\)/,
  );
});

test('document removal animates only the affected virtual rows before mutation', () => {
  assert.match(componentSource, /async function animateDocumentRemoval\(documentIds = \[\]\)/);
  assert.match(componentSource, /row\.classList\.add\('document-row--removing'\)/);
  assert.match(componentSource, /defineExpose\(\{\s*animateDocumentRemoval,/);
  assert.doesNotMatch(componentSource, /^\s*<TransitionGroup(?:\s|>)/m);
  assert.match(
    workspaceSource,
    /await documentListPanelRef\.value\?\.animateDocumentRemoval\?\.\(\[\.\.\.removeSet\]\);\s*documents\.value = next;/,
  );
});
