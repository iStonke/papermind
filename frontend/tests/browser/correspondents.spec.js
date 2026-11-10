import { expect, test } from '@playwright/test';
import { syntheticDocumentPdf } from './fixtures/syntheticDocumentPdf.js';

const clubId = '30000000-0000-4000-8000-000000000001';
const utilityId = '30000000-0000-4000-8000-000000000002';

function collectApplicationErrors(page) {
  const errors = [];
  page.on('pageerror', error => {
    if (error.message === 'WebSocket closed without opened.' && error.stack?.includes('/@vite/client:')) return;
    errors.push(error.message);
  });
  return errors;
}

async function prepareWorkspace(page, { failUtilityOnce = false, themeMode = 'light', reorderDetailTags = false, includeUntyped = false } = {}) {
  await page.addInitScript(() => localStorage.setItem('pm.dev.preferences.v1', JSON.stringify({ showOnboardingLauncher: false })));
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
  const errors = collectApplicationErrors(page);
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
  const errors = collectApplicationErrors(page);
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

test('the document search shows and clears the exact filter opened from a correspondent profile', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { requests } = await prepareWorkspace(page);
  const correspondent = { id: utilityId, name: 'Stadtwerke Leipzig', kind: 'organization', usage_count: 1 };
  const member = { id: '30000000-0000-4000-8000-000000000003', name: 'Alex Bauer', kind: 'person', parent_id: utilityId };
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: [correspondent, member] } }));
  await page.route(`**/api/correspondents/${utilityId}/profile`, route => route.fulfill({
    json: { correspondent, document_count: 1, own_document_count: 1, members: [member], activity: [], relations: [] },
  }));

  const search = page.getByRole('textbox', { name: 'Diese Dokumentliste durchsuchen', exact: true });
  const chip = page.getByRole('search').getByRole('button', { name: 'Korrespondentenfilter entfernen: Stadtwerke Leipzig', exact: true });
  const groups = page.locator('.doc-groups__name');

  async function openFilteredDocuments() {
    await page.locator('.sidebar-item--correspondents').click();
    const workspace = page.locator('.panel-correspondents');
    await workspace.getByRole('tree').getByText('Stadtwerke Leipzig', { exact: true }).click();
    await workspace.getByRole('button', { name: 'In Dokumenten zeigen', exact: true }).click();
    await expect(chip).toBeVisible();
    await expect(search).toHaveValue('');
    await expect(groups).toHaveText(['Stadtwerke Leipzig']);
  }

  await openFilteredDocuments();
  expect(requests.some(request => request.correspondent_id === utilityId && request.correspondent_members === 'true' && !request.q)).toBe(true);
  const header = page.locator('.panel-middle__header').filter({ has: search });
  await expect(header.locator('.panel-middle__count')).toHaveText('1 Treffer');
  await expect(header.locator('.panel-middle__scope')).toHaveCount(0);
  expect(await chip.locator('span').evaluate(label => label.scrollWidth <= label.clientWidth)).toBe(true);
  const scopeButton = header.getByRole('button', { name: /^Suchfeld:/ });
  await scopeButton.click();
  await page.getByText('Nur direkt zugeordnete Dokumente', { exact: true }).click();
  await expect.poll(() => requests.some(request => request.correspondent_id === utilityId && !request.correspondent_members)).toBe(true);
  await search.fill('Stadtwerke');
  await expect.poll(() => requests.some(request => request.q === 'Stadtwerke' && request.correspondent_id === utilityId)).toBe(true);
  await scopeButton.click();
  await page.getByText(/^Alle Dokumente durchsuchen/).click();
  await expect(chip).toHaveCount(0);
  await scopeButton.click();
  await page.getByText(/^Nur in „Stadtwerke Leipzig/).click();
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(chip).toHaveCount(0);
  await expect(search).toHaveValue('Stadtwerke');
  await expect.poll(() => requests.some(request => request.q === 'Stadtwerke' && !request.correspondent_id)).toBe(true);
  await search.clear();
  await expect(groups).toHaveCount(3);

  await openFilteredDocuments();
  await search.press('Backspace');
  await expect(chip).toHaveCount(0);
  await expect(groups).toHaveCount(3);
});

test('profile documents scroll horizontally, load the next page and open in the document preview', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { requests, utility } = await prepareWorkspace(page);
  Object.assign(utility, { amount: '42.00', currency: 'EUR' });
  const correspondents = [
    { id: clubId, name: 'Kieler Männer-Turnverein', kind: 'organization', usage_count: 52 },
    { id: utilityId, name: 'Stadtwerke Leipzig', kind: 'organization', usage_count: 1 },
    { id: 'energy', name: 'Energie', kind: 'collection', usage_count: 0 },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: correspondents } }));
  for (const correspondent of correspondents) {
    await page.route(`**/api/correspondents/${correspondent.id}/profile`, route => route.fulfill({ json: {
      correspondent, document_count: correspondent.usage_count, own_document_count: correspondent.usage_count,
      members: [], activity: [], relations: [],
    } }));
  }
  let failNextPage = true;
  await page.route('**/api/documents?*', route => {
    const params = new URL(route.request().url()).searchParams;
    if (failNextPage && params.get('correspondent_id') === clubId && params.get('offset') === '12') {
      failNextPage = false;
      return route.fulfill({ status: 503, json: {} });
    }
    return route.fallback();
  });

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  const tree = workspace.getByRole('tree');
  await tree.getByText('Kieler Männer-Turnverein', { exact: true }).click();
  const rail = workspace.getByRole('list', { name: 'Dokumente von Kieler Männer-Turnverein' });
  await expect(rail.getByRole('listitem')).toHaveCount(12);
  // Eine Reihe: die vierte Karte steht rechts neben der ersten, nicht darunter.
  const [first, fourth] = await Promise.all([rail.getByRole('listitem').first().boundingBox(), rail.getByRole('listitem').nth(3).boundingBox()]);
  expect(Math.abs(fourth.y - first.y)).toBeLessThan(6);
  expect(fourth.x).toBeGreaterThan(first.x + first.width);
  await rail.evaluate(list => { list.scrollLeft = list.scrollWidth; });
  const error = workspace.getByRole('status').filter({ hasText: 'Weitere Dokumente konnten nicht geladen werden.' });
  await expect(error).toBeVisible();
  await expect(rail.getByRole('listitem')).toHaveCount(12);
  await error.getByRole('button', { name: 'Erneut versuchen' }).click();
  await expect(rail.getByRole('listitem')).toHaveCount(24);
  expect(requests.some(request => request.correspondent_id === clubId && request.correspondent_members === 'true'
    && request.sort === 'correspondent_date' && request.offset === '12')).toBe(true);
  await expect(workspace.getByRole('button', { name: 'Alle 52 anzeigen' })).toBeVisible();

  await tree.getByText('Stadtwerke Leipzig', { exact: true }).click();
  const grid = workspace.getByRole('list', { name: 'Dokumente von Stadtwerke Leipzig' });
  await expect(grid.getByRole('listitem')).toHaveCount(1);
  const documentCard = grid.getByRole('button', { name: /^Jahresabrechnung Strom/ });
  await expect(documentCard.getByText('Rechnung', { exact: true })).toHaveCSS('border-top-style', 'solid');
  await expect(documentCard.getByText('20.05.2026')).toBeVisible();
  await expect(documentCard).not.toContainText('42,00');
  expect(await grid.evaluate(list => list.scrollLeft)).toBe(0);
  // Ein einzelnes Dokument nimmt wie zwei oder drei ein Drittel der Reihe ein.
  const railWidth = (await grid.boundingBox()).width;
  expect((await grid.getByRole('listitem').first().boundingBox()).width).toBeCloseTo((railWidth - 24) / 3, 0);

  // Sammlungen zeigen statt des Dokumentrasters Mitglieder-Kacheln.
  await tree.getByText('Energie', { exact: true }).click();
  await expect(workspace.getByRole('heading', { name: 'Energie', exact: true })).toBeVisible();
  await expect(workspace.getByRole('region', { name: 'Dokumente', exact: true })).toHaveCount(0);
  await expect(workspace.getByRole('list', { name: 'Mitglieder von Energie' })).toBeVisible();
  await expect(workspace.getByRole('button', { name: 'Mitglied hinzufügen', exact: true })).toBeVisible();

  // Ein Klick auf eine Dokumentkachel (Lupe) öffnet eine große Vorschau als Overlay – nicht im Dokumentbereich.
  await tree.getByText('Stadtwerke Leipzig', { exact: true }).click();
  const tileButton = grid.getByRole('button', { name: 'Jahresabrechnung Strom groß anzeigen' });
  await expect(tileButton).toHaveCSS('cursor', 'zoom-in');
  await tileButton.click();
  const overlay = page.getByRole('region', { name: 'Vorschau: Jahresabrechnung Strom' });
  await expect(overlay).toBeVisible();
  await expect(page.locator('.details-drawer__subtitle')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(overlay).toHaveCount(0);
  await expect(tileButton).toBeFocused();
});

