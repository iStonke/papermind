import test from "node:test";
import assert from "node:assert/strict";
import { createPinia, setActivePinia } from "pinia";

import { useImportStagingStore } from "../src/stores/importStaging.js";

function createStore() {
  setActivePinia(createPinia());
  return useImportStagingStore();
}

test("closing parks and restores the complete import without rebuilding its pages", () => {
  const store = createStore();
  const file = new Blob(['pdf']);
  const doc = store.addDocumentFromSource({ sourceFileId: 'one', title: 'Mein Titel', pageCount: 2, tags: ['tag'] });
  store.setStagingFile('one', file, { pageCount: 2, inboxItemId: 'inbox-one', sourceType: 'scanner' });
  Object.assign(doc.meta.form, { date: '22.10.2026', category: 'Brief', correspondentId: 'sender', note: 'Notiz' });
  doc.meta.form.aiFilled.note = true;
  doc.pages.reverse();doc.pages[0].rotation = 90;store.setAllPagesColorMode('grayscale');
  const batch = store.batchId, ids = doc.pages.map(page => page.id);
  store.parkDraft();
  assert.equal(store.totalPages, 0);assert.equal(store.availablePageCount, 2);
  assert.equal(store.restoreAvailableDraft(), true);
  assert.equal(store.availableDraft, null);assert.equal(store.batchId, batch);
  assert.deepEqual(store.documents[0].pages.map(page => page.id), ids);
  assert.equal(store.documents[0].pages[0].rotation, 90);
  assert.equal(store.allPagesColorMode, 'grayscale');
  assert.equal(store.documents[0].meta.form.note, 'Notiz');
  assert.equal(store.documents[0].meta.form.aiFilled.note, true);
  assert.equal(store.stagingFiles.get('one'), file);
  assert.equal(store.sourceMetaById.get('one').inboxItemId, 'inbox-one');
});

test('an uncertain local PDF submission stays retryable without becoming available pages', () => {
  const store = createStore();
  store.addDocumentFromSource({ sourceFileId: 'local', pageCount: 2 });
  store.pendingCommit = { body: { request_id: 'durable-id' }, submitted: {} };
  store.parkDraft();
  assert.equal(store.totalPages, 2);
  assert.equal(store.availablePageCount, 0);
  assert.equal(store.pendingCommit.body.request_id, 'durable-id');
});

test("an empty close preserves the saved import and only a new nonempty import replaces it", () => {
  const store = createStore();
  store.addDocumentFromSource({ sourceFileId: 'old', title: 'Alt', pageCount: 3 });
  store.setStagingFile('old', null, { pageCount: 3, sourceType: 'scanner' });
  store.parkDraft();store.addEmptyDocument();store.parkDraft();
  assert.equal(store.availablePageCount, 3);
  store.addDocumentFromSource({ sourceFileId: 'new', title: 'Neu', pageCount: 1 });
  store.setStagingFile('new', null, { pageCount: 1, sourceType: 'scanner' });
  assert.equal(store.restoreAvailableDraft(), false);
  assert.equal(store.parkDraft().documents[0].title, 'Alt');
  assert.equal(store.availablePageCount, 1);
  store.restoreAvailableDraft();
  assert.equal(store.documents[0].title, 'Neu');assert.equal(store.availablePageCount, 0);
});

test('closing a local PDF keeps the previous scans and filters mixed documents page by page', () => {
  const store = createStore();
  store.addDocumentFromSource({ sourceFileId: 'scan', title: 'Scan', pageCount: 2 });
  store.setStagingFile('scan', null, { pageCount: 2, sourceType: 'scanner' });
  store.parkDraft();
  const previous = store.availableDraft;
  store.addDocumentFromSource({ sourceFileId: 'local', title: 'Ausgewählt', pageCount: 1 });
  store.setStagingFile('local', new Blob(['pdf']), { pageCount: 1, sourceType: 'local' });
  store.parkDraft();
  assert.equal(store.availableDraft, previous);
  assert.equal(store.availablePageCount, 2);
  store.restoreAvailableDraft();
  const local = store.addDocumentFromSource({ sourceFileId: 'another-local', pageCount: 1 });
  store.setStagingFile('another-local', new Blob(['pdf']), { pageCount: 1 });
  store.movePage(local.pages[0].id, store.documents[0].id, 1);
  store.documents[0].pages[2].rotation = 90;
  store.parkDraft();
  assert.equal(store.availablePageCount, 2);
  assert.deepEqual(store.availableDraft.documents[0].pages.map(page => page.sourceFileId), ['scan', 'scan']);
  assert.equal(store.availableDraft.documents[0].pages[1].rotation, 90);
  assert.deepEqual(store.availableDraft.sourceMeta.map(([id]) => id), ['scan']);
  assert.deepEqual(store.availableDraft.files.map(([id]) => id), ['scan']);
});

test("addEmptyDocument appends when insertIndex is null", () => {
  const store = createStore();

  store.addDocumentFromSource({
    sourceFileId: "pdf-source",
    title: "PDF zuerst",
    pageCount: 1
  });
  store.addEmptyDocument(null, "Scan danach");

  assert.deepEqual(
    store.documents.map((document) => document.title),
    ["PDF zuerst", "Scan danach"]
  );
});

test("addEmptyDocument still honors explicit insertIndex", () => {
  const store = createStore();

  store.addDocumentFromSource({
    sourceFileId: "pdf-source",
    title: "PDF zuerst",
    pageCount: 1
  });
  store.addEmptyDocument(0, "Explizit vorne");

  assert.deepEqual(
    store.documents.map((document) => document.title),
    ["Explizit vorne", "PDF zuerst"]
  );
});

test("the import color mode covers every document and is inherited by later sources", () => {
  const store = createStore();
  const first = store.addDocumentFromSource({ sourceFileId: "first", pageCount: 2 });
  store.addDocumentFromSource({ sourceFileId: "second", pageCount: 1 });
  first.pages[0].rotation = 90;
  store.setAllPagesColorMode("grayscale");
  store.appendSourceToDocument(first.id, { sourceFileId: "later-scan", pageCount: 2 });
  store.addDocumentFromSource({ sourceFileId: "later-pdf", pageCount: 2 });
  assert.equal(store.allPagesColorMode, "grayscale");
  assert.deepEqual(store.documents.flatMap(doc => doc.pages.map(page => page.colorMode)), Array(7).fill("grayscale"));
  assert.equal(first.pages[0].rotation, 90);
  assert.ok(store.commitDocuments.every(doc => doc.pages.every(page => page.color_mode === "grayscale")));
  for (const mode of ["color", "auto"]) {
    store.setAllPagesColorMode(mode);
    assert.equal(store.allPagesColorMode, mode);
    assert.ok(store.documents.every(doc => doc.pages.every(page => page.colorMode === mode)));
  }
  store.setAllPagesColorMode("color");
  store.reset();
  const next = store.addDocumentFromSource({ sourceFileId: "new-import", pageCount: 1 });
  assert.equal(next.pages[0].colorMode, "auto");
});
