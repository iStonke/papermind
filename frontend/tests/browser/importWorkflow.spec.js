import { test, expect } from '@playwright/test';

import { mount, revealImportTools, startImportAnalysis, completeRequiredMetadata } from './fixtures/importHarness.js';

for (const width of [1366, 430]) test(`scan errors replace the scanner tile and retry cleanly at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  await mount(page, { documents: 0, parkedPages: 6 });
  await page.evaluate(() => {
    const now = Date.now();
    window.importFixture.scannerJobs.value = [
      { id: 'timeout', state: 'error', error_kind: 'timeout', created_at: new Date(now + 100).toISOString() },
      { id: 'older-failure', state: 'error', error_kind: 'failed', created_at: new Date(now + 10).toISOString() },
      { id: 'cancelled', state: 'error', error_kind: 'cancelled', created_at: new Date(now + 200).toISOString() },
    ];
  });
  const failure = page.locator('.isd-dropzone__actions > .import-scan-error');
  await expect(failure).toContainText('Zeitlimit überschritten');
  await expect(page.getByRole('alert')).toHaveCount(1);
  await expect(page.locator('.isd-import-error')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '6 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'PDFs auswählen Eine oder mehrere PDF-Dateien', exact: true })).toBeVisible();
  await page.screenshot({ path: `/private/tmp/papermind-scan-error-${width}-light.png`, animations: 'disabled' });
  await page.evaluate(() => window.importFixture.setTheme('dark'));
  await page.screenshot({ path: `/private/tmp/papermind-scan-error-${width}-dark.png`, animations: 'disabled' });
  await failure.getByRole('button', { name: 'Erneut scannen', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(await page.evaluate(() => window.importFixture.commands)).toEqual(['page']);
  await page.evaluate(() => {
    window.importFixture.scannerJobs.value.push({ id: 'new-failure', state: 'error', error_kind: 'scanner_offline', created_at: new Date(Date.now() + 300).toISOString() });
  });
  await expect(failure).toContainText('Scanner nicht erreichbar');
  await expect(page.getByRole('alert')).toHaveCount(1);
});

test('a failed additional scan stays next to the page list without changing existing pages', async ({ page }) => {
  await mount(page, { pages: 2 });
  const before = await page.evaluate(() => JSON.stringify(window.importFixture.store.documents));
  await page.evaluate(() => {
    window.importFixture.scannerJobs.value = [{ id: 'additional-failure', state: 'error', error_kind: 'file_missing', updated_at: new Date(Date.now() + 100).toISOString() }];
  });
  const failure = page.locator('.isd-page-grid > .import-scan-error');
  await expect(failure).toContainText('Seite nicht verfügbar');
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
  expect(await page.evaluate(() => JSON.stringify(window.importFixture.store.documents))).toBe(before);
  await failure.getByRole('button', { name: 'Erneut scannen', exact: true }).click();
  await expect(failure).toHaveCount(0);
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
});

test('import help explains missing fields on demand and focuses them without red errors', async ({ page }) => {
  await mount(page);
  const help = page.getByRole('button', { name:'Was fehlt für den Import?', exact:true });
  await expect(help).toBeVisible();
  await help.click();
  const explanation = page.getByRole('dialog', { name:'Für den Import erforderliche Angaben', exact:true });
  await expect(explanation).toContainText('Dokumentdatum ergänzen');
  await expect(explanation).toContainText('Korrespondent ergänzen');
  await expect.poll(() => explanation.evaluate(element => getComputedStyle(element.closest('.v-overlay__content')).opacity)).toBe('1');
  await page.screenshot({ path:'/private/tmp/papermind-import-readiness-help.png' });
  await explanation.getByRole('button', { name:'Dokumentdatum ergänzen', exact:true }).press('Enter');
  await expect(page.getByLabel('Dokumentdatum', { exact:true })).toBeFocused();
  await expect(page.locator('.pm-metadata-error')).toHaveCount(0);
  await completeRequiredMetadata(page);
  await expect(help).toHaveCount(0);
  await expect(page.getByRole('button', { name:'Importieren', exact:true })).toBeEnabled();
});

test('a missing correspondent can be created from search, retried after failure and selected without losing the import', async ({ page }) => {
  await mount(page);
  await completeRequiredMetadata(page);
  await page.evaluate(() => { window.importFixture.store.documents[0].meta.form.correspondentId = null; });
  const created = [];
  await page.route('**/api/correspondents', route => {
    if (route.request().method() !== 'POST') return route.fulfill({ json:{ items:[] } });
    const body = route.request().postDataJSON(); created.push(body);
    return route.fulfill(created.length === 1 ? { status:503, json:{ message:'Temporär nicht verfügbar' } }
      : { json:{ id:'created-correspondent', name:body.name, kind:body.kind } });
  });
  await page.getByRole('combobox', { name:'Korrespondent', exact:true }).fill('Neue Firma');
  await expect.poll(() => page.locator('.isd-create-correspondent').evaluate(el => getComputedStyle(el.closest('.v-overlay__content')).opacity)).toBe('1');
  await page.locator('.isd-create-correspondent').focus();
  await expect(page.locator('.isd-create-correspondent')).toBeFocused();
  await page.locator('.isd-create-correspondent').press('Enter');
  const dialog = page.getByRole('dialog').filter({ has:page.getByRole('heading', { name:'Korrespondenten anlegen', exact:true }) });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel('Name', { exact:true })).toHaveValue('Neue Firma');
  await page.screenshot({ path:'/private/tmp/papermind-import-correspondent-dialog.png' });
  await dialog.getByLabel('Name', { exact:true }).fill('');
  await expect(dialog.getByRole('button', { name:'Anlegen und auswählen', exact:true })).toBeDisabled();
  await dialog.getByLabel('Name', { exact:true }).fill('Neue Firma');
  await dialog.getByRole('button', { name:'Anlegen und auswählen', exact:true }).click();
  await expect(dialog.getByText('Der Korrespondent konnte nicht angelegt werden. Bitte erneut versuchen.', { exact:true })).toBeVisible();
  await expect(dialog.getByLabel('Name', { exact:true })).toHaveValue('Neue Firma');
  await dialog.getByRole('button', { name:'Anlegen und auswählen', exact:true }).click();
  await expect(dialog).toHaveCount(0);
  expect(created).toEqual([{ name:'Neue Firma', kind:'organization' }, { name:'Neue Firma', kind:'organization' }]);
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].meta.form.correspondentId)).toBe('created-correspondent');
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await expect(page.getByRole('button', { name:'Importieren', exact:true })).toBeEnabled();
});

test('field chips expose contextual proposals and keep accepted or dismissed choices explicit', async ({ page }) => {
  const requests = await mount(page);
  await completeRequiredMetadata(page);
  await page.evaluate(() => {
    window.importFixture.store.documents[0].meta.form.proposals = {
      category:{ value:'Vertrag', origin:'KI' }, date:{ value:'21.10.2026', origin:'KI' }, correspondent:{ value:'Neue Firma', origin:'KI' },
    };
  });
  const chip = page.getByRole('button', { name:'KI-Vorschlag für Dokumenttyp anzeigen', exact:true });
  await chip.focus();
  await chip.press('Enter');
  const category = page.getByRole('dialog', { name:'KI-Vorschlag für Dokumenttyp', exact:true });
  await expect(category).toContainText('Vertrag');
  await expect.poll(() => category.evaluate(element => getComputedStyle(element.closest('.v-overlay__content')).opacity)).toBe('1');
  await page.screenshot({ path:'/private/tmp/papermind-import-field-proposal.png' });
  const accept = category.getByRole('button', { name:'Übernehmen', exact:true });
  await accept.focus();
  await accept.press('Enter');
  expect(requests).toHaveLength(0);
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].meta.form.category)).toBe('Vertrag');
  await expect(page.getByRole('button', { name:'KI-Vorschlag für Dokumenttyp anzeigen', exact:true })).toHaveCount(0);
  await page.getByRole('button', { name:'KI-Vorschlag für Dokumentdatum anzeigen', exact:true }).click();
  await page.getByRole('dialog', { name:'KI-Vorschlag für Dokumentdatum', exact:true }).getByRole('button', { name:'Verwerfen', exact:true }).click();
  await expect(page.getByLabel('Dokumentdatum', { exact:true })).toHaveValue('20.10.2026');
  expect(await page.evaluate(() => window.importFixture.store.documents[0].meta.form.dismissed.date)).toBe('21.10.2026');
  await page.getByRole('button', { name:'KI-Vorschlag für Korrespondent anzeigen', exact:true }).click();
  await page.getByRole('dialog', { name:'KI-Vorschlag für Korrespondent', exact:true }).getByRole('button', { name:'Korrespondenten anlegen', exact:true }).click();
  const create = page.getByRole('dialog').filter({ has:page.getByRole('heading', { name:'Korrespondenten anlegen', exact:true }) });
  await expect(create.getByLabel('Name', { exact:true })).toHaveValue('Neue Firma');
  await create.getByRole('button', { name:'Abbrechen', exact:true }).click();
  await expect(create).toHaveCount(0);
  expect(await page.evaluate(() => window.importFixture.store.documents[0].meta.form.correspondentId)).toBe('30000000-0000-4000-8000-000000000001');
});

for (const action of ['leave', 'edit']) test(`analysis waits for the focused empty field before ${action}`, async ({ page }) => {
  await mount(page);
  let response;
  await page.route('**/suggest-title', route => { response = route; });
  await startImportAnalysis(page);
  await expect.poll(() => Boolean(response)).toBe(true);
  const date = page.getByLabel('Dokumentdatum', { exact:true });
  await date.focus();
  if (action === 'edit') await date.fill('01.01.2026');
  await response.fulfill({ json:{ status:'ready', suggestion:'Erkannter Brief', meta:{ date:'2026-03-16', analysis_phase:'llm' } } });
  await expect(page.getByLabel('Dokumentname', { exact:true })).toHaveValue('Erkannter Brief');
  await expect(date).toHaveValue(action === 'edit' ? '01.01.2026' : '');
  await date.blur();
  await expect(date).toHaveValue(action === 'edit' ? '01.01.2026' : '16.03.2026');
  if (action === 'edit') await expect(page.getByRole('button', { name:'KI-Vorschlag für Dokumentdatum anzeigen', exact:true })).toBeVisible();
});

test('automatic notes reject metadata fragments while manual notes remain untouched', async ({ page }) => {
  await mount(page);
  await page.route('**/suggest-title', route => route.fulfill({ json:{ status:'ready', suggestion:'Förderverein', meta:{ note:'Absender: %; é&‘. Dokumenttyp: Verträge', analysis_phase:'llm' } } }));
  await startImportAnalysis(page);
  await expect(page.getByLabel('Dokumentname', { exact:true })).toHaveValue('Förderverein');
  await expect(page.getByLabel('Notizen', { exact:true })).toHaveValue('');
  await page.getByLabel('Notizen', { exact:true }).fill('Meine eigene Notiz');
  await startImportAnalysis(page);
  await expect(page.locator('.isd-ai-status-btn--busy')).toHaveCount(0);
  await expect(page.getByLabel('Notizen', { exact:true })).toHaveValue('Meine eigene Notiz');
});

test('analysis page coverage is disclosed only in the existing AI hint', async ({ page }) => {
  await mount(page, { pages:7 });
  await page.evaluate(() => {
    const doc = window.importFixture.store.documents[0];
    doc.meta.titleSuggestionMeta = { pages_analyzed:5, pages_total:7, scope_limited:true, page_refs:doc.pages.slice(0, 5).map(page => `${page.sourceFileId}:${page.pageIndex}`) };
  });
  await expect(page.locator('.isd-props-heading')).not.toContainText('5 von 7');
  await page.locator('.isd-ai-status-btn').focus();
  await expect(page.getByRole('tooltip')).toContainText('Seiten 1, 2, 3, 4, 5 (5 von 7)');
  await expect(page.getByRole('tooltip')).toContainText('Weitere Seiten wurden nicht berücksichtigt.');
});

test('document boundaries and an adjustable details pane preserve page navigation and the device preference', async ({ page }) => {
  await page.setViewportSize({ width:1440, height:1000 });
  await mount(page, { documents:2 });
  await expect(page.getByRole('combobox', { name:'Dokument bearbeiten', exact:true })).toHaveCount(0);
  await expect(page.locator('.isd-document-boundary')).toHaveText(['Arbeitsstätte', 'Dokument 2']);
  await expect(page.locator('.isd-page-card')).toHaveCount(6);
  await page.screenshot({ path:'/private/tmp/papermind-import-document-groups.png' });
  const divider = page.getByRole('separator', { name:'Breite der Dokumentdetails ändern', exact:true });
  await divider.focus();
  await divider.press('ArrowLeft');
  await expect(divider).toHaveAttribute('aria-valuenow', '380');
  const position = await divider.boundingBox();
  await page.mouse.move(position.x + position.width / 2, position.y + position.height / 2);
  await page.mouse.down(); await page.mouse.move(position.x - 96, position.y + position.height / 2); await page.mouse.up();
  const width = await divider.getAttribute('aria-valuenow');
  expect(Number(width)).toBeGreaterThan(450);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('papermind.import.details-width'))).toBe(width);
  await page.reload();
  await page.evaluate(() => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow()));
  await expect(divider).toHaveAttribute('aria-valuenow', width);
  await page.setViewportSize({ width:430, height:900 });
  await expect(divider).toBeHidden();
  expect((await page.getByLabel('Dokumentname', { exact:true }).boundingBox()).width).toBeGreaterThan(250);
  await page.setViewportSize({ width:1440, height:1000 });
  await expect(divider).toHaveAttribute('aria-valuenow', width);
  await divider.dblclick();
  await expect(divider).toHaveAttribute('aria-valuenow', '360');
  await revealImportTools(page);
  await page.screenshot({ path:'/private/tmp/papermind-import-ui-desktop.png' });
});

test('page thumbnails select the document form and preserve separate edits without a document selector', async ({ page }) => {
  await page.setViewportSize({ width:1440, height:1000 });
  await mount(page, { documents:2, pages:2 });
  await expect(page.getByRole('combobox', { name:'Dokument bearbeiten', exact:true })).toHaveCount(0);
  const name = page.getByLabel('Dokumentname', { exact:true });
  await name.fill('Erstes Dokument');
  await page.locator('.isd-page-card').nth(2).click();
  await expect(name).toHaveValue('Dokument 2');
  await name.fill('Zweites Dokument');
  await page.locator('.isd-page-card').nth(0).focus();
  await page.locator('.isd-page-card').nth(0).press('Enter');
  await expect(name).toHaveValue('Erstes Dokument');
  await expect(page.locator('.isd-document-boundary--active')).toHaveText('Erstes Dokument');
  await page.locator('.isd-page-card').nth(3).click();
  await expect(name).toHaveValue('Zweites Dokument');
  await expect(page.locator('.isd-document-boundary--active')).toHaveText('Zweites Dokument');
  expect(await page.evaluate(() => window.importFixture.store.documents.map(doc => doc.title))).toEqual(['Erstes Dokument', 'Zweites Dokument']);
});

for (const theme of ['light', 'dark']) test(`document group titles stay on one line with compact generated scan names in ${theme}`, async ({ page }) => {
  const generated = 'Scan-20261024-013011-803102918-pmdev-59202204a2a22319db1309b16';
  const longTitle = 'Beitragsrechnung für die private Haftpflichtversicherung und weitere ausführliche Angaben zum Versicherungsvertrag';
  await mount(page, { documents:2, pages:1, title:generated });
  await page.evaluate(({ theme, longTitle }) => {
    window.importFixture.setTheme(theme);
    window.importFixture.store.documents[1].title = longTitle;
  }, { theme, longTitle });
  const headings = page.locator('.isd-document-boundary');
  await expect(headings).toHaveText(['Scan 1', longTitle]);
  await expect(headings.nth(0)).toHaveAttribute('title', generated);
  await expect(headings.nth(1)).toHaveAttribute('title', longTitle);
  for (const width of [1440, 800, 430, 320]) {
    await page.setViewportSize({ width, height:1000 });
    const layout = await headings.evaluateAll(elements => elements.map(element => {
      const range = document.createRange(); range.selectNodeContents(element);
      const rail = element.closest('.isd-grid-scroll');
      return { textHeight:range.getBoundingClientRect().height, lineHeight:parseFloat(getComputedStyle(element).lineHeight),
        headingWidth:element.getBoundingClientRect().width, railWidth:rail.clientWidth, overflow:rail.scrollWidth - rail.clientWidth };
    }));
    expect(layout.every(row => row.textHeight <= row.lineHeight + 1 && row.headingWidth <= row.railWidth && row.overflow <= 1)).toBe(true);
    if (width === 1440 || width === 430) await page.screenshot({ path:`/private/tmp/papermind-compact-document-groups-${theme}-${width}.png`, animations:'disabled' });
  }
  // Only the rail presentation is shortened; the editable document name stays intact.
  expect(await page.evaluate(() => window.importFixture.store.documents[0].title)).toBe(generated);
});

test.describe('import controls with coarse touch input', () => {
  test.use({ viewport:{ width:430, height:900 }, hasTouch:true });
  test('editing, zoom and help controls have generous touch targets', async ({ page }) => {
    await mount(page);
    const controls = page.locator('.isd-toolbar button, .isd-ai-status-btn, .isd-toolbar-select-btn, .isd-readiness-help');
    expect(await controls.evaluateAll(elements => elements.every(element => { const rect = element.getBoundingClientRect(); return rect.width >= 44 && rect.height >= 44; }))).toBe(true);
    await page.evaluate(() => window.importFixture.setTheme('dark'));
    await expect(page.locator('.isd-toolbar')).toHaveCSS('background-color', 'rgba(15, 23, 42, 0.58)');
    await page.screenshot({ path:'/private/tmp/papermind-import-ui-touch-dark.png' });
  });
});

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

for (const action of ['close', 'escape', 'commit', 'empty']) test(`${action} closes at its current size with the standard dialog animation`, async ({ page }) => {
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
  else if (action === 'escape') await page.keyboard.press('Escape');
  else {
    await card.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  }
  await expect(card).toHaveCount(0);
  const frames = await page.evaluate(() => window.importCloseFrames);
  expect(frames.every(frame => Math.abs(frame.width - width) < 1)).toBe(true);
  expect(frames.filter(frame => frame.closing).length).toBeGreaterThan(1);
  expect(frames.some(frame => frame.standardAnimation)).toBe(true);
  await expect.poll(() => page.evaluate(() => window.importFixture.store.totalPages)).toBe(0);
  expect(await page.evaluate(() => window.importFixture.store.availablePageCount)).toBe(['close', 'escape'].includes(action) ? 3 : 0);
  await page.evaluate(() => { window.importFixture.open.value = true; });
  await expect(card).toBeVisible();
  await expect(card).toHaveCSS('width', '680px');
  await expect(page.locator('.isd-dropzone')).toBeVisible();
});

test('required metadata disables import until complete and still guards a programmatic submission', async ({ page }) => {
  const requests = await mount(page);
  const submit = page.getByRole('button', { name: 'Importieren', exact: true });
  await expect(page.locator('.pm-metadata-label')).toHaveText(['Dokumentname', 'Dokumentdatum', 'Dokumenttyp', 'Korrespondent', 'Tags', 'Notizen']);
  await expect(page.getByText('Nur Notizen sind optional.')).toBeVisible();
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveAttribute('required', '');
  await expect(page.getByLabel('Notizen', { exact: true })).not.toHaveAttribute('required');
  await expect(submit).toBeDisabled();
  await submit.dispatchEvent('click');
  await expect(page.locator('.pm-metadata-error, .pm-metadata-control--error, .isd-footer-hint')).toHaveCount(0);
  expect(requests).toHaveLength(0);
  await expect(page.getByLabel('Dokumentdatum', { exact: true })).toBeFocused();
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 1 von 3');
  await page.getByLabel('Dokumentdatum', { exact: true }).fill('20.10.2026');
  await expect(submit).toBeDisabled();
  await page.locator('[data-field="category"] .v-field').click();
  await page.getByRole('option', { name: 'Brief', exact: true }).click();
  await expect(submit).toBeDisabled();
  await page.evaluate(() => { window.importFixture.correspondents.correspondents = [{ id: '30000000-0000-4000-8000-000000000001', name: 'Testfirma', kind: 'organization' }]; });
  await page.locator('[data-field="correspondent"] .v-field').click();
  await page.getByRole('option', { name: 'Testfirma', exact: true }).click();
  await expect(submit).toBeDisabled();
  await page.getByText('Tags', { exact: true }).click();
  const tags = page.getByRole('combobox', { name: 'Tag hinzufügen', exact: true });
  await tags.fill('Unterlagen');
  await tags.press('Enter');
  await expect(page.locator('.pm-metadata-error')).toHaveCount(0);
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents[0].note).toBeNull();
  expect(requests[0].documents[0].tag_names).toEqual(['Unterlagen']);
});

test('entering and then clearing initially empty metadata stays quiet while import remains disabled', async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    window.importFixture.store.documents[0].title = '';
    window.importFixture.correspondents.correspondents = [{ id: '30000000-0000-4000-8000-000000000001', name: 'Testfirma', kind: 'organization' }];
  });
  const expectQuiet = async () => {
    await expect(page.locator('.pm-metadata-error, .pm-metadata-control--error, .isd-footer-hint')).toHaveCount(0);
    await expect(page.locator('.pm-metadata-fields [aria-invalid="true"]')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
  };
  for (const [label, value] of [['Dokumentname', 'Neuer Name'], ['Dokumentdatum', '20.10.2026'], ['Notizen', 'Testnotiz']]) {
    const input = page.getByLabel(label, { exact: true });
    await expect(input).toHaveValue('');
    await input.fill(value);
    await input.blur();
    await input.fill('');
    await input.blur();
    await expectQuiet();
  }
  for (const [field, option] of [['category', 'Brief'], ['correspondent', 'Testfirma']]) {
    const row = page.locator(`[data-field="${field}"]`);
    await row.locator('.v-field').click();
    await page.getByRole('option', { name: option, exact: true }).click();
    await row.hover();
    await row.locator('.v-field__clearable').click();
    await page.locator('.isd-props-heading h3').click();
    await expectQuiet();
  }
  await page.getByText('Tags', { exact: true }).click();
  const tags = page.getByRole('combobox', { name: 'Tag hinzufügen', exact: true });
  await tags.fill('Unterlagen');
  await tags.press('Enter');
  await page.locator('[data-field="tags"] .v-chip__close').click();
  await page.locator('.isd-props-heading h3').click();
  await expectQuiet();
});

test('clearing or invalidating any required field immediately disables import again', async ({ page }) => {
  const requests = await mount(page);
  await completeRequiredMetadata(page);
  const submit = page.getByRole('button', { name: 'Importieren', exact: true });
  const invalidCases = [
    { field: 'title', value: '   ' },
    { field: 'title', value: 'A'.repeat(201) },
    { field: 'date', value: '' },
    { field: 'date', value: '31.02.2026' },
    { field: 'date', value: '20.10.26' },
    { field: 'category', value: null },
    { field: 'correspondentId', value: null },
    { field: 'tags', value: [] },
  ];
  for (const invalid of invalidCases) {
    await expect(submit).toBeEnabled();
    const previous = await page.evaluate(({ field, value }) => {
      const doc = window.importFixture.store.documents[0];
      const target = field === 'title' ? doc : field === 'tags' ? doc.meta : doc.meta.form;
      const key = field === 'tags' ? 'pendingTagNames' : field;
      const previous = target[key];
      target[key] = value;
      return previous;
    }, invalid);
    await expect(submit, `Invalid ${invalid.field}: ${invalid.value}`).toBeDisabled();
    await page.locator('.isd-props-heading h3').click();
    await page.keyboard.press('Control+Enter');
    await page.keyboard.press('Meta+Enter');
    expect(requests).toHaveLength(0);
    await page.evaluate(({ field, value }) => {
      const doc = window.importFixture.store.documents[0];
      const target = field === 'title' ? doc : field === 'tags' ? doc.meta : doc.meta.form;
      target[field === 'tags' ? 'pendingTagNames' : field] = value;
    }, { field: invalid.field, value: previous });
  }
  await expect(submit).toBeEnabled();
  await expect(page.getByLabel('Notizen', { exact: true })).toHaveValue('');
  await page.getByLabel('Notizen', { exact: true }).fill('Optionale Notiz');
  await expect(submit).toBeEnabled();
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
  await date.fill('');
  await date.blur();
  await expect(page.locator('.pm-metadata-error, .pm-metadata-control--error')).toHaveCount(0);
  await expect(date).toHaveAttribute('aria-invalid', 'false');
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
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
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
  await completeRequiredMetadata(page);
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
  await expect(page.getByRole('button', { name: 'Auswahl importieren (1)' })).toBeDisabled();
  await page.getByRole('button', { name: 'Auswahl importieren (1)' }).dispatchEvent('click');
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  expect(requests).toHaveLength(0);
  await expect(page.locator('.pm-metadata-error, .pm-metadata-control--error')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Auswahl importieren (1)' })).toBeVisible();
});

test('selection import validates every selected document without blocking on unselected documents', async ({ page }) => {
  const requests = await mount(page, { documents: 2 });
  await completeRequiredMetadata(page);
  await page.evaluate(() => { window.importFixture.store.documents[1].meta.form.date = ''; });
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
  await page.getByTitle('Seiten auswählen', { exact: true }).click();
  await page.locator('.isd-page-card').nth(0).click();
  await expect(page.getByRole('button', { name: 'Auswahl importieren (1)' })).toBeEnabled();
  await page.locator('.isd-page-card').nth(3).click();
  await expect(page.getByRole('button', { name: 'Auswahl importieren (2)' })).toBeDisabled();
  await page.locator('.isd-page-card').nth(3).click();
  await page.getByRole('button', { name: 'Auswahl importieren (1)' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].documents).toHaveLength(1);
  expect(requests[0].documents[0].title).toBe('Arbeitsstätte');
  await expect(page.locator('.isd-page-card')).toHaveCount(5);
  await expect(page.getByRole('button', { name: 'Importieren', exact: true })).toBeDisabled();
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
    await completeRequiredMetadata(page);
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
    const fits = await statusButton.evaluate((button, limit) => {
      const rect = button.getBoundingClientRect();
      const header = button.closest('.isd-props-heading');
      const bounds = header.getBoundingClientRect();
      const title = header.querySelector('.isd-props-title').getBoundingClientRect();
      return rect.width <= limit && rect.left >= title.right + 8 && rect.right <= bounds.right - 16;
    }, width === 1440 ? 36 : 44);
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

test('the translucent page-list footer overlays scrolling thumbnails while the active page stays unobscured', async ({ page }) => {
  await mount(page, { pages: 10 });
  for (const width of [1440, 430]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['light', 'dark']) {
      await page.evaluate(theme => window.importFixture.setTheme(theme), theme);
      const card = page.locator('.isd-page-card').nth(6);
      await card.scrollIntoViewIfNeeded();
      await expect.poll(() => card.locator('img').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
      const footerTop = await page.evaluate(() => {
        const footer = document.querySelector('.isd-pages-footer');
        const rail = document.querySelector('.isd-grid-scroll');
        const thumb = document.querySelectorAll('.isd-page-card')[6];
        const bar = footer.getBoundingClientRect();
        const page = thumb.getBoundingClientRect();
        rail.scrollTop += page.top + page.height / 2 - (bar.top + bar.height / 2);
        return bar.top;
      });
      await expect.poll(() => card.evaluate(element => {
        const page = element.getBoundingClientRect();
        const footer = document.querySelector('.isd-pages-footer').getBoundingClientRect();
        const rail = document.querySelector('.isd-grid-scroll').getBoundingClientRect();
        return page.top < footer.bottom && page.bottom > footer.top
          && Math.abs(footer.bottom - rail.bottom) < 1;
      })).toBe(true);
      await page.mouse.move(0, 0);
      await page.locator('.isd-left').screenshot({ path: `/private/tmp/papermind-page-list-glass-${width}-${theme}.png` });
      await page.locator('.isd-page-card').first().click();
      for (let i = 0; i < 9; i++) await page.keyboard.press('ArrowDown');
      await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 10 von 10');
      await expect.poll(() => page.locator('.isd-page-card--selected').evaluate(element => {
        const page = element.getBoundingClientRect();
        const bar = document.querySelector('.isd-pages-footer').getBoundingClientRect();
        return page.bottom <= bar.top;
      })).toBe(true);
      expect((await page.locator('.isd-pages-footer').boundingBox()).y).toBe(footerTop);
    }
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

test('thumbnail frames fit complete portrait, landscape and cropped pages without gaps after rotation', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { pages: 3 });
  await page.evaluate(() => {
    const sizes = [[210, 297], [420, 210], [300, 900]];
    const { store } = window.importFixture;
    store.documents[0].pages.forEach((page, index) => {
      const [width, height] = sizes[index];
      page.thumbUrl = 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="white"/><path d="M0 0H${width}V${height}H0Z" fill="none" stroke="#137c80" stroke-width="8"/><text x="20" y="60">Seite ${index + 1}</text></svg>`);
    });
    const source = store.documents[0].pages[2].sourceFileId;
    store.sourceMetaById.get(source).scanCleanup = { auto_crop: { pages: [{ page_index: 2, applied: true, cropped_size_pixels: [300, 900] }] } };
  });
  for (const width of [1440, 430]) {
    await page.setViewportSize({ width, height: 1000 });
    for (let index = 0; index < 3; index++) {
      const card = page.locator('.isd-page-card').nth(index);
      await card.scrollIntoViewIfNeeded();
      await expect.poll(() => card.locator('img').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
      for (const rotation of [0, 90, 180, 270, 0]) {
        await page.evaluate(({ index, rotation }) => { window.importFixture.store.documents[0].pages[index].rotation = rotation; }, { index, rotation });
        await expect.poll(() => card.evaluate(element => {
          const image = element.querySelector('.isd-page-thumb');
          const frame = element.querySelector('.isd-page-thumb-inner').getBoundingClientRect();
          const rect = image.getBoundingClientRect();
          // Both the transformed box and the contained page must fill the frame.
          const style = getComputedStyle(image);
          const imageWidth = parseFloat(style.width);
          const imageHeight = parseFloat(style.height);
          const scale = Math.min(imageWidth / image.naturalWidth, imageHeight / image.naturalHeight);
          return Math.max(Math.abs(rect.left - frame.left), Math.abs(rect.right - frame.right),
            Math.abs(rect.top - frame.top), Math.abs(rect.bottom - frame.bottom),
            Math.abs(imageWidth - image.naturalWidth * scale), Math.abs(imageHeight - image.naturalHeight * scale));
        }), `${width}px, page ${index + 1}, rotation ${rotation}`).toBeLessThanOrEqual(.6);
      }
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => window.importFixture.setTheme('dark'));
  await page.locator('.isd-page-card').first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: '/private/tmp/papermind-thumbnail-filled-dark.png' });
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