test('alias and note placeholders expand to solid borders, and saved notes keep their border', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const correspondent = { id: utilityId, name: 'Stadtwerke Leipzig', kind: 'organization', aliases: [{ id: 'utility-alias', alias: 'SW Leipzig' }] };
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: [correspondent] } }));
  await page.route(`**/api/correspondents/${utilityId}/profile`, route => route.fulfill({
    json: { correspondent, document_count: 0, own_document_count: 0, members: [], activity: [], relations: [] },
  }));
  await page.route(`**/api/correspondents/${utilityId}`, route => {
    Object.assign(correspondent, route.request().postDataJSON());
    return route.fulfill({ json: correspondent });
  });

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  await workspace.getByRole('tree').getByText('Stadtwerke Leipzig', { exact: true }).click();
  const aliasButton = workspace.getByRole('button', { name: 'Alias hinzufügen', exact: true });
  const noteButton = workspace.getByRole('button', { name: 'Notiz hinzufügen', exact: true });

  async function expectResize(selector, dimensions, action, grows = false) {
    const animation = page.waitForFunction(({ selector, dimensions, grows }) => {
      const field = document.querySelector(selector);
      if (!field || getComputedStyle(field).borderTopStyle !== (grows ? 'solid' : 'dashed')) return false;
      const animations = field.getAnimations();
      if (animations.some(animation => animation.animationName === 'pm-inline-add-in')) return false;
      return animations.some(animation => {
        const [start, end] = animation.effect.getKeyframes();
        return dimensions.every(dimension => grows
          ? parseFloat(end[dimension]) > parseFloat(start[dimension])
          : parseFloat(end[dimension]) < parseFloat(start[dimension]));
      });
    }, { selector, dimensions, grows }, { timeout: 3000 });
    await Promise.all([animation, action()]);
  }

  await expect(aliasButton).toHaveCSS('border-top-style', 'dashed');
  await expectResize('.pm-recog__add', ['width'], () => aliasButton.click(), true);
  const aliasInput = workspace.getByRole('textbox', { name: 'Weiteren Alias hinzufügen' });
  await expect(aliasInput).toBeFocused();
  await aliasInput.evaluate(input => Promise.all(input.form.getAnimations().map(animation => animation.finished)));
  await expectResize('.pm-recog__action', ['width'], () => workspace.getByRole('heading', { name: 'Aliase' }).click());
  await expect(aliasInput).toHaveCount(0);
  await expect(aliasButton).toBeVisible();

  const notePlaceholderWidth = (await noteButton.boundingBox()).width;
  await expect(noteButton).toHaveCSS('border-top-style', 'dashed');
  await expectResize('.corr-note--input', ['width', 'height'], () => noteButton.click(), true);
  const noteInput = workspace.getByRole('textbox', { name: 'Notiz zum Korrespondenten' });
  await expect(noteInput).toBeFocused();
  await noteInput.evaluate(input => Promise.all(input.getAnimations().map(animation => animation.finished)));
  const noteSection = workspace.getByRole('region', { name: 'Notiz', exact: true });
  const availableWidth = (await noteSection.boundingBox()).width;
  const initialEditorWidth = (await noteInput.boundingBox()).width;
  expect(initialEditorWidth).toBeGreaterThan(notePlaceholderWidth);
  expect(initialEditorWidth).toBeLessThan(availableWidth);
  await expectResize('.corr-note--empty', ['width', 'height'], () => noteInput.press('Escape'));
  await expect(noteInput).toHaveCount(0);
  await expect(noteButton).toBeFocused();

  const noteHeading = workspace.getByRole('heading', { name: 'Notiz', exact: true });
  await noteButton.click();
  await noteInput.evaluate(input => Promise.all(input.getAnimations().map(animation => animation.finished)));
  await noteInput.fill('LangerNotiztext'.repeat(80));
  expect((await noteInput.boundingBox()).width).toBeCloseTo(availableWidth, 0);
  expect(await noteInput.evaluate(input => input.scrollWidth - input.clientWidth)).toBeLessThanOrEqual(1);
  await noteInput.fill('Zählerstand im Dezember melden.');
  expect((await noteInput.boundingBox()).width).toBeLessThan(availableWidth);
  await noteHeading.click();
  const savedNote = workspace.getByRole('button', { name: 'Zählerstand im Dezember melden.', exact: true });
  await expect(savedNote).toHaveCSS('border-top-style', 'solid');
  const aliasBackground = await workspace.locator('.pm-recog__chip').evaluate(chip => getComputedStyle(chip).backgroundColor);
  await expect(savedNote).toHaveCSS('background-color', aliasBackground);
  await savedNote.evaluate(note => Promise.all(note.getAnimations().map(animation => animation.finished)));
  expect((await savedNote.boundingBox()).width).toBeLessThan(availableWidth);

  await savedNote.click();
  await noteInput.clear();
  await noteHeading.click();
  await expect(noteButton).toHaveCSS('border-top-style', 'dashed');
  await expect(noteButton).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
});

for (const [themeMode, fieldBackground] of [['light', 'rgb(251, 252, 253)'], ['dark', 'rgb(40, 53, 59)']]) {
  test(`the correspondent name editor uses the ${themeMode} form palette`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await prepareWorkspace(page, { themeMode });

    await page.locator('.sidebar-item--correspondents').click();
    const workspace = page.locator('.panel-correspondents');
    await workspace.getByRole('tree').getByText('Stadtwerke Leipzig', { exact: true }).click();
    await workspace.getByRole('button', { name: 'Stadtwerke Leipzig', exact: true }).click();
    const nameInput = workspace.getByRole('textbox', { name: 'Name des Korrespondenten' });
    await expect(nameInput).toBeFocused();
    await expect(nameInput).toHaveCSS('background-color', fieldBackground);
    const selection = await nameInput.evaluate(input => {
      const style = getComputedStyle(input, '::selection');
      return {
        text: input.value.slice(input.selectionStart, input.selectionEnd),
        foreground: style.color,
        background: style.backgroundColor,
        textColor: getComputedStyle(input).color,
      };
    });
    expect(selection.text).toBe('Stadtwerke Leipzig');
    expect(selection.foreground).toBe(selection.textColor);
    expect(selection.background).not.toBe('rgba(0, 0, 0, 0)');
  });
}

