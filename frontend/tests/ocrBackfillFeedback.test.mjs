import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const componentUrl = new URL('../src/components/SettingsDialog.vue', import.meta.url);
const stylesUrl = new URL('../src/components/SettingsDialog.styles.css', import.meta.url);

const source = await readFile(componentUrl, 'utf8');
const styles = await readFile(stylesUrl, 'utf8');

test('OCR backfill shows a clear in-progress state and an accessible inline result', () => {
  assert.match(source, /:disabled="ocrBackfillLoading"/);
  assert.match(source, /OCR-Lücken werden geprüft …/);
  assert.match(source, /if \(ocrBackfillFeedback\.value\) return 'Erneut prüfen';/);
  assert.match(source, /tone === 'success' \? 'outlined' : 'tonal'/);
  assert.match(source, /aria-live="polite"/);
  assert.match(source, /aria-atomic="true"/);
  assert.match(source, /ocr-backfill-feedback--\$\{ocrBackfillFeedback\.tone\}/);
});

test('OCR backfill distinguishes queued, complete, and failed outcomes', () => {
  const start = source.indexOf('async function runOcrBackfillNow()');
  const end = source.indexOf('const isSettingsLoading', start);
  const handler = source.slice(start, end);

  assert.ok(start >= 0 && end > start, 'OCR backfill handler should be present');
  assert.match(handler, /Die Verarbeitung läuft im Hintergrund\./);
  assert.match(handler, /Stand gerade: Keine OCR-Lücken gefunden\./);
  assert.match(handler, /OCR-Verarbeitung konnte nicht gestartet werden\. Erneut versuchen\./);
  assert.doesNotMatch(handler, /notify\(\{\s*type:\s*'(?:success|info)'/);
  assert.match(handler, /notifyError\(error,/);
});

test('OCR backfill feedback uses compact success and error styling', () => {
  assert.match(styles, /\.ocr-backfill-feedback\s*\{/);
  assert.match(styles, /\.ocr-backfill-feedback--success\s*\{/);
  assert.match(styles, /\.ocr-backfill-feedback--error\s*\{/);
});
