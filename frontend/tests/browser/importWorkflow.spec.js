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
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeVisible();
  return requests;
}

async function revealImportTools(page) {
  await page.locator('.isd-preview-panel').hover();
  await expect(page.getByRole('toolbar', { name: 'Seitenwerkzeuge' })).toHaveCSS('opacity', '1');
}
async function startImportAnalysis(page) {
  await page.locator('.isd-props-heading .isd-ai-status-btn').click();
}

async function completeRequiredMetadata(page) {
  await page.evaluate(() => {
    const { store, correspondents } = window.importFixture;
    correspondents.correspondents = [{ id: '30000000-0000-4000-8000-000000000001', name: 'Testfirma', kind: 'organization' }];
    for (const doc of store.documents) {
      Object.assign(doc.meta.form, { date: '20.10.2026', category: 'Brief', correspondentId: correspondents.correspondents[0].id });
      doc.meta.pendingTagNames = ['Unterlagen'];
    }
  });
}

test('empty title suggestions are hidden and a complete form imports without notes', async ({ page }) => {
  const requests = await mount(page);
  await completeRequiredMetadata(page);
  await page.evaluate(() => {
    const doc = window.importFixture.store.documents[0];
    doc.meta.titleSuggestion = 'Ohne Betreff';
    doc.meta.titleSuggestionUsedFallback = true;
  });
  await expect(page.getByText('Ohne Betreff')).toHaveCount(0);
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents[0].date).toBe('2026-10-20');
  expect(requests[0].documents[0].tag_names).toEqual(['Unterlagen']);
  expect(requests[0].documents[0].note).toBeNull();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

for (const action of ['discard', 'commit', 'minimize', 'empty']) test(`${action} closes at its current size with the standard dialog animation`, async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { documents: action === 'empty' ? 0 : 1 });
  await page.evaluate(() => import('/src/style.css'));
  if (action === 'commit') await completeRequiredMetadata(page);
  const card = page.locator('.isd-card.pm-dialog');
  const width = await card.evaluate(element => parseFloat(getComputedStyle(element).width));
  await page.evaluate(() => {
    const card = document.querySelector('.isd-card.pm-dialog');
    const overlay = card.closest('.v-overlay__content');
    window.importCloseFrames = [];
    const sample = () => {
      if (!card.isConnected) return;
      if (overlay.checkVisibility()) window.importCloseFrames.push({
        width: parseFloat(getComputedStyle(card).width), closing: !window.importFixture.open.value,
        standardAnimation: overlay.classList.contains('pm-dialog-leave-active'),
      });
      requestAnimationFrame(sample);
    };
    sample();
  });
  if (action === 'commit') await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  else if (action === 'minimize') await page.getByRole('button', { name: 'Import minimieren', exact: true }).click();
  else {
    await card.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
    if (action === 'discard') await page.getByRole('button', { name: 'Verwerfen', exact: true }).click();
  }
  await expect(card).toHaveCount(0);
  const frames = await page.evaluate(() => window.importCloseFrames);
  expect(frames.every(frame => Math.abs(frame.width - width) < 1)).toBe(true);
  expect(frames.filter(frame => frame.closing).length).toBeGreaterThan(1);
  expect(frames.some(frame => frame.standardAnimation)).toBe(true);
  expect(await page.evaluate(() => window.importFixture.store.totalPages)).toBe(action === 'minimize' ? 3 : 0);
  await page.evaluate(() => { window.importFixture.open.value = true; });
  await expect(card).toBeVisible();
  await expect(card).toHaveCSS('width', action === 'minimize' ? `${width}px` : '680px');
  if (action !== 'minimize') await expect(page.locator('.isd-dropzone')).toBeVisible();
});

test('required metadata has no stars, blocks incomplete imports and focuses the missing field', async ({ page }) => {
  const requests = await mount(page);
  await expect(page.locator('.pm-metadata-label')).toHaveText(['Dokumentname', 'Dokumentdatum', 'Dokumenttyp', 'Korrespondent', 'Tags', 'Notizen']);
  await expect(page.getByText('Nur Notizen sind optional.')).toBeVisible();
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveAttribute('required', '');
  await expect(page.getByLabel('Notizen', { exact: true })).not.toHaveAttribute('required');
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  for (const message of ['Bitte ein Dokumentdatum eingeben.', 'Bitte einen Dokumenttyp wählen.', 'Bitte einen Korrespondenten wählen.', 'Bitte mindestens einen Tag hinzufügen.']) {
    await expect(page.getByText(message, { exact: true })).toBeVisible();
  }
  expect(requests).toHaveLength(0);
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toBeFocused();
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 1 von 3');
  await page.getByLabel('Dokumentdatum', { exact: true }).fill('20.10.2026');
  await page.locator('[data-field="category"] .v-field').click();
  await page.getByRole('option', { name: 'Brief', exact: true }).click();
  await page.evaluate(() => { window.importFixture.correspondents.correspondents = [{ id: '30000000-0000-4000-8000-000000000001', name: 'Testfirma', kind: 'organization' }]; });
  await page.locator('[data-field="correspondent"] .v-field').click();
  await page.getByRole('option', { name: 'Testfirma', exact: true }).click();
  await page.getByText('Tags', { exact: true }).click();
  const tags = page.getByRole('combobox', { name: 'Tag hinzufügen', exact: true });
  await tags.fill('Unterlagen');
  await tags.press('Enter');
  await expect(page.locator('.pm-metadata-error')).toHaveCount(0);
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents[0].note).toBeNull();
  expect(requests[0].documents[0].tag_names).toEqual(['Unterlagen']);
});

