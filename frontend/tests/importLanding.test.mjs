import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveImportDestination } from '../src/utils/importLanding.js';

const sidebar = { left: 20, top: 90, width: 18, height: 18, vanish: true };

test('import target is measured only after the refreshed documents are ready', async () => {
  let ready;
  let measured = false;
  const documentsReady = new Promise(resolve => { ready = resolve; });
  const panel = { beginImportLanding: async id => { assert.equal(id, 'older-document'); measured = true; return { top: 380 }; } };
  const pending = resolveImportDestination({ documentId: 'older-document', documentsReady, preparedPanel: panel, getPanel: () => panel, getSidebarTarget: () => sidebar });
  await Promise.resolve();
  assert.equal(measured, false);
  ready();
  assert.deepEqual(await pending, { target: { top: 380 }, panel, destination: 'list' });
});

test('changing the view during refresh prepares and measures the new view', async () => {
  let cancelled = false;
  let prepared = false;
  const oldPanel = { cancelImportLanding: () => { cancelled = true; } };
  const panel = { prepareImportLanding: id => { assert.equal(id, 'scan'); prepared = true; }, beginImportLanding: async () => ({ top: 250 }) };
  const result = await resolveImportDestination({ documentId: 'scan', preparedPanel: oldPanel, getPanel: () => panel, getSidebarTarget: () => sidebar });
  assert.equal(cancelled, true);
  assert.equal(prepared, true);
  assert.equal(result.panel, panel);
});

test('filtered or unloaded imports use the sidebar instead of an unrelated first row', async () => {
  let cancelled = false;
  const panel = { beginImportLanding: async () => null, cancelImportLanding: () => { cancelled = true; } };
  assert.deepEqual(await resolveImportDestination({ documentId: 'scan', preparedPanel: panel, getPanel: () => panel, getSidebarTarget: () => sidebar }), { target: sidebar, panel: null, destination: 'all-documents' });
  assert.equal(cancelled, true);
});

test('a view removed while locating the import cannot become a stale flight target', async () => {
  let current;
  let cancelled = false;
  const panel = { beginImportLanding: async () => { current = null; return { top: 200 }; }, cancelImportLanding: () => { cancelled = true; } };
  current = panel;
  const result = await resolveImportDestination({ documentId: 'scan', preparedPanel: panel, getPanel: () => current, getSidebarTarget: () => sidebar });
  assert.equal(result.destination, 'all-documents');
  assert.equal(result.target, sidebar);
  assert.equal(cancelled, true);
});

test('a failing group lookup still finishes with a sidebar target', async () => {
  const panel = { beginImportLanding: async () => { throw new Error('offline'); } };
  const result = await resolveImportDestination({ documentId: 'scan', preparedPanel: panel, getPanel: () => panel, getSidebarTarget: () => sidebar });
  assert.equal(result.target, sidebar);
  assert.equal(result.panel, null);
});
