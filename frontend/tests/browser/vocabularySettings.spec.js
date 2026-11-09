import { expect, test } from '@playwright/test';

const categoryRow = (page, id) => page.locator(`.settings-category-row:has(#category-editor-${id})`);

async function mount(page, { deferCreate = false, failFirstCreate = false, dark = false, category = 'categories' } = {}) {
  const patches = [], categoryCreates = [], pending = [];
  const categories = [
    { id: 'invoice', name: 'Rechnung', area: 'finance', naming_template: null, usage_count: 5 },
    { id: 'contract', name: 'Vertrag', area: 'contracts_law', naming_template: null, usage_count: 2 },
  ];
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    if (path === '/api/settings') return route.fulfill({ json: { ui: { theme_mode: dark ? 'dark' : 'light' } } });
    const match = path.match(/^\/api\/document-types\/([^/]+)$/);
    if (match) {
      const target = categories.find(item => item.id === match[1]);
      if (request.method() === 'PATCH') {
        const payload = request.postDataJSON();
        patches.push({ id: target.id, ...payload });
        Object.assign(target, payload);
      }
      return route.fulfill({ json: { ...target, usage_count: null } });
    }
    if (path === '/api/document-types') {
      if (request.method() === 'POST') {
        categoryCreates.push(request.postDataJSON());
        if (deferCreate && categoryCreates.length === 1) await new Promise(resolve => pending.push(resolve));
        if (failFirstCreate && categoryCreates.length === 1) return route.fulfill({ status: 500, json: { error: { message: 'Anlegen fehlgeschlagen' } } });
        const created = { id: 'created-type', ...request.postDataJSON(), area: null, naming_template: null, is_active: true, usage_count: null };
        categories.push({ ...created, usage_count: 0 });
        return route.fulfill({ json: created });
      }
      return route.fulfill({ json: { items: categories } });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/__vocabulary-settings', route => route.fulfill({ contentType: 'text/html', body: '<div id="app" class="papermind-app"></div>' }));
  await page.goto('/__vocabulary-settings');
  await page.evaluate(async options => (await import('/tests/browser/fixtures/vocabularySettings.js')).mountVocabularySettings(options), { dark, category });
  if (category === 'categories') {
    await expect(page.getByRole('tab', { name: 'Dokumenttypen', exact: true })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('.settings-category-row').first()).toBeVisible();
  }
  return { patches, categoryCreates, categories, release: () => pending.shift()() };
}

test('the removed correspondents settings tab falls back to appearance', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('pm.settings.activeCategory', 'correspondents'));
  await mount(page, { category: 'correspondents' });
  await expect(page.getByRole('tab', { name: 'Korrespondenten', exact: true })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Darstellung', exact: true })).toHaveAttribute('aria-selected', 'true');
});

test(`document types: a pending or failed creation retains the search text and allows retry without duplicate submissions`, async ({ page }) => {
  const result = await mount(page, { deferCreate: true, failFirstCreate: true });
  const creates = result.categoryCreates;
  const button = page.getByRole('button', { name: 'Dokumenttyp hinzufügen', exact: true });
  const search = page.getByRole('textbox', { name: 'Dokumenttypen durchsuchen', exact: true });
  await search.fill('Neuer Testeintrag');
  await button.click();
  await expect.poll(() => creates.length).toBe(1);
  await expect(button).toBeDisabled();
  await expect(search).toHaveAttribute('readonly', '');
  await search.press('Enter');
  expect(creates).toHaveLength(1);
  result.release();
  await expect(button).toBeEnabled();
  await expect(search).toHaveValue('Neuer Testeintrag');
  await button.click();
  const createdRow = categoryRow(page, 'created-type');
  await expect(createdRow.locator('.settings-category-name')).toHaveText('Neuer Testeintrag');
  await expect(button).toBeDisabled();
  expect(creates).toHaveLength(2);
});

async function sampleDrawerAnimation(drawer) {
  return drawer.evaluate(async element => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const animation = element.getAnimations().find(item => item.transitionProperty === 'grid-template-rows');
    if (!animation) return { animated: false };
    animation.pause();
    animation.currentTime = Number(animation.effect.getTiming().duration) / 2;
    await new Promise(requestAnimationFrame);
    return {
      animated: true,
      height: element.getBoundingClientRect().height,
      fullHeight: element.querySelector('.settings-drawer__clip').firstElementChild.getBoundingClientRect().height,
      name: element.querySelector('input').value,
    };
  });
}