test('the directory handles open document assignments and only offers short names outside collections', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { utility } = await prepareWorkspace(page);
  const correspondents = [
    { id: utilityId, name: 'Stadtwerke Leipzig', kind: 'organization' },
    { id: 'energy', name: 'Energie', kind: 'collection', short_name: 'Altbestand' },
    { id: 'untyped', name: 'Unsortierter Kontakt', kind: null },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: correspondents } }));
  for (const item of correspondents) {
    await page.route(`**/api/correspondents/${item.id}/profile`, route => route.fulfill({
      json: { correspondent: item, document_count: 0, own_document_count: 0, members: [], activity: [], relations: [] },
    }));
  }
  await page.route(`**/api/correspondents/${utilityId}`, route => {
    Object.assign(correspondents[0], route.request().postDataJSON());
    return route.fulfill({ json: correspondents[0] });
  });
  const classificationUpdates = [];
  await page.route('**/api/correspondents/untyped', route => {
    const payload = route.request().postDataJSON();
    classificationUpdates.push(payload);
    Object.assign(correspondents[2], payload);
    return route.fulfill({ json: correspondents[2] });
  });
  const unassigned = [
    { document_id: 'unassigned1', title: 'Garantiebeleg', sender: 'Stadtwerke-Leipzig', document_type: 'Rechnung', document_date: '2026-05-20' },
    { document_id: 'unassignedNew', title: 'Teilnahmebestätigung', sender: 'Nordlicht Akademie' },
    { document_id: 'unassigned2', title: 'Privater Beleg' },
  ];
  const assignments = [];
  const newCorrespondents = [];
  const academy = { id: 'academy', name: 'Nordlicht Akademie' };
  await page.route('**/api/correspondents', route => {
    expect(route.request().method()).toBe('POST');
    newCorrespondents.push(route.request().postDataJSON());
    correspondents.push(academy);
    return route.fulfill({ json: academy });
  });
  await page.route('**/api/correspondents/unresolved?*', route => route.fulfill({ json: { items: unassigned } }));
  await page.route('**/api/documents/unassigned1', route => {
    expect(route.request().method()).toBe('PATCH');
    assignments.push(route.request().postDataJSON());
    unassigned.shift();
    return route.fulfill({ json: {} });
  });
  await page.route('**/api/documents/unassignedNew', route => {
    expect(route.request().method()).toBe('PATCH');
    assignments.push(route.request().postDataJSON());
    unassigned.shift();
    return route.fulfill({ json: {} });
  });
  await page.route('**/api/documents/unassigned*/file?*', route => {
    expect(new URL(route.request().url()).searchParams.get('role')).toBe('searchable');
    return route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() });
  });
  await page.route('**/api/correspondents/unresolved/unassigned2/ignore', route => {
    expect(route.request().method()).toBe('POST');
    unassigned.shift();
    return route.fulfill({ json: { ok: true } });
  });

  const utilityGroup = page.locator('.doc-groups__group').filter({ hasText: utility.correspondent_name });
  await utilityGroup.locator('.doc-groups__heading').click();
  await utilityGroup.getByRole('button', { name: /^Jahresabrechnung Strom/ }).press('Enter');
  await page.getByRole('button', { name: 'Dokumentdetails öffnen', exact: true }).click();
  const drawerMeta = page.locator('.details-drawer__meta-line');
  const drawerSpacing = await drawerMeta.evaluate(element => {
    const { columnGap, rowGap, marginTop } = getComputedStyle(element);
    const type = element.querySelector('.details-drawer__meta-part--type');
    return { columnGap, rowGap, marginTop, inset: getComputedStyle(type).paddingInlineEnd };
  });
  await page.getByRole('button', { name: 'Zu Korrespondenten wechseln', exact: true }).click();

  const workspace = page.locator('.panel-correspondents');
  await expect(workspace.getByRole('heading', { name: 'Stadtwerke Leipzig', exact: true })).toBeVisible();
  const profileMeta = workspace.locator('.corr-profile__meta');
  await expect(profileMeta).toHaveCSS('column-gap', drawerSpacing.columnGap);
  await expect(profileMeta).toHaveCSS('row-gap', drawerSpacing.rowGap);
  await expect(profileMeta).toHaveCSS('margin-top', drawerSpacing.marginTop);
  await expect(profileMeta.getByText('0 Dokumente', { exact: true })).toHaveCSS('padding-inline-end', drawerSpacing.inset);
  const affiliations = workspace.getByRole('region', { name: 'Zugehörigkeiten', exact: true });
  await expect(affiliations.getByRole('button', { name: 'Zugehörigkeit hinzufügen', exact: true })).toBeVisible();
  await expect(affiliations.getByText('Noch keine Zugehörigkeiten.')).toHaveCount(0);
  await workspace.getByRole('button', { name: 'Kurzname hinzufügen', exact: true }).click();
  const shortNameDialog = page.getByRole('dialog').filter({ has: page.getByRole('heading', { name: 'Kurzname bearbeiten' }) });
  await shortNameDialog.getByRole('textbox', { name: 'Kurzname' }).fill('SW Leipzig');
  await shortNameDialog.getByRole('button', { name: 'Speichern' }).click();
  await expect(workspace.getByRole('button', { name: 'Kurzname bearbeiten: SW Leipzig' })).toBeVisible();
  await workspace.getByRole('textbox', { name: 'Korrespondenten durchsuchen' }).fill('SW Leipzig');
  await expect(workspace.getByRole('treeitem')).toHaveCount(1);
  await workspace.getByRole('textbox', { name: 'Korrespondenten durchsuchen' }).clear();
  await workspace.getByRole('tree').getByText('Energie', { exact: true }).click();
  await expect(workspace.getByRole('heading', { name: 'Energie', exact: true })).toBeVisible();
  await expect(workspace.getByRole('button', { name: /^Kurzname/ })).toHaveCount(0);
  await expect(workspace.getByText('Altbestand', { exact: true })).toHaveCount(0);
  const members = workspace.getByRole('region', { name: 'Mitglieder', exact: true });
  await members.getByRole('button', { name: 'Mitglied hinzufügen', exact: true }).click();
  await expect(members.getByText('Noch keine Mitglieder.')).toHaveCount(0);
  const connectionMenu = page.getByRole('dialog', { name: 'Verbindung hinzufügen' });
  await expect(connectionMenu.getByRole('button', { name: /Stadtwerke Leipzig/ })).toBeVisible();
  await expect(connectionMenu.getByRole('button', { name: /Unsortierter Kontakt/ })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(connectionMenu).toBeHidden();

  const untyped = workspace.getByRole('treeitem').filter({ hasText: 'Unsortierter Kontakt' });
  await expect(untyped).toHaveAttribute('draggable', 'false');
  await untyped.click();
  const classification = workspace.getByRole('region', { name: 'Einordnung', exact: true });
  await expect(classification.getByText('Dieser Eintrag hat noch keinen Typ.')).toHaveCount(0);
  const typePlaceholder = classification.getByRole('button', { name: 'Typ festlegen', exact: true });
  await expect(typePlaceholder).toHaveCSS('border-top-style', 'dashed');
  await expect(typePlaceholder).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  const notePlaceholder = workspace.getByRole('button', { name: 'Notiz hinzufügen', exact: true });
  expect((await typePlaceholder.boundingBox()).height).toBe((await notePlaceholder.boundingBox()).height);
  expect((await typePlaceholder.boundingBox()).width).toBeLessThan((await classification.boundingBox()).width);
  await typePlaceholder.click();
  const kindDialog = page.getByRole('dialog', { name: 'Typ festlegen', exact: true });
  await kindDialog.getByRole('radio', { name: 'Organisation', exact: true }).check();
  await kindDialog.getByRole('button', { name: 'Typ übernehmen' }).click();
  await expect(classification).toHaveCount(0);
  await affiliations.getByRole('button', { name: 'Zugehörigkeit hinzufügen', exact: true }).click();
  await connectionMenu.getByRole('button', { name: 'Richtung tauschen' }).click();
  await expect(connectionMenu.getByRole('button', { name: /Stadtwerke Leipzig/ })).toHaveCount(0);
  await connectionMenu.getByRole('button', { name: /Energie/ }).click();
  const collectionTile = affiliations.getByRole('button', { name: /^Energie/ });
  await expect(collectionTile).toBeVisible();
  expect(classificationUpdates).toEqual([{ kind: 'organization' }, { parent_id: 'energy' }]);
  const addAffiliation = affiliations.getByRole('button', { name: 'Zugehörigkeit hinzufügen', exact: true });
  await expect(addAffiliation).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  expect((await addAffiliation.boundingBox()).y).toBeGreaterThan((await collectionTile.boundingBox()).y);

  await collectionTile.click();
  // Neues Mitglied ohne Dokumente: Kachel sichtbar, aber nicht aufklappbar.
  await expect(members.getByRole('listitem').filter({ hasText: 'Unsortierter Kontakt' })).toBeVisible();
  await expect(members.getByRole('button', { name: /^Unsortierter Kontakt.*aufklappen$/ })).toHaveCount(0);
  await expect(members.getByRole('button', { name: 'Zuordnung von Unsortierter Kontakt lösen' })).toBeAttached();
  const addMember = members.getByRole('button', { name: 'Mitglied hinzufügen', exact: true });
  await expect(addMember).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  await expect(addMember).toHaveCSS('border-top-style', 'dashed');

  const tree = workspace.getByRole('tree', { name: 'Korrespondenten' });
  const unassignedGroup = tree.getByRole('group', { name: 'Ohne Korrespondent', exact: true });
  await expect(tree.getByRole('group').first()).toHaveAttribute('aria-label', 'Ohne Korrespondent');
  const inboxRow = unassignedGroup.getByRole('treeitem', { name: 'Ohne Korrespondent', exact: true });
  await expect(unassignedGroup.getByRole('treeitem')).toHaveCount(1);
  await expect(inboxRow.locator('.corr-inbox__count')).toHaveText('3');
  await expect(tree.getByRole('treeitem', { name: 'Garantiebeleg', exact: true })).toHaveCount(0);
  await expect(workspace.getByRole('button', { name: 'Dokumente ohne Korrespondenten', exact: true })).toHaveCount(0);
  await inboxRow.press('Enter');
  const review = workspace.getByRole('region', { name: 'Dokumente ohne Korrespondenten', exact: true });
  await expect(tree).toBeVisible();
  await expect(inboxRow).toHaveAttribute('aria-selected', 'true');
  // Eine Seite wie „Mögliche Doppelte“: eine Karte pro Dokument, keine große Vorschau, kein Streifen.
  await expect(review.getByRole('heading', { name: 'Ohne Korrespondent', level: 1 })).toBeVisible();
  await expect(review.getByText('3 Dokumente · zuordnen', { exact: true })).toBeVisible();
  await expect(review.locator('.assign-card')).toHaveCount(3);
  await expect(review.locator('.pdf-preview')).toHaveCount(0);
  await expect(review.getByRole('listbox', { name: 'Offene Dokumente' })).toHaveCount(0);
  const garantie = review.getByRole('listitem', { name: 'Garantiebeleg', exact: true });
  await expect(garantie.getByRole('heading', { name: 'Garantiebeleg', exact: true })).toBeVisible();
  await expect(garantie.locator('.assign-card__meta')).toContainText('Rechnung');
  await expect(garantie.locator('.assign-card__meta')).toContainText('20.05.2026');
  const correspondent = garantie.getByRole('combobox', { name: 'Korrespondent', exact: true });
  const suggestionChip = garantie.getByText('Vorschlag', { exact: true });
  await expect(suggestionChip).toBeVisible();
  await correspondent.fill('Energie');
  await page.getByRole('option').filter({ hasText: 'Energie' }).click();
  await expect(suggestionChip).toHaveCount(0);
  await correspondent.fill('Stadtwerke');
  await page.getByRole('option').filter({ hasText: 'Stadtwerke Leipzig' }).click();
  await expect(suggestionChip).toBeVisible();

  await garantie.getByRole('button', { name: 'Weitere Aktionen für Garantiebeleg' }).click();
  await page.getByText('Absender als Alias übernehmen', { exact: true }).click();
  await expect(correspondent).toBeFocused();
  await expect(suggestionChip).toHaveCount(0);
  await expect(garantie.getByRole('button', { name: 'Alias übernehmen und zuordnen' })).toBeDisabled();
  await garantie.getByRole('button', { name: 'Abbrechen', exact: true }).click();
  await expect(garantie.locator('.pm-metadata-value')).toContainText('SW Leipzig');
  await expect(garantie.getByText(/Erkannter Absender|Vorschlag anhand/)).toHaveCount(0);
  await garantie.getByRole('button', { name: 'Zuordnen', exact: true }).click();
  await expect(garantie).toHaveCount(0);
  await expect(review.locator('.assign-card')).toHaveCount(2);

  const course = review.getByRole('listitem', { name: 'Teilnahmebestätigung', exact: true });
  await expect(course.locator('.pm-metadata-value')).toContainText('Nordlicht Akademie');
  await expect(course.getByText('Vorschlag', { exact: true })).toBeVisible();
  expect(newCorrespondents).toEqual([]);
  await course.getByRole('button', { name: 'Anlegen und zuordnen', exact: true }).click();
  await expect(course).toHaveCount(0);
  expect(newCorrespondents).toEqual([{ name: academy.name }]);
  const privateCard = review.getByRole('listitem', { name: 'Privater Beleg', exact: true });
  await expect(privateCard.getByText('Vorschlag', { exact: true })).toHaveCount(0);
  await expect(privateCard.getByRole('button', { name: 'Zuordnen', exact: true })).toBeDisabled();
  expect(assignments).toEqual([{ correspondent_id: utilityId }, { correspondent_id: academy.id }]);
  await expect(inboxRow.locator('.corr-inbox__count')).toHaveText('1');

  const remainingRow = inboxRow;
  await expect(remainingRow).toHaveAttribute('aria-selected', 'true');
  await page.setViewportSize({ width: 820, height: 1000 });
  await expect(tree).toBeHidden();
  await review.getByRole('button', { name: 'Korrespondenten', exact: true }).click();
  await expect(tree).toBeVisible();
  await expect(remainingRow).toBeFocused();
  await remainingRow.click();
  await expect(privateCard).toBeVisible();
  await privateCard.getByRole('button', { name: 'Weitere Aktionen für Privater Beleg' }).click();
  await page.getByText('Bewusst ohne Korrespondent', { exact: true }).click();
  await expect(review.getByRole('status')).toContainText('Keine offenen Zuordnungen.');
  await review.getByRole('button', { name: 'Korrespondenten', exact: true }).click();
  await expect(unassignedGroup).toHaveCount(0);
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

test('new correspondent detects exact aliases and can add alternative spellings', async ({ page }) => {
  await prepareWorkspace(page);
  const correspondent = { id: utilityId, name: 'Wiker Autoservice', kind: 'organization', aliases: [{ id: 'old', alias: 'Wiker Werkstatt' }] };
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: [correspondent] } }));
  await page.route(`**/api/correspondents/${utilityId}/profile`, route => route.fulfill({ json: { correspondent, document_count: 0, members: [], activity: [], relations: [] } }));
  let savedAlias;
  await page.route(`**/api/correspondents/${utilityId}/aliases`, route => {
    savedAlias = route.request().postDataJSON().alias;
    return route.fulfill({ json: { ...correspondent, aliases: [...correspondent.aliases, { id: 'new', alias: savedAlias }] } });
  });
  await page.locator('.sidebar-item--correspondents').click();
  await page.getByRole('button', { name: 'Neuer Korrespondent', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const name = dialog.getByRole('textbox', { name: 'Name', exact: true });
  await name.fill('Wiker Werkstatt');
  await expect(dialog.getByText('Dieser Name ist bereits vorhanden.', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Anlegen', exact: true })).toBeDisabled();
  const matches = dialog.getByRole('region', { name: 'Vorhandene Korrespondenten', exact: true });
  await name.fill('Wiker Autoservice GmbH');
  await expect(matches.getByText('„Wiker Autoservice“ ist bereits vorhanden – nur die Rechtsform unterscheidet sich.', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Trotzdem anlegen', exact: true })).toBeEnabled();
  await name.fill('Wiker-Auto-Service');
  await expect(matches.getByText('1 ähnlicher Eintrag vorhanden', { exact: true })).toBeVisible();
  await expect(matches.getByText('Organisation · 0 Dokumente', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Trotzdem anlegen', exact: true })).toBeEnabled();
  await expect(name).toHaveAttribute('autocomplete', 'off');
  // Safari AutoFill: no <form> that records submitted values, no contact-like field name.
  await expect(name).toHaveAttribute('name', 'pm-correspondent-search');
  await expect(dialog.locator('form')).toHaveCount(0);
  // Matches sit directly below the name in a single narrow column.
  const nameBox = await name.boundingBox();
  const matchesBox = await matches.boundingBox();
  expect(matchesBox.y).toBeGreaterThan(nameBox.y);
  expect(Math.abs(matchesBox.x - (await dialog.locator('.corr-create .v-field').first().boundingBox()).x)).toBeLessThan(2);
  expect((await dialog.locator('.corr-create-dialog').boundingBox()).width).toBeLessThanOrEqual(520);
  // Organisations can only belong to collections; without any the link stays away.
  const parentLink = dialog.getByRole('button', { name: 'Gehört zu …', exact: true });
  await expect(parentLink).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Person', exact: true }).click();
  await expect(dialog.getByRole('combobox', { name: 'Gehört zu', exact: true })).toHaveCount(0);
  await parentLink.click();
  await expect(dialog.getByRole('combobox', { name: 'Gehört zu', exact: true })).toBeVisible();
  await page.getByRole('option', { name: 'Wiker Autoservice' }).click();
  await dialog.getByRole('button', { name: 'Organisation', exact: true }).click();
  await expect(name).toHaveValue('Wiker-Auto-Service');
  await page.setViewportSize({ width: 420, height: 900 });
  await expect(matches).toBeVisible();
  await dialog.getByRole('button', { name: 'Als Alias zu Wiker Autoservice hinzufügen', exact: true }).click();
  await expect(dialog).toBeHidden();
  expect(savedAlias).toBe('Wiker-Auto-Service');
});

test('enter in the name field creates the correspondent without a form submit', async ({ page }) => {
  await prepareWorkspace(page);
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: [] } }));
  let created;
  await page.route('**/api/correspondents', route => {
    if (route.request().method() !== 'POST') return route.fallback();
    created = route.request().postDataJSON();
    return route.fulfill({ json: { id: 'new-corr', name: created.name, kind: created.kind || 'organization', aliases: [] } });
  });
  await page.locator('.sidebar-item--correspondents').click();
  await page.getByRole('button', { name: 'Neuer Korrespondent', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const name = dialog.getByRole('textbox', { name: 'Name', exact: true });
  await name.fill('Neue Firma');
  const shortName = dialog.getByRole('textbox', { name: 'Kurzname (optional)', exact: true });
  await expect(shortName).toHaveValue('');
  await name.fill('Neue Firma GmbH');
  await expect(shortName).toHaveValue('Neue Firma');
  await expect(dialog.getByText('Vorschlag ohne Rechtsform GmbH', { exact: true })).toBeVisible();
  await name.press('Enter');
  await expect.poll(() => created?.name).toBe('Neue Firma GmbH');
  expect(created.short_name).toBe('Neue Firma');
});

test('the short name can be edited, cleared or set for persons', async ({ page }) => {
  await prepareWorkspace(page);
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: [] } }));
  const created = [];
  await page.route('**/api/correspondents', route => {
    if (route.request().method() !== 'POST') return route.fallback();
    const body = route.request().postDataJSON();
    created.push(body);
    return route.fulfill({ json: { id: `new-${created.length}`, name: body.name, kind: body.kind, aliases: [] } });
  });
  await page.locator('.sidebar-item--correspondents').click();
  const open = async () => {
    await page.getByRole('button', { name: 'Neuer Korrespondent', exact: true }).click();
    return page.getByRole('dialog');
  };
  let dialog = await open();
  const shortName = () => dialog.getByRole('textbox', { name: 'Kurzname (optional)', exact: true });
  await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill('Muster Versicherung AG');
  await expect(shortName()).toHaveValue('Muster Versicherung');
  // Clearing keeps the full name visible: no short name is stored.
  await shortName().fill('');
  await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill('Muster Versicherung SE');
  await expect(shortName()).toHaveValue('');
  await dialog.getByRole('button', { name: 'Anlegen', exact: true }).click();
  await expect.poll(() => created.length).toBe(1);
  expect(created[0]).toMatchObject({ name: 'Muster Versicherung SE', kind: 'organization', short_name: null });

  dialog = await open();
  await dialog.getByRole('button', { name: 'Person', exact: true }).click();
  await dialog.getByRole('textbox', { name: 'Vorname', exact: true }).fill('Erika');
  await dialog.getByRole('textbox', { name: 'Nachname', exact: true }).fill('Mustermann');
  await shortName().fill('Oma');
  await dialog.getByRole('button', { name: 'Anlegen', exact: true }).click();
  await expect.poll(() => created.length).toBe(2);
  expect(created[1]).toMatchObject({ kind: 'person', first_name: 'Erika', last_name: 'Mustermann', short_name: 'Oma' });

  dialog = await open();
  await dialog.getByRole('button', { name: 'Sammlung', exact: true }).click();
  await expect(shortName()).toHaveCount(0);
});

