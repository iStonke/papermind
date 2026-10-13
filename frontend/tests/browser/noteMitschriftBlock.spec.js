import { expect, test } from '@playwright/test';

async function mountNote(page, bodyJson) {
  const note = {
    id: 'title-note', title: 'Mitschrift-Test', revision: 1,
    title_is_generated: false, collection_id: null, tags: [], body_json: bodyJson,
  };
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let data = { items: [] };
    if (path === '/api/notes/title-note') {
      if (request.method() === 'PATCH') {
        Object.assign(note, request.postDataJSON());
        note.revision++;
      }
      data = note;
    } else if (path === '/api/settings') data = {};
    else if (path.endsWith('/images') && request.method() === 'POST') {
      data = { id: 'note-image', note_id: 'title-note', filename: 'Bild.png', src: '/api/test-image/file', width: 400, height: 240 };
    } else if (path.endsWith('/file')) {
      return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240"><rect width="400" height="240" fill="#5b6f86"/></svg>' });
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__note-title', route => route.fulfill({
    contentType: 'text/html',
    body: '<html><body><div id="app" class="papermind-app v-theme--light" style="height:900px"></div></body></html>',
  }));
  const open = async () => {
    await page.goto('/__note-title');
    await page.evaluate(async () => (await import('/tests/browser/fixtures/noteTitle.js')).mountTitleEditor());
    await expect(page.getByRole('textbox', { name: 'Titel der Notiz', exact: true })).toHaveValue('Mitschrift-Test');
  };
  await open();
  return { note, open };
}

async function chooseLayout(page, name) {
  await page.getByRole('button', { name: /^Mitschrift, Ansicht:/ }).click();
  await page.getByRole('menuitemradio', { name, exact: true }).click();
  await expect(page.getByRole('menu', { name: 'Ansicht der Mitschrift', exact: true })).toBeHidden();
}

test('Mitschrift is insertable from Blocks and its numbered text sections survive reloading', async ({ page }) => {
  const { note, open } = await mountNote(page, {
    type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Einleitung' }] }],
  });
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
  await page.locator('.tiptap > p').first().click();
  await page.getByRole('button', { name: 'Blöcke', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Mitschrift', exact: true }).click();
  const rows = page.locator('.pm-lecture-slide');
  await expect(rows).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Nur Text' })).toBeVisible();
  await expect(rows.first().locator('.pm-lecture-slide__media')).toBeHidden();
  await expect(page.locator('.tiptap')).toBeFocused();
  await page.keyboard.type('Hier steht Text …');
  await expect(rows.first().locator('time')).toBeVisible();
  const timestamp = await rows.first().locator('time').getAttribute('datetime');
  await chooseLayout(page, 'Bild neben Text');
  await expect(rows.first().locator('.pm-lecture-slide__media')).toBeVisible();
  await chooseLayout(page, 'Bild über Text');
  await expect(rows.first().locator('.pm-lecture-slide__media')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Bild über Text' })).toBeVisible();
  await chooseLayout(page, 'Nur Text');
  await expect(rows.first().locator('.pm-lecture-slide__media')).toBeHidden();
  await page.getByRole('button', { name: 'Abschnitt hinzufügen', exact: true }).click();
  await expect(rows).toHaveCount(2);
  await expect(page.locator('.tiptap')).toBeFocused();
  await page.keyboard.type('Hier steht ein langer Text …');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1).locator('.pm-lecture-slide__meta')).toContainText('Abschnitt 2');
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Nur Text' })).toBeVisible();
  await expect.poll(() => note.body_json.content.filter(node => node.type === 'lectureSlide').length).toBe(2);
  await expect.poll(() => JSON.stringify(note.body_json)).toContain('Hier steht ein langer Text …');
  expect(note.body_json.content[0].content[0].text).toBe('Einleitung');
  expect(note.body_json.attrs).toMatchObject({ lectureLayout: 'text', lectureMode: false });

  await open();
  await expect(rows).toHaveCount(2);
  await expect(rows.first().locator('.pm-lecture-slide__notes')).toHaveText('Hier steht Text …');
  await expect(rows.nth(1).locator('.pm-lecture-slide__notes')).toHaveText('Hier steht ein langer Text …');
  expect(await rows.first().locator('time').getAttribute('datetime')).toBe(timestamp);
  for (const row of await rows.all()) await expect(row.locator('.pm-lecture-slide__media')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Abschnitt hinzufügen', exact: true })).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Nur Text' })).toBeVisible();
  await chooseLayout(page, 'Bild neben Text');
  for (const row of await rows.all()) await expect(row.locator('.pm-lecture-slide__media')).toBeVisible();
  await expect.poll(() => note.body_json.attrs).toMatchObject({ lectureLayout: 'side', lectureMode: true });
  await open();
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Bild neben Text' })).toBeVisible();
  for (const row of await rows.all()) await expect(row.locator('.pm-lecture-slide__media')).toBeVisible();
});

