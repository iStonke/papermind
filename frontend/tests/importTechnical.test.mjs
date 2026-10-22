import test from 'node:test';
import assert from 'node:assert/strict';
import { documentRevision, analysisRevision, pageDisplayRevision } from '../src/utils/importWorkflow.js';
import { createByteLruCache } from '../src/utils/byteLruCache.js';
import { createPdfSourcePool } from '../src/utils/pdfSourcePool.js';
import { createImportAnalysisQueue, abortableDelay } from '../src/utils/importAnalysisQueue.js';
import { setImportAnalysisState, importProcessState } from '../src/utils/importProcess.js';
import { createImportDiagnostics } from '../src/utils/importDiagnostics.js';
import { convertImportPreviewPixels } from '../src/utils/importPreviewPixels.js';
import { migrateImportDraft } from '../src/utils/importDraftStorage.js';

test('analysis is independent of display colour; order, rotation and source version still invalidate it', () => {
  const doc = { pages: [{ id:'a', sourceFileId:'source', pageIndex:0, colorMode:'auto', rotation:0, thumbUrl:'old' }, { id:'b', sourceFileId:'source', pageIndex:1 }] };
  const meta = new Map([['source', { sourceRevision:'v1' }]]);
  const initial = analysisRevision(doc, meta), display = documentRevision(doc, meta), page = pageDisplayRevision(doc.pages[0], meta);
  doc.pages[0].colorMode = 'grayscale';
  assert.equal(analysisRevision(doc, meta), initial); assert.notEqual(documentRevision(doc, meta), display);
  assert.notEqual(pageDisplayRevision(doc.pages[0], meta), page);
  doc.pages[0].rotation = 90; assert.notEqual(analysisRevision(doc, meta), initial);
  doc.pages[0].rotation = 0; doc.pages.reverse(); assert.notEqual(analysisRevision(doc, meta), initial);
  doc.pages.reverse(); meta.get('source').sourceRevision = 'v2'; assert.notEqual(analysisRevision(doc, meta), initial);
});

test('image cache has a byte bound, true LRU access and neighbour priority', () => {
  const removed = [], cache = createByteLruCache({ budget:10, cost:v=>v, dispose:(_, key)=>removed.push(key) });
  cache.set('a',4); cache.set('b',4); cache.protect(['a']); cache.set('c',4);
  assert.equal(cache.get('b'), undefined); assert.equal(cache.bytes,8);
  cache.get('c'); cache.protect([]); cache.set('d',4); assert.equal(cache.get('a'), undefined);
  assert.equal(cache.set('oversize',11),false); assert.ok(cache.bytes<=10);
  cache.clear(); assert.equal(cache.bytes,0); assert.equal(removed.length,5);
});

test('PDF pool shares concurrent opens, leases survive eviction and replaced files never reuse old bytes', async () => {
  let opens=0, destroys=0;
  const pool=createPdfSourcePool(async () => ({ number:++opens, destroy:async()=>{destroys++;} }), { maxSources:1 });
  const file=new Blob(['one']), replacement=new Blob(['two']);
  const [a,b]=await Promise.all([pool.acquire('source',file),pool.acquire('source',file)]);
  assert.equal(opens,1); assert.equal(a.pdf,b.pdf);
  const c=await pool.acquire('source',replacement); assert.notEqual(c.pdf,a.pdf);
  assert.equal(destroys,0); a.release(); b.release(); await Promise.resolve(); assert.equal(destroys,1);
  c.release(); pool.close(); await Promise.resolve(); assert.equal(destroys,2);
});

test('failed PDF opens are removed and a retry can recover', async () => {
  let calls=0;
  const pool=createPdfSourcePool(async()=>{ if (++calls===1) throw new Error('invalid'); return { destroy(){} }; });
  const file=new Blob(['pdf']); await assert.rejects(pool.acquire('x',file));
  const lease=await pool.acquire('x',file); lease.release(); pool.close(); assert.equal(calls,2);
});

test('analysis queue aborts stale work and backoff before starting the next document', async () => {
  const queue=createImportAnalysisQueue(), events=[];
  const first=queue.enqueue('a','v1',async signal=>{events.push('a');await abortableDelay(60000,signal);events.push('a-end');});
  const duplicate=queue.enqueue('a','v1',()=>assert.fail('duplicate')); assert.equal(first,duplicate);
  const second=queue.enqueue('b','v1',()=>events.push('b'));
  await Promise.resolve(); await Promise.resolve();
  queue.reconcile(new Map([['b','v1']])); await Promise.all([first,second]);
  assert.deepEqual(events,['a','a-end','b']); assert.equal(queue.jobs.size,0); queue.close();
});

test('process transitions remove contradictory pending/error flags and commit blockers have fixed precedence', () => {
  const meta={analysisReconnecting:true,analysisLookupPending:true};
  setImportAnalysisState(meta,'llm'); assert.equal(meta.analysisLookupPending,false); assert.equal(meta.analysisPending,true);
  setImportAnalysisState(meta,'complete'); assert.equal(meta.analysisPending,false); assert.equal(meta.titleSuggestionStatus,'ready');
  setImportAnalysisState(meta,'error'); assert.equal(meta.analysisPending,false);
  assert.deepEqual(importProcessState({pages:2,cleanup:true,analysis:'llm'}),{phase:'cleanup',busy:true,blocksCommit:true});
  assert.equal(importProcessState({pages:2,analysis:'llm'}).blocksCommit,false);
  assert.equal(importProcessState({pages:2,conflict:true}).blocksCommit,true);
});

test('diagnostics are bounded, numeric only and never retain document identifiers or text', () => {
  let time=0; const d=createImportDiagnostics({now:()=>time,limit:3});
  d.start('private-source','analysis_start'); time=12; d.end('private-source','analysis_complete',{pages:2,title:'secret',source_file_id:'private-source'});
  d.once('one','first_metadata');d.once('one','first_metadata');d.record('commit_start');
  const rows=d.snapshot();assert.equal(rows.length,3);assert.equal(rows[0].duration_ms,12);
  assert.equal(JSON.stringify(rows).includes('secret'),false);assert.equal(JSON.stringify(rows).includes('private-source'),false);
});

test('draft migration accepts legacy records but rejects unknown schemas without discarding them', () => {
  assert.equal(migrateImportDraft({version:1,documents:[],sourceMeta:[]}).revision,0);
  assert.throws(()=>migrateImportDraft({version:99,documents:[],sourceMeta:[]}));
  assert.throws(()=>migrateImportDraft({version:2,documents:[],sourceMeta:[],assetRefs:[],availableDraft:{documents:[{}],sourceMeta:[]}}));
});


test('local preview colour conversion preserves alpha and original pixels in auto mode', () => {
  const original = new Uint8ClampedArray([255,0,0,127,0,255,0,255]);
  assert.deepEqual(convertImportPreviewPixels(original.slice(),'auto'),original);
  assert.deepEqual([...convertImportPreviewPixels(original.slice(),'grayscale')],[76,76,76,127,150,150,150,255]);
  assert.deepEqual([...convertImportPreviewPixels(original.slice(),'bw')],[0,0,0,127,255,255,255,255]);
});