for (const width of [1440, 430]) test(`native snapping centers mixed page formats precisely in both directions at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  await mount(page, { pages: 3 });
  await page.evaluate(() => {
    const pages = window.importFixture.store.documents[0].pages;
    for (const [index, [width, height]] of [[200, 280], [360, 180], [240, 240]].entries()) {
      pages[index].thumbUrl = 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="white"/><text x="20" y="50">Blatt ${index + 1}</text></svg>`);
    }
  });
  await expect.poll(() => page.locator('.isd-preview-page-image').evaluateAll(images =>
    images.every(image => image.complete && image.naturalWidth > 0)
  )).toBe(true);
  const stage = page.locator('.isd-preview-stage');
  await expect(stage).toHaveCSS('scroll-snap-type', 'y mandatory');
  for (const index of [1, 2, 1, 0]) {
    await stage.evaluate((element, index) => {
      const rect = element.querySelectorAll('.isd-preview-page')[index].getBoundingClientRect();
      element.scrollTop += rect.top + rect.height / 2 - element.getBoundingClientRect().top - element.clientHeight / 2 + (index ? 23 : -23);
    }, index);
    await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', `Seite ${index + 1} von 3`);
    await expect.poll(() => stage.evaluate((element, index) => {
      const rect = element.querySelectorAll('.isd-preview-page')[index].getBoundingClientRect();
      return Math.abs(rect.top + rect.height / 2 - element.getBoundingClientRect().top - element.clientHeight / 2);
    }, index)).toBeLessThan(1);
  }
  await stage.hover();
  await page.mouse.wheel(0, await stage.evaluate(element => element.clientHeight * .8));
  await expect(page.locator('.isd-preview-image')).not.toHaveAttribute('alt', 'Seite 1 von 3');
  await expect.poll(() => stage.evaluate(element => {
    const rect = element.querySelector('.isd-preview-page--active').getBoundingClientRect();
    return Math.abs(rect.top + rect.height / 2 - element.getBoundingClientRect().top - element.clientHeight / 2);
  })).toBeLessThan(1);
  await page.mouse.wheel(0, -10000);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 1 von 3');
});

