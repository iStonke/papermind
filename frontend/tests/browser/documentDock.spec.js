import { test, expect } from '@playwright/test';
import { syntheticDocumentPdf } from './fixtures/syntheticDocumentPdf.js';
async function mountDock(page) {
  await page.setViewportSize({ width: 1280, height: 950 });
  await page.route('**/__details-test.pdf', route => route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() }));
  await page.route('**/__document-dock', route => route.fulfill({ contentType: 'text/html', body: '<html><body style="margin:0"><div id="app"></div></body></html>' }));
  await page.route(url => url.pathname.startsWith('/api/'), route => route.fulfill({ json: { items: [], has_more: false } }));
  await page.goto('/__document-dock');
  await page.evaluate(async () => { const { mount } = await import('/tests/browser/fixtures/documentDock.js'); mount(); });
  await expect(page.locator('.pdf-preview--document-ready')).toBeVisible();
}
test('attached panel shrinks the page, keeps field nodes and returns focus when collapsed', async ({ page }) => {
  await mountDock(page);
  const drawer = page.locator('.preview-layout__drawer');
  const toggle = page.getByRole('button', { name: 'Dokumentdetails umschalten' });
  const firstPage = page.locator('.pdf-preview__page').first();
  const initialHeight = await firstPage.evaluate(el => el.getBoundingClientRect().height);
  await expect.poll(() => firstPage.evaluate(el => Math.abs(el.getBoundingClientRect().top - el.parentElement.getBoundingClientRect().top))).toBeLessThan(1);
  const textPosition = el => {
    const page = el.getBoundingClientRect(), text = el.querySelector('.textLayer span').getBoundingClientRect();
    return (text.left - page.left) / page.width;
  };
  const initialTextPosition = await firstPage.evaluate(textPosition);
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect.poll(() => page.locator('.pdf-preview__page').first().evaluate(el => el.getBoundingClientRect().height)).toBeLessThan(initialHeight - 100);
  await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().width))).toBe(848);
  expect(await firstPage.evaluate(textPosition)).toBeCloseTo(initialTextPosition, 2);
  const name = page.getByLabel('Dokumentname', { exact: true });
  await name.fill('Bearbeiteter Titel');
  await name.evaluate(el => { window.originalNameInput = el; });
  await page.evaluate(() => { window.dock.open = false; });
  await expect(toggle).toBeFocused();
  await expect(drawer).toHaveCSS('height', '72px');
  await toggle.click();
  await expect(name).toHaveValue('Bearbeiteter Titel');
  expect(await name.evaluate(el => el === window.originalNameInput)).toBe(true);
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; window.dock.title = 'Ein anderes Dokument'; });
  await expect(page.locator('.details-drawer__subtitle')).toHaveText('Ein anderes Dokument');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await expect.poll(() => page.locator('.preview-layout__content').evaluate(el => el.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  await page.evaluate(() => { window.dock.title = 'Teilnahmebestätigung · Gestaltungsseminar'; window.dock.form.name = window.dock.title; });
  await expect.poll(() => page.locator('.preview-layout__content').evaluate(el => el.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  await page.screenshot({ path: '/tmp/papermind-document-dock-dark.png' });
});
test('collapsed details show the PDF behind a translucent surface and expanded details remain opaque', async ({ page }) => {
  await mountDock(page);
  const drawer = page.locator('.preview-layout__drawer');
  for (const theme of ['light', 'dark']) {
    await page.evaluate(theme => { window.dock.theme = theme; window.dock.open = false; }, theme);
    await expect(drawer).toHaveCSS('height', '72px');
    const geometry = () => page.locator('.preview-layout').evaluate(el => {
      const viewer = el.querySelector('.preview-layout__viewer').getBoundingClientRect();
      const details = el.querySelector('.preview-layout__drawer').getBoundingClientRect();
      const page = el.querySelector('.pdf-preview__page').getBoundingClientRect();
      return { reserved: Math.abs(viewer.bottom - el.getBoundingClientRect().bottom), overlap: page.bottom - details.top };
    });
    await expect.poll(async () => (await geometry()).reserved).toBeLessThan(1);
    await expect.poll(async () => (await geometry()).overlap).toBeGreaterThan(40);
    await expect(drawer).toHaveCSS('backdrop-filter', 'blur(6px)');
    await expect.poll(() => drawer.evaluate(el => el.getAnimations().filter(effect => effect.playState === 'running').length)).toBe(0);
    const alpha = await drawer.evaluate(el => {
      const color = getComputedStyle(el).backgroundColor;
      return Number(color.match(/\/\s*([\d.]+)/)?.[1] ?? color.match(/rgba\([^)]*,\s*([\d.]+)\)/)?.[1] ?? 1);
    });
    expect(alpha).toBeCloseTo(.84, 2);
    await expect(page.locator('.preview-layout__header')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    await page.screenshot({ path: `/tmp/papermind-translucent-details-${theme}.png` });
    await page.getByRole('button', { name: 'Dokumentdetails umschalten' }).click();
    await expect(drawer).toHaveCSS('background-color', theme === 'light' ? 'rgb(255, 255, 255)' : 'rgb(51, 59, 62)');
    await expect.poll(() => page.locator('.preview-layout__viewer').evaluate(el => Math.abs(el.getBoundingClientRect().bottom - el.nextElementSibling.getBoundingClientRect().top))).toBeLessThan(1);
  }
  await page.evaluate(() => { window.dock.open = false; });
  const pages = page.locator('.pdf-preview__pages');
  await expect(drawer).toHaveCSS('height', '72px');
  await expect.poll(() => pages.evaluate(el => parseFloat(getComputedStyle(el).paddingBottom))).toBe(88);
  await pages.evaluate(el => { el.scrollTop = el.scrollHeight; });
  await expect.poll(() => page.locator('.pdf-preview__page').last().evaluate(el => el.getBoundingClientRect().bottom - document.querySelector('.preview-layout__drawer').getBoundingClientRect().top)).toBeLessThan(-10);
});
test('opening and closing the drawer each run one uninterrupted height transition', async ({ page }) => {
  await mountDock(page);
  const drawer = page.locator('.preview-layout__drawer');
  await expect.poll(() => drawer.evaluate(el => el.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length)).toBe(0);
  await drawer.evaluate(el => {
    window.drawerHeightStarts = 0;
    el.addEventListener('transitionrun', event => {
      if (event.target === el && event.propertyName === 'height') window.drawerHeightStarts++;
    });
  });
  const toggle = page.getByRole('button', { name: 'Dokumentdetails umschalten' });
  await toggle.click();
  await expect.poll(() => drawer.evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThan(300);
  await expect.poll(() => drawer.evaluate(el => el.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length)).toBe(0);
  expect(await page.evaluate(() => window.drawerHeightStarts)).toBe(1);
  await toggle.click();
  await expect(drawer).toHaveCSS('height', '72px');
  await expect.poll(() => drawer.evaluate(el => el.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length)).toBe(0);
  expect(await page.evaluate(() => window.drawerHeightStarts)).toBe(2);
});
test('rapid reversals settle, resizing keeps the header accessible and scrolling cue follows content', async ({ page }) => {
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; });
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await page.evaluate(async () => {
    for (let i = 0; i < 5; i++) { window.dock.open = !window.dock.open; await new Promise(resolve => setTimeout(resolve, 35)); }
    window.dock.open = true; window.dock.width = 390; window.dock.height = 480;
  });
  const drawer = page.locator('.preview-layout__drawer');
  await expect.poll(() => drawer.evaluate(el => el.getBoundingClientRect().height)).toBeLessThanOrEqual(302);
  await expect(page.getByRole('button', { name: 'Dokumentdetails umschalten' })).toBeVisible();
  await expect(page.locator('.preview-layout__scroll-cue')).toHaveCSS('opacity', '1');
  await page.locator('.preview-layout__body').evaluate(el => { el.scrollTop = el.scrollHeight; });
  await expect(page.locator('.preview-layout__scroll-cue')).toHaveCSS('opacity', '0');
  await page.evaluate(() => { window.dock.theme = 'light'; window.dock.width = 850; window.dock.height = 720; });
  await page.locator('.preview-layout__body').evaluate(el => { el.scrollTop = 0; });
  await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().width))).toBe(848);
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await expect(drawer).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.screenshot({ path: '/tmp/papermind-document-dock-light.png' });
});
test('save confirmation respects errors and document switches', async ({ page }) => {
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; window.dock.saving = true; });
  await expect(page.locator('.metadata-save')).toHaveText('Wird gespeichert …');
  await page.evaluate(() => { window.dock.saving = false; });
  await expect(page.locator('.metadata-save')).toHaveText('Gespeichert');
  await page.evaluate(() => { window.dock.saving = true; });
  await page.evaluate(() => { window.dock.error = true; window.dock.saving = false; });
  await expect(page.locator('.metadata-save')).toBeEmpty();
  await page.evaluate(() => { window.dock.error = false; window.dock.saving = true; });
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; window.dock.saving = false; });
  await expect(page.locator('.metadata-save')).toBeEmpty();
});