for (const failure of ['analysis-result', 'http-error']) test(`internal OCR diagnostics stay hidden for legacy drafts and ${failure}`, async ({ page }) => {
  await mount(page);
  const diagnostic = 'source=5d5c3d0d-c509-4ada-ba18-56ebdfb329ba page=0 psm=6: Die PDF-Seite konnte nicht verarbeitet werden.';
  await page.evaluate(diagnostic => { window.importFixture.store.documents[0].meta.analysisError = diagnostic; }, diagnostic);
  await expect(page.locator('body')).not.toContainText(diagnostic);
  await page.route('**/suggest-title', route => route.fulfill(failure === 'analysis-result'
    ? { json: { status: 'error', suggestion: '', meta: { analysis_status: 'ocr_failed', analysis_error: diagnostic, ocr: { errors: [diagnostic] } } } }
    : { status: 400, json: { error: { message: diagnostic } } }));
  await startImportAnalysis(page);
  await expect(page.locator('.isd-ai-status-btn--failed')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('source=');
  await expect(page.locator('body')).not.toContainText('psm=');
  await expect(page.getByRole('button', { name: 'Analyse wiederholen', exact: true })).toBeEnabled();
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Arbeitsstätte');
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

test('early fields appear before slow lookups and late replies preserve manual input', async ({ page }) => {
  await mount(page, { pages: 1 });
  let post;
  let posts = 0;
  let finished = false;
  const lookups = [];
  await page.route(url => url.pathname === '/api/tags' || url.pathname === '/api/correspondents', route => { lookups.push(route); });
  await page.evaluate(async () => { (await import('/src/stores/correspondents.js')).useCorrespondentStore().isLoaded = false; });
  await page.route('**/suggest-title', route => { post = route; posts++; });
  await page.route(url => url.pathname.includes('/stages/') && url.pathname.endsWith('/analysis'), route => route.fulfill({ json: finished
    ? { status: 'ready', suggestion: 'TSV Flintbek Kündigung', meta: { analysis_job_id: 'progress', analysis_sequence: 3, analysis_phase: 'llm', analysis_pending: false,
      date: '2026-03-16', document_type: 'Brief', sender_raw: 'Sportverein', correspondent: { id: 'sport', name: 'Sportverein' }, note: 'Deine Mitgliedschaft endet am 30. Juni 2026.', tags: ['Sportverein', 'Mitgliedschaft'] } }
    : { status: 'ready', suggestion: 'Kündigung', meta: { analysis_job_id: 'progress', analysis_sequence: 2, analysis_phase: 'rule', progress_phase: 'llm', analysis_pending: true,
      date: '2026-03-16', document_type: 'Brief', tags: ['Sportverein'] } } }));
  await startImportAnalysis(page);
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveAttribute('placeholder', 'Wird ermittelt…');
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Kündigung');
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('16.03.2026');
  await expect(page.locator('[data-field="date"] .pm-metadata-ai-chip')).toBeVisible();
  await expect(page.locator('.isd-ai-status-btn--busy')).toBeVisible();
  await page.screenshot({ path: '/private/tmp/papermind-progressive-import-early.png' });
  await expect.poll(() => lookups.length).toBeGreaterThan(0);
  await page.getByLabel('Dokumentname', { exact: true }).fill('Mein geprüfter Dokumentname');
  // An older request may fail after the newer rule result was already shown.
  await post.fulfill({ json: { status: 'error', suggestion: '', meta: { analysis_job_id: 'progress', analysis_sequence: 1, analysis_pending: false } } });
  await expect(page.locator('.isd-ai-status-btn--failed')).toHaveCount(0);
  finished = true;
  await expect(page.getByLabel('Notizen', { exact: true })).toHaveValue('Deine Mitgliedschaft endet am 30. Juni 2026.');
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Mein geprüfter Dokumentname');
  await expect(page.locator('[data-field="date"] .pm-metadata-ai-chip')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Absender wird zugeordnet – Details anzeigen', exact: true })).toBeVisible();
  expect(posts).toBe(1);
  await expect.poll(() => lookups.some(route => new URL(route.request().url()).pathname === '/api/correspondents')).toBe(true);
  for (const route of lookups) await route.fulfill({ json: { items: [] } });
  await expect(page.locator('.isd-ai-status-btn--busy')).toHaveCount(0);
  await page.screenshot({ path: '/private/tmp/papermind-progressive-import-filled.png' });
});

test('a lost request keeps observing the server job without a false failure or duplicate POST', async ({ page }) => {
  await mount(page, { pages: 1 });
  let posts = 0;
  let finished = false;
  await page.route('**/suggest-title', route => { posts++; return route.abort('failed'); });
  await page.route(url => url.pathname.includes('/stages/') && url.pathname.endsWith('/analysis'), route => route.fulfill({ json: finished
    ? { status: 'ready', suggestion: 'Erkannter Brief', meta: { analysis_phase: 'llm', analysis_pending: false, date: '2026-10-15' } }
    : { status: 'pending_ocr', suggestion: '', meta: { analysis_pending: true, progress_phase: 'ocr' } } }));
  await startImportAnalysis(page);
  await expect(page.getByRole('button', { name: 'Text wird erkannt – Details anzeigen', exact: true })).toBeVisible();
  await expect(page.locator('.isd-ai-status-btn--failed')).toHaveCount(0);
  finished = true;
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('15.10.2026');
  await expect(page.locator('.isd-ai-status-btn--busy')).toHaveCount(0);
  expect(posts).toBe(1);
});

test('a failed refinement retains early fields and leaves missing fields editable', async ({ page }) => {
  await mount(page, { pages: 1 });
  let finished = false;
  await page.route('**/suggest-title', route => route.fulfill({ json: { status: 'ready', suggestion: 'Erkannter Brief', meta: {
    analysis_job_id: 'partial', analysis_sequence: 2, analysis_phase: 'rule', analysis_pending: true, date: '2026-10-15' } } }));
  await page.route(url => url.pathname.includes('/stages/') && url.pathname.endsWith('/analysis'), route => route.fulfill({ json: finished
    ? { status: 'error', suggestion: '', meta: { analysis_job_id: 'partial', analysis_sequence: 3, analysis_pending: false } }
    : { status: 'ready', suggestion: 'Erkannter Brief', meta: { analysis_job_id: 'partial', analysis_sequence: 2, analysis_phase: 'rule', analysis_pending: true, date: '2026-10-15' } } }));
  await startImportAnalysis(page);
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('15.10.2026');
  finished = true;
  await expect(page.locator('.isd-ai-status-btn--partial')).toBeVisible();
  await expect(page.locator('.isd-ai-status-btn--failed')).toHaveCount(0);
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('15.10.2026');
  await expect(page.getByLabel('Notizen', { exact: true })).toHaveAttribute('placeholder', 'Notiz hinzufügen…');
  await page.getByLabel('Notizen', { exact: true }).fill('Manuell ergänzt');
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeEnabled();
});

test('a cached preliminary result starts observation even though the title is already available', async ({ page }) => {
  await mount(page, { pages: 1 });
  let posts = 0;
  await page.route('**/suggest-title', route => { posts++; return route.fulfill({ json: {
    status: 'pending_ocr', suggestion: '', meta: { analysis_pending: true, progress_phase: 'llm' } } }); });
  await page.route(url => url.pathname.includes('/stages/') && url.pathname.endsWith('/analysis'), route => route.fulfill({ json: {
    status: 'ready', suggestion: 'Kündigung', meta: { analysis_phase: 'llm', analysis_pending: false,
      date: '2026-03-16', note: 'Die Mitgliedschaft endet am 30. Juni 2026.' } } }));
  await page.evaluate(() => window.importFixture.component.value.openWithRemoteSources({ sessionId: 'cached-progress', sources: [{
    source_file_id: window.importFixture.store.documents[0].pages[0].sourceFileId,
    page_count: 1, source_revision: 'revision-1', analysis: { status: 'ready', suggestion: 'Kündigung',
      meta: { result_revision: 'cached-rule', analysis_phase: 'rule', refinement_pending: true, date: '2026-03-16' } },
  }] }));
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('16.03.2026');
  await expect(page.getByLabel('Notizen', { exact: true })).toHaveValue('Die Mitgliedschaft endet am 30. Juni 2026.');
  await expect(page.locator('.isd-ai-status-btn--busy')).toHaveCount(0);
  expect(posts).toBe(1);
});

test('the 90-second browser timeout leaves an active server analysis running', async ({ page }) => {
  await page.clock.install();
  await mount(page, { pages: 1 });
  let posts = 0;
  let finished = false;
  await page.route('**/suggest-title', () => { posts++; });
  await page.route(url => url.pathname.includes('/stages/') && url.pathname.endsWith('/analysis'), route => route.fulfill({ json: finished
    ? { status: 'ready', suggestion: 'Später erkannter Brief', meta: { analysis_pending: false, analysis_phase: 'llm', date: '2026-10-15' } }
    : { status: 'pending_ocr', suggestion: '', meta: { analysis_pending: true, progress_phase: 'llm' } } }));
  await startImportAnalysis(page);
  await expect(page.getByRole('button', { name: 'KI analysiert Dokument – Details anzeigen', exact: true })).toBeVisible();
  await page.clock.fastForward(91000);
  await expect(page.locator('.isd-ai-status-btn--busy')).toBeVisible();
  await expect(page.locator('.isd-ai-status-btn--failed')).toHaveCount(0);
  await page.locator('.isd-ai-status-btn--busy').focus();
  await expect(page.getByRole('tooltip')).toContainText('Die Erkennung dauert etwas länger');
  finished = true;
  await page.clock.fastForward(11000);
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('15.10.2026');
  await expect(page.locator('.isd-ai-status-btn--busy')).toHaveCount(0);
  expect(posts).toBe(1);
});

test('checking an interrupted analysis reuses the job instead of forcing new work', async ({ page }) => {
  await mount(page, { pages: 1 });
  let body;
  await page.route('**/suggest-title', route => {
    body = route.request().postDataJSON();
    return route.fulfill({ json: { status: 'ready', suggestion: 'Erkannter Brief', meta: { analysis_pending: false, analysis_phase: 'llm' } } });
  });
  await page.getByLabel('Dokumentname', { exact: true }).fill('Eigener Dokumentname');
  await page.evaluate(() => { window.importFixture.store.documents[0].meta.titleSuggestionStatus = 'interrupted'; });
  await page.getByRole('button', { name: 'Analysestatus aktualisieren', exact: true }).click();
  await expect.poll(() => body?.force).toBe(false);
  expect(body.repeatOcr).toBe(false);
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Eigener Dokumentname');
});

test('selection import preserves unselected pages and never sends a discard request', async ({ page }) => {
  const requests = await mount(page);
  await completeRequiredMetadata(page);
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
  await completeRequiredMetadata(page);
  await page.getByLabel('Dokumentname', { exact: true }).fill('');
  await page.getByTitle('Seiten auswählen', { exact: true }).click();
  await page.locator('.isd-page-card').nth(1).click();
  await page.getByRole('button', { name: 'Auswahl importieren (1)' }).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  expect(requests).toHaveLength(0);
  await expect(page.getByText('Bitte einen Dokumentnamen eingeben.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Auswahl importieren (1)' })).toBeVisible();
});

test('lost commit response retries the identical request and preserves all pages', async ({ page }) => {
  await mount(page);
  await completeRequiredMetadata(page);
  const attempts = [];
  await page.route('**/api/import/commit', async route => {
    const body = route.request().postDataJSON();
    attempts.push(body);
    if (attempts.length === 1) return route.abort('failed');
    return route.fulfill({ json: { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: 'saved', title: doc.title, page_count: 3, replayed: true })), errors: [] } });
  });
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Importstatus prüfen' })).toBeEnabled();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await page.goto('/__import-workflow');
  await page.evaluate(() => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow({ restore: true })));
  await expect(page.getByRole('button', { name: 'Importstatus prüfen' })).toBeEnabled();
  await page.getByRole('button', { name: 'Importstatus prüfen' }).click();
  await expect.poll(() => attempts.length).toBe(2);
  expect(attempts[1]).toEqual(attempts[0]);
});