test('loading a sharp page keeps a normal cursor, stable geometry and every visible image painted', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { pages: 3 });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  const pending = [];
  await page.route('**/color-preview?*', route => { pending.push(route); });
  const stage = page.locator('.isd-preview-stage');
  const pageDistance = await stage.evaluate(element => element.clientHeight);
  await page.evaluate(() => {
    window.previewOriginalNodes = [...document.querySelectorAll('.isd-preview-page-image')];
    window.previewBlankFrames = [];
    window.samplePreviewFrames = true;
    const sample = () => {
      if (!window.samplePreviewFrames) return;
      for (const image of document.querySelectorAll('.isd-preview-page-image')) {
        if (!image.complete || !image.naturalWidth) window.previewBlankFrames.push(image.alt);
      }
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  await stage.hover();
  await stage.evaluate(element => { const page = element.querySelectorAll('.isd-preview-page')[1]; element.scrollTop = page.offsetTop + page.offsetHeight / 2 - element.clientHeight / 2; });
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 2 von 3');
  await expect.poll(() => pending.length).toBe(1);
  await expect(stage).toHaveAttribute('aria-busy', 'true');
  await expect(stage).toHaveCSS('cursor', 'default');
  await expect(page.locator('.isd-preview-image')).toHaveCSS('cursor', 'default');
  const original = await page.locator('.isd-preview-page-image').evaluateAll(images => images.map(image => image.getAttribute('src')));
  const size = await page.locator('.isd-preview-image').boundingBox();
  const body = '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1401"><rect width="100%" height="100%" fill="white"/><text x="90" y="100" font-size="50">Scharfe Seite 2</text></svg>';
  await pending[0].fulfill({ contentType: 'image/svg+xml', body });
  await expect(stage).toHaveAttribute('aria-busy', 'false');
  await expect.poll(() => page.locator('.isd-preview-image').evaluate(image => image.naturalHeight)).toBe(1401);
  const sharp = await page.locator('.isd-preview-image').getAttribute('src');
  const sharpened = await page.locator('.isd-preview-image').boundingBox();
  expect(Math.abs(sharpened.height - size.height)).toBeLessThan(.1);
  expect(Math.abs(sharpened.y - size.y)).toBeLessThan(.6);
  await stage.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 3 von 3');
  await expect.poll(() => pending.length).toBe(2);
  await expect(page.locator('.isd-preview-page-image').nth(1)).toHaveAttribute('src', sharp);
  await expect(page.locator('.isd-preview-page-image').nth(0)).toHaveAttribute('src', original[0]);
  await expect(page.locator('.isd-preview-page-image').nth(2)).toHaveAttribute('src', original[2]);
  await pending[1].fulfill({ status: 404, body: '' });
  await expect(stage).toHaveAttribute('aria-busy', 'false');
  await stage.evaluate(element => { const page = element.querySelectorAll('.isd-preview-page')[1]; element.scrollTop = page.offsetTop + page.offsetHeight / 2 - element.clientHeight / 2; });
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 2 von 3');
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('src', sharp);
  await page.evaluate(() => { window.samplePreviewFrames = false; });
  expect(await page.evaluate(() => window.previewBlankFrames)).toEqual([]);
  expect(await page.evaluate(() => [...document.querySelectorAll('.isd-preview-page-image')].every((image, index) => image === window.previewOriginalNodes[index]))).toBe(true);
  await page.screenshot({ path: '/private/tmp/papermind-preview-snapped-stable.png' });
});

test('the continuous preview scrolls natively in both directions without gesture pauses', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { documents: 2, pages: 2 });
  const stage = page.locator('.isd-preview-stage');
  const preview = page.locator('.isd-preview-image');
  await expect(page.locator('.isd-preview-page')).toHaveCount(4);
  await stage.hover();
  await page.mouse.wheel(0, 12);
  await expect.poll(() => stage.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await expect(preview).toHaveAttribute('alt', /Seite [12] von 4/);
  await stage.evaluate(element => { element.scrollTop = element.clientHeight * .58; });
  await expect(preview).toHaveAttribute('alt', 'Seite 2 von 4');
  await page.screenshot({ path: '/private/tmp/papermind-continuous-preview-desktop.png' });
  await stage.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(preview).toHaveAttribute('alt', 'Seite 4 von 4');
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Dokument 2');
  await stage.evaluate(element => { element.scrollTop = 0; });
  await expect(preview).toHaveAttribute('alt', 'Seite 1 von 4');
  await expect(page.getByLabel('Dokumentname', { exact: true })).toHaveValue('Arbeitsstätte');
  await expect(page.locator('.isd-page-card--selected')).toHaveCount(1);
  await expect(page.locator('.isd-preview-page')).toHaveCount(4);
  await expect.poll(() => page.locator('.isd-preview-page-image').count()).toBeLessThanOrEqual(4);
});

