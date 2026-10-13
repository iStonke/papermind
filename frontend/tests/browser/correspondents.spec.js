import { expect, test } from '@playwright/test';

const clubId = '30000000-0000-4000-8000-000000000001';
const utilityId = '30000000-0000-4000-8000-000000000002';

async function prepareWorkspace(page, { failUtilityOnce = false, themeMode = 'light', reorderDetailTags = false, includeUntyped = false } = {}) {
  const user = { id: '20000000-0000-4000-8000-000000000001', username: 'review', is_admin: true, is_active: true };
  let loggedIn = false;
  const requests = [];
  const makeDocument = (index, extra = {}) => ({
    id: `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
    display_name: `Beitragsbescheinigung ${index}`, original_filename: `Beitrag-${index}.pdf`,
    document_date: new Date(Date.UTC(2026, 8, index)).toISOString().slice(0, 10),
    document_type: 'Bescheinigung', correspondent_id: clubId, correspondent_name: 'Kieler Männer-Turnverein',
    tags: [], is_unread: false, is_favorite: false, is_deleted: false,
    status: 'ready', ocr_status: 'not_started', text_source: 'none', embedding_status: 'not_started',
    notes: '', files: [], jobs: [], flags: {}, page_count: 0,
    created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z', ...extra,
  });
  const documents = Array.from({ length: 52 }, (_, index) => makeDocument(index + 1, { is_unread: index === 0 }));
  const utility = makeDocument(53, {
    display_name: 'Jahresabrechnung Strom', correspondent_id: utilityId, correspondent_name: 'Stadtwerke Leipzig',
    document_type: 'Rechnung', document_date: '2026-05-20',
    tags: ['Tanzschule', 'Jugend-Grundkurs', 'Zahlung'].map((name, index) => ({
      id: `40000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`, name,
    })),
  });
  documents.push(utility, makeDocument(54, { display_name: 'Garantiebeleg Kaffeemaschine', document_type: 'Beleg', correspondent_id: null, correspondent_name: null, document_date: null }));
  if (includeUntyped) documents.push(makeDocument(55, {
    display_name: 'Dokument ohne Typ', document_type: null, correspondent_id: utilityId,
    correspondent_name: 'Stadtwerke Leipzig', document_date: '2025-03-01',
  }));
  const tokens = () => ({ user,
    access_token: `test.${Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url')}.test`,
    token_type: 'bearer', expires_in: 3600,
  });
  await page.route('**/api/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (!path.startsWith('/api/')) return route.continue();
    const params = url.searchParams;
    const json = body => route.fulfill({ json: body });
    if (path === '/api/auth/login') { loggedIn = true; return json(tokens()); }
    if (path === '/api/auth/me') return loggedIn ? json(user) : route.fulfill({ status: 401, json: {} });
    if (path === '/api/auth/refresh' || path === '/api/auth/renew') return loggedIn ? json(tokens()) : route.fulfill({ status: 401, json: {} });
    if (path === '/api/auth/file-token') return json({ token: 'file-token', expires_in: 300 });
    if (path === '/api/settings') return json({ ui: { start_view: 'all', drawer_remember_state: true, theme_mode: themeMode }, retention: { enabled: false } });
    if (path === '/api/documents') {
      requests.push(Object.fromEntries(params));
      let matches = documents.filter(doc => {
        if (params.get('correspondent_id') && doc.correspondent_id !== params.get('correspondent_id')) return false;
        if (params.get('without_correspondent') === 'true' && doc.correspondent_id) return false;
        if (params.get('document_type') && String(doc.document_type || '').trim().toLowerCase() !== params.get('document_type').trim().toLowerCase()) return false;
        if (params.get('without_document_type') === 'true' && String(doc.document_type || '').trim()) return false;
        const q = String(params.get('q') || '').toLocaleLowerCase('de-DE');
        const searchValue = params.get('search_scope') === 'correspondent' ? doc.correspondent_name || ''
          : params.get('search_scope') === 'title' ? doc.display_name
            : params.get('search_scope') === 'document_type' ? doc.document_type || ''
            : params.get('search_scope') === 'year' ? String(doc.document_date || '').slice(0, 4)
            : `${doc.display_name} ${doc.correspondent_name || ''}`;
        if (q && !searchValue.toLocaleLowerCase('de-DE').includes(q)) return false;
        return true;
      }).sort((a, b) => String(b.document_date || '').localeCompare(a.document_date || ''));
      if (failUtilityOnce && params.get('correspondent_id') === utilityId) {
        failUtilityOnce = false;
        return route.fulfill({ status: 503, json: { error: { message: 'Vorübergehend nicht verfügbar' } } });
      }
      const groups = [];
      if (params.get('include_correspondent_groups') === 'true') {
        for (const doc of matches) {
          let group = groups.find(entry => entry.correspondent_id === doc.correspondent_id);
          if (!group) {
            group = { correspondent_id: doc.correspondent_id, name: doc.correspondent_name, short_name: doc.correspondent_id === clubId ? 'KMTV' : null, kind: doc.correspondent_id ? 'organization' : null, count: 0 };
            groups.push(group);
          }
          group.count += 1;
        }
      }
      const offset = Number(params.get('offset') || 0);
      const limit = Number(params.get('limit') || 50);
      const typeGroups = [];
      if (params.get('include_document_type_groups') === 'true') {
        for (const doc of matches) {
          const name = String(doc.document_type || '').trim() || null;
          let group = typeGroups.find(entry => (entry.document_type || '').toLowerCase() === (name || '').toLowerCase());
          if (!group) { group = { document_type: name, count: 0 }; typeGroups.push(group); }
          group.count += 1;
        }
      }
      return json({ items: matches.slice(offset, offset + limit), total: params.get('include_total') === 'false' ? null : matches.length,
        offset, limit, correspondent_groups: params.get('include_correspondent_groups') === 'true' ? groups : null,
        document_type_groups: params.get('include_document_type_groups') === 'true' ? typeGroups : null });
    }
    const doc = documents.find(entry => path === `/api/documents/${entry.id}`);
    if (doc) return json(reorderDetailTags ? { ...doc, tags: [...doc.tags].reverse() } : doc);
    const viewed = documents.find(entry => path === `/api/documents/${entry.id}/mark-viewed`);
    if (viewed) { viewed.is_unread = false; return json({ ok: true }); }
    if (path === '/api/sidebar/counts') return json({ all_documents: 54, total_count: 54, all_count: 54 });
    if (path === '/api/correspondents') return json({ items: [
      { id: clubId, name: 'Kieler Männer-Turnverein', short_name: 'KMTV' },
      { id: utilityId, name: 'Stadtwerke Leipzig' },
    ] });
    if (path.endsWith('/statuses')) return json({ items: [] });
    if (path.startsWith('/api/notes') || ['/api/tags', '/api/document-types', '/api/saved-searches', '/api/smart-folders', '/api/scanners'].includes(path)) return json([]);
    if (path.includes('/annotations')) return json([]);
    if (path.endsWith('/events')) return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' });
    return json({});
  });
  await page.goto('/login');
  await page.getByLabel('Benutzername oder E-Mail').fill('review');
  await page.getByLabel('Passwort', { exact: true }).fill('password');
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.getByRole('button', { name: 'Darstellung: Liste. Ändern', exact: true }).click();
  await expect(page.getByRole('menuitemradio')).toHaveCount(4);
  await expect(page.getByRole('menuitemradio', { name: 'Kalender', exact: true })).toHaveCount(0);
  await page.getByRole('menuitemradio', { name: 'Korrespondenten', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Korrespondent', exact: true })).toBeVisible();
  await expect(page.locator('.doc-groups__group')).toHaveCount(3);
  return { requests, utility };
}

test('document type view has complete counts, pagination, animated groups and correspondent metadata', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const { requests } = await prepareWorkspace(page, { includeUntyped: true, reorderDetailTags: true });
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Dokumenttyp', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Dokumenttyp', exact: true })).toBeVisible();
  const groups = page.locator('.doc-groups__group');
  await expect(groups.locator('.doc-groups__name')).toHaveText(['Beleg', 'Bescheinigung', 'Rechnung', 'Ohne Dokumenttyp']);
  await expect(groups.locator('.doc-groups__count')).toHaveText(['1 Dokument', '52 Dokumente', '1 Dokument', '1 Dokument']);
  const certificates = groups.nth(1);
  await certificates.locator('.doc-groups__heading').click();
  expect(await certificates.locator('.doc-groups__reveal').evaluate(element =>
    element.getAnimations().some(animation => animation.transitionProperty === 'grid-template-rows')
  )).toBe(true);
  await expect(certificates.locator('.doc-groups__document')).toHaveCount(50);
  await expect(certificates.locator('.doc-groups__title').first()).toHaveText('Beitragsbescheinigung 52');
  await expect(certificates.locator('.doc-groups__type').first()).toHaveText('Kieler Männer-Turnverein');
  await certificates.getByRole('button', { name: 'Weitere Dokumente laden', exact: true }).click();
  await expect(certificates.locator('.doc-groups__document')).toHaveCount(52);
  expect(requests.some(request => request.document_type === 'Bescheinigung' && request.offset === '50')).toBe(true);
  await certificates.locator('.doc-groups__document').last().click();
  await expect(certificates.locator('.doc-groups__document').last()).toHaveAttribute('aria-pressed', 'true');
  await expect(certificates.locator('.doc-groups__unread')).toHaveCount(0);
  await expect(certificates.locator('.doc-groups__document')).toHaveCount(52);
  await certificates.locator('.doc-groups__heading').click();
  await expect(certificates.locator('.doc-groups__reveal')).toHaveJSProperty('inert', true);
  const invoice = groups.nth(2);
  await invoice.locator('.doc-groups__heading').click();
  await expect(invoice.locator('.doc-groups__type')).toHaveText('Stadtwerke Leipzig');
  await expect(invoice.locator('.doc-groups__tag')).toHaveText(['Jugend-Grundkurs', 'Tanzschule']);
  await invoice.locator('.doc-groups__document').click();
  await expect(page.locator('.details-drawer__subtitle')).toContainText('Jahresabrechnung Strom');
  await expect(invoice.locator('.doc-groups__tag')).toHaveText(['Jugend-Grundkurs', 'Tanzschule']);
  await page.screenshot({ path: testInfo.outputPath('document-types-desktop.png') });
  expect(errors).toEqual([]);
});

