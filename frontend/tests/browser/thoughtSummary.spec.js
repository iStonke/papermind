import { expect, test } from '@playwright/test';
import { openThoughts } from './helpers/thoughtSummary.js';

test('preview can be cancelled without creating a note', async ({ page }) => {
  const created = await openThoughts(page);
  await page.getByRole('button', { name: 'Alle Gedanken zusammenfassen', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Titel der neuen Notiz' })).toHaveValue('Generierter Titel');
  expect(created).toHaveLength(0);
  await page.getByRole('button', { name: 'Zurück', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(created).toHaveLength(0);
  await expect(page.locator('article.thoughts-card')).toHaveCount(2);
});

test('explicit transfer uses edited title and content and opens the new note', async ({ page }) => {
  const created = await openThoughts(page);
  await page.getByRole('button', { name: 'Alle Gedanken zusammenfassen', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Titel der neuen Notiz' })).toHaveValue('Generierter Titel');
  expect(created).toHaveLength(0);
  await page.getByRole('textbox', { name: 'Titel der neuen Notiz' }).fill('Mein bearbeiteter Titel');
  await page.getByRole('textbox', { name: 'Zusammenfassung', exact: true }).fill('## Nächste Schritte\n\n- Mein ergänzter Gedanke');
  await page.getByRole('button', { name: 'Als Notiz übernehmen', exact: true }).click();
  await expect.poll(() => created.length).toBe(1);
  expect(created[0].title).toBe('Mein bearbeiteter Titel');
  expect(created[0].collection_id).toBe('collection');
  expect(created[0].body_json).toMatchObject({ type: 'doc', content: expect.any(Array) });
  expect(created[0].body_json.content.map(node => node.type)).toEqual(['heading', 'bulletList']);
  expect(JSON.stringify(created[0].body_json)).toContain('Mein ergänzter Gedanke');
  expect(JSON.stringify(created[0].body_json)).toContain('bulletList');
  await expect.poll(() => page.evaluate(() => window.openedNote)).toBe('new-note');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
