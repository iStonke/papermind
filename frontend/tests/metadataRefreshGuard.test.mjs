import assert from 'node:assert/strict';
import test from 'node:test';
import {
  shouldPreserveMetadataDraft,
  tagQueryIsEmpty,
} from '../src/workspaces/documents/metadataRefreshGuard.js';

const base = { documentId: 'doc', draftDocumentId: 'doc' };

test('OCR refresh preserves every active kind of drawer input', () => {
  for (const state of [
    { editorHasFocus: true },
    { metadataDirty: true },
    { tagSelectionDirty: true },
    { tagQuery: 'neu' },
    { tagSearch: 'neu' },
    { categoryDirty: true },
    { correspondentDirty: true },
    { hasPendingMutation: true },
  ]) {
    assert.equal(shouldPreserveMetadataDraft({ ...base, ...state }), true);
  }
});

test('refresh applies normally without an active draft and never crosses documents', () => {
  assert.equal(shouldPreserveMetadataDraft(base), false);
  assert.equal(shouldPreserveMetadataDraft({
    ...base,
    draftDocumentId: 'other',
    metadataDirty: true,
    editorHasFocus: true,
  }), false);
});

test('a completed tag save only clears the query it actually settled', () => {
  assert.equal(tagQueryIsEmpty('', '  '), true);
  assert.equal(tagQueryIsEmpty('next tag', ''), false);
  assert.equal(tagQueryIsEmpty('', 'next tag'), false);
});
