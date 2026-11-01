import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveOcrDetails } from '../src/utils/ocrDetails.js';

test('OCR details use backend quality and confidence without inventing missing scores', () => {
  const known = resolveOcrDetails({ ocr_quality_status: 'warning', ocr_confidence_score: 72.4 });
  assert.equal(known.quality, 'warning');
  assert.equal(known.scoreLabel, '72,4 %');
  const unscored = resolveOcrDetails({ ocr_quality_status: 'good' });
  assert.equal(unscored.qualityLabel, 'Gut');
  assert.equal(unscored.score, null);
  for (const value of [null, undefined, NaN, Infinity, -1, 101, '90']) {
    const missing = resolveOcrDetails({ ocr_confidence_score: value });
    assert.equal(missing.score, null);
    assert.equal(missing.quality, null);
  }
  assert.equal(resolveOcrDetails({ ocr_confidence_score: 0 }).score, 0);
  assert.equal(resolveOcrDetails({ ocr_confidence_score: 59.9 }).quality, 'error');
  assert.equal(resolveOcrDetails({ ocr_confidence_score: 60 }).quality, 'warning');
  assert.equal(resolveOcrDetails({ ocr_confidence_score: 80 }).quality, 'good');
});

test('the most recent OCR job supplies the actual finish and fallback duration', () => {
  const document = { text_source: 'embedded', text_content: '<b>Originaltext</b>', jobs: [
    { type: 'OCR', created_at: '2026-10-01', started_at: '2026-10-01T10:00:00Z', finished_at: '2026-10-01T10:00:20Z' },
    { type: 'INDEX', created_at: '2026-10-30' },
    { type: 'OCR', created_at: '2026-10-29', started_at: '2026-10-29T10:00:00Z', finished_at: '2026-10-29T10:01:12Z' }
  ] };
  const result = resolveOcrDetails(document);
  assert.equal(result.duration, '1 Min. 12 Sek.');
  assert.match(result.finished, /29\.10\.2026/);
  assert.equal(result.source, 'Bereits im PDF enthalten');
  assert.equal(result.text, '<b>Originaltext</b>');
  assert.equal(result.hasText, true);
  assert.equal(resolveOcrDetails({ ocr_processing_seconds: 119.8 }).duration, '2 Min. 0 Sek.');
  assert.equal(resolveOcrDetails({ ocr_processing_seconds: 0.4 }).duration, 'Unter 1 Sekunde');
});

test('running and failed attempts do not present a stale successful quality rating', () => {
  const document = { ocr_quality_status: 'good', ocr_confidence_score: 98, ocr_processing_seconds: 20, flags: { ocr: { quality: { status: 'good', confidence_score: 98 } } } };
  for (const tone of ['progress', 'failed']) {
    const result = resolveOcrDetails(document, tone);
    assert.equal(result.quality, null);
    assert.equal(result.score, null);
    assert.equal(result.duration, '');
  }
  assert.equal(resolveOcrDetails({ jobs: [{ type: 'OCR', status: 'queued' }] }, 'progress').status, 'In Warteschlange');
  assert.equal(resolveOcrDetails({ text_content: '  ' }).hasText, false);
  assert.equal(resolveOcrDetails({}).finished, '');
});

test('missing assessments reuse saved OCR quality or average confidence without a new run', () => {
  const result = resolveOcrDetails({ flags: { ocr: { quality: { status: 'warning', confidence_score: 69.4, message: 'Einige Zeichen sind unsicher.' } } } });
  assert.equal(result.quality, 'warning');
  assert.equal(result.scoreLabel, '69,4 %');
  assert.equal(result.message, 'Einige Zeichen sind unsicher.');
  assert.equal(result.needsAssessment, false);
  const average = resolveOcrDetails({ flags: { ocr: { quality: { avg_confidence: .923 } } } });
  assert.equal(average.score, 92.3);
  assert.equal(average.quality, 'good');
  assert.equal(resolveOcrDetails({ flags: { ocr: { quality: { avg_confidence: 0 } } } }).score, 0);
});

test('current assessments take precedence and are not mixed with an older stored score', () => {
  const flags = { ocr: { quality: { status: 'good', confidence_score: 98, message: 'Alter Hinweis' } } };
  const current = resolveOcrDetails({ flags, ocr_confidence_score: 40, ocr_quality_message: 'Neuer Hinweis' });
  assert.equal(current.score, 40);
  assert.equal(current.quality, 'error');
  assert.equal(current.message, 'Neuer Hinweis');
  const unscored = resolveOcrDetails({ flags, ocr_quality_status: 'warning' });
  assert.equal(unscored.score, null);
  assert.equal(unscored.quality, 'warning');
  for (const tone of ['progress', 'failed']) {
    const busy = resolveOcrDetails({ flags }, tone);
    assert.equal(busy.score, null);
    assert.equal(busy.quality, null);
    assert.equal(busy.needsAssessment, false);
  }
});

test('invalid saved values produce the actionable unrated state rather than a fabricated rating', () => {
  const result = resolveOcrDetails({ flags: { ocr: { quality: { status: 'constructor', confidence_score: '90', avg_confidence: 1.1, message: {} } } } });
  assert.equal(result.quality, null);
  assert.equal(result.score, null);
  assert.equal(result.qualityLabel, 'Noch nicht bewertet');
  assert.equal(result.needsAssessment, true);
  assert.match(result.message, /erneut aus/);
});
