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

async function openTrashWithMixedItems(page) {
  await mockApi(page);
  const documents = [1, 2].map(index => ({
    id: `trash-doc-${index}`, original_filename: `Papierkorb-Dokument ${index}.pdf`,
    display_name: `Papierkorb-Dokument ${index}`, document_date: null,
    status: 'ready', ocr_status: 'not_started', embedding_status: 'not_started',
    text_source: 'none', is_deleted: true, is_unread: false,
    tags: [], files: [], jobs: [], flags: {}, page_count: 0,
    created_at: '2026-10-01T10:00:00Z', updated_at: '2026-10-19T10:00:00Z',
  }));
  const notes = [1, 2].map(index => ({
    id: `trash-note-${index}`, title: `Papierkorb-Notiz ${index}`,
    preview: `Inhalt der Notiz ${index}`, is_deleted: true, is_template: false,
    tags: [], revision: 1, collection_id: null, notebook_id: null,
    created_at: '2026-10-01T10:00:00Z', updated_at: '2026-10-19T10:00:00Z',
    deleted_at: '2026-10-19T10:00:00Z',
    body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: `Inhalt der Notiz ${index}` }] }] },
  }));
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    const json = body => route.fulfill({ json: body });
    if (url.pathname === '/api/sidebar/counts') return json({ all_documents: 1, trash_count: 4 });
    if (url.pathname === '/api/documents' && url.searchParams.get('in_trash') === 'true') {
      return json({ items: documents, total: documents.length, offset: 0 });
    }
    const document = documents.find(item => url.pathname === `/api/documents/${item.id}`);
    if (document) return json(document);
    if (url.pathname === '/api/notes' && url.searchParams.get('in_trash') === 'true') {
      return json({ items: notes, total: notes.length, has_more: false });
    }
    const note = notes.find(item => url.pathname === `/api/notes/${item.id}`);
    if (note) return json(note);
    return route.fallback();
  });
  await login(page);
  await page.locator('.sidebar-foot__actions').getByRole('button', { name: 'Weitere Aktionen', exact: true }).click();
  await page.locator('.sidebar-foot__more-menu').getByText('Papierkorb', { exact: false }).click();
  await expect(page.locator('[data-document-id="trash-doc-1"]')).toBeVisible();
  await expect(page.locator('[data-trash-note-id="trash-note-2"]')).toBeVisible();
}

test('trash keeps one selection when switching between documents and notes', async ({ page }) => {
  await openTrashWithMixedItems(page);
  const document = page.locator('[data-document-id="trash-doc-1"]');
  const firstNote = page.locator('[data-trash-note-id="trash-note-1"]');
  const secondNote = page.locator('[data-trash-note-id="trash-note-2"]');
  const selected = page.locator('.document-row--active, .document-row--selected');

  await document.click();
  await expect(document).toHaveClass(/document-row--active/);
  await firstNote.click();
  await expect(firstNote).toHaveClass(/document-row--active/);
  await expect(selected).toHaveCount(1);
  await expect(page.locator('.note-preview__title')).toHaveText('Papierkorb-Notiz 1');

  await secondNote.focus();
  await secondNote.press('Space');
  await expect(secondNote).toHaveClass(/document-row--active/);
  await expect(selected).toHaveCount(1);
  await expect(page.locator('.note-preview__title')).toHaveText('Papierkorb-Notiz 2');

  await document.focus();
  await document.press('Enter');
  await expect(document).toHaveClass(/document-row--active/);
  await expect(selected).toHaveCount(1);
  await expect(page.locator('.note-preview')).toHaveCount(0);
});

