import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const workspaceSource = await readFile(new URL('../src/views/DocumentsWorkspace.vue', import.meta.url), 'utf8');
const sidebarSource = await readFile(new URL('../src/components/AppSidebar.vue', import.meta.url), 'utf8');
const itemSource = await readFile(new URL('../src/components/SidebarItem.vue', import.meta.url), 'utf8');

test('imports without a visible document list fly into the all-documents sidebar item', () => {
  assert.match(workspaceSource, /appSidebarRef\.value\?\.getAllDocumentsFlightTarget\?\.\(\)/);
  assert.match(workspaceSource, /destination = 'all-documents'/);
  assert.match(workspaceSource, /:all-documents-pulse-key="allDocumentsPulseKey"/);
  assert.match(sidebarSource, /getAllDocumentsFlightTarget/);
  assert.match(sidebarSource, /:pulse-key="allDocumentsPulseKey"/);
});

test('sidebar item pulse is restartable and respects reduced motion', () => {
  assert.match(itemSource, /watch\(\s*\(\) => props\.pulseKey/);
  assert.match(itemSource, /sidebar-item--pulse/);
  assert.match(itemSource, /prefers-reduced-motion: reduce/);
});

test('the sidebar flight target vanishes by shrinking to zero without a final flash', async () => {
  const flightSource = await readFile(new URL('../src/components/ImportFlightCard.vue', import.meta.url), 'utf8');
  assert.match(itemSource, /vanish: true/);
  assert.match(flightSource, /targetWidth = vanishAtTarget \? 0 : end\.width/);
  assert.match(flightSource, /raw - 0\.9/);
});
