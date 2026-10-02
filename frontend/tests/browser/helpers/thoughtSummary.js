import { expect } from '@playwright/test';

export async function openThoughts(page, colors = [null, null]) {
  const created = [];
  const timestamp = '2026-10-01T12:00:00Z';
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    let body;
    if (url.pathname === '/api/notes/collections') body = { items: [{ id: 'collection', name: 'Arbeit', note_count: 0 }] };
    else if (url.pathname === '/api/notes/pins/rooms') body = [{ id: 'room', collection_id: 'collection', title: 'Projektideen', content: 'Idee eins Idee zwei', created_at: timestamp, updated_at: timestamp }];
    else if (url.pathname === '/api/notes/pins') body = { items: colors.map((color, index) => ({ id: `pin-${index + 1}`, room_id: 'room', text: `Idee ${index + 1}`, title_color: color, position_x: 24 + (index % 2) * 300, position_y: 80 + Math.floor(index / 2) * 240, created_at: timestamp, updated_at: timestamp })) };
    else if (url.pathname === '/api/notes/pins/rooms/room/summary') body = { title: 'Generierter Titel', content: '## Überblick\n\nZusammengefasste Ideen.' };
    else if (url.pathname === '/api/notes' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON();
      created.push(payload);
      body = { ...payload, id: 'new-note', created_at: timestamp, updated_at: timestamp };
    } else body = { count: 2, items: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/__thought-summary', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="width:1200px;height:850px"></div></body></html>' }));
  await page.goto('/__thought-summary');
  await page.evaluate(async () => { const { mountThoughts } = await import('/tests/browser/fixtures/thoughtSummary.js'); mountThoughts(); });
  await expect(page.getByRole('button', { name: 'Alle Gedanken zusammenfassen', exact: true })).toBeEnabled();
  return created;
}