test('the duplicates tile lists likely pairs and merges into the entry with more documents', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const small = { id: clubId, name: 'Vodafone', kind: 'organization', usage_count: 2, aliases: [], notes: 'Kundennr. 42' };
  const large = { id: utilityId, name: 'Vodafone GmbH', kind: 'organization', usage_count: 12, aliases: [] };
  const other = { id: '30000000-0000-4000-8000-000000000009', name: 'Vodafone Kabel', kind: 'organization', usage_count: 1, aliases: [] };
  let items = [small, large, other];
  let mergeRequest;
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items } }));
  for (const entry of [small, large, other]) {
    await page.route(`**/api/correspondents/${entry.id}/profile`, route => route.fulfill({
      json: { correspondent: entry, document_count: entry.usage_count, own_document_count: entry.usage_count, members: [], activity: [], relations: [] },
    }));
  }
  await page.route(`**/api/correspondents/*/merge`, route => {
    mergeRequest = { target: route.request().url().split('/').at(-2), ...route.request().postDataJSON() };
    const merged = { ...large, usage_count: 14, aliases: [{ id: 'alias-1', alias: 'Vodafone' }] };
    items = [merged, other];
    return route.fulfill({ json: { correspondent: merged, documents: 2, aliases: 1, matchers: 0, relations: 0, members: 0, notes: 0 } });
  });

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  const tile = workspace.getByRole('treeitem', { name: 'Mögliche Doppelte', exact: true });
  await expect(tile.locator('.corr-inbox__count')).toHaveText('1');
  await tile.click();
  await expect(tile).toHaveAttribute('aria-selected', 'true');
  const panel = workspace.getByRole('region', { name: 'Mögliche Doppelte', exact: true });
  const pairs = panel.getByRole('list', { name: 'Paare' }).getByRole('listitem');
  await expect(pairs).toHaveCount(1);
  await expect(pairs.first()).toContainText('Nur die Rechtsform unterscheidet sich');
  await expect(panel).not.toContainText('Vodafone Kabel');
  await pairs.first().getByRole('button', { name: 'Vodafone und Vodafone GmbH zusammenführen' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('combobox', { name: 'Zusammenführen mit' })).toBeVisible();
  const keep = dialog.getByRole('radiogroup', { name: 'Bleibt erhalten', exact: true });
  await expect(keep.getByRole('radio', { name: /Vodafone GmbH/ })).toHaveAttribute('aria-checked', 'true');
  await expect(dialog.getByText('2 Dokumente von „Vodafone“ werden „Vodafone GmbH“ zugeordnet.', { exact: true })).toBeVisible();
  await expect(dialog.getByText('Die Notiz von „Vodafone“ wird angehängt.', { exact: true })).toBeVisible();
  await expect(dialog.getByText('„Vodafone“ wird danach gelöscht. Das lässt sich nicht rückgängig machen.', { exact: true })).toBeVisible();
  // Switching sides swaps the summary.
  await keep.getByRole('radio', { name: /^Vodafone 2 Dokumente/ }).click();
  await expect(dialog.getByText('12 Dokumente von „Vodafone GmbH“ werden „Vodafone“ zugeordnet.', { exact: true })).toBeVisible();
  await keep.getByRole('radio', { name: /Vodafone GmbH/ }).click();
  await dialog.getByRole('button', { name: 'Zusammenführen', exact: true }).click();

  await expect(dialog).toBeHidden();
  expect(mergeRequest).toEqual({ target: utilityId, source_id: clubId });
  await expect(workspace.getByRole('tree').getByText('Vodafone', { exact: true })).toHaveCount(0);
  // The duplicates view stays open and is now empty; the tile disappears.
  await expect(panel.getByText('Keine möglichen Doppelten.')).toBeVisible();
  await expect(tile).toHaveCount(0);
});

