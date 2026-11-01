import { test, expect } from '@playwright/test';

async function mount(page, options = {}) {
  await page.setViewportSize({ width: 1000, height: 950 });
  await page.route('**/__ocr-details', route => route.fulfill({ contentType: 'text/html', body: '<div id="app"></div>' }));
  await page.goto('/__ocr-details');
  await page.evaluate(async options => (await import('/tests/browser/fixtures/ocrDetails.js')).mount(options), options);
  await page.getByRole('button', { name: 'OCR-Details anzeigen', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Texterkennung', exact: true })).toBeVisible();
}

for (const theme of ['light', 'dark']) {
  test(`OCR popover shows the scale, facts, explanation and escaped text in ${theme}`, async ({ page }) => {
    await mount(page, { theme, document: { text_content: '<script>kein HTML</script>\nZweite Zeile' } });
    const dialog = page.getByRole('dialog', { name: 'Texterkennung', exact: true });
    await expect(dialog.getByRole('meter')).toHaveAttribute('aria-valuenow', '93.2');
    await expect(dialog).toContainText('93,2 %');
    await expect(dialog).toContainText('12,4 Sekunden');
    await expect(dialog).toContainText('Durch OCR erkannt');
    await expect(dialog).toContainText('30.10.2026');
    const help = dialog.getByRole('button', { name: 'Was macht OCR?', exact: true });
    const explanation = dialog.locator('.ocr-details__explanation');
    await expect(help).toHaveAttribute('aria-expanded', 'false');
    await expect(explanation).toBeHidden();
    expect(await page.evaluate(() => window.ocrDemo.headerClicks.value)).toBe(0);
    await dialog.screenshot({ path: `/tmp/papermind-ocr-popover-${theme}.png`, animations: 'disabled' });
    await help.focus();
    await page.keyboard.press('Enter');
    await expect(help).toHaveAttribute('aria-expanded', 'true');
    await expect(explanation).toBeVisible();
    await expect(explanation).toContainText('OCR macht Scans und Bilder durchsuchbar');
    await dialog.screenshot({ path: `/tmp/papermind-ocr-help-${theme}.png`, animations: 'disabled' });
    await help.click();
    await expect(explanation).toBeHidden();
    await help.click();
    await dialog.getByRole('button', { name: 'OCR-Details schließen', exact: true }).click();
    await page.getByRole('button', { name: 'OCR-Details anzeigen', exact: true }).click();
    await expect(help).toHaveAttribute('aria-expanded', 'false');
    await expect(explanation).toBeHidden();
    await dialog.getByRole('button', { name: 'Erkannten Text ansehen', exact: true }).click();
    const textDialog = page.getByRole('dialog', { name: 'Erkannter Text', exact: true });
    await expect(textDialog.getByLabel('Erkannter Dokumenttext')).toHaveText('<script>kein HTML</script>\nZweite Zeile');
    await expect(textDialog.locator('script')).toHaveCount(0);
    await textDialog.getByRole('button', { name: 'Zurück zu den OCR-Details', exact: true }).click();
    await dialog.getByRole('button', { name: 'Erneut erkennen', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(await page.evaluate(() => window.ocrDemo.retries.value)).toBe(1);
  });
}

test('unknown quality, busy states and document changes never expose stale data', async ({ page }) => {
  await mount(page, { document: { ocr_quality_status: null, ocr_confidence_score: null, ocr_quality_message: null, text_content: null, jobs: [], ocr_processing_seconds: null } });
  const dialog = page.getByRole('dialog', { name: 'Texterkennung', exact: true });
  await expect(dialog.getByRole('meter')).toHaveCount(0);
  await expect(dialog).toContainText('Noch nicht bewertet');
  await expect(dialog.locator('.ocr-details__scale, .ocr-details__legend')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Erneut erkennen und bewerten', exact: true })).toBeEnabled();
  await dialog.screenshot({ path: '/tmp/papermind-ocr-unrated-light.png', animations: 'disabled' });
  await expect(dialog.getByRole('button', { name: 'Erkannten Text ansehen', exact: true })).toBeDisabled();
  await expect(dialog).not.toContainText('Letzter Durchlauf');
  await page.evaluate(() => { window.ocrDemo.status.tone = 'progress'; });
  await expect(dialog).toContainText('Wird ermittelt');
  await expect(dialog.getByRole('button', { name: 'Erneut erkennen', exact: true })).toBeDisabled();
  await page.evaluate(() => { window.ocrDemo.data.id = 'document-b'; });
  await expect(dialog).toHaveCount(0);
});

test('the unrated action starts a new assessment and stored quality restores the actual scale', async ({ page }) => {
  await mount(page, { theme: 'dark', document: { ocr_quality_status: null, ocr_confidence_score: null, ocr_quality_message: null } });
  const dialog = page.getByRole('dialog', { name: 'Texterkennung', exact: true });
  await expect(dialog.getByRole('button', { name: 'Erneut erkennen', exact: true })).toHaveCount(0);
  await dialog.screenshot({ path: '/tmp/papermind-ocr-unrated-dark.png', animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Erneut erkennen und bewerten', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(await page.evaluate(() => window.ocrDemo.retries.value)).toBe(1);
  await page.evaluate(() => { window.ocrDemo.data.flags = { ocr: { quality: { status: 'warning', confidence_score: 69.4, message: 'Hinweis aus dem gespeicherten Ergebnis.' } } }; });
  await page.getByRole('button', { name: 'OCR-Details anzeigen', exact: true }).click();
  await expect(dialog.getByRole('meter')).toHaveAttribute('aria-valuenow', '69.4');
  await expect(dialog).toContainText('Eingeschränkt');
  await expect(dialog).toContainText('Hinweis aus dem gespeicherten Ergebnis.');
  await expect(dialog.getByRole('button', { name: 'Erneut erkennen und bewerten', exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => window.ocrDemo.retries.value)).toBe(1);
});

test('warning quality remains readable on a narrow viewport and Escape closes only the popover', async ({ page }) => {
  await mount(page, { tone: 'warning', document: { ocr_quality_status: 'warning', ocr_confidence_score: 65, ocr_quality_message: 'Einige Zeichen wurden unsicher erkannt.' } });
  await page.setViewportSize({ width: 390, height: 740 });
  const dialog = page.getByRole('dialog', { name: 'Texterkennung', exact: true });
  await expect(dialog).toContainText('Eingeschränkt');
  await expect(dialog).toContainText('Einige Zeichen wurden unsicher erkannt.');
  await expect.poll(() => dialog.evaluate(el => el.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await dialog.getByRole('button', { name: 'Was macht OCR?', exact: true }).click();
  await expect(dialog.locator('.ocr-details__explanation')).toBeInViewport();
  expect(await dialog.locator('.ocr-details__help').evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s');
  await dialog.screenshot({ path: '/tmp/papermind-ocr-popover-mobile.png', animations: 'disabled' });
  await dialog.getByRole('button', { name: 'OCR-Details schließen', exact: true }).focus();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'OCR-Details anzeigen', exact: true })).toBeFocused();
});
