import { test, expect } from '@playwright/test';

test.use({ timezoneId: 'Europe/Berlin' });

async function mount(page, options = {}) {
  await page.setViewportSize({ width: 1000, height: 850 });
  await page.route('**/__document-dates', route => route.fulfill({ contentType: 'text/html', body: '<div id="app"></div>' }));
  await page.goto('/__document-dates');
  await page.evaluate(async options => (await import('/tests/browser/fixtures/documentDates.js')).mount(options), options);
}

for (const theme of ['light', 'dark']) {
  test(`date popover shows distinct dates and optional help in ${theme}`, async ({ page }) => {
    await mount(page, { theme });
    const trigger = page.getByRole('button', { name: 'Datumsangaben anzeigen', exact: true });
    await expect(trigger).toHaveText('24.08.2026, 01:05');
    await trigger.hover();
    await expect.poll(() => trigger.evaluate(el => getComputedStyle(el, '::before').opacity)).toBe('1');
    await trigger.click();
    const dialog = page.getByRole('dialog', { name: 'Datumsangaben', exact: true });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('dt')).toHaveText(['Hinzugefügt am', 'Dokumentdatum', 'Zuletzt geändert']);
    await expect(dialog.locator('dd')).toHaveText(['24.08.2026, 01:05', '16.10.2018', '01.11.2026, 20:30']);
    await expect(dialog.locator('time').nth(1)).toHaveAttribute('datetime', '2018-10-16');
    const help = dialog.getByRole('button', { name: 'Datumsangaben erklären', exact: true });
    const explanation = dialog.locator('.document-dates__explanation');
    await expect(explanation).toBeHidden();
    await dialog.screenshot({ path: `/tmp/papermind-dates-${theme}.png`, animations: 'disabled' });
    await help.focus();
    await page.keyboard.press('Enter');
    await expect(help).toHaveAttribute('aria-expanded', 'true');
    await expect(explanation).toContainText('wann dieses Dokument zu PaperMind hinzugefügt wurde');
    await expect(explanation).toBeVisible();
    await dialog.screenshot({ path: `/tmp/papermind-dates-help-${theme}.png`, animations: 'disabled' });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await trigger.click();
    await expect(help).toHaveAttribute('aria-expanded', 'false');
    await expect(explanation).toBeHidden();
    expect(await page.evaluate(() => window.documentDatesDemo.headerClicks.value)).toBe(0);
    await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('dialog', { name: 'Wissen', exact: true })).toBeVisible();
  });
}

test('dates update with the document and never substitute AI dates or invented timestamps', async ({ page }) => {
  await mount(page, { document: { document_date: null, ai_document_date: '2018-10-16', updated_at: null } });
  await page.getByRole('button', { name: 'Datumsangaben anzeigen', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Datumsangaben', exact: true });
  await expect(dialog.locator('dd')).toHaveText(['24.08.2026, 01:05', 'Nicht angegeben', 'Nicht verfügbar']);
  await page.evaluate(() => { Object.assign(window.documentDatesDemo.data, { document_date: '2020-02-29', updated_at: '2026-11-01T20:45:00Z' }); });
  await expect(dialog.locator('dd').nth(1)).toHaveText('29.02.2020');
  await expect(dialog.locator('dd').nth(2)).toHaveText('01.11.2026, 21:45');
  await page.evaluate(() => { window.documentDatesDemo.data.id = 'document-b'; window.documentDatesDemo.data.created_at = 'invalid'; });
  await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: 'Datumsangaben anzeigen', exact: true }).click();
  await expect(dialog.locator('dd').first()).toHaveText('Nicht verfügbar');
});

test('date help fits narrow viewports and respects reduced motion', async ({ page }) => {
  await mount(page, { theme: 'dark' });
  await page.setViewportSize({ width: 390, height: 740 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.getByRole('button', { name: 'Datumsangaben anzeigen', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Datumsangaben', exact: true });
  await dialog.getByRole('button', { name: 'Datumsangaben erklären', exact: true }).click();
  await expect(dialog.locator('.document-dates__explanation')).toBeInViewport();
  await expect.poll(() => dialog.evaluate(el => el.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  expect(await dialog.locator('.document-dates__help').evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s');
  await dialog.screenshot({ path: '/tmp/papermind-dates-mobile.png', animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Datumsangaben schließen', exact: true }).click();
  await expect(dialog).toHaveCount(0);
});