test('scanner session can be cancelled from the scan preview', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => { window.importFixture.scannerActive.value = true; });
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Scan abbrechen', exact: true }).click();
  expect(await page.evaluate(() => window.importFixture.commands)).toContain('cancel');
});

for (const width of [1440, 430]) test.describe(`preparation status at ${width}px`, () => {
  test.use({ viewport: { width, height: 1000 }, hasTouch: width === 430 });
  test('stays in the form header and opens accessibly', async ({ page }) => {
    await mount(page);
    await page.evaluate(() => {
      const fixture = window.importFixture;
      for (const meta of fixture.store.sourceMetaById.values()) meta.scanCleanup = { status: 'running' };
    });
    const statusButton = page.getByRole('button', { name: 'Scan wird verbessert – Details anzeigen', exact: true });
    await expect(statusButton).toBeVisible();
    await expect(page.locator('.isd-props-heading .v-progress-circular')).toHaveCount(1);
    await expect(page.locator('.isd-preview-panel .v-progress-circular')).toHaveCount(0);
    await page.mouse.move(0, 0);
    if (width === 1440) await expect(page.getByRole('toolbar', { name: 'Seitenwerkzeuge' })).toHaveCSS('opacity', '0');
    await expect(page.locator('.isd-props-heading [role="status"]')).toHaveText('Scan wird verbessert');
    await expect(page.locator('.isd-footer')).not.toContainText('Die Scan-Seiten werden noch verbessert.');
    await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
    const fits = await statusButton.evaluate(button => {
      const rect = button.getBoundingClientRect();
      const header = button.closest('.isd-props-heading');
      const bounds = header.getBoundingClientRect();
      const title = header.querySelector('.isd-props-title').getBoundingClientRect();
      return rect.width <= 36 && rect.left >= title.right + 8 && rect.right <= bounds.right - 16;
    });
    expect(fits).toBe(true);
    if (width === 1440) await statusButton.focus();
    else await statusButton.tap();
    await expect(page.getByRole('tooltip')).toBeVisible();
    await expect(page.getByRole('tooltip')).toContainText('Die Scan-Seiten werden noch verbessert.');
    await expect(page.getByRole('tooltip')).toHaveClass(/v-overlay--active/);
    await expect(page.getByRole('tooltip').locator('.v-overlay__content')).toHaveCSS('transform', 'none');
    await expect.poll(async () => (await page.getByRole('tooltip').locator('.v-overlay__content').boundingBox())?.width || 0).toBeGreaterThan(200);
    await page.screenshot({ path: `/private/tmp/papermind-import-preparation-${width}.png` });
    await page.evaluate(() => {
      const fixture = window.importFixture;
      fixture.store.documents[0].meta.titleSuggestionStatus = 'working';
      for (const meta of fixture.store.sourceMetaById.values()) meta.scanCleanup = { status: 'ready' };
    });
    await expect(page.getByRole('button', { name: 'KI analysiert Dokument – Details anzeigen', exact: true })).toBeVisible();
    await expect(page.locator('.isd-props-heading [role="status"]')).toHaveText('KI analysiert Dokument');
    await expect(page.getByRole('tooltip')).toContainText('Verfügbare Angaben erscheinen nach und nach.');
    if (width === 1440) await page.keyboard.press('Escape');
    else await page.getByLabel('Dokumentname', { exact: true }).tap();
    await expect(page.getByRole('tooltip').locator('.v-overlay__content')).not.toBeVisible();
    await expect(page.getByRole('dialog')).toHaveCount(1);
    await page.evaluate(() => { window.importFixture.store.documents[0].meta.titleSuggestionStatus = 'ready'; });
    await expect(page.locator('.isd-ai-status-btn--busy')).toHaveCount(0);
    await expect(page.getByRole('tooltip')).not.toHaveClass(/v-overlay--active/);
    await expect(page.getByRole('tooltip').locator('.v-overlay__content')).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeEnabled();
  });

  test('keeps the AI action visible while scrolling the form', async ({ page }) => {
    await page.setViewportSize({ width, height: 720 });
    await mount(page);
    await page.evaluate(() => {
      const doc = window.importFixture.store.documents[0];
      doc.meta.titleSuggestionStatus = 'working';
      doc.meta.analysisPhase = 'ocr';
    });
    const status = page.locator('.isd-props-heading [role="status"]');
    await expect(status).toHaveText('Text wird erkannt');
    await page.getByLabel('Notizen', { exact: true }).scrollIntoViewIfNeeded();
    await expect(page.getByLabel('Notizen', { exact: true })).toBeInViewport();
    const button = page.getByRole('button', { name: 'Text wird erkannt – Details anzeigen', exact: true });
    await expect(button).toBeInViewport();
    await expect.poll(() => page.evaluate(() => {
      const heading = document.querySelector('.isd-props-heading').getBoundingClientRect();
      const body = document.querySelector('.isd-body').getBoundingClientRect();
      return Math.abs(heading.top - body.top);
    })).toBeLessThan(2);
    await page.evaluate(() => { window.importFixture.store.documents[0].meta.analysisPhase = 'llm'; });
    await expect(status).toHaveText('KI analysiert Dokument');
    const updatedButton = page.getByRole('button', { name: 'KI analysiert Dokument – Details anzeigen', exact: true });
    if (width === 1440) await updatedButton.focus();
    else await updatedButton.tap();
    await expect(page.getByRole('tooltip')).toContainText('Du kannst die Formularfelder bereits bearbeiten.');
    await page.screenshot({ path: `/private/tmp/papermind-import-analysis-header-scroll-${width}.png` });
  });
});

