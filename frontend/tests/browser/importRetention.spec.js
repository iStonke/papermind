import { test, expect } from '@playwright/test';
import { mount, completeRequiredMetadata } from './fixtures/importHarness.js';

const sourceId = '40000000-0000-4000-8000-000000000001';
const readDraft = page => page.evaluate(async () => (await import('/src/utils/importDraftStorage.js')).importDraftStorage('import-browser-test'));
const reopen = page => page.evaluate(() => { window.importFixture.open.value = true; });
async function close(page) {
  await page.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.importFixture.store.totalPages)).toBe(0);
}

test('closing retains form values, AI origins, page edits and PDF assets across reload', async ({ page }) => {
  await mount(page);
  const destructive = [];
  page.on('request', request => { if (request.method() === 'DELETE' || request.url().includes('/discard')) destructive.push(request.url()); });
  await page.getByLabel('Dokumentname', { exact: true }).fill('Mein geschlossener Import');
  await page.getByLabel('Dokumentdatum', { exact: true }).fill('22.10.2026');
  await page.getByLabel('Notizen', { exact: true }).fill('Diese Notiz bleibt erhalten.');
  await page.evaluate(() => {
    const store = window.importFixture.store, doc = store.documents[0];
    doc.pages.reverse();doc.pages[0].rotation = 90;store.setAllPagesColorMode('grayscale');
    doc.meta.form.aiFilled.category = 'KI';doc.meta.form.category = 'Brief';
    doc.meta.form.correspondentId = 'my-correspondent';doc.tags = ['my-tag'];
    store.stagingFiles.set(doc.pages[0].sourceFileId, new File(['saved-pdf'], 'Mein Dokument.pdf', { type: 'application/pdf' }));
    window.expectedPages = JSON.parse(JSON.stringify(doc.pages));
  });
  const expectedPages = await page.evaluate(() => window.expectedPages);
  await close(page);
  await expect.poll(async () => (await readDraft(page))?.availableDraft?.documents[0].title).toBe('Mein geschlossener Import');
  expect(destructive).toEqual([]);
  await mount(page, { restore: true });
  const available = page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true });
  await expect(available).toBeVisible();
  await expect(page.getByRole('button', { name: 'Import minimieren', exact: true })).toHaveCount(0);
  await available.click();
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Mein geschlossener Import');
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('22.10.2026');
  await expect(page.getByLabel('Notizen', { exact: true })).toHaveValue('Diese Notiz bleibt erhalten.');
  const result = await page.evaluate(() => {
    const store = window.importFixture.store, doc = store.documents[0];
    return { pages: doc.pages, categoryOrigin: doc.meta.form.aiFilled.category, correspondent: doc.meta.form.correspondentId,
      tags: doc.tags, fileName: [...store.stagingFiles.values()][0].name, savedPages: store.availablePageCount };
  });
  expect(result.pages).toEqual(expectedPages);expect(result.categoryOrigin).toBe('KI');
  expect(result.correspondent).toBe('my-correspondent');expect(result.tags).toEqual(['my-tag']);
  expect(result.fileName).toBe('Mein Dokument.pdf');expect(result.savedPages).toBe(0);
});

test('closing an empty window preserves the last import and a new nonempty close replaces it', async ({ page }) => {
  await mount(page);
  await close(page);await reopen(page);
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  await close(page);await reopen(page);
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  await page.evaluate(sourceId => window.importFixture.component.value.openWithRemoteSources({ sources: [
    { source_file_id: sourceId, original_name: 'Neuer Entwurf.pdf', page_count: 1, source_revision: 'one' },
  ] }), sourceId);
  await expect(page.locator('.isd-page-card')).toHaveCount(1);
  await close(page);
  await expect.poll(async () => (await readDraft(page))?.availableDraft?.documents[0].pages.length).toBe(1);
  await mount(page, { restore: true });
  await page.getByRole('button', { name: '1 verfügbare Seite öffnen', exact: true }).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(1);
  expect(await page.evaluate(() => window.importFixture.store.documents[0].pages[0].sourceFileId)).toBe(sourceId);
});

test('an upload can finish after closing without reopening the window or losing its pages', async ({ page }) => {
  await mount(page, { documents: 0 });
  let upload;
  await page.route('**/api/import/source', route => { upload = route; });
  const picker = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'PDFs auswählen Eine oder mehrere PDF-Dateien', exact: true }).click();
  await (await picker).setFiles({ name: 'Später Upload.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n%%EOF') });
  await expect.poll(() => Boolean(upload)).toBe(true);
  await page.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await upload.fulfill({ json: { items: [{ source_file_id: sourceId, original_name: 'Später Upload.pdf', page_count: 2 }] } });
  await expect.poll(() => page.evaluate(() => window.importFixture.store.availablePageCount)).toBe(2);
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await reopen(page);
  await page.getByRole('button', { name: '2 verfügbare Seiten öffnen', exact: true }).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
});

test('a late source PDF download is saved into the closed draft without reopening it', async ({ page }) => {
  await mount(page, { documents: 0 });
  let download;
  await page.route('**/api/import/source/*/file', route => { download = route; });
  await page.evaluate(sourceId => window.importFixture.component.value.openWithRemoteSources({ sources: [
    { source_file_id: sourceId, original_name: 'Späte Quelle.pdf', page_count: 1, source_revision: 'late-1' },
  ] }), sourceId);
  await expect.poll(() => Boolean(download)).toBe(true);
  await close(page);
  await download.fulfill({ contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF' });
  await expect.poll(() => page.evaluate(() => window.importFixture.store.availableDraft.files.map(([id, file]) => ({ id, name: file?.name })))).toEqual([{ id: sourceId, name: 'Späte Quelle.pdf' }]);
  await expect.poll(() => page.evaluate(async () => {
    const draft = await (await import('/src/utils/importDraftStorage.js')).importDraftStorage('import-browser-test');
    return draft?.availableDraft?.files[0]?.[1]?.name;
  })).toBe('Späte Quelle.pdf');
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await mount(page, { restore: true });
  await page.getByRole('button', { name: '1 verfügbare Seite öffnen', exact: true }).click();
  expect(await page.evaluate(() => [...window.importFixture.store.stagingFiles.values()][0].name)).toBe('Späte Quelle.pdf');
});

test('closing during an uncertain commit preserves its durable request for an exact retry', async ({ page }) => {
  await mount(page);await completeRequiredMetadata(page);
  let held;
  const attempts = [];
  await page.route('**/api/import/commit', route => {
    const body = route.request().postDataJSON();attempts.push(body);
    if (attempts.length === 1) { held = route;return; }
    return route.fulfill({ json: { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: 'created' })), errors: [] } });
  });
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  await expect.poll(() => Boolean(held)).toBe(true);
  await page.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await held.fulfill({ status: 503, json: { message: 'Antwort vorübergehend nicht verfügbar' } });
  await expect.poll(() => page.evaluate(() => window.importFixture.store.availablePageCount)).toBe(3);
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await reopen(page);await page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true }).click();
  await page.getByRole('button', { name: 'Importstatus prüfen', exact: true }).click();
  await expect.poll(() => attempts.length).toBe(2);
  expect(attempts[1]).toEqual(attempts[0]);
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await reopen(page);await expect(page.locator('.isd-dropzone')).toBeVisible();
  await expect(page.locator('.isd-dropzone__available-pages')).toHaveCount(0);
});