test('continuous scrolling preserves zoom when moving between pages', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { pages: 2 });
  await revealImportTools(page);
  for (let i = 0; i < 4; i++) await page.getByRole('button', { name: 'Vergrößern', exact: true }).click();
  const stage = page.locator('.isd-preview-stage');
  const preview = page.locator('.isd-preview-image');
  await stage.evaluate(element => { element.scrollTop = 0; });
  await stage.hover();
  await page.mouse.wheel(0, 100);
  await expect.poll(() => stage.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await expect(preview).toHaveAttribute('alt', 'Seite 1 von 2');
  await stage.evaluate(element => { element.scrollTop = element.scrollHeight; });
  // Oversized snap areas remain freely readable down to their actual page edge.
  await expect.poll(() => stage.evaluate(element => {
    const bottom = element.querySelector('.isd-preview-page:last-child').getBoundingClientRect().bottom;
    return Math.abs(bottom - element.getBoundingClientRect().bottom);
  })).toBeLessThan(2);
  await expect(preview).toHaveAttribute('alt', 'Seite 2 von 2');
  await expect(page.getByRole('button', { name: /Zoom 157 Prozent/ })).toBeVisible();
  await stage.evaluate(element => { element.scrollTop = 0; });
  await expect(preview).toHaveAttribute('alt', 'Seite 1 von 2');
  await expect(page.getByRole('button', { name: /Zoom 157 Prozent/ })).toBeVisible();
});

