import { test, expect } from '@playwright/test';

const IMAGE_SRC = '/api/notes/11111111-1111-1111-1111-111111111111/images/22222222-2222-2222-2222-222222222222/file';

async function mountNote(page, bodyJson, { rememberedLayout = 'side' } = {}) {
  const note = { id: 'title-note', title: 'Computergrafik – Vorlesung 3', title_is_generated: false, revision: 1, collection_id: null, tags: [], body_json: bodyJson };
  const patches = [];
  const settingsPatches = [];
  const ui = { notes_lecture_layout: rememberedLayout };
  await page.route('**/api/**', async route => {
    const req = route.request();
    const url = new URL(req.url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    if (url.pathname.endsWith('/file')) {
      return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="#5b6f86"/></svg>' });
    }
    let data = { items: [] };
    if (url.pathname === '/api/notes/title-note') {
      if (req.method() === 'PATCH') {
        const patch = req.postDataJSON();
        patches.push(patch);
        Object.assign(note, patch);
        note.revision++;
      }
      data = note;
    } else if (url.pathname === '/api/settings') {
      if (req.method() === 'PATCH') {
        const patch = req.postDataJSON();
        settingsPatches.push(patch);
        Object.assign(ui, patch.ui || {});
      }
      data = { ui };
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.route('**/__note-title', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="height:800px"></div></body></html>' }));
  await page.goto('/__note-title');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/noteTitle.js')).mountTitleEditor());
  await expect(page.getByRole('textbox', { name: 'Titel der Notiz', exact: true })).toHaveValue('Computergrafik – Vorlesung 3');
  // Der Fixture lädt keine Einstellungen; die gemerkte Wahl wie beim App-Start setzen.
  await page.evaluate(async (layout) => {
    const { useSettingsStore } = await import('/src/stores/settings.js');
    useSettingsStore().settings.ui.notes_lecture_layout = layout;
  }, rememberedLayout);
  patches.settings = settingsPatches;
  return patches;
}

const slideWithImage = {
  type: 'lectureSlide',
  attrs: { capturedAt: '2026-10-09T11:07:00Z' },
  content: [
    { type: 'lectureSlideMedia', content: [{ type: 'image', attrs: { src: IMAGE_SRC, alt: 'Folie 1' } }] },
    { type: 'lectureSlideNotes', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Rotation um den Ursprung' }] }] },
  ],
};

async function chooseLayout(page, name) {
  await page.getByRole('button', { name: /^Vorlesung, Layout:/ }).click();
  await page.getByRole('menuitemradio', { name }).click();
}

test('the Vorlesung chip switches between side-by-side, stacked and text-only layouts', async ({ page }) => {
  const patches = await mountNote(page, { type: 'doc', attrs: { lectureMode: true }, content: [slideWithImage] });
  const media = page.locator('.pm-lecture-slide__media');
  const notes = page.locator('.pm-lecture-slide__notes');
  await expect(page.getByRole('button', { name: 'Vorlesung, Layout: Folie neben Mitschrift' })).toBeVisible();
  await expect(media).toBeVisible();

  // Nur Mitschrift: Folie ausgeblendet, Text in voller Breite, Inhalt unverändert.
  await chooseLayout(page, 'Nur Mitschrift');
  await expect(media).toBeHidden();
  await expect(notes).toContainText('Rotation um den Ursprung');
  await expect.poll(() => patches.at(-1)?.body_json?.attrs).toMatchObject({ lectureLayout: 'text', lectureMode: false });
  // Die Wahl wird als Vorgabe für neue Vorlesungsnotizen gemerkt.
  await expect.poll(() => patches.settings.at(-1)).toEqual({ ui: { notes_lecture_layout: 'text' } });
  expect(patches.at(-1).body_json.content[0].content[0].content[0].attrs.src).toBe(IMAGE_SRC);
  const fullWidth = await page.locator('.pm-lecture-slide__columns').evaluate(el => el.getBoundingClientRect().width);
  expect(await notes.evaluate(el => el.getBoundingClientRect().width)).toBeGreaterThan(fullWidth - 2);
  // Ohne Folie keine Schreiblinie und kein Einzug: Text bündig unter „Folie 1".
  expect(await notes.evaluate(el => [getComputedStyle(el, '::after').content, getComputedStyle(el).paddingLeft])).toEqual(['none', '0px']);

  // Ausgeblendeter Screenshot bleibt über die Kopfzeile erreichbar.
  await page.getByRole('button', { name: 'Ausgeblendeten Screenshot ansehen' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.locator('.pm-note-image__preview')).toBeVisible();
  await page.waitForTimeout(250); // Einblend-Transition abwarten, sonst geht Escape ins Leere.
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);

  // Folie über Mitschrift: Folie wieder sichtbar, eine Spalte.
  await chooseLayout(page, 'Folie über Mitschrift');
  await expect(media).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ausgeblendeten Screenshot ansehen' })).toHaveCount(0);
  const [mediaBox, notesBox] = await Promise.all([media.boundingBox(), notes.boundingBox()]);
  expect(notesBox.y).toBeGreaterThan(mediaBox.y + mediaBox.height - 1);
  await expect.poll(() => patches.at(-1)?.body_json?.attrs).toMatchObject({ lectureLayout: 'stacked', lectureMode: false });

  // Zurück zu „neben": zwei Spalten.
  await chooseLayout(page, 'Folie neben Mitschrift');
  const [sideMedia, sideNotes] = await Promise.all([media.boundingBox(), notes.boundingBox()]);
  expect(sideNotes.x).toBeGreaterThan(sideMedia.x + sideMedia.width);
  await expect.poll(() => patches.at(-1)?.body_json?.attrs).toMatchObject({ lectureLayout: 'side', lectureMode: true });
});

test('a plain note becomes a lecture note in the remembered layout', async ({ page }) => {
  const patches = await mountNote(page, { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Leere Mitschrift' }] }] }, { rememberedLayout: 'text' });
  await expect(page.locator('.note-workspace-editor__kind-chip')).toHaveCount(0);
  await page.getByRole('button', { name: 'Weitere Aktionen', exact: true }).click();
  await expect(page.getByRole('menuitem', { name: /Als Vorlesung mitschreiben/ })).toContainText('Nur Mitschrift');
  await page.getByRole('menuitem', { name: /Als Vorlesung mitschreiben/ }).click();
  await expect(page.getByRole('button', { name: 'Vorlesung, Layout: Nur Mitschrift' })).toBeVisible();
  await expect.poll(() => patches.at(-1)?.body_json?.attrs).toMatchObject({ lectureLayout: 'text', lectureMode: false });
  // Gleiche Wahl wie gemerkt → keine überflüssige Einstellungs-Speicherung.
  expect(patches.settings).toEqual([]);
  await page.getByRole('button', { name: 'Weitere Aktionen', exact: true }).click();
  await expect(page.getByRole('menuitem', { name: /Als Vorlesung mitschreiben/ })).toHaveCount(0);
});