test('a pair marked as no duplicate stays hidden', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const items = [
    { id: clubId, name: 'Müller', kind: 'organization', usage_count: 1, aliases: [] },
    { id: utilityId, name: 'Müller GmbH', kind: 'organization', usage_count: 2, aliases: [] },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items } }));
  let patch;
  await page.route('**/api/settings', route => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    patch = route.request().postDataJSON();
    return route.fulfill({ json: { ui: { start_view: 'all', theme_mode: 'light', ...patch.ui }, retention: { enabled: false } } });
  });
  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  const tile = workspace.getByRole('treeitem', { name: 'Mögliche Doppelte', exact: true });
  await tile.click();
  const panel = workspace.getByRole('region', { name: 'Mögliche Doppelte', exact: true });
  await panel.getByRole('button', { name: 'Müller und Müller GmbH: kein Doppel' }).click();
  await expect.poll(() => patch).toEqual({ ui: { correspondent_duplicate_dismissals: [[clubId, utilityId].sort().join('|')] } });
  await expect(panel.getByText('Keine möglichen Doppelten.')).toBeVisible();
  await expect(tile).toHaveCount(0);

  // Ausgeblendete Paare lassen sich ansehen und wieder anzeigen.
  await panel.getByRole('button', { name: 'Ausgeblendete Paare (1)' }).click();
  await expect(panel.getByText('1 Paar · als „Kein Doppel“ markiert')).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Aufräumen …' })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Müller und Müller GmbH wieder anzeigen' }).click();
  await expect.poll(() => patch).toEqual({ ui: { correspondent_duplicate_dismissals: [] } });
  await expect(panel.getByText('Keine ausgeblendeten Paare.')).toBeVisible();
  await panel.getByRole('button', { name: 'Offene anzeigen' }).click();
  await expect(panel.getByRole('button', { name: 'Müller und Müller GmbH: kein Doppel' })).toBeVisible();

  // „Aufräumen …“ öffnet den vorhandenen Aufräumen-Dialog.
  await panel.getByRole('button', { name: 'Aufräumen …' }).click();
  await expect(page.getByRole('dialog').filter({ hasText: 'Aufräumen' })).toBeVisible();
});

