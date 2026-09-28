import assert from 'node:assert/strict';
import test from 'node:test';

import { mergeWavBlobs, splitSpeechText } from '../src/utils/ttsAudio.js';

function wavBlob(samples) {
  const data = Uint8Array.from(samples);
  const buffer = new ArrayBuffer(44 + data.length);
  const view = new DataView(buffer);
  const write = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  write(0, 'RIFF');
  view.setUint32(4, buffer.byteLength - 8, true);
  write(8, 'WAVE');
  write(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 22050, true);
  view.setUint32(28, 22050, true);
  view.setUint16(32, 1, true);
  view.setUint16(34, 8, true);
  write(36, 'data');
  view.setUint32(40, data.length, true);
  new Uint8Array(buffer, 44).set(data);
  return new Blob([buffer], { type: 'audio/wav' });
}

test('splitSpeechText keeps every Piper request inside the configured limit', () => {
  const text = `${'Erster Satz. '.repeat(12)}${'Zweiter Abschnitt '.repeat(14)}`;
  const chunks = splitSpeechText(text, 80);
  assert.ok(chunks.length > 1);
  assert.ok(chunks.every((chunk) => chunk.length <= 80));
  assert.equal(chunks.join(' ').replace(/\s+/g, ' '), text.trim().replace(/\s+/g, ' '));
});

test('mergeWavBlobs creates one valid WAV with all audio frames', async () => {
  const merged = await mergeWavBlobs([wavBlob([1, 2]), wavBlob([3, 4, 5])]);
  const buffer = await merged.arrayBuffer();
  const view = new DataView(buffer);
  assert.equal(new TextDecoder().decode(buffer.slice(0, 4)), 'RIFF');
  assert.equal(new TextDecoder().decode(buffer.slice(8, 12)), 'WAVE');
  assert.equal(view.getUint32(40, true), 5);
  assert.deepEqual([...new Uint8Array(buffer.slice(44, 49))], [1, 2, 3, 4, 5]);
});
