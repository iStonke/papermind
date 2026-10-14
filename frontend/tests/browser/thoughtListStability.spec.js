import { expect, test } from '@playwright/test';

async function mountThoughts(page) {
  const rooms = Array.from({ length: 14 }, (_, index) => ({
    id: `room-${index}`, collection_id: 'collection', title: `Sammlung ${index + 1}`,
    content: index === 0 ? 'Erster Gedanke' : '', note_count: index === 0 ? 1 : 0,
    created_at: `2026-10-${String(14 - index).padStart(2, '0')}T12:00:00Z`, updated_at: '2026-10-14T12:00:00Z',
  }));
  let pin = { id: 'pin', room_id: 'room-0', text: 'Erster Gedanke', position_x: 24, position_y: 80, created_at: rooms[0].created_at, updated_at: rooms[0].updated_at };
  const pending = [];
  const releases = [];
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let data = { items: [] };
    if (request.method() === 'PATCH') {
      pending.push(path);
      await new Promise(resolve => releases.push(resolve));
      if (path === '/api/notes/pins/pin') {
        pin = { ...pin, text: request.postDataJSON().text, updated_at: '2026-10-14T12:05:00Z' };
        rooms[0].content = pin.text;
        data = pin;
      } else if (path === '/api/notes/pins/rooms/room-0') {
        Object.assign(rooms[0], request.postDataJSON());
        data = rooms[0];
      }
    } else if (path === '/api/notes/collections') data = { items: [{ id: 'collection', name: 'Arbeit' }] };
    else if (path === '/api/notes/pins/rooms') data = rooms;
    else if (path === '/api/notes/pins') data = { items: [pin] };
    else if (path === '/api/notes/pins/count') data = { count: 1 };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__thought-list', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="width:1200px;height:850px"></div></body></html>' }));
  await page.goto('/__thought-list');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/thoughtSummary.js')).mountThoughts());
  await expect(page.locator('.notes-ws__item')).toHaveCount(14);
  await expect(page.locator('article.thoughts-card')).toHaveCount(1);
  await page.evaluate(() => {
    window.originalRoomRows = [...document.querySelectorAll('[data-room-id]')];
    const list = document.querySelector('.thoughts-list');
    list.scrollTop = 200;
    window.originalRoomScrollTop = list.scrollTop;
  });
  return { pending, release: () => releases.shift()?.() };
}

async function expectStableList(page) {
  const items = page.locator('.notes-ws__item-select');
  await expect(items.first()).toBeDisabled();
  for (const item of await items.all()) await expect(item).toHaveCSS('opacity', '1');
  expect(await page.evaluate(() => window.originalRoomRows.every(row => row.isConnected))).toBe(true);
  expect(await page.locator('.thoughts-list').evaluate(el => el.scrollTop)).toBe(await page.evaluate(() => window.originalRoomScrollTop));
  await expect(page.locator('[data-room-id="room-0"]')).toHaveClass(/is-active/);
}

test('repeated autosaves keep every collection row visible without replacing the list', async ({ page }) => {
  const server = await mountThoughts(page);
  await page.locator('.thoughts-text').click();
  const editor = page.getByRole('textbox', { name: 'Gedanken bearbeiten' });
  for (let index = 1; index <= 2; index++) {
    await editor.fill(`Bearbeiteter Gedanke ${index}`);
    await expect.poll(() => server.pending.length).toBe(index);
    try { await expectStableList(page); } finally { server.release(); }
    await expect(page.locator('.notes-ws__item-select').first()).toBeEnabled();
    await expect(page.locator('[data-room-id="room-0"] .notes-ws__item-snippet')).toHaveText(`Bearbeiteter Gedanke ${index}`);
  }
});

test('renaming a collection keeps the list opaque, mounted and at the same scroll position', async ({ page }) => {
  const server = await mountThoughts(page);
  // Die erste Sammlung bleibt für die Bedienung sichtbar; den Scrollstand
  // anschließend erneut sichern, um den folgenden Refresh zu überprüfen.
  await page.locator('[data-room-id="room-0"]').hover();
  await page.evaluate(() => { window.originalRoomScrollTop = document.querySelector('.thoughts-list').scrollTop; });
  await page.locator('[data-room-id="room-0"]').getByRole('button', { name: 'Sammlung umbenennen' }).click();
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Umbenannte Sammlung');
  await page.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect.poll(() => server.pending.length).toBe(1);
  try { await expectStableList(page); } finally { server.release(); }
  await expect(page.locator('.notes-ws__item-select').first()).toBeEnabled();
  await expect(page.locator('[data-room-id="room-0"] .notes-ws__item-title')).toHaveText('Umbenannte Sammlung');
  expect(await page.evaluate(() => window.originalRoomRows.every(row => row.isConnected))).toBe(true);
});
