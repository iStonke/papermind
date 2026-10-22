import { test, expect } from '@playwright/test';
import { mount, revealImportTools } from './fixtures/importHarness.js';

const image = version => `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1400"><rect width="1000" height="1400" fill="white"/><text x="50" y="80">Version ${version}</text></svg>`;

async function readDraft(page, owner = 'import-browser-test') {
  return page.evaluate(async owner => (await import('/src/utils/importDraftStorage.js')).importDraftStorage(owner), owner);
}

test('colour changes affect display only; replacing the source invalidates analysis', async ({ page }) => {
  await mount(page, { pages: 2 });
  const calls = [];
  await page.route('**/suggest-title', route => { calls.push(route.request().postDataJSON()); return route.fulfill({ json:{ status:'ready', suggestion:'', meta:{} } }); });
  await page.clock.install();
  await revealImportTools(page);
  await page.getByRole('button', { name:'Graustufen', exact:true }).click();
  await page.clock.runFor(1600);
  expect(calls).toHaveLength(0);
  await page.evaluate(() => { for (const meta of window.importFixture.store.sourceMetaById.values()) meta.sourceRevision = 'version-2'; });
  await page.clock.runFor(900);
  await expect.poll(() => calls.length).toBe(1);
});

test('inactive sharp images cannot outlive a source revision', async ({ page }) => {
  await mount(page, { pages:2 });
  await page.route('**/color-preview?*', route => route.fulfill({ contentType:'image/svg+xml', body:image(1) }));
  // Change a display property to trigger a new request after installing the route.
  await page.evaluate(() => { window.importFixture.store.documents[0].pages[0].rotation = 180; });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy','false');
  await expect.poll(() => page.locator('.isd-preview-image').evaluate(el=>el.naturalWidth)).toBe(1000);
  const old = await page.locator('.isd-preview-image').getAttribute('src');
  await page.locator('.isd-page-card').nth(1).dispatchEvent('click');
  await expect.poll(() => page.locator('.isd-preview-image').evaluate(el=>el.naturalWidth)).toBe(1000);
  let latest;
  await page.route('**/color-preview?*', route => { latest = route; });
  await page.evaluate(() => { for (const meta of window.importFixture.store.sourceMetaById.values()) meta.sourceRevision='version-2'; });
  await page.locator('.isd-page-card').nth(0).dispatchEvent('click');
  await expect(page.locator('.isd-preview-image')).not.toHaveAttribute('src',old);
  await expect.poll(() => Boolean(latest)).toBe(true);
  await latest.fulfill({ contentType:'image/svg+xml', body:image(2) });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy','false');
  await expect(page.locator('.isd-preview-image')).not.toHaveAttribute('src',old);
});

for (const zoom of [1, 1.25]) test(`100 page stack keeps stable slots and bounded images at layout zoom ${zoom}`, async ({ page }) => {
  await page.setViewportSize({width:1440,height:1000});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await mount(page,{pages:100});
  await page.evaluate(zoom=>{document.documentElement.style.zoom=zoom;window.originalSlots=[...document.querySelectorAll('.isd-preview-page')];},zoom);
  const slots=page.locator('.isd-preview-page'), stage=page.locator('.isd-preview-stage');
  await expect(slots).toHaveCount(100);
  for (const index of [20,50,99,2]) {
    await page.locator('.isd-page-card').nth(index).dispatchEvent('click');
    await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt',`Seite ${index+1} von 100`);
    await expect.poll(()=>page.locator('.isd-preview-page-image').count()).toBeLessThanOrEqual(8);
    await expect.poll(()=>page.evaluate(index=>{
      const stage=document.querySelector('.isd-preview-stage').getBoundingClientRect();
      const page=document.querySelectorAll('.isd-preview-page')[index].getBoundingClientRect();
      return Math.abs((page.top+page.bottom)/2-(stage.top+stage.bottom)/2);
    },index)).toBeLessThan(3);
  }
  await stage.hover();
  for (const delta of [40,70,110,160,220]) await page.mouse.wheel(0,delta);
  await expect.poll(()=>stage.evaluate(el=>getComputedStyle(el).cursor)).toBe('default');
  await expect.poll(()=>page.locator('.isd-page-card--selected').count()).toBe(1);
  expect(await page.evaluate(()=>window.originalSlots.every((el,i)=>el===document.querySelectorAll('.isd-preview-page')[i]))).toBe(true);
  expect(errors).toEqual([]);
});

