import assert from 'node:assert/strict';
import test from 'node:test';
import { defaultSpeechOptions, normalizeSpeechOptions } from '../src/utils/speechSettings.js';
import { synthesizeSpeechWithMetrics } from '../src/api/tts.js';

test('old settings gain independent default speech options', () => {
  assert.deepEqual(normalizeSpeechOptions(), defaultSpeechOptions());
  const first = defaultSpeechOptions();
  first.pronunciations.push({ word: 'x' });
  assert.deepEqual(defaultSpeechOptions().pronunciations, []);
});
test('options clamp speed and keep paragraph pauses coherent', () => {
  assert.deepEqual(normalizeSpeechOptions({ speed: Infinity, sentence_pause: .8, paragraph_pause: .1, engine: 'remote' }),
    { ...defaultSpeechOptions(), sentence_pause: .8, paragraph_pause: .8 });
  assert.equal(normalizeSpeechOptions({ speed: 4 }).speed, 1.5);
});
test('dictionary removes malformed and duplicate entries without interpreting regular expressions', () => {
  const options = normalizeSpeechOptions({ pronunciations: [
    { word: ' QIS ', pronunciation: ' Kiss ' },
    { word: 'qis', pronunciation: 'duplicate' },
    { word: 'C++', pronunciation: 'C plus plus', enabled: false },
    { word: 'a\nb', pronunciation: 'x' },
  ] });
  assert.deepEqual(options.pronunciations, [
    { word: 'QIS', pronunciation: 'Kiss', case_sensitive: false, enabled: true },
    { word: 'C++', pronunciation: 'C plus plus', case_sensitive: false, enabled: false },
  ]);
});
test('preview sends the options and exposes real generation metrics', async () => {
  const original = globalThis.fetch;
  const options = { ...defaultSpeechOptions(), speed: 1.15, engine: 'kokoro' };
  let payload;
  globalThis.fetch = async (_url, request) => {
    payload = JSON.parse(request.body);
    return new Response(new Blob(['RIFF'], { type: 'audio/wav' }), { headers: {
      'Content-Type': 'audio/wav', 'X-Speech-Duration': '3.2', 'X-Speech-Generation-Ms': '1250', 'X-Speech-Engine': 'kokoro',
    } });
  };
  try {
    const result = await synthesizeSpeechWithMetrics('Test', { options, languageMode: 'de' });
    assert.deepEqual(payload, { text: 'Test', voice: 'standard', language_mode: 'de', options });
    assert.equal(result.duration, 3.2);
    assert.equal(result.generationMs, 1250);
    assert.equal(result.engine, 'kokoro');
  } finally { globalThis.fetch = original; }
});
