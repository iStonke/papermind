import assert from 'node:assert/strict';
import test from 'node:test';
import { createPinia, setActivePinia } from 'pinia';
import { mergeAvailableDrafts } from '../src/composables/useAvailableImportRemoval.js';
import { useImportStagingStore } from '../src/stores/importStaging.js';
import { importAvailability } from '../src/workspaces/documents/importAvailability.js';
import { migrateImportDraft } from '../src/utils/importDraftStorage.js';

test('pending removals exclude only their sources from availability while active pages still count', () => {
  setActivePinia(createPinia());
  const store = useImportStagingStore();
  store.availableRemovals = [{ items: [{ id: 'one', source_file_id: 'removed' }], draft: null }];
  assert.deepEqual(importAvailability({ pendingCount: 5, items: [{ source_file_id: 'removed', page_count: 3 }, { source_file_id: 'new', page_count: 2 }],
    documents: [{ pages: [{ sourceFileId: 'active' }] }], excludedSources: store.removedAvailableSources }), { pendingPages: 2, totalPages: 3 });
});

test('undo merges both drafts without changing active imports or discarding newer metadata', () => {
  const file = new Blob(['pdf']);
  const older = { documents: [{ id: 'old', pages: [1] }], sourceMeta: [['one', { revision: 1 }]], files: [['one', file]] };
  const newer = { documents: [{ id: 'new', pages: [2] }], sourceMeta: [['two', { revision: 2 }]], files: [], pendingCommit: { body: { request_id: 'new-request' } } };
  const merged = mergeAvailableDrafts(older, newer);
  assert.deepEqual(merged.documents.map(doc => doc.id), ['old', 'new']);
  assert.equal(merged.files[0][1], file);
  assert.equal(merged.pendingCommit, newer.pendingCommit);
  assert.equal(older.documents.length, 1); assert.equal(newer.documents.length, 1);
});

test('the durable removal journal rejects invalid deadlines and damaged undo drafts', () => {
  const base = { version: 2, documents: [], sourceMeta: [], files: [], assetRefs: [] };
  const removal = { id: 'removal', expiresAt: 10000, pageCount: 3, items: [], draft: null };
  assert.equal(migrateImportDraft({ ...base, availableRemovals: [removal] }).availableRemovals[0].id, 'removal');
  for (const change of [{ expiresAt: NaN }, { pageCount: -1 }, { items: [null] }, { draft: { documents: 'broken' } }]) {
    assert.throws(() => migrateImportDraft({ ...base, availableRemovals: [{ ...removal, ...change }] }));
  }
});