test('draft assets are stored once, field edits write metadata and restoration hydrates files and images', async ({ page }) => {
  await mount(page,{pages:2});
  await page.evaluate(()=>{
    const store=window.importFixture.store;
    const id=store.documents[0].pages[0].sourceFileId;
    store.stagingFiles.set(id,new File(['synthetic-pdf'], 'test.pdf',{type:'application/pdf'}));
    window.assetWrites=0;
    const original=IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put=function(...args){if(this.name==='assets') window.assetWrites++;return original.apply(this,args);};
    store.documents[0].title='Gesicherter Entwurf';
  });
  await expect.poll(async()=> (await readDraft(page))?.documents[0].title).toBe('Gesicherter Entwurf');
  const writes=await page.evaluate(()=>window.assetWrites);expect(writes).toBeGreaterThan(0);
  await page.getByLabel('Notizen',{exact:true}).fill('Eine Änderung ohne erneutes Speichern der PDF.');
  await expect.poll(async()=> (await readDraft(page))?.documents[0].meta.form.note).toContain('Eine Änderung');
  expect(await page.evaluate(()=>window.assetWrites)).toBe(writes);
  await mount(page,{restore:true});
  await expect(page.getByLabel('Notizen',{exact:true})).toHaveValue('Eine Änderung ohne erneutes Speichern der PDF.');
  expect(await page.evaluate(()=>[...window.importFixture.store.stagingFiles.values()][0].size)).toBe(13);
  await expect(page.locator('.isd-page-thumb')).toHaveCount(2);
  await expect.poll(()=>page.evaluate(()=>window.importFixture.component.value.diagnostics().filter(row=>row.event==='draft_saved').at(-1)?.bytes)).toBe(0);
});

test('two concurrent writers cannot overwrite the same draft and delete tombstones preserve the revision', async ({ page }) => {
  await mount(page);
  const result=await page.evaluate(async()=>{
    const {importDraftStorage}=await import('/src/utils/importDraftStorage.js');
    const owner='conflict-test', value={version:2,documents:[{id:'one',pages:[]}],sourceMeta:[],files:[],assetRefs:[]};
    const initial=await importDraftStorage(owner,value,true,{expectedRevision:0});
    const settled=await Promise.allSettled([
      importDraftStorage(owner,{...value,batchId:'winner-a'},true,{expectedRevision:initial.revision}),
      importDraftStorage(owner,{...value,batchId:'winner-b'},true,{expectedRevision:initial.revision}),
    ]);
    const saved=await importDraftStorage(owner);
    const deleted=await importDraftStorage(owner,null,true,{expectedRevision:saved.revision});
    let stale;
    try {await importDraftStorage(owner,value,true,{expectedRevision:saved.revision});}catch(e){stale=e.name;}
    return {states:settled.map(r=>r.status),error:settled.find(r=>r.status==='rejected').reason.name,revision:deleted.revision,stale};
  });
  expect(result.states.sort()).toEqual(['fulfilled','rejected']);expect(result.error).toBe('DraftConflictError');
  expect(result.revision).toBe(3);expect(result.stale).toBe('DraftConflictError');
});

