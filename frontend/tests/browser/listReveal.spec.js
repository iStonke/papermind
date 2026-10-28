import { test, expect } from '@playwright/test';
async function mount(page) {
  await page.route('**/__list-reveal', route => route.fulfill({ contentType: 'text/html', body: '<div id="app"></div>' }));
  await page.goto('/__list-reveal');
  await page.evaluate(async () => { (await import('/tests/browser/fixtures/listReveal.js')).mount(); });
}
const rows = Array.from({ length: 20 }, (_, id) => ({ id, title: `Eintrag ${id}` }));
const running = () => [...document.querySelectorAll('[data-row]')].flatMap(el => el.getAnimations()).filter(a => a.playState === 'running').length;
test('new rows stay invisible until ready and fade in without a visible-to-hidden flash', async ({ page }) => {
  await mount(page);
  const samples = await page.evaluate(async items => {
    const nextTick = window.listRevealNextTick;
    window.listReveal.items = items;
    await nextTick();
    const row = document.querySelector('[data-row="0"]');
    const opacity = () => Number(getComputedStyle(row).opacity);
    const before = [opacity()];
    for (let i = 0; i < 4; i++) {
      await new Promise(requestAnimationFrame);
      before.push(opacity());
    }
    window.listReveal.ready = true;
    await nextTick();
    const during = [];
    const started = performance.now();
    while (performance.now() - started < 650) {
      await new Promise(requestAnimationFrame);
      during.push(opacity());
    }
    return { before, during };
  }, rows);
  expect(samples.before.every(opacity => opacity === 0)).toBe(true);
  expect(samples.during.at(-1)).toBe(1);
  expect(samples.during.every((opacity, index) => index === 0 || opacity >= samples.during[index - 1] - .001)).toBe(true);
});
test('a removal takes over a row without the entrance keeping it visible', async ({ page }) => {
  await mount(page);
  await page.evaluate(items => { window.listReveal.items = items; window.listReveal.ready = true; }, rows);
  await expect.poll(() => page.evaluate(running)).toBeGreaterThan(0);
  await page.locator('[data-row="0"]').evaluate(el => {
    el.style.opacity = '.25';
    el.classList.add('document-row--removing');
  });
  await expect(page.locator('[data-row="0"]')).toHaveCSS('opacity', '0.25');
  expect(await page.locator('[data-row="0"]').evaluate(el => el.getAnimations().length)).toBe(0);
});
test('waits for data, staggers visible items and does not replay on edits or scrolling', async ({ page }) => {
  await mount(page);
  await page.evaluate(items => { window.listReveal.items = items; }, rows);
  expect(await page.evaluate(running)).toBe(0);
  await page.evaluate(() => { window.listReveal.ready = true; });
  await expect.poll(() => page.evaluate(running)).toBeGreaterThan(0);
  const timing = await page.locator('[data-row="1"]').evaluate(el => el.getAnimations().find(a => 'opacity' in a.effect.getKeyframes()[0]).effect.getTiming());
  expect(timing.delay).toBe(55);
  expect(timing.duration).toBe(500);
  expect(await page.locator('[data-row="15"]').evaluate(el => el.getAnimations().length)).toBe(0);
  await expect.poll(() => page.evaluate(running)).toBe(0);
  await page.evaluate(() => { window.listReveal.items[0].title = 'Bearbeitet'; window.listReveal.items.push({ id: 30, title: 'Nachgeladen' }); });
  await expect(page.locator('[data-row="0"]')).toHaveText('Bearbeitet');
  expect(await page.evaluate(running)).toBe(0);
  await page.locator('#list').evaluate(el => { el.scrollTop = 250; });
  expect(await page.evaluate(running)).toBe(0);
});
test('rearms for a new view, waits for hidden lists and cancels on scroll', async ({ page }) => {
  await mount(page);
  await page.evaluate(items => { window.listReveal.hidden = true; window.listReveal.items = items; window.listReveal.ready = true; }, rows);
  expect(await page.evaluate(running)).toBe(0);
  await page.evaluate(() => { window.listReveal.hidden = false; });
  await expect.poll(() => page.evaluate(running)).toBeGreaterThan(0);
  await page.locator('#list').evaluate(el => { el.scrollTop = 20; });
  await expect.poll(() => page.evaluate(running)).toBe(0);
  await page.evaluate(() => { window.listReveal.key = 'another-view'; });
  await expect.poll(() => page.evaluate(running)).toBeGreaterThan(0);
});
test('offscreen lists reveal when shown and pending masks are released when motion is disabled', async ({ page }) => {
  await mount(page);
  await page.evaluate(items => {
    document.querySelector('#app').style.marginTop = '1800px';
    window.listReveal.items = items;
    window.listReveal.ready = true;
  }, rows);
  await expect(page.locator('[data-row="0"]')).toHaveCSS('opacity', '0');
  await page.locator('#list').evaluate(el => el.scrollIntoView());
  await expect.poll(() => page.evaluate(running)).toBeGreaterThan(0);
  await expect.poll(() => page.evaluate(running)).toBe(0);
  await expect(page.locator('[data-row="0"]')).toHaveCSS('opacity', '1');
  await page.evaluate(() => { window.listReveal.ready = false; window.listReveal.key = 'loading'; });
  await expect(page.locator('[data-row="0"]')).toHaveCSS('opacity', '0');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('[data-row="0"]')).toHaveCSS('opacity', '1');
  expect(await page.locator('[data-row="0"]').evaluate(el => el.getAnimations().length)).toBe(0);
});
test('respects both animation settings and reduced motion', async ({ page }) => {
  await mount(page);
  await page.evaluate(items => { window.listReveal.disabled = true; window.listReveal.items = items; window.listReveal.ready = true; }, rows);
  await expect(page.locator('[data-row="0"]')).toBeVisible();
  expect(await page.evaluate(running)).toBe(0);
  await page.evaluate(() => { window.listReveal.disabled = false; window.listReveal.key = 'enabled'; });
  await expect.poll(() => page.evaluate(running)).toBeGreaterThan(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect.poll(() => page.evaluate(running)).toBe(0);
  await page.evaluate(() => { window.listReveal.key = 'reduced'; });
  expect(await page.evaluate(running)).toBe(0);
});
