import { expect, test } from '@playwright/test';

const row = (page, id) => page.locator(`.settings-correspondent-row:has(#correspondent-editor-${id})`);
const categoryRow = (page, id) => page.locator(`.settings-category-row:has(#category-editor-${id})`);

async function mount(page, { deferFirstSave = false, failFirstSave = false, deferCreate = false, failFirstCreate = false, dark = false, category = 'correspondents', animationsEnabled = true } = {}) {
  const patches = [], creates = [], categoryCreates = [], pending = [];
  const items = [
    { id: 'alpha', name: 'Alpenverein', short_name: 'DAV', kind: 'organization', parent_id: null, aliases: [{ id: 'alias-1', alias: 'Deutscher Alpenverein' }], usage_count: 12 },
    { id: 'beta', name: 'Bergwerke GmbH', short_name: null, kind: 'organization', parent_id: null, aliases: [], usage_count: 0 },
    { id: 'person', name: 'Mara Fischer', short_name: null, kind: 'person', parent_id: 'alpha', aliases: [], usage_count: 2 },
    { id: 'collection', name: 'Versicherungen', short_name: null, kind: 'collection', parent_id: null, aliases: [], usage_count: 3 },
    { id: 'unknown', name: 'TV', short_name: null, kind: null, parent_id: null, aliases: [], usage_count: 0 },
  ];
  const categories = [
    { id: 'invoice', name: 'Rechnung', area: 'finance', naming_template: null, usage_count: 5 },
    { id: 'contract', name: 'Vertrag', area: 'contracts_law', naming_template: null, usage_count: 2 },
  ];
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    if (path === '/api/settings') return route.fulfill({ json: { ui: { theme_mode: dark ? 'dark' : 'light' } } });
    if (path === '/api/correspondents/unresolved') return route.fulfill({ json: { items: [] } });
    if (path === '/api/correspondents') {
      if (request.method() === 'POST') {
        creates.push(request.postDataJSON());
        if (deferCreate && creates.length === 1) await new Promise(resolve => pending.push(resolve));
        if (failFirstCreate && creates.length === 1) return route.fulfill({ status: 500, json: { error: { message: 'Anlegen fehlgeschlagen' } } });
        const created = { id: 'created', kind: null, ...request.postDataJSON(), short_name: null, parent_id: null, aliases: [], usage_count: null };
        items.push({ ...created, usage_count: 0 });
        return route.fulfill({ json: created });
      }
      return route.fulfill({ json: { items } });
    }
    const match = path.match(/^\/api\/(correspondents|document-types)\/([^/]+)(\/aliases(?:\/([^/]+))?)?$/);
    if (match) {
      const target = (match[1] === 'correspondents' ? items : categories).find(item => item.id === match[2]);
      if (request.method() === 'PATCH') {
        const payload = request.postDataJSON();
        patches.push({ id: target.id, ...payload });
        if (deferFirstSave && patches.length === 1) await new Promise(resolve => pending.push(resolve));
        if (failFirstSave && patches.length === 1) return route.fulfill({ status: 500, json: { error: { message: 'Speichern fehlgeschlagen' } } });
        Object.assign(target, payload);
      } else if (match[3] && request.method() === 'POST') {
        target.aliases.push({ id: 'added-alias', alias: request.postDataJSON().alias });
      } else if (match[3] && request.method() === 'DELETE') {
        target.aliases = target.aliases.filter(alias => alias.id !== match[4]);
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
  await page.evaluate(async options => (await import('/tests/browser/fixtures/vocabularySettings.js')).mountVocabularySettings(options), { dark, category, animationsEnabled });
  await expect(page.getByRole('tab', { name: category === 'categories' ? 'Dokumenttypen' : 'Korrespondenten', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator(category === 'categories' ? '.settings-category-row' : '.settings-correspondent-row').first()).toBeVisible();
  return { patches, creates, categoryCreates, items, categories, release: () => pending.shift()() };
}

test('the combined search control creates only when no name, short name or alias matches across all types', async ({ page }) => {
  const { items, creates } = await mount(page);
  const button = page.getByRole('button', { name: 'Korrespondent hinzufügen', exact: true });
  const search = page.getByRole('textbox', { name: 'Korrespondenten durchsuchen', exact: true });
  await expect(button).toBeDisabled();
  for (const query of ['  ', 'x', 'Alpen', ' DAV ', 'deutscher   ALPENVEREIN', 'Mara Fischer']) {
    await search.fill(query);
    await expect(button).toBeDisabled();
    await search.press('Enter');
  }
  expect(creates).toHaveLength(0);
  await page.locator('.settings-correspondent-filter .v-chip').filter({ hasText: 'Personen' }).click();
  await search.fill('Alpenverein');
  await expect(page.locator('.settings-correspondent-row')).toHaveCount(0);
  await expect(button).toBeDisabled();
  await search.fill('  Neuer   Testverein  ');
  await expect(button).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Typ des neuen Korrespondenten', exact: true })).toHaveCount(0);
  await button.click();
  await expect.poll(() => items.find(item => item.id === 'created')?.name).toBe('Neuer Testverein');
  expect(creates).toEqual([{ name: 'Neuer Testverein' }]);
  expect(items.find(item => item.id === 'created').kind).toBeNull();
  await expect(row(page, 'created').locator('.settings-category-meta')).toContainText('ohne Typ');
  await expect(page.locator('.settings-correspondent-filter .v-chip').filter({ hasText: 'Ohne Typ' })).toHaveText('Ohne Typ 2');
  await expect(button).toBeDisabled();
  await expect(row(page, 'created').locator('.settings-correspondent-summary')).toHaveAttribute('aria-expanded', 'true');
  await expect(row(page, 'created').getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Neuer Testverein');
});

for (const category of ['correspondents', 'categories']) {
  test(`${category}: a pending or failed creation retains the search text and allows retry without duplicate submissions`, async ({ page }) => {
    const result = await mount(page, { category, deferCreate: true, failFirstCreate: true });
    const isCategory = category === 'categories';
    const creates = isCategory ? result.categoryCreates : result.creates;
    const button = page.getByRole('button', { name: isCategory ? 'Dokumenttyp hinzufügen' : 'Korrespondent hinzufügen', exact: true });
    const search = page.getByRole('textbox', { name: isCategory ? 'Dokumenttypen durchsuchen' : 'Korrespondenten durchsuchen', exact: true });
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
    const createdRow = isCategory ? categoryRow(page, 'created-type') : row(page, 'created');
    await expect(createdRow.locator('.settings-category-name')).toHaveText('Neuer Testeintrag');
    await expect(button).toBeDisabled();
    expect(creates).toHaveLength(2);
  });
}

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

for (const category of ['correspondents', 'categories']) {
  test(`${category} drawers animate both directions and retain outgoing field values`, async ({ page }) => {
    await mount(page, { category });
    const selectedRow = category === 'categories'
      ? page.locator('.settings-category-row:has(#category-editor-invoice)') : row(page, 'alpha');
    const summary = selectedRow.locator(category === 'categories' ? '.settings-category-summary' : '.settings-correspondent-summary');
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
    expect(closing.name).toBe(category === 'categories' ? 'Rechnung' : 'Alpenverein');
    await expect(summary).toHaveAttribute('aria-expanded', 'false');
    await finishDrawerAnimation(drawer);
    await expect(drawer).toHaveCount(0);
  });
}

for (const preference of ['disabled', 'reduced-motion']) {
  test(`drawer animation respects ${preference}`, async ({ page }) => {
    if (preference === 'reduced-motion') await page.emulateMedia({ reducedMotion: 'reduce' });
    await mount(page, { animationsEnabled: preference !== 'disabled' });
    const selectedRow = row(page, 'alpha');
    const summary = selectedRow.locator('.settings-correspondent-summary');
    await summary.evaluate(element => element.click());
    await expect(selectedRow.getByRole('textbox', { name: 'Name', exact: true })).toBeVisible();
    expect(await selectedRow.locator('.settings-drawer').evaluate(element => element.getAnimations().length)).toBe(0);
    await summary.evaluate(element => element.click());
    await expect(selectedRow.locator('.settings-drawer')).toHaveCount(0);
  });
}

test('reopening during collapse cancels the outgoing animation without losing the draft', async ({ page }) => {
  await mount(page);
  const selectedRow = row(page, 'alpha');
  const summary = selectedRow.locator('.settings-correspondent-summary');
  await summary.click();
  await selectedRow.getByRole('textbox', { name: 'Kurzname', exact: true }).fill('ENTWURF');
  await summary.evaluate(element => element.click());
  await sampleDrawerAnimation(selectedRow.locator('.settings-drawer'));
  await summary.evaluate(element => element.click());
  await expect(summary).toHaveAttribute('aria-expanded', 'true');
  await expect(selectedRow.getByRole('textbox', { name: 'Kurzname', exact: true })).toHaveValue('ENTWURF');
  await expect(selectedRow.getByRole('textbox', { name: 'Kurzname', exact: true })).toBeVisible();
  await expect(selectedRow.locator('.settings-drawer-leave-active')).toHaveCount(0);
});

test('slow autosaves keep the editor, focus and position stable and save the latest draft', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { patches, items, release } = await mount(page, { deferFirstSave: true });
  const alpha = row(page, 'alpha');
  await alpha.locator('.settings-correspondent-summary').click();
  const before = await alpha.boundingBox();
  await alpha.getByRole('textbox', { name: 'Name', exact: true }).fill('Zweiter Alpenverein');
  await expect.poll(() => patches.length).toBe(1);
  await alpha.getByRole('textbox', { name: 'Name', exact: true }).fill('Neuster Alpenverein');
  await alpha.getByRole('textbox', { name: 'Kurzname', exact: true }).fill('NEU');
  await expect(alpha.locator('.record-save-status')).toHaveCount(0);
  expect(patches).toHaveLength(1);
  release();
  await expect(alpha.locator('.settings-category-name')).toHaveText('Neuster Alpenverein');
  expect(patches).toHaveLength(2);
  expect(items.find(item => item.id === 'alpha').name).toBe('Neuster Alpenverein');
  await expect(alpha.locator('.settings-correspondent-summary')).toHaveAttribute('aria-expanded', 'true');
  await expect(alpha.getByRole('textbox', { name: 'Kurzname', exact: true })).toBeFocused();
  expect(Math.abs((await alpha.boundingBox()).y - before.y)).toBeLessThan(2);
  await expect(alpha.locator('.settings-category-count')).toHaveText('12');
});

test('rapid row switches, closing and reopening flush the right records', async ({ page }) => {
  const { patches } = await mount(page);
  await row(page, 'alpha').locator('.settings-correspondent-summary').click();
  await page.getByRole('textbox', { name: 'Kurzname', exact: true }).fill('NEU-A');
  await row(page, 'beta').locator('.settings-correspondent-summary').click();
  await page.getByRole('textbox', { name: 'Kurzname', exact: true }).fill('NEU-B');
  await page.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  await expect.poll(() => patches.length).toBe(2);
  expect(patches.map(patch => [patch.id, patch.short_name])).toEqual([['alpha', 'NEU-A'], ['beta', 'NEU-B']]);
  await page.evaluate(() => window.vocabularySettings.open());
  await expect(page.getByRole('textbox', { name: 'Kurzname', exact: true })).toHaveValue('NEU-B');
  await row(page, 'alpha').locator('.settings-correspondent-summary').click();
  await expect(page.getByRole('textbox', { name: 'Kurzname', exact: true })).toHaveValue('NEU-A');
});

test('failed and invalid saves preserve the draft and offer an explicit retry', async ({ page }) => {
  const { patches } = await mount(page, { failFirstSave: true });
  const alpha = row(page, 'alpha');
  await alpha.locator('.settings-correspondent-summary').click();
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Entwurf Alpenverein');
  await expect(alpha.getByRole('status')).toContainText('Nicht gespeichert');
  await page.evaluate(() => window.vocabularySettings.reload());
  await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Entwurf Alpenverein');
  await page.getByRole('button', { name: 'Erneut speichern', exact: true }).click();
  await expect(alpha.locator('.record-save-status')).toHaveCount(0);
  expect(patches).toHaveLength(2);
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('');
  await page.evaluate(() => window.vocabularySettings.reload());
  await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('');
  await row(page, 'beta').locator('.settings-correspondent-summary').click();
  await alpha.locator('.settings-correspondent-summary').click();
  await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('');
  expect(patches).toHaveLength(2);
});

test('changing kind under a filter and editing aliases never closes the active row', async ({ page }) => {
  const { patches } = await mount(page);
  await page.locator('.settings-correspondent-filter .v-chip').filter({ hasText: 'Organisationen' }).click();
  const beta = row(page, 'beta');
  await beta.locator('.settings-correspondent-summary').click();
  await beta.getByRole('button', { name: 'Person', exact: true }).click();
  await expect.poll(() => patches.at(-1)?.kind).toBe('person');
  expect(patches.at(-1).kind).toBe('person');
  await expect(beta.locator('.settings-correspondent-summary')).toHaveAttribute('aria-expanded', 'true');
  await expect(beta.getByRole('combobox', { name: 'Gehört zu Organisation', exact: true })).toBeVisible();
  await beta.getByRole('textbox', { name: 'Aliase', exact: true }).fill('Bergwerk');
  await beta.getByRole('button', { name: 'Alias hinzufügen', exact: true }).click();
  await expect(beta.locator('.settings-chip-list')).toContainText('Bergwerk');
  await expect(beta.locator('.settings-correspondent-summary')).toHaveAttribute('aria-expanded', 'true');
  await page.getByRole('textbox', { name: 'Korrespondenten durchsuchen' }).fill('Bergwerk');
  await expect(beta).toBeVisible();
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
  await page.getByRole('tab', { name: 'Korrespondenten', exact: true }).click();
  await expect.poll(() => patches.length).toBe(2);
  expect(patches.at(-1).naming_template).toBe('{betreff}');
});

for (const category of ['correspondents', 'categories']) {
  for (const dark of [false, true]) {
    test(`${category}: desktop ${dark ? 'dark' : 'light'} layout`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 1000 });
      await mount(page, { category, dark });
      const isCategory = category === 'categories';
      const selectedRow = isCategory ? categoryRow(page, 'invoice') : row(page, 'alpha');
      await selectedRow.locator(isCategory ? '.settings-category-summary' : '.settings-correspondent-summary').click();
      await expect(selectedRow.getByRole('textbox', { name: 'Name', exact: true })).toBeVisible();
      await page.waitForTimeout(250); // Finish the drawer transition before positioning the preview.
      const summary = selectedRow.locator(isCategory ? '.settings-category-summary' : '.settings-correspondent-summary');
      const mainBounds = await summary.locator('.settings-category-main').boundingBox();
      const actionsBounds = await summary.locator(isCategory ? '.settings-category-actions' : '.settings-correspondent-summary__right').boundingBox();
      expect(actionsBounds.x).toBeGreaterThan(mainBounds.x + mainBounds.width);
      expect(Math.abs(mainBounds.y + mainBounds.height / 2 - actionsBounds.y - actionsBounds.height / 2)).toBeLessThan(1);
      await selectedRow.evaluate(element => {
        const panel = element.closest('.pm-settings-panel');
        panel.scrollTop += element.getBoundingClientRect().top - panel.getBoundingClientRect().top - panel.querySelector('.settings-info-card').offsetHeight - 10;
      });
      await page.screenshot({ path: `../.runtime/vocabulary-settings/${isCategory ? 'document-types-' : ''}desktop-${dark ? 'dark' : 'light'}.png`, fullPage: true, animations: 'disabled' });
      expect(await page.locator('.pm-settings-panel').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    });
  }
}

test('mobile editor controls fit and remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mount(page);
  const unassigned = page.locator('.settings-correspondent-filter .v-chip').filter({ hasText: 'Ohne Typ' });
  await expect(unassigned).toHaveText('Ohne Typ 1');
  await unassigned.click();
  await expect(page.locator('.settings-correspondent-row')).toHaveCount(1);
  await expect(row(page, 'unknown')).toBeVisible();
  await row(page, 'unknown').locator('.settings-correspondent-summary').click();
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('TV Verein');
  await expect(row(page, 'unknown').locator('.settings-category-name')).toHaveText('TV Verein');
  await row(page, 'unknown').getByRole('button', { name: 'Organisation', exact: true }).click();
  await expect(row(page, 'unknown').locator('.settings-category-meta')).not.toContainText('ohne Typ');
  await expect(unassigned).toHaveText('Ohne Typ 0');
  await expect(row(page, 'unknown').locator('.settings-correspondent-summary')).toHaveAttribute('aria-expanded', 'true');
  await row(page, 'unknown').evaluate(element => {
    const panel = element.closest('.pm-settings-panel');
    panel.scrollTop += element.getBoundingClientRect().top - panel.getBoundingClientRect().top - panel.querySelector('.settings-info-card').offsetHeight - 10;
  });
  await page.screenshot({ path: '../.runtime/vocabulary-settings/mobile.png', fullPage: true, animations: 'disabled' });
  expect(await page.locator('.pm-settings-panel').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});

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