test('quota/aborted asset writes preserve the previous complete draft', async ({ page }) => {
  await mount(page);
  const result=await page.evaluate(async()=>{
    const {importDraftStorage}=await import('/src/utils/importDraftStorage.js');
    const owner='quota-test',value={version:2,documents:[{id:'one',title:'Letzter sicherer Stand',pages:[]}],sourceMeta:[],files:[],assetRefs:[]};
    const initial=await importDraftStorage(owner,value,true,{expectedRevision:0});
    const original=IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put=function(...args){ if(this.name==='assets') {this.transaction.abort();throw new DOMException('full','QuotaExceededError');}return original.apply(this,args);};
    let error;
    try {await importDraftStorage(owner,{...value,documents:[{title:'Unsicher'}],assetRefs:['new']},true,{expectedRevision:initial.revision,assets:[['new',new Blob(['x'])]]});}catch(e){error=e.name;}
    finally {IDBObjectStore.prototype.put=original;}
    const saved=await importDraftStorage(owner);return {error,title:saved.documents[0].title,revision:saved.revision};
  });
  expect(result.title).toBe('Letzter sicherer Stand');expect(result.revision).toBe(1);expect(result.error).toBeTruthy();
});

test('legacy draft migration restores metadata and unavailable sources without dropping pages', async ({page})=>{
  await mount(page);
  await page.evaluate(async()=>{
    const {importDraftStorage}=await import('/src/utils/importDraftStorage.js');
    const store=window.importFixture.store;
    const value={version:1,batchId:'legacy',createdAt:1,documents:JSON.parse(JSON.stringify(store.documents)),sourceMeta:JSON.parse(JSON.stringify([...store.sourceMetaById])),files:[],pendingCommit:{body:{request_id:'durable'},submitted:{}}};
    value.documents[0].title='Altbestand';value.documents[0].pages[0].thumbUrl='';
    await importDraftStorage('legacy-owner',value,true);
  });
  await mount(page,{owner:'legacy-owner',restore:true});
  await expect(page.getByLabel('Dokumentname',{exact:true})).toHaveValue('Altbestand');
  expect(await page.evaluate(()=>window.importFixture.store.documents[0].pages.length)).toBe(3);
  expect(await page.evaluate(()=>window.importFixture.store.documents[0].pages[0].previewError)).toBe(true);
  expect(await page.evaluate(()=>window.importFixture.store.pendingCommit.body.request_id)).toBe('durable');
});

test('an actual second window blocks stale commits and closing it cannot delete shared sources', async ({page,context})=>{
  const requests=await mount(page,{pages:1});
  await page.getByLabel('Dokumentname',{exact:true}).fill('Erstes Fenster');
  await expect.poll(async()=> (await readDraft(page))?.documents[0].title).toBe('Erstes Fenster');
  const other=await context.newPage();
  await mount(other,{restore:true});
  await other.getByLabel('Dokumentname',{exact:true}).fill('Zweites Fenster');
  await expect.poll(async()=> (await readDraft(other))?.documents[0].title).toBe('Zweites Fenster');
  await page.getByLabel('Dokumentname',{exact:true}).fill('Lokale Eingabe bleibt erhalten');
  await expect.poll(()=>page.evaluate(()=>window.importFixture.component.value.diagnostics().filter(row=>row.event==='draft_saved').length)).toBeGreaterThan(0);
  // Waiting for the conflict-driven disabled state also waits for the write attempt.
  await page.evaluate(()=>{const {store,correspondents}=window.importFixture;correspondents.correspondents=[{id:'known',name:'Firma'}];Object.assign(store.documents[0].meta.form,{date:'20.10.2026',category:'Brief',correspondentId:'known'});store.documents[0].meta.pendingTagNames=['Unterlagen'];});
  await expect(page.getByRole('button',{name:'Importieren',exact:true})).toBeDisabled();
  await expect(page.getByLabel('Dokumentname',{exact:true})).toHaveValue('Lokale Eingabe bleibt erhalten');
  const deletes=[];await page.route('**/api/import/source/*',route=>{if(route.request().method()==='DELETE') deletes.push(route.request().url());return route.fulfill({json:{}});});
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(deletes).toEqual([]);expect(requests).toEqual([]);
  expect((await readDraft(other)).documents[0].title).toBe('Zweites Fenster');
  await other.close();
});

