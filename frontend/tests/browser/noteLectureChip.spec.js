import { test, expect } from '@playwright/test';

async function mountNote(page, bodyJson) {
  const note = { id: 'title-note', title: 'Computergrafik – Vorlesung 3', title_is_generated: false, revision: 1, collection_id: null, tags: [], body_json: bodyJson };
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const data = url.pathname === '/api/notes/title-note' ? note : url.pathname === '/api/settings' ? {} : { items: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__note-title', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__note-title');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/noteTitle.js')).mountTitleEditor());
  const title = page.getByRole('textbox', { name: 'Titel der Notiz', exact: true });
  await expect(title).toHaveValue('Computergrafik – Vorlesung 3');
  return title;
}

const lectureSlide = {
  type: 'lectureSlide',
  content: [
    { type: 'lectureSlideMedia', content: [] },
    { type: 'lectureSlideNotes', content: [{ type: 'paragraph' }] },
  ],
};

test('lecture notes show a Vorlesung chip directly beside the title', async ({ page }) => {
  const title = await mountNote(page, { type: 'doc', attrs: { lectureMode: true }, content: [lectureSlide] });
  const chip = page.locator('.note-workspace-editor__kind-chip');
  await expect(chip).toHaveText('Vorlesung');
  const [titleBox, chipBox] = await Promise.all([title.boundingBox(), chip.boundingBox()]);
  // Direkt hinter dem Titeltext, nicht am rechten Rand der Kopfzeile.
  expect(chipBox.x - (titleBox.x + titleBox.width)).toBeGreaterThanOrEqual(0);
  expect(chipBox.x - (titleBox.x + titleBox.width)).toBeLessThanOrEqual(8);
  expect(Math.abs((chipBox.y + chipBox.height / 2) - (titleBox.y + titleBox.height / 2))).toBeLessThan(2);
});

test('lecture slides alone mark a note as Vorlesung', async ({ page }) => {
  await mountNote(page, { type: 'doc', content: [lectureSlide] });
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveText('Vorlesung');
});

test('plain notes have no Vorlesung chip', async ({ page }) => {
  await mountNote(page, { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Einkaufsliste' }] }] });
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
});
