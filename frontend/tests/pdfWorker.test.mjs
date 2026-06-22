import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workerConfig = await readFile(
  new URL('../src/utils/pdfWorker.js', import.meta.url),
  'utf8',
);

test('cache-busts the PDF module worker URL', () => {
  assert.match(workerConfig, /pdfWorkerSrc\}\?pm-worker=\d+/);
});
