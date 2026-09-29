import { expect, test } from '@playwright/test';

const docId = '10000000-0000-4000-8000-000000000001';
const user = { id: '20000000-0000-4000-8000-000000000001', username: 'review', is_admin: true, is_active: true };

async function mockApi(page) {
  let loggedIn = false;
  const patches = [];
  const imports = [];
  const settings = {
    ui: {
      start_view: 'all', drawer_remember_state: true,
      dashboard_show_import_action: true, dashboard_show_note_action: true,
    },
    retention: { enabled: false },
  };
  const document = {
    id: docId, original_filename: 'Prüfbeleg.pdf', display_name: 'Prüfbeleg',
    notes: '', document_date: null, status: 'ready', ocr_status: 'not_started',
    text_source: 'none', embedding_status: 'not_started', is_deleted: false,
    is_unread: false, tags: [], files: [], jobs: [], flags: {}, page_count: 0,
    created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
  };
  const tokens = () => ({
    user, access_token: `test.${Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url')}.test`,
    token_type: 'bearer', expires_in: 3600,
  });
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    const json = (body, status = 200) => route.fulfill({ status, json: body });
    if (path === '/api/auth/login') {
      if (request.postDataJSON().password !== 'valid-password') return json({ error: { message: 'Ungültige Zugangsdaten' } }, 401);
      loggedIn = true;
      return json(tokens());
    }
    if (path === '/api/auth/refresh' || path === '/api/auth/renew') return loggedIn ? json(tokens()) : json({}, 401);
    if (path === '/api/auth/me') return loggedIn ? json(user) : json({}, 401);
    if (path === '/api/auth/file-token') return json({ token: 'file-token', expires_in: 300 });
    if (path === '/api/settings') {
      if (request.method() === 'PATCH') {
        const patch = request.postDataJSON();
        settings.ui = { ...settings.ui, ...(patch.ui || {}) };
        settings.retention = { ...settings.retention, ...(patch.retention || {}) };
      }
      return json(settings);
    }
    if (path === '/api/documents') return json({ items: [document], total: 1, limit: 100, offset: 0 });
    if (path === `/api/documents/${docId}`) {
      if (request.method() === 'PATCH') {
        patches.push(request.postDataJSON());
        Object.assign(document, request.postDataJSON());
      }
      return json(document);
    }
    if (path === '/api/import/source') {
      imports.push('source');
      return json({ items: [{ source_file_id: 'source-1', original_name: 'Import.pdf', page_count: 1 }] });
    }
    if (path === '/api/import/commit') {
      imports.push(request.postDataJSON());
      return json({ created: [{ id: docId, document_id: docId }], errors: [] });
    }
    if (path === '/api/import/inbox/events') return route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': connected\n\n' });
    if (path === '/api/import/inbox') return json({ items: [], pending_count: 0, scanner_jobs: [] });
    if (path === '/api/sidebar/counts') return json({ total_count: 1, all_count: 1 });
    if (path.startsWith('/api/notes') || ['/api/tags', '/api/document-types', '/api/correspondents', '/api/saved-searches', '/api/smart-folders', '/api/scanners'].includes(path)) return json([]);
    if (path.includes('/annotations')) return json([]);
    if (path === '/api/documents/statuses') return json({ items: [] });
    return json({});
  });
  await page.addInitScript(() => localStorage.setItem('pm.drawerExpanded', '1'));
  return { patches, imports };
}

async function login(page) {
  await page.goto('/login');
  await page.getByLabel('Benutzername oder E-Mail').fill('review');
  await page.getByLabel('Passwort', { exact: true }).fill('valid-password');
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('button', { name: 'Einstellungen', exact: true }).first()).toBeVisible();
}

