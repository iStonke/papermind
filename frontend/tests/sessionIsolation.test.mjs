import assert from 'node:assert/strict';
import test from 'node:test';
import { createPinia, setActivePinia } from 'pinia';

const values = new Map();
globalThis.window = {
  location: { origin: 'http://127.0.0.1:5179' },
  localStorage: { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) },
  atob: globalThis.atob, setTimeout, clearTimeout, addEventListener() {}, removeEventListener() {},
};
const { useAuthStore } = await import('../src/stores/auth.js');
const { useNotesStore } = await import('../src/stores/notes.js');
const { useImportStagingStore } = await import('../src/stores/importStaging.js');
const { apiFetch, authedUrl, setFileToken, setToken, targetsApi } = await import('../src/api/client.js');
const { resetApiSession } = await import('../src/api/session.js');
const json = data => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } });

test('logout removes private note details, nested state and Map entries before another account loads', async () => {
  setActivePinia(createPinia());
  const auth = useAuthStore();
  const notes = useNotesStore();
  const staging = useImportStagingStore();
  globalThis.fetch = async () => json({ id: 'private-a', title: 'A private title', body_json: { type: 'doc' } });
  await notes.get('private-a');
  notes.loaded = true;
  staging.sourceMetaById.set('private-file-a', { name: 'Private A' });
  auth.user = { id: 'account-a' }; auth.status = 'authenticated';
  auth.clearSession();
  auth.user = { id: 'account-b' }; auth.status = 'authenticated';
  assert.equal(notes.peek('private-a'), null);
  assert.deepEqual(notes.allNotes, []);
  assert.equal(notes.loaded, false);
  assert.ok(staging.sourceMetaById instanceof Map);
  assert.equal(staging.sourceMetaById.size, 0);
  globalThis.fetch = async () => new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } });
  await assert.rejects(notes.get('private-a'));
});

test('a late response from a previous session cannot refill a reset note cache', async () => {
  setActivePinia(createPinia());
  const notes = useNotesStore();
  const auth = useAuthStore();
  let finish;
  globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = notes.get('late-a');
  const rejection = assert.rejects(pending, error => error.code === 'SESSION_CHANGED');
  auth.clearSession();
  finish(json({ id: 'late-a', title: 'Private A', body_json: { type: 'doc' } }));
  await rejection;
  assert.equal(notes.peek('late-a'), null);
  assert.deepEqual(notes.allNotes, []);
});

test('API origins and paths gate native file tokens', () => {
  setFileToken('synthetic-file-token');
  assert.equal(targetsApi('/api/documents/a/file'), true);
  assert.equal(targetsApi('https://example.invalid/api/documents/a/file'), false);
  assert.equal(targetsApi('/other?next=/api/documents/a/file'), false);
  assert.equal(authedUrl('https://example.invalid/api/public'), 'https://example.invalid/api/public');
  assert.match(authedUrl('/api/documents/a/file'), /token=synthetic-file-token/);
  setFileToken('');
});

test('fetch interceptor preserves Request methods and never exports a token to another origin', async () => {
  const { installFetchInterceptor } = await import('../src/api/fetchInterceptor.js');
  setToken('synthetic-access');
  const calls = [];
  window.fetch = async (input, init) => { calls.push({ input, init }); return json({ ok: true }); };
  installFetchInterceptor();
  const req = new Request('http://127.0.0.1:5179/api/notes', { method: 'POST', body: 'payload' });
  await window.fetch(req);
  assert.equal(calls[0].input, req);
  assert.equal(calls[0].input.method, 'POST');
  assert.equal(calls[0].init.headers.get('Authorization'), 'Bearer synthetic-access');
  await window.fetch('https://example.invalid/api/public');
  assert.equal(calls[1].init?.headers, undefined);
  const source = new AbortController();
  await window.fetch('/api/ai/chat', { signal: source.signal });
  source.abort();
  assert.equal(calls[2].init.signal.aborted, true, 'caller abort remains linked after headers arrive');
  setToken('');
});

test('logout during response body reading discards the previous account payload', async () => {
  let finish;
  globalThis.fetch = async () => ({ status: 200, ok: true, headers: new Headers({ 'content-type': 'application/json' }),
    json: () => new Promise(resolve => { finish = resolve; }) });
  const pending = apiFetch('/api/notes');
  const rejection = assert.rejects(pending, error => error.code === 'SESSION_CHANGED');
  await new Promise(resolve => setImmediate(resolve));
  resetApiSession('account-b');
  finish({ items: [{ title: 'Private A' }] });
  await rejection;
});

test('session refresh is scheduled from the two-part backend token', () => {
  setActivePinia(createPinia());
  const auth = useAuthStore();
  const exp = Math.floor(Date.now() / 1000) + 3600;
  const token = `${Buffer.from(JSON.stringify({ exp })).toString('base64url')}.signature`;
  const timers = [];
  const original = window.setTimeout;
  window.setTimeout = (callback, delay) => { timers.push(delay); return null; };
  try { auth.scheduleSessionRefresh(token); }
  finally { window.setTimeout = original; auth.clearSession(); }
  assert.equal(timers.length, 1);
  assert.ok(timers[0] > 3_000_000 && timers[0] <= 3_300_000);
});

test('note pagination retains every page of the metadata catalog', async () => {
  const { listNotes } = await import('../src/api/notes.js');
  const offsets = [];
  globalThis.fetch = async url => {
    const offset = Number(new URL(url, window.location.origin).searchParams.get('offset'));
    offsets.push(offset);
    return json(offset === 0 ? { items: [{ id: 'first' }, { id: 'second' }], has_more: true }
      : { items: [{ id: 'third' }], has_more: false });
  };
  assert.deepEqual((await listNotes()).items.map(item => item.id), ['first', 'second', 'third']);
  assert.deepEqual(offsets, [0, 2]);
});

test('an external abort remains effective when an API timeout is configured', async () => {
  const source = new AbortController();
  globalThis.fetch = (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')));
  });
  const pending = apiFetch('/api/notes', { signal: source.signal, timeoutMs: 5000 });
  const rejection = assert.rejects(pending, error => error.name === 'AbortError' && error.code !== 'REQUEST_TIMEOUT');
  source.abort();
  await rejection;
});

test('a pending file token from account A cannot overwrite account B or block its request', async () => {
  setActivePinia(createPinia());
  const auth = useAuthStore();
  const responses = [];
  globalThis.fetch = () => new Promise(resolve => responses.push(resolve));
  const oldRequest = auth.refreshFileToken();
  auth.clearSession();
  const newRequest = auth.refreshFileToken();
  assert.equal(responses.length, 2);
  responses[1](json({ token: 'file-b', expires_in: 300 }));
  await newRequest;
  responses[0](json({ token: 'file-a', expires_in: 300 }));
  await oldRequest;
  assert.match(authedUrl('/api/documents/file'), /token=file-b/);
  auth.clearSession();
});
