import { expect, test } from '@playwright/test';
async function mount(page, options = {}) {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.route('**/__live-review', r => r.fulfill({ contentType: 'text/html', body: '<div id="app" class="papermind-app v-theme--light"></div>' }));
  await page.goto('/__live-review');
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await page.evaluate(async options => { const { mountLiveReview } = await import('/tests/browser/fixtures/noteLiveReview.js'); mountLiveReview(options); }, options);
  await page.evaluate(() => window.liveCalls[0].finish());
  await expect(page.locator('.pm-review-card')).toHaveCount(options.invalidAnchor ? 0 : 1);
}

test('typing updates live hints without replacing cards or stealing the cursor; pause and full check work', async ({ page }) => {
  await mount(page);
  await page.locator('.tiptap p').last().click();
  await page.keyboard.press('End');
  await page.keyboard.type(' und mehr');
  const caret = await page.evaluate(() => window.liveReview.editor.state.selection.from);
  await page.clock.fastForward(14999);
  expect(await page.evaluate(() => window.liveCalls.length)).toBe(1);
  await page.clock.fastForward(1);
  expect(await page.evaluate(() => window.liveCalls.length)).toBe(2);
  await expect(page.locator('.pm-review-card[data-review-id="1"]')).toBeVisible();
  await expect(page.locator('.pm-review-panel__rubric')).toHaveText('WIRD LOKAL GEPRÜFT');
  await page.evaluate(() => window.liveCalls[1].finish());
  await expect(page.locator('.pm-review-card[data-review-id="1"]')).toBeVisible();
  expect(await page.evaluate(() => window.liveReview.editor.state.selection.from)).toBe(caret);
  expect(await page.evaluate(() => window.liveReview.editor.isFocused)).toBe(true);
  await page.getByTitle('Automatische Prüfung pausieren').click();
  await page.locator('.tiptap p').last().click();
  await page.keyboard.type(' weiter');
  await page.clock.fastForward(2000);
  expect(await page.evaluate(() => window.liveCalls.length)).toBe(2);
  await page.getByTitle('Automatische Prüfung fortsetzen').click();
  await page.clock.fastForward(15000);
  expect(await page.evaluate(() => window.liveCalls.length)).toBe(3);
  await page.evaluate(() => window.liveCalls[2].finish());
  await expect(page.getByRole('button', { name: 'Gesamte Notiz prüfen' })).toBeEnabled();
  await page.getByRole('button', { name: 'Gesamte Notiz prüfen' }).click();
  expect(await page.evaluate(() => window.liveCalls[3].payload.mode)).toBe('full');
  await page.evaluate(() => window.liveCalls[3].finish());
  await expect(page.locator('.pm-review-card[data-review-id="1"]')).toBeVisible();
});

test('click shows the replacement; ignored hints stay hidden and accepting supports undo', async ({ page }) => {
  await mount(page);
  await page.locator('.pm-review-card[data-review-id="1"]').click();
  await page.clock.runFor(500);
  await expect(page.locator('.pm-review-preview')).toContainText('Ergebnis');
  await page.getByRole('button', { name: 'Ablehnen', exact: true }).click();
  await expect(page.locator('.pm-review-card')).toHaveCount(0);
  await page.evaluate(() => window.liveReview.editor.commands.insertContentAt(1, 'Heute: '));
  await page.clock.fastForward(15000);
  expect(await page.evaluate(() => window.liveCalls.length)).toBe(2);
  await page.evaluate(() => window.liveCalls[1].finish());
  await expect(page.locator('.pm-review-card')).toHaveCount(0);
  await page.evaluate(() => window.liveReview.c.reopenChange(1));
  await page.locator('.pm-review-card[data-review-id="1"]').click();
  await page.clock.runFor(500);
  await page.getByRole('button', { name: 'Annehmen', exact: true }).click();
  await expect(page.locator('.tiptap')).toContainText('Heute: Das Ergebnis steht fest.');
  await page.evaluate(() => window.liveReview.editor.commands.undo());
  await expect(page.locator('.tiptap')).toContainText('Heute: Das Ergebniss steht fest.');
  await page.getByRole('button', { name: 'Schließen', exact: true }).click();
  expect(await page.evaluate(() => window.liveReview.c.review.pending)).toBe(false);
});

test('the live panel fits in the correction margin', async ({ page }) => {
  await mount(page);
  await page.locator('.pm-review-card[data-review-id="1"]').click();
  expect(await page.locator('.pm-review-panel').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  const body = page.locator('.pm-review-panel__body');
  expect(await body.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: '/private/tmp/papermind-live-review.png' });
});

test('an invented anchor is skipped and the next live check remains available', async ({ page }) => {
  await mount(page, { invalidAnchor: true });
  await expect(page.getByText('Ein unsicherer KI-Hinweis wurde ausgelassen. Du kannst weiterschreiben.')).toBeVisible();
  await expect(page.locator('.pm-review-panel__rubric')).toHaveText('LOKAL GEPRÜFT · 0');
  await expect(page.getByRole('button', { name: 'Erneut prüfen' })).toHaveCount(0);
  const before = await page.evaluate(() => window.liveReview.editor.getText());
  await page.evaluate(() => {
    window.invalidLiveAnchor = false;
    window.liveReview.editor.commands.insertContentAt(window.liveReview.editor.state.doc.content.size - 1, ' Weiter');
  });
  await page.clock.fastForward(15000);
  await page.evaluate(() => window.liveCalls[1].finish());
  await expect(page.locator('.pm-review-card')).toHaveCount(1);
  await expect(page.getByText('Ein unsicherer KI-Hinweis wurde ausgelassen. Du kannst weiterschreiben.')).toHaveCount(0);
  expect(await page.evaluate(() => window.liveReview.editor.getText())).toBe(before + ' Weiter');
});