test('failed login stays usable, successful login opens workspace', async ({ page }) => {
  await mockApi(page);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/login');
  await page.getByLabel('Benutzername oder E-Mail').fill('review');
  await page.getByLabel('Passwort', { exact: true }).fill('wrong-password');
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await login(page);
  await expect(page.getByText('Prüfbeleg', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Zuletzt bearbeitet', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Angepinnt', { exact: true }).first()).toBeVisible();
  await page.getByText('Zuletzt bearbeitet', { exact: true }).first().click();
  await expect(page.locator('.notes-ws__heading')).toHaveText('Zuletzt bearbeitet');
  await page.getByText('Angepinnt', { exact: true }).first().click();
  await expect(page.locator('.notes-ws__heading')).toHaveText('Angepinnt');
  await expect(page.locator('.sidebar-foot__actions').getByRole('button', { name: /in Bearbeitung|fehlgeschlagen/ })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('sidebar footer shows activity only while work is running and keeps shortcuts in overflow', async ({ page }, testInfo) => {
  await mockApi(page);
  await page.route('**/api/jobs/activity', async (route) => {
    await route.fulfill({ json: {
      jobs: [{
        id: 'job-1', document_id: docId, document_title: 'Prüfbeleg',
        status: 'running', type: 'OCR',
      }],
      ocr_backlog: { total: 1, done: 0, pending: 1, failed: 0 },
      backup: null,
    } });
  });
  await login(page);

  const footerActions = page.locator('.sidebar-foot__actions');
  await expect(footerActions.locator(':scope > .v-btn')).toHaveCount(3);
  const activityButton = footerActions.getByRole('button', { name: /1 Dokument\(e\) in Bearbeitung/ });
  await expect(activityButton).toBeVisible();
  await expect(footerActions.getByRole('button', { name: 'Einstellungen', exact: true })).toBeVisible();

  await activityButton.click();
  const activityPanel = page.locator('.activity-card');
  await expect(activityPanel).toBeVisible();
  const [activityButtonBox, activityPanelBox] = await Promise.all([
    activityButton.boundingBox(),
    activityPanel.boundingBox(),
  ]);
  expect(activityPanelBox.y + activityPanelBox.height).toBeLessThanOrEqual(activityButtonBox.y + 4);
  await page.keyboard.press('Escape');

  const moreButton = footerActions.getByRole('button', { name: 'Weitere Aktionen', exact: true });
  await moreButton.click();
  const overflowMenu = page.locator('.sidebar-foot__more-menu');
  await expect(overflowMenu).toBeVisible();
  await expect(overflowMenu.getByText('Tastenkürzel', { exact: true })).toBeVisible();
  await expect(overflowMenu.getByText('Aktivität', { exact: true })).toHaveCount(0);
  await expect(overflowMenu.getByText('Papierkorb', { exact: false })).toBeVisible();
  await page.waitForTimeout(250); // Overlay-Transition vor dem visuellen Snapshot abschließen.
  await page.screenshot({ path: testInfo.outputPath('sidebar-footer-overflow.png') });
});

test('Lernraum keeps one navigable path from course to focused learning', async ({ page }) => {
  await mockApi(page);
  const courseId = '30000000-0000-4000-8000-000000000001';
  const sheetId = '40000000-0000-4000-8000-000000000001';
  const course = {
    id: courseId, title: 'Computergrafik', session_count: 1, sheet_count: 1, card_count: 2,
    proficiency: { total: 2, strong: 1, medium: 0, weak: 0, open: 1 },
  };
  const sheet = {
    id: sheetId, course_id: courseId, session_id: 'session-1', title: 'Rasterisierung',
    status: 'in_progress', is_favorite: false, card_count: 2, kind_summary: 'gemischt',
  };
  const cards = [
    { id: 'card-1', sheet_id: sheetId, kind: 'fakt', front: 'Was ist ein Fragment?', back: 'Ein Kandidat für ein Pixel.', status: 'open' },
    { id: 'card-2', sheet_id: sheetId, kind: 'verstaendnis', front: 'Warum wird gerastert?', back: 'Um Geometrie auf Pixel abzubilden.', status: 'strong' },
  ];
  let sheetDeleted = false;

  await page.route('**/api/learn/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body) => route.fulfill({ status: 200, json: body });
    if (path === '/api/learn/courses') return json({ items: [course] });
    if (path === `/api/learn/courses/${courseId}` && request.method() === 'PATCH') {
      Object.assign(course, request.postDataJSON());
      return json(course);
    }
    if (path === `/api/learn/courses/${courseId}/board`) return json({ course, sessions: [{ id: 'session-1', title: 'Vorlesung 1', sheets: sheetDeleted ? [] : [sheet] }], loose_sheets: [] });
    if (path === '/api/learn/sheets') return json({ items: sheetDeleted ? [] : [sheet] });
    if (path === `/api/learn/sheets/${sheetId}` && request.method() === 'PATCH') {
      Object.assign(sheet, request.postDataJSON());
      return json(sheet);
    }
    if (path === `/api/learn/sheets/${sheetId}` && request.method() === 'DELETE') {
      sheetDeleted = true;
      return json({ ok: true });
    }
    if (path === `/api/learn/sheets/${sheetId}/cards`) return json({ items: cards });
    if (path === '/api/learn/markers') return json({ items: [] });
    if (path.startsWith('/api/learn/cards/') && path.endsWith('/review')) return json({ ...cards[0], status: request.postDataJSON().status });
    return json({});
  });

  await login(page);
  await page.goto('/lernen');
  await expect(page.getByRole('heading', { name: 'Lernraum', exact: true })).toBeVisible();
  await expect(page.locator('.lr-header-progress')).toBeVisible();
  const homeHeaderHeight = await page.locator('.lr-nav').evaluate((element) => element.getBoundingClientRect().height);
  const homeTitleLeft = await page.locator('.lr-title').evaluate((element) => element.getBoundingClientRect().left);
  const homeTitleTop = await page.locator('.lr-title').evaluate((element) => element.getBoundingClientRect().top);
  await expect(page.getByRole('button', { name: 'Kurs anlegen', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: /Computergrafik/ }).click();
  await expect(page).toHaveURL(new RegExp(`course=${courseId}`));
  await expect(page.getByRole('heading', { name: 'Computergrafik', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Zurück zum Lernraum' })).toBeVisible();
  expect(await page.locator('.lr-nav').evaluate((element) => element.getBoundingClientRect().height)).toBe(homeHeaderHeight);
  expect(await page.locator('.lr-title').evaluate((element) => element.getBoundingClientRect().left)).toBe(homeTitleLeft);
  expect(await page.locator('.lr-title').evaluate((element) => element.getBoundingClientRect().top)).toBe(homeTitleTop);
  await expect(page.locator('.lr-header-progress')).toBeVisible();
  await expect(page.locator('.lr-course-overview')).toHaveCount(0);
  await expect(page.locator('.lr-sheet-tile').getByRole('button', { name: 'Jetzt lernen', exact: true })).toBeVisible();
  await expect(page.locator('.lr-nav').getByRole('button', { name: /Jetzt lernen/ })).toHaveCount(0);
  await page.locator('.lr-title-edit').click();
  await expect(page.locator('.lr-title-input')).toHaveValue('Computergrafik');
  await page.locator('.lr-title-input').fill('Grafik Grundlagen');
  await page.locator('.lr-title-input').press('Enter');
  await expect(page.getByRole('heading', { name: 'Grafik Grundlagen', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '„Rasterisierung“ umbenennen' }).click();
  await page.getByLabel('Lernblattname').fill('Rastergrafik');
  await page.getByLabel('Lernblattname').press('Enter');
  await expect(page.locator('.lr-sheet-title-button')).toHaveText('Rastergrafik');
  await page.getByRole('button', { name: 'Rastergrafik', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`sheet=${sheetId}`));
  await expect(page.getByRole('heading', { name: 'Rastergrafik', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Zurück zu Grafik Grundlagen' })).toBeVisible();
  expect(await page.locator('.lr-nav').evaluate((element) => element.getBoundingClientRect().height)).toBe(homeHeaderHeight);
  expect(await page.locator('.lr-title').evaluate((element) => element.getBoundingClientRect().left)).toBe(homeTitleLeft);
  expect(await page.locator('.lr-title').evaluate((element) => element.getBoundingClientRect().top)).toBe(homeTitleTop);
  await page.getByRole('button', { name: /Jetzt lernen/ }).click();
  await expect(page.locator('.lr-focus')).toBeVisible();
  await expect(page.getByText('Was ist ein Fragment?', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/learn=1/);
  await page.getByRole('button', { name: 'Beenden', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`sheet=${sheetId}`));
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Löschen', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`course=${courseId}`));
  await expect(page.locator('.lr-sheet-tile')).toHaveCount(0);
});

test('title-sorted notes form one alphabetical list without date headings', async ({ page }) => {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem('pm-notes-list-preferences-v1', JSON.stringify({ sortMode: 'title' }));
  });
  await page.route(/^.*\/api\/notes(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [
      {
        id: '30000000-0000-4000-8000-000000000010', title: 'Zulu', preview: 'Neue Notiz',
        created_at: '2026-09-20T10:00:00Z', updated_at: '2026-09-20T10:00:00Z', is_favorite: false,
      },
      {
        id: '30000000-0000-4000-8000-000000000011', title: 'Alpha', preview: 'Ältere Notiz',
        created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z', is_favorite: false,
      },
    ] } });
  });
  await login(page);

  await page.getByText('Alle Notizen', { exact: true }).click();
  await expect(page.locator('.notes-ws__item-title')).toHaveText(['Alpha', 'Zulu']);
  await expect(page.locator('.notes-ws__group-heading')).toHaveCount(0);

  const showListButton = page.getByRole('button', { name: 'Notizenliste einblenden' });
  if (await showListButton.isVisible()) await showListButton.click();
  const viewMenuButton = page.getByRole('button', { name: 'Titel · Auto', exact: true });
  await viewMenuButton.click();
  await expect(page.getByText('Sortieren nach', { exact: true })).toBeVisible();
  await expect(page.getByText('Gruppieren', { exact: true })).toBeVisible();
  await page.getByText('Nach Notizbuch', { exact: true }).click();
  await expect(page.locator('.list-action-toolbar__action-btn').filter({ hasText: 'Titel · Notizbuch' })).toBeVisible();
});

test('notes support recently-opened sorting plus notebook and pinned groups', async ({ page }) => {
  await mockApi(page);
  await page.addInitScript(() => {
    if (!localStorage.getItem('pm-notes-list-preferences-v1')) {
      localStorage.setItem('pm-notes-list-preferences-v1', JSON.stringify({
        sortMode: 'opened', grouping: 'none',
      }));
    }
  });
  const notes = [
    {
      id: '30000000-0000-4000-8000-000000000020', title: 'Alpha', preview: 'Angepinnt',
      notebook_id: 'notebook-work', is_favorite: true,
      created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-20T10:00:00Z',
      last_opened_at: '2026-09-21T10:00:00Z',
    },
    {
      id: '30000000-0000-4000-8000-000000000021', title: 'Bravo', preview: 'Zuletzt geöffnet',
      notebook_id: 'notebook-private', is_favorite: false,
      created_at: '2026-09-02T10:00:00Z', updated_at: '2026-09-18T10:00:00Z',
      last_opened_at: '2026-09-24T10:00:00Z',
    },
    {
      id: '30000000-0000-4000-8000-000000000022', title: 'Charlie', preview: 'Ohne Ablage',
      notebook_id: null, is_favorite: false,
      created_at: '2026-09-03T10:00:00Z', updated_at: '2026-09-19T10:00:00Z',
      last_opened_at: '2026-09-23T10:00:00Z',
    },
  ];
  await page.route(/^.*\/api\/notes(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: notes } });
  });
  await page.route(/^.*\/api\/notes\/notebooks(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [
      { id: 'notebook-work', name: 'Arbeit', note_count: 1 },
      { id: 'notebook-private', name: 'Privat', note_count: 1 },
    ] } });
  });
  await login(page);

  await page.getByText('Alle Notizen', { exact: true }).click();
  await expect(page.locator('.notes-ws__item-title')).toHaveText(['Bravo', 'Charlie', 'Alpha']);

  await page.evaluate(() => localStorage.setItem('pm-notes-list-preferences-v1', JSON.stringify({
    sortMode: 'title', grouping: 'notebook',
  })));
  await page.reload();
  await page.getByText('Alle Notizen', { exact: true }).click();
  const showNotebookGroups = page.getByRole('button', { name: 'Notizenliste einblenden' });
  if (await showNotebookGroups.isVisible()) await showNotebookGroups.click();
  await expect(page.locator('.notes-ws__group-heading')).toHaveText(['Arbeit', 'Privat', 'Ohne Notizbuch']);

  await page.evaluate(() => localStorage.setItem('pm-notes-list-preferences-v1', JSON.stringify({
    sortMode: 'title', grouping: 'favorites',
  })));
  await page.reload();
  await page.getByText('Alle Notizen', { exact: true }).click();
  const showFavoriteGroups = page.getByRole('button', { name: 'Notizenliste einblenden' });
  if (await showFavoriteGroups.isVisible()) await showFavoriteGroups.click();
  await expect(page.locator('.notes-ws__group-heading')).toHaveText(['Angepinnt', 'Weitere Notizen']);
  await expect(page.locator('.notes-ws__item-title').first()).toHaveText('Alpha');
});

