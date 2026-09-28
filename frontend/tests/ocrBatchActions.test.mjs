import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const panelSource = await readFile(
  new URL('../src/components/DocumentListPanel.vue', import.meta.url),
  'utf8',
);
const apiSource = await readFile(
  new URL('../src/api/documents.js', import.meta.url),
  'utf8',
);

test('document selection exposes OCR as a batch action', () => {
  assert.match(workspaceSource, /key: 'ocr',\s*label: 'OCR',\s*icon: 'mdi-text-recognition'/);
  assert.match(workspaceSource, /@action="handleDocumentBatchAction"/);
  assert.match(workspaceSource, /openOcrBatchDialog\('selection'\)/);
});

test('the list toolbar can start OCR for every matching page', () => {
  assert.match(workspaceSource, /key: 'ocr-list',\s*label: 'OCR für Liste'/);
  assert.match(workspaceSource, /const documentListRightActions = computed\(\(\) => \{[\s\S]*?\|\| !isNoTextView\.value[\s\S]*?return \[\];/);
  assert.match(panelSource, /:right-actions="rightActions"/);
  assert.match(workspaceSource, /async function collectCurrentDocumentListIds\(\)/);
  assert.match(workspaceSource, /limit: 100/);
  assert.match(workspaceSource, /openOcrBatchDialog\('list'\)/);
});

test('OCR batch actions require a preview and default to missing OCR only', () => {
  assert.match(workspaceSource, /const ocrBatchRerunCompleted = ref\(false\)/);
  assert.match(workspaceSource, /dryRun: true/);
  assert.match(workspaceSource, /:primary-disabled="isPreviewingOcrBatch \|\| !ocrBatchPreview\?\.eligible"/);
  assert.match(apiSource, /document_ids: documentIds/);
  assert.match(apiSource, /rerun_completed: rerunCompleted/);
  assert.match(apiSource, /dry_run: dryRun/);
});