test('trash treats Cmd and Ctrl clicks as single selection', async ({ page }) => {
  await openTrashWithMixedItems(page);
  const selected = page.locator('.document-row--active, .document-row--selected');
  const firstDocument = page.locator('[data-document-id="trash-doc-1"]');
  const secondDocument = page.locator('[data-document-id="trash-doc-2"]');
  const note = page.locator('[data-trash-note-id="trash-note-1"]');

  await firstDocument.click();
  await secondDocument.click({ modifiers: ['Meta'] });
  await expect(secondDocument).toHaveClass(/document-row--active/);
  await expect(selected).toHaveCount(1);
  await expect(page.getByRole('toolbar', { name: 'Batch-Aktionen' })).toHaveCount(0);

  // macOS verwendet echte Ctrl-Klicks für das Kontextmenü. Den normalen
  // Browser-Klick mit Ctrl separat auslösen, um auch diesen Auswahlpfad zu prüfen.
  await note.dispatchEvent('click', { ctrlKey: true });
  await expect(note).toHaveClass(/document-row--active/);
  await expect(selected).toHaveCount(1);
  await firstDocument.dispatchEvent('click', { ctrlKey: true });
  await expect(firstDocument).toHaveClass(/document-row--active/);
  await expect(selected).toHaveCount(1);
  await expect(page.getByRole('toolbar', { name: 'Batch-Aktionen' })).toHaveCount(0);
});

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
  const activityButton = footerActions.getByRole('button', { name: /1 Vorgang\/Vorgänge in Bearbeitung/ });
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
  const crumbs = page.locator('.lr-crumbs');
  const titleBox = () => page.locator('.lr-title').evaluate((element) => {
    const { left, top } = element.getBoundingClientRect();
    return { left, top };
  });
  await expect(page.getByRole('heading', { name: 'Lernraum', exact: true })).toBeVisible();
  await expect(page.locator('.lr-header-progress')).toBeVisible();
  await expect(crumbs.locator('[aria-current="page"]')).toHaveText('Startseite');
  const homeTitle = await titleBox();
  await expect(page.getByRole('button', { name: 'Kurs anlegen', exact: true })).toHaveCount(0);

  // Kurs: Brotkrumen führen zurück, Fortschritt sitzt im Kopf, Lernen startet je Lernblatt.
  await page.getByRole('button', { name: 'Kurs „Computergrafik“ öffnen' }).click();
  await expect(page).toHaveURL(new RegExp(`course=${courseId}`));
  await expect(page.getByRole('heading', { name: 'Computergrafik', exact: true })).toBeVisible();
  await expect(crumbs.getByRole('button', { name: 'Startseite', exact: true })).toBeVisible();
  expect(await titleBox()).toEqual(homeTitle);
  await expect(page.locator('.lr-header-progress')).toBeVisible();
  await expect(page.locator('.lr-course-overview')).toHaveCount(0);
  await expect(page.locator('.lr-sheet-tile').getByRole('button', { name: 'Jetzt lernen', exact: true })).toBeVisible();
  await page.locator('.lr-title-edit').click();
  await expect(page.locator('.lr-title-input')).toHaveValue('Computergrafik');
  await page.locator('.lr-title-input').fill('Grafik Grundlagen');
  await page.locator('.lr-title-input').press('Enter');
  await expect(page.getByRole('heading', { name: 'Grafik Grundlagen', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '„Rasterisierung“ umbenennen' }).click();
  await page.getByLabel('Lernblattname').fill('Rastergrafik');
  await page.getByLabel('Lernblattname').press('Enter');
  await expect(page.locator('.lr-sheet-tile .lr-course-name')).toHaveText('Rastergrafik');

  // Lernblatt: eine Ebene tiefer, Brotkrume führt zum Kurs zurück.
  await page.getByRole('button', { name: 'Lernblatt „Rastergrafik“ öffnen' }).click();
  await expect(page).toHaveURL(new RegExp(`sheet=${sheetId}`));
  await expect(page.getByRole('heading', { name: 'Rastergrafik', exact: true })).toBeVisible();
  expect(await titleBox()).toEqual(homeTitle);
  await crumbs.getByRole('button', { name: 'Grafik Grundlagen', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`course=${courseId}$`));

  // Fokussiertes Lernen mit definiertem Rückweg zum Lernblatt.
  await page.locator('.lr-sheet-tile').getByRole('button', { name: 'Jetzt lernen', exact: true }).click();
  await expect(page.locator('.lr-learning-focus')).toBeVisible();
  await expect(page.locator('.lr-focus-card-face--front').getByText('Was ist ein Fragment?', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/learn=1/);
  await page.locator('.lr-focus-exit').click();
  await page.locator('.lr-learn-exit-confirm').click();
  await expect(page.locator('.lr-learning-focus')).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`sheet=${sheetId}`));
  await expect(page).not.toHaveURL(/learn=1/);

  await crumbs.getByRole('button', { name: 'Grafik Grundlagen', exact: true }).click();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '„Rastergrafik“ löschen' }).click();
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
      notebook_id: 'notebook-work', is_favorite: false,
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

  // Eine früher gespeicherte Favoriten-Gruppierung gibt es nicht mehr (Notizen
  // kennen nur Pins): Sie fällt auf „Automatisch" zurück, ohne Favoriten-Block.
  await page.evaluate(() => localStorage.setItem('pm-notes-list-preferences-v1', JSON.stringify({
    sortMode: 'title', grouping: 'favorites',
  })));
  await page.reload();
  await page.getByText('Alle Notizen', { exact: true }).click();
  const showFallbackGroups = page.getByRole('button', { name: 'Notizenliste einblenden' });
  if (await showFallbackGroups.isVisible()) await showFallbackGroups.click();
  await expect(page.locator('.notes-ws__item-title')).toHaveText(['Alpha', 'Bravo', 'Charlie']);
  await expect(page.locator('.notes-ws__group-heading', { hasText: 'Favoriten' })).toHaveCount(0);

  // Die angepinnte Notiz steht in jeder Gruppierung als eigener Block ganz oben.
  notes[2].pinned_at = '2026-09-25T10:00:00Z';
  await page.evaluate(() => localStorage.setItem('pm-notes-list-preferences-v1', JSON.stringify({
    sortMode: 'title', grouping: 'notebook',
  })));
  await page.reload();
  await page.getByText('Alle Notizen', { exact: true }).click();
  const showPinnedGroups = page.getByRole('button', { name: 'Notizenliste einblenden' });
  if (await showPinnedGroups.isVisible()) await showPinnedGroups.click();
  await expect(page.locator('.notes-ws__group-heading')).toHaveText(['Angepinnt', 'Arbeit', 'Privat']);
  await expect(page.locator('.notes-ws__item-title').first()).toHaveText('Charlie');
  await expect(page.locator('.notes-ws__item-pin').first()).toHaveAttribute('aria-pressed', 'true');
});