test('command palette finds and opens individual notes', async ({ page }) => {
  await mockApi(page);
  const noteId = '30000000-0000-4000-8000-000000000030';
  const note = {
    id: noteId, title: 'Projektgedanke', preview: 'Ideen für die nächste Etappe',
    body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Ideen für die nächste Etappe' }] }] },
    notebook_id: 'notebook-ideas', is_favorite: true,
    created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-20T10:00:00Z',
    last_opened_at: '2026-09-23T10:00:00Z',
  };
  await page.route(/^.*\/api\/notes(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [note] } });
  });
  await page.route(/^.*\/api\/notes\/notebooks(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [{ id: 'notebook-ideas', name: 'Ideen', note_count: 1 }] } });
  });
  await page.route(`**/api/notes/${noteId}`, async (route) => {
    await route.fulfill({ json: note });
  });
  await page.route(`**/api/notes/${noteId}/opened`, async (route) => {
    await route.fulfill({ json: { id: noteId, last_opened_at: '2026-09-24T10:00:00Z' } });
  });
  await login(page);

  await page.keyboard.press('Control+K');
  const palette = page.getByRole('dialog', { name: 'Befehle und Suche' });
  await expect(palette).toBeVisible();
  await palette.getByRole('combobox', { name: 'Aktion oder Suche' }).fill('Projektgedanke');
  await expect(palette.getByText('Notizen', { exact: true })).toBeVisible();
  await expect(palette.getByText('Angepinnt · Ideen', { exact: true })).toBeVisible();
  await palette.getByText('Projektgedanke', { exact: true }).click();

  await expect(page.getByRole('textbox', { name: 'Titel der Notiz' })).toHaveValue('Projektgedanke');
  await expect(page.getByRole('region', { name: 'Notizbereich' })).toContainText('Ideen für die nächste Etappe');
});

