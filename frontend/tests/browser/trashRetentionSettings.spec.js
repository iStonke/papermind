import { expect, test } from '@playwright/test';

async function mount(page, { admin = true, failFirstSave = false } = {}) {
  const persisted = { documents: { trash_retention_days: 30 } };
  const patches = [];
  let release;
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request();
    if (new URL(request.url()).pathname === '/api/settings') {
      if (request.method() === 'PATCH') {
        const patch = request.postDataJSON();
        patches.push(patch);
        if (failFirstSave && patches.length === 1) {
          await new Promise(resolve => { release = resolve; });
          return route.fulfill({ status: 500, json: { error: { message: 'Speichern fehlgeschlagen' } } });
        }
        Object.assign(persisted.documents, patch.documents);
      }
      return route.fulfill({ json: persisted });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/__trash-retention-settings', route => route.fulfill({
    contentType: 'text/html', body: '<div id="app" class="papermind-app"></div>',
  }));
  await page.goto('/__trash-retention-settings');
  await page.evaluate(async options => {
    await (await import('/tests/browser/fixtures/trashRetentionSettings.js')).mountTrashRetentionSettings(options);
  }, { admin });
  return { persisted, patches, release: () => release() };
}

async function chooseRetention(page, label) {
  const control = page.getByRole('combobox', { name: 'Automatisch löschen', exact: true });
  await expect(control).toBeEnabled();
  await control.press('Enter');
  await page.getByRole('option', { name: label, exact: true }).click();
}

const retentionSelect = page => page.locator('.pm-setting-select').filter({
  has: page.getByRole('combobox', { name: 'Automatisch löschen', exact: true }),
});

test('general settings save every trash retention period including never across a fresh settings session', async ({ page }, testInfo) => {
  const { persisted, patches } = await mount(page);
  const surface = page.locator('.pm-settings-nav__group').filter({ hasText: 'Oberfläche' });
  await expect(surface.getByRole('tab', { name: 'Allgemein', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tab', { name: 'Bibliothek', exact: true })).toHaveCount(0);
  await expect(page.locator('.pm-settings-panel')).toContainText('Dokumente und Notizen');
  await expect(page.getByRole('combobox', { name: 'Anzeigen für', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Leere Tags suchen', exact: true })).toBeVisible();
  for (const [days, label] of [[0, 'Nie'], [1, 'Nach 1 Tag'], [7, 'Nach 7 Tagen'], [14, 'Nach 14 Tagen'], [30, 'Nach 30 Tagen'], [90, 'Nach 90 Tagen'], [180, 'Nach 180 Tagen'], [365, 'Nach 365 Tagen'], [0, 'Nie']]) {
    await chooseRetention(page, label);
    await expect.poll(() => persisted.documents.trash_retention_days).toBe(days);
    await expect(retentionSelect(page)).not.toHaveClass(/v-input--disabled/);
    await expect(retentionSelect(page).locator('.v-select__selection-text')).toHaveText(label);
  }
  expect(patches).toHaveLength(9);
  expect(patches.at(-1)).toEqual({ documents: { trash_retention_days: 0 } });
  await page.screenshot({ path: testInfo.outputPath('general-trash-retention.png'), animations: 'disabled' });
  await page.evaluate(async () => {
    window.unmountTrashRetentionSettings();
    await (await import('/tests/browser/fixtures/trashRetentionSettings.js')).mountTrashRetentionSettings();
  });
  await expect(retentionSelect(page).locator('.v-select__selection-text')).toHaveText('Nie');
});

test('failed trash retention saves restore the previous period and permit retry', async ({ page }) => {
  const { persisted, patches, release } = await mount(page, { failFirstSave: true });
  await chooseRetention(page, 'Nach 7 Tagen');
  await expect.poll(() => patches.length).toBe(1);
  await expect(retentionSelect(page)).toHaveClass(/v-input--disabled/);
  release();
  await expect(retentionSelect(page).locator('.v-select__selection-text')).toHaveText('Nach 30 Tagen');
  expect(persisted.documents.trash_retention_days).toBe(30);
  await chooseRetention(page, 'Nach 14 Tagen');
  await expect.poll(() => persisted.documents.trash_retention_days).toBe(14);
  expect(patches).toHaveLength(2);
});

test('non-admins cannot change the global trash retention policy', async ({ page }) => {
  const { patches } = await mount(page, { admin: false });
  const surface = page.locator('.pm-settings-nav__group').filter({ hasText: 'Oberfläche' });
  await expect(surface.getByRole('tab', { name: 'Allgemein', exact: true })).toHaveCount(0);
  await expect(page.getByRole('combobox', { name: 'Automatisch löschen', exact: true })).toHaveCount(0);
  expect(patches).toEqual([]);
});
