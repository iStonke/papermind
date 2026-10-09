import { test, expect } from '@playwright/test';
test('first empty template field accepts clicks and typing', async ({ page }) => {
  await page.route('**/api/**', route => new URL(route.request().url()).pathname.startsWith('/api/') ? route.fulfill({ contentType: 'application/json', body: '{"items":[]}' }) : route.continue());
  await page.route('**/__template-fields', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__template-fields');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/templateFields.js')).mountTemplateFields());
  const field = page.locator('.pm-tf__value').first();
  await page.locator('.pm-tf__value').nth(1).click();
  await field.click({ position: { x: 80, y: 12 } });
  await expect(page.locator('.pm-tf').first()).toHaveClass(/is-focused-empty/);
  expect(await field.evaluate(el => getComputedStyle(el, '::after').borderLeftWidth)).toBe('2px');
  await expect.poll(() => field.evaluate(el => {
    const selection = window.getSelection();
    return document.activeElement?.classList.contains('ProseMirror')
      && selection?.isCollapsed && el.querySelector('.pm-tf__content').contains(selection.anchorNode);
  })).toBe(true);
  await page.keyboard.type('Meine Vorlesung');
  await expect(field).toContainText('Meine Vorlesung');
  await expect(page.locator('.pm-tf').first()).not.toHaveClass(/is-focused-empty/);
  expect(await page.evaluate(() => window.lectureBody.content[0].content[0].content[0].text)).toBe('Meine Vorlesung');
  await page.reload();
  await page.evaluate(async () => (await import('/tests/browser/fixtures/templateFields.js')).mountTemplateFields());
  await field.click({ position: { x: 250, y: 12 } });
  await expect.poll(() => field.evaluate(el => el.querySelector('.pm-tf__content').contains(window.getSelection()?.anchorNode))).toBe(true);
  await page.keyboard.type('Direkter Einstieg');
  await expect(field).toContainText('Direkter Einstieg');
});