test('command palette creates a new note and focuses its editor', async ({ page }) => {
  await mockApi(page);
  const noteId = '30000000-0000-4000-8000-000000000031';
  let createRequests = 0;
  const createdNote = {
    id: noteId, title: '', preview: '',
    body_json: { type: 'doc', content: [{ type: 'paragraph' }] },
    notebook_id: null, collection_id: null, is_favorite: false,
    created_at: '2026-09-24T11:00:00Z', updated_at: '2026-09-24T11:00:00Z',
    last_opened_at: null,
  };
  await page.route(/^.*\/api\/notes(?:\?.*)?$/, async (route) => {
    if (route.request().method() === 'POST') {
      createRequests += 1;
      return route.fulfill({ json: createdNote });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route(`**/api/notes/${noteId}/opened`, async (route) => {
    await route.fulfill({ json: { id: noteId, last_opened_at: '2026-09-24T11:00:01Z' } });
  });
  await login(page);

  await page.keyboard.press('Control+K');
  const palette = page.getByRole('dialog', { name: 'Befehle und Suche' });
  await palette.getByRole('combobox', { name: 'Aktion oder Suche' }).fill('Neue Notiz erstellen');
  await palette.getByText('Neue Notiz erstellen', { exact: true }).click();

  await expect.poll(() => createRequests).toBe(1);
  await expect(page.getByRole('textbox', { name: 'Titel der Notiz' })).toHaveValue('');
  await expect(page.locator('.tiptap[contenteditable="true"]')).toBeFocused();
});

test('dashboard header offers colored import and note quick actions', async ({ page }) => {
  await mockApi(page);
  const noteId = '30000000-0000-4000-8000-000000000032';
  let createRequests = 0;
  const createdNote = {
    id: noteId, title: '', preview: '',
    body_json: { type: 'doc', content: [{ type: 'paragraph' }] },
    notebook_id: null, collection_id: null, is_favorite: false,
    created_at: '2026-09-24T12:00:00Z', updated_at: '2026-09-24T12:00:00Z',
    last_opened_at: null,
  };
  await page.route(/^.*\/api\/notes(?:\?.*)?$/, async (route) => {
    if (route.request().method() === 'POST') {
      createRequests += 1;
      return route.fulfill({ json: createdNote });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route(`**/api/notes/${noteId}/opened`, async (route) => {
    await route.fulfill({ json: { id: noteId, last_opened_at: '2026-09-24T12:00:01Z' } });
  });
  await login(page);
  await page.getByText('Übersicht', { exact: true }).first().click();

  const actions = page.locator('.dash-head__actions');
  const importButton = actions.getByRole('button', { name: 'Dokument importieren', exact: true });
  const noteButton = actions.getByRole('button', { name: 'Notiz schreiben', exact: true });
  await expect(importButton).toBeVisible();
  await expect(noteButton).toBeVisible();
  await expect(importButton).toHaveClass(/dash-btn--import/);
  await expect(noteButton).toHaveClass(/dash-btn--note/);

  await actions.getByRole('button', { name: 'Anpassen', exact: true }).click();
  const widgetDialog = page.getByRole('dialog');
  const importToggle = widgetDialog.getByRole('switch', { name: 'Dokument importieren' });
  await expect(importToggle).toHaveAttribute('aria-checked', 'true');
  await importToggle.click();
  await expect(importButton).toHaveCount(0);
  await expect(noteButton).toHaveCount(1);
  await expect(importToggle).toHaveAttribute('aria-checked', 'false');
  await importToggle.click();
  await page.keyboard.press('Escape');
  await expect(importButton).toBeVisible();

  await importButton.click();
  await expect(page.getByRole('dialog').getByText('Importieren', { exact: true }).first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog').getByText('Importieren', { exact: true })).toHaveCount(0);

  await noteButton.click();
  await expect.poll(() => createRequests).toBe(1);
  await expect(page.locator('.tiptap[contenteditable="true"]')).toBeFocused();
});

test('global search opens the selected result in its list when cleared', async ({ page }, testInfo) => {
  await mockApi(page);
  const selectedDocId = '10000000-0000-4000-8000-000000000002';
  const listDocuments = [
    { id: docId, original_filename: 'Prüfbeleg.pdf', display_name: 'Prüfbeleg' },
    { id: selectedDocId, original_filename: 'Prüfbericht.pdf', display_name: 'Prüfbericht', snippet: 'Prüf-<mark>bericht</mark> bestätigt' },
  ].map((doc) => ({
    ...doc, notes: '', document_date: null, status: 'ready', ocr_status: 'not_started',
    text_source: 'none', embedding_status: 'not_started', is_deleted: false,
    is_unread: false, tags: [], files: [], jobs: [], flags: {}, page_count: 0,
    created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
  }));
  await page.route(/^.*\/api\/documents(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: listDocuments, total: listDocuments.length, limit: 100, offset: 0 } });
  });
  await page.route(`**/api/documents/${selectedDocId}`, async (route) => {
    await route.fulfill({ json: listDocuments[1] });
  });
  await page.route(/^.*\/api\/notes(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [{
      id: '30000000-0000-4000-8000-000000000001', title: 'Prüfnotiz', preview: 'Prüfbeleg erklärt',
      created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
    }] } });
  });
  await page.route('**/api/notes/30000000-0000-4000-8000-000000000001', async (route) => {
    await route.fulfill({ json: {
      id: '30000000-0000-4000-8000-000000000001', title: 'Prüfnotiz',
      body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Prüfbeleg erklärt' }] }] },
      created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
    } });
  });
  await login(page);

  await page.getByPlaceholder('Überall suchen …').fill('Prüf');
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toBeVisible();
  const resultsHeader = page.locator('.global-results__header');
  await expect(resultsHeader.locator('.panel-middle__heading')).toHaveText('Suchergebnisse');
  await expect(resultsHeader.locator('.panel-middle__count')).toContainText('Treffer');
  await expect(resultsHeader.locator('input')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: /Dokumente/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Notizen/ })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Globale Suchergebnisse' }).getByText('Prüfnotiz')).toBeVisible();
  const selectedSnippet = page.getByRole('region', { name: 'Globale Suchergebnisse' }).locator('.global-results__snippet').filter({ hasText: 'Prüf-bericht bestätigt' });
  await expect(selectedSnippet.locator('mark')).toHaveText('bericht');
  await expect(selectedSnippet).not.toContainText('<mark>');
  await page.getByRole('button', { name: 'Standard', exact: true }).click();
  await page.getByText('Name Z–A', { exact: true }).click();
  await expect(page.locator('.global-results__group').first().locator('li').first()).toContainText('Prüfbericht');
  await page.getByRole('button', { name: 'Alle Treffer', exact: true }).click();
  await page.getByText('Notizen', { exact: true }).last().click();
  await expect(page.getByRole('heading', { name: /Dokumente/ })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: /Notizen/ })).toBeVisible();
  await expect(page.locator('.global-results__header .panel-middle__count')).toContainText('1 Treffer');
  await page.getByRole('button', { name: 'Notizen', exact: true }).click();
  await page.getByText('Alle Treffer', { exact: true }).last().click();
  await page.getByRole('button', { name: /^Prüfbericht/ }).click();
  // Dokumenttreffer nutzen das reguläre Vorschau-Panel inkl. Detailschublade.
  await expect(page.getByRole('region', { name: 'Suchtreffer-Vorschau' })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'PDF Vorschau' })).toBeVisible();
  await expect(page.getByPlaceholder('Dokumentname…')).toHaveValue('Prüfbericht');
  await expect(page.locator('.global-results__open')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('global-search-split.png') });
  await page.getByPlaceholder('Überall suchen …').fill('');
  await expect(page.getByLabel('Diese Dokumentliste durchsuchen')).toBeVisible();
  await expect(page.getByPlaceholder('Überall suchen …')).toHaveValue('');
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toHaveCount(0);
  await expect(page.locator(`.document-row--active[data-document-id="${selectedDocId}"]`)).toBeVisible();
  await expect(page.getByPlaceholder('Dokumentname…')).toHaveValue('Prüfbericht');
  await expect(page.getByRole('region', { name: 'PDF Vorschau' })).toBeVisible();

  await page.getByText('Alle Notizen', { exact: true }).click();
  const showNotesList = page.getByRole('button', { name: 'Notizenliste einblenden' });
  await expect(showNotesList).toBeVisible();
  await showNotesList.click();
  await page.getByLabel('Notizen durchsuchen', { exact: true }).fill('Prüf');
  await expect(page.getByText('Prüfnotiz')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toHaveCount(0);

  await page.getByPlaceholder('Überall suchen …').fill('Prüf');
  await page.getByRole('region', { name: 'Globale Suchergebnisse' }).getByRole('button', { name: /^Prüfnotiz/ }).click();
  const preview = page.getByRole('region', { name: 'Suchtreffer-Vorschau' });
  await expect(preview.getByText('Notiz · Nur-Lese-Vorschau')).toBeVisible();
  await expect(preview).toContainText('Prüfbeleg erklärt');
  await page.screenshot({ path: testInfo.outputPath('global-search-note-preview.png') });
  await page.locator('.sidebar-search__field .v-field__clearable').click();
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: 'Titel der Notiz' })).toHaveValue('Prüfnotiz');
  await expect(page.getByRole('region', { name: 'Notizbereich' })).toContainText('Prüfbeleg erklärt');
  await expect(page.locator('.notes-ws__item.is-active[data-note-id="30000000-0000-4000-8000-000000000001"]')).toBeVisible();
});

