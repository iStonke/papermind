import { test, expect } from '@playwright/test';
import { syntheticDocumentPdf } from './fixtures/syntheticDocumentPdf.js';

async function clickDocumentTurn(page, back = false) {
  await page.locator('.document-flip').hover({ position: { x: 12, y: 12 } });
  await page.getByRole('button', { name: back ? 'Zurück zum Dokument' : 'Dokument wenden – Zusammenhänge anzeigen', exact: true }).click();
}
async function mount(page) {
  await page.setViewportSize({ width: 1280, height: 950 });
  await page.route('**/__details-test.pdf', route => route.fulfill({ contentType: 'application/pdf', body: syntheticDocumentPdf() }));
  await page.route('**/__document-dock', route => route.fulfill({ contentType: 'text/html', body: '<html><body style="margin:0"><div id="app"></div></body></html>' }));
  await page.route(url => url.pathname.startsWith('/api/'), route => route.fulfill({ json: { items: [], has_more: false } }));
  await page.goto('/__document-dock');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/documentDock.js')).mount());
  await expect(page.getByRole('button', { name: 'Dokument wenden – Zusammenhänge anzeigen' })).toBeVisible();
}
const settled = page => expect(page.locator('.document-flip')).not.toHaveClass(/document-flip--turning/);
test('turn control fades with the toolbar on hover and remains keyboard accessible on both sides', async ({ page }) => {
  await mount(page);
  const flip = page.locator('.document-flip');
  const toggle = page.locator('.document-flip__toggle');
  const toolbar = page.getByRole('toolbar', { name: 'PDF-Steuerung' });
  await page.mouse.move(10, 10);
  await expect(toggle).toHaveCSS('opacity', '0');
  await expect(toggle).toHaveCSS('pointer-events', 'none');
  await expect(toolbar).toHaveCSS('opacity', '0');
  await flip.hover({ position: { x: 12, y: 12 } });
  await expect(toggle).toHaveCSS('opacity', '1');
  await expect(toolbar).toHaveCSS('opacity', '1');
  expect(await toggle.evaluate(el => getComputedStyle(el).transitionDuration.split(',')[0].trim())).toBe('0.16s');
  await toggle.hover();
  await expect(toolbar).toHaveCSS('opacity', '1');
  await page.mouse.move(10, 10);
  await expect(toggle).toHaveCSS('opacity', '0');
  await expect(toolbar).toHaveCSS('opacity', '0');
  await toggle.focus();
  await expect(toggle).toHaveCSS('opacity', '1');
  await expect(toggle).toHaveCSS('pointer-events', 'auto');
  await toggle.press('Enter');
  await settled(page);
  await expect(toggle).toHaveCSS('opacity', '0');
  await flip.hover({ position: { x: 12, y: 12 } });
  await expect(toggle).toHaveCSS('opacity', '1');
  await page.mouse.move(10, 10);
  await expect(toggle).toHaveCSS('opacity', '0');
});
test('touch devices keep the toolbar and document turn control visible without hover', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5179', hasTouch: true, isMobile: true });
  try {
    const page = await context.newPage();
    await mount(page);
    await expect(page.locator('.document-flip__toggle')).toHaveCSS('opacity', '1');
    await expect(page.getByRole('toolbar', { name: 'PDF-Steuerung' })).toHaveCSS('opacity', '1');
  } finally { await context.close(); }
});
test('turns the actual sheet to a useful back, returns with Escape and keeps PDF and fields mounted', async ({ page }) => {
  await mount(page);
  await page.getByRole('button', { name: 'Dokumentdetails umschalten' }).click();
  const name = page.getByLabel('Dokumentname', { exact: true });
  await name.fill('Mein unveränderter Entwurf');
  await name.evaluate(el => { window.originalField = el; });
  await page.locator('.pdf-preview').evaluate(el => { window.originalPdfPreview = el; });
  await clickDocumentTurn(page);
  await expect.poll(() => page.locator('.document-flip__snapshot canvas').count()).toBeGreaterThan(0);
  await expect(page.locator('.document-flip__live')).toHaveAttribute('inert', '');
  await settled(page);
  const reverse = page.getByRole('region', { name: 'Zusammenhänge zum Dokument' });
  await expect(reverse).toBeFocused();
  await expect(reverse.locator('.document-flip__heading p')).toHaveText('Teilnahmebestätigung · Gestaltungsseminar · Nordlicht Akademie · 2 Seiten');
  await page.evaluate(() => { window.dock.form.correspondent = ''; });
  await expect(reverse.locator('.document-flip__heading p')).toHaveText('Teilnahmebestätigung · Gestaltungsseminar · 2 Seiten');
  await page.evaluate(() => { window.dock.form.correspondent = 'nordlicht'; });
  for (const title of ['Ähnliche Dokumente', 'Verknüpfte Notizen', 'Lernmarkierungen']) await expect(reverse.getByRole('heading', { name: new RegExp(title) })).toBeVisible();
  await expect(reverse.locator('.document-section-card--empty')).toHaveCount(3);
  await expect(reverse.locator('.document-section-card__count')).toHaveCount(0);
  await expect(reverse.locator('.document-section-card__empty .v-icon')).toHaveCount(0);
  expect(await reverse.locator('.document-section-card--empty').evaluateAll(cards => cards.reduce((height, card) => height + card.getBoundingClientRect().height, 0))).toBeLessThan(350);
  await expect(reverse.getByRole('button', { name: 'Notiz hinzufügen', exact: true })).toBeVisible();
  await expect(page.locator('.preview-layout__drawer')).toHaveClass(/pm-drawer--collapsed/);
  await expect(page.locator('.preview-layout__drawer')).not.toBeVisible();
  await expect(page.locator('.preview-layout__drawer')).toHaveCSS('height', '0px');
  await expect(page.locator('.preview-layout__drawer')).toHaveAttribute('aria-hidden', 'true');
  const centering = await reverse.evaluate(el => {
    const paper = el.getBoundingClientRect(), area = el.closest('.preview-layout').getBoundingClientRect();
    return { x: Math.abs(paper.x + paper.width / 2 - area.x - area.width / 2),
      y: Math.abs(paper.y + paper.height / 2 - area.y - area.height / 2) };
  });
  expect(centering.x).toBeLessThan(2);
  expect(centering.y).toBeLessThan(2);
  await expect.poll(() => reverse.evaluate(el => el.clientHeight)).toBeGreaterThan(400);
  await expect.poll(() => page.locator('.preview-layout__drawer').evaluate(el => el.getAnimations().filter(animation => animation.playState === 'running').length)).toBe(0);
  await page.screenshot({ path: '/tmp/papermind-document-back-dark.png' });
  await page.evaluate(() => { window.dock.theme = 'light'; });
  await expect(page.locator('.papermind-app')).toHaveAttribute('data-theme', 'light');
  await page.screenshot({ path: '/tmp/papermind-document-back-empty-light.png' });
  await page.keyboard.press('Escape');
  await settled(page);
  await expect(page.getByRole('button', { name: 'Dokument wenden – Zusammenhänge anzeigen' })).toBeFocused();
  await expect(page.locator('.document-flip__live')).not.toHaveAttribute('inert', '');
  await expect(name).toHaveValue('Mein unveränderter Entwurf');
  expect(await name.evaluate(el => el === window.originalField)).toBe(true);
  expect(await page.locator('.pdf-preview').evaluate(el => el === window.originalPdfPreview)).toBe(true);
  await expect(page.locator('.preview-layout__drawer')).toHaveClass(/pm-drawer--expanded/);
  await expect(page.locator('.preview-layout__drawer')).toBeVisible();
  await expect(page.locator('.preview-layout__drawer')).not.toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('.document-flip__snapshot canvas')).toHaveCount(0);
});
test('loads connections on the back, opens their targets and clears the previous document', async ({ page }) => {
  await mount(page);
  let requests = 0;
  await page.route('**/api/documents/*/related?limit=5', route => {
    requests++;
    return route.fulfill({ json: { items: [{ id: 'other-document', title: 'Police.pdf', same_correspondent: true, shared_tag_count: 1, shared_tags: ['Vertrag'] }] } });
  });
  await page.route('**/api/notes?**', route => route.fulfill({ json: { items: [{ id: 'note-a', title: 'Meine Notiz', preview: 'Ein Gedanke' }] } }));
  await page.route('**/api/documents/*/learn-highlights', route => route.fulfill({ json: { items: [{ id: 'highlight-a', note_id: 'note-a', quote: 'Wichtige Stelle', color: 'important', page: 1, note_title: 'Meine Notiz' }] } }));
  expect(requests).toBe(0);
  await clickDocumentTurn(page);
  await settled(page);
  const reverse = page.getByRole('region', { name: 'Zusammenhänge zum Dokument' });
  await reverse.getByRole('button', { name: /Meine Notiz Ein Gedanke/ }).click();
  expect(await page.evaluate(() => window.dock.lastOpenedNote)).toBe('note-a');
  await reverse.getByRole('button', { name: /Wichtige Stelle/ }).click();
  expect(await page.evaluate(() => window.dock.lastOpenedHighlight.id)).toBe('highlight-a');
  await reverse.getByRole('button', { name: 'Notiz hinzufügen', exact: true }).click();
  expect(await page.evaluate(() => window.dock.createdNote)).toBe(true);
  await reverse.getByRole('button', { name: /Police/ }).click();
  await expect.poll(() => page.evaluate(() => window.dock.lastRelatedDocument)).toBe('other-document');
  await expect(page.locator('.document-flip')).toHaveClass(/document-flip--back/);
  await expect(page.locator('.document-flip__snapshot canvas')).toHaveCount(0);
});
test('the drawer slides in during the return turn and the sheet lands on the fitted PDF', async ({ page }) => {
  await mount(page);
  await page.getByRole('button', { name: 'Dokumentdetails umschalten' }).click();
  await expect(page.locator('.preview-layout__drawer')).toHaveClass(/pm-drawer--expanded/);
  await clickDocumentTurn(page);
  await settled(page);
  const drawer = page.locator('.preview-layout__drawer');
  await expect(drawer).not.toBeVisible();
  // Hold the returning sheet mid-turn while the real drawer and PDF layout
  // continue moving. This catches a drawer that starts only after the turn.
  await page.evaluate(() => {
    const animate = Element.prototype.animate;
    Element.prototype.animate = function (frames, options) {
      const effect = animate.call(this, frames, options);
      if (this.matches('.document-flip__card')) { effect.pause(); effect.currentTime = options.duration / 2; }
      return effect;
    };
  });
  await clickDocumentTurn(page, true);
  await expect(page.locator('.document-flip')).toHaveClass(/document-flip--turning/);
  await expect(drawer).toBeVisible();
  await expect(drawer).toHaveClass(/pm-drawer--expanded/);
  await expect(drawer).toHaveCSS('opacity', '1');
  await expect(drawer).toHaveAttribute('inert', '');
  await expect(drawer).not.toHaveAttribute('aria-hidden', 'true');
  await expect(page.getByRole('button', { name: 'Dokumentdetails umschalten' })).toBeVisible();
  await expect.poll(() => drawer.evaluate(el => el.getAnimations().filter(effect => effect.playState === 'running').length)).toBe(0);
  await expect(page.locator('.document-flip')).toHaveClass(/document-flip--turning/);
  const mismatch = () => page.evaluate(() => {
    const root = document.querySelector('.document-flip').getBoundingClientRect();
    const page = document.querySelector('.document-flip__live .pdf-preview__page').getBoundingClientRect();
    const last = document.querySelector('.document-flip__card').getAnimations()[0].effect.getKeyframes().at(-1);
    return Math.max(Math.abs(parseFloat(last.width) - page.width), Math.abs(parseFloat(last.height) - page.height),
      Math.abs(parseFloat(last.left) - page.left + root.left), Math.abs(parseFloat(last.top) - page.top + root.top));
  });
  await expect.poll(mismatch).toBeLessThan(2);
  await page.evaluate(() => {
    for (const selector of ['.document-flip__card', '.document-flip__paper', '.document-flip__reverse']) {
      document.querySelector(selector).getAnimations().forEach(effect => effect.finish());
    }
  });
  await settled(page);
  await expect(drawer).not.toHaveAttribute('inert', '');
  await expect(page.getByLabel('Dokumentname', { exact: true })).toBeVisible();
});
test('rapid reversals, resizing, reduced motion and the animation switch settle on the requested side', async ({ page }) => {
  await mount(page);
  await page.evaluate(async () => {
    void window.dock.flip.turn(true);
    await new Promise(resolve => setTimeout(resolve, 100));
    void window.dock.flip.turn(false);
    await new Promise(resolve => setTimeout(resolve, 70));
    void window.dock.flip.turn(true);
  });
  await settled(page);
  await expect(page.locator('.document-flip')).toHaveClass(/document-flip--back/);
  await page.evaluate(() => { window.dock.width = 390; window.dock.height = 480; window.dock.theme = 'light'; });
  const reverse = page.getByRole('region', { name: 'Zusammenhänge zum Dokument' });
  await expect.poll(() => reverse.evaluate(el => el.getBoundingClientRect().width)).toBeLessThan(360);
  expect(await reverse.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/papermind-document-back-narrow.png' });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await clickDocumentTurn(page, true);
  await settled(page);
  await clickDocumentTurn(page);
  await settled(page);
  expect(await page.locator('.document-flip__card').evaluate(el => el.getAnimations().length)).toBe(0);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.locator('.papermind-app').evaluate(el => el.classList.add('pm-no-animations'));
  await clickDocumentTurn(page, true);
  await settled(page);
  expect(await page.locator('.document-flip__card').evaluate(el => el.getAnimations().length)).toBe(0);
});

test('turns settle as a continuous damped motion and preserve momentum when reversed', async ({ page }) => {
  await mount(page);
  const sample = fraction => page.evaluate(fraction => {
    for (const selector of ['.document-flip__card', '.document-flip__paper', '.document-flip__reverse']) {
      for (const effect of document.querySelector(selector).getAnimations()) {
        effect.pause(); effect.currentTime = Number(effect.effect.getTiming().duration) * fraction;
      }
    }
    const matrix = new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.document-flip__card')).transform);
    const angle = Math.atan2(-matrix.m13, matrix.m11) * 180 / Math.PI;
    return angle < -90 ? angle + 360 : angle;
  }, fraction);
  await page.evaluate(() => { void window.dock.flip.turn(true); });
  await expect.poll(() => page.locator('.document-flip__paper').evaluate(el => el.getAnimations().length)).toBe(1);
  const peak = await sample(.47);
  expect(peak).toBeGreaterThan(182);
  expect(peak).toBeLessThan(188);
  expect(await sample(.55)).toBeLessThan(peak);
  const reversingAt = await sample(.42);
  await page.evaluate(() => { window.dock.width = 760; });
  await expect.poll(() => page.locator('.document-flip').evaluate(el => el.clientWidth)).toBeLessThan(770);
  await expect.poll(() => page.locator('.document-flip__card').evaluate(el => el.getAnimations()[0].effect.getKeyframes().length)).toBeGreaterThan(50);
  expect(await sample(.42)).toBeCloseTo(reversingAt, 2);
  await page.evaluate(() => { void window.dock.flip.turn(false); });
  await expect.poll(() => page.locator('.document-flip__paper').evaluate(el => el.getAnimations().length)).toBe(1);
  expect(await sample(0)).toBeCloseTo(reversingAt, 2);
  // Inertia briefly continues in the old direction before the sheet reverses.
  expect(await sample(.002)).toBeGreaterThan(reversingAt);
  const returnPeak = await sample(.47);
  expect(returnPeak).toBeGreaterThan(-8);
  expect(returnPeak).toBeLessThan(-2);
  expect(await sample(1)).toBeCloseTo(0, 1);
  await page.evaluate(() => {
    for (const selector of ['.document-flip__card', '.document-flip__paper', '.document-flip__reverse']) {
      document.querySelector(selector).getAnimations().forEach(effect => effect.finish());
    }
  });
  await settled(page);
  await expect(page.locator('.document-flip')).not.toHaveClass(/document-flip--back/);
});

test('returning remains possible when the PDF fails while showing its back', async ({ page }) => {
  await mount(page);
  await clickDocumentTurn(page);
  await settled(page);
  await page.route('**/__failed-preview.pdf', route => route.fulfill({ status: 404, body: '' }));
  await page.evaluate(() => { window.dock.previewSource = '/__failed-preview.pdf'; });
  await expect(page.locator('.document-flip__live .pdf-preview__placeholder')).toBeAttached();
  await clickDocumentTurn(page, true);
  await settled(page);
  await expect(page.getByText('Vorschau nicht verfügbar', { exact: true })).toBeVisible();
  await expect(page.locator('.document-flip__snapshot canvas')).toHaveCount(0);
});

test('document changes hold the scrolled back until all sections are ready and crossfade them together', async ({ page }) => {
  await mount(page);
  const waiting = new Map();
  const requests = new Set();
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    const id = url.searchParams.get('document_id') || url.pathname.split('/')[3];
    const section = url.pathname.endsWith('/related') ? 'related' : url.pathname.endsWith('/learn-highlights') ? 'highlights' : 'notes';
    if (id === 'document-b') {
      requests.add(section);
      await new Promise(resolve => waiting.set(section, [...(waiting.get(section) || []), resolve]));
    }
    const count = id === 'document-a' ? 8 : 4;
    const items = Array.from({ length: count }, (_, i) => section === 'related'
      ? { id: `${id}-related-${i}`, title: `${id} Verbindung ${i}`, same_correspondent: true }
      : section === 'notes' ? { id: `${id}-note-${i}`, title: `${id} Notiz ${i}`, preview: 'Ein Gedanke' }
        : { id: `${id}-highlight-${i}`, note_id: 'note', quote: `${id} Markierung ${i}`, color: 'important', page: 1 });
    await route.fulfill({ json: { items } });
  });
  try {
    await clickDocumentTurn(page);
    await settled(page);
    const reverse = page.locator('.document-flip__reverse');
    const live = page.locator('.document-flip__back-body > .document-flip__connections');
    await expect(reverse.getByRole('button', { name: /document-a Markierung 7/ })).toBeVisible();
    await reverse.evaluate(el => {
      const notes = el.querySelector('.doc-notes');
      el.scrollTop += notes.getBoundingClientRect().top - el.getBoundingClientRect().top - 30;
    });
    const oldTop = await live.locator('.doc-notes').evaluate(el => el.getBoundingClientRect().top);
    const oldHeight = await page.locator('.document-flip__back-body').evaluate(el => el.getBoundingClientRect().height);
    await page.evaluate(() => { window.dock.documentKey = 'document-b'; window.dock.title = 'Dokument B'; });
    await expect.poll(() => requests.size).toBe(3);
    await expect.poll(() => waiting.get('notes')?.length).toBe(1);
    await expect.poll(() => waiting.get('highlights')?.length).toBe(1);
    await expect(live).toHaveAttribute('inert', '');
    await expect(live).toHaveCSS('opacity', '0');
    const outgoing = page.locator('.document-flip__outgoing');
    expect(await outgoing.locator('.doc-notes').evaluate(el => el.getBoundingClientRect().top)).toBeCloseTo(oldTop, 0);
    expect(await page.locator('.document-flip__back-body').evaluate(el => el.getBoundingClientRect().height)).toBeCloseTo(oldHeight, 0);
    expect(await outgoing.locator('[id]').count()).toBe(0);
    await expect(reverse.getByRole('button', { name: /document-a Notiz 0/ })).toHaveCount(0);
    waiting.get('notes').forEach(resolve => resolve()); waiting.delete('notes');
    waiting.get('highlights').forEach(resolve => resolve()); waiting.delete('highlights');
    await expect(live.getByText('document-b Notiz 0', { exact: true })).toBeAttached();
    await expect(live.getByText('document-b Markierung 0', { exact: true })).toBeAttached();
    await expect(live).toHaveCSS('opacity', '0');
    expect(await outgoing.locator('.doc-notes').evaluate(el => el.getBoundingClientRect().top)).toBeCloseTo(oldTop, 0);
    // Pause at the midpoint to prove there is one shared crossfade rather than
    // another staggered row entrance or a flash of partly loaded content.
    await page.evaluate(() => {
      const animate = Element.prototype.animate;
      Element.prototype.animate = function (frames, options) {
        const effect = animate.call(this, frames, options);
        if (this.matches('.document-flip__connections, .document-flip__outgoing')) {
          effect.pause(); effect.currentTime = options.duration / 2;
        }
        return effect;
      };
    });
    waiting.get('related').forEach(resolve => resolve()); waiting.delete('related');
    await expect(live).toHaveCSS('opacity', '0.5');
    await expect(outgoing).toHaveCSS('opacity', '0.5');
    expect(await live.locator('.doc-notes').evaluate(el => el.getBoundingClientRect().top)).toBeCloseTo(oldTop, 0);
    expect(await live.locator('li').evaluateAll(items => items.every(item => item.getAnimations().length === 0))).toBe(true);
    await page.screenshot({ path: '/tmp/papermind-back-crossfade.png' });
    await page.evaluate(() => {
      document.querySelectorAll('.document-flip__connections, .document-flip__outgoing').forEach(el => el.getAnimations().forEach(effect => effect.finish()));
    });
    await expect(live).not.toHaveAttribute('inert', '');
    await expect(outgoing.locator(':scope > *')).toHaveCount(0);
    await expect(reverse.getByRole('button', { name: /document-b Notiz 0/ })).toBeVisible();
  } finally { waiting.forEach(releases => releases.forEach(resolve => resolve())); }
});

