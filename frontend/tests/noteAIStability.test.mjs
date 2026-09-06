import { readNoteEditorSource } from './helpers/noteEditorSource.mjs';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { streamNoteText } from '../src/api/notes.js';

const editorSource = await readNoteEditorSource();

test('note AI consumes streamed metadata and text deltas', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response([
    '{"type":"meta","provider":"ollama","model":"local-writer","fallback_from":"openai"}',
    '{"type":"delta","text":"Hallo"}',
    '{"type":"delta","text":" Welt"}',
    '{"type":"done"}',
    '',
  ].join('\n'), {
    status: 200,
    headers: { 'content-type': 'application/x-ndjson' },
  });

  const events = [];
  try {
    await streamNoteText({ instruction: 'Schreibe weiter' }, {
      onEvent: (event) => events.push(event),
    });
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(events[0].fallback_from, 'openai');
  assert.equal(events.filter((event) => event.type === 'delta').map((event) => event.text).join(''), 'Hallo Welt');
  assert.match(editorSource, /aiPrompt\.fallbackFrom = event\.fallback_from \|\| ''/);
  assert.match(editorSource, /Lokaler Fallback/);
});

test('note AI surfaces an NDJSON stream error instead of reporting empty text', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(
    '{"type":"error","message":"Das Modell ist nicht erreichbar."}\n',
    { status: 200, headers: { 'content-type': 'application/x-ndjson' } },
  );

  try {
    await assert.rejects(
      streamNoteText({ instruction: 'Schreibe weiter' }),
      /Das Modell ist nicht erreichbar/,
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});
