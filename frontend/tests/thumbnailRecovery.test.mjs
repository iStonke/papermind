import assert from 'node:assert/strict';
import test from 'node:test';

import {
  THUMBNAIL_RETRY_BASE_DELAYS_MS,
  thumbnailRetryDelay,
} from '../src/utils/thumbnailRecovery.js';

test('Thumbnail-Retries werden begrenzt und zeitlich gestaffelt', () => {
  const documentId = '123e4567-e89b-12d3-a456-426614174000';
  const delays = THUMBNAIL_RETRY_BASE_DELAYS_MS.map((_, attempt) =>
    thumbnailRetryDelay(attempt, documentId)
  );

  assert.equal(delays.length, 3);
  assert.ok(delays[0] >= 500 && delays[0] < 800);
  assert.ok(delays[1] >= 1_600 && delays[1] < 1_900);
  assert.ok(delays[2] >= 5_000 && delays[2] < 5_300);
  assert.equal(thumbnailRetryDelay(3, documentId), null);
  assert.equal(thumbnailRetryDelay(-1, documentId), null);
});

test('verschiedene Dokumente erhalten einen stabilen Retry-Versatz', () => {
  const first = thumbnailRetryDelay(0, 'document-a');
  const second = thumbnailRetryDelay(0, 'document-b');

  assert.equal(first, thumbnailRetryDelay(0, 'document-a'));
  assert.notEqual(first, second);
});