test('back changes settle after errors without motion and allow returning while requests are pending', async ({ page }) => {
  await mount(page);
  await clickDocumentTurn(page);
  await settled(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.route('**/api/**', route => route.fulfill({ status: 500, json: { detail: 'Fehler' } }));
  await page.evaluate(() => { window.dock.documentKey = 'failed-document'; });
  const body = page.locator('.document-flip__back-body');
  await expect(body).toHaveAttribute('aria-busy', 'false');
  await expect(body.getByText('Ähnliche Dokumente konnten nicht geladen werden.', { exact: true })).toBeVisible();
  expect(await body.evaluate(el => el.getAnimations({ subtree: true }).length)).toBe(0);
  const releases = [];
  await page.route('**/api/**', async route => {
    await new Promise(resolve => { releases.push(resolve); });
    await route.fulfill({ json: { items: [] } });
  });
  try {
    await page.evaluate(() => { window.dock.documentKey = 'pending-document'; });
    await expect(body).toHaveAttribute('aria-busy', 'true');
    await clickDocumentTurn(page, true);
    await settled(page);
    await expect(body).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('.document-flip')).not.toHaveClass(/document-flip--back/);
  } finally { releases.forEach(resolve => resolve()); }
});

test('the sheet shadow matches the PDF at handoff and stays continuous through a reversal', async ({ page }) => {
  await mount(page);
  const alpha = shadow => shadow === 'none' ? 0 : Number(shadow.match(/rgba\([^)]*,\s*([\d.]+)\)/)?.[1] ?? 1);
  const original = alpha(await page.locator('.pdf-preview__page').first().evaluate(el => getComputedStyle(el).boxShadow));
  const restingBack = alpha(await page.locator('.document-flip__reverse').evaluate(el => getComputedStyle(el).boxShadow));
  const setProgress = fraction => page.evaluate(fraction => {
    for (const selector of ['.document-flip__card', '.document-flip__paper', '.document-flip__reverse']) {
      for (const animation of document.querySelector(selector).getAnimations()) {
        animation.pause();
        animation.currentTime = Number(animation.effect.getTiming().duration) * fraction;
      }
    }
    return ['.document-flip__paper', '.document-flip__reverse'].map(selector => getComputedStyle(document.querySelector(selector)).boxShadow);
  }, fraction);
  await page.evaluate(() => { void window.dock.flip.turn(true); });
  await expect.poll(() => page.locator('.document-flip__paper').evaluate(el => el.getAnimations().length)).toBe(1);
  const first = (await setProgress(0)).map(alpha);
  expect(first[0]).toBeCloseTo(original, 3);
  expect(first[1]).toBeCloseTo(original, 3);
  const halfway = (await setProgress(.3)).map(alpha);
  expect(halfway[0]).toBeGreaterThan(original);
  expect(halfway[0]).toBeLessThan(restingBack);
  expect(halfway[0]).toBeCloseTo(halfway[1], 3);
  await page.evaluate(() => { void window.dock.flip.turn(false); });
  await expect.poll(() => page.locator('.document-flip__paper').evaluate(el => el.getAnimations().length)).toBe(1);
  const reversed = (await setProgress(0)).map(alpha);
  expect(reversed[0]).toBeCloseTo(halfway[0], 3);
  const returning = (await setProgress(.5)).map(alpha);
  expect(returning[0]).toBeLessThan(reversed[0]);
  expect(returning[0]).toBeGreaterThanOrEqual(original);
  const end = (await setProgress(1)).map(alpha);
  expect(end[0]).toBeCloseTo(original, 3);
  await page.evaluate(() => {
    for (const selector of ['.document-flip__card', '.document-flip__paper', '.document-flip__reverse']) {
      document.querySelector(selector).getAnimations().forEach(animation => animation.finish());
    }
  });
  await settled(page);
  expect(alpha(await page.locator('.pdf-preview__page').first().evaluate(el => getComputedStyle(el).boxShadow))).toBeCloseTo(original, 3);
});
