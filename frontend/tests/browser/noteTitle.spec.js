import { test, expect } from '@playwright/test';

test('local title is automatically saved in italics and becomes manual when edited', async ({ page }) => {
  let requests = 0;
  const note = { id: 'title-note', title: '', title_is_generated: false, revision: 1, collection_id: null, tags: [], body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Inhalt über lokale Lernmethoden. '.repeat(30) }] }] } };
  await page.route('**/api/**', async route => {
    const req = route.request();
    const url = new URL(req.url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    let data = { items: [] };
    if (url.pathname === '/api/notes/title-note/suggest-title') {
      requests++;
      data = { title: 'Lokale Lernmethoden im Überblick', base_revision: note.revision };
    } else if (url.pathname === '/api/notes/title-note') {
      if (req.method() === 'PATCH') { Object.assign(note, req.postDataJSON()); note.revision++; }
      data = note;
    } else if (url.pathname === '/api/settings') data = {};
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__note-title', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__note-title');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/noteTitle.js')).mountTitleEditor());
  const title = page.getByRole('textbox', { name: 'Titel der Notiz', exact: true });
  await expect(title).toBeEnabled();
  await expect(title).toHaveValue('Lokale Lernmethoden im Überblick', { timeout: 16000 });
  await expect(title).toHaveClass(/is-generated/);
  await expect.poll(() => note.title_is_generated).toBe(true);
  await title.fill('Mein eigener Titel');
  await expect(title).not.toHaveClass(/is-generated/);
  await expect.poll(() => note.title).toBe('Mein eigener Titel');
  expect(note.title_is_generated).toBe(false);
  expect(requests).toBe(1);
});
