import { test, expect } from '@playwright/test';

async function mount(page, options = {}) {
  const requests = [];
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes('/color-preview')) return route.fulfill({ status: 404, body: '' });
    if (path.endsWith('/suggest-title')) return route.fulfill({ json: { status: 'ready', suggestion: '', meta: {} } });
    if (path === '/api/import/commit') {
      const body = route.request().postDataJSON();
      requests.push(body);
      return route.fulfill({ json: { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: `saved-${doc.client_document_id}`, title: doc.title, page_count: doc.pages.length })), errors: [] } });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/__import-workflow', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__import-workflow');
  await page.evaluate(options => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow(options)), options);
  await expect(page.getByRole('button', { name: /^Importieren \(/ })).toBeVisible();
  return requests;
}

test('empty title suggestions are hidden and optional fields allow a normal import', async ({ page }) => {
  const requests = await mount(page);
  await page.evaluate(() => {
    const doc = window.importFixture.store.documents[0];
    doc.meta.titleSuggestion = 'Ohne Betreff';
    doc.meta.titleSuggestionUsedFallback = true;
  });
  await expect(page.getByText('Ohne Betreff')).toHaveCount(0);
  await page.getByRole('button', { name: 'Importieren (3 Seiten)', exact: true }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents[0].date).toBeNull();
  expect(requests[0].documents[0].tag_ids).toEqual([]);
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('date uses the drawer normalization and a visible inline error', async ({ page }) => {
  await mount(page);
  const date = page.getByLabel('Dokumentdatum', { exact: true });
  await date.fill('31.2.2026');
  await date.blur();
  await expect(page.getByText(/Bitte ein gültiges Datum eingeben/)).toBeVisible();
  await date.fill('1.2.2026');
  await date.blur();
  await expect(date).toHaveValue('01.02.2026');
  await expect(page.getByText(/Bitte ein gültiges Datum eingeben/)).toHaveCount(0);
});

test('selection import preserves unselected pages and never sends a discard request', async ({ page }) => {
  const requests = await mount(page);
  let discards = 0;
  page.on('request', request => { if (request.url().includes('discard') || request.method() === 'DELETE') discards++; });
  await page.getByTitle('Seiten auswählen', { exact: true }).click();
  await page.locator('.isd-page-card').nth(1).click();
  await page.getByRole('button', { name: 'Auswahl importieren (1)' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents[0].pages.map(page => page.page_index)).toEqual([1]);
  expect(requests[0].preserve_source_ids).toHaveLength(1);
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
  expect(discards).toBe(0);
});

test('failed selection validation leaves every page intact', async ({ page }) => {
  const requests = await mount(page);
  await page.getByLabel('Dokumentname *', { exact: true }).fill('');
  await page.getByTitle('Seiten auswählen', { exact: true }).click();
  await page.locator('.isd-page-card').nth(1).click();
  await page.getByRole('button', { name: 'Auswahl importieren (1)' }).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  expect(requests).toHaveLength(0);
  await expect(page.getByText('Bitte einen Dokumentnamen eingeben.')).toBeVisible();
});

test('lost commit response retries the identical request and preserves all pages', async ({ page }) => {
  await mount(page);
  const attempts = [];
  await page.route('**/api/import/commit', async route => {
    const body = route.request().postDataJSON();
    attempts.push(body);
    if (attempts.length === 1) return route.abort('failed');
    return route.fulfill({ json: { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: 'saved', title: doc.title, page_count: 3, replayed: true })), errors: [] } });
  });
  await page.getByRole('button', { name: 'Importieren (3 Seiten)', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Importstatus prüfen' })).toBeEnabled();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await page.goto('/__import-workflow');
  await page.evaluate(() => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow({ restore: true })));
  await expect(page.getByRole('button', { name: 'Importstatus prüfen' })).toBeEnabled();
  await page.getByRole('button', { name: 'Importstatus prüfen' }).click();
  await expect.poll(() => attempts.length).toBe(2);
  expect(attempts[1]).toEqual(attempts[0]);
});

test('scanner session has explicit completion and cancellation actions', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => { window.importFixture.scannerActive.value = true; });
  await expect(page.getByRole('button', { name: 'Importieren (3 Seiten)', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Scannen abschließen' }).click();
  expect(await page.evaluate(() => window.importFixture.commands)).toContain('finish');
});

test('a targeted analysis sends only the explicitly selected page', async ({ page }) => {
  await mount(page);
  let request;
  await page.route('**/suggest-title', async route => {
    request = route.request().postDataJSON();
    return route.fulfill({ json: { status: 'ready', suggestion: '', meta: {} } });
  });
  await page.locator('.isd-page-card').nth(2).click();
  await page.getByRole('button', { name: 'Analyseaktionen' }).click();
  await page.getByText('Ausgewählte Seiten analysieren', { exact: true }).click();
  await expect.poll(() => request?.pages?.length).toBe(1);
  expect(request.pages[0].page_index).toBe(2);
  expect(request.force).toBe(true);
});

test('partial success removes only acknowledged documents and retries only the failure', async ({ page }) => {
  await mount(page, { documents: 2 });
  const requests = [];
  await page.route('**/api/import/commit', async route => {
    const body = route.request().postDataJSON();
    requests.push(body);
    return route.fulfill({ json: requests.length === 1 ? {
      created: [{ client_document_id: body.documents[0].client_document_id, doc_id: 'saved-first', title: 'Erstes', page_count: 3 }],
      errors: [{ client_document_id: body.documents[1].client_document_id, message: 'Konvertierung vorübergehend ausgelastet.', retryable: true }],
    } : { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: 'saved-second', title: doc.title, page_count: 3 })), errors: [] } });
  });
  await page.getByRole('button', { name: 'Importieren (6 Seiten)', exact: true }).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await expect(page.getByText('Konvertierung vorübergehend ausgelastet.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Importieren (3 Seiten)', exact: true }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].documents).toHaveLength(1);
  expect(requests[1].documents[0].client_document_id).toBe(requests[0].documents[1].client_document_id);
});

