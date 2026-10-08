import { test, expect } from '@playwright/test';
test('integrated templates are visible and protected while a new lecture note is editable', async ({ page }) => {
  let payload;
  await page.route('**/api/notes', async route => {
    payload = route.request().postDataJSON();
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...payload, id: 'new-lecture-note', title: '' }) });
  });
  await page.route('**/__builtin-templates', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__builtin-templates');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/builtinTemplates.js')).mountBuiltinTemplates());
  const start = page.locator('.vk').filter({ hasText: 'Vorlesungsmitschrift' });
  const block = page.locator('.vk').filter({ hasText: 'Folie + Mitschrift' });
  await expect(block).toHaveCount(0);
  for (const card of [start]) {
    await expect(card).toBeVisible();
    await expect(card.getByText('Integriert', { exact: true })).toBeVisible();
    await expect(card.getByRole('button', { name: 'Löschen', exact: true })).toHaveCount(0);
    await expect(card.getByRole('button', { name: 'Bearbeiten', exact: true })).toHaveCount(0);
  }
  await expect(page.locator('.vk').filter({ hasText: 'Eigene Startnotiz' }).getByRole('button', { name: 'Löschen', exact: true })).toBeAttached();
  await start.click();
  await expect.poll(() => page.evaluate(() => window.openedTemplateNote)).toBe('new-lecture-note');
  expect(payload.body_json.attrs.lectureMode).toBe(true);
  expect(payload.body_json.content[0].type).toBe('paragraph');
  expect(payload.body_json.content[1].type).toBe('lectureSlide');
  expect(await page.evaluate(() => window.templateStore.templates[0].builtin)).toBe(true);
});
