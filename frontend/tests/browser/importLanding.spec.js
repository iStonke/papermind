import { expect, test } from '@playwright/test';

const docs = Array.from({ length: 140 }, (_, index) => ({
  id: `doc-${index}`, display_name: `Dokument ${index}`, original_filename: `doc-${index}.pdf`,
  document_date: index < 60 ? '2026-10-13' : '2018-04-12', updated_at: '2026-10-13T12:00:00',
  is_unread: true, tags: [], correspondent_id: index < 60 ? 'bank' : 'tax',
  correspondent_name: index < 60 ? 'Bank' : 'Finanzamt', document_type: index < 60 ? 'Brief' : 'Steuern',
}));

async function mount(page, mode, delayMs = 0) {
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/thumbnail')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80"><rect width="60" height="80" fill="#d0e9e6"/></svg>' });
    let data = { items: [] };
    if (url.pathname === '/api/documents') {
      if (delayMs) await new Promise(resolve => setTimeout(resolve, delayMs));
      if (url.searchParams.has('include_correspondent_groups')) data = { correspondent_groups: [{ correspondent_id: 'bank', name: 'Bank', count: 60 }, { correspondent_id: 'tax', name: 'Finanzamt', count: 80 }] };
      else if (url.searchParams.has('include_document_type_groups')) data = { document_type_groups: [{ document_type: 'Brief', count: 60 }, { document_type: 'Steuern', count: 80 }] };
      else {
        const matching = docs.filter(doc => !url.searchParams.get('correspondent_id') || doc.correspondent_id === url.searchParams.get('correspondent_id'))
          .filter(doc => !url.searchParams.get('document_type') || doc.document_type === url.searchParams.get('document_type'));
        const offset = Number(url.searchParams.get('offset') || 0);
        data = { items: matching.slice(offset, offset + 50) };
      }
    } else if (url.pathname === '/api/settings') data = {};
    else if (url.pathname.startsWith('/api/documents/')) data = docs.find(doc => doc.id === url.pathname.split('/').at(-1)) || {};
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__import-landing', r => r.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__import-landing');
  await page.evaluate(async ({ mode, docs }) => (await import('/tests/browser/fixtures/importLanding.js')).mountImportLanding(mode, docs), { mode, docs });
}

for (const mode of ['list', 'timeline', 'correspondents', 'document_types']) {
  test(`scanner import lands on the older document in ${mode} view`, async ({ page }) => {
    await mount(page, mode);
    const target = await page.evaluate(() => window.flyImport('doc-120'));
    expect(target).not.toBeNull();
    expect(target.onRealRow).toBe(true);
    const row = page.locator('[data-document-id="doc-120"]');
    await expect(row).toBeVisible();
    await expect.poll(() => page.evaluate(() => window.lastLanding)).not.toBeNull();
    const final = await page.evaluate(() => window.lastLanding);
    for (const property of ['left', 'top', 'width', 'height']) expect(Math.abs(final[property] - target[property])).toBeLessThan(1);
    const thumb = row.locator('.document-row__thumb, .doc-timeline__thumb, .doc-groups__thumbnail');
    await expect(thumb.locator('img')).toHaveCSS('opacity', '1');
    await expect(row).toHaveClass(/just-arrived|pm-import-arrival/);
    expect(await page.locator('.document-row--import-landing').count()).toBe(0);
  });
}

test('an import absent from the filtered list never lands on the first document', async ({ page }) => {
  await mount(page, 'list');
  expect(await page.evaluate(() => window.locateImport('filtered-out'))).toBeNull();
  const target = await page.evaluate(() => window.flyImport('filtered-out'));
  expect(target.vanish).toBe(true);
  expect(await page.evaluate(() => window.importDestination)).toBe('all-documents');
  await expect.poll(() => page.evaluate(() => window.lastLanding)).not.toBeNull();
  expect(await page.evaluate(() => window.lastLanding.width)).toBe(0);
  await expect(page.locator('.document-row--just-arrived')).toHaveCount(0);
});

test('reduced motion lands immediately and reveals the timeline thumbnail', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mount(page, 'timeline');
  const target = await page.evaluate(() => window.flyImport('doc-120'));
  expect(target).not.toBeNull();
  await expect.poll(() => page.evaluate(() => window.lastLanding)).not.toBeNull();
  await expect(page.locator('[data-document-id="doc-120"] .doc-timeline__thumb img')).toHaveCSS('opacity', '1');
});

test('slow grouped refresh is awaited before locating the correct second-page document', async ({ page }) => {
  await mount(page, 'document_types', 450);
  await page.evaluate(() => window.refreshImportGroups());
  const target = await page.evaluate(() => window.flyImport('doc-120'));
  expect(target).not.toBeNull();
  await expect.poll(() => page.evaluate(() => window.lastLanding)).not.toBeNull();
  await expect(page.locator('[data-document-id="doc-120"]')).toHaveClass(/pm-import-arrival/);
});
