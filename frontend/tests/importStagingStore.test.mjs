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
