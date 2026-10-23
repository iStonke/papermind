import { test, expect } from '@playwright/test';
import { mount } from './fixtures/importHarness.js';

async function showAvailablePages(page) {
  await mount(page, { documents: 0, parkedPages: 7 });
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
    for (const button of await page.locator('.isd-dropzone__actions button').all()) {
      await button.scrollIntoViewIfNeeded();
      await expect.poll(() => button.evaluate(isUnclipped), { message: `${width}×${height}: complete button inside its scroll area` }).toBe(true);
    }
    if (width === 1366 && height === 769) await page.screenshot({ path: `/private/tmp/papermind-import-start-options-${theme}.png`, animations: 'disabled' });
  }
  await available.press('Enter');
  await expect(page.locator('.isd-page-card')).toHaveCount(7);
});

async function sampleStartLayout(page, duration = 650) {
  return page.evaluate(async duration => {
    const samples = [];
    const start = performance.now();
    do {
      await new Promise(requestAnimationFrame);
      const rect = selector => document.querySelector(selector).getBoundingClientRect();
      const scene = rect('.isd-dz-scene');
      const front = rect('.isd-dz-sheet--front');
      const title = rect('.isd-dropzone__title');
      const actions = rect('.isd-dropzone__actions');
      const artwork = [...document.querySelectorAll('.isd-dz-scene .isd-dz-sheet, .isd-dz-scene__merge')]
        .filter(element => Number(getComputedStyle(element).opacity) > 0.05);
      samples.push({
        artGap: Math.min(...artwork.map(element => title.top - element.getBoundingClientRect().bottom)),
        textGap: actions.top - rect('.isd-dropzone__text-shell').bottom,
        frontRatio: front.width / scene.width,
        titleTop: title.top, actionsTop: actions.top, width: front.width, height: front.height,
      });
    } while (performance.now() - start < duration);
    return samples;
  }, duration);
}

for (const [width, height] of [[1440, 1000], [1366, 768], [430, 900]]) {
  test(`scan preview grows into the available space and restores the source layout at ${width}×${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await showAvailablePages(page);
    const opening = await sampleStartLayout(page);
    expect(opening.every(frame => frame.artGap >= 12 && frame.textGap >= 12)).toBe(true);
    expect(Math.max(...opening.map(frame => frame.frontRatio)) - Math.min(...opening.map(frame => frame.frontRatio))).toBeLessThan(0.01);
    const initial = opening.at(-1);
    for (const active of [true, false, true, false]) {
      await page.evaluate(active => { window.importFixture.scannerActive.value = active; }, active);
      for (const choice of await page.locator('.isd-dropzone__source-choices > button').all()) {
        if (active) await expect(choice).toBeHidden();
        else await expect(choice).toBeVisible();
      }
      if (active) {
        await expect(page.locator('.isd-dropzone__available-pages')).toBeHidden();
        await expect(page.getByRole('button', { name: 'Scan abbrechen', exact: true })).toBeVisible();
      } else {
        await expect(page.locator('.isd-dropzone__available-pages')).toBeVisible();
      }
      const frames = await sampleStartLayout(page);
      for (const frame of frames) {
        expect(frame.artGap).toBeGreaterThanOrEqual(12);
      }
      const settled = frames.at(-1);
      if (active) {
        expect(settled.width).toBeGreaterThan(initial.width * 1.6);
        const preview = await page.locator('.isd-dz-sheet--front').boundingBox();
        const viewport = await page.locator('.isd-grid-scroll').boundingBox();
        const cancel = await page.getByRole('button', { name: 'Scan abbrechen', exact: true }).boundingBox();
        expect(preview.x).toBeGreaterThanOrEqual(viewport.x);
        expect(preview.x + preview.width).toBeLessThanOrEqual(viewport.x + viewport.width);
        expect(preview.y).toBeGreaterThanOrEqual(viewport.y);
        expect(cancel.y + cancel.height).toBeLessThanOrEqual(viewport.y + viewport.height);
        await page.screenshot({ path: `/private/tmp/papermind-large-scan-${width}.png` });
      } else {
        for (const key of ['titleTop', 'actionsTop', 'width', 'height']) expect(Math.abs(settled[key] - initial[key]), key).toBeLessThan(1);
      }
    }
    await page.screenshot({ path: `/private/tmp/papermind-import-artwork-${width}.png` });
  });
}

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
