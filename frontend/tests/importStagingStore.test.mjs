import test from "node:test";
import assert from "node:assert/strict";
import { createPinia, setActivePinia } from "pinia";

import { useImportStagingStore } from "../src/stores/importStaging.js";

function createStore() {
  setActivePinia(createPinia());
  return useImportStagingStore();
}

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