test('document type view remembers groups separately and supports type search, untyped documents and narrow columns', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const { requests } = await prepareWorkspace(page, { includeUntyped: true, themeMode: 'dark' });
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Dokumenttyp', exact: true }).click();
  const group = name => page.locator('.doc-groups__group').filter({ has: page.locator('.doc-groups__name', { hasText: name }) });
  const invoice = group('Rechnung');
  const untyped = group('Ohne Dokumenttyp');
  await invoice.locator('.doc-groups__heading').click();
  await untyped.locator('.doc-groups__heading').click();
  await expect(untyped.locator('.doc-groups__title')).toHaveText('Dokument ohne Typ');
  await expect(untyped.locator('.doc-groups__full-name')).toHaveText('Typ noch nicht zugeordnet');
  expect(requests.some(request => request.without_document_type === 'true')).toBe(true);
  expect(await invoice.locator('.doc-groups__reveal').evaluate(element => element.getAnimations().length)).toBe(0);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Darstellung: Dokumenttyp. Ändern', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Suchfeld: Dokumenttyp', exact: true })).toBeVisible();
  await expect(invoice.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await expect(untyped.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  const search = page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true });
  await search.fill('Rechnung');
  await expect(page.locator('.doc-groups__group')).toHaveCount(1);
  await expect.poll(() => requests.filter(request => request.q === 'Rechnung').at(-1)?.search_scope).toBe('document_type');
  await expect(invoice.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await search.fill('');
  await expect(page.locator('.doc-groups__group')).toHaveCount(4);
  await expect(untyped.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await page.getByRole('button', { name: 'Darstellung: Dokumenttyp. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Korrespondenten', exact: true }).click();
  await expect(group('Ohne Korrespondent').locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Dokumenttyp', exact: true }).click();
  await expect(untyped.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await page.locator('.doc-groups').screenshot({ path: testInfo.outputPath('document-types-dark.png') });
  await page.locator('.doc-groups').evaluate(element => { element.style.width = '320px'; });
  expect(await page.locator('.doc-groups').evaluate(element => element.scrollWidth > element.clientWidth)).toBe(false);
  await page.locator('.doc-groups').screenshot({ path: testInfo.outputPath('document-types-narrow.png') });
  await invoice.locator('.doc-groups__heading').click();
  await page.reload();
  await expect(invoice.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'false');
  await expect(untyped.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
});

test('correspondent view has complete groups, paged documents, keyboard toggles and opens documents beyond the list page', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const { requests, utility } = await prepareWorkspace(page);
  const groups = page.locator('.doc-groups__group');
  await expect(groups.locator('.doc-groups__name')).toHaveText(['KMTV', 'Stadtwerke Leipzig', 'Ohne Korrespondent']);
  await expect(groups.locator('.doc-groups__kind')).toHaveText(['Organisation', 'Organisation']);
  const club = groups.nth(0);
  await expect(club.locator('.doc-groups__count')).toContainText('52 Dokumente');
  await expect(club.locator('.doc-groups__documents')).toBeHidden();
  await club.locator('.doc-groups__heading').click();
  await expect(club.locator('.doc-groups__document')).toHaveCount(50);
  await expect(club.locator('.doc-groups__title').first()).toHaveText('Beitragsbescheinigung 52');
  await club.getByRole('button', { name: 'Weitere Dokumente laden', exact: true }).click();
  await expect(club.locator('.doc-groups__document')).toHaveCount(52);
  expect(requests.some(request => request.correspondent_id === clubId && request.offset === '50')).toBe(true);
  await club.locator('.doc-groups__document').last().click();
  await expect(club.locator('.doc-groups__document').last()).toHaveAttribute('aria-pressed', 'true');
  await expect(club.locator('.doc-groups__unread')).toHaveCount(0);
  await expect(club.locator('.doc-groups__document')).toHaveCount(52);
  await club.locator('.doc-groups__heading').click();
  await expect(club.locator('.doc-groups__reveal')).toHaveJSProperty('inert', true);
  await expect(club.locator('.doc-groups__documents')).toBeHidden();
  await page.keyboard.press('Enter');
  expect(await club.locator('.doc-groups__reveal').evaluate(element =>
    element.getAnimations().some(animation => animation.transitionProperty === 'grid-template-rows')
  )).toBe(true);
  await expect(club.locator('.doc-groups__documents')).toBeVisible();
  await club.locator('.doc-groups__heading').click();
  const utilityGroup = groups.nth(1);
  await utilityGroup.locator('.doc-groups__heading').click();
  await utilityGroup.getByRole('button', { name: /Jahresabrechnung Strom/ }).click();
  await expect(utilityGroup.locator('.doc-groups__document')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.doc-groups__document--active')).toHaveCount(1);
  await expect(page.locator('.details-drawer__subtitle')).toContainText(utility.display_name);
  await page.screenshot({ path: testInfo.outputPath('correspondents-desktop.png') });
  await page.locator('.doc-groups__body').screenshot({ path: testInfo.outputPath('correspondents-cards.png') });
  await page.reload();
  await expect(page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true })).toBeVisible();
  await expect(utilityGroup.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await expect(utilityGroup.locator('.doc-groups__document')).toHaveCount(1);
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Liste', exact: true }).click();
  await expect(page.locator('.document-list__rows')).toBeVisible();
  expect(errors).toEqual([]);
});

test('a saved calendar preference falls back to the list and the timeline defaults to year search', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { requests } = await prepareWorkspace(page);
  await page.evaluate(() => localStorage.setItem('pm.documentViewMode', 'calendar'));
  await page.reload();
  await expect(page.locator('.document-list__rows')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Darstellung: Liste. Ändern', exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('pm.documentViewMode'))).toBe('list');
  await page.getByRole('button', { name: 'Darstellung: Liste. Ändern', exact: true }).click();
  await expect(page.getByRole('menuitemradio')).toHaveText(['Liste', 'Zeitleiste', 'Korrespondenten', 'Dokumenttyp']);
  await page.getByRole('menuitemradio', { name: 'Zeitleiste', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Jahr', exact: true })).toBeVisible();
  await expect(page.locator('.doc-timeline')).toBeVisible();
  await expect(page.locator('.doc-timeline__item').first()).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Darstellung: Zeitleiste. Ändern', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Suchfeld: Jahr', exact: true })).toBeVisible();
  await expect(page.locator('.doc-timeline__item').first()).toBeVisible();
  const search = page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true });
  await search.fill('2026');
  await expect.poll(() => requests.filter(request => request.q === '2026').at(-1)?.search_scope).toBe('year');
  await expect(page.locator('.doc-timeline__item').first()).toBeVisible();
  await search.fill('2025');
  await expect.poll(() => requests.filter(request => request.q === '2025').at(-1)?.search_scope).toBe('year');
  await expect(page.locator('.doc-timeline__empty')).toBeVisible();
});