test('a card is assigned with the keyboard shortcut and a new spelling can be kept as alias', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const utility = { id: utilityId, name: 'Stadtwerke Leipzig', kind: 'organization', aliases: [] };
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items: [utility] } }));
  let unassigned = [
    { document_id: 'bulk1', title: 'Abschlag Januar', sender: 'SWL Energie' },
    { document_id: 'bulk2', title: 'Abschlag Februar', sender: 'SWL Energie' },
    { document_id: 'bulk3', title: 'Notizzettel' },
  ];
  let hiddenDocs = [{ document_id: 'ignored1', title: 'Werbeprospekt' }];
  const restored = [];
  await page.route('**/api/correspondents/unresolved?*', route => {
    const hidden = new URL(route.request().url()).searchParams.get('hidden') === 'true';
    return route.fulfill({ json: { items: hidden ? hiddenDocs : unassigned } });
  });
  await page.route('**/api/correspondents/unresolved/*/ignore', route => {
    if (route.request().method() !== 'DELETE') return route.fallback();
    const id = new URL(route.request().url()).pathname.split('/').at(-2);
    restored.push(id);
    hiddenDocs = hiddenDocs.filter(doc => doc.document_id !== id);
    return route.fulfill({ json: { ok: true } });
  });
  const patched = [];
  await page.route('**/api/documents/bulk*', route => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    const id = new URL(route.request().url()).pathname.split('/').at(-1);
    patched.push([id, route.request().postDataJSON().correspondent_id]);
    unassigned = unassigned.filter(item => item.document_id !== id);
    return route.fulfill({ json: {} });
  });
  await page.route('**/api/documents/bulk*/file?*', route => route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() }));
  let alias;
  await page.route(`**/api/correspondents/${utilityId}/aliases`, route => {
    alias = route.request().postDataJSON().alias;
    return route.fulfill({ json: { ...utility, aliases: [{ id: 'a1', alias }] } });
  });

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  await workspace.getByRole('treeitem', { name: 'Ohne Korrespondent', exact: true }).click();
  const review = workspace.getByRole('region', { name: 'Dokumente ohne Korrespondenten', exact: true });
  // Kopf: Sammelaktion für eindeutige Vorschläge – „SWL Energie“ passt noch zu keinem Eintrag.
  await expect(review.getByRole('button', { name: 'Alle Vorschläge übernehmen: Keine eindeutigen Vorschläge' })).toBeDisabled();
  // Ausgeblendete ansehen und zurückholen.
  await review.getByRole('button', { name: 'Ausgeblendete (1)' }).click();
  await expect(review.getByText('1 Dokument · bewusst ohne Korrespondent')).toBeVisible();
  await review.getByRole('button', { name: 'Werbeprospekt zurückholen' }).click();
  await expect.poll(() => restored).toEqual(['ignored1']);
  await expect(review.getByText('Nichts ausgeblendet.')).toBeVisible();
  await review.getByRole('button', { name: 'Offene anzeigen' }).click();
  // Ohne Ausgeblendete bleibt der Button sichtbar, aber ausgegraut.
  await expect(review.getByRole('button', { name: 'Ausgeblendete (0)' })).toBeDisabled();

  const january = review.getByRole('listitem', { name: 'Abschlag Januar', exact: true });
  // Keine Mehrfachauswahl: jede Karte wird für sich zugeordnet.
  await expect(review.getByRole('checkbox')).toHaveCount(0);

  const correspondent = january.getByRole('combobox', { name: 'Korrespondent', exact: true });
  await correspondent.fill('Stadtwerke');
  await page.getByRole('option').filter({ hasText: 'Stadtwerke Leipzig' }).click();
  await expect(january.getByRole('button', { name: 'Zuordnen', exact: true })).toBeEnabled();
  await page.keyboard.press('ControlOrMeta+Enter');

  await expect.poll(() => patched).toEqual([['bulk1', utilityId]]);
  await expect(january).toHaveCount(0);
  await expect(review.locator('.assign-card')).toHaveCount(2);
  await expect(review.getByRole('listitem', { name: 'Abschlag Februar', exact: true })).toBeFocused();
  const toast = page.getByText('Dokument zugeordnet. „SWL Energie“ als Schreibweise von Stadtwerke Leipzig merken?');
  await expect(toast).toBeVisible();
  await page.getByRole('button', { name: 'Als Alias merken' }).click();
  await expect.poll(() => alias).toBe('SWL Energie');

  // Mit dem neuen Alias passt „Abschlag Februar“ eindeutig: die Sammelaktion übernimmt ihn.
  const bulk = review.getByRole('button', { name: 'Alle Vorschläge übernehmen (1)' });
  await expect(bulk).toBeVisible();
  await bulk.click();
  const dialog = page.getByRole('dialog').filter({ hasText: 'Alle Vorschläge übernehmen?' });
  await expect(dialog.getByText('Abschlag Februar')).toBeVisible();
  await expect(dialog.getByText('Stadtwerke Leipzig', { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: '1 Dokument zuordnen' }).click();
  await expect.poll(() => patched).toEqual([['bulk1', utilityId], ['bulk2', utilityId]]);
  await expect(review.getByRole('listitem', { name: 'Abschlag Februar', exact: true })).toHaveCount(0);

  // Das Vorschaubild öffnet eine große Vorschau als Overlay – nicht im Dokumentbereich.
  const thumb = review.getByRole('button', { name: 'Notizzettel groß anzeigen' });
  await thumb.click();
  const overlay = page.getByRole('region', { name: 'Vorschau: Notizzettel' });
  await expect(overlay).toBeVisible();
  // Nur über dem rechten Bereich: die Liste links bleibt frei.
  const [overlayBox, reviewBox] = await Promise.all([overlay.boundingBox(), review.boundingBox()]);
  expect(overlayBox.x).toBeGreaterThanOrEqual(reviewBox.x - 1);
  expect(overlayBox.width).toBeLessThanOrEqual(reviewBox.width + 1);
  await expect(overlay.locator('.pdf-preview__viewer--ready')).toBeVisible({ timeout: 10000 });
  await expect(review).toBeVisible();
  await expect(page.locator('.details-drawer__subtitle')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(overlay).toHaveCount(0);
  await expect(thumb).toBeFocused();
});