test('continuous preview keeps the reading position when earlier page images change and pages are reordered', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mount(page, { pages: 3 });
  const id = await page.evaluate(() => window.importFixture.store.documents[0].pages[2].id);
  const current = page.locator(`[data-preview-page-id="${id}"]`);
  await current.evaluate(element => element.scrollIntoView({ block: 'center' }));
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 3 von 3');
  const top = await current.evaluate(element => element.getBoundingClientRect().top);
  await page.evaluate(() => {
    const page = window.importFixture.store.documents[0].pages[0];
    page.thumbUrl = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="500" height="200"><rect width="500" height="200" fill="white"/></svg>');
  });
  await expect.poll(() => page.locator('.isd-preview-page-image').first().evaluate(image => image.naturalWidth)).toBe(500);
  await expect.poll(() => current.evaluate((element, top) => Math.abs(element.getBoundingClientRect().top - top), top)).toBeLessThan(1);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 3 von 3');
  await page.evaluate(id => {
    const { store } = window.importFixture;
    store.movePage(id, store.documents[0].id, 0);
  }, id);
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 1 von 3');
  await expect.poll(() => current.evaluate((element, top) => Math.abs(element.getBoundingClientRect().top - top), top)).toBeLessThan(1);
});

test('horizontal scrolling, form scrolling and zoom gestures do not turn pages', async ({ page }) => {
  await mount(page, { pages: 3 });
  const stage = page.locator('.isd-preview-stage');
  const preview = page.locator('.isd-preview-image');
  await stage.dispatchEvent('wheel', { deltaX: 120, deltaY: 10 });
  await stage.dispatchEvent('wheel', { deltaY: 120, shiftKey: true });
  await page.locator('.isd-props-scroll').dispatchEvent('wheel', { deltaY: 120 });
  await page.locator('.isd-grid-scroll').dispatchEvent('wheel', { deltaY: 120 });
  await stage.dispatchEvent('wheel', { deltaY: -80, ctrlKey: true });
  await expect(page.getByRole('button', { name: /Zoom 122 Prozent/ })).toBeAttached();
  await stage.dispatchEvent('wheel', { deltaY: 80, metaKey: true });
  await expect(page.getByRole('button', { name: /Zoom 100 Prozent/ })).toBeAttached();
  await expect(preview).toHaveAttribute('alt', 'Seite 1 von 3');
});

