import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const config = await readFile(new URL('../nginx.conf', import.meta.url), 'utf8');

test('serves ES module workers with a JavaScript MIME type', () => {
  assert.match(config, /location\s+~\*\s+\\\.mjs\$/);
  assert.match(config, /default_type\s+application\/javascript;/);
});
