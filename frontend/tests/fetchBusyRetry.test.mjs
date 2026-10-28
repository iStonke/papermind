import assert from 'node:assert/strict';
import test from 'node:test';

globalThis.window = {
  location: { origin: 'http://127.0.0.1:5179' },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  setTimeout, clearTimeout, addEventListener() {}, removeEventListener() {},
};

const { busyRetryDelayMs, installFetchInterceptor } = await import('../src/api/fetchInterceptor.js');

const busy = (retryAfter = '0') => new Response(
  JSON.stringify({ error: { code: 'DATABASE_BUSY', message: 'busy' } }),
  { status: 503, headers: { 'content-type': 'application/json', ...(retryAfter === null ? {} : { 'Retry-After': retryAfter }) } },
);
const ok = () => new Response('{"ok":true}', { headers: { 'content-type': 'application/json' } });

let responder = () => ok();
const calls = [];
window.fetch = async (input, init) => {
  calls.push({ input, init });
  return responder(calls.length);
};
installFetchInterceptor();

function reset(next) {
  calls.length = 0;
  responder = next;
}

test('busy delay only applies to idempotent 503 responses with Retry-After', () => {
  assert.equal(busyRetryDelayMs(busy('5'), 'GET'), 5000);
  assert.equal(busyRetryDelayMs(busy('5'), 'head'), 5000);
  assert.equal(busyRetryDelayMs(busy('120'), 'GET'), 10_000, 'capped');
  assert.equal(busyRetryDelayMs(busy('5'), 'POST'), null);
  assert.equal(busyRetryDelayMs(busy(null), 'GET'), null);
  assert.equal(busyRetryDelayMs(busy('Wed, 21 Oct 2026 07:28:00 GMT'), 'GET'), null);
  assert.equal(busyRetryDelayMs(new Response('', { status: 500, headers: { 'Retry-After': '5' } }), 'GET'), null);
});

test('a busy GET is retried once and the caller sees the successful response', async () => {
  reset(count => (count === 1 ? busy('0') : ok()));
  const response = await window.fetch('/api/documents');
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true });
  assert.equal(calls.length, 2);
});

test('a GET that stays busy is retried only once', async () => {
  reset(() => busy('0'));
  const response = await window.fetch('/api/documents');
  assert.equal(response.status, 503);
  assert.equal(calls.length, 2);
});

test('writes are never retried automatically', async () => {
  reset(() => busy('0'));
  const response = await window.fetch('/api/notes', { method: 'POST', body: '{}' });
  assert.equal(response.status, 503);
  assert.equal(calls.length, 1);
});

test('aborting during the wait cancels the retry', async () => {
  reset(() => busy('5'));
  const controller = new AbortController();
  const pending = window.fetch('/api/documents', { signal: controller.signal });
  setTimeout(() => controller.abort(), 20);
  await assert.rejects(pending, error => error.name === 'AbortError');
  assert.equal(calls.length, 1);
});

test('non-API requests pass through untouched', async () => {
  reset(() => busy('0'));
  const response = await window.fetch('https://example.invalid/api/public');
  assert.equal(response.status, 503);
  assert.equal(calls.length, 1);
});