test('partial success removes only acknowledged documents and retries only the failure', async ({ page }) => {
  await mount(page, { documents: 2 });
  await completeRequiredMetadata(page);
  const requests = [];
  await page.route('**/api/import/commit', async route => {
    const body = route.request().postDataJSON();
    requests.push(body);
    return route.fulfill({ json: requests.length === 1 ? {
      created: [{ client_document_id: body.documents[0].client_document_id, doc_id: 'saved-first', title: 'Erstes', page_count: 3 }],
      errors: [{ client_document_id: body.documents[1].client_document_id, message: 'Konvertierung vorübergehend ausgelastet.', retryable: true }],
    } : { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: 'saved-second', title: doc.title, page_count: 3 })), errors: [] } });
  });
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await expect(page.getByText('Konvertierung vorübergehend ausgelastet.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
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
  await startImportAnalysis(page);
  await expect.poll(() => Boolean(response)).toBe(true);
  await page.getByLabel('Dokumentname', { exact: true }).fill('Mein eigener Titel');
  await page.evaluate(() => {
    const form = window.importFixture.store.documents[0].meta.form;
    form.category = null;
    form.touched.category = true;
    form.revisions.category = (form.revisions.category || 0) + 1;
  });
  await response.fulfill({ json: { status: 'ready', suggestion: 'Verspäteter KI-Titel', meta: { document_type: 'Brief', analysis_phase: 'llm' } } });
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Mein eigener Titel');
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].meta.form.category)).toBeNull();
});

