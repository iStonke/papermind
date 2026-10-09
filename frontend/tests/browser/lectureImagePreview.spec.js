import { expect, test } from '@playwright/test';

test('lecture screenshot opens centered standard dialog and closes with Escape, close button and backdrop', async ({ page }) => {
  await page.route('**/api/**', route => {
    if (!new URL(route.request().url()).pathname.startsWith('/api/')) return route.continue();
    if (new URL(route.request().url()).pathname.endsWith('/file')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720"><rect width="1200" height="720" fill="teal"/></svg>' });
    return route.fulfill({ contentType: 'application/json', body: '{"items":[]}' });
  });
  await page.route('**/__lecture-preview', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="width:1100px"></div></body></html>' }));
  await page.goto('/__lecture-preview');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/lectureRows.js')).mountLectureRows({ src: '/api/notes/11111111-1111-1111-1111-111111111111/images/22222222-2222-2222-2222-222222222222/file', alt: 'Testfolie' }));
  const screenshot = page.getByRole('button', { name: 'Screenshot vergrößern' });
  await expect.poll(() => screenshot.evaluate(img => img.complete && img.naturalWidth > 0)).toBe(true);
  const before = await page.evaluate(() => JSON.stringify(window.lectureBody));
  await screenshot.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.pm-dialog__subtitle')).toHaveText(/Folie 1 · \d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}/);
  await expect(page.locator('.pm-lecture-slide__meta time')).toHaveText(/· \d{2}\.\d{2}\.\d{4} · \d{2}:\d{2}/);
  await expect(page.locator('.pm-lecture-slide .pm-note-image__tools')).toHaveCount(0);
  await expect(page.locator('.pm-lecture-slide .pm-note-image__resize')).toHaveCount(0);
  const image = dialog.locator('.pm-note-image__preview');
  await expect(image).toBeVisible();
  const box = await image.boundingBox();
  const viewport = page.viewportSize();
  expect(Math.abs(box.x + box.width / 2 - viewport.width / 2)).toBeLessThan(3);
  for (const size of [{ width: 1280, height: 720 }, { width: 800, height: 400 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size);
    await expect.poll(() => dialog.locator('.pm-screenshot-dialog').evaluate(card => {
      const elements = [card, card.querySelector('.pm-dialog__content-wrap'), card.querySelector('.pm-dialog__content')];
      return elements.every(el => el.scrollHeight <= el.clientHeight + 1 && el.scrollWidth <= el.clientWidth + 1);
    })).toBe(true);
    const bounds = await image.boundingBox();
    expect(bounds.y).toBeGreaterThanOrEqual(0);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(size.height);
  }
  await page.setViewportSize(viewport);
  await expect(page.locator('.v-overlay--active .v-overlay__scrim')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await screenshot.focus();
  await page.keyboard.press('Enter');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Dialog schließen' }).click();
  await expect(dialog).toBeHidden();
  await screenshot.click();
  await expect(dialog).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(dialog).toBeHidden();
  expect(await page.evaluate(() => JSON.stringify(window.lectureBody))).toBe(before);
});
