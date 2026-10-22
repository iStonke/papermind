import test from 'node:test';
import assert from 'node:assert/strict';
import { importAvailability, shouldLoadInboxIntoOpenImport } from '../src/workspaces/documents/importAvailability.js';

test('background availability includes pending PDF pages and minimized draft pages', () => {
  assert.deepEqual(importAvailability({pendingCount:4,documents:[{pages:[{sourceFileId:'local',pageIndex:0}]}]}),{pendingPages:4,totalPages:5});
  assert.deepEqual(importAvailability(),{pendingPages:0,totalPages:0});
});

test('a restored source is counted once and removed draft pages do not return in the badge', () => {
  assert.deepEqual(importAvailability({pendingCount:7,items:[{source_file_id:'restored',page_count:5},{source_file_id:'other',page_count:2}],
    documents:[{pages:[{sourceFileId:'restored',pageIndex:0},{sourceFileId:'restored',pageIndex:4}]}]}),{pendingPages:2,totalPages:4});
});

test('closed draft pages and new background pages are available together without duplicate sources', () => {
  assert.deepEqual(importAvailability({pendingCount:5,items:[{source_file_id:'saved',page_count:3},{source_file_id:'background',page_count:2}],
    availableDocuments:[{pages:[{sourceFileId:'saved',pageIndex:0},{sourceFileId:'saved',pageIndex:2}]}]}),{pendingPages:2,totalPages:4});
  assert.equal(shouldLoadInboxIntoOpenImport({open:true,stagedPages:0,scannerActive:false,activeItems:3}),false);
});

test('invalid counts cannot leak into the badge', () => {
  for(const pendingCount of [-1,NaN,Infinity,'bad']) assert.equal(importAvailability({pendingCount}).totalPages,0);
  assert.equal(importAvailability({pendingCount:102.5}).totalPages,102);
});

test('opening an empty import keeps pending pages behind the explicit source choice', () => {
  assert.equal(shouldLoadInboxIntoOpenImport({open:true,stagedPages:0,scannerActive:false,activeItems:0}),false);
  assert.equal(shouldLoadInboxIntoOpenImport({open:true,stagedPages:2}),true);
  assert.equal(shouldLoadInboxIntoOpenImport({open:true,scannerActive:true}),true);
  assert.equal(shouldLoadInboxIntoOpenImport({open:false,stagedPages:2,scannerActive:true}),false);
});