test('changed page order rejects a response for the old document revision', async ({ page }) => {
  await mount(page);
  let first;
  await page.route('**/suggest-title', route => { first ||= route; });
  await startImportAnalysis(page);
  await expect.poll(() => Boolean(first)).toBe(true);
  await page.evaluate(() => { window.importFixture.store.documents[0].pages.reverse(); });
  const revision = first.request().postDataJSON().documentRevision;
  await first.fulfill({ json: { status: 'ready', suggestion: 'Falsche alte Reihenfolge', meta: { document_revision: revision } } });
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Arbeitsstätte');
});

test('draft fields and page order survive reloading for the same account', async ({ page }) => {
  await mount(page);
  await page.getByLabel('Dokumentname', { exact: true }).fill('Wiederhergestellter Import');
  await page.getByLabel('Dokumentdatum', { exact: true }).fill('1.2.2026');
  await page.getByLabel('Dokumentdatum', { exact: true }).blur();
  await expect.poll(() => page.evaluate(async () => {
    const { importDraftStorage } = await import('/src/utils/importDraftStorage.js');
    return (await importDraftStorage('import-browser-test'))?.documents?.[0]?.title;
  })).toBe('Wiederhergestellter Import');
  await mount(page, { restore: true });
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Wiederhergestellter Import');
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toHaveValue('01.02.2026');
});

