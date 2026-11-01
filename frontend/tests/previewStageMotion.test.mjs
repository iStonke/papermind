import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cssTimeToMilliseconds } from '../src/utils/previewStageMotion.js';

test('CSS durations retain their length when the production build changes units', () => {
  assert.equal(cssTimeToMilliseconds('420ms', 420), 420);
  assert.equal(cssTimeToMilliseconds('.42s', 420), 420);
  assert.equal(cssTimeToMilliseconds(' 0.42s ', 420), 420);
  assert.equal(cssTimeToMilliseconds('1.2s', 420), 1200);
  assert.equal(cssTimeToMilliseconds('0s', 420), 0);
  for (const value of ['', 'invalid', '-1s', '420', '1..2ms']) {
    assert.equal(cssTimeToMilliseconds(value, 420), 420);
  }
});
