import { test, expect } from '@playwright/test';

async function mountMotion(page, reduced = false) {
  await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' });
  await page.route('**/__document-motion', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app"></div></body></html>' }));
  await page.route(url => url.pathname.startsWith('/api/'), route => route.fulfill({ contentType: 'application/json', body: '[]' }));
  await page.goto('/__document-motion');
  await page.evaluate(async () => {
    const { mount } = await import('/tests/browser/fixtures/documentMotion.js');
    mount();
  });
}

test('preview retains pixels across rapid changes and releases them when ready or failed', async ({ page }) => {
  await mountMotion(page);
  await page.evaluate(() => { window.motion.state.key = 'b'; });
  await expect(page.locator('.preview-swap')).toHaveAttribute('aria-busy', 'true');
  expect(await page.locator('.preview-swap__snapshot canvas').evaluate(el => [...el.getContext('2d').getImageData(0, 0, 1, 1).data])).toEqual([255, 0, 0, 255]);
  await page.evaluate(() => { window.motion.state.key = 'c'; });
  expect(await page.locator('.preview-swap__snapshot canvas').count()).toBe(1);
  await page.evaluate(() => window.motion.reveal());
  await expect(page.locator('.preview-swap')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('.preview-swap__snapshot canvas')).toHaveCount(0);
});

test('list marker moves, scrolling stays quiet, drawer fields follow the shell', async ({ page }) => {
  await mountMotion(page);
  const marker = page.locator('.document-list__selection-marker');
  await expect(marker).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 0, 24)');
  await page.locator('[data-document-id="doc-2"]').click();
  await expect(marker).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 0, 268)');
  await page.evaluate(() => { window.motion.state.open = true; });
  await expect(page.locator('.preview-layout__body')).toHaveCSS('opacity', '1');
  await expect.poll(() => page.locator('.preview-layout__drawer').evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThan(250);
  await page.evaluate(() => { window.motion.state.open = false; });
  await expect(page.locator('.preview-layout__drawer')).toHaveCSS('height', '72px');
  await expect(page.locator('.preview-layout__body')).toHaveAttribute('inert', '');
  await page.evaluate(() => { window.motion.state.filter = 'favorites'; });
  await expect(page.locator('.document-row--reveal').first()).toBeAttached();
  await page.locator('.document-list-shell').evaluate(el => { el.scrollTop = 3000; });
  await expect(page.locator('.document-row--reveal')).toHaveCount(0);
  expect(await page.locator('.document-row').count()).toBeLessThan(100);
});

test('reduced motion skips snapshots and staged list entry', async ({ page }) => {
  await mountMotion(page, true);
  await page.evaluate(() => { window.motion.state.key = 'b'; window.motion.state.filter = 'favorites'; });
  await expect(page.locator('.preview-swap')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('.preview-swap__snapshot canvas')).toHaveCount(0);
  await expect(page.locator('.document-row--reveal')).toHaveCount(0);
  await expect(page.locator('.document-list__selection-marker')).toHaveCSS('transition-duration', '0s');
});


test('the app animation switch skips movement as well', async ({ page }) => {
  await mountMotion(page);
  await page.locator('main').evaluate(el => el.classList.add('pm-no-animations'));
  await page.evaluate(() => { window.motion.state.key = 'b'; window.motion.state.filter = 'favorites'; window.motion.state.open = true; });
  await expect(page.locator('.preview-swap')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('.preview-swap__snapshot canvas')).toHaveCount(0);
  await expect(page.locator('.document-row--reveal')).toHaveCount(0);
  await expect(page.locator('.preview-layout__drawer')).toHaveCSS('transition-duration', '0s');
});
