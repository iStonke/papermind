import { test, expect } from '@playwright/test';

async function mount(page, { theme = 'light', empty = false, failSave = false } = {}) {
  await page.setViewportSize({ width: 1360, height: 1000 });
  const persisted = { ui: { theme_mode: theme, drawerRememberState: false, autoHideDetailsDrawer: true, showFilenameSuffix: false } };
  const patches = [], searches = [], recommendations = [];
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.pathname === '/api/settings') {
      if (request.method() === 'PATCH') {
        const patch = request.postDataJSON(); patches.push(patch);
        if (failSave) return route.fulfill({ status: 500, json: { error: { message: 'Fehler' } } });
        Object.assign(persisted.ui, patch.ui);
      }
      return route.fulfill({ json: persisted });
    }
    if (url.pathname === '/api/documents') {
      searches.push(url.searchParams.get('q'));
      // Match the real API's validated search arguments.
      expect(url.searchParams.get('search_scope')).toBe('title');
      return route.fulfill({ json: { items: empty ? [] : [
        { id: 'document-a', display_name: 'Beitragsrechnung 2026' }, { id: 'document-b', display_name: 'Jahresübersicht 2025' },
      ] } });
    }
    if (url.pathname.endsWith('/related')) {
      recommendations.push(url);
      const title = url.searchParams.get('profile') === 'thematic' ? 'Thematisch passender Vertrag.pdf' : 'Beitrag aus derselben Serie.pdf';
      return route.fulfill({ json: { items: [{ id: 'related', title, same_series: !title.startsWith('Thematisch'), shared_tag_count: 1, shared_tags: ['Versicherung'] }], total: 1 } });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/__document-settings', route => route.fulfill({ contentType: 'text/html', body: '<div id="app"></div>' }));
  await page.goto('/__document-settings');
  await page.evaluate(async options => (await import('/tests/browser/fixtures/documentDetailsSettings.js')).mount(options), { theme });
  await expect(page.getByRole('group', { name: 'Gewichtungsprofil', exact: true })).toBeVisible();
  return { persisted, patches, searches, recommendations };
}
const profile = (page, name) => page.getByRole('group', { name: 'Gewichtungsprofil', exact: true }).getByRole('button', { name: new RegExp(`^${name}`) });

