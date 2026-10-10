import { expect, test } from '@playwright/test';
test('lecture rows keep timestamps, accept clipboard screenshots and add/remove rows', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const body = url.pathname.endsWith('/images') ? {
      id: 'image-test', note_id: 'lecture-note', filename: 'Screenshot.png',
      src: '/api/notes/lecture-note/images/image-test', width: 400, height: 240,
    } : { items: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/__lecture-rows', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="width:1100px"></div></body></html>' }));
  await page.goto('/__lecture-rows');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/lectureRows.js')).mountLectureRows());
  const rows = page.locator('.pm-lecture-slide');
  await expect(rows).toHaveCount(1);
  await rows.first().hover();
  await expect(rows.first().getByRole('button', { name: 'Zeile entfernen', exact: true })).toHaveCount(0);
  const notes = rows.first().locator('.pm-lecture-slide__notes p').first();
  await notes.click();
  await page.keyboard.type('Meine erste Mitschrift');
  await expect(rows.first().locator('time')).toBeVisible();
  const timestamp = await rows.first().locator('time').getAttribute('datetime');
  await page.keyboard.type(' mit Ergänzung');
  expect(await rows.first().locator('time').getAttribute('datetime')).toBe(timestamp);
  const drop = rows.first().locator('.pm-lecture-slide__drop');
  await drop.click();
  await expect(drop).toBeFocused();
  await expect(drop).toHaveClass(/is-active/);
  await notes.click();
  await expect(drop).not.toHaveClass(/is-active/);
  await drop.click();
  await expect(drop).toHaveClass(/is-active/);
  await drop.evaluate(el => {
    const clipboardData = new DataTransfer();
    clipboardData.items.add(new File(['image'], 'Screenshot.png', { type: 'image/png' }));
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData, bubbles: true, cancelable: true }));
  });
  await expect(rows.first().locator('.pm-note-image')).toBeVisible();
  await expect(rows.first().locator('.pm-lecture-slide__meta time')).toHaveText(/· \d{2}:\d{2}/);
  await expect(rows.first().locator('.pm-lecture-slide__meta')).toContainText('Folie 1');
  await expect(rows.first().locator('.pm-note-image__caption')).toHaveCount(0);
  await expect(rows.first().getByRole('textbox', { name: 'Bildunterschrift' })).toHaveCount(0);
  expect(await page.evaluate(() => window.lectureBody.content[0].content[1].content[0].content[0].text)).toContain('Meine erste Mitschrift');
  await page.evaluate(() => {
    window.rowAnimations = [];
    const animate = Element.prototype.animate;
    Element.prototype.animate = function (frames, options) {
      if (this.matches('.pm-lecture-slide')) window.rowAnimations.push({ frames, duration: options.duration });
      return animate.call(this, frames, options);
    };
  });
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Screenshot & Mitschrift hinzufügen', exact: true }).last().click();
  expect(await page.evaluate(() => window.rowAnimations.length)).toBe(3);
  expect(await page.evaluate(() => window.rowAnimations[0].duration)).toBe(240);
  await expect(rows).toHaveCount(4);
  await expect(rows.first().getByRole('button', { name: 'Zeile entfernen', exact: true })).toHaveCount(0);
  await expect(rows.last().locator('time')).toHaveCount(0);
  const divider = await rows.nth(1).evaluate(el => getComputedStyle(el).borderTopWidth);
  expect(divider).toBe('1px');
  await rows.nth(1).getByRole('button', { name: 'Zeile entfernen', exact: true }).click();
  await expect(rows).toHaveCount(3);
  expect(await rows.first().locator('time').getAttribute('datetime')).toBe(timestamp);
  await rows.first().getByRole('button', { name: 'Inhalt oberhalb einfügen', exact: true }).click();
  await page.keyboard.type('Einleitung vor der ersten Folie');
  expect(await page.evaluate(() => window.lectureBody.content[0].type)).toBe('paragraph');
  expect(await page.evaluate(() => window.lectureBody.content[0].content[0].text)).toBe('Einleitung vor der ersten Folie');
  await expect(rows.first().getByRole('button', { name: 'Inhalt oberhalb einfügen', exact: true })).toHaveCount(0);
  await expect(rows.first().getByRole('button', { name: 'Zeile entfernen', exact: true })).toHaveCount(0);
});