test('new Mitschrift blocks inherit the lecture view and follow the header view switch', async ({ page }) => {
  const { note } = await mountNote(page, {
    type: 'doc', attrs: { lectureMode: true, lectureLayout: 'side' }, content: [{
      type: 'lectureSlide', content: [
        { type: 'lectureSlideMedia', content: [] },
        { type: 'lectureSlideNotes', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Vorlesungstext' }] }] },
      ],
    }],
  });
  const rows = page.locator('.pm-lecture-slide');
  await rows.first().locator('.pm-lecture-slide__notes p').click();
  await page.keyboard.press('End');
  await page.keyboard.type(' /mitschrift');
  await page.getByRole('option', { name: /Mitschrift.*Abschnitte/ }).click();
  await expect(rows).toHaveCount(2);
  const block = rows.nth(1);
  await expect(rows.first().locator('.pm-lecture-slide__media')).toBeVisible();
  await expect(block.locator('.pm-lecture-slide__media')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Bild neben Text' })).toBeVisible();
  await chooseLayout(page, 'Nur Text');
  await expect(rows.first().locator('.pm-lecture-slide__media')).toBeHidden();
  await expect(block.locator('.pm-lecture-slide__media')).toBeHidden();
  await block.locator('.pm-lecture-slide__notes p').click();
  await page.keyboard.type('Meine Mitschrift');
  const appearance = await block.evaluate(row => {
    const notes = row.querySelector('.pm-lecture-slide__notes');
    return {
      fullWidth: Math.abs(notes.getBoundingClientRect().width - row.querySelector('.pm-lecture-slide__columns').getBoundingClientRect().width) < 1,
      padding: getComputedStyle(notes).paddingLeft,
      line: getComputedStyle(notes, '::after').content,
      buttonCentered: Math.abs(row.querySelector('.pm-lecture-slide__add').getBoundingClientRect().x + 14 - (row.getBoundingClientRect().x + row.getBoundingClientRect().width / 2)) < 1,
    };
  });
  expect(appearance).toEqual({ fullWidth: true, padding: '0px', line: 'none', buttonCentered: true });
  await block.locator('.pm-lecture-slide__notes p').evaluate(element => {
    const clipboardData = new DataTransfer();
    clipboardData.items.add(new File(['image'], 'Bild.png', { type: 'image/png' }));
    element.dispatchEvent(new ClipboardEvent('paste', { clipboardData, bubbles: true, cancelable: true }));
  });
  await expect(block.locator('.pm-lecture-slide__notes .pm-note-image')).toBeVisible();
  await expect.poll(() => note.body_json.content[1]?.content[1]?.content.some(node => node.type === 'image')).toBe(true);
  expect(note.body_json.attrs).toMatchObject({ lectureLayout: 'text', lectureMode: false });
});

test('removing Mitschrift through the chip preserves images, formatting and text and is undoable', async ({ page }) => {
  const image = { type: 'image', attrs: { src: '/api/test-image/file', caption: 'Bildbeschriftung' } };
  const heading = { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Überschrift' }] };
  const list = { type: 'bulletList', content: [{ type: 'listItem', content: [{
    type: 'paragraph', content: [{ type: 'text', text: 'Wichtiger Punkt', marks: [{ type: 'bold' }] }],
  }] }] };
  const { note, open } = await mountNote(page, {
    type: 'doc', attrs: { lectureLayout: 'text', lectureMode: false, favorite: true }, content: [
      { type: 'paragraph', content: [{ type: 'text', text: 'Einleitung' }] },
      { type: 'lectureSlide', attrs: { capturedAt: '2026-10-13T12:00:00Z' }, content: [
        { type: 'lectureSlideMedia', content: [image] },
        { type: 'lectureSlideNotes', content: [heading, list] },
      ] },
      { type: 'paragraph', content: [{ type: 'text', text: 'Abschluss' }] },
    ],
  });
  await expect(page.locator('.pm-lecture-slide__media')).toBeHidden();
  async function removeView() {
    await page.getByRole('button', { name: /^Mitschrift, Ansicht:/ }).click();
    await page.getByRole('menuitem', { name: 'In Notiz umwandeln', exact: true }).click();
    await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
    await expect(page.locator('.pm-lecture-slide')).toHaveCount(0);
    await expect(page.locator('.pm-note-image')).toBeVisible();
    await expect.poll(() => note.body_json.attrs).toMatchObject({ lectureLayout: null, lectureMode: false, favorite: true });
    expect(note.body_json.content.map(node => node.type)).toEqual(['paragraph', 'image', 'heading', 'bulletList', 'paragraph']);
    expect(note.body_json.content[1]).toMatchObject(image);
    expect(note.body_json.content[2]).toMatchObject(heading);
    expect(note.body_json.content[3]).toMatchObject(list);
    await expect(page.locator('.tiptap')).toContainText('Einleitung');
    await expect(page.locator('.tiptap')).toContainText('Abschluss');
  }
  await removeView();
  await page.getByRole('button', { name: 'Rückgängig', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Mitschrift, Ansicht: Nur Text' })).toBeVisible();
  await expect(page.locator('.pm-lecture-slide')).toHaveCount(1);
  await expect(page.locator('.pm-lecture-slide__media')).toBeHidden();
  await expect(page.locator('.pm-lecture-slide__notes')).toContainText('Wichtiger Punkt');
  await removeView();
  await open();
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
  await expect(page.locator('.pm-lecture-slide')).toHaveCount(0);
  await expect(page.locator('.pm-note-image')).toBeVisible();
  await expect(page.locator('.tiptap strong')).toHaveText('Wichtiger Punkt');
});

test('the chip can remove an active Mitschrift view without sections', async ({ page }) => {
  const { note, open } = await mountNote(page, {
    type: 'doc', attrs: { lectureLayout: 'side', lectureMode: true },
    content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Meine Notiz' }] }],
  });
  await page.getByRole('button', { name: /^Mitschrift, Ansicht:/ }).click();
  await page.getByRole('menuitem', { name: 'In Notiz umwandeln', exact: true }).click();
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
  await expect.poll(() => note.body_json.attrs).toMatchObject({ lectureLayout: null, lectureMode: false });
  await expect(page.locator('.tiptap > p')).toHaveText('Meine Notiz');
  await open();
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
  await expect(page.locator('.tiptap > p')).toHaveText('Meine Notiz');
});