test('rapid page navigation starts only the final render and reuses decoded page images', async ({ page }) => {
  await mount(page, { pages: 4 });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  await page.clock.install();
  const requests = [];
  await page.route('**/color-preview?*', route => { requests.push(route); });
  for (const index of [1, 2, 3]) await page.locator('.isd-page-card').nth(index).dispatchEvent('click');
  await page.clock.runFor(150);
  await expect.poll(() => requests.length).toBe(1);
  expect(new URL(requests[0].request().url()).searchParams.get('page_index')).toBe('3');
  const body = '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1400"><rect width="1000" height="1400" fill="white"/></svg>';
  await requests[0].fulfill({ contentType: 'image/svg+xml', body });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  const decoded = await page.locator('.isd-preview-image').getAttribute('src');
  await page.locator('.isd-page-card').nth(2).dispatchEvent('click');
  await page.clock.runFor(150);
  await expect.poll(() => requests.length).toBe(2);
  await requests[1].fulfill({ contentType: 'image/svg+xml', body });
  await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
  await page.locator('.isd-page-card').nth(3).dispatchEvent('click');
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('src', decoded);
  await page.clock.runFor(200);
  expect(requests.length).toBe(2);
});

test.describe('native touch scrolling through import pages', () => {
  test.use({ viewport: { width: 430, height: 900 }, hasTouch: true });
  test('a swipe scrolls the continuous stack and updates the selected miniature', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Native touch gesture injection is a Chromium CDP API; the cross-engine suite separately tests native scrolling and snapping.');
    await mount(page, { pages: 4 });
    const stage = page.locator('.isd-preview-stage');
    const rect = await stage.boundingBox();
    const session = await page.context().newCDPSession(page);
    await session.send('Input.synthesizeScrollGesture', {
      x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2),
      yDistance: -600, speed: 800, gestureSourceType: 'touch', preventFling: true,
    });
    await expect.poll(() => stage.evaluate(element => element.scrollTop)).toBeGreaterThan(200);
    await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', /Seite [2-4] von 4/);
    await expect(page.locator('.isd-page-card--selected')).toHaveCount(1);
    await page.screenshot({ path: '/private/tmp/papermind-continuous-preview-touch.png' });
    await session.detach();
  });
});

