import test from 'node:test';
import assert from 'node:assert/strict';

import { setToken } from '../src/api/client.js';
import {
  backfillWiki,
  controlWikiBackfill,
  correctWikiClaim,
  getWikiBackfillStatus,
  getWikiPage,
  listWikiPages,
  listWikiProposals,
  reviewWikiProposal,
} from '../src/api/wiki.js';

test('wiki API encodes filters and sends authenticated review mutations', async () => {
  const previousFetch = globalThis.fetch;
  const previousLocalStorage = globalThis.localStorage;
  const calls = [];
  globalThis.localStorage ??= { getItem: () => null, removeItem: () => {}, setItem: () => {} };
  setToken('test-token');
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ items: [], total: 0 }),
    };
  };

  try {
    await listWikiPages({ q: 'Miete & Vertrag', kind: 'contract', limit: 20 });
    await listWikiProposals({ limit: 50, offset: 100 });
    await getWikiPage('page-1', { claimLimit: 100, claimOffset: 200 });
    await backfillWiki({ batchSize: 1, documentLimit: 20 });
    await getWikiBackfillStatus();
    await controlWikiBackfill('run-1', 'pause');
    await reviewWikiProposal('proposal-1', { action: 'reject', note: 'nicht belegt' });
    await correctWikiClaim('claim-1', { expected_revision_id: 'revision-1', corrected_text: 'Text', reason: 'Grund' });
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.localStorage = previousLocalStorage;
    setToken('');
  }

  assert.equal(calls[0].url, '/api/wiki/pages?q=Miete+%26+Vertrag&kind=contract&limit=20');
  assert.equal(calls[1].url, '/api/wiki/proposals?status=pending&limit=50&offset=100');
  assert.equal(calls[2].url, '/api/wiki/pages/page-1?claim_limit=100&claim_offset=200');
  assert.equal(calls[3].url, '/api/wiki/backfill?batch_size=1&document_limit=20');
  assert.equal(calls[3].options.method, 'POST');
  assert.equal(calls[4].url, '/api/wiki/backfill/status');
  assert.equal(calls[5].url, '/api/wiki/backfill/run-1/control');
  assert.deepEqual(JSON.parse(calls[5].options.body), { action: 'pause' });
  assert.equal(calls[6].options.headers.Authorization, 'Bearer test-token');
  assert.equal(calls[7].url, '/api/wiki/claims/claim-1/correct');
});