test('correspondent view defaults the search to correspondents on entry and reload', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { requests } = await prepareWorkspace(page);
  const search = page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true });
  await search.fill('Jahresabrechnung');
  await expect.poll(() => requests.filter(request => request.include_correspondent_groups === 'true'
    && request.q === 'Jahresabrechnung').at(-1)?.search_scope).toBe('correspondent');
  await expect(page.locator('.doc-groups__group')).toHaveCount(0);
  await expect(page.getByText('Keine Dokumente in dieser Auswahl', { exact: true })).toBeVisible();
  // The user can still deliberately search titles within this representation.
  await page.getByRole('button', { name: 'Suchfeld: Korrespondent', exact: true }).click();
  await page.locator('.pm-searchbar__menu .v-list-item').filter({ hasText: /^Titel$/ }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Titel', exact: true })).toBeVisible();
  await expect(page.locator('.doc-groups__group')).toHaveCount(1);
  await expect.poll(() => requests.filter(request => request.include_correspondent_groups === 'true'
    && request.q === 'Jahresabrechnung').at(-1)?.search_scope).toBe('title');
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Liste', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Alles', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Darstellung: Liste. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Korrespondenten', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Korrespondent', exact: true })).toBeVisible();
  await expect(page.locator('.doc-groups__group')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Suchfeld: Korrespondent', exact: true })).toBeVisible();
});

