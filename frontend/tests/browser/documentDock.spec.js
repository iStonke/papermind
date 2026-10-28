import { test, expect } from '@playwright/test';
async function mountDock(page) {
  await page.setViewportSize({ width: 1280, height: 950 });
  await page.route('**/__document-dock', route => route.fulfill({ contentType: 'text/html', body: '<html><body style="margin:0"><div id="app"></div></body></html>' }));
  await page.goto('/__document-dock');
  await page.evaluate(async () => { const { mount } = await import('/tests/browser/fixtures/documentDock.js'); mount(); });
}
test('dock unfolds, keeps field nodes and edits, and returns focus when collapsed', async ({ page }) => {
  await mountDock(page);
  const drawer = page.locator('.preview-layout__drawer');
  const toggle = page.getByRole('button', { name: 'Dokumentdetails umschalten' });
  const collapsedWidth = await drawer.evaluate(el => el.getBoundingClientRect().width);
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect.poll(() => drawer.evaluate(el => el.getBoundingClientRect().width)).toBeGreaterThan(collapsedWidth + 30);
  const name = page.getByLabel('Dokumentname', { exact: true });
  await name.fill('Bearbeiteter Titel');
  await name.evaluate(el => { window.originalNameInput = el; });
  await page.evaluate(() => { window.dock.open = false; });
  await expect(toggle).toBeFocused();
  await expect(drawer).toHaveCSS('height', '72px');
  await toggle.click();
  await expect(name).toHaveValue('Bearbeiteter Titel');
  expect(await name.evaluate(el => el === window.originalNameInput)).toBe(true);
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; window.dock.title = 'Ein anderes Dokument'; });
  await expect(page.locator('.details-drawer__subtitle')).toHaveText('Ein anderes Dokument');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await expect.poll(() => page.locator('.preview-layout__content').evaluate(el => el.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  await page.evaluate(() => { window.dock.title = 'Teilnahmebestätigung · Gestaltungsseminar'; window.dock.form.name = window.dock.title; });
  await expect.poll(() => page.locator('.preview-layout__content').evaluate(el => el.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  await page.screenshot({ path: '/tmp/papermind-document-dock-dark.png' });
});
test('rapid reversals settle, resizing keeps the header accessible and scrolling cue follows content', async ({ page }) => {
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; });
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await page.evaluate(async () => {
    for (let i = 0; i < 5; i++) { window.dock.open = !window.dock.open; await new Promise(resolve => setTimeout(resolve, 35)); }
    window.dock.open = true; window.dock.width = 390; window.dock.height = 480;
  });
  const drawer = page.locator('.preview-layout__drawer');
  await expect.poll(() => drawer.evaluate(el => el.getBoundingClientRect().height)).toBeLessThanOrEqual(323);
  await expect(page.getByRole('button', { name: 'Dokumentdetails umschalten' })).toBeVisible();
  await expect(page.locator('.preview-layout__scroll-cue')).toHaveCSS('opacity', '1');
  await page.locator('.preview-layout__body').evaluate(el => { el.scrollTop = el.scrollHeight; });
  await expect(page.locator('.preview-layout__scroll-cue')).toHaveCSS('opacity', '0');
  await page.evaluate(() => { window.dock.theme = 'light'; window.dock.width = 850; window.dock.height = 720; });
  await page.locator('.preview-layout__body').evaluate(el => { el.scrollTop = 0; });
  await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().width))).toBe(760);
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await expect(drawer).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.screenshot({ path: '/tmp/papermind-document-dock-light.png' });
});
test('save confirmation respects errors and document switches', async ({ page }) => {
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; window.dock.saving = true; });
  await expect(page.getByRole('status')).toHaveText('Wird gespeichert …');
  await page.evaluate(() => { window.dock.saving = false; });
  await expect(page.getByRole('status')).toHaveText('Gespeichert');
  await page.evaluate(() => { window.dock.saving = true; });
  await page.evaluate(() => { window.dock.error = true; window.dock.saving = false; });
  await expect(page.getByRole('status')).toBeEmpty();
  await page.evaluate(() => { window.dock.error = false; window.dock.saving = true; });
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; window.dock.saving = false; });
  await expect(page.getByRole('status')).toBeEmpty();
});


test('reduced motion also disables the document content swap', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; });
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; });
  await expect(page.locator('.preview-layout__drawer')).toHaveCSS('transition-duration', '0s');
  expect(await page.locator('.preview-layout__content').evaluate(el => el.getAnimations().length)).toBe(0);
});