test('document details group preserves existing options and saves profiles, custom weights and reset with a live preview', async ({ page }) => {
  const { persisted, patches, recommendations } = await mount(page);
  const documentsGroup = page.locator('.pm-settings-nav__group').filter({ has: page.locator('.pm-settings-nav__group-label', { hasText: /^Dokumente$/ }) });
  await expect(documentsGroup.getByRole('tab', { name: 'Allgemein', exact: true })).toHaveAttribute('aria-selected', 'true');
  const preview = page.getByRole('complementary', { name: 'Beispielvorschau ähnlicher Dokumente' });
  await expect(preview.getByText('Beitrag aus derselben Serie', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.documentSettings.settings.ui.drawerRememberState)).toBe(false);
  // Older saved preferences must not bring the removed dimming behavior back.
  expect(await page.evaluate(() => 'autoHideDetailsDrawer' in window.documentSettings.settings.ui)).toBe(false);
  await expect(page.locator('.pm-settings-panel')).not.toContainText('Detailleiste bei Inaktivität dimmen');
  await expect(page.getByRole('checkbox', { name: 'Dokumentendetails automatisch minimieren', exact: true })).toBeChecked();
  await page.getByRole('button', { name: /^Dokumentendetails automatisch minimieren/ }).click();
  await expect.poll(() => persisted.ui.drawerRememberState).toBe(true);
  await expect(page.getByRole('checkbox', { name: 'Dokumentendetails automatisch minimieren', exact: true })).not.toBeChecked();
  await profile(page, 'Thematisch verwandt').click();
  await expect.poll(() => persisted.ui.related_documents?.profile).toBe('thematic');
  await expect(preview.getByText('Thematisch passender Vertrag', { exact: true })).toBeVisible();
  expect(recommendations.at(-1).searchParams.get('profile')).toBe('thematic');
  await page.getByText('Gewichtung anpassen', { exact: true }).click();
  await page.getByRole('group', { name: 'Dokumentserien', exact: true }).getByRole('button', { name: 'Stark', exact: true }).click();
  await expect.poll(() => persisted.ui.related_documents?.profile).toBe('custom');
  await expect.poll(() => recommendations.at(-1)?.searchParams.get('series_weight')).toBe('high');
  expect(persisted.ui.related_documents.weights.tags).toBe('high');
  await page.evaluate(async () => {
    window.unmountDocumentSettings();
    await (await import('/tests/browser/fixtures/documentDetailsSettings.js')).mount();
  });
  await expect(page.getByRole('group', { name: 'Dokumentserien', exact: true }).getByRole('button', { name: 'Stark', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Auf Standard zurücksetzen', exact: true }).click();
  await expect(profile(page, 'Ausgewogen')).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => persisted.ui.related_documents.profile).toBe('balanced');
  expect(patches.at(-1).ui.related_documents.weights.series).toBe('normal');
  await page.getByRole('tab', { name: 'Darstellung', exact: true }).click();
  await expect(page.locator('.pm-settings-panel')).not.toContainText('Dokumentendetails automatisch minimieren');
  await expect(page.locator('.pm-settings-panel')).not.toContainText('Detailleiste bei Inaktivität dimmen');
});

test('failed profile saves restore the active profile and the example results', async ({ page }) => {
  const { persisted } = await mount(page, { failSave: true });
  await profile(page, 'Gleicher Vorgang').click();
  await expect(page.getByRole('alert')).toContainText('bisherige Einstellung wurde wiederhergestellt');
  await expect(profile(page, 'Ausgewogen')).toHaveAttribute('aria-pressed', 'true');
  await expect(profile(page, 'Gleicher Vorgang')).toBeEnabled();
  expect(persisted.ui.related_documents).toBeUndefined();
});

test('preview searches and switches its document and handles an empty library', async ({ page }) => {
  const { searches, recommendations } = await mount(page);
  const select = page.getByRole('combobox', { name: 'Beispieldokument' });
  await select.click();
  await select.fill('Jahresübersicht');
  await expect.poll(() => searches.includes('Jahresübersicht')).toBe(true);
  await page.getByRole('option', { name: 'Jahresübersicht 2025', exact: true }).click();
  await expect.poll(() => recommendations.at(-1).pathname).toContain('/document-b/related');
  await page.reload();
  await page.evaluate(() => { document.querySelector('#app').replaceChildren(); });
  await page.route('**/api/documents?**', route => route.fulfill({ json: { items: [] } }));
  await page.evaluate(async () => (await import('/tests/browser/fixtures/documentDetailsSettings.js')).mount());
  await expect(page.locator('.related-settings-preview')).toContainText('Wähle ein vorhandenes Dokument');
  await expect(page.locator('.related-settings-preview .related-documents')).toHaveCount(0);
});

for (const theme of ['light', 'dark']) test(`document details and preview fit ${theme} desktop and narrow screens`, async ({ page }) => {
  await mount(page, { theme });
  await expect(page.locator('.related-settings-preview .related-documents__item')).toHaveCount(1);
  await page.screenshot({ path: `/tmp/papermind-document-settings-${theme}.png`, animations: 'disabled' });
  await page.setViewportSize({ width: 800, height: 900 });
  await expect(page.locator('.document-details-preview--inline')).toBeAttached();
  await expect(page.locator('.pm-settings-preview-rail')).toHaveCount(0);
  await page.locator('.document-details-preview--inline').scrollIntoViewIfNeeded();
  await expect(page.getByRole('combobox', { name: 'Beispieldokument' })).toBeVisible();
  expect(await page.locator('.pm-settings-panel').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.setViewportSize({ width: 390, height: 850 });
  await page.locator('.document-details-preview--inline').scrollIntoViewIfNeeded();
  expect(await page.locator('.pm-settings-layout').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: `/tmp/papermind-document-settings-${theme}-narrow.png`, animations: 'disabled' });
});