test('cleanup fills in short names and deletes empty entries', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  let items = [
    { id: utilityId, name: 'Vodafone GmbH', kind: 'organization', usage_count: 12, aliases: [] },
    { id: clubId, name: 'Vodafone', kind: 'organization', usage_count: 3, aliases: [] },
    { id: 'empty-1', name: 'Alte Hausverwaltung', kind: 'organization', usage_count: 0, aliases: [] },
    { id: 'empty-2', name: 'Testkontakt', kind: null, usage_count: 0, aliases: [] },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items } }));
  const patches = [];
  const deletes = [];
  await page.route(/\/api\/correspondents\/[^/?]+$/, route => {
    const id = new URL(route.request().url()).pathname.split('/').at(-1);
    if (route.request().method() === 'PATCH') {
      const body = route.request().postDataJSON();
      patches.push([id, body]);
      items = items.map(item => (item.id === id ? { ...item, ...body } : item));
      return route.fulfill({ json: items.find(item => item.id === id) });
    }
    if (route.request().method() === 'DELETE') {
      deletes.push(id);
      items = items.filter(item => item.id !== id);
      return route.fulfill({ json: { ok: true } });
    }
    return route.fallback();
  });

  await page.locator('.sidebar-item--correspondents').click();
  const cleanupButton = page.getByRole('button', { name: 'Aufräumen: 3 Vorschläge', exact: true });
  await cleanupButton.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('list', { name: 'Mögliche Doppelte' })).toHaveCount(0);

  const shortNames = dialog.getByRole('list', { name: 'Kurznamen nachtragen' });
  await expect(shortNames.getByRole('checkbox', { name: 'Kurzname Vodafone für Vodafone GmbH' })).toBeChecked();
  await dialog.getByRole('button', { name: '1 Kurzname übernehmen' }).click();
  await expect.poll(() => patches).toEqual([[utilityId, { short_name: 'Vodafone' }]]);
  await expect(shortNames).toHaveCount(0);

  const empties = dialog.getByRole('list', { name: 'Ohne Dokumente' });
  await expect(empties.getByRole('checkbox')).toHaveCount(2);
  await dialog.getByRole('button', { name: 'Alle auswählen', exact: true }).click();
  await dialog.getByRole('button', { name: '2 Einträge löschen …' }).click();
  expect(deletes).toEqual([]);
  await dialog.getByRole('button', { name: '2 Einträge endgültig löschen' }).click();
  await expect.poll(() => deletes.sort()).toEqual(['empty-1', 'empty-2']);
  await expect(empties).toHaveCount(0);

  await dialog.getByRole('button', { name: 'Fertig', exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(cleanupButton).toHaveCount(0);
});

test('choosing a collection or organisation offers the more specific members of the document', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const items = [
    { id: 'bank', name: 'Bank', kind: 'collection', aliases: [] },
    { id: 'sparkasse', name: 'Förde Sparkasse AöR', short_name: 'Förde Sparkasse', kind: 'organization', parent_id: 'bank', aliases: [] },
    { id: 'volksbank', name: 'Volksbank', kind: 'organization', parent_id: 'bank', aliases: [] },
    { id: 'praxis', name: 'Praxis am Markt', kind: 'organization', aliases: [] },
    { id: 'berger', name: 'Anna Berger', kind: 'person', parent_id: 'praxis', aliases: [] },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items } }));
  await page.route('**/api/correspondents/unresolved?*', route => route.fulfill({ json: { items: [{ document_id: 'refine1', title: 'Kontoauszug März' }] } }));
  await page.route('**/api/documents/refine1/file?*', route => route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() }));
  const requests = [];
  await page.route('**/api/correspondents/*/refinements?*', route => {
    const url = new URL(route.request().url());
    const id = url.pathname.split('/').at(-2);
    requests.push([id, url.searchParams.get('document_id')]);
    const byId = {
      bank: [{ ...items[1], mentioned: true }, { ...items[2], mentioned: false }],
      praxis: [{ ...items[4], mentioned: true }],
    };
    return route.fulfill({ json: { items: byId[id] || [] } });
  });

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  await workspace.getByRole('treeitem', { name: 'Ohne Korrespondent', exact: true }).click();
  const drawer = workspace.getByRole('listitem', { name: 'Kontoauszug März', exact: true });
  const correspondent = drawer.getByRole('combobox', { name: 'Korrespondent', exact: true });
  await correspondent.fill('Bank');
  await page.getByRole('option').filter({ hasText: 'Bank · Sammlung' }).click();
  const hint = drawer.getByRole('group', { name: 'Sammlung – genauer:' });
  await expect(hint.getByRole('button')).toHaveCount(2);
  await expect(hint.getByRole('button').first()).toHaveAccessibleName('Genauer zuordnen: Förde Sparkasse AöR (im Dokument genannt)');
  await hint.getByRole('button').first().click();
  await expect(drawer.locator('.pm-metadata-value')).toContainText('Förde Sparkasse');
  await expect(hint).toHaveCount(0);

  await correspondent.fill('Praxis');
  await page.getByRole('option').filter({ hasText: 'Praxis am Markt' }).click();
  const personHint = drawer.getByRole('group', { name: 'Genauer:' });
  await personHint.getByRole('button', { name: 'Genauer zuordnen: Anna Berger (im Dokument genannt)' }).click();
  await expect(drawer.locator('.pm-metadata-value')).toContainText('Anna Berger');
  expect(requests).toEqual([['bank', 'refine1'], ['praxis', 'refine1']]);
});