test('list view defaults to searching all fields on entry and reload', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { requests } = await prepareWorkspace(page);
  const search = page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true });
  await search.fill('Jahresabrechnung');
  await expect(page.getByText('Keine Dokumente in dieser Auswahl', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Liste', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Suchfeld: Alles', exact: true })).toBeVisible();
  await expect(page.locator('.document-list__rows')).toContainText('Jahresabrechnung Strom');
  await expect.poll(() => requests.filter(request => request.q === 'Jahresabrechnung').at(-1)?.search_scope || 'all').toBe('all');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Darstellung: Liste. Ändern', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Suchfeld: Alles', exact: true })).toBeVisible();
});

test('opening a document keeps its visible tags and their order stable', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page, { reorderDetailTags: true });
  const utility = page.locator('.doc-groups__group').nth(1);
  await utility.locator('.doc-groups__heading').click();
  const document = utility.locator('.doc-groups__document');
  await expect(document).toHaveCount(1);
  const tags = document.locator('.doc-groups__tag');
  const initialTags = await tags.allTextContents();
  expect(initialTags).toHaveLength(2);
  const initialTitle = await document.locator('.doc-groups__title').textContent();
  await document.click();
  await expect(page.locator('.details-drawer__subtitle')).toContainText('Jahresabrechnung Strom');
  await expect(document).toHaveAttribute('aria-pressed', 'true');
  await expect(tags).toHaveText(initialTags);
  await expect(document.locator('.doc-groups__title')).toHaveText(initialTitle);
  await page.reload();
  await expect(tags).toHaveText(initialTags);
});