test('command palette finds and opens individual notes', async ({ page }) => {
  await mockApi(page);
  const noteId = '30000000-0000-4000-8000-000000000030';
  const note = {
    id: noteId, title: 'Projektgedanke', preview: 'Ideen für die nächste Etappe',
    body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Ideen für die nächste Etappe' }] }] },
    notebook_id: 'notebook-ideas', is_favorite: false, pinned_at: '2026-09-22T10:00:00Z',
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
  const nav = page.getByRole('tablist', { name: 'Einstellungskategorien' });
  const notesGroup = nav.locator('.pm-settings-nav__group').filter({ hasText: 'Notizen' });
  for (const name of ['Allgemein', 'Textdarstellung', 'Abstände', 'Textersetzung']) {
    await expect(notesGroup.getByRole('tab', { name, exact: true })).toBeVisible();
  }
  const preview = page.locator('.notes-settings-preview');

  await notesGroup.getByRole('tab', { name: 'Allgemein', exact: true }).click();
  await expect(page.getByText('Standardansicht und Sortierung deiner Notizen.')).toBeVisible();
  await expect(page.getByText('Standardansicht', { exact: true })).toBeVisible();
  await expect(preview).toHaveCount(0);

  await notesGroup.getByRole('tab', { name: 'Textdarstellung', exact: true }).click();
  await expect(page.getByText('Schreibbreite, Schrift und Lesekomfort anpassen.')).toBeVisible();
  await expect(preview).toContainText('Eine klare Überschrift');

  await notesGroup.getByRole('tab', { name: 'Abstände', exact: true }).click();
  await expect(page.getByText('Abstände und Gliederung', { exact: true })).toBeVisible();
  await expect(page.getByText('Abstand vor Überschriften', { exact: true })).toBeVisible();
  await expect(page.getByText('Abstand bei Inhaltsblöcken', { exact: true })).toBeVisible();
  await expect(preview).toContainText('Eine klare Überschrift');
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

async function mockAvailableImportPages(page, initialCount = 3) {
  await mockApi(page);
  const sourceId = '30000000-0000-4000-8000-000000000001';
  const state = { count:initialCount, extraCount:0, failure:false, scanning:false, calls:0, mutations:[], discardedIds:[] };
  await page.route('**/api/import/inbox?*', route => {
    state.calls++;
    return route.fulfill(state.failure ? {status:503,json:{error:{message:'Temporär nicht verfügbar'}}} : {json:{
      items:[...(state.count ? [{ id:'available-pdf',source_file_id:sourceId,source_revision:'ready-1',source_type:'shortcut',is_assigned_to_me:true,
        original_name:'Bereitgestellte PDF.pdf',page_count:state.count,preview_url:'/api/available-pdf-preview' }] : []),
        ...(state.extraCount ? [{id:'new-pdf',source_file_id:'30000000-0000-4000-8000-000000000002',source_revision:'new-1',source_type:'shortcut',
          is_assigned_to_me:true,original_name:'Neue Seiten.pdf',page_count:state.extraCount,preview_url:'/api/available-pdf-preview'}] : [])],
      pending_count:state.count+state.extraCount,scanner_jobs:[],scanning:state.scanning,scanner:{id:'scanner-ready',name:'Scanner'},
    }});
  });
  await page.route('**/api/import/inbox/claim', route => {state.mutations.push('claim');return route.fulfill({json:{}});});
  await page.route('**/api/import/inbox/discard', route => {
    state.mutations.push('discard');state.discardedIds.push(...route.request().postDataJSON().item_ids);
    if(state.discardedIds.includes('available-pdf')) state.count=0;
    if(state.discardedIds.includes('new-pdf')) state.extraCount=0;
    return route.fulfill({json:{pending_count:state.count+state.extraCount}});
  });
  await page.route('**/api/import/source/*/file', route => route.fulfill({status:404}));
  await page.route('**/api/import/source/*/color-preview?*', route => route.fulfill({status:404}));
  await page.route('**/api/import/stages/*/suggest-title', route => route.fulfill({json:{status:'ready',suggestion:'',meta:{analysis_pending:false}}}));
  await page.route('**/api/available-pdf-preview', route => route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="280"><rect width="200" height="280" fill="white"/><text x="18" y="50">Verfügbare PDF</text></svg>'}));
  await login(page);
  return state;
}

async function refreshAvailableImportPages(page) {
  const response=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/import/inbox');
  await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await response;
}

test('closed import and new background PDFs share the explicit available pages entry',async({page})=>{
  const state=await mockAvailableImportPages(page,3);
  await page.getByRole('button',{name:'Importieren – 3 verfügbare Seiten',exact:true}).click();
  await page.getByRole('button',{name:'3 verfügbare Seiten öffnen',exact:true}).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  state.extraCount=2;await refreshAvailableImportPages(page);
  await page.getByRole('button',{name:'Importieren – 5 verfügbare Seiten',exact:true}).click();
  const available=page.getByRole('button',{name:'5 verfügbare Seiten öffnen',exact:true});
  await expect(available).toBeVisible();await refreshAvailableImportPages(page);
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
  await available.click();await expect(page.locator('.isd-page-card')).toHaveCount(5);
  expect(state.mutations).toEqual([]);
});

test('a new scan stays separate from the closed import and replaces only that saved draft on close',async({page})=>{
  const state=await mockAvailableImportPages(page,3);
  await page.getByRole('button',{name:'Importieren – 3 verfügbare Seiten',exact:true}).click();
  await page.getByRole('button',{name:'3 verfügbare Seiten öffnen',exact:true}).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await page.getByRole('button',{name:'Importieren – 3 verfügbare Seiten',exact:true}).click();
  await expect(page.getByRole('button',{name:'3 verfügbare Seiten öffnen',exact:true})).toBeVisible();
  state.scanning=true;await refreshAvailableImportPages(page);
  state.extraCount=2;state.scanning=false;await refreshAvailableImportPages(page);
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
  await expect(page.locator('.import-availability-badge .v-badge__badge')).toHaveText('5');
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await expect.poll(()=>state.discardedIds).toEqual(['available-pdf']);
  await page.getByRole('button',{name:'Importieren – 2 verfügbare Seiten',exact:true}).click();
  await page.getByRole('button',{name:'2 verfügbare Seiten öffnen',exact:true}).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
});

test('available background PDFs show an import badge and load only through the third source choice',async({page})=>{
  const state=await mockAvailableImportPages(page,3);
  const badge=page.locator('.import-availability-badge .v-badge__badge');
  const trigger=page.getByRole('button',{name:'Importieren – 3 verfügbare Seiten',exact:true});
  await expect(badge).toHaveText('3');await trigger.click();
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  const available=page.getByRole('button',{name:'3 verfügbare Seiten öffnen',exact:true});
  await expect(available).toBeVisible();
  await expect(page.locator('.isd-dropzone__actions > button strong')).toHaveText(['Scannen','PDFs auswählen','Verfügbare Seiten']);
  await refreshAvailableImportPages(page);
  await expect(available).toBeVisible();await expect(page.locator('.isd-page-card')).toHaveCount(0);
  const availableRect=await available.boundingBox();
  const scrollRect=await page.locator('.isd-grid-scroll').boundingBox();
  expect(availableRect.y+availableRect.height).toBeLessThanOrEqual(scrollRect.y+scrollRect.height);
  await page.screenshot({path:'/private/tmp/papermind-available-import-pages-light.png',animations:'disabled'});
  await page.emulateMedia({colorScheme:'dark'});
  await expect(page.locator('.isd-card')).toHaveClass(/v-theme--dark/);
  await page.screenshot({path:'/private/tmp/papermind-available-import-pages-dark.png',animations:'disabled'});
  await available.click();await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await expect(page.locator('.isd-dropzone')).toHaveCount(0);await expect(badge).toHaveText('3');
  expect(state.mutations).toEqual([]);
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await expect(badge).toHaveText('3');expect(state.mutations).toEqual([]);
  await trigger.click();await expect(available).toBeVisible();
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
  await available.click();await expect(page.locator('.isd-page-card')).toHaveCount(3);
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await page.reload();await expect(badge).toHaveText('3');
  await trigger.click();await expect(available).toBeVisible();
  await available.click();await expect(page.locator('.isd-page-card')).toHaveCount(3);
  expect(state.mutations).toEqual([]);
});

test('background page availability updates while the empty import is open and stale pages disappear',async({page})=>{
  const state=await mockAvailableImportPages(page,0);
  await page.getByRole('button',{name:'Importieren',exact:true}).click();
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  await expect(page.locator('.isd-dropzone__available-pages')).toHaveCount(0);
  state.count=1;await refreshAvailableImportPages(page);
  const available=page.getByRole('button',{name:'1 verfügbare Seite öffnen',exact:true});
  await expect(available).toBeVisible();await expect(available).toContainText('1 Seite wartet auf den Import');
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
  state.count=0;await available.click();
  await expect(page.locator('.isd-dropzone__available-pages')).toHaveCount(0);
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  await expect(page.locator('.import-availability-badge .v-badge__badge')).toBeHidden();
  expect(state.mutations).toEqual([]);
});

test('pages from an active scan still arrive directly in the open import',async({page})=>{
  const state=await mockAvailableImportPages(page,0);
  await page.getByRole('button',{name:'Importieren',exact:true}).click();
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  state.scanning=true;await refreshAvailableImportPages(page);
  state.count=2;state.scanning=false;await refreshAvailableImportPages(page);
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
  await expect(page.locator('.isd-dropzone')).toHaveCount(0);
  expect(state.mutations).toEqual([]);
});

test('a failed background page request leaves the source choice retryable and closing preserves the inbox',async({page})=>{
  const state=await mockAvailableImportPages(page,2);
  await page.getByRole('button',{name:'Importieren – 2 verfügbare Seiten',exact:true}).click();
  const available=page.getByRole('button',{name:'2 verfügbare Seiten öffnen',exact:true});
  await expect(available).toBeVisible();state.failure=true;
  const failed=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/import/inbox'&&response.status()===503);
  await available.click();await failed;await expect(available).toBeEnabled();await expect(available).toHaveAttribute('aria-busy','false');
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);expect(state.mutations).toEqual([]);
  state.failure=false;await page.getByRole('button',{name:'Importieren – 2 verfügbare Seiten',exact:true}).click();
  await page.getByRole('button',{name:'2 verfügbare Seiten öffnen',exact:true}).click();
  await expect(page.locator('.isd-page-card')).toHaveCount(2);
});

test('closing the import during a background page request does not reopen it',async({page})=>{
  await mockAvailableImportPages(page,2);
  const trigger=page.getByRole('button',{name:'Importieren – 2 verfügbare Seiten',exact:true});
  await trigger.click();
  const available=page.getByRole('button',{name:'2 verfügbare Seiten öffnen',exact:true});
  await expect(available).toBeVisible();
  let heldRequest;
  const holdRequest=route=>{heldRequest=route;};
  await page.route('**/api/import/inbox?*',holdRequest);
  await available.click();await expect.poll(()=>Boolean(heldRequest)).toBe(true);
  await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await expect(page.locator('.isd-card')).toHaveCount(0);
  const response=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/import/inbox');
  await heldRequest.fallback();await (await response).finished();
  await page.unroute('**/api/import/inbox?*',holdRequest);
  // Wait for the request handler and Vue update to finish, then reopen manually.
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await expect(page.locator('.isd-card')).toHaveCount(0);
  await trigger.click();await expect(available).toBeVisible();
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
});

for(const width of [430,320]) test(`available pages stay reachable on the import start screen at ${width}px`,async({page})=>{
  await mockAvailableImportPages(page,4);
  await page.getByRole('button',{name:'Importieren – 4 verfügbare Seiten',exact:true}).click();
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  await page.setViewportSize({width,height:900});
  const available=page.getByRole('button',{name:'4 verfügbare Seiten öffnen',exact:true});
  await available.scrollIntoViewIfNeeded();await expect(available).toBeVisible();
  const rect=await available.boundingBox();expect(rect.x).toBeGreaterThanOrEqual(0);expect(rect.x+rect.width).toBeLessThanOrEqual(width);expect(rect.height).toBeGreaterThanOrEqual(44);
  await available.click();await expect(page.locator('.isd-page-card')).toHaveCount(4);
});
