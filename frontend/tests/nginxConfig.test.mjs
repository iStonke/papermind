import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const config = await readFile(new URL('../nginx.conf', import.meta.url), 'utf8');

test('serves ES module workers with a JavaScript MIME type', () => {
  assert.match(config, /location\s+~\*\s+\\\.mjs\$/);
  assert.match(config, /default_type\s+application\/javascript;/);
  assert.match(config, /expires\s+-1;/);
});

test('prevents caching of HTML bootstrap responses', () => {
  assert.match(config, /~\*text\/html\s+"no-store, no-cache, must-revalidate, max-age=0"/);
  assert.match(config, /add_header\s+Cache-Control\s+\$pm_html_cache_control\s+always;/);
});

test('recovers browsers requesting removed JavaScript chunks', () => {
  assert.match(config, /location\s+~\*\s+\\\.js\$/);
  assert.match(config, /try_files\s+\$uri\s+\/stale-client\.js;/);
});
