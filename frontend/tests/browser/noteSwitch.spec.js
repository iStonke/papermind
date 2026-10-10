import { test, expect } from '@playwright/test';

const IMAGE_SRC = '/api/notes/11111111-1111-1111-1111-111111111111/images/22222222-2222-2222-2222-222222222222/file';
const slide = (text, image = false) => ({
  type: 'lectureSlide',
  attrs: { capturedAt: '2026-10-09T11:07:00Z' },
  content: [
    { type: 'lectureSlideMedia', content: image ? [{ type: 'image', attrs: { src: IMAGE_SRC, alt: 'Folie' } }] : [] },
    { type: 'lectureSlideNotes', content: [text ? { type: 'paragraph', content: [{ type: 'text', text }] } : { type: 'paragraph' }] },
  ],
});
const notes = {
  'lecture-note': { title: '', body_json: { type: 'doc', attrs: { lectureMode: true }, content: [
    { type: 'templateBox', attrs: { variant: 'note', color: 'rose', title: 'Vorlesung' }, content: [{ type: 'templateField', attrs: { label: 'Titel', hint: 'Meetingbezeichnung' } }] },
    slide('Rotation um den Ursprung', true), slide('Homogene Koordinaten'), slide(''),
  ] } },
  'empty-note': { title: '', body_json: { type: 'doc', content: [{ type: 'paragraph' }] } },
  'plain-note': { title: 'Fakten', body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'pflichtversichert' }] }] } },
};

async function mount(page) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    if (url.pathname.endsWith('/file')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="9"/>' });
    const id = url.pathname.split('/').pop();
    const data = notes[id] ? { id, revision: 1, title_is_generated: false, collection_id: null, tags: [], ...notes[id] } : url.pathname === '/api/settings' ? {} : { items: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__switch', (route) => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="height:800px"></div></body></html>' }));
  await page.goto('/__switch');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/noteSwitch.js')).mountSwitch());
  await expect(page.locator('.pm-lecture-slide')).toHaveCount(3);
  return errors;
}

for (const [target, expected] of [['empty-note', ''], ['plain-note', 'Fakten']]) {
  test(`switching from a lecture note to ${target} replaces the editor content`, async ({ page }) => {
    const errors = await mount(page);
    await page.evaluate((id) => window.switchNote(id), target);
    await expect(page.getByRole('textbox', { name: 'Titel der Notiz', exact: true })).toHaveValue(expected);
    await expect(page.locator('.pm-lecture-slide')).toHaveCount(0);
    // Zurück zur Vorlesung und wieder weg: Folien-Kopfzeilen dürfen keinen Wechsel abbrechen.
    await page.evaluate(() => window.switchNote('lecture-note'));
    await expect(page.locator('.pm-lecture-slide')).toHaveCount(3);
    await page.evaluate((id) => window.switchNote(id), target);
    await expect(page.locator('.pm-lecture-slide')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}
