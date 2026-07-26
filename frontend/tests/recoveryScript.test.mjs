import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('production recovery suite requires explicit confirmation and protects service recovery', async () => {
  const source = await readFile(
    new URL('../../scripts/prod_pi_recovery_check.sh', import.meta.url),
    'utf8',
  );

  assert.match(source, /--confirm-production/);
  assert.match(source, /trap recover_services EXIT/);
  assert.match(source, /stop ai/);
  assert.match(source, /stop db/);
  assert.match(source, /restart worker/);
  assert.match(source, /non-destructive/);
});
