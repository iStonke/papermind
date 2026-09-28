import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { didOcrReachTerminalState } from '../src/workspaces/documents/ocrStatusTransition.js';

const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);

test('detects OCR jobs that leave the active queue', () => {
  assert.equal(didOcrReachTerminalState('queued', 'done'), true);
  assert.equal(didOcrReachTerminalState('running', 'done'), true);
  assert.equal(didOcrReachTerminalState('running', 'failed'), true);
  assert.equal(didOcrReachTerminalState('queued', 'running'), false);
  assert.equal(didOcrReachTerminalState('done', 'done'), false);
});

test('OCR completion refreshes the no-text list and its sidebar count together', () => {
  const start = workspaceSource.indexOf('async function refreshDocumentStatuses(documentIds)');
  const end = workspaceSource.indexOf('function startDocumentListSettle()', start);
  const handler = workspaceSource.slice(start, end);

  assert.ok(start >= 0 && end > start, 'OCR status refresh handler should be present');
  assert.match(handler, /didOcrReachTerminalState\(document\.ocr_status, statusUpdate\.ocr_status\)/);
  assert.match(handler, /const refreshes = \[fetchSidebarCounts\(\)\];/);
  assert.match(handler, /if \(isNoTextView\.value\) \{\s*refreshes\.push\(fetchDocuments\(selectedDocumentId\.value, \{ silent: true \}\)\);/);
  assert.match(handler, /await Promise\.all\(refreshes\);/);
});