test('wide and narrow import layouts keep fields and actions visible', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page);
  await expect(page.getByLabel('Dokumentname', { exact: true })).toBeVisible();
  await page.screenshot({ path: '/private/tmp/papermind-import-screen.png', fullPage: true });
  await page.setViewportSize({ width: 430, height: 900 });
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeVisible();
  expect((await page.getByLabel('Dokumentname', { exact: true }).boundingBox()).width).toBeGreaterThan(250);
  await page.screenshot({ path: '/private/tmp/papermind-import-mobile.png', fullPage: true });
});

test('the page list stays vertical beside a persistent preview and its tools at every window size', async ({ page }) => {
  await mount(page);
  for (const width of [1440, 1024, 768, 430, 360, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 1 von 3');
    const layout = await page.evaluate(() => {
      const rect = selector => document.querySelector(selector).getBoundingClientRect();
      const rail = rect('.isd-grid-scroll');
      const preview = rect('.isd-preview-panel');
      const toolbar = rect('.isd-toolbar');
      const pages = [...document.querySelectorAll('.isd-page-card')].map(page => page.getBoundingClientRect());
      const tools = [...document.querySelectorAll('.isd-toolbar button')].filter(button => button.checkVisibility()).map(button => button.getBoundingClientRect());
      return { vertical: pages.every((page, index) => Math.abs(page.left - pages[0].left) < 1 && (!index || page.top >= pages[index - 1].bottom)),
        previewBeside: preview.left >= rail.right - 1, toolbarOverlay: toolbar.left >= preview.left - 1 && toolbar.right <= preview.right + 1 && toolbar.top >= preview.top && toolbar.bottom <= preview.bottom,
        toolsFit: tools.every(tool => tool.left >= toolbar.left && tool.right <= toolbar.right),
        noHorizontalOverflow: document.querySelector('.isd-body').scrollWidth <= document.querySelector('.isd-body').clientWidth };
    });
    expect(layout, `${width}px`).toEqual({ vertical: true, previewBeside: true, toolbarOverlay: true, toolsFit: true, noHorizontalOverflow: true });
  }
});

test('floating import tools reveal on hover and keyboard focus', async ({ page }) => {
  await mount(page);
  const toolbar = page.getByRole('toolbar', { name: 'Seitenwerkzeuge' });
  await page.mouse.move(0, 0);
  await expect(toolbar).toHaveCSS('opacity', '0');
  await revealImportTools(page);
  await page.mouse.move(0, 0);
  await expect(toolbar).toHaveCSS('opacity', '0');
  await page.locator('.isd-preview-stage').focus();
  await page.keyboard.press('Shift+Tab');
  await expect(toolbar).toHaveCSS('opacity', '1');
  expect(await toolbar.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await page.mouse.move(0, 0);
  await expect(toolbar).toHaveCSS('opacity', '1');
  await page.getByLabel('Dokumentname', { exact: true }).focus();
  await expect(toolbar).toHaveCSS('opacity', '0');
});

test('color adjustments cover all import pages, later scans and the exported documents', async ({ page }) => {
  const requests = await mount(page, { documents: 2, pages: 2 });
  await page.getByTitle('Seiten auswählen', { exact: true }).click();
  await page.locator('.isd-page-card').nth(2).click();
  await revealImportTools(page);
  const colors = page.getByRole('group', { name: 'Farbmodus für alle Seiten', exact: true });
  for (const [label, mode] of [['Graustufen', 'grayscale'], ['Originalfarbe des Scans', 'color'], ['Automatische Scanbereinigung beibehalten', 'auto'], ['Graustufen', 'grayscale']]) {
    await colors.getByRole('button', { name: label, exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.importFixture.store.documents.flatMap(doc => doc.pages.map(page => page.colorMode)))).toEqual(Array(4).fill(mode));
    await expect(colors.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-pressed', 'true');
  }
  await expect(page.locator('.isd-page-card').filter({ hasText: 'Graustufen' })).toHaveCount(0);
  expect(await page.locator('.import-staging-page__thumb').evaluateAll(images => images.every(image => image.style.filter === 'grayscale(1)'))).toBe(true);
  await page.route('**/api/global-color-live-preview', route => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="280"><rect width="200" height="280" fill="#137c80"/></svg>' }));
  await page.evaluate(() => {
    const fixture = window.importFixture;
    fixture.scannerActive.value = true;
    fixture.scanner.value = { ...fixture.scanner.value, scan_progress: 50, live_preview_url: '/api/global-color-live-preview' };
  });
  await expect(page.locator('.isd-scanning-page-preview')).toBeVisible();
  await expect(page.locator('.isd-scanning-page-preview')).toHaveCSS('filter', 'grayscale(1)');
  await page.evaluate(() => {
    const fixture = window.importFixture;
    fixture.scannerActive.value = false;
    fixture.scanner.value = { ...fixture.scanner.value, scan_progress: null, live_preview_url: null };
  });
  await page.getByTitle('Auswahl beenden', { exact: true }).click();
  await page.evaluate(() => {
    const { store } = window.importFixture;
    const sourceFileId = '10000000-0000-4000-8000-000000000099';
    store.setStagingFile(sourceFileId, null, { pageCount: 1, sourceRevision: 'later-scan' });
    store.appendSourceToDocument(store.documents[0].id, { sourceFileId, pageCount: 1 });
  });
  await expect(page.locator('.isd-page-card')).toHaveCount(5);
  await completeRequiredMetadata(page);
  await page.getByRole('button', { name: 'Importieren', exact: true }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents.flatMap(doc => doc.pages.map(page => page.color_mode))).toEqual(Array(5).fill('grayscale'));
});

test('preview zoom fits the page and editing tools work through deleting the last page', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { pages: 1 });
  await revealImportTools(page);
  await page.getByRole('button', { name: 'Vergrößern', exact: true }).click();
  await page.getByRole('button', { name: 'Vergrößern', exact: true }).click();
  await expect(page.getByRole('button', { name: /Zoom 125 Prozent/ })).toBeVisible();
  expect(await page.locator('.isd-preview-stage').evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
  await page.getByRole('button', { name: /Zoom 125 Prozent/ }).click();
  await expect(page.getByRole('button', { name: /Zoom 100 Prozent/ })).toBeVisible();
  expect(await page.locator('.isd-preview-stage').evaluate(element => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
  await page.getByRole('button', { name: 'Nach rechts drehen', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].rotation)).toBe(90);
  await expect.poll(async () => { const rect = await page.locator('.isd-preview-image').boundingBox(); return rect.width > rect.height; }).toBe(true);
  await page.getByRole('button', { name: 'Graustufen', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].colorMode)).toBe('grayscale');
  await page.getByRole('button', { name: 'Automatische Scanbereinigung beibehalten', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].colorMode)).toBe('auto');
  await page.getByRole('button', { name: 'Nach links drehen', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].rotation)).toBe(0);
  await page.getByRole('button', { name: 'Ausgewählte Seiten löschen', exact: true }).click();
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
});

for (const width of [430, 320]) test.describe(`floating import tools on touch at ${width}px`, () => {
  test.use({ viewport: { width, height: 1000 }, hasTouch: true });
  test('remain visible and expose direct editing actions', async ({ page }) => {
    await mount(page);
    const toolbar = page.getByRole('toolbar', { name: 'Seitenwerkzeuge' });
    await expect(toolbar).toHaveCSS('opacity', '1');
    await page.getByRole('button', { name: 'Vergrößern', exact: true }).tap();
    await expect(page.getByRole('button', { name: /Zoom 112 Prozent/ })).toBeVisible();
    await page.getByRole('button', { name: 'Nach rechts drehen', exact: true }).tap();
    await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].rotation)).toBe(90);
    await page.getByRole('button', { name: 'Graustufen', exact: true }).tap();
    await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].colorMode)).toBe('grayscale');
    await expect(toolbar).toHaveCSS('opacity', '1');
    expect(await toolbar.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      const parent = element.parentElement.getBoundingClientRect();
      return bounds.left >= parent.left && bounds.right <= parent.right;
    })).toBe(true);
  });
});