async function finishDrawerAnimation(drawer) {
  // Removing the completed leaving node can cancel its remaining opacity transition.
  await drawer.evaluate(element => Promise.allSettled(element.getAnimations().map(animation => {
    animation.play();
    return animation.finished;
  })));
}

test(`document types drawers animate both directions and retain outgoing field values`, async ({ page }) => {
  await mount(page);
  const selectedRow = categoryRow(page, 'invoice');
  const summary = selectedRow.locator('.settings-category-summary');
  const drawer = selectedRow.locator('.settings-drawer');
  await summary.evaluate(element => element.click());
  const opening = await sampleDrawerAnimation(drawer);
  expect(opening.animated).toBe(true);
  expect(opening.height).toBeGreaterThan(0);
  expect(opening.height).toBeLessThan(opening.fullHeight - 1);
  await finishDrawerAnimation(drawer);
  await summary.evaluate(element => element.click());
  const closing = await sampleDrawerAnimation(drawer);
  expect(closing.animated).toBe(true);
  expect(closing.height).toBeGreaterThan(0);
  expect(closing.height).toBeLessThan(closing.fullHeight - 1);
  expect(closing.name).toBe('Rechnung');
  await expect(summary).toHaveAttribute('aria-expanded', 'false');
  await finishDrawerAnimation(drawer);
  await expect(drawer).toHaveCount(0);
});