test('reduced motion also disables the document content swap', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; });
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; });
  await expect(page.locator('.preview-layout__drawer')).toHaveCSS('transition-duration', '0s');
  expect(await page.locator('.preview-layout__content').evaluate(el => el.getAnimations().length)).toBe(0);
});


test('whole active page stays above the panel in portrait, landscape and narrow stages', async ({ page }) => {
  await mountDock(page);
  await page.evaluate(() => { window.dock.open = true; });
  const withinStage = () => page.locator('.pdf-preview__pages').evaluate(el => {
    const viewport = el.getBoundingClientRect();
    const articles = [...el.querySelectorAll('article')].map(el => el.getBoundingClientRect());
    return articles.some(rect => rect.top >= viewport.top - 0.5 && rect.bottom <= viewport.bottom - 12 && rect.left >= viewport.left && rect.right <= viewport.right);
  });
  await expect.poll(withinStage).toBe(true);
  await page.evaluate(() => window.dock.preview.goToPage(2));
  await expect.poll(() => page.evaluate(() => window.dock.preview.currentPage)).toBe(2);
  await expect.poll(withinStage).toBe(true);
  await page.evaluate(() => { window.dock.width = 390; window.dock.height = 480; });
  await expect.poll(withinStage).toBe(true);
  await expect.poll(() => page.evaluate(() => window.dock.preview.currentPage)).toBe(2);
  const geometry = () => page.locator('.preview-layout').evaluate(el => {
    const viewer = el.querySelector('.preview-layout__viewer').getBoundingClientRect();
    const details = el.querySelector('.preview-layout__drawer').getBoundingClientRect();
    const root = el.getBoundingClientRect();
    return { gap: Math.abs(viewer.bottom - details.top), bottomGap: Math.abs(details.bottom - root.bottom) };
  });
  // A fitted page can already be visible while the drawer is still rebounding.
  await expect.poll(async () => (await geometry()).gap).toBeLessThan(1);
  await expect.poll(async () => (await geometry()).bottomGap).toBeLessThan(1);
});