test('preview navigation crosses document boundaries, follows reordering and keeps the active page visible', async ({ page }) => {
  await mount(page, { documents: 2, pages: 6 });
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 1 von 12');
  await page.locator('.isd-page-card').first().focus();
  const toolbarTop = (await page.locator('.isd-toolbar').boundingBox()).y;
  for (let index = 0; index < 7; index++) await page.keyboard.press('ArrowDown');
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 8 von 12');
  await expect(page.locator('.isd-page-card--selected')).toBeFocused();
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Dokument 2');
  const inView = await page.locator('.isd-page-card--selected').evaluate(page => {
    const rect = page.getBoundingClientRect();
    const rail = page.closest('.isd-grid-scroll').getBoundingClientRect();
    return rect.top >= rail.top - 1 && rect.bottom <= rail.bottom + 1;
  });
  expect(inView).toBe(true);
  expect((await page.locator('.isd-toolbar').boundingBox()).y).toBe(toolbarTop);
  await revealImportTools(page);
  await page.getByTitle('Ausgewählte Seiten löschen', { exact: true }).click();
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 8 von 11');
  await expect(page.locator('.isd-page-card--selected')).toHaveCount(1);
});

test('dragging below a page inserts after it regardless of the horizontal pointer position', async ({ page }) => {
  await mount(page);
  const original = await page.evaluate(() => window.importFixture.store.documents[0].pages.map(page => page.id));
  const dataTransfer = await page.evaluateHandle(() => new DataTransfer());
  const first = page.locator('.isd-page-card').first();
  const second = page.locator('.isd-page-card').nth(1);
  await first.dispatchEvent('dragstart', { dataTransfer });
  const target = await second.boundingBox();
  await second.dispatchEvent('dragover', { dataTransfer, clientX: target.x + 4, clientY: target.y + target.height - 4 });
  await expect(second).toHaveClass(/isd-page-card--drop-after/);
  await second.dispatchEvent('drop', { dataTransfer });
  await page.locator(`[data-page-id="${original[0]}"]`).dispatchEvent('dragend', { dataTransfer });
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages.map(page => page.id))).toEqual([original[1], original[0], original[2]]);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 2 von 3');
  await dataTransfer.dispose();
});