test('local PDFs render sharp images for successive pages in the continuous preview', async ({ page }) => {
  await mount(page, { pages: 2 });
  const streams = ['BT /F1 20 Tf 50 760 Td (Lokales Blatt 1) Tj ET', 'BT /F1 20 Tf 50 760 Td (Lokales Blatt 2) Tj ET'];
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 6 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>',
    ...streams.map(stream => `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`)];
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 8\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  await page.evaluate(data => {
    const { store } = window.importFixture;
    const source = store.documents[0].pages[0].sourceFileId;
    store.setStagingFile(source, new File([data], 'local.pdf', { type: 'application/pdf' }), { pageCount: 2, sourceRevision: 'local-file' });
  }, pdf);
  await expect.poll(() => page.locator('.isd-preview-image').evaluate(image => image.naturalHeight)).toBe(1400);
  const first = await page.locator('.isd-preview-image').getAttribute('src');
  await revealImportTools(page);
  for (const rotation of [90, 180, 270, 0]) {
    await page.getByRole('button', { name: 'Nach rechts drehen', exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.importFixture.store.documents[0].pages[0].rotation)).toBe(rotation);
    await expect(page.locator('.isd-preview-stage')).toHaveAttribute('aria-busy', 'false');
    await expect.poll(() => page.locator('.isd-preview-image').evaluate(image => Math.max(image.naturalWidth, image.naturalHeight))).toBe(1400);
    const box = await page.locator('.isd-preview-image').boundingBox();
    expect(box.width > box.height).toBe([90, 270].includes(rotation));
  }
  await page.locator('.isd-page-card').nth(1).click();
  await expect(page.locator('.isd-preview-image')).toHaveAttribute('alt', 'Seite 2 von 2');
  await expect.poll(() => page.locator('.isd-preview-image').evaluate(image => image.naturalHeight)).toBe(1400);
  await expect(page.locator('.isd-preview-image')).not.toHaveAttribute('src', first);
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
