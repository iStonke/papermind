import { expect, test } from '@playwright/test';

const docId = '10000000-0000-4000-8000-000000000001';
const user = { id: '20000000-0000-4000-8000-000000000001', username: 'review', is_admin: true, is_active: true };

async function mockApi(page) {
  let loggedIn = false;
  const patches = [];
  const imports = [];
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
    if (path === '/api/settings') return json({ ui: { start_view: 'all', drawer_remember_state: true }, retention: { enabled: false } });
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
  expect(errors).toEqual([]);
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