test('a static placeholder and retained preview keep only the form header spinning', async ({ page }) => {
  await mount(page, { pages: 1, thumbnails: false });
  const stage = page.locator('.isd-preview-stage');
  await expect(stage).toHaveAttribute('aria-busy', 'false');
  const pending = [];
  await page.route('**/color-preview?*', route => { pending.push(route); });
  await page.evaluate(() => {
    const { store } = window.importFixture;
    const metadata = store.sourceMetaById.get(store.documents[0].pages[0].sourceFileId);
    metadata.scanCleanup = { status: 'running' };
    metadata.sourceRevision = 'first-preview';
  });
  await expect.poll(() => pending.length).toBe(1);
  await expect(stage).toHaveAttribute('aria-busy', 'true');
  await expect(page.getByText('Vorschau wird vorbereitet', { exact: true })).toBeVisible();
  await expect(page.locator('.isd-preview-image')).toHaveCount(0);
  await expect(page.locator('.isd-card .v-progress-circular')).toHaveCount(1);
  await expect(page.locator('.isd-props-heading .v-progress-circular')).toBeVisible();
  await page.screenshot({ path: '/private/tmp/papermind-import-single-spinner-placeholder.png' });
  await pending[0].fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1400"><rect width="1000" height="1400" fill="white"/><text x="100" y="200" font-size="50">Scanvorschau</text></svg>' });
  await expect(stage).toHaveAttribute('aria-busy', 'false');
  const preview = page.locator('.isd-preview-image');
  await expect(preview).toBeVisible();
  const source = await preview.getAttribute('src');
  await page.evaluate(() => {
    const { store } = window.importFixture;
    store.sourceMetaById.get(store.documents[0].pages[0].sourceFileId).sourceRevision = 'improved-preview';
  });
  await expect.poll(() => pending.length).toBe(2);
  await expect(stage).toHaveAttribute('aria-busy', 'true');
  await expect(preview).toHaveAttribute('src', source);
  await expect(page.locator('.isd-preview-empty')).toHaveCount(0);
  await expect(page.locator('.isd-card .v-progress-circular')).toHaveCount(1);
  await page.screenshot({ path: '/private/tmp/papermind-import-single-spinner-preview.png' });
  await pending[1].fulfill({ contentType: 'image/png', body: 'incomplete image' });
  await expect(stage).toHaveAttribute('aria-busy', 'false');
  await expect(preview).toHaveAttribute('src', source);
  expect(await preview.evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
});

test('late previews cannot replace the active page and refreshed thumbnails invalidate the large preview', async ({ page }) => {
  await mount(page);
  const pending = [];
  await page.route('**/color-preview?*', route => { pending.push(route); });
  await page.locator('.isd-page-card').nth(1).click();
  await expect.poll(() => pending.length).toBe(1);
  await page.locator('.isd-page-card').nth(2).click();
  await expect.poll(() => pending.length).toBe(2);
  const image = color => `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1400"><rect width="1000" height="1400" fill="${color}"/></svg>`;
  await pending[1].fulfill({ contentType: 'image/svg+xml', body: image('blue') });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  const activeImage = await page.locator('.isd-preview-image').getAttribute('src');
  await pending[0].fulfill({ contentType: 'image/svg+xml', body: image('red') });
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('src', activeImage);
  const refreshedThumbnail = 'data:image/svg+xml,' + encodeURIComponent(image('green'));
  await page.evaluate(url => { window.importFixture.store.documents[0].pages[2].thumbUrl = url; }, refreshedThumbnail);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('src', activeImage);
  await expect.poll(() => pending.length).toBe(3);
  await pending[2].fulfill({ contentType: 'image/svg+xml', body: image('green') });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('.isd-preview-image')).not.toHaveAttribute('src', activeImage);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 3 von 3');
  await revealImportTools(page);
  await page.getByRole('button', { name: 'Lupe', exact: true }).click();
  const preview = await page.locator('.isd-preview-stage').boundingBox();
  await page.mouse.move(preview.x + preview.width / 2, preview.y + preview.height / 2);
  await expect(page.locator('.isd-preview-magnifier')).toBeVisible();
  await page.mouse.move(preview.x + 1, preview.y + preview.height / 2);
  await expect(page.locator('.isd-preview-magnifier')).toHaveCount(0);
  await page.locator('.isd-page-card').first().click();
  await expect.poll(() => pending.length).toBe(4);
  await pending[3].fulfill({ json: { message: 'Not an image' } });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  await expect.poll(() => page.locator('.isd-preview-image').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('src', /^data:image\/svg\+xml,/);
});

test('a draft from another account is never restored into the active account', async ({ page }) => {
  await mount(page);
  await page.getByLabel('Dokumentname', { exact: true }).fill('Privater Entwurf von Konto eins');
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