test('document types combine search and creation across area filters and keep the editor open after assignment', async ({ page }) => {
  const { categories, categoryCreates } = await mount(page, { category: 'categories' });
  const search = page.getByRole('textbox', { name: 'Dokumenttypen durchsuchen', exact: true });
  const add = page.getByRole('button', { name: 'Dokumenttyp hinzufügen', exact: true });
  const filters = page.locator('.settings-category-filter');
  const unassigned = filters.locator('.v-chip').filter({ hasText: 'Nicht zugeordnet' });
  await expect(filters.locator('.v-chip')).toHaveText(['Alle 2', 'Nicht zugeordnet 0']);
  await expect(add).toBeDisabled();
  for (const query of [' ', 'x', 'rech', ' RECHNUNG ', 'x'.repeat(31)]) {
    await search.fill(query);
    await expect(add).toBeDisabled();
    await search.press('Enter');
  }
  expect(categoryCreates).toHaveLength(0);
  await unassigned.click();
  await search.fill('Vertrag');
  await expect(page.locator('.settings-category-row')).toHaveCount(0);
  await expect(add).toBeDisabled();
  await search.fill('  Neue   Bescheinigung  ');
  await expect(add).toBeEnabled();
  await search.press('Enter');
  const created = categoryRow(page, 'created-type');
  await expect(created.locator('.settings-category-summary')).toHaveAttribute('aria-expanded', 'true');
  expect(categoryCreates).toEqual([{ name: 'Neue Bescheinigung' }]);
  expect(categories.find(category => category.id === 'created-type').area).toBeNull();
  await expect(created.locator('.settings-category-meta')).toHaveText('Ohne Zuordnung');
  await expect(unassigned).toHaveText('Nicht zugeordnet 1');
  await expect(add).toBeDisabled();
  await filters.locator('.v-chip').filter({ hasText: 'Alle' }).click();
  await unassigned.click();
  await expect(page.locator('.settings-category-row')).toHaveCount(1);
  await created.locator('.settings-category-summary').click();
  await created.getByRole('combobox', { name: 'Bereich', exact: true }).press('Enter');
  await page.getByRole('option', { name: 'Finanzen', exact: true }).click();
  await expect(unassigned).toHaveText('Nicht zugeordnet 0');
  await expect(filters.locator('.v-chip').filter({ hasText: 'Alle' })).toHaveText('Alle 3');
  await expect(created.locator('.settings-category-summary')).toHaveAttribute('aria-expanded', 'true');
  await search.fill('Nicht vorhanden');
  await expect(created.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Neue Bescheinigung');
  await created.locator('.settings-category-summary').click();
  await expect(page.locator('.settings-category-row')).toHaveCount(0);
});

test('document type edits stay open across sorting/filter changes and flush on tab switch', async ({ page }) => {
  const { patches } = await mount(page, { category: 'categories' });
  const invoice = page.locator('.settings-category-row:has(#category-editor-invoice)');
  await invoice.locator('.settings-category-summary').click();
  await invoice.getByRole('textbox', { name: 'Name', exact: true }).fill('Zahlungsbeleg');
  await expect(invoice.locator('.settings-category-name')).toHaveText('Zahlungsbeleg');
  await expect(invoice.locator('.settings-category-summary')).toHaveAttribute('aria-expanded', 'true');
  await invoice.getByRole('textbox', { name: 'Dateiname-Template', exact: true }).fill('{betreff}');
  await page.getByRole('tab', { name: 'Seitenleiste', exact: true }).click();
  await expect.poll(() => patches.length).toBe(2);
  expect(patches.at(-1).naming_template).toBe('{betreff}');
});

for (const dark of [false, true]) {
  test(`document types: desktop ${dark ? 'dark' : 'light'} layout`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await mount(page, { dark });
    const selectedRow = categoryRow(page, 'invoice');
    await selectedRow.locator('.settings-category-summary').click();
    await expect(selectedRow.getByRole('textbox', { name: 'Name', exact: true })).toBeVisible();
    await page.waitForTimeout(250); // Finish the drawer transition before positioning the preview.
    const summary = selectedRow.locator('.settings-category-summary');
    const mainBounds = await summary.locator('.settings-category-main').boundingBox();
    const actionsBounds = await summary.locator('.settings-category-actions').boundingBox();
    expect(actionsBounds.x).toBeGreaterThan(mainBounds.x + mainBounds.width);
    expect(Math.abs(mainBounds.y + mainBounds.height / 2 - actionsBounds.y - actionsBounds.height / 2)).toBeLessThan(1);
    await selectedRow.evaluate(element => {
      const panel = element.closest('.pm-settings-panel');
      panel.scrollTop += element.getBoundingClientRect().top - panel.getBoundingClientRect().top - panel.querySelector('.settings-info-card').offsetHeight - 10;
    });
    await page.screenshot({ path: `../.runtime/vocabulary-settings/document-types-desktop-${dark ? 'dark' : 'light'}.png`, fullPage: true, animations: 'disabled' });
    expect(await page.locator('.pm-settings-panel').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  });
}

test('document type search, chips and editor fit on mobile and keep drafts on row switches', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { patches } = await mount(page, { category: 'categories' });
  const search = page.getByRole('textbox', { name: 'Dokumenttypen durchsuchen', exact: true });
  const create = page.getByRole('button', { name: 'Dokumenttyp hinzufügen', exact: true });
  await search.fill('Rechnung');
  await expect(page.locator('.settings-category-row')).toHaveCount(1);
  await expect(create).toBeDisabled();
  await search.fill('Neue Bescheinigung');
  await expect(create).toBeEnabled();
  await page.screenshot({ path: '../.runtime/vocabulary-settings/document-types-mobile-search.png', fullPage: true, animations: 'disabled' });
  await search.fill('');
  const invoice = categoryRow(page, 'invoice');
  const contract = categoryRow(page, 'contract');
  await invoice.locator('.settings-category-summary').click();
  await invoice.getByRole('textbox', { name: 'Dateiname-Template', exact: true }).fill('{betreff}');
  await contract.locator('.settings-category-summary').click();
  await expect.poll(() => patches.length).toBe(1);
  expect(patches[0]).toMatchObject({ id: 'invoice', naming_template: '{betreff}' });
  await contract.evaluate(element => {
    const panel = element.closest('.pm-settings-panel');
    panel.scrollTop += element.getBoundingClientRect().top - panel.getBoundingClientRect().top - panel.querySelector('.settings-info-card').offsetHeight - 10;
  });
  await expect(contract.getByRole('textbox', { name: 'Name', exact: true })).toBeVisible();
  await page.screenshot({ path: '../.runtime/vocabulary-settings/document-types-mobile.png', fullPage: true, animations: 'disabled' });
  expect(await page.locator('.pm-settings-panel').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});
