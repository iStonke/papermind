import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveOcrHeaderPresentation } from '../src/workspaces/documents/ocrHeaderState.js';

const baseState = {
  hasDocument: true,
  ocrStatus: 'not_started',
  inProgress: false,
  hasCompletedOcr: false,
  qualityStatus: null
};

test('failed OCR replaces the overflow action with a retry chip', () => {
  const result = resolveOcrHeaderPresentation({
    ...baseState,
    ocrStatus: 'failed'
  });

  assert.deepEqual(result, {
    status: {
      tone: 'failed',
      text: 'OCR fehlgeschlagen',
      icon: 'mdi-refresh'
    },
    showMenuAction: false
  });
});

test('failed OCR wins over a stale processing document status', () => {
  const result = resolveOcrHeaderPresentation({
    ...baseState,
    ocrStatus: 'failed',
    inProgress: true
  });

  assert.equal(result.status?.tone, 'failed');
  assert.equal(result.showMenuAction, false);
});

test('OCR that has never run remains available in the overflow menu', () => {
  assert.deepEqual(resolveOcrHeaderPresentation(baseState), {
    status: null,
    showMenuAction: true
  });
});

test('running and completed OCR never add an overflow action', () => {
  const running = resolveOcrHeaderPresentation({ ...baseState, inProgress: true });
  const completed = resolveOcrHeaderPresentation({
    ...baseState,
    ocrStatus: 'done',
    hasCompletedOcr: true
  });

  assert.equal(running.status?.tone, 'progress');
  assert.equal(running.showMenuAction, false);
  assert.equal(completed.status?.tone, 'done');
  assert.equal(completed.showMenuAction, false);
});
