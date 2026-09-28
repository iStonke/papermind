import assert from 'node:assert/strict';
import test from 'node:test';

import { synthesizeSpeech } from '../src/api/tts.js';

test('synthesizeSpeech posts selected text and returns a WAV blob', async () => {
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return new Response(new Blob(['RIFF'], { type: 'audio/wav' }), {
      status: 200,
      headers: { 'Content-Type': 'audio/wav' },
    });
  };

  try {
    const blob = await synthesizeSpeech('Hallo Welt');
    assert.equal(blob.type, 'audio/wav');
    assert.match(request.url, /\/api\/tts\/speech$/);
    assert.equal(request.options.method, 'POST');
    assert.deepEqual(JSON.parse(request.options.body), { text: 'Hallo Welt', voice: 'standard', language_mode: 'auto' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('synthesizeSpeech sends the selected voice preset', async () => {
  const originalFetch = globalThis.fetch;
  let requestBody;
  globalThis.fetch = async (_url, options) => {
    requestBody = JSON.parse(options.body);
    return new Response(new Blob(['RIFF'], { type: 'audio/wav' }), {
      status: 200,
      headers: { 'Content-Type': 'audio/wav' },
    });
  };

  try {
    await synthesizeSpeech('Gute Nacht', { voice: 'sleepy', languageMode: 'de' });
    assert.deepEqual(requestBody, { text: 'Gute Nacht', voice: 'sleepy', language_mode: 'de' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('synthesizeSpeech exposes the backend error message', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    error: { message: 'Die lokale Sprachausgabe ist derzeit nicht verfügbar.' },
  }), {
    status: 503,
    headers: { 'Content-Type': 'application/json' },
  });

  try {
    await assert.rejects(
      synthesizeSpeech('Hallo'),
      /Die lokale Sprachausgabe ist derzeit nicht verfügbar/,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