test('a late analysis cannot overwrite typing or a deliberately cleared type', async ({ page }) => {
  await mount(page);
  let response;
  await page.route('**/suggest-title', async route => {
    response = route;
  });
  await page.getByRole('button', { name: 'Analyseaktionen' }).click();
  await page.getByText('Metadaten neu analysieren', { exact: true }).click();
  await expect.poll(() => Boolean(response)).toBe(true);
  await page.getByLabel('Dokumentname *', { exact: true }).fill('Mein eigener Titel');
  await page.evaluate(() => {
    const form = window.importFixture.store.documents[0].meta.form;
    form.category = null;
    form.touched.category = true;
    form.revisions.category = (form.revisions.category || 0) + 1;
  });
  await response.fulfill({ json: { status: 'ready', suggestion: 'Verspäteter KI-Titel', meta: { document_type: 'Brief', analysis_phase: 'llm' } } });
  await expect(page.getByLabel('Dokumentname *', { exact: true })).toHaveValue('Mein eigener Titel');
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].meta.form.category)).toBeNull();
});

test('changed page order rejects a response for the old document revision', async ({ page }) => {
  await mount(page);
  let first;
  await page.route('**/suggest-title', route => { first ||= route; });
  await page.getByRole('button', { name: 'Analyseaktionen' }).click();
  await page.getByText('Metadaten neu analysieren', { exact: true }).click();
  await expect.poll(() => Boolean(first)).toBe(true);
  await page.evaluate(() => { window.importFixture.store.documents[0].pages.reverse(); });
  const revision = first.request().postDataJSON().documentRevision;
  await first.fulfill({ json: { status: 'ready', suggestion: 'Falsche alte Reihenfolge', meta: { document_revision: revision } } });
  await expect(page.getByLabel('Dokumentname *', { exact: true })).toHaveValue('Arbeitsstätte');
});

test('draft fields and page order survive reloading for the same account', async ({ page }) => {
  await mount(page);
  await page.getByLabel('Dokumentname *', { exact: true }).fill('Wiederhergestellter Import');
  await page.getByLabel('Dokumentdatum', { exact: true }).fill('1.2.2026');
  await page.getByLabel('Dokumentdatum', { exact: true }).blur();
  await expect.poll(() => page.evaluate(async () => {
    const { importDraftStorage } = await import('/src/utils/importDraftStorage.js');
    return (await importDraftStorage('import-browser-test'))?.documents?.[0]?.title;
  })).toBe('Wiederhergestellter Import');
  await mount(page, { restore: true });
  await expect(page.getByLabel('Dokumentname *', { exact: true })).toHaveValue('Wiederhergestellter Import');
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('01.02.2026');
});

test('wide and narrow import layouts keep fields and actions visible', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page);
  await expect(page.getByLabel('Dokumentname *', { exact: true })).toBeVisible();
  await page.screenshot({ path: '/private/tmp/papermind-import-screen.png', fullPage: true });
  await page.setViewportSize({ width: 430, height: 900 });
  await expect(page.getByRole('button', { name: 'Importieren (3 Seiten)', exact: true })).toBeVisible();
  expect((await page.getByLabel('Dokumentname *', { exact: true }).boundingBox()).width).toBeGreaterThan(250);
  await page.screenshot({ path: '/private/tmp/papermind-import-mobile.png', fullPage: true });
});

test('a draft from another account is never restored into the active account', async ({ page }) => {
  await mount(page);
  await page.getByLabel('Dokumentname *', { exact: true }).fill('Privater Entwurf von Konto eins');
  await expect.poll(() => page.evaluate(async () => {
    const { importDraftStorage } = await import('/src/utils/importDraftStorage.js');
    return (await importDraftStorage('import-browser-test'))?.documents?.[0]?.title;
  })).toBe('Privater Entwurf von Konto eins');
  await page.goto('/__import-workflow');
  await page.evaluate(() => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow({ restore: true, owner: 'different-account' })));
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.importFixture.store.documents.length)).toBe(0);
  await expect(page.getByText('Privater Entwurf von Konto eins', { exact: true })).toHaveCount(0);
});