test('commit waits for durable request storage and retry uses the same request id', async({page})=>{
  const {completeRequiredMetadata}=await import('./fixtures/importHarness.js');
  const requests=await mount(page,{pages:1});await completeRequiredMetadata(page);
  await expect.poll(async()=> (await readDraft(page))?.documents[0].meta.form.date).toBe('20.10.2026');
  await page.evaluate(()=>{
    window.originalPut=IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put=function(...args){if(this.name==='drafts') throw new DOMException('full','QuotaExceededError');return window.originalPut.apply(this,args);};
  });
  await page.getByRole('button',{name:'Importieren',exact:true}).click();
  const retry=page.getByRole('button',{name:'Importstatus prüfen',exact:true});await expect(retry).toBeEnabled();
  expect(requests).toHaveLength(0);
  const id=await page.evaluate(()=>window.importFixture.store.pendingCommit.body.request_id);
  await page.evaluate(()=>{IDBObjectStore.prototype.put=window.originalPut;});
  await retry.click();await expect.poll(()=>requests.length).toBe(1);expect(requests[0].request_id).toBe(id);
});

test('unknown draft schemas are preserved for recovery instead of overwritten on mount',async({page})=>{
  await mount(page);
  await page.evaluate(()=>new Promise((resolve,reject)=>{
    const request=indexedDB.open('papermind-import-drafts',2);
    request.onsuccess=()=>{const db=request.result,tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').put({version:99,documents:[{title:'Unbekanntes Format',pages:[]}],sourceMeta:[]},'future-owner');tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};
  }));
  await mount(page,{owner:'future-owner',restore:true});
  const record=await page.evaluate(()=>new Promise(resolve=>{const request=indexedDB.open('papermind-import-drafts',2);request.onsuccess=()=>{const db=request.result,tx=db.transaction('drafts'),read=tx.objectStore('drafts').get('future-owner');tx.oncomplete=()=>{db.close();resolve(read.result);};};}));
  expect(record.version).toBe(99);expect(record.documents[0].title).toBe('Unbekanntes Format');
  expect(await page.evaluate(()=>window.importFixture.store.documents.length)).toBe(0);
});

test('the local PDF fallback respects colour changes when the preview endpoint is unavailable',async({page})=>{
  await mount(page,{pages:1});
  const stream='1 0 0 rg 0 0 595 842 re f';
  const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents 4 0 R >>',`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`];
  let pdf='%PDF-1.4\n';const offsets=[];
  objects.forEach((object,index)=>{offsets.push(pdf.length);pdf+=`${index+1} 0 obj\n${object}\nendobj\n`;});
  const xref=pdf.length;pdf+=`xref\n0 5\n0000000000 65535 f \n${offsets.map(offset=>`${String(offset).padStart(10,'0')} 00000 n \n`).join('')}trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  await page.evaluate(data=>{
    const {store}=window.importFixture;const source=store.documents[0].pages[0].sourceFileId;
    store.setStagingFile(source,new File([data],'red.pdf',{type:'application/pdf'}),{pageCount:1,sourceRevision:'local-red'});
  },pdf);
  const sample=()=>page.locator('.isd-preview-image').evaluate(image=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
    const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,1,1);return [...ctx.getImageData(0,0,1,1).data];
  });
  await expect.poll(()=>page.locator('.isd-preview-image').evaluate(image=>image.naturalHeight)).toBe(1400);
  const red=await sample();expect(red[0]).toBeGreaterThan(240);expect(red[1]).toBeLessThan(15);
  await revealImportTools(page);await page.getByRole('button',{name:'Graustufen',exact:true}).click();
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy','false');
  await expect.poll(async()=>{const [r,g,b]=await sample();return Math.max(r,g,b)-Math.min(r,g,b);}).toBeLessThan(3);
  await expect.poll(()=>page.locator('.isd-preview-image').evaluate(image=>image.naturalHeight)).toBe(1400);
});