test('global tag and document type results lead to their filtered lists', async ({ page }) => {
  await mockApi(page);
  await page.route(/^.*\/api\/tags(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [{ id: 'tag-1', name: 'Rechnung', usage_count: 1 }] } });
  });
  await page.route(/^.*\/api\/document-types(?:\?.*)?$/, async (route) => {
    await route.fulfill({ json: { items: [{ id: 'type-1', name: 'Rechnungstyp', usage_count: 1 }] } });
  });
  await login(page);

  await page.getByPlaceholder('Überall suchen …').fill('Rechnung');
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toBeVisible();
  await page.locator('.global-results__chip', { has: page.locator('.global-results__chip-label', { hasText: /^Rechnung$/ }) }).click();
  await page.getByPlaceholder('Überall suchen …').fill('');
  await expect(page.getByLabel('Tagliste durchsuchen')).toHaveValue('Rechnung');
  await expect(page.locator('.tag-row').filter({ hasText: 'Rechnung' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toHaveCount(0);

  await page.getByPlaceholder('Überall suchen …').fill('Rechnungstyp');
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toBeVisible();
  await page.locator('.global-results__chip', { has: page.locator('.global-results__chip-label', { hasText: /^Rechnungstyp$/ }) }).click();
  await page.getByPlaceholder('Überall suchen …').fill('');
  await expect(page.getByLabel('Dokumenttypenliste durchsuchen')).toHaveValue('Rechnungstyp');
  await expect(page.locator('.tag-row').filter({ hasText: 'Rechnungstyp' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Suchergebnisse' })).toHaveCount(0);
});

test('note settings use the standard PaperMind header and grouped live preview', async ({ page }) => {
  await mockApi(page);
  await login(page);
  await page.getByRole('button', { name: 'Einstellungen', exact: true }).first().click();
  await page.getByRole('tab', { name: 'Notizen', exact: true }).click();
  await expect(page.getByText('Schreiben, Darstellung und Gliederung nach deinen Gewohnheiten.')).toBeVisible();
  await expect(page.getByText('Allgemein', { exact: true })).toBeVisible();
  await expect(page.getByText('Schreiben', { exact: true })).toBeVisible();
  await expect(page.getByText('Textdarstellung', { exact: true })).toBeVisible();
  await expect(page.getByText('Abstände und Gliederung', { exact: true })).toBeVisible();
  await expect(page.locator('.notes-settings-preview')).toContainText('Eine klare Überschrift');
  await expect(page.getByText('Abstand vor Überschriften', { exact: true })).toBeVisible();
  await expect(page.getByText('Abstand bei Inhaltsblöcken', { exact: true })).toBeVisible();
});

test('document edits autosave and remain after reload', async ({ page }, testInfo) => {
  const { patches } = await mockApi(page);
  await login(page);
  const name = page.getByPlaceholder('Dokumentname…');
  if (!(await name.isVisible())) await page.getByRole('button', { name: 'Details ein- oder ausklappen' }).click();
  await expect(name).toHaveValue('Prüfbeleg');
  await name.fill('Gespeicherter Beleg');
  await expect.poll(() => patches.some((patch) => patch.display_name === 'Gespeicherter Beleg')).toBe(true);
  await page.reload();
  await expect(page.getByText('Gespeicherter Beleg', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('workspace.png') });
});

test('updated note editor accepts text and restores it after reload', async ({ page }) => {
  await mockApi(page);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/dev/notes');
  await page.getByRole('button', { name: '＋ Neue Notiz', exact: true }).click();
  const editor = page.locator('.tiptap[contenteditable="true"]');
  await expect(editor).toBeVisible();
  await editor.fill('Notiz nach dem Editor-Update');
  await expect(page.getByText('Gespeichert', { exact: true })).toBeVisible();
  await page.reload();
  await expect(editor).toContainText('Notiz nach dem Editor-Update');
  expect(errors).toEqual([]);
});

test('dropping a PDF uploads and commits the selected pages', async ({ page }) => {
  const { imports } = await mockApi(page);
  await login(page);
  const transfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['%PDF-1.4\n%%EOF'], 'Import.pdf', { type: 'application/pdf' }));
    return transfer;
  });
  await page.locator('.docs-list-dropzone').dispatchEvent('drop', { dataTransfer: transfer });
  await expect.poll(() => imports.length).toBe(2);
  expect(imports[1].documents[0].pages).toEqual([{ source_file_id: 'source-1', page_index: 0, rotation: 0 }]);
});