test('tabs hide when collapsed, size to each section and retain input nodes', async ({ page }) => {
  await mountDock(page);
  await expect(page.getByRole('tablist')).toBeHidden();
  await page.getByRole('button', { name: 'Dokumentdetails umschalten' }).click();
  await page.getByRole('tab', { name: 'Überblick', exact: true }).click();
  const metadataPanel = page.getByRole('tabpanel', { name: 'Überblick', exact: true });
  await expect(metadataPanel).toBeVisible();
  const name = page.getByLabel('Dokumentname', { exact: true });
  await name.fill('Titel bleibt beim Wechsel erhalten');
  await name.evaluate(el => { window.originalTabInput = el; });
  const drawer = page.locator('.preview-layout__drawer');
  await expect.poll(() => drawer.evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThan(300);
  await expect.poll(() => page.locator('.preview-layout__body').evaluate(el => el.scrollHeight - el.clientHeight)).toBeLessThanOrEqual(2);
  const metadataHeight = await drawer.evaluate(el => el.getBoundingClientRect().height);
  await expect(page.getByRole('tab')).toHaveText(['Überblick', 'Notizen', 'Ähnliche Dokumente', 'Aufbewahrung']);
  await expect(page.getByRole('tab', { name: 'Lernmarkierungen', exact: true })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Notizen', exact: true }).click();
  const notesPanel = page.getByRole('tabpanel', { name: 'Notizen', exact: true });
  await expect(notesPanel.locator('.pm-metadata-label, .doc-notes')).toHaveCount(0);
  await expect.poll(() => notesPanel.evaluate(el => Math.abs(el.clientWidth - el.querySelector('.pm-metadata-control').getBoundingClientRect().width))).toBeLessThan(2);
  await expect(metadataPanel).toBeHidden();
  await expect.poll(() => drawer.evaluate(el => el.getBoundingClientRect().height)).toBeLessThan(metadataHeight - 30);
  await expect.poll(() => drawer.evaluate(el => el.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length)).toBe(0);
  const note = page.getByRole('textbox', { name: 'Notizen', exact: true });
  await note.fill('Eine erhaltene Textnotiz');
  await page.getByRole('tab', { name: 'Überblick', exact: true }).click();
  await expect(name).toHaveValue('Titel bleibt beim Wechsel erhalten');
  expect(await name.evaluate(el => el === window.originalTabInput)).toBe(true);
  await page.getByRole('tab', { name: 'Notizen', exact: true }).click();
  await expect(note).toHaveValue('Eine erhaltene Textnotiz');
  await expect.poll(() => drawer.evaluate(el => el.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length)).toBe(0);
  await notesPanel.screenshot({ path: '/tmp/papermind-notes-field.png' });
  await page.evaluate(() => { window.dock.theme = 'light'; });
  await page.screenshot({ path: '/tmp/papermind-notes-field-light.png', animations: 'disabled' });
  const toggle = page.getByRole('button', { name: 'Dokumentdetails umschalten' });
  await toggle.click();
  await expect(page.getByRole('tablist')).toBeHidden();
  await toggle.click();
  await expect(page.getByRole('tab', { name: 'Notizen', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(note).toHaveValue('Eine erhaltene Textnotiz');
});

test('tabs support keyboard navigation, async height changes and overflow', async ({ page }) => {
  await mountDock(page);
  await page.getByRole('button', { name: 'Dokumentdetails umschalten' }).click();
  const firstTab = page.getByRole('tab', { name: 'Überblick', exact: true });
  await firstTab.focus();
  await firstTab.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Notizen', exact: true })).toBeFocused();
  await expect(page.getByRole('tabpanel', { name: 'Notizen', exact: true })).toBeVisible();
  await page.evaluate(() => { window.dock.height = 480; });
  await page.getByRole('textbox', { name: 'Notizen', exact: true }).fill(Array.from({ length: 30 }, (_, index) => `Gedanke ${index + 1}`).join('\n'));
  await expect.poll(() => page.locator('.preview-layout__body').evaluate(el => el.scrollHeight - el.clientHeight)).toBeGreaterThan(100);
  await expect.poll(() => page.locator('.preview-layout__viewer').evaluate(el => el.clientHeight)).toBeGreaterThanOrEqual(178);
  await page.getByRole('tab', { name: 'Notizen', exact: true }).press('End');
  await expect(page.getByRole('tabpanel', { name: 'Aufbewahrung', exact: true })).toBeVisible();
  await expect(page.getByText('Aufbewahrungsdauer', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Aufbewahrung', exact: true }).press('Home');
  await expect(firstTab).toBeFocused();
  await expect(firstTab).toHaveAttribute('aria-selected', 'true');
});


const relatedItem = (id, title) => ({ id, title, document_date: '2026-10-01', same_correspondent: true, same_type: true, shared_tag_count: 2, shared_tags: ['Auto', 'Versicherung'] });
async function openRelated(page) {
  await page.getByRole('button', { name: 'Dokumentdetails umschalten' }).click();
  await page.getByRole('tab', { name: 'Ähnliche Dokumente', exact: true }).click();
}
test('related tab loads on demand, explains matches, caches and opens documents', async ({ page }) => {
  await mountDock(page);
  let requests = 0;
  await page.route('**/api/documents/*/related?limit=5', route => {
    requests++;
    return route.fulfill({ json: { items: [relatedItem('related-1', 'Beitragsrechnung 2025'), relatedItem('related-2', 'Versicherungsvertrag')] } });
  });
  expect(requests).toBe(0);
  await openRelated(page);
  const panel = page.getByRole('tabpanel', { name: 'Ähnliche Dokumente', exact: true });
  await expect(panel.getByRole('button', { name: /Beitragsrechnung 2025/ })).toBeVisible();
  await expect(panel.getByText('Gleicher Korrespondent und Dokumenttyp').first()).toBeVisible();
  await expect(panel.getByText('Gemeinsame Tags: Auto, Versicherung').first()).toHaveAttribute('title', '2 gemeinsame Tags: Auto, Versicherung');
  await expect(panel.getByText('01.10.2026').first()).toBeVisible();
  await page.getByRole('tab', { name: 'Überblick', exact: true }).click();
  await page.getByRole('tab', { name: 'Ähnliche Dokumente', exact: true }).click();
  expect(requests).toBe(1);
  await expect.poll(() => panel.evaluate(el => el.closest('.preview-layout__drawer').getAnimations({ subtree: true }).filter(animation => animation.playState === 'running').length)).toBe(0);
  await page.screenshot({ path: '/tmp/papermind-related-documents.png' });
  await panel.getByRole('button', { name: /Beitragsrechnung 2025/ }).click();
  await expect.poll(() => page.evaluate(() => window.dock.lastRelatedDocument)).toBe('related-1');
  await expect.poll(() => requests).toBe(2);
  await page.evaluate(() => { window.dock.matchRevision++; });
  await expect.poll(() => requests).toBe(3);
});

test('related tab handles errors, retry and empty results', async ({ page }) => {
  await mountDock(page);
  let requests = 0;
  await page.route('**/api/documents/*/related?limit=5', route => ++requests === 1
    ? route.fulfill({ status: 500, json: { error: { message: 'Testfehler' } } })
    : route.fulfill({ json: { items: [] } }));
  await openRelated(page);
  await expect(page.getByText('Ähnliche Dokumente konnten nicht geladen werden.')).toBeVisible();
  await page.getByRole('button', { name: 'Erneut versuchen' }).click();
  await expect(page.getByText('Keine Vorschläge. Probiere „Gleicher Absender“ oder „Gemeinsame Tags“.')).toBeVisible();
  await expect.poll(() => page.locator('.preview-layout__drawer').evaluate(el => el.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length)).toBe(0);
  await page.locator('.related-documents').screenshot({ path: '/tmp/papermind-related-card.png' });
  expect(requests).toBe(2);
});

test('related tab ignores old responses after changing the selected document', async ({ page }) => {
  await mountDock(page);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/documents/*/related?limit=5', async route => {
    const old = route.request().url().includes('/document-a/');
    if (old) await gate;
    await route.fulfill({ json: { items: [relatedItem(old ? 'old' : 'new', old ? 'Alter Vorschlag' : 'Aktueller Vorschlag')] } });
  });
  await openRelated(page);
  await expect(page.getByText('Ähnliche Dokumente werden gesucht …')).toBeVisible();
  await page.evaluate(() => { window.dock.documentKey = 'document-b'; });
  await expect(page.getByRole('button', { name: /Aktueller Vorschlag/ })).toBeVisible();
  const oldResponse = page.waitForResponse(response => response.url().includes('/document-a/related'));
  release();
  await (await oldResponse).finished();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => resolve())));
  await expect(page.getByRole('button', { name: /Alter Vorschlag/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Aktueller Vorschlag/ })).toBeVisible();
});


test('related titles and tooltips follow the suffix preference without changing names or reloading', async ({ page }) => {
  await mountDock(page);
  let requests = 0;
  const titles = ['Versicherungsnachweis VBLklassik 2025.pdf', 'Meine VBL Freischaltcode September 2026.PDF', 'Versicherungsnachweis VBLklassik 2024', 'Antrag a. Rückerstattung_300768'];
  await page.route('**/api/documents/*/related?limit=5', route => {
    requests++;
    return route.fulfill({ json: { items: titles.map((title, i) => relatedItem(`related-${i}`, title)) } });
  });
  await openRelated(page);
  const labels = page.locator('.related-documents__title');
  const buttons = page.locator('.related-documents__item');
  const hidden = titles.map((title, i) => i < 2 ? title.slice(0, -4) : title);
  await expect(labels).toHaveText(hidden);
  for (let i = 0; i < titles.length; i++) await expect(buttons.nth(i)).toHaveAttribute('title', hidden[i]);
  await page.evaluate(() => { window.dock.showSuffix = true; });
  await expect(labels).toHaveText(titles);
  for (let i = 0; i < titles.length; i++) await expect(buttons.nth(i)).toHaveAttribute('title', titles[i]);
  await page.evaluate(() => { window.dock.showSuffix = false; });
  await expect(labels).toHaveText(hidden);
  expect(requests).toBe(1);
});

test('related filters cache independently, explain series and load additional pages with retry', async ({ page }) => {
  await mountDock(page);
  const calls = [];
  let failNextPage = true;
  await page.route('**/api/documents/*/related?**', route => {
    const url = new URL(route.request().url());
    const mode = url.searchParams.get('mode') || 'recommended';
    const offset = Number(url.searchParams.get('offset') || 0);
    calls.push({ mode, offset });
    if (mode === 'recommended') return route.fulfill({ json: { total: 1, has_more: false,
      items: [{ ...relatedItem('series', 'Beitragsrechnung 2025'), same_series: true }] } });
    if (mode === 'tags') return route.fulfill({ json: { items: [], total: 0, has_more: false } });
    if (offset && failNextPage) { failNextPage = false; return route.fulfill({ status: 500, json: {} }); }
    return route.fulfill({ json: { items: Array.from({ length: offset ? 2 : 5 }, (_, i) => relatedItem(`sender-${offset + i}`, `Absenderbeleg ${offset + i}`)), total: 7, has_more: offset === 0 } });
  });
  await openRelated(page);
  const panel = page.getByRole('tabpanel', { name: 'Ähnliche Dokumente', exact: true });
  await expect(panel.getByText('Gleiche Dokumentserie', { exact: true })).toBeVisible();
  await panel.getByRole('button', { name: 'Gleicher Absender', exact: true }).click();
  await expect(panel.locator('.related-documents__item')).toHaveCount(5);
  await expect(panel.getByText('5 von 7 Vorschlägen', { exact: true })).toBeVisible();
  await panel.getByRole('button', { name: 'Mehr anzeigen', exact: true }).click();
  await expect(panel.getByText('Weitere Dokumente konnten nicht geladen werden.', { exact: true })).toBeVisible();
  await expect(panel.locator('.related-documents__item')).toHaveCount(5);
  await panel.getByRole('button', { name: 'Erneut versuchen', exact: true }).click();
  await expect(panel.locator('.related-documents__item')).toHaveCount(7);
  await expect(panel.getByRole('button', { name: 'Mehr anzeigen', exact: true })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Gemeinsame Tags', exact: true }).click();
  await expect(panel.getByText('Es wurden keine weiteren Dokumente mit gemeinsamen Tags gefunden.', { exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Gleicher Absender', exact: true })).toBeVisible();
  const before = calls.length;
  await panel.getByRole('button', { name: 'Gleicher Absender', exact: true }).click();
  await expect(panel.locator('.related-documents__item')).toHaveCount(7);
  expect(calls.length).toBe(before);
  expect(calls.filter(call => call.mode === 'correspondent' && call.offset === 5)).toHaveLength(2);
  await panel.getByRole('button', { name: 'Empfohlen', exact: true }).click();
  await expect(panel.getByText('Gleiche Dokumentserie', { exact: true })).toBeVisible();
  expect(calls.length).toBe(before);
});

test('a late filtered page cannot overwrite another selected filter', async ({ page }) => {
  await mountDock(page);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/documents/*/related?**', async route => {
    const url = new URL(route.request().url());
    const mode = url.searchParams.get('mode');
    if (mode === 'correspondent') await gate;
    return route.fulfill({ json: { total: 1, has_more: false, items: [relatedItem(mode || 'recommended', mode === 'correspondent' ? 'Verspäteter Absenderbeleg' : mode === 'tags' ? 'Tag-Treffer' : 'Empfehlung')] } });
  });
  try {
    await openRelated(page);
    const panel = page.getByRole('tabpanel', { name: 'Ähnliche Dokumente', exact: true });
    await panel.getByRole('button', { name: 'Gleicher Absender', exact: true }).click();
    await expect(panel.getByText('Ähnliche Dokumente werden gesucht …')).toBeVisible();
    await panel.getByRole('button', { name: 'Gemeinsame Tags', exact: true }).click();
    await expect(panel.getByRole('button', { name: /Tag-Treffer/ })).toBeVisible();
    const response = page.waitForResponse(response => response.url().includes('mode=correspondent'));
    release();
    await (await response).finished();
    await expect(panel.getByRole('button', { name: /Tag-Treffer/ })).toBeVisible();
    await expect(panel.getByRole('button', { name: /Verspäteter Absenderbeleg/ })).toHaveCount(0);
    await expect(panel.getByRole('button', { name: 'Gemeinsame Tags', exact: true })).toHaveAttribute('aria-pressed', 'true');
  } finally { release(); }
});