test('remembers open and closed groups across view changes, searches and reloads', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const group = name => page.locator('.doc-groups__group').filter({
    has: page.locator('.doc-groups__name', { hasText: name }),
  });
  const utility = group('Stadtwerke Leipzig');
  const unassigned = group('Ohne Korrespondent');
  await utility.locator('.doc-groups__heading').click();
  await unassigned.locator('.doc-groups__heading').click();
  await expect(unassigned.locator('.doc-groups__document')).toHaveCount(1);
  await page.getByRole('button', { name: 'Darstellung: Korrespondenten. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Liste', exact: true }).click();
  await expect(page.locator('.document-list__rows')).toBeVisible();
  await page.getByRole('button', { name: 'Darstellung: Liste. Ändern', exact: true }).click();
  await page.getByRole('menuitemradio', { name: 'Korrespondenten', exact: true }).click();
  await expect(utility.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await expect(unassigned.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await expect(utility.locator('.doc-groups__document')).toHaveCount(1);
  const search = page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true });
  await search.fill('Stadtwerke');
  await expect(page.locator('.doc-groups__group')).toHaveCount(1);
  await expect(utility.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await search.fill('');
  await expect(page.locator('.doc-groups__group')).toHaveCount(3);
  await expect(unassigned.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await utility.locator('.doc-groups__heading').click();
  await page.reload();
  await expect(utility.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'false');
  await expect(unassigned.locator('.doc-groups__heading')).toHaveAttribute('aria-expanded', 'true');
  await expect(unassigned.locator('.doc-groups__document')).toHaveCount(1);
  await unassigned.locator('.doc-groups__heading').click();
  await page.reload();
  await expect(page.locator('.doc-groups__heading[aria-expanded="false"]')).toHaveCount(3);
});

test('a group can retry loading and unassigned documents stay separate', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await prepareWorkspace(page, { failUtilityOnce: true, themeMode: 'dark' });
  const utility = page.locator('.doc-groups__group').nth(1);
  await utility.locator('.doc-groups__heading').click();
  await expect(utility.getByRole('alert')).toContainText('Dokumente konnten nicht geladen werden.');
  await utility.getByRole('button', { name: 'Erneut versuchen', exact: true }).click();
  await expect(utility.locator('.doc-groups__document')).toHaveCount(1);
  const unassigned = page.locator('.doc-groups__group').last();
  await unassigned.locator('.doc-groups__heading').click();
  await expect(unassigned.locator('.doc-groups__title')).toHaveText('Garantiebeleg Kaffeemaschine');
  await page.locator('.doc-groups').screenshot({ path: testInfo.outputPath('correspondents-dark.png') });
});

test('search narrows groups and narrow view has no horizontal overflow', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await prepareWorkspace(page);
  await page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true }).fill('Stadtwerke');
  await expect(page.locator('.doc-groups__group')).toHaveCount(1);
  await expect(page.locator('.doc-groups__name')).toHaveText('Stadtwerke Leipzig');
  await page.locator('.doc-groups__heading').click();
  await expect(page.locator('.doc-groups__document')).toHaveCount(1);
  expect(await page.locator('.doc-groups__reveal').evaluate(element => element.getAnimations().length)).toBe(0);
  // Exercise the narrow list column independently of the desktop workspace shell.
  await page.locator('.doc-groups').evaluate(element => { element.style.width = '320px'; });
  expect(await page.locator('.doc-groups').evaluate(element => element.clientWidth)).toBe(320);
  const overflow = await page.locator('.doc-groups').evaluate(element => element.scrollWidth > element.clientWidth);
  expect(overflow).toBe(false);
  await page.locator('.doc-groups').screenshot({ path: testInfo.outputPath('correspondents-narrow.png') });
});
