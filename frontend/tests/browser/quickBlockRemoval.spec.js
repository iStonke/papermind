import { expect, test } from '@playwright/test';

async function mountBlock(page, kind, readonly = false) {
  const deletes = [];
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    if (route.request().method() === 'DELETE') deletes.push(route.request().url());
    return route.fulfill({ contentType: 'application/json', body: '{"items":[]}' });
  });
  await page.route('**/__quick-block-removal', route => route.fulfill({
    contentType: 'text/html',
    body: '<html><body style="height:800px"><div id="app" class="papermind-app v-theme--light" style="width:1100px"></div></body></html>',
  }));
  await page.goto('/__quick-block-removal');
  await page.evaluate(async ({ kind, readonly }) => {
    if (kind === 'template') {
      (await import('/tests/browser/fixtures/templateFields.js')).mountTemplateFields({ readonly });
    } else {
      (await import('/tests/browser/fixtures/lectureRows.js')).mountLectureRows(null, { readonly });
    }
  }, { kind, readonly });
  await expect(page.locator(kind === 'template' ? '.pm-template' : '.pm-lecture-slide')).toHaveCount(1);
  return deletes;
}

test('template block removal is subtle, keyboard accessible, undoable and leaves a writable note', async ({ page }) => {
  const deletes = await mountBlock(page, 'template');
  const block = page.locator('.pm-template');
  const remove = block.getByRole('button', { name: 'Schnellblock entfernen', exact: true });
  await block.locator('.pm-tf__value').first().click({ position: { x: 80, y: 12 } });
  await page.keyboard.type('Wichtiger Inhalt');
  await page.locator('body').click({ position: { x: 1200, y: 600 } });
  await expect.poll(() => block.locator('.pm-template__tools').evaluate(element => getComputedStyle(element).opacity)).toBe('0');
  await remove.focus();
  await expect(remove).toBeFocused();
  await expect.poll(() => block.locator('.pm-template__tools').evaluate(element => getComputedStyle(element).opacity)).toBe('1');
  await page.keyboard.press('Enter');
  await expect(block).toHaveCount(0);
  await expect(page.locator('.tiptap')).toBeFocused();
  await expect(page.locator('.tiptap > p')).toHaveCount(1);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(block).toHaveCount(1);
  await expect(block.locator('.pm-tf__value').first()).toContainText('Wichtiger Inhalt');
  await block.hover();
  await remove.click();
  await expect(block).toHaveCount(0);
  await expect(page.locator('.tiptap')).toBeFocused();
  await page.keyboard.type('Weiter schreiben');
  await expect(page.locator('.tiptap > p')).toHaveText('Weiter schreiben');
  expect(deletes).toEqual([]);
});

test('first and last Mitschrift sections can be removed and restored with their text', async ({ page }) => {
  await mountBlock(page, 'lecture');
  const rows = page.locator('.pm-lecture-slide');
  await rows.first().locator('.pm-lecture-slide__notes p').click();
  await page.keyboard.type('Erster Abschnitt');
  await rows.first().hover();
  await rows.first().getByRole('button', { name: 'Abschnitt entfernen', exact: true }).click();
  await expect(rows).toHaveCount(0);
  await expect(page.locator('.tiptap')).toBeFocused();
  await expect(page.locator('.tiptap > p')).toHaveCount(1);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(rows).toHaveCount(1);
  await expect(rows.first().locator('.pm-lecture-slide__notes')).toHaveText('Erster Abschnitt');
  await page.getByRole('button', { name: 'Abschnitt hinzufügen', exact: true }).click();
  await expect(rows).toHaveCount(2);
  await expect(page.locator('.tiptap')).toBeFocused();
  await page.keyboard.type('Zweiter Abschnitt');
  await rows.first().hover();
  await rows.first().getByRole('button', { name: 'Abschnitt entfernen', exact: true }).click();
  await expect(rows).toHaveCount(1);
  await expect(rows.first().locator('.pm-lecture-slide__meta')).toContainText('Abschnitt 1');
  await expect(rows.first().locator('.pm-lecture-slide__notes')).toHaveText('Zweiter Abschnitt');
  await expect(page.locator('.tiptap')).toBeFocused();
  await page.keyboard.press('ControlOrMeta+z');
  await expect(rows).toHaveCount(2);
  await expect(rows.first().locator('.pm-lecture-slide__notes')).toHaveText('Erster Abschnitt');
  await expect(rows.nth(1).locator('.pm-lecture-slide__notes')).toHaveText('Zweiter Abschnitt');
});

for (const kind of ['template', 'lecture']) {
  test(`${kind} block previews have no removal action`, async ({ page }) => {
    await mountBlock(page, kind, true);
    await expect(page.getByRole('button', { name: /(?:Schnellblock|Abschnitt) entfernen/ })).toHaveCount(0);
  });
}
