import { test, expect } from '@playwright/test';
import { mount } from './fixtures/importHarness.js';

async function showAvailablePages(page) {
  await mount(page, { documents: 0 });
  await page.evaluate(() => {
    const store = window.importFixture.store;
    store.addDocumentFromSource({ sourceFileId: 'saved-layout-source', title: 'Verfügbare Seiten', pageCount: 7 });
    store.parkDraft();
  });
  await expect(page.getByRole('button', { name: '7 verfügbare Seiten öffnen', exact: true })).toBeVisible();
}

function isUnclipped(button) {
  const card = button.closest('.isd-card');
  const scroll = card.querySelector('.isd-grid-scroll').getBoundingClientRect();
  const footer = card.querySelector('.pm-dialog__footer').getBoundingClientRect();
  const bounds = button.getBoundingClientRect();
  return bounds.top >= scroll.top && bounds.bottom <= Math.min(scroll.bottom, footer.top)
    && bounds.left >= scroll.left && bounds.right <= scroll.right
    && [bounds.top + 4, bounds.bottom - 4].every(y => button.contains(document.elementFromPoint((bounds.left + bounds.right) / 2, y)));
}

for (const theme of ['light', 'dark']) test(`all source choices remain fully visible or scrollable in ${theme} import starts`, async ({ page }) => {
  await showAvailablePages(page);
  await page.evaluate(theme => window.importFixture.setTheme(theme), theme);
  const available = page.getByRole('button', { name: '7 verfügbare Seiten öffnen', exact: true });
  for (const [width, height] of [[1280, 720], [1366, 768], [1366, 769], [1440, 800], [1440, 1000], [800, 800], [430, 900], [320, 640], [1280, 540]]) {
    await page.setViewportSize({ width, height });
    await page.locator('.isd-grid-scroll').evaluate(element => { element.scrollTop = 0; });
    if (width >= 800 && height >= 720) await expect.poll(() => available.evaluate(isUnclipped), { message: `${width}×${height}: third choice visible without scrolling` }).toBe(true);
    for (const button of await page.locator('.isd-dropzone__actions > button').all()) {
      await button.scrollIntoViewIfNeeded();
      await expect.poll(() => button.evaluate(isUnclipped), { message: `${width}×${height}: complete button inside its scroll area` }).toBe(true);
    }
    if (width === 1366 && height === 769) await page.screenshot({ path: `/private/tmp/papermind-import-start-options-${theme}.png`, animations: 'disabled' });
  }
  await available.press('Enter');
  await expect(page.locator('.isd-page-card')).toHaveCount(7);
});

test('the available pages choice stays accessible with enlarged layout zoom', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await showAvailablePages(page);
  const available = page.getByRole('button', { name: '7 verfügbare Seiten öffnen', exact: true });
  for (const zoom of [1.25, 1.5]) {
    await page.evaluate(zoom => { document.documentElement.style.zoom = zoom; }, zoom);
    await available.scrollIntoViewIfNeeded();
    await expect.poll(() => available.evaluate(isUnclipped)).toBe(true);
  }
  await available.press('Enter');
  await expect(page.locator('.isd-page-card')).toHaveCount(7);
});