test('correspondent pickers find entries by their short name', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const items = [
    { id: 'aok', name: 'Allgemeine Ortskrankenkasse Nordwest', short_name: 'AOK', kind: 'organization', usage_count: 2, aliases: [] },
    { id: 'tk', name: 'Techniker Krankenkasse', short_name: 'TK', kind: 'organization', usage_count: 3, aliases: [] },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items } }));
  await page.route('**/api/correspondents/unresolved?*', route => route.fulfill({ json: { items: [{ document_id: 'short1', title: 'Beitragsbescheid' }] } }));
  await page.route('**/api/documents/short1/file?*', route => route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() }));
  for (const entry of items) {
    await page.route(`**/api/correspondents/${entry.id}/profile`, route => route.fulfill({ json: { correspondent: entry, document_count: entry.usage_count, own_document_count: entry.usage_count, members: [], activity: [], relations: [] } }));
  }

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  await workspace.getByRole('treeitem', { name: 'Ohne Korrespondent', exact: true }).click();
  const drawer = workspace.getByRole('listitem', { name: 'Beitragsbescheid', exact: true });
  await drawer.getByRole('combobox', { name: 'Korrespondent', exact: true }).fill('AOK');
  await expect(page.getByRole('option').filter({ hasText: 'Allgemeine Ortskrankenkasse Nordwest' })).toBeVisible();
  await expect(page.getByRole('option').filter({ hasText: 'Techniker Krankenkasse' })).toHaveCount(0);
  await page.keyboard.press('Escape');

  // With "Kurznamen bevorzugen" (default) the list shows the short name, the full name as tooltip.
  const tkRow = workspace.getByRole('tree').getByText('TK', { exact: true });
  await expect(tkRow).toHaveAttribute('title', 'Techniker Krankenkasse');
  await expect(workspace.getByRole('tree').getByText('Techniker Krankenkasse', { exact: true })).toHaveCount(0);
  // The merge dialog searches the same way.
  await tkRow.click();
  await workspace.getByRole('button', { name: 'Zusammenführen …', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Zusammenführen mit' }).fill('aok');
  await expect(page.getByRole('option').filter({ hasText: 'Allgemeine Ortskrankenkasse Nordwest' })).toBeVisible();
});

test('documents assigned to a collection can be refined to a member or kept', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await prepareWorkspace(page);
  const items = [
    { id: 'bank', name: 'Bank', kind: 'collection', usage_count: 2, aliases: [] },
    { id: 'sparkasse', name: 'Förde Sparkasse', kind: 'organization', parent_id: 'bank', usage_count: 0, aliases: [] },
    { id: 'volksbank', name: 'Volksbank', kind: 'organization', parent_id: 'bank', usage_count: 0, aliases: [] },
  ];
  await page.route('**/api/correspondents?include_count=true', route => route.fulfill({ json: { items } }));
  let collectionDocs = [
    { document_id: 'coll1', title: 'Kontoauszug März', correspondent_id: 'bank', correspondent_name: 'Bank' },
    { document_id: 'coll2', title: 'Allgemeine Bedingungen', correspondent_id: 'bank', correspondent_name: 'Bank' },
  ];
  await page.route('**/api/correspondents/collection-documents?*', route => route.fulfill({ json: { scanned: collectionDocs.length, unresolved: collectionDocs.length, include_deleted: false, items: collectionDocs } }));
  await page.route('**/api/documents/coll*/file?*', route => route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() }));
  await page.route('**/api/correspondents/*/refinements?*', route => {
    const documentId = new URL(route.request().url()).searchParams.get('document_id');
    const mentioned = documentId === 'coll1';
    return route.fulfill({ json: { items: [{ ...items[1], mentioned }, { ...items[2], mentioned: false }] } });
  });
  const patched = [];
  await page.route('**/api/documents/coll*', route => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    const id = new URL(route.request().url()).pathname.split('/').at(-1);
    patched.push([id, route.request().postDataJSON().correspondent_id]);
    collectionDocs = collectionDocs.filter(doc => doc.document_id !== id);
    return route.fulfill({ json: {} });
  });
  const kept = [];
  await page.route('**/api/correspondents/collection-documents/*/keep', route => {
    const id = new URL(route.request().url()).pathname.split('/').at(-2);
    kept.push(id);
    collectionDocs = collectionDocs.filter(doc => doc.document_id !== id);
    return route.fulfill({ json: { ok: true } });
  });

  await page.locator('.sidebar-item--correspondents').click();
  const workspace = page.locator('.panel-correspondents');
  const tile = workspace.getByRole('treeitem', { name: 'Genauer zuordnen', exact: true });
  await expect(tile.locator('.corr-inbox__count')).toHaveText('2');
  await tile.click();
  const review = workspace.getByRole('region', { name: 'Dokumente an Sammlungen', exact: true });
  await expect(review.getByRole('heading', { name: 'Genauer zuordnen', level: 1 })).toBeVisible();
  // Nur „Kontoauszug März“ nennt genau ein Mitglied.
  await expect(review.getByRole('button', { name: 'Genannte Mitglieder übernehmen (1)' })).toBeVisible();
  const first = review.getByRole('listitem', { name: 'Kontoauszug März', exact: true });
  await expect(first.locator('.assign-card__collection')).toHaveText('Bank');
  // The member named in the document is preselected as suggestion.
  await expect(first.locator('.pm-metadata-value')).toContainText('Förde Sparkasse');
  await expect(first.getByText('Vorschlag', { exact: true })).toBeVisible();
  await first.getByRole('button', { name: 'Zuordnen', exact: true }).click();
  await expect.poll(() => patched).toEqual([['coll1', 'sparkasse']]);
  await expect(first).toHaveCount(0);

  // Without a mentioned member the collection stays selected and cannot be "assigned" again.
  const second = review.getByRole('listitem', { name: 'Allgemeine Bedingungen', exact: true });
  await expect(second.getByRole('button', { name: 'Zuordnen', exact: true })).toBeDisabled();
  await expect(second.getByRole('group', { name: 'Sammlung – genauer:' }).getByRole('button')).toHaveCount(2);
  await second.getByRole('button', { name: 'Weitere Aktionen für Allgemeine Bedingungen' }).click();
  await page.getByText('Bei der Sammlung lassen', { exact: true }).click();
  await expect.poll(() => kept).toEqual(['coll2']);
  await expect(review.getByText('Alle Dokumente sind genauer zugeordnet.')).toBeVisible();
});
